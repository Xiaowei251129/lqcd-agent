import json
from pathlib import Path

import pytest

from lqcd_agent.graph.approval_packet import (
    APPROVAL_PACKET_FILENAME,
    APPROVAL_SUMMARY_FILENAME,
    APPROVAL_PACKET_DIRNAME,
    HUMAN_DECISION_FILENAME,
    write_approval_packet,
)
from lqcd_agent.graph.nodes import human_approval_gate_node
from lqcd_agent.graph.routing import route_after_human_approval_gate
from lqcd_agent.graph.state import initialize_state


def _write_json(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _decision_file(
    tmp_path: Path,
    *,
    run_id: str = "run_a",
    case_id: str = "case_a",
    decision: str | None,
) -> Path:
    packet_dir = tmp_path / APPROVAL_PACKET_DIRNAME
    packet_dir.mkdir(parents=True, exist_ok=True)
    path = packet_dir / HUMAN_DECISION_FILENAME
    decision_value = "null" if decision is None else f'"{decision}"'
    path.write_text(
        "\n".join(
            [
                'schema_version: "0.1"',
                f'run_id: "{run_id}"',
                f'case_id: "{case_id}"',
                f"decision: {decision_value}",
                'conditions: ""',
                'reason: "Reviewed by test."',
                'decided_by: "tester"',
                'decided_at: "2026-06-19T00:00:00+00:00"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _state(tmp_path: Path, *, approval_required: bool = True):
    state = initialize_state(
        case_id="case_a",
        run_id="run_a",
        user_goal="mock goal",
        case_config_path="case.yaml",
        output_dir=str(tmp_path),
        checkpoint_backend="memory",
    )
    state["risk_level"] = "high" if approval_required else "medium"
    state["recommended_action"] = "pending_human_approval"
    state["human_approval_required"] = approval_required
    state["method_plan_path"] = _write_json(
        tmp_path / "method_plan.json",
        {"schema_version": "0.1", "run_id": "run_a", "case_id": "case_a", "status": "success"},
    )
    state["run_result_path"] = _write_json(
        tmp_path / "run_result.json",
        {"schema_version": "0.1", "run_id": "run_a", "case_id": "case_a", "status": "success"},
    )
    state["scientific_review_report_path"] = _write_json(
        tmp_path / "scientific_review_report.json",
        {"schema_version": "0.1", "run_id": "run_a", "case_id": "case_a", "status": "success"},
    )
    state["decision_log_path"] = _write_json(
        tmp_path / "decision_log.json",
        {
            "schema_version": "0.1",
            "run_id": "run_a",
            "case_id": "case_a",
            "status": "pending",
            "reasons": [{"code": "severe_or_flagged_review_warning"}],
            "next_actions": [{"action": "pending_human_approval", "primary": True}],
            "routing_decision": {"requested_route": "human_approval_gate"},
        },
    )
    return state


def test_approval_packet_is_not_generated_when_approval_is_not_required(tmp_path: Path) -> None:
    state = _state(tmp_path, approval_required=False)

    result = write_approval_packet(state)

    assert result["approval_packet_dir"] is None
    assert not (tmp_path / APPROVAL_PACKET_DIRNAME).exists()


def test_high_risk_generates_approval_packet_and_template(tmp_path: Path) -> None:
    state = _state(tmp_path)

    result = write_approval_packet(state)
    packet_dir = tmp_path / APPROVAL_PACKET_DIRNAME
    packet = json.loads((packet_dir / APPROVAL_PACKET_FILENAME).read_text(encoding="utf-8"))

    assert result["approval_packet_dir"] == str(packet_dir)
    assert (packet_dir / APPROVAL_SUMMARY_FILENAME).exists()
    assert (packet_dir / HUMAN_DECISION_FILENAME).exists()
    assert packet["requested_decision"]["risk_level"] == "high"
    assert packet["scientific_review_report"]["path"] == state["scientific_review_report_path"]
    assert {option["decision"] for option in packet["decision_options"]} == {
        "approve_with_conditions",
        "approve_rerun",
        "request_code_change",
        "reject_or_hold",
    }


def test_no_human_decision_keeps_gate_pending(tmp_path: Path) -> None:
    state = _state(tmp_path)

    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)

    assert state["status"] == "pending"
    assert state["approval_packet_dir"] == str(tmp_path / APPROVAL_PACKET_DIRNAME)
    assert state["human_decision_path"] == str(tmp_path / APPROVAL_PACKET_DIRNAME / HUMAN_DECISION_FILENAME)
    assert route == "memory_report"
    assert state["route_decisions"][-1]["fields"]["actual_route"] == "memory_report"
    assert state["route_decisions"][-1]["fields"]["proposed_follow_up_route"] == "human_approval_gate"


def test_existing_human_decision_file_is_not_overwritten(tmp_path: Path) -> None:
    state = _state(tmp_path)
    decision_path = _decision_file(tmp_path, decision="approve_with_conditions")
    original = decision_path.read_text(encoding="utf-8")

    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)

    assert decision_path.read_text(encoding="utf-8") == original
    assert state["status"] == "running"
    assert route == "memory_report"


def test_invalid_human_decision_keeps_gate_pending(tmp_path: Path) -> None:
    state = _state(tmp_path)
    _decision_file(tmp_path, decision="ship_it")

    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)

    assert state["status"] == "pending"
    assert route == "end"
    assert state["errors"][-1]["node"] == "human_approval_gate"
    assert state["errors"][-1]["field"] == "decision"


@pytest.mark.parametrize(
    ("decision", "expected_route", "expected_status", "rerun_requested", "code_fix_requested"),
    [
        ("approve_with_conditions", "memory_report", "running", False, False),
        ("approve_rerun", "end", "pending", True, False),
        ("request_code_change", "codex_handoff", "running", False, True),
        ("reject_or_hold", "memory_report", "running", False, False),
    ],
)
def test_supported_human_decisions_set_clear_route_fields(
    tmp_path: Path,
    decision: str,
    expected_route: str,
    expected_status: str,
    rerun_requested: bool,
    code_fix_requested: bool,
) -> None:
    state = _state(tmp_path)
    _decision_file(tmp_path, decision=decision)

    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)
    fields = state["route_decisions"][-1]["fields"]

    assert state["status"] == expected_status
    assert route == expected_route
    assert fields["human_decision"] == decision
    assert fields["rerun_requested"] is rerun_requested
    assert fields["code_fix_requested"] is code_fix_requested
    if decision == "approve_rerun":
        assert fields["proposed_follow_up_route"] == "analysis_engineer"
