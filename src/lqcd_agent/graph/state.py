"""State schema helpers for the mock LangGraph runtime."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict


Status = Literal["running", "success", "failed", "pending", "halted"]
ContextWindowStatus = Literal["normal", "near_limit", "summarized", "overflow_halt"]

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

    checkpoint_thread_id: str
    checkpoint_backend: str
    checkpoint_db_path: str | None

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


def initialize_state(
    *,
    case_id: str,
    run_id: str,
    user_goal: str,
    case_config_path: str,
    output_dir: str,
    checkpoint_backend: str = "memory",
    checkpoint_db_path: str | None = None,
    max_retry: int = 1,
) -> AnalysisState:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return {
        "run_id": run_id,
        "case_id": case_id,
        "user_goal": user_goal,
        "case_config_path": case_config_path,
        "output_dir": str(output_path),
        "current_node": "START",
        "status": "running",
        "checkpoint_thread_id": stable_checkpoint_thread_id(case_id, run_id),
        "checkpoint_backend": checkpoint_backend,
        "checkpoint_db_path": checkpoint_db_path,
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


def append_event(state: AnalysisState, *, node: str, kind: str, summary: str, **fields: Any) -> None:
    state["event_log"].append(
        {
            "created_at": utc_now(),
            "node": node,
            "kind": kind,
            "summary": summary,
            **fields,
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
        "fields": fields,
    }
    state["route_decisions"].append(decision)
    append_event(state, node=source, kind="route_decision", summary=reason, route=route)


def write_json_artifact(state: AnalysisState, relative_path: str, payload: dict[str, Any]) -> str:
    path = Path(state["output_dir"]) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "case_id": state["case_id"],
        "user_goal": state["user_goal"],
        "status": state["status"],
        "current_node": state["current_node"],
        "method_plan_path": state["method_plan_path"],
        "run_result_path": state["run_result_path"],
        "scientific_review_report_path": state["scientific_review_report_path"],
        "decision_log_path": state["decision_log_path"],
        "risk_level": state["risk_level"],
        "recommended_action": state["recommended_action"],
        "event_log_summary": state["event_log_summary"],
        "context_window_status": state["context_window_status"],
    }
