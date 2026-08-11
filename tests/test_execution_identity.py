import json
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from lqcd_agent.graph.analysis_graph import (
    build_state_graph,
    compile_analysis_graph,
    execute_graph_node_transition,
)
from lqcd_agent.graph.routing import committed_route
from lqcd_agent.graph.state import (
    AnalysisState,
    abandon_attempt,
    commit_external_transition,
    commit_transition,
    execute_scheduled_attempt,
    finish_attempt,
    initialize_state,
    start_attempt,
    submit_human_response,
    validate_human_response,
)


def _state(tmp_path: Path, *, run_id: str = "run_a", parent_run_id: str | None = None):
    case_path = tmp_path / f"{run_id}.yaml"
    case_path.write_text('case_id: "case_a"\n', encoding="utf-8")
    return initialize_state(
        case_id="case_a",
        run_id=run_id,
        user_goal="mock goal",
        case_config_path=str(case_path),
        output_dir=str(tmp_path / run_id),
        parent_run_id=parent_run_id,
        run_creation_reason="fork" if parent_run_id else "initial",
        checkpoint_backend="memory",
    )


def _history(state) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]


def _successful_node(active):
    result = dict(active)
    result["status"] = "running"
    return result


def test_initialize_state_creates_run_cycle_planner_and_start_transition(tmp_path: Path) -> None:
    state = _state(tmp_path)
    records = _history(state)

    assert state["cycle_id"] == "cycle_0001"
    assert state["attempt_id"] == "attempt_000001"
    assert state["attempt_kind"] == "method_planner"
    assert state["attempt_node"] == "method_planner"
    assert state["attempt_status"] == "scheduled"
    assert state["inbound_transition_id"] == "transition_000001"
    assert state["committed_transition_id"] == "transition_000001"
    assert state["transition_index"] == 1
    assert state["committed_route"] == "method_planner"
    assert state["checkpoint_thread_id"] == "case_a:run_a"
    assert [(record["record_type"], record["event"]) for record in records[:4]] == [
        ("run", "created"),
        ("cycle", "created"),
        ("attempt", "scheduled"),
        ("transition", "committed"),
    ]
    assert records[0]["canonical_output_root"] == str((tmp_path / "run_a").resolve())
    assert records[0]["root_goal_reference"]["sha256"]
    assert records[0]["input_snapshot_reference"]["sha256"]
    assert records[3]["source_attempt_id"] is None
    assert records[3]["target_attempt_id"] == "attempt_000001"
    assert records[3]["transition_id"] == "transition_000001"
    assert records[3]["transition_index"] == 1
    assert records[3]["status"] == "committed"
    assert records[3]["committed_at"]


def test_transition_preallocates_target_before_target_execution(tmp_path: Path) -> None:
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    scheduled = commit_transition(
        planner,
        source_node="method_planner",
        route="analysis_engineer",
        reason="Plan is ready.",
        fields={"code_needed": False},
        target_node="analysis_engineer",
        target_attempt_kind="analysis_engineer",
    )

    assert scheduled["attempt_id"] == "attempt_000002"
    assert scheduled["parent_attempt_id"] == "attempt_000001"
    assert scheduled["attempt_status"] == "scheduled"
    assert scheduled["inbound_transition_id"] == "transition_000002"
    assert scheduled["committed_transition_id"] == "transition_000002"
    assert scheduled["transition_index"] == 2
    assert scheduled["route_decisions"][-1]["source_attempt_id"] == "attempt_000001"
    assert scheduled["route_decisions"][-1]["target_attempt_id"] == "attempt_000002"
    attempt_records = [record for record in _history(scheduled) if record["record_type"] == "attempt"]
    target_records = [record for record in attempt_records if record["attempt_id"] == "attempt_000002"]
    assert [record["event"] for record in target_records] == ["scheduled"]
    transition = scheduled["route_decisions"][-1]
    assert transition["trigger_reason"] == "forward"
    assert transition["applied_state_update_keys"] == []
    assert transition["applied_state_updates_sha256"]

    finished = execute_scheduled_attempt(
        scheduled,
        node_name="analysis_engineer",
        attempt_kind="analysis_engineer",
        node=_successful_node,
    )
    target_records = [
        record
        for record in _history(finished)
        if record["record_type"] == "attempt" and record["attempt_id"] == "attempt_000002"
    ]
    assert [record["event"] for record in target_records] == ["scheduled", "started", "finished"]


