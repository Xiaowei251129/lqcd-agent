"""Independently observed B03 producer reservation crash cases."""
from harness.temporary import mkdtemp
from pathlib import Path
from dataclasses import asdict
from functools import partial
import multiprocessing
import os

import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case, process_hook_request, consume_process_hook, production_hook
from harness.strict_json import read
from harness.trace import compare, event
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.pause import ConsumerStopObservation
from lqcd_agent.control.strict_json import ControlIntegrityError, loads
from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.code_agent.external_operation import CodeWatchdog, ExternalProducer
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.prestart import CodePrestart
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.pause import ResolveExternalInterruptRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest
from lqcd_agent.control.protocol import PROTOCOL
from test_b03_reservation_boundaries import first_external_reservation_durability
from test_fake_code_agent import _host_timeout_process
from test_external_operation_recovery import (backend_cancel_recovery, containment_stop_recovery,
                                              dispatch_integrity_recovery, dispatch_watchdog_recovery,
                                              dispatch_authorization_recovery,
                                              reference_publication_domain_gap, reference_publication_recovery,
                                              uncertain_dispatch_recovery)
from test_code_prestart import prestart, prestart_client
from helpers.canonical_code import timeout_prestart_source
from test_external_consumption_control import normal_external, CanonicalDomainConsumer


