"""The execution parent is fixed, canonical and shared with pytest's own roots."""
from pathlib import Path
import sys

import pytest

from lqcd_agent.control import storage
from lqcd_agent.control.strict_json import ControlIntegrityError


def test_actual_scratch_parent_is_fixed_and_existing(monkeypatch):
    monkeypatch.setenv("TMPDIR", "/tmp/foreign-caller-parent")
    expected = (Path("/private/tmp") if sys.platform == "darwin" else
                Path("/lustre/orion/nph158/proj-shared/xgao/lqcd_agent/tmp"))
    assert storage.execution_scratch_root() == expected
    assert expected.is_dir() and expected.resolve() == expected


def test_pytest_owned_tmp_path_uses_the_same_approved_parent(tmp_path):
    assert tmp_path.is_relative_to(storage.execution_scratch_root())
    assert tmp_path.relative_to(storage.execution_scratch_root()).parts[0].startswith("lqcd-agent-")


@pytest.mark.parametrize("fault", ["missing", "symlink"])
def test_invalid_linux_parent_is_refused_without_fallback(tmp_path, monkeypatch, fault):
    if sys.platform == "darwin":
        assert storage.execution_scratch_root() == Path("/private/tmp")
        return
    proposed = tmp_path / "untrusted-parent"
    if fault == "symlink":
        proposed.symlink_to(storage.execution_scratch_root(), target_is_directory=True)
    monkeypatch.setattr(storage, "LINUX_SCRATCH", proposed)
    with pytest.raises(ControlIntegrityError, match="existing canonical directory"):
        storage.execution_scratch_root()
