"""Inspection consumes existing authority and does not assemble executors."""
from hashlib import sha256
from lqcd_agent.inspection import host_root
from tests.support import command


def test_status_never_assembles_or_rewrites_authority(monkeypatch):
    result = command('start', '--key', 'inspection')
    root = host_root(result['host'])
    assert not (root/'example_repository').exists()
    before = {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    import lqcd_agent.runtime as runtime
    def forbidden(*args, **kwargs):
        raise AssertionError('Status must not construct executors or the writer coordinator')
    monkeypatch.setattr(runtime, 'assemble', forbidden)
    monkeypatch.setattr(runtime, 'Coordinator', forbidden)
    queried = runtime.execute(runtime.ApplicationRequest('status', host=result['host'],
        case=result['run_locator']['case_id'], run=result['run_locator']['run_id']))
    assert queried == result
    after = {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    assert before == after
    assert queried['next_action'] == 'archive'


def test_read_schema_guard_rejects_unknown_tables_without_a_host():
    import sqlite3
    import pytest
    from lqcd_agent.control.coordinator import validate_coordinator_schema
    from lqcd_agent.control.strict_json import ControlIntegrityError
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE unknown (value TEXT)')
        with pytest.raises(ControlIntegrityError, match='Unknown or incomplete coordinator schema'):
            validate_coordinator_schema(db, '/unused')


def test_live_job_status_reads_original_namespace_without_backend_construction(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from lqcd_agent.code_agent.backend import validate_receipt
    from lqcd_agent.code_agent.codex_backend import CodexCodingBackend, JOBS_DIRECTORY
    from lqcd_agent.control.strict_json import canonical_bytes, digest
    from lqcd_agent.inspection import RunSnapshot
    # This is a passive view fixture, with no coordinator, worker or model call.
    operation = 'operation'
    root = tmp_path/'run'; root.mkdir()
    job = tmp_path/JOBS_DIRECTORY/operation; job.mkdir(parents=True)
    task = {'producer_operation_id':operation, 'task_id':'task', 'task_digest':digest('task'),
            'coding_backend_kind':'codex', 'backend_version':CodexCodingBackend.version}
    manifest = {'workspace_id':'workspace','manifest_digest':digest('workspace')}
    receipt = {'schema_version':'0.1','producer_operation_id':operation,'task_id':'task',
        'task_digest':task['task_digest'],'workspace_id':'workspace','workspace_manifest_digest':manifest['manifest_digest'],
        'backend_kind':'codex','backend_version':CodexCodingBackend.version,
        'provider_operation_reference':'codex-job:'+operation,'provider_thread_reference':None,'dispatch_status':'accepted'}
    receipt['receipt_digest'] = digest(receipt)
    (job/'receipt.json').write_bytes(canonical_bytes(validate_receipt(receipt,task,manifest).value))
    (job/'state.json').write_bytes(canonical_bytes({'status':'completed'}))
    (root/'root_goal.json').write_bytes(canonical_bytes({'live':True}))
    (root/'input_snapshot.json').write_bytes(canonical_bytes({'kind':'fixture'}))
    pause = {'pause_id':'pause','reason':'external_result'}
    records = SimpleNamespace(values=[{'event':'pause_opened','pause_id':'pause',
        'input_contract':{'producer_operation_id':operation}}])
    snapshot = RunSnapshot(tmp_path,{'case_id':'case','run_id':'run'},root,{},None,records,
        {'run_status':'paused','execution_head':digest('head'),'active_pause':pause})
    before = {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    def forbidden(*args,**kwargs):
        raise AssertionError('Inspection must not construct a Code backend')
    monkeypatch.setattr(CodexCodingBackend,'__init__',forbidden)
    status = snapshot.status()['coding_backend']
    assert status['status'] == 'completed' and status['receipt_reference'] == 'codex-receipt:'+operation
    assert before == {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}

    import pytest
    from lqcd_agent.control.strict_json import ControlIntegrityError
    jobs = tmp_path/JOBS_DIRECTORY
    actual = tmp_path/'original_jobs'
    jobs.rename(actual)
    jobs.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ControlIntegrityError, match='Backend root was redirected'):
        snapshot.status()
