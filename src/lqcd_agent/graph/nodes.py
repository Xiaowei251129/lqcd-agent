"""Deterministic mock nodes for the initial graph runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lqcd_agent.agents.analysis_engineer import run_analysis_engineer
from lqcd_agent.agents.decision_coordinator import run_decision_coordinator
from lqcd_agent.agents.method_planner import run_method_planner
from lqcd_agent.agents.scientific_reviewer import run_scientific_reviewer
from lqcd_agent.coder.codex_handoff import ensure_task_packet, read_handoff_results
from lqcd_agent.coder.task_packet import TaskPacketValidationError
from lqcd_agent.graph.approval_packet import (
    decision_route_target,
    parse_human_decision,
    write_approval_packet,
)
from lqcd_agent.graph.state import (
    AnalysisState,
    append_event,
    llm_context_view,
    save_graph_state,
)
from lqcd_agent.memory.store import write_memory_update
from lqcd_agent.report.generate_report import write_final_report
from lqcd_agent.tools.repo_inventory import build_repo_inventory


def _read_case_config(path: str) -> dict[str, Any] | None:
    case_path = Path(path)
    if not case_path.exists():
        return None

    result: dict[str, Any] = {}
    for raw_line in case_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        if value and not value.startswith("["):
            result[key.strip()] = value
    return result


def method_planner_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "method_planner"
    state["status"] = "running"
    llm_context_view(state)
    repo_root = Path(__file__).resolve().parents[3]
    result = run_method_planner(
        user_goal=state["user_goal"],
        case_config=_read_case_config(state["case_config_path"]),
        repo_inventory=build_repo_inventory(repo_root),
        output_dir=state["output_dir"],
        run_id=state["run_id"],
    )
    method_plan = result["method_plan"]
    state["method_plan_path"] = result["method_plan_path"]
    state["code_needed"] = result["code_needed"]
    state["coder_task_packet_path"] = result["coder_task_packet_path"]

    if result["status"] == "needs_more_info":
        state["status"] = "pending"
        state["errors"].extend(
            {
                "node": "method_planner",
                "field": error.get("field"),
                "message": error.get("message"),
                "method_plan_path": state["method_plan_path"],
            }
            for error in method_plan.get("errors", [])
        )
        append_event(
            state,
            node="method_planner",
            kind="node_pending",
            summary="Method planner needs more information before analysis can run.",
        )
    elif result["status"] != "success":
        state["status"] = "halted"
        state["errors"].extend(
            {
                "node": "method_planner",
                "field": error.get("field"),
                "message": error.get("message"),
                "method_plan_path": state["method_plan_path"],
            }
            for error in method_plan.get("errors", [])
        )
        append_event(
            state,
            node="method_planner",
            kind="node_halted",
            summary="Method planner failed validation before analysis could run.",
        )
    elif state["code_needed"]:
        state["status"] = "running"
        append_event(
            state,
            node="method_planner",
            kind="node_complete",
            summary="Method planner wrote a coder task packet for Codex Handoff.",
        )
    else:
        state["status"] = "running"
        append_event(state, node="method_planner", kind="node_complete", summary=method_plan["summary"])
    save_graph_state(state)
    return state


def codex_handoff_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "codex_handoff"
    state["status"] = "running"
    llm_context_view(state)

    try:
        task_packet = ensure_task_packet(state)
    except TaskPacketValidationError as exc:
        state["status"] = "halted"
        state["errors"].extend(
            {
                "node": "codex_handoff",
                "field": "coder_task_packet_path",
                "message": error,
            }
            for error in exc.errors
        )
        append_event(
            state,
            node="codex_handoff",
            kind="node_halted",
            summary="Codex Handoff could not validate or rebuild coder_task_packet.yaml.",
        )
        save_graph_state(state)
        return state

    state["coder_task_packet_path"] = task_packet["coder_task_packet_path"]
    handoff = read_handoff_results(state["output_dir"])
    state["code_change_summary_path"] = handoff["code_change_summary_path"]
    state["tests_status_path"] = handoff["tests_status_path"]

    if handoff["handoff_status"] == "halted":
        state["status"] = "halted"
        state["errors"].extend(
            {
                "node": "codex_handoff",
                "field": error.get("field"),
                "message": error.get("message"),
                "path": error.get("path"),
            }
            for error in handoff["errors"]
        )
        append_event(
            state,
            node="codex_handoff",
            kind="node_halted",
            summary=handoff["summary"],
        )
    elif handoff["handoff_status"] == "tests_passed":
        state["status"] = "running"
        state["code_needed"] = False
        state["code_fix_requested"] = False
        state["failure_type"] = None
        append_event(
            state,
            node="codex_handoff",
            kind="node_complete",
            summary="Structured handoff tests passed; analysis can continue.",
            tests_status_path=state["tests_status_path"],
            code_change_summary_path=state["code_change_summary_path"],
        )
    elif handoff["handoff_status"] == "tests_failed":
        state["status"] = "pending"
        state["code_fix_requested"] = True
        state["failure_type"] = "code"
        append_event(
            state,
            node="codex_handoff",
            kind="node_pending",
            summary="Structured handoff tests failed; awaiting an external code fix.",
            tests_status_path=state["tests_status_path"],
        )
    else:
        state["status"] = "pending"
        append_event(
            state,
            node="codex_handoff",
            kind="node_pending",
            summary=handoff["summary"],
            coder_task_packet_path=state["coder_task_packet_path"],
        )

    state["warnings"].extend(
        {
            "node": "codex_handoff",
            "field": warning.get("field"),
            "message": warning.get("message"),
        }
        for warning in handoff["warnings"]
    )
    save_graph_state(state)
    return state


def analysis_engineer_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "analysis_engineer"
    state["status"] = "running"
    llm_context_view(state)
    repo_root = Path(__file__).resolve().parents[3]
    result = run_analysis_engineer(
        case_config_path=state["case_config_path"],
        case_id=state["case_id"],
        run_id=state["run_id"],
        run_output_dir=state["output_dir"],
        method_plan_path=state["method_plan_path"],
        repo_root=repo_root,
    )
    state["run_result_path"] = result["run_result_path"]
    state["analysis_outputs_dir"] = result["analysis_outputs_dir"]
    state["run_success"] = result["run_success"]
    state["failure_type"] = result["failure_type"]
    state["warnings"].extend(
        {
            "node": "analysis_engineer",
            "field": warning.get("field"),
            "message": warning.get("message"),
        }
        for warning in result["warnings"]
    )
    state["errors"].extend(
        {
            "node": "analysis_engineer",
            "field": error.get("field"),
            "message": error.get("message"),
            "command_id": error.get("command_id"),
            "return_code": error.get("return_code"),
        }
        for error in result["errors"]
    )
    state["status"] = "running" if result["run_success"] else "failed"
    summary = (
        result["run_result"]["summary"]
        if result["run_result"]
        else "Analysis Engineer stopped before writing run artifacts."
    )
    append_event(
        state,
        node="analysis_engineer",
        kind="node_complete" if result["run_success"] else "node_failed",
        summary=summary,
        manifest_path=result["manifest_path"],
    )
    save_graph_state(state)
    return state


def scientific_reviewer_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "scientific_reviewer"
    state["status"] = "running"
    llm_context_view(state)
    result = run_scientific_reviewer(
        run_id=state["run_id"],
        case_id=state["case_id"],
        run_output_dir=state["output_dir"],
        run_result_path=state["run_result_path"],
        analysis_outputs_dir=state["analysis_outputs_dir"],
        method_plan_path=state["method_plan_path"],
    )
    report = result["report"]
    state["scientific_review_report_path"] = result["scientific_review_report_path"]
    state["warnings"].extend(
        {
            "node": "scientific_reviewer",
            "section": warning.get("section"),
            "code": warning.get("code"),
            "severity": warning.get("severity"),
            "decision_coordinator_flag": warning.get("decision_coordinator_flag"),
            "message": warning.get("message"),
            "path": warning.get("path"),
            "field": warning.get("field"),
            "value": warning.get("value"),
        }
        for warning in report["warnings"]
    )
    if any(warning.get("severity") == "severe" for warning in report["warnings"]):
        state["risk_level"] = "high"
    elif report["warnings"]:
        state["risk_level"] = "medium"
    else:
        state["risk_level"] = "low"
    append_event(state, node="scientific_reviewer", kind="node_complete", summary=report["summary"])
    save_graph_state(state)
    return state


def decision_coordinator_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "decision_coordinator"
    state["status"] = "running"
    llm_context_view(state)
    result = run_decision_coordinator(
        run_id=state["run_id"],
        case_id=state["case_id"],
        output_dir=state["output_dir"],
        method_plan_path=state["method_plan_path"],
        run_result_path=state["run_result_path"],
        scientific_review_report_path=state["scientific_review_report_path"],
    )
    decision_log = result["decision_log"]
    state["decision_log_path"] = result["decision_log_path"]
    state["risk_level"] = result["risk_level"]
    state["recommended_action"] = result["recommended_action"]
    state["human_approval_required"] = result["human_approval_required"]
    state["rerun_requested"] = result["rerun_requested"]
    state["rerun_target"] = result["rerun_target"]
    state["code_fix_requested"] = result["code_fix_requested"]
    state["status"] = "running" if result["status"] == "success" else "pending"
    append_event(state, node="decision_coordinator", kind="node_complete", summary=decision_log["summary"])
    save_graph_state(state)
    return state


def human_approval_gate_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "human_approval_gate"
    llm_context_view(state)

    if not state["human_approval_required"]:
        state["status"] = "running"
        append_event(
            state,
            node="human_approval_gate",
            kind="node_complete",
            summary="Human Approval Gate was bypassed because approval is not required.",
        )
        save_graph_state(state)
        return state

    packet_paths = write_approval_packet(state)
    state["approval_packet_dir"] = packet_paths["approval_packet_dir"]
    state["human_decision_path"] = packet_paths["human_decision_path"]

    decision_result = parse_human_decision(
        state["human_decision_path"],
        run_id=state["run_id"],
        case_id=state["case_id"],
    )
    if decision_result["status"] == "pending":
        state["status"] = "pending"
        append_event(
            state,
            node="human_approval_gate",
            kind="node_pending",
            summary="Approval packet is ready and waiting for a human decision.",
            approval_packet_dir=state["approval_packet_dir"],
            human_decision_path=state["human_decision_path"],
        )
        save_graph_state(state)
        return state

    if decision_result["status"] == "invalid":
        state["status"] = "pending"
        state["errors"].extend(
            {
                "node": "human_approval_gate",
                "field": error.get("field"),
                "message": error.get("message"),
                "path": error.get("path"),
                "value": error.get("value"),
                "expected": error.get("expected"),
            }
            for error in decision_result["errors"]
        )
        append_event(
            state,
            node="human_approval_gate",
            kind="node_pending",
            summary="Human decision file is present but invalid; waiting for correction.",
            human_decision_path=state["human_decision_path"],
        )
        save_graph_state(state)
        return state

    decision = decision_result["decision"]
    follow_up_route = decision_route_target(decision)
    state["rerun_requested"] = False
    state["rerun_target"] = None
    state["code_fix_requested"] = False
    state["code_needed"] = False

    if decision == "approve_rerun":
        state["status"] = "pending"
        state["rerun_requested"] = True
        state["rerun_target"] = "analysis_engineer"
    elif decision == "request_code_change":
        state["status"] = "running"
        state["code_fix_requested"] = True
        state["code_needed"] = True
    else:
        state["status"] = "running"

    append_event(
        state,
        node="human_approval_gate",
        kind="node_complete",
        summary=f"Human decision recorded: {decision}.",
        human_decision_path=state["human_decision_path"],
        requested_route=follow_up_route,
    )
    save_graph_state(state)
    return state


def memory_report_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "memory_report"
    llm_context_view(state)
    memory_result = write_memory_update(state)
    state["memory_update_path"] = memory_result["memory_update_path"]
    memory_status = memory_result["memory_update"]["memory_status"]
    state["status"] = "success" if memory_status == "accepted" else "pending"
    report_result = write_final_report(state, memory_result["memory_update"])
    state["final_report_path"] = report_result["final_report_path"]
    append_event(
        state,
        node="memory_report",
        kind="node_complete",
        summary="Wrote final report and structured memory update.",
        memory_status=memory_status,
        final_report_path=state["final_report_path"],
        memory_update_path=state["memory_update_path"],
    )
    save_graph_state(state)
    return state
