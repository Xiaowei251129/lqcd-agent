"""One local execution boundary for sealed scientific programs and independent grading."""
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import math
import ctypes
import errno
from types import SimpleNamespace
from lqcd_agent.control.coordinator import publish_exact, read_regular
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, loads, require
from lqcd_agent.settings import child_environment


def interpreter_identity(python, *, timeout=15):
    script = ('import json,sys,importlib.metadata as m; '
        'print(json.dumps({"python":sys.version,"prefix":sys.prefix,"base_prefix":sys.base_prefix,'
        '"libraries":{d.metadata["Name"].lower():d.version for d in m.distributions() '
        'if d.metadata["Name"].lower() in ("numpy","scipy")}}))')
    return loads(subprocess.check_output([str(python), '-I', '-B', '-c', script],
        env=child_environment(), timeout=timeout), canonical=False)


# Numerical controls may vary in a new, separately sealed Run. Measured values,
# sample identities, units and physical definitions remain immutable source data.
ANALYSIS_PARAMETERS = frozenset({'binsize', 'bootstrap_samples', 'seed', 'tmins', 'tmax',
                                 'fixed_ground_energy', 'omit_reference'})


def read_scientific_input(workspace, snapshot, parameters):
    from lqcd_agent.tools.dataset import read_dataset
    record, payload = read_dataset(workspace, snapshot['path'], values=True)
    require(record == snapshot, 'Scientific dataset changed before consumption')
    require(not (parameters.keys() & payload.keys()) - ANALYSIS_PARAMETERS,
            'Scientific parameters replace source data fields')
    return {**payload, **parameters}


def sandbox_command(command, cwd, interpreter_roots, *, timeout=120, cancelled=None):
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
        'permissions.research_grade.network.enabled=false')
    argv = [str(bundled_codex_path())]
    for override in overrides:
        argv.extend(['--config', override])
    argv.extend(['sandbox', '--permission-profile', 'research_grade', '--cd', str(cwd), '--', *command])
    launcher = ('import os,resource,sys; '
        'resource.setrlimit(resource.RLIMIT_CORE,(0,0)); '
        'resource.setrlimit(resource.RLIMIT_CPU,('+str(math.ceil(timeout))+','+str(math.ceil(timeout))+')); '
        'resource.setrlimit(resource.RLIMIT_FSIZE,(2000000,2000000)); os.execv(sys.argv[1],sys.argv[1:])')
    import sys
    with (cwd/'stdout.log').open('wb') as stdout, (cwd/'stderr.log').open('wb') as stderr:
        process = subprocess.Popen([sys.executable, '-I', '-S', '-c', launcher, *argv],
            cwd=cwd, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
        # Darwin's Python omits os.waitid. libc WNOWAIT observes exit while the
        # unreaped leader still owns its PID/PGID, including on the success path.
        waitid = ctypes.CDLL(None, use_errno=True).waitid
        waitid.argtypes = (ctypes.c_int, ctypes.c_uint, ctypes.c_void_p, ctypes.c_int)
        waitid.restype = ctypes.c_int
        def exited():
            info = ctypes.create_string_buffer(128)
            result = waitid(os.P_PID, process.pid, info, os.WEXITED | os.WNOWAIT | os.WNOHANG)
            if result != 0:
                code = ctypes.get_errno()
                if code == errno.EINTR:
                    return False
                raise OSError(code, os.strerror(code))
            return any(info.raw)
        try:
            deadline = time.monotonic() + timeout
            while not exited():
                if cancelled is not None and cancelled():
                    raise InterruptedError('Numerical execution cancelled')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                time.sleep(min(.05, remaining))
        finally:
            # A successful program can leave background descendants. Revoke their
            # ability to mutate scratch before freezing any stdout or stderr.
            from .codex_backend import group_members
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                # Darwin rejects killpg on a group containing only its zombie
                # leader. Verify no live member remains; never waive a live one.
                require(not group_members(process.pid), 'Numerical process group could not be stopped')
            drained = time.monotonic() + 2
            while group_members(process.pid) and time.monotonic() < drained:
                time.sleep(.05)
            require(not group_members(process.pid), 'Numerical process group did not stop')
            process.wait(timeout=2)
    return SimpleNamespace(exit_code=process.returncode,
        stdout=(cwd/'stdout.log').read_text(), stderr=(cwd/'stderr.log').read_text())


class CandidateExecutionError(ControlIntegrityError):
    """A known numerical failure with the actual immutable execution evidence."""
    def __init__(self, message, execution):
        super().__init__(message)
        self.execution = execution


def execute_candidate(program, payload, python, *, timeout=120, expected_runtime=None, cancelled=None):
    """The candidate sees its inputs and libraries, never reference results or keys."""
    started = time.monotonic()
    metadata = interpreter_identity(python, timeout=min(15, timeout))
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
    remaining = timeout - (time.monotonic() - started)
    require(remaining > 0, 'Scientific interpreter inspection exhausted execution time')
    timed_out = False
    try:
        reply = sandbox_command([str(python), '-I', '-B', str(root/'analysis.py'), str(root/'input.json')],
                                root, interpreter_roots, timeout=remaining, cancelled=cancelled)
    except subprocess.TimeoutExpired:
        timed_out = True
        reply = None
    require(read_regular(root/'analysis.py') == program and read_regular(root/'input.json') == input_bytes,
            'Candidate changed its sealed source or input')
    execution = {'root': str(root), 'program_sha256': sha256(program).hexdigest(),
                    'stdout_sha256': sha256(read_regular(root/'stdout.log')).hexdigest(),
                    'stderr_sha256': sha256(read_regular(root/'stderr.log')).hexdigest(),
                    'input_sha256': sha256(input_bytes).hexdigest(), 'python': str(python),
                    'runtime_roots': sorted(str(Path(p).resolve()) for p in interpreter_roots), **metadata}
    if timed_out:
        raise CandidateExecutionError('Candidate execution timed out', execution)
    if reply.exit_code != 0:
        raise CandidateExecutionError('Candidate execution failed: '+reply.stderr[:1500], execution)
    try:
        result = loads(reply.stdout, canonical=False)
        require(type(result) is dict, 'Candidate must produce a JSON object')
    except ValueError as error:
        raise CandidateExecutionError('Candidate output is not a finite JSON object', execution) from error
    return result, execution
