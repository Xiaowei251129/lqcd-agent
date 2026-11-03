"""Scientific inputs and model proposals retain exact identity and Host authority."""
import hashlib
import json
from pathlib import Path
import pytest
from lqcd_agent.agents.analysis_engineer import run_analysis_engineer
from lqcd_agent.agents.method_planner import run_method_planner
from lqcd_agent.analysis_programs.registry import selected_analysis_programs
from lqcd_agent.llm.base import LLMResponse
from lqcd_agent.llm.mock_provider import MockLLMProvider
from lqcd_agent.llm.schemas import validate_proposal
from lqcd_agent.tools.dataset import snapshot_dataset, read_dataset
from lqcd_agent.tools.repo_inventory import build_repo_inventory


def inputs(tmp_path):
    raw = tmp_path / 'raw_data/correlator.csv'
    raw.parent.mkdir()
    raw.write_bytes(b't,value,error\r\n0,1,.02\r\n1,.7,.03\r\n2,.49,.04\r\n')
    config = {'case_id': 'case', 'raw_data_path': 'raw_data/correlator.csv',
              'physics_goal': 'Estimate effective mass.', 'target_observables': ['effective_mass_estimates'],
              'expected_outputs': ['analysis_outputs/effective_mass_estimates.json']}
    inventory = {**build_repo_inventory(tmp_path), 'dataset_snapshot': snapshot_dataset(config, tmp_path)}
    case = tmp_path/'case.json'; case.write_text(json.dumps(config))
    plan = tmp_path/'plan.json'; plan.write_text(json.dumps({'selected_analysis_programs': selected_analysis_programs(config, inventory)}))
    return raw, config, inventory, case, plan


def test_manifest_identifies_consumed_bytes_even_if_path_changes_during_calculation(tmp_path, monkeypatch):
    raw, config, inventory, case, plan = inputs(tmp_path)
    original = raw.read_bytes()
    from lqcd_agent.analysis_programs.two_point_fit import program
    calculate = program.single_exponential_effective_mass
    calls = []
    def changed(**kwargs):
        calls.append(kwargs)
        raw.write_bytes(original.replace(b'.7', b'.6'))
        return calculate(**kwargs)
    monkeypatch.setattr(program, 'single_exponential_effective_mass', changed)
    result = run_analysis_engineer(case_config_path=case, case_id='case', run_id='run',
        run_output_dir=tmp_path/'outputs/case/run', method_plan_path=plan, repo_root=tmp_path,
        dataset_snapshot=inventory['dataset_snapshot'])
    assert result['run_success']
    manifest = json.loads(Path(result['manifest_path']).read_text())
    source = next(r for r in manifest['input_files'] if r['path'] == config['raw_data_path'])
    assert source['sha256'] == hashlib.sha256(original).hexdigest()
    assert source['bytes'] == len(original) and source['columns'] == ['t', 'value', 'error']
    assert calls[0]['correlator_values'] == [1, .7, .49]
    second = run_analysis_engineer(case_config_path=case, case_id='case', run_id='changed',
        run_output_dir=tmp_path/'outputs/case/changed', method_plan_path=plan, repo_root=tmp_path,
        dataset_snapshot=inventory['dataset_snapshot'])
    assert not second['run_success'] and len(calls) == 1
    assert 'frozen Run input' in json.dumps(second)


def test_provider_selects_id_host_materializes_mapping_and_identity(tmp_path):
    raw, config, inventory, _, _ = inputs(tmp_path)
    result = run_method_planner(user_goal=config['physics_goal'], case_config=config,
        repo_inventory=inventory, output_dir=tmp_path, run_id='host-run', provider=MockLLMProvider())
    assert result['status'] == 'success', result
    plan = result['method_plan']
    assert plan['run_id'] == 'host-run' and plan['producer'] == 'method_planner'
    assert plan['selected_analysis_programs'][0]['input_mapping']['correlator_errors'] == 'raw_data_csv.error'
    trace = json.loads((tmp_path/'llm_calls/method_planner.json').read_text())
    proposal = json.loads(trace['response']['content'])
    assert not validate_proposal(proposal, 'method_plan')
    assert proposal['selected_analysis_programs'] == ['single_exponential_effective_mass']
    assert not {'run_id', 'case_id', 'producer', 'created_at', 'required_outputs'} & proposal.keys()
    assert not plan['warnings']


