"""Admit PI-proposed experiments through the original Host start/advance path."""
from copy import deepcopy
from contextlib import closing
from hashlib import sha256
from pathlib import Path

from lqcd_agent.control.clock import FakeClock, HostClock
from lqcd_agent.control.budget import BudgetExhausted
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.research_budget import DuplicateExperiment, ResearchBudget, plan_exhausted
from lqcd_agent.control.strict_json import ControlIntegrityError, closed, digest, loads, number, require, text
from lqcd_agent.inspection import host_root, read_snapshot, read_preparation
from lqcd_agent.code_agent.execution import FAMILY_CONTROLS


def experiment_config(config, proposal):
    """Only analysis parameters and reviewed local methods may vary, never IO authority."""
    closed(proposal, ('question', 'rationale', 'parameter_changes', 'method_ids'))
    text(proposal['question']); text(proposal['rationale'])
    require(len(proposal['question']) <= 4096 and len(proposal['rationale']) <= 8192,
            'Experiment description is too large')
    require(type(proposal['parameter_changes']) is list and len(proposal['parameter_changes']) <= 16,
            'Experiment parameter changes must be bounded')
    result = deepcopy(config)
    require(type(result.get('generated_program')) is dict, 'Experiment requires a generated scientific contract')
    program = result['generated_program']
    parameters = program['parameters']
    family = program['result_kind']
    allowed = FAMILY_CONTROLS[family]
    seen = set()
    for change in proposal['parameter_changes']:
        closed(change, ('name', 'value_json'))
        name = change['name']
        require(name in allowed and name not in seen, 'Experiment tried to change data, authority or duplicate parameters')
        seen.add(name)
        raw = text(change['value_json'])
        require(len(raw) <= 8192, 'Experiment parameter is too large')
        value = loads(raw, canonical=False)
        if name in ('binsize', 'bootstrap_samples', 'tmax'):
            number(value, integer=True, minimum=2 if name == 'bootstrap_samples' else 1)
            require(value <= 100000, 'Unbounded analysis parameter')
        elif name == 'seed':
            number(value, integer=True, minimum=0)
        elif name == 'tmins':
            require(type(value) is list and 0 < len(value) <= 64 and
                    all(type(t) is int and t >= 0 for t in value) and len(set(value)) == len(value),
                    'Invalid fit-window experiment')
        elif name in ('fixed_ground_energy', 'omit_reference'):
            require(type(value) is bool, 'Experiment flag must be boolean')
        parameters[name] = value
    require(type(proposal['method_ids']) is list and len(proposal['method_ids']) <= 16 and
            all(type(item) is str and item for item in proposal['method_ids']), 'Invalid experiment methods')
    return result


def proposal(snapshot):
    goal = loads(read_regular(snapshot.root/'root_goal.json'))
    if goal.get('workflow') == 'intake':
        selected = read_preparation(snapshot.root)
        return selected if selected is not None and selected[0]['status'] == 'ready' else None
    pointer = loads(read_regular(snapshot.root / 'artifact_index.json'))['current']['review']
    if pointer is None:
        return None
    member = next(m for m in pointer['members'] if m['logical_name'] == 'scientific_review_report.json')
    raw = read_regular(snapshot.root / member['canonical_path'])
    require(sha256(raw).hexdigest() == member['sha256'], 'Experiment review evidence changed')
    document = loads(raw)
    request = document.get('collaboration', {}).get('next_experiment')
    return None if request is None else (request, member['sha256'])


