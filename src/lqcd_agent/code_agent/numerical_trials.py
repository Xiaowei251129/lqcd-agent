"""Development-only numerical feedback inside the original Code reservation."""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import threading

from lqcd_agent.control.coordinator import Coordinator, publish_exact, read_regular
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import canonical_bytes, closed, digest, loads, require
from .execution import CandidateExecutionError, execute_candidate
from .external_operation import ExternalDispatch
from .workspace import WorkspaceProvider, scan_tree


SERVER = 'lqcd_numerical'
TOOL = 'run_numerical_trial'
TOOL_SPEC = {'name': TOOL, 'description':
    'Run the current analysis.py on your small synthetic JSON input using the fixed scientific Python. '
    'This is a recorded development trial, not private-data analysis or independent calibration. '
    'The Host supplies the program path, interpreter, sandbox, time and budget. '
    'Include every JSON field your program needs. Return small outputs so feedback is complete.',
    'inputSchema': {'type': 'object', 'properties': {
        'purpose': {'type': 'string', 'maxLength': 1000},
        'input_json': {'type': 'string', 'maxLength': 64000}},
        'required': ['purpose', 'input_json'], 'additionalProperties': False}}


class TrialInputError(ValueError):
    """A correctable model argument error, before authority or execution effects."""


def _input(arguments):
    try:
        closed(arguments, ('purpose', 'input_json'))
        require(type(arguments['purpose']) is str and 0 < len(arguments['purpose']) <= 1000 and
                type(arguments['input_json']) is str and 0 < len(arguments['input_json'].encode()) <= 64000,
                'Numerical trials need bounded synthetic input and purpose')
        payload = loads(arguments['input_json'], canonical=False)
        require(type(payload) is dict, 'Numerical trial input must be a JSON object')
        return payload
    except (ValueError, TypeError, KeyError) as error:
        raise TrialInputError('Supply only purpose (1–1000 characters) and input_json '
                              '(a finite JSON object encoded as at most 64000 UTF-8 bytes).') from error


def _save(coordinator, db, value):
    previous = value['phase_revision']
    value['phase_revision'] += 1
    require(db.execute('UPDATE external_operations SET revision=?,value=? '
        'WHERE external_operation_id=? AND revision=?', (value['phase_revision'], canonical_bytes(value),
            value['producer_operation_id'], previous)).rowcount == 1, 'Numerical trial CAS lost')


def _directory(host, producer, ordinal):
    path = host / 'coding_jobs' / producer / 'numerical_trials' / f'{ordinal:06d}'
    require(path == path.resolve(), 'Numerical trial evidence directory redirected')
    return path


def trial_member(coordinator, task):
    """Reconstruct exact evidence from the producer journal, never a model pass claim."""
    value = ExternalControl(coordinator).read(coordinator.connection, task['producer_operation_id'])
    trials = value.get('numerical_trials', [])
    if not trials:
        return {}
    require(value['task_digest'] == task['task_digest'], 'Numerical trials have a foreign task')
    records = []
    for ordinal, entry in enumerate(trials, 1):
        closed(entry, ('intent', 'receipt_sha256'))
        intent = entry['intent']
        require(intent['ordinal'] == ordinal and intent['task_digest'] == task['task_digest'] and
                intent['producer_operation_id'] == task['producer_operation_id'] and
                entry['receipt_sha256'] is not None, 'Numerical trial is foreign or unsettled')
        directory = _directory(coordinator.root, task['producer_operation_id'], ordinal)
        require(read_regular(directory / 'intent.json') == canonical_bytes(intent), 'Numerical trial intent changed')
        raw = read_regular(directory / 'receipt.json')
        require(sha256(raw).hexdigest() == entry['receipt_sha256'], 'Numerical trial receipt changed')
        receipt = loads(raw)
        require(receipt['intent_sha256'] == digest(intent) and receipt['scientific_acceptance'] is False,
                'Numerical trial receipt lost its scope')
        files = {}
        for name, expected in receipt['files'].items():
            require(name in ('analysis.py', 'input.json', 'stdout.log', 'stderr.log'), 'Unexpected trial evidence path')
            content = read_regular(directory / name)
            require(sha256(content).hexdigest() == expected, 'Numerical trial bytes changed')
            files[name] = content.decode('utf-8')
        require(set(files) == {'analysis.py', 'input.json', 'stdout.log', 'stderr.log'} and
                receipt['files']['analysis.py'] == intent['program_sha256'] and
                receipt['files']['input.json'] == intent['input_sha256'], 'Numerical trial source changed')
        records.append({'intent': intent, 'receipt': receipt, 'files_utf8': files})
    return {'numerical_trials.json': canonical_bytes({'schema_version': '1',
        'kind': 'model_supplied_development_trials', 'scientific_acceptance': False,
        'trials': records})}


