import json
from pathlib import Path

from lqcd_agent.graph.routing import (
    route_after_analysis_engineer,
    route_after_codex_handoff,
    route_after_decision_coordinator,
    route_after_method_planner,
)
from lqcd_agent.graph.state import initialize_state


def _state(tmp_path: Path):
    return initialize_state(
        case_id="case_a",
        run_id="run_a",
        user_goal="mock goal",
        case_config_path="case.yaml",
        output_dir=str(tmp_path),
        checkpoint_backend="memory",
    )


def test_method_planner_routes_no_code_to_analysis(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["code_needed"] = False

    assert route_after_method_planner(state) == "analysis_engineer"
    assert state["route_decisions"][-1]["fields"]["code_needed"] is False


def test_method_planner_routes_code_needed_to_codex_handoff(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["code_needed"] = True
    state["coder_task_packet_path"] = str(tmp_path / "coder_task_packet.yaml")

    assert route_after_method_planner(state) == "codex_handoff"
    assert state["route_decisions"][-1]["fields"]["code_needed"] is True


def test_method_planner_routes_pending_to_safe_end(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["status"] = "pending"
    state["errors"].append({"field": "user_goal", "message": "Required input is missing."})

    assert route_after_method_planner(state) == "end"
    assert state["route_decisions"][-1]["fields"]["status"] == "pending"


def test_analysis_routes_on_structured_run_success(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["run_success"] = True

    assert route_after_analysis_engineer(state) == "scientific_reviewer"
    assert state["route_decisions"][-1]["fields"]["run_success"] is True


def test_analysis_code_failure_routes_to_codex_handoff_with_retry(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["run_success"] = False
    state["failure_type"] = "code"

    assert route_after_analysis_engineer(state) == "codex_handoff"
    assert state["retry_count"] == 1
    assert state["code_fix_requested"] is True


def test_codex_handoff_routes_passed_tests_to_analysis(tmp_path: Path) -> None:
    state = _state(tmp_path)
    tests_status = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "test_runner",
        "status": "tests_passed",
        "summary": "All configured verification commands passed.",
        "warnings": [],
        "errors": [],
        "commands": [
            {
                "command": "pytest tests/test_coder_task_packet.py -q",
                "working_directory": str(tmp_path),
                "timeout_seconds": 60,
                "return_code": 0,
                "stdout": "passed",
                "stderr": "",
                "produced_files": [],
                "status": "passed",
            }
        ],
    }
    tests_path = tmp_path / "tests_status.json"
    tests_path.write_text(json.dumps(tests_status), encoding="utf-8")
    summary_path = tmp_path / "code_change_summary.md"
    summary_path.write_text("External code change summary.\n", encoding="utf-8")
    state["tests_status_path"] = str(tests_path)
    state["code_change_summary_path"] = str(summary_path)

    assert route_after_codex_handoff(state) == "analysis_engineer"
    assert state["route_decisions"][-1]["fields"]["tests_status"] == "tests_passed"


def test_codex_handoff_routes_failed_tests_to_safe_end(tmp_path: Path) -> None:
    state = _state(tmp_path)
    tests_status = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "test_runner",
        "status": "tests_failed",
        "summary": "One configured verification command failed.",
        "warnings": [],
        "errors": [],
        "commands": [
            {
                "command": "pytest tests/test_coder_task_packet.py -q",
                "working_directory": str(tmp_path),
                "timeout_seconds": 60,
                "return_code": 1,
                "stdout": "failed",
                "stderr": "",
                "produced_files": [],
                "status": "failed",
            }
        ],
    }
    tests_path = tmp_path / "tests_status.json"
    tests_path.write_text(json.dumps(tests_status), encoding="utf-8")
    state["tests_status_path"] = str(tests_path)

    assert route_after_codex_handoff(state) == "end"
    assert state["route_decisions"][-1]["fields"]["tests_status"] == "tests_failed"


def test_decision_route_records_checkpoint_relevant_metadata(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "low"
    state["recommended_action"] = "accept_mock_result"
    state["decision_log_path"] = str(tmp_path / "decision_log.json")

    assert route_after_decision_coordinator(state) == "memory_report"
    assert state["route_decisions"][-1]["source"] == "decision_coordinator"
    fields = state["route_decisions"][-1]["fields"]
    assert fields["requested_route"] == "memory_report"
    assert fields["proposed_follow_up_route"] == "memory_report"
    assert fields["decision_log_path"] == str(tmp_path / "decision_log.json")


def test_decision_route_records_code_fix_intent_in_state(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "high"
    state["recommended_action"] = "code_fix"
    state["human_approval_required"] = True
    state["code_fix_requested"] = True
    state["decision_log_path"] = str(tmp_path / "decision_log.json")

    assert route_after_decision_coordinator(state) == "human_approval_gate"
    fields = state["route_decisions"][-1]["fields"]
    assert fields["requested_route"] == "human_approval_gate"
    assert fields["proposed_follow_up_route"] == "codex_handoff"
    assert fields["code_fix_requested"] is True


def test_decision_route_records_targeted_rerun_intent_in_state(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "high"
    state["recommended_action"] = "targeted_rerun"
    state["human_approval_required"] = True
    state["rerun_requested"] = True
    state["rerun_target"] = "analysis_engineer"
    state["decision_log_path"] = str(tmp_path / "decision_log.json")

    assert route_after_decision_coordinator(state) == "human_approval_gate"
    fields = state["route_decisions"][-1]["fields"]
    assert fields["requested_route"] == "human_approval_gate"
    assert fields["proposed_follow_up_route"] == "analysis_engineer"
    assert fields["rerun_requested"] is True
    assert fields["rerun_target"] == "analysis_engineer"
