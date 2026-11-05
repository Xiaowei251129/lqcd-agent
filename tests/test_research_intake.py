"""Research preparation with real SDK serialization and offline model fixtures."""
import asyncio
from copy import deepcopy
import json
import sys
from types import SimpleNamespace

from agents import Model
from agents.items import ModelResponse
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
import pytest

from lqcd_agent.control.strict_json import digest
from lqcd_agent.research.agent_runtime import ResearchAgentRuntime
from lqcd_agent.research.collaboration import _RoleProvider
from lqcd_agent.research.intake import offline_preparation, run_intake, snapshot_intake
from tests.test_research_collaboration import ReadOnlyMeter, discussion, issue


def fixture_intake_project(workspace):
    path = workspace/'raw_data/correlator.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'source_kind': 'synthetic_placeholder', 'nt': 16,
        'configuration_ids': [11, 12, 13, 14], 'configurations': [[937.24681012]*16 for _ in range(4)]}))
    return {'id': 'intake-case', 'goal': 'Compare fit-window sensitivity without changing the declared source.',
        'case_config': {'raw_data_path': 'raw_data/correlator.json',
            'generated_program': {'python': sys.executable, 'parameters': {'bootstrap_samples': 8}}}}


class IntakeModel(Model):
    def __init__(self, calls, *, parameters=None, family='c2', pi_need=False, answer='omitted'):
        self.calls, self.family, self.pi_need, self.answer = calls, family, pi_need, answer
        self.read = False
        self.parameters = ({'binsize': 1, 'seed': 2, 'tmins': [2], 'tmax': 6, 'fixed_ground_energy': False}
                           if family == 'c2' else {})
        if parameters is not None:
            self.parameters.update(parameters)

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema,
                           handoffs, tracing, **kwargs):
        assert tracing.is_disabled() and not handoffs
        self.calls.append({'schema': output_schema.name(), 'input': deepcopy(input), 'instructions': system_instructions})
        if output_schema.name() == 'IntakePlan' and self.answer == 'verified' and not self.read:
            self.read = True
            output = [ResponseFunctionToolCall(type='function_call', name='read_context',
                arguments=json.dumps({'section': 'intake_profile', 'offset': 0}), call_id='read-intake')]
        else:
            if output_schema.name() == 'ResearchBrief':
                value = {'physics_question': f'Check the supported {self.family} contract.',
                    'competing_explanations': ['Analysis choice sensitivity'], 'discriminating_checks': ['Retain each requested estimate.'],
                    'success_criteria': ['Preserve all failed replica identities.'], 'discussion': discussion()}
                if self.pi_need:
                    value['discussion'] = discussion(decision='need_information',
                        issues=[issue(question='Which output contract is supported by these data?')])
            else:
                assert output_schema.name() == 'IntakePlan'
                response = discussion()
                if self.pi_need and self.answer != 'omitted':
                    message = next(json.loads(row['content']) for row in reversed(input)
                        if type(row) is dict and row.get('role') == 'user' and
                        type(row.get('content')) is str and 'pi_brief' in json.loads(row['content']))
                    asked = message['issues'][0]
                    initial = json.loads(input[0]['content'])
                    response['issues'] = [{**asked, 'status': 'addressed', 'response': 'The declared source has the C2 contract.',
                        'evidence_references': [digest(initial['intake_profile']) if self.answer == 'verified' else 'invented-proof']}]
                value = {'family': self.family, 'parameters': [{'name': key, 'value_json': json.dumps(value)}
                    for key, value in self.parameters.items()], 'method_steps': ['Compute each requested estimate.'],
                    'assumptions': ['Use the declared observable units.'], 'discussion': response}
            output = [ResponseOutputMessage(type='message', id='answer', role='assistant', status='completed',
                content=[ResponseOutputText(type='output_text', text=json.dumps(value), annotations=[])])]
        return ModelResponse(output=output, usage=Usage(requests=1, input_tokens=10, output_tokens=5, total_tokens=15),
                             raw_usage={'total_tokens': 15}, response_id='fixture-'+str(len(self.calls)))

    async def stream_response(self, *args, **kwargs):
        raise AssertionError('No streaming fixture')
        yield


