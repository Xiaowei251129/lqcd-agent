"""Deterministic Analysis Engineer Agent for Phase 4."""

from __future__ import annotations

import csv
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from lqcd_agent.analysis_programs.registry import available_programs
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
    commands = _resolve_explicit_commands(case_config)
    return commands or list(DEFAULT_ANALYSIS_COMMANDS)


def _resolve_explicit_commands(case_config: dict[str, Any]) -> list[str]:
    commands = _as_string_list(case_config.get("analysis_commands"))
    if not commands:
        commands = _as_string_list(case_config.get("analysis_command"))
    return commands


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


def _selected_program_configs(task_config: dict[str, Any]) -> list[dict[str, Any]]:
    selected = task_config.get("selected_analysis_programs", [])
    if not isinstance(selected, list):
        return []
    return [program for program in selected if isinstance(program, dict)]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _resolve_raw_data_path(case_config: dict[str, Any], repo_root: Path) -> tuple[Path | None, str | None]:
    raw_value = case_config.get("raw_data_path")
    if not raw_value:
        return None, "case_config.raw_data_path is required for selected analysis programs."
    raw_path = Path(str(raw_value))
    if raw_path.is_absolute():
        return None, "raw_data_path must be relative to the repository root."
    resolved = (repo_root / raw_path).resolve()
    raw_root = (repo_root / "raw_data").resolve()
    if not _is_within(resolved, raw_root):
        return None, "raw_data_path must stay under raw_data/."
    if not resolved.exists() or not resolved.is_file():
        return None, "raw_data_path does not exist or is not a file."
    return resolved, None


def _read_raw_csv_columns(path: Path) -> tuple[dict[str, list[float]] | None, str | None]:
    columns: dict[str, list[float]] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return None, "Raw CSV has no header row."
            for field in reader.fieldnames:
                columns[field] = []
            for row_index, row in enumerate(reader, start=2):
                for field in reader.fieldnames:
                    try:
                        columns[field].append(float(row[field]))
                    except (TypeError, ValueError):
                        return None, f"Raw CSV column {field} has a non-numeric value on row {row_index}."
    except OSError as exc:
        return None, str(exc)
    return columns, None


def _resolve_program_inputs(
    *,
    selected_program: dict[str, Any],
    csv_columns: dict[str, list[float]],
) -> tuple[dict[str, Any] | None, str | None]:
    input_mapping = selected_program.get("input_mapping")
    if not isinstance(input_mapping, dict):
        return None, "selected_analysis_programs[].input_mapping must be an object."

    inputs: dict[str, Any] = {}
    for input_name, source in input_mapping.items():
        source_text = str(source)
        prefix = "raw_data_csv."
        if not source_text.startswith(prefix):
            return None, f"Unsupported input source: {source_text}."
        column_name = source_text[len(prefix):]
        if column_name not in csv_columns:
            return None, f"Raw CSV column is missing: {column_name}."
        inputs[str(input_name)] = csv_columns[column_name]
    return inputs, None


def _safe_analysis_output_path(run_output_dir: Path, relative_path: str) -> tuple[Path | None, str | None]:
    output_path = Path(relative_path)
    if output_path.is_absolute():
        return None, "Analysis program output_path must be relative."
    if any(part in {"raw_data", "accepted_results"} for part in output_path.parts):
        return None, "Analysis program output_path must not target raw_data or accepted_results."
    resolved = (run_output_dir / output_path).resolve()
    if not _is_within(resolved, run_output_dir):
        return None, "Analysis program output_path must stay under the run output directory."
    return resolved, None


def _registered_program_by_name() -> dict[str, Any]:
    return {program.name: program for program in available_programs()}


def _load_registered_callable(selected_program: dict[str, Any]) -> tuple[Any | None, str | None]:
    name = str(selected_program.get("name", ""))
    callable_path = str(selected_program.get("callable_path", ""))
    registered = _registered_program_by_name().get(name)
    if registered is None:
        return None, f"Selected analysis program is not registered: {name}."
    if registered.callable_path != callable_path:
        return None, f"Selected analysis program callable_path does not match registry for {name}."
    module_path, _, function_name = callable_path.rpartition(".")
    if not module_path or not function_name:
        return None, f"Invalid callable_path for selected analysis program: {callable_path}."
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        return None, str(exc)
    function = getattr(module, function_name, None)
    if not callable(function):
        return None, f"Registered callable is not importable: {callable_path}."
    return function, None


def _program_result(
    *,
    command_id: str,
    selected_program: dict[str, Any],
    repo_root: Path,
    timeout_seconds: int,
    started_at: str,
    status: str,
    return_code: int | None,
    stdout: str = "",
    stderr: str = "",
    produced_files: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "command_id": command_id,
        "command": f"analysis_program:{selected_program.get('name', '')}",
        "command_kind": "analysis_program",
        "working_directory": str(repo_root),
        "timeout_seconds": timeout_seconds,
        "started_at": started_at,
        "completed_at": utc_now(),
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
        "produced_files": produced_files or [],
        "status": status,
    }


