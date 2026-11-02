"""One application entry for CLI and Python clients over the canonical engine."""
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
import tempfile
from lqcd_agent.control.storage import execution_scratch_root
from lqcd_agent.control.coordinator import Coordinator, component, read_regular
from lqcd_agent.control.strict_json import digest, loads, require
from .inspection import host_root, read_snapshot
from lqcd_agent.settings import workspace_root


@dataclass
class ApplicationRequest:
    command: str
    key: str | None = None
    host: str | None = None
    case: str = 'case'
    run: str | None = None
    pause: str | None = None
    source_digest: str | None = None
    response: str | None = None
    goal: str | None = None
    workflow: str = 'no-code'
    live: bool = False
    case_config: str | None = None
    archive_path: str | None = None
    project: str | None = None
    project_digest: str | None = None


def create_host():
    return Path(tempfile.mkdtemp(prefix='lqcd-agent-host-', dir=execution_scratch_root()))


def assemble(coordinator, agent_port=None, *, live=False, workflow='no-code', initialize=False, method_sources=()):
    from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
    from lqcd_agent.control.interfaces import ActorContext
    code = analysis = None
    if workflow == 'code':
        from .examples import prepare_code
        code, analysis = prepare_code(coordinator, live=live, initialize=initialize)
    if workflow == 'scientific' and agent_port is not None and agent_port.config.get('generated_program') is not None:
        from .research_codegen import prepare_research
        code, analysis = prepare_research(coordinator, agent_port.config, workspace=agent_port.workspace,
                                          live=live, initialize=initialize, method_sources=method_sources)
    if agent_port is None:
        from .examples import SyntheticAgent
        agent_port = SyntheticAgent()
    actor = ActorContext('operator', 'human', tuple(sorted(('start', 'resume', 'cancel', 'replay', 'fork', 'policy.select', 'control.internal'))))
    runtime = CanonicalProductRuntime(coordinator, worker_id='product-host', actor=actor,
        agent_port=agent_port, analysis_handoff=analysis, code_host=code)
    return runtime, actor, code

@dataclass(frozen=True)
class Submission:
    status: dict
    advance: bool = False