def prepare_fixture(workspace, project, **model_options):
    host = workspace/'host'
    output = host/'domain/attempt_000001/intake-case/run-fixture'
    output.mkdir(parents=True)
    context = {'identity': {'case_id': 'intake-case', 'run_id': 'run-fixture',
                           'attempt_id': 'attempt_000001', 'attempt_kind': 'method_planner'},
        'root_goal': {'project_id': project['id'], 'goal': project['goal'], 'intake': snapshot_intake(workspace, project)},
        'budget_summary': {'dimensions': {'llm_calls_per_attempt': {'remaining': 8},
                                          'llm_calls_per_run': {'remaining': 32}}}}
    calls = []
    runtime = ResearchAgentRuntime(IntakeModel(calls, **model_options), max_output_tokens=2048)
    agent = SimpleNamespace(workspace=workspace, host=host, config=project['case_config'], request_timeout_seconds=10)
    with asyncio.Runner() as runner:
        provider = _RoleProvider(agent, 'method_planner', context, output, runtime, runner, ReadOnlyMeter())
        result = run_intake(provider)
        runner.run(runtime.aclose())
    return result, calls, context


def test_intake_profiles_declared_data_without_raw_values_or_interpreter_execution(tmp_path, monkeypatch):
    project = fixture_intake_project(tmp_path)
    monkeypatch.setattr('subprocess.check_output', lambda *args, **kwargs: pytest.fail('Intake must not run a Python executable'))
    snapshot = snapshot_intake(tmp_path, project)
    assert snapshot['data_profile']['shapes'] == {'configurations': [4, 16]}
    assert snapshot['data_profile']['family_candidates'] == ['c2'] and snapshot['missing_inputs'] == []
    assert snapshot['python_identity']['path'] == sys.executable
    assert '937.24681012' not in json.dumps(snapshot) and '[11, 12, 13, 14]' not in json.dumps(snapshot)
    assert snapshot['dataset_snapshot']['path'] == 'raw_data/correlator.json'
    original = snapshot['dataset_snapshot']['sha256']
    source = tmp_path/'raw_data/correlator.json'
    source.write_text(source.read_text().replace('937.24681012', '937.24681013'))
    assert snapshot_intake(tmp_path, project)['dataset_snapshot']['sha256'] != original
    source.unlink()
    source.symlink_to(tmp_path/'outside.json')
    with pytest.raises(ValueError, match='raw_data'):
        snapshot_intake(tmp_path, project)


def test_normalization_intake_binds_original_paired_replica_keys(tmp_path):
    source = tmp_path/'raw_data'/'ratios.json'
    source.parent.mkdir()
    config = {'raw_data_path': 'raw_data/ratios.json', 'source_kind': 'synthetic',
              'generated_program': {'python': sys.executable}}
    base = {'pz': 3, 'bT': 2, 'bz': 1, 'sample_id': 8, 'success': True, 'real': .5, 'imag': 0}
    payload = {'target_pz': 3, 'target_bT': 2, 'bz_values': [1], 'omit_reference': False,
               'records': [base, {**base, 'sample_id': 2, 'success': False, 'real': None, 'imag': None}]}
    source.write_text(json.dumps(payload))
    profile = snapshot_intake(tmp_path, {'case_config': config})['data_profile']
    assert profile['family_candidates'] == ['normalization'] and profile['issues'] == []
    assert profile['replica_keys_sha256'] == digest([[3, 2, 1, 8], [3, 2, 1, 2]])
    payload['records'].append(base)
    source.write_text(json.dumps(payload))
    duplicate = snapshot_intake(tmp_path, {'case_config': config})['data_profile']
    assert 'Resolve duplicate normalization replica identities.' in duplicate['issues']


