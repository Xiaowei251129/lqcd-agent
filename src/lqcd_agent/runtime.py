"""Canonical Host with offline fixtures and explicit application API opt-in."""
from lqcd_agent.control.storage import execution_scratch_root
import argparse
from contextlib import closing
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
from lqcd_agent.code_agent.external_operation import CodeExternalStop
from lqcd_agent.code_agent.schemas import IDENTITY
from lqcd_agent.code_agent.subgraph import ProductCodeHost
from lqcd_agent.code_agent.workspace import WorkspaceProvider, canonical_patch, immutable_git_tree, seal_workspace, tree_digest
from lqcd_agent.control.children import ForkRunRequest, ReplayRunRequest
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, component, read_regular
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.pause import CancelPauseRequest, ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads, require
from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime

SAMPLE_ANALYSIS_COMMAND = "import ast,pathlib; source=pathlib.Path('sample.py').read_text(); expected='def value(): return 2'; assert ast.dump(ast.parse(source)) == ast.dump(ast.parse(expected)), 'Unsupported demo program'; namespace={}; exec(compile(source,'sample.py','exec'),namespace); assert type(namespace['value']()) is int and namespace['value']()==2; print(2)"

class SyntheticAgent:
    """Supply domain facts through the existing validated Agent port."""

    def run(self, node, context, *, timeout_seconds):
        diagnostic = {'status': 'success', 'category': 'validated_domain', 'affected_layer': 'none', 'evidence': [], 'retryability': 'not_retryable', 'candidates': [], 'confidence': 'unique', 'fingerprint': None, 'human_need': None, 'risk': 'low'}
        workflow = context['root_goal'].get('workflow', 'no-code')
        content = {'domain': 'synthetic'}
        if node == 'method_planner':
            content = {'code_needed': workflow == 'code', 'requirements': [context['root_goal']['goal']]}
        if node == 'scientific_reviewer' and workflow == 'human' and (context['remediation'] is None):
            diagnostic.update(risk='critical', human_need='approval')
        return {'diagnostic': diagnostic, 'content': content}

class SyntheticBackend(FakeCodingBackend):
    """Produce one fixed Fake effect; production independently verifies its claims."""

    def __init__(self, coordinator, repository, containment):
        super().__init__(coordinator.root / 'fake_backend', clock=lambda: 100)
        self.coordinator, self.repository, self.containment = (coordinator, repository, containment)

    def dispatch(self, task, manifest, producer):
        existing = self.lookup(producer)
        if existing['status'] != 'unknown':
            receipt = self.read_receipt(existing['receipt_reference'])
            require(receipt == self._receipt(task, manifest), 'Synthetic dispatch identity changed')
            return receipt
        provider = WorkspaceProvider(self.coordinator.root / 'code_workspaces')
        base = immutable_git_tree(self.repository, task['base_revision'])
        self.containment.record_tool(producer)
        (provider.path(manifest['workspace_id']) / 'sample.py').write_bytes(b'def value():\n    return 2\n')
        tool = task['tool_policy'][0]
        audit = canonical_bytes({'tool_event_index': 1, 'task_id': task['task_id'], 'workspace_id': manifest['workspace_id'], 'tool_id': tool['spec_id'], 'argv_digest': digest(tool['argv']), 'cwd': '.', 'start_at': 100, 'end_at': 100, 'status': 'completed', 'affected_paths': ['sample.py'], 'output_digest': digest(''), 'resource_usage': {'llm_calls': 0, 'tool_calls': 1, 'active_seconds': 0}}) + b'\n'
        witness = provider._public_witness(manifest)
        stop = {'termination_or_not_dispatched': 'confirmed', 'write_lease_revocation': True, 'verify_empty': True, 'bounded_drain': True, 'post_stop_stability': True}
        changes, seal = seal_workspace(provider, task, manifest, witness, base, backend_status='completed', stop_proof=stop, tool_audit=audit, sealed_at=self.coordinator._time().monotonic_seconds, fence=lambda: None)
        final = provider.verify_sealed(manifest, witness, seal['final_tree_digest'])
        patch = canonical_patch(base, final, changes['changes'])
        receipt = self._receipt(task, manifest)
        result = {**{key: task[key] for key in IDENTITY}, 'schema_version': '0.1', 'result_id': task['attempt_id'] + ':external_result', 'task_id': task['task_id'], 'task_digest': task['task_digest'], 'workspace_id': manifest['workspace_id'], 'workspace_manifest_digest': manifest['manifest_digest'], 'base_revision': task['base_revision'], 'base_tree_digest': task['base_tree_digest'], 'coding_backend_kind': 'fake', 'backend_version': '0.1', 'provider_operation_reference': None, 'provider_thread_reference': None, 'dispatch_receipt_digest': digest(receipt), 'workspace_seal_digest': seal['seal_digest'], 'change_manifest_digest': changes['change_manifest_digest'], 'tool_audit_digest': seal['tool_audit_digest'], 'change_blobs': [{'path': change['path'], 'sha256': change['after_sha256']} for change in changes['changes'] if change['after_sha256'] is not None], 'patch_digest': sha256(patch).hexdigest(), 'declared_status': 'success', 'backend_verification_claims': [], 'resource_usage': {'llm_calls': 0, 'tool_calls': 1, 'verification_commands': 0, 'active_seconds': 0}, 'warnings': [], 'errors': [], 'failure_evidence': None}
        result['result_digest'] = digest(result)
        directory = self.coordinator.root / 'synthetic_deliveries' / producer
        directory.mkdir(parents=True)
        for name, data in (('tool-audit.jsonl', audit), ('patch.diff', patch)):
            with (directory / name).open('xb') as stream:
                stream.write(data)
        self.operation_scenarios[producer] = producer
        self.fixtures[producer] = {'status': 'completed', 'result': canonical_bytes(result)}
        return super().dispatch(task, manifest, producer)

