"""Structured routing functions for the mock runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from lqcd_agent.graph.approval_packet import DECISION_ROUTE_TARGETS, parse_human_decision
from lqcd_agent.graph.state import AnalysisState, read_committed_route


PRODUCT_ROUTES = {
    "START": ("method_planner",),
    "method_planner": ("analysis_engineer", "code_agent", "decision_coordinator"),
    "code_agent": ("analysis_engineer", "decision_coordinator"),
    "analysis_engineer": ("scientific_reviewer", "decision_coordinator"),
    "scientific_reviewer": ("decision_coordinator",),
    "decision_coordinator": ("scientific_reviewer", "analysis_engineer", "code_agent", "method_planner", "human_gate", "memory_report"),
    "human_gate": ("decision_coordinator",),
    "memory_report": ("end",),
}
PRODUCT_FALLBACKS = {
    "method_planner": ("replan", "automatic_replan_per_run"),
    "code_agent": ("code_fix", "automatic_code_fix_per_cycle"),
    "analysis_engineer": ("analysis_rerun", "automatic_analysis_rerun_per_cycle"),
    "scientific_reviewer": ("re_review", "automatic_re_review_per_cycle"),
}


def product_budget_decision(state, *, target, trigger, risk, stop_sequence_id=None, proposed_grant=None):
    """Admit an exact route from replayed counters without modifying the input."""
    from lqcd_agent.control.budget import WORK_KINDS, validate_budget_payload
    from lqcd_agent.control.strict_json import digest, require

    budget = state["budget"]
    changes = {"cycles_per_run": int(trigger == "replan"), "work_attempts_per_run": int(target in WORK_KINDS),
               "control_attempts_per_run": int(target is not None and target not in WORK_KINDS), "transitions_per_run": 1}
    route_dimension = PRODUCT_FALLBACKS.get(target, (None, None))[1] if trigger in {row[0] for row in PRODUCT_FALLBACKS.values()} else None
    if route_dimension is not None:
        changes[route_dimension] = 1
    dimensions = {key: {**value, "projected_after": value["used"] + changes.get(key, 0)}
                  for key, value in budget["dimensions"].items()}
    failure = budget["active_failure"]
    grant = budget["active_grant"]
    if proposed_grant is not None:
        require(grant is None and stop_sequence_id is None, "Proposed grant cannot replace an active grant or terminal reserve")
        validate_budget_payload("grant_issued", proposed_grant)
        grant = proposed_grant
    if grant is not None:
        require(grant["target_node"] == target and grant["route_dimension"] == route_dimension and failure is not None and
                grant["fingerprint_digest"] == failure["fingerprint_digest"] and grant["occurrence"] == failure["occurrence"],
                "Active grant does not match this route proposal")
    exceeded = [key for key, value in dimensions.items() if changes.get(key, 0) > value["remaining"] and
                not (grant is not None and key == route_dimension)]
    if stop_sequence_id is None:
        for key, reserve in (("control_attempts_per_run", 5), ("transitions_per_run", 6)):
            if changes.get(key, 0) + reserve > dimensions[key]["remaining"]:
                exceeded.append(key)
    else:
        require(target not in WORK_KINDS, "Terminal reserve cannot dispatch work")
    action = "halt" if exceeded else "allow"
    body = {"schema_version": "0.1", "proposal_id": digest({"source": state["attempt_id"], "target": target,
                "trigger": trigger, "stop_sequence_id": stop_sequence_id}), "proposed_action": "route",
            "target_kind": target, "risk": risk,
            "fingerprint_digest": failure["fingerprint_digest"] if failure else None,
            "occurrence": failure["occurrence"] if failure else 0, "dimensions": dimensions,
            "budget_grant_id": grant["budget_grant_id"] if grant else None, "decision": action,
            "reason_code": "capacity_exhausted" if exceeded else "canonical_route_admitted",
            "next_control_action": "close_run" if exceeded else "advance"}
    result = {**body, "decision_digest": digest(body)}
    validate_budget_payload("decision_recorded", result)
    return result


def select_product_route(view, diagnostic, *, code_needed=False, code_usable=False,
                         human_response=None, human_authorization=None, stop_sequence_id=None, proposed_grant=None):
    """Select a canonical edge from verified outcomes; Agents cannot select it."""
    from lqcd_agent.agents.decision_coordinator import validate_product_diagnostic
    from lqcd_agent.control.strict_json import digest, require

    diagnostic = validate_product_diagnostic(diagnostic)
    source, state = view["source"], view["state"]
    node = source["node_name"]
    require(node in PRODUCT_ROUTES, "Legacy node cannot enter the canonical graph")
    success = source["status"] == "succeeded" and diagnostic["status"] == "success"
    safety_failure = diagnostic["category"] in ("security", "policy", "data") or (
        diagnostic["category"].startswith("scientific") and diagnostic["status"] != "success"
        and diagnostic["retryability"] != "retryable")
    forward = success and diagnostic["risk"] in ("low", "medium") and diagnostic["confidence"] == "unique" and (
        diagnostic["human_need"] is None and not safety_failure)
    trigger = "forward"
    request = None
    if node == "method_planner":
        target = ("code_agent" if code_needed else "analysis_engineer") if forward else "decision_coordinator"
    elif node == "code_agent":
        target = "analysis_engineer" if forward and code_usable else "decision_coordinator"
    elif node == "analysis_engineer":
        target = "scientific_reviewer" if forward else "decision_coordinator"
    elif node == "scientific_reviewer":
        target = "decision_coordinator"
    elif node == "human_gate":
        require(human_response is not None and human_response["status"] == "validated" and
                human_response["validator_attempt_id"] == source["attempt_id"] and
                human_response["authorized_transition_target"] == "decision_coordinator",
                "Human edge requires an exact validated response")
        target, trigger = "decision_coordinator", "human_response"
    elif node == "memory_report":
        require(success, "END requires a completed deterministic terminal sink")
        target = None
    else:
        from lqcd_agent.control.budget import policy

        candidates = diagnostic["candidates"]
        failure = state["budget"]["active_failure"]
        selected_policy = policy(state["budget"]["profile_id"]).value
        reserve = selected_policy["terminal_reserve"]
        dimensions = state["budget"]["dimensions"]
        repeat = (diagnostic["status"] != "success" or bool(diagnostic["candidates"])) and failure is not None and failure["occurrence"] >= 2
        needs_human = diagnostic["risk"] in ("high", "critical") or diagnostic["confidence"] != "unique" or repeat or diagnostic["human_need"] is not None or safety_failure
        if stop_sequence_id is not None:
            target, trigger = "memory_report", "budget_stop"
        elif human_authorization is not None:
            require(human_authorization["target_node"] in candidates or human_authorization["target_node"] == "memory_report",
                    "Human authorization does not match the diagnosed work scope")
            require(diagnostic["category"] not in ("security", "policy", "data"), "Authorization cannot override a hard safety gate")
            target = human_authorization["target_node"]
        elif candidates and not needs_human and diagnostic["retryability"] == "retryable":
            require(len(candidates) == 1, "Ambiguous fallback cannot dispatch work")
            target = candidates[0]
        elif needs_human or candidates:
            target = "human_gate"
        else:
            target = "memory_report"
        if target in PRODUCT_FALLBACKS:
            trigger = PRODUCT_FALLBACKS[target][0]
            decision = product_budget_decision(state, target=target, trigger=trigger, risk=diagnostic["risk"], proposed_grant=proposed_grant)
            if decision["decision"] != "allow":
                route_dimension = PRODUCT_FALLBACKS[target][1]
                grant_possible = (human_authorization is None and failure is not None and
                    state["budget"]["active_grant"] is None and not safety_failure and
                    diagnostic["confidence"] == "unique" and diagnostic["retryability"] == "retryable" and
                    dimensions[route_dimension]["remaining"] == 0 and
                    all(row["projected_after"] - row["used"] <= row["remaining"]
                        for key, row in decision["dimensions"].items() if key != route_dimension) and
                    dimensions["control_attempts_per_run"]["remaining"] >= 3 + reserve["control_attempts"] and
                    dimensions["transitions_per_run"]["remaining"] >= 4 + reserve["transitions"])
                target, trigger = "human_gate", "forward" if grant_possible else "budget_stop"
        if target == "human_gate":
            # The publisher and validator each consume one original admission.
            if any(dimensions[key]["remaining"] < 2 + reserve[reserve_key] for key, reserve_key in
                   (("control_attempts_per_run", "control_attempts"), ("transitions_per_run", "transitions"))):
                trigger = "budget_stop"
            target_scope = candidates[0] if len(candidates) == 1 and trigger != "budget_stop" else None
            decisions = ["approve_with_conditions", "reject_or_hold"]
            if target_scope is not None:
                decisions.extend(["approve_budget_window", "approve_rerun" if target_scope == "analysis_engineer" else "request_code_change" if target_scope == "code_agent" else "approve_with_conditions"])
            decisions = sorted(set(decisions))
            request = {"request_kind": diagnostic["human_need"] or "approval", "authorization_scope": {
                "allowed_decisions": decisions, "allowed_target_nodes": ["decision_coordinator"],
                "decision_transition_routes": dict.fromkeys(decisions, "decision_coordinator"),
                "decision_transition_targets": dict.fromkeys(decisions, "decision_coordinator"),
                "work_target": target_scope, "failure_fingerprint": failure,
                "diagnostic_digest": digest(diagnostic)}}
    require((target or "end") in PRODUCT_ROUTES[node], "Undeclared canonical product edge")
    sequence = stop_sequence_id
    if target == "human_gate" and sequence is None and trigger == "budget_stop":
        sequence = digest({"run_id": state["run_id"], "source_attempt_id": source["attempt_id"], "reason": "budget_stop"})
    decision = product_budget_decision(state, target=target, trigger=trigger, risk=diagnostic["risk"], stop_sequence_id=sequence, proposed_grant=proposed_grant)
    if sequence is not None and target == "human_gate" and any(
            state["budget"]["dimensions"][key]["remaining"] < needed for key, needed in
            (("control_attempts_per_run", 4), ("transitions_per_run", 5))):
        decision.update(decision="halt", reason_code="terminal_tail_capacity", next_control_action="close_run")
        decision["decision_digest"] = digest({k: v for k, v in decision.items() if k != "decision_digest"})
    if decision["decision"] != "allow" and node != "decision_coordinator" and target not in (None, "decision_coordinator"):
        target, trigger = "decision_coordinator", "budget_stop"
        sequence = digest({"run_id": state["run_id"], "source_attempt_id": source["attempt_id"], "reason": "budget_stop"})
        decision = product_budget_decision(state, target=target, trigger=trigger, risk=diagnostic["risk"], stop_sequence_id=sequence)
    return {"target_node": target, "route": target or "end", "trigger_reason": trigger,
            "budget_decision": decision, "human_request": request, "stop_sequence_id": sequence}


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
