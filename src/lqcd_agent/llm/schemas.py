"""Strict schema checks for provider-backed agent artifacts."""

from __future__ import annotations

from typing import Any


BASE_FIELDS = [
    "schema_version",
    "run_id",
    "case_id",
    "producer",
    "status",
    "summary",
    "warnings",
    "errors",
]
METHOD_PLAN_FIELDS = [
    "physics_goal",
    "target_observables",
    "method_steps",
    "required_inputs",
    "required_outputs",
    "implementation_gaps",
    "code_needed",
    "coder_task_summary",
]
SCIENTIFIC_REVIEW_FIELDS = [
    "correlator_diagnostics",
    "fit_diagnostics",
    "matrix_element_diagnostics",
    "findings",
    "evidence",
    "recommended_checks",
    "confidence",
]
DECISION_FIELDS = [
    "risk_level",
    "recommended_action",
    "human_approval_required",
    "reasons",
    "evidence",
    "next_actions",
    "routing_decision",
]

ALLOWED_BASE_STATUSES = {"success", "failed", "pending", "needs_more_info"}
ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_ACTUAL_ROUTES = {"human_approval_gate", "memory_report"}
ALLOWED_FOLLOW_UP_ROUTES = {"human_approval_gate", "memory_report", "analysis_engineer", "codex_handoff"}


def _missing_fields(payload: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if field not in payload]


def _expect_type(errors: list[str], payload: dict[str, Any], field: str, expected_type: type) -> None:
    if field in payload and not isinstance(payload[field], expected_type):
        errors.append(f"{field} must be {expected_type.__name__}.")


def _expect_list_items_dict(errors: list[str], payload: dict[str, Any], field: str) -> None:
    value = payload.get(field)
    if isinstance(value, list) and any(not isinstance(item, dict) for item in value):
        errors.append(f"{field} items must be dict.")


def _validate_base(
    payload: dict[str, Any],
    *,
    run_id: str,
    case_id: str,
    producer: str,
) -> list[str]:
    errors = _missing_fields(payload, BASE_FIELDS)
    if payload.get("schema_version") != "0.1":
        errors.append("schema_version must be 0.1.")
    if payload.get("run_id") != run_id:
        errors.append("run_id must match the active run.")
    if payload.get("case_id") != case_id:
        errors.append("case_id must match the active case.")
    if payload.get("producer") != producer:
        errors.append(f"producer must be {producer}.")
    if payload.get("status") not in ALLOWED_BASE_STATUSES:
        errors.append("status is not allowed.")
    _expect_type(errors, payload, "summary", str)
    _expect_type(errors, payload, "warnings", list)
    _expect_type(errors, payload, "errors", list)
    _expect_list_items_dict(errors, payload, "warnings")
    _expect_list_items_dict(errors, payload, "errors")
    return errors


def validate_method_plan_payload(payload: dict[str, Any], *, run_id: str, case_id: str) -> list[str]:
    errors = _validate_base(payload, run_id=run_id, case_id=case_id, producer="method_planner")
    errors.extend(_missing_fields(payload, METHOD_PLAN_FIELDS))
    for field in [
        "target_observables",
        "method_steps",
        "required_inputs",
        "required_outputs",
        "implementation_gaps",
    ]:
        _expect_type(errors, payload, field, list)
    if "code_needed" in payload and not isinstance(payload["code_needed"], bool):
        errors.append("code_needed must be bool.")
    return errors


def validate_scientific_review_payload(payload: dict[str, Any], *, run_id: str, case_id: str) -> list[str]:
    errors = _validate_base(
        payload,
        run_id=run_id,
        case_id=case_id,
        producer="scientific_reviewer",
    )
    errors.extend(_missing_fields(payload, SCIENTIFIC_REVIEW_FIELDS))
    for field in [
        "findings",
        "evidence",
        "recommended_checks",
        "warnings",
        "errors",
    ]:
        _expect_type(errors, payload, field, list)
    for field in ["findings", "evidence"]:
        _expect_list_items_dict(errors, payload, field)
    for field in ["correlator_diagnostics", "fit_diagnostics", "matrix_element_diagnostics"]:
        _expect_type(errors, payload, field, dict)
    if payload.get("confidence") not in ALLOWED_CONFIDENCE:
        errors.append("confidence is not allowed.")
    return errors


def validate_decision_log_payload(payload: dict[str, Any], *, run_id: str, case_id: str) -> list[str]:
    errors = _validate_base(
        payload,
        run_id=run_id,
        case_id=case_id,
        producer="decision_coordinator",
    )
    errors.extend(_missing_fields(payload, DECISION_FIELDS))
    if payload.get("risk_level") not in ALLOWED_RISK_LEVELS:
        errors.append("risk_level is not allowed.")
    _expect_type(errors, payload, "recommended_action", str)
    if "human_approval_required" in payload and not isinstance(payload["human_approval_required"], bool):
        errors.append("human_approval_required must be bool.")
    if payload.get("risk_level") in {"high", "critical"} and payload.get("human_approval_required") is not True:
        errors.append("high and critical risk require human_approval_required=true.")
    for field in ["reasons", "evidence", "next_actions"]:
        _expect_type(errors, payload, field, list)
        _expect_list_items_dict(errors, payload, field)
    routing = payload.get("routing_decision")
    if not isinstance(routing, dict):
        errors.append("routing_decision must be dict.")
        return errors

    actual_route = routing.get("actual_route")
    if actual_route not in ALLOWED_ACTUAL_ROUTES:
        errors.append("routing_decision.actual_route is not allowed.")
    requested_route = routing.get("requested_route")
    if requested_route not in ALLOWED_FOLLOW_UP_ROUTES:
        errors.append("routing_decision.requested_route is not allowed.")
    proposed_route = routing.get("proposed_follow_up_route")
    if proposed_route not in ALLOWED_FOLLOW_UP_ROUTES:
        errors.append("routing_decision.proposed_follow_up_route is not allowed.")
    fields = routing.get("fields")
    if not isinstance(fields, dict):
        errors.append("routing_decision.fields must be dict.")
        return errors
    if fields.get("risk_level") != payload.get("risk_level"):
        errors.append("routing_decision.fields.risk_level must match risk_level.")
    if fields.get("human_approval_required") != payload.get("human_approval_required"):
        errors.append("routing_decision.fields.human_approval_required must match human_approval_required.")
    for field in ["rerun_requested", "code_fix_requested"]:
        if field in fields and not isinstance(fields[field], bool):
            errors.append(f"routing_decision.fields.{field} must be bool.")
    return errors