def host_root(token):
    require(type(token) is str and re.fullmatch('[a-z0-9_]{8}', token) is not None, 'Invalid controlled Host identifier')
    root = execution_scratch_root() / ('lqcd-agent-host-' + token)
    require(root.is_dir() and root == root.resolve() and (root.stat().st_uid == os.getuid()) and (root.stat().st_mode & 63 == 0), 'Host root is not an owned private directory')
    return root

def create_host():
    root = Path(tempfile.mkdtemp(prefix='lqcd-agent-host-', dir=execution_scratch_root()))
    repository = root / 'synthetic_repository'
    repository.mkdir()
    (repository / 'sample.py').write_bytes(b'def value():\n    return 1\n')
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_SYSTEM='/dev/null', GIT_AUTHOR_DATE='2000-01-01T00:00:00+00:00', GIT_COMMITTER_DATE='2000-01-01T00:00:00+00:00')
    for argv in (('init', '-q'), ('add', 'sample.py'), ('-c', 'user.name=Phase B', '-c', 'user.email=phase-b@local', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'Synthetic base')):
        subprocess.run(['git', *argv], cwd=repository, env=environment, capture_output=True, check=True, timeout=30)
    return root

def assemble(coordinator, agent_port=None, *, live=False):
    repository = coordinator.root / 'synthetic_repository'
    require(repository.is_dir() and repository == repository.resolve(), 'Synthetic base escaped its Host')
    revision = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], timeout=30).decode().strip()
    base = immutable_git_tree(repository, revision)
    require(base == {'sample.py': b'def value():\n    return 1\n'}, 'Synthetic base changed')
    tool = {'spec_id': 'synthetic-update', 'argv': ['fixture:write', 'sample.py'], 'cwd': '.', 'timeout_seconds': 1, 'required': True, 'expected_exit_codes': [0], 'environment_keys': []}
    policy = {'base_revision': revision, 'base_tree_digest': tree_digest(base), 'task_summary': 'Implement the synthetic observable', 'acceptance_criteria': ['Trusted syntax check passes'], 'read_paths': ['sample.py'], 'write_paths': ['sample.py'], 'forbidden_paths': ['.git'], 'tool_policy': [tool], 'network_policy': {'enabled': False}, 'filesystem_policy': {'binary_changes': False, 'executable_changes': False, 'ephemeral_paths': ['__pycache__']}, 'verification_specs': [{**tool, 'spec_id': 'syntax', 'argv': ['python', '-m', 'compileall', 'sample.py']}], 'coding_backend_kind': 'fake', 'backend_version': '0.1', 'backend_runtime_fingerprint': digest('fake-0.1')}
    if live:
        from lqcd_agent.code_agent.codex_backend import CodexCodingBackend, ProcessContainment
        backend = CodexCodingBackend(coordinator.root / 'coding_jobs', coordinator.root / 'code_workspaces')
        containment = ProcessContainment(backend)
        tool = {**tool, 'spec_id': 'host-apply-proposal', 'argv': ['host:apply-proposal', 'sample.py']}
        policy.update(coding_backend_kind=backend.kind, backend_version=backend.version,
            backend_runtime_fingerprint=digest('openai-codex-' + backend.version), tool_policy=[tool],
            task_summary='Bounded sample program', acceptance_criteria=['value() returns integer 2'])
    else:
        containment = DeterministicContainment(coordinator.root / 'containment')
        backend = SyntheticBackend(coordinator, repository, containment)
    code = ProductCodeHost(coordinator, repository, backend, containment, task_policy=policy, maximum_charge={'llm_calls': 1, 'tool_calls': 1, 'verification_commands': 0}, timeout_seconds=240 if live else 20, lease_seconds=300 if live else 30)
    analysis = AnalysisHandoff(coordinator, repository, allowed_command=[sys.executable, '-I', '-S', '-c', SAMPLE_ANALYSIS_COMMAND])
    actor = ActorContext('operator', 'human', tuple(sorted(('start', 'resume', 'cancel', 'replay', 'fork', 'policy.select', 'control.internal'))))
    runtime = CanonicalProductRuntime(coordinator, worker_id='product-host', actor=actor, agent_port=agent_port or SyntheticAgent(), analysis_handoff=analysis, code_host=code)
    return (runtime, actor, code)