@pytest.mark.parametrize('mutation', ['identity', 'path', 'unknown', 'duplicate', 'empty', 'pending'])
def test_invalid_proposal_cannot_assign_authority_or_be_silently_repaired(tmp_path, mutation):
    _, config, inventory, _, _ = inputs(tmp_path)
    class Provider(MockLLMProvider):
        def generate(self, request):
            response = super().generate(request)
            value = json.loads(response.content)
            if mutation == 'identity': value['run_id'] = 'forged'
            elif mutation == 'path': value['selected_analysis_programs'] = [{'name': 'single_exponential_effective_mass', 'callable_path': 'untrusted.run'}]
            elif mutation == 'unknown': value['selected_analysis_programs'] = ['unknown']
            elif mutation == 'duplicate': value['selected_analysis_programs'] *= 2
            elif mutation == 'empty': value['selected_analysis_programs'] = []
            else: value['status'] = 'pending'
            return LLMResponse('mock', 'test', json.dumps(value))
    result = run_method_planner(user_goal=config['physics_goal'], case_config=config,
        repo_inventory=inventory, output_dir=tmp_path, run_id='run', provider=Provider())
    assert result['status'] == ('pending' if mutation == 'pending' else 'failed')
    assert result['method_plan']['run_id'] == 'run'


def test_role_view_retains_full_catalog_for_verified_on_demand_reads(tmp_path):
    from lqcd_agent.llm.context import read_context_evidence
    _, config, inventory, _, _ = inputs(tmp_path)
    inventory['allowed_files'] = ['scope/' + str(i) + '.py' for i in range(2000)]
    result = run_method_planner(user_goal=config['physics_goal'], case_config=config,
        repo_inventory=inventory, output_dir=tmp_path, run_id='run', provider=MockLLMProvider())
    assert result['status'] == 'success', result
    trace = json.loads((tmp_path/'llm_calls/method_planner.json').read_text())
    model_context = json.loads(trace['request']['messages'][1]['content'])
    assert 'allowed_files' not in model_context['repo_inventory']
    assert 'callable_path' not in model_context['repo_inventory']['analysis_programs'][0]
    reference = model_context['evidence_catalog']
    restored = read_context_evidence(tmp_path, reference, 'repo_inventory', fields=['allowed_files'])
    assert restored == {'allowed_files': inventory['allowed_files']}
    assert read_context_evidence(tmp_path, reference, 'user_goal') == config['physics_goal']
    with pytest.raises(ValueError, match='Unknown context section'):
        read_context_evidence(tmp_path, reference, 'unregistered')
    with pytest.raises(ValueError, match='Unknown context field'):
        read_context_evidence(tmp_path, reference, 'repo_inventory', fields=['unregistered'])
    path = tmp_path/'context_evidence'/(reference['sha256']+'.json')
    path.write_text('{}')
    with pytest.raises(ValueError, match='Context evidence changed'):
        read_context_evidence(tmp_path, reference, 'user_goal')


def test_context_reader_refuses_redirected_evidence(tmp_path):
    from lqcd_agent.llm.context import read_context_evidence, context_reference
    reference = context_reference({'goal': 'test'})
    external = tmp_path/'external'; external.mkdir()
    (tmp_path/'context_evidence').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='cannot be redirected'):
        read_context_evidence(tmp_path, reference, 'goal')


