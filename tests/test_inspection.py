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


def observe_sdk_resources(workspace, monkeypatch, observe):
    """Inspect inside actual SDK model/tool effects owned by the real Host."""
    import asyncio
    from dataclasses import replace
    from lqcd_agent.research import collaboration
    from tests import test_research_collaboration as fixtures
    current = {}
    scoped = collaboration.CollaborationAgent.run_scoped
    def run_scoped(self, node, context, **options):
        current.update(host=self.host, locator={key: context['identity'][key] for key in ('case_id', 'run_id')},
                       coordinator=options['port'].leases.coordinator)
        return scoped(self, node, context, **options)
    class InspectingModel(fixtures.CollaborationModel):
        async def get_response(self, *args, **kwargs):
            observe('model', current)
            await asyncio.sleep(.01)
            observe('model', current)
            return await super().get_response(*args, **kwargs)
    build = collaboration.build_tools
    def build_tools(*args, **kwargs):
        result = []
        for tool in build(*args, **kwargs):
            if tool.name == 'read_context':
                original = tool.on_invoke_tool
                async def read(context, arguments, original=original):
                    observe('tool', current)
                    await asyncio.sleep(.01)
                    observe('tool', current)
                    return await original(context, arguments)
                tool = replace(tool, on_invoke_tool=read)
            result.append(tool)
        return result
    monkeypatch.setattr(collaboration.CollaborationAgent, 'run_scoped', run_scoped)
    monkeypatch.setattr(collaboration, 'build_tools', build_tools)
    monkeypatch.setattr(fixtures, 'CollaborationModel', InspectingModel)
    return fixtures.execute_collaboration(workspace)


def test_published_sdk_resource_view_is_read_only_and_never_reexecutes(tmp_path, monkeypatch):
    import pytest
    from lqcd_agent.control.capabilities import ArtifactEffectPort
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.inspection import read_snapshot
    from lqcd_agent.control.strict_json import ControlIntegrityError, digest
    observed, settled_gaps = [], []
    append = ArtifactEffectPort.append_budget
    def append_budget(self, event, payload):
        result = append(self, event, payload)
        if event == 'resource_settled':
            assert payload['actual'] is not None
            _, capability = self.leases.get(self.capability_id)
            identity = capability['authorization']['identity']
            locator = {key: identity[key] for key in ('case_id', 'run_id')}
            with pytest.raises(ControlIntegrityError, match='no single active ordinary resource'):
                read_snapshot(self.leases.coordinator.root, locator)
            settled_gaps.append(payload['resource_operation_id'])
        return result
    monkeypatch.setattr(ArtifactEffectPort, 'append_budget', append_budget)
    def observe(stage, current):
        host, locator, coordinator = (current[key] for key in ('host', 'locator', 'coordinator'))
        root = host/locator['case_id']/locator['run_id']
        names = ('execution_history.jsonl', 'artifact_history.jsonl', 'artifact_index.json',
                 'budget_policy.json', 'root_goal.json', 'input_snapshot.json')
        before = {name: read_regular(root/name) for name in names}
        rows = coordinator.connection.execute('SELECT capability_id,revision,value FROM invocation_capabilities').fetchall()
        control = coordinator.connection.execute('SELECT value FROM run_controls WHERE run_key=?', (digest(locator),)).fetchone()[0]
        snapshot = read_snapshot(host, locator)
        assert snapshot.state['run_status'] == 'running' and snapshot.state['attempt_status'] == 'running'
        assert not snapshot.can_advance and snapshot.capability.get('completion_intent') is None
        assert snapshot.state['execution_event_index'] > snapshot.control['manifest']['execution_event_index']
        assert before == {name: read_regular(root/name) for name in names}
        assert [tuple(row) for row in rows] == [tuple(row) for row in coordinator.connection.execute(
            'SELECT capability_id,revision,value FROM invocation_capabilities')]
        assert coordinator.connection.execute('SELECT value FROM run_controls WHERE run_key=?', (digest(locator),)).fetchone()[0] == control
        observed.append(stage)
    snapshot, calls, _ = observe_sdk_resources(tmp_path, monkeypatch, observe)
    assert set(observed) == {'model', 'tool'} and len(observed) >= 4
    assert settled_gaps and len(set(settled_gaps)) == len(settled_gaps)
    assert len(calls) == 4 and snapshot.state['run_status'] == 'completed'
    assert read_snapshot(snapshot.host, snapshot.locator).status() == snapshot.status()


def test_sdk_resource_view_rejects_forged_intents_sources_and_files(tmp_path, monkeypatch):
    from copy import deepcopy
    import pytest
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
    from lqcd_agent.inspection import read_snapshot
    checked = []
    def observe(stage, current):
        if checked or stage != 'model':
            return
        host, locator, coordinator = (current[key] for key in ('host', 'locator', 'coordinator'))
        root = host/locator['case_id']/locator['run_id']
        cap_row, = coordinator.connection.execute('SELECT capability_id,revision,value FROM invocation_capabilities').fetchall()
        original = loads(cap_row['value'])
        for fault in ('intent_digest', 'unpublished', 'foreign_attempt', 'producer', 'ledger', 'index'):
            changed = deepcopy(original)
            path = None
            before = None
            if fault == 'intent_digest':
                changed['budget_intents'][-1]['intent_digest'] = '0' * 64
            elif fault == 'unpublished':
                changed['budget_intents'][-1]['published'] = False
            elif fault == 'foreign_attempt':
                entry = changed['budget_intents'][-1]
                entry['record']['payload']['attempt_id'] = 'attempt_999999'
                entry['intent_digest'] = digest({key: value for key, value in entry.items()
                                                if key not in ('intent_digest', 'published')})
            elif fault == 'producer':
                changed['authorization']['producer_operation_id'] = 'control_foreign'
                changed['authorization_digest'] = digest(changed['authorization'])
            else:
                path = root/('execution_history.jsonl' if fault == 'ledger' else 'artifact_index.json')
                before = read_regular(path)
                if fault == 'ledger':
                    path.write_bytes(before+b' ')
                else:
                    index = loads(before)
                    index['execution_head'] = '0' * 64
                    path.write_bytes(canonical_bytes(index))
            if path is None:
                with coordinator.transaction() as db:
                    db.execute('UPDATE invocation_capabilities SET value=? WHERE capability_id=?',
                               (canonical_bytes(changed), cap_row['capability_id']))
            try:
                with pytest.raises(ControlIntegrityError):
                    read_snapshot(host, locator)
            finally:
                if path is not None:
                    path.write_bytes(before)
                else:
                    with coordinator.transaction() as db:
                        db.execute('UPDATE invocation_capabilities SET value=? WHERE capability_id=?',
                                   (cap_row['value'], cap_row['capability_id']))
            assert not read_snapshot(host, locator).can_advance
            checked.append(fault)
    snapshot, _, _ = observe_sdk_resources(tmp_path, monkeypatch, observe)
    assert checked == ['intent_digest', 'unpublished', 'foreign_attempt', 'producer', 'ledger', 'index']
    assert snapshot.state['run_status'] == 'completed'