def continue_research(host, locator):
    """Reconcile one completed parent; return a newly admitted child or None."""
    snapshot = read_snapshot(host_root(host), locator)
    if snapshot.state['run_status'] != 'completed':
        return None
    goal = loads(read_regular(snapshot.root / 'root_goal.json'))
    if 'research_task' not in goal or goal.get('workflow') not in ('scientific', 'intake'):
        return None
    selected = proposal(snapshot)
    if selected is None:
        return None
    request, evidence_sha = selected
    if goal['workflow'] == 'intake':
        if goal['plan_mode'] != 'auto':
            return None
        # Automatic and operator-selected plans use the same version-bound admission.
        from lqcd_agent.runtime import ApplicationRequest, submit
        from lqcd_agent.inspection import read_operation
        key = 'preparation-' + digest([locator, evidence_sha])
        old = read_operation(snapshot.host, key)
        if old is not None and old['status'] == 'committed':
            return None
        if old is None:
            clock = HostClock() if goal['live'] else FakeClock(100, 0)
            with closing(Coordinator(snapshot.host, clock=clock)) as coordinator:
                quota = ResearchBudget(coordinator, locator)
                account = quota.snapshot()
                if any(row['parent'] == locator for row in account['runs']) or digest(locator) in account['unexecuted_experiments']:
                    return None
                if plan_exhausted(account, clock.now().monotonic_seconds):
                    quota.decline_experiment(digest(request), 'research_budget_exhausted')
                    return None
        admitted = submit(ApplicationRequest('run', key=key, host=host, case=locator['case_id'], project=goal['project_id'],
            project_digest=goal['project_sha256'], live=goal['live'], intake_parent=locator['run_id'],
            plan_action='execute', plan_digest=evidence_sha))
        return admitted.status['run_locator'] if admitted.advance else None
    lineage = 'experiment'
    evidence_field = 'review_sha256'
    clock = HostClock() if goal['live'] else FakeClock(100, 0)
    with closing(Coordinator(snapshot.host, clock=clock)) as coordinator:
        quota = ResearchBudget(coordinator, locator)
        account = quota.snapshot()
        if digest(locator) in account['unexecuted_experiments']:
            return None
        if goal.get('plan_mode') == 'review':
            quota.decline_experiment(digest(request), 'new_scientific_scope_requires_review')
            return None
        request_key = lineage + '-' + digest([locator, evidence_sha, request])
        existing = coordinator.lookup_key('public_control', request_key)
        if existing is not None and existing['status'] == 'committed':
            frozen = existing['request']['root_inputs']['root_goal']
            require(frozen[lineage]['proposal_sha256'] == digest(request) and
                    frozen['research_task']['parent'] == locator, 'Experiment operation changed')
            return None
        if existing is None and (account['remaining_runs'] == 0 or account['remaining_model_calls'] == 0 or
                account['remaining_tokens'] == 0 or coordinator._time().monotonic_seconds >= account['deadline']):
            quota.decline_experiment(digest(request), 'research_budget_exhausted')
            return None
        if existing is not None:
            # Recover the original admitted bytes; mutable library heads cannot
            # replace sources after a partially published start operation.
            inputs = existing['request']['root_inputs']
            child_goal = inputs['root_goal']
            require(child_goal[lineage]['proposal_sha256'] == digest(request) and
                    child_goal['research_task']['parent'] == locator, 'Experiment intent changed')
            config, method_sources = child_goal['case_config'], child_goal['method_sources']
            workspace = Path(child_goal['workspace'])
        else:
            workspace = Path(goal['workspace'])
            try:
                config = experiment_config(goal['case_config'], request)
            except (ControlIntegrityError, ValueError, TypeError, KeyError):
                quota.decline_experiment(digest(request), 'unsupported_experiment_scope')
                return None
            if request['method_ids']:
                from .library import Library
                try:
                    records = [Library(workspace).read('method', item) for item in request['method_ids']]
                    config['method_dependencies'] = [{key: row[key] for key in ('id', 'revision', 'sha256')} for row in records]
                except (ControlIntegrityError, ValueError, KeyError, FileNotFoundError):
                    quota.decline_experiment(digest(request), 'method_not_independently_qualified')
                    return None
            parameters_sha = digest(config.get('generated_program', {}).get('parameters', {}))
            from lqcd_agent.tools.dataset import snapshot_dataset
            require(snapshot_dataset(config, workspace) == goal['dataset_snapshot'],
                    'Additional experiment cannot replace its original data')
            from .methods import snapshot_methods
            try:
                method_sources = snapshot_methods(config, workspace)
            except (ControlIntegrityError, ValueError, KeyError):
                quota.decline_experiment(digest(request), 'method_not_independently_qualified')
                return None
            methods_sha = digest(method_sources)
            if any(row['parameters_sha256'] == parameters_sha and row['methods_sha256'] == methods_sha
                   for row in account['runs']):
                quota.decline_experiment(digest(request), 'no_new_analysis_parameters_or_methods')
                return None
            config['generated_program']['requirements'].append('Additional scientific check: ' + request['question'])
            child_goal = {**deepcopy(goal), 'workflow': 'scientific', 'case_config': config, 'method_sources': method_sources,
                          'goal': goal['goal'] + '\nAdditional experiment: ' + request['question'],
                          'research_task': {**goal['research_task'], 'parent': dict(locator)},
                          lineage: {'parent': dict(locator), evidence_field: evidence_sha,
                                         'proposal': request, 'proposal_sha256': digest(request), 'request_key': request_key}}
            child_goal.pop('preparation', None)
            child_goal.pop('previous_plan', None)
            child_goal.pop('plan_origin', None)
            child_goal.pop('intake_parent', None)
            child_goal['request_intent'] = {'command': lineage, 'parent': dict(locator),
                                           'proposal_sha256': digest(request), evidence_field: evidence_sha}
            inputs = {'root_goal': child_goal, 'input_snapshot': {'kind': 'scientific_case', 'case_config': config}}
        from lqcd_agent.runtime import assemble, scientific_agent
        from lqcd_agent.settings import ApplicationSettings
        settings = ApplicationSettings.load() if goal['live'] else None
        runtime, _, _ = assemble(coordinator, scientific_agent(snapshot.host, config, settings, workspace),
                                live=goal['live'], workflow='scientific', initialize=True, method_sources=method_sources)
        actor = ActorContext('research-system', 'system', ('start',))
        try:
            result = runtime.plane.start_run(StartRunRequest(locator['case_id'], inputs, digest(inputs),
                request_key), actor=actor)
        except DuplicateExperiment:
            quota.decline_experiment(digest(request), 'no_new_analysis_parameters_or_methods')
            return None
        except BudgetExhausted:
            quota.decline_experiment(digest(request), 'research_budget_exhausted')
            return None
        child = result['result']['run_locator']
    return child


