"""Filesystem evidence checks on disposable, committed synthetic repositories."""
from copy import deepcopy
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile

import pytest

from lqcd_agent.code_agent.workspace import WorkspaceProvider, immutable_git_tree, scan_tree, tree_digest, validate_changes
from lqcd_agent.control.strict_json import ControlIntegrityError, digest


@pytest.fixture
def workspace():
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-workspace-", dir="/private/tmp"))
    base = {"sample.py": b"value = 1\n"}
    manifest = {"workspace_id": "workspace_fixture", "manifest_digest": digest("manifest"),
                "managed_root_identity": digest("root"), "base_tree_digest": tree_digest(base)}
    provider = WorkspaceProvider(root / "managed")
    witness = provider.materialize(manifest, base, lambda: None)
    return provider, manifest, witness, base


def test_workspace_reopens_exact_identity_and_rejects_replacement(workspace):
    provider, manifest, witness, base = workspace
    reopened = WorkspaceProvider(provider.root)
    assert reopened.materialize(manifest, base, lambda: None, witness=witness) == witness
    path = reopened.verify_identity(manifest, witness)
    backup = path.with_name("old_workspace")
    path.rename(backup)
    shutil.copytree(backup, path)
    assert scan_tree(path) == base
    with pytest.raises(ControlIntegrityError, match="replaced"):
        reopened.verify_identity(manifest, witness)


def test_workspace_fence_runs_before_any_directory_or_file_creation(workspace):
    provider, manifest, witness, base = workspace
    other = {**manifest, "workspace_id": "workspace_unowned"}
    def reject():
        raise ControlIntegrityError("Stale owner")
    with pytest.raises(ControlIntegrityError, match="Stale"):
        provider.materialize(other, base, reject)
    assert not provider.path(other["workspace_id"]).exists()


@pytest.mark.parametrize("fault", ["symlink", "hardlink", "directory_symlink", "socket", "executable", "git_metadata", "empty_directory", "binary", "post_seal", "missing"])
def test_workspace_scope_and_seal_fail_closed(workspace, fault):
    provider, manifest, witness, base = workspace
    root = provider.path(manifest["workspace_id"])
    socket_handle = None
    if fault == "symlink":
        (root / "escape.py").symlink_to(root.parent / "outside")
    elif fault == "hardlink":
        os.link(root / "sample.py", root / "alias.py")
    elif fault == "directory_symlink":
        (root / "escape").symlink_to(root.parent, target_is_directory=True)
    elif fault == "socket":
        socket_handle = socket.socket(socket.AF_UNIX)
        socket_handle.bind(str(root / "s"))
    elif fault == "executable":
        (root / "sample.py").chmod(0o700)
    elif fault == "git_metadata":
        (root / ".git").mkdir()
    elif fault == "empty_directory":
        (root / "undeclared").mkdir()
    elif fault == "binary":
        (root / "sample.py").write_bytes(b"binary\x00content")
    elif fault == "post_seal":
        (root / "sample.py").write_text("value = 2\n")
    else:
        shutil.rmtree(root)
    try:
        with pytest.raises((ControlIntegrityError, ValueError)):
            provider.verify_sealed(manifest, witness, manifest["base_tree_digest"])
    finally:
        if socket_handle is not None:
            socket_handle.close()


def test_changes_are_derived_from_full_content_and_explicit_scope(workspace):
    _, manifest, _, base = workspace
    task = {"base_tree_digest": manifest["base_tree_digest"], "write_paths": ["sample.py"], "forbidden_paths": [],
            "filesystem_policy": {"ephemeral_paths": ["cache"]}}
    final = {"sample.py": b"value = 2\n"}
    changes = validate_changes(task, base, final)
    assert len(changes) == 1 and changes[0]["kind"] == "modified" and changes[0]["before_sha256"] != changes[0]["after_sha256"]
    assert validate_changes(task, base, base) == []
    with pytest.raises(ControlIntegrityError, match="scope"):
        validate_changes(task, base, {**final, "outside.py": b"pass\n"})
    widened = deepcopy(task)
    widened["write_paths"].append("cache")
    with pytest.raises(ControlIntegrityError, match="scope"):
        validate_changes(widened, base, {**final, "cache/temp.py": b"pass\n"})


def test_immutable_base_reads_committed_blobs_without_checkout_or_dirty_bytes():
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-base-", dir="/private/tmp"))
    (root / "sample.py").write_bytes(b"value = 1\n")
    def git(*args):
        return subprocess.check_output(["/usr/bin/git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
    git("init", "-q")
    git("add", "sample.py")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
        "-c", "core.hooksPath=/dev/null", "commit", "-qm", "Immutable workspace fixture")
    revision = git("rev-parse", "HEAD")
    (root / "sample.py").write_bytes(b"value = 99\n")
    (root / "untracked.py").write_bytes(b"pass\n")
    assert immutable_git_tree(root, revision) == {"sample.py": b"value = 1\n"}
    assert (root / "sample.py").read_bytes() == b"value = 99\n"
    with pytest.raises(ControlIntegrityError):
        immutable_git_tree(root, "HEAD")
    with pytest.raises(ControlIntegrityError):
        immutable_git_tree(Path(__file__).resolve().parents[2], revision)
