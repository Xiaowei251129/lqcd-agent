"""Real Host, native MCP and numerical sandbox checks without paid providers."""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from lqcd_agent.code_agent.context_gateway import CodingContextGateway
from lqcd_agent.code_agent.numerical_trials import NumericalTrials, trial_member
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from lqcd_agent.settings import ApplicationSettings
from tests.test_codex_context_gate import upstream, count_response
from tests.test_sandbox_network import _responses_stream


@pytest.fixture
def trial_producer(tmp_path, monkeypatch):
    from lqcd_agent.control.storage import execution_scratch_root
    from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
    from lqcd_agent.research_codegen import prepare_research
    from lqcd_agent.science import ScientificAgent
    from lqcd_agent.tools.dataset import snapshot_dataset
    from tests.support import mkdtemp
    launch = subprocess.Popen
    def idle(argv, **kwargs):
        if isinstance(argv, (list, tuple)) and 'lqcd_agent.code_agent.codex_worker' in argv:
            return launch([sys.executable, '-I', '-S', '-c', 'import time;time.sleep(240)'], **kwargs)
        return launch(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', idle)
    workspace = tmp_path / 'operator'
    (workspace / 'raw_data').mkdir(parents=True)
    from lqcd_agent.research_evaluation import calibration
    (workspace / 'raw_data' / 'input.json').write_bytes(canonical_bytes(
        {**calibration('c2'), 'private_marker': 'never sent to Code'}))
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(workspace))
    config = {'schema_version': '0.1', 'case_id': 'trial', 'physics_goal': 'Exercise numerical trial feedback.',
        'raw_data_path': 'raw_data/input.json', 'source_kind': 'synthetic',
        'target_observables': ['c2_scientific_result'], 'generated_program': {
            'python': sys.executable, 'parameters': {}, 'timeout_seconds': 120, 'result_kind': 'c2',
            'requirements': ['Read JSON argv[1] and print finite JSON.']}}
    host = Path(mkdtemp(prefix='lqcd-agent-host-', dir=execution_scratch_root()))
    with closing(Coordinator(host)) as coordinator:
        code, analysis = prepare_research(coordinator, config, workspace=workspace, live=True, initialize=True)
        actor = ActorContext('operator', 'human', ('control.internal', 'resume', 'start'))
        runtime = CanonicalProductRuntime(coordinator, worker_id='trial-fixture', actor=actor,
            agent_port=ScientificAgent(host, config, workspace=workspace), code_host=code, analysis_handoff=analysis)
        inputs = {'root_goal': {'goal': config['physics_goal'], 'workflow': 'scientific', 'live': True,
            'workspace': str(workspace), 'case_config': config, 'dataset_snapshot': snapshot_dataset(config, workspace),
            'research_task': {'id': digest(str(host)), 'limits': {'runs': 1, 'model_calls': 8,
                'tokens': 2_000_000, 'seconds': 3600},
                'deadline': coordinator._time().monotonic_seconds + 360, 'parent': None}},
            'input_snapshot': {'kind': 'scientific_case', 'case_config': config}}
        created = runtime.plane.start_run(StartRunRequest('trial', inputs, digest(inputs), 'trial-fixture'), actor=actor)
        locator = created['result']['run_locator']
        runtime.run(locator)
        producer = loads(coordinator.connection.execute('SELECT value FROM external_operations').fetchone()[0])
        job = code.backend.job(producer['producer_operation_id'])
        try:
            request = json.loads((job / 'request.json').read_text())
            yield coordinator, code, runtime, locator, job, request
        finally:
            code.backend.stop(producer['producer_operation_id'])


def trial_gateway(fixture):
    _, _, _, _, job, request = fixture
    gateway = CodingContextGateway(ApplicationSettings(api_key='offline-key'), job,
        producer_authority=request['producer_authority'], task=request['task'])
    gateway.numerical_trials = NumericalTrials(gateway, request['workspace'], request['manifest'],
        cancelled=lambda: False)
    return gateway


