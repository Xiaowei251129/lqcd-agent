"""Real Host intake and scientific continuation with offline SDK/model fixtures."""
from contextlib import closing
from copy import deepcopy

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


def completed_intake(workspace, monkeypatch):
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
    with monkeypatch.context() as stop:
        stop.setattr(experiments, 'continue_research', lambda *_: None)
        status = runtime.execute(ApplicationRequest('run', project=project['id'],
            project_digest=project['sha256'], key='prepare-project'))
    return status, project, calls


def test_preparation_runs_real_sdk_then_admits_scientific_child_with_original_quota(tmp_path, monkeypatch):
    from lqcd_agent import runtime
    from lqcd_agent.research.experiments import continue_research
    status, project, calls = completed_intake(tmp_path, monkeypatch)
    host, parent = host_root(status['host']), status['run_locator']
    snapshot = read_snapshot(host, parent)
    assert status['run_status'] == 'completed' and status['workflow'] == 'intake'
    assert status['preparation']['status'] == 'ready' and status['active_pause'] is None
    assert [row['schema'] for row in calls] == ['ResearchBrief', 'IntakePlan']
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
    assert quota['model_calls'] == 2 and quota['charged_tokens'] == 30
    child = continue_research(status['host'], parent)
    assert child is not None and continue_research(status['host'], parent) is None
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


def test_prepared_contract_cannot_consume_changed_data_or_expired_task(tmp_path, monkeypatch):
    from lqcd_agent.research import experiments
    status, _, _ = completed_intake(tmp_path, monkeypatch)
    parent, host = status['run_locator'], host_root(status['host'])
    source = tmp_path/'raw_data/correlator.json'
    original = source.read_bytes()
    source.write_bytes(original.replace(b'937.24681012', b'937.24681013'))
    with pytest.raises(ControlIntegrityError, match='inputs changed after preparation'):
        experiments.continue_research(status['host'], parent)
    with closing(Coordinator(host, clock=FakeClock(100, 0))) as coordinator:
        before = deepcopy(ResearchBudget(coordinator, parent).snapshot())
    assert len(before['runs']) == 1
    source.write_bytes(original)
    monkeypatch.setattr(experiments, 'FakeClock', lambda *_: FakeClock(100, before['deadline']))
    assert experiments.continue_research(status['host'], parent) is None
    with closing(Coordinator(host, clock=FakeClock(100, 0))) as coordinator:
        after = ResearchBudget(coordinator, parent).snapshot()
    assert len(after['runs']) == 1 and after['deadline'] == before['deadline']
    assert after['model_calls'] == before['model_calls'] and after['charged_tokens'] == before['charged_tokens']
    assert next(iter(after['unexecuted_experiments'].values()))['reason'] == 'research_budget_exhausted'
