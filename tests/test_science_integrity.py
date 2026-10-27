"""Scientific reuse binds both the registered result and its workspace members."""
import hashlib
import json
import pytest
from lqcd_agent.science import ScientificAgent
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes


def test_changed_scientific_member_is_rejected(tmp_path):
    member = tmp_path / 'domain' / 'result.json'
    member.parent.mkdir()
    member.write_bytes(b'{"mass":1}')
    root = tmp_path / 'case' / 'run'
    artifact = root / 'attempts' / 'attempt_000001' / 'run_result.json'
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(canonical_bytes({'domain_result': {'member_digests': {'domain/result.json': hashlib.sha256(member.read_bytes()).hexdigest()}}}))
    context = {'identity': {'case_id': 'case', 'run_id': 'run'}, 'current_evidence': [
        {'member': str(artifact.relative_to(root)), 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}]}
    agent = ScientificAgent(tmp_path, {})
    assert agent._artifact(context, 'run_result.json')['domain_result']
    member.write_bytes(b'{"mass":9}')
    with pytest.raises(ControlIntegrityError, match='Scientific workspace member changed'):
        agent._artifact(context, 'run_result.json')


@pytest.mark.parametrize('declared_risk', [None, 'low'])
def test_scientific_confirmation_is_host_policy_not_a_reviewer_risk_field(tmp_path, monkeypatch, declared_risk):
    from lqcd_agent.agents import scientific_reviewer
    from lqcd_agent.llm.prompts import build_scientific_reviewer_request
    schema = build_scientific_reviewer_request().json_schema['schema']
    assert 'risk_level' not in schema['properties'] and not schema['additionalProperties']
    agent = ScientificAgent(tmp_path, {})
    monkeypatch.setattr(agent, '_artifact', lambda context, name: {'domain_result': {
        'run_result_path': str(tmp_path/'result.json'), 'analysis_outputs_dir': str(tmp_path),
        'method_plan_path': str(tmp_path/'plan.json')}})
    def review(**kwargs):
        path = kwargs['run_output_dir']/'scientific_review_report.json'
        value = {'status': 'success', 'warnings': [], 'confidence': 'high'}
        if declared_risk is not None:
            value['risk_level'] = declared_risk
        path.write_text(json.dumps(value))
        return {'status': 'success', 'scientific_review_report_path': str(path)}
    monkeypatch.setattr(scientific_reviewer, 'run_scientific_reviewer', review)
    result = agent.run('scientific_reviewer', {'identity': {
        'attempt_id': 'attempt', 'case_id': 'case', 'run_id': 'run'}}, timeout_seconds=1)
    assert result['diagnostic']['risk'] == 'high'
    assert result['diagnostic']['human_need'] == 'approval'
    assert result['diagnostic']['category'] == 'scientific_review'


@pytest.mark.parametrize('node', ['method_planner', 'scientific_reviewer'])
def test_scientific_roles_receive_frozen_remediation_and_history(tmp_path, monkeypatch, node):
    from copy import deepcopy
    from lqcd_agent.llm.context import context_reference, read_context_evidence
    from lqcd_agent.llm.mock_provider import MockLLMProvider
    from tests.test_research_evidence import inputs
    from tests.test_scientific_reviewer import _write_effective_mass_artifacts

    class RecordingProvider(MockLLMProvider):
        def generate(self, request):
            self.request = request
            return super().generate(request)

    _, config, inventory, _, _ = inputs(tmp_path)
    run_dir, result_path, plan_path = _write_effective_mass_artifacts(tmp_path, run_id='run', case_id='case')
    provider = RecordingProvider()
    agent = ScientificAgent(tmp_path, config, workspace=tmp_path, provider=provider)
    monkeypatch.setattr(agent, '_artifact', lambda context, name: {'domain_result': {
        'run_result_path': str(result_path), 'analysis_outputs_dir': str(run_dir / 'analysis_outputs'),
        'method_plan_path': str(plan_path)}})
    context = {'identity': {'attempt_id': 'first', 'case_id': 'case', 'run_id': 'run'},
        'root_goal': {'goal': 'Estimate effective mass.', 'dataset_snapshot': inventory['dataset_snapshot']},
        'remediation': {'problem': 'Window stability', 'constraints': ['Preserve measured data'],
            'success_criteria': ['Compare fit windows']},
        'relevant_history': [{'artifact_id': 'prior:review', 'status': 'failed'}]}
    for attempt, criterion in [('first', 'Compare fit windows'), ('second', 'Report unresolved uncertainty')]:
        context['identity']['attempt_id'] = attempt
        context['remediation']['success_criteria'] = [criterion]
        result = agent.run(node, context, timeout_seconds=1)
        payload = json.loads(provider.request.messages[1]['content'])
        expected = {key: deepcopy(context[key]) for key in ('remediation', 'relevant_history')}
        assert payload['research_context'] == expected
        if node == 'scientific_reviewer':
            assert result['diagnostic']['risk'] == 'high' and result['diagnostic']['human_need'] == 'approval'
        output = tmp_path / 'domain' / attempt / 'case' / 'run'
        catalog = context_reference(provider.request.context_sources)
        context['remediation']['success_criteria'].append('Do not mutate prior context')
        assert read_context_evidence(output, catalog, 'research_context') == expected
