"""One local execution boundary for sealed scientific programs and independent grading."""
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from types import SimpleNamespace
from lqcd_agent.control.coordinator import publish_exact, read_regular
from lqcd_agent.control.strict_json import canonical_bytes, loads, require
from lqcd_agent.settings import child_environment


def interpreter_identity(python):
    script = ('import json,sys,importlib.metadata as m; '
        'print(json.dumps({"python":sys.version,"prefix":sys.prefix,"base_prefix":sys.base_prefix,'
        '"libraries":{d.metadata["Name"].lower():d.version for d in m.distributions() '
        'if d.metadata["Name"].lower() in ("numpy","scipy")}}))')
    return loads(subprocess.check_output([str(python), '-I', '-B', '-c', script],
        env=child_environment(), timeout=15), canonical=False)


def read_scientific_input(workspace, snapshot, parameters):
    from lqcd_agent.tools.dataset import read_dataset
    record, payload = read_dataset(workspace, snapshot['path'], values=True)
    require(record == snapshot, 'Scientific dataset changed before consumption')
    require(not parameters.keys() & payload.keys(), 'Scientific parameters replace source data fields')
    return {**payload, **parameters}


def sandbox_command(command, cwd, interpreter_roots, *, timeout=120):
    """Apply the pinned runtime's explicit OS permission profile without a model."""
    from codex_cli_bin import bundled_codex_path
    cwd = Path(cwd)
    home = cwd.parent/(cwd.name+'-sdk-home')
    home.mkdir(mode=0o700)
    profile = {':root': 'deny', ':minimal': 'read', ':workspace_roots': {'.': 'write'},
               ':tmpdir': 'write', ':slash_tmp': 'deny',
               **{str(Path(root).resolve()): 'read' for root in interpreter_roots}}
    environment = child_environment()
    environment.update(CODEX_HOME=str(home), CODEX_SQLITE_HOME=str(home), TMPDIR=str(cwd))
    overrides = ('permissions.research_grade.filesystem='+json.dumps(profile).replace(': ', ' = '),
        'permissions.research_grade.network.enabled=true')
    argv = [str(bundled_codex_path())]
    for override in overrides:
        argv.extend(['--config', override])
    argv.extend(['sandbox', '--permission-profile', 'research_grade', '--cd', str(cwd), '--', *command])
    launcher = ('import os,resource,sys; '
        'resource.setrlimit(resource.RLIMIT_CORE,(0,0)); '
        'resource.setrlimit(resource.RLIMIT_CPU,('+str(timeout)+','+str(timeout)+')); '
        'resource.setrlimit(resource.RLIMIT_FSIZE,(2000000,2000000)); os.execv(sys.argv[1],sys.argv[1:])')
    import sys
    with (cwd/'stdout.log').open('wb') as stdout, (cwd/'stderr.log').open('wb') as stderr:
        process = subprocess.Popen([sys.executable, '-I', '-S', '-c', launcher, *argv],
            cwd=cwd, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # A timed-out leader has not been reaped, so its group ID cannot be reused.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
    return SimpleNamespace(exit_code=process.returncode,
        stdout=(cwd/'stdout.log').read_text(), stderr=(cwd/'stderr.log').read_text())


def execute_candidate(program, payload, python, *, timeout=120, expected_runtime=None):
    """The candidate sees its inputs and libraries, never reference results or keys."""
    metadata = interpreter_identity(python)
    require(expected_runtime is None or metadata == expected_runtime, 'Scientific interpreter changed')
    interpreter_roots = {metadata['prefix'], metadata['base_prefix']}
    executable = Path(python).absolute()
    while True:
        for path in (executable, *executable.parents):
            if path.is_symlink():
                interpreter_roots.add(str(path.parent))
        interpreter_roots.add(str(executable.parent))
        if not executable.is_symlink():
            break
        link = executable.readlink()
        executable = (executable.parent/link).absolute() if not link.is_absolute() else link
    root = Path(tempfile.mkdtemp(prefix='lqcd-research-grade-', dir='/private/tmp'))
    publish_exact(root/'analysis.py', program)
    input_bytes = canonical_bytes(payload)
    publish_exact(root/'input.json', input_bytes)
    reply = sandbox_command([str(python), '-I', '-B', str(root/'analysis.py'), str(root/'input.json')],
                            root, interpreter_roots, timeout=timeout)
    require(read_regular(root/'analysis.py') == program and read_regular(root/'input.json') == input_bytes,
            'Candidate changed its sealed source or input')
    require(reply.exit_code == 0, 'Candidate execution failed: '+reply.stderr[:1500])
    result = loads(reply.stdout, canonical=False)
    require(type(result) is dict, 'Candidate must produce a JSON object')
    return result, {'root': str(root), 'program_sha256': sha256(program).hexdigest(),
                    'stdout_sha256': sha256(read_regular(root/'stdout.log')).hexdigest(),
                    'stderr_sha256': sha256(read_regular(root/'stderr.log')).hexdigest(),
                    'input_sha256': sha256(input_bytes).hexdigest(), 'python': str(python),
                    'runtime_roots': sorted(str(Path(p).resolve()) for p in interpreter_roots), **metadata}