def test_target_rejects_missing_or_mismatched_preallocation(tmp_path: Path) -> None:
    state = _state(tmp_path)

    with pytest.raises(ValueError, match="does not match"):
        start_attempt(state, node_name="analysis_engineer", attempt_kind="analysis_engineer")

    active = start_attempt(state, node_name="method_planner", attempt_kind="method_planner")
    with pytest.raises(ValueError, match="not scheduled"):
        start_attempt(active, node_name="method_planner", attempt_kind="method_planner")

    missing_inbound = dict(_state(tmp_path, run_id="missing_inbound"))
    missing_inbound["inbound_transition_id"] = None
    with pytest.raises(ValueError, match="no committed inbound"):
        start_attempt(missing_inbound, node_name="method_planner", attempt_kind="method_planner")


def test_duplicate_outbound_transition_is_rejected_without_side_effects(tmp_path: Path) -> None:
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    committed = commit_transition(
        planner,
        source_node="method_planner",
        route="analysis_engineer",
        reason="Plan is ready.",
        fields={},
        target_node="analysis_engineer",
        target_attempt_kind="analysis_engineer",
    )
    history_size = len(_history(committed))

    with pytest.raises(ValueError, match="already has a committed outbound"):
        commit_transition(
            planner,
            source_node="method_planner",
            route="decision_coordinator",
            reason="Conflicting duplicate route.",
            fields={},
            target_node="decision_coordinator",
            target_attempt_kind="decision_coordinator",
        )

    assert len(_history(committed)) == history_size
    assert committed["attempt_index"] == 2
    assert committed["transition_index"] == 2


def test_stale_external_transition_state_is_rejected_before_duplicate_allocation(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    committed = commit_external_transition(
        planner,
        source_name="EXTERNAL_CONTROL",
        route="analysis_engineer",
        reason="Schedule one external continuation.",
        fields={},
        target_node="analysis_engineer",
        target_attempt_kind="analysis_engineer",
        trigger_reason="external_continuation",
    )
    history_size = len(_history(committed))

    with pytest.raises(ValueError, match="counter is not the latest execution ledger head"):
        commit_external_transition(
            planner,
            source_name="EXTERNAL_CONTROL",
            route="analysis_engineer",
            reason="Stale duplicate continuation.",
            fields={},
            target_node="analysis_engineer",
            target_attempt_kind="analysis_engineer",
            trigger_reason="external_continuation",
        )

    assert len(_history(committed)) == history_size
    assert committed["attempt_index"] == 2
    assert committed["transition_index"] == 2


def test_route_updates_cannot_modify_control_identity(tmp_path: Path) -> None:
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )

    with pytest.raises(ValueError, match="cannot update identity fields"):
        commit_transition(
            planner,
            source_node="method_planner",
            route="analysis_engineer",
            reason="Invalid identity mutation.",
            fields={},
            state_updates={"attempt_id": "agent_selected_attempt"},
            target_node="analysis_engineer",
            target_attempt_kind="analysis_engineer",
        )


