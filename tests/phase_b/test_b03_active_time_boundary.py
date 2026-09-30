"""Verify the durable B00C09 handoff without claiming B03 acceptance credit."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import multiprocessing
import os

import pytest

from lqcd_agent.code_agent.prestart import CodePrestart
from lqcd_agent.control.budget import validate_budget_payload
from lqcd_agent.control.clock import FakeClock, measure
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger, replay
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.pause import PublishPauseRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from helpers.code_workspace import immutable_base_repository
from test_b03_task_trace_boundary import task_trace_witness
from test_execution_0_4_foundation import bootstrap, attempt, reserve, DIGEST
from test_external_consumption_control import ExternalDomainConsumer
from test_external_control import SyntheticExternalStop
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.pause import ResolveExternalInterruptRequest
from lqcd_agent.control.pause import ConsumerStopObservation
from lqcd_agent.control.strict_json import canonical_bytes
from test_timeout_consumption_control import DomainTimeout


def crash_during_setup_publication(root, producer, task, boundary):
    coordinator = Coordinator(Path(root).parent.parent, clock=FakeClock(100, 0))

    def observer(name, side, value):
        if (name, side) == boundary:
            os._exit(95)
    coordinator.observer = observer
    CodePrestart(coordinator, producer, "host", 1).commit_task(task)
    raise AssertionError("Setup publication did not reach its fault boundary")


def fresh_budget_reader(pipe, output, locator):
    coordinator = Coordinator(Path(output), clock=FakeClock(200, 100, epoch_id="fresh_reader_epoch"))
    try:
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes())
        control = loads(coordinator.connection.execute("SELECT value FROM run_controls WHERE run_key=?",
            (digest(locator),)).fetchone()[0])
        state = validate_run_root(root, manifest=control["manifest"], projection=control["projection"]).value
        pipe.send({"replay": rows.projection.value["budget"]["dimensions"],
                   "stable": state["budget"]["dimensions"]})
    finally:
        coordinator.close()
        pipe.close()


def crash_timeout_after_start_intent(output, request):
    coordinator = Coordinator(Path(output), clock=FakeClock(103, 3))

    def observer(name, side, value):
        if (name, side) == ("invocation.started_intent", "after"):
            os._exit(96)
    coordinator.observer = observer
    plane = ControlPlane(coordinator, worker_id="host", external_adapter=DomainTimeout(coordinator))
    plane.resolve_external_interrupt(ResolveExternalInterruptRequest(**request),
        actor=ActorContext("operator", "human", ("control.internal",)))
    raise AssertionError("Timeout did not reach its frozen start intent")


def setup_clock_witness(*, pause_epoch=None):
    repository, base = immutable_base_repository()
    witness = task_trace_witness(base)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    clock = FakeClock(100, 0)
    coordinator = Coordinator(root.parent.parent, clock=clock)
    try:
        service = CodePrestart(coordinator, witness["task"]["producer_operation_id"], "host", 1)
        start = clock.now()
        service.commit_task(witness["task"])
        clock.advance(3)
        service.commit_manifest(witness["manifest"])
        expected = measure("host_setup", start, clock.now())
        before = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        before_dimensions = replay(before).projection.value["budget"]["dimensions"]
        reservation = service.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
            "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10, config_digest=digest("config"))
        service.commit_core()
        service.materialize_workspace(repository)
        if pause_epoch is not None:
            coordinator.clock = FakeClock(103, 3, epoch_id=pause_epoch)
        locator = {key: witness["task"][key] for key in ("case_id", "run_id")}
        target = witness["task"]["attempt_id"]
        paused = ControlPlane(coordinator, worker_id="host").publish_pause(
            PublishPauseRequest(locator, "external_result", target, target,
                {"kind": "external_result", "producer_operation_id": service.producer},
                {"actor_type": "human", "scopes": ["resume"]}, "publish-clock-witness"),
            actor=ActorContext("operator", "human", ("control.internal",)))
        assert paused["operation_status"] == "committed" and paused["run_status"] == "paused"
        after = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        return {"root": str(root), "expected_setup_charge": asdict(expected),
                "before_dimensions": before_dimensions,
                "after_dimensions": replay(after).projection.value["budget"]["dimensions"],
                "reservation": reservation, "records": after, "pause": paused}
    finally:
        coordinator.close()


def test_host_setup_clock_is_replayed_as_run_only_before_public_pause():
    value = setup_clock_witness()
    assert value["expected_setup_charge"] == {"stage": "host_setup", "run_seconds": 3, "attempt_seconds": 0}
    assert value["before_dimensions"]["active_seconds_per_run"]["used"] == 10
    assert value["before_dimensions"]["active_seconds_per_attempt"]["used"] == 0
    assert value["after_dimensions"]["active_seconds_per_run"]["used"] == 13
    assert value["after_dimensions"]["active_seconds_per_attempt"]["used"] == 10
    assert [row["event"] for row in value["records"][-3:]] == [
        "transitioned", "active_interval_settled", "pause_opened"]
    assert not any(record["record_type"] == "attempt" and record["event"] == "started" and
                   record["attempt_id"] == value["reservation"]["payload"]["attempt_id"] for record in value["records"])


def test_changed_host_epoch_conservatively_keeps_setup_maximum():
    value = setup_clock_witness(pause_epoch="fake_clock_epoch_2")
    settlements = [row for row in value["records"] if row["record_type"] == "budget" and
                   row["event"] == "active_interval_settled"]
    assert len(settlements) == 1 and settlements[0]["payload"]["disposition"] == "conservative_maximum"
    assert value["after_dimensions"]["active_seconds_per_run"]["used"] == 20
    assert value["after_dimensions"]["active_seconds_per_attempt"]["used"] == 10


def test_canonical_producer_cannot_downgrade_to_legacy_without_its_marker():
    witness = setup_clock_witness()
    root = Path(witness["root"])
    producer = witness["reservation"]["payload"]["producer_operation_id"]
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(103, 3))
    try:
        with coordinator.transaction() as db:
            value = ExternalControl(coordinator).read(db, producer)
            del value["prestart"]["active_time"]
            db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?",
                       (canonical_bytes(value), producer))
        with pytest.raises(ControlIntegrityError, match="lost its frozen active-time intent"):
            ExternalControl(coordinator).read(coordinator.connection, producer)
    finally:
        coordinator.close()


@pytest.mark.parametrize("verification_count", [0, 2])
def test_canonical_attempt_charges_its_whole_active_interval(verification_count):
    witness = setup_clock_witness()
    root = Path(witness["root"])
    producer = witness["reservation"]["payload"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(103, 3))
    try:
        coordinator.clock.advance(6)
        with coordinator.transaction() as db:
            external = ExternalControl(coordinator).read(db, producer)
            external["resolution_owner"] = "normal"
            SyntheticExternalStop().publish(coordinator, db, external)
            final = ExternalControl(coordinator).read(db, producer)
            path = root / final["terminal_evidence_reference"]
            proof = loads(path.read_bytes())
            proof["resource_actual"]["active_seconds"] = 6
            path.write_bytes(canonical_bytes(proof))
            final["terminal_evidence_digest"] = digest(proof)
            db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?",
                       (canonical_bytes(final), producer))
        external = ExternalControl(coordinator).read(coordinator.connection, producer)
        payload = {"producer_operation_id": producer, "external_final_digest": external["terminal_evidence_digest"]}
        request = ResumeRunRequest(locator, witness["pause"]["result"]["pause_id"], "canonical-no-call",
                                   "external_result", payload, digest(payload))

        class ElapsedConsumer(ExternalDomainConsumer):
            def consume_external(self, identity, binding, port):
                for ordinal in range(verification_count):
                    def effect():
                        coordinator.clock.advance(1)
                        return {"status": "passed"}
                    port.run_verification(spec_id=f"check-{ordinal}", input_digest=digest("input"),
                                          config_digest=digest("config"), timeout_seconds=1, effect=effect)
                elapsed = 6 if verification_count == 0 else 5
                coordinator.clock.advance(elapsed - verification_count)
                raise ControlIntegrityError("Controlled post-verification failure")

            def stop_consumption(self, coordinator, intent):
                return ConsumerStopObservation({"termination_or_not_dispatched": "confirmed",
                    "write_lease_revocation": True, "verify_empty": True, "bounded_drain": True,
                    "post_stop_stability": True}, {})

        adapter = ElapsedConsumer(root)
        plane = ControlPlane(coordinator, worker_id="host", resume_target_adapter=adapter, external_adapter=adapter)
        result = plane.resume_run(request, actor=ActorContext("operator", "human", ("control.internal", "resume")))
        assert result["operation_status"] == "committed" and result["run_status"] == "failed", result
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        intervals = [row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_settled"]
        elapsed = 6 if verification_count == 0 else 5
        assert len(intervals) == 2 and intervals[-1]["payload"]["actual_seconds"] == elapsed
        dimensions = replay(rows).projection.value["budget"]["dimensions"]
        assert dimensions["active_seconds_per_run"]["used"] == 3 + 6 + elapsed
        assert dimensions["active_seconds_per_attempt"]["used"] == 6 + elapsed
        assert dimensions["verification_commands_per_code_attempt"]["used"] == verification_count
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        reader = context.Process(target=fresh_budget_reader, args=(child, str(coordinator.root), locator))
        reader.start()
        child.close()
        try:
            assert parent.poll(20)
            observed = parent.recv()
            reader.join(20)
            assert reader.exitcode == 0 and observed["replay"] == observed["stable"] == dimensions
        finally:
            if reader.is_alive():
                reader.kill()
                reader.join()
            parent.close()
    finally:
        coordinator.close()


def test_canonical_recoverable_timeout_settles_the_original_attempt_interval():
    witness = setup_clock_witness()
    root = Path(witness["root"])
    producer = witness["reservation"]["payload"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(103, 3))
    try:
        with coordinator.transaction() as db:
            external = ExternalControl(coordinator).read(db, producer)
            external.update(operation_phase="dispatch_authorized", operation_status="active",
                            phase_revision=external["phase_revision"] + 1)
            db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=?",
                       (external["phase_revision"], canonical_bytes(external), producer))
        trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
        (root / "timeout_trigger.json").write_bytes(canonical_bytes(trigger))
        request = ResolveExternalInterruptRequest(locator, producer, "operation_timeout", "timeout_trigger.json", digest(trigger))
        plane = ControlPlane(coordinator, worker_id="host", external_adapter=DomainTimeout(coordinator))

        def observer(name, side, value):
            if name.endswith("interrupted_code_attempt_started") and side == "after":
                coordinator.clock.advance(2)
        coordinator.observer = observer
        result = plane.resolve_external_interrupt(request, actor=ActorContext("operator", "human", ("control.internal",)))
        assert result["operation_status"] == "committed" and result["domain_status"] == "failed", result
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        intervals = [row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_settled"]
        assert len(intervals) == 2 and intervals[-1]["payload"]["actual_seconds"] == 2
        dimensions = replay(rows).projection.value["budget"]["dimensions"]
        assert dimensions["active_seconds_per_run"]["used"] == 5
        assert dimensions["active_seconds_per_attempt"]["used"] == 2
    finally:
        coordinator.close()


def test_canonical_timeout_restart_uses_frozen_attempt_and_cross_epoch_maximum():
    witness = setup_clock_witness()
    root = Path(witness["root"])
    producer = witness["reservation"]["payload"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(103, 3))
    try:
        with coordinator.transaction() as db:
            external = ExternalControl(coordinator).read(db, producer)
            external.update(operation_phase="dispatch_authorized", operation_status="active",
                            phase_revision=external["phase_revision"] + 1)
            db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=?",
                       (external["phase_revision"], canonical_bytes(external), producer))
        trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
        (root / "timeout_trigger.json").write_bytes(canonical_bytes(trigger))
    finally:
        coordinator.close()
    request = ResolveExternalInterruptRequest(locator, producer, "operation_timeout", "timeout_trigger.json", digest(trigger))
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=crash_timeout_after_start_intent, args=(str(root.parent.parent), asdict(request)))
    process.start()
    process.join(20)
    assert process.exitcode == 96
    restarted = Coordinator(root.parent.parent, clock=FakeClock(143, 43, epoch_id="fake_clock_epoch_2"))
    try:
        result = ControlPlane(restarted, worker_id="host", external_adapter=DomainTimeout(restarted)).resolve_external_interrupt(
            request, actor=ActorContext("operator", "human", ("control.internal",)))
        assert result["operation_status"] == "committed" and result["domain_status"] == "failed", result
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        intervals = [row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_settled"]
        assert len(intervals) == 2 and intervals[-1]["payload"]["disposition"] == "conservative_maximum"
        active = next(row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_reserved" and
                      row["payload"]["stage"] == "attempt_active")
        assert replay(rows).projection.value["budget"]["dimensions"]["active_seconds_per_attempt"]["used"] == active["payload"]["maximum_seconds"]
    finally:
        restarted.close()


@pytest.mark.parametrize("elapsed", [3, 10])
def test_canonical_pre_pause_interrupt_settles_setup_without_backend(elapsed):
    _, base = immutable_base_repository()
    witness = task_trace_witness(base)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    producer = witness["task"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(100, 0))
    try:
        CodePrestart(coordinator, producer, "host", 1).commit_task(witness["task"])
        coordinator.clock.advance(elapsed)
        trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "terminal_operator_stop"}
        (root / "interrupt_trigger.json").write_bytes(canonical_bytes(trigger))
        plane = ControlPlane(coordinator, worker_id="host", external_adapter=SyntheticExternalStop())
        request = ResolveExternalInterruptRequest(locator, producer, "terminal_operator_stop", "interrupt_trigger.json", digest(trigger))
        result = plane.resolve_external_interrupt(request, actor=ActorContext("operator", "human", ("control.internal",)))
        assert result["operation_status"] == "committed" and result["run_status"] == "halted", result
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        settlements = [row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_settled"]
        assert len(settlements) == 1 and settlements[0]["payload"]["actual_seconds"] == elapsed
        assert replay(rows).projection.value["budget"]["dimensions"]["active_seconds_per_run"]["used"] == elapsed
    finally:
        coordinator.close()


def test_interrupt_materializes_committed_stub_before_claiming_terminal_owner():
    _, base = immutable_base_repository()
    witness = task_trace_witness(base)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    producer = witness["task"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(100, 0))
    try:
        trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "terminal_operator_stop"}
        (root / "interrupt_trigger.json").write_bytes(canonical_bytes(trigger))
        plane = ControlPlane(coordinator, worker_id="host", external_adapter=SyntheticExternalStop())
        result = plane.resolve_external_interrupt(ResolveExternalInterruptRequest(
            locator, producer, "terminal_operator_stop", "interrupt_trigger.json", digest(trigger)),
            actor=ActorContext("operator", "human", ("control.internal",)))
        assert result["operation_status"] == "committed" and result["run_status"] == "halted", result
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        assert sum(row["record_type"] == "budget" and row["event"] == "active_interval_reserved" for row in rows) == 1
        assert sum(row["record_type"] == "budget" and row["event"] == "active_interval_settled" for row in rows) == 1
        assert not (root / "code_agent_control" / witness["task"]["attempt_id"] / "code_agent_task.json").exists()
    finally:
        coordinator.close()


def test_expired_unpublished_stub_materializes_then_terminalizes_unavailable():
    _, base = immutable_base_repository()
    witness = task_trace_witness(base)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    producer = witness["task"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(140, 40))
    try:
        trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "terminal_operator_stop"}
        (root / "interrupt_trigger.json").write_bytes(canonical_bytes(trigger))
        plane = ControlPlane(coordinator, worker_id="host", external_adapter=SyntheticExternalStop())
        with pytest.raises(ControlIntegrityError, match="Stale setup materialization owner"):
            CodePrestart(coordinator, producer, "host", 1).publish_setup()
        result = plane.resolve_external_interrupt(ResolveExternalInterruptRequest(
            locator, producer, "terminal_operator_stop", "interrupt_trigger.json", digest(trigger)),
            actor=ActorContext("operator", "human", ("control.internal",)))
        assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable"
        assert "observed=40" in result["error"]["message"]
        recovered = ExternalControl(coordinator).read(coordinator.connection, producer)
        assert recovered["lease_epoch"] == 2 and recovered["prestart"]["active_time"]["recovery_only"]
        assert coordinator.connection.execute("SELECT COUNT(*) FROM run_terminal_closure").fetchone()[0] == 1
        assert sum(row["event"] == "active_interval_reserved" for row in
                   parse_ledger((root / "execution_history.jsonl").read_bytes()).values) == 1
        assert not (root / "code_agent_control" / witness["task"]["attempt_id"] / "code_agent_task.json").exists()
        before = (root / "execution_history.jsonl").read_bytes()
        assert CodePrestart(coordinator, producer, "host", 1).publish_setup() == recovered["prestart"]["active_time"]["setup_record"]
        assert (root / "execution_history.jsonl").read_bytes() == before
    finally:
        coordinator.close()


def test_expired_stub_from_old_clock_epoch_settles_conservatively():
    _, base = immutable_base_repository()
    witness = task_trace_witness(base)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    producer = witness["task"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(140, 40, epoch_id="fake_clock_epoch_2"))
    try:
        trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "terminal_operator_stop"}
        (root / "interrupt_trigger.json").write_bytes(canonical_bytes(trigger))
        result = ControlPlane(coordinator, worker_id="host", external_adapter=SyntheticExternalStop()).resolve_external_interrupt(
            ResolveExternalInterruptRequest(locator, producer, "terminal_operator_stop", "interrupt_trigger.json", digest(trigger)),
            actor=ActorContext("operator", "human", ("control.internal",)))
        assert result["operation_status"] == "committed" and result["run_status"] == "halted", result
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        settlement = next(row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_settled")
        assert settlement["payload"]["disposition"] == "conservative_maximum"
        assert replay(rows).projection.value["budget"]["dimensions"]["active_seconds_per_run"]["used"] == 10
    finally:
        coordinator.close()


@pytest.mark.parametrize("boundary", [("external.setup_reservation.file_sync", "after"),
                                     ("external.active_time_reserved", "after")])
def test_frozen_setup_suffix_survives_process_exit_without_duplicate(boundary):
    _, base = immutable_base_repository()
    witness = task_trace_witness(base)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    producer = witness["task"]["producer_operation_id"]
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=crash_during_setup_publication,
                              args=(str(root), producer, witness["task"], boundary))
    process.start()
    process.join(20)
    assert process.exitcode == 95
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(100, 0))
    try:
        frozen = ExternalControl(coordinator).read(coordinator.connection, producer)["prestart"]["active_time"]
        assert frozen["setup_record_digest"] == digest(frozen["setup_record"])
        CodePrestart(coordinator, producer, "host", 1).commit_task(witness["task"])
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        setup = [row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_reserved"]
        assert setup == [frozen["setup_record"]]
        assert ExternalControl(coordinator).read(coordinator.connection, producer)["prestart"]["active_time"]["published"]
    finally:
        coordinator.close()


@pytest.mark.parametrize("phase", ["pause_prepared_recorded", "paused_lifecycle_recorded"])
def test_canonical_partial_pause_interrupt_settles_setup(phase):
    repository, base = immutable_base_repository()
    witness = task_trace_witness(base)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    producer = witness["task"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    target = witness["task"]["attempt_id"]
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(100, 0))
    try:
        service = CodePrestart(coordinator, producer, "host", 1)
        service.commit_task(witness["task"])
        coordinator.clock.advance(3)
        service.commit_manifest(witness["manifest"])
        service.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
            "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10, config_digest=digest("config"))
        service.commit_core()
        service.materialize_workspace(repository)
        plane = ControlPlane(coordinator, worker_id="host")

        class PausedBeforeOpen(BaseException):
            pass

        def observer(name, side, value):
            if (name, side) == ("control.publish_pause.not_applicable." + phase, "after"):
                raise PausedBeforeOpen()
        coordinator.observer = observer
        with pytest.raises(PausedBeforeOpen):
            plane.publish_pause(PublishPauseRequest(locator, "external_result", target, target,
                {"kind": "external_result", "producer_operation_id": producer},
                {"actor_type": "human", "scopes": ["resume"]}, "partial-canonical-pause"),
                actor=ActorContext("operator", "human", ("control.internal",)))
        coordinator.observer = None
        trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "terminal_operator_stop"}
        (root / "interrupt_trigger.json").write_bytes(canonical_bytes(trigger))
        plane.external_adapter = SyntheticExternalStop()
        result = plane.resolve_external_interrupt(ResolveExternalInterruptRequest(
            locator, producer, "terminal_operator_stop", "interrupt_trigger.json", digest(trigger)),
            actor=ActorContext("operator", "human", ("control.internal",)))
        assert result["operation_status"] == "committed" and result["run_status"] == "halted", result
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        settlements = [row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_settled"]
        assert len(settlements) == 1 and settlements[0]["payload"]["actual_seconds"] == 3
        assert [row["status"] for row in rows if row["record_type"] == "pause"] == ["prepared", "aborted"]
    finally:
        coordinator.close()


@pytest.mark.parametrize("failure_mode", ["plain", "nested", "cross_epoch", "epoch_during_effect"])
def test_canonical_consumption_failure_settles_open_attempt(failure_mode):
    witness = setup_clock_witness()
    root = Path(witness["root"])
    producer = witness["reservation"]["payload"]["producer_operation_id"]
    locator = {"case_id": root.parent.name, "run_id": root.name}
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(103, 3))
    try:
        with coordinator.transaction() as db:
            external = ExternalControl(coordinator).read(db, producer)
            external["resolution_owner"] = "normal"
            SyntheticExternalStop().publish(coordinator, db, external)
        external = ExternalControl(coordinator).read(coordinator.connection, producer)
        payload = {"producer_operation_id": producer, "external_final_digest": external["terminal_evidence_digest"]}
        request = ResumeRunRequest(locator, witness["pause"]["result"]["pause_id"], "canonical-failure",
                                   "external_result", payload, digest(payload))

        class FailingConsumer(ExternalDomainConsumer):
            def consume_external(self, identity, binding, port):
                if failure_mode in ("nested", "cross_epoch", "epoch_during_effect"):
                    if failure_mode == "cross_epoch":
                        coordinator.clock = FakeClock(103, 3, epoch_id="replacement_epoch")
                    def effect():
                        coordinator.clock.advance(2)
                        if failure_mode == "epoch_during_effect":
                            coordinator.clock = FakeClock(105, 5, epoch_id="replacement_epoch")
                            return {"status": "passed"}
                        raise ControlIntegrityError("Verifier effect failed")
                    return port.run_verification(spec_id="failing-check", input_digest=digest("input"),
                        config_digest=digest("config"), timeout_seconds=2, effect=effect)
                coordinator.clock.advance(2)
                raise ControlIntegrityError("Verifier failed")

            def stop_consumption(self, coordinator, intent):
                return ConsumerStopObservation({"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
                    "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}, {})

        adapter = FailingConsumer(root)
        plane = ControlPlane(coordinator, worker_id="host", resume_target_adapter=adapter, external_adapter=adapter)
        result = plane.resume_run(request, actor=ActorContext("operator", "human", ("control.internal", "resume")))
        assert result["operation_status"] == "committed" and result["run_status"] == "failed", result
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        intervals = [row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_settled"]
        assert len(intervals) == 2
        active = next(row for row in rows if row["record_type"] == "budget" and row["event"] == "active_interval_reserved" and
                      row["payload"]["stage"] == "attempt_active")
        if failure_mode != "plain":
            assert intervals[-1]["payload"]["disposition"] == "conservative_maximum"
            expected = 3 + active["payload"]["maximum_seconds"]
        else:
            assert intervals[-1]["payload"]["actual_seconds"] == 2
            expected = 5
        dimensions = replay(rows).projection.value["budget"]["dimensions"]
        assert dimensions["active_seconds_per_run"]["used"] == expected
        assert dimensions["verification_commands_per_code_attempt"]["used"] == int(failure_mode in ("nested", "epoch_during_effect"))
    finally:
        coordinator.close()


def test_legacy_manual_attempt_without_an_interval_keeps_old_accounting():
    ledger = bootstrap()
    started = attempt(ledger, "started")
    ledger.clock.advance(5)
    finished = attempt(ledger, "finished")
    elapsed = finished["created_at"]["monotonic_seconds"] - started["created_at"]["monotonic_seconds"]
    assert elapsed == 6
    dimensions = replay(ledger.records).projection.value["budget"]["dimensions"]
    assert dimensions["active_seconds_per_run"]["used"] == dimensions["active_seconds_per_attempt"]["used"] == 0


@pytest.mark.parametrize("proposal", ["new_kind", "run_only_vector", "new_event"])
def test_unversioned_budget_substitutes_are_rejected(proposal):
    ledger = bootstrap()
    attempt(ledger, "started")
    value = deepcopy(reserve(ledger)["payload"])
    event = "resource_reserved"
    if proposal == "new_kind":
        value["resource_kind"] = "host_setup"
    elif proposal == "run_only_vector":
        value["maximum_charge"]["run_active_seconds"] = 3
    else:
        event = "active_time_recorded"
    with pytest.raises(ControlIntegrityError):
        validate_budget_payload(event, value)


def test_legacy_resource_seconds_still_charge_both_dimensions():
    ledger = bootstrap()
    attempt(ledger, "started")
    reserve(ledger)
    ledger.budget("resource_settled", resource_operation_id="resource_1",
        actual={"llm_calls": 1, "tool_calls": 0, "verification_commands": 0, "active_seconds": 7},
        tokens={"state": "unknown", "value": None}, cost={"state": "unknown", "value": None},
        evidence_digest=DIGEST, operation_id="owner", lease_epoch=1, phase_revision=1)
    dimensions = replay(ledger.records).projection.value["budget"]["dimensions"]
    assert dimensions["active_seconds_per_run"]["used"] == dimensions["active_seconds_per_attempt"]["used"] == 7