class NumericalTrials:
    """A single MCP tool; all execution remains inside the original Host producer."""
    def __init__(self, gateway, workspace, manifest, *, cancelled):
        self.gateway, self.workspace, self.manifest = gateway, Path(workspace), manifest
        self.cancelled = cancelled
        self.lock = threading.Lock()

    def close(self):
        # The gateway is already closed, so the numerical executor's cancellation
        # callback stops its entire process group before the SDK worker exits.
        with self.lock:
            pass

    def _authority(self, coordinator, db):
        gateway = self.gateway
        require(gateway.producer_authority is not None and not gateway.failed.is_set() and
                not gateway._closed and not self.cancelled(), 'Numerical trial lacks live worker authority')
        dispatch = ExternalDispatch(coordinator, gateway.task['producer_operation_id'],
            gateway.producer_authority['worker_owner_id'], gateway.producer_authority['lease_epoch'],
            None, None, None, None)
        value, root, _, task, manifest = dispatch.model_authority(db)
        require(task == gateway.task and manifest == self.manifest, 'Numerical trial task changed')
        goal = loads(read_regular(root / 'root_goal.json'))
        now = coordinator._time().monotonic_seconds
        aggregate = value['prestart']['aggregate']['request']
        deadline = min(value['worker_lease_expires_at'], value['hard_deadline'],
            value['dispatch_started_at'] + aggregate['timeout_seconds'],
            value['dispatch_started_at'] + task['tool_policy'][0]['timeout_seconds'],
            goal['research_task']['deadline'])
        require(now < deadline, 'Numerical trial deadline exhausted')
        program = goal['case_config'].get('generated_program')
        require(type(program) is dict and Path(program['python']).is_absolute(),
                'Numerical trial requires a frozen generated-program interpreter')
        provider = WorkspaceProvider(coordinator.root / 'code_workspaces')
        workspace = provider.verify_identity(manifest, value['prestart']['workspace'])
        require(workspace == self.workspace and 'analysis.py' in task['write_paths'],
                'Numerical trial workspace changed')
        return value, program, deadline - now, aggregate['maximum_charge']['tool_calls']

    def call(self, identifier, arguments):
        payload = _input(arguments)
        request_digest = digest({'id': identifier, 'arguments': arguments})
        request_key = digest(identifier)
        gateway = self.gateway
        host = gateway.job.parent.parent
        require(gateway.job.name == gateway.task['producer_operation_id'] and gateway.job == gateway.job.resolve(),
                'Numerical trial job changed')
        with self.lock, closing(Coordinator(host)) as coordinator:
            with coordinator.transaction() as db:
                value, program, remaining, maximum_tools = self._authority(coordinator, db)
                trials = value.setdefault('numerical_trials', [])
                previous = next((entry for entry in trials if entry['intent']['request_key'] == request_key), None)
                if previous is not None:
                    require(previous['intent']['request_sha256'] == request_digest, 'Numerical trial request key conflicts')
                    require(previous['receipt_sha256'] is not None, 'Unsettled numerical trial cannot be replayed')
                    return self._feedback(_directory(host, gateway.task['producer_operation_id'], previous['intent']['ordinal']),
                                          previous['receipt_sha256'])
                require(all(entry['receipt_sha256'] is not None for entry in trials),
                        'Unsettled numerical trial prevents new effects')
                native = value.get('native_tool_intents', [])
                used = {entry['intent']['native_item_id'] for entry in trials}
                admitted = next((item for item in native if item['type'] == 'function_call' and
                    item['namespace'] == 'mcp__' + SERVER and item['name'] == TOOL and
                    item['arguments_sha256'] == digest(arguments) and item['id'] not in used), None)
                require(admitted is not None and len(native) + len(gateway.task['write_paths']) <= maximum_tools,
                        'Numerical trial lacks original native tool admission')
                timeout = min(program['timeout_seconds'], remaining - 1)
                require(timeout > 1, 'Numerical trial lacks time for execution and settlement')
                source = scan_tree(self.workspace)['analysis.py']
                require(0 < len(source) <= 128000, 'Numerical trial program is oversized')
                intent = {'ordinal': len(trials) + 1, 'producer_operation_id': gateway.task['producer_operation_id'],
                    'task_digest': gateway.task['task_digest'], 'request_sha256': request_digest, 'request_key': request_key,
                    'arguments_sha256': digest(arguments), 'native_item_id': admitted['id'],
                    'purpose': arguments['purpose'], 'program_sha256': sha256(source).hexdigest(),
                    'input_sha256': digest(payload), 'python': program['python'], 'timeout_seconds': timeout,
                    'started_at': coordinator._time().monotonic_seconds,
                    'input_kind': 'model_supplied_development_input'}
                trials.append({'intent': intent, 'receipt_sha256': None})
                _save(coordinator, db, value)
            directory = _directory(host, gateway.task['producer_operation_id'], intent['ordinal'])
            directory.mkdir(mode=0o700, parents=True)
            for name, content in (('intent.json', canonical_bytes(intent)), ('analysis.py', source),
                                  ('input.json', canonical_bytes(payload))):
                publish_exact(directory / name, content)
            with coordinator.transaction() as db:
                self._authority(coordinator, db)
                timeout = intent['started_at'] + intent['timeout_seconds'] - coordinator._time().monotonic_seconds
                require(timeout > 0, 'Numerical trial preparation exhausted its original window')
            status, error = 'succeeded', None
            try:
                _, execution = execute_candidate(source, payload, program['python'], timeout=timeout,
                    cancelled=lambda: self.cancelled() or gateway.failed.is_set() or gateway._closed)
            except CandidateExecutionError as failure:
                status, error, execution = 'failed', str(failure), failure.execution
            files = {'analysis.py': intent['program_sha256'], 'input.json': intent['input_sha256']}
            for name in ('stdout.log', 'stderr.log'):
                content = read_regular(Path(execution['root']) / name)
                files[name] = sha256(content).hexdigest()
                publish_exact(directory / name, content)
            receipt = {'intent_sha256': digest(intent), 'status': status, 'error': error,
                'execution': execution, 'files': files, 'scientific_acceptance': False,
                'finished_at': coordinator._time().monotonic_seconds}
            raw = canonical_bytes(receipt)
            with coordinator.transaction() as db:
                value, _, _, _ = self._authority(coordinator, db)
                entry = value['numerical_trials'][intent['ordinal'] - 1]
                require(entry == {'intent': intent, 'receipt_sha256': None}, 'Numerical trial settlement changed')
                entry['receipt_sha256'] = sha256(raw).hexdigest()
                publish_exact(directory / 'receipt.json', raw)
                _save(coordinator, db, value)
            return self._feedback(directory, sha256(raw).hexdigest())

    @staticmethod
    def _feedback(directory, expected):
        raw = read_regular(directory / 'receipt.json')
        require(sha256(raw).hexdigest() == expected, 'Numerical trial feedback changed')
        receipt = loads(raw)
        output = read_regular(directory / 'stdout.log')
        require(sha256(output).hexdigest() == receipt['files']['stdout.log'], 'Numerical trial output changed')
        return {'status': receipt['status'], 'error': receipt['error'], 'scientific_acceptance': False,
            'evidence_sha256': expected, 'program_sha256': receipt['files']['analysis.py'],
            'input_sha256': receipt['files']['input.json'],
            'output_preview': output[:12000].decode('utf-8', errors='replace'), 'output_complete': len(output) <= 12000,
            'evidence_member': 'numerical_trials.json',
            'scope': 'Development feedback only; complete bytes retained. Formal Analysis and independent review remain required.'}

    def rpc(self, body):
        require(type(body) is dict and body.get('jsonrpc') == '2.0', 'Invalid numerical MCP request')
        method = body.get('method')
        identifier = body.get('id')
        if method == 'notifications/initialized' and identifier is None:
            return None
        require(type(identifier) in (str, int), 'Numerical MCP request needs an identity')
        if method == 'initialize':
            result = {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}},
                      'serverInfo': {'name': SERVER, 'version': '1'}}
        elif method == 'tools/list':
            result = {'tools': [TOOL_SPEC]}
        elif method == 'ping':
            result = {}
        elif method == 'tools/call':
            params = body.get('params', {})
            require(params.get('name') == TOOL and not set(params) - {'name', 'arguments', '_meta'},
                    'Unknown numerical trial tool')
            try:
                feedback = self.call(identifier, params.get('arguments'))
            except TrialInputError as error:
                result = {'content': [{'type': 'text', 'text': json.dumps({
                    'status': 'not_executed', 'reason': 'invalid_trial_arguments', 'correction': str(error)})}],
                    'isError': True}
            else:
                result = {'content': [{'type': 'text', 'text': json.dumps(feedback)}], 'isError': False}
        else:
            return {'jsonrpc': '2.0', 'id': identifier, 'error': {'code': -32601, 'message': 'Unknown method'}}
        return {'jsonrpc': '2.0', 'id': identifier, 'result': result}
