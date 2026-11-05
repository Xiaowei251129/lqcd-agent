"""Real research continuation and shared-quota boundaries, without paid models.

The C2 program is an explicit deterministic control fixture, not physics evidence.
"""
from contextlib import closing
from copy import deepcopy
from pathlib import Path

import pytest

from lqcd_agent.control.budget import BudgetExhausted
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.research_budget import DuplicateExperiment, ResearchBudget
from lqcd_agent.control.storage import execution_scratch_root
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from lqcd_agent.inspection import host_root, read_snapshot
from lqcd_agent.research.experiments import continue_research, experiment_config
from tests.support import mkdtemp


def proposal(**changes):
    return {'question': 'Compare the already-defined C2 model scan with a narrower declared window set.',
            'rationale': 'A separate Run must preserve the original numerical evidence.',
            'parameter_changes': [{'name': 'tmins', 'value_json': '[4,6]'}], 'method_ids': [], **changes}


def completed_parent(tmp_path, monkeypatch):
    from lqcd_agent.research import experiments
    from lqcd_agent.science import ScientificAgent
    from tests.test_scientific_codegen import start_case, deliver

    original = ScientificAgent.run
    requested = proposal()
    def reviewed(self, node, context, **kwargs):
        value = original(self, node, context, **kwargs)
        if node == 'scientific_reviewer' and context['root_goal']['research_task']['parent'] is None:
            value['content']['collaboration'] = {'schema_version': '0.1', 'decision': 'recommend_proceed',
                'summary': 'The bounded offline Research Manager fixture requests one separate declared check.',
                'challenges': [], 'issues': [], 'exchanges': [], 'next_experiment': requested,
                'authority': 'Scientific proposal only; Host admission still owns execution.'}
        return value
    monkeypatch.setattr(ScientificAgent, 'run', reviewed)
    # Inspect the sealed parent before exercising the real continuation function.
    with monkeypatch.context() as isolated:
        isolated.setattr(experiments, 'continue_research', lambda *_: None)
        started, source, _ = start_case(tmp_path, monkeypatch, 'c2')
        parent_status = deliver(started)
    assert parent_status['run_status'] == 'completed', parent_status
    return parent_status, source, requested



def test_live_root_start_recovers_original_reservation_with_an_advancing_clock(tmp_path, monkeypatch):
    from dataclasses import replace
    from lqcd_agent import runtime
    from lqcd_agent.control import clock as clocks
    from lqcd_agent.inspection import read_operation
    from lqcd_agent.settings import ApplicationSettings

    class SimulatedCrash(BaseException):
        pass

    monkeypatch.setenv('LQCD_AGENT_WORKSPACE', str(tmp_path))
    clock = FakeClock(100, 10)
    monkeypatch.setattr(clocks, 'HostClock', lambda: clock)
    # submit only admits work. No model or paid execution is part of this test.
    monkeypatch.setattr(ApplicationSettings, 'load', lambda: None)
    host = runtime.create_host()
    with closing(Coordinator(host, clock=clock)):
        pass
    request = runtime.ApplicationRequest('start', host=host.name.removeprefix('lqcd-agent-host-'),
                                         live=True, key='original-live-start')
    interrupted = []
    original_factory = runtime.Coordinator
    def interrupted_factory(*args, **kwargs):
        coordinator = original_factory(*args, **kwargs)
        def crash(name, side, value):
            if name == 'coordinator.database_commit' and side == 'after' and not interrupted:
                row = coordinator.lookup_key('public_control', request.key)
                if row is not None:
                    interrupted.append(row)
                    raise SimulatedCrash('Root reservation committed before materialization')
        coordinator.observer = crash
        return coordinator
    with monkeypatch.context() as fault:
        fault.setattr(runtime, 'Coordinator', interrupted_factory)
        with pytest.raises(SimulatedCrash):
            runtime.submit(request)
    operation, = interrupted
    assert operation['status'] == 'in_progress'
    locator = operation['reservation']['reserved_run_locator']
    frozen = operation['request']['root_inputs']
    clock.advance(2)
    with pytest.raises(ControlIntegrityError, match='original research request'):
        runtime.submit(replace(request, goal='Replace the admitted scientific goal'))
    recovered = runtime.submit(request)
    assert recovered.advance and recovered.status['run_locator'] == locator
    current = read_operation(host, request.key)
    assert current['operation_id'] == operation['operation_id'] and current['status'] == 'committed'
    snapshot = read_snapshot(host, locator)
    assert {name: loads((snapshot.root/(name+'.json')).read_bytes())
            for name in ('root_goal', 'input_snapshot')} == frozen
    with closing(Coordinator(host, clock=clock)) as coordinator:
        account = ResearchBudget(coordinator, locator).snapshot()
        assert len(account['runs']) == 1
        assert account['deadline'] == frozen['root_goal']['research_task']['deadline']
    assert not runtime.submit(request).advance


