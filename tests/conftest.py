"""Own only this test session's fresh roots under the configured scratch parent."""
import os
from pathlib import Path
import shutil
import stat
import tempfile
import pytest
from tests.support import OWNED

def pytest_configure(config):
    from lqcd_agent.control.storage import execution_scratch_root
    if config.option.basetemp is None:
        parent = Path(tempfile.mkdtemp(prefix="lqcd-agent-tests-", dir=execution_scratch_root()))
        config.option.basetemp = str(parent / "pytest")

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, "report_" + outcome.get_result().when, outcome.get_result())

@pytest.fixture(autouse=True)
def owned_roots(request):
    start = len(OWNED)
    yield
    failed = any(getattr(request.node, "report_" + phase, None) is not None and
                 getattr(request.node, "report_" + phase).failed for phase in ("setup", "call"))
    if failed or os.environ.get("LQCD_KEEP_TEST_RUNS") == "1":
        return
    for path, device, inode in OWNED[start:]:
        if path.exists():
            current = path.lstat()
            if stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == (device, inode):
                shutil.rmtree(path)
