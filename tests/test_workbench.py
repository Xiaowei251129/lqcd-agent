"""HTTP admission and hostile/stale clients cannot bypass original control proofs."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import fcntl
import os
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, loads
from lqcd_agent.examples import SyntheticAgent
from lqcd_agent.inspection import host_root, list_runs, read_snapshot
from lqcd_agent.runtime import ApplicationRequest, advance, assemble, execute, submit
from lqcd_agent.workbench.server import create_app
from lqcd_agent.workbench.service import Workbench
from lqcd_agent.workbench.worker import step, worker_active, launch_worker
from tests.support import own


@pytest.fixture
def workbench(tmp_path, monkeypatch):
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(tmp_path))
    directory = tmp_path/'configs'; directory.mkdir()
    (directory/'example.json').write_bytes(canonical_bytes({'schema_version':'0.1', 'case_id':'example',
        'source_kind':'synthetic_placeholder', 'physics_goal':'Offline synthetic acceptance.'}))
    service = Workbench()
    own(host_root(service.host))
    monkeypatch.setattr(service, 'ensure_worker', lambda **kwargs: None)
    return service


def client(service):
    result = TestClient(create_app(service), base_url='http://127.0.0.1')
    session = result.get('/api/session').json()
    result.headers.update({'X-Workbench-Token':session['token'], 'Origin':'http://127.0.0.1'})
    return result


def url(status):
    return '/api/runs/'+status['host']+'/'+status['run_locator']['case_id']+'/'+status['run_locator']['run_id']


def paused(service, workflow='human'):
    return execute(ApplicationRequest('start', host=service.host, workflow=workflow, key='fixture-'+workflow))


def request(status, operation='response'):
    return {'pause':status['active_pause']['pause_id'], 'head':status['execution_head'], 'key':operation,
        'decision':'approve_with_conditions', 'conditions':['Synthetic fixture only'], 'reason':'Approve this synthetic engineering fixture only.'}


def test_http_authentication_strict_input_and_durable_admission(workbench):
    http = client(workbench)
    assert http.get('/').status_code == 200
    assert "script-src 'self'" in http.get('/').headers['content-security-policy']
    assert http.get('/api/runs', headers={'Host':'evil.example'}).status_code == 403
    assert http.get('/api/runs', headers={'Origin':'https://evil.example'}).status_code == 403
    assert http.get('/api/runs', headers={'X-Workbench-Token':'wrong'}).status_code == 403
    body = {'case':'example', 'goal':'Offline only', 'live':False, 'key':'start-once'}
    assert http.post('/api/runs', json={**body,'actor':'admin'}).status_code == 409
    assert http.post('/api/runs', content='{"key":"one","key":"two"}', headers={'Content-Type':'application/json'}).status_code == 409
    response = http.post('/api/runs', json=body)
    assert response.status_code == 202, response.text
    status = response.json()
    snapshot = read_snapshot(host_root(status['host']), status['run_locator'])
    assert status['run_status'] == 'running' and snapshot.can_advance
    assert snapshot.capability['started_intent'] is None
    assert http.get('/api/operations/start-once').json()['run_locator'] == status['run_locator']
    assert len(list_runs(snapshot.host)) == 1


def test_refresh_server_restart_and_duplicate_submission_use_original_operation(workbench, monkeypatch):
    body = {'case':'example', 'goal':'Stable intent', 'live':False, 'key':'lost-ack'}
    first = client(workbench).post('/api/runs', json=body).json()
    original = read_regular(host_root(workbench.host)/first['run_locator']['case_id']/first['run_locator']['run_id']/'execution_history.jsonl')
    restarted = Workbench(workbench.workspace)
    monkeypatch.setattr(restarted, 'ensure_worker', lambda **kwargs: None)
    assert restarted.host == workbench.host
    http = client(restarted)
    assert http.post('/api/runs', json=body).json() == first
    assert http.post('/api/runs', json={**body,'goal':'Changed intent'}).status_code == 409
    for _ in range(2):
        assert http.get(url(first)).status_code == 200
    assert read_regular(host_root(workbench.host)/first['run_locator']['case_id']/first['run_locator']['run_id']/'execution_history.jsonl') == original
    assert len(list_runs(host_root(workbench.host))) == 1


def test_concurrent_submissions_reconcile_one_original_run(workbench):
    body = {'case':'example', 'goal':'Concurrent synthetic intent', 'live':False, 'key':'concurrent'}
    clients = [client(workbench) for _ in range(3)]
    with ThreadPoolExecutor(max_workers=3) as threads:
        responses = list(threads.map(lambda http:http.post('/api/runs',json=body), clients))
    assert all(response.status_code in (202,409) for response in responses)
    http = client(workbench)
    response = http.post('/api/runs',json=body)
    assert response.status_code == 202, response.text
    assert len(list_runs(host_root(workbench.host))) == 1
    assert http.get('/api/operations/concurrent').json()['run_locator'] == response.json()['run_locator']


def test_human_gate_stale_scope_duplicate_and_original_ids(workbench):
    status = paused(workbench)
    http = client(workbench)
    body = request(status)
    view = http.get(url(status)).json()
    assert view['actions'] == {'cancel':True, 'respond':True}
    original = read_snapshot(host_root(workbench.host), status['run_locator'])
    before = read_regular(original.root/'execution_history.jsonl')
    assert http.post(url(status)+'/respond', json={**body,'head':'0'*64}).status_code == 409
    assert http.post(url(status)+'/respond', json={**body,'decision':'approve_anything'}).status_code == 400
    assert http.post(url(status)+'/respond', json={**body,'authorization_scope':['*']}).status_code == 409
    assert read_regular(original.root/'execution_history.jsonl') == before
    first = http.post(url(status)+'/respond', json=body)
    assert first.status_code == 202, first.text
    assert first.json()['run_status'] == 'running'
    snapshot = read_snapshot(host_root(workbench.host), status['run_locator'])
    response, = [r for r in snapshot.records.values if r.get('record_type') == 'human_response' and r['event'] == 'submitted']
    assert response['human_request_id'] == original.state['active_human_request_id']
    assert response['cycle_id'] == original.state['cycle_id']
    assert http.post(url(status)+'/respond', json=body).json() == first.json()
    assert http.post(url(status)+'/respond', json={**body,'key':'stale-tab'}).status_code == 409
    assert http.post(url(status)+'/respond', json={**body,'reason':'Different reason'}).status_code == 409
    done = advance(workbench.host, status['run_locator'])
    assert done['run_status'] == 'completed'
    assert http.post(url(status)+'/respond', json=body).json() == done
    final = read_snapshot(host_root(workbench.host), status['run_locator'])
    assert len([r for r in final.records.values if r.get('record_type') == 'human_response' and r['event'] == 'submitted']) == 1


def test_external_cancel_uses_original_owner_without_workspace_or_credentials(workbench, monkeypatch):
    status = paused(workbench, 'code')
    http = client(workbench)
    body = {k:v for k,v in request(status, 'cancel-once').items() if k in ('pause','head','key')}
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    relocated = workbench.workspace.with_name(workbench.workspace.name+'-relocated')
    workbench.workspace.rename(relocated)
    try:
        response = http.post(url(status)+'/cancel', json=body)
        assert response.status_code == 202, response.text
        assert response.json()['run_status'] == 'halted'
        assert http.post(url(status)+'/cancel', json=body).json() == response.json()
        snapshot = read_snapshot(host_root(workbench.host), status['run_locator'])
        assert snapshot.state.get('active_pause') is None and snapshot.closure['terminal_closure'] == 'committed'
    finally:
        relocated.rename(workbench.workspace)


def test_evidence_inventory_hash_scope_and_workspace_are_enforced(workbench, tmp_path):
    status = paused(workbench)
    http = client(workbench)
    view = http.get(url(status)).json()
    item = view['evidence'][0]
    response = http.get(url(status)+'/evidence/'+item['id'])
    assert response.status_code == 200 and response.json()['sha256'] == item['sha256']
    for identifier in ('0'*64, '.env', '%2e%2e%2f.env'):
        assert http.get(url(status)+'/evidence/'+identifier).status_code == 404
    root = host_root(workbench.host)
    secret = tmp_path/'.env'; secret.write_text('PRIVATE_VALUE=must-not-be-served\n'); secret.chmod(0o600)
    scope = root/'domain/attempt_000001'/status['run_locator']['case_id']/status['run_locator']['run_id']
    scope.mkdir(parents=True)
    redirected = scope/'redirect.json'; redirected.symlink_to(secret)
    with pytest.raises(ControlIntegrityError):
        workbench._member(redirected, scope, sha256(secret.read_bytes()).hexdigest())
    other = root/'domain/attempt_000001/other/run/result.json'; other.parent.mkdir(parents=True)
    other.write_text('{}')
    with pytest.raises(ControlIntegrityError):
        workbench._member(other, scope, sha256(other.read_bytes()).hexdigest())
    member = workbench.evidence(read_snapshot(root, status['run_locator']))[item['id']]['path']
    member.write_bytes(member.read_bytes()+b' ')
    assert http.get(url(status)+'/evidence/'+item['id']).status_code == 409


def test_worker_reopens_admitted_run_and_concludes_without_human_response(workbench):
    body = {'case':'example','goal':'Offline browser acceptance','live':False,'key':'restart-worker'}
    status = client(workbench).post('/api/runs', json=body).json()
    command = [sys.executable,'-B','-m','lqcd_agent.workbench.worker',workbench.host]
    descriptor = os.open(host_root(workbench.host)/'workbench-worker.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        assert worker_active(workbench.host)
        assert subprocess.run(command,capture_output=True,timeout=30).returncode == 0
        assert read_snapshot(host_root(workbench.host), status['run_locator']).capability['started_intent'] is None
    finally:
        os.close(descriptor)
    assert not worker_active(workbench.host)
    processes = [subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
    for process in processes:
        stdout, stderr = process.communicate(timeout=120)
        assert process.returncode == 0, stderr.decode()+stdout.decode()
    snapshot = read_snapshot(host_root(workbench.host), status['run_locator'])
    assert snapshot.state['run_status'] == 'completed' and snapshot.state.get('active_pause') is None
    assert not any(r['record_type'] == 'human_response' for r in snapshot.records.values)
    assert launch_worker(workbench.host, workbench.workspace) is None
    before = read_regular(snapshot.root/'execution_history.jsonl')
    assert subprocess.run([sys.executable,'-B','-m','lqcd_agent.workbench.worker',workbench.host],capture_output=True,timeout=30).returncode == 0
    assert read_regular(snapshot.root/'execution_history.jsonl') == before
    view = client(workbench).get(url(status))
    assert view.status_code == 200 and view.json()['summaries']['method_plan.json']['summary']
    assert view.json()['decision_origin'] == 'system'
    assert view.json()['scientific_outcome'] in ('supported', 'qualified', 'inconclusive')
    assert not view.json()['actions']['respond']


def test_worker_closes_ended_integrity_failure_and_captures_actual_project_outcome(workbench, monkeypatch):
    from lqcd_agent import runtime
    from lqcd_agent.research.projects import ProjectStore
    from lqcd_agent.science import ScientificAgent
    projects = ProjectStore(workbench.workspace)
    project = projects.create('failed-study', 'Failed study', 'Preserve the original integrity boundary.',
        case_config={'schema_version': '0.1', 'case_id': 'failed-study', 'source_kind': 'synthetic_placeholder'})
    admitted = submit(ApplicationRequest('run', host=workbench.host, project=project['id'], key='ended-integrity'))
    calls = []
    class Corrupt(ScientificAgent):
        def run(self, node, context, **kwargs):
            calls.append(node)
            raise ControlIntegrityError('Fixture evidence identity changed.')
    monkeypatch.setattr(runtime, 'scientific_agent',
        lambda host, config, settings, workspace: Corrupt(host, config, workspace=workspace))
    locator = admitted.status['run_locator']
    with pytest.raises(ControlIntegrityError, match='Fixture evidence identity changed'):
        step(workbench.host, locator)
    snapshot = read_snapshot(host_root(workbench.host), locator)
    assert snapshot.state['run_status'] == 'failed' and snapshot.closure['terminal_closure'] == 'committed'
    index = loads(read_regular(snapshot.root/'artifact_index.json'))['current']
    assert all(pointer is None for pointer in index.values())
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in snapshot.records.values)
    captured, = projects.runs(project['id'])
    assert captured['run_status'] == 'failed' and not captured['preliminary']
    assert captured['scientific_outcome'] == 'inconclusive' and captured['decision_origin'] == 'system'
    assert captured['outcome_source'] == 'control_closure'
    original = read_regular(snapshot.root/'execution_history.jsonl')
    assert step(workbench.host, locator) is False and calls == ['method_planner']
    assert read_regular(snapshot.root/'execution_history.jsonl') == original


def test_worker_never_replays_uncertain_started_invocation(workbench):
    class Crash(SyntheticAgent):
        def run(self, *args, **kwargs):
            raise SystemExit(7)
    admitted = submit(ApplicationRequest('start',host=workbench.host,key='uncertain'))
    with closing(Coordinator(host_root(workbench.host), clock=FakeClock(100, 0))) as coordinator:
        runtime, _, _ = assemble(coordinator, Crash())
        with pytest.raises(SystemExit):
            runtime.run(admitted.status['run_locator'])
        capability, = [loads(row[0]) for row in coordinator.connection.execute('SELECT value FROM invocation_capabilities')]
        assert capability['started_intent'] is not None and capability.get('completion_intent') is None
    root = host_root(workbench.host)/admitted.status['run_locator']['case_id']/admitted.status['run_locator']['run_id']
    original = read_regular(root/'execution_history.jsonl')
    with pytest.raises(ControlIntegrityError):
        step(workbench.host, admitted.status['run_locator'])
    with pytest.raises(ControlIntegrityError):
        launch_worker(workbench.host, workbench.workspace)
    assert read_regular(root/'execution_history.jsonl') == original
    http = client(workbench)
    assert http.get(url(admitted.status)).status_code == 409
    listing = http.get('/api/runs').json()
    assert listing[0]['inspection'] == 'unavailable' and listing[0]['run_status'] is None


def test_workspace_and_imported_run_control_boundaries(workbench, tmp_path, monkeypatch):
    status = paused(workbench)
    other = tmp_path/'other-workspace'; other.mkdir()
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(other))
    isolated = Workbench()
    own(host_root(isolated.host))
    assert client(isolated).get(url(status)).status_code == 403
    assert client(isolated).post(url(status)+'/cancel', json={k:v for k,v in request(status).items() if k in ('pause','head','key')}).status_code == 403


def test_cli_and_workbench_share_native_driver_launch_and_credential_boundary(workbench, monkeypatch):
    admitted = submit(ApplicationRequest('run', host=workbench.host,
        case_config=str(workbench.workspace/'configs/example.json'), key='shared-driver'))
    observed = []
    class Process:
        def poll(self):
            return None
    def spawn(argv, **options):
        observed.append((argv, options))
        return Process()
    monkeypatch.setattr('lqcd_agent.workbench.worker.Popen', spawn)
    monkeypatch.setenv('OPENAI_API_KEY', 'must-not-be-exported')
    monkeypatch.setenv('LQCD_AGENT_API_KEY', 'also-must-not-be-exported')
    process = launch_worker(workbench.host, workbench.workspace)
    assert isinstance(process, Process) and len(observed) == 1
    argv, options = observed[0]
    assert argv == [sys.executable, '-B', '-m', 'lqcd_agent.workbench.worker', workbench.host]
    assert options['cwd'] == workbench.workspace and options['start_new_session']
    assert options['env']['LQCD_AGENT_WORKSPACE'] == str(workbench.workspace)
    assert 'OPENAI_API_KEY' not in options['env'] and 'LQCD_AGENT_API_KEY' not in options['env']
    with monkeypatch.context() as patch:
        patch.setattr('lqcd_agent.workbench.worker.worker_active', lambda host: True)
        assert launch_worker(workbench.host, workbench.workspace) is None
    snapshot = read_snapshot(host_root(workbench.host), admitted.status['run_locator'])
    assert snapshot.capability['started_intent'] is None
    assert not any(r.get('event') == 'resource_reserved' for r in snapshot.records.values)


def test_driver_launcher_refuses_foreign_workspace_and_incompatible_build(workbench, tmp_path, monkeypatch):
    admitted = submit(ApplicationRequest('start', host=workbench.host, key='driver-scope'))
    other = tmp_path/'foreign'; other.mkdir()
    with pytest.raises(ControlIntegrityError, match='workspace'):
        launch_worker(workbench.host, other)
    snapshot = read_snapshot(host_root(workbench.host), admitted.status['run_locator'])
    assert snapshot.capability['started_intent'] is None
    monkeypatch.setattr('lqcd_agent.workbench.worker.Popen', lambda *args, **kwargs:
        (_ for _ in ()).throw(AssertionError('Unexpected worker launch')))
    # An incompatible build is never scheduled by this launcher.
    from dataclasses import replace
    original = read_snapshot
    monkeypatch.setattr('lqcd_agent.workbench.worker.read_snapshot', lambda host, locator:
        replace(original(host, locator), fingerprint={**snapshot.fingerprint, 'application_build': '0'*64}))
    assert launch_worker(workbench.host, workbench.workspace) is None