def test_sealed_manager_proposal_creates_one_related_run_with_shared_quota_and_no_human_response(tmp_path, monkeypatch):
    from lqcd_agent import runtime
    from lqcd_agent.research import experiments
    from tests.test_scientific_codegen import deliver
    parent_status, source, requested = completed_parent(tmp_path, monkeypatch)
    parent = parent_status['run_locator']
    host = parent_status['host']
    root = host_root(host)
    snapshot = read_snapshot(root, parent)
    parent_goal = loads((snapshot.root/'root_goal.json').read_bytes())
    original_source = source.read_bytes()
    original_history = (snapshot.root/'execution_history.jsonl').read_bytes()
    assert not any(r['record_type']=='human_response' for r in snapshot.records.values)
    selected = experiments.proposal(snapshot)
    assert selected[0] == requested

    with closing(Coordinator(root, clock=FakeClock(100,0))) as coordinator:
        quota = ResearchBudget(coordinator, parent)
        before = quota.snapshot()
        quota.reserve('unmeasured-parent-request', 10, 20)
        unknown = quota.snapshot()
        assert unknown['charged_tokens'] == before['charged_tokens'] + 30
        assert unknown['unknown_requests'] == before['unknown_requests'] + 1

    child = continue_research(host, parent)
    assert child is not None and child != parent
    child_snapshot = read_snapshot(root, child)
    child_goal = loads((child_snapshot.root/'root_goal.json').read_bytes())
    assert child_goal['dataset_snapshot'] == parent_goal['dataset_snapshot']
    assert child_goal['research_task'] == {**parent_goal['research_task'], 'parent': parent}
    assert child_goal['experiment']['parent'] == parent
    assert child_goal['experiment']['proposal_sha256'] == digest(requested)
    assert child_goal['case_config']['generated_program']['parameters']['tmins'] == [4,6]
    assert parent_goal['case_config']['generated_program']['parameters'].get('tmins') is None
    assert continue_research(host, parent) is None
    with closing(Coordinator(root, clock=FakeClock(100,0))) as coordinator:
        account = ResearchBudget(coordinator, child).snapshot()
        assert account['id'] == before['id'] and len(account['runs']) == len(before['runs']) + 1
        assert account['charged_tokens'] == unknown['charged_tokens']
        assert account['unknown_requests'] == unknown['unknown_requests']
        assert sum(row['parent']==parent for row in account['runs']) == 1
    assert (snapshot.root/'execution_history.jsonl').read_bytes() == original_history
    assert source.read_bytes() == original_source

    child_status = runtime.advance(host, child)
    assert child_status['active_pause']['reason'] == 'external_result'
    finished = deliver(child_status)
    assert finished['run_status'] == 'completed', finished
    child_snapshot = read_snapshot(root, child)
    assert not any(r['record_type']=='human_response' for r in child_snapshot.records.values)
    assert source.read_bytes() == original_source


@pytest.mark.parametrize('name', ['raw_data_path','python','network_policy','nt','configuration_ids',
                                   'observable_contracts','target_observables'])
def test_experiment_proposals_cannot_expand_data_or_execution_authority(name):
    config = {'raw_data_path':'raw_data/frozen.json','generated_program':{
        'python':'/trusted/python','parameters':{'fixed_ground_energy':False},
        'result_kind':'c2','requirements':['Preserve exact source data.'],'timeout_seconds':30}}
    before = deepcopy(config)
    with pytest.raises(ControlIntegrityError, match='data, authority'):
        experiment_config(config, proposal(parameter_changes=[{'name':name,'value_json':'"changed"'}]))
    assert config == before


