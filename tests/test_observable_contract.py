"""Independent resampling arithmetic never stands in for physics validation."""
from copy import deepcopy
import math

import pytest

from lqcd_agent.analysis.generated_diagnostics import diagnose_generated_output
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes
from lqcd_agent.research.observable_contract import check_observables


def fixture(method='bootstrap'):
    payload = {'replica_groups': [{'id': 'paired', 'sample_ids': [10, 20, 30], 'method': method,
                                  'provenance': 'Explicit synthetic calibration identities, not measured data'}],
               'observable_contracts': [{'id': 'matrix_real', 'definition': 'Real component of fixture ratio',
                    'unit': 'dimensionless', 'group': 'paired', 'kinematics': {'pz': 1, 'z': 0}}]}
    error = 1.0 if method == 'bootstrap' else math.sqrt(4/3)
    result = {'status': 'ok', 'observables': [{'id': 'matrix_real',
        'samples': [{'sample_id': sid, 'value': value} for sid, value in zip([10,20,30], [-2,-1,0], strict=True)],
        'mean': -1., 'error': error}], 'assumptions': [], 'limitations': ['Synthetic calibration only.']}
    return payload, result


@pytest.mark.parametrize('method', ['bootstrap', 'jackknife'])
def test_independent_uncertainty_arithmetic_and_required_physics_warning(tmp_path, method):
    payload, result = fixture(method)
    assert check_observables(payload, result)['valid_observables'] == 1
    path = tmp_path/'result.json'; path.write_bytes(canonical_bytes(result))
    report = diagnose_generated_output(path, 'replica_observables', payload)
    assert report['status'] == 'warning'
    assert any(w['code'] == 'observable_physics_not_validated' for w in report['warnings'])
    result['observables'][0]['error'] /= math.sqrt(3)
    with pytest.raises(ControlIntegrityError, match='arithmetic'):
        check_observables(payload, result)


@pytest.mark.parametrize('mutation', ['drop', 'duplicate', 'renumber', 'boolean', 'invent', 'nan'])
def test_bad_replica_identity_and_estimate_are_rejected(mutation):
    payload, result = fixture()
    samples = result['observables'][0]['samples']
    if mutation == 'drop': samples.pop()
    elif mutation == 'duplicate': samples.append(deepcopy(samples[0]))
    elif mutation == 'renumber': samples[0]['sample_id'] = 0
    elif mutation == 'boolean': samples[0]['sample_id'] = True
    elif mutation == 'invent': result['observables'][0]['id'] = 'invented'
    elif mutation == 'nan': samples[0]['value'] = float('nan')
    with pytest.raises(ControlIntegrityError):
        check_observables(payload, result)


def test_failed_jackknife_never_silently_drops_block_or_returns_error_bar():
    payload, result = fixture('jackknife')
    result['status'] = 'partial'
    result['observables'][0]['samples'][0]['value'] = None
    with pytest.raises(ControlIntegrityError, match='Insufficient'):
        check_observables(payload, result)
    result['observables'][0].update(mean=None, error=None)
    assert check_observables(payload, result)['failed_replicas'] == 1


def test_project_observable_program_executes_and_keeps_physics_warning(tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    from tests.test_scientific_codegen import install_backend, deliver
    from lqcd_agent.runtime import ApplicationRequest, execute
    from lqcd_agent.research.projects import ProjectStore
    from lqcd_agent.inspection import host_root
    from lqcd_agent.control.strict_json import loads
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(tmp_path))
    payload, _ = fixture()
    payload['values'] = [-2,-1,0]
    raw = tmp_path/'raw_data'; raw.mkdir()
    (raw/'observables.json').write_bytes(canonical_bytes(payload))
    config = {'schema_version':'0.1','case_id':'observables','physics_goal':'Independent synthetic uncertainty check',
        'raw_data_path':'raw_data/observables.json','source_kind':'synthetic','target_observables':['matrix_real'],
        'generated_program': {'python':sys.executable,'parameters':{},'timeout_seconds':30,
            'requirements':['Implement replica_observables; no scientific acceptance.'], 'result_kind':'replica_observables'}}
    program = b'''import json,sys,math
p=json.load(open(sys.argv[1]));v=p['values'];m=sum(v)/len(v)
r={'id':'matrix_real','samples':[{'sample_id':i,'value':x} for i,x in zip(p['replica_groups'][0]['sample_ids'],v)],'mean':m,'error':math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))}
print(json.dumps({'status':'ok','observables':[r],'assumptions':[],'limitations':['Synthetic calibration only.']}))
'''
    install_backend(monkeypatch, program)
    projects = ProjectStore(tmp_path)
    project = projects.create('ratios', 'Ratio study', config['physics_goal'], config)
    start = execute(ApplicationRequest('run', project='ratios', project_digest=project['sha256'], key='observable-start'))
    assert start['active_pause']['reason'] == 'external_result'
    result = deliver(start)
    assert result['active_pause']['reason'] == 'human_input'
    root = host_root(result['host'])/'observables'/result['run_locator']['run_id']
    index = loads((root/'artifact_index.json').read_bytes())['current']
    review = loads(Path(index['review']['state_paths']['scientific_review_report_path']).read_bytes())['domain_result']['report']
    assert any(w['code']=='observable_physics_not_validated' for w in review['warnings'])
    history = projects.runs('ratios')
    assert len(history) == 1 and history[0]['preliminary'] and not history[0]['resumable']