def continuation_pending(snapshot):
    """Identify recoverable, budgeted follow-up admission without changing state."""
    if snapshot.state['run_status'] != 'completed':
        return False
    goal = loads(read_regular(snapshot.root / 'root_goal.json'))
    if 'research_task' not in goal or proposal(snapshot) is None:
        return False
    from lqcd_agent.control.research_budget import inspect_budget
    account = inspect_budget(snapshot.host, snapshot.locator)
    if digest(snapshot.locator) in account['unexecuted_experiments']:
        return False
    from lqcd_agent.inspection import read_operation
    request, evidence_sha = proposal(snapshot)
    if goal['workflow'] == 'intake':
        if goal['plan_mode'] != 'auto':
            return False
        key = 'preparation-' + digest([snapshot.locator, evidence_sha])
    else:
        key = 'experiment-' + digest([snapshot.locator, evidence_sha, request])
    existing = read_operation(snapshot.host, key)
    if existing is not None:
        return existing['status'] == 'in_progress'
    if goal['workflow'] == 'intake' and any(row['parent'] == snapshot.locator for row in account['runs']):
        return False
    now = HostClock().now().monotonic_seconds if goal['live'] else 0
    return not plan_exhausted(account, now)


def select_plan(request, project, workspace, intake):
    """Select immutable preparation bytes and recheck the current executable inputs."""
    from lqcd_agent.control.pause import runtime_fingerprint
    from lqcd_agent.control.research_budget import inspect_budget
    from .projects import ProjectStore
    parent = {'case_id': request.case, 'run_id': request.intake_parent}
    snapshot = read_snapshot(host_root(request.host), parent)
    goal = loads(read_regular(snapshot.root/'root_goal.json'))
    require(snapshot.state['run_status'] == 'completed' and goal['workflow'] == 'intake' and
            snapshot.fingerprint == runtime_fingerprint(), 'Plan action needs the original completed preparation and runtime')
    require(goal['workspace'] == str(workspace) and goal['project_id'] == project['id'] and
            goal['live'] == request.live, 'Plan action cannot change workspace, Project or model authority')
    sealed = read_preparation(snapshot.root)
    require(sealed is not None and sealed[1] == request.plan_digest, 'Selected plan digest changed')
    proposal = sealed[0]
    if proposal['status'] == 'ready':
        config = proposal['case_config']
        require(config['case_id'] == parent['case_id'] and
                config.get('raw_data_path') == goal['case_config'].get('raw_data_path'),
                'Prepared plan changed its original case or data source')
    account = inspect_budget(snapshot.host, parent)
    clock = HostClock() if goal['live'] else FakeClock(100, 0)
    renew = request.plan_action == 'renew'
    require(plan_exhausted(account, clock.now().monotonic_seconds) == renew,
            'Use the original remaining quota, or explicitly renew an exhausted plan')
    notes = ProjectStore(workspace).research_inputs(project['id'], snapshot.host, parent)
    unread = {row['sha256'] for row in notes} - set(proposal['scientific_input_sha256'])
    unchanged = project['sha256'] == goal['project_sha256'] and intake == goal['intake'] and not unread
    ready = proposal['status'] == 'ready'
    if ready and unchanged:
        from .methods import snapshot_methods
        try:
            snapshot_methods(proposal['case_config'], workspace)
        except (ControlIntegrityError, FileNotFoundError):
            unchanged = False
    if request.plan_action == 'execute':
        require(ready and unchanged, 'Research inputs changed after preparation or plan needs revision')
    if request.plan_action == 'revise':
        require(not unchanged, 'Supply scientific feedback or update the Project inputs before revising')
    return {'goal': goal, 'proposal': proposal, 'parent': parent,
            'execute': request.plan_action != 'revise' and ready and unchanged}
