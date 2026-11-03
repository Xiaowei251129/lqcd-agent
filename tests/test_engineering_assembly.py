"""Contract and real assembly regressions for installed scientific capabilities."""
import json
import pytest
from lqcd_agent.agents.analysis_engineer import run_analysis_engineer
from lqcd_agent.configuration import read_config
from lqcd_agent.analysis_programs.registry import selected_analysis_programs
from lqcd_agent.science import ScientificAgent
from lqcd_agent.tools.repo_inventory import build_repo_inventory


def test_nested_yaml_matches_json_and_rejects_ambiguous_values(tmp_path):
    value = {'nested': {'choices': ['a', 'b'], 'enabled': True}, 'number': 0.4}
    path = tmp_path/'case.yaml'
    path.write_text('nested:\n  choices: [a, b]\n  enabled: true\nnumber: 0.4\n')
    assert read_config(path) == value
    for suffix, source in [('yaml', 'a: 1\na: 2\n'), ('json', '{"a":1,"a":2}'),
                           ('yaml', 'date: 2026-10-27'), ('yaml', '[a,b]'), ('yaml', 'a: .nan'), ('yaml', 'a: [unterminated'), ('yaml', 'true: false')]:
        target = tmp_path/('bad.'+suffix); target.write_text(source)
        with pytest.raises(ValueError):
            read_config(target)


@pytest.mark.parametrize('csv_text,success', [
    ('z,Pz,component,value\n0,5,real,1.01\n1,5,real,0.7\n', True),
    ('z,Pz,component,value,value\n0,5,real,1,2\n', False),
    ('z,Pz,component,value\n0,5,real,1,2\n', False),
    ('z,Pz,component,value\n1,5,real,0.7\n', False),
])
def test_registered_matrix_program_runs_through_canonical_analysis(tmp_path, csv_text, success):
    raw = tmp_path/'raw_data'; raw.mkdir()
    (raw/'matrix.csv').write_text(csv_text)
    config = {'raw_data_path': 'raw_data/matrix.csv', 'target_observables': ['normalization_diagnostics'],
              'expected_outputs': ['analysis_outputs/normalization_diagnostics.json']}
    inventory = build_repo_inventory(tmp_path)
    selected = selected_analysis_programs(config, inventory)
    assert selected[0]['input_mapping'] == {'matrix_elements': 'raw_data_csv.rows'}
    case = tmp_path/'case.json'; case.write_text(json.dumps(config))
    plan = tmp_path/'plan.json'; plan.write_text(json.dumps({'selected_analysis_programs': selected}))
    result = run_analysis_engineer(case_config_path=case, case_id='case', run_id='run',
        run_output_dir=tmp_path/'outputs/case/run', method_plan_path=plan, repo_root=tmp_path)
    assert result['run_success'] is success, result
    if not success:
        return
    payload = json.loads((tmp_path/'outputs/case/run/analysis_outputs/normalization_diagnostics.json').read_text())
    assert payload['all_passed'] is True


def test_failed_review_is_a_failed_domain_diagnostic(tmp_path, monkeypatch):
    import lqcd_agent.agents.scientific_reviewer as reviewer
    monkeypatch.setattr(reviewer, 'run_scientific_reviewer', lambda **_: {'status': 'failed'})
    agent = ScientificAgent(tmp_path, {}, workspace=tmp_path)
    monkeypatch.setattr(agent, '_artifact', lambda context, name: {'domain_result':
        {'method_plan_path': 'plan.json'} if name == 'method_plan.json' else
        {'run_result_path': 'result.json', 'analysis_outputs_dir': 'analysis_outputs'}})
    value = agent.run('scientific_reviewer', {'identity': {'attempt_id': 'a', 'case_id': 'c', 'run_id': 'r'}}, timeout_seconds=1)
    assert value['diagnostic']['status'] == 'failed'
    assert value['diagnostic']['category'] == 'scientific_review'
    assert value['diagnostic']['affected_layer'] == 'review' and value['diagnostic']['human_need'] is None
