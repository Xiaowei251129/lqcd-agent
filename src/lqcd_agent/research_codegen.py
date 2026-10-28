"""Research task assembly over the existing durable CodeHost and graph."""
import subprocess
from pathlib import Path

from .code_agent.analysis_handoff import AnalysisHandoff
from .code_agent.codex_backend import CodexCodingBackend, ProcessContainment, JOBS_DIRECTORY
from .code_agent.subgraph import ProductCodeHost
from .code_agent.workspace import create_base_repository, immutable_git_tree, tree_digest
from .control.strict_json import digest, require


def prepare_research(coordinator, config, *, workspace, live, initialize):
    require(live, 'Generated scientific analysis requires explicit live Codex activation')
    program = config['generated_program']
    from .control.strict_json import closed, number
    closed(program, ('python', 'parameters', 'requirements', 'timeout_seconds', 'result_kind'))
    require(program['result_kind'] in ('c2', 'normalization'), 'Unknown generated scientific output contract')
    require(type(program['requirements']) is list and program['requirements'] and
            all(type(r) is str and 0 < len(r) <= 4096 for r in program['requirements']), 'Missing bounded programming contract')
    require(type(program['parameters']) is dict, 'Scientific parameters must be an object')
    require(Path(program['python']).is_absolute() and Path(program['python']).is_file(), 'Select an existing absolute scientific interpreter')
    number(program['timeout_seconds'], integer=True, minimum=1)
    repository = coordinator.root/'research_repository'
    base_files = {'analysis.py': b'raise NotImplementedError("Implement the research task")\n'}
    if initialize and not repository.exists():
        create_base_repository(repository, base_files)
    revision = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip()
    base = immutable_git_tree(repository, revision)
    require(base == base_files, 'Research coding base changed')
    backend = CodexCodingBackend(coordinator.root/JOBS_DIRECTORY, coordinator.root/'code_workspaces')
    containment = ProcessContainment(backend)
    tool = {'spec_id': 'research-codex', 'argv': ['codex:research-task'], 'cwd': '.',
            'timeout_seconds': 600, 'required': True, 'expected_exit_codes': [0], 'environment_keys': []}
    policy = {'base_revision': revision, 'base_tree_digest': tree_digest(base),
        'task_summary': 'Implement the current scientific Method Plan',
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
    handoff = AnalysisHandoff(coordinator, repository,
        allowed_command=[program['python'], '-I', '-B', 'analysis.py', 'input.json'],
        expected_outputs=['analysis_outputs/generated_result.json'], generated_program=program, workspace=workspace)
    return code, handoff