SPECS = case_specs(PROTOCOL)
CONTAINMENT_STOP_CASES = tuple(
    case_id for case_id, spec in SPECS.items()
    if spec["failpoint_id"] in ("external.write_lease_revocation", "external.containment_kill_all",
                                "external.bounded_drain", "external.verify_empty", "external.post_stop_stability")
)
INITIAL_CUTS = {
    "external.stub.before.reservation_rolled_back": "before_insert",
    "external.stub.after.reservation_rolled_back": "after_insert",
    "external.external_operation_reserved.before.reservation_rolled_back": "before",
    "external.external_operation_reserved.after.committed_result_replay": "after",
}
HOST_FINAL_CUTS = tuple(
    f"external.{phase}.{side}.committed_result_replay"
    for phase in ("termination_evidence_committed", "external_final_evidence_committed")
    for side in ("before", "after")
)
UNCERTAIN_DISPATCH_CASE = "external.backend_dispatch.after.committed_result_replay"
BEFORE_DISPATCH_STOP_CASES = tuple(
    f"external.backend_dispatch.before.{outcome}"
    for outcome in ("committed_result_replay", "non_materializable_domain_gap")
)
AFTER_DISPATCH_GAP_CASE = "external.backend_dispatch.after.non_materializable_domain_gap"
DISPATCH_INTEGRITY_CASES = tuple(
    f"external.backend_dispatch.{side}.integrity_conflict" for side in ("before", "after")
)
DISPATCH_AUTHORIZATION_CASES = tuple(
    f"external.{boundary}.{side}.{outcome}"
    for boundary, outcomes in (
        ("dispatch_authorization", ("materializable_publication_prefix", "committed_result_replay",
                                    "integrity_conflict", "non_materializable_domain_gap")),
        ("dispatch_authorized", ("committed_result_replay", "integrity_conflict",
                                 "non_materializable_domain_gap")))
    for side in ("before", "after") for outcome in outcomes
)
BACKEND_CANCEL_CASES = tuple(
    f"external.backend_cancel.{side}.{outcome}"
    for side in ("before", "after")
    for outcome in ("committed_result_replay", "integrity_conflict", "non_materializable_domain_gap")
)
REFERENCE_PUBLICATION_CASES = tuple(
    f"{boundary}.{side}.{'materializable_publication_prefix' if boundary in ('external.receipt', 'external.immutable_result') else 'committed_result_replay'}"
    for boundary in ("external.receipt", "external.dispatch_receipt_committed",
                     "external.immutable_result", "external.result_reference_committed")
    for side in ("before", "after")
)
REFERENCE_REPLAY_CASES = tuple(
    f"{boundary}.{side}.committed_result_replay"
    for boundary in ("external.receipt", "external.immutable_result")
    for side in ("before", "after")
)
REFERENCE_INTEGRITY_CASES = tuple(
    f"{boundary}.{side}.integrity_conflict"
    for boundary in ("external.receipt", "external.dispatch_receipt_committed",
                     "external.immutable_result", "external.result_reference_committed")
    for side in ("before", "after")
)
REFERENCE_GAP_CASES = tuple(
    f"{boundary}.{side}.non_materializable_domain_gap"
    for boundary in ("external.receipt", "external.dispatch_receipt_committed",
                     "external.immutable_result", "external.result_reference_committed")
    for side in ("before", "after")
)
COMPLETION_PUBLICATION_CASES = tuple(
    f"external.backend_completion.{side}.{outcome}"
    for side in ("before", "after")
    for outcome in ("materializable_publication_prefix", "committed_result_replay", "integrity_conflict")
)
COMPLETION_GAP_CASES = tuple(
    f"external.backend_completion.{side}.non_materializable_domain_gap"
    for side in ("before", "after")
)
STUB_SETUP_CASE = "external.external_operation_reserved.after.materializable_publication_prefix"
STUB_INTEGRITY_CASE = "external.external_operation_reserved.after.integrity_conflict"
STUB_DOMAIN_GAP_CASE = "external.external_operation_reserved.after.non_materializable_domain_gap"
UNSTARTED_PHASES = (
    ("pause_ownership_reserved", "pause_claimed_recorded"),
    ("pause_claimed_recorded", "prestart_records_committed"),
    ("prestart_records_committed", "pause_consumed_recorded"),
    ("pause_consumed_recorded", "running_lifecycle_recorded"),
    ("running_lifecycle_recorded", "resume_checkpoint_committed"),
    ("resume_checkpoint_committed", "invocation_authorized"),
)
UNSTARTED_CASES = tuple(
    (f"post_claim.{phase}.unstarted_recovery.{authority}", phase, next_phase, authority)
    for phase, next_phase in UNSTARTED_PHASES for authority in ("appendable", "unavailable")
)
SAFE_POST_CLAIM_CASES = tuple(
    (f"post_claim.{phase}.safe_stop.{authority}", phase, next_phase, authority)
    for phase, next_phase in UNSTARTED_PHASES for authority in ("appendable", "unavailable")
)
STARTED_POST_CLAIM_CASES = tuple(
    (f"post_claim.invocation_authorized.{stop}.{authority}", stop, authority)
    for stop in ("safe_stop", "unavailable") for authority in ("appendable", "unavailable")
)
PRESTART_CASES = {
    "external.task.before.materializable_publication_prefix": ("external.task.file_sync", "external_operation_reserved", False),
    "external.task.after.materializable_publication_prefix": ("external.task.file_sync", "external_operation_reserved", False),
    "external.task_committed.before.materializable_publication_prefix": (
        "external.task_committed", "external_operation_reserved", False),
    "external.task_committed.after.committed_result_replay": ("external.task_committed", "task_committed", False),
    "external.unmaterialized_manifest.before.materializable_publication_prefix": (
        "external.unmaterialized_manifest.file_sync", "task_committed", False),
    "external.unmaterialized_manifest.after.materializable_publication_prefix": (
        "external.unmaterialized_manifest.file_sync", "task_committed", False),
    "external.workspace_manifest_committed.before.materializable_publication_prefix": (
        "external.workspace_manifest_committed", "task_committed", False),
    "external.workspace_manifest_committed.after.committed_result_replay": (
        "external.workspace_manifest_committed", "workspace_manifest_committed", False),
    "external.aggregate_reservation.before.materializable_publication_prefix": (
        "external.aggregate_reservation.file_sync", "workspace_manifest_committed", False),
    "external.aggregate_reservation.after.materializable_publication_prefix": (
        "external.aggregate_reservation.file_sync", "workspace_manifest_committed", False),
    "external.reservation_committed.before.materializable_publication_prefix": (
        "external.reservation_committed", "workspace_manifest_committed", False),
    "external.reservation_committed.after.committed_result_replay": (
        "external.reservation_committed", "reservation_committed", False),
    "external.immutable_core_cas.before.materializable_publication_prefix": (
        "external.immutable_core_cas", "reservation_committed", False),
    "external.immutable_core_cas.after.materializable_publication_prefix": (
        "external.immutable_core_cas", "reservation_committed", False),
    "external.core_contract_committed.before.materializable_publication_prefix": (
        "external.core_contract_committed", "reservation_committed", False),
    "external.core_contract_committed.after.committed_result_replay": (
        "external.core_contract_committed", "core_contract_committed", False),
    "external.workspace_materialization.before.materializable_publication_prefix": (
        "external.workspace_materialization", "core_contract_committed", True),
    "external.workspace_materialization.after.materializable_publication_prefix": (
        "external.workspace_materialization", "core_contract_committed", True),
    "external.workspace_materialized.before.materializable_publication_prefix": (
        "external.workspace_materialized", "core_contract_committed", True),
    "external.workspace_materialized.after.committed_result_replay": (
        "external.workspace_materialized", "workspace_materialized", True),
}
PRESTART_COMPLEMENT_CASES = {
    cid.rsplit(".", 1)[0] + (".committed_result_replay" if cid.endswith("materializable_publication_prefix")
                             else ".materializable_publication_prefix"): details
    for cid, details in PRESTART_CASES.items()
}
PRESTART_INTEGRITY_CASES = {
    cid.rsplit(".", 1)[0] + ".integrity_conflict": details
    for cid, details in PRESTART_CASES.items()
}
PRESTART_GAP_CASES = {
    cid.rsplit(".", 1)[0] + ".non_materializable_domain_gap": details
    for cid, details in PRESTART_CASES.items()
}


