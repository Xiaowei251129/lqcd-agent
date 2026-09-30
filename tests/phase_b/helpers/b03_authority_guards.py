"""Real Backend and consumer fences reject late or foreign effects."""
from dataclasses import asdict, replace
from functools import partial
from pathlib import Path

from harness.pytest_evidence import production_hook
from harness.trace import event
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.external_operation import ExternalDispatch
from lqcd_agent.code_agent.verification_resources import _commit
from lqcd_agent.control.capabilities import ArtifactEffectPort, InvocationLeases
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from test_external_consumption_control import CanonicalDomainConsumer, normal_external
from test_external_operation_recovery import RefuseRedispatch
from .b03_analysis_execution_cases import _run
from .b03_uncertain_consumer_cases import CanonicalConsumerHost
from .runtime_cases import run_files


GUARDS = ("external.late_writer", "consumption_failure.backend_proof_not_consumer_proof",
          "consumption_failure.duplicate_settlement", "consumption_failure.forged_artifact",
          "consumption_failure.late_writer", "consumption_failure.nonexternal_reason_rejection",
          "consumption_failure.second_stop_owner")


class RejectWithoutConsumerStop(CanonicalDomainConsumer):
    """Backend stop evidence cannot establish a separate consumer stop."""

    def consume_external(self, identity, binding, port):
        self.preflight_delivery(binding)
        raise ControlIntegrityError("Deterministic consumer failure without Host stop evidence")


def _guard_client(pipe, output, producer, request, actor, boundary, hook, side, payload, hook_request=None):
    def observer(name, observed_side, value):
        if hook_request is not None and (name, observed_side) == (hook, side):
            observer.production_hooks.pop((hook, side), None)

    if hook_request is not None:
        observer.production_hooks = {(hook, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0), observer=observer)
    try:
        plane = ControlPlane(coordinator, worker_id="worker")
        if boundary == "consumption_failure.backend_proof_not_consumer_proof":
            plane.resume_target_adapter = plane.external_adapter = RejectWithoutConsumerStop(
                coordinator, coordinator.root / "base_repository")
            pipe.send(plane.resume_run(ResumeRunRequest(**request), actor=ActorContext(
                **{**actor, "scopes": tuple(actor["scopes"])})))
            return
        try:
            if boundary == "external.late_writer":
                backend = RefuseRedispatch(coordinator.root / "fake_backend", clock=lambda: 100)
                ExternalDispatch(coordinator, producer, "host", 1, backend,
                    DeterministicContainment(coordinator.root / "containment"),
                    backend.read_receipt, backend.read_result).authorize()
            elif boundary in ("consumption_failure.nonexternal_reason_rejection", "consumption_failure.second_stop_owner"):
                plane.resume_run(ResumeRunRequest(**request), actor=ActorContext(
                    **{**actor, "scopes": tuple(actor["scopes"])}))
            else:
                port = ArtifactEffectPort(InvocationLeases(coordinator), None, payload["capability"], "worker", 1)
                if boundary == "consumption_failure.duplicate_settlement":
                    _commit(port, "resource_settled", payload["settlement"])
                else:
                    member = "code_agent_result.json" if boundary == "consumption_failure.forged_artifact" else "late.py"
                    port.write_member(member, b'{"usable":true}')
        except ControlIntegrityError as error:
            pipe.send({"rejected": type(error).__name__, "reason": str(error)})
        else:
            raise AssertionError("Foreign or revoked effect was accepted")
    finally:
        coordinator.close()
        pipe.close()


