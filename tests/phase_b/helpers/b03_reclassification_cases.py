"""A durable normal-unavailable handoff cannot return to normal resolution."""
from functools import partial
import os
from pathlib import Path

from harness.pytest_evidence import production_hook
from harness.trace import event
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.external_operation import ExternalDispatch, ExternalNormalFinal
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.operations import ExternalControl
from test_external_operation_recovery import RefuseRedispatch
from .b03_analysis_execution_cases import _run
from .canonical_code import canonical_source


HOOK = "control.resolve_external_interrupt.integrity_failure.interrupt_and_terminal_ownership_reserved"


class RecoverableContainment(DeterministicContainment):
    """One failed Fake kill is durable; the next observation may safely stop."""

    def kill_all(self, operation_id):
        super().kill_all(operation_id)
        with self._db(write=True) as db:
            db.execute("UPDATE operations SET kill_fault=0 WHERE operation_id=?", (operation_id,))


def _reclass_client(pipe, output, producer, audit, patch, side, crash=False, hook_request=None):
    def observer(name, observed_side, value):
        if crash and (name, observed_side) == (HOOK, side):
            os._exit(97)

    if hook_request is not None:
        observer.production_hooks = {(HOOK, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0), observer=observer)
    try:
        backend = RefuseRedispatch(coordinator.root / "fake_backend", clock=lambda: 100)
        dispatch = ExternalDispatch(coordinator, producer, "host", 1, backend,
            RecoverableContainment(coordinator.root / "containment"), backend.read_receipt, backend.read_result)
        result = ExternalNormalFinal(dispatch, coordinator.root / "base_repository").commit(tool_audit=audit, patch=patch)
        pipe.send({"result": result, "external": ExternalControl(coordinator).read(coordinator.connection, producer)})
    finally:
        coordinator.close()
        pipe.close()


def reclassification_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    coordinator, _, _, locator, dispatch, _, audit, patch = canonical_source(
        success=True, finalize=False, containment_fault={"kill_all": False})
    producer = dispatch.producer
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    try:
        args = (str(coordinator.root), producer, audit, patch, side)
        _run(_reclass_client, (*args, True, hook_request), crash=True, hook_request=hook_request)
        source = ExternalControl(coordinator).read(coordinator.connection, producer)
        assert source["resolution_owner"] is None and source["operation_phase"] == "result_reference_committed"
        operations = [coordinator.get(row[0]) for row in coordinator.connection.execute(
            "SELECT operation_id FROM control_operations WHERE operation_type='resolve_external_interrupt'")]
        assert len(operations) == 1
        operation = operations[0]
        if outcome == "integrity_conflict":
            task = root / "code_agent_control" / source["attempt_id"] / "code_agent_task.json"
            task.write_bytes(b"{}")
        elif outcome == "non_materializable_domain_gap":
            with coordinator.transaction() as db:
                db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (operation["operation_id"],))
        first = _run(_reclass_client, args)
        second = _run(_reclass_client, args)
        assert first == second and first["result"]["operation_id"] == operation["operation_id"], first
        value = first["external"]
        assert value["resolution_owner"] != "normal"
        assert value["dispatch_receipt_digest"] == source["dispatch_receipt_digest"]
        assert value["result_digest"] == source["result_digest"]
        positive = outcome in ("committed_result_replay", "materializable_publication_prefix")
        if positive:
            assert first["result"]["operation_status"] == "committed" and first["result"]["run_status"] == "failed"
            assert value["resolution_owner"] == "interrupt" and value["proof_kind"] == "safe_stop"
        else:
            assert first["result"]["operation_status"] in ("failed", "recovery_required") and first["result"]["run_status"] is None
        assert len([row for row in coordinator.connection.execute(
            "SELECT operation_id FROM control_operations WHERE operation_type='resolve_external_interrupt'")]) == 1
        assert not (root / "attempts" / source["attempt_id"] / "code_agent_result.json").exists()
        if outcome == "integrity_conflict":
            assert task.read_bytes() == b"{}"
        return {"schema_version": "0.1", "events": [
            event("normal_unavailable_handoff_cut", phase=HOOK, stage=side, outcome=outcome,
                  source="result_reference_committed", owner="original_interrupt"),
            event("normal_unavailable_handoff_recovered", status=first["result"]["operation_status"],
                  run_status=first["result"]["run_status"], target=first["result"]["terminal_closure"],
                  owner="original_interrupt", guard="no_normal_unavailable_or_second_resolution"),
            event("normal_unavailable_handoff_replayed", accepted=True, guard="same_original_interrupt")]
        }
    finally:
        coordinator.close()
