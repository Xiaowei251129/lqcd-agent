"""Scoped local files for research metadata, separate from Run execution authority."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile

from lqcd_agent.control.coordinator import sync_directory
from lqcd_agent.control.strict_json import require


class WorkspaceFiles:
    """Canonical paths, advisory metadata locks and durable atomic replacement."""

    def __init__(self, workspace, namespace):
        self.workspace = Path(workspace).absolute()
        require(self.workspace == self.workspace.resolve() and self.workspace.is_dir(),
                "Research workspace must be an existing canonical directory")
        require(namespace in ("library", "projects"), "Unknown research namespace")
        self.root = self.workspace / namespace

    def _path(self, relative):
        require(type(relative) is str and relative and "\\" not in relative and "\0" not in relative,
                "Invalid research path")
        parts = PurePosixPath(relative).parts
        require(not PurePosixPath(relative).is_absolute() and parts and
                all(part not in (".", "..") for part in parts) and
                str(PurePosixPath(relative)) == relative, "Invalid research relative path")
        path = self.workspace / relative
        require(path == path.resolve() and path.is_relative_to(self.workspace), "Redirected research path")
        return path

    @contextmanager
    def _locked(self, *, create=False, write=False):
        path = self._path(self.root.name + "/.lock")
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
        if create:
            flags |= os.O_CREAT
        descriptor = os.open(path, flags, 0o600)
        try:
            info = os.fstat(descriptor)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Invalid research metadata lock")
            fcntl.flock(descriptor, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            yield
        finally:
            os.close(descriptor)

    def _atomic(self, path, content):
        require(path == path.resolve() and path.is_relative_to(self.root), "Redirected asset publication")
        descriptor, stage = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(stage, path)
            sync_directory(path.parent)
        finally:
            if os.path.exists(stage):
                os.unlink(stage)
