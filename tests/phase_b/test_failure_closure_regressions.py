"""Real restart and ownership regressions for B02 failure classification."""
from dataclasses import asdict
import multiprocessing

import pytest

from helpers.process_client import external_resume_client, pause_client, resume_client
from lqcd_agent.control.capabilities import HumanResponseVerdict, TargetOutcome
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ControlPlane
from lqcd_agent.control.operations import BootstrapIntegrityError, TerminalOperations
from lqcd_agent.control.pause import ConsumptionFailure, ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from test_bootstrap_control import ACTOR, request as start_request, root
from test_external_consumption_control import normal_external
from test_human_control import human_pause
from test_pause_control import control
from test_snapshot_loss_control import interrupt_plan


def process_result(target, args, **kwargs):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=target, args=(child, *args), kwargs=kwargs)
    try:
        process.start()
        child.close()
        assert parent.poll(30), "Fresh control client did not finish"
        result = parent.recv()
        process.join(20)
        assert process.exitcode == 0, result
        return result
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()


def files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("side", ["before", "after"])
def test_close_reserved_before_ownership_retries_corrupt_source_in_same_operation(side):
    from helpers.runtime_cases import exercise_phase_case

    exercise_phase_case("control.close_run.not_applicable.terminal_ownership_reserved." + side + ".integrity_conflict")


@pytest.mark.parametrize("side", ["before", "after"])
def test_lost_failure_intent_quarantines_original_normal_binding(side):
    from helpers.runtime_cases import exercise_phase_case

    exercise_phase_case("control.resume_run.continue_execution.consumption_failure_stop_verified." + side + ".non_materializable_domain_gap")


@pytest.mark.parametrize("action", ["publish", "cancel", "resume"])
def test_corrupt_pause_log_closes_original_operation_after_restart(control, action):
    coordinator, plane, actor, locator = control
    operation, request, method = interrupt_plan(control, action)
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    with (run / "execution_history.jsonl").open("ab") as stream:
        stream.write(b"{")
    before = files(run)
    kind, result = process_result(pause_client, (str(coordinator.root), locator, action), elapsed=40)
    assert kind == "result", result
    assert result["operation_id"] == operation["operation_id"] and result["operation_status"] == "failed"
    assert result["run_status"] is None
    assert result["terminal_closure"] == ("not_applicable" if action == "publish" else "unavailable")
    assert method(request, actor=actor) == result == plane.query_operation(operation["operation_id"])
    assert files(run) == before
    closures = list(coordinator.connection.execute("SELECT value FROM run_terminal_closure"))
    assert len(closures) == (0 if action == "publish" else 1)
    if closures:
        assert loads(closures[0][0])["terminal_closure_owner_operation_id"] == operation["operation_id"]


def test_old_bootstrap_error_cannot_use_same_worker_new_epoch(root, monkeypatch):
    from lqcd_agent.control.clock import FakeClock

    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    plane = ControlPlane(coordinator, worker_id="worker")
    original = TerminalOperations.fail_bootstrap
    replacement = {}

    def break_prefix(*args):
        raise BootstrapIntegrityError("synthetic bootstrap integrity rejection")

    def replace_before_classifying(self, operation, error):
        assert error.control_failure_context["phase_revision"] == 1
        coordinator.clock.advance(31)
        competitor = Coordinator(root, clock=coordinator.clock)
        try:
            replacement.update(competitor.acquire(operation["operation_id"], "worker", lease_seconds=30))
        finally:
            competitor.close()
        return original(self, operation, error)

    monkeypatch.setattr(plane, "_verify_start_prefix", break_prefix)
    monkeypatch.setattr(TerminalOperations, "fail_bootstrap", replace_before_classifying)
    try:
        with pytest.raises(ControlIntegrityError, match="Stale"):
            plane.start_run(start_request(), actor=ACTOR)
        assert replacement["lease_epoch"] == 2
        assert coordinator.get(replacement["operation_id"]) == replacement
        assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 0
    finally:
        coordinator.close()


