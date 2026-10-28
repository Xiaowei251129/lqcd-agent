"""Exercise scientific assembly with a deterministic backend, actual processes and Host review."""
from pathlib import Path
from contextlib import closing
import json
import sys

import pytest

from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, loads
from lqcd_agent.research_evaluation import calibration
from lqcd_agent.runtime import ApplicationRequest, execute
from lqcd_agent.inspection import host_root
from lqcd_agent.tools.dataset import snapshot_dataset


NORMALIZATION = b'''import json,sys,math
p=json.load(open(sys.argv[1]))
records={(r['pz'],r['bT'],r['bz'],r['sample_id']):r for r in p['records']}
def z(key):
 r=records[key];return complex(r['real'],r['imag'])
rows=[]
for r in p['records']:
 if (r['pz'],r['bT'])!=(p['target_pz'],p['target_bT']):continue
 sid=r['sample_id'];bz=r['bz'];P=p['target_pz'];B=p['target_bT']
 for mode in ('mode2','mode3'):
  value=z((P,B,bz,sid))/z((0,B,0,sid))
  if mode=='mode3':value=value*z((0,0,0,sid))/z((P,0,0,sid))
  rows.append(dict(mode=mode,bz=bz,sample_id=sid,success=True,real=value.real,imag=value.imag))
summaries=[]
for mode in ('mode2','mode3'):
 for bz in p['bz_values']:
  for component in ('real','imag'):
   values=sorted(r[component] for r in rows if (r['mode'],r['bz'])==(mode,bz))
   def q(f):
    i=(len(values)-1)*f;a=math.floor(i);b=math.ceil(i);return values[a]+(values[b]-values[a])*(i-a)
   lo,hi=q(.16),q(.84)
   summaries.append(dict(mode=mode,bz=bz,component=component,mean=(lo+hi)/2,error=(hi-lo)/2,n_valid=len(values)))
print(json.dumps(dict(status='ok',results=rows,summaries=summaries)))
'''
C2 = b'''import json,sys,math
p=json.load(open(sys.argv[1]));fixed=p['fixed_ground_energy']
e=math.hypot(p['ground_energy_at_rest'],2*math.pi*p['pz']/p['ns']) if fixed else .27
fits=[dict(nstates=n,tmin=t,tmax=p['tmax'],E0=e,E0_error=0 if fixed else .001,chi2_dof=1,bootstrap_successes=p['bootstrap_samples'],bootstrap_total=p['bootstrap_samples'],failed_sample_ids=[]) for n in (1,2) for t in p['tmins']]
print(json.dumps(dict(status='ok',fits=fits,ground_energy_fixed=fixed,dispersion_independently_tested=False)))
'''


def install_backend(monkeypatch, program):
    from lqcd_agent import research_codegen
    from lqcd_agent.code_agent.containment import DeterministicContainment
    from lqcd_agent.examples import SyntheticBackend
    prepare = research_codegen.prepare_research
    def fixture(coordinator, config, **options):
        containment = DeterministicContainment(coordinator.root/'containment')
        def backend(*_):
            value = SyntheticBackend(coordinator, coordinator.root/'research_repository', containment,
                                     files={'analysis.py': program})
            value.kind, value.version = 'fake', '0.1'
            return value
        with monkeypatch.context() as patch:
            patch.setattr(research_codegen, 'CodexCodingBackend', backend)
            patch.setattr(research_codegen, 'ProcessContainment', lambda _: containment)
            return prepare(coordinator, config, **{**options, 'live': True})
    monkeypatch.setattr(research_codegen, 'prepare_research', fixture)


def start_case(tmp_path, monkeypatch, family):
    monkeypatch.setenv('LQCD_AGENT_WORKSPACE',str(tmp_path))
    raw=tmp_path/'raw_data';raw.mkdir()
    payload=calibration(family)
    flag='fixed_ground_energy' if family=='c2' else 'omit_reference'
    parameters={flag:payload.pop(flag)}
    source=raw/'input.json';source.write_bytes(canonical_bytes(payload))
    config={'schema_version':'0.1','case_id':'generated','physics_goal':'Validate the specified synthetic scientific contract.',
        'raw_data_path':'raw_data/input.json','source_kind':'synthetic',
        'target_observables':[family+'_scientific_result'],
        'generated_program':{'python':sys.executable,'parameters':parameters,'timeout_seconds':10,
            'requirements':['Read JSON argv[1] and produce the requested finite scientific result.'], 'result_kind':family}}
    path=tmp_path/'case.json';path.write_bytes(canonical_bytes(config))
    install_backend(monkeypatch,C2 if family=='c2' else NORMALIZATION)
    return execute(ApplicationRequest('run',case_config=str(path),key='start')),source,config