def _post_claim_first_process(pipe, root, request, next_phase, hook_request, phase_after_only):
    from functools import partial
    from harness.pytest_evidence import production_hook

    coordinator = None
    fired = False
    armed_owner = None

    def observer(name, side, value):
        nonlocal fired, armed_owner
        if name == "control.resume_run.continue_execution." + next_phase and side == "before" and not fired:
            fired = True
            raise ControlIntegrityError("Injected failure before the next consumer phase")
        if name == "control.resume_run.continue_execution.consumption_failure_ownership_reserved" and side == "after":
            assert fired and armed_owner is None
            if phase_after_only:
                os._exit(97)
            armed_owner = value["operation_id"]
            observer.production_hooks = {("coordinator.database_commit", "after"): (
                partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
        if name == "coordinator.database_commit" and side == "after" and armed_owner is not None:
            assert coordinator.get(armed_owner)["phase"] == "consumption_failure_ownership_reserved"
            os._exit(97)

    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=observer)
    try:
        actor = ActorContext("operator", "human", ("control.internal", "resume"))
        adapter = CanonicalDomainConsumer(coordinator, Path(root) / "base_repository")
        plane = ControlPlane(coordinator, worker_id="post-claim-first", external_adapter=adapter,
                             resume_target_adapter=adapter)
        pipe.send(plane.resume_run(ResumeRunRequest(**request), actor=actor))
    finally:
        coordinator.close()
        pipe.close()


def _post_claim_recovery_process(pipe, root, request):
    coordinator = Coordinator(root, clock=FakeClock(140, 40, epoch_id="fake_clock_epoch_2"))
    try:
        class StopCountingConsumer(CanonicalDomainConsumer):
            def __init__(self, coordinator, repository):
                super().__init__(coordinator, repository)
                self.stop_calls = 0

            def stop_consumption(self, coordinator, intent):
                self.stop_calls += 1
                return super().stop_consumption(coordinator, intent)

        adapter = StopCountingConsumer(coordinator, Path(root) / "base_repository")
        plane = ControlPlane(coordinator, worker_id="post-claim-recovery", external_adapter=adapter,
                             resume_target_adapter=adapter)
        actor = ActorContext("operator", "human", ("control.internal", "resume"))
        result = plane.resume_run(ResumeRunRequest(**request), actor=actor)
        pipe.send((result, adapter.calls, adapter.stop_calls))
    finally:
        coordinator.close()
        pipe.close()


def _spawn_post_claim(context, target, args, *, expected_exit):
    parent, child = context.Pipe()
    process = context.Process(target=target, args=(child, *args))
    try:
        process.start()
        child.close()
        process.join(30)
        assert process.exitcode == expected_exit, process.exitcode
        value = parent.recv() if expected_exit == 0 and parent.poll(2) else None
        assert expected_exit != 0 or value is not None
        return process, value
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()


def unstarted_post_claim_recovery(case_id, source_phase, next_phase, authority, *, hook_request):
    fixture = normal_external.__wrapped__()
    coordinator, _, _, locator, request, _ = next(fixture)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    context = multiprocessing.get_context("spawn")
    original = ExternalControl(coordinator).read(coordinator.connection, request.input_snapshot["producer_operation_id"])
    normal_final = (root / original["terminal_evidence_reference"]).read_bytes()
    try:
        crashed, _ = _spawn_post_claim(context, _post_claim_first_process,
                                       (str(coordinator.root), asdict(request), next_phase, hook_request, False),
                                       expected_exit=97)
        consume_process_hook(hook_request, crashed, expected_exit=97)
        operation = coordinator.lookup_key("public_control", request.idempotency_key)
        owner = operation["operation_id"]
        assert operation["phase"] == "consumption_failure_ownership_reserved"
        history = coordinator.history(owner)
        reserved = [row for row in history if row["phase"] == "consumption_failure_ownership_reserved"]
        assert len(reserved) == 1
        frozen = reserved[0]["evidence"]["frozen_failure_snapshot_and_disposition_contract"]
        assert frozen["source_phase"] == source_phase
        assert frozen["failure"]["attempt_identity_status_and_started_intent"]["started_intent"] is None
        assert frozen["stop_intent"]["consumer_capability_id"] == "capability_" + owner
        if authority == "unavailable":
            with (root / "execution_history.jsonl").open("ab") as stream:
                stream.write(b"{partial")
        recovered, output = _spawn_post_claim(context, _post_claim_recovery_process,
                                               (str(coordinator.root), asdict(request)), expected_exit=0)
        assert recovered.pid != crashed.pid
        result, consumer_calls, stop_calls = output
        assert result["operation_id"] == owner and consumer_calls == stop_calls == 0
        expected_outcome = "failed_closure" if authority == "appendable" else "unavailable_closure"
        assert result["operation_status"] == ("committed" if authority == "appendable" else "recovery_required")
        assert result["terminal_closure"] == ("committed" if authority == "appendable" else "unavailable")
        assert result["run_status"] == ("failed" if authority == "appendable" else None)
        history = coordinator.history(owner)
        for phase in ("consumption_failure_ownership_reserved", "consumption_failure_stop_verified",
                      "consumption_failure_classified"):
            assert sum(row["phase"] == phase for row in history) == 1
        stop = next(row["evidence"] for row in history if row["phase"] == "consumption_failure_stop_verified")
        proof = stop["consumer_verifier_containment_stop_and_write_fence_proof"]
        assert proof["classification"] == "safe_stop"
        assert proof["proof"] == {"termination_or_not_dispatched": {"tag": "not_dispatched"},
                                  "write_lease_revocation": True, "verify_empty": True,
                                  "bounded_drain": True, "post_stop_stability": True}
        assert stop["run_authority_integrity_proof_or_unavailable"]["classification"] == authority
        classified = next(row["evidence"]["consumption_failure_outcome"] for row in history
                          if row["phase"] == "consumption_failure_classified")
        assert classified == expected_outcome
        closures = coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchall()
        assert len(closures) == 1
        closure = loads(closures[0][0])
        assert closure["terminal_closure_owner_operation_id"] == owner
        assert (root / original["terminal_evidence_reference"]).read_bytes() == normal_final
        assert ExternalControl(coordinator).read(coordinator.connection,
                                                  request.input_snapshot["producer_operation_id"])["resolution_owner"] == "normal"
        trace = {"schema_version": "0.1", "events": [
            event("post_claim_failure_committed", phase="consumption_failure_ownership_reserved",
                  source=source_phase, stage="after_database_commit", started=False,
                  owner="original_resume_owner"),
            event("post_claim_unstarted_recovered", source=source_phase, outcome=classified,
                  status=result["terminal_closure"], run_status=result["run_status"],
                  owner="same_resume_owner", guard="not_dispatched", target="stop_adapter_not_called",
                  invariants=["one_terminal_closure", "original_normal_final_unchanged"]),
        ]}
        return trace
    finally:
        fixture.close()


@pytest.mark.parametrize("case_id,source_phase,next_phase,authority", UNSTARTED_CASES)
def test_unstarted_post_claim_case(case_id, source_phase, next_phase, authority):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-unstarted-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = unstarted_post_claim_recovery(case_id, source_phase, next_phase, authority, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


def safe_post_claim_failure(case_id, source_phase, next_phase, authority):
    fixture = normal_external.__wrapped__()
    coordinator, plane, actor, locator, request, adapter = next(fixture)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    original = ExternalControl(coordinator).read(coordinator.connection, request.input_snapshot["producer_operation_id"])
    normal_final = (root / original["terminal_evidence_reference"]).read_bytes()
    fault_name = "control.resume_run.continue_execution." + next_phase
    fired = []
    stop_calls = []

    def stop_adapter(coordinator, intent):
        stop_calls.append(intent)
        raise AssertionError("An unstarted consumer called its stop adapter")

    def observer(name, side, value):
        if name == fault_name and side == "before" and not fired:
            fired.append(name)
            raise ControlIntegrityError("Injected failure before the next consumer phase")
        if (name, side) == ("control.resume_run.continue_execution.consumption_failure_ownership_reserved", "after"):
            if authority == "unavailable":
                (root / "artifact_index.json").write_bytes(b"{}")

    observer.production_hooks = {(fault_name, "before"): (partial(production_hook, case_id),)}
    adapter.stop_consumption = stop_adapter
    coordinator.observer = observer
    try:
        result = plane.resume_run(request, actor=actor)
        assert fired == [fault_name] and stop_calls == []
        owner = result["operation_id"]
        history = coordinator.history(owner)
        frozen = next(row["evidence"]["frozen_failure_snapshot_and_disposition_contract"] for row in history
                      if row["phase"] == "consumption_failure_ownership_reserved")
        assert frozen["source_phase"] == source_phase
        assert frozen["failure"]["attempt_identity_status_and_started_intent"]["started_intent"] is None
        stop = next(row["evidence"] for row in history if row["phase"] == "consumption_failure_stop_verified")
        assert stop["consumer_verifier_containment_stop_and_write_fence_proof"]["classification"] == "safe_stop"
        assert stop["consumer_verifier_containment_stop_and_write_fence_proof"]["proof"][
            "termination_or_not_dispatched"] == {"tag": "not_dispatched"}
        assert stop["run_authority_integrity_proof_or_unavailable"]["classification"] == authority
        outcome = "failed_closure" if authority == "appendable" else "unavailable_closure"
        assert next(row["evidence"]["consumption_failure_outcome"] for row in history
                    if row["phase"] == "consumption_failure_classified") == outcome
        assert result["operation_status"] == ("committed" if authority == "appendable" else "recovery_required")
        assert result["terminal_closure"] == ("committed" if authority == "appendable" else "unavailable")
        assert result["run_status"] == ("failed" if authority == "appendable" else None)
        assert (root / original["terminal_evidence_reference"]).read_bytes() == normal_final
        assert ExternalControl(coordinator).read(coordinator.connection,
                                                  request.input_snapshot["producer_operation_id"])["resolution_owner"] == "normal"
        return {"schema_version": "0.1", "events": [
            event("post_claim_failure_entry", source=source_phase, phase=next_phase,
                  stage="before", started=False),
            event("post_claim_safe_stop_classified", source=source_phase, outcome=outcome,
                  status=result["terminal_closure"], run_status=result["run_status"],
                  owner="same_resume_owner", guard="not_dispatched", target="stop_adapter_not_called",
                  invariants=["normal_external_resolution_immutable", "one_failure_owner"]),
        ]}
    finally:
        fixture.close()


@pytest.mark.parametrize("case_id,source_phase,next_phase,authority", SAFE_POST_CLAIM_CASES)
def test_safe_post_claim_case(case_id, source_phase, next_phase, authority):
    trace = safe_post_claim_failure(case_id, source_phase, next_phase, authority)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


def started_post_claim_failure(case_id, stop, authority):
    fixture = normal_external.__wrapped__()
    coordinator, plane, actor, locator, request, adapter = next(fixture)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    original = ExternalControl(coordinator).read(coordinator.connection, request.input_snapshot["producer_operation_id"])
    normal_final = (root / original["terminal_evidence_reference"]).read_bytes()
    started = []
    stopped = []

    def observer(name, side, value):
        if (name, side) == ("invocation.started_intent", "after"):
            started.append(value)

    observer.production_hooks = {("invocation.started_intent", "after"): (partial(production_hook, case_id),)}

    def fail_consume(identity, binding, port):
        adapter.calls += 1
        if authority == "unavailable":
            (root / "artifact_index.json").write_bytes(b"{}")
        raise ControlIntegrityError("Injected consumer integrity failure")

    def stop_consume(coordinator, intent):
        stopped.append(intent)
        return ConsumerStopObservation({"termination_or_not_dispatched": "confirmed",
            "write_lease_revocation": True, "verify_empty": stop == "safe_stop",
            "bounded_drain": True, "post_stop_stability": True}, {})

    adapter.consume_external = fail_consume
    adapter.stop_consumption = stop_consume
    coordinator.observer = observer
    try:
        result = plane.resume_run(request, actor=actor)
        assert len(started) == len(stopped) == adapter.calls == 1
        owner = result["operation_id"]
        history = coordinator.history(owner)
        frozen = next(row["evidence"]["frozen_failure_snapshot_and_disposition_contract"] for row in history
                      if row["phase"] == "consumption_failure_ownership_reserved")
        assert frozen["source_phase"] == "invocation_authorized"
        assert frozen["failure"]["attempt_identity_status_and_started_intent"]["started_intent"] is not None
        proof = next(row["evidence"] for row in history if row["phase"] == "consumption_failure_stop_verified")
        assert proof["consumer_verifier_containment_stop_and_write_fence_proof"]["classification"] == stop
        assert proof["run_authority_integrity_proof_or_unavailable"]["classification"] == authority
        outcome = "failed_closure" if stop == "safe_stop" and authority == "appendable" else "unavailable_closure"
        assert next(row["evidence"]["consumption_failure_outcome"] for row in history
                    if row["phase"] == "consumption_failure_classified") == outcome
        assert result["terminal_closure"] == ("committed" if outcome == "failed_closure" else "unavailable")
        assert result["run_status"] == ("failed" if outcome == "failed_closure" else None)
        assert (root / original["terminal_evidence_reference"]).read_bytes() == normal_final
        assert ExternalControl(coordinator).read(coordinator.connection,
                                                  request.input_snapshot["producer_operation_id"])["resolution_owner"] == "normal"
        return {"schema_version": "0.1", "events": [
            event("post_claim_consumer_started", phase="invocation_authorized", started=True,
                  stage="after", owner="same_resume_owner"),
            event("post_claim_started_classified", source="invocation_authorized", outcome=outcome,
                  status=result["terminal_closure"], run_status=result["run_status"],
                  owner="same_resume_owner", guard=stop, target=authority,
                  invariants=["normal_external_resolution_immutable", "one_failure_owner"]),
        ]}
    finally:
        fixture.close()


@pytest.mark.parametrize("case_id,stop,authority", STARTED_POST_CLAIM_CASES)
def test_started_post_claim_case(case_id, stop, authority):
    trace = started_post_claim_failure(case_id, stop, authority)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("source_phase,next_phase", UNSTARTED_PHASES)
def test_unstarted_phase_after_exit_rolls_back_failure_owner(source_phase, next_phase):
    fixture = normal_external.__wrapped__()
    coordinator, _, _, _, request, _ = next(fixture)
    try:
        context = multiprocessing.get_context("spawn")
        _spawn_post_claim(context, _post_claim_first_process,
                          (str(coordinator.root), asdict(request), next_phase, None, True), expected_exit=97)
        operation = coordinator.lookup_key("public_control", request.idempotency_key)
        assert operation["phase"] != "consumption_failure_ownership_reserved"
        assert not any(row["phase"] == "consumption_failure_ownership_reserved"
                       for row in coordinator.history(operation["operation_id"]))
        assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 0
    finally:
        fixture.close()


@pytest.mark.parametrize("case_id", sorted(INITIAL_CUTS))
def test_independent_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-runtime-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = first_external_reservation_durability(INITIAL_CUTS[case_id], hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


def host_final_replay(case_id, *, hook_request=None, with_root=False):
    boundary, side, outcome = case_id.rsplit(".", 2)
    coordinator, _, _, locator, root, task, _ = timeout_prestart_source()
    producer = task["producer_operation_id"]
    trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
    (root / "timeout_trigger.json").write_bytes(canonical_bytes(trigger))
    request = asdict(ResolveExternalInterruptRequest(locator, producer, "operation_timeout",
                                                     "timeout_trigger.json", digest(trigger)))
    context = multiprocessing.get_context("spawn")

    def run(cut, receipt=None):
        parent, child = context.Pipe()
        process = context.Process(target=_host_timeout_process,
                                  args=(child, str(coordinator.root), request, cut, receipt, side))
        try:
            process.start()
            child.close()
            process.join(30)
            assert process.exitcode == (97 if cut else 0)
            if receipt is not None:
                consume_process_hook(receipt, process, expected_exit=97)
            if cut is None:
                assert parent.poll(2)
                return parent.recv()
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()

    try:
        run(boundary, hook_request)
        stopped = ExternalControl(coordinator).read(coordinator.connection, producer)
        predecessor = ("interrupt_stop_intent_committed" if boundary.endswith("termination_evidence_committed")
                       else "termination_evidence_committed")
        assert stopped["operation_phase"] == predecessor
        assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(producer)["status"] == "unknown"
        recovered = run(None)
        assert recovered["operation_status"] == "committed" and recovered["terminal_closure"] == "not_applicable"
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["operation_phase"] == "external_final_evidence_committed"
        assert value["resolution_owner"] == "interrupt" and proof["proof_kind"] == "safe_stop"
        assert proof["stop_proof"]["termination_or_not_dispatched"] == {"tag": "not_dispatched"}
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations WHERE external_operation_id=?",
                                              (producer,)).fetchone()[0] == 1
        assert run(None) == recovered
        assert ExternalControl(coordinator).read(coordinator.connection, producer) == value
        assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(producer)["status"] == "unknown"
        trace = {"schema_version": "0.1", "events": [
            event("external_final_cut", phase=boundary, stage=side, outcome=outcome,
                  source=stopped["operation_phase"]),
            event("external_final_replayed", phase=value["operation_phase"], outcome=recovered["operation_status"],
                  owner=value["resolution_owner"], status=recovered["terminal_closure"],
                  lease_epoch=value["lease_epoch"], target="backend_unknown", guard=proof["proof_kind"]),
        ]}
        return (trace, str(coordinator.root)) if with_root else trace
    finally:
        coordinator.close()


@pytest.mark.parametrize("case_id", HOST_FINAL_CUTS)
def test_host_final_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-host-final-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = host_final_replay(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


def test_uncertain_dispatch_case():
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-dispatch-hook-", dir="/private/tmp"))
    request = process_hook_request(UNCERTAIN_DISPATCH_CASE, directory)
    trace = uncertain_dispatch_recovery(hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" /
                        (UNCERTAIN_DISPATCH_CASE + ".json")))
    spec = SPECS[UNCERTAIN_DISPATCH_CASE]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + UNCERTAIN_DISPATCH_CASE, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(UNCERTAIN_DISPATCH_CASE, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("case_id", BEFORE_DISPATCH_STOP_CASES)
def test_before_dispatch_stop_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-dispatch-before-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = dispatch_watchdog_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


def test_after_dispatch_gap_case():
    case_id = AFTER_DISPATCH_GAP_CASE
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-dispatch-after-gap-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = dispatch_watchdog_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("case_id", DISPATCH_INTEGRITY_CASES)
def test_dispatch_integrity_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-dispatch-integrity-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = dispatch_integrity_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("case_id", DISPATCH_AUTHORIZATION_CASES)
def test_dispatch_authorization_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-dispatch-authorization-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = dispatch_authorization_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("case_id", BACKEND_CANCEL_CASES)
def test_backend_cancel_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-backend-cancel-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = backend_cancel_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("case_id", CONTAINMENT_STOP_CASES)
def test_containment_stop_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-containment-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = containment_stop_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("case_id", REFERENCE_PUBLICATION_CASES + REFERENCE_REPLAY_CASES +
                         REFERENCE_INTEGRITY_CASES + COMPLETION_PUBLICATION_CASES)
def test_reference_publication_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-reference-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = reference_publication_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("case_id", REFERENCE_GAP_CASES + COMPLETION_GAP_CASES)
def test_reference_domain_gap_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-reference-gap-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = reference_publication_domain_gap(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


def _recover_stub_setup(pipe, output, producer, locator):
    coordinator = Coordinator(output, clock=FakeClock(140, 40))
    try:
        source = ExternalProducer(coordinator).lookup(producer)
        if source["prestart"]["active_time"]["published"]:
            record = source["prestart"]["active_time"]["setup_record"]
        else:
            value = ExternalProducer(coordinator).recover_setup(producer, worker_id="setup-recovery", lease_seconds=10)
            record = CodePrestart(coordinator, producer, "setup-recovery", value["lease_epoch"]).publish_setup()
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        saved = ExternalControl(coordinator).read(coordinator.connection, producer)
        assert sum(row == record for row in rows) == 1
        assert saved["operation_phase"] == "external_operation_reserved"
        assert saved["prestart"]["active_time"]["published"] is True
        assert not (coordinator.root / "fake_backend").exists()
        pipe.send({"record_digest": digest(record), "phase": saved["operation_phase"],
                   "lease_epoch": saved["lease_epoch"]})
    finally:
        coordinator.close()
        pipe.close()


def stub_setup_recovery(*, hook_request=None):
    _, output, producer, locator = first_external_reservation_durability(
        "after", hook_request=hook_request, with_context=True)
    context = multiprocessing.get_context("spawn")
    recovered = None
    for _ in range(2):
        parent, child = context.Pipe()
        process = context.Process(target=_recover_stub_setup, args=(child, output, producer, locator))
        try:
            process.start()
            child.close()
            process.join(30)
            assert process.exitcode == 0 and parent.poll(2)
            result = parent.recv()
            if recovered is None:
                recovered = result
            else:
                assert result == recovered
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
    return {"schema_version": "0.1", "events": [
        event("external_stub_cut", phase="external.external_operation_reserved", stage="after",
              source="durable_stub", outcome="materializable_publication_prefix"),
        event("original_setup_materialized", phase=recovered["phase"], status="published_once",
              owner="original_producer", lease_epoch=recovered["lease_epoch"],
              target="frozen_setup_record", guard="no_backend_dispatch"),
    ]}


def test_stub_setup_case():
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-stub-setup-hook-", dir="/private/tmp"))
    request = process_hook_request(STUB_SETUP_CASE, directory)
    trace = stub_setup_recovery(hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" /
                        (STUB_SETUP_CASE + ".json")))
    spec = SPECS[STUB_SETUP_CASE]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + STUB_SETUP_CASE, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(STUB_SETUP_CASE, spec["outcome"], invariants, trace)


def _reject_stub_setup(pipe, output, producer):
    coordinator = Coordinator(output, clock=FakeClock(140, 40))
    try:
        value = ExternalProducer(coordinator).recover_setup(producer, worker_id="setup-recovery", lease_seconds=10)
        try:
            CodePrestart(coordinator, producer, "setup-recovery", value["lease_epoch"]).publish_setup()
        except ControlIntegrityError as error:
            saved = ExternalControl(coordinator).read(coordinator.connection, producer)
            assert saved["prestart"]["active_time"]["published"] is False
            pipe.send({"rejected": str(error), "phase": saved["operation_phase"]})
        else:
            raise AssertionError("Corrupt Run ledger was accepted as the original setup source")
    finally:
        coordinator.close()
        pipe.close()


def stub_integrity_rejection(*, hook_request=None):
    _, output, producer, locator = first_external_reservation_durability(
        "after", hook_request=hook_request, with_context=True)
    root = Path(output) / locator["case_id"] / locator["run_id"]
    ledger = root / "execution_history.jsonl"
    ledger.write_bytes(ledger.read_bytes() + b"{")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_reject_stub_setup, args=(child, output, producer))
    try:
        process.start()
        child.close()
        process.join(30)
        assert process.exitcode == 0 and parent.poll(2)
        result = parent.recv()
        assert result["phase"] == "external_operation_reserved" and result["rejected"]
        assert ledger.read_bytes().endswith(b"{")
        assert not (Path(output) / "fake_backend").exists()
        return {"schema_version": "0.1", "events": [
            event("external_stub_cut", phase="external.external_operation_reserved", stage="after",
                  source="durable_stub", outcome="integrity_conflict"),
            event("original_setup_rejected", phase=result["phase"], status="rejected",
                  owner="original_producer", target="changed_ledger", guard="no_backend_dispatch"),
        ]}
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()


def test_stub_integrity_case():
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-stub-integrity-hook-", dir="/private/tmp"))
    request = process_hook_request(STUB_INTEGRITY_CASE, directory)
    trace = stub_integrity_rejection(hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" /
                        (STUB_INTEGRITY_CASE + ".json")))
    spec = SPECS[STUB_INTEGRITY_CASE]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + STUB_INTEGRITY_CASE, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(STUB_INTEGRITY_CASE, spec["outcome"], invariants, trace)


def _stub_deadline_watchdog(pipe, output, producer):
    coordinator = Coordinator(output, clock=FakeClock(140, 40))
    backend = FakeCodingBackend(coordinator.root / "fake_backend")
    containment = DeterministicContainment(coordinator.root / "containment")
    try:
        result = CodeWatchdog(coordinator, backend, containment, backend.read_receipt).enforce(producer)
        saved = ExternalControl(coordinator).read(coordinator.connection, producer)
        assert result["operation_status"] == "recovery_required"
        assert result["terminal_closure"] == "unavailable" and result["run_status"] is None
        assert saved["resolution_owner"] == "interrupt" and saved["operation_phase"] == "external_final_evidence_committed"
        assert backend.lookup(producer)["status"] == "unknown"
        pipe.send({"status": result["operation_status"], "closure": result["terminal_closure"],
                   "owner": saved["resolution_owner"], "phase": saved["operation_phase"]})
    finally:
        coordinator.close()
        pipe.close()


def stub_domain_gap(*, hook_request=None):
    _, output, producer, _ = first_external_reservation_durability(
        "after", hook_request=hook_request, with_context=True)
    context = multiprocessing.get_context("spawn")
    recovered = None
    for _ in range(2):
        parent, child = context.Pipe()
        process = context.Process(target=_stub_deadline_watchdog, args=(child, output, producer))
        try:
            process.start()
            child.close()
            process.join(30)
            assert process.exitcode == 0 and parent.poll(2)
            result = parent.recv()
            if recovered is None:
                recovered = result
            else:
                assert result == recovered
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
    return {"schema_version": "0.1", "events": [
        event("external_stub_cut", phase="external.external_operation_reserved", stage="after",
              source="durable_stub", outcome="non_materializable_domain_gap"),
        event("original_setup_expired", phase=recovered["phase"], status=recovered["status"],
              owner=recovered["owner"], target="deadline_exceeded", guard="no_backend_dispatch",
              outcome=recovered["closure"]),
    ]}


def test_stub_domain_gap_case():
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-stub-gap-hook-", dir="/private/tmp"))
    request = process_hook_request(STUB_DOMAIN_GAP_CASE, directory)
    trace = stub_domain_gap(hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" /
                        (STUB_DOMAIN_GAP_CASE + ".json")))
    spec = SPECS[STUB_DOMAIN_GAP_CASE]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + STUB_DOMAIN_GAP_CASE, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(STUB_DOMAIN_GAP_CASE, spec["outcome"], invariants, trace)


