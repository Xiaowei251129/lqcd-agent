"""Real Host intake and scientific continuation with offline SDK/model fixtures."""
from contextlib import closing
from dataclasses import replace

import pytest

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.research_budget import ResearchBudget
from lqcd_agent.control.strict_json import ControlIntegrityError, loads
from lqcd_agent.inspection import host_root, read_preparation, read_snapshot
from lqcd_agent.research.agent_runtime import ResearchAgentRuntime
from lqcd_agent.research.collaboration import CollaborationAgent
from lqcd_agent.research.projects import ProjectStore
from lqcd_agent.runtime import ApplicationRequest
from lqcd_agent.science import ScientificAgent
from tests.test_research_intake import IntakeModel, fixture_intake_project
from tests.test_scientific_codegen import C2, deliver, install_backend


def completed_intake(workspace, monkeypatch, mode=None):
    from lqcd_agent import runtime
    from lqcd_agent.research import experiments
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(workspace))
    draft = fixture_intake_project(workspace)
    project = ProjectStore(workspace).create(draft['id'], 'Prepare a C2 analysis', draft['goal'], draft['case_config'])
    calls = []
    def agent(host, config, settings, selected_workspace):
        if config.get('schema_version') == '0.1':
            return ScientificAgent(host, config, workspace=selected_workspace)
        return CollaborationAgent(host, config, workspace=selected_workspace, request_timeout_seconds=10,
            runtime_factory=lambda: ResearchAgentRuntime(IntakeModel(calls), max_output_tokens=2048))
    monkeypatch.setattr(runtime, 'scientific_agent', agent)
    install_backend(monkeypatch, C2)
    request = ApplicationRequest('run', project=project['id'], plan_mode=mode,
                                 project_digest=project['sha256'], key='prepare-project')
    if mode == 'auto':
        with monkeypatch.context() as stop:
            stop.setattr(experiments, 'continue_research', lambda *_: None)
            status = runtime.execute(request)
    else:
        status = runtime.execute(request)
    return status, project, calls


def test_preparation_runs_real_sdk_then_admits_scientific_child_with_original_quota(tmp_path, monkeypatch):
    from lqcd_agent import runtime
    from lqcd_agent.research.experiments import continue_research
    status, project, calls = completed_intake(tmp_path, monkeypatch)
    host, parent = host_root(status['host']), status['run_locator']
    snapshot = read_snapshot(host, parent)
    assert status['run_status'] == 'completed' and status['workflow'] == 'intake'
    assert status['preparation']['status'] == 'ready' and status['active_pause'] is None
    assert [row['schema'] for row in calls] == ['IntakePlan']
    assert not any(row.get('attempt_kind') in ('code_agent', 'analysis_engineer', 'scientific_reviewer')
                   for row in snapshot.records.values)
    assert not any(row['record_type'] == 'human_response' for row in snapshot.records.values)
    index = loads((snapshot.root/'artifact_index.json').read_bytes())['current']
    # Find the actual terminal contract without depending on member order.
    member = next(row for row in index['terminal']['members'] if row['logical_name'] == 'memory_update.json')
    terminal = loads((snapshot.root/member['canonical_path']).read_bytes())
    assert not terminal['accepted_result'] and terminal['preparation_status'] == 'ready'
    before = (snapshot.root/'execution_history.jsonl').read_bytes()
    with closing(Coordinator(host, clock=FakeClock(100, 0))) as coordinator:
        quota = ResearchBudget(coordinator, parent).snapshot()
    assert quota['model_calls'] == 1 and quota['charged_tokens'] == 15
    assert status['next_action'] == 'review_plan' and not status['plan_exhausted']
    assert continue_research(status['host'], parent) is None
    from lqcd_agent.research.experiments import continuation_state
    assert continuation_state(snapshot, loads((snapshot.root/'root_goal.json').read_bytes())) == 'settled'
    accept = plan_action(status, project, 'execute')
    with pytest.raises(ControlIntegrityError, match='plan digest changed'):
        runtime.submit(replace(accept, key='stale', plan_digest='0'*64))
    admitted = runtime.submit(accept)
    child = admitted.status['run_locator']
    assert admitted.advance and not runtime.submit(accept).advance
    with pytest.raises(ControlIntegrityError, match='already has a successor'):
        runtime.submit(replace(accept, key='duplicate-accept'))
    child_snapshot = read_snapshot(host, child)
    goal = loads((child_snapshot.root/'root_goal.json').read_bytes())
    assert goal['workflow'] == 'scientific' and goal['preparation']['parent'] == parent
    assert goal['case_config'] == read_preparation(snapshot.root)[0]['case_config']
    assert goal['research_task']['deadline'] == quota['deadline']
    assert ProjectStore(tmp_path).read(project['id']) == project
    with closing(Coordinator(host, clock=FakeClock(100, 0))) as coordinator:
        after = ResearchBudget(coordinator, child).snapshot()
    assert after['id'] == quota['id'] and after['limits'] == quota['limits']
    assert len(after['runs']) == 2 and after['charged_tokens'] == quota['charged_tokens']
    pending = runtime.advance(status['host'], child)
    assert pending['active_pause']['reason'] == 'external_result'
    finished = deliver(pending)
    assert finished['run_status'] == 'completed' and finished['active_pause'] is None
    assert (snapshot.root/'execution_history.jsonl').read_bytes() == before
    captures = ProjectStore(tmp_path).runs(project['id'])
    assert {row['workflow'] for row in captures} == {'intake', 'scientific'}
    assert next(row for row in captures if row['workflow'] == 'intake')['preparation']['status'] == 'ready'


