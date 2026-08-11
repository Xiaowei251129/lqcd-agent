import json
from pathlib import Path

import pytest

from lqcd_agent.graph.approval_packet import (
    APPROVAL_PACKET_FILENAME,
    APPROVAL_SUMMARY_FILENAME,
    APPROVAL_PACKET_DIRNAME,
    HUMAN_DECISION_FILENAME,
    parse_human_decision,
    read_flat_human_decision_yaml,
    write_approval_packet,
)
from lqcd_agent.graph.nodes import human_approval_gate_node
from lqcd_agent.graph.routing import route_after_human_approval_gate, select_after_human_approval_gate
from lqcd_agent.graph.state import (
    commit_transition,
    execute_scheduled_attempt,
    initialize_state,
    start_attempt,
    submit_human_response,
    validate_human_response,
)


def _write_json(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _decision_file(
    tmp_path: Path,
    *,
    run_id: str = "run_a",
    case_id: str = "case_a",
    cycle_id: str = "cycle_0001",
    human_request_id: str = "human_request_000001",
    requesting_attempt_id: str = "attempt_000002",
    human_response_id: str | None = "human_response_000001",
    schema_version: str = "0.2",
    decision: str | None,
) -> Path:
    packet_dir = tmp_path / APPROVAL_PACKET_DIRNAME
    packet_dir.mkdir(parents=True, exist_ok=True)
    path = packet_dir / HUMAN_DECISION_FILENAME
    decision_value = "null" if decision is None else f'"{decision}"'
    path.write_text(
        "\n".join(
            [
                f'schema_version: "{schema_version}"',
                f'run_id: "{run_id}"',
                f'case_id: "{case_id}"',
                *(
                    [
                        f'cycle_id: "{cycle_id}"',
                        f'human_request_id: "{human_request_id}"',
                        f'requesting_attempt_id: "{requesting_attempt_id}"',
                        (
                            "human_response_id: null"
                            if human_response_id is None
                            else f'human_response_id: "{human_response_id}"'
                        ),
                    ]
                    if schema_version == "0.2"
                    else []
                ),
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


def _state(
    tmp_path: Path,
    *,
    approval_required: bool = True,
    human_response_id: str | None = None,
    submitted_decision: str = "approve_with_conditions",
    authorization_scope: dict[str, object] | None = None,
):
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
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=lambda active: {**active, "status": "running"},
    )
    coordinator = commit_transition(
        planner,
        source_node="method_planner",
        route="decision_coordinator",
        reason="Approval packet unit-test setup.",
        fields={},
        target_node="decision_coordinator",
        target_attempt_kind="decision_coordinator",
    )
    coordinator = execute_scheduled_attempt(
        coordinator,
        node_name="decision_coordinator",
        attempt_kind="decision_coordinator",
        node=lambda active: {**active, "status": "running"},
    )
    gate = commit_transition(
        coordinator,
        source_node="decision_coordinator",
        route="human_approval_gate",
        reason="Human approval is required.",
        fields={},
        target_node="human_approval_gate",
        target_attempt_kind="human_gate",
        human_request_kind="approval",
        human_authorization_scope=authorization_scope
        or {
            "allowed_decisions": [
                "approve_rerun",
                "approve_with_conditions",
                "reject_or_hold",
                "request_code_change",
            ],
            "allowed_target_nodes": ["analysis_engineer", "codex_handoff", "memory_report"],
            "decision_transition_routes": {
                "approve_rerun": "end",
                "approve_with_conditions": "memory_report",
                "reject_or_hold": "memory_report",
                "request_code_change": "codex_handoff",
            },
            "decision_transition_targets": {
                "approve_rerun": "END",
                "approve_with_conditions": "memory_report",
                "reject_or_hold": "memory_report",
                "request_code_change": "codex_handoff",
            },
        },
    )
    if human_response_id:
        gate = submit_human_response(
            gate,
            payload={
                "decision": submitted_decision,
                "human_request_id": gate["active_human_request_id"],
            },
            payload_reference="inline:test",
        )
        assert gate["active_human_response_id"] == human_response_id
    return start_attempt(
        gate,
        node_name="human_approval_gate",
        attempt_kind="human_gate",
    )


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
    assert packet["schema_version"] == "0.2"
    assert packet["cycle_id"] == "cycle_0001"
    assert packet["human_request_id"] == "human_request_000001"
    assert packet["requesting_attempt_id"] == "attempt_000002"
    assert packet["scientific_review_report"]["path"] == state["scientific_review_report_path"]
    assert {option["decision"] for option in packet["decision_options"]} == {
        "approve_with_conditions",
        "approve_rerun",
        "request_code_change",
        "reject_or_hold",
    }
    template = read_flat_human_decision_yaml(packet_dir / HUMAN_DECISION_FILENAME)
    assert template["schema_version"] == "0.2"
    assert template["cycle_id"] == "cycle_0001"
    assert template["human_request_id"] == "human_request_000001"
    assert template["requesting_attempt_id"] == "attempt_000002"
    assert template["human_response_id"] is None


def test_stale_open_request_state_cannot_allocate_duplicate_response_identity(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    first = submit_human_response(
        state,
        payload={
            "decision": "approve_with_conditions",
            "human_request_id": state["active_human_request_id"],
        },
        payload_reference="inline:first",
    )
    history_path = Path(first["execution_history_path"])
    history_size = len(history_path.read_text(encoding="utf-8").splitlines())

    with pytest.raises(ValueError, match="Human Response counter is not the latest"):
        submit_human_response(
            state,
            payload={
                "decision": "approve_with_conditions",
                "human_request_id": state["active_human_request_id"],
            },
            payload_reference="inline:stale",
        )

    records = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
    submitted = [
        record
        for record in records
        if record.get("record_type") == "human_response" and record.get("event") == "submitted"
    ]
    assert len(records) == history_size
    assert [record["human_response_id"] for record in submitted] == ["human_response_000001"]


def test_no_human_decision_keeps_gate_pending(tmp_path: Path) -> None:
    state = _state(tmp_path)

    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)

    assert state["status"] == "pending"
    assert state["approval_packet_dir"] == str(tmp_path / APPROVAL_PACKET_DIRNAME)
    assert state["human_decision_path"] == str(tmp_path / APPROVAL_PACKET_DIRNAME / HUMAN_DECISION_FILENAME)
    assert route == "memory_report"
    fields = select_after_human_approval_gate(state)["fields"]
    assert fields["actual_route"] == "memory_report"
    assert fields["proposed_follow_up_route"] == "human_approval_gate"


def test_existing_human_decision_file_is_not_overwritten(tmp_path: Path) -> None:
    state = _state(tmp_path, human_response_id="human_response_000001")
    decision_path = _decision_file(tmp_path, decision="approve_with_conditions")
    original = decision_path.read_text(encoding="utf-8")

    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)

    assert decision_path.read_text(encoding="utf-8") == original
    assert state["status"] == "running"
    assert route == "memory_report"


def test_new_human_request_refreshes_current_decision_template(tmp_path: Path) -> None:
    state = _state(tmp_path)
    first = write_approval_packet(state)
    decision_path = Path(str(first["human_decision_path"]))
    _decision_file(tmp_path, decision="approve_with_conditions")
    next_request = dict(state)
    next_request["human_request_index"] = 2
    next_request["active_human_request_id"] = "human_request_000002"
    next_request["human_requesting_attempt_id"] = "attempt_000004"
    next_request["human_request_status"] = "open"
    next_request["active_human_response_id"] = None
    next_request["human_response_status"] = None

    write_approval_packet(next_request)
    refreshed = read_flat_human_decision_yaml(decision_path)

    assert refreshed["human_request_id"] == "human_request_000002"
    assert refreshed["requesting_attempt_id"] == "attempt_000004"
    assert refreshed["human_response_id"] is None
    assert refreshed["decision"] is None


def test_invalid_human_decision_keeps_gate_pending(tmp_path: Path) -> None:
    state = _state(
        tmp_path,
        human_response_id="human_response_000001",
        submitted_decision="ship_it",
    )
    _decision_file(tmp_path, decision="ship_it")

    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)

    assert state["status"] == "pending"
    assert route == "end"
    assert state["errors"][-1]["node"] == "human_approval_gate"
    assert state["errors"][-1]["field"] == "decision"


def test_out_of_scope_human_route_is_invalid_before_target_allocation(tmp_path: Path) -> None:
    state = _state(
        tmp_path,
        human_response_id="human_response_000001",
        authorization_scope={
            "allowed_decisions": ["approve_with_conditions"],
            "allowed_target_nodes": ["memory_report"],
            "decision_transition_routes": {
                "approve_with_conditions": "memory_report",
            },
            "decision_transition_targets": {
                "approve_with_conditions": "memory_report",
            },
        },
        submitted_decision="request_code_change",
    )
    attempt_index = state["attempt_index"]
    _decision_file(tmp_path, decision="request_code_change")

    state = human_approval_gate_node(state)

    assert state["human_response_status"] == "invalid"
    assert state["human_request_status"] == "open"
    assert state["attempt_index"] == attempt_index
    assert state["status"] == "pending"
    assert state["errors"][-1]["field"] == "authorization_scope"


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
    state = _state(
        tmp_path,
        human_response_id="human_response_000001",
        submitted_decision=decision,
    )
    _decision_file(tmp_path, decision=decision)

    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)
    fields = select_after_human_approval_gate(state)["fields"]

    assert state["status"] == expected_status
    assert route == expected_route
    assert fields["human_decision"] == decision
    assert fields["rerun_requested"] is rerun_requested
    assert fields["code_fix_requested"] is code_fix_requested
    if decision == "approve_rerun":
        assert fields["proposed_follow_up_route"] == "analysis_engineer"


