"""Provenance manifest helpers for analysis runs."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Sequence


MANIFEST_SCHEMA_VERSION = "0.1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str | None:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    return {
        "path": str(file_path),
        "exists": file_path.exists(),
        "sha256": sha256_file(file_path),
        "bytes": file_path.stat().st_size if file_path.exists() and file_path.is_file() else None,
    }


def _combined_config_hash(paths: Sequence[str | Path]) -> str | None:
    existing_records = [_file_record(path) for path in paths if Path(path).exists()]
    if not existing_records:
        return None
    digest = hashlib.sha256()
    for record in sorted(existing_records, key=lambda item: item["path"]):
        digest.update(str(record["path"]).encode("utf-8"))
        digest.update(str(record["sha256"]).encode("utf-8"))
    return digest.hexdigest()


def _run_git_command(repo_root: Path, args: Sequence[str]) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        return None, completed.stderr.strip() or completed.stdout.strip()
    return completed.stdout.strip(), None


def _git_summary(repo_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    commit, commit_error = _run_git_command(repo_root, ["rev-parse", "HEAD"])
    status_text, status_error = _run_git_command(repo_root, ["status", "--short", "--", "."])

    if commit_error:
        warnings.append({"field": "git.commit", "message": commit_error})
    if status_error:
        warnings.append({"field": "git.status", "message": status_error})

    status_entries = status_text.splitlines() if status_text else []
    return (
        {
            "commit": commit,
            "status_summary": {
                "dirty": bool(status_entries),
                "entry_count": len(status_entries),
                "entries": status_entries[:50],
                "truncated": len(status_entries) > 50,
            },
        },
        warnings,
    )


def _tool_versions() -> dict[str, str | None]:
    try:
        package_version = metadata.version("lqcd-agent")
    except metadata.PackageNotFoundError:
        package_version = None
    return {
        "python": platform.python_version(),
        "lqcd_agent": package_version,
    }


def build_manifest(
    *,
    run_id: str,
    case_id: str,
    repo_root: str | Path,
    run_output_dir: str | Path,
    input_files: Sequence[str | Path],
    output_files: Sequence[str | Path],
    commands: Sequence[dict[str, Any]],
    status: str,
    summary: str,
    data_inputs: Sequence[dict[str, Any]] = (),
    warnings: Sequence[dict[str, Any]] | None = None,
    errors: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo_root).resolve()
    output_path = Path(run_output_dir).resolve()
    created_at = utc_now()
    git, git_warnings = _git_summary(repo_path)
    manifest_warnings = [dict(warning) for warning in (warnings or [])]
    manifest_warnings.extend(git_warnings)

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": created_at,
        "producer": "analysis_engineer",
        "status": status,
        "summary": summary,
        "warnings": manifest_warnings,
        "errors": [dict(error) for error in (errors or [])],
        "git": git,
        "config_hash": _combined_config_hash(input_files),
        "input_files": [_file_record(path) for path in input_files] + [dict(record) for record in data_inputs],
        "output_files": [_file_record(path) for path in output_files],
        "commands": [dict(command) for command in commands],
        "tool_versions": _tool_versions(),
        "environment_summary": {
            "cwd": str(repo_path),
            "run_output_dir": str(output_path),
            "python_executable": sys.executable,
            "platform": platform.platform(),
        },
    }


def write_manifest_json(output_dir: str | Path, payload: dict[str, Any]) -> str:
    path = Path(output_dir) / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return str(path)