def test_node_identity_mutation_fails_original_attempt_and_cannot_retry(tmp_path: Path) -> None:
    state = _state(tmp_path)

    def mutating_node(active):
        return {**active, "attempt_id": "agent_selected_attempt", "status": "running"}

    with pytest.raises(ValueError, match="modified control-plane identity"):
        execute_scheduled_attempt(
            state,
            node_name="method_planner",
            attempt_kind="method_planner",
            node=mutating_node,
        )

    records = [
        record
        for record in _history(state)
        if record["record_type"] == "attempt" and record["attempt_id"] == "attempt_000001"
    ]
    assert records[-1]["status"] == "failed"
    assert not any(record.get("attempt_id") == "agent_selected_attempt" for record in _history(state))
    with pytest.raises(ValueError, match="latest scheduled lifecycle"):
        execute_scheduled_attempt(
            state,
            node_name="method_planner",
            attempt_kind="method_planner",
            node=_successful_node,
        )


def test_in_place_node_identity_mutation_cannot_escape_control_plane(tmp_path: Path) -> None:
    state = _state(tmp_path)

    def mutating_node(active):
        active["attempt_id"] = "agent_selected_attempt"
        active["current_node"] = "analysis_engineer"
        return active

    with pytest.raises(ValueError, match="modified control-plane identity"):
        execute_scheduled_attempt(
            state,
            node_name="method_planner",
            attempt_kind="method_planner",
            node=mutating_node,
        )

    records = _history(state)
    assert not any(record.get("attempt_id") == "agent_selected_attempt" for record in records)
    planner_records = [
        record
        for record in records
        if record["record_type"] == "attempt" and record["attempt_id"] == "attempt_000001"
    ]
    assert planner_records[-1]["status"] == "failed"


def test_in_place_selector_mutation_cannot_commit_transition(tmp_path: Path) -> None:
    state = _state(tmp_path)

    def mutating_selector(completed):
        completed["attempt_id"] = "router_selected_attempt"
        return {
            "route": "analysis_engineer",
            "reason": "Invalid selector mutation.",
            "fields": {},
            "state_updates": {},
        }

    with pytest.raises(ValueError, match="Route selector modified its input state"):
        execute_graph_node_transition(
            state,
            node_name="method_planner",
            attempt_kind="method_planner",
            node=_successful_node,
            route_selector=mutating_selector,
            route_targets={"analysis_engineer": ("analysis_engineer", "analysis_engineer")},
        )

    records = _history(state)
    assert not any(record.get("attempt_id") == "router_selected_attempt" for record in records)
    assert [record for record in records if record["record_type"] == "transition"][-1][
        "transition_id"
    ] == "transition_000001"


def test_scheduled_attempt_can_be_abandoned_but_not_reused(tmp_path: Path) -> None:
    state = _state(tmp_path)
    abandoned = abandon_attempt(state, reason="Transition was superseded before execution.")

    assert abandoned["attempt_status"] == "abandoned"
    assert _history(abandoned)[-1]["event"] == "abandoned"
    with pytest.raises(ValueError, match="not scheduled"):
        start_attempt(abandoned, node_name="method_planner", attempt_kind="method_planner")


def test_stale_attempt_state_cannot_repeat_terminal_lifecycle_events(tmp_path: Path) -> None:
    state = _state(tmp_path)
    active = start_attempt(state, node_name="method_planner", attempt_kind="method_planner")
    finished = finish_attempt(active, status="succeeded")
    history_size = len(_history(finished))

    with pytest.raises(ValueError, match="latest running lifecycle"):
        finish_attempt(active, status="succeeded")

    assert len(_history(finished)) == history_size

    second = _state(tmp_path, run_id="abandon_once")
    abandoned = abandon_attempt(second, reason="Superseded before execution.")
    abandoned_history_size = len(_history(abandoned))

    with pytest.raises(ValueError, match="latest scheduled lifecycle"):
        abandon_attempt(second, reason="Stale duplicate abandonment.")

    assert len(_history(abandoned)) == abandoned_history_size


