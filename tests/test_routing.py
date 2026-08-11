import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

import pytest

from lqcd_agent.graph.routing import (
    RouteSelection,
    committed_route,
    select_after_analysis_engineer,
    select_after_codex_handoff,
    select_after_decision_coordinator,
    select_after_human_approval_gate,
    select_after_method_planner,
)
from lqcd_agent.graph.state import (
    AnalysisState,
    commit_transition,
    execute_scheduled_attempt,
    initialize_state,
)


def _state(tmp_path: Path) -> AnalysisState:
    return initialize_state(
        case_id="case_a",
        run_id="run_a",
        user_goal="mock goal",
        case_config_path="case.yaml",
        output_dir=str(tmp_path),
        checkpoint_backend="memory",
    )


def _select_without_mutation(
    selector: Callable[[AnalysisState], RouteSelection],
    state: AnalysisState,
) -> RouteSelection:
    before = deepcopy(state)

    selection = selector(state)

    assert state == before
    assert state["route_decisions"] == before["route_decisions"]
    assert selection["reason"]
    assert "fields" in selection
    assert "state_updates" in selection
    assert "trigger_reason" in selection
    return selection


def _write_tests_status(tmp_path: Path, *, status: str) -> Path:
    return_code = 0 if status == "tests_passed" else 1
    payload = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "test_runner",
        "status": status,
        "summary": "Configured verification commands completed.",
        "warnings": [],
        "errors": [],
        "commands": [
            {
                "command": "pytest tests/test_coder_task_packet.py -q",
                "working_directory": str(tmp_path),
                "timeout_seconds": 60,
                "return_code": return_code,
                "stdout": "passed" if return_code == 0 else "failed",
                "stderr": "",
                "produced_files": [],
                "status": "passed" if return_code == 0 else "failed",
            }
        ],
    }
    path = tmp_path / "tests_status.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _successful_node(active: AnalysisState) -> AnalysisState:
    return {**active, "status": "running"}