def deliver(start):
    return execute(ApplicationRequest('resume',host=start['host'],**{
        'case':start['run_locator']['case_id'],'run':start['run_locator']['run_id']},
        pause=start['active_pause']['pause_id'],key='delivery'))


@pytest.mark.parametrize('family',['c2','normalization'])
def test_scientific_codegen_delivers_real_output_to_reviewer_and_human_gate(tmp_path,monkeypatch,family):
    start,source,config=start_case(tmp_path,monkeypatch,family)
    assert start['active_pause']['reason']=='external_result'
    before=source.read_bytes()
    final=deliver(start)
    assert final['run_status']=='paused' and final['active_pause']['reason']=='human_input',final
    root=host_root(final['host'])/final['run_locator']['case_id']/final['run_locator']['run_id']
    index=loads((root/'artifact_index.json').read_bytes())['current']
    assert all(index[slot]['status']=='success' for slot in ('plan','code','analysis','review'))
    assert index['approval']['status']=='pending' and index['terminal'] is None
    analysis=loads(Path(index['analysis']['state_paths']['run_result_path']).read_bytes())['domain_result']
    observed=analysis['run_result']['generated_execution']
    assert observed['dataset_snapshot']['exists'] and observed['execution']['input_sha256']
    assert (Path(analysis['analysis_outputs_dir'])/'generated_result.json').is_file()
    review=loads(Path(index['review']['state_paths']['scientific_review_report_path']).read_bytes())['domain_result']['report']
    assert review['generated_diagnostics']['status']=='pass' and review['generated_diagnostics']['findings']
    history=(root/'execution_history.jsonl').read_bytes()
    repeated=deliver(start)
    assert repeated==final and (root/'execution_history.jsonl').read_bytes()==history
    assert source.read_bytes()==before
    from lqcd_agent.control.coordinator import Coordinator
    from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
    from lqcd_agent.code_agent import execution
    with closing(Coordinator(host_root(final['host']))) as coordinator:
        capabilities=[loads(row[0]) for row in coordinator.connection.execute('SELECT value FROM invocation_capabilities')]
        preparation=next(c['authorization']['target_preparation'] for c in capabilities
            if c['authorization']['identity']['attempt_kind']=='analysis_engineer')
        handoff=AnalysisHandoff(coordinator,coordinator.root/'research_repository',
            allowed_command=[sys.executable,'-I','-B','analysis.py','input.json'],
            expected_outputs=['analysis_outputs/generated_result.json'],generated_program=config['generated_program'],workspace=tmp_path)
        original=execution.interpreter_identity
        with monkeypatch.context() as patch:
            patch.setattr(execution,'interpreter_identity',lambda python:{**original(python),'libraries':{'changed':'1'}})
            with pytest.raises(ControlIntegrityError,match='Frozen Analysis'):handoff.verify_preparation(preparation)
        manifest=loads(preparation['canonical_workspace_manifest_bytes'])
        (handoff.provider.path(manifest['workspace_id'])/'analysis.py').write_bytes(b'print("changed")\n')
        with pytest.raises(ControlIntegrityError):handoff.verify_preparation(preparation)


def test_changed_json_is_refused_before_generated_program_execution(tmp_path,monkeypatch):
    start,source,_=start_case(tmp_path,monkeypatch,'normalization')
    source.write_text('{}')
    final=deliver(start)
    root=host_root(final['host'])/final['run_locator']['case_id']/final['run_locator']['run_id']
    index=loads((root/'artifact_index.json').read_bytes())['current']
    assert index['analysis'] is None and index['review'] is None and index['terminal'] is None
    assert final['run_status'] in ('failed','paused')


