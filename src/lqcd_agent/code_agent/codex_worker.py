"""Private tool-enabled SDK worker; the Host validates the final file proposal."""
import json
from hashlib import sha256
import os
from pathlib import Path
import signal
import sys
import threading
import time

from lqcd_agent.settings import ApplicationSettings, child_environment, workspace_root


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


def run(job):
    from openai_codex import Codex, CodexConfig, ApprovalMode
    from openai_codex._run import _collect_turn_result
    request = json.loads((job / 'request.json').read_text())
    task, manifest = request['task'], request['manifest']
    workspace = Path(request['workspace'])
    home = job / 'codex-home'
    home.mkdir(mode=0o700, exist_ok=True)
    settings = ApplicationSettings.load()
    workspace_config = workspace_root()
    profile = {':root': 'deny', ':minimal': 'read', ':workspace_roots': {'.': 'write'},
               str(workspace_config / '.venv'): 'read', str(workspace_config / '.runtime'): 'read', ':slash_tmp': 'deny', ':tmpdir': 'write'}
    tool_environment = {'PYTHONDONTWRITEBYTECODE': '1', 'RUFF_CACHE_DIR': str(home/'cache'/'ruff')}
    overrides = ('forced_login_method="api"', 'cli_auth_credentials_store="ephemeral"',
                 'default_permissions="lqcd"',
                 'web_search=' + json.dumps('live' if task['network_policy']['enabled'] else 'disabled'),
                 'permissions.lqcd.filesystem=' + json.dumps(profile).replace(': ', ' = '),
                 'permissions.lqcd.network.enabled=' + str(task['network_policy']['enabled']).lower(),
                 'shell_environment_policy.set=' + json.dumps(tool_environment).replace(': ', ' = '),
                 'project_doc_max_bytes=0',
                 'openai_base_url=' + json.dumps(settings.api_base))
    environment = child_environment()
    environment.update(CODEX_HOME=str(home), CODEX_SQLITE_HOME=str(home), TMPDIR=os.environ['TMPDIR'])
    state = json.loads((job / 'state.json').read_text())
    cancelled = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: cancelled.set())
    signal.signal(signal.SIGINT, lambda *_: cancelled.set())
    turn = None
    schema = {'type': 'object', 'properties': {'files': {'type': 'array', 'items': {'type': 'object',
        'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
        'required': ['path', 'content'], 'additionalProperties': False}}}, 'required': ['files'], 'additionalProperties': False}
    try:
        with Codex(CodexConfig(cwd=str(workspace), env=environment, config_overrides=overrides,
                               client_name='lqcd_agent', client_title='LQCD Agent')) as codex:
            codex.login_api_key(settings.api_key)
            account = codex.account()
            if getattr(getattr(account.account, 'root', account.account), 'type', None) != 'apiKey':
                raise RuntimeError('Application API-key authentication was not selected')
            thread = codex.thread_start(model=settings.coding_model, cwd=str(workspace), approval_mode=ApprovalMode.auto_review)
            state.update(thread_id=thread.id, status='running')
            write_json(job / 'state.json', state)
            base = request['base_files']
            prompt = ('Implement and test the requested program. Use tools and network access when useful. '
                      'Never read credentials or modify original research data. Keep temporary test files outside '
                      'the deliverable workspace and avoid bytecode files. Return the complete UTF-8 contents of changed files '
                      'only in the required JSON schema. Only these write paths are permitted: ' + json.dumps(task['write_paths'])
                      + '\nTask: ' + json.dumps(task['requirements']) + '\nAcceptance: ' + json.dumps(task['acceptance_criteria'])
                      + '\nExisting files: ' + json.dumps(base))
            turn = thread.turn(prompt, output_schema=schema)
            state['turn_id'] = turn.id
            write_json(job / 'state.json', state)
            finished = threading.Event()
            def stop_watch():
                deadline = time.monotonic() + task['tool_policy'][0]['timeout_seconds']
                while not finished.wait(.1):
                    if cancelled.is_set() or time.monotonic() >= deadline:
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
                                if is_tool_item(item):
                                    observed = tools.setdefault(item['id'], {'id': item['id'], 'type': item['type'],
                                        'start_at': time.monotonic()})
                                    observed['sha256'] = sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
                                    if event.method == 'item/completed':
                                        observed['end_at'] = time.monotonic()
                                    state.update(tool_count=len(tools), tool_events=list(tools.values()))
                                    write_json(job / 'state.json', state)
                        yield event
                # Reuse the pinned SDK collector while observing its single event stream.
                result = _collect_turn_result(observed_events(), turn_id=turn.id)
            finally:
                finished.set()
                monitor.join(2)
            if cancelled.is_set():
                state.update(status='cancelled', error='coding_cancelled_or_timed_out')
            else:
                if str(result.status.value) != 'completed':
                    raise RuntimeError('Coding turn did not complete')
                items = [i.model_dump(mode='json', by_alias=True) for i in result.items]
                proposal = json.loads(result.final_response)
                usage = result.usage.model_dump(mode='json', by_alias=True) if result.usage else {}
                write_json(job / 'proposal.json', {'files': proposal['files'], 'usage': usage,
                    'thread_id': thread.id, 'turn_id': turn.id, 'status': str(result.status),
                    'items': items})
                state.update(status='completed')
    except Exception as error:
        # Persist bounded diagnostics after removing application credentials.
        import re
        detail = re.sub(r'sk-[A-Za-z0-9_-]+', '[REDACTED]', str(error).replace(settings.api_key, '[REDACTED]'))
        state.update(status='cancelled' if cancelled.is_set() else 'failed', error=type(error).__name__, error_message=detail[:2000])
    finally:
        state['finished_at'] = time.monotonic()
        write_json(job / 'state.json', state)
    return 0 if state['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(run(Path(sys.argv[1]).resolve()))