@pytest.mark.parametrize("action", ["publish", "cancel", "resume"])
def test_pause_failure_rejects_old_epoch_then_new_call_revalidates(control, action, monkeypatch):
    coordinator, plane, actor, locator = control
    operation, request, method = interrupt_plan(control, action)
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    with (run / "execution_history.jsonl").open("ab") as stream:
        stream.write(b"{")
    before = files(run)
    replacement = {}
    original = coordinator.failed_operation

    def replace(db, failed, worker, error):
        context = error.control_failure_context
        assert context["lease_epoch"] == operation["lease_epoch"]
        assert context["phase_revision"] == coordinator.get(operation["operation_id"], db=db)["phase_revision"]
        # Another committed lease is acquired before the error handler's transaction.
        return original(db, failed, worker, error)

    from lqcd_agent.control.pause import PauseOperations
    fail = PauseOperations._fail
    def change_lease(self, failed, error):
        coordinator.clock.advance(31)
        competitor = Coordinator(coordinator.root, clock=coordinator.clock)
        try:
            replacement.update(competitor.acquire(operation["operation_id"], "worker", lease_seconds=30))
        finally:
            competitor.close()
        return fail(self, failed, error)
    monkeypatch.setattr(coordinator, "failed_operation", replace)
    monkeypatch.setattr(PauseOperations, "_fail", change_lease)
    with pytest.raises(ControlIntegrityError, match="Stale"):
        method(request, actor=actor)
    assert coordinator.get(operation["operation_id"]) == replacement
    assert files(run) == before
    monkeypatch.setattr(PauseOperations, "_fail", fail)
    monkeypatch.setattr(coordinator, "failed_operation", original)
    result = method(request, actor=actor)
    assert result["operation_status"] == "failed" and result["lease_epoch"] == 2
    assert result["terminal_closure"] == ("not_applicable" if action == "publish" else "unavailable")
    assert method(request, actor=actor) == result and files(run) == before


def test_old_consumption_error_cannot_reserve_failure_under_new_epoch(normal_external, monkeypatch):
    coordinator, plane, actor, locator, request, adapter = normal_external
    original = ConsumptionFailure.start
    replacement = {}
    def stop(name, side, value):
        if name == "control.resume_run.continue_execution.prestart_records_committed" and side == "before":
            raise ControlIntegrityError("synthetic claimed failure")
    def replace(self, operation, error):
        coordinator.clock.advance(31)
        competitor = Coordinator(coordinator.root, clock=coordinator.clock)
        try:
            replacement.update(competitor.acquire(operation["operation_id"], "worker", lease_seconds=30))
        finally:
            competitor.close()
        return original(self, operation, error)
    coordinator.observer = stop
    monkeypatch.setattr(ConsumptionFailure, "start", replace)
    with pytest.raises(ControlIntegrityError, match="Stale"):
        plane.resume_run(request, actor=actor)
    coordinator.observer = None
    assert coordinator.get(replacement["operation_id"]) == replacement and replacement["lease_epoch"] == 2
    assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 0
    assert adapter.calls == 0
    monkeypatch.setattr(ConsumptionFailure, "start", original)
    result = plane.resume_run(request, actor=actor)
    assert result["operation_status"] == "committed" and adapter.calls == 1


def test_phase_revision_is_bound_to_failed_boundary_even_without_lease_change(control):
    coordinator, plane, actor, locator = control
    operation, request, method = interrupt_plan(control, "publish")
    error = ControlIntegrityError("old phase failure")
    with pytest.raises(ControlIntegrityError):
        with coordinator.failure_context(operation):
            raise error
    def stop(name, side, value):
        if name == "control.publish_pause.not_applicable.public_paused_checkpoint_committed" and side == "before":
            raise RuntimeError("later boundary")
    coordinator.observer = stop
    with pytest.raises(RuntimeError, match="later boundary"):
        method(request, actor=actor)
    coordinator.observer = None
    current = coordinator.get(operation["operation_id"])
    assert current["lease_epoch"] == operation["lease_epoch"] and current["phase_revision"] > operation["phase_revision"]
    with coordinator.transaction() as db, pytest.raises(ControlIntegrityError, match="Stale"):
        coordinator.failed_operation(db, operation, "worker", error)
    assert coordinator.get(operation["operation_id"]) == current


@pytest.mark.parametrize("missing", [False, True])
def test_claimed_external_lost_plan_uses_original_failure_tail_after_restart(normal_external, missing):
    coordinator, plane, actor, locator, request, adapter = normal_external
    def stop(name, side, value):
        if name == "control.resume_run.continue_execution.prestart_records_committed" and side == "before":
            raise RuntimeError("stop after durable claim")
    coordinator.observer = stop
    with pytest.raises(RuntimeError, match="durable claim"):
        plane.resume_run(request, actor=actor)
    coordinator.observer = None
    operation = coordinator.lookup_key("public_control", request.idempotency_key)
    assert operation["phase"] == "pause_claimed_recorded"
    with coordinator.transaction() as db:
        if missing:
            db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (operation["operation_id"],))
        else:
            db.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?", (b"{}", operation["operation_id"]))
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    before = files(run)
    external_before = loads(coordinator.connection.execute("SELECT value FROM external_operations").fetchone()[0])
    result, calls = process_result(external_resume_client, (str(coordinator.root), asdict(request)), elapsed=40)
    assert calls == 0
    assert result["operation_id"] == operation["operation_id"]
    assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable"
    assert result["operation_phase"] == "consumption_failure_unavailable_recorded" and result["run_status"] is None
    phases = [row["phase"] for row in coordinator.history(operation["operation_id"])]
    assert phases[-4:] == ["consumption_failure_ownership_reserved", "consumption_failure_stop_verified",
                           "consumption_failure_classified", "consumption_failure_unavailable_recorded"]
    external = loads(coordinator.connection.execute("SELECT value FROM external_operations").fetchone()[0])
    assert external["terminal_evidence_digest"] == external_before["terminal_evidence_digest"]
    assert external["resolution_owner"] == "normal" and external["active_binding_status"] == "quarantined"
    assert len(list(coordinator.connection.execute("SELECT * FROM run_terminal_closure"))) == 1
    assert plane.resume_run(request, actor=actor) == result and adapter.calls == 0
    assert files(run) == before