def prestart_publication_recovery(case_id, *, hook_request=None, fixture_case=None):
    source_case = fixture_case or case_id
    integrity = source_case in PRESTART_INTEGRITY_CASES
    cut, stopped_phase, physical = (PRESTART_INTEGRITY_CASES if integrity else
        PRESTART_CASES | PRESTART_COMPLEMENT_CASES)[source_case]
    side = case_id.rsplit(".", 2)[1]
    fixture = prestart.__wrapped__()
    service, root, witness = next(fixture)
    producer = witness["task"]["producer_operation_id"]
    context = multiprocessing.get_context("spawn")
    try:
        for crashed in (True, False):
            parent, child = context.Pipe()
            process = context.Process(target=prestart_client, args=(child, str(service.coordinator.root), witness,
                                      (cut, side) if crashed else None, physical,
                                      hook_request if crashed else None, integrity and not crashed))
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == (95 if crashed else 0)
                if crashed:
                    if hook_request is not None:
                        consume_process_hook(hook_request, process, expected_exit=95)
                    interim = ExternalControl(service.coordinator).read(service.coordinator.connection, producer)
                    assert interim["operation_phase"] == stopped_phase
                    if integrity:
                        task_path = root / "code_agent_control" / witness["task"]["attempt_id"] / "code_agent_task.json"
                        task_path.parent.mkdir(parents=True, exist_ok=True)
                        task_path.write_bytes(b"{}")
                else:
                    assert parent.poll(2)
                    recovered = parent.recv()
                    if integrity:
                        assert "rejected" in recovered and (
                            "task" in recovered["rejected"].lower() or
                            "publication" in recovered["rejected"].lower())
                    else:
                        core = recovered
            finally:
                if process.is_alive():
                    process.kill()
                    process.join()
                parent.close()
        if integrity:
            assert ExternalControl(service.coordinator).read(service.coordinator.connection, producer) == interim
            assert task_path.read_bytes() == b"{}"
            assert not (service.coordinator.root / "fake_backend").exists()
            return {"schema_version": "0.1", "events": [
                event("prestart_publication_cut", phase=cut, stage=side, source=stopped_phase,
                      outcome="integrity_conflict"),
                event("prestart_integrity_rejected", phase=stopped_phase, status="rejected",
                      target="changed_task_member", guard="same_producer_no_reexecution"),
            ]}
        final = ExternalControl(service.coordinator).read(service.coordinator.connection, producer)
        assert final["operation_phase"] == ("workspace_materialized" if physical else "core_contract_committed")
        assert final["operation_contract_digest"] == core["operation_contract_digest"]
        assert service.commit_core() == core
        if physical:
            witness_value = service.materialize_workspace(witness["base_repository"])
            assert witness_value["base_tree_digest"] == witness["manifest"]["base_tree_digest"]
        replay = source_case in PRESTART_COMPLEMENT_CASES and SPECS[case_id]["outcome"] == "committed_result_replay"
        if replay:
            parent, child = context.Pipe()
            process = context.Process(target=prestart_client,
                args=(child, str(service.coordinator.root), witness, None, physical))
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == 0 and parent.poll(2)
                assert parent.recv() == core
            finally:
                if process.is_alive():
                    process.kill()
                    process.join()
                parent.close()
        events = [
            event("prestart_publication_cut", phase=cut, stage=side, source=stopped_phase,
                  outcome=SPECS[case_id]["outcome"]),
            event("prestart_original_recovered", phase=final["operation_phase"],
                  owner="original_producer", status="one_aggregate", guard="same_task_manifest_core",
                  target="workspace_materialized" if physical else "core_contract_committed"),
        ]
        if replay:
            events.append(event("prestart_original_replayed", phase=final["operation_phase"],
                                owner="original_producer", status="one_aggregate",
                                guard="same_task_manifest_core", target=final["operation_phase"]))
        return {"schema_version": "0.1", "events": events}
    finally:
        fixture.close()