def submit(request: ApplicationRequest):
    """Commit the requested control action before executing subsequent work."""
    args = replace(request)
    require(args.command in ('start','run','resume','replay','fork','cancel','status','archive','verify-archive'),
            'Unsupported application command')
    if args.command == 'verify-archive':
        from .archive import verify_archive
        return Submission(verify_archive(args.archive_path))
    if args.command == 'archive':
        from .archive import archive_run
        return Submission(archive_run(host_root(args.host), {'case_id': args.case, 'run_id': args.run}))
    if args.command == 'status':
        return Submission(read_snapshot(host_root(args.host), {'case_id': args.case, 'run_id': args.run}).status())
    intent = {field: getattr(args, field) for field in
              ('command', 'case', 'goal', 'workflow', 'live', 'case_config', 'project', 'project_digest')}
    if args.command in ('start', 'run') and args.host is not None:
        from .inspection import read_operation
        original = read_operation(host_root(args.host), args.key)
        if original is not None and original['status'] == 'committed':
            require(original['operation_type'] == 'start_run', 'Operation key belongs to another action')
            frozen = original['request']['root_inputs']['root_goal']
            require(frozen.get('request_intent') == intent, 'Operation key conflicts with the original research request')
            require(frozen['workspace'] == str(workspace_root()), 'Select the original operator workspace')
            require(original['request_digest'] == digest({key: original[key] for key in
                    ('operation_type', 'operation_variant', 'request')}), 'Original operation request changed')
            locator = original['reservation']['reserved_run_locator']
            snapshot = read_snapshot(host_root(args.host), locator)
            creation = next(row for row in snapshot.records.values if row['record_type'] == 'run_lifecycle'
                            and row['from_status'] == 'initializing')
            require(creation['operation_id'] == original['operation_id'], 'Operation points to another Run')
            require(original['request']['root_inputs'] == {name: loads(read_regular(snapshot.root/(name+'.json')))
                    for name in ('root_goal', 'input_snapshot')}, 'Original Run inputs changed')
            return Submission(snapshot.status())
    from lqcd_agent.control.children import ForkRunRequest, ReplayRunRequest
    from lqcd_agent.control.clock import FakeClock
    from lqcd_agent.control.interfaces import StartRunRequest
    from lqcd_agent.control.pause import CancelPauseRequest, ResumeRunRequest
    config = None
    workspace = workspace_root() if args.command != 'cancel' else None
    project = None
    if args.project is not None:
        require(args.command == 'run', 'Use run --project to bind a scientific Project')
        from .research.projects import ProjectStore
        project = ProjectStore(workspace).read(args.project)
        require(args.project_digest is None or project['sha256'] == args.project_digest, 'Project changed before Run admission')
        args.goal = args.goal if args.goal is not None else project['goal']
        config = project['case_config']
    if args.command == 'run':
        from lqcd_agent.configuration import read_config
        if args.case_config is not None:
            require(project is None, 'Use the case configuration frozen in the Project')
            config = read_config(Path(args.case_config))
        require(config is not None, 'This Project needs an executable case configuration before starting a Run')
        require(config.get('schema_version') == '0.1', 'Unsupported case configuration version')
        args.case = config.get('case_id', args.case)
        args.command, args.workflow = 'start', 'scientific'
    if args.command == 'start' and args.goal is None:
        args.goal = config.get('physics_goal', 'Analyze the configured case') if config else (
            'Implement value() in sample.py returning integer 2' if args.workflow == 'code' else 'Validate the synthetic observable')
    component(args.case)
    if args.command != 'start':
        component(args.run)
    root = create_host() if args.command == 'start' and args.host is None else host_root(args.host)
    live = args.live
    method_sources = []
    if args.command != 'start':
        goal = loads(read_regular(root / args.case / args.run / 'root_goal.json'))
        if args.command != 'cancel':
            require(goal['workspace'] == str(workspace), 'Select the original operator workspace before resuming this Run')
        args.workflow = goal['workflow']
        config, live = goal.get('case_config'), goal['live']
        method_sources = goal.get('method_sources', [])
    elif config is not None:
        from .research.methods import snapshot_methods
        method_sources = snapshot_methods(config, workspace)
    from lqcd_agent.control.clock import HostClock
    from lqcd_agent.settings import ApplicationSettings
    settings = ApplicationSettings.load() if live and args.command in ('start', 'resume', 'fork', 'replay') else None
    with closing(Coordinator(root, clock=HostClock() if live else FakeClock(100, 0))) as coordinator:
        previous = coordinator.lookup_key('public_control', args.key)
        replay = previous is not None and previous['status'] == 'committed'
        advance_work = False
        runtime, actor, code = assemble(coordinator, scientific_agent(root, config, settings, workspace) if config is not None and args.command != 'cancel' else None,
            live=live, workflow=args.workflow, initialize=args.command == 'start', method_sources=method_sources)
        plane = runtime.plane
        if args.command == 'start':
            inputs = {'root_goal': {'goal': args.goal, 'workflow': args.workflow, 'live': live, 'workspace': str(workspace), 'request_intent': intent}, 'input_snapshot': {'kind': 'current_mock' if config is None else 'scientific_case', 'case_config': config}}
            if project is not None:
                inputs['root_goal'].update(project_id=project['id'], project_revision=project['revision'],
                                          project_sha256=project['sha256'], project_snapshot=project)
            if config is not None:
                inputs['root_goal']['case_config'] = config
                inputs['root_goal']['method_sources'] = method_sources
                from .tools.dataset import snapshot_dataset
                inputs['root_goal']['dataset_snapshot'] = snapshot_dataset(config, workspace)
            result = plane.start_run(StartRunRequest(args.case, inputs, digest(inputs), args.key), actor=actor)
            locator = result['result']['run_locator']
            advance_work = not replay and result['operation_status'] == 'committed' and result['run_status'] == 'running'
        else:
            locator = {'case_id': args.case, 'run_id': args.run}
            if args.command in ('replay', 'fork'):
                request = ReplayRunRequest(locator, args.key, args.source_digest) if args.command == 'replay' else ForkRunRequest(locator, args.key, args.source_digest)
                create = plane.replay_run if args.command == 'replay' else plane.fork_run
                result = create(request, actor=actor)
                locator = result['result']['run_locator']
                advance_work = not replay and result['operation_status'] == 'committed' and result['run_status'] == 'running'
            elif args.command == 'cancel':
                if code is not None:
                    from lqcd_agent.code_agent.external_operation import CodeExternalStop
                    plane.external_adapter = CodeExternalStop(coordinator, code.backend, code.containment, code.backend.read_receipt)
                elif live and config is not None and config.get('generated_program'):
                    from .code_agent.codex_backend import CodexCodingBackend, ProcessContainment, JOBS_DIRECTORY
                    from .code_agent.external_operation import CodeExternalStop
                    backend = CodexCodingBackend(root/JOBS_DIRECTORY, root/'code_workspaces')
                    plane.external_adapter = CodeExternalStop(coordinator, backend, ProcessContainment(backend), backend.read_receipt)
                plane.cancel_pause(CancelPauseRequest(locator, args.pause, args.key, 'operator_cancel'), actor=actor)
            else:
                _, execution = runtime._records(locator)
                pause = next((record for record in execution.values if record['record_type'] == 'pause' and record['pause_id'] == args.pause and (record['event'] == 'pause_opened')), None)
                require(pause is not None, 'Unknown original Pause')
                if args.response is not None:
                    payload = loads(args.response, canonical=False)
                    kind = 'human_response'
                else:
                    require(pause['reason'] == 'external_result', 'Human Resume requires a business response')
                    require(code is not None, 'External Resume requires its original Code host')
                    producer = pause['input_contract']['producer_operation_id']
                    if live:
                        from lqcd_agent.code_agent.codex_backend import seal_codex_result
                        audit, patch = seal_codex_result(code.backend, coordinator, producer, code.base_repository, code.containment)
                    else:
                        delivery = root / 'synthetic_deliveries' / producer
                        audit, patch = read_regular(delivery / 'tool-audit.jsonl'), read_regular(delivery / 'patch.diff')
                    final = code.finalize(producer, tool_audit=audit, patch=patch)
                    payload = {'producer_operation_id': producer, 'external_final_digest': final['terminal_evidence_digest']}
                    kind = 'external_result'
                result = runtime.resume_control(ResumeRunRequest(locator, args.pause, args.key, kind, payload, digest(payload)), actor=actor)
                advance_work = not replay and result['operation_status'] == 'committed' and result['run_status'] == 'running'
    snapshot = read_snapshot(root, locator)
    status = snapshot.status()
    if args.command == 'cancel':
        # Stopping the original job must not depend on an available data workspace.
        if goal.get('project_id') is not None:
            try:
                Path(goal['workspace']).stat()
                capture_project(snapshot, goal)
            except OSError:
                status['project_capture'] = 'unavailable'
    else:
        capture_project(snapshot)
    return Submission(status, advance_work)


