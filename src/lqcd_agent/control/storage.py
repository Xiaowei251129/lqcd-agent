"""Trusted scratch and the approved one-Host Orion storage admission profile."""
import os
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
import re
import sqlite3
import stat
import sys

from .strict_json import canonical_bytes, loads, require


@lru_cache(maxsize=1)
def storage_profile():
    """Read a trusted deployment profile; callers cannot pass output roots."""
    import json
    path = Path(os.environ.get("LQCD_AGENT_STORAGE_CONFIG", str(files("lqcd_agent").joinpath("resources/storage.json"))))
    require(path == path.resolve() and path.is_file() and not path.is_symlink(), "Invalid storage configuration path")
    identity = path.stat()
    require(identity.st_uid == os.getuid() and not identity.st_mode & 0o002, "Untrusted storage configuration owner or mode")
    value = json.loads(path.read_text())
    require(set(value) == {"scratch_root", "mount_point", "filesystem_type", "mount_source", "required_options", "forbidden_options", "minimum_sqlite_version"}, "Invalid storage configuration fields")
    return value

LINUX_SCRATCH = Path(storage_profile()["scratch_root"])


def execution_scratch_root():
    """Return the fixed trusted parent, never a caller-selected output root."""
    require(sys.platform in ("darwin", "linux"), "Unsupported execution scratch platform")
    root = Path("/private/tmp") if sys.platform == "darwin" else LINUX_SCRATCH
    require(root.is_absolute() and root.is_dir() and root == root.resolve() and not root.is_symlink(),
            "Execution scratch must be an existing canonical directory")
    return root


def _mount(path):
    matches = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        fields, filesystem = left.split(), right.split()
        mount = fields[4]
        for escaped, character in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
            mount = mount.replace(escaped, character)
        parent = Path(mount)
        if path == parent or parent in path.parents:
            matches.append((len(parent.parts), {"parent": parent, "filesystem_type": filesystem[0],
                            "mount_source": filesystem[1], "options": set(fields[5].split(",")) |
                            set(filesystem[2].split(","))}))
    require(bool(matches), "Cannot identify the actual control mount")
    return max(matches, key=lambda item: item[0])[1]


def linux_filesystem(control):
    """Admit only the specifically approved native Lustre client and mount."""
    require(sys.platform == "linux", "Unverified Linux storage platform")
    control = Path(control)
    parent = execution_scratch_root()
    require(control == control.resolve() and control.is_relative_to(parent) and control != parent,
            "Control escaped the approved execution parent")
    private = parent / control.relative_to(parent).parts[0]
    identity = private.stat()
    require(private.name.startswith("lqcd-agent-") and identity.st_uid == os.getuid() and
            stat.S_ISDIR(identity.st_mode) and identity.st_mode & 0o077 == 0,
            "Control requires an owned private execution root")
    mount = _mount(control)
    profile = storage_profile()
    require(mount["parent"] == Path(profile["mount_point"]) and mount["filesystem_type"] == profile["filesystem_type"] and
            mount["mount_source"] == profile["mount_source"] and set(profile["required_options"]) <= mount["options"] and
            not mount["options"].intersection(profile["forbidden_options"]), "Unqualified storage mount or lock profile")
    require(sqlite3.sqlite_version_info >= tuple(profile["minimum_sqlite_version"]), "SQLite runtime is below the supported minimum")
    return mount


def _host_record(control):
    mount = linux_filesystem(control)
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    require(re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", boot) is not None,
            "Cannot establish the actual Host boot identity")
    return {"schema_version": "0.1", "profile": "olcf_lustre_single_host_v1", "host_boot_id": boot,
            "control_root": str(control), "filesystem_type": mount["filesystem_type"],
            "mount_source": mount["mount_source"]}


def require_host_binding(control):
    """Check immutable admission before opening an active SQLite authority."""
    if sys.platform != "linux":
        return
    from .coordinator import read_regular
    control = Path(control)
    path = control / "storage_host.json"
    require(path.exists() or path.is_symlink(), "Missing Storage Host admission")
    identity = path.lstat()
    require(stat.S_ISREG(identity.st_mode) and identity.st_nlink == 1 and
            identity.st_uid == os.getuid() and identity.st_mode & 0o077 == 0,
            "Storage Host admission is not an owned private regular file")
    raw = read_regular(path)
    expected = _host_record(control)
    require(loads(raw) == expected and raw == canonical_bytes(expected),
            "Storage Host admission changed or belongs to a different Host")


def bind_storage_host(control):
    """Exclusively admit a fresh root; never migrate or repair an existing one."""
    if sys.platform != "linux":
        return
    from .coordinator import publish_exact
    control = Path(control)
    path = control / "storage_host.json"
    if not path.exists() and not path.is_symlink():
        require(not (control / "control_operations.sqlite").exists(),
                "Existing SQLite authority has no Storage Host admission")
        publish_exact(path, canonical_bytes(_host_record(control)))
    require_host_binding(control)