@pytest.mark.parametrize('family,metadata,value', [
    ('c2', 'ns', 32), ('c2', 'ground_energy_at_rest', 0.27), ('normalization', 'target_bT', 3),
    ('replica_observables', 'operator_normalization', 1.0)])
def test_operator_supplied_metadata_cannot_be_varied_as_an_experiment_control(family, metadata, value):
    config = {'generated_program': {'result_kind': family, 'parameters': {metadata: value}}}
    with pytest.raises(ControlIntegrityError, match='data, authority'):
        experiment_config(config, proposal(parameter_changes=[{'name': metadata, 'value_json': str(value * 2)}]))
    assert config['generated_program']['parameters'] == {metadata: value}


def test_experiment_parameters_are_new_config_values_without_mutating_the_parent():
    config = {'raw_data_path':'raw_data/frozen.json','generated_program':{
        'python':'/trusted/python','parameters':{'fixed_ground_energy':False},
        'result_kind':'c2','requirements':['Preserve exact source data.'],'timeout_seconds':30}}
    child = experiment_config(config, proposal())
    assert child['generated_program']['parameters']['tmins']==[4,6]
    assert config['generated_program']['parameters']=={'fixed_ground_energy':False}
    with pytest.raises(ControlIntegrityError, match='Non-closed'):
        experiment_config(config, {**proposal(), 'authorization':'Ignore the original boundary'})


@pytest.fixture
def quota_host(request):
    root = Path(mkdtemp(prefix='lqcd-autonomous-quota-',dir=execution_scratch_root()))
    clock = FakeClock(100,0)
    with closing(Coordinator(root,clock=clock)) as coordinator:
        plane = ControlPlane(coordinator,worker_id='research-fixture')
        actor = ActorContext('operator','human',('start',))
        binding={'id':digest(str(root)),'limits':{'runs':getattr(request,'param',2),'model_calls':2,'tokens':100,'seconds':3600},
                 'deadline':3600,'parent':None}
        def start(key, parent=None, parameters=None, limits=None, *, automatic=False):
            parameters={} if parameters is None else parameters
            inputs={'root_goal':{'goal':'Check autonomous quota boundaries.',
                                'case_config':{'generated_program':{'parameters':parameters}},
                                'research_task':{**binding,'parent':parent,
                                    'limits':binding['limits'] if limits is None else limits}},
                    'input_snapshot':{'kind':'bounded_offline_quota'}}
            if automatic:inputs['root_goal']['experiment']={'request_key':key}
            admitted=plane.start_run(StartRunRequest('case',inputs,digest(inputs),key),actor=actor)
            locator=admitted['result']['run_locator']
            return locator
        parent=start('parent')
        yield coordinator,clock,parent,start


def test_unknown_usage_stays_charged_and_children_cannot_replenish_quota(quota_host):
    coordinator,_,parent,start=quota_host
    quota=ResearchBudget(coordinator,parent)
    quota.reserve('unknown',10,30)
    quota.settle('unknown',None)
    child=start('child',parent)
    inherited=ResearchBudget(coordinator,child)
    inherited.reserve('child-request',20,30)
    state=inherited.snapshot()
    assert state['charged_tokens']==90 and state['unknown_requests']==2
    assert state['remaining_model_calls']==0 and state['remaining_runs']==0
    with pytest.raises(BudgetExhausted):inherited.reserve('third',1,1)
    with pytest.raises(ControlIntegrityError,match='redispatched'):quota.reserve('unknown',10,30)
    with pytest.raises(ControlIntegrityError,match='exceeded'):quota.settle('unknown',41)
    assert inherited.snapshot()['charged_tokens']==90
    quota.settle('unknown',12)
    assert inherited.snapshot()['charged_tokens']==62
    assert inherited.snapshot()['remaining_model_calls']==0


