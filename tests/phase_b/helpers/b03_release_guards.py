"""Reject forged release authority in separate, side-effect-free processes."""
from dataclasses import asdict
from functools import partial
from pathlib import Path

from harness.pytest_evidence import production_hook
from harness.trace import event
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, loads
from test_external_consumption_control import normal_external
from .b03_analysis_execution_cases import _run
from .runtime_cases import run_client, run_files


GUARDS = ("release.conflicting_bytes", "release.stale_generation", "release.stale_epoch",
          "release.missing_settlement", "release.missing_attempt", "release.missing_artifact",
          "release.forged_not_applicable")
HOOK = "external.consumption_release_validation"


def _release_client(pipe, output, owner, proof, side, hook_request=None):
    def observer(name, observed_side, value):
        pass

    if hook_request is not None:
        observer.production_hooks = {(HOOK, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(140, 40), observer=observer)
    try:
        try:
            with coordinator.transaction() as db:
                ExternalControl(coordinator).release_consumption(db, coordinator.get(owner, db=db), proof)
        except ControlIntegrityError as error:
            pipe.send({"rejected": type(error).__name__, "reason": str(error)})
        else:
            raise AssertionError("Forged release authority was accepted")
    finally:
        coordinator.close()
        pipe.close()


def release_guard(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in GUARDS and outcome == "integrity_conflict"
    fixture = normal_external.__wrapped__()
    coordinator, plane, actor, locator, resume, adapter = next(fixture)
    try:
        config = {"root": str(coordinator.root), "method": "resume_run", "request_class": "ResumeRunRequest",
                  "request": asdict(resume), "actor": asdict(actor), "safe": True, "failure": False,
                  "ordinary": False, "route": "decision_coordinator", "variant": "continue_execution"}
        run_client(config, 0, fault=("control.resume_run.continue_execution.external_consumption_released", "before"))
        operation = coordinator.lookup_key("public_control", resume.idempotency_key)
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        ledger = root / "execution_history.jsonl"
        external = ExternalControl(coordinator)
        value = external.read(coordinator.connection, resume.input_snapshot["producer_operation_id"])
        proof = external.consumption_proof(operation, value, parse_ledger(read_regular(ledger)).values,
            loads(read_regular(root / "artifact_index.json")), phase_revision=operation["phase_revision"] + 1)
        if boundary == "release.conflicting_bytes":
            final = ExternalControl(coordinator).read(coordinator.connection, proof["external_operation_id"])
            (root / final["terminal_evidence_reference"]).write_bytes(b"{}")
        elif boundary == "release.stale_generation":
            proof["active_binding_generation"] += 1
        elif boundary == "release.stale_epoch":
            proof["consumption_epoch"] += 1
        elif boundary == "release.forged_not_applicable":
            proof.update(release_kind="not_applicable", not_applicable_reason="external_result_has_no_external_operation")
        elif boundary in ("release.missing_settlement", "release.missing_attempt"):
            records = parse_ledger(read_regular(ledger)).values
            wanted = "resource_settled" if boundary == "release.missing_settlement" else "finished"
            victim = next(row for row in records if row["event"] == wanted and
                          (row["record_type"] == "budget" if wanted == "resource_settled" else row.get("attempt_id") == "attempt_000002"))
            ledger.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in records if row is not victim))
        else:
            path = root / "artifact_index.json"
            index = loads(read_regular(path))
            index["current"]["code"] = None
            path.write_bytes(canonical_bytes(index))
        files = run_files(coordinator.root)
        original = ExternalControl(coordinator).read(coordinator.connection, proof["external_operation_id"])
        assert original["active_binding_status"] == "active" and original["consumption_release"] is None
        tables = ("control_operations", "control_phases", "invocation_capabilities", "external_operations", "run_terminal_closure")
        rows = {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)] for table in tables}
        args = (str(coordinator.root), operation["operation_id"], proof, side)
        first = _run(_release_client, (*args, hook_request), hook_request=hook_request)
        second = _run(_release_client, args)
        assert first == second and run_files(coordinator.root) == files
        assert rows == {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)] for table in tables}
        assert ExternalControl(coordinator).read(coordinator.connection, proof["external_operation_id"]) == original
        return {"schema_version": "0.1", "events": [
            event("release_authority_checked", phase=HOOK, stage=side, outcome=outcome, target=boundary, owner="original_resume"),
            event("release_authority_rejected", status="rejected", guard="no_release_no_settlement_no_registration", owner="original_resume"),
            event("release_rejection_replayed", accepted=True, guard="same_original_bytes")]
        }
    finally:
        fixture.close()