def test_intake_sdk_builds_only_host_resolved_contract_and_retains_source_evidence(tmp_path):
    project = fixture_intake_project(tmp_path)
    outcome, calls, context = prepare_fixture(tmp_path, project)
    preparation = outcome['content']['domain_result']['preparation']
    assert preparation['status'] == 'ready' and preparation['questions'] == []
    config = preparation['case_config']
    assert config['raw_data_path'] == project['case_config']['raw_data_path']
    assert config['case_id'] == context['identity']['case_id'] and config['source_kind'] == 'synthetic_placeholder'
    assert config['generated_program']['python'] == sys.executable
    assert config['generated_program']['parameters']['bootstrap_samples'] == 8
    assert 'Retain each requested estimate.' in config['generated_program']['requirements']
    assert not outcome['content']['code_needed'] and outcome['diagnostic']['category'] == 'research_intake'
    assert [call['schema'] for call in calls] == ['ResearchBrief', 'IntakePlan']
    assert '937.24681012' not in json.dumps(calls)
    members = outcome['content']['domain_result']['member_digests']
    assert any(path.endswith('/intake_context.json') for path in members)
    for path, expected in members.items():
        from hashlib import sha256
        assert sha256((tmp_path/'host'/path).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize('answer', ['omitted', 'unverified', 'verified'])
def test_intake_preserves_pi_prerequisite_until_postdoc_reads_answer_evidence(tmp_path, answer):
    outcome, calls, _ = prepare_fixture(tmp_path, fixture_intake_project(tmp_path), pi_need=True, answer=answer)
    preparation = outcome['content']['domain_result']['preparation']
    assert preparation['status'] == ('ready' if answer == 'verified' else 'needs_information')
    assert (preparation['case_config'] is not None) is (answer == 'verified')
    issue = outcome['content']['collaboration']['issues'][0]
    assert issue['status'] == ('addressed' if answer == 'verified' else 'blocked')
    assert len(calls) == (3 if answer == 'verified' else 2)


@pytest.mark.parametrize('parameters,family,expected', [
    ({'bootstrap_samples': 9}, 'c2', 'operator-specified parameter'),
    ({'python': '/private/tmp/model-interpreter'}, 'c2', 'Unsupported'),
    ({'tmax': 15}, 'c2', 'folded time range'),
    ({}, 'normalization', 'supported by the declared input'),
])
def test_intake_cannot_change_fixed_inputs_or_invent_execution_scope(tmp_path, parameters, family, expected):
    outcome, _, _ = prepare_fixture(tmp_path, fixture_intake_project(tmp_path), parameters=parameters, family=family)
    preparation = outcome['content']['domain_result']['preparation']
    assert preparation['status'] == 'needs_information' and preparation['case_config'] is None
    assert any(expected in question for question in preparation['questions'])


def test_intake_missing_input_and_offline_mode_do_not_claim_readiness(tmp_path):
    project = {'id': 'intake-case', 'goal': 'Analyze a future dataset.', 'case_config': None}
    snapshot = snapshot_intake(tmp_path, project)
    assert snapshot['dataset_snapshot'] is None and snapshot['python_identity'] is None
    assert len(snapshot['missing_inputs']) == 3
    context = {'root_goal': {'intake': snapshot}}
    output = tmp_path/'host/domain/attempt_000001/intake-case/run-fixture'
    outcome = offline_preparation(context, output)
    preparation = outcome['content']['domain_result']['preparation']
    assert preparation['status'] == 'needs_information' and preparation['case_config'] is None
    assert outcome['content']['collaboration']['exchanges'] == []


def test_intake_binds_missing_metadata_supplied_by_operator_without_replacing_data(tmp_path):
    project = fixture_intake_project(tmp_path)
    source = tmp_path/'raw_data/correlator.json'
    payload = json.loads(source.read_text())
    del payload['nt']
    source.write_text(json.dumps(payload))
    project['case_config']['generated_program']['parameters']['nt'] = 16
    outcome, _, context = prepare_fixture(tmp_path, project)
    profile = context['root_goal']['intake']['data_profile']
    assert 'nt' not in profile['fields'] and profile['metadata']['nt'] == 16
    assert profile['operator_metadata_fields'] == ['bootstrap_samples', 'nt']
    preparation = outcome['content']['domain_result']['preparation']
    assert preparation['status'] == 'ready'
    assert preparation['case_config']['generated_program']['parameters']['nt'] == 16
    assert json.loads(source.read_text()) == payload


def test_intake_retains_unsupported_binary_source_as_a_question_without_parsing_csv(tmp_path):
    from hashlib import sha256
    project = fixture_intake_project(tmp_path)
    source = tmp_path/'raw_data/correlator.h5'
    raw = b'\x89HDF\r\n\x1a\n\x00\xff\xfe\x80private-binary-array'
    source.write_bytes(raw)
    project['case_config'].update(raw_data_path='raw_data/correlator.h5', source_kind='synthetic_placeholder')
    outcome, calls, context = prepare_fixture(tmp_path, project)
    snapshot = context['root_goal']['intake']
    assert snapshot['dataset_snapshot'] == {'path': 'raw_data/correlator.h5', 'exists': True,
        'sha256': sha256(raw).hexdigest(), 'bytes': len(raw), 'columns': []}
    assert snapshot['data_profile']['format'] == 'h5' and snapshot['data_profile']['family_candidates'] == []
    preparation = outcome['content']['domain_result']['preparation']
    assert preparation['status'] == 'needs_information' and preparation['case_config'] is None
    assert any('supported C2' in question for question in preparation['questions'])
    assert 'private-binary-array' not in json.dumps(calls) and source.read_bytes() == raw
