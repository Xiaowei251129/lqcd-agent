"""Private tool-enabled SDK worker; the Host validates the final file proposal."""
from contextlib import ExitStack
import json
from hashlib import sha256
import os
from pathlib import Path
import signal
import sys
import threading
import time

from lqcd_agent.settings import (ApplicationSettings, child_environment, workspace_root,
                                 INPUT_TOKEN_LIMIT, COMPACT_TOKEN_LIMIT)
from .context_gateway import CodingContextGateway
from .schemas import relative_path, within
from .workspace import scan_tree
from lqcd_agent.control.strict_json import loads, require


def write_json(path, value):
    stage = path.with_suffix('.new')
    with stage.open('w') as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    stage.replace(path)


def is_tool_item(item):
    return item['type'] not in {'userMessage', 'reasoning', 'agentMessage', 'plan',
                                'contextCompaction', 'enteredReviewMode', 'exitedReviewMode'}


def written_file_proposal(workspace, task, response):
    """Read SDK-written files into the existing proposal; the Host seals independently."""
    value = loads(response, canonical=False)
    require(type(value) is dict and set(value) == {'files'} and type(value['files']) is list and
            0 < len(value['files']) <= 32, 'Invalid changed-file list')
    paths = []
    for item in value['files']:
        require(type(item) is dict and set(item) == {'path'}, 'Return changed paths only')
        path = item['path']
        relative_path(path)
        require(path not in paths and within(path, task['write_paths']) and
                not within(path, task['forbidden_paths']), 'Changed path escaped task')
        paths.append(path)
    observed = scan_tree(workspace)
    require(all(path in observed and len(observed[path]) <= 128000 for path in paths),
            'Missing or oversized changed file')
    return [{'path': path, 'content': observed[path].decode('utf-8')} for path in paths]


