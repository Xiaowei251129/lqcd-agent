"""C13 original Human ports, independent owners, and bounded terminal tails."""
from harness.temporary import mkdtemp
from contextlib import closing, contextmanager
from copy import deepcopy
from pathlib import Path

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_human import human_trace
from helpers.ordinary_maximum import PassiveClock
from helpers.product_failure_sources import ProductFailureSources
from helpers.trace_sources import current_binding
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, diagnostic


@contextmanager
def original_source(*, mode="approve_rerun", profile="balanced_v1", outcomes=None):
    output = Path(mkdtemp(prefix="lqcd-agent-b00c13-" + mode + "-", dir="/private/tmp"))
    with HostIdentities("b00c13-" + mode).installed():
        coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
        sources = ProductFailureSources(coordinator)
        capture = ControlTrace(output, version="0.8", ordinary_sources=sources)
        coordinator.observer = lambda name, side, value: sources.observer(capture, name, side, value)
        agent = StructuredOutcomes(outcomes or {"analysis_engineer": [diagnostic(status="failed", category="tool_failure",
            affected_layer="analysis", retryability="retryable", candidates=["analysis_engineer"], risk="low"), diagnostic()]})
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        try:
            result = run_canonical_graph(coordinator=coordinator, actor=actor, agent_port=sources.agent(agent),
                request=StartRunRequest("case", inputs, digest(inputs), "start", profile))
            root = output / result["run_locator"]["case_id"] / result["run_locator"]["run_id"]
            yield coordinator, capture, agent, actor, result, root
        finally:
            coordinator.close()


def resume_request(result, state, decision, *, key="resume", reason="Synthetic Human continuation"):
    payload = {**result["run_locator"], "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
        "decision": decision, "conditions": [], "reason": reason, "decided_by": "operator"}
    return ResumeRunRequest(result["run_locator"], state["active_pause"]["pause_id"], key, "human_response", payload, digest(payload))


def records(root):
    return parse_ledger((root / "execution_history.jsonl").read_bytes())


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def continuation(decision, *, reason="Synthetic Human continuation"):
    with original_source(mode=decision) as (coordinator, capture, agent, actor, result, root):
        packet = next(root.glob("attempts/*/approval_packet/request.json"))
        original_packet = packet.read_bytes()
        request = resume_request(result, result["state"], decision, reason=reason)
        resumed = result["runtime"].resume(request, actor=actor)
        execution = records(root)
        response = [r for r in execution.values if r["record_type"] == "human_response"]
        assert resumed["operation_status"] == "committed"
        assert [r["event"] for r in response] == ["submitted", "validated", "consumed"]
        assert execution.projection.value["run_status"] == "completed"
        assert packet.read_bytes() == original_packet
        before, calls = files(root), len(agent.contexts)
        operation = coordinator.get(resumed["operation_id"])
        result["runtime"].resume(request, actor=actor)
        result["runtime"].run(result["run_locator"])
        assert files(root) == before and len(agent.contexts) == calls
        assert coordinator.get(resumed["operation_id"]) == operation
        trace = capture.finish(coordinator)
        normalized = normalize(trace, binding=current_binding())
        terminal = loads((root / "artifact_index.json").read_bytes())["current"]["terminal"]["status"]
        assert terminal == ("accepted" if decision == "approve_rerun" else "rejected")
        assert [node for node, _ in agent.contexts] == (["method_planner", "analysis_engineer", "analysis_engineer", "scientific_reviewer"]
            if decision == "approve_rerun" else ["method_planner", "analysis_engineer"])
        facts = {"operation_status": resumed["operation_status"], "run_status": execution.projection.value["run_status"],
            "response_events": [r["event"] for r in response], "calls": [node for node, _ in agent.contexts],
            "terminal_status": terminal, "packet_unchanged": True, "duplicate_readonly": True, "B04_owned": False}
        output = root.parent.parent
        for name, value in (("raw", trace), ("normalized", normalized), ("facts", facts)):
            (output / (name + ".json")).write_bytes(canonical_bytes(value))
        return trace, output, facts


@pytest.mark.parametrize("decision", ["approve_rerun", "reject_or_hold"])
def test_dual_root_original_continuation(decision):
    first, output, facts = continuation(decision)
    second, other, other_facts = continuation(decision)
    assert output != other and facts == other_facts
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    compare(first, read(ROOT / ("tests/phase_b/expected_traces/b00c16/" + decision + ".json")), binding=current_binding())
    objects = {r["sha256"]: r["value"] for r in first["proof"]["objects"]}
    diagnostics = [d for d in first["proof"]["ordinary_members"] if d["member"] == "decision_coordinator_diagnostic.json"]
    matching = [d for d in diagnostics if d["sha256"] == diagnostics[0]["sha256"]]
    assert len(matching) == 2
    assert len({objects[d["registration_head"]]["attempt_id"] for d in matching}) == 2
    observe("B00C13-" + decision.upper(), {"kind": "boolean", "value": True},
        ["B04_owned_false", "independent_member_owners", "original_human_continuation", "single_use_response"], first)


