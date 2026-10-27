"""The Mac execution parent is fixed and rejects unsupported paths/platforms."""
from pathlib import Path

import pytest

from lqcd_agent.control import storage
from lqcd_agent.control.strict_json import ControlIntegrityError


def test_actual_scratch_parent_is_fixed_and_existing(monkeypatch):
    monkeypatch.setenv("TMPDIR", "/tmp/foreign-caller-parent")
    assert storage.execution_scratch_root() == Path("/private/tmp")


def test_pytest_owned_tmp_path_uses_the_same_approved_parent(tmp_path):
    assert tmp_path.is_relative_to(storage.execution_scratch_root())
    assert tmp_path.relative_to(storage.execution_scratch_root()).parts[0].startswith("lqcd-agent-")


@pytest.mark.parametrize("fault", ["missing", "symlink"])
def test_invalid_parent_is_refused_without_fallback(tmp_path, monkeypatch, fault):
    proposed = tmp_path / "untrusted-parent"
    if fault == "symlink":
        proposed.symlink_to(storage.execution_scratch_root(), target_is_directory=True)
    monkeypatch.setattr(storage, "Path", lambda _: proposed)
    with pytest.raises(ControlIntegrityError, match="existing canonical directory"):
        storage.execution_scratch_root()


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_unqualified_platform_cannot_select_an_execution_parent(monkeypatch, platform):
    monkeypatch.setattr(storage.sys, "platform", platform)
    with pytest.raises(ControlIntegrityError, match="qualified macOS platform"):
        storage.execution_scratch_root()
