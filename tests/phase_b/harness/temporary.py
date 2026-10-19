"""Own new test directories without changing frozen source-root locations."""
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import stat
import tempfile

import pytest


LEDGER_ENV = "LQCD_PYTEST_TEMP_LEDGER"


def mkdtemp(*args, **kwargs):
    directory = tempfile.mkdtemp(*args, **kwargs)
    ledger = os.environ.get(LEDGER_ENV)
    if ledger:
        path = Path(directory).resolve()
        identity = path.stat()
        row = {"path": str(path), "device": identity.st_dev, "inode": identity.st_ino}
        try:
            with open(ledger, "ab") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                stream.write((json.dumps(row) + "\n").encode())
        except BaseException:
            path.rmdir()
            raise
    return directory


class TemporaryDirectories:
    def __init__(self, config):
        self.config = config
        self.directory = Path(tempfile.mkdtemp(prefix="lqcd-agent-pytest-", dir="/private/tmp"))
        self.ledger = self.directory / "directories.jsonl"
        self.ledger.touch(mode=0o600)
        self.formal = bool(os.environ.get("PHASE_B_EVIDENCE_REQUEST"))
        os.environ[LEDGER_ENV] = str(self.ledger)

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_sessionfinish(self, session, exitstatus):
        outcome = yield
        retained = self.formal or int(exitstatus) != 0 or outcome.excinfo is not None
        retained = retained or bool(multiprocessing.active_children())
        if not retained:
            try:
                rows = [json.loads(line) for line in self.ledger.read_text().splitlines()]
                for row in reversed(rows):
                    path = Path(row["path"])
                    try:
                        identity = path.lstat()
                    except FileNotFoundError:
                        continue
                    if not stat.S_ISDIR(identity.st_mode) or (identity.st_dev, identity.st_ino) != (row["device"], row["inode"]):
                        retained = True
                        continue
                    shutil.rmtree(path)
                if not retained:
                    shutil.rmtree(self.directory)
            except (OSError, ValueError, KeyError, TypeError):
                retained = True
        if retained:
            terminal = self.config.pluginmanager.getplugin("terminalreporter")
            if terminal:
                terminal.write_line(f"Test directories retained; ownership ledger: {self.ledger}")

    def pytest_unconfigure(self):
        if os.environ.get(LEDGER_ENV) == str(self.ledger):
            del os.environ[LEDGER_ENV]


def pytest_configure(config):
    # Nested pytest and spawned workers append to the outer owner's ledger.
    if not os.environ.get(LEDGER_ENV):
        config.pluginmanager.register(TemporaryDirectories(config), "phase-b-temporary-directories")