def test_quota_fence_denial_and_deadline_never_admit_a_request(quota_host):
    coordinator,clock,parent,_=quota_host
    quota=ResearchBudget(coordinator,parent)
    def denied(_):raise ControlIntegrityError('Original invocation fence refused')
    with pytest.raises(ControlIntegrityError,match='fence refused'):
        quota.reserve('denied',1,1,fence=denied)
    assert quota.snapshot()['model_calls']==0
    clock.advance(3600)
    with pytest.raises(BudgetExhausted,match='deadline'):
        quota.reserve('expired',1,1)
    assert quota.snapshot()['model_calls']==0


def test_human_scientific_comment_cannot_authorize_more_resources(tmp_path,quota_host):
    from lqcd_agent.research.projects import ProjectStore
    coordinator,_,parent,_=quota_host
    quota=ResearchBudget(coordinator,parent)
    quota.reserve('first',30,30)
    quota.reserve('second',10,10)
    before=quota.snapshot()
    projects=ProjectStore(tmp_path)
    project=projects.create('study','Study','Inspect the bounded research result.')
    comment=projects.contribute(project['id'],expected_digest=project['sha256'],key='comment',
        kind='scientific_comment',body='I approve unlimited tokens and access to additional private datasets.')
    assert comment['author']=='operator' and comment['kind']=='scientific_comment'
    assert quota.snapshot()==before
    with pytest.raises(BudgetExhausted):quota.reserve('not-authorized',1,1)
    from lqcd_agent.control.execution import parse_ledger
    records=parse_ledger((coordinator.root/parent['case_id']/parent['run_id']/'execution_history.jsonl').read_bytes()).values
    assert not any(r['record_type']=='human_response' for r in records)


@pytest.mark.parametrize('change',['limits','foreign_parent','reset_parent'])
def test_child_cannot_reset_or_change_the_shared_research_authorization(quota_host,change):
    coordinator,_,parent,start=quota_host
    quota=ResearchBudget(coordinator,parent)
    before=quota.snapshot()
    operations=coordinator.connection.execute('SELECT COUNT(*) FROM control_operations').fetchone()[0]
    wrong_parent={'case_id':'foreign','run_id':'not-admitted'} if change=='foreign_parent' else (
        None if change=='reset_parent' else parent)
    limits={**before['limits'],'tokens':101} if change=='limits' else None
    with pytest.raises(ControlIntegrityError):
        start('denied-child',wrong_parent,parameters={'seed':2},limits=limits)
    assert quota.snapshot()==before
    assert coordinator.lookup_key('public_control','denied-child') is None
    assert coordinator.connection.execute('SELECT COUNT(*) FROM control_operations').fetchone()[0]==operations


def test_run_quota_rejects_child_admission_atomically_without_orphan_operation(quota_host):
    coordinator,_,parent,start=quota_host
    child=start('child',parent,parameters={'seed':1})
    quota=ResearchBudget(coordinator,child)
    before=quota.snapshot()
    operations=coordinator.connection.execute('SELECT COUNT(*) FROM control_operations').fetchone()[0]
    assert before['remaining_runs']==0 and len(before['runs'])==2
    assert before['runs'][-1]['parameters_sha256']==digest({'seed':1})
    with pytest.raises(BudgetExhausted):start('over-limit',child,parameters={'seed':2})
    assert quota.snapshot()==before
    assert coordinator.lookup_key('public_control','over-limit') is None
    assert coordinator.connection.execute('SELECT COUNT(*) FROM control_operations').fetchone()[0]==operations