@pytest.fixture(scope="module")
def successful_source():
    return continuation("approve_rerun")


@pytest.mark.parametrize("fault", ["missing", "duplicate", "foreign_registration", "bytes", "sha", "requester", "stale"])
def test_successful_owner_chain_rejects_bad_source(fault, successful_source):
    trace, _, _ = successful_source
    bad = deepcopy(trace)
    proof = bad["proof"]
    member = next(d for d in proof["ordinary_members"] if d["member"] == "decision_coordinator_diagnostic.json")
    if fault == "missing": proof["ordinary_members"].remove(member)
    elif fault == "duplicate": proof["ordinary_members"].append(deepcopy(member))
    elif fault == "foreign_registration": member["registration_head"] = "f" * 64
    elif fault == "bytes": member["content"] += " "
    elif fault == "sha": member["sha256"] = "f" * 64
    elif fault == "stale": proof["binding"]["invocation_token"] = "stale"
    else:
        request = next(o for o in proof["objects"] if o["value"].get("record_type") == "human_request" and o["value"].get("event") == "created")
        request["value"]["requesting_attempt_id"] = "attempt_000006"
        request["sha256"] = digest(request["value"])
    with pytest.raises(Invalid): normalize(bad, binding=current_binding())


def test_committed_duplicate_before_graph_advance_is_readonly():
    with original_source() as (coordinator, capture, agent, actor, result, root):
        request = resume_request(result, result["state"], "approve_rerun")
        runtime = result["runtime"]
        from lqcd_agent.graph.nodes import ProductNode
        runtime.plane.resume_target_adapter = ProductNode(root, runtime.agent_port)
        resumed = runtime.plane.resume_run(request, actor=actor)
        assert resumed["operation_status"] == "committed" and resumed["run_status"] == "running"
        before, calls = files(root), len(agent.contexts)
        runtime.resume(request, actor=actor)
        assert files(root) == before and len(agent.contexts) == calls
        runtime.run(result["run_locator"])
        assert records(root).projection.value["run_status"] == "completed"


def test_latest_response_belongs_to_current_request():
    outcomes = {"analysis_engineer": diagnostic(status="failed", category="tool_failure", affected_layer="analysis",
        retryability="retryable", candidates=["analysis_engineer"], risk="low")}
    with original_source(mode="repeated", outcomes=outcomes) as (coordinator, capture, agent, actor, result, root):
        first = resume_request(result, result["state"], "approve_rerun")
        result["runtime"].resume(first, actor=actor)
        state = records(root).projection.value
        assert state["run_status"] == "paused" and state["active_human_request_id"] != first.input_snapshot["human_request_id"]
        second = resume_request(result, state, "reject_or_hold", key="resume-second")
        result["runtime"].resume(second, actor=actor)
        responses = [r for r in records(root).values if r["record_type"] == "human_response"]
        assert [r["event"] for r in responses] == ["submitted", "validated", "consumed"] * 2
        assert records(root).projection.value["run_status"] == "completed"
        assert len([node for node, _ in agent.contexts if node == "analysis_engineer"]) == 2
        assert normalize(capture.finish(coordinator), binding=current_binding())


@pytest.mark.parametrize("decision", ["reject_or_hold", "approve_with_conditions"])
def test_real_stop_uses_five_remaining_control_without_work(decision):
    outcomes = {"scientific_reviewer": diagnostic(category="review_incomplete", affected_layer="review",
        retryability="retryable", candidates=["scientific_reviewer"], risk="medium")}
    with original_source(mode="stop", profile="phase_b_test", outcomes=outcomes) as (coordinator, capture, agent, actor, result, root):
        assert result["state"]["budget"]["dimensions"]["control_attempts_per_run"]["remaining"] == 5
        count = len(agent.contexts)
        result["runtime"].resume(resume_request(result, result["state"], decision), actor=actor)
        execution = records(root)
        assert execution.projection.value["run_status"] == "halted" and len(agent.contexts) == count
        sequences = [r["fields"]["stop_sequence_id"] for r in execution.values if r["record_type"] == "transition" and r["fields"].get("stop_sequence_id")]
        assert len(sequences) == 4 and len(set(sequences)) == 1
        assert loads((root / "artifact_index.json").read_bytes())["current"]["terminal"]["status"] != "accepted"
        trace = capture.finish(coordinator)
        assert normalize(trace, binding=current_binding())
        from test_b00c12_human_request_packet import packet_entry
        extension, chain, _, _, _ = packet_entry(trace)
        inbound = next(r for r in chain if r.get("source") == "HUMAN_RESPONSE")
        inbound["fields"]["stop_sequence_id"] = "f" * 64
        with pytest.raises(Invalid):
            extension.stop_sequences(extension.executions)