def admit(gateway, identifier, arguments):
    with gateway._model_budget() as (budget, fence):
        gateway._admit_tools(budget, fence, 'fixture-' + identifier, [{
            'id': identifier, 'call_id': identifier, 'type': 'function_call',
            'name': 'run_numerical_trial', 'namespace': 'mcp__lqcd_numerical',
            'arguments_sha256': digest(arguments)}])


def test_trial_failure_repair_and_exact_evidence_without_raw_input(trial_producer):
    coordinator, _, _, _, job, request = trial_producer
    path = Path(request['workspace']) / 'analysis.py'
    path.write_text('raise ValueError("deliberate development defect")\n')
    arguments = {'purpose': 'Check the synthetic sum.', 'input_json': '{"values": [2, 3]}'}
    with trial_gateway(trial_producer) as gateway:
        invalid = gateway.numerical_trials.rpc({'jsonrpc': '2.0', 'id': 'bad', 'method': 'tools/call',
            'params': {'name': 'run_numerical_trial', 'arguments': {'purpose': 'Bad JSON', 'input_json': '{'}}})
        assert invalid['result']['isError'] and 'not_executed' in invalid['result']['content'][0]['text']
        admit(gateway, 'first', arguments)
        first = gateway.numerical_trials.call('first', arguments)
        assert first['status'] == 'failed' and 'deliberate development defect' in first['error']
        path.write_text('import json,sys\np=json.load(open(sys.argv[1]));print(json.dumps({"sum":sum(p["values"])}))\n')
        admit(gateway, 'second', arguments)
        second = gateway.numerical_trials.call('second', arguments)
        assert second['status'] == 'succeeded' and json.loads(second['output_preview']) == {'sum': 5}
        assert gateway.numerical_trials.call('second', arguments) == second
        with pytest.raises(ControlIntegrityError, match='key conflicts'):
            gateway.numerical_trials.call('second', {**arguments, 'input_json': '{}'})
    member = trial_member(coordinator, request['task'])['numerical_trials.json']
    assert b'never sent to Code' not in member
    records = loads(member)['trials']
    assert len(records) == 2 and [r['receipt']['status'] for r in records] == ['failed', 'succeeded']
    assert all(r['receipt']['scientific_acceptance'] is False for r in records)
    for record in records:
        for name, text in record['files_utf8'].items():
            assert sha256(text.encode()).hexdigest() == record['receipt']['files'][name]
    (job / 'numerical_trials/000001/stdout.log').write_text('forged')
    with pytest.raises(ControlIntegrityError, match='bytes changed'):
        trial_member(coordinator, request['task'])


@pytest.mark.parametrize('fault', ['epoch', 'unadmitted', 'unsettled'])
def test_trial_refuses_lost_authority_or_budget_before_execution(trial_producer, fault, monkeypatch):
    from lqcd_agent.code_agent import numerical_trials
    coordinator, _, _, _, _, request = trial_producer
    path = Path(request['workspace']) / 'analysis.py'
    path.write_text('print("{}")\n')
    with trial_gateway(trial_producer) as gateway:
        if fault == 'epoch':
            gateway.producer_authority['lease_epoch'] += 1
        elif fault == 'unsettled':
            def crash(*args, **kwargs):
                raise RuntimeError('simulated crash after durable intent')
            monkeypatch.setattr(numerical_trials, 'execute_candidate', crash)
            admit(gateway, 'first', {'purpose': 'Crash test.', 'input_json': '{}'})
            with pytest.raises(RuntimeError, match='durable intent'):
                gateway.numerical_trials.call('first', {'purpose': 'Crash test.', 'input_json': '{}'})
        def forbidden(*args, **kwargs):
            pytest.fail('Unadmitted trial reached the numerical executor')
        monkeypatch.setattr(numerical_trials, 'execute_candidate', forbidden)
        with pytest.raises(ControlIntegrityError):
            gateway.numerical_trials.call('new', {'purpose': 'Must not run.', 'input_json': '{}'})
    if fault == 'unsettled':
        with pytest.raises(ControlIntegrityError, match='unsettled'):
            trial_member(coordinator, request['task'])


