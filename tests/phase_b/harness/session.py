"""Fresh local sessions bind evidence to the actual checked worktree."""
import os
import secrets
import stat
from pathlib import Path

from .contracts import DIGEST_KEYS
from .strict_json import canonical, digest, keys, require, sha, text

INPUT_ROOTS = ("src", "tests", "scripts", "configs", "evaluation", "docs")
MANIFESTS = ("AGENTS.md", "README.md", "pyproject.toml", "uv.lock", "requirements.txt", ".gitignore")
IGNORED = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"}


def worktree_digest(root):
    root = Path(root).resolve()
    paths = [root / name for name in MANIFESTS if (root / name).exists()]
    for name in INPUT_ROOTS:
        directory = root / name
        if not directory.exists():
            continue
        for current, dirs, files in os.walk(directory, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED)
            for d in dirs:
                require(not (Path(current) / d).is_symlink(), "worktree", "directory_symlink")
            paths.extend(Path(current) / f for f in files if f not in IGNORED and not f.endswith((".pyc", ".pyo")))
    rows = []
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        require(not path.is_symlink() and path.is_file(), "worktree", relative)
        require(not any(part.startswith(".env") or part.lower() in {"secrets", "raw_data", "outputs"}
                        for part in path.relative_to(root).parts), "worktree", "excluded_input")
        rows.append({"path": relative, "type": "file", "mode": stat.S_IMODE(path.stat().st_mode),
                     "sha256": sha(path.read_bytes())})
    return digest(rows)


def validate_digests(value, *, nullable=False):
    keys(value, DIGEST_KEYS, "digests")
    for name, item in value.items():
        require((nullable and item is None) or (type(item) is str and len(item) == 64
                and all(c in "0123456789abcdef" for c in item)), "digests", name)


class Session:
    def __init__(self, root, evidence_dir, digests):
        self.root = Path(root).resolve()
        self.directory = Path(evidence_dir).resolve()
        require(not self.directory.exists(), "session", "fresh_evidence_dir")
        require(not self.directory.is_relative_to(self.root), "session", "evidence_outside_inputs")
        self.directory.mkdir(parents=True)
        self.token = secrets.token_hex(32)
        self.digests = dict(digests, worktree_inputs=worktree_digest(self.root))
        validate_digests(self.digests)

    def unchanged(self):
        require(worktree_digest(self.root) == self.digests["worktree_inputs"],
                "session", "worktree_inputs", "invalid_evidence")

    def verify_binding(self, value):
        require(value["invocation_token"] == self.token, "evidence", "invocation_token", "invalid_evidence")
        validate_digests(value["digests"])
        require(value["digests"] == self.digests, "evidence", "digests", "invalid_evidence")
