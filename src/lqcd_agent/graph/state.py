"""State schema helpers for the mock LangGraph runtime."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict


Status = Literal["running", "success", "failed", "pending", "halted"]
ContextWindowStatus = Literal["normal", "near_limit", "summarized", "overflow_halt"]
AttemptStatus = Literal["scheduled", "running", "succeeded", "failed", "pending", "abandoned"]
AttemptKind = Literal[
    "method_planner",
    "legacy_codex_handoff",
    "code_agent",
    "analysis_engineer",
    "scientific_reviewer",
    "decision_coordinator",
    "human_gate",
    "memory_report",
]

ATTEMPT_KIND_BY_NODE: dict[str, AttemptKind] = {
    "method_planner": "method_planner",
    "codex_handoff": "legacy_codex_handoff",
    "code_agent": "code_agent",
    "analysis_engineer": "analysis_engineer",
    "scientific_reviewer": "scientific_reviewer",
    "decision_coordinator": "decision_coordinator",
    "human_approval_gate": "human_gate",
    "memory_report": "memory_report",
}

LONG_EVENT_LOG_LIMIT = 8
LONG_EVENT_TEXT_LIMIT = 240


class AnalysisState(TypedDict):
    run_id: str
    case_id: str
    user_goal: str
    case_config_path: str
    output_dir: str
    current_node: str
    status: Status
    llm_provider_config_path: str | None
    auto_codex_handoff: bool
    codex_bin: str
    codex_model: str | None
    codex_timeout_seconds: int
    verification_timeout_seconds: int
    force_codex_handoff: bool
    dry_run_codex: bool

    checkpoint_thread_id: str
    checkpoint_backend: str
    checkpoint_db_path: str | None

    parent_run_id: str | None
    cycle_id: str
    cycle_index: int
    parent_cycle_id: str | None
    attempt_id: str | None
    attempt_index: int
    parent_attempt_id: str | None
    attempt_kind: AttemptKind | None
    attempt_node: str | None
    attempt_trigger: str | None
    attempt_status: AttemptStatus | None
    inbound_transition_id: str | None
    committed_transition_id: str | None
    transition_index: int
    committed_route: str | None
    execution_history_path: str

    human_request_index: int
    human_response_index: int
    active_human_request_id: str | None
    human_requesting_attempt_id: str | None
    human_request_kind: str | None
    human_request_status: str | None
    human_request_authorization_scope: dict[str, Any] | None
    active_human_response_id: str | None
    human_response_status: str | None
    human_response_decision: str | None
    human_response_authorized_route: str | None
    human_response_authorized_transition_route: str | None
    human_response_authorized_transition_target: str | None
    human_response_validator_attempt_id: str | None
    human_response_consumer_attempt_id: str | None
    human_response_target_attempt_id: str | None

    context_policy_path: str | None
    context_summary_path: str | None
    event_log_summary: str | None
    context_window_status: ContextWindowStatus

    method_plan_path: str | None
    code_needed: bool
    coder_task_packet_path: str | None
    code_change_summary_path: str | None
    tests_status_path: str | None
    retry_count: int
    max_retry: int

    run_success: bool
    failure_type: str | None
    run_result_path: str | None
    analysis_outputs_dir: str | None

    scientific_review_report_path: str | None
    decision_log_path: str | None
    risk_level: str
    recommended_action: str | None
    rerun_requested: bool
    rerun_target: str | None
    code_fix_requested: bool

    human_approval_required: bool
    approval_packet_dir: str | None
    human_decision_path: str | None

    final_report_path: str | None
    memory_update_path: str | None
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    event_log: list[dict[str, Any]]
    route_decisions: list[dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_checkpoint_thread_id(case_id: str, run_id: str) -> str:
    return f"{case_id}:{run_id}"


def stable_cycle_id(cycle_index: int) -> str:
    return f"cycle_{cycle_index:04d}"


def stable_attempt_id(attempt_index: int) -> str:
    return f"attempt_{attempt_index:06d}"


def stable_transition_id(transition_index: int) -> str:
    return f"transition_{transition_index:06d}"


def stable_human_request_id(request_index: int) -> str:
    return f"human_request_{request_index:06d}"


def stable_human_response_id(response_index: int) -> str:
    return f"human_response_{response_index:06d}"


def canonical_attempt_kind(node_name: str) -> AttemptKind:
    try:
        return ATTEMPT_KIND_BY_NODE[node_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported graph node for Attempt identity: {node_name}") from exc


def _validate_attempt_kind(attempt_kind: str) -> AttemptKind:
    if attempt_kind not in set(ATTEMPT_KIND_BY_NODE.values()):
        raise ValueError(f"Unsupported Attempt kind: {attempt_kind}")
    return attempt_kind  # type: ignore[return-value]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _root_goal_reference(user_goal: str) -> dict[str, Any]:
    return {
        "kind": "state_field",
        "field": "user_goal",
        "sha256": _sha256_bytes(user_goal.encode("utf-8")),
    }


def _input_snapshot_reference(case_config_path: str) -> dict[str, Any]:
    path = Path(case_config_path)
    exists = path.is_file()
    return {
        "kind": "file",
        "path": case_config_path,
        "exists": exists,
        "sha256": _sha256_bytes(path.read_bytes()) if exists else None,
    }


def _read_execution_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid execution history JSON on line {line_number}: {path}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Execution history line {line_number} is not an object: {path}")
        records.append(record)
    return records


def _load_existing_execution_identity(
    path: Path,
    *,
    run_id: str,
    case_id: str,
    expected_run_record: dict[str, Any],
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    records = _read_execution_records(path)
    for record in records:
        if record.get("run_id") != run_id or record.get("case_id") != case_id:
            raise ValueError(f"Execution history identity does not match {case_id}/{run_id}: {path}")
    if not records:
        raise ValueError(f"Execution history is empty: {path}")
    run_records = [
        record
        for record in records
        if record.get("record_type") == "run" and record.get("event") == "created"
    ]
    if len(run_records) != 1:
        raise ValueError(f"Execution history must contain exactly one Run creation record: {path}")
    run_record = run_records[0]
    immutable_fields = (
        "parent_run_id",
        "creation_reason",
        "root_goal_reference",
        "input_snapshot_reference",
        "canonical_output_root",
        "checkpoint_thread_id",
    )
    for field in immutable_fields:
        if run_record.get(field) != expected_run_record.get(field):
            raise ValueError(f"Run identity field {field} does not match existing history: {path}")
    cycle_records = [record for record in records if record.get("record_type") == "cycle"]
    if not cycle_records:
        raise ValueError(f"Execution history does not contain a Cycle record: {path}")
    latest_cycle = max(cycle_records, key=lambda record: int(record.get("cycle_index", 0)))
    attempt_records = [record for record in records if record.get("record_type") == "attempt"]
    latest_attempt = (
        max(
            enumerate(attempt_records),
            key=lambda item: (int(item[1].get("attempt_index", 0)), item[0]),
        )[1]
        if attempt_records
        else None
    )
    human_request_records = [record for record in records if record.get("record_type") == "human_request"]
    human_response_records = [record for record in records if record.get("record_type") == "human_response"]
    transition_records = [record for record in records if record.get("record_type") == "transition"]
    latest_request = (
        max(
            enumerate(human_request_records),
            key=lambda item: (int(item[1].get("request_index", 0)), item[0]),
        )[1]
        if human_request_records
        else None
    )
    latest_response = (
        max(
            enumerate(
                [
                    record
                    for record in human_response_records
                    if latest_request
                    and record.get("human_request_id") == latest_request.get("human_request_id")
                ]
            ),
            key=lambda item: (int(item[1].get("response_index", 0)), item[0]),
        )[1]
        if latest_request
        and any(
            record.get("human_request_id") == latest_request.get("human_request_id")
            for record in human_response_records
        )
        else None
    )
    return {
        "parent_run_id": run_record.get("parent_run_id"),
        "cycle_id": str(latest_cycle["cycle_id"]),
        "cycle_index": int(latest_cycle["cycle_index"]),
        "parent_cycle_id": latest_cycle.get("parent_cycle_id"),
        "attempt_id": latest_attempt.get("attempt_id") if latest_attempt else None,
        "attempt_index": int(latest_attempt.get("attempt_index", 0)) if latest_attempt else 0,
        "parent_attempt_id": latest_attempt.get("parent_attempt_id") if latest_attempt else None,
        "attempt_kind": latest_attempt.get("attempt_kind") if latest_attempt else None,
        "attempt_node": latest_attempt.get("node_name") if latest_attempt else None,
        "attempt_trigger": latest_attempt.get("attempt_trigger") if latest_attempt else None,
        "attempt_status": latest_attempt.get("status") if latest_attempt else None,
        "inbound_transition_id": latest_attempt.get("inbound_transition_id") if latest_attempt else None,
        "attempt_input_references": latest_attempt.get("input_references", {}) if latest_attempt else {},
        "committed_transition_id": (
            transition_records[-1].get("transition_id") if transition_records else None
        ),
        "run_terminal": bool(
            transition_records
            and transition_records[-1].get("target_attempt_id") is None
            and transition_records[-1].get("route") in {"end", "__end__"}
            and any(
                record.get("attempt_id") == transition_records[-1].get("source_attempt_id")
                and record.get("attempt_kind") == "memory_report"
                and record.get("event") == "finished"
                for record in attempt_records
            )
        ),
        "transition_index": max(
            (
                int(record.get("transition_index", 0))
                for record in transition_records
            ),
            default=0,
        ),
        "human_request_index": max(
            (int(record.get("request_index", 0)) for record in records if record.get("record_type") == "human_request"),
            default=0,
        ),
        "human_response_index": max(
            (int(record.get("response_index", 0)) for record in records if record.get("record_type") == "human_response"),
            default=0,
        ),
        "active_human_request_id": latest_request.get("human_request_id") if latest_request else None,
        "human_requesting_attempt_id": latest_request.get("requesting_attempt_id") if latest_request else None,
        "human_request_kind": latest_request.get("request_kind") if latest_request else None,
        "human_request_status": latest_request.get("status") if latest_request else None,
        "human_request_authorization_scope": (
            latest_request.get("authorization_scope") if latest_request else None
        ),
        "active_human_response_id": latest_response.get("human_response_id") if latest_response else None,
        "human_response_status": latest_response.get("status") if latest_response else None,
        "human_response_decision": latest_response.get("decision") if latest_response else None,
        "human_response_authorized_route": (
            latest_response.get("authorized_route") if latest_response else None
        ),
        "human_response_authorized_transition_route": (
            latest_response.get("authorized_transition_route") if latest_response else None
        ),
        "human_response_authorized_transition_target": (
            latest_response.get("authorized_transition_target") if latest_response else None
        ),
        "human_response_validator_attempt_id": latest_response.get("validator_attempt_id") if latest_response else None,
        "human_response_consumer_attempt_id": latest_response.get("consumer_attempt_id") if latest_response else None,
        "human_response_target_attempt_id": latest_response.get("authorized_target_attempt_id") if latest_response else None,
        "records": records,
    }


def initialize_state(
    *,
    case_id: str,
    run_id: str,
    user_goal: str,
    case_config_path: str,
    output_dir: str,
    parent_run_id: str | None = None,
    run_creation_reason: str = "initial",
    checkpoint_backend: str = "memory",
    checkpoint_db_path: str | None = None,
    max_retry: int = 1,
    llm_provider_config_path: str | None = None,
    auto_codex_handoff: bool = False,
    codex_bin: str = "codex",
    codex_model: str | None = None,
    codex_timeout_seconds: int = 900,
    verification_timeout_seconds: int = 60,
    force_codex_handoff: bool = False,
    dry_run_codex: bool = False,
) -> AnalysisState:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    execution_history_path = output_path / "execution_history.jsonl"
    checkpoint_thread_id = stable_checkpoint_thread_id(case_id, run_id)
    run_record = {
        "schema_version": "0.2",
        "record_type": "run",
        "event": "created",
        "run_id": run_id,
        "case_id": case_id,
        "parent_run_id": parent_run_id,
        "creation_reason": run_creation_reason,
        "root_goal_reference": _root_goal_reference(user_goal),
        "input_snapshot_reference": _input_snapshot_reference(case_config_path),
        "canonical_output_root": str(output_path.resolve()),
        "checkpoint_thread_id": checkpoint_thread_id,
        "status": "running",
    }
    existing_identity = _load_existing_execution_identity(
        execution_history_path,
        run_id=run_id,
        case_id=case_id,
        expected_run_record=run_record,
    )
    identity = existing_identity or {
        "parent_run_id": parent_run_id,
        "cycle_id": stable_cycle_id(1),
        "cycle_index": 1,
        "parent_cycle_id": None,
        "attempt_id": None,
        "attempt_index": 0,
        "parent_attempt_id": None,
        "attempt_kind": None,
        "attempt_node": None,
        "attempt_trigger": None,
        "attempt_status": None,
        "inbound_transition_id": None,
        "attempt_input_references": {},
        "committed_transition_id": None,
        "run_terminal": False,
        "transition_index": 0,
        "human_request_index": 0,
        "human_response_index": 0,
        "active_human_request_id": None,
        "human_requesting_attempt_id": None,
        "human_request_kind": None,
        "human_request_status": None,
        "human_request_authorization_scope": None,
        "active_human_response_id": None,
        "human_response_status": None,
        "human_response_decision": None,
        "human_response_authorized_route": None,
        "human_response_authorized_transition_route": None,
        "human_response_authorized_transition_target": None,
        "human_response_validator_attempt_id": None,
        "human_response_consumer_attempt_id": None,
        "human_response_target_attempt_id": None,
    }
    state: AnalysisState = {
        "run_id": run_id,
        "case_id": case_id,
        "user_goal": user_goal,
        "case_config_path": case_config_path,
        "output_dir": str(output_path),
        "current_node": "START",
        "status": "running",
        "llm_provider_config_path": llm_provider_config_path,
        "auto_codex_handoff": auto_codex_handoff,
        "codex_bin": codex_bin,
        "codex_model": codex_model,
        "codex_timeout_seconds": codex_timeout_seconds,
        "verification_timeout_seconds": verification_timeout_seconds,
        "force_codex_handoff": force_codex_handoff,
        "dry_run_codex": dry_run_codex,
        "checkpoint_thread_id": checkpoint_thread_id,
        "checkpoint_backend": checkpoint_backend,
        "checkpoint_db_path": checkpoint_db_path,
        "parent_run_id": identity["parent_run_id"],
        "cycle_id": identity["cycle_id"],
        "cycle_index": identity["cycle_index"],
        "parent_cycle_id": identity["parent_cycle_id"],
        "attempt_id": identity["attempt_id"],
        "attempt_index": identity["attempt_index"],
        "parent_attempt_id": identity["parent_attempt_id"],
        "attempt_kind": identity["attempt_kind"],
        "attempt_node": identity["attempt_node"],
        "attempt_trigger": identity["attempt_trigger"],
        "attempt_status": identity["attempt_status"],
        "inbound_transition_id": identity["inbound_transition_id"],
        "committed_transition_id": identity["committed_transition_id"],
        "transition_index": identity["transition_index"],
        "committed_route": None,
        "execution_history_path": str(execution_history_path),
        "human_request_index": identity["human_request_index"],
        "human_response_index": identity["human_response_index"],
        "active_human_request_id": identity["active_human_request_id"],
        "human_requesting_attempt_id": identity["human_requesting_attempt_id"],
        "human_request_kind": identity["human_request_kind"],
        "human_request_status": identity["human_request_status"],
        "human_request_authorization_scope": identity["human_request_authorization_scope"],
        "active_human_response_id": identity["active_human_response_id"],
        "human_response_status": identity["human_response_status"],
        "human_response_decision": identity["human_response_decision"],
        "human_response_authorized_route": identity["human_response_authorized_route"],
        "human_response_authorized_transition_route": identity[
            "human_response_authorized_transition_route"
        ],
        "human_response_authorized_transition_target": identity[
            "human_response_authorized_transition_target"
        ],
        "human_response_validator_attempt_id": identity["human_response_validator_attempt_id"],
        "human_response_consumer_attempt_id": identity["human_response_consumer_attempt_id"],
        "human_response_target_attempt_id": identity["human_response_target_attempt_id"],
        "context_policy_path": None,
        "context_summary_path": None,
        "event_log_summary": None,
        "context_window_status": "normal",
        "method_plan_path": None,
        "code_needed": False,
        "coder_task_packet_path": None,
        "code_change_summary_path": None,
        "tests_status_path": None,
        "retry_count": 0,
        "max_retry": max_retry,
        "run_success": False,
        "failure_type": None,
        "run_result_path": None,
        "analysis_outputs_dir": None,
        "scientific_review_report_path": None,
        "decision_log_path": None,
        "risk_level": "unknown",
        "recommended_action": None,
        "rerun_requested": False,
        "rerun_target": None,
        "code_fix_requested": False,
        "human_approval_required": False,
        "approval_packet_dir": None,
        "human_decision_path": None,
        "final_report_path": None,
        "memory_update_path": None,
        "errors": [],
        "warnings": [],
        "event_log": [
            {
                "created_at": utc_now(),
                "kind": "state_initialized",
                "node": "START",
                "summary": "Initialized mock graph state.",
            }
        ],
        "route_decisions": [],
    }
    if existing_identity is None:
        _append_record(state, {**run_record, "created_at": utc_now()})
        _append_cycle_record(
            state,
            event="created",
            status="active",
            trigger_reason="initial",
            created_by_attempt_id=None,
        )
        transition_index = state["transition_index"] + 1
        transition_id = stable_transition_id(transition_index)
        state = allocate_attempt(
            state,
            node_name="method_planner",
            attempt_kind="method_planner",
            trigger_reason="initial",
            parent_attempt_id=None,
            inbound_transition_id=transition_id,
        )
        state = _record_committed_transition(
            state,
            transition_id=transition_id,
            transition_index=transition_index,
            source_node="START",
            source_cycle_id=None,
            source_attempt_id=None,
            route="method_planner",
            target_node="method_planner",
            reason="Initialized the Run with a preallocated Planner Attempt.",
            fields={"trigger": "initial"},
            evidence_references={},
            trigger_reason="initial",
            state_updates={},
        )
    elif state["attempt_status"] == "scheduled":
        if state["attempt_node"] != "method_planner":
            raise ValueError("A scheduled non-Planner Attempt requires checkpoint resume defined by A04.")
        state["committed_route"] = "method_planner"
    elif state["attempt_status"] == "running":
        raise ValueError("A running Attempt requires checkpoint recovery defined by A04.")
    elif identity["run_terminal"]:
        raise ValueError("A terminal Run cannot be re-entered; replay or fork is defined by A04.")
    else:
        transition_index = state["transition_index"] + 1
        transition_id = stable_transition_id(transition_index)
        state = allocate_attempt(
            state,
            node_name="method_planner",
            attempt_kind="method_planner",
            trigger_reason="legacy_reentry",
            parent_attempt_id=state.get("attempt_id"),
            inbound_transition_id=transition_id,
        )
        state = _record_committed_transition(
            state,
            transition_id=transition_id,
            transition_index=transition_index,
            source_node="START",
            source_cycle_id=state["cycle_id"],
            source_attempt_id=None,
            route="method_planner",
            target_node="method_planner",
            reason="Legacy incomplete-Run re-entry scheduled a new Planner Attempt.",
            fields={
                "trigger": "legacy_reentry",
                "prior_attempt_id": state.get("parent_attempt_id"),
            },
            evidence_references={},
            trigger_reason="legacy_reentry",
            state_updates={},
        )
    save_graph_state(state)
    return state


def _identity_fields(state: AnalysisState) -> dict[str, Any]:
    return {
        "run_id": state["run_id"],
        "case_id": state["case_id"],
        "parent_run_id": state.get("parent_run_id"),
        "cycle_id": state["cycle_id"],
        "cycle_index": state["cycle_index"],
        "parent_cycle_id": state.get("parent_cycle_id"),
        "attempt_id": state.get("attempt_id"),
        "attempt_index": state["attempt_index"],
        "parent_attempt_id": state.get("parent_attempt_id"),
        "attempt_kind": state.get("attempt_kind"),
        "attempt_node": state.get("attempt_node"),
        "attempt_trigger": state.get("attempt_trigger"),
        "inbound_transition_id": state.get("inbound_transition_id"),
        "committed_transition_id": state.get("committed_transition_id"),
    }


def _append_record(state: AnalysisState, record: dict[str, Any]) -> None:
    path = Path(state["execution_history_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _append_cycle_record(
    state: AnalysisState,
    *,
    event: str,
    status: str,
    trigger_reason: str,
    created_by_attempt_id: str | None,
) -> None:
    _append_record(
        state,
        {
            "schema_version": "0.2",
            "record_type": "cycle",
            "event": event,
            "run_id": state["run_id"],
            "case_id": state["case_id"],
            "cycle_id": state["cycle_id"],
            "cycle_index": state["cycle_index"],
            "parent_cycle_id": state.get("parent_cycle_id"),
            "trigger_reason": trigger_reason,
            "created_by_attempt_id": created_by_attempt_id,
            "status": status,
            "created_at": utc_now(),
        },
    )


def _append_attempt_record(
    state: AnalysisState,
    *,
    event: str,
    status: AttemptStatus,
    input_references: dict[str, Any] | None = None,
    output_references: dict[str, Any] | None = None,
    error: dict[str, str] | None = None,
) -> None:
    _append_record(
        state,
        {
            "schema_version": "0.2",
            "record_type": "attempt",
            "event": event,
            "run_id": state["run_id"],
            "case_id": state["case_id"],
            "cycle_id": state["cycle_id"],
            "cycle_index": state["cycle_index"],
            "attempt_id": state["attempt_id"],
            "attempt_index": state["attempt_index"],
            "parent_attempt_id": state.get("parent_attempt_id"),
            "attempt_kind": state["attempt_kind"],
            "node_name": state["attempt_node"],
            "attempt_trigger": state.get("attempt_trigger"),
            "inbound_transition_id": state.get("inbound_transition_id"),
            "status": status,
            "created_at": utc_now(),
            "input_references": input_references or {},
            "output_references": output_references or {},
            "error": error,
        },
    )


def create_human_request(
    state: AnalysisState,
    *,
    request_kind: str,
    requesting_attempt_id: str,
    authorization_scope: dict[str, Any],
) -> AnalysisState:
    _assert_human_request_head(state)
    if request_kind not in {"clarification", "approval", "external_action"}:
        raise ValueError(f"Unsupported human request kind: {request_kind}")
    if state.get("active_human_request_id") and state.get("human_request_status") == "open":
        raise ValueError(f"Human request {state['active_human_request_id']} is still active.")
    updated = dict(state)
    updated["human_request_index"] = state["human_request_index"] + 1
    updated["active_human_request_id"] = stable_human_request_id(updated["human_request_index"])
    updated["human_requesting_attempt_id"] = requesting_attempt_id
    updated["human_request_kind"] = request_kind
    updated["human_request_status"] = "open"
    updated["human_request_authorization_scope"] = dict(authorization_scope)
    updated["active_human_response_id"] = None
    updated["human_response_status"] = None
    updated["human_response_decision"] = None
    updated["human_response_authorized_route"] = None
    updated["human_response_authorized_transition_route"] = None
    updated["human_response_authorized_transition_target"] = None
    updated["human_response_validator_attempt_id"] = None
    updated["human_response_consumer_attempt_id"] = None
    updated["human_response_target_attempt_id"] = None
    _append_record(
        updated,
        {
            "schema_version": "0.2",
            "record_type": "human_request",
            "event": "created",
            "run_id": updated["run_id"],
            "case_id": updated["case_id"],
            "cycle_id": updated["cycle_id"],
            "human_request_id": updated["active_human_request_id"],
            "request_index": updated["human_request_index"],
            "request_kind": request_kind,
            "requesting_attempt_id": requesting_attempt_id,
            "authorization_scope": authorization_scope,
            "packet_reference": None,
            "status": "open",
            "created_at": utc_now(),
        },
    )
    append_event(
        updated,
        node="decision_coordinator",
        kind="human_request_created",
        summary=f"Created {updated['active_human_request_id']} for {request_kind}.",
        human_request_id=updated["active_human_request_id"],
    )
    return updated


def record_human_request_packet(state: AnalysisState, *, packet_reference: str) -> AnalysisState:
    request_id = state.get("active_human_request_id")
    if not request_id:
        raise ValueError("Cannot record a human request packet without an active request.")
    _active_human_request_records(state)
    updated = dict(state)
    _append_record(
        updated,
        {
            "schema_version": "0.2",
            "record_type": "human_request",
            "event": "packet_written",
            "run_id": updated["run_id"],
            "case_id": updated["case_id"],
            "cycle_id": updated["cycle_id"],
            "human_request_id": request_id,
            "request_index": updated["human_request_index"],
            "request_kind": updated.get("human_request_kind"),
            "requesting_attempt_id": updated.get("human_requesting_attempt_id"),
            "authorization_scope": updated.get("human_request_authorization_scope") or {},
            "packet_reference": packet_reference,
            "status": "open",
            "created_at": utc_now(),
        },
    )
    return updated


def _active_human_request_records(
    state: AnalysisState,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _assert_human_request_head(state)
    request_id = state.get("active_human_request_id")
    records = [
        record
        for record in _read_execution_records(Path(state["execution_history_path"]))
        if record.get("record_type") == "human_request"
        and record.get("human_request_id") == request_id
    ]
    created = [record for record in records if record.get("event") == "created"]
    if len(created) != 1 or not records:
        raise ValueError(f"Human request {request_id} does not have one authoritative creation record.")
    authoritative = created[0]
    latest = records[-1]
    expected_state = {
        "cycle_id": authoritative.get("cycle_id"),
        "active_human_request_id": authoritative.get("human_request_id"),
        "human_request_index": authoritative.get("request_index"),
        "human_requesting_attempt_id": authoritative.get("requesting_attempt_id"),
        "human_request_kind": authoritative.get("request_kind"),
        "human_request_authorization_scope": authoritative.get("authorization_scope"),
        "human_request_status": latest.get("status"),
    }
    mismatches = [field for field, value in expected_state.items() if state.get(field) != value]
    if mismatches:
        raise ValueError(f"Active Human Request state disagrees with the execution ledger: {mismatches}")
    return authoritative, latest


def _assert_human_request_head(state: AnalysisState) -> None:
    records = [
        record
        for record in _read_execution_records(Path(state["execution_history_path"]))
        if record.get("record_type") == "human_request"
    ]
    if not records:
        if state.get("human_request_index") != 0 or state.get("active_human_request_id") is not None:
            raise ValueError("Human Request state has no matching execution ledger history.")
        return
    max_index = max(int(record.get("request_index", 0)) for record in records)
    latest_records = [record for record in records if int(record.get("request_index", 0)) == max_index]
    latest = latest_records[-1]
    if (
        state.get("human_request_index") != max_index
        or state.get("active_human_request_id") != latest.get("human_request_id")
        or state.get("human_request_status") != latest.get("status")
    ):
        raise ValueError("Human Request state is not the latest execution ledger head.")


def _assert_human_response_counter_current(state: AnalysisState) -> None:
    records = [
        record
        for record in _read_execution_records(Path(state["execution_history_path"]))
        if record.get("record_type") == "human_response"
    ]
    max_index = max((int(record.get("response_index", 0)) for record in records), default=0)
    if state.get("human_response_index") != max_index:
        raise ValueError("Human Response counter is not the latest execution ledger head.")


def _active_human_response_record(state: AnalysisState) -> dict[str, Any]:
    _assert_human_response_counter_current(state)
    response_id = state.get("active_human_response_id")
    records = [
        record
        for record in _read_execution_records(Path(state["execution_history_path"]))
        if record.get("record_type") == "human_response"
        and record.get("human_response_id") == response_id
    ]
    if not records:
        raise ValueError(f"Human response {response_id} is not recorded in the execution ledger.")
    latest = records[-1]
    expected_state = {
        "human_request_id": state.get("active_human_request_id"),
        "status": state.get("human_response_status"),
        "response_index": state.get("human_response_index"),
        "decision": state.get("human_response_decision"),
        "authorized_route": state.get("human_response_authorized_route"),
        "authorized_transition_route": state.get(
            "human_response_authorized_transition_route"
        ),
        "authorized_transition_target": state.get(
            "human_response_authorized_transition_target"
        ),
    }
    if any(latest.get(field) != value for field, value in expected_state.items()):
        raise ValueError("Active Human Response state disagrees with the execution ledger.")
    return latest


def submit_human_response(
    state: AnalysisState,
    *,
    payload: dict[str, Any],
    payload_reference: str,
) -> AnalysisState:
    request_id = state.get("active_human_request_id")
    if not request_id or state.get("human_request_status") != "open":
        raise ValueError("No active human request is available for a response.")
    _active_human_request_records(state)
    _assert_human_response_counter_current(state)
    payload_request_id = payload.get("human_request_id")
    if payload_request_id is not None and payload_request_id != request_id:
        raise ValueError("Human response payload does not match the active Human Request.")
    if state.get("human_response_status") in {"submitted", "validated", "consumed"}:
        raise ValueError(f"Human request {request_id} already has an active or consumed response.")
    updated = dict(state)
    updated["human_response_index"] = state["human_response_index"] + 1
    updated["active_human_response_id"] = stable_human_response_id(updated["human_response_index"])
    updated["human_response_status"] = "submitted"
    updated["human_response_decision"] = None
    updated["human_response_authorized_route"] = None
    updated["human_response_authorized_transition_route"] = None
    updated["human_response_authorized_transition_target"] = None
    updated["human_response_validator_attempt_id"] = None
    updated["human_response_consumer_attempt_id"] = None
    updated["human_response_target_attempt_id"] = None
    payload_hash = _sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))
    _append_record(
        updated,
        {
            "schema_version": "0.2",
            "record_type": "human_response",
            "event": "submitted",
            "run_id": updated["run_id"],
            "case_id": updated["case_id"],
            "cycle_id": updated["cycle_id"],
            "human_request_id": request_id,
            "human_response_id": updated["active_human_response_id"],
            "response_index": updated["human_response_index"],
            "payload_reference": payload_reference,
            "payload_snapshot": payload,
            "payload_sha256": payload_hash,
            "validator_attempt_id": None,
            "consumer_attempt_id": None,
            "authorized_target_attempt_id": None,
            "decision": None,
            "authorized_route": None,
            "authorized_transition_route": None,
            "authorized_transition_target": None,
            "status": "submitted",
            "created_at": utc_now(),
        },
    )
    append_event(
        updated,
        node="HUMAN_RESPONSE",
        kind="human_response_submitted",
        summary=f"Submitted {updated['active_human_response_id']} for {request_id}.",
        human_request_id=request_id,
        human_response_id=updated["active_human_response_id"],
    )
    save_graph_state(updated)
    return updated


def validate_human_response(
    state: AnalysisState,
    *,
    validator_attempt_id: str,
    valid: bool,
    decision_payload: dict[str, Any] | None = None,
    authorized_route: str | None = None,
    error: str | None = None,
) -> AnalysisState:
    response_id = state.get("active_human_response_id")
    if not response_id or state.get("human_response_status") != "submitted":
        raise ValueError("No submitted human response is available for validation.")
    _active_human_request_records(state)
    submitted_record = _active_human_response_record(state)
    if validator_attempt_id != state.get("attempt_id"):
        raise ValueError("The validator Attempt does not match the current Human Gate Attempt.")
    if (
        state.get("attempt_status") != "running"
        or state.get("attempt_kind") != "human_gate"
        or canonical_attempt_kind(str(state.get("attempt_node"))) != "human_gate"
    ):
        raise ValueError("A Human Response can only be validated by the running Human Gate Attempt.")
    validator_record = _latest_attempt_lifecycle_record(state, validator_attempt_id)
    if validator_record is None or validator_record.get("event") != "started":
        raise ValueError("The Human Gate validator does not have a running Attempt lifecycle record.")
    scope = state.get("human_request_authorization_scope") or {}
    decision = decision_payload.get("decision") if decision_payload else None
    authorized_transition_route = None
    authorized_transition_target = None
    validation_errors: list[str] = []
    if valid:
        submitted_payload = submitted_record.get("payload_snapshot")
        if not isinstance(submitted_payload, dict) or not isinstance(decision, str):
            validation_errors.append("Human response payload does not contain a typed decision.")
        else:
            for field in ("decision", "conditions", "reason", "decided_by"):
                if field in submitted_payload and submitted_payload.get(field) != decision_payload.get(field):
                    validation_errors.append(
                        f"Human decision field {field} does not match the submitted response payload."
                    )
        if decision not in scope.get("allowed_decisions", []):
            validation_errors.append(f"Human decision {decision!r} is outside the authorization scope.")
        if not authorized_route or authorized_route not in scope.get("allowed_target_nodes", []):
            validation_errors.append(
                f"Human response target {authorized_route!r} is outside the authorization scope."
            )
        authorized_transition_route = scope.get("decision_transition_routes", {}).get(decision)
        authorized_transition_target = scope.get("decision_transition_targets", {}).get(decision)
        if not isinstance(authorized_transition_route, str) or not isinstance(
            authorized_transition_target,
            str,
        ):
            validation_errors.append(
                f"Human decision {decision!r} does not have one exact authorized transition."
            )
    if validation_errors:
        valid = False
        error = " ".join(validation_errors)
    updated = dict(state)
    status = "validated" if valid else "invalid"
    updated["human_response_status"] = status
    updated["human_response_decision"] = decision if valid else None
    updated["human_response_authorized_route"] = authorized_route if valid else None
    updated["human_response_authorized_transition_route"] = (
        authorized_transition_route if valid else None
    )
    updated["human_response_authorized_transition_target"] = (
        authorized_transition_target if valid else None
    )
    updated["human_response_validator_attempt_id"] = validator_attempt_id
    _append_record(
        updated,
        {
            "schema_version": "0.2",
            "record_type": "human_response",
            "event": status,
            "run_id": updated["run_id"],
            "case_id": updated["case_id"],
            "cycle_id": updated["cycle_id"],
            "human_request_id": updated["active_human_request_id"],
            "human_response_id": response_id,
            "response_index": updated["human_response_index"],
            "payload_reference": updated.get("human_decision_path"),
            "payload_sha256": None,
            "validator_attempt_id": validator_attempt_id,
            "consumer_attempt_id": None,
            "authorized_target_attempt_id": None,
            "decision": decision if valid else None,
            "authorized_route": authorized_route if valid else None,
            "authorized_transition_route": authorized_transition_route if valid else None,
            "authorized_transition_target": authorized_transition_target if valid else None,
            "status": status,
            "error": error,
            "created_at": utc_now(),
        },
    )
    return updated


def consume_human_response(
    state: AnalysisState,
    *,
    consumer_attempt_id: str,
    authorized_target_attempt_id: str | None,
    transition_route: str,
    transition_target: str,
) -> AnalysisState:
    response_id = state.get("active_human_response_id")
    if not response_id or state.get("human_response_status") != "validated":
        raise ValueError("Only a validated, unconsumed human response can be consumed.")
    _active_human_request_records(state)
    _active_human_response_record(state)
    if (
        transition_route != state.get("human_response_authorized_transition_route")
        or transition_target != state.get("human_response_authorized_transition_target")
    ):
        raise ValueError("Human Response cannot be consumed by a transition outside its exact authorization.")
    updated = dict(state)
    updated["human_response_status"] = "consumed"
    updated["human_response_consumer_attempt_id"] = consumer_attempt_id
    updated["human_response_target_attempt_id"] = authorized_target_attempt_id
    updated["human_request_status"] = "satisfied"
    _append_record(
        updated,
        {
            "schema_version": "0.2",
            "record_type": "human_response",
            "event": "consumed",
            "run_id": updated["run_id"],
            "case_id": updated["case_id"],
            "cycle_id": updated["cycle_id"],
            "human_request_id": updated["active_human_request_id"],
            "human_response_id": response_id,
            "response_index": updated["human_response_index"],
            "payload_reference": updated.get("human_decision_path"),
            "payload_sha256": None,
            "validator_attempt_id": state.get("human_response_validator_attempt_id"),
            "consumer_attempt_id": consumer_attempt_id,
            "authorized_target_attempt_id": authorized_target_attempt_id,
            "decision": state.get("human_response_decision"),
            "authorized_route": state.get("human_response_authorized_route"),
            "authorized_transition_route": transition_route,
            "authorized_transition_target": transition_target,
            "status": "consumed",
            "created_at": utc_now(),
        },
    )
    _append_record(
        updated,
        {
            "schema_version": "0.2",
            "record_type": "human_request",
            "event": "satisfied",
            "run_id": updated["run_id"],
            "case_id": updated["case_id"],
            "cycle_id": updated["cycle_id"],
            "human_request_id": updated["active_human_request_id"],
            "request_index": updated["human_request_index"],
            "request_kind": updated.get("human_request_kind"),
            "requesting_attempt_id": updated.get("human_requesting_attempt_id"),
            "authorization_scope": updated.get("human_request_authorization_scope") or {},
            "packet_reference": updated.get("approval_packet_dir"),
            "response_id": response_id,
            "status": "satisfied",
            "created_at": utc_now(),
        },
    )
    return updated


def _artifact_references(state: AnalysisState) -> dict[str, str]:
    references: dict[str, str] = {}
    for field in (
        "method_plan_path",
        "coder_task_packet_path",
        "code_change_summary_path",
        "tests_status_path",
        "run_result_path",
        "analysis_outputs_dir",
        "scientific_review_report_path",
        "decision_log_path",
        "approval_packet_dir",
        "human_decision_path",
        "memory_update_path",
        "final_report_path",
    ):
        value = state.get(field)
        if value:
            references[field] = str(value)
    return references


def _assert_allocation_counter_current(
    state: AnalysisState,
    *,
    record_type: str,
    record_index_field: str,
    state_index_field: str,
) -> None:
    ledger_index = max(
        (
            int(record.get(record_index_field, 0))
            for record in _read_execution_records(Path(state["execution_history_path"]))
            if record.get("record_type") == record_type
        ),
        default=0,
    )
    if state.get(state_index_field) != ledger_index:
        raise ValueError(f"{record_type.title()} counter is not the latest execution ledger head.")


def start_new_cycle(
    state: AnalysisState,
    *,
    trigger_reason: str,
    created_by_attempt_id: str | None = None,
) -> AnalysisState:
    _assert_allocation_counter_current(
        state,
        record_type="cycle",
        record_index_field="cycle_index",
        state_index_field="cycle_index",
    )
    updated = dict(state)
    previous_cycle_id = state["cycle_id"]
    updated["cycle_index"] = state["cycle_index"] + 1
    updated["parent_cycle_id"] = previous_cycle_id
    updated["cycle_id"] = stable_cycle_id(updated["cycle_index"])
    _append_cycle_record(
        updated,
        event="created",
        status="active",
        trigger_reason=trigger_reason,
        created_by_attempt_id=created_by_attempt_id or state.get("attempt_id"),
    )
    updated["event_log"].append(
        {
            "created_at": utc_now(),
            "node": "decision_coordinator" if created_by_attempt_id else "START",
            "kind": "cycle_created",
            "summary": f"Created {updated['cycle_id']} for {trigger_reason}.",
            "run_id": updated["run_id"],
            "case_id": updated["case_id"],
            "cycle_id": updated["cycle_id"],
            "parent_cycle_id": updated.get("parent_cycle_id"),
            "created_by_attempt_id": created_by_attempt_id,
            "trigger_reason": trigger_reason,
        }
    )
    return updated


def allocate_attempt(
    state: AnalysisState,
    *,
    node_name: str,
    attempt_kind: str,
    trigger_reason: str,
    parent_attempt_id: str | None,
    new_cycle: bool = False,
    inbound_transition_id: str | None = None,
) -> AnalysisState:
    _assert_allocation_counter_current(
        state,
        record_type="attempt",
        record_index_field="attempt_index",
        state_index_field="attempt_index",
    )
    validated_kind = _validate_attempt_kind(attempt_kind)
    expected_kind = canonical_attempt_kind(node_name)
    if validated_kind != expected_kind:
        raise ValueError(
            f"Attempt kind {validated_kind} does not match graph node {node_name} ({expected_kind})."
        )
    if state.get("attempt_status") in {"scheduled", "running"}:
        raise ValueError(f"Cannot allocate a new Attempt while {state.get('attempt_id')} is active.")
    input_references = _artifact_references(state)
    updated = (
        start_new_cycle(
            state,
            trigger_reason=trigger_reason,
            created_by_attempt_id=parent_attempt_id,
        )
        if new_cycle
        else dict(state)
    )
    updated["attempt_index"] = state["attempt_index"] + 1
    updated["parent_attempt_id"] = parent_attempt_id
    updated["attempt_id"] = stable_attempt_id(updated["attempt_index"])
    updated["attempt_kind"] = validated_kind
    updated["attempt_node"] = node_name
    updated["attempt_trigger"] = trigger_reason
    updated["attempt_status"] = "scheduled"
    updated["inbound_transition_id"] = inbound_transition_id
    updated["current_node"] = node_name
    _append_attempt_record(
        updated,
        event="scheduled",
        status="scheduled",
        input_references=input_references,
    )
    updated["event_log"].append(
        {
            "created_at": utc_now(),
            "node": node_name,
            "kind": "attempt_scheduled",
            "summary": f"Scheduled {updated['attempt_id']} for {validated_kind}.",
            **_identity_fields(updated),
        }
    )
    return updated


def _find_committed_transition(
    state: AnalysisState,
    transition_id: str,
) -> dict[str, Any] | None:
    matches = [
        record
        for record in _read_execution_records(Path(state["execution_history_path"]))
        if record.get("record_type") == "transition"
        and record.get("event") == "committed"
        and record.get("transition_id") == transition_id
    ]
    if len(matches) > 1:
        raise ValueError(f"Transition {transition_id} has duplicate committed records.")
    return matches[0] if matches else None


def _latest_attempt_lifecycle_record(
    state: AnalysisState,
    attempt_id: str,
) -> dict[str, Any] | None:
    records = [
        record
        for record in _read_execution_records(Path(state["execution_history_path"]))
        if record.get("record_type") == "attempt" and record.get("attempt_id") == attempt_id
    ]
    return records[-1] if records else None


def start_attempt(
    state: AnalysisState,
    *,
    node_name: str,
    attempt_kind: str,
) -> AnalysisState:
    validated_kind = _validate_attempt_kind(attempt_kind)
    expected_kind = canonical_attempt_kind(node_name)
    if validated_kind != expected_kind:
        raise ValueError(
            f"Attempt kind {validated_kind} does not match graph node {node_name} ({expected_kind})."
        )
    if state.get("attempt_status") != "scheduled":
        raise ValueError(f"Attempt {state.get('attempt_id')} is not scheduled.")
    if state.get("attempt_node") != node_name or state.get("attempt_kind") != validated_kind:
        raise ValueError(
            f"Scheduled Attempt {state.get('attempt_id')} does not match {node_name}/{validated_kind}."
        )
    attempt_id = state.get("attempt_id")
    latest_lifecycle = _latest_attempt_lifecycle_record(state, str(attempt_id))
    if latest_lifecycle is None or latest_lifecycle.get("event") != "scheduled":
        raise ValueError(f"Attempt {attempt_id} is not the latest scheduled lifecycle record.")
    inbound_transition_id = state.get("inbound_transition_id")
    if not inbound_transition_id:
        raise ValueError(f"Scheduled Attempt {state.get('attempt_id')} has no committed inbound Transition.")
    transition = _find_committed_transition(state, inbound_transition_id)
    if transition is None:
        raise ValueError(f"Inbound Transition {inbound_transition_id} is not committed.")
    expected_target = (
        transition.get("target_attempt_id"),
        transition.get("target_node"),
        transition.get("target_attempt_kind"),
        transition.get("target_cycle_id"),
    )
    actual_target = (
        state.get("attempt_id"),
        node_name,
        validated_kind,
        state.get("cycle_id"),
    )
    if expected_target != actual_target:
        raise ValueError(
            f"Inbound Transition {inbound_transition_id} target does not match scheduled Attempt "
            f"{state.get('attempt_id')}."
        )
    updated = dict(state)
    updated["attempt_status"] = "running"
    _append_attempt_record(
        updated,
        event="started",
        status="running",
        input_references=_artifact_references(state),
    )
    append_event(
        updated,
        node=node_name,
        kind="attempt_started",
        summary=f"Started {updated['attempt_id']} for {validated_kind}.",
    )
    save_graph_state(updated)
    return updated


_CONTROL_PLANE_IDENTITY_FIELDS = (
    "run_id",
    "case_id",
    "user_goal",
    "case_config_path",
    "output_dir",
    "checkpoint_thread_id",
    "checkpoint_backend",
    "checkpoint_db_path",
    "parent_run_id",
    "cycle_id",
    "cycle_index",
    "parent_cycle_id",
    "attempt_id",
    "attempt_index",
    "parent_attempt_id",
    "attempt_kind",
    "attempt_node",
    "attempt_trigger",
    "attempt_status",
    "current_node",
    "inbound_transition_id",
    "committed_transition_id",
    "transition_index",
    "committed_route",
    "execution_history_path",
)

_HUMAN_CONTROL_FIELDS = (
    "human_request_index",
    "human_response_index",
    "active_human_request_id",
    "human_requesting_attempt_id",
    "human_request_kind",
    "human_request_status",
    "human_request_authorization_scope",
    "active_human_response_id",
    "human_response_status",
    "human_response_decision",
    "human_response_authorized_route",
    "human_response_authorized_transition_route",
    "human_response_authorized_transition_target",
    "human_response_validator_attempt_id",
    "human_response_consumer_attempt_id",
    "human_response_target_attempt_id",
)


def _validate_node_identity_envelope(
    active: AnalysisState,
    result: AnalysisState,
) -> None:
    mismatches = [
        field
        for field in _CONTROL_PLANE_IDENTITY_FIELDS
        if result.get(field) != active.get(field)
    ]
    human_mismatches = [
        field
        for field in _HUMAN_CONTROL_FIELDS
        if result.get(field) != active.get(field)
    ]
    if active.get("attempt_kind") == "human_gate":
        allowed_gate_changes = {
            "human_response_status",
            "human_response_decision",
            "human_response_authorized_route",
            "human_response_authorized_transition_route",
            "human_response_authorized_transition_target",
            "human_response_validator_attempt_id",
        }
        unexpected_human_changes = set(human_mismatches).difference(allowed_gate_changes)
        response_changed = bool(set(human_mismatches).intersection(allowed_gate_changes))
        response_status = result.get("human_response_status")
        valid_gate_validation = active.get("human_response_status") == "submitted" and (
            (
                response_status == "validated"
                and all(
                    isinstance(result.get(field), str) and result.get(field)
                    for field in (
                        "human_response_decision",
                        "human_response_authorized_route",
                        "human_response_authorized_transition_route",
                        "human_response_authorized_transition_target",
                    )
                )
            )
            or (
                response_status == "invalid"
                and all(
                    result.get(field) is None
                    for field in (
                        "human_response_decision",
                        "human_response_authorized_route",
                        "human_response_authorized_transition_route",
                        "human_response_authorized_transition_target",
                    )
                )
            )
        ) and result.get("human_response_validator_attempt_id") == active.get("attempt_id")
        if unexpected_human_changes or (response_changed and not valid_gate_validation):
            mismatches.extend(sorted(unexpected_human_changes or allowed_gate_changes))
    else:
        mismatches.extend(human_mismatches)
    if mismatches:
        raise ValueError(f"Graph node modified control-plane identity fields: {mismatches}")


def begin_attempt(
    state: AnalysisState,
    *,
    attempt_kind: str,
    trigger_reason: str,
    new_cycle: bool = False,
    node_name: str | None = None,
) -> AnalysisState:
    resolved_node = node_name or next(
        (node for node, kind in ATTEMPT_KIND_BY_NODE.items() if kind == attempt_kind and node != "human_gate"),
        attempt_kind,
    )
    source_node = state.get("attempt_node")
    if not source_node:
        raise ValueError("Attempt execution requires a current source node and committed transition.")
    scheduled = commit_transition(
        state,
        source_node=source_node,
        route=resolved_node,
        reason=f"Compatibility helper scheduled {resolved_node}.",
        fields={"compatibility_helper": "begin_attempt"},
        target_node=resolved_node,
        target_attempt_kind=attempt_kind,
        trigger_reason=trigger_reason,
        new_cycle=new_cycle,
    )
    return start_attempt(scheduled, node_name=resolved_node, attempt_kind=attempt_kind)


def finish_attempt(
    state: AnalysisState,
    *,
    status: AttemptStatus,
    input_references: dict[str, str] | None = None,
    error: dict[str, str] | None = None,
) -> AnalysisState:
    if status not in {"succeeded", "failed", "pending"}:
        raise ValueError(f"Attempt cannot finish with non-terminal status {status}.")
    if not state.get("attempt_id"):
        raise ValueError("Cannot finish an attempt before identity allocation.")
    if state.get("attempt_status") != "running":
        raise ValueError(
            f"Attempt {state['attempt_id']} is already terminal with status {state.get('attempt_status')}."
        )
    latest_lifecycle = _latest_attempt_lifecycle_record(state, str(state["attempt_id"]))
    if latest_lifecycle is None or latest_lifecycle.get("event") != "started":
        raise ValueError(f"Attempt {state['attempt_id']} does not have the latest running lifecycle record.")
    updated = dict(state)
    updated["attempt_status"] = status
    current_references = _artifact_references(updated)
    previous_references = input_references or {}
    output_references = {
        field: value
        for field, value in current_references.items()
        if previous_references.get(field) != value
    }
    _append_attempt_record(
        updated,
        event="finished",
        status=status,
        input_references=previous_references,
        output_references=output_references,
        error=error,
    )
    append_event(
        updated,
        node=updated.get("attempt_node") or updated["current_node"],
        kind="attempt_finished",
        summary=f"Finished {updated.get('attempt_id')} with status {status}.",
        attempt_outcome=status,
    )
    save_graph_state(updated)
    return updated


def abandon_attempt(state: AnalysisState, *, reason: str) -> AnalysisState:
    if state.get("attempt_status") != "scheduled":
        raise ValueError(f"Attempt {state.get('attempt_id')} is not scheduled and cannot be abandoned.")
    latest_lifecycle = _latest_attempt_lifecycle_record(state, str(state.get("attempt_id")))
    if latest_lifecycle is None or latest_lifecycle.get("event") != "scheduled":
        raise ValueError(f"Attempt {state.get('attempt_id')} is not the latest scheduled lifecycle record.")
    updated = dict(state)
    updated["attempt_status"] = "abandoned"
    _append_attempt_record(
        updated,
        event="abandoned",
        status="abandoned",
        error={"type": "AttemptAbandoned", "message": reason},
    )
    append_event(
        updated,
        node=updated.get("attempt_node") or updated["current_node"],
        kind="attempt_abandoned",
        summary=reason,
    )
    save_graph_state(updated)
    return updated


def execute_scheduled_attempt(
    state: AnalysisState,
    *,
    node_name: str,
    attempt_kind: str,
    node: Callable[[AnalysisState], AnalysisState],
) -> AnalysisState:
    input_references = _artifact_references(state)
    active = start_attempt(state, node_name=node_name, attempt_kind=attempt_kind)
    try:
        result = node(deepcopy(active))
        _validate_node_identity_envelope(active, result)
    except Exception as exc:
        finish_attempt(
            active,
            status="failed",
            input_references=input_references,
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise
    graph_status = result["status"]
    if graph_status in {"failed", "halted"}:
        attempt_status: AttemptStatus = "failed"
    elif graph_status == "pending":
        attempt_status = "pending"
    else:
        attempt_status = "succeeded"
    return finish_attempt(result, status=attempt_status, input_references=input_references)


def execute_node_attempt(
    state: AnalysisState,
    *,
    attempt_kind: str,
    node: Callable[[AnalysisState], AnalysisState],
    trigger_reason: str,
    new_cycle: bool = False,
    node_name: str | None = None,
) -> AnalysisState:
    resolved_node = node_name or next(
        (candidate for candidate, kind in ATTEMPT_KIND_BY_NODE.items() if kind == attempt_kind and candidate != "human_gate"),
        attempt_kind,
    )
    active = begin_attempt(
        state,
        attempt_kind=attempt_kind,
        trigger_reason=trigger_reason,
        new_cycle=new_cycle,
        node_name=resolved_node,
    )
    input_references = _artifact_references(state)
    try:
        result = node(deepcopy(active))
        _validate_node_identity_envelope(active, result)
    except Exception as exc:
        finish_attempt(
            active,
            status="failed",
            input_references=input_references,
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise
    graph_status = result["status"]
    status: AttemptStatus
    if graph_status in {"failed", "halted"}:
        status = "failed"
    elif graph_status == "pending":
        status = "pending"
    else:
        status = "succeeded"
    return finish_attempt(result, status=status, input_references=input_references)


def _record_committed_transition(
    state: AnalysisState,
    *,
    transition_id: str,
    transition_index: int,
    source_node: str,
    source_cycle_id: str | None,
    source_attempt_id: str | None,
    route: str,
    target_node: str | None,
    reason: str,
    fields: dict[str, Any],
    evidence_references: dict[str, Any],
    trigger_reason: str,
    state_updates: dict[str, Any],
) -> AnalysisState:
    if transition_index != state["transition_index"] + 1:
        raise ValueError(f"Transition index {transition_index} is not the next Run-local index.")
    if transition_id != stable_transition_id(transition_index):
        raise ValueError(f"Transition identity {transition_id} does not match index {transition_index}.")
    if _find_committed_transition(state, transition_id) is not None:
        raise ValueError(f"Transition {transition_id} is already committed.")
    updated = dict(state)
    updated["transition_index"] = transition_index
    updated["committed_transition_id"] = transition_id
    updated["committed_route"] = route
    target_attempt_id = updated.get("attempt_id") if target_node is not None else None
    target_cycle_id = updated.get("cycle_id") if target_attempt_id else None
    recorded_target_node = updated.get("attempt_node") if target_attempt_id else None
    target_kind = updated.get("attempt_kind") if target_attempt_id else None
    if target_node is not None and (
        recorded_target_node != target_node
        or updated.get("inbound_transition_id") != transition_id
        or updated.get("attempt_status") != "scheduled"
    ):
        raise ValueError(f"Transition {transition_id} does not own its scheduled target Attempt.")
    record = {
        "schema_version": "0.2",
        "record_type": "transition",
        "event": "committed",
        "transition_id": transition_id,
        "transition_index": transition_index,
        "run_id": updated["run_id"],
        "case_id": updated["case_id"],
        "source": source_node,
        "source_node": source_node,
        "source_cycle_id": source_cycle_id,
        "source_attempt_id": source_attempt_id,
        "route": route,
        "target_node": recorded_target_node,
        "target_cycle_id": target_cycle_id,
        "target_attempt_id": target_attempt_id,
        "target_attempt_kind": target_kind,
        "human_request_id": updated.get("active_human_request_id"),
        "human_response_id": updated.get("active_human_response_id"),
        "trigger_reason": trigger_reason,
        "reason": reason,
        "fields": fields,
        "evidence_references": evidence_references,
        "applied_state_update_keys": sorted(state_updates),
        "applied_state_updates_sha256": _sha256_bytes(
            json.dumps(state_updates, sort_keys=True, default=str).encode("utf-8")
        ),
        "status": "committed",
        "committed_at": utc_now(),
    }
    record["created_at"] = record["committed_at"]
    _append_record(updated, record)
    updated["route_decisions"].append(record)
    updated["event_log"].append(
        {
            "created_at": record["created_at"],
            "node": source_node,
            "kind": "route_decision",
            "summary": reason,
            "run_id": updated["run_id"],
            "case_id": updated["case_id"],
            "source_cycle_id": source_cycle_id,
            "source_attempt_id": source_attempt_id,
            "transition_id": transition_id,
            "route": route,
            "target_cycle_id": target_cycle_id,
            "target_attempt_id": target_attempt_id,
        }
    )
    save_graph_state(updated)
    return updated


def _committed_outbound_transition(
    state: AnalysisState,
    *,
    source_attempt_id: str,
) -> dict[str, Any] | None:
    matches = [
        record
        for record in _read_execution_records(Path(state["execution_history_path"]))
        if record.get("record_type") == "transition"
        and record.get("event") == "committed"
        and record.get("source_attempt_id") == source_attempt_id
    ]
    if len(matches) > 1:
        raise ValueError(f"Attempt {source_attempt_id} has multiple committed outbound Transitions.")
    return matches[0] if matches else None


def commit_transition(
    state: AnalysisState,
    *,
    source_node: str,
    route: str,
    reason: str,
    fields: dict[str, Any],
    evidence_references: dict[str, Any] | None = None,
    state_updates: dict[str, Any] | None = None,
    target_node: str | None = None,
    target_attempt_kind: str | None = None,
    trigger_reason: str = "forward",
    new_cycle: bool = False,
    human_request_kind: str | None = None,
    human_authorization_scope: dict[str, Any] | None = None,
) -> AnalysisState:
    source_cycle_id = state["cycle_id"]
    source_attempt_id = state.get("attempt_id")
    if state.get("attempt_status") not in {"succeeded", "failed", "pending", "abandoned"}:
        raise ValueError("A transition can only be committed after the source Attempt is terminal or pending.")
    if not source_attempt_id or state.get("attempt_node") != source_node:
        raise ValueError("The transition source does not match the current source Attempt.")
    if canonical_attempt_kind(source_node) != state.get("attempt_kind"):
        raise ValueError("The transition source kind does not match the current source Attempt.")
    if _committed_outbound_transition(state, source_attempt_id=source_attempt_id) is not None:
        raise ValueError(f"Attempt {source_attempt_id} already has a committed outbound Transition.")
    _assert_allocation_counter_current(
        state,
        record_type="transition",
        record_index_field="transition_index",
        state_index_field="transition_index",
    )
    if target_node is None:
        if target_attempt_kind is not None:
            raise ValueError("A terminal transition cannot define a target Attempt kind.")
        if new_cycle:
            raise ValueError("A terminal transition cannot create a Cycle.")
    else:
        if target_attempt_kind is None:
            raise ValueError("A non-terminal transition requires a target Attempt kind.")
        validated_target_kind = _validate_attempt_kind(target_attempt_kind)
        expected_target_kind = canonical_attempt_kind(target_node)
        if validated_target_kind != expected_target_kind:
            raise ValueError(
                f"Attempt kind {validated_target_kind} does not match graph node "
                f"{target_node} ({expected_target_kind})."
            )
        if new_cycle and (
            source_node != "decision_coordinator"
            or target_node != "method_planner"
            or validated_target_kind != "method_planner"
            or trigger_reason != "replan"
        ):
            raise ValueError(
                "Only a Coordinator replan transition to Method Planner can create a Cycle."
            )
    if human_request_kind:
        if source_node != "decision_coordinator" or not source_attempt_id:
            raise ValueError("Only a Coordinator transition can create a human request.")
        if target_attempt_kind != "human_gate":
            raise ValueError("A Human Request transition must target the Human Gate.")
        if human_request_kind not in {"clarification", "approval", "external_action"}:
            raise ValueError(f"Unsupported human request kind: {human_request_kind}")
        if not isinstance(human_authorization_scope, dict) or not human_authorization_scope:
            raise ValueError("A Human Request requires a typed authorization scope.")
        if human_request_kind == "approval":
            allowed_decisions = human_authorization_scope.get("allowed_decisions")
            transition_routes = human_authorization_scope.get("decision_transition_routes")
            transition_targets = human_authorization_scope.get("decision_transition_targets")
            if (
                not isinstance(allowed_decisions, list)
                or not allowed_decisions
                or not isinstance(transition_routes, dict)
                or not isinstance(transition_targets, dict)
                or set(transition_routes) != set(allowed_decisions)
                or set(transition_targets) != set(allowed_decisions)
            ):
                raise ValueError("Approval scope must define one exact transition for every decision.")
    protected_state_fields = set(_CONTROL_PLANE_IDENTITY_FIELDS).union(_HUMAN_CONTROL_FIELDS)
    illegal_updates = protected_state_fields.intersection(state_updates or {})
    if illegal_updates:
        raise ValueError(f"Route selection cannot update identity fields: {sorted(illegal_updates)}")
    transition_index = state["transition_index"] + 1
    transition_id = stable_transition_id(transition_index)
    updated = dict(state)
    if state_updates:
        updated.update(state_updates)
    if human_request_kind:
        updated = create_human_request(
            updated,
            request_kind=human_request_kind,
            requesting_attempt_id=source_attempt_id,
            authorization_scope=human_authorization_scope or {},
        )
    should_consume_response = (
        updated.get("attempt_kind") == "human_gate"
        and updated.get("active_human_response_id") is not None
        and updated.get("human_response_status") == "validated"
    )
    if should_consume_response:
        authorized_transition_target = target_node or "END"
        if (
            route != updated.get("human_response_authorized_transition_route")
            or authorized_transition_target
            != updated.get("human_response_authorized_transition_target")
        ):
            raise ValueError(
                "Transition route or target does not match the validated Human Response authorization."
            )
    if target_node is not None:
        updated = allocate_attempt(
            updated,
            node_name=target_node,
            attempt_kind=target_attempt_kind,
            trigger_reason=trigger_reason,
            parent_attempt_id=source_attempt_id,
            new_cycle=new_cycle,
            inbound_transition_id=transition_id,
        )
    if should_consume_response:
        target_attempt_id = updated.get("attempt_id") if target_node else None
        updated = consume_human_response(
            updated,
            consumer_attempt_id=source_attempt_id,
            authorized_target_attempt_id=target_attempt_id,
            transition_route=route,
            transition_target=target_node or "END",
        )
    return _record_committed_transition(
        updated,
        transition_id=transition_id,
        transition_index=transition_index,
        source_node=source_node,
        source_cycle_id=source_cycle_id,
        source_attempt_id=source_attempt_id,
        route=route,
        target_node=target_node,
        reason=reason,
        fields=fields,
        evidence_references=evidence_references or {},
        trigger_reason=trigger_reason,
        state_updates=state_updates or {},
    )


def commit_external_transition(
    state: AnalysisState,
    *,
    source_name: str,
    route: str,
    reason: str,
    fields: dict[str, Any],
    target_node: str,
    target_attempt_kind: str,
    trigger_reason: str,
) -> AnalysisState:
    _assert_allocation_counter_current(
        state,
        record_type="transition",
        record_index_field="transition_index",
        state_index_field="transition_index",
    )
    if state.get("attempt_status") in {"scheduled", "running"}:
        raise ValueError("An external transition cannot replace an active Attempt.")
    parent_attempt_id = state.get("attempt_id")
    transition_index = state["transition_index"] + 1
    transition_id = stable_transition_id(transition_index)
    updated = allocate_attempt(
        state,
        node_name=target_node,
        attempt_kind=target_attempt_kind,
        trigger_reason=trigger_reason,
        parent_attempt_id=parent_attempt_id,
        inbound_transition_id=transition_id,
    )
    return _record_committed_transition(
        updated,
        transition_id=transition_id,
        transition_index=transition_index,
        source_node=source_name,
        source_cycle_id=state["cycle_id"],
        source_attempt_id=None,
        route=route,
        target_node=target_node,
        reason=reason,
        fields=fields,
        evidence_references={},
        trigger_reason=trigger_reason,
        state_updates={},
    )


def read_committed_route(state: AnalysisState) -> str:
    transition_id = state.get("committed_transition_id")
    route = state.get("committed_route")
    if not transition_id or not route:
        raise ValueError("Graph routing requires a committed Transition and route.")
    transition = _find_committed_transition(state, transition_id)
    if transition is None or transition.get("route") != route:
        raise ValueError(f"Committed route does not match Transition {transition_id}.")
    target_attempt_id = transition.get("target_attempt_id")
    if target_attempt_id is not None:
        expected_target = (
            target_attempt_id,
            transition.get("target_node"),
            transition.get("target_attempt_kind"),
            transition.get("target_cycle_id"),
        )
        current_target = (
            state.get("attempt_id"),
            state.get("attempt_node"),
            state.get("attempt_kind"),
            state.get("cycle_id"),
        )
        if expected_target != current_target or state.get("inbound_transition_id") != transition_id:
            raise ValueError(f"Committed Transition {transition_id} does not match the current target Attempt.")
    return str(route)


def append_event(state: AnalysisState, *, node: str, kind: str, summary: str, **fields: Any) -> None:
    state["event_log"].append(
        {
            "created_at": utc_now(),
            "node": node,
            "kind": kind,
            "summary": summary,
            **fields,
            **_identity_fields(state),
        }
    )


def record_route_decision(
    state: AnalysisState, *, source: str, route: str, reason: str, fields: dict[str, Any]
) -> None:
    decision = {
        "created_at": utc_now(),
        "source": source,
        "route": route,
        "reason": reason,
        **_identity_fields(state),
        "source_attempt_id": state.get("attempt_id"),
        "target_attempt_id": None,
        "fields": fields,
    }
    state["route_decisions"].append(decision)
    append_event(state, node=source, kind="route_decision", summary=reason, route=route)


def write_json_artifact(state: AnalysisState, relative_path: str, payload: dict[str, Any]) -> str:
    path = Path(state["output_dir"]) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    identity_payload = dict(payload)
    identity_payload.update(
        {
            "cycle_id": state["cycle_id"],
            "attempt_id": state.get("attempt_id"),
            "parent_attempt_id": state.get("parent_attempt_id"),
            "attempt_kind": state.get("attempt_kind"),
            "attempt_node": state.get("attempt_node"),
            "inbound_transition_id": state.get("inbound_transition_id"),
            "committed_transition_id": state.get("committed_transition_id"),
        }
    )
    path.write_text(json.dumps(identity_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def save_graph_state(state: AnalysisState) -> str:
    path = Path(state["output_dir"]) / "graph_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def maybe_summarize_event_log(state: AnalysisState) -> None:
    long_entry_count = sum(
        1 for event in state["event_log"] if len(str(event.get("summary", ""))) > LONG_EVENT_TEXT_LIMIT
    )
    if len(state["event_log"]) <= LONG_EVENT_LOG_LIMIT and long_entry_count == 0:
        return

    node_counts: dict[str, int] = {}
    for event in state["event_log"]:
        node = str(event.get("node", "unknown"))
        node_counts[node] = node_counts.get(node, 0) + 1
    ordered_counts = ", ".join(f"{node}:{count}" for node, count in sorted(node_counts.items()))
    state["event_log_summary"] = (
        f"Deterministic mock summary of {len(state['event_log'])} events; "
        f"long_entries={long_entry_count}; node_counts={ordered_counts}."
    )
    state["context_window_status"] = "summarized"
    summary_path = write_json_artifact(
        state,
        "context/event_log_summary.json",
        {
            "schema_version": "0.1",
            "run_id": state["run_id"],
            "case_id": state["case_id"],
            "created_at": utc_now(),
            "producer": "context_boundary",
            "status": "success",
            "summary": state["event_log_summary"],
            "warnings": [],
            "errors": [],
        },
    )
    state["context_summary_path"] = summary_path


def llm_context_view(state: AnalysisState) -> dict[str, Any]:
    maybe_summarize_event_log(state)
    return {
        "run_id": state["run_id"],
        "cycle_id": state["cycle_id"],
        "attempt_id": state["attempt_id"],
        "parent_attempt_id": state["parent_attempt_id"],
        "attempt_kind": state["attempt_kind"],
        "attempt_node": state["attempt_node"],
        "attempt_trigger": state["attempt_trigger"],
        "active_human_request_id": state["active_human_request_id"],
        "human_request_status": state["human_request_status"],
        "active_human_response_id": state["active_human_response_id"],
        "human_response_status": state["human_response_status"],
        "case_id": state["case_id"],
        "user_goal": state["user_goal"],
        "status": state["status"],
        "current_node": state["current_node"],
        "llm_provider_config_path": state["llm_provider_config_path"],
        "method_plan_path": state["method_plan_path"],
        "run_result_path": state["run_result_path"],
        "scientific_review_report_path": state["scientific_review_report_path"],
        "decision_log_path": state["decision_log_path"],
        "risk_level": state["risk_level"],
        "recommended_action": state["recommended_action"],
        "event_log_summary": state["event_log_summary"],
        "context_window_status": state["context_window_status"],
    }
