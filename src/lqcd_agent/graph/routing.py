"""Structured routing functions for the mock runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from lqcd_agent.graph.approval_packet import DECISION_ROUTE_TARGETS, parse_human_decision
from lqcd_agent.graph.state import AnalysisState, read_committed_route


class RouteSelection(TypedDict, total=False):
    route: str
    target_node: str | None
    target_attempt_kind: str | None
    reason: str
    fields: dict[str, Any]
    evidence_references: dict[str, Any]
    state_updates: dict[str, Any]
    trigger_reason: str
    new_cycle: bool
    human_request_kind: str
    human_authorization_scope: dict[str, Any]


_CURRENT_ROUTE_TARGETS: dict[str, tuple[str, str] | None] = {
    "analysis_engineer": ("analysis_engineer", "analysis_engineer"),
    "codex_handoff": ("codex_handoff", "legacy_codex_handoff"),
    "decision_coordinator": ("decision_coordinator", "decision_coordinator"),
    "scientific_reviewer": ("scientific_reviewer", "scientific_reviewer"),
    "human_approval_gate": ("human_approval_gate", "human_gate"),
    "memory_report": ("memory_report", "memory_report"),
    "method_planner": ("method_planner", "method_planner"),
    "end": None,
}


def route_target_contract(route: str) -> dict[str, str | None]:
    target = _CURRENT_ROUTE_TARGETS[route]
    return {
        "target_node": target[0] if target else None,
        "target_attempt_kind": target[1] if target else None,
    }


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


def select_after_method_planner(state: AnalysisState) -> RouteSelection:
    if state["status"] in {"pending", "halted"}:
        route = "end"
        reason = "method planner reached a safe terminal status before analysis."
    elif state["code_needed"]:
        route = "codex_handoff"
        reason = "code_needed is true and a file-based Codex Handoff is required."
    else:
        route = "analysis_engineer"
        reason = "code_needed is false."
    return {
        "route": route,
        **route_target_contract(route),
        "reason": reason,
        "fields": {
            "status": state["status"],
            "code_needed": state["code_needed"],
            "coder_task_packet_path": state["coder_task_packet_path"],
            "error_count": len(state["errors"]),
            "retry_count": state["retry_count"],
            "max_retry": state["max_retry"],
        },
        "evidence_references": {
            "method_plan_path": state.get("method_plan_path"),
            "coder_task_packet_path": state.get("coder_task_packet_path"),
        },
        "state_updates": {},
        "trigger_reason": "forward",
        "new_cycle": False,
    }


def select_after_analysis_engineer(state: AnalysisState) -> RouteSelection:
    state_updates: dict[str, Any] = {}
    if state["run_success"]:
        route = "scientific_reviewer"
        reason = "run_success is true."
    elif state["failure_type"] == "code" and state["retry_count"] < state["max_retry"]:
        state_updates = {
            "retry_count": state["retry_count"] + 1,
            "code_fix_requested": True,
        }
        route = "codex_handoff"
        reason = "code failure has retry budget and requires Codex Handoff."
    else:
        route = "decision_coordinator"
        reason = "analysis failed without a mock retry route."
    effective_retry_count = int(state_updates.get("retry_count", state["retry_count"]))
    return {
        "route": route,
        **route_target_contract(route),
        "reason": reason,
        "fields": {
            "run_success": state["run_success"],
            "failure_type": state["failure_type"],
            "retry_count": effective_retry_count,
        },
        "evidence_references": {
            "run_result_path": state.get("run_result_path"),
            "tests_status_path": state.get("tests_status_path"),
        },
        "state_updates": state_updates,
        "trigger_reason": "legacy_code_retry" if route == "codex_handoff" else "forward",
        "new_cycle": False,
    }


def select_after_codex_handoff(state: AnalysisState) -> RouteSelection:
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
    return {
        "route": route,
        **route_target_contract(route),
        "reason": reason,
        "fields": {
            "status": state["status"],
            "tests_status": tests_status,
            "coder_task_packet_path": state["coder_task_packet_path"],
            "code_change_summary_path": state["code_change_summary_path"],
            "tests_status_path": state["tests_status_path"],
            "retry_count": state["retry_count"],
            "max_retry": state["max_retry"],
        },
        "evidence_references": {
            "code_change_summary_path": state.get("code_change_summary_path"),
            "tests_status_path": state.get("tests_status_path"),
        },
        "state_updates": {},
        "trigger_reason": "forward",
        "new_cycle": False,
    }


def select_after_decision_coordinator(state: AnalysisState) -> RouteSelection:
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
    selection: RouteSelection = {
        "route": route,
        **route_target_contract(route),
        "reason": reason,
        "fields": {
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
        "evidence_references": {
            "scientific_review_report_path": state.get("scientific_review_report_path"),
            "decision_log_path": state.get("decision_log_path"),
        },
        "state_updates": {},
        "trigger_reason": "forward",
        "new_cycle": False,
    }
    if route == "human_approval_gate":
        selection["human_request_kind"] = "approval"
        selection["human_authorization_scope"] = {
            "allowed_decisions": sorted(DECISION_ROUTE_TARGETS),
            "allowed_target_nodes": sorted(set(DECISION_ROUTE_TARGETS.values())),
            "decision_transition_routes": {
                "approve_rerun": "end",
                "approve_with_conditions": "memory_report",
                "reject_or_hold": "memory_report",
                "request_code_change": "codex_handoff",
            },
            "decision_transition_targets": {
                "approve_rerun": "END",
                "approve_with_conditions": "memory_report",
                "reject_or_hold": "memory_report",
                "request_code_change": "codex_handoff",
            },
            "compatibility_topology": True,
        }
    return selection


def select_after_human_approval_gate(state: AnalysisState) -> RouteSelection:
    decision = state.get("human_response_decision")
    decision_status = (
        "approved"
        if state.get("human_response_status") in {"validated", "consumed"}
        and isinstance(decision, str)
        else None
    )
    decision_path = state.get("human_decision_path")
    if decision_status is None and decision_path:
        decision_result = parse_human_decision(
            decision_path,
            run_id=state["run_id"],
            case_id=state["case_id"],
            cycle_id=state["cycle_id"],
            human_request_id=state.get("active_human_request_id"),
            requesting_attempt_id=state.get("human_requesting_attempt_id"),
            human_response_id=state.get("active_human_response_id"),
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

    return {
        "route": route,
        **route_target_contract(route),
        "reason": reason,
        "fields": {
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
        "evidence_references": {
            "approval_packet_dir": state.get("approval_packet_dir"),
            "human_decision_path": state.get("human_decision_path"),
        },
        "state_updates": {},
        "trigger_reason": "human_response" if decision_status == "approved" else "forward",
        "new_cycle": False,
    }


def committed_route(state: AnalysisState) -> str:
    return read_committed_route(state)


def route_after_method_planner(state: AnalysisState) -> str:
    return select_after_method_planner(state)["route"]


def route_after_analysis_engineer(state: AnalysisState) -> str:
    return select_after_analysis_engineer(state)["route"]


def route_after_codex_handoff(state: AnalysisState) -> str:
    return select_after_codex_handoff(state)["route"]


def route_after_decision_coordinator(state: AnalysisState) -> str:
    return select_after_decision_coordinator(state)["route"]


def route_after_human_approval_gate(state: AnalysisState) -> str:
    return select_after_human_approval_gate(state)["route"]
