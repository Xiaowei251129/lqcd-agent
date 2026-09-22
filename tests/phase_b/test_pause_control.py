"""B02 Pause publication uses the production coordinator and execution records."""
from pathlib import Path
import multiprocessing
import tempfile

import pytest

from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome
from lqcd_agent.control.checkpoints import verify_checkpoint
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.pause import CancelPauseRequest, PauseExpired, PublishPauseRequest, ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from lqcd_agent.control.protocol import operation_variant
from helpers.process_client import pause_client
from lqcd_agent.control.operations import AdvanceRunRequest
from test_advance_control import SyntheticDomainRoute


@pytest.fixture
def control():
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-pause-", dir="/private/tmp"))
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    actor = ActorContext("operator", "human", ("cancel", "control.internal", "resume", "start"))
    plane = ControlPlane(coordinator, worker_id="worker")
    inputs = {"root_goal": {"goal": "synthetic"}, "input_snapshot": {"data": "synthetic"}}
    result = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "phase_b_test"), actor=actor)
    leases = InvocationLeases(coordinator)
    capability = result["result"]["capability_id"]
    leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)

    class Target:
        def invoke(self, identity):
            return TargetOutcome("failed", {"current_artifact_ids": {}}, {"type": "SyntheticRecovery", "message": "Deterministic domain input"})

    leases.invoke(capability, "consumer", 1, Target())
    try:
        yield coordinator, plane, actor, result["result"]["run_locator"]
    finally:
        coordinator.close()


def test_recovery_pause_publication_has_exact_two_checkpoint_closure(control):
    coordinator, plane, actor, locator = control
    request = PublishPauseRequest(locator, "recovery_decision", "attempt_000001", None,
                                  {"kind": "recovery_decision", "actions": ["abandon_and_halt"]},
                                  {"actor_type": "human", "scopes": ["resume"]}, "publish")
    result = plane.publish_pause(request, actor=actor)
    assert result["operation_status"] == "committed"
    assert result["result"]["pause_id"] == "pause_000001"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert [(r["record_type"], r["event"]) for r in records[-3:]] == [
        ("pause", "pause_prepared"), ("run_lifecycle", "transitioned"), ("pause", "pause_opened")]
    snapshot = coordinator.snapshot(result["operation_id"])
    pending = next(step["checkpoint"] for step in snapshot["steps"] if step["target"] == "prepared_checkpoint_committed")
    prepared_state = verify_checkpoint(root, pending["manifest"])
    assert prepared_state["pending_pause"]["status"] == "prepared" and prepared_state["active_pause"] is None
    public = snapshot["public"]
    public_state = verify_checkpoint(root, public["manifest"])
    assert public_state["pending_pause"] is None and public_state["active_pause"]["status"] == "opened"
    assert public_state["run_status"] == "paused"
    validate_run_root(root, manifest=public["manifest"], projection=public["projection"])
    row = coordinator.connection.execute("SELECT value FROM pause_ownership").fetchone()
    assert loads(row[0])["owner"] is None
    assert plane.publish_pause(request, actor=actor) == result


def test_null_external_cancel_owns_pause_and_terminal_together(control):
    coordinator, plane, actor, locator = control
    published = plane.publish_pause(PublishPauseRequest(
        locator, "recovery_decision", "attempt_000001", None,
        {"kind": "recovery_decision", "actions": ["abandon_and_halt"]}, {"actor_type": "human", "scopes": ["resume"]}, "publish"), actor=actor)
    request = CancelPauseRequest(locator, published["result"]["pause_id"], "cancel", "operator_cancel")
    result = plane.cancel_pause(request, actor=actor)
    assert result["operation_status"] == "committed" and result["terminal_closure"] == "committed"
    assert result["run_status"] == "halted"
    owner = loads(coordinator.connection.execute("SELECT value FROM pause_ownership").fetchone()[0])
    terminal = loads(coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0])
    assert owner["owner"] == terminal["terminal_closure_owner_operation_id"] == result["operation_id"]
    assert owner["status"] == "cancelled"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    ledger = (root / "execution_history.jsonl").read_bytes()
    records = parse_ledger(ledger).values
    assert [row["status"] for row in records if row["record_type"] == "pause"] == ["prepared", "opened", "cancelled"]
    assert not any(row["record_type"] == "attempt" for row in records[-2:])
    assert plane.cancel_pause(request, actor=actor) == result
    assert (root / "execution_history.jsonl").read_bytes() == ledger
    with pytest.raises(ControlIntegrityError, match="opened Pause"):
        plane.cancel_pause(CancelPauseRequest(locator, request.pause_id, "second", "operator_cancel"), actor=actor)


