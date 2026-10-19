"""Human response claims allocate one validator and consume the old Pause once."""
from harness.temporary import mkdtemp
from dataclasses import asdict, replace
from pathlib import Path
import multiprocessing

import pytest

from lqcd_agent.control.capabilities import HumanResponseVerdict, InvocationLeases, TargetOutcome
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import AdvanceRunRequest
from lqcd_agent.control.pause import PublishPauseRequest, ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from test_advance_control import SyntheticDomainRoute
from test_bootstrap_control import ACTOR, request as start_request
from helpers.process_client import resume_client
from helpers.domain_adapters import SyntheticRepauseAdapter


SCOPE = {"allowed_decisions": ["approve"], "allowed_target_nodes": ["decision_coordinator"],
         "decision_transition_routes": {"approve": "decision_coordinator"},
         "decision_transition_targets": {"approve": "decision_coordinator"}}


class HumanRoute(SyntheticDomainRoute):
    def admit(self, view):
        return replace(super().admit(view), human_request={"request_kind": "approval", "authorization_scope": SCOPE})


class PendingTarget:
    def invoke(self, identity):
        return TargetOutcome("pending", {"current_artifact_ids": {}})


class GatePacket:
    def invoke_with_artifacts(self, identity, port):
        path = port.write_member("approval_packet/request.json", b'{"synthetic":true}')
        return TargetOutcome("pending", {"current_artifact_ids": {}}, human_request_packet=str(path))


@pytest.fixture(params=["phase_b_test", "balanced_v1"])
def human_pause(request):
    output = Path(mkdtemp(prefix="lqcd-agent-b02-human-", dir="/private/tmp"))
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    source = ControlPlane(coordinator, worker_id="worker").start_run(replace(start_request(), profile_id=request.param), actor=ACTOR)
    locator = source["result"]["run_locator"]
    actor = ActorContext("operator", "human", ("control.internal", "resume"))
    leases = InvocationLeases(coordinator)
    capability = source["result"]["capability_id"]
    try:
        for position, (adapter, target) in enumerate(((SyntheticDomainRoute("decision_coordinator"), PendingTarget()),
                                                     (HumanRoute("human_approval_gate"), PendingTarget())), 1):
            leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
            state = leases.invoke(capability, "consumer", 1, target)
            plane = ControlPlane(coordinator, worker_id="worker", route_adapter=adapter, resume_decision_adapter=SyntheticRepauseAdapter())
            result = plane.advance_run(AdvanceRunRequest(locator, state["attempt_id"], f"advance-{position}"), actor=actor)
            capability = result["result"]["capability_id"]
        leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
        state = leases.invoke(capability, "consumer", 1, GatePacket())
        published = plane.publish_pause(PublishPauseRequest(locator, "human_input", state["attempt_id"], None,
            {"kind": "human_response", "human_request_id": state["active_human_request_id"]},
            {"actor_type": "human", "scopes": ["resume"]}, "human-pause"), actor=actor)
        payload = {**locator, "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
                   "decision": "approve", "conditions": [], "reason": "Synthetic decision", "decided_by": "operator"}
        yield coordinator, plane, actor, locator, published["result"]["pause_id"], payload
    finally:
        coordinator.close()