def _run_selected_analysis_programs(
    *,
    selected_programs: Sequence[dict[str, Any]],
    case_config: dict[str, Any],
    repo_root: Path,
    run_output_dir: Path,
    run_id: str,
    case_id: str,
    timeout_seconds: int,
    force: bool,
) -> list[dict[str, Any]]:
    raw_data_path, raw_error = _resolve_raw_data_path(case_config, repo_root)
    if raw_error or raw_data_path is None:
        return [
            _program_result(
                command_id="analysis_program_0",
                selected_program=selected_programs[0] if selected_programs else {"name": "unknown"},
                repo_root=repo_root,
                timeout_seconds=timeout_seconds,
                started_at=utc_now(),
                status="blocked",
                return_code=None,
                stderr=raw_error or "Invalid raw data path.",
            )
        ]

    csv_columns, csv_error = _read_raw_csv_columns(raw_data_path)
    if csv_error or csv_columns is None:
        return [
            _program_result(
                command_id="analysis_program_0",
                selected_program=selected_programs[0] if selected_programs else {"name": "unknown"},
                repo_root=repo_root,
                timeout_seconds=timeout_seconds,
                started_at=utc_now(),
                status="blocked",
                return_code=None,
                stderr=csv_error or "Raw CSV could not be read.",
            )
        ]

    results: list[dict[str, Any]] = []
    for index, selected_program in enumerate(selected_programs):
        command_id = f"analysis_program_{index}"
        started_at = utc_now()
        function, load_error = _load_registered_callable(selected_program)
        if load_error or function is None:
            results.append(
                _program_result(
                    command_id=command_id,
                    selected_program=selected_program,
                    repo_root=repo_root,
                    timeout_seconds=timeout_seconds,
                    started_at=started_at,
                    status="blocked",
                    return_code=None,
                    stderr=load_error or "Selected analysis program could not be loaded.",
                )
            )
            continue

        output_path, output_error = _safe_analysis_output_path(
            run_output_dir,
            str(selected_program.get("output_path", "")),
        )
        if output_error or output_path is None:
            results.append(
                _program_result(
                    command_id=command_id,
                    selected_program=selected_program,
                    repo_root=repo_root,
                    timeout_seconds=timeout_seconds,
                    started_at=started_at,
                    status="blocked",
                    return_code=None,
                    stderr=output_error or "Invalid analysis program output path.",
                )
            )
            continue
        if output_path.exists() and not force:
            results.append(
                _program_result(
                    command_id=command_id,
                    selected_program=selected_program,
                    repo_root=repo_root,
                    timeout_seconds=timeout_seconds,
                    started_at=started_at,
                    status="blocked",
                    return_code=None,
                    stderr=f"Refusing to overwrite existing analysis program output: {output_path}",
                )
            )
            continue

        inputs, input_error = _resolve_program_inputs(selected_program=selected_program, csv_columns=csv_columns)
        if input_error or inputs is None:
            results.append(
                _program_result(
                    command_id=command_id,
                    selected_program=selected_program,
                    repo_root=repo_root,
                    timeout_seconds=timeout_seconds,
                    started_at=started_at,
                    status="blocked",
                    return_code=None,
                    stderr=input_error or "Could not resolve selected analysis program inputs.",
                )
            )
            continue

        try:
            payload = function(**inputs)
        except Exception as exc:
            results.append(
                _program_result(
                    command_id=command_id,
                    selected_program=selected_program,
                    repo_root=repo_root,
                    timeout_seconds=timeout_seconds,
                    started_at=started_at,
                    status="failed",
                    return_code=1,
                    stderr=str(exc),
                )
            )
            continue
        if not isinstance(payload, dict):
            results.append(
                _program_result(
                    command_id=command_id,
                    selected_program=selected_program,
                    repo_root=repo_root,
                    timeout_seconds=timeout_seconds,
                    started_at=started_at,
                    status="failed",
                    return_code=1,
                    stderr="Selected analysis program did not return a JSON object payload.",
                )
            )
            continue

        payload = {
            "schema_version": "0.1",
            "run_id": run_id,
            "case_id": case_id,
            "created_at": utc_now(),
            "producer": "analysis_engineer",
            "source_kind": "raw_data_csv",
            "raw_data_path": str(raw_data_path.relative_to(repo_root)),
            **payload,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        program_status = "passed" if payload.get("status") == "success" else "failed"
        results.append(
            _program_result(
                command_id=command_id,
                selected_program=selected_program,
                repo_root=repo_root,
                timeout_seconds=timeout_seconds,
                started_at=started_at,
                status=program_status,
                return_code=0 if program_status == "passed" else 1,
                stdout=f"Wrote analysis program output for {selected_program.get('name', '')}.\n",
                stderr="" if program_status == "passed" else "Selected analysis program returned non-success status.",
                produced_files=[str(output_path)],
            )
        )
    return results


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
    explicit_commands = _resolve_explicit_commands(case_config)
    selected_programs = _selected_program_configs(task_config)
    expected_outputs = _resolve_expected_outputs(case_config, task_config)
    repo_path = (Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]).resolve()
    golden_reference_files = _resolve_case_reference_files(case_config, repo_path)

    if explicit_commands:
        allowed_commands = _resolve_allowed_commands(case_config, explicit_commands)
        command_results = run_commands(
            commands=explicit_commands,
            cwd=repo_path,
            output_dir=run_dir,
            run_id=run_id,
            case_id=case_id,
            timeout_seconds=timeout_seconds,
            allowed_commands=allowed_commands,
            force=force,
        )
    elif selected_programs:
        command_results = _run_selected_analysis_programs(
            selected_programs=selected_programs,
            case_config=case_config,
            repo_root=repo_path,
            run_output_dir=run_dir,
            run_id=run_id,
            case_id=case_id,
            timeout_seconds=timeout_seconds,
            force=force,
        )
    else:
        commands = _resolve_commands(case_config)
        allowed_commands = _resolve_allowed_commands(case_config, commands)
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
