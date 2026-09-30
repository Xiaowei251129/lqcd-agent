"""Real resume-owned verification accounting, separate from Backend coverage."""
from dataclasses import asdict
import multiprocessing
import os
from pathlib import Path

import pytest

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.pause import ConsumerStopObservation, ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from test_external_consumption_control import ExternalDomainConsumer, normal_external
from lqcd_agent.code_agent.subgraph import CodeAgentSubgraph


class VerificationConsumer(ExternalDomainConsumer):
    def __init__(self, root, coordinator, *, fault=None):
        super().__init__(root)
        self.coordinator, self.fault = coordinator, fault
        self.canonical = CodeAgentSubgraph(coordinator, coordinator.root / "base_repository")

    def preflight_delivery(self, binding):
        return self.canonical.preflight_delivery(binding)

    def verify_consumption(self, identity, binding, outcome):
        return self.canonical.verify_consumption(identity, binding, outcome)

    def consume_external(self, identity, binding, port):
        assert not self.coordinator.connection.in_transaction

        def effect():
            assert not self.coordinator.connection.in_transaction
            rows = parse_ledger((self.root / "execution_history.jsonl").read_bytes()).values
            assert rows[-1]["event"] == "resource_reserved"
            # A separate connection must see the committed reservation intent.
            import sqlite3
            database = self.coordinator.connection.execute("PRAGMA database_list").fetchone()[2]
            with sqlite3.connect(database) as reader:
                value = loads(reader.execute("SELECT value FROM invocation_capabilities WHERE capability_id=?", (port.capability_id,)).fetchone()[0])
                assert value["verification_intents"][-1]["published"]
            marker = self.root.parent.parent / "verification-effect.txt"
            with marker.open("a") as stream:
                stream.write("executed\n")
            if self.fault == "exception":
                raise ControlIntegrityError("Verifier integrity failure")
            if self.fault == "tamper":
                (self.root / "artifact_index.json").write_bytes(b"{}")
            if self.fault == "expiry":
                self.coordinator.clock.advance(40)
            if self.fault == "crash":
                os._exit(94)
            return {"spec_id": "check", "status": "passed", "output_digest": digest("bounded output")}

        result = port.run_verification(spec_id="check", input_digest=digest("input"), config_digest=digest("config"),
                                       timeout_seconds=1, effect=effect)
        assert result["status"] == "passed"
        if self.fault == "budget":
            policy = loads((self.root / "budget_policy.json").read_bytes())
            limit = policy["limits"]["verification_commands_per_code_attempt"]
            for ordinal in range(1, limit + 1):
                port.run_verification(spec_id=f"check-{ordinal}", input_digest=digest("input"),
                                      config_digest=digest("config"), timeout_seconds=1, effect=effect)
        if self.fault == "duplicate":
            with pytest.raises(ControlIntegrityError, match="twice"):
                port.run_verification(spec_id="check", input_digest=digest("input"), config_digest=digest("config"),
                                      timeout_seconds=1, effect=effect)
        return self.canonical.consume_external(identity, binding, port)

    def stop_consumption(self, coordinator, intent):
        return ConsumerStopObservation({"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
            "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}, {})


@pytest.mark.parametrize("fault", [None, "duplicate", "exception", "tamper"])
def test_verification_commit_effect_settlement_or_same_owner_failure(normal_external, fault):
    coordinator, plane, actor, locator, request, _ = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    adapter = VerificationConsumer(root, coordinator, fault=fault)
    plane.resume_target_adapter = plane.external_adapter = adapter
    result = plane.resume_run(request, actor=actor)
    assert result["operation_status"] == ("recovery_required" if fault == "tamper" else "committed"), result
    assert result["run_status"] == (None if fault == "tamper" else "failed" if fault == "exception" else "running"), result
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    reserved = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved" and r["payload"]["resource_kind"] == "verification_command"]
    assert len(reserved) == 1
    settlements = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled" and
                   r["payload"]["resource_operation_id"] == reserved[0]["payload"]["resource_operation_id"]]
    if fault != "tamper":
        assert len(settlements) == 1 and settlements[0]["payload"]["operation_id"] == result["operation_id"]
        assert (settlements[0]["payload"]["actual"] is None) == (fault == "exception")
    else:
        phase = next(r for r in coordinator.history(result["operation_id"]) if r["phase"] == "consumption_failure_ownership_reserved")
        failure = phase["evidence"]["frozen_failure_snapshot_and_disposition_contract"]["failure"]
        pending = failure["pending_resource_operation_ids_and_settlement_snapshots"]["pending"]
        assert pending == reserved
    marker = coordinator.root / "verification-effect.txt"
    assert marker.read_text() == "executed\n"
    assert plane.resume_run(request, actor=actor) == result
    assert marker.read_text() == "executed\n"


def test_verification_policy_capacity_rejects_before_an_extra_effect(normal_external):
    coordinator, plane, actor, locator, request, _ = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    plane.resume_target_adapter = plane.external_adapter = VerificationConsumer(root, coordinator, fault="budget")
    result = plane.resume_run(request, actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "failed", result
    limit = loads((root / "budget_policy.json").read_bytes())["limits"]["verification_commands_per_code_attempt"]
    assert (coordinator.root / "verification-effect.txt").read_text() == "executed\n" * limit
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    resources = [r for r in rows if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                 r["payload"]["resource_kind"] == "verification_command"]
    assert len(resources) == limit
    assert plane.resume_run(request, actor=actor) == result


def test_expired_verification_worker_cannot_settle_or_publish(normal_external):
    coordinator, plane, actor, locator, request, _ = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    plane.resume_target_adapter = plane.external_adapter = VerificationConsumer(root, coordinator, fault="expiry")
    with pytest.raises(ControlIntegrityError):
        plane.resume_run(request, actor=actor)
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert rows[-1]["event"] == "resource_reserved"
    result = plane.resume_run(request, actor=actor)
    assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable" and result["run_status"] is None, result
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    reservation = next(r for r in rows if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                       r["payload"]["resource_kind"] == "verification_command")
    settled = [r for r in rows if r["record_type"] == "budget" and r["event"] == "resource_settled" and
               r["payload"]["resource_operation_id"] == reservation["payload"]["resource_operation_id"]]
    assert not settled
    assert (coordinator.root / "verification-effect.txt").read_text() == "executed\n"


def verification_client(pipe, output, request, crash_boundary, elapsed, effect_crash):
    coordinator = Coordinator(Path(output), clock=FakeClock(100 + elapsed, elapsed,
        epoch_id="fake_clock_epoch_2" if elapsed else "fake_clock_epoch_1"))
    locator = request["run_locator"]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    adapter = VerificationConsumer(root, coordinator, fault="crash" if effect_crash else None)
    plane = ControlPlane(coordinator, worker_id="verification-worker", lease_seconds=30,
                         resume_target_adapter=adapter, external_adapter=adapter)
    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(94)
    coordinator.observer = observer
    try:
        result = plane.resume_run(ResumeRunRequest(**request), actor=ActorContext("operator", "human", ("control.internal", "resume")))
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


@pytest.mark.parametrize("boundary,effect_crash,ran", [
    (("control.resume_run.continue_execution.invocation_authorized", "after"), False, True),
    (("invocation.verification_resource_reserved", "after"), False, False),
    (("invocation.verification_ledger.file_sync", "after"), False, False),
    (None, True, True),
    (("invocation.verification_resource_settled", "after"), False, True),
    (("invocation.completion_intent", "after"), False, True),
])
def test_verification_crash_materializes_owned_suffix_without_redispatch(normal_external, boundary, effect_crash, ran):
    coordinator, _, _, locator, request, _ = normal_external
    context = multiprocessing.get_context("spawn")
    results = []
    for elapsed in (0, 40):
        parent, child = context.Pipe()
        process = context.Process(target=verification_client, args=(child, str(coordinator.root), asdict(request),
            boundary if not elapsed else None, elapsed, effect_crash if not elapsed else False))
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            assert process.exitcode == (0 if elapsed else 94)
            if elapsed:
                assert parent.poll(2)
                results.append(parent.recv())
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
    result = results[0]
    uncertain_effect = boundary in (("invocation.verification_resource_reserved", "after"),
                                    ("invocation.verification_ledger.file_sync", "after")) or effect_crash
    assert result["operation_status"] == ("recovery_required" if uncertain_effect else "committed"), result
    materialized = boundary in (("invocation.completion_intent", "after"),
                                ("control.resume_run.continue_execution.invocation_authorized", "after"))
    assert result["run_status"] == (None if uncertain_effect else "running" if materialized else "failed"), result
    if uncertain_effect:
        assert result["terminal_closure"] == "unavailable", result
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    reservations = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved" and r["payload"]["resource_kind"] == "verification_command"]
    assert len(reservations) == 1
    settlements = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled" and
                   r["payload"]["resource_operation_id"] == reservations[0]["payload"]["resource_operation_id"]]
    assert len(settlements) == (0 if uncertain_effect else 1)
    if settlements:
        assert settlements[0]["payload"]["operation_id"] == result["operation_id"]
    marker = coordinator.root / "verification-effect.txt"
    assert marker.exists() == ran
    if ran:
        assert marker.read_text() == "executed\n"