@pytest.mark.parametrize("human_pause", ["balanced_v1"], indirect=True)
@pytest.mark.parametrize("missing", [False, True])
def test_failed_human_repause_is_propagated_to_parent_after_restart(human_pause, missing):
    coordinator, plane, actor, locator, pause, payload = human_pause
    class Invalid:
        calls = 0
        def invoke(self, identity):
            self.calls += 1
            return TargetOutcome("pending", {"current_artifact_ids": {}}, human_response_verdict=HumanResponseVerdict(False, "Synthetic invalid input"))
    adapter = Invalid()
    plane.resume_target_adapter = adapter
    request = ResumeRunRequest(locator, pause, "invalid-response", "human_response", payload, digest(payload))
    def stop(name, side, value):
        if name == "control.publish_pause.not_applicable.pause_prepared_recorded" and side == "after":
            raise RuntimeError("stop second Pause")
    coordinator.observer = stop
    with pytest.raises(RuntimeError, match="second Pause"):
        plane.resume_run(request, actor=actor)
    coordinator.observer = None
    parent = coordinator.lookup_key("public_control", request.idempotency_key)
    child = next(coordinator.get(row[0]) for row in coordinator.connection.execute(
        "SELECT operation_id FROM control_operations WHERE operation_type='publish_pause' AND status='in_progress'"))
    with coordinator.transaction() as db:
        if missing:
            db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (child["operation_id"],))
        else:
            db.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?", (b"{}", child["operation_id"]))
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    before = files(run)
    kind, result, calls = process_result(resume_client, (str(coordinator.root), asdict(request)), elapsed=40, valid=False)
    assert kind == "result", result
    assert calls == []
    assert result["operation_id"] == parent["operation_id"]
    assert result["operation_status"] == ("recovery_required" if missing else "failed")
    assert coordinator.get(parent["operation_id"])["error"]["followup_operation_id"] == child["operation_id"]
    assert plane.resume_run(request, actor=actor) == result and adapter.calls == 1
    assert coordinator.connection.execute("SELECT count(*) FROM control_operations WHERE operation_type='publish_pause'").fetchone()[0] == 2
    assert files(run) == before


@pytest.mark.parametrize("human_pause", ["balanced_v1"], indirect=True)
@pytest.mark.parametrize("missing", [False, True])
def test_committed_human_repause_survives_lost_plan_without_revalidation(human_pause, missing):
    coordinator, plane, actor, locator, pause, payload = human_pause
    class Invalid:
        calls = 0
        def invoke(self, identity):
            self.calls += 1
            return TargetOutcome("pending", {"current_artifact_ids": {}}, human_response_verdict=HumanResponseVerdict(False, "Synthetic invalid input"))
    adapter = Invalid()
    plane.resume_target_adapter = adapter
    request = ResumeRunRequest(locator, pause, "committed-repause", "human_response", payload, digest(payload))
    armed = False
    def stop(name, side, value):
        nonlocal armed
        if (name, side) == ("control.publish_pause.not_applicable.result_committed", "after"):
            armed = True
        if armed and (name, side) == ("coordinator.database_commit", "after"):
            raise RuntimeError("durable child result")
    coordinator.observer = stop
    with pytest.raises(RuntimeError, match="durable child"):
        plane.resume_run(request, actor=actor)
    coordinator.observer = None
    parent = coordinator.lookup_key("public_control", request.idempotency_key)
    child = coordinator.get(coordinator.connection.execute(
        "SELECT operation_id FROM control_operations WHERE operation_type='publish_pause' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
    assert child["status"] == "committed" and parent["status"] == "in_progress"
    with coordinator.transaction() as db:
        if missing:
            db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (child["operation_id"],))
        else:
            db.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?", (b"{}", child["operation_id"]))
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    before = files(run)
    kind, result, calls = process_result(resume_client, (str(coordinator.root), asdict(request)), elapsed=40, valid=False)
    assert kind == "result" and calls == [], result
    assert result["operation_id"] == parent["operation_id"] and result["operation_status"] == "committed"
    assert result["run_status"] == "paused" and result["result"]["pause_id"] == child["result"]["pause_id"]
    assert plane.resume_run(request, actor=actor) == result and adapter.calls == 1
    assert coordinator.get(child["operation_id"]) == child and files(run) == before
    assert coordinator.connection.execute("SELECT count(*) FROM control_operations WHERE operation_type='publish_pause'").fetchone()[0] == 2