def test_node_exception_records_failed_attempt_and_is_re_raised(tmp_path: Path) -> None:
    state = _state(tmp_path)

    def failing_node(active):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        execute_scheduled_attempt(
            state,
            node_name="method_planner",
            attempt_kind="method_planner",
            node=failing_node,
        )

    attempt_records = [record for record in _history(state) if record["record_type"] == "attempt"]
    assert attempt_records[-1]["status"] == "failed"
    assert attempt_records[-1]["error"] == {"message": "boom", "type": "RuntimeError"}


def test_stategraph_retry_cannot_reuse_failed_attempt(tmp_path: Path) -> None:
    state = _state(tmp_path)

    def wrapper(current):
        return execute_graph_node_transition(
            current,
            node_name="method_planner",
            attempt_kind="method_planner",
            node=lambda active: (_ for _ in ()).throw(RuntimeError("boom")),
            route_selector=lambda completed: {
                "route": "end",
                "reason": "Unreachable after failure.",
                "fields": {},
                "state_updates": {},
            },
            route_targets={"end": None},
        )

    graph = StateGraph(AnalysisState)
    graph.add_node("method_planner", wrapper)
    graph.add_edge(START, "method_planner")
    graph.add_edge("method_planner", END)
    app = graph.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}

    with pytest.raises(RuntimeError, match="boom"):
        app.invoke(state, config=config)
    with pytest.raises(ValueError, match="latest scheduled lifecycle"):
        app.invoke(state, config=config)

    attempt_records = [
        record
        for record in _history(state)
        if record["record_type"] == "attempt" and record["attempt_id"] == "attempt_000001"
    ]
    assert [record["event"] for record in attempt_records] == ["scheduled", "started", "finished"]


def test_replan_transition_creates_new_cycle_without_cross_cycle_attempt_record(tmp_path: Path) -> None:
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    coordinator = commit_transition(
        planner,
        source_node="method_planner",
        route="decision_coordinator",
        reason="Control review is required.",
        fields={},
        target_node="decision_coordinator",
        target_attempt_kind="decision_coordinator",
    )
    coordinator = execute_scheduled_attempt(
        coordinator,
        node_name="decision_coordinator",
        attempt_kind="decision_coordinator",
        node=_successful_node,
    )
    replanned = commit_transition(
        coordinator,
        source_node="decision_coordinator",
        route="method_planner",
        reason="The method contract must change.",
        fields={"affected_layer": "method"},
        target_node="method_planner",
        target_attempt_kind="method_planner",
        trigger_reason="replan",
        new_cycle=True,
    )

    assert replanned["cycle_id"] == "cycle_0002"
    assert replanned["parent_cycle_id"] == "cycle_0001"
    assert replanned["attempt_id"] == "attempt_000003"
    assert replanned["parent_attempt_id"] == "attempt_000002"
    cycle_two = [
        record
        for record in _history(replanned)
        if record["record_type"] == "cycle" and record["cycle_id"] == "cycle_0002"
    ][0]
    assert "attempt_id" not in cycle_two
    assert cycle_two["created_by_attempt_id"] == "attempt_000002"


@pytest.mark.parametrize(
    ("source_node", "trigger_reason"),
    [
        ("method_planner", "replan"),
        ("decision_coordinator", "forward"),
    ],
)
def test_only_coordinator_replan_can_create_cycle_without_partial_records(
    tmp_path: Path,
    source_node: str,
    trigger_reason: str,
) -> None:
    state = _state(tmp_path, run_id=f"invalid_cycle_{source_node}_{trigger_reason}")
    source = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    if source_node == "decision_coordinator":
        source = commit_transition(
            source,
            source_node="method_planner",
            route="decision_coordinator",
            reason="Prepare invalid replan trigger.",
            fields={},
            target_node="decision_coordinator",
            target_attempt_kind="decision_coordinator",
        )
        source = execute_scheduled_attempt(
            source,
            node_name="decision_coordinator",
            attempt_kind="decision_coordinator",
            node=_successful_node,
        )
    history_size = len(_history(source))
    identity_snapshot = (
        source["cycle_index"],
        source["attempt_index"],
        source["transition_index"],
    )

    with pytest.raises(ValueError, match="Only a Coordinator replan transition"):
        commit_transition(
            source,
            source_node=source_node,
            route="method_planner",
            reason="Invalid Cycle creation.",
            fields={},
            target_node="method_planner",
            target_attempt_kind="method_planner",
            trigger_reason=trigger_reason,
            new_cycle=True,
        )

    assert len(_history(source)) == history_size
    assert (
        source["cycle_index"],
        source["attempt_index"],
        source["transition_index"],
    ) == identity_snapshot