def advance(host, locator):
    """Drive an already admitted Run through its original fenced runtime."""
    from .control.clock import FakeClock, HostClock
    from .settings import ApplicationSettings
    from .control.pause import runtime_fingerprint
    root = host_root(host)
    snapshot = read_snapshot(root, locator)
    require(snapshot.fingerprint == runtime_fingerprint(), 'Unsupported runtime fingerprint')
    require(snapshot.can_advance, 'Run requires its original Pause or explicit recovery before advancing')
    goal = loads(read_regular(root/locator['case_id']/locator['run_id']/'root_goal.json'))
    workspace = workspace_root()
    require(goal['workspace'] == str(workspace), 'Select the original operator workspace before advancing this Run')
    settings = ApplicationSettings.load() if goal['live'] else None
    with closing(Coordinator(root, clock=HostClock() if goal['live'] else FakeClock(100, 0))) as coordinator:
        agent = scientific_agent(root, goal['case_config'], settings, workspace) if goal.get('case_config') is not None else None
        runtime, _, _ = assemble(coordinator, agent, live=goal['live'], workflow=goal['workflow'],
                                 method_sources=goal.get('method_sources', []))
        runtime.run(locator)
    snapshot = read_snapshot(root, locator)
    capture_project(snapshot)
    return snapshot.status()


def execute(request: ApplicationRequest):
    """Preserve synchronous CLI behavior over submission and controlled work."""
    result = submit(request)
    return advance(result.status['host'], result.status['run_locator']) if result.advance else result.status


def scientific_agent(host, config, settings, workspace):
    from .science import ScientificAgent
    if settings is None:
        return ScientificAgent(host, config, workspace=workspace)
    from .research.collaboration import CollaborationAgent
    return CollaborationAgent(host, config, runtime_factory=settings.research_runtime, workspace=workspace,
                              request_timeout_seconds=settings.timeout_seconds)


def capture_project(snapshot, goal=None):
    """Preserve inspectable project evidence, without creating execution authority."""
    if goal is None:
        goal = loads(read_regular(snapshot.root/'root_goal.json'))
    if goal.get('project_id') is not None:
        from .research.projects import ProjectStore
        ProjectStore(Path(goal['workspace'])).capture_run(snapshot)