def test_scientific_replay_keeps_original_dataset_identity(tmp_path, monkeypatch):
    from tests.support import command
    from tests.test_cli import arguments, persisted
    raw, config, inventory, case, _ = inputs(tmp_path)
    config['schema_version'] = '0.1'
    case.write_text(json.dumps(config))
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(tmp_path))
    first = command('run', '--case-config', str(case), '--key', 'original-data')
    root, _, index = persisted(first)
    goal = json.loads((root/'root_goal.json').read_text())
    assert goal['dataset_snapshot'] == inventory['dataset_snapshot']
    assert first['run_status'] == 'completed' and index['current']['terminal'] is not None
    terminal = json.loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_text())
    assert terminal['decision_origin'] == 'system' and terminal['authorization_decision'] is None
    raw.write_bytes(raw.read_bytes().replace(b'.7', b'.6'))
    child = command('replay', *arguments(first), '--source-digest', first['root_inputs_digest'], '--key', 'changed-data')
    child_root, child_execution, child_index = persisted(child)
    assert json.loads((child_root/'root_goal.json').read_text())['dataset_snapshot'] == goal['dataset_snapshot']
    result = json.loads(Path(child_index['current']['analysis']['state_paths']['run_result_path']).read_text())['domain_result']
    assert result['run_success'] is False
    run_result = json.loads(Path(result['run_result_path']).read_text())
    assert 'frozen Run input' in json.dumps(run_result)
    assert run_result['commands'] and all(command['status'] == 'blocked' and command['return_code'] is None
        and command['produced_files'] == [] for command in run_result['commands'])
    assert child['run_status'] == 'halted' and child['active_pause'] is None
    from lqcd_agent.control.strict_json import digest
    from lqcd_agent.inspection import read_snapshot
    snapshot = read_snapshot(child_root.parent.parent, child['run_locator'])
    assert snapshot.closure['terminal_closure'] == 'committed' and snapshot.closure['run_status'] == 'halted'
    failure = child['execution_failure']
    assert failure['source'] == 'committed_control_closure' and failure['closure_sha256'] == digest(snapshot.closure)
    assert failure['scientific_outcome'] == 'inconclusive' and failure['decision_origin'] == 'system'
    terminal = json.loads(Path(child_index['current']['terminal']['state_paths']['memory_update_path']).read_text())
    assert terminal['scientific_outcome'] == 'inconclusive' and terminal['decision_origin'] == 'system'
    assert terminal['accepted_result'] is False
    assert child_index['current']['terminal']['status'] == 'rejected' and child_index['current']['approval'] is None
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in child_execution.values)


def test_reviewer_reads_scientific_method_without_sending_command_logs(tmp_path):
    from lqcd_agent.llm.prompts import build_scientific_reviewer_request
    from lqcd_agent.llm.context import persist_context, read_context_evidence
    logs = 'NUMERICAL_LOG_ONLY_LOCAL ' * 10000
    request = build_scientific_reviewer_request(
        run_result={'status': 'success', 'run_success': True, 'commands': [{'stdout': logs}]},
        method_plan={'status': 'success', 'physics_goal': 'Test stability',
                     'method_steps': ['Compare neighboring windows'],
                     'warnings': [{'message': 'Do not assume independence'}]})
    persist_context(tmp_path, request)
    view = json.loads(request.messages[1]['content'])
    assert logs not in request.messages[1]['content']
    assert view['method_plan_summary']['method_step_count'] == 1
    assert 'method_steps' not in view['method_plan_summary']
    method = read_context_evidence(tmp_path, view['evidence_catalog'], 'method_plan', fields=['method_steps'])
    assert method['method_steps'] == ['Compare neighboring windows']
    assert view['method_plan_summary']['warnings'] == [{'message': 'Do not assume independence'}]
    source = read_context_evidence(tmp_path, view['evidence_catalog'], 'run_result', fields=['commands'])
    assert source['commands'][0]['stdout'] == logs


def test_missing_frozen_input_cannot_appear_unnoticed(tmp_path):
    raw, config, inventory, case, plan = inputs(tmp_path)
    raw.unlink()
    absent = snapshot_dataset(config, tmp_path)
    raw.write_text('t,value,error\n0,1,.02\n1,.7,.03\n')
    result = run_analysis_engineer(case_config_path=case, case_id='case', run_id='run',
        run_output_dir=tmp_path/'outputs/case/run', method_plan_path=plan, repo_root=tmp_path,
        dataset_snapshot=absent)
    assert not result['run_success']
    assert 'frozen Run input' in json.dumps(result)
    assert not (tmp_path/'outputs/case/run/analysis_outputs/effective_mass_estimates.json').exists()


@pytest.mark.parametrize('newline', ['\r', '\r\n', '\n'])
def test_dataset_hash_and_values_preserve_csv_newline_formats(tmp_path, newline):
    path = tmp_path/'raw_data/data.csv'
    path.parent.mkdir()
    original = newline.join(['label,value', '"质量\ncontinued",1.5', '']).encode('utf-8')
    path.write_bytes(original)
    record, values = read_dataset(tmp_path, 'raw_data/data.csv', text_columns=['label'], values=True)
    assert values == {'label': ['质量\ncontinued'], 'value': [1.5]}
    assert record['sha256'] == hashlib.sha256(original).hexdigest()
    assert record['bytes'] == len(original)
    assert snapshot_dataset({'raw_data_path': 'raw_data/data.csv'}, tmp_path) == record
