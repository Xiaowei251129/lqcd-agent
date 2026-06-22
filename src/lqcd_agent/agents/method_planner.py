"""Deterministic structured-output Method Planner Agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.coder.task_packet import build_coder_task_packet, write_task_packet_yaml


REQUIRED_PLAN_FIELDS = [
    "physics_goal",
    "target_observables",
    "method_steps",
    "required_inputs",
    "required_outputs",
    "implementation_gaps",
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
            "code_needed": False,
            "coder_task_summary": None,
        }

    assert case_config is not None
    assert repo_inventory is not None
    physics_goal = str(case_config.get("physics_goal") or user_goal)
    gaps = _inventory_gaps(repo_inventory)
    code_needed = bool(gaps)
    required_inputs = [
        "case_config",
        "repo_inventory",
        "synthetic matrix-element case metadata",
    ]
    required_outputs = [
        "method_plan.json",
        "run_result.json",
        "analysis_outputs/synthetic_matrix_elements.json",
        "scientific_review_report.json",
        "decision_log.json",
    ]

    return {
        **_base_artifact(
            run_id=run_id,
            case_id=case_id,
            producer="method_planner",
            status="success",
            summary="Created deterministic mock method plan for a pion quasi-DA analysis support run.",
        ),
        "physics_goal": physics_goal,
        "target_observables": [
            "bare_matrix_elements_real_imag_vs_z_and_pz",
            "normalized_matrix_elements_real_imag_vs_z_and_pz",
            "matrix_element_uncertainties",
            "diagnostic_flags",
        ],
        "method_steps": [
            "Confirm the case uses synthetic placeholder inputs and does not require raw numeric data.",
            "Plan deterministic matrix-element generation or validation versus Wilson-line separation z and hadron momentum Pz.",
            "Plan structured review checks for monotonicity, uncertainty sanity, and diagnostic flags.",
            "Route downstream decisions using structured status, code_needed, run_success, and risk fields.",
        ],
        "required_inputs": required_inputs,
        "required_outputs": required_outputs,
        "implementation_gaps": gaps,
        "code_needed": code_needed,
        "coder_task_summary": (
            "Implement or repair missing mock-only workflow support before analysis execution."
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


def run_method_planner(
    *,
    user_goal: str | None,
    case_config: dict[str, Any] | None,
    repo_inventory: dict[str, Any] | None,
    output_dir: str | Path,
    run_id: str = "mock_run",
) -> dict[str, Any]:
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
    coder_task_packet_path = None
    if plan["status"] == "success" and plan["code_needed"]:
        packet = build_coder_task_packet(method_plan=plan, repo_inventory=repo_inventory or {})
        coder_task_packet_path = write_task_packet_yaml(output_dir, packet)

    return {
        "status": plan["status"],
        "method_plan_path": method_plan_path,
        "code_needed": plan["code_needed"],
        "coder_task_packet_path": coder_task_packet_path,
        "method_plan": plan,
    }