def test_method_planner_selects_no_code_route_without_mutating_state(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["code_needed"] = False

    selection = _select_without_mutation(select_after_method_planner, state)

    assert selection["route"] == "analysis_engineer"
    assert selection["reason"] == "code_needed is false."
    assert selection["fields"] == {
        "status": "running",
        "code_needed": False,
        "coder_task_packet_path": None,
        "error_count": 0,
        "retry_count": 0,
        "max_retry": 1,
    }
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"
    assert selection["new_cycle"] is False


def test_method_planner_selects_legacy_codex_route_without_mutating_state(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["code_needed"] = True
    state["coder_task_packet_path"] = str(tmp_path / "coder_task_packet.yaml")

    selection = _select_without_mutation(select_after_method_planner, state)

    assert selection["route"] == "codex_handoff"
    assert selection["reason"] == "code_needed is true and a file-based Codex Handoff is required."
    assert selection["fields"]["code_needed"] is True
    assert selection["fields"]["coder_task_packet_path"] == state["coder_task_packet_path"]
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"


def test_method_planner_selects_safe_end_without_mutating_state(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["status"] = "pending"
    state["errors"].append({"field": "user_goal", "message": "Required input is missing."})

    selection = _select_without_mutation(select_after_method_planner, state)

    assert selection["route"] == "end"
    assert selection["reason"] == "method planner reached a safe terminal status before analysis."
    assert selection["fields"]["status"] == "pending"
    assert selection["fields"]["error_count"] == 1
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"


def test_analysis_selects_review_on_structured_success_without_mutation(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["run_success"] = True

    selection = _select_without_mutation(select_after_analysis_engineer, state)

    assert selection == {
        "route": "scientific_reviewer",
        "target_node": "scientific_reviewer",
        "target_attempt_kind": "scientific_reviewer",
        "reason": "run_success is true.",
        "fields": {
            "run_success": True,
            "failure_type": None,
            "retry_count": 0,
        },
        "evidence_references": {
            "run_result_path": None,
            "tests_status_path": None,
        },
        "state_updates": {},
        "trigger_reason": "forward",
        "new_cycle": False,
    }


def test_analysis_selects_code_retry_as_explicit_updates_without_mutation(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["run_success"] = False
    state["failure_type"] = "code"

    selection = _select_without_mutation(select_after_analysis_engineer, state)

    assert selection["route"] == "codex_handoff"
    assert selection["reason"] == "code failure has retry budget and requires Codex Handoff."
    assert selection["fields"] == {
        "run_success": False,
        "failure_type": "code",
        "retry_count": 1,
    }
    assert selection["state_updates"] == {
        "retry_count": 1,
        "code_fix_requested": True,
    }
    assert selection["trigger_reason"] == "legacy_code_retry"
    assert selection["new_cycle"] is False
    assert state["retry_count"] == 0
    assert state["code_fix_requested"] is False


def test_analysis_selects_coordinator_when_code_retry_budget_is_exhausted(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["run_success"] = False
    state["failure_type"] = "code"
    state["retry_count"] = state["max_retry"]

    selection = _select_without_mutation(select_after_analysis_engineer, state)

    assert selection["route"] == "decision_coordinator"
    assert selection["reason"] == "analysis failed without a mock retry route."
    assert selection["fields"]["retry_count"] == state["max_retry"]
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"


def test_analysis_retry_updates_become_state_through_transition_commit(tmp_path: Path) -> None:
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    analysis = commit_transition(
        planner,
        source_node="method_planner",
        route="analysis_engineer",
        reason="The plan is ready for analysis.",
        fields={"code_needed": False},
        target_node="analysis_engineer",
        target_attempt_kind="analysis_engineer",
    )
    analysis["run_success"] = False
    analysis["failure_type"] = "code"
    completed = execute_scheduled_attempt(
        analysis,
        node_name="analysis_engineer",
        attempt_kind="analysis_engineer",
        node=_successful_node,
    )
    selection = _select_without_mutation(select_after_analysis_engineer, completed)

    committed = commit_transition(
        completed,
        source_node="analysis_engineer",
        route=selection["route"],
        reason=selection["reason"],
        fields=selection["fields"],
        state_updates=selection["state_updates"],
        target_node="codex_handoff",
        target_attempt_kind="legacy_codex_handoff",
        trigger_reason=selection["trigger_reason"],
    )

    assert committed["retry_count"] == 1
    assert committed["code_fix_requested"] is True
    assert committed["attempt_node"] == "codex_handoff"
    assert committed["attempt_kind"] == "legacy_codex_handoff"
    assert committed["attempt_trigger"] == "legacy_code_retry"
    assert committed["route_decisions"][-1]["fields"]["retry_count"] == 1


def test_codex_handoff_selects_analysis_for_passed_tests_without_mutation(tmp_path: Path) -> None:
    state = _state(tmp_path)
    tests_path = _write_tests_status(tmp_path, status="tests_passed")
    summary_path = tmp_path / "code_change_summary.md"
    summary_path.write_text("External code change summary.\n", encoding="utf-8")
    state["tests_status_path"] = str(tests_path)
    state["code_change_summary_path"] = str(summary_path)

    selection = _select_without_mutation(select_after_codex_handoff, state)

    assert selection["route"] == "analysis_engineer"
    assert selection["reason"] == "structured tests_status.json reports tests_passed."
    assert selection["fields"]["tests_status"] == "tests_passed"
    assert selection["fields"]["code_change_summary_path"] == str(summary_path)
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"


def test_codex_handoff_selects_safe_end_for_failed_tests_without_mutation(tmp_path: Path) -> None:
    state = _state(tmp_path)
    tests_path = _write_tests_status(tmp_path, status="tests_failed")
    state["tests_status_path"] = str(tests_path)

    selection = _select_without_mutation(select_after_codex_handoff, state)

    assert selection["route"] == "end"
    assert selection["reason"] == "structured tests_status.json reports tests_failed."
    assert selection["fields"]["tests_status"] == "tests_failed"
    assert selection["fields"]["tests_status_path"] == str(tests_path)
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"


def test_decision_selects_memory_report_with_checkpoint_metadata_without_mutation(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "low"
    state["recommended_action"] = "accept_mock_result"
    state["decision_log_path"] = str(tmp_path / "decision_log.json")

    selection = _select_without_mutation(select_after_decision_coordinator, state)

    assert selection["route"] == "memory_report"
    assert selection["reason"] == "approval is not required for this risk level."
    assert selection["fields"]["actual_route"] == "memory_report"
    assert selection["fields"]["requested_route"] == "memory_report"
    assert selection["fields"]["proposed_follow_up_route"] == "memory_report"
    assert selection["fields"]["decision_log_path"] == str(tmp_path / "decision_log.json")
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"
    assert "human_request_kind" not in selection


def test_decision_selects_human_gate_with_code_fix_intent_without_mutation(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "high"
    state["recommended_action"] = "code_fix"
    state["human_approval_required"] = True
    state["code_fix_requested"] = True
    state["decision_log_path"] = str(tmp_path / "decision_log.json")

    selection = _select_without_mutation(select_after_decision_coordinator, state)

    assert selection["route"] == "human_approval_gate"
    assert selection["reason"] == "high or critical risk requires Human Approval Gate before reporting."
    assert selection["fields"]["requested_route"] == "human_approval_gate"
    assert selection["fields"]["proposed_follow_up_route"] == "codex_handoff"
    assert selection["fields"]["code_fix_requested"] is True
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"
    assert selection["human_request_kind"] == "approval"


def test_decision_selects_human_gate_with_targeted_rerun_intent_without_mutation(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "high"
    state["recommended_action"] = "targeted_rerun"
    state["human_approval_required"] = True
    state["rerun_requested"] = True
    state["rerun_target"] = "analysis_engineer"
    state["decision_log_path"] = str(tmp_path / "decision_log.json")

    selection = _select_without_mutation(select_after_decision_coordinator, state)

    assert selection["route"] == "human_approval_gate"
    assert selection["fields"]["requested_route"] == "human_approval_gate"
    assert selection["fields"]["proposed_follow_up_route"] == "analysis_engineer"
    assert selection["fields"]["rerun_requested"] is True
    assert selection["fields"]["rerun_target"] == "analysis_engineer"
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"
    assert selection["human_request_kind"] == "approval"


def test_human_gate_selects_reporting_without_mutating_state(tmp_path: Path) -> None:
    state = _state(tmp_path)

    selection = _select_without_mutation(select_after_human_approval_gate, state)

    assert selection["route"] == "memory_report"
    assert selection["reason"] == "human decision allows reporting to continue."
    assert selection["fields"]["human_decision"] is None
    assert selection["fields"]["actual_route"] == "memory_report"
    assert selection["fields"]["proposed_follow_up_route"] == "memory_report"
    assert selection["state_updates"] == {}
    assert selection["trigger_reason"] == "forward"


def test_human_gate_selector_uses_validated_snapshot_not_mutable_projection(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    decision_path = tmp_path / "decision.yaml"
    decision_path.write_text(
        "\n".join(
            [
                'schema_version: "0.2"',
                'run_id: "run_a"',
                'case_id: "case_a"',
                'cycle_id: "cycle_0001"',
                'human_request_id: "human_request_000001"',
                'requesting_attempt_id: "attempt_000004"',
                'human_response_id: "human_response_000001"',
                'decision: "reject_or_hold"',
                'conditions: ""',
                'reason: "Changed projection."',
                'decided_by: "tester"',
                'decided_at: "2026-08-11T00:00:00+00:00"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    state["human_decision_path"] = str(decision_path)
    state["human_response_status"] = "validated"
    state["human_response_decision"] = "approve_with_conditions"

    selection = _select_without_mutation(select_after_human_approval_gate, state)

    assert selection["fields"]["human_decision"] == "approve_with_conditions"
    assert selection["trigger_reason"] == "human_response"


def test_committed_route_is_a_pure_read(tmp_path: Path) -> None:
    state = _state(tmp_path)
    before = deepcopy(state)

    assert committed_route(state) == "method_planner"
    assert state == before


def test_committed_route_rejects_state_that_disagrees_with_ledger(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["committed_route"] = "analysis_engineer"

    with pytest.raises(ValueError, match="does not match"):
        committed_route(state)
