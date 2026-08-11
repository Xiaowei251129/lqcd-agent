"""Final Markdown report generator for agent graph runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lqcd_agent.graph.state import AnalysisState, utc_now


FINAL_REPORT_FILENAME = "final_report.md"


def _read_json_object(path: str | Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if not path:
        return None, "path not recorded"
    json_path = Path(path)
    if not json_path.exists():
        return None, "file missing"
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "invalid JSON"
    if not isinstance(payload, dict):
        return None, "JSON value is not an object"
    return payload, None


def _human_decision_summary(state: AnalysisState) -> str:
    if state.get("human_response_status") != "consumed":
        return f"No consumed human decision; response status: `{state.get('human_response_status')}`."
    decision = state.get("human_response_decision")
    if isinstance(decision, str):
        return f"Approved human decision: `{decision}`."
    return "Consumed human response has no validated decision snapshot."


def _display_action(value: Any) -> Any:
    return "accept_result" if value == "accept_mock_result" else value


def _display_message(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("mock-result", "result")
    return value


def _bullet_lines(items: list[Any], *, empty: str) -> list[str]:
    if not items:
        return [f"- {empty}"]
    lines = []
    for item in items:
        if isinstance(item, dict):
            code = _display_action(item.get("code") or item.get("action") or item.get("field") or "item")
            message = _display_message(item.get("message") or item.get("summary") or item.get("status") or item)
            lines.append(f"- `{code}`: {message}")
        else:
            lines.append(f"- {_display_message(item)}")
    return lines


def _llm_call_lines(output_dir: str | Path) -> list[str]:
    trace_dir = Path(output_dir) / "llm_calls"
    if not trace_dir.exists():
        return ["- No LLM call transcripts recorded."]
    trace_files = sorted(path for path in trace_dir.glob("*.json") if path.is_file())
    if not trace_files:
        return ["- No LLM call transcripts recorded."]
    return [f"- {path.name}: {path}" for path in trace_files]


def build_final_report(state: AnalysisState, memory_update: dict[str, Any]) -> str:
    method_plan, method_error = _read_json_object(state.get("method_plan_path"))
    run_result, run_error = _read_json_object(state.get("run_result_path"))
    review, review_error = _read_json_object(state.get("scientific_review_report_path"))
    decision_log, decision_error = _read_json_object(state.get("decision_log_path"))

    report_warnings = []
    for name, error in [
        ("method_plan", method_error),
        ("run_result", run_error),
        ("scientific_review_report", review_error),
        ("decision_log", decision_error),
    ]:
        if error:
            report_warnings.append(f"{name}: {error}")

    review_warnings = review.get("warnings", []) if review else []
    decision_next_actions = decision_log.get("next_actions", []) if decision_log else []

    lines = [
        "# Final LQCD Agent Report",
        "",
        "## Metadata",
        f"- run_id: {state['run_id']}",
        f"- case_id: {state['case_id']}",
        f"- cycle_id: {state['cycle_id']}",
        f"- attempt_id: {state['attempt_id']}",
        f"- parent_attempt_id: {state['parent_attempt_id']}",
        f"- attempt_kind: {state['attempt_kind']}",
        f"- attempt_node: {state['attempt_node']}",
        f"- inbound_transition_id: {state['inbound_transition_id']}",
        f"- committed_transition_id: {state['committed_transition_id']}",
        f"- created_at: {utc_now()}",
        f"- graph_status: {state['status']}",
        f"- current_node: {state['current_node']}",
        "",
        "## Method Plan",
        f"- status: {method_plan.get('status') if method_plan else 'unavailable'}",
        f"- summary: {method_plan.get('summary') if method_plan else 'No method plan could be read.'}",
        f"- path: {state.get('method_plan_path')}",
        "",
        "## Run Summary",
        f"- run_success: {run_result.get('run_success') if run_result else 'unavailable'}",
        f"- failure_type: {run_result.get('failure_type') if run_result else 'unavailable'}",
        f"- analysis_outputs_dir: {state.get('analysis_outputs_dir')}",
        f"- run_result_path: {state.get('run_result_path')}",
        "",
        "## Scientific Review",
        f"- confidence: {review.get('confidence') if review else 'unavailable'}",
        f"- summary: {review.get('summary') if review else 'No scientific review could be read.'}",
        f"- scientific_review_report_path: {state.get('scientific_review_report_path')}",
        "",
        "## Warnings",
        *_bullet_lines(review_warnings + report_warnings, empty="No warnings recorded."),
        "",
        "## Coordinator Decision",
        f"- risk_level: {state['risk_level']}",
        f"- recommended_action: {_display_action(state['recommended_action'])}",
        f"- human_approval_required: {state['human_approval_required']}",
        f"- decision_log_path: {state.get('decision_log_path')}",
        "",
        "## LLM Calls",
        *_llm_call_lines(state["output_dir"]),
        "",
        "## Approval Status",
        f"- approval_packet_dir: {state.get('approval_packet_dir')}",
        f"- human_decision_path: {state.get('human_decision_path')}",
        f"- human_request_id: {state.get('active_human_request_id')}",
        f"- human_request_status: {state.get('human_request_status')}",
        f"- human_response_id: {state.get('active_human_response_id')}",
        f"- human_response_status: {state.get('human_response_status')}",
        f"- human_response_validator_attempt_id: {state.get('human_response_validator_attempt_id')}",
        f"- human_response_consumer_attempt_id: {state.get('human_response_consumer_attempt_id')}",
        f"- human_response_target_attempt_id: {state.get('human_response_target_attempt_id')}",
        f"- decision: {_human_decision_summary(state)}",
        "",
        "## Memory Update",
        f"- memory_status: {memory_update.get('memory_status')}",
        f"- accepted_result: {memory_update.get('accepted_result')}",
        f"- memory_update_path: {state.get('memory_update_path')}",
        "",
        "## Next Actions",
        *_bullet_lines(decision_next_actions, empty="No next actions recorded."),
        "",
        "## Reproducibility",
        f"- case_config_path: {state['case_config_path']}",
        f"- output_dir: {state['output_dir']}",
        f"- checkpoint_backend: {state['checkpoint_backend']}",
        f"- checkpoint_thread_id: {state['checkpoint_thread_id']}",
        f"- checkpoint_db_path: {state['checkpoint_db_path']}",
        f"- execution_history_path: {state['execution_history_path']}",
        "",
    ]
    return "\n".join(lines)


def write_final_report(state: AnalysisState, memory_update: dict[str, Any]) -> dict[str, str]:
    output_dir = Path(state["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / FINAL_REPORT_FILENAME
    path.write_text(build_final_report(state, memory_update), encoding="utf-8")
    return {"final_report_path": str(path)}
