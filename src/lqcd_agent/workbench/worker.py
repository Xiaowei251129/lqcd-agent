"""Single-Host driver; durable control records remain the only work queue."""
from contextlib import closing
import fcntl
import os
import stat
from subprocess import Popen, DEVNULL
import sys
import time

from lqcd_agent.control.clock import HostClock
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.pause import runtime_fingerprint
from lqcd_agent.control.strict_json import digest, loads, require
from lqcd_agent.inspection import host_root, list_runs, read_snapshot
from lqcd_agent.runtime import ApplicationRequest, advance, execute
from lqcd_agent.settings import child_environment, workspace_root


def worker_active(host):
    path = host_root(host)/'workbench-worker.lock'
    if not path.exists():
        return False
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
                info.st_mode & 0o077 == 0, 'Unsafe worker lock')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False
    finally:
        os.close(descriptor)


def launch_worker(host, workspace):
    """Start the one native Host driver after canonical admission, for CLI or HTTP."""
    workspace = workspace_root(workspace)
    root = host_root(host)
    if worker_active(host):
        return None
    from lqcd_agent.research.experiments import continuation_pending
    pending = False
    for locator in list_runs(root):
        snapshot = read_snapshot(root, locator)
        goal = loads(read_regular(snapshot.root/'root_goal.json'))
        require(goal['workspace'] == str(workspace), 'Driver workspace does not match the admitted Run')
        pause = snapshot.state.get('active_pause')
        if snapshot.fingerprint == runtime_fingerprint() and (snapshot.can_advance or
            pause is not None and pause['reason'] == 'external_result' or continuation_pending(snapshot)):
            pending = True
            break
    if not pending:
        return None
    environment = child_environment()
    environment.update(LQCD_AGENT_WORKSPACE=str(workspace), PYTHONDONTWRITEBYTECODE='1')
    descriptor = os.open(root/'workbench-worker.log', os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'ab') as log:
        info = os.fstat(log.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
                info.st_mode & 0o077 == 0, 'Unsafe worker log')
        return Popen([sys.executable, '-B', '-m', 'lqcd_agent.workbench.worker', host],
            cwd=workspace, env=environment, stdin=DEVNULL, stdout=log, stderr=log, start_new_session=True)


def step(host, locator):
    snapshot = read_snapshot(host_root(host), locator)
    if snapshot.fingerprint != runtime_fingerprint():
        return False
    if snapshot.can_advance:
        advance(host, locator)
        return True
    if snapshot.state['run_status'] == 'completed':
        from lqcd_agent.research.experiments import continue_research
        child = continue_research(host, locator)
        if child is not None:
            advance(host, child)
        return child is not None
    pause = snapshot.state.get('active_pause')
    if pause is None or pause['reason'] != 'external_result':
        return False
    status = snapshot.status()
    job = status.get('coding_backend')
    if 'coding_backend' not in status or job is not None and job['status'] == 'completed':
        execute(ApplicationRequest('resume', host=host, case=locator['case_id'], run=locator['run_id'],
            pause=pause['pause_id'], key='workbench-delivery-'+digest([locator, pause['pause_id']])))
        return True
    with closing(Coordinator(snapshot.host, clock=HostClock())) as coordinator:
        from lqcd_agent.code_agent.codex_backend import CodexCodingBackend, ProcessContainment, JOBS_DIRECTORY
        from lqcd_agent.code_agent.external_operation import CodeWatchdog
        backend = CodexCodingBackend(snapshot.host/JOBS_DIRECTORY, snapshot.host/'code_workspaces')
        opened = next(r for r in snapshot.records.values if r.get('event') == 'pause_opened' and r['pause_id'] == pause['pause_id'])
        watchdog = CodeWatchdog(coordinator, backend, ProcessContainment(backend), backend.read_receipt)
        watchdog.enforce(opened['input_contract']['producer_operation_id'])
    after = read_snapshot(snapshot.host, locator)
    if after.state['execution_head'] != snapshot.state['execution_head']:
        from lqcd_agent.runtime import capture_project
        capture_project(after)
    return True


def main():
    host, = sys.argv[1:]
    root = host_root(host)
    descriptor = os.open(root/'workbench-worker.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
                info.st_mode & 0o077 == 0, 'Unsafe worker lock')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        failed = set()
        while True:
            pending = False
            for locator in list_runs(root):
                identity = digest(locator)
                if identity in failed:
                    continue
                try:
                    pending = step(host, locator) or pending
                except Exception as error:
                    failed.add(identity)
                    print('Run requires operator inspection:', locator['run_id'], type(error).__name__, flush=True)
            if not pending:
                break
            time.sleep(1)
        if failed:
            raise SystemExit(1)
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    main()