@pytest.mark.parametrize("target", ["decision_coordinator", "code_agent", "codex_handoff"])
def test_recovery_continue_only_reuses_an_allowed_ordinary_target(control, target):
    coordinator, plane, actor, locator = control

    class Consumer:
        calls = 0

        def invoke(self, identity):
            self.calls += 1
            assert identity["attempt_id"] == "attempt_000002"
            return TargetOutcome("pending", {"current_artifact_ids": {}})

    consumer = Consumer()
    plane.route_adapter = SyntheticDomainRoute(target)
    plane.resume_target_adapter = consumer
    plane.advance_run(AdvanceRunRequest(locator, "attempt_000001", "advance"), actor=actor)
    result = plane.publish_pause(PublishPauseRequest(locator, "recovery_decision", "attempt_000001", "attempt_000002",
                                                    {"kind": "recovery_decision", "actions": ["abandon_and_halt", "continue_existing_target"]},
                                                    {"actor_type": "human", "scopes": ["resume"]}, "publish"), actor=actor)
    payload = {"action": "continue_existing_target"}
    request = ResumeRunRequest(locator, result["result"]["pause_id"], "resume", "recovery_decision", payload, digest(payload))
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    before = (root / "execution_history.jsonl").read_bytes()
    capabilities = coordinator.connection.execute("SELECT count(*) FROM invocation_capabilities").fetchone()[0]
    if target in ("code_agent", "codex_handoff"):
        with pytest.raises(ControlIntegrityError, match="cannot continue"):
            plane.resume_run(request, actor=actor)
        assert consumer.calls == 0 and (root / "execution_history.jsonl").read_bytes() == before
        assert coordinator.connection.execute("SELECT count(*) FROM invocation_capabilities").fetchone()[0] == capabilities
        assert loads(coordinator.connection.execute("SELECT value FROM pause_ownership").fetchone()[0])["owner"] is None
    else:
        resumed = plane.resume_run(request, actor=actor)
        assert resumed["operation_status"] == "committed" and resumed["run_status"] == "running"
        assert consumer.calls == 1
        assert plane.resume_run(request, actor=actor) == resumed and consumer.calls == 1
        records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        assert sum(r["record_type"] == "attempt" and r["event"] == "scheduled" for r in records) == 2
        tail = [(r["record_type"], r["event"]) for r in records[-5:]]
        assert tail == [("pause", "pause_claimed"), ("pause", "pause_consumed"), ("run_lifecycle", "transitioned"),
                        ("attempt", "started"), ("attempt", "finished")]


CRASH_PHASES = [("publish", phase) for phase in operation_variant("publish_pause", "not_applicable")["phases"][1:]]
CRASH_PHASES += [("abandon", phase) for phase in operation_variant("resume_run", "abandon_and_halt")["phases"][1:]]
CRASH_PHASES += [("cancel", phase) for phase in ("cancel_arbitrated", "pause_cancelled_recorded", "target_disposition_committed",
                 "resource_disposition_committed", "terminal_eligibility_verified", "terminal_lifecycle_recorded", "terminal_checkpoint_committed", "result_committed")]


@pytest.mark.parametrize("action,phase", CRASH_PHASES)
@pytest.mark.parametrize("side", ["before", "after"])
def test_pause_real_process_restart_preserves_published_producers(control, action, phase, side):
    coordinator, plane, actor, locator = control
    if action != "publish":
        plane.publish_pause(PublishPauseRequest(locator, "recovery_decision", "attempt_000001", None,
                                               {"kind": "recovery_decision", "actions": ["abandon_and_halt"]},
                                               {"actor_type": "human", "scopes": ["resume"]}, "publish"), actor=actor)
    operation_type = {"publish": "publish_pause.not_applicable", "cancel": "cancel_pause.not_applicable", "abandon": "resume_run.abandon_and_halt"}[action]
    context = multiprocessing.get_context("spawn")

    def run_child(boundary, elapsed):
        parent, child = context.Pipe()
        process = context.Process(target=pause_client, args=(child, str(coordinator.root), locator, action, boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary is not None:
                assert process.exitcode == 87
                return None
            assert process.exitcode == 0 and parent.poll(2)
            kind, result = parent.recv()
            assert kind == "result", result
            return result
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()

    run_child(("control." + operation_type + "." + phase, side), 0)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    prefix = (root / "execution_history.jsonl").read_bytes()
    result = run_child(None, 40)
    assert result["operation_status"] == "committed"
    assert (root / "execution_history.jsonl").read_bytes().startswith(prefix)
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    for row in records[len(parse_ledger(prefix).records):]:
        if row["record_type"] == "pause":
            assert row["lease_epoch"] == 2
    operation = coordinator.get(result["operation_id"])
    assert operation["lease_epoch"] == 2
    if action != "publish":
        assert result["run_status"] == "halted" and result["terminal_closure"] == "committed"
        assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 1


@pytest.mark.parametrize("elapsed", [59, 60, 61])
def test_null_recovery_resume_abandons_without_attempt_or_expires_without_mutation(control, elapsed):
    coordinator, plane, actor, locator = control
    published = plane.publish_pause(PublishPauseRequest(
        locator, "recovery_decision", "attempt_000001", None,
        {"kind": "recovery_decision", "actions": ["abandon_and_halt"]}, {"actor_type": "human", "scopes": ["resume"]}, "publish"), actor=actor)
    pause_id = published["result"]["pause_id"]
    payload = {"action": "abandon_and_halt"}
    request = ResumeRunRequest(locator, pause_id, "resume", "recovery_decision", payload, digest(payload))
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    ledger = root / "execution_history.jsonl"
    before = ledger.read_bytes()
    count = coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0]
    coordinator.clock.advance(elapsed)
    if elapsed >= 60:
        with pytest.raises(PauseExpired):
            plane.resume_run(request, actor=actor)
        assert ledger.read_bytes() == before
        assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == count
        assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 0
    else:
        result = plane.resume_run(request, actor=actor)
        assert result["operation_status"] == "committed" and result["run_status"] == "halted"
        records = parse_ledger(ledger.read_bytes()).values
        assert records[-1]["from_status"] == "paused" and records[-1]["to_status"] == "halted"
        assert sum(r["record_type"] == "attempt" for r in records) == 3
        assert [r["status"] for r in records if r["record_type"] == "pause"] == ["prepared", "opened", "claimed", "consumed"]
        assert plane.resume_run(request, actor=actor) == result
        payload = {"action": "continue_existing_target"}
        changed = ResumeRunRequest(locator, pause_id, "resume", "recovery_decision", payload, digest(payload))
        with pytest.raises(ControlIntegrityError, match="Same-key"):
            plane.resume_run(changed, actor=actor)