def test_json_input_identity_rejects_duplicates_and_binds_parameters(tmp_path):
    from lqcd_agent.code_agent.execution import read_scientific_input
    raw=tmp_path/'raw_data';raw.mkdir();path=raw/'input.json'
    path.write_text('{"a":1,"a":2}')
    with pytest.raises(ControlIntegrityError):snapshot_dataset({'raw_data_path':'raw_data/input.json'},tmp_path)
    path.write_text('{"a":1}')
    identity=snapshot_dataset({'raw_data_path':'raw_data/input.json'},tmp_path)
    with pytest.raises(ControlIntegrityError,match='replace source'):read_scientific_input(tmp_path,identity,{'a':2})
    assert read_scientific_input(tmp_path,identity,{'new_parameter':True})=={'a':1,'new_parameter':True}


def test_empty_generated_contract_is_rejected_instead_of_selecting_registered_execution(tmp_path):
    from lqcd_agent.control.coordinator import Coordinator
    from lqcd_agent.runtime import assemble,create_host
    from lqcd_agent.science import ScientificAgent
    with closing(Coordinator(create_host())) as coordinator:
        with pytest.raises(ControlIntegrityError,match='Non-closed'):
            assemble(coordinator,ScientificAgent(coordinator.root,{'generated_program':{}},workspace=tmp_path),
                live=True,workflow='scientific')


def test_nonzero_analysis_exit_cannot_be_overridden_by_agent_success(monkeypatch):
    from lqcd_agent import runtime
    assemble=runtime.assemble
    def failure(*args,**kwargs):
        result=assemble(*args,**kwargs)
        if result[0].analysis_handoff is not None:
            monkeypatch.setattr(result[0].analysis_handoff,'execute',lambda _: {'returncode':1,'stdout':'','stderr':'failed'})
        return result
    monkeypatch.setattr(runtime,'assemble',failure)
    start=execute(ApplicationRequest('start',workflow='code',key='failed-analysis'))
    final=deliver(start)
    root=host_root(final['host'])/final['run_locator']['case_id']/final['run_locator']['run_id']
    current=loads((root/'artifact_index.json').read_bytes())['current']
    assert current['analysis']['status']=='failed'
    assert current['terminal'] is None and final['run_status']=='paused'


def test_pending_implementation_plan_is_retained_without_starting_code(tmp_path,monkeypatch):
    from lqcd_agent.science import ScientificAgent
    monkeypatch.setattr('lqcd_agent.agents.method_planner.run_method_planner',lambda **_:
        {'status':'pending','code_needed':True,'code_request':None})
    agent=ScientificAgent(tmp_path,{'generated_program':{}},workspace=tmp_path)
    outcome=agent.run('method_planner',{'identity':{'attempt_id':'a','case_id':'c','run_id':'r'},
        'root_goal':{'goal':'Plan the implementation','dataset_snapshot':None}},timeout_seconds=1)
    assert outcome['content']['code_needed'] is False
    assert outcome['content']['domain_result']['status']=='pending'
    assert outcome['diagnostic']['human_need']=='approval'