def test_incomplete_run_reentry_validates_run_and_schedules_new_planner(tmp_path: Path) -> None:
    state = _state(tmp_path)
    pending = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=lambda active: {**active, "status": "pending"},
    )
    assert pending["attempt_status"] == "pending"

    reentered = _state(tmp_path)
    records = _history(reentered)
    assert reentered["attempt_id"] == "attempt_000002"
    assert reentered["parent_attempt_id"] == "attempt_000001"
    assert reentered["attempt_trigger"] == "legacy_reentry"
    assert reentered["inbound_transition_id"] == "transition_000002"
    assert reentered["committed_transition_id"] == "transition_000002"
    assert reentered["transition_index"] == 2
    assert len([record for record in records if record["record_type"] == "run"]) == 1
    assert len([record for record in records if record["record_type"] == "cycle"]) == 1

    with pytest.raises(ValueError, match="root_goal_reference"):
        initialize_state(
            case_id="case_a",
            run_id="run_a",
            user_goal="different goal",
            case_config_path=str(tmp_path / "run_a.yaml"),
            output_dir=str(tmp_path / "run_a"),
            checkpoint_backend="memory",
        )


def test_scheduled_bootstrap_reentry_is_idempotent(tmp_path: Path) -> None:
    state = _state(tmp_path)
    history_size = len(_history(state))

    reentered = _state(tmp_path)

    assert reentered["attempt_id"] == "attempt_000001"
    assert reentered["attempt_status"] == "scheduled"
    assert reentered["committed_transition_id"] == "transition_000001"
    assert len(_history(reentered)) == history_size


def test_reentry_rejects_changed_input_snapshot(tmp_path: Path) -> None:
    state = _state(tmp_path)
    case_path = Path(state["case_config_path"])
    case_path.write_text('case_id: "case_a"\nchanged: true\n', encoding="utf-8")

    with pytest.raises(ValueError, match="input_snapshot_reference"):
        initialize_state(
            case_id="case_a",
            run_id="run_a",
            user_goal="mock goal",
            case_config_path=str(case_path),
            output_dir=str(tmp_path / "run_a"),
            checkpoint_backend="memory",
        )


def test_running_attempt_reentry_requires_a04_checkpoint_recovery(tmp_path: Path) -> None:
    state = _state(tmp_path)
    start_attempt(state, node_name="method_planner", attempt_kind="method_planner")

    with pytest.raises(ValueError, match="requires checkpoint recovery defined by A04"):
        _state(tmp_path)


def test_unregistered_target_node_is_rejected_before_allocation(tmp_path: Path) -> None:
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    history_size = len(_history(planner))

    with pytest.raises(ValueError, match="Unsupported graph node"):
        commit_transition(
            planner,
            source_node="method_planner",
            route="unknown_worker",
            reason="Invalid target.",
            fields={},
            target_node="unknown_worker",
            target_attempt_kind="analysis_engineer",
        )

    assert len(_history(planner)) == history_size
    assert planner["attempt_index"] == 1
    assert planner["transition_index"] == 1


