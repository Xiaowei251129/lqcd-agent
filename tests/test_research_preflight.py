"""Pre-model research failures retain evidence without inventing resource use."""
from contextlib import closing

import pytest

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.strict_json import digest, loads
from lqcd_agent.graph.nodes import product_diagnostic, product_failure_material
from lqcd_agent.llm.prompts import ContextLimitError
from tests.test_research_collaboration import execute_collaboration


@pytest.mark.parametrize('role', ['method_planner', 'scientific_reviewer'])
def test_request_failure_before_model_reaches_human_with_real_evidence(tmp_path, monkeypatch, role):
    from lqcd_agent.agents import method_planner, scientific_reviewer

    def reject_request(**kwargs):
        raise ContextLimitError('Required scientific evidence does not fit the request budget.')

    module, builder = ((method_planner, 'build_method_planner_request') if role == 'method_planner'
                       else (scientific_reviewer, 'build_scientific_reviewer_request'))
    monkeypatch.setattr(module, builder, reject_request)
    snapshot, calls, _ = execute_collaboration(tmp_path)
    assert snapshot.state['run_status'] == 'paused'
    assert snapshot.state['active_pause']['reason'] == 'human_input'
    assert [call['schema'] for call in calls] == ([] if role == 'method_planner' else
        ['ResearchBrief', 'ResearchBrief', 'method_plan_discussion'])
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    source = index['current']['plan' if role == 'method_planner' else 'review']
    assert source['status'] == 'failed'
    assert index['current']['decision'] is not None and index['current']['terminal'] is None
    assert not any(row['record_type'] == 'human_response' for row in snapshot.records.values)
    records = snapshot.records.values
    assert not any(row.get('event') == 'resource_reserved'
                   and row['payload']['attempt_id'] == source['attempt_id'] for row in records)
    report = next(member for member in source['members'] if member['logical_name'] ==
                  ('method_plan.json' if role == 'method_planner' else 'scientific_review_report.json'))
    assert 'context_limit_exceeded' in (snapshot.root/report['canonical_path']).read_text()
    observed = [row for row in records if row.get('event') == 'failure_observed']
    assert len(observed) == 1
    with closing(Coordinator(snapshot.host, clock=FakeClock(100, 0))) as coordinator:
        fingerprint, derivation, _ = product_failure_material(snapshot.root, source,
            product_diagnostic(snapshot.root, source), records, coordinator)
    assert fingerprint == observed[0]['payload']['fingerprint']
    bindings = derivation['context_bindings']
    assert bindings['tool_ids']['value'] == []
    assert bindings['config_digest']['value'] == digest(
        {'node': role, 'structured_output': True, 'phase': 'before_resource'})
    started = next(row for row in records if row.get('record_type') == 'attempt'
                   and row['event'] == 'started' and row['attempt_id'] == source['attempt_id'])
    assert bindings['config_digest']['inputs'] == [{'kind': 'execution_record', 'head': digest(started),
        'registration_head': None, 'member': None, 'path': ['attempt_kind']}]
