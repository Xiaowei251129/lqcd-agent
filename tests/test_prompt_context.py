"""Prompt limits preserve complete tasks or reject them before provider invocation."""
import json
from pathlib import Path

import pytest

from lqcd_agent.agents.method_planner import run_method_planner
from lqcd_agent.agents.scientific_reviewer import run_scientific_reviewer
from lqcd_agent.llm.base import LLMProviderConfig
from lqcd_agent.llm.prompts import MAX_CONTEXT_CHARS, build_method_planner_request
from tests.test_scientific_reviewer import _write_effective_mass_artifacts


def planner_request(goal):
    return build_method_planner_request(user_goal=goal,
        case_config={'case_id': 'case'}, repo_inventory={'analysis_programs': []})


def test_context_boundary_preserves_goal_constraints_and_schema():
    goal = 'Keep the measured input unchanged.\nVerify "mass" in lattice units: 质量。'
    first = planner_request(goal)
    goal += 'x' * (MAX_CONTEXT_CHARS - len(first.messages[1]['content']))
    request = planner_request(goal)
    content = request.messages[1]['content']
    payload = json.loads(content)
    assert len(content) == MAX_CONTEXT_CHARS
    assert payload['user_goal'] == goal
    assert payload['case_config'] == {'case_id': 'case'}
    assert payload['repo_inventory'] == {'analysis_programs': []}
    assert not {'run_id', 'case_id', 'created_at', 'producer'} & request.json_schema['schema']['properties'].keys()
    assert request.json_schema == first.json_schema
    assert 'truncated' not in payload
    with pytest.raises(ValueError, match='Prompt context exceeds'):
        planner_request(goal + 'x')


@pytest.mark.parametrize('agent', ['method_planner', 'scientific_reviewer'])
def test_oversized_context_records_failure_without_calling_provider(tmp_path, agent):
    class UncalledProvider:
        config = LLMProviderConfig(provider='uncalled')
        calls = 0

        def generate(self, request):
            self.calls += 1
            raise AssertionError('An oversized request must never reach a provider')

    provider = UncalledProvider()
    run_dir, result_path, plan_path = _write_effective_mass_artifacts(
        tmp_path, run_id='run', case_id='case')
    plan = json.loads(plan_path.read_text())
    evidence = 'sensitive evidence must not appear in the error ' * MAX_CONTEXT_CHARS
    plan['warnings'] = [{'message': evidence}]
    plan_path.write_text(json.dumps(plan))
    if agent == 'method_planner':
        result = run_method_planner(user_goal=evidence, case_config={'case_id': 'case'},
            repo_inventory={'analysis_programs': []}, output_dir=run_dir,
            run_id='run', provider=provider)
        artifact_path = result['method_plan_path']
    elif agent == 'scientific_reviewer':
        result = run_scientific_reviewer(run_id='run', case_id='case', run_output_dir=run_dir,
            run_result_path=result_path, method_plan_path=plan_path, provider=provider)
        artifact_path = result['scientific_review_report_path']
    artifact = json.loads(Path(artifact_path).read_text())
    trace = json.loads((run_dir / 'llm_calls' / (agent + '.json')).read_text())
    assert result['status'] == artifact['status'] == 'failed'
    assert provider.calls == 0
    assert artifact['errors'][0]['code'] == trace['errors'][0]['code'] == 'context_limit_exceeded'
    assert trace['status'] == 'failed'
    assert trace['request'] is None and trace['response'] is None
    assert 'sensitive evidence' not in json.dumps(trace)