def test_native_sdk_calls_host_trial_and_receives_real_numerical_feedback(trial_producer, monkeypatch):
    from lqcd_agent.code_agent import codex_worker
    coordinator, code, runtime, locator, job, request = trial_producer
    from tests.test_scientific_codegen import C2
    program = ('import json,sys\np=json.load(open(sys.argv[1]))\n'
        'if "values" in p:\n print(json.dumps({"sum":sum(p["values"])}));sys.exit()\n' + C2.decode())
    (Path(request['workspace']) / 'analysis.py').write_text(program)
    review_contexts = []
    original = runtime.agent_port.run
    def observe(node, context, *, timeout_seconds):
        if node == 'scientific_reviewer':
            review_contexts.append(context)
        return original(node, context, timeout_seconds=timeout_seconds)
    monkeypatch.setattr(runtime.agent_port, 'run', observe)
    generations = []
    def respond(route, raw):
        if route.endswith('/input_tokens'):
            return count_response(100)
        body = json.loads(raw)
        generations.append(body)
        if len(generations) <= 2:
            if len(generations) == 2:
                assert 'TypeError' in str(body['input']) and 'failed' in str(body['input'])
            namespace = next(tool for tool in body['tools'] if tool.get('name') == 'mcp__lqcd_numerical')
            assert namespace['type'] == 'namespace'
            name = next(tool['name'] for tool in namespace['tools'] if tool['name'] == 'run_numerical_trial')
            items = [{'id': 'fc_trial_' + str(len(generations)), 'type': 'function_call',
                      'call_id': 'call_trial_' + str(len(generations)), 'name': name,
                      'namespace': namespace['name'],
                      'arguments': json.dumps({'purpose': 'Check a synthetic sum.',
                          'input_json': '{"values":["bad"]}' if len(generations) == 1 else '{"values":[2,3]}'}),
                      'status': 'completed'}]
        else:
            assert 'sum' in str(body['input']) and 'succeeded' in str(body['input'])
            text = json.dumps({'files': [{'path': 'analysis.py'}]})
            items = [{'id': 'msg_final', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                      'content': [{'type': 'output_text', 'text': text, 'annotations': [], 'logprobs': []}]}]
        return 200, _responses_stream(items[0]), 'text/event-stream'
    with upstream(respond) as (base, _):
        monkeypatch.setattr(codex_worker.ApplicationSettings, 'load', lambda:
            ApplicationSettings(api_key='offline-key', api_base=base, coding_model='gpt-6.1-terra'))
        before = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
        try:
            assert codex_worker.run(job) == 0, ((job / 'state.json').read_text(),
                [[tool.get('name', tool.get('type')) for tool in body['tools']] for body in generations])
        finally:
            signal.signal(signal.SIGTERM, before[0]); signal.signal(signal.SIGINT, before[1])
    assert len(generations) == 3
    state = json.loads((job / 'state.json').read_text())
    assert state['tool_count'] == 2 and state['tool_events'][0]['type'] == 'mcpToolCall'
    document = loads(trial_member(coordinator, request['task'])['numerical_trials.json'])
    assert document['trials'][0]['files_utf8']['analysis.py'] == program
    assert document['trials'][0]['receipt']['status'] == 'failed'
    assert json.loads(document['trials'][1]['files_utf8']['stdout.log']) == {'sum': 5}
    from lqcd_agent.code_agent.codex_backend import seal_codex_result
    from lqcd_agent.control.pause import ResumeRunRequest
    producer = request['task']['producer_operation_id']
    audit, patch = seal_codex_result(code.backend, coordinator, producer, code.base_repository, code.containment)
    final = code.finalize(producer, tool_audit=audit, patch=patch)
    payload = {'producer_operation_id': producer, 'external_final_digest': final['terminal_evidence_digest']}
    _, records = runtime._records(locator)
    pause = next(row for row in reversed(records.values) if row['record_type'] == 'pause' and row['event'] == 'pause_opened')
    runtime.resume(ResumeRunRequest(locator, pause['pause_id'], 'trial-delivery', 'external_result', payload,
                                   digest(payload)), actor=runtime.actor)
    root = coordinator.root / locator['case_id'] / locator['run_id']
    index = loads((root / 'artifact_index.json').read_bytes())['current']
    assert index['analysis']['status'] == 'success' and index['terminal']['status'] == 'accepted'
    trial = next(member for member in index['code']['members'] if member['logical_name'] == 'numerical_trials.json')
    assert loads((root / trial['canonical_path']).read_bytes()) == document
    assert len(review_contexts) == 1
    reference = {'artifact_id': index['code']['artifact_id'], 'member': trial['canonical_path'], 'sha256': trial['sha256']}
    assert reference in review_contexts[0]['current_evidence']


