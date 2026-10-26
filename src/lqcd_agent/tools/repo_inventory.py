"""Small repository inventory helper for mock planning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lqcd_agent.analysis_programs import program_inventory


DEFAULT_REQUIRED_FILES = [
    "src/lqcd_agent/graph/nodes.py",
    "src/lqcd_agent/runtime.py",
    "src/lqcd_agent/analysis_programs/registry.py",
    "contracts/control.json",
]

DEFAULT_ALLOWED_FILES = [
    "src/lqcd_agent/analysis_programs/",
    "tests/",
    "contracts/control.json",
    "docs/REPO_CURRENT_STATE.md",
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
        "allowed_files": allowed_files or DEFAULT_ALLOWED_FILES,
        "analysis_programs": program_inventory(),
        "analysis_program_guidance": (
            "Reuse existing analysis_programs entries when possible. Add new reusable programs "
            "under src/lqcd_agent/analysis_programs/ only when no suitable program exists."
        ),
    }