def test_route_target_contract_mismatch_fails_before_target_allocation(tmp_path: Path) -> None:
    state = _state(tmp_path)

    with pytest.raises(ValueError, match="does not match declared target"):
        execute_graph_node_transition(
            state,
            node_name="method_planner",
            attempt_kind="method_planner",
            node=_successful_node,
            route_selector=lambda completed: {
                "route": "analysis_engineer",
                "target_node": "scientific_reviewer",
                "target_attempt_kind": "scientific_reviewer",
                "reason": "Invalid target contract.",
                "fields": {},
                "state_updates": {},
            },
            route_targets={"analysis_engineer": ("analysis_engineer", "analysis_engineer")},
        )

    records = _history(state)
    assert len([record for record in records if record["record_type"] == "attempt"]) == 3
    assert len([record for record in records if record["record_type"] == "transition"]) == 1


def test_terminal_memory_report_run_requires_replay_or_fork(tmp_path: Path) -> None:
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    report = commit_transition(
        planner,
        source_node="method_planner",
        route="memory_report",
        reason="Test terminal report.",
        fields={},
        target_node="memory_report",
        target_attempt_kind="memory_report",
    )
    report = execute_scheduled_attempt(
        report,
        node_name="memory_report",
        attempt_kind="memory_report",
        node=_successful_node,
    )
    commit_transition(
        report,
        source_node="memory_report",
        route="end",
        reason="Report completed.",
        fields={},
    )

    with pytest.raises(ValueError, match="terminal Run cannot be re-entered"):
        _state(tmp_path)


def test_reentry_pairs_response_only_with_its_human_request(tmp_path: Path) -> None:
    scope = {
        "allowed_decisions": ["approve_with_conditions"],
        "allowed_target_nodes": ["memory_report"],
        "decision_transition_routes": {
            "approve_with_conditions": "memory_report",
        },
        "decision_transition_targets": {
            "approve_with_conditions": "memory_report",
        },
    }
    state = _state(tmp_path)
    planner = execute_scheduled_attempt(
        state,
        node_name="method_planner",
        attempt_kind="method_planner",
        node=_successful_node,
    )
    coordinator = commit_transition(
        planner,
        source_node="method_planner",
        route="decision_coordinator",
        reason="Human identity setup.",
        fields={},
        target_node="decision_coordinator",
        target_attempt_kind="decision_coordinator",
    )
    coordinator = execute_scheduled_attempt(
        coordinator,
        node_name="decision_coordinator",
        attempt_kind="decision_coordinator",
        node=_successful_node,
    )
    gate = commit_transition(
        coordinator,
        source_node="decision_coordinator",
        route="human_approval_gate",
        reason="Create the first request.",
        fields={},
        target_node="human_approval_gate",
        target_attempt_kind="human_gate",
        human_request_kind="approval",
        human_authorization_scope=scope,
    )
    gate = submit_human_response(
        gate,
        payload={
            "decision": "approve_with_conditions",
            "human_request_id": gate["active_human_request_id"],
        },
        payload_reference="inline:test",
    )
    gate = start_attempt(gate, node_name="human_approval_gate", attempt_kind="human_gate")
    gate = validate_human_response(
        gate,
        validator_attempt_id=str(gate["attempt_id"]),
        valid=True,
        decision_payload={"decision": "approve_with_conditions"},
        authorized_route="memory_report",
    )
    gate = finish_attempt(gate, status="succeeded")
    report = commit_transition(
        gate,
        source_node="human_approval_gate",
        route="memory_report",
        reason="Consume the first response.",
        fields={},
        target_node="memory_report",
        target_attempt_kind="memory_report",
    )
    report = execute_scheduled_attempt(
        report,
        node_name="memory_report",
        attempt_kind="memory_report",
        node=_successful_node,
    )
    coordinator = commit_transition(
        report,
        source_node="memory_report",
        route="decision_coordinator",
        reason="Create another request for re-entry validation.",
        fields={},
        target_node="decision_coordinator",
        target_attempt_kind="decision_coordinator",
    )
    coordinator = execute_scheduled_attempt(
        coordinator,
        node_name="decision_coordinator",
        attempt_kind="decision_coordinator",
        node=_successful_node,
    )
    second_gate = commit_transition(
        coordinator,
        source_node="decision_coordinator",
        route="human_approval_gate",
        reason="Create the second request.",
        fields={},
        target_node="human_approval_gate",
        target_attempt_kind="human_gate",
        human_request_kind="approval",
        human_authorization_scope=scope,
    )
    abandon_attempt(second_gate, reason="Leave the second request open for compatibility re-entry.")

    reentered = _state(tmp_path)

    assert reentered["active_human_request_id"] == "human_request_000002"
    assert reentered["human_request_status"] == "open"
    assert reentered["active_human_response_id"] is None
    assert reentered["human_response_status"] is None
    assert reentered["human_response_index"] == 1


