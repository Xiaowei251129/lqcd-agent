"""Original ordinary and terminal repause sources keep their distinct capacity."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import read
from harness.trace import compare, normalize
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes
from test_b00c13_human_continuation import original_source, resume_request, records, files
from test_b04_product_graph import diagnostic
from test_b00c17_terminal_reserve_handoff import ledger_capacity_witness


def repause_trace(mode, *, reason="Synthetic Human continuation"):
    terminal = mode == "terminal_corrected"
    outcomes = {"scientific_reviewer": diagnostic(category="review_incomplete", affected_layer="review",
        retryability="retryable", candidates=["scientific_reviewer"], risk="medium")} if terminal else None
    profile = "balanced_v1" if mode == "ordinary_corrected" else "phase_b_test"
    with original_source(mode="c18-" + mode, profile=profile, outcomes=outcomes) as (coordinator, capture, agent, actor, result, root):
        views = []
        adapter = result["runtime"].route_adapter
        original = adapter.repause
        def passive(view):
            views.append(deepcopy(view))
            return original(view)
        adapter.repause = passive
        count = len(agent.contexts)
        request = resume_request(result, result["state"], "approve_rerun" if terminal else "request_code_change", reason=reason)
        resumed = result["runtime"].resume(request, actor=actor)
        state = records(root).projection.value
        assert len(views) == 1 and views[0]["human_continuation"]["mode"] == ("terminal" if terminal else "ordinary")
        assert len(agent.contexts) == count
        prefix = records(root).values
        decision, = [r for r in prefix if r.get("record_type") == "budget" and r["event"] == "decision_recorded" and
                     r["payload"]["proposed_action"] == "repause"]
        assert [r["event"] for r in prefix if r["record_type"] == "human_response"] == ["submitted", "invalid"]
        if mode == "ordinary_insufficient":
            assert result["state"]["budget"]["dimensions"]["control_attempts_per_run"]["remaining"] == 6
            assert views[0]["budget"]["dimensions"]["control_attempts_per_run"]["remaining"] == 5
            assert decision["payload"]["decision"] == "halt" and state["run_status"] == "halted"
            assert len([r for r in prefix if r["record_type"] == "pause" and r["event"] == "pause_opened"]) == 1
        else:
            assert decision["payload"]["decision"] == "allow" and state["run_status"] == "paused"
            corrected = resume_request(result, state, "reject_or_hold", key="corrected", reason=reason)
            result["runtime"].resume(corrected, actor=actor)
            assert records(root).projection.value["run_status"] == ("halted" if terminal else "completed")
        before = files(root)
        result["runtime"].resume(request, actor=actor)
        result["runtime"].run(result["run_locator"])
        assert files(root) == before and len(agent.contexts) == count
        execution = records(root)
        sequences = [r["fields"]["stop_sequence_id"] for r in execution.values if r["record_type"] == "transition" and
                     r["fields"].get("stop_sequence_id")]
        assert (len(sequences) == 5 and len(set(sequences)) == 1) if terminal else not sequences
        assert not any(r.get("event") in ("grant_issued", "grant_consumed") for r in execution.values)
        trace = capture.finish(coordinator)
        normalized = normalize(trace, binding=current_binding())
        facts = {"mode": mode, "run_status": execution.projection.value["run_status"], "calls": count,
                 "duplicate_readonly": True, "sequence_transitions": len(sequences), "B04_owned": False}
        output = root.parent.parent
        for name, value in (("raw", trace), ("normalized", normalized), ("facts", facts), ("views", views)):
            (output / (name + ".json")).write_bytes(canonical_bytes(value))
        (output / "capacity-witness.json").write_bytes(canonical_bytes(ledger_capacity_witness(execution)))
        print("ORIGINAL_PORT_CAPACITY_WITNESS", output)
        return trace, output, facts


@pytest.mark.parametrize("mode", ["ordinary_insufficient", "ordinary_corrected", "terminal_corrected"])
def test_original_repause_dual_fresh(mode):
    first, root, facts = repause_trace(mode)
    second, other, other_facts = repause_trace(mode)
    assert root != other and facts == other_facts
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    expected = read(ROOT / ("tests/phase_b/expected_traces/b00c18/" + mode + ".json"))
    compare(first, expected, binding=current_binding())
    observe("B00C18-" + mode.upper(), {"kind": "boolean", "value": True},
            ["B04_owned_false", "exact_sources", "original_ports", "single_effect"], first)


@pytest.mark.parametrize("terminal", [False, True])
def test_reachable_control_boundaries_use_original_invalid_responses(terminal):
    normalized = []
    for _ in range(2):
        outcomes = {"scientific_reviewer": diagnostic(category="review_incomplete", affected_layer="review",
            retryability="retryable", candidates=["scientific_reviewer"], risk="medium")} if terminal else None
        with original_source(mode="c18-capacity-ladder-" + str(terminal),
                profile="phase_b_test" if terminal else "balanced_v1", outcomes=outcomes) as (coordinator, capture, agent, actor, result, root):
            views = []
            adapter = result["runtime"].route_adapter
            original = adapter.repause

            def passive(view):
                views.append(deepcopy(view))
                return original(view)

            adapter.repause = passive
            calls = len(agent.contexts)
            required = 3 if terminal else 6
            state = records(root).projection.value
            for index in range(16):
                assert state["run_status"] == "paused"
                request = resume_request(result, state, "approve_rerun" if terminal else "request_code_change",
                                         key="invalid-" + str(index))
                result["runtime"].resume(request, actor=actor)
                state = records(root).projection.value
                remaining = views[-1]["budget"]["dimensions"]["control_attempts_per_run"]["remaining"]
                assert len(agent.contexts) == calls
                if remaining < required:
                    assert remaining == required - 1 and state["run_status"] == "halted"
                    break
                assert state["run_status"] == "paused"
            else:
                pytest.fail("Original invalid responses did not reach the immutable capacity boundary")
            assert {required - 1, required, required + 1} <= {
                v["budget"]["dimensions"]["control_attempts_per_run"]["remaining"] for v in views}
            rows = records(root)
            pauses = [r for r in rows.values if r.get("event") == "pause_opened"]
            invalid = [r for r in rows.values if r.get("event") == "invalid"]
            assert len(pauses) == len(invalid) == len(views)
            assert not any(r.get("event") in ("grant_issued", "grant_consumed") for r in rows.values)
            before = files(root)
            result["runtime"].resume(request, actor=actor)
            result["runtime"].run(result["run_locator"])
            assert files(root) == before and len(agent.contexts) == calls
            raw = capture.finish(coordinator)
            normal = normalize(raw, binding=current_binding())
            output = root.parent.parent
            for name, value in (("raw", raw), ("normalized", normal), ("views", views),
                                ("capacity-witness", ledger_capacity_witness(rows))):
                (output / (name + ".json")).write_bytes(canonical_bytes(value))
            print("ORIGINAL_CONTROL_BOUNDARIES", output)
            normalized.append(normal)
    assert normalized[0] == normalized[1]


@pytest.fixture(scope="module")
def repause_sources():
    return {mode: repause_trace(mode)[0] for mode in ("ordinary_corrected", "terminal_corrected")}


@pytest.mark.parametrize("mode", ["ordinary_corrected", "terminal_corrected"])
def test_real_human_reason_remains_material_in_complete_trace(repause_sources, mode):
    changed, _, facts = repause_trace(mode, reason="A different authorized Human explanation")
    original = repause_sources[mode]
    assert normalize(changed, binding=current_binding()) != normalize(original, binding=current_binding())
    def fingerprints(trace):
        return [r["value"]["payload"]["fingerprint"] for r in trace["proof"]["objects"]
                if r["value"].get("event") == "failure_observed"]
    assert fingerprints(changed) == fingerprints(original) and not facts["B04_owned"]


@pytest.mark.parametrize("mode", ["ordinary_corrected", "terminal_corrected"])
@pytest.mark.parametrize("fault", ["mode", "missing", "validator_head", "stop_binding", "foreign_run", "request", "validator", "sequence"])
def test_original_repause_source_rejects_unbound_continuation(repause_sources, mode, fault):
    from types import SimpleNamespace
    from lqcd_agent.control.execution import replay
    from lqcd_agent.control.operations import invalid_response_admission
    from lqcd_agent.graph.analysis_graph import ProductRouteAdapter

    trace = repause_sources[mode]
    rows = sorted((deepcopy(r["value"]) for r in trace["proof"]["objects"] if r["kind"] == "execution_0_4"),
                  key=lambda r: r["event_index"])
    decision, = [r for r in rows if r.get("event") == "decision_recorded" and r["payload"]["proposed_action"] == "repause"]
    execution = replay(rows[:decision["event_index"] - 1])
    views = []
    adapter = ProductRouteAdapter(None)

    class Capture:
        def repause(self, view):
            views.append(deepcopy(view))
            return adapter.repause(view)

    actual, _ = invalid_response_admission(execution, Capture())
    assert actual == decision["payload"]
    if fault in ("mode", "missing", "validator_head", "stop_binding"):
        view = deepcopy(views[0])
        continuation = view["human_continuation"]
        if fault == "mode": continuation["mode"] = "untrusted"
        elif fault == "missing": continuation.pop("validator_transition_head")
        elif fault == "validator_head": continuation["validator_transition_head"] = "foreign"
        else: continuation["stop_sequence_id"] = None if mode == "terminal_corrected" else "f" * 64
        with pytest.raises(ValueError):
            adapter.repause(view)
    else:
        # Corrupted source views are negative unit inputs, never published Runs.
        prefix = deepcopy(execution.values)
        inbound = next(r for r in prefix if r["record_type"] == "transition" and
                       r["target_attempt_id"] == prefix[-1]["attempt_id"])
        if fault == "foreign_run": inbound["run_id"] = "foreign"
        elif fault == "request": inbound["human_request_id"] = "foreign"
        elif fault == "validator": inbound["target_attempt_id"] = "foreign"
        else: inbound["fields"]["stop_sequence_id"] = "f" * 64
        with pytest.raises(ValueError):
            invalid_response_admission(SimpleNamespace(values=prefix, projection=execution.projection), adapter)


@pytest.mark.parametrize("mode", ["ordinary_corrected", "terminal_corrected"])
@pytest.mark.parametrize("fault", ["proposal", "projected", "used", "remaining", "prefix", "validator", "request", "missing_pause"])
def test_repause_binding_rejects_changed_original_sources(repause_sources, mode, fault):
    from harness.product_failure_trace import ProductProjection
    from harness.strict_json import Invalid

    trace = deepcopy(repause_sources[mode])
    assert normalize(trace, binding=current_binding())
    objects = {row["sha256"]: row for row in trace["proof"]["objects"]}
    run, = {(r["value"]["case_id"], r["value"]["run_id"]) for r in objects.values() if r["kind"] == "execution_0_4"}
    rows = sorted((r["value"] for r in objects.values() if r["kind"] == "execution_0_4"), key=lambda r: r["event_index"])
    decision, = [r for r in rows if r.get("event") == "decision_recorded" and r["payload"]["proposed_action"] == "repause"]
    prefix = rows[:decision["event_index"] - 1]
    if fault == "proposal": decision["payload"]["proposal_id"] = "f" * 64
    elif fault in ("projected", "used", "remaining"):
        key = "projected_after" if fault == "projected" else fault
        decision["payload"]["dimensions"]["control_attempts_per_run"][key] += 1
    elif fault == "prefix": decision["previous_execution_head"] = "f" * 64
    elif fault == "validator": prefix[-1]["attempt_id"] = "foreign"
    elif fault == "request": next(r for r in reversed(prefix) if r["record_type"] == "human_response")["human_request_id"] = "foreign"
    else: rows.remove(next(r for r in reversed(prefix) if r["record_type"] == "pause"))
    extension = ProductProjection(trace["proof"])
    extension.base_sources = objects
    with pytest.raises((Invalid, ValueError)):
        extension.repause_sources(objects, {run: rows})
