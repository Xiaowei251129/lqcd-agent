"""Deterministic structured-output Method Planner Agent."""

from __future__ import annotations

from lqcd_agent.analysis_programs.registry import canonical_program_selection, requested_programs, selected_analysis_programs

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.llm.base import LLMProvider
from lqcd_agent.llm.prompts import build_method_planner_request
from lqcd_agent.llm.provider_factory import create_provider_from_config_path
from lqcd_agent.llm.schemas import validate_method_plan_payload
from lqcd_agent.llm.structured_output import (
    parse_json_object,
    provider_exception_artifact,
    validation_error_artifact,
)
from lqcd_agent.llm.trace import write_llm_call_trace


REQUIRED_PLAN_FIELDS = [
    "physics_goal",
    "target_observables",
    "method_steps",
    "required_inputs",
    "required_outputs",
    "implementation_gaps",
    "selected_analysis_programs",
    "code_needed",
    "coder_task_summary",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_artifact(
    *,
    run_id: str,
    case_id: str,
    producer: str,
    status: str,
    summary: str,
    warnings: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": utc_now(),
        "producer": producer,
        "status": status,
        "summary": summary,
        "warnings": warnings or [],
        "errors": errors or [],
    }


def _missing_inputs(
    *,
    user_goal: str | None,
    case_config: dict[str, Any] | None,
    repo_inventory: dict[str, Any] | None,
) -> list[str]:
    missing: list[str] = []
    if not user_goal or not user_goal.strip():
        missing.append("user_goal")
    if not case_config:
        missing.append("case_config")
    if not repo_inventory:
        missing.append("repo_inventory")
    if case_config and not case_config.get("case_id"):
        missing.append("case_config.case_id")
    return missing


def _inventory_gaps(repo_inventory: dict[str, Any]) -> list[str]:
    gaps = repo_inventory.get("implementation_gaps", [])
    if isinstance(gaps, list) and gaps:
        return [str(gap) for gap in gaps]

    missing_files = repo_inventory.get("missing_files", [])
    if isinstance(missing_files, list):
        return [f"Missing required file: {path}" for path in missing_files]
    return []


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _program_inventory(repo_inventory: dict[str, Any]) -> list[dict[str, Any]]:
    programs = repo_inventory.get("analysis_programs", [])
    if not isinstance(programs, list):
        return []
    return [program for program in programs if isinstance(program, dict)]


def _raw_data_missing(case_config: dict[str, Any], repo_inventory: dict[str, Any] | None) -> bool:
    raw_value = case_config.get("raw_data_path")
    repo_root = (repo_inventory or {}).get("repo_root")
    if not raw_value or not repo_root:
        return False
    raw_path = Path(str(raw_value))
    if raw_path.is_absolute():
        return False
    resolved = (Path(str(repo_root)) / raw_path).resolve()
    return not resolved.is_file()


def _runtime_input_warning(case_config: dict[str, Any]) -> dict[str, Any]:
    raw_value = str(case_config.get("raw_data_path", ""))
    return {
        "code": "runtime_input_validation_deferred_to_analysis_engineer",
        "message": "Raw data availability is a runtime input check and will be validated by Analysis Engineer.",
        "field": "raw_data_path",
        "path": raw_value,
        "value": raw_value,
    }


def _matching_inventory_program(
    selected_program: dict[str, Any],
    repo_inventory: dict[str, Any],
) -> dict[str, Any] | None:
    selected_name = str(selected_program.get("name", ""))
    selected_callable = str(selected_program.get("callable_path", ""))
    for program in _program_inventory(repo_inventory):
        program_name = str(program.get("name", ""))
        program_callable = str(program.get("callable_path", ""))
        if selected_name and selected_name == program_name:
            return program
        if selected_callable and selected_callable == program_callable:
            return program
    return None


def _append_warning(payload: dict[str, Any], warning: dict[str, Any]) -> None:
    warnings = payload.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
    warnings.append(warning)
    payload["warnings"] = warnings


def _changed_program_fields(original: dict[str, Any], normalized: dict[str, Any]) -> list[str]:
    fields = sorted(set(original) | set(normalized))
    return [field for field in fields if original.get(field) != normalized.get(field)]


def _normalize_provider_selected_programs(
    *,
    payload: dict[str, Any],
    case_config: dict[str, Any] | None,
    repo_inventory: dict[str, Any] | None,
) -> dict[str, Any]:
    if case_config is None or repo_inventory is None:
        return payload

    normalized = dict(payload)
    selected = normalized.get("selected_analysis_programs", [])
    if not isinstance(selected, list):
        return normalized

    canonical_selected: list[dict[str, Any]] = []
    changed_programs: list[str] = []
    changed_fields: list[dict[str, Any]] = []
    for item in selected:
        if not isinstance(item, dict):
            continue
        program = _matching_inventory_program(item, repo_inventory)
        if program is None:
            canonical_selected.append(item)
            continue
        canonical = canonical_program_selection(program, case_config, repo_inventory)
        if canonical is None:
            canonical_selected.append(item)
            continue
        if item != canonical:
            changed_programs.append(str(canonical["name"]))
            changed_fields.append(
                {
                    "name": str(canonical["name"]),
                    "changed_fields": _changed_program_fields(item, canonical),
                }
            )
        canonical_selected.append(canonical)

    if not canonical_selected:
        inferred = selected_analysis_programs(case_config=case_config, repo_inventory=repo_inventory)
        if inferred:
            canonical_selected = inferred
            changed_programs.extend(str(program["name"]) for program in inferred)
            changed_fields.extend(
                {
                    "name": str(program["name"]),
                    "changed_fields": ["selected_analysis_programs"],
                }
                for program in inferred
            )

    if canonical_selected != selected:
        normalized["selected_analysis_programs"] = canonical_selected
        _append_warning(
            normalized,
            {
                "code": "selected_analysis_programs_normalized",
                "severity": "info",
                "decision_coordinator_flag": False,
                "message": (
                    "Provider selected registered analysis program(s), and the runtime normalized "
                    "their executable input mappings from repo inventory."
                ),
                "programs": sorted(set(changed_programs)),
                "changed_fields": changed_fields,
                "original_selected_analysis_programs": selected,
                "normalized_selected_analysis_programs": canonical_selected,
            },
        )
    return normalized


def build_method_plan(
    *,
    user_goal: str | None,
    case_config: dict[str, Any] | None,
    repo_inventory: dict[str, Any] | None,
    run_id: str = "mock_run",
) -> dict[str, Any]:
    """Build a deterministic method plan without calling a real LLM."""

    case_id = str((case_config or {}).get("case_id", "unknown_case"))
    missing = _missing_inputs(
        user_goal=user_goal,
        case_config=case_config,
        repo_inventory=repo_inventory,
    )
    if missing:
        return {
            **_base_artifact(
                run_id=run_id,
                case_id=case_id,
                producer="method_planner",
                status="needs_more_info",
                summary="Missing critical inputs for method planning.",
                errors=[{"field": field, "message": "Required input is missing."} for field in missing],
            ),
            "physics_goal": user_goal or "",
            "target_observables": [],
            "method_steps": [],
            "required_inputs": [],
            "required_outputs": [],
            "implementation_gaps": [],
            "selected_analysis_programs": [],
            "code_needed": False,
            "coder_task_summary": None,
        }

    assert case_config is not None
    assert repo_inventory is not None
    physics_goal = str(case_config.get("physics_goal") or user_goal)
    gaps = _inventory_gaps(repo_inventory)
    selected_programs = selected_analysis_programs(case_config=case_config, repo_inventory=repo_inventory)
    program_requested = bool(case_config.get("raw_data_path")) and bool(
        any(requested_programs(case_config))
    )
    missing_requested_program = program_requested and not selected_programs
    code_needed = bool(gaps) or missing_requested_program
    warnings: list[dict[str, Any]] = []
    if selected_programs and _raw_data_missing(case_config, repo_inventory):
        warnings.append(_runtime_input_warning(case_config))
    required_inputs = [
        "case_config",
        "repo_inventory",
        "raw data" if selected_programs else "synthetic matrix-element case metadata",
    ]
    required_outputs = ["method_plan.json", "run_result.json"]
    if selected_programs:
        required_outputs.extend(str(program["output_path"]) for program in selected_programs)
    else:
        required_outputs.append("analysis_outputs/synthetic_matrix_elements.json")
    required_outputs.extend(["scientific_review_report.json", "decision_log.json"])

    return {
        **_base_artifact(
            run_id=run_id,
            case_id=case_id,
            producer="method_planner",
            status="success",
            summary=(
                "Selected registered analysis program(s) for deterministic mock planning."
                if selected_programs
                else "Created deterministic mock method plan for a pion quasi-DA analysis support run."
            ),
            warnings=warnings,
        ),
        "physics_goal": physics_goal,
        "target_observables": (
            _as_string_list(case_config.get("target_observables"))
            or [
                "bare_matrix_elements_real_imag_vs_z_and_pz",
                "normalized_matrix_elements_real_imag_vs_z_and_pz",
                "matrix_element_uncertainties",
                "diagnostic_flags",
            ]
        ),
        "method_steps": (
            [
                "Inspect repository inventory for reusable registered analysis programs.",
                "Select registered programs whose tags and produced outputs satisfy the case request.",
                "Map raw CSV columns to the selected program inputs before execution.",
                "Validate generated analysis outputs before downstream scientific review.",
            ]
            if selected_programs
            else [
                "Confirm the case uses synthetic placeholder inputs and does not require raw numeric data.",
                "Plan deterministic matrix-element generation or validation versus Wilson-line separation z and hadron momentum Pz.",
                "Plan structured review checks for monotonicity, uncertainty sanity, and diagnostic flags.",
                "Route downstream decisions using structured status, code_needed, run_success, and risk fields.",
            ]
        ),
        "required_inputs": required_inputs,
        "required_outputs": required_outputs,
        "implementation_gaps": gaps,
        "selected_analysis_programs": selected_programs,
        "code_needed": code_needed,
        "coder_task_summary": (
            "Implement a reusable registered analysis program for the requested raw-data analysis."
            if missing_requested_program
            else "Implement or repair missing mock-only workflow support before analysis execution."
            if code_needed
            else None
        ),
    }


def validate_method_plan(plan: dict[str, Any]) -> list[str]:
    missing = [field for field in REQUIRED_PLAN_FIELDS if field not in plan]
    if plan.get("status") == "success" and not isinstance(plan.get("code_needed"), bool):
        missing.append("code_needed must be boolean")
    return missing


def write_method_plan(output_dir: str | Path, plan: dict[str, Any]) -> str:
    path = Path(output_dir) / "method_plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _provider_failure_plan(
    *,
    run_id: str,
    case_id: str,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    return {
        **artifact,
        "run_id": run_id,
        "case_id": case_id,
        "physics_goal": "",
        "target_observables": [],
        "method_steps": [],
        "required_inputs": [],
        "required_outputs": [],
        "implementation_gaps": [],
        "selected_analysis_programs": [],
        "code_needed": False,
        "coder_task_summary": None,
    }


def _normalize_provider_method_plan(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if (
        normalized.get("status") in {"pending", "needs_more_info"}
        and not normalized.get("errors")
        and isinstance(normalized.get("code_needed"), bool)
        and all(field in normalized for field in REQUIRED_PLAN_FIELDS)
    ):
        warnings = normalized.get("warnings", [])
        if not isinstance(warnings, list):
            warnings = []
        warnings.append(
            {
                "code": "provider_status_normalized",
                "message": "Provider returned a complete executable plan with a non-terminal status; normalized to success.",
                "original_status": normalized.get("status"),
            }
        )
        normalized["warnings"] = warnings
        normalized["status"] = "success"
    return normalized


def _provider_errors_are_only_missing_raw_data(payload: dict[str, Any], case_config: dict[str, Any]) -> bool:
    errors = payload.get("errors", [])
    if not isinstance(errors, list):
        return False
    if not errors:
        return True
    raw_value = str(case_config.get("raw_data_path", "")).lower()
    for error in errors:
        if not isinstance(error, dict):
            return False
        text = " ".join(
            str(error.get(field, ""))
            for field in ["field", "path", "value", "message", "code", "artifact"]
            if error.get(field) is not None
        ).lower()
        if "raw_data_path" not in text and raw_value not in text:
            return False
        if "missing" not in text and "absent" not in text and "not exist" not in text and "unavailable" not in text:
            return False
    return True


def _normalize_provider_deferred_runtime_inputs(
    *,
    payload: dict[str, Any],
    case_config: dict[str, Any] | None,
    repo_inventory: dict[str, Any] | None,
) -> dict[str, Any]:
    if case_config is None or repo_inventory is None:
        return payload
    selected = payload.get("selected_analysis_programs", [])
    if not selected or not isinstance(selected, list):
        return payload
    if not _raw_data_missing(case_config, repo_inventory):
        return payload
    if not _provider_errors_are_only_missing_raw_data(payload, case_config):
        return payload
    implementation_gaps = payload.get("implementation_gaps", [])
    if isinstance(implementation_gaps, list) and implementation_gaps:
        return payload

    normalized = dict(payload)
    original_errors = normalized.get("errors", [])
    original_status = normalized.get("status")
    original_code_needed = normalized.get("code_needed")
    if original_status in {"pending", "needs_more_info"}:
        normalized["status"] = "success"
    normalized["errors"] = []
    normalized["code_needed"] = False
    normalized["coder_task_summary"] = None
    _append_warning(
        normalized,
        {
            **_runtime_input_warning(case_config),
            "original_status": original_status,
            "original_code_needed": original_code_needed,
            "original_errors": original_errors if isinstance(original_errors, list) else [],
        },
    )
    return normalized


def _run_provider_method_planner(
    *,
    user_goal: str | None,
    case_config: dict[str, Any] | None,
    repo_inventory: dict[str, Any] | None,
    output_dir: str | Path,
    run_id: str,
    provider: LLMProvider,
) -> dict[str, Any]:
    case_id = str((case_config or {}).get("case_id", "unknown_case"))
    request = None
    try:
        request = build_method_planner_request(
            run_id=run_id,
            case_id=case_id,
            user_goal=user_goal,
            case_config=case_config,
            repo_inventory=repo_inventory,
        )
        response = provider.generate(request)
    except Exception as exc:
        plan = _provider_failure_plan(
            run_id=run_id,
            case_id=case_id,
            artifact=provider_exception_artifact(
                producer="method_planner",
                run_id=run_id,
                case_id=case_id,
                code=getattr(exc, "code", "provider_call_failed"),
                message=str(exc),
            ),
        )
        method_plan_path = write_method_plan(output_dir, plan)
        write_llm_call_trace(
            output_dir=output_dir,
            agent="method_planner",
            provider=provider,
            request=request,
            parsed_payload_path=method_plan_path,
            status="failed",
            error=plan,
        )
        return {
            "status": "failed",
            "method_plan_path": method_plan_path,
            "code_needed": False,
            "code_request": None,
            "method_plan": plan,
        }

    payload, parse_error = parse_json_object(
        response.content,
        producer="method_planner",
        run_id=run_id,
        case_id=case_id,
    )
    if parse_error is not None:
        plan = _provider_failure_plan(run_id=run_id, case_id=case_id, artifact=parse_error)
        method_plan_path = write_method_plan(output_dir, plan)
        write_llm_call_trace(
            output_dir=output_dir,
            agent="method_planner",
            provider=provider,
            request=request,
            response=response,
            parsed_payload_path=method_plan_path,
            status="failed",
            error=parse_error,
        )
        return {
            "status": "failed",
            "method_plan_path": method_plan_path,
            "code_needed": False,
            "code_request": None,
            "method_plan": plan,
        }

    assert payload is not None
    payload = _normalize_provider_method_plan(payload)
    payload = _normalize_provider_selected_programs(
        payload=payload,
        case_config=case_config,
        repo_inventory=repo_inventory,
    )
    payload = _normalize_provider_deferred_runtime_inputs(
        payload=payload,
        case_config=case_config,
        repo_inventory=repo_inventory,
    )
    validation_errors = validate_method_plan_payload(payload, run_id=run_id, case_id=case_id)
    if validation_errors:
        plan = _provider_failure_plan(
            run_id=run_id,
            case_id=case_id,
            artifact=validation_error_artifact(
                producer="method_planner",
                run_id=run_id,
                case_id=case_id,
                errors=validation_errors,
            ),
        )
        method_plan_path = write_method_plan(output_dir, plan)
        write_llm_call_trace(
            output_dir=output_dir,
            agent="method_planner",
            provider=provider,
            request=request,
            response=response,
            parsed_payload_path=method_plan_path,
            status="failed",
            error=plan,
        )
        return {
            "status": "failed",
            "method_plan_path": method_plan_path,
            "code_needed": False,
            "code_request": None,
            "method_plan": plan,
        }

    method_plan_path = write_method_plan(output_dir, payload)
    write_llm_call_trace(
        output_dir=output_dir,
        agent="method_planner",
        provider=provider,
        request=request,
        response=response,
        parsed_payload_path=method_plan_path,
        status=payload["status"],
    )
    code_request = None
    if payload["status"] == "success" and payload["code_needed"]:
        code_request = {"summary": payload["coder_task_summary"], "requirements": payload["method_steps"],
                        "proposed_paths": (repo_inventory or {}).get("allowed_files", [])}
    return {
        "status": payload["status"],
        "method_plan_path": method_plan_path,
        "code_needed": payload["code_needed"],
        "code_request": code_request,
        "method_plan": payload,
    }


def run_method_planner(
    *,
    user_goal: str | None,
    case_config: dict[str, Any] | None,
    repo_inventory: dict[str, Any] | None,
    output_dir: str | Path,
    run_id: str = "mock_run",
    provider: LLMProvider | None = None,
    provider_config_path: str | Path | None = None,
) -> dict[str, Any]:
    if provider is None and provider_config_path is not None:
        provider = create_provider_from_config_path(provider_config_path)
    if provider is not None:
        return _run_provider_method_planner(
            user_goal=user_goal,
            case_config=case_config,
            repo_inventory=repo_inventory,
            output_dir=output_dir,
            run_id=run_id,
            provider=provider,
        )

    plan = build_method_plan(
        user_goal=user_goal,
        case_config=case_config,
        repo_inventory=repo_inventory,
        run_id=run_id,
    )
    validation_errors = validate_method_plan(plan)
    if validation_errors:
        plan["status"] = "failed"
        plan["errors"].extend(
            {"field": "method_plan", "message": error} for error in validation_errors
        )

    method_plan_path = write_method_plan(output_dir, plan)
    code_request = None
    if plan["status"] == "success" and plan["code_needed"]:
        code_request = {"summary": plan["coder_task_summary"], "requirements": plan["method_steps"],
                        "proposed_paths": (repo_inventory or {}).get("allowed_files", [])}

    return {
        "status": plan["status"],
        "method_plan_path": method_plan_path,
        "code_needed": plan["code_needed"],
        "code_request": code_request,
        "method_plan": plan,
    }
