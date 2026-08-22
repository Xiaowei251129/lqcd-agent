"""Human Approval Gate packet and decision helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APPROVAL_PACKET_DIRNAME = "approval_packet"
APPROVAL_PACKET_FILENAME = "approval_packet.json"
APPROVAL_SUMMARY_FILENAME = "approval_summary.md"
HUMAN_DECISION_FILENAME = "07_human_decision.yaml"
APPROVAL_SCHEMA_VERSION = "0.2"
LEGACY_APPROVAL_SCHEMA_VERSION = "0.1"
_EXPECTED_ID_UNSET = object()

DECISION_ROUTE_TARGETS = {
    "approve_with_conditions": "memory_report",
    "approve_rerun": "analysis_engineer",
    "request_code_change": "codex_handoff",
    "reject_or_hold": "memory_report",
}

DECISION_OPTIONS = [
    {
        "decision": "approve_with_conditions",
        "route": "memory_report",
        "summary": "Allow reporting to continue with human-recorded conditions.",
    },
    {
        "decision": "approve_rerun",
        "route": "analysis_engineer",
        "summary": "Request a targeted rerun. Phase 7 records route intent only.",
    },
    {
        "decision": "request_code_change",
        "route": "codex_handoff",
        "summary": "Request an external code change before analysis continues.",
    },
    {
        "decision": "reject_or_hold",
        "route": "memory_report",
        "summary": "Hold or reject the result; accepted memory must not be written.",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def approval_packet_dir(output_dir: str | Path) -> Path:
    return Path(output_dir) / APPROVAL_PACKET_DIRNAME


def decision_route_target(decision: str | None) -> str | None:
    if not decision:
        return None
    return DECISION_ROUTE_TARGETS.get(decision)


def _read_json_object(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    json_path = Path(path)
    if not json_path.exists():
        return None
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _artifact_ref(name: str, path: str | None) -> dict[str, Any]:
    exists = bool(path and Path(path).exists())
    return {"name": name, "path": path, "exists": exists}


def _available_comparisons(state: dict[str, Any]) -> list[dict[str, Any]]:
    method_path = state.get("method_plan_path")
    run_path = state.get("run_result_path")
    review_path = state.get("scientific_review_report_path")
    decision_path = state.get("decision_log_path")
    return [
        {
            "name": "method_plan_vs_run_result",
            "status": "available" if method_path and run_path else "not_available",
            "artifacts": [
                _artifact_ref("method_plan", method_path),
                _artifact_ref("run_result", run_path),
            ],
        },
        {
            "name": "run_result_vs_scientific_review",
            "status": "available" if run_path and review_path else "not_available",
            "artifacts": [
                _artifact_ref("run_result", run_path),
                _artifact_ref("scientific_review_report", review_path),
            ],
        },
        {
            "name": "scientific_review_vs_decision_log",
            "status": "available" if review_path and decision_path else "not_available",
            "artifacts": [
                _artifact_ref("scientific_review_report", review_path),
                _artifact_ref("decision_log", decision_path),
            ],
        },
    ]


def _required_identity(state: dict[str, Any], field: str) -> str:
    value = state.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Approval projection requires {field} from the control plane.")
    return value


def build_approval_packet(state: dict[str, Any], human_decision_path: str) -> dict[str, Any]:
    cycle_id = _required_identity(state, "cycle_id")
    human_request_id = _required_identity(state, "active_human_request_id")
    requesting_attempt_id = _required_identity(state, "human_requesting_attempt_id")
    decision_log = _read_json_object(state.get("decision_log_path")) or {}
    risk_level = state.get("risk_level")
    recommended_action = state.get("recommended_action")
    summary = (
        f"Human approval is required for {risk_level} risk before accepted memory or "
        "accepted-result promotion."
    )
    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "run_id": state["run_id"],
        "case_id": state["case_id"],
        "cycle_id": cycle_id,
        "human_request_id": human_request_id,
        "requesting_attempt_id": requesting_attempt_id,
        "human_request_status": state.get("human_request_status"),
        "human_response_id": state.get("active_human_response_id"),
        "attempt_id": state.get("attempt_id"),
        "parent_attempt_id": state.get("parent_attempt_id"),
        "created_at": utc_now(),
        "producer": "human_approval_gate",
        "status": "pending",
        "summary": summary,
        "warnings": [],
        "errors": [],
        "requested_decision": {
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "human_approval_required": state.get("human_approval_required"),
        },
        "authorization_scope": state.get("human_request_authorization_scope") or {},
        "human_summary": summary,
        "method_and_run_context": {
            "method_plan_path": state.get("method_plan_path"),
            "run_result_path": state.get("run_result_path"),
            "analysis_outputs_dir": state.get("analysis_outputs_dir"),
            "decision_log_path": state.get("decision_log_path"),
        },
        "available_comparisons": _available_comparisons(state),
        "scientific_review_report": {
            "path": state.get("scientific_review_report_path"),
            "exists": bool(
                state.get("scientific_review_report_path")
                and Path(str(state["scientific_review_report_path"])).exists()
            ),
        },
        "ai_recommendation": {
            "recommended_action": recommended_action,
            "next_actions": decision_log.get("next_actions", []),
            "routing_decision": decision_log.get("routing_decision", {}),
        },
        "risk_rationale": decision_log.get("reasons", []),
        "decision_options": DECISION_OPTIONS,
        "human_decision_template_path": human_decision_path,
    }


def _summary_markdown(packet: dict[str, Any]) -> str:
    requested = packet["requested_decision"]
    options = "\n".join(
        f"- `{option['decision']}` -> `{option['route']}`: {option['summary']}"
        for option in packet["decision_options"]
    )
    return (
        "# Human Approval Packet\n\n"
        f"- run_id: {packet['run_id']}\n"
        f"- case_id: {packet['case_id']}\n"
        f"- cycle_id: {packet['cycle_id']}\n"
        f"- human_request_id: {packet['human_request_id']}\n"
        f"- requesting_attempt_id: {packet['requesting_attempt_id']}\n"
        f"- risk_level: {requested['risk_level']}\n"
        f"- recommended_action: {requested['recommended_action']}\n"
        f"- scientific_review_report: {packet['scientific_review_report']['path']}\n"
        f"- decision_template: {packet['human_decision_template_path']}\n\n"
        "## Decision Options\n\n"
        f"{options}\n"
    )


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _parse_yaml_scalar(value: str) -> Any:
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


def _template_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "run_id": state["run_id"],
        "case_id": state["case_id"],
        "cycle_id": _required_identity(state, "cycle_id"),
        "human_request_id": _required_identity(state, "active_human_request_id"),
        "requesting_attempt_id": _required_identity(state, "human_requesting_attempt_id"),
        "human_response_id": state.get("active_human_response_id"),
        "decision": None,
        "conditions": "",
        "reason": "",
        "decided_by": "",
        "decided_at": "",
    }


def _write_flat_yaml(path: Path, payload: dict[str, Any]) -> None:
    lines = [f"{key}: {_yaml_scalar(value)}" for key, value in payload.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_approval_packet(
    state: dict[str, Any],
    *,
    output_dir: str | Path | None = None,
) -> dict[str, str | None]:
    if not state.get("human_approval_required"):
        return {
            "approval_packet_dir": None,
            "approval_packet_path": None,
            "approval_summary_path": None,
            "human_decision_path": None,
        }

    packet_dir = approval_packet_dir(output_dir or state["output_dir"])
    packet_dir.mkdir(parents=True, exist_ok=True)
    human_decision_path = packet_dir / HUMAN_DECISION_FILENAME
    packet_path = packet_dir / APPROVAL_PACKET_FILENAME
    previous_packet = _read_json_object(packet_path)
    request_changed = bool(
        previous_packet
        and previous_packet.get("human_request_id") != state.get("active_human_request_id")
    )
    if not human_decision_path.exists() or request_changed:
        _write_flat_yaml(human_decision_path, _template_payload(state))

    packet = build_approval_packet(state, str(human_decision_path))
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path = packet_dir / APPROVAL_SUMMARY_FILENAME
    summary_path.write_text(_summary_markdown(packet), encoding="utf-8")
    return {
        "approval_packet_dir": str(packet_dir),
        "approval_packet_path": str(packet_path),
        "approval_summary_path": str(summary_path),
        "human_decision_path": str(human_decision_path),
    }


def read_flat_human_decision_yaml(path: str | Path) -> dict[str, Any]:
    decision_path = Path(path)
    payload: dict[str, Any] = {}
    for line_number, raw_line in enumerate(decision_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"line {line_number} is not valid flat decision YAML.")
        key, raw_value = line.split(":", 1)
        payload[key.strip()] = _parse_yaml_scalar(raw_value.strip())
    return payload


def _identity_error(
    *,
    field: str,
    value: Any,
    expected: Any,
    path: str | Path,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "field": field,
        "value": value,
        "expected": expected,
        "message": message or f"human decision {field} does not match the active request.",
        "path": str(path),
    }


def parse_human_decision(
    path: str | Path | None,
    *,
    run_id: str,
    case_id: str,
    cycle_id: str | None = None,
    human_request_id: str | None = None,
    requesting_attempt_id: str | None = None,
    human_response_id: str | None | object = _EXPECTED_ID_UNSET,
    legacy_import: bool = False,
    legacy_open_request_ids: list[str] | None = None,
) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {"status": "pending", "decision": None, "errors": []}

    try:
        payload = read_flat_human_decision_yaml(path)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "invalid",
            "decision": None,
            "errors": [{"field": "$", "message": str(exc), "path": str(path)}],
        }

    errors: list[dict[str, Any]] = []
    schema_version = payload.get("schema_version")
    if schema_version == LEGACY_APPROVAL_SCHEMA_VERSION:
        if not legacy_import:
            errors.append(
                _identity_error(
                    field="schema_version",
                    value=schema_version,
                    expected=APPROVAL_SCHEMA_VERSION,
                    path=path,
                    message="legacy human decision schema requires explicit compatibility import.",
                )
            )
        missing_binding = [
            field
            for field, value in {
                "cycle_id": cycle_id,
                "human_request_id": human_request_id,
                "requesting_attempt_id": requesting_attempt_id,
            }.items()
            if not isinstance(value, str) or not value
        ]
        if legacy_import and missing_binding:
            errors.append(
                _identity_error(
                    field="legacy_import",
                    value=missing_binding,
                    expected="one explicitly identified active Human Request",
                    path=path,
                    message="legacy import requires the caller to bind one active Human Request.",
                )
            )
        if legacy_import and not missing_binding and legacy_open_request_ids != [human_request_id]:
            errors.append(
                _identity_error(
                    field="legacy_open_request_ids",
                    value=legacy_open_request_ids,
                    expected=[human_request_id],
                    path=path,
                    message="legacy import requires exactly one matching open Human Request from the ledger.",
                )
            )
        if legacy_import and not missing_binding and not errors:
            payload = {
                **payload,
                "schema_version": APPROVAL_SCHEMA_VERSION,
                "imported_schema_version": LEGACY_APPROVAL_SCHEMA_VERSION,
                "cycle_id": cycle_id,
                "human_request_id": human_request_id,
                "requesting_attempt_id": requesting_attempt_id,
                "human_response_id": (
                    None if human_response_id is _EXPECTED_ID_UNSET else human_response_id
                ),
            }
    elif schema_version != APPROVAL_SCHEMA_VERSION:
        errors.append(
            _identity_error(
                field="schema_version",
                value=schema_version,
                expected=APPROVAL_SCHEMA_VERSION,
                path=path,
            )
        )

    for field, expected in {"run_id": run_id, "case_id": case_id}.items():
        value = payload.get(field)
        if value != expected:
            errors.append(
                _identity_error(
                    field=field,
                    value=value,
                    expected=expected,
                    path=path,
                    message=f"human decision {field} does not match the active run.",
                )
            )

    if payload.get("schema_version") == APPROVAL_SCHEMA_VERSION:
        for field in ("cycle_id", "human_request_id", "requesting_attempt_id"):
            value = payload.get(field)
            if not isinstance(value, str) or not value:
                errors.append(
                    _identity_error(
                        field=field,
                        value=value,
                        expected="non-empty control-plane identity",
                        path=path,
                    )
                )
        for field, expected in {
            "cycle_id": cycle_id,
            "human_request_id": human_request_id,
            "requesting_attempt_id": requesting_attempt_id,
        }.items():
            if expected is not None and payload.get(field) != expected:
                errors.append(
                    _identity_error(
                        field=field,
                        value=payload.get(field),
                        expected=expected,
                        path=path,
                    )
                )
        if (
            human_response_id is not _EXPECTED_ID_UNSET
            and payload.get("human_response_id") != human_response_id
        ):
            errors.append(
                _identity_error(
                    field="human_response_id",
                    value=payload.get("human_response_id"),
                    expected=human_response_id,
                    path=path,
                )
            )

    decision = payload.get("decision")
    if decision in {None, ""}:
        return {"status": "invalid" if errors else "pending", "decision": None, "errors": errors}
    if not isinstance(payload.get("human_response_id"), str) or not payload["human_response_id"]:
        errors.append(
            _identity_error(
                field="human_response_id",
                value=payload.get("human_response_id"),
                expected="runtime-allocated Human Response identity",
                path=path,
                message="a submitted human decision requires a runtime-allocated response identity.",
            )
        )
    if not isinstance(decision, str) or decision not in DECISION_ROUTE_TARGETS:
        errors.append(
            {
                "field": "decision",
                "value": decision,
                "expected": sorted(DECISION_ROUTE_TARGETS),
                "message": "human decision is not supported.",
                "path": str(path),
            }
        )
    if errors:
        return {"status": "invalid", "decision": None, "errors": errors}
    return {"status": "approved", "decision": decision, "payload": payload, "errors": []}
