"""Private case extraction, independent oracles and real SDK sandbox boundaries."""
from hashlib import sha256
from pathlib import Path
import json
import sys

import pytest

from lqcd_agent.control.strict_json import ControlIntegrityError
from lqcd_agent.research_cases import _grouped, extract, verify_pack
from lqcd_agent.research_evaluation import calibration
from lqcd_agent.analysis.generated_diagnostics import check_c2, check_normalization
from lqcd_agent.code_agent.execution import sandbox_command


def source_fixture(root):
    project = root/'project'
    for pz in (0, 6):
        title = f'l64c64a076_m140_fit_pz{pz}'
        for bt in (0, 2):
            for component in ('real', 'imag'):
                path = project/'2-bm-new/results_fit_nst2'/title/'samples'/f'{title}_T5_eta0_bT{bt}_{component}_2state_samples.txt'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('bz\tsample_id\tsuccess\tm0\n'+''.join(
                    f'{bz}\t{sid}\t1\t{1 if component == "real" else 2}\n'
                    for bz in (0, 2, 4) for sid in (7, 13)))
    title = 'l64c64a076_m140_fit_pz6'
    for mode in ('mode2', 'mode3'):
        path = project/'3-normalize-new'/title/'samples'/f'{title}_T5_eta0_bT2_{mode}_real_2state_samples.txt'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('bz\tsample_id\tsuccess\tm0\n0\t7\t1\t1\n')
    directory = project/'1-c2pt-fit'
    for name in ('nstate_fit_k6.ipynb', 'nstate_fit_k6_2state.ipynb'):
        (directory/name).parent.mkdir(parents=True, exist_ok=True)
        (directory/name).write_text('{}')
    path = directory/'results_nstate_fit_1state'/title/'tables'/f'{title}_symmetric_1state_tmax13_fits.txt'
    path.parent.mkdir(parents=True)
    path.write_text('# tmin E0_mean E0_err\n4 .6 .01\n5 .6 .01\n6 .6 .01\n')
    raw = root/'correlator.csv'
    raw.write_text("['csv']\n"+''.join(','.join(map(str,[t,*[float(t+i+1) for i in range(20)]]))+'\n' for t in range(64)))
    return project, raw


def test_extract_preserves_sources_replica_ids_and_withholds_references(tmp_path):
    project, raw = source_fixture(tmp_path)
    sources = [raw, *[p for p in project.rglob('*') if p.is_file()]]
    before = {p: sha256(p.read_bytes()).hexdigest() for p in sources}
    extract(project, raw, workspace=tmp_path)
    root = tmp_path/'raw_data/research_cases'
    manifest = verify_pack(root)
    assert len(manifest['cases']) == 4 and manifest['scientific_acceptance'] == 'not_system_reviewed'
    c2 = json.loads((root/'inputs/c2.json').read_text())
    assert len(c2['configurations']) == 20 and all(len(row) == 64 for row in c2['configurations'])
    norm = json.loads((root/'inputs/normalization.json').read_text())
    assert {r['sample_id'] for r in norm['records']} == {7,13}
    assert {p:sha256(p.read_bytes()).hexdigest() for p in sources} == before
    (root/'inputs/normalization.json').write_text('{}')
    with pytest.raises(ControlIntegrityError,match='changed'):
        verify_pack(root)


def test_duplicate_complex_replica_is_not_silently_repaired(tmp_path):
    project, raw = source_fixture(tmp_path)
    path = next(project.rglob('*_real_2state_samples.txt'))
    path.write_text(path.read_text()+'0\t7\t1\t5\n')
    with pytest.raises(ControlIntegrityError,match='Duplicate bootstrap'):
        extract(project,raw,workspace=tmp_path)
    assert not (tmp_path/'raw_data/research_cases/manifest.json').exists()


@pytest.mark.parametrize('raw',[b'bz\tbz\tm0\n0\t0\t1\n',b'bz\tm0\nmalformed row\n'])
def test_malformed_source_rows_and_duplicate_headers_are_rejected(raw):
    with pytest.raises(ControlIntegrityError):_grouped(raw)


def test_table_metadata_preface_is_not_mistaken_for_data_or_used_to_drop_bad_rows():
    raw=b'normalization_mode mode2\ntitle source\n\nbz\tsample_id\tsuccess\tm0\n0\t7\t1\t2\n'
    assert _grouped(raw)==[{'bz':'0','sample_id':'7','success':'1','m0':'2'}]
    with pytest.raises(ControlIntegrityError):_grouped(raw+b'broken row\n')


def normalized_control():
    return {'status':'ok','results':[
        {'mode':mode,'bz':0,'sample_id':sid,'success':True,'real':real,'imag':imag}
        for mode,real,imag in (('mode2',0,2),('mode3',2.5,3.5)) for sid in (7,13)],
        'summaries':[{'mode':mode,'bz':0,'component':component,'mean':value,'error':0,'n_valid':2}
            for mode,real,imag in (('mode2',0,2),('mode3',2.5,3.5))
            for component,value in (('real',real),('imag',imag))]}


