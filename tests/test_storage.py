"""Exercise real native admission and the new immutable one-Host storage record."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.support import mkdtemp
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.storage import execution_scratch_root
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes


@pytest.fixture
def admitted_root():
    root = Path(mkdtemp(prefix="lqcd-agent-c38-admission-", dir=execution_scratch_root()))
    coordinator = Coordinator(root)
    coordinator.close()
    return root


def linux_record(root):
    path = root / ".lqcd/storage_host.json"
    if sys.platform == "darwin":
        assert not path.exists()
        return None
    assert sys.platform == "linux"
    assert path.is_file()
    return path


def test_actual_native_profile_keeps_wal_full_and_foreign_keys(admitted_root):
    coordinator = Coordinator(admitted_root)
    try:
        assert coordinator.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert coordinator.connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert coordinator.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        path = linux_record(admitted_root)
        if path is not None:
            record = json.loads(path.read_bytes())
            assert set(record) == {"schema_version", "profile", "host_boot_id", "control_root",
                                   "filesystem_type", "mount_source"}
            assert record["host_boot_id"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            assert record["control_root"] == str(admitted_root / ".lqcd")
            assert record["filesystem_type"] == coordinator.filesystem == "lustre"
    finally:
        coordinator.close()


@pytest.mark.parametrize("field", ["schema_version", "profile", "host_boot_id", "control_root",
                                   "filesystem_type", "mount_source"])
def test_changed_admission_is_rejected_before_sqlite_changes(admitted_root, field):
    path = linux_record(admitted_root)
    if path is None:
        return
    previous = path.read_bytes()
    (admitted_root / "original-storage-admission.json").write_bytes(previous)
    value = json.loads(previous)
    value[field] = "foreign-" + value[field]
    path.write_bytes(canonical_bytes(value))
    database = admitted_root / ".lqcd/control_operations.sqlite"
    before = sha256(database.read_bytes()).hexdigest()
    with pytest.raises(ControlIntegrityError, match="Storage Host admission"):
        Coordinator(admitted_root)
    assert sha256(database.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("fault", ["missing", "symlink", "hardlink", "extra_field", "partial_json",
                                   "duplicate_field", "noncanonical", "public_mode"])
def test_malformed_or_redirected_admission_never_reopens_authority(admitted_root, fault):
    path = linux_record(admitted_root)
    if path is None:
        return
    previous = path.read_bytes()
    saved = admitted_root / "original-storage-admission.json"
    saved.write_bytes(previous)
    if fault in ("missing", "symlink"):
        path.rename(admitted_root / "before-storage-admission.json")
        if fault == "symlink":
            path.symlink_to(saved)
    elif fault == "hardlink":
        os.link(path, admitted_root / "linked-storage-admission.json")
    elif fault == "extra_field":
        path.write_bytes(canonical_bytes({**json.loads(previous), "allow": True}))
    elif fault == "partial_json":
        path.write_bytes(previous[:10])
    elif fault == "duplicate_field":
        path.write_bytes(b'{"profile":"duplicate",' + previous[1:])
    elif fault == "noncanonical":
        path.write_bytes(previous + b"\n")
    else:
        path.chmod(0o644)
    database = admitted_root / ".lqcd/control_operations.sqlite"
    before = sha256(database.read_bytes()).hexdigest()
    with pytest.raises(ControlIntegrityError):
        Coordinator(admitted_root)
    assert sha256(database.read_bytes()).hexdigest() == before


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