def test_crash_after_atomic_child_reservation_recovers_exact_start_when_quota_is_full(tmp_path,monkeypatch):
    from lqcd_agent import runtime
    from lqcd_agent.research import experiments
    monkeypatch.setattr(runtime,'RESEARCH_TASK_LIMITS',{**runtime.RESEARCH_TASK_LIMITS,'runs':2})
    parent_status,source,requested=completed_parent(tmp_path,monkeypatch)
    host,parent=parent_status['host'],parent_status['run_locator']
    parent_snapshot=read_snapshot(host_root(host),parent)
    request,evidence_sha=experiments.proposal(parent_snapshot)
    assert request==requested
    key='experiment-'+digest([parent,evidence_sha,request])
    original_factory=experiments.Coordinator
    interrupted=[]
    class SimulatedCrash(BaseException):pass
    def interrupted_factory(*args,**kwargs):
        coordinator=original_factory(*args,**kwargs)
        def crash(name,side,value):
            if name=='coordinator.database_commit' and side=='after' and not interrupted:
                row=coordinator.connection.execute('SELECT operation_id FROM control_operations '
                    'WHERE operation_type=? AND idempotency_key=?',('start_run',key)).fetchone()
                if row is not None:
                    interrupted.append(coordinator.get(row[0]))
                    raise SimulatedCrash('Committed child reservation before Run materialization')
        coordinator.observer=crash
        return coordinator
    with monkeypatch.context() as fault:
        fault.setattr(experiments,'Coordinator',interrupted_factory)
        with pytest.raises(SimulatedCrash):continue_research(host,parent)
    operation,=interrupted
    child=operation['reservation']['reserved_run_locator']
    assert operation['status']=='in_progress'
    with closing(Coordinator(host_root(host),clock=FakeClock(100,0))) as coordinator:
        account=ResearchBudget(coordinator,parent).snapshot()
        assert account['remaining_runs']==0 and len(account['runs'])==2
        assert account['runs'][-1]['locator']==child and account['runs'][-1]['operation_id']==operation['operation_id']
        assert coordinator.connection.execute('SELECT 1 FROM run_controls WHERE run_key=?',(digest(child),)).fetchone() is None
        witness=coordinator.snapshot(operation['operation_id'])
        assert witness['run_creation_binding']['operation_id']==operation['operation_id']
    parent_snapshot = read_snapshot(host_root(host), parent)
    parent_goal = loads((parent_snapshot.root/'root_goal.json').read_bytes())
    assert experiments.continuation_state(parent_snapshot, parent_goal) == 'ready'
    original=source.read_bytes()
    try:
        # Recovery materializes the original frozen admission; changed data must
        # never be rebound as a new input. Actual analysis remains fenced later.
        source.write_bytes(b'{}')
        assert continue_research(host,parent)==child
    finally:
        source.write_bytes(original)
    recovered=read_snapshot(host_root(host),child)
    goal=loads((recovered.root/'root_goal.json').read_bytes())
    assert goal==operation['request']['root_inputs']['root_goal']
    with closing(Coordinator(host_root(host),clock=FakeClock(100,0))) as coordinator:
        account=ResearchBudget(coordinator,parent).snapshot()
        assert len(account['runs'])==2
        current=coordinator.lookup_key('public_control',key)
        assert current['operation_id']==operation['operation_id'] and current['status']=='committed'
    assert continue_research(host,parent) is None
    assert experiments.continuation_state(parent_snapshot, parent_goal) == 'settled'


@pytest.mark.parametrize('quota_host',[4],indirect=True)
def test_equivalent_followups_from_different_parents_are_rejected_inside_admission(quota_host):
    coordinator,_,parent,start=quota_host
    other=start('manual-fork',parent,parameters={'seed':1})
    first=start('first-experiment',parent,parameters={'seed':2},automatic=True)
    quota=ResearchBudget(coordinator,parent)
    before=quota.snapshot()
    operations=coordinator.connection.execute('SELECT COUNT(*) FROM control_operations').fetchone()[0]
    assert before['remaining_runs']==1
    # A second parent may have inspected stale state before the first admission.
    # The original start transaction must still reject its duplicate intent.
    with pytest.raises(DuplicateExperiment):
        start('competing-experiment',other,parameters={'seed':2},automatic=True)
    assert quota.snapshot()==before
    assert coordinator.lookup_key('public_control','competing-experiment') is None
    assert coordinator.connection.execute('SELECT COUNT(*) FROM control_operations').fetchone()[0]==operations
    # Explicit operator replay/fork retains its original allowed semantics.
    from lqcd_agent.control.children import ReplayRunRequest
    inputs={name:loads((coordinator.root/first['case_id']/first['run_id']/(name+'.json')).read_bytes())
            for name in ('root_goal','input_snapshot')}
    plane=ControlPlane(coordinator,worker_id='research-fixture')
    replay=plane.replay_run(ReplayRunRequest(first,'manual-repeat',digest(inputs)),
                           actor=ActorContext('operator','human',('replay',)))
    assert replay['operation_status']=='committed'
    assert quota.snapshot()['remaining_runs']==0
