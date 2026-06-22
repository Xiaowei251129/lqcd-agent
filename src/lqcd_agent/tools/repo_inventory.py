"""Small repository inventory helper for mock planning."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_FILES = [
    "src/lqcd_agent/graph/nodes.py",
    "src/lqcd_agent/graph/run_graph.py",
    "docs/ARTIFACT_CONTRACTS.md",
]


def build_repo_inventory(
    root: str | Path,
    *,
    required_files: list[str] | None = None,
    allowed_files: list[str] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    required = required_files or DEFAULT_REQUIRED_FILES
    missing_files = [path for path in required if not (repo_root / path).exists()]
    return {
        "schema_version": "0.1",
        "repo_root": str(repo_root),
        "required_files": required,
        "missing_files": missing_files,
        "implementation_gaps": [f"Missing required file: {path}" for path in missing_files],
        "allowed_files": allowed_files or [],
    }
