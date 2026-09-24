"""Standalone committed synthetic bases; never the control repository."""
import os
from pathlib import Path
import subprocess
import tempfile

from lqcd_agent.code_agent.workspace import tree_digest


def immutable_base_repository():
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-base-", dir="/private/tmp"))
    files = {"sample.py": b"value = 1\n"}
    for path, content in files.items():
        (root / path).write_bytes(content)
    def git(*args):
        return subprocess.check_output(["/usr/bin/git", "-C", str(root), *args], stderr=subprocess.DEVNULL,
            env={**os.environ, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00"}).decode().strip()
    git("init", "-q")
    git("add", "sample.py")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
        "-c", "core.hooksPath=/dev/null", "commit", "-qm", "Immutable workspace fixture")
    return root, {"base_revision": git("rev-parse", "HEAD"), "base_tree_digest": tree_digest(files)}