def execute(args):
    config = None
    if args.command == 'run':
        from lqcd_agent.agents.analysis_engineer import read_case_config
        config = read_case_config(Path(args.case_config))
        args.case = config.get('case_id', args.case)
        args.command, args.workflow = 'start', 'scientific'
    if args.command == 'start' and args.goal is None:
        args.goal = config.get('physics_goal', 'Analyze the configured case') if config else (
            'Implement value() in sample.py returning integer 2' if args.workflow == 'code' else 'Validate the synthetic observable')
    component(args.case)
    if args.command != 'start':
        component(args.run)
    root = create_host() if args.command == 'start' and args.host is None else host_root(args.host)
    live = bool(getattr(args, 'live', False))
    if args.command != 'start':
        goal = loads(read_regular(root / args.case / args.run / 'root_goal.json'))
        config, live = goal.get('case_config'), goal.get('live', False)
    from lqcd_agent.control.clock import HostClock
    from lqcd_agent.settings import ApplicationSettings
    settings = ApplicationSettings.load() if live and args.command in ('start', 'resume', 'fork', 'replay') else None
    with closing(Coordinator(root, clock=HostClock() if live else FakeClock(100, 0))) as coordinator:
        from lqcd_agent.science import ScientificAgent
        runtime, actor, code = assemble(coordinator, ScientificAgent(root, config, provider=settings.provider() if settings else None) if config is not None else None, live=live)
        plane = runtime.plane
        if args.command == 'start':
            inputs = {'root_goal': {'goal': args.goal, 'workflow': args.workflow, 'live': live}, 'input_snapshot': {'kind': 'current_mock' if config is None else 'scientific_case', 'case_config': config}}
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
            elif args.command == 'status':
                pass
            elif args.command == 'cancel':
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
        run, execution = runtime._records(locator)
        state = execution.projection.value
        inputs = {name: loads(read_regular(run / (name + '.json'))) for name in ('root_goal', 'input_snapshot')}
        backend_state = None
        if live and state.get('active_pause'):
            opened = next((r for r in reversed(execution.values) if r.get('event') == 'pause_opened' and r.get('pause_id') == state['active_pause']['pause_id']), None)
            if opened and opened['reason'] == 'external_result':
                backend_state = code.backend.lookup(opened['input_contract']['producer_operation_id'])
        result = {'host': root.name.removeprefix('lqcd-agent-host-'), 'run_locator': locator, 'run_status': state['run_status'], 'execution_head': state['execution_head'], 'root_inputs_digest': digest(inputs), 'active_pause': state.get('active_pause')}
        if live:
            result['coding_backend'] = backend_state
        return result