@pytest.mark.parametrize('fault',['renumber','drop','duplicate','real_division','uncertainty','mode_tag','invent_reference'])
def test_independent_normalization_oracle_rejects_corrupted_results(fault):
    payload=calibration('normalization'); result=normalized_control()
    check_normalization(payload,result)
    if fault=='renumber': result['results'][0]['sample_id']=0
    elif fault=='drop': result['results'].pop()
    elif fault=='duplicate': result['results'].append(result['results'][0])
    elif fault=='real_division': result['results'][0]['real']=1
    elif fault=='uncertainty':result['summaries'][0]['error']=1
    elif fault=='mode_tag':result['results'][0]['mode']=2
    else: payload['omit_reference']=True
    with pytest.raises(ControlIntegrityError):check_normalization(payload,result)


def test_missing_reference_requires_an_explicit_unsuccessful_outcome():
    payload=calibration('normalization')
    payload['records']=[r for r in payload['records'] if (r['pz'],r['bT'])!=(0,2)]
    check_normalization(payload,{'status':'needs_more_info','results':[]})
    with pytest.raises(ControlIntegrityError):check_normalization(payload,normalized_control())


def test_failed_replica_is_retained_without_zero_substitution():
    payload=calibration('normalization');result=normalized_control()
    for row in payload['records']:
        if row['sample_id']==7 and (row['pz'],row['bT'])==(0,2):
            row.update(success=False,real=None,imag=None)
    for row in result['results']:
        if row['sample_id']==7:row.update(success=False,real=None,imag=None)
    for row in result['summaries']:row['n_valid']=1
    check_normalization(payload,result)
    result['results'][0].update(real=0,imag=0)
    with pytest.raises(ControlIntegrityError,match='replaced'):check_normalization(payload,result)


def test_fixed_energy_cannot_be_claimed_as_independent_dispersion_evidence():
    payload=calibration('c2');payload['fixed_ground_energy']=True
    result={'status':'ok','ground_energy_fixed':True,'dispersion_independently_tested':False,
        'fits':[{'nstates':n,'tmin':t,'tmax':13,'E0':.15,'E0_error':0,'chi2_dof':1,
                 'bootstrap_successes':200,'bootstrap_total':200,'failed_sample_ids':[]} for n in (1,2) for t in payload['tmins']]}
    check_c2(payload,result)
    result['fits'][0]['E0_error']=None
    with pytest.raises(ControlIntegrityError,match='Invalid C2 fit'):check_c2(payload,result)
    result['fits'][0]['E0_error']=0.0
    check_c2(payload,result)
    result['dispersion_independently_tested']=True
    with pytest.raises(ControlIntegrityError,match='independent dispersion'):check_c2(payload,result)
    payload['fixed_ground_energy']=False;result['ground_energy_fixed']=False
    with pytest.raises(ControlIntegrityError,match='independent dispersion'):check_c2(payload,result)


def test_multistep_code_task_failure_concludes_without_required_human_input(monkeypatch):
    from lqcd_agent.examples import SyntheticAgent
    from lqcd_agent.runtime import ApplicationRequest,execute
    original=SyntheticAgent.run
    def agent(self,node,context,**options):
        value=original(self,node,context,**options)
        if node=='method_planner':value['content']['requirements']=['zeta requirement','alpha requirement']
        if node=='analysis_engineer':value['diagnostic'].update(status='failed',category='implementation_gap',
            affected_layer='analysis',risk='high',human_need='approval')
        return value
    monkeypatch.setattr(SyntheticAgent,'run',agent)
    start=execute(ApplicationRequest('start',workflow='code',key='multistep-code'))
    locator=start['run_locator']
    result=execute(ApplicationRequest('resume',host=start['host'],case=locator['case_id'],run=locator['run_id'],
        pause=start['active_pause']['pause_id'],key='multistep-delivery'))
    assert result['run_status']=='completed' and result['active_pause'] is None
    from lqcd_agent.inspection import host_root, read_snapshot
    snapshot=read_snapshot(host_root(start['host']),locator)
    index=json.loads((snapshot.root/'artifact_index.json').read_text())
    terminal=json.loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_text())
    assert terminal['scientific_outcome']=='inconclusive' and terminal['decision_origin']=='system'
    assert snapshot.state['active_human_request_id'] is None


@pytest.mark.integration
def test_local_sdk_command_isolation_without_model_or_credentials(tmp_path):
    work=tmp_path/'work';work.mkdir()
    outside=tmp_path/'outside.txt';outside.write_text('private sentinel')
    script=('from pathlib import Path\np=Path('+repr(str(outside))+')\n'
            'local=Path("allowed.txt");local.write_text("ok");assert local.read_text()=="ok"\n'
            'for operation in (p.read_text,lambda:p.write_text("changed")):\n'
            ' try: operation()\n'
            ' except PermissionError: pass\n'
            ' else: raise RuntimeError("sandbox escape")\n'
            'print("isolated")\n')
    from tests.test_sandbox_network import operator_service, network_probe
    with operator_service(work) as (port, unix_path, hits):
        script += network_probe(port,unix_path,managed=False)
        reply=sandbox_command([sys.executable,'-I','-B','-c',script],work,[sys.prefix,sys.base_prefix],timeout=15)
        assert hits == []
    assert reply.exit_code==0 and reply.stdout.strip()=='isolated',reply.stderr
    assert outside.read_text()=='private sentinel'