def test_out_of_scope_stop_response_can_be_corrected_without_work():
    outcomes = {"scientific_reviewer": diagnostic(category="review_incomplete", affected_layer="review",
        retryability="retryable", candidates=["scientific_reviewer"], risk="medium")}
    with original_source(mode="invalid-stop", profile="phase_b_test", outcomes=outcomes) as (coordinator, capture, agent, actor, result, root):
        count = len(agent.contexts)
        result["runtime"].resume(resume_request(result, result["state"], "approve_rerun"), actor=actor)
        state = records(root).projection.value
        assert state["run_status"] == "paused" and len(agent.contexts) == count
        responses = [r for r in records(root).values if r["record_type"] == "human_response"]
        assert [r["event"] for r in responses] == ["submitted", "invalid"]
        result["runtime"].resume(resume_request(result, state, "reject_or_hold", key="corrected"), actor=actor)
        assert records(root).projection.value["run_status"] == "halted" and len(agent.contexts) == count
        trace = capture.finish(coordinator)
        assert normalize(trace, binding=current_binding())
        from test_b00c11_human_snapshot import snapshot_entry
        for field, value in (("decision", "approve_rerun"), ("error", None), ("validator_attempt_id", "foreign")):
            extension, declaration, registration, chain, _ = snapshot_entry(deepcopy(trace))
            invalid = next(r for r in chain if r.get("record_type") == "human_response" and r["event"] == "invalid")
            invalid[field] = value
            extension.human_snapshots.clear()
            with pytest.raises(Invalid, match="human_snapshot_action"):
                extension.human_snapshot(declaration, registration)


def test_ordinary_approval_without_next_route_capacity_closes_safely():
    with original_source(mode="ordinary-capacity", profile="phase_b_test") as (coordinator, capture, agent, actor, result, root):
        assert result["state"]["budget"]["dimensions"]["control_attempts_per_run"]["remaining"] == 6
        assert not any(r["record_type"] == "transition" and r["fields"].get("stop_sequence_id") for r in records(root).values)
        count = len(agent.contexts)
        result["runtime"].resume(resume_request(result, result["state"], "approve_rerun"), actor=actor)
        execution = records(root)
        assert execution.projection.value["run_status"] == "halted" and len(agent.contexts) == count
        assert not any(r["record_type"] == "human_response" and r["event"] == "consumed" for r in execution.values)
        assert normalize(capture.finish(coordinator), binding=current_binding())


def test_materialization_pending_uses_original_suffix_without_effect():
    with original_source(mode="materialization") as (coordinator, capture, agent, actor, result, root):
        receipts = []
        def observer(name, side, value):
            capture.observer(name, side, value)
            if name == "invocation.attempt_finished" and side == "after" and not receipts:
                response = next((r for r in reversed(records(root).values) if r["record_type"] == "human_response"), None)
                if response and response["status"] == "validated":
                    receipts.append(response["validator_attempt_id"])
                    raise RuntimeError("Synthetic exact Human publication fault")
        coordinator.observer = observer
        request = resume_request(result, result["state"], "approve_rerun")
        runtime = result["runtime"]
        pending = runtime.resume(request, actor=actor)
        assert pending["operation_status"] == "in_progress" and pending["publication_status"] == "materialization_pending"
        assert [r["event"] for r in records(root).values if r["record_type"] == "human_response"] == ["submitted", "validated"]
        assert normalize(capture.finish(coordinator), binding=current_binding())
        count = len(agent.contexts)
        coordinator.observer = capture.observer
        completed = runtime.plane.resume_run(request, actor=actor)
        assert completed["operation_id"] == pending["operation_id"] and completed["operation_status"] == "committed"
        assert len(agent.contexts) == count
        runtime.resume(request, actor=actor)
        assert len(agent.contexts) == count


def test_physical_node_must_match_original_kind():
    with original_source(mode="physical") as (coordinator, capture, agent, actor, result, root):
        count = len(agent.contexts)
        source = next(r for r in reversed(records(root).values) if r["record_type"] == "attempt")
        view = {"run_locator": result["run_locator"], "source": {**source, "node_name": "method_planner"}}
        with pytest.raises(ValueError, match="physical node/kind mismatch"):
            result["runtime"].route_adapter.admit(view)
        assert len(agent.contexts) == count