def test_approval_projection_does_not_allocate_missing_request_identity(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["active_human_request_id"] = None
    request_index = state["human_request_index"]

    with pytest.raises(ValueError, match="active_human_request_id"):
        write_approval_packet(state)

    assert state["human_request_index"] == request_index
    assert state["active_human_request_id"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cycle_id", "cycle_0002"),
        ("human_request_id", "human_request_000002"),
        ("human_response_id", "human_response_000002"),
    ],
)
def test_parse_rejects_stale_response_identity(tmp_path: Path, field: str, value: str) -> None:
    path = _decision_file(tmp_path, decision="approve_with_conditions", **{field: value})

    result = parse_human_decision(
        path,
        run_id="run_a",
        case_id="case_a",
        cycle_id="cycle_0001",
        human_request_id="human_request_000001",
        requesting_attempt_id="attempt_000002",
        human_response_id="human_response_000001",
    )

    assert result["status"] == "invalid"
    assert result["decision"] is None
    assert any(error["field"] == field for error in result["errors"])


def test_submitted_decision_requires_runtime_response_identity(tmp_path: Path) -> None:
    path = _decision_file(
        tmp_path,
        decision="approve_with_conditions",
        human_response_id=None,
    )

    result = parse_human_decision(
        path,
        run_id="run_a",
        case_id="case_a",
        cycle_id="cycle_0001",
        human_request_id="human_request_000001",
        requesting_attempt_id="attempt_000002",
    )

    assert result["status"] == "invalid"
    assert any(error["field"] == "human_response_id" for error in result["errors"])