def run(job):
    from openai_codex import Codex, CodexConfig, ApprovalMode
    from openai_codex._run import _collect_turn_result
    request = json.loads((job / 'request.json').read_text())
    task, manifest = request['task'], request['manifest']
    workspace = Path(request['workspace'])
    home = job / 'codex-home'
    home.mkdir(mode=0o700, exist_ok=True)
    temporary = home / 'tmp'
    temporary.mkdir(mode=0o700, exist_ok=True)
    settings = ApplicationSettings.load()
    workspace_config = workspace_root()
    profile = {':root': 'deny', ':minimal': 'read', ':workspace_roots': {'.': 'write'},
               str(workspace_config / '.venv'): 'read', str(workspace_config / '.runtime'): 'read',
               str(Path(sys.base_prefix).resolve()): 'read', ':slash_tmp': 'deny', ':tmpdir': 'write'}
    tool_environment = {'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(temporary),
                        'TMPPREFIX': str(temporary/'zsh'), 'RUFF_CACHE_DIR': str(temporary/'ruff')}
    overrides = ('forced_login_method="api"', 'cli_auth_credentials_store="ephemeral"',
                 'default_permissions="lqcd"',
                 'web_search=' + json.dumps('live' if task['network_policy']['enabled'] else 'disabled'),
                 'permissions.lqcd.filesystem=' + json.dumps(profile).replace(': ', ' = '),
                 'permissions.lqcd.network.enabled=' + str(task['network_policy']['enabled']).lower(),
                 'features.network_proxy=true',
                 'permissions.lqcd.network.domains={"*"="allow"}',
                 'permissions.lqcd.network.proxy_url="http://127.0.0.1:0"',
                 'permissions.lqcd.network.enable_socks5=false',
                 'shell_environment_policy.set=' + json.dumps(tool_environment).replace(': ', ' = '),
                 'project_doc_max_bytes=0',
                 f'model_context_window={INPUT_TOKEN_LIMIT}',
                 f'model_auto_compact_token_limit={COMPACT_TOKEN_LIMIT}',
                 'model_auto_compact_token_limit_scope="total"')
    environment = child_environment()
    environment.update(CODEX_HOME=str(home), CODEX_SQLITE_HOME=str(home), TMPDIR=str(temporary))
    state = json.loads((job / 'state.json').read_text())
    cancelled = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: cancelled.set())
    signal.signal(signal.SIGINT, lambda *_: cancelled.set())
    turn = None
    gateway = None
    schema = {'type': 'object', 'properties': {'files': {'type': 'array', 'items': {'type': 'object',
        'properties': {'path': {'type': 'string'}},
        'required': ['path'], 'additionalProperties': False}}}, 'required': ['files'], 'additionalProperties': False}
    try:
        with ExitStack() as stack:
            gateway = stack.enter_context(CodingContextGateway(settings, job,
                producer_authority=request.get('producer_authority'), task=task))
            overrides += ('openai_base_url=' + json.dumps(gateway.base_url),)
            if request.get('producer_authority') is not None and task['tool_policy'][0].get('spec_id') == 'research-codex':
                from .numerical_trials import NumericalTrials, SERVER, TOOL
                gateway.numerical_trials = NumericalTrials(gateway, workspace, manifest,
                    cancelled=cancelled.is_set)
                overrides += (f'mcp_servers.{SERVER}.url=' + json.dumps(gateway.base_url.removesuffix('/v1') + '/mcp'),
                    f'mcp_servers.{SERVER}.http_headers={{"Authorization"=' + json.dumps('Bearer ' + gateway.token) + '}',
                    f'mcp_servers.{SERVER}.enabled_tools=' + json.dumps([TOOL]),
                    f'mcp_servers.{SERVER}.tools.{TOOL}.approval_mode="approve"',
                    f'mcp_servers.{SERVER}.tool_timeout_sec=' + str(task['tool_policy'][0]['timeout_seconds']))
            codex = stack.enter_context(Codex(CodexConfig(cwd=str(workspace), env=environment, config_overrides=overrides,
                               client_name='lqcd_agent', client_title='LQCD Agent')))
            codex.login_api_key(gateway.token)
            account = codex.account()
            if getattr(getattr(account.account, 'root', account.account), 'type', None) != 'apiKey':
                raise RuntimeError('Application API-key authentication was not selected')
            thread = codex.thread_start(model=settings.coding_model, cwd=str(workspace), approval_mode=ApprovalMode.deny_all)
            state.update(thread_id=thread.id, status='running')
            write_json(job / 'state.json', state)
            prompt = ('Implement and test the requested program. Use tools and network access when useful. '
                      'Never read credentials or modify original research data. Keep temporary test files outside '
                      'the deliverable workspace and avoid bytecode files. Write persistent changes with tools, then return '
                      'only their paths in the required JSON schema; do not copy file contents into the final reply. '
                      f'You have {task["tool_policy"][0]["timeout_seconds"]} seconds for all tools and the final reply. '
                      'Choose bounded synthetic test sizes while honoring the full requested input counts in the program. '
                      'Only these write paths are permitted: ' + json.dumps(task['write_paths'])
                      + '\nTask: ' + json.dumps(task['requirements']) + '\nAcceptance: ' + json.dumps(task['acceptance_criteria'])
                      + '\nExisting workspace files (read with tools as needed): ' + json.dumps(request['base_paths']))
            if gateway.numerical_trials is not None:
                prompt += ('\nUse run_numerical_trial to test the current analysis.py with a small synthetic JSON input. '
                    'The Host runs the fixed scientific Python and retains exact source, input, output and failure evidence. '
                    'Repair implementation defects from this feedback. Trial success is not independent calibration '
                    'or a formal private-data result. Preserve the planned method and full requested production counts; '
                    'report scientific-method changes rather than silently changing the research question.')
            turn = thread.turn(prompt, output_schema=schema)
            state['turn_id'] = turn.id
            write_json(job / 'state.json', state)
            finished = threading.Event()
            deadline = time.monotonic() + task['tool_policy'][0]['timeout_seconds']
            if request.get('producer_authority') is not None:
                from lqcd_agent.control.coordinator import component, read_regular
                host = job.parent.parent
                root = host / component(task['case_id']) / component(task['run_id'])
                goal = loads(read_regular(root / 'root_goal.json'))
                deadline = min(deadline, goal['research_task']['deadline'])
            def stop_watch():
                while not finished.wait(.1):
                    if gateway.failed.is_set() or cancelled.is_set() or time.monotonic() >= deadline:
                        if not gateway.failed.is_set():
                            cancelled.set()
                        try: turn.interrupt()
                        except Exception: pass
                        return
            monitor = threading.Thread(target=stop_watch, daemon=True)
            monitor.start()
            try:
                def observed_events():
                    tools = {}
                    for event in turn.stream():
                        if event.method in ('item/started', 'item/completed'):
                            payload = event.payload
                            if payload.turn_id == turn.id:
                                item = payload.item.model_dump(mode='json', by_alias=True)
                                if item['type'] == 'contextCompaction':
                                    state.setdefault('context_compactions', []).append({
                                        'id': item['id'], 'event': event.method, 'observed_at': time.monotonic()})
                                    write_json(job / 'state.json', state)
                                if is_tool_item(item):
                                    observed = tools.setdefault(item['id'], {'id': item['id'], 'type': item['type'],
                                        'start_at': time.monotonic()})
                                    if item['type'] == 'mcpToolCall':
                                        observed.update(server=item['server'], tool=item['tool'])
                                    observed['sha256'] = sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
                                    if event.method == 'item/completed':
                                        observed['end_at'] = time.monotonic()
                                    state.update(tool_count=len(tools), tool_events=list(tools.values()))
                                    write_json(job / 'state.json', state)
                        elif event.method == 'thread/tokenUsage/updated' and event.payload.turn_id == turn.id:
                            state['usage'] = event.payload.token_usage.model_dump(mode='json', by_alias=True)
                            write_json(job / 'state.json', state)
                        yield event
                # Reuse the pinned SDK collector while observing its single event stream.
                result = _collect_turn_result(observed_events(), turn_id=turn.id)
            finally:
                finished.set()
                monitor.join(2)
            if gateway.failed.is_set():
                raise RuntimeError(gateway.failure_reason)
            if cancelled.is_set():
                state.update(status='cancelled', error='coding_cancelled_or_timed_out')
            else:
                if str(result.status.value) != 'completed':
                    raise RuntimeError('Coding turn did not complete')
                items = [i.model_dump(mode='json', by_alias=True) for i in result.items]
                files = written_file_proposal(workspace, task, result.final_response)
                usage = result.usage.model_dump(mode='json', by_alias=True) if result.usage else {}
                write_json(job / 'proposal.json', {'files': files, 'usage': usage,
                    'thread_id': thread.id, 'turn_id': turn.id, 'status': str(result.status),
                    'items': items})
                state.update(status='completed')
    except Exception as error:
        # Persist bounded diagnostics after removing application credentials.
        import re
        detail = str(error).replace(settings.api_key, '[REDACTED]')
        if gateway is not None:
            detail = detail.replace(gateway.token, '[REDACTED]')
            if gateway.failed.is_set():
                detail = gateway.failure_reason
        detail = re.sub(r'sk-[A-Za-z0-9_-]+', '[REDACTED]', detail)
        state.update(status='cancelled' if cancelled.is_set() else 'failed', error=type(error).__name__, error_message=detail[:2000])
    finally:
        if gateway is not None and gateway.generation_usage_unknown.is_set():
            state['usage_incomplete'] = True
        state['finished_at'] = time.monotonic()
        write_json(job / 'state.json', state)
    return 0 if state['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(run(Path(sys.argv[1]).resolve()))
