"""Deterministic Decision Coordinator Agent for Phase 6."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.llm.base import LLMProvider
from lqcd_agent.llm.prompts import build_decision_coordinator_request
from lqcd_agent.llm.provider_factory import create_provider_from_config_path
from lqcd_agent.llm.schemas import validate_decision_log_payload
from lqcd_agent.llm.structured_output import (
    parse_json_object,
    provider_exception_artifact,
    validation_error_artifact,
)
from lqcd_agent.llm.trace import write_llm_call_trace


RISK_RUBRIC = {
    "schema_version": "0.1",
    "risk_order": ["critical", "high", "medium", "low"],
    "rules": [
        {
            "risk_level": "critical",
            "summary": "Required artifacts are missing, unreadable, identity-mismatched, or the method plan is not usable.",
            "human_approval_required": True,
        },
        {
            "risk_level": "high",
            "summary": "The run failed, a code fix or targeted rerun is required, or the review contains severe flagged warnings.",
            "human_approval_required": True,
        },
        {
            "risk_level": "medium",
            "summary": "The run succeeded but non-severe warnings or medium-confidence review evidence remain.",
            "human_approval_required": False,
        },
        {
            "risk_level": "low",
            "summary": "The plan, run, and review succeeded with no warnings and structured review evidence.",
            "human_approval_required": False,
        },
    ],
}
RISK_SEVERITY = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def validate_product_diagnostic(value):
    """Validate A01 diagnostics without granting route or scientific authority."""
    from lqcd_agent.control.strict_json import closed, digest_value, require, text
    closed(value, ("status", "category", "affected_layer", "evidence", "retryability", "candidates",
                   "confidence", "fingerprint", "human_need", "risk"))
    require(value["status"] in ("success", "failed", "needs_input", "needs_human", "pending"), "Unknown product outcome")
    text(value["category"])
    require(value["affected_layer"] in ("plan", "code", "analysis", "review", "none"), "Unknown affected layer")
    require(value["retryability"] in ("retryable", "not_retryable", "new_evidence_required"), "Unknown retryability")
    require(value["confidence"] in ("unique", "ambiguous", "insufficient"), "Unknown diagnosis confidence")
    require(value["human_need"] in (None, "clarification", "approval", "external_action"), "Unknown Human need")
    require(value["risk"] in RISK_SEVERITY, "Unknown diagnostic risk")
    require(type(value["candidates"]) is list and value["candidates"] == sorted(set(value["candidates"])) and
            set(value["candidates"]) <= {"method_planner", "code_agent", "analysis_engineer", "scientific_reviewer"},
            "Invalid remediation candidates")
    require(type(value["evidence"]) is list, "Missing diagnostic evidence")
    for reference in value["evidence"]:
        closed(reference, ("artifact_id", "member", "sha256"))
        text(reference["artifact_id"])
        text(reference["member"])
        digest_value(reference["sha256"])
    digest_value(value["fingerprint"], nullable=True)
    require(value["status"] == "success" or bool(value["evidence"]), "Failure requires attributable evidence")
    return value


def product_coordinator_diagnosis(diagnostics, *, local_risk_floor):
    """Merge bounded evidence; the control selector admits the resulting action."""
    from copy import deepcopy
    from lqcd_agent.control.strict_json import require
    require(type(diagnostics) is list and diagnostics, "Coordinator requires bounded source diagnostics")
    require(local_risk_floor in RISK_SEVERITY, "Missing deterministic risk floor")
    values = [validate_product_diagnostic(deepcopy(value)) for value in diagnostics]
    result = values[-1]
    risks = [local_risk_floor, *[value["risk"] for value in values]]
    result["risk"] = max(risks, key=RISK_SEVERITY.__getitem__)
    candidates = sorted({candidate for value in values for candidate in value["candidates"]})
    result["candidates"] = candidates
    if len(candidates) > 1 or any(value["confidence"] != "unique" for value in values):
        result["confidence"] = "ambiguous"
    if result["risk"] in ("high", "critical") and result["human_need"] is None:
        result["human_need"] = "approval"
    return validate_product_diagnostic(result)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_artifact(*, run_id: str, case_id: str, status: str, summary: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": utc_now(),
        "producer": "decision_coordinator",
        "status": status,
        "summary": summary,
        "warnings": [],
        "errors": [],
    }


def _read_json_artifact(
    path: str | Path | None,
    *,
    artifact_name: str,
    run_id: str,
    case_id: str,
    allow_failed_status: bool = False,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    evidence = [
        {
            "artifact": artifact_name,
            "path": str(path) if path else None,
            "field": "exists",
            "value": bool(path and Path(path).exists()),
        }
    ]
    errors: list[dict[str, Any]] = []
    if not path:
        errors.append(
            {
                "artifact": artifact_name,
                "path": None,
                "field": "path",
                "message": f"{artifact_name} path is required.",
            }
        )
        return None, evidence, errors

    artifact_path = Path(path)
    if not artifact_path.exists():
        errors.append(
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "exists",
                "message": f"{artifact_name} is required but missing.",
            }
        )
        return None, evidence, errors

    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append(
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "$",
                "message": f"{artifact_name} is not valid JSON.",
            }
        )
        return None, evidence, errors

    if not isinstance(payload, dict):
        errors.append(
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "$",
                "message": f"{artifact_name} must be a JSON object.",
            }
        )
        return None, evidence, errors

    evidence.extend(
        [
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "schema_version",
                "value": payload.get("schema_version"),
            },
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "run_id",
                "value": payload.get("run_id"),
            },
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "case_id",
                "value": payload.get("case_id"),
            },
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "status",
                "value": payload.get("status"),
            },
        ]
    )
    if not payload.get("schema_version"):
        errors.append(
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "schema_version",
                "message": f"{artifact_name} is missing schema_version.",
            }
        )
    for field, expected in {"run_id": run_id, "case_id": case_id}.items():
        value = payload.get(field)
        if value != expected:
            errors.append(
                {
                    "artifact": artifact_name,
                    "path": str(artifact_path),
                    "field": field,
                    "value": value,
                    "expected": expected,
                    "message": f"{artifact_name} {field} does not match the active run.",
                }
            )
    if payload.get("status") == "failed" and not allow_failed_status:
        errors.append(
            {
                "artifact": artifact_name,
                "path": str(artifact_path),
                "field": "status",
                "value": "failed",
                "message": f"{artifact_name} is a failed artifact and cannot be used for low-risk routing.",
            }
        )
    return payload, evidence, errors


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _reason(code: str, message: str, *, source: str, field: str | None = None, value: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "source": source,
        "field": field,
        "value": value,
        "message": message,
    }


def _review_warnings(review: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not review:
        return []
    return [warning for warning in _as_list(review.get("warnings")) if isinstance(warning, dict)]


def _is_advisory_normalization_warning(warning: dict[str, Any]) -> bool:
    return (
        warning.get("code") == "selected_analysis_programs_normalized"
        and warning.get("decision_coordinator_flag") is not True
        and warning.get("severity") in {None, "info"}
    )


def _risk_relevant_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [warning for warning in warnings if not _is_advisory_normalization_warning(warning)]


def _warning_evidence(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "artifact": "scientific_review_report",
            "section": warning.get("section"),
            "code": warning.get("code"),
            "severity": warning.get("severity"),
            "decision_coordinator_flag": warning.get("decision_coordinator_flag"),
            "message": warning.get("message"),
            "path": warning.get("path"),
            "field": warning.get("field"),
            "value": warning.get("value"),
        }
        for warning in warnings
    ]


def _targeted_rerun_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for warning in warnings:
        code = str(warning.get("code", "")).lower()
        value = str(warning.get("value", "")).lower()
        if "targeted_rerun" in code or "targeted_rerun" in value:
            matches.append(warning)
    return matches


def _review_structured_evidence(review: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not review:
        return []
    evidence_items = _as_list(review.get("evidence"))
    return [
        {
            "artifact": "scientific_review_report",
            "source_field": "evidence",
            **item,
        }
        for item in evidence_items
        if isinstance(item, dict)
    ]


def _run_failure_action(run_result: dict[str, Any]) -> tuple[str, bool, str | None]:
    failure_type = run_result.get("failure_type")
    if failure_type == "code":
        return "code_fix", False, None
    return "targeted_rerun", True, "analysis_engineer"


def _missing_input_reasons(run_result: dict[str, Any]) -> list[dict[str, Any]]:
    reasons = [
        _reason(
            "config_or_data_failure",
            "Analysis Engineer could not run because required runtime input data or config was invalid.",
            source="run_result",
            field="failure_type",
            value=run_result.get("failure_type"),
        )
    ]
    for error in _as_list(run_result.get("errors")):
        if not isinstance(error, dict):
            continue
        message = str(error.get("message", ""))
        field = error.get("field")
        if "raw_data_path" in message or "raw data" in message.lower():
            reasons.append(
                _reason(
                    "missing_required_input",
                    message,
                    source="run_result",
                    field=str(field) if field is not None else "raw_data_path",
                    value=error.get("value"),
                )
            )
            break
    return reasons


def _classify_decision(
    *,
    method_plan: dict[str, Any] | None,
    run_result: dict[str, Any] | None,
    review: dict[str, Any] | None,
    artifact_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[dict[str, Any]] = []
    if artifact_errors:
        reasons.extend(
            _reason(
                "artifact_contract_error",
                str(error["message"]),
                source=str(error.get("artifact", "artifact")),
                field=error.get("field"),
                value=error.get("value"),
            )
            for error in artifact_errors
        )
        return {
            "risk_level": "critical",
            "recommended_action": "pending_human_approval",
            "human_approval_required": True,
            "reasons": reasons,
            "rerun_requested": False,
            "rerun_target": None,
            "code_fix_requested": False,
            "requested_route": "human_approval_gate",
            "proposed_follow_up_route": "memory_report",
        }

    assert method_plan is not None
    assert run_result is not None

    if method_plan.get("status") != "success":
        return {
            "risk_level": "critical",
            "recommended_action": "pending_human_approval",
            "human_approval_required": True,
            "reasons": [
                _reason(
                    "method_plan_not_usable",
                    "Decision coordination requires a successful method plan.",
                    source="method_plan",
                    field="status",
                    value=method_plan.get("status"),
                )
            ],
            "rerun_requested": False,
            "rerun_target": None,
            "code_fix_requested": False,
            "requested_route": "human_approval_gate",
            "proposed_follow_up_route": "memory_report",
        }

    if run_result.get("run_success") is not True:
        if run_result.get("failure_type") == "config_or_data":
            return {
                "risk_level": "critical",
                "recommended_action": "pending_human_approval",
                "human_approval_required": True,
                "reasons": _missing_input_reasons(run_result),
                "rerun_requested": False,
                "rerun_target": None,
                "code_fix_requested": False,
                "requested_route": "human_approval_gate",
                "proposed_follow_up_route": "memory_report",
            }
        recommended_action, rerun_requested, rerun_target = _run_failure_action(run_result)
        return {
            "risk_level": "high",
            "recommended_action": recommended_action,
            "human_approval_required": True,
            "reasons": [
                _reason(
                    "run_failed",
                    "Decision coordination cannot accept a failed analysis run.",
                    source="run_result",
                    field="run_success",
                    value=run_result.get("run_success"),
                ),
                _reason(
                    "failure_type",
                    "The structured failure type determines the primary repair action.",
                    source="run_result",
                    field="failure_type",
                    value=run_result.get("failure_type"),
                ),
            ],
            "rerun_requested": rerun_requested,
            "rerun_target": rerun_target,
            "code_fix_requested": recommended_action == "code_fix",
            "requested_route": "human_approval_gate",
            "proposed_follow_up_route": "codex_handoff" if recommended_action == "code_fix" else "analysis_engineer",
        }

    assert review is not None
    warnings = _review_warnings(review)
    risk_warnings = _risk_relevant_warnings(warnings)
    severe_or_flagged = [
        warning
        for warning in risk_warnings
        if warning.get("severity") == "severe" or warning.get("decision_coordinator_flag") is True
    ]
    if severe_or_flagged:
        return {
            "risk_level": "high",
            "recommended_action": "pending_human_approval",
            "human_approval_required": True,
            "reasons": [
                _reason(
                    "severe_or_flagged_review_warning",
                    "Severe or Decision-Coordinator-flagged scientific warnings prevent low-risk acceptance.",
                    source="scientific_review_report",
                    field="warnings",
                    value=len(severe_or_flagged),
                )
            ],
            "rerun_requested": False,
            "rerun_target": None,
            "code_fix_requested": False,
            "requested_route": "human_approval_gate",
            "proposed_follow_up_route": "memory_report",
        }

    targeted_rerun = _targeted_rerun_warnings(risk_warnings)
    if targeted_rerun:
        return {
            "risk_level": "medium",
            "recommended_action": "targeted_rerun",
            "human_approval_required": False,
            "reasons": [
                _reason(
                    "targeted_rerun_recommended",
                    "Structured reviewer warnings request a targeted synthetic rerun.",
                    source="scientific_review_report",
                    field="warnings",
                    value=len(targeted_rerun),
                )
            ],
            "rerun_requested": True,
            "rerun_target": "analysis_engineer",
            "code_fix_requested": False,
            "requested_route": "memory_report",
            "proposed_follow_up_route": "analysis_engineer",
        }

    confidence = review.get("confidence")
    review_evidence = _as_list(review.get("evidence"))
    if risk_warnings or confidence == "medium" or not review_evidence:
        reasons = []
        if risk_warnings:
            reasons.append(
                _reason(
                    "non_severe_review_warning",
                    "Non-severe review warnings require pending or review-recommended handling.",
                    source="scientific_review_report",
                    field="warnings",
                    value=len(risk_warnings),
                )
            )
        if confidence == "medium":
            reasons.append(
                _reason(
                    "medium_review_confidence",
                    "Medium review confidence requires human-review-recommended handling.",
                    source="scientific_review_report",
                    field="confidence",
                    value=confidence,
                )
            )
        if not review_evidence:
            reasons.append(
                _reason(
                    "missing_review_evidence",
                    "Low risk requires structured review evidence.",
                    source="scientific_review_report",
                    field="evidence",
                    value=[],
                )
            )
        return {
            "risk_level": "medium",
            "recommended_action": "human_review_recommended",
            "human_approval_required": False,
            "reasons": reasons,
            "rerun_requested": False,
            "rerun_target": None,
            "code_fix_requested": False,
            "requested_route": "memory_report",
            "proposed_follow_up_route": "memory_report",
        }

    return {
        "risk_level": "low",
        "recommended_action": "accept_mock_result",
        "human_approval_required": False,
        "reasons": [
            _reason(
                "low_risk_structured_evidence",
                "Method plan, run result, and scientific review are successful with no warnings.",
                source="decision_coordinator",
                field="risk_level",
                value="low",
            )
        ],
        "rerun_requested": False,
        "rerun_target": None,
        "code_fix_requested": False,
        "requested_route": "memory_report",
        "proposed_follow_up_route": "memory_report",
    }


def _next_action(decision: dict[str, Any]) -> dict[str, Any]:
    action = str(decision["recommended_action"])
    if action == "code_fix":
        target = "codex_handoff"
    elif action == "targeted_rerun":
        target = decision.get("rerun_target") or "analysis_engineer"
    elif decision["human_approval_required"]:
        target = "human_approval_gate"
    else:
        target = "memory_report"
    return {
        "action": action,
        "primary": True,
        "target": target,
        "status": "pending" if decision["risk_level"] != "low" else "ready",
    }


def _summary(decision: dict[str, Any]) -> str:
    risk_level = decision["risk_level"]
    if risk_level == "low":
        return "Decision Coordinator classified the run as low risk for result acceptance."
    if risk_level == "medium":
        return "Decision Coordinator classified the run as medium risk and kept memory pending."
    if risk_level == "high":
        return "Decision Coordinator classified the run as high risk and requires human approval before acceptance."
    return "Decision Coordinator classified the run as critical risk due to unusable structured evidence."


def write_decision_log(output_dir: str | Path, decision_log: dict[str, Any]) -> str:
    path = Path(output_dir) / "decision_log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(decision_log, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _method_plan_summary(payload: dict[str, Any] | None, *, path: str | Path | None) -> dict[str, Any]:
    if payload is None:
        return {"exists": bool(path and Path(path).exists()), "path": str(path) if path else None}
    return {
        "exists": True,
        "path": str(path) if path else None,
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
        "code_needed": payload.get("code_needed"),
        "implementation_gap_count": len(payload.get("implementation_gaps", []))
        if isinstance(payload.get("implementation_gaps"), list)
        else None,
    }


def _run_result_summary(payload: dict[str, Any] | None, *, path: str | Path | None) -> dict[str, Any]:
    if payload is None:
        return {"exists": bool(path and Path(path).exists()), "path": str(path) if path else None}
    return {
        "exists": True,
        "path": str(path) if path else None,
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
        "run_success": payload.get("run_success"),
        "failure_type": payload.get("failure_type"),
        "analysis_outputs_dir": payload.get("analysis_outputs_dir"),
        "produced_output_count": len(payload.get("produced_outputs", []))
        if isinstance(payload.get("produced_outputs"), list)
        else None,
    }


def _scientific_review_summary(payload: dict[str, Any] | None, *, path: str | Path | None) -> dict[str, Any]:
    if payload is None:
        return {"exists": bool(path and Path(path).exists()), "path": str(path) if path else None}
    return {
        "exists": True,
        "path": str(path) if path else None,
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
        "confidence": payload.get("confidence"),
        "evidence_count": len(payload.get("evidence", [])) if isinstance(payload.get("evidence"), list) else None,
    }


def _build_decision_log(
    *,
    run_id: str,
    case_id: str,
    decision: dict[str, Any],
    review: dict[str, Any] | None,
    artifact_errors: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    summary: str | None = None,
) -> dict[str, Any]:
    status = "success" if decision["risk_level"] == "low" else "pending"
    actual_route = "human_approval_gate" if decision["human_approval_required"] else "memory_report"
    return {
        **_base_artifact(run_id=run_id, case_id=case_id, status=status, summary=summary or _summary(decision)),
        "warnings": _review_warnings(review),
        "errors": artifact_errors,
        "risk_rubric": RISK_RUBRIC,
        "risk_level": decision["risk_level"],
        "recommended_action": decision["recommended_action"],
        "human_approval_required": decision["human_approval_required"],
        "reasons": decision["reasons"],
        "evidence": evidence,
        "next_actions": [_next_action(decision)],
        "routing_decision": {
            "actual_route": actual_route,
            "requested_route": decision["requested_route"],
            "proposed_follow_up_route": decision["proposed_follow_up_route"],
            "fields": {
                "risk_level": decision["risk_level"],
                "recommended_action": decision["recommended_action"],
                "human_approval_required": decision["human_approval_required"],
                "rerun_requested": decision["rerun_requested"],
                "rerun_target": decision["rerun_target"],
                "code_fix_requested": decision["code_fix_requested"],
            },
        },
    }


def _local_decision_context(
    *,
    run_id: str,
    case_id: str,
    method_plan_path: str | Path | None,
    run_result_path: str | Path | None,
    scientific_review_report_path: str | Path | None,
) -> dict[str, Any]:
    method_plan, method_evidence, method_errors = _read_json_artifact(
        method_plan_path,
        artifact_name="method_plan",
        run_id=run_id,
        case_id=case_id,
    )
    run_result, run_evidence, run_errors = _read_json_artifact(
        run_result_path,
        artifact_name="run_result",
        run_id=run_id,
        case_id=case_id,
        allow_failed_status=True,
    )
    review, review_artifact_evidence, review_errors = _read_json_artifact(
        scientific_review_report_path,
        artifact_name="scientific_review_report",
        run_id=run_id,
        case_id=case_id,
    )
    if (
        isinstance(run_result, dict)
        and run_result.get("run_success") is not True
        and run_result.get("failure_type") == "config_or_data"
    ):
        review_errors = []
    artifact_errors = method_errors + run_errors + review_errors
    decision = _classify_decision(
        method_plan=method_plan,
        run_result=run_result,
        review=review,
        artifact_errors=artifact_errors,
    )
    evidence = (
        method_evidence
        + run_evidence
        + review_artifact_evidence
        + _review_structured_evidence(review)
        + _warning_evidence(_review_warnings(review))
    )
    decision_log = _build_decision_log(
        run_id=run_id,
        case_id=case_id,
        decision=decision,
        review=review,
        artifact_errors=artifact_errors,
        evidence=evidence,
    )
    return {
        "method_plan": method_plan,
        "run_result": run_result,
        "review": review,
        "decision": decision,
        "decision_log": decision_log,
        "method_plan_summary": _method_plan_summary(method_plan, path=method_plan_path),
        "run_result_summary": _run_result_summary(run_result, path=run_result_path),
        "scientific_review_summary": _scientific_review_summary(review, path=scientific_review_report_path),
    }


def _risk_is_lower_than_floor(candidate: str, floor: str) -> bool:
    return RISK_SEVERITY.get(candidate, -1) < RISK_SEVERITY.get(floor, -1)


def _risk_is_higher_than_floor(candidate: str, floor: str) -> bool:
    return RISK_SEVERITY.get(candidate, -1) > RISK_SEVERITY.get(floor, -1)


def _apply_provider_safety_floor(
    *,
    provider_log: dict[str, Any],
    local_context: dict[str, Any],
) -> dict[str, Any]:
    floor_log = local_context["decision_log"]
    floor_risk = floor_log["risk_level"]
    provider_risk = str(provider_log.get("risk_level"))
    if not _risk_is_lower_than_floor(provider_risk, str(floor_risk)):
        if (
            provider_log.get("human_approval_required") is True
            and floor_log.get("human_approval_required") is False
            and _risk_is_higher_than_floor(provider_risk, str(floor_risk))
        ):
            adjusted = dict(floor_log)
            adjusted["summary"] = (
                "Provider-backed decision was constrained by the local evidence policy: "
                f"{floor_log['summary']}"
            )
            adjusted["reasons"] = [
                _reason(
                    "provider_unsupported_human_gate",
                    "Provider output requested Human Gate without deterministic high-risk evidence.",
                    source="decision_coordinator",
                    field="risk_level",
                    value={
                        "provider": provider_log.get("risk_level"),
                        "local_policy": floor_risk,
                    },
                ),
                *floor_log["reasons"],
            ]
            adjusted["evidence"] = [
                *floor_log["evidence"],
                {
                    "artifact": "provider_decision_log",
                    "field": "risk_level",
                    "value": provider_log.get("risk_level"),
                },
                {
                    "artifact": "provider_decision_log",
                    "field": "recommended_action",
                    "value": provider_log.get("recommended_action"),
                },
            ]
            return adjusted
        return provider_log

    adjusted = dict(floor_log)
    adjusted["summary"] = (
        "Provider-backed decision was raised by the local safety floor: "
        f"{floor_log['summary']}"
    )
    adjusted["reasons"] = [
        _reason(
            "provider_safety_floor",
            "Provider output proposed a lower risk than deterministic artifact evidence allows.",
            source="decision_coordinator",
            field="risk_level",
            value={
                "provider": provider_log.get("risk_level"),
                "floor": floor_risk,
            },
        ),
        *floor_log["reasons"],
    ]
    adjusted["evidence"] = [
        *floor_log["evidence"],
        {
            "artifact": "provider_decision_log",
            "field": "risk_level",
            "value": provider_log.get("risk_level"),
        },
        {
            "artifact": "provider_decision_log",
            "field": "recommended_action",
            "value": provider_log.get("recommended_action"),
        },
    ]
    return adjusted


def _provider_failure_decision_log(
    *,
    run_id: str,
    case_id: str,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    errors = artifact.get("errors", [])
    return {
        **_base_artifact(
            run_id=run_id,
            case_id=case_id,
            status="pending",
            summary="Decision Coordinator rejected invalid provider output and requires human approval.",
        ),
        "errors": errors if isinstance(errors, list) else [],
        "risk_rubric": RISK_RUBRIC,
        "risk_level": "critical",
        "recommended_action": "pending_human_approval",
        "human_approval_required": True,
        "reasons": [
            _reason(
                "provider_output_invalid",
                artifact.get("summary", "Provider output was invalid."),
                source="decision_coordinator",
                field="provider_output",
            )
        ],
        "evidence": [],
        "next_actions": [
            {
                "action": "pending_human_approval",
                "primary": True,
                "target": "human_approval_gate",
                "status": "pending",
            }
        ],
        "routing_decision": {
            "actual_route": "human_approval_gate",
            "requested_route": "human_approval_gate",
            "proposed_follow_up_route": "memory_report",
            "fields": {
                "risk_level": "critical",
                "recommended_action": "pending_human_approval",
                "human_approval_required": True,
                "rerun_requested": False,
                "rerun_target": None,
                "code_fix_requested": False,
            },
        },
    }


def _normalize_provider_decision_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    risk_level = normalized.get("risk_level")
    action_text = str(normalized.get("recommended_action", "")).lower()
    if "targeted" in action_text and "rerun" in action_text:
        normalized["recommended_action"] = "targeted_rerun"
    elif "code" in action_text and ("fix" in action_text or "change" in action_text):
        normalized["recommended_action"] = "code_fix"
    elif risk_level in {"high", "critical"} or "human gate" in action_text:
        normalized["recommended_action"] = "pending_human_approval"
    elif risk_level == "medium" or "review" in action_text:
        normalized["recommended_action"] = "human_review_recommended"
    elif "approval" in action_text:
        normalized["recommended_action"] = "pending_human_approval"
    elif risk_level == "low":
        normalized["recommended_action"] = "accept_mock_result"
    if risk_level in {"high", "critical"}:
        normalized["human_approval_required"] = True
    human_approval_required = bool(normalized.get("human_approval_required", False))
    if normalized.get("status") == "success" and risk_level != "low":
        normalized["status"] = "pending"

    routing = normalized.get("routing_decision")
    if not isinstance(routing, dict):
        routing = {}
    fields = routing.get("fields")
    if not isinstance(fields, dict):
        fields = {}
    recommended_action = normalized.get("recommended_action")
    rerun_requested = bool(fields.get("rerun_requested", False)) or recommended_action == "targeted_rerun"
    rerun_target = fields.get("rerun_target")
    if recommended_action == "targeted_rerun":
        rerun_target = "analysis_engineer"
    fields.update(
        {
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "human_approval_required": human_approval_required,
            "rerun_requested": rerun_requested,
            "rerun_target": rerun_target,
            "code_fix_requested": bool(fields.get("code_fix_requested", False)) or recommended_action == "code_fix",
        }
    )
    actual_route = "human_approval_gate" if human_approval_required else "memory_report"
    proposed_follow_up_route = routing.get("proposed_follow_up_route") or actual_route
    if recommended_action == "targeted_rerun":
        proposed_follow_up_route = "analysis_engineer"
    routing.update(
        {
            "actual_route": actual_route,
            "requested_route": routing.get("requested_route") or actual_route,
            "proposed_follow_up_route": proposed_follow_up_route,
            "fields": fields,
        }
    )
    normalized["routing_decision"] = routing
    return normalized


def _run_provider_decision_coordinator(
    *,
    run_id: str,
    case_id: str,
    output_dir: str | Path,
    method_plan_path: str | Path | None,
    run_result_path: str | Path | None,
    scientific_review_report_path: str | Path | None,
    provider: LLMProvider,
) -> dict[str, Any]:
    local_context = _local_decision_context(
        run_id=run_id,
        case_id=case_id,
        method_plan_path=method_plan_path,
        run_result_path=run_result_path,
        scientific_review_report_path=scientific_review_report_path,
    )
    request = None
    try:
        request = build_decision_coordinator_request(
            run_id=run_id,
            case_id=case_id,
            method_plan_path=str(method_plan_path) if method_plan_path else None,
            run_result_path=str(run_result_path) if run_result_path else None,
            scientific_review_report_path=str(scientific_review_report_path) if scientific_review_report_path else None,
            method_plan_summary=local_context["method_plan_summary"],
            run_result_summary=local_context["run_result_summary"],
            scientific_review_summary=local_context["scientific_review_summary"],
        )
        response = provider.generate(request)
    except Exception as exc:
        decision_log = _provider_failure_decision_log(
            run_id=run_id,
            case_id=case_id,
            artifact=provider_exception_artifact(
                producer="decision_coordinator",
                run_id=run_id,
                case_id=case_id,
                code=getattr(exc, "code", "provider_call_failed"),
                message=str(exc),
            ),
        )
        decision_log_path = write_decision_log(output_dir, decision_log)
        write_llm_call_trace(
            output_dir=output_dir,
            agent="decision_coordinator",
            provider=provider,
            request=request,
            parsed_payload_path=decision_log_path,
            status="failed",
            error=decision_log,
        )
        return _decision_result(decision_log, decision_log_path)

    payload, parse_error = parse_json_object(
        response.content,
        producer="decision_coordinator",
        run_id=run_id,
        case_id=case_id,
    )
    if parse_error is not None:
        decision_log = _provider_failure_decision_log(run_id=run_id, case_id=case_id, artifact=parse_error)
        decision_log_path = write_decision_log(output_dir, decision_log)
        write_llm_call_trace(
            output_dir=output_dir,
            agent="decision_coordinator",
            provider=provider,
            request=request,
            response=response,
            parsed_payload_path=decision_log_path,
            status="failed",
            error=parse_error,
        )
        return _decision_result(decision_log, decision_log_path)

    assert payload is not None
    payload = _normalize_provider_decision_payload(payload)
    validation_errors = validate_decision_log_payload(payload, run_id=run_id, case_id=case_id)
    if validation_errors:
        decision_log = _provider_failure_decision_log(
            run_id=run_id,
            case_id=case_id,
            artifact=validation_error_artifact(
                producer="decision_coordinator",
                run_id=run_id,
                case_id=case_id,
                errors=validation_errors,
            ),
        )
        decision_log_path = write_decision_log(output_dir, decision_log)
        write_llm_call_trace(
            output_dir=output_dir,
            agent="decision_coordinator",
            provider=provider,
            request=request,
            response=response,
            parsed_payload_path=decision_log_path,
            status="failed",
            error=decision_log,
        )
        return _decision_result(decision_log, decision_log_path)

    payload.setdefault("risk_rubric", RISK_RUBRIC)
    decision_log = _apply_provider_safety_floor(provider_log=payload, local_context=local_context)
    decision_log_path = write_decision_log(output_dir, decision_log)
    write_llm_call_trace(
        output_dir=output_dir,
        agent="decision_coordinator",
        provider=provider,
        request=request,
        response=response,
        parsed_payload_path=decision_log_path,
        status=decision_log["status"],
    )
    return _decision_result(decision_log, decision_log_path)


def _decision_result(decision_log: dict[str, Any], decision_log_path: str) -> dict[str, Any]:
    routing_fields = decision_log.get("routing_decision", {}).get("fields", {})
    if not isinstance(routing_fields, dict):
        routing_fields = {}
    return {
        "status": decision_log["status"],
        "decision_log_path": decision_log_path,
        "decision_log": decision_log,
        "risk_level": decision_log["risk_level"],
        "recommended_action": decision_log["recommended_action"],
        "human_approval_required": decision_log["human_approval_required"],
        "rerun_requested": bool(routing_fields.get("rerun_requested", False)),
        "rerun_target": routing_fields.get("rerun_target"),
        "code_fix_requested": bool(routing_fields.get("code_fix_requested", False)),
    }


def run_decision_coordinator(
    *,
    run_id: str,
    case_id: str,
    output_dir: str | Path,
    method_plan_path: str | Path | None,
    run_result_path: str | Path | None,
    scientific_review_report_path: str | Path | None,
    provider: LLMProvider | None = None,
    provider_config_path: str | Path | None = None,
) -> dict[str, Any]:
    if provider is None and provider_config_path is not None:
        provider = create_provider_from_config_path(provider_config_path)
    if provider is not None:
        return _run_provider_decision_coordinator(
            run_id=run_id,
            case_id=case_id,
            output_dir=output_dir,
            method_plan_path=method_plan_path,
            run_result_path=run_result_path,
            scientific_review_report_path=scientific_review_report_path,
            provider=provider,
        )

    decision_log = _local_decision_context(
        run_id=run_id,
        case_id=case_id,
        method_plan_path=method_plan_path,
        run_result_path=run_result_path,
        scientific_review_report_path=scientific_review_report_path,
    )["decision_log"]
    decision_log_path = write_decision_log(output_dir, decision_log)
    return {
        "status": decision_log["status"],
        "decision_log_path": decision_log_path,
        "decision_log": decision_log,
        "risk_level": decision_log["risk_level"],
        "recommended_action": decision_log["recommended_action"],
        "human_approval_required": decision_log["human_approval_required"],
        "rerun_requested": decision_log["routing_decision"]["fields"]["rerun_requested"],
        "rerun_target": decision_log["routing_decision"]["fields"]["rerun_target"],
        "code_fix_requested": decision_log["routing_decision"]["fields"]["code_fix_requested"],
    }
