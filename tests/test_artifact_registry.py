import json
from copy import deepcopy
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from lqcd_agent.artifacts.registry import (
    ARTIFACT_SLOTS,
    INVALIDATED_SLOTS_BY_TARGET_KIND,
    current_artifact_pointer,
    initialize_artifact_registry,
    prepare_attempt_output_dir,
    protect_current_artifact,
    register_artifact_bundle,
    validate_state_artifacts,
)
from lqcd_agent.graph.state import (
    AnalysisState,
    commit_external_transition,
    commit_transition,
    execute_scheduled_attempt,
    finish_attempt,
    initialize_state,
    start_attempt,
    submit_human_response,
    validate_human_response,
)


def _state(tmp_path: Path, run_id: str = "artifact_run") -> AnalysisState:
    case_path = tmp_path / f"{run_id}.yaml"
    case_path.write_text('case_id: "case_a"\n', encoding="utf-8")
    return initialize_state(
        case_id="case_a",
        run_id=run_id,
        user_goal="artifact registry test",
        case_config_path=str(case_path),
        output_dir=str(tmp_path / run_id),
        checkpoint_backend="memory",
    )


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _bundle_node(slot: str, marker: str, *, status: str = "success"):
    def node(active: AnalysisState) -> AnalysisState:
        artifact_dir = prepare_attempt_output_dir(active)
        if slot == "plan":
            path = _write(artifact_dir / "method_plan.json", f'{{"marker": "{marker}"}}\n')
            state_paths = {"method_plan_path": path, "coder_task_packet_path": None}
        elif slot == "code":
            summary = _write(artifact_dir / "code_change_summary.md", f"{marker}\n")
            tests = _write(artifact_dir / "tests_status.json", '{"status": "tests_passed"}\n')
            state_paths = {"code_change_summary_path": summary, "tests_status_path": tests}
        elif slot == "analysis":
            result = _write(artifact_dir / "run_result.json", f'{{"marker": "{marker}"}}\n')
            output_dir = artifact_dir / "analysis_outputs"
            _write(output_dir / "result.json", f'{{"marker": "{marker}"}}\n')
            state_paths = {"run_result_path": result, "analysis_outputs_dir": str(output_dir)}
        elif slot == "review":
            path = _write(artifact_dir / "scientific_review_report.json", f'{{"marker": "{marker}"}}\n')
            state_paths = {"scientific_review_report_path": path}
        elif slot == "decision":
            path = _write(artifact_dir / "decision_log.json", f'{{"marker": "{marker}"}}\n')
            state_paths = {"decision_log_path": path}
        elif slot == "terminal":
            memory = _write(artifact_dir / "memory_update.json", f'{{"marker": "{marker}"}}\n')
            report = _write(artifact_dir / "final_report.md", f"{marker}\n")
            state_paths = {"memory_update_path": memory, "final_report_path": report}
        else:
            raise AssertionError(f"Unsupported test bundle slot: {slot}")
        updated = register_artifact_bundle(
            active,
            slot=slot,
            member_paths=[artifact_dir],
            state_paths=state_paths,
            status=status,
        )
        updated["status"] = "running"
        return updated

    return node


def _run_attempt(state: AnalysisState, node_name: str, attempt_kind: str, slot: str) -> AnalysisState:
    return execute_scheduled_attempt(
        state,
        node_name=node_name,
        attempt_kind=attempt_kind,
        node=_bundle_node(slot, str(state["attempt_id"])),
    )


def _schedule(
    state: AnalysisState,
    *,
    source: str,
    target: str,
    kind: str,
    trigger_reason: str = "forward",
    new_cycle: bool = False,
) -> AnalysisState:
    return commit_transition(
        state,
        source_node=source,
        route=target,
        reason="Artifact registry test transition.",
        fields={},
        target_node=target,
        target_attempt_kind=kind,
        trigger_reason=trigger_reason,
        new_cycle=new_cycle,
    )


def _decision_chain(tmp_path: Path, run_id: str = "chain") -> AnalysisState:
    state = _run_attempt(_state(tmp_path, run_id), "method_planner", "method_planner", "plan")
    state = _schedule(
        state,
        source="method_planner",
        target="codex_handoff",
        kind="legacy_codex_handoff",
    )
    state = _run_attempt(state, "codex_handoff", "legacy_codex_handoff", "code")
    state = _schedule(
        state,
        source="codex_handoff",
        target="analysis_engineer",
        kind="analysis_engineer",
    )
    state = _run_attempt(state, "analysis_engineer", "analysis_engineer", "analysis")
    state = _schedule(
        state,
        source="analysis_engineer",
        target="scientific_reviewer",
        kind="scientific_reviewer",
    )
    state = _run_attempt(state, "scientific_reviewer", "scientific_reviewer", "review")
    state = _schedule(
        state,
        source="scientific_reviewer",
        target="decision_coordinator",
        kind="decision_coordinator",
    )
    return _run_attempt(state, "decision_coordinator", "decision_coordinator", "decision")


def _accepted_terminal_node(active: AnalysisState) -> AnalysisState:
    updated = _bundle_node("terminal", "accepted", status="accepted")(active)
    return protect_current_artifact(updated, slot="terminal", protected_kind="accepted_result")


def _accepted_terminal_state(tmp_path: Path, run_id: str) -> AnalysisState:
    state = _decision_chain(tmp_path, run_id)
    terminal = _schedule(
        state,
        source="decision_coordinator",
        target="memory_report",
        kind="memory_report",
    )
    return execute_scheduled_attempt(
        terminal,
        node_name="memory_report",
        attempt_kind="memory_report",
        node=_accepted_terminal_node,
    )


def _submitted_human_response(tmp_path: Path, run_id: str) -> AnalysisState:
    state = _decision_chain(tmp_path, run_id)
    scope = {
        "allowed_decisions": ["approve_with_conditions"],
        "allowed_target_nodes": ["memory_report"],
        "decision_transition_routes": {"approve_with_conditions": "memory_report"},
        "decision_transition_targets": {"approve_with_conditions": "memory_report"},
    }
    gate = commit_transition(
        state,
        source_node="decision_coordinator",
        route="human_approval_gate",
        reason="Create protected response test request.",
        fields={},
        target_node="human_approval_gate",
        target_attempt_kind="human_gate",
        human_request_kind="approval",
        human_authorization_scope=scope,
    )
    return submit_human_response(
        gate,
        payload={
            "decision": "approve_with_conditions",
            "human_request_id": gate["active_human_request_id"],
        },
        payload_reference="inline:test",
    )


def _artifact_history(state: AnalysisState) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(state["artifact_history_path"]).read_text(encoding="utf-8").splitlines()
    ]


def _write_artifact_history(state: AnalysisState, records: list[dict]) -> None:
    content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    Path(state["artifact_history_path"]).write_text(content, encoding="utf-8")