def test_generated_scientific_cancel_restores_stop_adapter_without_execution_dependencies(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from lqcd_agent import runtime
    from lqcd_agent.code_agent.external_operation import CodeExternalStop
    root=runtime.create_host()
    run=root/'generated'/'run-cancel';run.mkdir(parents=True)
    (run/'root_goal.json').write_bytes(canonical_bytes({'workflow':'scientific','live':True,
        'workspace':'/unavailable-workspace','case_config':{'generated_program':{'python':'/unavailable-python'}}}))
    def unavailable(*_,**__):
        pytest.fail('Cancellation must not load credentials, data or a scientific interpreter')
    monkeypatch.setattr(runtime,'workspace_root',unavailable)
    monkeypatch.setattr('lqcd_agent.settings.ApplicationSettings.load',unavailable)
    monkeypatch.setattr('lqcd_agent.science.ScientificAgent',unavailable)
    def cancel(request,*,actor):
        assert isinstance(plane.external_adapter,CodeExternalStop)
        assert plane.external_adapter.backend.root==root/'coding_jobs'
        assert request.run_locator=={'case_id':'generated','run_id':'run-cancel'}
    plane=SimpleNamespace(cancel_pause=cancel)
    monkeypatch.setattr(runtime,'host_root',lambda _:root)
    monkeypatch.setattr(runtime,'assemble',lambda *_,**__: (SimpleNamespace(plane=plane),object(),None))
    monkeypatch.setattr(runtime,'read_snapshot',lambda *_: SimpleNamespace(status=lambda:{'cancelled':True}))
    assert execute(ApplicationRequest('cancel',host='test',case='generated',run='run-cancel',pause='pause',key='cancel'))=={'cancelled':True}


@pytest.mark.parametrize('corrupt',[False,True])
def test_generated_diagnostics_survive_provider_review_without_raw_replica_context(tmp_path,corrupt):
    from lqcd_agent.agents.scientific_reviewer import run_scientific_reviewer
    from lqcd_agent.llm.mock_provider import MockLLMProvider
    from tests.test_research_cases import normalized_control
    payload=calibration('normalization');payload.update(lineage_limit='Original resampling correspondence is unavailable.',private_probe='PRIVATE_REPLICA_SENTINEL')
    result=normalized_control()
    if corrupt:result['results'][0]['real']=1
    outputs=tmp_path/'analysis_outputs';outputs.mkdir()
    (outputs/'generated_result.json').write_bytes(canonical_bytes(result))
    run=tmp_path/'run_result.json';run.write_bytes(canonical_bytes({'run_success':True,
        'generated_execution':{'result_kind':'normalization'},'analysis_outputs_dir':str(outputs)}))
    class Capture(MockLLMProvider):
        def generate(self,request):
            self.request=request
            return super().generate(request)
    provider=Capture()
    reviewed=run_scientific_reviewer(run_id='r',case_id='c',run_output_dir=tmp_path,
        run_result_path=run,provider=provider,generated_input=payload)
    assert reviewed['report']['generated_diagnostics']['status']==('severe' if corrupt else 'warning')
    assert reviewed['confidence']==('low' if corrupt else 'medium')
    assert 'PRIVATE_REPLICA_SENTINEL' not in json.dumps(provider.request.messages)
    assert 'generated_diagnostics' in provider.request.context_sources['review_evidence']


def test_generated_review_keeps_full_production_summary_without_irrelevant_artifact_scans(tmp_path,monkeypatch):
    from copy import deepcopy
    from lqcd_agent.agents import scientific_reviewer as reviewer
    from lqcd_agent.llm.mock_provider import MockLLMProvider
    from tests.test_research_cases import normalized_control
    payload=calibration('normalization');payload['bz_values']=[0,2,4]
    target=[r for r in payload['records'] if (r['pz'],r['bT'])==(6,2)]
    payload['records'].extend({**r,'bz':bz} for bz in (2,4) for r in target)
    payload['lineage_limit']='The original resampling-index plan is unavailable.'
    result=normalized_control()
    for field in ('results','summaries'):
        original=deepcopy(result[field])
        result[field].extend({**r,'bz':bz} for bz in (2,4) for r in original)
    outputs=tmp_path/'analysis_outputs';outputs.mkdir()
    (outputs/'generated_result.json').write_bytes(canonical_bytes(result))
    run=tmp_path/'run_result.json';run.write_bytes(canonical_bytes({'run_success':True,
        'generated_execution':{'result_kind':'normalization'},'analysis_outputs_dir':str(outputs)}))
    plan=tmp_path/'method_plan.json';steps=[f'Step {i}: '+('Preserve paired complex resampling, reference identity and explicit failure masks. '*2) for i in range(7)]
    plan.write_bytes(canonical_bytes({'status':'success','physics_goal':'Assess complex normalization.',
        'method_steps':steps,'warnings':[{'message':'Keep the unavailable original resampling plan explicit.'}]}))
    def irrelevant(*_):
        pytest.fail('Generated output must use its own numerical contract')
    monkeypatch.setattr(reviewer,'diagnose_correlator_outputs',irrelevant)
    monkeypatch.setattr(reviewer,'diagnose_fit_outputs',irrelevant)
    class Capture(MockLLMProvider):
        def generate(self,request):
            self.request=request
            return super().generate(request)
    provider=Capture()
    reviewed=reviewer.run_scientific_reviewer(run_id='r',case_id='c',run_output_dir=tmp_path,
        run_result_path=run,method_plan_path=plan,provider=provider,generated_input=payload)
    assert reviewed['status']=='success',reviewed
    assert provider.request.max_tokens==4096
    view=json.loads(provider.request.messages[1]['content'])
    assert view['method_plan_summary']['method_steps']==steps
    assert len(view['review_evidence']['findings'])==12
    assert view['review_evidence']['warnings'][0]['code']=='resampling_lineage_unverified'
    assert reviewed['report']['correlator_diagnostics']['status']=='not_applicable'
    assert reviewed['report']['fit_diagnostics']['status']=='not_applicable'
