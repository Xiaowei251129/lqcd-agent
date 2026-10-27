"""Exercise native macOS durability and fail-closed Host admission."""
import json
import subprocess
import sys

import pytest

from tests.support import own
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.strict_json import ControlIntegrityError


@pytest.fixture
def admitted_root():
    from lqcd_agent.runtime import create_host
    root = own(create_host())
    coordinator = Coordinator(root)
    coordinator.close()
    return root


def test_actual_native_profile_keeps_wal_full_and_foreign_keys(admitted_root):
    coordinator = Coordinator(admitted_root)
    try:
        assert coordinator.filesystem
        assert coordinator.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert coordinator.connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert coordinator.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        coordinator.close()


def test_existing_authority_rejects_unsupported_platform_without_writes(admitted_root, monkeypatch):
    from lqcd_agent.control.clock import FakeClock
    database = admitted_root / ".lqcd/control_operations.sqlite"
    before = database.read_bytes()
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(ControlIntegrityError, match="Unverified platform durability profile"):
        Coordinator(admitted_root, clock=FakeClock())
    assert database.read_bytes() == before


def test_public_host_lookup_rejects_permissions_before_database_changes(admitted_root):
    from lqcd_agent.inspection import host_root
    database = admitted_root / ".lqcd/control_operations.sqlite"
    before = database.read_bytes()
    admitted_root.chmod(0o755)
    try:
        with pytest.raises(ControlIntegrityError):
            host_root(admitted_root.name.removeprefix('lqcd-agent-host-'))
    finally:
        admitted_root.chmod(0o700)
    assert database.read_bytes() == before


def test_independent_processes_reopen_the_same_native_authority(admitted_root):
    code = '''import json, os, sys
from lqcd_agent.control.coordinator import Coordinator
coordinator = Coordinator(sys.argv[1])
try:
 print(json.dumps({"pid":os.getpid(), "database":str(coordinator.path),
                   "mode":coordinator.connection.execute("PRAGMA journal_mode").fetchone()[0]}))
finally:
 coordinator.close()
'''
    argv = [sys.executable, "-B", "-c", code, str(admitted_root)]
    clients = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
               for _ in range(2)]
    rows = []
    for client in clients:
        stdout, stderr = client.communicate(timeout=60)
        assert client.returncode == 0, stderr
        rows.append(json.loads(stdout))
    (admitted_root / "independent-clients.json").write_text(json.dumps(rows))
    assert rows[0]["pid"] != rows[1]["pid"]
    assert {row["mode"] for row in rows} == {"wal"}
    assert {row["database"] for row in rows} == {str(admitted_root / ".lqcd/control_operations.sqlite")}
