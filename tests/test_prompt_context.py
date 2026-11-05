"""Complete scientific instructions survive projection; wire tokens are counted later."""
import json

from lqcd_agent.llm.prompts import build_method_planner_request, build_scientific_reviewer_request


def test_context_preserves_long_goal_constraints_and_schema():
    goal = 'Keep measured inputs unchanged; mass units are lattice units: 质量。' * 200
    config = {'case_id': 'case'}
    request = build_method_planner_request(user_goal=goal, case_config=config,
        repo_inventory={'analysis_programs': []})
    config['case_id'] = 'changed'
    payload = json.loads(request.messages[1]['content'])
    assert payload['user_goal'] == goal
    assert payload['case_config'] == request.context_sources['case_config'] == {'case_id': 'case'}
    assert not {'run_id', 'case_id', 'created_at', 'producer'} & request.json_schema['schema']['properties'].keys()
    assert 'truncated' not in payload


def test_scientific_reviewer_prompt_includes_scope_policy() -> None:
    request = build_scientific_reviewer_request(
        review_evidence={"fit_diagnostics": {"status": "pass"}},
        review_scope={
            "requires_matrix_element_validation": False,
            "has_effective_mass_outputs": True,
        },
    )
    payload = json.loads(request.messages[1]["content"])

    assert request.json_schema is not None
    assert request.json_schema["name"] == "scientific_review_report"
    assert payload["review_scope"]["requires_matrix_element_validation"] is False
    assert payload["review_evidence"]["fit_diagnostics"]["status"] == "pass"
    assert request.json_schema["strict"] is True
    assert "do not warn about missing synthetic_matrix_elements.json" in request.messages[0]["content"]
