"""Single-Host driver; durable control records remain the only work queue."""
from contextlib import closing
import fcntl
import os
import stat
import sys
import time

from lqcd_agent.control.clock import HostClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.pause import runtime_fingerprint
from lqcd_agent.control.strict_json import digest, require
from lqcd_agent.inspection import host_root, list_runs, read_snapshot
from lqcd_agent.runtime import ApplicationRequest, advance, execute


def step(host, locator):
    snapshot = read_snapshot(host_root(host), locator)
    if snapshot.fingerprint != runtime_fingerprint():
        return False
    if snapshot.can_advance:
        advance(host, locator)
        return True
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