def authority_guard(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in GUARDS and outcome == "integrity_conflict"
    fixture = normal_external.__wrapped__()
    coordinator, plane, actor, locator, request, _ = next(fixture)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    producer = request.input_snapshot["producer_operation_id"]
    original = ExternalControl(coordinator).read(coordinator.connection, producer)
    original_final = read_regular(root / original["terminal_evidence_reference"])
    payload = {}
    backend_proof = boundary == "consumption_failure.backend_proof_not_consumer_proof"
    failure_guard = boundary not in ("external.late_writer", "consumption_failure.nonexternal_reason_rejection") and not backend_proof
    try:
        if failure_guard:
            plane.resume_target_adapter = plane.external_adapter = CanonicalConsumerHost(
                coordinator, coordinator.root / "base_repository", reject=True)
            failed = plane.resume_run(request, actor=actor)
            assert failed["operation_status"] == "committed" and failed["run_status"] == "failed", failed
            capability = "capability_" + failed["operation_id"]
            cap = InvocationLeases(coordinator).get(capability)[1]
            assert cap["state"] == "uncertain" and cap["invocation_epoch"] > 1
            settlements = [r["payload"] for r in parse_ledger(read_regular(root / "execution_history.jsonl")).values
                           if r["record_type"] == "budget" and r["event"] == "resource_settled"]
            assert len(settlements) == 1
            payload = {"capability": capability, "settlement": settlements[0]}
        if boundary in ("consumption_failure.nonexternal_reason_rejection", "consumption_failure.second_stop_owner"):
            value = {"action": "abandon_and_halt" if failure_guard else "continue_existing_target"}
            request = replace(request, idempotency_key="foreign-consumer-stop", input_kind="recovery_decision",
                              input_snapshot=value, input_digest=digest(value))
            hook = "resume.request"
        elif backend_proof:
            hook = "control.resume_run.continue_execution.consumption_failure_stop_verified"
        else:
            hook = "external.backend_authority_lookup" if boundary == "external.late_writer" else "invocation.capability_lookup"
        tables = ("control_operations", "control_phases", "invocation_capabilities", "external_operations", "run_terminal_closure")
        def rows():
            return {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)] for table in tables}
        files, prior = run_files(coordinator.root), rows()
        args = (str(coordinator.root), producer, asdict(request), asdict(actor), boundary, hook, side, payload)
        first = _run(_guard_client, (*args, hook_request), hook_request=hook_request)
        stable_files, stable_rows = run_files(coordinator.root), rows()
        second = _run(_guard_client, args)
        assert first == second and stable_files == run_files(coordinator.root) and stable_rows == rows()
        if backend_proof:
            assert first["operation_status"] == "recovery_required" and first["terminal_closure"] == "unavailable", first
            operation = coordinator.get(first["operation_id"])
            evidence = next(row["evidence"] for row in coordinator.history(first["operation_id"])
                            if row["phase"] == "consumption_failure_stop_verified")
            assert evidence["consumer_verifier_containment_stop_and_write_fence_proof"]["classification"] == "unavailable"
            assert operation["reservation"]["target_prestart_closure"]["external"]["value"]["proof_kind"] == "safe_stop"
            assert loads(read_regular(root / "artifact_index.json"))["current"]["code"] is None
        else:
            assert files == stable_files and prior == stable_rows
            expected = ("Backend worker lost its original authority" if boundary == "external.late_writer" else
                        "Resume reason or opened head mismatch" if boundary == "consumption_failure.nonexternal_reason_rejection" else
                        "Run already has terminal owner" if boundary == "consumption_failure.second_stop_owner" else
                        "Resume authorization is not active")
            assert first["reason"] == expected, first
        final = ExternalControl(coordinator).read(coordinator.connection, producer)
        assert final["resolution_owner"] == original["resolution_owner"] == "normal"
        assert final["terminal_evidence_digest"] == original["terminal_evidence_digest"]
        assert read_regular(root / original["terminal_evidence_reference"]) == original_final
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        return {"schema_version": "0.1", "events": [
            event("code_effect_authority_checked", phase=hook, stage=side, outcome=outcome, target=boundary),
            event("code_effect_authority_rejected", status="unavailable" if backend_proof else "rejected",
                  guard="original_owner_no_foreign_effect_no_borrowed_proof"),
            event("code_effect_rejection_replayed", accepted=True, guard="same_original_final_bytes")]
        }
    finally:
        fixture.close()
