"""Explicit integration examples using the canonical engine and existing Code interface."""
from hashlib import sha256
import subprocess
import sys
from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
from lqcd_agent.code_agent.schemas import IDENTITY
from lqcd_agent.code_agent.subgraph import ProductCodeHost
from lqcd_agent.code_agent.workspace import WorkspaceProvider, canonical_patch, create_base_repository, immutable_git_tree, seal_workspace, tree_digest
from lqcd_agent.control.strict_json import canonical_bytes, digest, require

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

    def __init__(self, coordinator, repository, containment, *, files=None):
        super().__init__(coordinator.root / 'fake_backend', clock=lambda: 100)
        self.coordinator, self.repository, self.containment = (coordinator, repository, containment)
        self.files = files if files is not None else {'sample.py': b'def value():\n    return 2\n'}

    def dispatch(self, task, manifest, producer):
        existing = self.lookup(producer)
        if existing['status'] != 'unknown':
            receipt = self.read_receipt(existing['receipt_reference'])
            require(receipt == self._receipt(task, manifest), 'Synthetic dispatch identity changed')
            return receipt
        provider = WorkspaceProvider(self.coordinator.root / 'code_workspaces')
        base = immutable_git_tree(self.repository, task['base_revision'])
        self.containment.record_tool(producer)
        for path, content in self.files.items():
            (provider.path(manifest['workspace_id'])/path).write_bytes(content)
        tool = task['tool_policy'][0]
        audit = canonical_bytes({'tool_event_index': 1, 'task_id': task['task_id'], 'workspace_id': manifest['workspace_id'], 'tool_id': tool['spec_id'], 'argv_digest': digest(tool['argv']), 'cwd': '.', 'start_at': 100, 'end_at': 100, 'status': 'completed', 'affected_paths': sorted(self.files), 'output_digest': digest(''), 'resource_usage': {'llm_calls': 0, 'tool_calls': 1, 'active_seconds': 0}}) + b'\n'
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


def prepare_code(coordinator, *, live, initialize):
    root = coordinator.root
    if initialize and not (root/'example_repository').exists():
        create_base_repository(root/'example_repository', {'sample.py': b'def value():\n    return 1\n'})
    repository = coordinator.root / 'example_repository'
    require(repository.is_dir() and repository == repository.resolve(), 'Synthetic base escaped its Host')
    revision = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], timeout=30).decode().strip()
    base = immutable_git_tree(repository, revision)
    require(base == {'sample.py': b'def value():\n    return 1\n'}, 'Synthetic base changed')
    tool = {'spec_id': 'synthetic-update', 'argv': ['fixture:write', 'sample.py'], 'cwd': '.', 'timeout_seconds': 1, 'required': True, 'expected_exit_codes': [0], 'environment_keys': []}
    policy = {'base_revision': revision, 'base_tree_digest': tree_digest(base), 'task_summary': 'Implement the synthetic observable', 'acceptance_criteria': ['Trusted syntax check passes'], 'read_paths': ['sample.py'], 'write_paths': ['sample.py'], 'forbidden_paths': ['.git'], 'tool_policy': [tool], 'network_policy': {'enabled': False}, 'filesystem_policy': {'binary_changes': False, 'executable_changes': False, 'ephemeral_paths': ['__pycache__']}, 'verification_specs': [{**tool, 'spec_id': 'syntax', 'argv': ['python', '-m', 'compileall', 'sample.py']}], 'coding_backend_kind': 'fake', 'backend_version': '0.1', 'backend_runtime_fingerprint': digest('fake-0.1')}
    if live:
        from lqcd_agent.code_agent.codex_backend import CodexCodingBackend, ProcessContainment, JOBS_DIRECTORY
        backend = CodexCodingBackend(coordinator.root / JOBS_DIRECTORY, coordinator.root / 'code_workspaces')
        containment = ProcessContainment(backend)
        tool = {**tool, 'spec_id': 'codex-task', 'argv': ['codex:task'], 'timeout_seconds': 240}
        policy.update(coding_backend_kind=backend.kind, backend_version=backend.version,
            backend_runtime_fingerprint=digest('openai-codex-' + backend.version), tool_policy=[tool],
            network_policy={'enabled': True}, task_summary='Bounded sample program', acceptance_criteria=['value() returns integer 2'])
    else:
        containment = DeterministicContainment(coordinator.root / 'containment')
        backend = SyntheticBackend(coordinator, repository, containment)
    code = ProductCodeHost(coordinator, repository, backend, containment, task_policy=policy, maximum_charge={'llm_calls': 1, 'tool_calls': 16 if live else 1, 'verification_commands': 0}, timeout_seconds=240 if live else 20, lease_seconds=300 if live else 30)
    analysis = AnalysisHandoff(coordinator, repository, allowed_command=[sys.executable, '-I', '-S', '-c', SAMPLE_ANALYSIS_COMMAND])
    return code, analysis
