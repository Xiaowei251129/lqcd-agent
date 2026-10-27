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


def create_host():
    return Path(tempfile.mkdtemp(prefix='lqcd-agent-host-', dir=execution_scratch_root()))


def assemble(coordinator, agent_port=None, *, live=False, workflow='no-code', initialize=False):
    from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
    from lqcd_agent.control.interfaces import ActorContext
    code = analysis = None
    if workflow == 'code':
        from .examples import prepare_code
        code, analysis = prepare_code(coordinator, live=live, initialize=initialize)
    if agent_port is None:
        from .examples import SyntheticAgent
        agent_port = SyntheticAgent()
    actor = ActorContext('operator', 'human', tuple(sorted(('start', 'resume', 'cancel', 'replay', 'fork', 'policy.select', 'control.internal'))))
    runtime = CanonicalProductRuntime(coordinator, worker_id='product-host', actor=actor,
        agent_port=agent_port, analysis_handoff=analysis, code_host=code)
    return runtime, actor, code

def execute(request: ApplicationRequest):
    args = replace(request)
    require(args.command in ('start','run','resume','replay','fork','cancel','status','archive','verify-archive'),
            'Unsupported application command')
    if args.command == 'verify-archive':
        from .archive import verify_archive
        return verify_archive(args.archive_path)
    if args.command == 'archive':
        from .archive import archive_run
        return archive_run(host_root(args.host), {'case_id': args.case, 'run_id': args.run})
    if args.command == 'status':
        return read_snapshot(host_root(args.host), {'case_id': args.case, 'run_id': args.run}).status()
    from lqcd_agent.control.children import ForkRunRequest, ReplayRunRequest
    from lqcd_agent.control.clock import FakeClock
    from lqcd_agent.control.interfaces import StartRunRequest
    from lqcd_agent.control.pause import CancelPauseRequest, ResumeRunRequest
    config = None
    if args.command == 'run':
        from lqcd_agent.configuration import read_config
        config = read_config(Path(args.case_config))
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
    workspace = workspace_root() if args.command != 'cancel' else None
    if args.command != 'start':
        goal = loads(read_regular(root / args.case / args.run / 'root_goal.json'))
        if args.command != 'cancel':
            require(goal['workspace'] == str(workspace), 'Select the original operator workspace before resuming this Run')
        args.workflow = goal['workflow']
        config, live = goal.get('case_config'), goal['live']
    from lqcd_agent.control.clock import HostClock
    from lqcd_agent.settings import ApplicationSettings
    settings = ApplicationSettings.load() if live and args.command in ('start', 'resume', 'fork', 'replay') else None
    with closing(Coordinator(root, clock=HostClock() if live else FakeClock(100, 0))) as coordinator:
        from lqcd_agent.science import ScientificAgent
        runtime, actor, code = assemble(coordinator, ScientificAgent(root, config, provider=settings.provider() if settings else None, workspace=workspace) if config is not None and args.command != 'cancel' else None,
            live=live, workflow=args.workflow, initialize=args.command == 'start')
        plane = runtime.plane
        if args.command == 'start':
            inputs = {'root_goal': {'goal': args.goal, 'workflow': args.workflow, 'live': live, 'workspace': str(workspace)}, 'input_snapshot': {'kind': 'current_mock' if config is None else 'scientific_case', 'case_config': config}}
            if config is not None:
                inputs['root_goal']['case_config'] = config
            result = plane.start_run(StartRunRequest(args.case, inputs, digest(inputs), args.key), actor=actor)
            locator = result['result']['run_locator']
            runtime.run(locator)
        else:
            locator = {'case_id': args.case, 'run_id': args.run}
            if args.command in ('replay', 'fork'):
                request = ReplayRunRequest(locator, args.key, args.source_digest) if args.command == 'replay' else ForkRunRequest(locator, args.key, args.source_digest)
                create = plane.replay_run if args.command == 'replay' else plane.fork_run
                result = create(request, actor=actor)
                locator = result['result']['run_locator']
                runtime.run(locator)
            elif args.command == 'cancel':
                if code is not None:
                    from lqcd_agent.code_agent.external_operation import CodeExternalStop
                    plane.external_adapter = CodeExternalStop(coordinator, code.backend, code.containment, code.backend.read_receipt)
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
                runtime.resume(ResumeRunRequest(locator, args.pause, args.key, kind, payload, digest(payload)), actor=actor)
    return read_snapshot(root, locator).status()
