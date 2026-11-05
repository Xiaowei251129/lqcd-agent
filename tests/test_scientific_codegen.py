"""Exercise scientific assembly with a deterministic backend, actual processes and Host review."""
from pathlib import Path
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
import sys

import pytest

from lqcd_agent.control.strict_json import digest, ControlIntegrityError, canonical_bytes, loads
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
if not fixed:fits[0]['E0_error']=1e20
print(json.dumps(dict(status='ok',fits=fits,ground_energy_fixed=fixed,dispersion_independently_tested=False,fixture_evidence='serialized-read-'*1000)))
'''


def install_backend(monkeypatch, program):
    from lqcd_agent import research_codegen
    from lqcd_agent.code_agent.containment import DeterministicContainment
    from lqcd_agent.examples import SyntheticBackend
    prepare = research_codegen.prepare_research
    def fixture(coordinator, config, **options):
        containment = DeterministicContainment(coordinator.root/'containment')
        def backend(*_, coordinator):
            value = SyntheticBackend(coordinator, next((coordinator.root/'research_repositories').iterdir()), containment,
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
        pause=start['active_pause']['pause_id'],
        key='delivery-'+digest([start['run_locator'],start['active_pause']['pause_id']])))


def test_settled_analysis_exception_closes_with_original_error_and_no_exit_code(tmp_path, monkeypatch):
    from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
    message = 'Process inspection denied before numerical output'
    def denied(*_):
        raise PermissionError(message)
    monkeypatch.setattr(AnalysisHandoff, 'execute', denied)
    pending, _, _ = start_case(tmp_path, monkeypatch, 'normalization')
    finished = deliver(pending)
    assert finished['run_status'] == 'completed' and finished['active_pause'] is None
    locator = finished['run_locator']
    root = host_root(finished['host'])/locator['case_id']/locator['run_id']
    analysis = loads((root/'run_result.json').read_bytes())
    assert analysis['status'] == 'failed' and 'execution' not in analysis
    assert analysis['errors'] == [{'type':'OrdinaryResourceFailure', 'message':message}]
    rows = [loads(row) for row in (root/'execution_history.jsonl').read_bytes().splitlines()]
    settlement, = [r for r in rows if r.get('event') == 'resource_settled' and
                   r['payload']['resource_operation_id'].endswith(':analysis-subprocess')]
    assert settlement['payload']['actual'] is None
    failed, = [r['payload']['fingerprint'] for r in rows if r.get('event') == 'failure_observed'
               and r['payload']['fingerprint']['code'] == 'execution_failure']
    assert failed['diagnostics']['exit_code'] is None
    assert not loads((root/'memory_update.json').read_bytes())['accepted_result']


@pytest.mark.parametrize('family',['c2','normalization'])
def test_scientific_codegen_delivers_real_output_to_autonomous_report(tmp_path,monkeypatch,family):
    from lqcd_agent.science import ScientificAgent
    review_contexts, attempted_mutations = [], []
    original_run = ScientificAgent.run
    def observe_and_mutate(agent, node, context, *, timeout_seconds):
        if node == 'scientific_reviewer':
            review_contexts.append(deepcopy(context))
        outcome = original_run(agent, node, context, timeout_seconds=timeout_seconds)
        if node == 'analysis_engineer' and family == 'c2':
            context['analysis_execution']['result']['fits'][0]['E0_error'] = 0.0
            context['analysis_execution']['result']['fixture_evidence'] = 'Agent mutation must not replace Host output.'
            attempted_mutations.append(True)
        return outcome
    monkeypatch.setattr(ScientificAgent, 'run', observe_and_mutate)
    start,source,config=start_case(tmp_path,monkeypatch,family)
    assert start['active_pause']['reason']=='external_result'
    before=source.read_bytes()
    final=deliver(start)
    assert final['run_status']=='completed' and final['active_pause'] is None,final
    root=host_root(final['host'])/final['run_locator']['case_id']/final['run_locator']['run_id']
    index=loads((root/'artifact_index.json').read_bytes())['current']
    task=loads((root/'code_agent_control'/index['code']['attempt_id']/'code_agent_task.json').read_bytes())
    records=[loads(row) for row in (root/'execution_history.jsonl').read_bytes().splitlines()]
    backend=next(row['payload'] for row in records if row.get('event')=='resource_reserved' and
        row['payload']['resource_kind']=='code_backend_operation')
    # Native work must finish inside its original reservation with room to verify and seal.
    assert task['tool_policy'][0]['timeout_seconds'] + sum(
        spec['timeout_seconds'] for spec in task['verification_specs']) < backend['maximum_charge']['active_seconds']
    assert all(index[slot]['status']=='success' for slot in ('plan','code','analysis','review'))
    assert index['approval'] is None and index['terminal']['status']=='accepted'
    assert not any(row['record_type']=='human_response' for row in records)
    analysis=loads(Path(index['analysis']['state_paths']['run_result_path']).read_bytes())['domain_result']
    observed=analysis['run_result']['generated_execution']
    assert observed['dataset_snapshot']['exists'] and observed['execution']['input_sha256']
    result_path=Path(analysis['analysis_outputs_dir'])/'generated_result.json'
    assert result_path.is_file()
    numeric_member=next(member for member in index['analysis']['members']
                        if member['logical_name']=='analysis_outputs/generated_result.json')
    numeric_path=root/numeric_member['canonical_path']
    numeric_bytes=numeric_path.read_bytes()
    assert numeric_bytes==result_path.read_bytes()
    assert numeric_member['sha256']==sha256(numeric_bytes).hexdigest()
    assert analysis['member_digests'][str(result_path.relative_to(host_root(final['host'])))]==numeric_member['sha256']
    assert not any(member['logical_name']=='analysis_outputs/result.json' for member in index['analysis']['members'])
    assert len(review_contexts)==1
    reference={'artifact_id':index['analysis']['artifact_id'], 'member':numeric_member['canonical_path'],
               'sha256':numeric_member['sha256']}
    assert reference in review_contexts[0]['current_evidence']
    review=loads(Path(index['review']['state_paths']['scientific_review_report_path']).read_bytes())['domain_result']['report']
    assert review['generated_diagnostics']['status']=='pass' and review['generated_diagnostics']['findings']
    if family=='c2':
        result=loads(result_path.read_bytes())
        assert result['fits'][0]['E0_error']==1e20 and type(result['fits'][0]['E0_error']) is float
        finding=next(item for item in review['generated_diagnostics']['findings'] if 'error=1e+20' in item)
        assert finding in review['findings']
        assert finding in Path(index['terminal']['state_paths']['final_report_path']).read_text()
        assert attempted_mutations==[True] and len(result['fixture_evidence'])>12000
        import ast
        from openai.types.responses import ResponseFunctionToolCall
        from lqcd_agent.research.agent_runtime import ResearchAgentRuntime
        from lqcd_agent.research.tools import build_tools
        from tests.test_research_agent_runtime import ScriptedModel, arguments, message
        section=digest(reference)
        def read_call(identifier, section_name, offset=0):
            return ResponseFunctionToolCall(type='function_call', name='read_context', call_id=identifier,
                arguments=json.dumps({'section':section_name,'offset':offset}))
        tools=build_tools(tmp_path,review_contexts[0],host=host_root(final['host']),output_dir=tmp_path/'sdk-read',
            sources={'run_result': analysis['run_result'], 'review_evidence': review})
        model=ScriptedModel([[read_call('catalog','catalog')],
            [read_call('formal',section)],
            [message('The complete Host numeric evidence is readable; this is not physics acceptance.')]])
        events=[]
        ResearchAgentRuntime(model,max_output_tokens=512).run_sync(**{
            **arguments(events.append,tools),'max_turns':3})
        responses={event['call_id']:ast.literal_eval(event['result']) if isinstance(event['result'],str)
                   else event['result'] for event in events if event['event']=='tool_end'}
        assert responses['catalog']['registered_evidence'][section]==reference
        assert responses['formal']['next_offset'] is None and responses['formal']['text'].encode()==numeric_bytes
        assert responses['formal']['sha256']==numeric_member['sha256']
        assert loads(responses['formal']['text'].encode())['fits'][0]['E0_error']==1e20
        numeric_path.write_bytes(b'changed')
        try:
            with pytest.raises(ControlIntegrityError,match='Research evidence changed'):
                ResearchAgentRuntime(ScriptedModel([[read_call('tampered',section)],
                    [message('Unreachable')]]),max_output_tokens=512).run_sync(**arguments(events.append,tools))
        finally:
            numeric_path.write_bytes(numeric_bytes)
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
        handoff=AnalysisHandoff(coordinator,next((coordinator.root/'research_repositories').iterdir()),
            allowed_command=[sys.executable,'-I','-B','analysis.py','input.json'],
            expected_outputs=['analysis_outputs/generated_result.json'],generated_program=config['generated_program'],workspace=tmp_path)
        handoff.verify_preparation(preparation)
        manifest=loads(preparation['canonical_workspace_manifest_bytes'])
        program=(handoff.provider.path(manifest['workspace_id'])/'analysis.py').read_bytes()
        assert program==(C2 if family=='c2' else NORMALIZATION)
        assert sha256(program).hexdigest()==observed['execution']['program_sha256']
        original=execution.interpreter_identity
        with monkeypatch.context() as patch:
            patch.setattr(execution,'interpreter_identity',lambda python:{**original(python),'libraries':{'changed':'1'}})
            with pytest.raises(ControlIntegrityError,match='Frozen Analysis'):handoff.verify_preparation(preparation)
        (handoff.provider.path(manifest['workspace_id'])/'analysis.py').write_bytes(b'print("changed")\n')
        with pytest.raises(ControlIntegrityError):handoff.verify_preparation(preparation)


@pytest.mark.parametrize('expire', [False, True])
def test_code_consumption_funds_publication_without_extending_execution_authority(tmp_path, monkeypatch, expire):
    from lqcd_agent.control.capabilities import InvocationLeases
    from lqcd_agent.control.clock import FakeClock
    from lqcd_agent.control.coordinator import Coordinator, read_regular
    from lqcd_agent.control.pause import ResumeRunRequest
    from lqcd_agent.inspection import read_snapshot
    from lqcd_agent.runtime import assemble, scientific_agent
    start, _, config = start_case(tmp_path, monkeypatch, 'normalization')
    host, locator = host_root(start['host']), start['run_locator']
    root = host/locator['case_id']/locator['run_id']
    clock, observed = FakeClock(100, 0), []
    def observer(name, side, value):
        if (name, side) != ('external.trusted_verification', 'after'):
            return
        row, = [row for row in coordinator.connection.execute('SELECT capability_id,value FROM invocation_capabilities')
                if loads(row['value'])['authorization'].get('activation_kind') == 'active_within_resume']
        leases = InvocationLeases(coordinator)
        _, capability = leases.get(row['capability_id'])
        owner = coordinator.get(capability['authorization']['producer_operation_id'])
        elapsed = capability['deadline'] - clock.now().monotonic_seconds + 1 if expire else 35
        assert owner['lease_expires'] > capability['deadline'] > 30
        assert all(entry['published'] for entry in capability['verification_intents'])
        assert capability['verification_intents'][-1]['record']['payload']['actual'] is not None
        observed.append((row['capability_id'], capability['deadline']))
        clock.advance(elapsed)
        if expire:
            with pytest.raises(ControlIntegrityError, match='Stale or expired invocation lease'):
                leases.require_effect_authority(row['capability_id'], capability['worker_id'], capability['invocation_epoch'])
    with closing(Coordinator(host, clock=clock, observer=observer)) as coordinator:
        runtime, actor, code = assemble(coordinator, scientific_agent(host, config, None, tmp_path), workflow='scientific')
        assert runtime.plane.lease_seconds == code.lease_seconds
        opened = next(row for row in reversed(runtime._records(locator)[1].values) if row.get('event') == 'pause_opened')
        producer = opened['input_contract']['producer_operation_id']
        delivery = host/'synthetic_deliveries'/producer
        final = code.finalize(producer, tool_audit=read_regular(delivery/'tool-audit.jsonl'),
                              patch=read_regular(delivery/'patch.diff'))
        payload = {'producer_operation_id': producer, 'external_final_digest': final['terminal_evidence_digest']}
        request = ResumeRunRequest(locator, opened['pause_id'], 'publication-window', 'external_result', payload, digest(payload))
        result = runtime.resume_control(request, actor=actor)
        assert len(observed) == 1
        cap_id, deadline = observed[0]
        _, capability = InvocationLeases(coordinator).get(cap_id)
        assert capability['deadline'] == deadline
        index = loads(read_regular(root/'artifact_index.json'))['current']
        if expire:
            assert result['operation_status'] == 'recovery_required' and result['terminal_closure'] == 'unavailable'
            assert capability['state'] == 'uncertain' and capability.get('completion_intent') is None
            assert index['code'] is index['analysis'] is index['terminal'] is None
        else:
            assert result['operation_status'] == 'committed' and result['run_status'] == 'running'
            assert capability['state'] == 'finished' and capability['invocation_epoch'] == 1
            assert index['code']['status'] == 'success'
        history = read_regular(root/'execution_history.jsonl')
        assert runtime.resume_control(request, actor=actor) == result
        assert len(observed) == 1 and read_regular(root/'execution_history.jsonl') == history
        records = runtime._records(locator)[1].values
        assert sum(row.get('event') == 'started' and row.get('attempt_id') == opened['target_attempt_id'] for row in records) == 1
        assert not any(row['record_type'] in ('human_request', 'human_response') for row in records)
        if not expire:
            runtime.run(locator)
            snapshot = read_snapshot(host, locator)
            assert snapshot.state['run_status'] == 'completed' and not snapshot.can_advance
            index = loads(read_regular(root/'artifact_index.json'))['current']
            analysis = loads(Path(index['analysis']['state_paths']['run_result_path']).read_bytes())['domain_result']
            assert analysis['run_success'] is True and index['terminal']['status'] == 'accepted'


def test_changed_json_is_refused_before_generated_program_execution(tmp_path,monkeypatch):
    from lqcd_agent.inspection import read_snapshot
    start,source,_=start_case(tmp_path,monkeypatch,'normalization')
    host=host_root(start['host'])
    locator=start['run_locator']
    root=host/locator['case_id']/locator['run_id']
    original=loads((root/'root_goal.json').read_bytes())['dataset_snapshot']
    source.write_text('{}')
    with pytest.raises(ControlIntegrityError,match='Scientific dataset changed before consumption'):
        deliver(start)
    final=execute(ApplicationRequest('status',host=start['host'],case=locator['case_id'],run=locator['run_id']))
    snapshot=read_snapshot(host,locator)
    failed=next(row for row in reversed(snapshot.records.values) if row['record_type']=='attempt')
    assert failed['event']=='finished' and failed['status']=='failed' and failed['error']['type']=='ControlIntegrityError'
    assert not snapshot.can_advance
    assert final['run_status']=='failed' and final['active_pause'] is None
    assert snapshot.closure['terminal_closure']=='committed' and snapshot.closure['run_status']=='failed'
    assert final['execution_failure']['source']=='committed_control_closure'
    assert final['execution_failure']['closure_sha256']==digest(snapshot.closure)
    assert final['execution_failure']['scientific_outcome']=='inconclusive'
    assert final['execution_failure']['decision_origin']=='system'
    assert loads((root/'root_goal.json').read_bytes())['dataset_snapshot']==original
    index=loads((root/'artifact_index.json').read_bytes())['current']
    assert all(index[slot] is None for slot in ('analysis','review','terminal','approval'))
    starts=[row for row in snapshot.records.values if row.get('record_type')=='attempt'
        and row['event']=='started' and row['attempt_kind']=='analysis_engineer']
    assert len(starts)==1
    assert not any(row['record_type'] in ('human_request','human_response') for row in snapshot.records.values)


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
    assert final['run_status']=='completed' and final['active_pause'] is None
    assert current['terminal']['status']=='rejected' and current['approval'] is None
    conclusion=loads(Path(current['terminal']['state_paths']['memory_update_path']).read_bytes())
    assert conclusion['scientific_outcome']=='inconclusive' and conclusion['decision_origin']=='system'
    records=[loads(row) for row in (root/'execution_history.jsonl').read_bytes().splitlines()]
    assert not any(row['record_type']=='human_response' for row in records)


def test_pending_implementation_plan_is_retained_without_starting_code(tmp_path,monkeypatch):
    from lqcd_agent.science import ScientificAgent
    monkeypatch.setattr('lqcd_agent.agents.method_planner.run_method_planner',lambda **_:
        {'status':'pending','code_needed':True,'code_request':None})
    agent=ScientificAgent(tmp_path,{'generated_program':{}},workspace=tmp_path)
    outcome=agent.run('method_planner',{'identity':{'attempt_id':'a','case_id':'c','run_id':'r'},
        'root_goal':{'goal':'Plan the implementation','dataset_snapshot':None}},timeout_seconds=1)
    assert outcome['content']['code_needed'] is False
    assert outcome['content']['domain_result']['status']=='pending'
    assert outcome['diagnostic']['status']=='failed' and outcome['diagnostic']['category']=='implementation_gap'
    assert outcome['diagnostic']['human_need'] is None


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
    plan=tmp_path/'method_plan.json';steps=[f'Step {i}: '+('Preserve paired complex resampling, reference identity and explicit failure masks. '*2) for i in range(70)]
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
    view=json.loads(provider.request.messages[1]['content'])
    assert 'method_steps' not in view['method_plan_summary']
    assert view['method_plan_summary']['method_step_count']==len(steps)
    assert "read_context(section='method_plan')" in view['method_plan_summary']['method_steps_source']
    from lqcd_agent.llm.context import read_context_evidence
    assert read_context_evidence(tmp_path,view['evidence_catalog'],'method_plan')['method_steps']==steps
    assert len(view['review_evidence']['findings'])==12
    assert view['review_evidence']['warnings'][0]['code']=='resampling_lineage_unverified'
    assert reviewed['report']['correlator_diagnostics']['status']=='not_applicable'
    assert reviewed['report']['fit_diagnostics']['status']=='not_applicable'
