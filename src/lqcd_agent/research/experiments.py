"""Admit PI-proposed experiments through the original Host start/advance path."""
from copy import deepcopy
from contextlib import closing
from hashlib import sha256
from pathlib import Path

from lqcd_agent.control.clock import FakeClock, HostClock
from lqcd_agent.control.budget import BudgetExhausted
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.research_budget import DuplicateExperiment, ResearchBudget
from lqcd_agent.control.strict_json import ControlIntegrityError, closed, digest, loads, number, require, text
from lqcd_agent.inspection import host_root, read_snapshot, read_preparation
from lqcd_agent.code_agent.execution import ANALYSIS_PARAMETERS


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
    allowed = (set(ANALYSIS_PARAMETERS) - {'omit_reference'} if family == 'c2' else
               {'omit_reference'} if family == 'normalization' else set()) | set(parameters)
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
        elif name in parameters:
            require(type(value) is type(parameters[name]), 'Experiment changed parameter type')
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
    preparation = goal['workflow'] == 'intake'
    lineage = 'preparation' if preparation else 'experiment'
    evidence_field = 'plan_sha256' if preparation else 'review_sha256'
    clock = HostClock() if goal['live'] else FakeClock(100, 0)
    with closing(Coordinator(snapshot.host, clock=clock)) as coordinator:
        quota = ResearchBudget(coordinator, locator)
        account = quota.snapshot()
        if digest(locator) in account['unexecuted_experiments']:
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
            if preparation:
                from .intake import snapshot_intake
                observed = snapshot_intake(workspace, goal['project_snapshot'])
                require(observed == goal['intake'], 'Research inputs changed after preparation; start a new intake')
                config = deepcopy(request['case_config'])
                require(config['case_id'] == locator['case_id'], 'Preparation changed its case identity')
                require(config.get('raw_data_path') == (goal['case_config'] or {}).get('raw_data_path'),
                        'Preparation changed its operator data source')
            else:
                try:
                    config = experiment_config(goal['case_config'], request)
                except (ControlIntegrityError, ValueError, TypeError, KeyError):
                    quota.decline_experiment(digest(request), 'unsupported_experiment_scope')
                    return None
            if not preparation and request['method_ids']:
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
            if not preparation and any(row['parameters_sha256'] == parameters_sha and row['methods_sha256'] == methods_sha
                   for row in account['runs']):
                quota.decline_experiment(digest(request), 'no_new_analysis_parameters_or_methods')
                return None
            if not preparation:
                config['generated_program']['requirements'].append('Additional scientific check: ' + request['question'])
            child_goal = {**deepcopy(goal), 'workflow': 'scientific', 'case_config': config, 'method_sources': method_sources,
                          'goal': goal['goal'] if preparation else goal['goal'] + '\nAdditional experiment: ' + request['question'],
                          'research_task': {**goal['research_task'], 'parent': dict(locator)},
                          lineage: {'parent': dict(locator), evidence_field: evidence_sha,
                                         'proposal': request, 'proposal_sha256': digest(request), 'request_key': request_key}}
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
    key = ('preparation' if goal['workflow'] == 'intake' else 'experiment') + '-' + digest([snapshot.locator, evidence_sha, request])
    existing = read_operation(snapshot.host, key)
    if existing is not None:
        return existing['status'] == 'in_progress'
    now = HostClock().now().monotonic_seconds if goal['live'] else 0
    return account['remaining_model_calls'] > 0 and account['remaining_tokens'] > 0 and now < account['deadline'] and account['remaining_runs'] > 0


def clarification_parent(host, case, run, project, live, workspace):
    """An explicit reply continuation can consume, never replace, its old task."""
    locator = {'case_id': case, 'run_id': run}
    snapshot = read_snapshot(host, locator)
    goal = loads(read_regular(snapshot.root/'root_goal.json'))
    require(snapshot.state['run_status'] == 'completed' and goal.get('workflow') == 'intake',
            'Only a completed research preparation can receive clarification')
    require(goal['workspace'] == str(workspace) and goal['project_id'] == project['id'] and goal['live'] == live,
            'Clarification cannot change workspace, Project or model authority')
    selected = read_preparation(snapshot.root)
    require(selected is not None and selected[0]['status'] == 'needs_information',
            'This preparation is not waiting for scientific information')
    from lqcd_agent.control.pause import runtime_fingerprint
    require(snapshot.fingerprint == runtime_fingerprint(), 'Clarification needs the original supported runtime')
    from .projects import ProjectStore
    current_contributions = ProjectStore(workspace).contributions(project['id'],
        run={'host': host.name.removeprefix('lqcd-agent-host-'), **locator})
    original_contributions = goal.get('intake_contributions', [])
    require(project['sha256'] != goal['project_sha256'] or
            bool({item['sha256'] for item in current_contributions} - set(original_contributions)),
            'Supply a scientific reply or update the Project inputs before continuing')
    return goal['research_task'], locator