def plan_action(status, project, action):
    return ApplicationRequest('run', host=status['host'], case=status['run_locator']['case_id'],
        intake_parent=status['run_locator']['run_id'], project=project['id'], project_digest=project['sha256'],
        plan_action=action, plan_digest=status['plan_digest'], key=action+'-chosen-plan')


def test_auto_admits_same_sealed_contract_and_reconciles_once(tmp_path, monkeypatch):
    from lqcd_agent.research.experiments import continue_research
    status, _, _ = completed_intake(tmp_path, monkeypatch, mode='auto')
    child = continue_research(status['host'], status['run_locator'])
    assert child and continue_research(status['host'], status['run_locator']) is None
    snap = read_snapshot(host_root(status['host']), child)
    goal = loads((snap.root/'root_goal.json').read_bytes())
    assert goal['preparation']['plan_sha256'] == status['plan_digest']
    assert goal['case_config'] == status['preparation']['case_config']


def test_plan_edit_blocks_stale_execution_and_revision_consumes_parent(tmp_path, monkeypatch):
    from lqcd_agent.runtime import submit
    status, project, _ = completed_intake(tmp_path, monkeypatch)
    revise = plan_action(status, project, 'revise')
    with pytest.raises(ControlIntegrityError, match='Supply scientific feedback'):
        submit(revise)
    from lqcd_agent.runtime import advance
    store = ProjectStore(tmp_path)
    root_run = {**status['run_locator'], 'host': status['host'], 'execution_head': status['execution_head']}
    def note(key, body):
        return store.contribute(project['id'], expected_digest=project['sha256'], key=key,
                                run=root_run, kind='scientific_comment', body=body)['sha256']
    first = note('require-failed-ids', 'Keep every failed fit replica in the diagnostic table.')
    with pytest.raises(ControlIntegrityError, match='inputs changed'):
        submit(plan_action(status, project, 'execute'))
    revised = submit(revise)
    assert revised.advance and revised.status['workflow'] == 'intake'
    assert revised.status['research_task']['deadline'] == status['research_task']['deadline']
    assert revised.status['research_task']['id'] == status['research_task']['id']
    with pytest.raises(ControlIntegrityError, match='already has a successor'):
        submit(replace(revise, key='duplicate-revise'))
    before_turn = note('residuals', 'Include residual inspection for each fit.')
    revision = advance(status['host'], revised.status['run_locator'])
    assert revision['preparation']['scientific_input_sha256'] == [first, before_turn]
    late = note('ancestor-scope', 'Make the identification limit explicit.')
    with pytest.raises(ControlIntegrityError, match='inputs changed'):
        submit(plan_action(revision, project, 'execute'))
    next_draft = submit(replace(plan_action(revision, project, 'revise'), key='add-ancestor-constraint'))
    latest = advance(status['host'], next_draft.status['run_locator'])
    assert latest['preparation']['scientific_input_sha256'] == [first, before_turn, late]
    accepted = submit(plan_action(latest, project, 'execute'))
    assert accepted.advance and accepted.status['workflow'] == 'scientific'


@pytest.mark.parametrize('changed', [True, False])
def test_explicit_renewal_uses_new_root_and_only_executes_unchanged_ready_plan(tmp_path, monkeypatch, changed):
    from lqcd_agent import runtime
    from lqcd_agent.research import experiments
    import lqcd_agent.control.clock as clocks
    status, project, _ = completed_intake(tmp_path, monkeypatch)
    before = status['research_task']
    accept = plan_action(status, project, 'execute')
    renew = plan_action(status, project, 'renew')
    with pytest.raises(ControlIntegrityError, match='original remaining quota'):
        runtime.submit(renew)
    expired = lambda *_: FakeClock(100, before['deadline'])
    monkeypatch.setattr(experiments, 'FakeClock', expired)
    monkeypatch.setattr(clocks, 'FakeClock', expired)
    if changed:
        source = tmp_path/'raw_data/correlator.json'
        source.write_bytes(source.read_bytes().replace(b'937.24681012', b'937.24681013'))
    with pytest.raises(ControlIntegrityError, match='original remaining quota'):
        runtime.submit(accept)
    result = runtime.submit(renew)
    assert result.advance and result.status['workflow'] == ('intake' if changed else 'scientific')
    current = result.status['research_task']
    assert current['id'] != before['id'] and current['runs'][0]['parent'] is None
    assert current['model_calls'] == 0 and current['deadline'] > before['deadline']
    host = host_root(status['host'])
    goal = loads((read_snapshot(host, result.status['run_locator']).root/'root_goal.json').read_bytes())
    assert goal['plan_mode'] == 'review' and goal['plan_origin']['task_id'] == before['id']
    assert goal['plan_origin']['plan_sha256'] == status['plan_digest']
    original = read_snapshot(host, status['run_locator']).status()
    assert original['research_task']['charged_tokens'] == before['charged_tokens']
    assert original['plan_successor'] == result.status['run_locator']
    assert not runtime.submit(renew).advance
    with pytest.raises(ControlIntegrityError, match='already has a successor'):
        runtime.submit(replace(renew, key='duplicate-renew'))