def test_human_claim_then_allocate_consume_start_and_validate(human_pause):
    coordinator, plane, actor, locator, pause, payload = human_pause
    calls = []

    class Validator:
        def invoke(self, identity):
            records = parse_ledger((coordinator.root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl").read_bytes()).values
            assert records[-1]["event"] == "started"
            assert [r["status"] for r in records if r["record_type"] == "pause"] == ["prepared", "opened", "claimed", "consumed"]
            calls.append(identity)
            return TargetOutcome("succeeded", {"current_artifact_ids": {}}, human_response_verdict=HumanResponseVerdict(True))

    plane.resume_target_adapter = Validator()
    request = ResumeRunRequest(locator, pause, "human-resume", "human_response", payload, digest(payload))
    result = plane.resume_run(request, actor=actor)
    assert result["operation_status"] == "committed" and len(calls) == 1
    assert plane.resume_run(request, actor=actor) == result and len(calls) == 1
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert [r["status"] for r in records if r["record_type"] == "human_response"] == ["submitted", "validated"]
    response = next(r for r in reversed(records) if r["record_type"] == "human_response")
    assert response["validator_attempt_id"] == "attempt_000004" and response["consumer_attempt_id"] is None
    external = next(r for r in records if r["record_type"] == "transition" and r["source_node"] == "HUMAN_RESPONSE")
    assert external["source_attempt_id"] is None and external["target_attempt_id"] == "attempt_000004"
    with pytest.raises(ControlIntegrityError, match="opened Pause"):
        plane.resume_run(replace(request, idempotency_key="duplicate-human-response"), actor=actor)
    plane.route_adapter = SyntheticDomainRoute("memory_report")
    with pytest.raises(ControlIntegrityError, match="authorize this exact Transition"):
        plane.advance_run(AdvanceRunRequest(locator, "attempt_000004", "wrong-response-route"), actor=actor)
    plane.route_adapter = SyntheticDomainRoute("decision_coordinator")
    consumed = plane.advance_run(AdvanceRunRequest(locator, "attempt_000004", "consume-response"), actor=actor)
    assert consumed["operation_status"] == "committed"
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert [r["status"] for r in records if r["record_type"] == "human_response"] == ["submitted", "validated", "consumed"]
    assert records[-1]["record_type"] == "human_request" and records[-1]["status"] == "satisfied"


def test_invalid_response_repauses_until_reserved_terminal_capacity_requires_halt(human_pause):
    coordinator, plane, actor, locator, pause, payload = human_pause
    calls = []

    class Invalid:
        def invoke(self, identity):
            calls.append(identity)
            return TargetOutcome("pending", {"current_artifact_ids": {}}, human_response_verdict=HumanResponseVerdict(False, "Synthetic invalid input"))

    plane.resume_target_adapter = Invalid()
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    from lqcd_agent.control.strict_json import loads
    last = 1 if loads((root / "budget_policy.json").read_bytes())["profile_id"] == "phase_b_test" else 9
    for number in range(1, last + 1):
        request = ResumeRunRequest(locator, pause, f"invalid-{number}", "human_response", payload, digest(payload))
        result = plane.resume_run(request, actor=actor)
        assert result["operation_status"] == "committed" and len(calls) == number
        assert plane.resume_run(request, actor=actor) == result and len(calls) == number
        if number < last:
            assert result["run_status"] == "paused" and result["result"]["pause_id"] == f"pause_{number + 1:06d}"
            pause = result["result"]["pause_id"]
        else:
            assert result["run_status"] == "halted" and result["result"]["pause_id"] is None
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert [r["payload"]["decision"] for r in records if r["record_type"] == "budget" and r["event"] == "decision_recorded" and
            r["payload"]["proposed_action"] == "repause"] == ["allow"] * (last - 1) + ["halt"]
    assert [r["pause_id"] for r in records if r["record_type"] == "pause" and r["status"] == "prepared"] == [f"pause_{number:06d}" for number in range(1, last + 1)]
    assert sum(r["record_type"] == "attempt" and r["event"] == "scheduled" for r in records) == 3 + last


HUMAN_CRASH_BOUNDARIES = [("control.resume_run.continue_execution." + phase, side)
    for phase in ("pause_ownership_reserved", "pause_claimed_recorded", "prestart_records_committed", "pause_consumed_recorded",
                  "running_lifecycle_recorded", "resume_checkpoint_committed", "invocation_authorized", "external_consumption_released", "stable_boundary_committed", "result_committed")
    for side in ("before", "after")]
HUMAN_CRASH_BOUNDARIES += [("invocation.completion_intent", "after"), ("invocation.started_intent", "after"),
                          ("invocation.attempt_started.file_sync", "after"), ("invocation.attempt_finished.file_sync", "after")]


@pytest.mark.parametrize("human_pause", ["phase_b_test"], indirect=True)
@pytest.mark.parametrize("crash_boundary", HUMAN_CRASH_BOUNDARIES)
def test_human_fresh_process_recovery_preserves_claim_and_never_reinvokes_started(human_pause, crash_boundary):
    coordinator, _, _, locator, pause, payload = human_pause
    request = asdict(ResumeRunRequest(locator, pause, "human-resume", "human_response", payload, digest(payload)))
    context = multiprocessing.get_context("spawn")

    def run(boundary, elapsed):
        parent, child = context.Pipe()
        process = context.Process(target=resume_client, args=(child, str(coordinator.root), request, boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary is not None:
                assert process.exitcode == 89
                return None
            assert process.exitcode == 0 and parent.poll(2)
            response = parent.recv()
            assert response[0] == "result", response
            return response[1:]
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()

    run(crash_boundary, 0)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    prefix = (root / "execution_history.jsonl").read_bytes()
    result, calls = run(None, 40)
    uncertain = crash_boundary[0] in ("invocation.started_intent", "invocation.attempt_started.file_sync")
    assert result["operation_status"] == ("recovery_required" if uncertain else "committed")
    assert (root / "execution_history.jsonl").read_bytes().startswith(prefix)
    if uncertain or crash_boundary[0].startswith("invocation.") or "external_consumption_released" in crash_boundary[0]:
        assert calls == []
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert sum(r["record_type"] == "attempt" and r["event"] == "scheduled" and r["attempt_id"] == "attempt_000004" for r in records) == 1


@pytest.mark.parametrize("human_pause", ["phase_b_test"], indirect=True)
@pytest.mark.parametrize("same_key", [False, True])
def test_two_real_processes_reserve_before_competing_for_one_human_claim(human_pause, same_key):
    coordinator, _, _, locator, pause, payload = human_pause
    context = multiprocessing.get_context("spawn")
    children, pipes = [], []
    try:
        for number in range(2):
            request = asdict(ResumeRunRequest(locator, pause, "race" if same_key else f"race-{number}", "human_response", payload, digest(payload)))
            parent, child = context.Pipe()
            process = context.Process(target=resume_client, args=(child, str(coordinator.root), request), kwargs={"synchronized": "reservation"})
            process.start()
            child.close()
            children.append(process)
            pipes.append(parent)
        for pipe in pipes:
            assert pipe.poll(10) and pipe.recv() == "ready"
            pipe.send("go")
        for pipe in pipes:
            assert pipe.poll(10) and pipe.recv() == "reserved"
        for pipe in pipes:
            pipe.send("claim")
        results = []
        for process, pipe in zip(children, pipes):
            process.join(20)
            assert process.exitcode == 0 and pipe.poll(2)
            results.append(pipe.recv())
        assert sum(len(item[2]) for item in results) == 1
        from lqcd_agent.control.strict_json import loads
        owned = loads(coordinator.connection.execute("SELECT value FROM pause_ownership").fetchone()[0])
        assert owned["status"] == "consumed"
        assert coordinator.get(owned["owner"])["status"] == "committed"
        operations = coordinator.connection.execute("SELECT status FROM control_operations WHERE operation_type='resume_run'").fetchall()
        assert sorted(row[0] for row in operations) == (["committed"] if same_key else ["committed", "failed"])
    finally:
        for process in children:
            if process.is_alive():
                process.terminate()
            process.join(5)
        for pipe in pipes:
            pipe.close()