@pytest.mark.parametrize("case_id", sorted(PRESTART_CASES | PRESTART_COMPLEMENT_CASES))
def test_prestart_publication_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-prestart-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = prestart_publication_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("case_id", sorted(PRESTART_INTEGRITY_CASES))
def test_prestart_integrity_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-prestart-integrity-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = prestart_publication_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


def prestart_domain_gap(case_id, *, hook_request=None, fixture_case=None):
    cut, stopped_phase, physical = PRESTART_GAP_CASES[fixture_case or case_id]
    side = case_id.rsplit(".", 2)[1]
    fixture = prestart.__wrapped__()
    service, _, witness = next(fixture)
    producer = witness["task"]["producer_operation_id"]
    context = multiprocessing.get_context("spawn")
    try:
        parent, child = context.Pipe()
        process = context.Process(target=prestart_client, args=(child, str(service.coordinator.root), witness,
                                  (cut, side), physical, hook_request))
        try:
            process.start()
            child.close()
            process.join(30)
            assert process.exitcode == 95
            if hook_request is not None:
                consume_process_hook(hook_request, process, expected_exit=95)
            saved = ExternalControl(service.coordinator).read(service.coordinator.connection, producer)
            assert saved["operation_phase"] == stopped_phase
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
        recovered = None
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=_stub_deadline_watchdog,
                                      args=(child, str(service.coordinator.root), producer))
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == 0 and parent.poll(2)
                result = parent.recv()
                if recovered is None:
                    recovered = result
                else:
                    assert recovered == result
            finally:
                if process.is_alive():
                    process.kill()
                    process.join()
                parent.close()
        final = ExternalControl(service.coordinator).read(service.coordinator.connection, producer)
        assert final["operation_phase"] == "external_final_evidence_committed"
        assert service.coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        run = service.coordinator.root / final["run_locator"]["case_id"] / final["run_locator"]["run_id"]
        reservations = [row for row in parse_ledger((run / "execution_history.jsonl").read_bytes()).values
                        if row["record_type"] == "budget" and row["event"] == "resource_reserved" and
                        row["payload"]["producer_operation_id"] == producer]
        assert len(reservations) == int("aggregate" in final.get("prestart", {}))
        if reservations:
            assert digest(reservations[0]) == final["reservation_digest"]
        assert FakeCodingBackend(service.coordinator.root / "fake_backend").lookup(producer)["status"] == "unknown"
        return {"schema_version": "0.1", "events": [
            event("prestart_publication_cut", phase=cut, stage=side, source=stopped_phase,
                  outcome="non_materializable_domain_gap"),
            event("prestart_deadline_unavailable", phase=recovered["phase"], status=recovered["status"],
                  owner=recovered["owner"], outcome=recovered["closure"],
                  target="original_producer", guard="no_backend_dispatch"),
        ]}
    finally:
        fixture.close()


@pytest.mark.parametrize("case_id", sorted(PRESTART_GAP_CASES))
def test_prestart_gap_case(case_id):
    directory = Path(mkdtemp(prefix="lqcd-agent-b03-prestart-gap-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = prestart_domain_gap(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)
