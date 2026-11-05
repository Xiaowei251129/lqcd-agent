"""Application-owned Codex executor and real process containment."""
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from lqcd_agent.control.coordinator import component, publish_exact, read_regular
from lqcd_agent.control.clock import host_boot_id
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, require
from lqcd_agent.settings import child_environment, workspace_root
from .backend import validate_receipt, validate_result_reference, validate_status
from .schemas import IDENTITY, relative_path, validate_manifest, validate_task, within
from .workspace import WorkspaceProvider, canonical_patch, immutable_git_tree, scan_tree, seal_workspace
from .codex_worker import is_tool_item, write_json


JOBS_DIRECTORY = 'coding_jobs'


def process_identity(pid):
    if sys.platform == 'darwin':
        import ctypes
        import errno
        # Darwin sys/proc_info.h, PROC_PIDTBSDINFO: retain microsecond start identity.
        class BSDInfo(ctypes.Structure):
            _fields_ = [('fields', ctypes.c_uint32 * 12), ('names', ctypes.c_char * 48),
                        ('files_and_group', ctypes.c_uint32 * 6),
                        ('start_seconds', ctypes.c_uint64), ('start_microseconds', ctypes.c_uint64)]
        library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        inspect = library.proc_pidinfo
        inspect.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        inspect.restype = ctypes.c_int
        info = BSDInfo()
        size = inspect(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
        if size == 0 and ctypes.get_errno() == errno.ESRCH:
            return None
        require(size == ctypes.sizeof(info) and info.fields[3] == pid, 'Cannot verify backend PID identity')
        return None if info.fields[1] == 5 else f'{info.start_seconds}:{info.start_microseconds}'
    require(sys.platform == 'linux', 'Unsupported backend process platform')
    try:
        text = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return None if text[0] == 'Z' else text[19]
    except (OSError, IndexError):
        return None


def group_members(group):
    if sys.platform == 'darwin':
        rows = subprocess.check_output(['/bin/ps', '-axo', 'pid=,pgid=,stat='], text=True, timeout=10)
        return [int(pid) for row in rows.splitlines() for pid, pgid, status in [row.split()]
                if int(pgid) == group and not status.startswith('Z')]
    require(sys.platform == 'linux', 'Unsupported backend process platform')
    found = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            fields = (p / 'stat').read_text().rsplit(')', 1)[1].split()
            if fields[0] != 'Z' and int(fields[2]) == group:
                found.append(int(p.name))
        except (OSError, ValueError, IndexError):
            pass
    return found


class CodexCodingBackend:
    kind = 'codex'
    version = '0.163.0'

    def __init__(self, root, workspace_root, *, coordinator=None):
        self.coordinator = coordinator
        self.root, self.workspace_root = Path(root), Path(workspace_root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(self.root == self.root.resolve(), 'Backend root was redirected')
        self.children = {}

    def job(self, operation):
        component(operation)
        return self.root / operation

    def dispatch(self, task_ref, workspace_manifest_ref, producer_operation_id):
        task = validate_task(task_ref).value
        manifest = validate_manifest(workspace_manifest_ref, task).value
        require(task['producer_operation_id'] == producer_operation_id and task['coding_backend_kind'] == self.kind,
                'Codex dispatch identity mismatch')
        boot_id = host_boot_id()
        job = self.job(producer_operation_id)
        if job.exists():
            saved = json.loads((job / 'request.json').read_text())
            require(saved['task'] == task and saved['manifest'] == manifest, 'Conflicting Codex dispatch')
            return self.read_receipt('codex-receipt:' + producer_operation_id)
        producer_authority = None
        if self.coordinator is not None:
            from .external_operation import ExternalDispatch
            from lqcd_agent.control.operations import ExternalControl
            require(self.coordinator.root == self.root.parent and self.coordinator.connection.in_transaction,
                    'Native dispatch requires its original producer transaction')
            value = ExternalControl(self.coordinator).read(self.coordinator.connection, producer_operation_id)
            dispatch = ExternalDispatch(self.coordinator, producer_operation_id,
                value['worker_owner_id'], value['lease_epoch'], self, None, None, None)
            observed, _, _, original_task, original_manifest = dispatch.model_authority(self.coordinator.connection)
            require(original_task == task and original_manifest == manifest, 'Native dispatch source changed')
            producer_authority = {key: observed[key] for key in ('worker_owner_id', 'lease_epoch')}
        else:
            require(not (self.root.parent / '.lqcd/control_operations.sqlite').exists(),
                    'Application Native dispatch requires the original Coordinator')
        job.mkdir(mode=0o700)
        workspace = WorkspaceProvider(self.workspace_root).path(manifest['workspace_id'])
        base = scan_tree(workspace)
        request = {'task': task, 'manifest': manifest, 'workspace': str(workspace),
                   'base_paths': sorted(base)}
        if producer_authority is not None:
            request['producer_authority'] = producer_authority
        write_json(job / 'request.json', request)
        receipt = {'schema_version': '0.1', 'producer_operation_id': producer_operation_id,
            'task_id': task['task_id'], 'task_digest': task['task_digest'], 'workspace_id': manifest['workspace_id'],
            'workspace_manifest_digest': manifest['manifest_digest'], 'backend_kind': self.kind, 'backend_version': self.version,
            'provider_operation_reference': 'codex-job:' + producer_operation_id,
            'provider_thread_reference': None, 'dispatch_status': 'accepted'}
        receipt['receipt_digest'] = digest(receipt)
        publish_exact(job / 'receipt.json', canonical_bytes(validate_receipt(receipt, task, manifest).value))
        write_json(job / 'state.json', {'status': 'accepted', 'created_at': time.monotonic()})
        environment = child_environment()
        from lqcd_agent.control.storage import execution_scratch_root
        environment.update(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(execution_scratch_root()),
                           LQCD_AGENT_WORKSPACE=str(workspace_root()))
        with (job / 'worker.log').open('wb') as log:
            process = subprocess.Popen([sys.executable, '-B', '-m', 'lqcd_agent.code_agent.codex_worker', str(job)],
                env=environment, cwd=self.root, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        self.children[producer_operation_id] = process
        write_json(job / 'process.json', {'pid': process.pid, 'start_ticks': process_identity(process.pid),
            'boot_id': boot_id})
        return receipt

    def lookup(self, producer_operation_id):
        return lookup_codex_job(self.root, producer_operation_id)

    def read_receipt(self, reference):
        require(reference.startswith('codex-receipt:'), 'Invalid Codex receipt')
        return loads(read_regular(self.job(reference.removeprefix('codex-receipt:')) / 'receipt.json'))

    def fetch_result(self, producer_operation_id):
        content = read_regular(self.job(producer_operation_id) / 'backend-result.json')
        return validate_result_reference({'schema_version': '0.1', 'producer_operation_id': producer_operation_id,
            'reference': 'codex-result:' + producer_operation_id, 'digest': sha256(content).hexdigest(), 'size': len(content)}).value

    def read_result(self, reference):
        value = validate_result_reference(reference).value
        require(value['reference'] == 'codex-result:' + value['producer_operation_id'], 'Invalid Codex result')
        data = read_regular(self.job(value['producer_operation_id']) / 'backend-result.json')
        require(len(data) == value['size'] and sha256(data).hexdigest() == value['digest'], 'Codex result changed')
        return data

    def cancel(self, producer_operation_id, typed_reason):
        from lqcd_agent.control.strict_json import text
        text(typed_reason)
        self.stop(producer_operation_id)
        state_path = self.job(producer_operation_id) / 'state.json'
        state = json.loads(state_path.read_text())
        state.update(status='cancelled')
        write_json(state_path, state)
        return self.lookup(producer_operation_id)

    def stop(self, operation):
        path = self.job(operation) / 'process.json'
        if not path.exists():
            return
        identity = json.loads(path.read_text())
        require(identity['boot_id'] == host_boot_id(), 'Foreign backend Host')
        group = identity['pid']
        current = process_identity(group)
        require(current is None or current == identity['start_ticks'], 'Backend PID identity changed')
        for sig, seconds in ((signal.SIGTERM, 2), (signal.SIGKILL, 2)):
            if not group_members(group):
                break
            try: os.killpg(group, sig)
            except ProcessLookupError: pass
            until = time.monotonic() + seconds
            while group_members(group) and time.monotonic() < until:
                time.sleep(.05)
        process = self.children.get(operation)
        if process is not None:
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: pass
        require(not group_members(group), 'Backend process group did not stop')


class ProcessContainment:
    """Actual SDK worker process groups and observed SDK/Host tool usage."""
    def __init__(self, backend):
        self.backend = backend
        self.root = backend.root / 'containment'
        self.root.mkdir(mode=0o700, exist_ok=True)

    def _path(self, operation):
        component(operation)
        return self.root / (operation + '.json')

    def _read(self, operation):
        return json.loads(self._path(operation).read_text())

    def start(self, operation, workspace):
        p = self._path(operation)
        if p.exists():
            require(self._read(operation)['workspace'] == workspace, 'Containment workspace changed')
            return
        write_json(p, {'workspace': workspace, 'revoked': False, 'stopped': False, 'tools': 0})

    def record_tool(self, operation):
        value = self._read(operation)
        require(not value['revoked'], 'Revoked workspace write')
        value['tools'] += 1
        write_json(self._path(operation), value)

    def revoke_writes(self, operation):
        value = self._read(operation); value['revoked'] = True
        write_json(self._path(operation), value)

    def terminate(self, operation):
        self.backend.stop(operation)

    def kill_all(self, operation):
        self.backend.stop(operation)
        value = self._read(operation); value['stopped'] = True
        write_json(self._path(operation), value)

    def drain(self, operation):
        self.backend.stop(operation)

    def proof(self, operation):
        value = self._read(operation)
        path = self.backend.job(operation) / 'process.json'
        empty = not path.exists() or not group_members(json.loads(path.read_text())['pid'])
        return {'termination_or_not_dispatched': 'confirmed' if value['stopped'] and empty else 'unknown',
            'write_lease_revocation': value['revoked'], 'verify_empty': empty, 'bounded_drain': empty,
            'post_stop_stability': value['stopped'] and empty}

    def observed_tool_count(self, operation):
        state = self.backend.job(operation) / 'state.json'
        return self._read(operation)['tools'] + (json.loads(state.read_text()).get('tool_count', 0) if state.exists() else 0)

    def never_started(self, operation):
        return not (self.backend.job(operation) / 'process.json').exists()


def sdk_tool_audit(task, manifest, observations, items, *, stopped_at):
    """Project completed or abandoned SDK invocations after the Host verifies stop."""
    observed = {event['id']: event for event in observations}
    tools = [item for item in items if is_tool_item(item)]
    completed = {item['id']: item for item in tools}
    require(len(observed) == len(observations) and len(completed) == len(tools) and completed.keys() <= observed.keys(),
            'SDK tool observations and final delivery differ')
    audit = []
    for identity, event in observed.items():
        item = completed.get(identity)
        if item is not None:
            require('end_at' in event and event['sha256'] == sha256(json.dumps(item, sort_keys=True).encode()).hexdigest(),
                    'SDK tool completion evidence changed')
            end_at, status, output = event['end_at'], 'completed', digest(item)
        else:
            require('end_at' not in event, 'Completed SDK tool missing from final delivery')
            end_at, status = stopped_at, 'failed'
            output = digest({'started_item_sha256': event['sha256'], 'host_stopped_at': stopped_at})
        require(end_at >= event['start_at'], 'SDK tool clock order changed')
        spec = task['tool_policy'][0]
        audit.append({'tool_event_index': len(audit)+1, 'task_id': task['task_id'],
            'workspace_id': manifest['workspace_id'], 'tool_id': spec['spec_id'],
            'argv_digest': digest(spec['argv']), 'cwd': '.', 'start_at': event['start_at'], 'end_at': end_at,
            'status': status, 'affected_paths': [], 'output_digest': output,
            'resource_usage': {'llm_calls': 1 if not audit else 0, 'tool_calls': 1, 'active_seconds': 0}})
    return audit


def seal_codex_result(backend, coordinator, producer, repository, containment):
    with coordinator.transaction() as db:
        return _seal_codex_result(backend, coordinator, producer, repository, containment, db)


def _seal_codex_result(backend, coordinator, producer, repository, containment, db):
    """Trusted Host applies the bounded proposal, observes stop and constructs evidence."""
    from .external_operation import ExternalProducer, ExternalDispatch
    source = ExternalProducer(coordinator).lookup(producer)
    dispatch = ExternalDispatch(coordinator, producer, source['worker_owner_id'], source['lease_epoch'],
        backend, containment, backend.read_receipt, backend.read_result)
    def fence():
        dispatch._source(db)
    root = coordinator.root / source['run_locator']['case_id'] / source['run_locator']['run_id']
    directory = root / 'code_agent_control' / source['attempt_id']
    task = loads(read_regular(directory / 'code_agent_task.json'))
    manifest = loads(read_regular(directory / 'workspace_manifest.json'))
    job = backend.job(producer)
    if (job / 'backend-result.json').exists():
        return read_regular(job / 'tool-audit.jsonl'), read_regular(job / 'patch.diff')
    fence()
    require(backend.lookup(producer)['status'] == 'completed', 'Coding task is not complete; query status or cancel')
    backend.stop(producer)
    proposal = json.loads((job / 'proposal.json').read_text())
    base = immutable_git_tree(repository, task['base_revision'])
    provider = WorkspaceProvider(coordinator.root / 'code_workspaces')
    witness = source['prestart']['workspace']
    workspace = provider.verify_identity(manifest, witness)
    files = proposal['files']
    require(isinstance(files, list) and 0 < len(files) <= 32, 'Invalid coding proposal size')
    expected = dict(base); seen = set()
    audit = sdk_tool_audit(task, manifest, json.loads((job/'state.json').read_text()).get('tool_events', []),
                           proposal['items'], stopped_at=coordinator._time().monotonic_seconds)
    if 'native_tool_intents' in source:
        admitted_ids = {item['call_id'] or item['id'] for item in source['native_tool_intents']}
        require(all(item['id'] in admitted_ids for item in proposal['items'] if is_tool_item(item)),
                'Native executed a tool without original admission')
    if source.get('numerical_trials'):
        from .numerical_trials import SERVER, TOOL, trial_member
        trial_member(coordinator, task)
        calls = [item for item in proposal['items'] if item['type'] == 'mcpToolCall' and
                 item['server'] == SERVER and item['tool'] == TOOL]
        require(len(calls) >= len(source['numerical_trials']), 'Native tool audit omitted a numerical trial')
        remaining = list(calls)
        for entry in source['numerical_trials']:
            native = next(item for item in source['native_tool_intents']
                          if item['id'] == entry['intent']['native_item_id'])
            match = next((item for item in remaining if item['id'] == native['call_id'] and
                          digest(item['arguments']) == entry['intent']['arguments_sha256']), None)
            require(match is not None, 'Native numerical trial arguments changed')
            remaining.remove(match)
    for change in files:
        require(set(change) == {'path', 'content'}, 'Invalid coding proposal fields')
        path, text = change['path'], change['content']; relative_path(path)
        require(path not in seen and within(path, task['write_paths']) and not within(path, task['forbidden_paths']), 'Coding proposal escaped task')
        require(isinstance(text, str) and len(text.encode()) <= 128000 and '\x00' not in text, 'Invalid code content')
        seen.add(path); expected[path] = text.encode()
    current = scan_tree(workspace)
    require(all(name in expected and content in (base.get(name), expected[name]) for name, content in current.items()), 'Unexpected workspace changes')
    for change in files:
        fence()
        path = workspace / change['path']
        require(path.parent == path.parent.resolve() and path.parent.is_relative_to(workspace), 'Code parent escaped workspace')
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, 'wb', closefd=False) as stream:
                stream.write(change['content'].encode()); stream.flush(); os.fsync(descriptor)
        finally: os.close(descriptor)
        containment.record_tool(producer)
        now = coordinator._time().monotonic_seconds
        spec = task['tool_policy'][0]
        audit.append({'tool_event_index': len(audit)+1, 'task_id': task['task_id'], 'workspace_id': manifest['workspace_id'],
            'tool_id': spec['spec_id'], 'argv_digest': digest(spec['argv']), 'cwd': '.', 'start_at': now, 'end_at': now,
            'status': 'completed', 'affected_paths': [change['path']], 'output_digest': sha256(change['content'].encode()).hexdigest(),
            'resource_usage': {'llm_calls': 1 if not audit else 0, 'tool_calls': 1, 'active_seconds': 0}})
    require(scan_tree(workspace) == expected, 'Applied code differs from proposal')
    audit_bytes = b''.join(canonical_bytes(row)+b'\n' for row in audit)
    containment.revoke_writes(producer); containment.terminate(producer); containment.kill_all(producer); containment.drain(producer)
    sealed_at = coordinator._time().monotonic_seconds
    changes, seal = seal_workspace(provider, task, manifest, witness, base, backend_status='completed',
        stop_proof=containment.proof(producer), tool_audit=audit_bytes, sealed_at=sealed_at, fence=fence)
    publish_exact(directory / 'workspace_seal.json', canonical_bytes(seal))
    patch = canonical_patch(base, expected, changes['changes'])
    receipt = backend.read_receipt('codex-receipt:' + producer)
    value = {**{k: task[k] for k in IDENTITY}, 'schema_version': '0.1', 'result_id': task['attempt_id']+':external_result',
        'task_id': task['task_id'], 'task_digest': task['task_digest'], 'workspace_id': manifest['workspace_id'],
        'workspace_manifest_digest': manifest['manifest_digest'], 'base_revision': task['base_revision'], 'base_tree_digest': task['base_tree_digest'],
        'coding_backend_kind': backend.kind, 'backend_version': backend.version,
        'provider_operation_reference': receipt['provider_operation_reference'], 'provider_thread_reference': receipt['provider_thread_reference'],
        'dispatch_receipt_digest': digest(receipt), 'workspace_seal_digest': seal['seal_digest'], 'change_manifest_digest': changes['change_manifest_digest'],
        'tool_audit_digest': seal['tool_audit_digest'], 'change_blobs': [{'path': c['path'], 'sha256': c['after_sha256']} for c in changes['changes'] if c['after_sha256'] is not None],
        'patch_digest': sha256(patch).hexdigest(), 'declared_status': 'success', 'backend_verification_claims': [],
        'resource_usage': {'llm_calls': 1, 'tool_calls': len(audit), 'verification_commands': 0, 'active_seconds': sealed_at-source['dispatch_started_at']},
        'warnings': [], 'errors': [], 'failure_evidence': None}
    value['result_digest'] = digest(value)
    publish_exact(job / 'tool-audit.jsonl', audit_bytes); publish_exact(job / 'patch.diff', patch)
    fence()
    publish_exact(job / 'backend-result.json', canonical_bytes(value))
    return audit_bytes, patch


def lookup_codex_job(root, producer_operation_id):
    root = Path(root)
    require(root.is_dir() and root == root.resolve(), 'Backend root was redirected')
    component(producer_operation_id)
    job = root/producer_operation_id
    receipt = loads(read_regular(job / 'receipt.json')) if (job / 'receipt.json').exists() else None
    state = json.loads((job / 'state.json').read_text()) if receipt else {}
    status = state.get('status', 'unknown')
    if status == 'accepted' and (job / 'process.json').exists():
        status = 'running'
    if status in ('accepted', 'running') and (job / 'process.json').exists():
        identity = json.loads((job / 'process.json').read_text())
        if process_identity(identity['pid']) != identity['start_ticks']:
            status = 'failed'
    value = {'schema_version': '0.1', 'producer_operation_id': producer_operation_id,
        'backend_kind': CodexCodingBackend.kind, 'backend_version': CodexCodingBackend.version, 'status': status,
        'receipt_reference': 'codex-receipt:' + producer_operation_id if receipt else None,
        'receipt_digest': digest(receipt) if receipt else None, 'queried_at': time.time()}
    return validate_status(value).value