def _write_artifact_index(state: AnalysisState, index: dict) -> None:
    Path(state["artifact_index_path"]).write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_execution_history(state: AnalysisState, records: list[dict]) -> None:
    content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    Path(state["execution_history_path"]).write_text(content, encoding="utf-8")


def _rewrite_registry_head(
    state: AnalysisState,
    history: list[dict],
    index: dict,
) -> AnalysisState:
    for event_index, record in enumerate(history, 1):
        record["event_index"] = event_index
        record["event_id"] = f"artifact_event_{event_index:06d}"
    _write_artifact_history(state, history)
    index["revision"] = len(history)
    index["last_event_id"] = history[-1]["event_id"] if history else None
    _write_artifact_index(state, index)
    forged = deepcopy(state)
    forged["artifact_event_index"] = len(history)
    forged["current_artifacts"] = deepcopy(index["current"])
    return forged


def test_registration_uses_attempt_namespace_and_managed_projection(tmp_path: Path) -> None:
    state = _run_attempt(_state(tmp_path), "method_planner", "method_planner", "plan")
    pointer = state["current_artifacts"]["plan"]
    canonical = Path(state["method_plan_path"])
    projection = Path(state["output_dir"]) / "method_plan.json"

    assert pointer["artifact_id"] == "attempt_000001:plan"
    assert canonical == Path(state["output_dir"]) / "attempts" / "attempt_000001" / "method_plan.json"
    assert canonical.read_bytes() == projection.read_bytes()
    assert pointer["members"][0]["sha256"]
    assert current_artifact_pointer(state, slot="plan") == pointer
    assert json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))["current"]["plan"] == pointer
    registered = next(record for record in _artifact_history(state) if record["event"] == "registered")
    assert registered["pointer"] == pointer
    assert registered["node_name"] == "method_planner"
    validate_state_artifacts(state)


def test_untampered_registry_restores_exact_current_pointer(tmp_path: Path) -> None:
    state = _run_attempt(_state(tmp_path, "restore"), "method_planner", "method_planner", "plan")

    restored = initialize_artifact_registry(dict(state))

    assert restored["current_artifacts"] == state["current_artifacts"]
    assert restored["method_plan_path"] == state["method_plan_path"]
    validate_state_artifacts(restored)


def test_reconstructed_empty_artifact_state_restores_from_registry(tmp_path: Path) -> None:
    state = _run_attempt(_state(tmp_path, "reconstructed_restore"), "method_planner", "method_planner", "plan")
    reconstructed = dict(state)
    reconstructed["artifact_event_index"] = 0
    reconstructed["current_artifacts"] = {}
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
        reconstructed[field] = None

    restored = initialize_artifact_registry(reconstructed)

    assert restored["artifact_event_index"] == state["artifact_event_index"]
    assert restored["current_artifacts"] == state["current_artifacts"]
    assert restored["method_plan_path"] == state["method_plan_path"]


def test_incomplete_run_reentry_invalidates_existing_artifacts(tmp_path: Path) -> None:
    state = _run_attempt(_state(tmp_path, "reentry_invalidation"), "method_planner", "method_planner", "plan")
    prior_plan_id = state["current_artifacts"]["plan"]["artifact_id"]

    reentered = _state(tmp_path, "reentry_invalidation")

    assert reentered["attempt_id"] == "attempt_000002"
    assert reentered["attempt_status"] == "scheduled"
    assert reentered["current_artifacts"]["plan"] is None
    assert reentered["method_plan_path"] is None
    assert any(
        record["event"] == "current_cleared"
        and record["artifact_id"] == prior_plan_id
        and record["target_attempt_id"] == "attempt_000002"
        for record in _artifact_history(reentered)
    )
    validate_state_artifacts(reentered)


