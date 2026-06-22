"""Deterministic Decision Coordinator Agent for Phase 6."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
    assert review is not None

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

    warnings = _review_warnings(review)
    severe_or_flagged = [
        warning
        for warning in warnings
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

    confidence = review.get("confidence")
    review_evidence = _as_list(review.get("evidence"))
    if warnings or confidence == "medium" or not review_evidence:
        reasons = []
        if warnings:
            reasons.append(
                _reason(
                    "non_severe_review_warning",
                    "Non-severe review warnings require pending or review-recommended handling.",
                    source="scientific_review_report",
                    field="warnings",
                    value=len(warnings),
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
        return "Decision Coordinator classified the run as low risk for mock-result acceptance."
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


def run_decision_coordinator(
    *,
    run_id: str,
    case_id: str,
    output_dir: str | Path,
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
    )
    review, review_artifact_evidence, review_errors = _read_json_artifact(
        scientific_review_report_path,
        artifact_name="scientific_review_report",
        run_id=run_id,
        case_id=case_id,
    )
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
    status = "success" if decision["risk_level"] == "low" else "pending"
    actual_route = "human_approval_gate" if decision["human_approval_required"] else "memory_report"
    decision_log = {
        **_base_artifact(run_id=run_id, case_id=case_id, status=status, summary=_summary(decision)),
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
    decision_log_path = write_decision_log(output_dir, decision_log)
    return {
        "status": status,
        "decision_log_path": decision_log_path,
        "decision_log": decision_log,
        "risk_level": decision["risk_level"],
        "recommended_action": decision["recommended_action"],
        "human_approval_required": decision["human_approval_required"],
        "rerun_requested": decision["rerun_requested"],
        "rerun_target": decision["rerun_target"],
        "code_fix_requested": decision["code_fix_requested"],
    }