@pytest.mark.parametrize('mode', ['success', 'cancel', 'timeout'])
def test_numerical_executor_drains_background_processes_before_return(tmp_path, mode):
    from lqcd_agent.code_agent.execution import sandbox_command
    from lqcd_agent.code_agent.codex_backend import process_identity
    marker = tmp_path / 'late-write'
    child = f'import time,pathlib;time.sleep(10);pathlib.Path({str(marker)!r}).write_text("escaped")'
    script = ('import subprocess,sys,time\n'
        f'p=subprocess.Popen([sys.executable,"-I","-B","-c",{child!r}])\n'
        'print(p.pid,flush=True)\n' + ('time.sleep(30)\n' if mode != 'success' else ''))
    started = time.monotonic()
    def run():
        return sandbox_command([sys.executable, '-I', '-B', '-c', script], tmp_path,
            [sys.prefix, sys.base_prefix], timeout=.8 if mode == 'timeout' else 10,
            cancelled=(lambda: time.monotonic() - started > .8) if mode == 'cancel' else None)
    if mode == 'success':
        assert run().exit_code == 0
    else:
        with pytest.raises(InterruptedError if mode == 'cancel' else subprocess.TimeoutExpired):
            run()
    child_pid = int((tmp_path / 'stdout.log').read_text().strip())
    assert process_identity(child_pid) is None and not marker.exists()


def test_mixed_tool_batch_exceeds_allowance_before_native_receives_effects(trial_producer):
    from tests.test_codex_context_gate import call
    coordinator, _, _, _, job, request = trial_producer
    tools = [{'id': 'shell-' + str(i), 'call_id': 'shell-' + str(i), 'type': 'function_call',
              'name': 'shell', 'arguments': '{"command":"touch must-not-exist"}'} for i in range(31)]
    tools.append({'id': 'trial-last', 'call_id': 'trial-last', 'type': 'function_call',
        'name': 'run_numerical_trial', 'namespace': 'mcp__lqcd_numerical',
        'arguments': json.dumps({'purpose': 'No budget remains.', 'input_json': '{}'})})
    def respond(path, raw):
        if path.endswith('/input_tokens'):
            return count_response(100)
        return 200, json.dumps({'object': 'response', 'status': 'completed', 'output': tools,
            'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}}).encode(), 'application/json'
    with upstream(respond) as (base, received):
        with CodingContextGateway(ApplicationSettings(api_key='offline-key', api_base=base), job,
                producer_authority=request['producer_authority'], task=request['task']) as gateway:
            status, body = call(gateway, {'model': gateway.settings.coding_model, 'input': 'fixture'})
            assert status == 422 and b'context_native_tool_admission_failed' in body
            assert b'touch must-not-exist' not in body and b'run_numerical_trial' not in body
            assert gateway.failed.is_set()
    value = loads(coordinator.connection.execute('SELECT value FROM external_operations').fetchone()[0])
    assert not value.get('native_tool_intents') and not value.get('numerical_trials')