def test_parent_linked_run_has_independent_root_and_thread(tmp_path: Path) -> None:
    parent = _state(tmp_path, run_id="parent")
    child = _state(tmp_path, run_id="child", parent_run_id=parent["run_id"])

    child_run_record = _history(child)[0]
    assert child_run_record["parent_run_id"] == "parent"
    assert child_run_record["creation_reason"] == "fork"
    assert child["checkpoint_thread_id"] == "case_a:child"
    assert child["output_dir"] != parent["output_dir"]


@pytest.mark.parametrize(
    ("route", "target_node", "target_kind", "trigger", "new_cycle"),
    [
        ("scientific_reviewer", "scientific_reviewer", "scientific_reviewer", "re_review", False),
        ("analysis_engineer", "analysis_engineer", "analysis_engineer", "analysis_rerun", False),
        ("code_agent", "code_agent", "code_agent", "code_fix", False),
        ("method_planner", "method_planner", "method_planner", "replan", True),
    ],
)
def test_control_plane_stategraph_harness_exercises_fallback_identity(
    tmp_path: Path,
    route: str,
    target_node: str,
    target_kind: str,
    trigger: str,
    new_cycle: bool,
) -> None:
    state = _state(tmp_path, run_id=trigger)

    def planner_wrapper(current):
        is_initial = current["attempt_trigger"] == "initial"
        return execute_graph_node_transition(
            current,
            node_name="method_planner",
            attempt_kind="method_planner",
            node=_successful_node,
            route_selector=lambda completed: {
                "route": "decision_coordinator" if is_initial else "end",
                "reason": "Harness bootstrap." if is_initial else "Harness replanned target completed.",
                "fields": {},
                "state_updates": {},
                "trigger_reason": "forward",
                "new_cycle": False,
            },
            route_targets={
                "decision_coordinator": ("decision_coordinator", "decision_coordinator"),
                "end": None,
            },
        )

    def coordinator_wrapper(current):
        return execute_graph_node_transition(
            current,
            node_name="decision_coordinator",
            attempt_kind="decision_coordinator",
            node=_successful_node,
            route_selector=lambda completed: {
                "route": route,
                "reason": f"Harness dispatch for {trigger}.",
                "fields": {"trigger": trigger},
                "state_updates": {},
                "trigger_reason": trigger,
                "new_cycle": new_cycle,
            },
            route_targets={route: (target_node, target_kind)},
        )

    def target_wrapper(current):
        return execute_graph_node_transition(
            current,
            node_name=target_node,
            attempt_kind=target_kind,
            node=_successful_node,
            route_selector=lambda completed: {
                "route": "end",
                "reason": "Harness target completed.",
                "fields": {},
                "state_updates": {},
                "trigger_reason": "forward",
                "new_cycle": False,
            },
            route_targets={"end": None},
        )

    graph = StateGraph(AnalysisState)
    graph.add_node("method_planner", planner_wrapper)
    graph.add_node("decision_coordinator", coordinator_wrapper)
    if target_node != "method_planner":
        graph.add_node(target_node, target_wrapper)
    graph.add_edge(START, "method_planner")
    graph.add_conditional_edges(
        "method_planner",
        committed_route,
        {"decision_coordinator": "decision_coordinator", "end": END},
    )
    graph.add_conditional_edges("decision_coordinator", committed_route, {route: target_node})
    if target_node != "method_planner":
        graph.add_edge(target_node, END)
    final_state = graph.compile(checkpointer=MemorySaver()).invoke(
        state,
        config={"configurable": {"thread_id": state["checkpoint_thread_id"]}},
    )

    finished = [
        record
        for record in _history(final_state)
        if record["record_type"] == "attempt" and record["event"] == "finished"
    ]
    assert finished[-1]["attempt_kind"] == target_kind
    assert finished[-1]["attempt_trigger"] == trigger
    assert final_state["cycle_index"] == (2 if new_cycle else 1)