def test_uncertain_started_validator_is_not_redispatched():
    trace, output, resumed = human_trace(fault="started")
    assert resumed["operation_status"] == "recovery_required"
    receipt = read(output / "fault-receipt.json")[0]
    assert not receipt["completion_frozen"] and receipt["effect_count"] == 2
    assert normalize(trace, binding=current_binding())
    from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
    with closing(Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))) as coordinator:
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        original = coordinator.get(resumed["operation_id"])
        request = ResumeRunRequest(**{k: original["request"][k] for k in
            ("run_locator", "pause_id", "input_kind", "input_snapshot", "input_digest")}, idempotency_key="resume")
        agent = StructuredOutcomes()
        runtime = CanonicalProductRuntime(coordinator, worker_id=original["worker_owner_id"], actor=actor, agent_port=agent)
        assert runtime.resume(request, actor=actor)["operation_status"] == "recovery_required"
        assert not agent.contexts and coordinator.get(resumed["operation_id"]) == original


def test_successful_material_change_and_legacy_rejection(successful_source):
    from test_b00c11_ordinary_maximum import legacy

    changed, _, _ = continuation("approve_rerun", reason="A different Human reason")
    original, output, _ = successful_source
    assert normalize(changed, binding=current_binding()) != normalize(original, binding=current_binding())
    before = files(output)
    assert normalize(read(output / "raw.json"), binding=current_binding()) == normalize(original, binding=current_binding())
    assert files(output) == before
    old = legacy(original)
    for field in ("product_failure_sources", "product_grant_sources"):
        old["proof"].pop(field)
    with pytest.raises(Invalid, match="human_owner"):
        normalize(old, binding=current_binding())


def test_satisfied_packet_locator_requires_actual_consumer(successful_source):
    from test_b00c12_human_request_packet import packet_entry

    extension, execution, _, _, _ = packet_entry(successful_source[0])
    satisfied = next(r for r in execution if r.get("record_type") == "human_request" and r["event"] == "satisfied")
    head = digest(satisfied)
    extension.locator_fields(head, satisfied)
    assert (head, ("packet_reference",)) in extension.packet_locators
    unknown = "unknown-container"
    extension.base_sources[unknown] = {"kind": "canonical_json", "value": {"nested": satisfied}}
    extension.locator_fields(unknown, {"nested": satisfied})
    assert (unknown, ("nested", "packet_reference")) not in extension.packet_locators
    assert extension.encode(unknown, ("nested", "packet_reference"), lambda x: x) is None
    satisfied["previous_execution_head"] = "f" * 64
    with pytest.raises(Invalid, match="packet_consumer_binding"):
        extension.locator_fields(head, satisfied)


@pytest.fixture(scope="module")
def pending_source():
    return human_trace()


@pytest.mark.parametrize("fault", ["producer", "worker", "epoch", "projection", "checkpoint", "ledger"])
def test_pending_completion_requires_exact_original_authority(pending_source, fault):
    from lqcd_agent.control.capabilities import InvocationLeases
    from lqcd_agent.control.strict_json import ControlIntegrityError

    _, output, resumed = pending_source
    with closing(Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))) as coordinator:
        leases = InvocationLeases(coordinator)
        operation = coordinator.get(resumed["operation_id"])
        identifier = "capability_" + operation["operation_id"]
        saved = coordinator.connection.execute("SELECT value FROM invocation_capabilities WHERE capability_id=?", (identifier,)).fetchone()[0]
        value = loads(saved)
        owner, worker, epoch = operation["operation_id"], operation["worker_owner_id"], operation["lease_epoch"]
        leases.verify_human_completion_prefix(identifier, owner, worker, epoch)
        if fault == "producer": owner = value["authorization"]["identity"]["run_id"]
        elif fault == "worker": worker = "foreign"
        elif fault == "epoch": epoch += 1
        elif fault == "projection": value["completion_intent"]["projection"]["active_human_request_id"] = "foreign"
        elif fault == "checkpoint": value["completion_intent"]["checkpoint"]["channel_values"]["control"]["run_status"] = "completed"
        else: value["completion_intent"]["content"] += "\n"
        if fault in ("projection", "checkpoint", "ledger"):
            coordinator.connection.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?", (canonical_bytes(value).decode(), identifier))
        before = files(output / operation["request"]["run_locator"]["case_id"] / operation["request"]["run_locator"]["run_id"])
        try:
            with pytest.raises((ControlIntegrityError, KeyError)):
                leases.verify_human_completion_prefix(identifier, owner, worker, epoch)
            root = output / operation["request"]["run_locator"]["case_id"] / operation["request"]["run_locator"]["run_id"]
            assert files(root) == before and coordinator.get(operation["operation_id"]) == operation
        finally:
            coordinator.connection.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?", (saved, identifier))
