"""Synthetic B03 source records exercise real B02 publication and arbitration."""
from copy import deepcopy
from dataclasses import asdict
import multiprocessing

import pytest

from lqcd_agent.control.execution import parse_ledger, replay
from lqcd_agent.control.operations import AdvanceRunRequest, ExternalControl
from lqcd_agent.control.pause import CancelPauseRequest, PublishPauseRequest, ResolveExternalInterruptRequest
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.projections import bounded_projection
from lqcd_agent.control.records import build_record
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from test_advance_control import SyntheticDomainRoute
from test_pause_control import control
from helpers.process_client import external_cancel_client, external_interrupt_client, external_pause_client


def external_source(control):
    """Install a deterministic domain input, not a Backend implementation."""
    coordinator, plane, actor, locator = control
    plane.route_adapter = SyntheticDomainRoute("code_agent")
    advanced = plane.advance_run(AdvanceRunRequest(locator, "attempt_000001", "advance-code"), actor=actor)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    index = loads((root / "artifact_index.json").read_bytes())
    policy = next(r["payload"]["policy"] for r in records if r["record_type"] == "budget" and r["event"] == "policy_initialized")
    budget_index = max(r["budget_event_index"] for r in records if r["record_type"] == "budget") + 1
    vector = {"llm_calls": 1, "tool_calls": 1, "verification_commands": 0, "active_seconds": 10}
    limits = {"llm_calls": 2, "tool_calls": 4, "verification_commands": 2, "active_seconds": 30}
    payload = {"resource_operation_id": "resource_code", "resource_kind": "code_backend_operation", "attempt_id": "attempt_000002",
               "ordinal": 1, "maximum_charge": vector, "applicable_limits": limits, "remaining_before": limits, "timeout_seconds": 10,
               "input_digest": digest("input"), "task_digest": digest("task"), "config_digest": digest("config"),
               "producer_operation_id": "producer_code", "workspace_id": "workspace_code", "task_id": "task_code",
               "code_task_context_digest": digest("context"), "coding_backend_kind": "synthetic_domain_input",
               "backend_runtime_fingerprint": digest("runtime"), "workspace_manifest_digest": digest("workspace")}
    reservation = build_record("budget", "resource_reserved", **locator, event_index=len(records) + 1,
                               previous_execution_head=digest(records[-1]), artifact_head=index["artifact_head"], artifact_event_index=index["revision"],
                               timestamp=coordinator._time(), budget_event_id=f"budget_event_{budget_index:06d}", budget_event_index=budget_index,
                               policy_version="0.1", policy_digest=policy["policy_digest"], payload=payload).value
    records.append(reservation)
    index["execution_head"] = digest(reservation)
    state = bounded_projection(replay(records), artifact_index=index, artifact_head=index["artifact_head"], artifact_event_index=index["revision"]).value
    value = {"producer_operation_id": "producer_code", "run_locator": locator, "cycle_id": "cycle_0001", "attempt_id": "attempt_000002",
             "parent_control_operation_id": advanced["operation_id"], "operation_phase": "workspace_materialized", "operation_status": "reserved",
             "phase_revision": 6, "lease_epoch": 1, "worker_owner_id": "domain_worker", "worker_lease_expires_at": 300,
             "resolution_owner": None, "pause_id": None, "pause_binding_digest": None, "workspace_id": "workspace_code",
             "reservation_id": payload["resource_operation_id"], "reservation_digest": digest(reservation),
             "task_digest": payload["task_digest"], "workspace_manifest_digest": payload["workspace_manifest_digest"],
             "operation_contract_digest": digest("synthetic_domain_core")}
    with coordinator.transaction() as db:
        control_row = loads(db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()[0])
        control_row.update(checkpoint_anchor_kind="external_prestart", external_owner=value["producer_operation_id"],
                           projection={**state, "checkpoint_head": control_row["manifest"]["checkpoint_head"]})
        db.execute("INSERT INTO external_operations VALUES (?,?,?)", (value["producer_operation_id"], value["phase_revision"], canonical_bytes(value)))
        db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes(control_row), digest(locator)))
        (root / "execution_history.jsonl").write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in records))
        (root / "artifact_index.json").write_bytes(canonical_bytes(index))
    return value


