"""Deterministic Analysis Engineer Agent for Phase 4."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from lqcd_agent.tools.command_runner import run_commands
from lqcd_agent.tools.manifest import build_manifest, write_manifest_json
from lqcd_agent.tools.output_validator import validate_expected_outputs


DEFAULT_ANALYSIS_COMMANDS = ["mock:write_synthetic_matrix_elements"]
DEFAULT_EXPECTED_OUTPUTS = ["analysis_outputs/synthetic_matrix_elements.json"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_artifact(*, run_id: str, case_id: str, status: str, summary: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": utc_now(),
        "producer": "analysis_engineer",
        "status": status,
        "summary": summary,
        "warnings": [],
        "errors": [],
    }


def _parse_scalar(value: str) -> Any:
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def read_case_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if config_path.suffix == ".json":
        return json.loads(config_path.read_text(encoding="utf-8"))

    config: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        stripped = raw_line.strip()
        if stripped.startswith("- ") and current_list_key:
            config.setdefault(current_list_key, [])
            config[current_list_key].append(_parse_scalar(stripped[2:].strip()))
            continue
        if not raw_line.startswith(" ") and ":" in raw_line:
            key, raw_value = raw_line.split(":", 1)
            value = raw_value.strip()
            if value:
                config[key.strip()] = _parse_scalar(value)
                current_list_key = None
            else:
                config[key.strip()] = []
                current_list_key = key.strip()
            continue
    return config


def _read_task_config(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    task_path = Path(path)
    if not task_path.exists():
        return {}
    if task_path.suffix == ".json":
        return json.loads(task_path.read_text(encoding="utf-8"))
    return read_case_config(task_path)


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _resolve_commands(case_config: dict[str, Any]) -> list[str]:
    commands = _as_string_list(case_config.get("analysis_commands"))
    if not commands:
        commands = _as_string_list(case_config.get("analysis_command"))
    return commands or list(DEFAULT_ANALYSIS_COMMANDS)


def _resolve_allowed_commands(case_config: dict[str, Any], commands: Sequence[str]) -> list[str]:
    allowed = _as_string_list(case_config.get("allowed_analysis_commands"))
    if not allowed:
        allowed = _as_string_list(case_config.get("allowed_commands"))
    allowed.extend(command for command in commands if str(command).startswith("mock:"))
    return sorted(set(allowed))


def _resolve_expected_outputs(case_config: dict[str, Any], task_config: dict[str, Any]) -> list[str]:
    expected = _as_string_list(case_config.get("expected_outputs"))
    if not expected:
        expected = _as_string_list(case_config.get("analysis_expected_outputs"))
    if not expected:
        required_outputs = _as_string_list(task_config.get("required_outputs"))
        expected = [output for output in required_outputs if output.startswith("analysis_outputs/")]
    return expected or list(DEFAULT_EXPECTED_OUTPUTS)


def _resolve_case_reference_files(case_config: dict[str, Any], repo_root: Path) -> list[str]:
    reference_files = _as_string_list(case_config.get("golden_reference_files"))
    if not reference_files:
        return []

    root_value = case_config.get("golden_example_root")
    reference_root = (repo_root / str(root_value)).resolve() if root_value else repo_root
    resolved: list[str] = []
    for reference_file in reference_files:
        path = Path(reference_file)
        if path.is_absolute():
            resolved.append(str(path))
        else:
            resolved.append(str((reference_root / path).resolve()))
    return resolved


def _resolve_run_output_dir(
    *, output_root: str | Path | None, run_output_dir: str | Path | None, case_id: str, run_id: str
) -> Path:
    if output_root is not None:
        return Path(output_root) / case_id / run_id
    if run_output_dir is not None:
        return Path(run_output_dir)
    raise ValueError("Either output_root or run_output_dir is required.")


def _canonical_path_error(path: Path, *, case_id: str, run_id: str) -> str | None:
    parts = path.resolve().parts
    if len(parts) < 2 or parts[-2:] != (case_id, run_id):
        return "Run output directory must use <output_root>/<case_id>/<run_id>/."
    return None


def _existing_artifact_error(run_output_dir: Path, *, force: bool) -> str | None:
    if force:
        return None
    protected_paths = [
        run_output_dir / "run_result.json",
        run_output_dir / "manifest.json",
        run_output_dir / "run.log",
    ]
    existing = [str(path) for path in protected_paths if path.exists()]
    if existing:
        return "Refusing to overwrite existing run artifacts without force: " + ", ".join(existing)
    return None


def _command_errors(command_results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "field": "analysis_commands",
            "message": result["stderr"] or f"{result['command']} did not pass.",
            "command_id": result["command_id"],
            "command": result["command"],
            "status": result["status"],
            "return_code": result["return_code"],
        }
        for result in command_results
        if result["status"] != "passed"
    ]


def _classify_failure(
    *, command_results: Sequence[dict[str, Any]], validation_results: dict[str, Any]
) -> str | None:
    if all(result["status"] == "passed" for result in command_results) and validation_results["status"] == "success":
        return None
    if any(result["status"] in {"failed", "timeout"} for result in command_results):
        return "code"
    return "config_or_data"


def _write_run_log(
    *,
    path: Path,
    run_id: str,
    case_id: str,
    commands: Sequence[dict[str, Any]],
    validation_results: dict[str, Any],
    run_success: bool,
    force: bool,
) -> str:
    if path.exists() and not force:
        raise FileExistsError("Refusing to overwrite run.log without force.")
    lines = [
        f"created_at={utc_now()}",
        f"run_id={run_id}",
        f"case_id={case_id}",
        f"run_success={run_success}",
    ]
    for command in commands:
        lines.append(
            "command="
            + json.dumps(
                {
                    "command_id": command["command_id"],
                    "command": command["command"],
                    "status": command["status"],
                    "return_code": command["return_code"],
                    "stderr": command["stderr"],
                },
                sort_keys=True,
            )
        )
    lines.append("validation=" + json.dumps(validation_results, sort_keys=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _write_run_result(output_dir: Path, payload: dict[str, Any], *, force: bool) -> str:
    path = output_dir / "run_result.json"
    if path.exists() and not force:
        raise FileExistsError("Refusing to overwrite run_result.json without force.")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def run_analysis_engineer(
    *,
    case_config_path: str | Path,
    case_id: str,
    run_id: str,
    output_root: str | Path | None = None,
    run_output_dir: str | Path | None = None,
    method_plan_path: str | Path | None = None,
    repo_root: str | Path | None = None,
    timeout_seconds: int = 60,
    force: bool = False,
) -> dict[str, Any]:
    run_dir = _resolve_run_output_dir(
        output_root=output_root,
        run_output_dir=run_output_dir,
        case_id=case_id,
        run_id=run_id,
    ).resolve()
    canonical_error = _canonical_path_error(run_dir, case_id=case_id, run_id=run_id)
    if canonical_error:
        return {
            "run_success": False,
            "failure_type": "workflow",
            "run_result_path": None,
            "manifest_path": None,
            "analysis_outputs_dir": None,
            "warnings": [],
            "errors": [{"field": "output_dir", "message": canonical_error, "path": str(run_dir)}],
            "run_result": None,
            "manifest": None,
        }

    existing_error = _existing_artifact_error(run_dir, force=force)
    if existing_error:
        return {
            "run_success": False,
            "failure_type": "workflow",
            "run_result_path": None,
            "manifest_path": None,
            "analysis_outputs_dir": None,
            "warnings": [],
            "errors": [{"field": "output_dir", "message": existing_error, "path": str(run_dir)}],
            "run_result": None,
            "manifest": None,
        }

    run_dir.mkdir(parents=True, exist_ok=True)
    case_config = read_case_config(case_config_path)
    task_config = _read_task_config(method_plan_path)
    commands = _resolve_commands(case_config)
    allowed_commands = _resolve_allowed_commands(case_config, commands)
    expected_outputs = _resolve_expected_outputs(case_config, task_config)
    repo_path = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
    golden_reference_files = _resolve_case_reference_files(case_config, repo_path)

    command_results = run_commands(
        commands=commands,
        cwd=repo_path,
        output_dir=run_dir,
        run_id=run_id,
        case_id=case_id,
        timeout_seconds=timeout_seconds,
        allowed_commands=allowed_commands,
        force=force,
    )
    validation_results = validate_expected_outputs(
        output_dir=run_dir,
        expected_outputs=expected_outputs,
        run_id=run_id,
        case_id=case_id,
    )
    failure_type = _classify_failure(
        command_results=command_results,
        validation_results=validation_results,
    )
    run_success = failure_type is None
    status = "success" if run_success else "failed"
    command_errors = _command_errors(command_results)
    errors = command_errors + validation_results["errors"]
    warnings = validation_results["warnings"]
    produced_outputs = sorted(
        {
            output
            for result in command_results
            for output in result.get("produced_files", [])
        }
        | set(validation_results["validated_outputs"])
    )

    run_log_path = run_dir / "run.log"
    run_result_path = run_dir / "run_result.json"
    manifest_path = run_dir / "manifest.json"
    summary = (
        "Analysis Engineer completed the mock analysis run."
        if run_success
        else "Analysis Engineer recorded a failed mock analysis run."
    )
    run_log_written_path = _write_run_log(
        path=run_log_path,
        run_id=run_id,
        case_id=case_id,
        commands=command_results,
        validation_results=validation_results,
        run_success=run_success,
        force=force,
    )
    run_result = {
        **_base_artifact(run_id=run_id, case_id=case_id, status=status, summary=summary),
        "warnings": warnings,
        "errors": errors,
        "run_success": run_success,
        "failure_type": failure_type,
        "analysis_outputs_dir": str(run_dir / "analysis_outputs"),
        "expected_outputs": expected_outputs,
        "produced_outputs": produced_outputs,
        "validation_results": validation_results,
        "command_references": [
            {
                "command_id": result["command_id"],
                "command": result["command"],
                "status": result["status"],
                "return_code": result["return_code"],
            }
            for result in command_results
        ],
        "commands": command_results,
        "run_log_path": run_log_written_path,
        "manifest_path": str(manifest_path),
        "golden_reference_files": golden_reference_files,
    }
    run_result_written_path = _write_run_result(run_dir, run_result, force=force)
    input_files = [str(case_config_path), *golden_reference_files]
    if method_plan_path:
        input_files.append(str(method_plan_path))
    manifest = build_manifest(
        run_id=run_id,
        case_id=case_id,
        repo_root=repo_path,
        run_output_dir=run_dir,
        input_files=input_files,
        output_files=[*produced_outputs, run_log_written_path, run_result_written_path],
        commands=command_results,
        status=status,
        summary=summary,
        warnings=warnings,
        errors=errors,
    )
    manifest_written_path = write_manifest_json(run_dir, manifest, force=force)

    return {
        "run_success": run_success,
        "failure_type": failure_type,
        "run_result_path": run_result_written_path,
        "manifest_path": manifest_written_path,
        "analysis_outputs_dir": str(run_dir / "analysis_outputs"),
        "warnings": warnings,
        "errors": errors,
        "run_result": run_result,
        "manifest": manifest,
    }