@pytest.mark.parametrize("mutation", ["counter", "pointer", "state_path"])
def test_populated_artifact_state_tampering_is_not_repaired(
    tmp_path: Path,
    mutation: str,
) -> None:
    state = _run_attempt(_state(tmp_path, f"populated_{mutation}"), "method_planner", "method_planner", "plan")
    tampered = deepcopy(state)
    if mutation == "counter":
        tampered["artifact_event_index"] += 1
    elif mutation == "pointer":
        tampered["current_artifacts"]["plan"]["attempt_id"] = "attempt_999999"
    else:
        tampered["method_plan_path"] = str(tmp_path / "forged-plan.json")

    with pytest.raises(ValueError):
        initialize_artifact_registry(tampered)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("attempt_id", "attempt_999999"),
        ("cycle_id", "cycle_9999"),
        ("attempt_kind", "analysis_engineer"),
        ("artifact_id", "attempt_999999:plan"),
        ("status", "tampered"),
        ("members", []),
        ("dependencies", ["attempt_000001:plan"]),
        (
            "state_paths",
            {
                "method_plan_path": "/private/tmp/tampered-method-plan.json",
                "coder_task_packet_path": None,
            },
        ),
    ],
)
def test_index_pointer_tampering_fails_closed(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    state = _run_attempt(_state(tmp_path, f"tamper_{field}"), "method_planner", "method_planner", "plan")
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    index["current"]["plan"][field] = replacement
    _write_artifact_index(state, index)

    with pytest.raises(ValueError, match="replayed artifact history"):
        current_artifact_pointer(state, slot="plan")
    with pytest.raises(ValueError, match="replayed artifact history"):
        initialize_artifact_registry(dict(state))


def test_cross_slot_pointer_substitution_fails_closed(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "cross_slot")
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    substituted = deepcopy(index["current"]["plan"])
    substituted["slot"] = "analysis"
    index["current"]["analysis"] = substituted
    _write_artifact_index(state, index)

    with pytest.raises(ValueError, match="replayed artifact history"):
        initialize_artifact_registry(dict(state))


@pytest.mark.parametrize(
    "projection",
    [
        "../../escape.txt",
        "extra.txt",
        "artifact_index.json",
        "attempts/attempt_999999/forged.json",
        "human_responses/response/payload.json",
        "checkpoints/forged.sqlite",
        "context/forged.json",
        "raw_data/forged.json",
        "accepted_results/forged.json",
    ],
)
def test_extra_managed_projection_entries_fail_closed(
    tmp_path: Path,
    projection: str,
) -> None:
    state = _run_attempt(_state(tmp_path, "extra_projection"), "method_planner", "method_planner", "plan")
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    index["managed_projections"][projection] = "attempt_000001:plan"
    _write_artifact_index(state, index)

    with pytest.raises(ValueError, match="projection|Projection"):
        initialize_artifact_registry(dict(state))


def test_duplicate_managed_projection_key_fails_closed(tmp_path: Path) -> None:
    state = _run_attempt(
        _state(tmp_path, "duplicate_projection"),
        "method_planner",
        "method_planner",
        "plan",
    )
    index_path = Path(state["artifact_index_path"])
    content = index_path.read_text(encoding="utf-8")
    entry = '"method_plan.json": "attempt_000001:plan"'
    index_path.write_text(content.replace(entry, f"{entry},\n    {entry}"), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        initialize_artifact_registry(dict(state))


@pytest.mark.parametrize("mutation", ["missing", "unknown_owner", "wrong_owner"])
def test_managed_projection_owner_mismatch_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    state = _decision_chain(tmp_path, f"projection_{mutation}")
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    if mutation == "missing":
        index["managed_projections"].pop("method_plan.json")
    elif mutation == "unknown_owner":
        index["managed_projections"]["method_plan.json"] = "attempt_999999:plan"
    else:
        index["managed_projections"]["method_plan.json"] = index["current"]["analysis"]["artifact_id"]
    _write_artifact_index(state, index)

    with pytest.raises(ValueError, match="projection|Projection"):
        initialize_artifact_registry(dict(state))


@pytest.mark.parametrize("mutation", ["missing", "identity"])
def test_registered_history_pointer_tampering_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    state = _run_attempt(_state(tmp_path, f"history_{mutation}"), "method_planner", "method_planner", "plan")
    history = _artifact_history(state)
    registered = next(record for record in history if record["event"] == "registered")
    if mutation == "missing":
        registered.pop("pointer")
    else:
        registered["pointer"]["attempt_id"] = "attempt_999999"
    _write_artifact_history(state, history)

    with pytest.raises(ValueError, match="Registered artifact pointer"):
        initialize_artifact_registry(dict(state))


def test_duplicate_artifact_history_key_fails_closed(tmp_path: Path) -> None:
    state = _run_attempt(_state(tmp_path, "duplicate_history_key"), "method_planner", "method_planner", "plan")
    history_path = Path(state["artifact_history_path"])
    content = history_path.read_text(encoding="utf-8")
    history_path.write_text(
        content.replace('"event": "registered"', '"event": "registered", "event": "current_set"', 1),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        initialize_artifact_registry(dict(state))


@pytest.mark.parametrize("mutation", ["missing", "tampered"])
def test_registered_node_identity_tampering_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    state = _run_attempt(_state(tmp_path, f"history_node_{mutation}"), "method_planner", "method_planner", "plan")
    history = _artifact_history(state)
    registered = next(record for record in history if record["event"] == "registered")
    if mutation == "missing":
        registered.pop("node_name")
    else:
        registered["node_name"] = "tampered_node"
    _write_artifact_history(state, history)

    with pytest.raises(ValueError, match="execution ledger"):
        initialize_artifact_registry(dict(state))


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("run_id", "tampered_run"),
        ("case_id", "tampered_case"),
        ("cycle_id", "cycle_9999"),
        ("attempt_id", "attempt_999999"),
        ("attempt_kind", "analysis_engineer"),
        ("node_name", "tampered_node"),
        ("run_id", None),
        ("case_id", None),
        ("cycle_id", None),
        ("attempt_id", None),
        ("attempt_kind", None),
        ("node_name", None),
    ],
)
def test_execution_ledger_identity_tampering_fails_closed(
    tmp_path: Path,
    field: str,
    replacement: str | None,
) -> None:
    state = _run_attempt(_state(tmp_path, f"ledger_{field}"), "method_planner", "method_planner", "plan")
    records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    for record in records:
        if record.get("record_type") == "attempt" and record.get("attempt_id") == "attempt_000001":
            if replacement is None:
                record.pop(field)
            else:
                record[field] = replacement
    _write_execution_history(state, records)

    with pytest.raises(ValueError, match="execution ledger"):
        initialize_artifact_registry(dict(state))


def test_registered_artifact_requires_started_attempt_lifecycle(tmp_path: Path) -> None:
    state = _run_attempt(_state(tmp_path, "missing_started"), "method_planner", "method_planner", "plan")
    records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    records = [
        record
        for record in records
        if not (
            record.get("record_type") == "attempt"
            and record.get("attempt_id") == "attempt_000001"
            and record.get("event") == "started"
        )
    ]
    _write_execution_history(state, records)

    with pytest.raises(ValueError, match="lifecycle is incomplete"):
        initialize_artifact_registry(dict(state))


def test_registered_pointer_kind_must_match_execution_ledger(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "history_kind")
    history = _artifact_history(state)
    registered = next(
        record
        for record in history
        if record["event"] == "registered" and record["slot"] == "code"
    )
    registered["pointer"]["attempt_kind"] = "code_agent"
    _write_artifact_history(state, history)

    with pytest.raises(ValueError, match="execution ledger"):
        initialize_artifact_registry(dict(state))


def test_history_clear_cannot_precede_current_set(tmp_path: Path) -> None:
    state = _run_attempt(_state(tmp_path, "clear_order"), "method_planner", "method_planner", "plan")
    history = _artifact_history(state)
    current_set = next(record for record in history if record["event"] == "current_set")
    current_set["event"] = "current_cleared"
    current_set["prior_artifact_id"] = current_set["artifact_id"]
    _write_artifact_history(state, history)

    with pytest.raises(ValueError, match="current_set"):
        initialize_artifact_registry(dict(state))


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("transition_id", "transition_999999"),
        ("target_attempt_id", "attempt_999999"),
        ("attempt_id", "attempt_999999"),
        ("cycle_id", "cycle_9999"),
        ("reason_code", "target_analysis_engineer"),
    ],
)
def test_current_clear_must_match_target_attempt_provenance(
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    state = _decision_chain(tmp_path, f"clear_provenance_{field}")
    scheduled = _schedule(
        state,
        source="decision_coordinator",
        target="method_planner",
        kind="method_planner",
        trigger_reason="replan",
        new_cycle=True,
    )
    history = _artifact_history(scheduled)
    cleared = next(record for record in history if record["event"] == "current_cleared")
    cleared[field] = replacement
    _write_artifact_history(scheduled, history)

    with pytest.raises(ValueError, match="current_cleared|execution ledger|committed Transition"):
        initialize_artifact_registry(dict(scheduled))


def test_current_clear_must_match_committed_transition_ledger(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "clear_transition_ledger")
    scheduled = _schedule(
        state,
        source="decision_coordinator",
        target="method_planner",
        kind="method_planner",
        trigger_reason="replan",
        new_cycle=True,
    )
    clear = next(
        record
        for record in _artifact_history(scheduled)
        if record["event"] == "current_cleared"
    )
    records = [
        json.loads(line)
        for line in Path(scheduled["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    transition = next(
        record
        for record in records
        if record.get("record_type") == "transition"
        and record.get("transition_id") == clear["transition_id"]
    )
    transition["target_attempt_id"] = "attempt_999999"
    _write_execution_history(scheduled, records)

    with pytest.raises(ValueError, match="target Attempt provenance"):
        initialize_artifact_registry(dict(scheduled))


def test_required_current_clear_cannot_be_deleted_from_history(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "missing_required_clear")
    prior_plan = deepcopy(state["current_artifacts"]["plan"])
    scheduled = _schedule(
        state,
        source="decision_coordinator",
        target="method_planner",
        kind="method_planner",
        trigger_reason="replan",
        new_cycle=True,
    )
    history = _artifact_history(scheduled)
    victim = next(
        event_index
        for event_index, record in enumerate(history)
        if record["event"] == "current_cleared" and record["slot"] == "plan"
    )
    del history[victim]
    index = json.loads(Path(scheduled["artifact_index_path"]).read_text(encoding="utf-8"))
    index["current"]["plan"] = deepcopy(prior_plan)
    index["managed_projections"] = {
        member["projection_path"]: prior_plan["artifact_id"]
        for member in prior_plan["members"]
    }
    forged = _rewrite_registry_head(scheduled, history, index)
    forged["method_plan_path"] = prior_plan["state_paths"]["method_plan_path"]
    forged["coder_task_packet_path"] = prior_plan["state_paths"]["coder_task_packet_path"]
    run_root = Path(forged["output_dir"])
    for member in prior_plan["members"]:
        projection = run_root / member["projection_path"]
        projection.parent.mkdir(parents=True, exist_ok=True)
        projection.write_bytes((run_root / member["canonical_path"]).read_bytes())

    with pytest.raises(ValueError, match="exact required invalidation"):
        initialize_artifact_registry(forged)


def test_cleared_artifact_cannot_be_set_current_again(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "stale_reset")
    old_pointer = deepcopy(state["current_artifacts"]["plan"])
    scheduled = _schedule(
        state,
        source="decision_coordinator",
        target="method_planner",
        kind="method_planner",
        trigger_reason="replan",
        new_cycle=True,
    )
    history = _artifact_history(scheduled)
    template = next(
        record
        for record in history
        if record["event"] == "current_set" and record["artifact_id"] == old_pointer["artifact_id"]
    )
    forged = deepcopy(template)
    forged["event_index"] = len(history) + 1
    forged["event_id"] = f"artifact_event_{len(history) + 1:06d}"
    history.append(forged)
    _write_artifact_history(scheduled, history)
    index = json.loads(Path(scheduled["artifact_index_path"]).read_text(encoding="utf-8"))
    index["revision"] = forged["event_index"]
    index["last_event_id"] = forged["event_id"]
    index["current"]["plan"] = old_pointer
    index["managed_projections"] = {
        member["projection_path"]: old_pointer["artifact_id"]
        for member in old_pointer["members"]
    }
    _write_artifact_index(scheduled, index)
    run_root = Path(scheduled["output_dir"])
    for member in old_pointer["members"]:
        projection = run_root / member["projection_path"]
        projection.parent.mkdir(parents=True, exist_ok=True)
        projection.write_bytes((run_root / member["canonical_path"]).read_bytes())

    with pytest.raises(ValueError, match="only once"):
        initialize_artifact_registry(dict(scheduled))


def test_registered_dependencies_must_match_replayed_current_chain(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "wrong_dependency")
    history = _artifact_history(state)
    review_id = next(
        record["artifact_id"]
        for record in history
        if record["event"] == "registered" and record["slot"] == "review"
    )
    for record in history:
        if record["artifact_id"] != "attempt_000003:analysis":
            continue
        if record["event"] == "registered":
            record["dependencies"] = [review_id]
            record["pointer"]["dependencies"] = [review_id]
        elif record["event"] == "current_set":
            record["dependencies"] = [review_id]
    _write_artifact_history(state, history)
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    index["current"]["analysis"]["dependencies"] = [review_id]
    _write_artifact_index(state, index)

    with pytest.raises(ValueError, match="replayed current history"):
        initialize_artifact_registry(dict(state))


def test_registered_member_must_remain_in_producing_attempt(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "member_attempt")
    history = _artifact_history(state)
    code_record = next(
        record
        for record in history
        if record["event"] == "registered" and record["slot"] == "code"
    )
    source = next(
        member for member in code_record["members"] if member["projection_path"] == "tests_status.json"
    )
    analysis_record = next(
        record
        for record in history
        if record["event"] == "registered" and record["slot"] == "analysis"
    )
    member_index = next(
        index
        for index, member in enumerate(analysis_record["members"])
        if member["projection_path"] == "analysis_outputs/result.json"
    )
    forged = deepcopy(analysis_record["members"][member_index])
    for field in ("canonical_path", "sha256", "size_bytes", "media_type"):
        forged[field] = source[field]
    analysis_record["members"][member_index] = deepcopy(forged)
    analysis_record["pointer"]["members"][member_index] = deepcopy(forged)
    _write_artifact_history(state, history)
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    index["current"]["analysis"]["members"][member_index] = deepcopy(forged)
    _write_artifact_index(state, index)
    run_root = Path(state["output_dir"])
    (run_root / forged["projection_path"]).write_bytes(
        (run_root / forged["canonical_path"]).read_bytes()
    )

    with pytest.raises(ValueError, match="producing Attempt"):
        initialize_artifact_registry(dict(state))


@pytest.mark.parametrize("projection", ["code_change_summary.md", "tests_status.json"])
def test_external_code_ingress_projection_must_exist(
    tmp_path: Path,
    projection: str,
) -> None:
    state = _decision_chain(tmp_path, f"missing_{projection}")
    (Path(state["output_dir"]) / projection).unlink()

    with pytest.raises(ValueError, match="projection is missing"):
        initialize_artifact_registry(dict(state))


def test_cross_slot_projection_collision_fails_before_registry_mutation(tmp_path: Path) -> None:
    state = _run_attempt(_state(tmp_path, "projection_collision"), "method_planner", "method_planner", "plan")
    scheduled = _schedule(
        state,
        source="method_planner",
        target="analysis_engineer",
        kind="analysis_engineer",
    )
    active = start_attempt(scheduled, node_name="analysis_engineer", attempt_kind="analysis_engineer")
    artifact_dir = prepare_attempt_output_dir(active)
    collision = artifact_dir / "method_plan.json"
    collision.write_text("collision bytes\n", encoding="utf-8")
    history_path = Path(active["artifact_history_path"])
    index_path = Path(active["artifact_index_path"])
    projection_path = Path(active["output_dir"]) / "method_plan.json"
    history_before = history_path.read_bytes()
    index_before = index_path.read_bytes()
    projection_before = projection_path.read_bytes()

    with pytest.raises(ValueError, match="owned by another current artifact"):
        register_artifact_bundle(
            active,
            slot="analysis",
            member_paths=[collision],
            state_paths={
                "run_result_path": str(collision),
                "analysis_outputs_dir": str(artifact_dir),
            },
            status="success",
        )

    assert history_path.read_bytes() == history_before
    assert index_path.read_bytes() == index_before
    assert projection_path.read_bytes() == projection_before


def test_duplicate_registration_and_path_escape_fail_closed(tmp_path: Path) -> None:
    state = _state(tmp_path, "duplicate")
    active = start_attempt(state, node_name="method_planner", attempt_kind="method_planner")
    artifact_dir = prepare_attempt_output_dir(active)
    plan_path = _write(artifact_dir / "method_plan.json", "first\n")
    registered = register_artifact_bundle(
        active,
        slot="plan",
        member_paths=[plan_path],
        state_paths={"method_plan_path": plan_path, "coder_task_packet_path": None},
        status="success",
    )
    with pytest.raises(ValueError, match="not invalidated"):
        register_artifact_bundle(
            registered,
            slot="plan",
            member_paths=[plan_path],
            state_paths={"method_plan_path": plan_path, "coder_task_packet_path": None},
            status="success",
        )

    escaped = _state(tmp_path, "escape")
    escaped_active = start_attempt(escaped, node_name="method_planner", attempt_kind="method_planner")
    prepare_attempt_output_dir(escaped_active)
    outside = _write(Path(escaped_active["output_dir"]) / "outside.json", "outside\n")
    with pytest.raises(ValueError, match="escapes the active Attempt"):
        register_artifact_bundle(
            escaped_active,
            slot="plan",
            member_paths=[outside],
            state_paths={"method_plan_path": outside, "coder_task_packet_path": None},
            status="success",
        )


def test_second_analysis_attempt_preserves_first_canonical_bytes(tmp_path: Path) -> None:
    first = _decision_chain(tmp_path, "immutable")
    first_path = Path(first["run_result_path"])
    first_bytes = first_path.read_bytes()
    scheduled = commit_external_transition(
        first,
        source_name="FALLBACK_HARNESS",
        route="analysis_engineer",
        reason="Test analysis rerun.",
        fields={},
        target_node="analysis_engineer",
        target_attempt_kind="analysis_engineer",
        trigger_reason="fallback_analysis_rerun",
    )
    second = _run_attempt(scheduled, "analysis_engineer", "analysis_engineer", "analysis")

    assert Path(second["run_result_path"]) != first_path
    assert first_path.read_bytes() == first_bytes
    assert second["current_artifacts"]["analysis"]["artifact_id"].endswith(":analysis")
    assert any(
        record["event"] == "current_cleared" and record["artifact_id"] == "attempt_000003:analysis"
        for record in _artifact_history(second)
    )


def test_code_invalidation_preserves_changed_external_ingress(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "new_code_ingress")
    run_root = Path(state["output_dir"])
    summary_path = run_root / "code_change_summary.md"
    tests_path = run_root / "tests_status.json"
    summary_path.write_text("new external result\n", encoding="utf-8")
    tests_path.write_text('{"status": "tests_failed", "summary": "new result"}\n', encoding="utf-8")
    restored = initialize_artifact_registry(dict(state))
    owner = restored["current_artifacts"]["code"]["artifact_id"]
    restored_index = json.loads(Path(restored["artifact_index_path"]).read_text(encoding="utf-8"))
    assert restored_index["managed_projections"]["code_change_summary.md"] == owner
    assert restored_index["managed_projections"]["tests_status.json"] == owner

    scheduled = commit_external_transition(
        restored,
        source_name="EXTERNAL_HANDOFF",
        route="codex_handoff",
        reason="A new handoff delivery is ready.",
        fields={},
        target_node="codex_handoff",
        target_attempt_kind="legacy_codex_handoff",
        trigger_reason="external_handoff",
    )

    assert summary_path.read_text(encoding="utf-8") == "new external result\n"
    assert json.loads(tests_path.read_text(encoding="utf-8"))["summary"] == "new result"
    assert scheduled["current_artifacts"]["code"] is None
    assert scheduled["current_artifacts"]["analysis"] is None
    index = json.loads(Path(scheduled["artifact_index_path"]).read_text(encoding="utf-8"))
    assert "code_change_summary.md" not in index["managed_projections"]
    assert "tests_status.json" not in index["managed_projections"]


@pytest.mark.parametrize(
    ("target_node", "target_kind", "kept", "cleared", "new_cycle"),
    [
        (
            "scientific_reviewer",
            "scientific_reviewer",
            {"plan", "code", "analysis"},
            {"review", "decision"},
            False,
        ),
        (
            "analysis_engineer",
            "analysis_engineer",
            {"plan", "code"},
            {"analysis", "review", "decision"},
            False,
        ),
        (
            "codex_handoff",
            "legacy_codex_handoff",
            {"plan"},
            {"code", "analysis", "review", "decision"},
            False,
        ),
        (
            "method_planner",
            "method_planner",
            set(),
            {"plan", "code", "analysis", "review", "decision"},
            True,
        ),
    ],
)
def test_stategraph_fallback_harness_clears_target_layer_before_consumption(
    tmp_path: Path,
    target_node: str,
    target_kind: str,
    kept: set[str],
    cleared: set[str],
    new_cycle: bool,
) -> None:
    state = _decision_chain(tmp_path, f"trajectory_{target_kind}")
    prior = {slot: state["current_artifacts"][slot] for slot in ARTIFACT_SLOTS}
    observed: list[dict] = []

    def commit(current: AnalysisState) -> AnalysisState:
        return _schedule(
            current,
            source="decision_coordinator",
            target=target_node,
            kind=target_kind,
            trigger_reason="replan" if new_cycle else "fallback",
            new_cycle=new_cycle,
        )

    def consume(scheduled: AnalysisState) -> AnalysisState:
        def target(active: AnalysisState) -> AnalysisState:
            observed.append(dict(active["current_artifacts"]))
            return {**active, "status": "pending"}

        return execute_scheduled_attempt(
            scheduled,
            node_name=target_node,
            attempt_kind=target_kind,
            node=target,
        )

    graph = StateGraph(AnalysisState)
    graph.add_node("commit", commit)
    graph.add_node("consume", consume)
    graph.add_edge(START, "commit")
    graph.add_edge("commit", "consume")
    graph.add_edge("consume", END)
    app = graph.compile(checkpointer=MemorySaver())
    result = app.invoke(state, config={"configurable": {"thread_id": f"fallback:{target_kind}"}})

    assert observed
    for slot in kept:
        assert observed[0][slot] == prior[slot]
    for slot in cleared:
        assert observed[0][slot] is None
    assert result["cycle_id"] == ("cycle_0002" if new_cycle else "cycle_0001")
    assert all(Path(member["canonical_path"]).is_absolute() is False for pointer in prior.values() if pointer for member in pointer["members"])


def test_invalidation_matrix_is_exact() -> None:
    assert INVALIDATED_SLOTS_BY_TARGET_KIND == {
        "method_planner": ARTIFACT_SLOTS,
        "legacy_codex_handoff": ARTIFACT_SLOTS[1:],
        "code_agent": ARTIFACT_SLOTS[1:],
        "analysis_engineer": ARTIFACT_SLOTS[2:],
        "scientific_reviewer": ARTIFACT_SLOTS[3:],
        "decision_coordinator": ARTIFACT_SLOTS[4:],
        "memory_report": ARTIFACT_SLOTS[6:],
    }


@pytest.mark.parametrize(
    ("slot", "protected_kind", "message"),
    [
        ("plan", "accepted_result", "terminal artifact slot"),
        ("plan", "forged_kind", "Unsupported current artifact protection"),
    ],
)
def test_invalid_protection_request_fails_before_registry_mutation(
    tmp_path: Path,
    slot: str,
    protected_kind: str,
    message: str,
) -> None:
    state = _run_attempt(_state(tmp_path, f"protection_{protected_kind}"), "method_planner", "method_planner", "plan")
    history_path = Path(state["artifact_history_path"])
    index_path = Path(state["artifact_index_path"])
    history_before = history_path.read_bytes()
    index_before = index_path.read_bytes()

    with pytest.raises(ValueError, match=message):
        protect_current_artifact(state, slot=slot, protected_kind=protected_kind)

    assert history_path.read_bytes() == history_before
    assert index_path.read_bytes() == index_before


def test_nonaccepted_terminal_cannot_be_protected_as_accepted_result(tmp_path: Path) -> None:
    state = _decision_chain(tmp_path, "nonaccepted_terminal")
    terminal = _schedule(
        state,
        source="decision_coordinator",
        target="memory_report",
        kind="memory_report",
    )
    terminal = _run_attempt(terminal, "memory_report", "memory_report", "terminal")
    history_path = Path(terminal["artifact_history_path"])
    index_path = Path(terminal["artifact_index_path"])
    history_before = history_path.read_bytes()
    index_before = index_path.read_bytes()

    with pytest.raises(ValueError, match="accepted terminal artifact"):
        protect_current_artifact(terminal, slot="terminal", protected_kind="accepted_result")

    assert history_path.read_bytes() == history_before
    assert index_path.read_bytes() == index_before


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("slot", "plan"),
        ("attempt_id", "attempt_999999"),
        ("cycle_id", "cycle_9999"),
    ],
)
def test_accepted_result_protection_must_match_current_terminal_pointer(
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    state = _decision_chain(tmp_path, f"accepted_provenance_{field}")
    terminal = _schedule(
        state,
        source="decision_coordinator",
        target="memory_report",
        kind="memory_report",
    )
    terminal = execute_scheduled_attempt(
        terminal,
        node_name="memory_report",
        attempt_kind="memory_report",
        node=_accepted_terminal_node,
    )
    history = _artifact_history(terminal)
    protected = next(
        record
        for record in history
        if record.get("protected_kind") == "accepted_result"
    )
    protected[field] = replacement
    _write_artifact_history(terminal, history)

    with pytest.raises(ValueError, match="Accepted-result protection"):
        initialize_artifact_registry(dict(terminal))


@pytest.mark.parametrize("mutation", ["coordinated_identity", "request", "ledger_digest"])
def test_human_response_snapshot_must_match_submission_ledger(
    tmp_path: Path,
    mutation: str,
) -> None:
    state = _submitted_human_response(tmp_path, f"response_provenance_{mutation}")
    history = _artifact_history(state)
    protected = next(
        record
        for record in history
        if record.get("protected_kind") == "human_response"
    )
    if mutation == "coordinated_identity":
        protected["artifact_id"] = "human_response_999999:payload"
        protected["human_response_id"] = "human_response_999999"
        _write_artifact_history(state, history)
    elif mutation == "request":
        protected["human_request_id"] = "human_request_999999"
        _write_artifact_history(state, history)
    else:
        records = [
            json.loads(line)
            for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
        ]
        submitted = next(
            record
            for record in records
            if record.get("record_type") == "human_response"
            and record.get("event") == "submitted"
        )
        submitted["payload_sha256"] = "0" * 64
        _write_execution_history(state, records)

    with pytest.raises(ValueError, match="Human Response snapshot"):
        initialize_artifact_registry(dict(state))


def test_accepted_result_protection_cannot_be_deleted_from_history(tmp_path: Path) -> None:
    terminal = _accepted_terminal_state(tmp_path, "missing_accepted_protection")
    history = _artifact_history(terminal)
    assert history[-1].get("protected_kind") == "accepted_result"
    history.pop()
    index = json.loads(Path(terminal["artifact_index_path"]).read_text(encoding="utf-8"))
    forged = _rewrite_registry_head(terminal, history, index)

    with pytest.raises(ValueError, match="exactly cover accepted terminal"):
        initialize_artifact_registry(forged)


def test_human_response_protection_cannot_be_deleted_from_history(tmp_path: Path) -> None:
    state = _submitted_human_response(tmp_path, "missing_human_protection")
    history = _artifact_history(state)
    assert history[-1].get("protected_kind") == "human_response"
    history.pop()
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    forged = _rewrite_registry_head(state, history, index)

    with pytest.raises(ValueError, match="exactly cover submitted Human Response"):
        initialize_artifact_registry(forged)


def test_finished_attempt_registration_cannot_be_deleted_from_history(tmp_path: Path) -> None:
    terminal = _accepted_terminal_state(tmp_path, "missing_terminal_registration")
    terminal_pointer = deepcopy(terminal["current_artifacts"]["terminal"])
    history = [
        record
        for record in _artifact_history(terminal)
        if record.get("artifact_id") != terminal_pointer["artifact_id"]
    ]
    index = json.loads(Path(terminal["artifact_index_path"]).read_text(encoding="utf-8"))
    for member in terminal_pointer["members"]:
        index["managed_projections"].pop(member["projection_path"])
    index["current"]["terminal"] = None
    forged = _rewrite_registry_head(terminal, history, index)
    forged["memory_update_path"] = None
    forged["final_report_path"] = None

    with pytest.raises(ValueError, match="output is missing its registered artifact"):
        initialize_artifact_registry(forged)


def test_committed_transition_target_attempt_cannot_be_deleted(tmp_path: Path) -> None:
    terminal = _accepted_terminal_state(tmp_path, "missing_target_attempt")
    terminal_pointer = deepcopy(terminal["current_artifacts"]["terminal"])
    history = [
        record
        for record in _artifact_history(terminal)
        if record.get("artifact_id") != terminal_pointer["artifact_id"]
    ]
    index = json.loads(Path(terminal["artifact_index_path"]).read_text(encoding="utf-8"))
    for member in terminal_pointer["members"]:
        index["managed_projections"].pop(member["projection_path"])
    index["current"]["terminal"] = None
    execution_records = [
        json.loads(line)
        for line in Path(terminal["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    execution_records = [
        record
        for record in execution_records
        if record.get("attempt_id") != terminal_pointer["attempt_id"]
    ]
    _write_execution_history(terminal, execution_records)
    forged = _rewrite_registry_head(terminal, history, index)
    forged["memory_update_path"] = None
    forged["final_report_path"] = None

    with pytest.raises(ValueError, match="Committed Transition target Attempt is missing"):
        initialize_artifact_registry(forged)


def test_active_human_response_chain_cannot_be_deleted(tmp_path: Path) -> None:
    state = _submitted_human_response(tmp_path, "missing_active_response_chain")
    response_id = state["active_human_response_id"]
    history = [
        record
        for record in _artifact_history(state)
        if record.get("human_response_id") != response_id
    ]
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    execution_records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    execution_records = [
        record
        for record in execution_records
        if record.get("human_response_id") != response_id
    ]
    _write_execution_history(state, execution_records)
    forged = _rewrite_registry_head(state, history, index)

    with pytest.raises(ValueError, match="State active Human Response is missing"):
        initialize_artifact_registry(forged)


def test_state_attempt_identity_cannot_rollback_to_prior_ledger_attempt(tmp_path: Path) -> None:
    state = _accepted_terminal_state(tmp_path, "stale_attempt_head")
    execution_records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    attempt_records = [record for record in execution_records if record.get("record_type") == "attempt"]
    prior_attempt_id = f"attempt_{state['attempt_index'] - 1:06d}"
    prior_lifecycle = [
        record for record in attempt_records if record.get("attempt_id") == prior_attempt_id
    ]
    prior = prior_lifecycle[0]
    forged = deepcopy(state)
    forged.update(
        {
            "cycle_id": prior["cycle_id"],
            "cycle_index": prior["cycle_index"],
            "attempt_id": prior_attempt_id,
            "attempt_index": prior["attempt_index"],
            "parent_attempt_id": prior["parent_attempt_id"],
            "attempt_kind": prior["attempt_kind"],
            "attempt_node": prior["node_name"],
            "attempt_trigger": prior["attempt_trigger"],
            "attempt_status": prior_lifecycle[-1]["status"],
            "inbound_transition_id": prior["inbound_transition_id"],
        }
    )

    with pytest.raises(ValueError, match="State Attempt identity is not the latest"):
        initialize_artifact_registry(forged)


def test_state_human_response_cannot_rollback_within_latest_request(tmp_path: Path) -> None:
    state = _submitted_human_response(tmp_path, "stale_response_head")
    first_response_id = state["active_human_response_id"]
    state = start_attempt(
        state,
        node_name="human_approval_gate",
        attempt_kind="human_gate",
    )
    state = validate_human_response(
        state,
        validator_attempt_id=str(state["attempt_id"]),
        valid=False,
        error="Rejected for regression coverage.",
    )
    state = finish_attempt(state, status="pending")
    state = submit_human_response(
        state,
        payload={
            "decision": "approve_with_conditions",
            "human_request_id": state["active_human_request_id"],
        },
        payload_reference="inline:test-second-response",
    )
    execution_records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    first_lifecycle = [
        record
        for record in execution_records
        if record.get("record_type") == "human_response"
        and record.get("human_response_id") == first_response_id
    ]
    first = first_lifecycle[-1]
    forged = deepcopy(state)
    forged.update(
        {
            "human_response_index": first["response_index"],
            "active_human_response_id": first_response_id,
            "human_response_status": first["status"],
            "human_response_decision": first["decision"],
            "human_response_authorized_route": first["authorized_route"],
            "human_response_authorized_transition_route": first[
                "authorized_transition_route"
            ],
            "human_response_authorized_transition_target": first[
                "authorized_transition_target"
            ],
            "human_response_validator_attempt_id": first["validator_attempt_id"],
            "human_response_consumer_attempt_id": first["consumer_attempt_id"],
            "human_response_target_attempt_id": first["authorized_target_attempt_id"],
        }
    )

    with pytest.raises(ValueError, match="Human Response counter is not the latest"):
        initialize_artifact_registry(forged)


def test_nonterminal_transition_target_cannot_be_erased(tmp_path: Path) -> None:
    state = _accepted_terminal_state(tmp_path, "erased_transition_target")
    terminal_pointer = deepcopy(state["current_artifacts"]["terminal"])
    history = [
        record
        for record in _artifact_history(state)
        if record.get("artifact_id") != terminal_pointer["artifact_id"]
    ]
    index = json.loads(Path(state["artifact_index_path"]).read_text(encoding="utf-8"))
    for member in terminal_pointer["members"]:
        index["managed_projections"].pop(member["projection_path"])
    index["current"]["terminal"] = None
    execution_records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    target_attempt_id = terminal_pointer["attempt_id"]
    target_lifecycle = [
        record for record in execution_records if record.get("attempt_id") == target_attempt_id
    ]
    inbound_transition_id = target_lifecycle[0]["inbound_transition_id"]
    execution_records = [
        record for record in execution_records if record.get("attempt_id") != target_attempt_id
    ]
    for record in execution_records:
        if record.get("transition_id") == inbound_transition_id:
            record["target_attempt_id"] = None
            record["target_node"] = None
            record["target_attempt_kind"] = None
            record["target_cycle_id"] = None
    _write_execution_history(state, execution_records)
    forged = _rewrite_registry_head(state, history, index)
    forged["memory_update_path"] = None
    forged["final_report_path"] = None
    prior_attempt_id = max(
        {
            record["attempt_id"]
            for record in execution_records
            if record.get("record_type") == "attempt"
        }
    )
    prior_lifecycle = [
        record for record in execution_records if record.get("attempt_id") == prior_attempt_id
    ]
    prior = prior_lifecycle[0]
    forged.update(
        {
            "cycle_id": prior["cycle_id"],
            "cycle_index": prior["cycle_index"],
            "attempt_id": prior_attempt_id,
            "attempt_index": prior["attempt_index"],
            "parent_attempt_id": prior["parent_attempt_id"],
            "attempt_kind": prior["attempt_kind"],
            "attempt_node": prior["node_name"],
            "attempt_trigger": prior["attempt_trigger"],
            "attempt_status": prior_lifecycle[-1]["status"],
            "inbound_transition_id": prior["inbound_transition_id"],
        }
    )

    with pytest.raises(ValueError, match="invalid terminal target shape"):
        initialize_artifact_registry(forged)


@pytest.mark.parametrize(
    ("state_factory", "field"),
    [
        ("terminal", "cycle_index"),
        ("terminal", "attempt_index"),
        ("terminal", "transition_index"),
        ("human", "human_request_index"),
        ("human", "human_response_index"),
    ],
)
def test_execution_head_counters_cannot_rollback(
    tmp_path: Path,
    state_factory: str,
    field: str,
) -> None:
    state = (
        _accepted_terminal_state(tmp_path, f"rollback_{field}")
        if state_factory == "terminal"
        else _submitted_human_response(tmp_path, f"rollback_{field}")
    )
    forged = deepcopy(state)
    forged[field] -= 1

    with pytest.raises(ValueError, match="latest execution ledger head"):
        initialize_artifact_registry(forged)


@pytest.mark.parametrize("mutation", ["reused", "gapped"])
def test_execution_ledger_transition_identity_sequence_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    state = _accepted_terminal_state(tmp_path, f"transition_{mutation}")
    execution_records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    latest_transition = next(
        record
        for record in execution_records
        if record.get("transition_id") == state["committed_transition_id"]
    )
    replacement_index = (
        int(latest_transition["transition_index"]) - 1
        if mutation == "reused"
        else int(latest_transition["transition_index"]) + 1
    )
    replacement_id = f"transition_{replacement_index:06d}"
    original_id = latest_transition["transition_id"]
    latest_transition["transition_index"] = replacement_index
    latest_transition["transition_id"] = replacement_id
    for record in execution_records:
        if record.get("record_type") == "attempt" and record.get("inbound_transition_id") == original_id:
            record["inbound_transition_id"] = replacement_id
    _write_execution_history(state, execution_records)
    forged = deepcopy(state)
    forged["transition_index"] = replacement_index
    forged["committed_transition_id"] = replacement_id
    forged["inbound_transition_id"] = replacement_id

    with pytest.raises(ValueError):
        initialize_artifact_registry(forged)


@pytest.mark.parametrize(
    "field",
    [
        "parent_cycle_id",
        "parent_attempt_id",
        "active_human_request_id",
        "human_response_decision",
    ],
)
def test_nullable_execution_head_state_fields_must_be_present(
    tmp_path: Path,
    field: str,
) -> None:
    state = _state(tmp_path, f"missing_state_{field}")
    forged = deepcopy(state)
    forged.pop(field)

    with pytest.raises(ValueError, match="latest execution ledger head|latest request response head"):
        initialize_artifact_registry(forged)


@pytest.mark.parametrize(
    ("record_type", "field"),
    [
        ("cycle", "parent_cycle_id"),
        ("attempt", "parent_attempt_id"),
    ],
)
def test_nullable_execution_ledger_identity_fields_must_be_present(
    tmp_path: Path,
    record_type: str,
    field: str,
) -> None:
    state = _run_attempt(
        _state(tmp_path, f"missing_ledger_{record_type}_{field}"),
        "method_planner",
        "method_planner",
        "plan",
    )
    execution_records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    for record in execution_records:
        if record.get("record_type") == record_type:
            record.pop(field)
    _write_execution_history(state, execution_records)

    with pytest.raises(ValueError, match="incomplete|invalid"):
        initialize_artifact_registry(dict(state))


@pytest.mark.parametrize(
    "field",
    [
        "target_attempt_id",
        "target_node",
        "target_cycle_id",
        "target_attempt_kind",
    ],
)
def test_terminal_transition_null_target_fields_must_be_present(
    tmp_path: Path,
    field: str,
) -> None:
    state = _accepted_terminal_state(tmp_path, f"missing_terminal_{field}")
    state = commit_transition(
        state,
        source_node="memory_report",
        route="end",
        reason="Complete terminal target-shape regression run.",
        fields={},
    )
    execution_records = [
        json.loads(line)
        for line in Path(state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    for record in execution_records:
        if record.get("transition_id") == state["committed_transition_id"]:
            record.pop(field)
    _write_execution_history(state, execution_records)

    with pytest.raises(ValueError, match="invalid terminal target shape"):
        initialize_artifact_registry(dict(state))


def test_human_response_snapshot_and_accepted_terminal_survive_invalidation(tmp_path: Path) -> None:
    gate = _submitted_human_response(tmp_path, "protected")
    response_path = Path(gate["output_dir"]) / "human_responses" / str(gate["active_human_response_id"]) / "payload.json"
    response_bytes = response_path.read_bytes()

    gate = execute_scheduled_attempt(
        gate,
        node_name="human_approval_gate",
        attempt_kind="human_gate",
        node=lambda active: {**active, "status": "running"},
    )
    terminal = _schedule(
        gate,
        source="human_approval_gate",
        target="memory_report",
        kind="memory_report",
    )

    terminal = execute_scheduled_attempt(
        terminal,
        node_name="memory_report",
        attempt_kind="memory_report",
        node=_accepted_terminal_node,
    )
    terminal_path = Path(terminal["memory_update_path"])
    terminal_bytes = terminal_path.read_bytes()
    invalidated = commit_external_transition(
        terminal,
        source_name="FALLBACK_HARNESS",
        route="analysis_engineer",
        reason="Clear current terminal without deleting protected history.",
        fields={},
        target_node="analysis_engineer",
        target_attempt_kind="analysis_engineer",
        trigger_reason="fallback_analysis_rerun",
    )

    history = _artifact_history(invalidated)
    assert response_path.read_bytes() == response_bytes
    assert terminal_path.read_bytes() == terminal_bytes
    assert invalidated["current_artifacts"]["terminal"] is None
    assert any(record.get("protected_kind") == "human_response" for record in history)
    assert any(record.get("protected_kind") == "accepted_result" for record in history)
    response_records = [
        record
        for record in Path(invalidated["execution_history_path"]).read_text(encoding="utf-8").splitlines()
        if '"record_type": "human_response"' in record
    ]
    assert response_records
    assert all(str(response_path) in record for record in response_records)


def test_unmanaged_legacy_output_is_preserved_and_registry_corruption_fails(tmp_path: Path) -> None:
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    legacy_path = legacy_root / "method_plan.json"
    legacy_path.write_bytes(b"legacy bytes\n")
    case_path = tmp_path / "legacy.yaml"
    case_path.write_text('case_id: "case_a"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Refusing to manage legacy Run artifacts"):
        initialize_state(
            case_id="case_a",
            run_id="legacy",
            user_goal="artifact registry test",
            case_config_path=str(case_path),
            output_dir=str(legacy_root),
            checkpoint_backend="memory",
        )
    assert legacy_path.read_bytes() == b"legacy bytes\n"
    assert not (legacy_root / "artifact_index.json").exists()

    state = _run_attempt(_state(tmp_path, "corrupt"), "method_planner", "method_planner", "plan")
    Path(state["method_plan_path"]).write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="digest changed"):
        validate_state_artifacts(state)