def test_compiled_graph_uses_canonical_kinds_and_bound_transitions(tmp_path: Path) -> None:
    run_dir = tmp_path / "mock_lqcd_goal" / "identity_smoke"
    state = initialize_state(
        case_id="mock_lqcd_goal",
        run_id="identity_smoke",
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path="configs/cases/mock_lqcd_goal.yaml",
        output_dir=str(run_dir),
        checkpoint_backend="memory",
    )
    app = compile_analysis_graph(MemorySaver())
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}

    final_state = app.invoke(state, config=config)
    records = _history(final_state)
    finished = [
        record
        for record in records
        if record["record_type"] == "attempt" and record["event"] == "finished"
    ]
    transitions = [record for record in records if record["record_type"] == "transition"]

    assert [record["attempt_kind"] for record in finished] == [
        "method_planner",
        "analysis_engineer",
        "scientific_reviewer",
        "decision_coordinator",
        "memory_report",
    ]
    assert transitions[-1]["route"] == "end"
    assert transitions[-1]["target_attempt_id"] is None
    assert [record["transition_index"] for record in transitions] == list(
        range(1, len(transitions) + 1)
    )
    assert [record["transition_id"] for record in transitions] == [
        f"transition_{index:06d}" for index in range(1, len(transitions) + 1)
    ]
    for transition in transitions[1:-1]:
        assert transition["source_attempt_id"]
        assert transition["target_attempt_id"]


def test_production_graph_declares_current_compatibility_routes_without_code_agent() -> None:
    graph = build_state_graph()

    assert set(graph.nodes) == {
        "method_planner",
        "codex_handoff",
        "analysis_engineer",
        "scientific_reviewer",
        "decision_coordinator",
        "human_approval_gate",
        "memory_report",
    }
    assert "code_agent" not in graph.nodes
    assert graph.edges == {
        (START, "method_planner"),
        ("scientific_reviewer", "decision_coordinator"),
        ("memory_report", END),
    }
    expected_branches = {
        "method_planner": {
            "analysis_engineer": "analysis_engineer",
            "codex_handoff": "codex_handoff",
            "decision_coordinator": "decision_coordinator",
            "end": END,
        },
        "codex_handoff": {
            "analysis_engineer": "analysis_engineer",
            "end": END,
        },
        "analysis_engineer": {
            "scientific_reviewer": "scientific_reviewer",
            "codex_handoff": "codex_handoff",
            "method_planner": "method_planner",
            "decision_coordinator": "decision_coordinator",
        },
        "decision_coordinator": {
            "human_approval_gate": "human_approval_gate",
            "memory_report": "memory_report",
        },
        "human_approval_gate": {
            "analysis_engineer": "analysis_engineer",
            "codex_handoff": "codex_handoff",
            "memory_report": "memory_report",
            "end": END,
        },
    }
    actual_branches = {
        source: next(iter(branches.values())).ends
        for source, branches in graph.branches.items()
    }
    assert actual_branches == expected_branches
