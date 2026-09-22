"""Lost control plans must not remain indefinitely materializable."""
import multiprocessing

import pytest

from helpers.process_client import pause_client
from lqcd_agent.control.coordinator import MaterializationSnapshotError
from lqcd_agent.control.pause import CancelPauseRequest, PublishPauseRequest, ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from test_pause_control import control


def requests(locator):
    publish = PublishPauseRequest(locator, "recovery_decision", "attempt_000001", None,
        {"kind": "recovery_decision", "actions": ["abandon_and_halt"]},
        {"actor_type": "human", "scopes": ["resume"]}, "publish")
    payload = {"action": "abandon_and_halt"}
    return {"publish": publish, "cancel": CancelPauseRequest(locator, "pause_000001", "cancel", "operator_cancel"),
            "resume": ResumeRunRequest(locator, "pause_000001", "resume", "recovery_decision", payload, digest(payload))}


def interrupt_plan(control, action):
    coordinator, plane, actor, locator = control
    request = requests(locator)
    if action != "publish":
        plane.publish_pause(request["publish"], actor=actor)
    phase = {"publish": "pause_prepared_recorded", "cancel": "pause_cancelled_recorded", "resume": "pause_claimed_recorded"}[action]
    def stop(name, side, value):
        if name.startswith("control." + action + "_") and name.endswith("." + phase) and side == "after":
            raise RuntimeError("synthetic plan interruption")
    coordinator.observer = stop
    method = getattr(plane, action + ("_pause" if action in ("publish", "cancel") else "_run"))
    with pytest.raises(RuntimeError, match="plan interruption"):
        method(request[action], actor=actor)
    coordinator.observer = None
    operation = coordinator.lookup_key("internal_pause" if action == "publish" else "public_control", action)
    return operation, request[action], method


@pytest.mark.parametrize("action", ["publish", "cancel", "resume"])
@pytest.mark.parametrize("missing", [False, True])
def test_pause_plan_loss_is_terminal_and_preserves_existing_owners_after_process_restart(control, action, missing):
    coordinator, plane, actor, locator = control
    operation, request, method = interrupt_plan(control, action)
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    before = {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    pause_before = [tuple(row) for row in coordinator.connection.execute("SELECT * FROM pause_ownership")]
    with coordinator.transaction() as db:
        if missing:
            db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (operation["operation_id"],))
        else:
            db.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?", (b'{}', operation["operation_id"]))
    # Query remains read-only; classification requires the rightful mutating caller.
    assert plane.query_operation(operation["operation_id"])["operation_status"] == "in_progress"
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    worker = context.Process(target=pause_client, args=(child, str(coordinator.root), locator, action), kwargs={"elapsed": 40})
    try:
        worker.start()
        child.close()
        assert parent.poll(20)
        kind, result = parent.recv()
        worker.join(20)
        assert worker.exitcode == 0 and kind == "result", result
    finally:
        if worker.is_alive():
            worker.kill()
            worker.join()
        parent.close()
    assert result["operation_status"] == ("recovery_required" if missing else "failed")
    assert result["publication_status"] == "terminal" and result["run_status"] is None
    assert result["terminal_closure"] == ("not_applicable" if action == "publish" else "unavailable")
    assert [tuple(row) for row in coordinator.connection.execute("SELECT * FROM pause_ownership")] == pause_before
    assert {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before
    assert method(request, actor=actor) == result
    assert plane.query_operation(operation["operation_id"]) == result
    if action != "publish":
        closure = loads(coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0])
        assert closure["terminal_closure_owner_operation_id"] == operation["operation_id"]
        assert closure["terminal_closure"] == "unavailable"


def test_lost_plan_classification_cannot_be_committed_by_stale_worker(control):
    coordinator, _, _, _ = control
    operation, _, _ = interrupt_plan(control, "publish")
    coordinator.clock.advance(31)
    replacement = coordinator.acquire(operation["operation_id"], "replacement", lease_seconds=30)
    with pytest.raises(ControlIntegrityError, match="Stale"):
        coordinator.quarantine_plan(operation, "worker", MaterializationSnapshotError(operation["operation_id"], missing=True))
    assert coordinator.get(operation["operation_id"]) == replacement