def test_parser_rejects_response_identity_when_runtime_expects_none(tmp_path: Path) -> None:
    path = _decision_file(tmp_path, decision="approve_with_conditions")

    result = parse_human_decision(
        path,
        run_id="run_a",
        case_id="case_a",
        cycle_id="cycle_0001",
        human_request_id="human_request_000001",
        requesting_attempt_id="attempt_000002",
        human_response_id=None,
    )

    assert result["status"] == "invalid"
    assert any(error["field"] == "human_response_id" for error in result["errors"])


def test_legacy_decision_is_rejected_by_default(tmp_path: Path) -> None:
    path = _decision_file(tmp_path, schema_version="0.1", decision="approve_with_conditions")

    result = parse_human_decision(path, run_id="run_a", case_id="case_a")

    assert result["status"] == "invalid"
    assert any(error["field"] == "schema_version" for error in result["errors"])


def test_legacy_import_requires_explicit_active_request_binding(tmp_path: Path) -> None:
    path = _decision_file(tmp_path, schema_version="0.1", decision="approve_with_conditions")

    result = parse_human_decision(
        path,
        run_id="run_a",
        case_id="case_a",
        legacy_import=True,
    )

    assert result["status"] == "invalid"
    assert any(error["field"] == "legacy_import" for error in result["errors"])


def test_explicit_legacy_import_binds_runtime_identities(tmp_path: Path) -> None:
    path = _decision_file(tmp_path, schema_version="0.1", decision="approve_with_conditions")

    result = parse_human_decision(
        path,
        run_id="run_a",
        case_id="case_a",
        cycle_id="cycle_0001",
        human_request_id="human_request_000001",
        requesting_attempt_id="attempt_000002",
        human_response_id="human_response_000001",
        legacy_import=True,
        legacy_open_request_ids=["human_request_000001"],
    )

    assert result["status"] == "approved"
    assert result["payload"]["schema_version"] == "0.2"
    assert result["payload"]["imported_schema_version"] == "0.1"
    assert result["payload"]["human_request_id"] == "human_request_000001"
    assert result["payload"]["human_response_id"] == "human_response_000001"
    assert read_flat_human_decision_yaml(path)["schema_version"] == "0.1"


def test_legacy_import_rejects_non_unique_open_request_binding(tmp_path: Path) -> None:
    path = _decision_file(tmp_path, schema_version="0.1", decision="approve_with_conditions")

    result = parse_human_decision(
        path,
        run_id="run_a",
        case_id="case_a",
        cycle_id="cycle_0001",
        human_request_id="human_request_000001",
        requesting_attempt_id="attempt_000002",
        human_response_id="human_response_000001",
        legacy_import=True,
        legacy_open_request_ids=["human_request_000001", "human_request_000002"],
    )

    assert result["status"] == "invalid"
    assert any(error["field"] == "legacy_open_request_ids" for error in result["errors"])


def test_only_running_human_gate_attempt_can_validate_response(tmp_path: Path) -> None:
    state = _state(tmp_path, human_response_id="human_response_000001")
    forged = dict(state)
    forged["attempt_kind"] = "method_planner"

    with pytest.raises(ValueError, match="running Human Gate"):
        validate_human_response(
            forged,
            validator_attempt_id=str(forged["attempt_id"]),
            valid=True,
            authorized_route="memory_report",
        )
