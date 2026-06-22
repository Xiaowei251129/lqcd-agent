"""Memory update writer for the deterministic mock graph runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lqcd_agent.graph.approval_packet import parse_human_decision
from lqcd_agent.graph.state import AnalysisState, utc_now


MEMORY_SCHEMA_VERSION = "0.1"
MEMORY_UPDATE_FILENAME = "memory_update.json"


def _base_artifact(state: AnalysisState, *, status: str, summary: str) -> dict[str, Any]:
    return {
        "schema_version": MEMORY_SCHEMA_VERSION,
        "run_id": state["run_id"],
        "case_id": state["case_id"],
        "created_at": utc_now(),
        "producer": "memory_report",
        "status": status,
        "summary": summary,
        "warnings": [],
        "errors": [],
    }


def _human_decision(state: AnalysisState) -> str | None:
    decision_path = state.get("human_decision_path")
    if not decision_path:
        return None
    result = parse_human_decision(
        decision_path,
        run_id=state["run_id"],
        case_id=state["case_id"],
    )
    decision = result.get("decision")
    return decision if isinstance(decision, str) else None


def classify_memory_update(state: AnalysisState) -> dict[str, Any]:
    """Classify the current run without using memory as scientific truth."""

    decision = _human_decision(state)
    risk_level = state["risk_level"]
    recommended_action = state["recommended_action"]

    if decision == "reject_or_hold":
        memory_status = "rejected"
        reason = "A valid human decision rejected or held the result."
    elif decision == "approve_with_conditions":
        memory_status = "accepted"
        reason = "A valid human decision approved reporting with conditions."
    elif (
        risk_level == "low"
        and recommended_action == "accept_mock_result"
        and not state["human_approval_required"]
    ):
        memory_status = "accepted"
        reason = "Low-risk mock result is eligible for accepted memory."
    else:
        memory_status = "pending"
        reason = "Result is not eligible for accepted memory without a low-risk decision or valid human approval."

    return {
        "memory_status": memory_status,
        "accepted_result": memory_status == "accepted",
        "human_decision": decision,
        "classification_reason": reason,
    }


def _existing_update_error(path: Path, state: AnalysisState, payload: dict[str, Any]) -> str | None:
    if not path.exists():
        return None
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return f"Refusing to overwrite unreadable existing memory update: {path}"
    if not isinstance(existing, dict):
        return f"Refusing to overwrite non-object existing memory update: {path}"
    if existing.get("run_id") != state["run_id"] or existing.get("case_id") != state["case_id"]:
        return f"Refusing to overwrite memory update for a different run: {path}"
    if existing.get("memory_status") == "accepted" and existing != payload:
        return "Refusing to overwrite accepted memory without versioning."
    return None


def build_memory_update(state: AnalysisState) -> dict[str, Any]:
    classification = classify_memory_update(state)
    memory_status = classification["memory_status"]
    return {
        **_base_artifact(
            state,
            status=memory_status,
            summary=classification["classification_reason"],
        ),
        **classification,
        "risk_level": state["risk_level"],
        "recommended_action": state["recommended_action"],
        "human_approval_required": state["human_approval_required"],
        "approval_packet_dir": state["approval_packet_dir"],
        "human_decision_path": state["human_decision_path"],
        "source_artifacts": {
            "method_plan_path": state["method_plan_path"],
            "run_result_path": state["run_result_path"],
            "scientific_review_report_path": state["scientific_review_report_path"],
            "decision_log_path": state["decision_log_path"],
        },
    }


def write_memory_update(state: AnalysisState) -> dict[str, Any]:
    output_dir = Path(state["output_dir"])
    path = output_dir / MEMORY_UPDATE_FILENAME
    payload = build_memory_update(state)
    error = _existing_update_error(path, state, payload)
    if error:
        raise FileExistsError(error)

    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"memory_update": payload, "memory_update_path": str(path)}
