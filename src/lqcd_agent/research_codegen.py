"""Research task assembly over the existing durable CodeHost and graph."""
import subprocess
import sys

from .code_agent.analysis_handoff import AnalysisHandoff
from .code_agent.codex_backend import CodexCodingBackend, ProcessContainment, JOBS_DIRECTORY
from .code_agent.subgraph import ProductCodeHost
from .code_agent.workspace import create_base_repository, immutable_git_tree, tree_digest
from .control.strict_json import digest, require
from .research_cases import PROGRAM_REQUIREMENTS


class ResearchCodeAgent:
    def __init__(self, family):
        self.family = family

    def run(self, node, context, *, timeout_seconds):
        diagnostic = {'status': 'success', 'category': 'validated_domain', 'affected_layer': 'none',
            'evidence': [], 'retryability': 'not_retryable', 'candidates': [], 'confidence': 'unique',
            'fingerprint': None, 'human_need': None, 'risk': 'low'}
        content = {'summary': 'Research program generation; scientific acceptance is pending.'}
        if node == 'method_planner':
            content.update(code_needed=True, requirements=PROGRAM_REQUIREMENTS[self.family])
        if node == 'analysis_engineer':
            diagnostic.update(status='failed', category='implementation_gap', affected_layer='analysis',
                human_need='approval', risk='high')
            content.update(summary='Code syntax verified. Independent numerical case evaluation is required.',
                           numerical_validation='pending', physics_accepted=False)
        return {'diagnostic': diagnostic, 'content': content}


def prepare_research(coordinator, family, *, live, initialize):
    require(family in PROGRAM_REQUIREMENTS and live, 'Research coding requires an explicit live Codex task')
    repository = coordinator.root/'research_repository'
    base_files = {'analysis.py': b'raise NotImplementedError("Implement the research task")\n'}
    if initialize:
        create_base_repository(repository, base_files)
    revision = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip()
    base = immutable_git_tree(repository, revision)
    require(base == base_files, 'Research coding base changed')
    backend = CodexCodingBackend(coordinator.root/JOBS_DIRECTORY, coordinator.root/'code_workspaces')
    containment = ProcessContainment(backend)
    tool = {'spec_id': 'research-codex', 'argv': ['codex:research-task'], 'cwd': '.',
            'timeout_seconds': 600, 'required': True, 'expected_exit_codes': [0], 'environment_keys': []}
    policy = {'base_revision': revision, 'base_tree_digest': tree_digest(base),
        'task_summary': 'Independent research program: '+family,
        'acceptance_criteria': ['Implement the specified JSON interface and test on synthetic calibration data.'],
        'read_paths': ['analysis.py'], 'write_paths': ['analysis.py'], 'forbidden_paths': ['.git'],
        'tool_policy': [tool], 'network_policy': {'enabled': True},
        'filesystem_policy': {'binary_changes': False, 'executable_changes': False, 'ephemeral_paths': ['__pycache__']},
        'verification_specs': [{**tool, 'spec_id': 'syntax', 'argv': ['python', '-m', 'compileall', 'analysis.py'],
                                'timeout_seconds': 10}],
        'coding_backend_kind': backend.kind, 'backend_version': backend.version,
        'backend_runtime_fingerprint': digest('openai-codex-'+backend.version)}
    code = ProductCodeHost(coordinator, repository, backend, containment, task_policy=policy,
        maximum_charge={'llm_calls': 1, 'tool_calls': 32, 'verification_commands': 0},
        timeout_seconds=600, lease_seconds=660)
    # This preparation never executes generated code in an unsandboxed Host interpreter.
    handoff = AnalysisHandoff(coordinator, repository,
        allowed_command=[sys.executable, '-I', '-S', '-c', 'print("independent_numerical_evaluation_pending")'])
    return ResearchCodeAgent(family), code, handoff