def external_pause_request(locator):
    return PublishPauseRequest(locator, "external_result", "attempt_000002", "attempt_000002",
                               {"kind": "external_result", "producer_operation_id": "producer_code"},
                               {"actor_type": "human", "scopes": ["resume"]}, "publish-external")


def test_external_pause_binds_only_after_real_prepared_publication(control):
    coordinator, plane, actor, locator = control
    source = external_source(control)
    observed = []

    def observer(name, side, value):
        if name == "external.pause_binding":
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
            observed.append((side, records[-1]["event"], records[-1]["status"]))

    coordinator.observer = observer
    result = plane.publish_pause(external_pause_request(locator), actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "paused"
    assert observed == [("before", "pause_prepared", "prepared"), ("after", "pause_prepared", "prepared")]
    external = ExternalControl(coordinator).read(coordinator.connection, source["producer_operation_id"])
    assert external["operation_phase"] == "pause_bound" and external["phase_revision"] == source["phase_revision"] + 1
    assert external["pause_id"] == result["result"]["pause_id"]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert not any(row["record_type"] == "attempt" and row["attempt_id"] == "attempt_000002" and row["event"] == "started" for row in records)
    assert plane.publish_pause(external_pause_request(locator), actor=actor) == result


@pytest.mark.parametrize("mutation", ["reservation", "core", "epoch", "target", "resolution"])
def test_external_publication_rejects_invalid_dependency_without_pause(control, mutation):
    coordinator, plane, actor, locator = control
    value = deepcopy(external_source(control))
    if mutation == "reservation":
        value["reservation_digest"] = digest("wrong")
    elif mutation == "core":
        value["operation_contract_digest"] = None
    elif mutation == "epoch":
        value["worker_lease_expires_at"] = 0
    elif mutation == "target":
        value["attempt_id"] = "attempt_000001"
    else:
        value["resolution_owner"] = "cancel"
    with coordinator.transaction() as db:
        db.execute("UPDATE external_operations SET value=?", (canonical_bytes(value),))
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    before = (root / "execution_history.jsonl").read_bytes()
    with pytest.raises(ControlIntegrityError):
        plane.publish_pause(external_pause_request(locator), actor=actor)
    assert (root / "execution_history.jsonl").read_bytes() == before
    assert coordinator.connection.execute("SELECT COUNT(*) FROM pause_ownership").fetchone()[0] == 0


EXTERNAL_CANCEL_PHASES = [(True, phase) for phase in ("cancel_arbitrated", "external_terminal_closure_verified", "pause_cancelled_recorded",
                         "target_disposition_committed", "resource_disposition_committed", "terminal_eligibility_verified",
                         "terminal_lifecycle_recorded", "terminal_checkpoint_committed", "result_committed")]
EXTERNAL_CANCEL_PHASES += [(False, phase) for phase in ("cancel_arbitrated", "external_unavailable_verified", "unavailable_resource_disposition_committed",
                          "pause_quarantined_recorded", "terminal_closure_unavailable_recorded")]


@pytest.mark.parametrize("safe,phase", EXTERNAL_CANCEL_PHASES)
@pytest.mark.parametrize("side", ["before", "after"])
def test_external_cancel_fresh_process_restart(control, safe, phase, side):
    coordinator, plane, actor, locator = control
    external_source(control)
    plane.publish_pause(external_pause_request(locator), actor=actor)
    context = multiprocessing.get_context("spawn")

    def run(boundary, elapsed):
        parent, child = context.Pipe()
        process = context.Process(target=external_cancel_client, args=(child, str(coordinator.root), locator, safe, boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary:
                assert process.exitcode == 90
                return None
            assert process.exitcode == 0 and parent.poll(2)
            return parent.recv()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()

    run(("control.cancel_pause.not_applicable." + phase, side), 0)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    prefix = (root / "execution_history.jsonl").read_bytes()
    result = run(None, 40)
    assert result["operation_status"] == ("committed" if safe else "recovery_required")
    assert result["terminal_closure"] == ("committed" if safe else "unavailable")
    assert (root / "execution_history.jsonl").read_bytes().startswith(prefix)
    assert coordinator.get(result["operation_id"])["lease_epoch"] == 2
    assert coordinator.connection.execute("SELECT COUNT(*) FROM run_terminal_closure").fetchone()[0] == 1


class SyntheticExternalStop:
    """Persist deterministic domain evidence; never starts a Backend or process."""

    def __init__(self, *, safe=True, violation=False):
        self.safe, self.violation, self.calls = safe, violation, 0

    def stop(self, coordinator, external_id, owner):
        self.calls += 1
        with coordinator.transaction() as db:
            value = ExternalControl(coordinator).read(db, external_id)
            assert value["resolution_owner_operation_id"] == owner
            assert value["resolution_owner"] in ("cancel", "interrupt")
            assert value["operation_phase"] == ("cancel_intent_committed" if value["resolution_owner"] == "cancel" else "interrupt_stop_intent_committed")
            self.publish(coordinator, db, value)

    def publish(self, coordinator, db, value):
        locator = value["run_locator"]
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        proof = {key: value[key] for key in ("producer_operation_id", "run_locator", "attempt_id", "cycle_id", "lease_epoch", "resolution_owner")}
        kind = "safe_stop" if self.safe else "unavailable"
        proof.update(stop_proof={"termination_or_not_dispatched": {"tag": "not_dispatched"}, "write_lease_revocation": True,
                                "verify_empty": self.safe, "bounded_drain": True, "post_stop_stability": True},
                     proof_kind=kind, classification_timing=PROTOCOL["state_machines"]["external_operation"]["final_proof_classification"]["resolution_timing"][value["resolution_owner"]],
                     interrupt_disposition=value.get("interrupt_disposition", "not_applicable"), proven_policy_violation=self.violation,
                     resource_actual={"llm_calls": 0, "tool_calls": 0, "verification_commands": 0, "active_seconds": 0})
        if value["resolution_owner"] == "normal":
            proof["stop_proof"]["termination_or_not_dispatched"] = "confirmed"
            for name in ("dispatch_receipt", "result"):
                content = {"run_locator": locator, "producer_operation_id": value["producer_operation_id"], "attempt_id": value["attempt_id"], "kind": name}
                reference = "synthetic_" + name + ".json"
                (root / reference).write_bytes(canonical_bytes(content))
                value[name + "_reference"], value[name + "_digest"] = reference, digest(content)
                proof[name + "_digest"] = digest(content)
        if not self.safe:
            proof.update(quarantine_reference="synthetic_quarantine", missing_proof_dimensions=["verify_empty"])
        reference = "synthetic_external_final.json"
        (root / reference).write_bytes(canonical_bytes(proof))
        value.update(operation_phase="external_final_evidence_committed", operation_status={"normal": "completed", "cancel": "cancelled", "interrupt": "interrupted"}[value["resolution_owner"]] if self.safe else "recovery_required",
                     phase_revision=value["phase_revision"] + 2, terminal_evidence_reference=reference, terminal_evidence_digest=digest(proof), proof_kind=kind)
        db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=?", (value["phase_revision"], canonical_bytes(value), value["producer_operation_id"]))


@pytest.mark.parametrize("case", ["cancel_safe", "cancel_violation", "cancel_unavailable", "normal_safe", "normal_violation"])
def test_external_cancel_resolves_from_verified_stop_not_backend_status(control, case):
    coordinator, plane, actor, locator = control
    external_source(control)
    published = plane.publish_pause(external_pause_request(locator), actor=actor)
    stop = SyntheticExternalStop(safe=case != "cancel_unavailable", violation=case.endswith("violation"))
    plane.external_adapter = stop
    if case.startswith("normal"):
        with coordinator.transaction() as db:
            value = ExternalControl(coordinator).read(db, "producer_code")
            value["resolution_owner"] = "normal"
            stop.publish(coordinator, db, value)
    request = CancelPauseRequest(locator, published["result"]["pause_id"], "cancel", "operator_cancel")
    result = plane.cancel_pause(request, actor=actor)
    assert stop.calls == int(case.startswith("cancel"))
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    if case == "cancel_unavailable":
        assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable"
        assert result["run_status"] is None
        assert records[-1]["status"] == "quarantined"
        assert [r["to_status"] for r in records if r["record_type"] == "run_lifecycle"] == ["running", "paused"]
    else:
        assert result["operation_status"] == "committed" and result["terminal_closure"] == "committed"
        assert result["run_status"] == ("failed" if case.endswith("violation") else "halted")
        assert [r["status"] for r in records if r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002"] == ["scheduled", "abandoned"]
    terminal = loads(coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0])
    pause = loads(coordinator.connection.execute("SELECT value FROM pause_ownership").fetchone()[0])
    assert pause["owner"] == terminal["terminal_closure_owner_operation_id"] == result["operation_id"]
    before = (root / "execution_history.jsonl").read_bytes()
    assert plane.cancel_pause(request, actor=actor) == result
    assert (root / "execution_history.jsonl").read_bytes() == before


@pytest.mark.parametrize("reason", ["terminal_operator_stop", "proven_integrity_trigger"])
@pytest.mark.parametrize("safe,violation", [(True, False), (True, True), (False, False)])
@pytest.mark.parametrize("opened", [True, False])
def test_external_interrupt_owns_typed_terminal_tail(control, reason, safe, violation, opened):
    coordinator, plane, actor, locator = control
    external_source(control)
    if opened:
        plane.publish_pause(external_pause_request(locator), actor=actor)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    trigger = {"run_locator": locator, "producer_operation_id": "producer_code", "reason": reason}
    (root / "synthetic_interrupt.json").write_bytes(canonical_bytes(trigger))
    stop = SyntheticExternalStop(safe=safe, violation=violation)
    plane.external_adapter = stop
    request = ResolveExternalInterruptRequest(locator, "producer_code", reason, "synthetic_interrupt.json", digest(trigger))
    result = plane.resolve_external_interrupt(request, actor=actor)
    assert stop.calls == 1
    assert result["operation_status"] == ("committed" if safe else "recovery_required")
    assert result["terminal_closure"] == ("committed" if safe else "unavailable")
    assert result["run_status"] == (None if not safe else "failed" if violation or reason == "proven_integrity_trigger" else "halted")
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    pauses = [r for r in records if r["record_type"] == "pause"]
    assert bool(pauses) == opened
    if opened:
        assert pauses[-1]["status"] == ("interrupted" if safe else "quarantined")
    assert plane.resolve_external_interrupt(request, actor=actor) == result and stop.calls == 1


@pytest.mark.parametrize("mutation", ["missing_final", "changed_final", "false_safe_stop"])
def test_external_cancel_failure_never_leaves_terminal_operation_with_pending_closure(control, mutation):
    coordinator, plane, actor, locator = control
    external_source(control)
    plane.publish_pause(external_pause_request(locator), actor=actor)
    root = coordinator.root / locator["case_id"] / locator["run_id"]

    class BrokenStop(SyntheticExternalStop):
        def stop(self, coordinator, external_id, owner):
            if mutation == "missing_final":
                raise OSError("Synthetic missing stop authority")
            super().stop(coordinator, external_id, owner)
            path = root / "synthetic_external_final.json"
            if mutation == "changed_final":
                path.write_bytes(b"{}")
            else:
                proof = loads(path.read_bytes())
                proof["stop_proof"]["verify_empty"] = False
                path.write_bytes(canonical_bytes(proof))
                with coordinator.transaction() as db:
                    value = ExternalControl(coordinator).read(db, external_id)
                    value["terminal_evidence_digest"] = digest(proof)
                    db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?", (canonical_bytes(value), external_id))

    plane.external_adapter = BrokenStop()
    request = CancelPauseRequest(locator, "pause_000001", "cancel", "operator_cancel")
    result = plane.cancel_pause(request, actor=actor)
    assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable" and result["run_status"] is None
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert records[-1]["record_type"] == "pause" and records[-1]["status"] == "opened"
    assert plane.cancel_pause(request, actor=actor) == result


INTERRUPT_PHASES = [(True, name) for name in ("interrupt_and_terminal_ownership_reserved", "external_final_evidence_verified", "resource_disposition_committed",
                    "resolved_interrupt_outcome_committed", "interrupt_terminal_ownership_reserved", "interrupt_safe_pause_disposition_committed",
                    "terminal_eligibility_verified", "terminal_lifecycle_recorded", "terminal_checkpoint_committed", "result_committed")]
INTERRUPT_PHASES += [(False, name) for name in ("external_final_evidence_verified", "resource_disposition_committed", "resolved_interrupt_outcome_committed",
                     "interrupt_terminal_ownership_reserved", "interrupt_unavailable_pause_disposition_committed", "terminal_closure_unavailable_recorded")]


@pytest.mark.parametrize("safe,phase", INTERRUPT_PHASES)
@pytest.mark.parametrize("side", ["before", "after"])
def test_external_interrupt_fresh_process_restart(control, safe, phase, side):
    coordinator, plane, actor, locator = control
    external_source(control)
    plane.publish_pause(external_pause_request(locator), actor=actor)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    trigger = {"run_locator": locator, "producer_operation_id": "producer_code", "reason": "terminal_operator_stop"}
    (root / "synthetic_interrupt.json").write_bytes(canonical_bytes(trigger))
    request = ResolveExternalInterruptRequest(locator, "producer_code", "terminal_operator_stop", "synthetic_interrupt.json", digest(trigger))
    context = multiprocessing.get_context("spawn")

    def run(boundary, elapsed):
        parent, child = context.Pipe()
        process = context.Process(target=external_interrupt_client, args=(child, str(coordinator.root), asdict(request), safe, boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary:
                assert process.exitcode == 91
                return None
            assert process.exitcode == 0 and parent.poll(2)
            return parent.recv()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()

    run(("control.resolve_external_interrupt.controlled_halt." + phase, side), 0)
    prefix = (root / "execution_history.jsonl").read_bytes()
    result = run(None, 40)
    assert result["operation_status"] == ("committed" if safe else "recovery_required")
    assert (root / "execution_history.jsonl").read_bytes().startswith(prefix)
    assert coordinator.get(result["operation_id"])["lease_epoch"] == 2
    assert coordinator.connection.execute("SELECT COUNT(*) FROM run_terminal_closure").fetchone()[0] == 1


@pytest.mark.parametrize("publication_phase", ["pause_prepared_recorded", "pause_dependencies_bound", "prepared_checkpoint_committed", "paused_lifecycle_recorded"])
@pytest.mark.parametrize("safe", [True, False])
@pytest.mark.parametrize("fresh_process", [False, True])
def test_interrupt_prepared_pause_revokes_publication_without_opening(control, publication_phase, safe, fresh_process):
    coordinator, plane, actor, locator = control
    external_source(control)

    class PublicationStopped(BaseException):
        pass

    def observer(name, side, value):
        if name == "control.publish_pause.not_applicable." + publication_phase and side == "after":
            raise PublicationStopped()

    publication = external_pause_request(locator)
    if fresh_process:
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=external_pause_client, args=(child, str(coordinator.root), locator, publication_phase))
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive() and process.exitcode == 92
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
    else:
        coordinator.observer = observer
        with pytest.raises(PublicationStopped):
            plane.publish_pause(publication, actor=actor)
        coordinator.observer = None
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    prefix = (root / "execution_history.jsonl").read_bytes()
    trigger = {"run_locator": locator, "producer_operation_id": "producer_code", "reason": "terminal_operator_stop"}
    (root / "synthetic_interrupt.json").write_bytes(canonical_bytes(trigger))
    plane.external_adapter = SyntheticExternalStop(safe=safe)
    request = ResolveExternalInterruptRequest(locator, "producer_code", trigger["reason"], "synthetic_interrupt.json", digest(trigger))
    coordinator.clock.advance(40)
    result = plane.resolve_external_interrupt(request, actor=actor)
    assert result["terminal_closure"] == ("committed" if safe else "unavailable"), result
    assert result["run_status"] == ("halted" if safe else None)
    final = (root / "execution_history.jsonl").read_bytes()
    assert final.startswith(prefix)
    rows = parse_ledger(final).values
    assert [r["status"] for r in rows if r["record_type"] == "pause"] == ["prepared", "aborted" if safe else "quarantined"]
    rejected = plane.publish_pause(publication, actor=actor)
    assert rejected["operation_status"] == "failed" and rejected["operation_id"] != result["operation_id"]
    assert plane.publish_pause(publication, actor=actor) == rejected
    closure = loads(coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0])
    assert closure["terminal_closure_owner_operation_id"] == result["operation_id"]
    assert (root / "execution_history.jsonl").read_bytes() == final
    assert plane.resolve_external_interrupt(request, actor=actor) == result


@pytest.mark.parametrize("winner_kind", ["cancel", "interrupt"])
@pytest.mark.parametrize("safe", [True, False])
def test_cancel_observes_existing_winner_without_consuming_final_or_acquiring_owners(control, winner_kind, safe):
    coordinator, plane, actor, locator = control
    external_source(control)
    published = plane.publish_pause(external_pause_request(locator), actor=actor)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    plane.external_adapter = SyntheticExternalStop(safe=safe)
    if winner_kind == "cancel":
        winner = plane.cancel_pause(CancelPauseRequest(locator, published["result"]["pause_id"], "winner", "operator_cancel"), actor=actor)
    else:
        trigger = {"run_locator": locator, "producer_operation_id": "producer_code", "reason": "terminal_operator_stop"}
        (root / "synthetic_interrupt.json").write_bytes(canonical_bytes(trigger))
        winner = plane.resolve_external_interrupt(ResolveExternalInterruptRequest(locator, "producer_code", trigger["reason"],
                                                  "synthetic_interrupt.json", digest(trigger)), actor=actor)
    pause_before = coordinator.connection.execute("SELECT value FROM pause_ownership").fetchone()[0]
    closure_before = coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0]
    external_before = coordinator.connection.execute("SELECT value FROM external_operations").fetchone()[0]
    (root / "synthetic_external_final.json").unlink()
    ledger_before = (root / "execution_history.jsonl").read_bytes()
    request = CancelPauseRequest(locator, published["result"]["pause_id"], "observer", "operator_cancel")
    plane.external_adapter = None
    observed = plane.cancel_pause(request, actor=actor)
    assert observed["operation_status"] == "committed" and observed["result"]["winner_operation_id"] == winner["operation_id"], observed
    assert [r["phase"] for r in coordinator.history(observed["operation_id"])] == ["operation_reserved", "cancel_arbitrated", "resolution_winner_observed", "result_committed"]
    assert coordinator.connection.execute("SELECT value FROM pause_ownership").fetchone()[0] == pause_before
    assert coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0] == closure_before
    assert coordinator.connection.execute("SELECT value FROM external_operations").fetchone()[0] == external_before
    assert (root / "execution_history.jsonl").read_bytes() == ledger_before
    assert plane.cancel_pause(request, actor=actor) == observed
