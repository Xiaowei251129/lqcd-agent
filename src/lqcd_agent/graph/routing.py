"""Structured routing functions for the mock runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lqcd_agent.graph.approval_packet import parse_human_decision
from lqcd_agent.graph.state import AnalysisState, record_route_decision, save_graph_state


def _structured_tests_status(state: AnalysisState) -> str | None:
    path = state.get("tests_status_path")
    if not path or not Path(path).exists():
        return None
    try:
        payload: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    status = payload.get("status")
    return status if isinstance(status, str) else None


def route_after_method_planner(state: AnalysisState) -> str:
    if state["status"] in {"pending", "halted"}:
        route = "end"
        reason = "method planner reached a safe terminal status before analysis."
    elif state["code_needed"]:
        route = "codex_handoff"
        reason = "code_needed is true and a file-based Codex Handoff is required."
    else:
        route = "analysis_engineer"
        reason = "code_needed is false."
    record_route_decision(
        state,
        source="method_planner",
        route=route,
        reason=reason,
        fields={
            "status": state["status"],
            "code_needed": state["code_needed"],
            "coder_task_packet_path": state["coder_task_packet_path"],
            "error_count": len(state["errors"]),
            "retry_count": state["retry_count"],
            "max_retry": state["max_retry"],
        },
    )
    save_graph_state(state)
    return route


def route_after_analysis_engineer(state: AnalysisState) -> str:
    if state["run_success"]:
        route = "scientific_reviewer"
        reason = "run_success is true."
    elif state["failure_type"] == "code" and state["retry_count"] < state["max_retry"]:
        state["retry_count"] += 1
        state["code_fix_requested"] = True
        route = "codex_handoff"
        reason = "code failure has retry budget and requires Codex Handoff."
    else:
        route = "decision_coordinator"
        reason = "analysis failed without a mock retry route."
    record_route_decision(
        state,
        source="analysis_engineer",
        route=route,
        reason=reason,
        fields={"run_success": state["run_success"], "failure_type": state["failure_type"], "retry_count": state["retry_count"]},
    )
    save_graph_state(state)
    return route


def route_after_codex_handoff(state: AnalysisState) -> str:
    tests_status = _structured_tests_status(state)
    summary_path = state["code_change_summary_path"]
    has_summary = bool(summary_path and Path(summary_path).exists())
    if state["status"] == "halted":
        route = "end"
        reason = "Codex Handoff halted before analysis could continue."
    elif tests_status == "tests_passed" and has_summary:
        route = "analysis_engineer"
        reason = "structured tests_status.json reports tests_passed."
    else:
        route = "end"
        if tests_status == "tests_failed":
            reason = "structured tests_status.json reports tests_failed."
        else:
            reason = "Codex Handoff is pending external result files."
    record_route_decision(
        state,
        source="codex_handoff",
        route=route,
        reason=reason,
        fields={
            "status": state["status"],
            "tests_status": tests_status,
            "coder_task_packet_path": state["coder_task_packet_path"],
            "code_change_summary_path": state["code_change_summary_path"],
            "tests_status_path": state["tests_status_path"],
            "retry_count": state["retry_count"],
            "max_retry": state["max_retry"],
        },
    )
    save_graph_state(state)
    return route


def route_after_decision_coordinator(state: AnalysisState) -> str:
    if state["human_approval_required"]:
        route = "human_approval_gate"
        reason = "high or critical risk requires Human Approval Gate before reporting."
    else:
        route = "memory_report"
        reason = "approval is not required for this risk level."
    if state["code_fix_requested"]:
        proposed_follow_up_route = "codex_handoff"
    elif state["rerun_requested"]:
        proposed_follow_up_route = "analysis_engineer"
    else:
        proposed_follow_up_route = "memory_report"
    record_route_decision(
        state,
        source="decision_coordinator",
        route=route,
        reason=reason,
        fields={
            "risk_level": state["risk_level"],
            "human_approval_required": state["human_approval_required"],
            "recommended_action": state["recommended_action"],
            "decision_log_path": state["decision_log_path"],
            "actual_route": route,
            "requested_route": route,
            "proposed_follow_up_route": proposed_follow_up_route,
            "rerun_requested": state["rerun_requested"],
            "rerun_target": state["rerun_target"],
            "code_fix_requested": state["code_fix_requested"],
        },
    )
    save_graph_state(state)
    return route


def route_after_human_approval_gate(state: AnalysisState) -> str:
    decision = None
    decision_status = None
    decision_path = state.get("human_decision_path")
    if decision_path:
        decision_result = parse_human_decision(
            decision_path,
            run_id=state["run_id"],
            case_id=state["case_id"],
        )
        decision = decision_result.get("decision")
        decision_status = decision_result.get("status")

    if state["status"] == "pending" and decision_status == "pending" and not state["rerun_requested"]:
        route = "memory_report"
        proposed_follow_up_route = "human_approval_gate"
        reason = "Human Approval Gate is waiting for a valid human decision; write pending report artifacts."
    elif state["status"] in {"pending", "halted"}:
        route = "end"
        if state["rerun_requested"]:
            proposed_follow_up_route = state["rerun_target"] or "analysis_engineer"
            reason = "human approved rerun intent; Phase 7 stops before rerun output management."
        else:
            proposed_follow_up_route = "human_approval_gate"
            reason = "Human Approval Gate is waiting for a valid human decision."
    elif state["code_fix_requested"]:
        route = "codex_handoff"
        proposed_follow_up_route = route
        reason = "human decision requested a code change."
    elif state["rerun_requested"]:
        route = "analysis_engineer"
        proposed_follow_up_route = route
        reason = "human decision approved a targeted rerun."
    else:
        route = "memory_report"
        proposed_follow_up_route = route
        reason = "human decision allows reporting to continue."

    record_route_decision(
        state,
        source="human_approval_gate",
        route=route,
        reason=reason,
        fields={
            "status": state["status"],
            "risk_level": state["risk_level"],
            "human_approval_required": state["human_approval_required"],
            "approval_packet_dir": state["approval_packet_dir"],
            "human_decision_path": state["human_decision_path"],
            "human_decision": decision,
            "actual_route": route,
            "requested_route": proposed_follow_up_route,
            "proposed_follow_up_route": proposed_follow_up_route,
            "rerun_requested": state["rerun_requested"],
            "rerun_target": state["rerun_target"],
            "code_fix_requested": state["code_fix_requested"],
        },
    )
    save_graph_state(state)
    return route
