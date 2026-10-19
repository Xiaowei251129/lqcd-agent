"""B02 child source isolation and shared production bootstrap admission."""
from harness.temporary import mkdtemp
from pathlib import Path
from dataclasses import asdict
import multiprocessing

import pytest

from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome
from lqcd_agent.control.children import ForkRunRequest, ReplayRunRequest
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.pause import PublishPauseRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from lqcd_agent.control.protocol import operation_variant
from helpers.process_client import child_client


@pytest.fixture
def child_control():
    root = Path(mkdtemp(prefix="lqcd-agent-b02-child-", dir="/private/tmp"))
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    plane = ControlPlane(coordinator, worker_id="worker")
    actor = ActorContext("operator", "human", ("control.internal", "fork", "policy.select", "replay", "resume", "start"))
    inputs = {"root_goal": {"goal": "synthetic"}, "input_snapshot": {"data": "synthetic"}}
    source = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "phase_b_test"), actor=actor)
    try:
        yield coordinator, plane, actor, source
    finally:
        coordinator.close()


@pytest.mark.parametrize("fork", [False, True])
def test_child_bootstrap_reuses_admission_and_never_mutates_source(child_control, fork):
    coordinator, plane, actor, source = child_control
    locator = source["result"]["run_locator"]
    source_root = coordinator.root / locator["case_id"] / locator["run_id"]
    if fork:
        class Target:
            def invoke(self, identity):
                return TargetOutcome("failed", {"current_artifact_ids": {}}, {"type": "SyntheticRecovery", "message": "Deterministic domain input"})

        leases = InvocationLeases(coordinator)
        capability = source["result"]["capability_id"]
        leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
        leases.invoke(capability, "consumer", 1, Target())
        plane.publish_pause(PublishPauseRequest(locator, "recovery_decision", "attempt_000001", None,
                                               {"kind": "recovery_decision", "actions": ["abandon_and_halt"]},
                                               {"actor_type": "human", "scopes": ["resume"]}, "publish"), actor=actor)
    before = {str(path.relative_to(source_root)): path.read_bytes() for path in source_root.rglob("*") if path.is_file()}
    head = loads(coordinator.connection.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()[0])["projection"]["execution_head"]
    input_digest = coordinator.get(source["operation_id"])["request"]["root_inputs_digest"]
    request = ForkRunRequest(locator, "child", head, profile_id="phase_b_test") if fork else ReplayRunRequest(locator, "child", input_digest)
    create = plane.fork_run if fork else plane.replay_run
    result = create(request, actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "running"
    child = result["result"]["run_locator"]
    assert child != locator
    records = parse_ledger((coordinator.root / child["case_id"] / child["run_id"] / "execution_history.jsonl").read_bytes()).values
    assert [r["record_type"] for r in records] == ["run", "lineage", "budget", "budget", "cycle", "attempt", "transition", "run_lifecycle"]
    assert records[1]["source_snapshot_proof"]["source_run_identity"] == locator
    assert records[2]["event"] == "policy_initialized" and records[3]["payload"]["decision"] == "allow"
    assert records[5]["status"] == "scheduled" and records[5]["attempt_id"] == "attempt_000001"
    assert not any(row["record_type"] == "pause" for row in records)
    assert create(request, actor=actor) == result
    assert {str(path.relative_to(source_root)): path.read_bytes() for path in source_root.rglob("*") if path.is_file()} == before
    InvocationLeases(coordinator).acquire(result["result"]["capability_id"], "child-consumer", expected_epoch=0, lease_seconds=5)
    changed = ForkRunRequest(locator, "child", head, profile_id="balanced_v1") if fork else ReplayRunRequest({**locator, "run_id": "unknown"}, "child", input_digest)
    with pytest.raises(ControlIntegrityError, match="Same-key"):
        create(changed, actor=actor)


def test_fork_running_source_rejects_before_child_reservation(child_control):
    coordinator, plane, actor, source = child_control
    with pytest.raises(ControlIntegrityError, match="committed terminal"):
        plane.fork_run(ForkRunRequest(source["result"]["run_locator"], "fork", source["result"]["execution_head"]), actor=actor)
    assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 1


@pytest.mark.parametrize("phase", operation_variant("replay_run", "not_applicable")["phases"][1:])
@pytest.mark.parametrize("side", ["before", "after"])
def test_replay_child_process_restart_keeps_one_frozen_child(child_control, phase, side):
    coordinator, plane, actor, source = child_control
    locator = source["result"]["run_locator"]
    source_root = coordinator.root / locator["case_id"] / locator["run_id"]
    source_bytes = {str(p.relative_to(source_root)): p.read_bytes() for p in source_root.rglob("*") if p.is_file()}
    request = ReplayRunRequest(locator, "replay", coordinator.get(source["operation_id"])["request"]["root_inputs_digest"])
    context = multiprocessing.get_context("spawn")

    def run_child(boundary, elapsed):
        parent, child = context.Pipe()
        process = context.Process(target=child_client, args=(child, str(coordinator.root), asdict(request), False, boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary is not None:
                assert process.exitcode == 88
                return None
            assert process.exitcode == 0 and parent.poll(2)
            return parent.recv()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()

    run_child(("control.replay_run.not_applicable." + phase, side), 0)
    reserved = coordinator.lookup_key("public_control", "replay")
    child = reserved["reservation"]["reserved_child_run_locator"]
    result = run_child(None, 40)
    assert result["operation_id"] == reserved["operation_id"] and result["operation_status"] == "committed"
    assert result["result"]["run_locator"] == child and result["lease_epoch"] == 2
    assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 2
    assert {str(p.relative_to(source_root)): p.read_bytes() for p in source_root.rglob("*") if p.is_file()} == source_bytes
