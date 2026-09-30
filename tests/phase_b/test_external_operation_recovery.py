"""Crash and restart proof for an uncertain Backend dispatch."""
from functools import partial
import multiprocessing
import os
from pathlib import Path

from harness.pytest_evidence import consume_process_hook, production_hook
from harness.trace import event
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.external_operation import CodeWatchdog, ExternalDispatch
from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
from lqcd_agent.code_agent.prestart import CodePrestart
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.pause import PublishPauseRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest
from helpers.code_workspace import immutable_base_repository
from test_b03_task_trace_boundary import task_trace_witness


class RefuseRedispatch(FakeCodingBackend):
    def dispatch(self, task, manifest, operation_id):
        raise AssertionError("Recovery dispatched the original Backend operation again")


class UnavailableLookupBackend(RefuseRedispatch):
    def lookup(self, operation_id):
        raise OSError("Original Backend lookup is unavailable")


def _authorization_client(pipe, output, operation_id, boundary, side, *, crash, hook_request):
    def observer(name, observed_side, value):
        if crash and (name, observed_side) == (boundary, side):
            os._exit(97)

    if hook_request is not None:
        observer.production_hooks = {(boundary, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0), observer=observer)
    try:
        backend = RefuseRedispatch(coordinator.root / "fake_backend", clock=lambda: 100)
        containment = DeterministicContainment(coordinator.root / "containment")
        dispatch = ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                                    backend.read_receipt, backend.read_result)
        try:
            changed = dispatch.authorize()
        except ControlIntegrityError as error:
            pipe.send({"rejected": str(error)})
        else:
            value = ExternalControl(coordinator).read(coordinator.connection, operation_id)
            pipe.send({"changed": changed, "phase": value["operation_phase"],
                       "revision": value["phase_revision"]})
    finally:
        coordinator.close()
        pipe.close()


def _authorization_gap_watchdog(pipe, output, operation_id):
    coordinator = Coordinator(Path(output), clock=FakeClock(140, 40))
    try:
        backend = UnavailableLookupBackend(coordinator.root / "fake_backend", clock=lambda: 140)
        containment = DeterministicContainment(coordinator.root / "containment")
        result = CodeWatchdog(coordinator, backend, containment, backend.read_receipt).enforce(operation_id)
        value = ExternalControl(coordinator).read(coordinator.connection, operation_id)
        pipe.send((result, value["operation_phase"], value["resolution_owner"]))
    finally:
        coordinator.close()
        pipe.close()


def dispatch_authorization_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in ("external.dispatch_authorization", "external.dispatch_authorized")
    coordinator, run_root, operation_id = _prepared_dispatch_source()
    context = multiprocessing.get_context("spawn")
    original = "dispatch_authorized" if boundary == "external.dispatch_authorized" and side == "after" else "pause_bound"

    def run(client, *args, crash=False, hook=None):
        parent, child = context.Pipe()
        process = context.Process(target=client, args=(child, str(coordinator.root), operation_id, *args),
                                  kwargs={"crash": crash, "hook_request": hook} if client is _authorization_client else {})
        try:
            process.start()
            child.close()
            process.join(30)
            assert process.exitcode == (97 if crash else 0)
            if crash:
                if hook is not None:
                    consume_process_hook(hook, process, expected_exit=97)
            else:
                assert parent.poll(2)
                return parent.recv()
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()

    try:
        run(_authorization_client, boundary, side, crash=True, hook=hook_request)
        source = ExternalControl(coordinator).read(coordinator.connection, operation_id)
        assert source["operation_phase"] == original
        assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(operation_id)["status"] == "unknown"
        assert DeterministicContainment(coordinator.root / "containment").never_started(operation_id)
        events = [event("dispatch_authorization_cut", phase=boundary, stage=side,
                        source=original, outcome=outcome)]
        if outcome == "integrity_conflict":
            task = run_root / "code_agent_control" / source["attempt_id"] / "code_agent_task.json"
            task.write_bytes(b"{}")
            first = run(_authorization_client, boundary, side)
            second = run(_authorization_client, boundary, side)
            assert first == second and first.get("rejected")
            assert ExternalControl(coordinator).read(coordinator.connection, operation_id) == source
            assert task.read_bytes() == b"{}"
            events.append(event("changed_source_rejected", phase=original, status="rejected",
                                owner="original_producer", target="task", guard="no_backend_dispatch"))
        elif outcome == "non_materializable_domain_gap":
            first = run(_authorization_gap_watchdog)
            second = run(_authorization_gap_watchdog)
            assert first == second
            response, phase, owner = first
            assert response["operation_status"] == "recovery_required"
            assert response["terminal_closure"] == "unavailable" and response["run_status"] is None
            assert phase == "external_final_evidence_committed" and owner == "interrupt"
            events.append(event("original_operation_stopped", phase=phase, status="recovery_required",
                                owner=owner, target="backend_lookup", guard="unavailable_no_redispatch"))
        else:
            first = run(_authorization_client, boundary, side)
            second = run(_authorization_client, boundary, side)
            assert first["phase"] == second["phase"] == "dispatch_authorized"
            assert second["changed"] is False and second["revision"] == first["revision"]
            assert first["changed"] is (original == "pause_bound")
            assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
            events.append(event("authorization_materialized", phase="dispatch_authorized", status="active",
                                owner="original_producer", target="same_intent", guard="no_backend_dispatch"))
            if outcome == "committed_result_replay":
                events.append(event("authorization_replayed", phase="dispatch_authorized", status="active",
                                    owner="original_producer", target="same_revision", guard="no_backend_dispatch"))
        return {"schema_version": "0.1", "events": events}
    finally:
        coordinator.close()


def _running_stop_source(*, containment_fault):
    coordinator, run_root, operation_id = _prepared_dispatch_source()
    backend = FakeCodingBackend(coordinator.root / "fake_backend",
        operation_scenarios={operation_id: "running"},
        fixtures={"running": {"status": "running", "result": None}}, clock=lambda: 100)
    faults = {"kill_all": False} if containment_fault is True else containment_fault
    containment = DeterministicContainment(coordinator.root / "containment",
        fault_by_operation={operation_id: faults} if faults else None)
    ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                     backend.read_receipt, backend.read_result).dispatch()
    value = ExternalControl(coordinator).read(coordinator.connection, operation_id)
    assert value["operation_phase"] == "dispatch_receipt_committed"
    assert backend.lookup(operation_id)["status"] == "running"
    return coordinator, run_root, operation_id


def _backend_cancel_client(pipe, output, operation_id, side, *, crash, hook_request,
                           boundary="external.backend_cancel"):
    def observer(name, observed_side, value):
        if crash and (name, observed_side) == (boundary, side):
            os._exit(97)

    if hook_request is not None:
        observer.production_hooks = {(boundary, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(140, 40), observer=observer)
    try:
        backend = RefuseRedispatch(coordinator.root / "fake_backend", clock=lambda: 140)
        containment = DeterministicContainment(coordinator.root / "containment")
        result = CodeWatchdog(coordinator, backend, containment, backend.read_receipt).enforce(operation_id)
        value = ExternalControl(coordinator).read(coordinator.connection, operation_id)
        _, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, operation_id)
        pipe.send((result, value["operation_phase"], value["resolution_owner"],
                   proof.get("missing_proof_dimensions", [])))
    finally:
        coordinator.close()
        pipe.close()


def backend_cancel_recovery(case_id, *, hook_request=None):
    return containment_stop_recovery(case_id, hook_request=hook_request)


def containment_stop_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in ("external.backend_cancel", "external.write_lease_revocation",
                        "external.containment_kill_all", "external.bounded_drain",
                        "external.verify_empty", "external.post_stop_stability")
    fault_name = {"external.bounded_drain": "bounded_drain",
                  "external.post_stop_stability": "post_stop_stability"}.get(boundary, "kill_all")
    coordinator, run_root, operation_id = _running_stop_source(
        containment_fault={fault_name: False} if outcome == "non_materializable_domain_gap" else None)
    context = multiprocessing.get_context("spawn")

    def run(*, crash, hook=None):
        parent, child = context.Pipe()
        process = context.Process(target=_backend_cancel_client,
            args=(child, str(coordinator.root), operation_id, side),
            kwargs={"crash": crash, "hook_request": hook, "boundary": boundary})
        try:
            process.start()
            child.close()
            process.join(30)
            assert process.exitcode == (97 if crash else 0)
            if crash:
                if hook is not None:
                    consume_process_hook(hook, process, expected_exit=97)
            else:
                assert parent.poll(2)
                return parent.recv()
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()

    try:
        run(crash=True, hook=hook_request)
        cut = ExternalControl(coordinator).read(coordinator.connection, operation_id)
        assert cut["operation_phase"] == "interrupt_stop_intent_committed"
        backend = RefuseRedispatch(coordinator.root / "fake_backend", clock=lambda: 140)
        backend_status = "running" if boundary == "external.backend_cancel" and side == "before" else "cancelled"
        assert backend.lookup(operation_id)["status"] == backend_status
        if boundary != "external.backend_cancel":
            containment = DeterministicContainment(coordinator.root / "containment")
            stop_snapshot = containment.proof(operation_id)
            revoked = boundary != "external.write_lease_revocation" or side == "after"
            assert stop_snapshot["write_lease_revocation"] is revoked
            empty = (fault_name != "kill_all" or outcome != "non_materializable_domain_gap") and (
                boundary in ("external.bounded_drain", "external.verify_empty", "external.post_stop_stability") or
                boundary == "external.containment_kill_all" and side == "after")
            assert stop_snapshot["verify_empty"] is empty
            drained = (fault_name != "bounded_drain" or outcome != "non_materializable_domain_gap") and (
                boundary in ("external.verify_empty", "external.post_stop_stability") or
                boundary == "external.bounded_drain" and side == "after")
            assert stop_snapshot["bounded_drain"] is drained
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        if outcome == "integrity_conflict":
            task = run_root / "code_agent_control" / cut["attempt_id"] / "code_agent_task.json"
            task.write_bytes(b"{}")
        first = run(crash=False)
        second = run(crash=False)
        assert first == second
        response, phase, owner, missing = first
        assert phase == "external_final_evidence_committed" and owner == "interrupt"
        if outcome in ("committed_result_replay", "materializable_publication_prefix"):
            assert (response["operation_status"], response["terminal_closure"], response["run_status"]) == (
                "committed", "not_applicable", "running")
            assert not missing
        else:
            assert (response["operation_status"], response["terminal_closure"], response["run_status"]) == (
                "recovery_required", "unavailable", None)
            if outcome == "integrity_conflict":
                assert task.read_bytes() == b"{}" and "backend_lookup" in missing
            else:
                missing_dimension = {"bounded_drain": "bounded_drain",
                                     "post_stop_stability": "post_stop_stability"}.get(
                    fault_name, "termination_or_not_dispatched")
                assert missing_dimension in missing
        assert backend.lookup(operation_id)["status"] == "cancelled"
        events = [event("backend_cancel_cut" if boundary == "external.backend_cancel" else "containment_stop_cut",
                        phase=boundary, stage=side,
                        source="interrupt_stop_intent_committed", outcome=outcome,
                        status=backend_status),
                  event("original_operation_stopped", phase=phase,
                        status=response["operation_status"], owner=owner,
                        target=response["terminal_closure"], guard="no_redispatch")]
        if boundary != "external.backend_cancel":
            assert containment.observed_tool_count(operation_id) == 0
            final_snapshot = containment.proof(operation_id)
            assert final_snapshot["write_lease_revocation"] is True
            assert final_snapshot["verify_empty"] is (not (outcome == "non_materializable_domain_gap" and
                                                           fault_name == "kill_all"))
            assert final_snapshot["bounded_drain"] is (not (outcome == "non_materializable_domain_gap" and
                                                            fault_name == "bounded_drain"))
            assert final_snapshot["post_stop_stability"] is (not (outcome == "non_materializable_domain_gap" and
                                                                  fault_name == "post_stop_stability"))
            events.insert(1, event("durable_containment_cut", target="original_operation",
                                  started=True, guard_passed=stop_snapshot["write_lease_revocation"],
                                  status="empty" if stop_snapshot["verify_empty"] else "descendants_present",
                                  accepted=stop_snapshot["bounded_drain"]))
        if outcome == "committed_result_replay":
            events.append(event("watchdog_result_replayed", phase=phase,
                                status=response["operation_status"], owner=owner,
                                target=response["terminal_closure"], guard="same_original_operation"))
        return {"schema_version": "0.1", "events": events}
    finally:
        coordinator.close()


def _dispatch_client(pipe, output, operation_id, *, crash, hook_request, side="after",
                     stop_unavailable=False):
    def observer(name, side, value):
        if crash and (name, side) == ("external.backend_dispatch", requested_side):
            os._exit(97)

    requested_side = side
    if hook_request is not None:
        observer.production_hooks = {("external.backend_dispatch", requested_side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0), observer=observer)
    backend_root = coordinator.root / "fake_backend"
    backend = (FakeCodingBackend(backend_root, operation_scenarios={operation_id: "completed"},
                                 fixtures={"completed": {"status": "completed", "result": b"{}"}},
                                 clock=lambda: 100) if crash else RefuseRedispatch(backend_root, clock=lambda: 101))
    containment = DeterministicContainment(coordinator.root / "containment",
        fault_by_operation={operation_id: {"kill_all": False}} if stop_unavailable else None)
    try:
        receipt = ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                                   backend.read_receipt, backend.read_result).dispatch()
        pipe.send((receipt, backend.lookup(operation_id)))
    finally:
        coordinator.close()
        pipe.close()


def uncertain_dispatch_recovery(*, hook_request=None):
    coordinator, run_root, operation_id = _prepared_dispatch_source()
    try:
        context = multiprocessing.get_context("spawn")
        output = str(coordinator.root)
        for crash in (True, False):
            parent, child = context.Pipe()
            process = context.Process(target=_dispatch_client, args=(child, output, operation_id),
                                      kwargs={"crash": crash, "hook_request": hook_request if crash else None})
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == (97 if crash else 0)
                if crash:
                    if hook_request is not None:
                        consume_process_hook(hook_request, process, expected_exit=97)
                    value = ExternalControl(coordinator).read(coordinator.connection, operation_id)
                    assert value["operation_phase"] == "dispatch_authorized"
                    assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(operation_id)["status"] == "completed"
                else:
                    assert parent.poll(2)
                    receipt, status = parent.recv()
                    value = ExternalControl(coordinator).read(coordinator.connection, operation_id)
                    assert value["operation_phase"] == "dispatch_receipt_committed"
                    assert status["status"] == "completed" and status["receipt_digest"] == value["dispatch_receipt_digest"]
                    assert (run_root / value["dispatch_receipt_reference"]).is_file()
                    assert receipt == FakeCodingBackend(coordinator.root / "fake_backend").read_receipt(
                        status["receipt_reference"])
            finally:
                if process.is_alive():
                    process.kill()
                    process.join()
                parent.close()
        return {"schema_version": "0.1", "events": [
            event("backend_dispatch_cut", phase="external.backend_dispatch", stage="after",
                  source="dispatch_authorized", outcome="committed_result_replay"),
            event("backend_receipt_replayed", phase="dispatch_receipt_committed", status="completed",
                  target="lookup_only", guard="original_operation", lease_epoch=1),
        ]}
    finally:
        coordinator.close()


def dispatch_watchdog_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary == "external.backend_dispatch" and (
        (side == "before" and outcome in ("committed_result_replay", "non_materializable_domain_gap")) or
        (side == "after" and outcome == "non_materializable_domain_gap"))
    coordinator, _, operation_id = _prepared_dispatch_source()
    context = multiprocessing.get_context("spawn")
    try:
        parent, child = context.Pipe()
        crashed = context.Process(target=_dispatch_client, args=(child, str(coordinator.root), operation_id),
            kwargs={"crash": True, "hook_request": hook_request, "side": side,
                    "stop_unavailable": outcome == "non_materializable_domain_gap"})
        try:
            crashed.start()
            child.close()
            crashed.join(30)
            assert crashed.exitcode == 97
            if hook_request is not None:
                consume_process_hook(hook_request, crashed, expected_exit=97)
            value = ExternalControl(coordinator).read(coordinator.connection, operation_id)
            assert value["operation_phase"] == "dispatch_authorized"
            backend_status = "unknown" if side == "before" else "completed"
            assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(operation_id)["status"] == backend_status
        finally:
            if crashed.is_alive():
                crashed.kill()
                crashed.join()
            parent.close()
        recovered = None
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=_reference_gap_watchdog,
                args=(child, str(coordinator.root), operation_id))
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
        response, phase, status, owner = recovered
        assert phase == "external_final_evidence_committed" and owner == "interrupt"
        expected = ("committed", "not_applicable", "running", "interrupted") if outcome == "committed_result_replay" else (
            "recovery_required", "unavailable", None, "recovery_required")
        assert (response["operation_status"], response["terminal_closure"], response["run_status"], status) == expected
        assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(operation_id)["status"] == backend_status
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        return {"schema_version": "0.1", "events": [
            event("backend_dispatch_cut", phase=boundary, stage=side,
                  source="dispatch_authorized", outcome=outcome),
            event("original_operation_stopped", phase=phase, status=status, owner=owner,
                  target="backend_" + backend_status, guard="no_redispatch"),
            event("watchdog_result_replayed", phase=phase, status=response["operation_status"],
                  owner=owner, target=response["terminal_closure"], guard="same_original_operation"),
        ]}
    finally:
        coordinator.close()


def _dispatch_integrity_client(pipe, output, operation_id):
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0))
    try:
        backend = RefuseRedispatch(coordinator.root / "fake_backend", clock=lambda: 140)
        containment = DeterministicContainment(coordinator.root / "containment")
        dispatch = ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                                    backend.read_receipt, backend.read_result)
        try:
            dispatch.dispatch()
        except ControlIntegrityError as error:
            rejected = str(error)
        else:
            raise AssertionError("Changed Task was accepted by original dispatch")
        final = ExternalControl(coordinator).read(coordinator.connection, operation_id)
        pipe.send((rejected, final["operation_phase"], final["operation_status"],
                   final["resolution_owner"]))
    finally:
        coordinator.close()
        pipe.close()


def dispatch_integrity_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary == "external.backend_dispatch" and side in ("before", "after")
    assert outcome == "integrity_conflict"
    coordinator, run_root, operation_id = _prepared_dispatch_source()
    context = multiprocessing.get_context("spawn")
    try:
        parent, child = context.Pipe()
        crashed = context.Process(target=_dispatch_client, args=(child, str(coordinator.root), operation_id),
            kwargs={"crash": True, "hook_request": hook_request, "side": side})
        try:
            crashed.start()
            child.close()
            crashed.join(30)
            assert crashed.exitcode == 97
            if hook_request is not None:
                consume_process_hook(hook_request, crashed, expected_exit=97)
            saved = ExternalControl(coordinator).read(coordinator.connection, operation_id)
            assert saved["operation_phase"] == "dispatch_authorized"
            backend_status = "unknown" if side == "before" else "completed"
            assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(operation_id)["status"] == backend_status
            task = run_root / "code_agent_control" / saved["attempt_id"] / "code_agent_task.json"
            task.write_bytes(b"{}")
        finally:
            if crashed.is_alive():
                crashed.kill()
                crashed.join()
            parent.close()
        recovered = None
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=_dispatch_integrity_client,
                args=(child, str(coordinator.root), operation_id))
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
        rejected, phase, status, owner = recovered
        assert rejected
        assert (phase, status, owner) == ("dispatch_authorized", "active", None)
        stopped = None
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=_reference_gap_watchdog,
                args=(child, str(coordinator.root), operation_id))
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == 0 and parent.poll(2)
                result = parent.recv()
                if stopped is None:
                    stopped = result
                else:
                    assert result == stopped
            finally:
                if process.is_alive():
                    process.kill()
                    process.join()
                parent.close()
        response, final_phase, final_status, final_owner = stopped
        assert (response["operation_status"], response["terminal_closure"], response["run_status"]) == (
            "recovery_required", "unavailable", None)
        assert (final_phase, final_status, final_owner) == (
            "external_final_evidence_committed", "recovery_required", "interrupt")
        assert ExternalControl(coordinator).read(coordinator.connection, operation_id)["proof_kind"] == "unavailable"
        assert task.read_bytes() == b"{}"
        assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(operation_id)["status"] == backend_status
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        return {"schema_version": "0.1", "events": [
            event("backend_dispatch_cut", phase=boundary, stage=side,
                  source="dispatch_authorized", outcome=outcome),
            event("original_authority_rejected", phase=phase, status="rejected", owner="original_producer",
                  target="backend_" + backend_status, guard="no_redispatch"),
            event("original_operation_stopped", phase=final_phase, status=final_status, owner=final_owner,
                  target="backend_" + backend_status, guard="unavailable_no_redispatch"),
        ]}
    finally:
        coordinator.close()


def _prepared_dispatch_source(*, publish=True):
    repository, base = immutable_base_repository()
    witness = task_trace_witness(base)
    task, manifest = witness["task"], witness["manifest"]
    run_root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    coordinator = Coordinator(run_root.parent.parent, clock=FakeClock(100, 0))
    operation_id = task["producer_operation_id"]
    try:
        prestart = CodePrestart(coordinator, operation_id, "host", 1)
        prestart.commit_task(task)
        prestart.commit_manifest(manifest)
        prestart.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
            "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10,
            config_digest=digest("config"))
        prestart.commit_core()
        prestart.materialize_workspace(repository)
        locator = {key: task[key] for key in ("case_id", "run_id")}
        target = task["attempt_id"]
        if not publish:
            return coordinator, run_root, operation_id
        ControlPlane(coordinator, worker_id="host").publish_pause(
            PublishPauseRequest(locator, "external_result", target, target,
                {"kind": "external_result", "producer_operation_id": operation_id},
                {"actor_type": "human", "scopes": ["resume"]}, "publish-uncertain-dispatch"),
            actor=ActorContext("operator", "human", ("control.internal",)))
        return coordinator, run_root, operation_id
    except BaseException:
        coordinator.close()
        raise


def test_uncertain_dispatch_restarts_with_lookup_only():
    uncertain_dispatch_recovery()


def _reference_client(pipe, output, operation_id, boundary, side, stage, *, crash, hook_request,
                      expect_rejection=False, stop_unavailable=False):
    def observer(name, observed_side, value):
        if crash and (name, observed_side) == (boundary, side):
            os._exit(97)

    if hook_request is not None:
        observer.production_hooks = {(boundary, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0), observer=observer)
    backend_root = coordinator.root / "fake_backend"
    backend = (FakeCodingBackend(backend_root, operation_scenarios={operation_id: "completed"},
                                fixtures={"completed": {"status": "completed", "result": b"{}"}},
                                clock=lambda: 100) if crash and stage == "receipt" else
               RefuseRedispatch(backend_root, clock=lambda: 101))
    containment = DeterministicContainment(coordinator.root / "containment",
        fault_by_operation={operation_id: {"kill_all": False}} if stop_unavailable else None)
    try:
        dispatch = ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                                    backend.read_receipt, backend.read_result)
        try:
            result = dispatch.dispatch() if stage == "receipt" else dispatch.publish_result_reference()
        except ControlIntegrityError as error:
            if not expect_rejection:
                raise
            pipe.send({"rejected": str(error)})
        else:
            assert not expect_rejection
            pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def reference_publication_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert outcome in ("materializable_publication_prefix", "committed_result_replay", "integrity_conflict")
    stage = "receipt" if boundary in ("external.receipt", "external.dispatch_receipt_committed") else "result"
    coordinator, run_root, operation_id = _prepared_dispatch_source()
    context = multiprocessing.get_context("spawn")
    try:
        if stage == "result":
            backend = FakeCodingBackend(coordinator.root / "fake_backend",
                operation_scenarios={operation_id: "completed"},
                fixtures={"completed": {"status": "completed", "result": b"{}"}}, clock=lambda: 100)
            containment = DeterministicContainment(coordinator.root / "containment")
            ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                             backend.read_receipt, backend.read_result).dispatch()
        predecessor = "dispatch_authorized" if stage == "receipt" else "dispatch_receipt_committed"
        recovered = None
        for crash in ((True, False) if outcome == "integrity_conflict" else (True, False, False)):
            parent, child = context.Pipe()
            process = context.Process(target=_reference_client,
                args=(child, str(coordinator.root), operation_id, boundary, side, stage),
                kwargs={"crash": crash, "hook_request": hook_request if crash else None,
                        "expect_rejection": outcome == "integrity_conflict" and not crash})
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == (97 if crash else 0)
                if crash:
                    if hook_request is not None:
                        consume_process_hook(hook_request, process, expected_exit=97)
                    saved = ExternalControl(coordinator).read(coordinator.connection, operation_id)
                    assert saved["operation_phase"] == predecessor
                    if outcome == "integrity_conflict":
                        directory = run_root / "code_agent_control" / saved["attempt_id"]
                        tampered = directory / ("backend_dispatch_receipt.json" if stage == "receipt"
                                                else "code_agent_external_result.json")
                        tampered.write_bytes(b'{"foreign":true}\n')
                else:
                    assert parent.poll(2)
                    result = parent.recv()
                    if outcome == "integrity_conflict":
                        assert "rejected" in result and result["rejected"]
                        continue
                    if recovered is None:
                        recovered = result
                    else:
                        assert result == recovered
            finally:
                if process.is_alive():
                    process.kill()
                    process.join()
                parent.close()
        final = ExternalControl(coordinator).read(coordinator.connection, operation_id)
        target = "dispatch_receipt_committed" if stage == "receipt" else "result_reference_committed"
        if outcome == "integrity_conflict":
            assert final["operation_phase"] == predecessor
            assert tampered.read_bytes() == b'{"foreign":true}\n'
            assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(operation_id)["status"] == "completed"
            assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
            return {"schema_version": "0.1", "events": [
                event("external_reference_cut", phase=boundary, stage=side, source=predecessor,
                      outcome=outcome),
                event("foreign_reference_rejected", phase=predecessor, status="rejected",
                      owner="original_producer", target=stage, guard="no_redispatch"),
            ]}
        assert final["operation_phase"] == target
        reference = final["dispatch_receipt_reference" if stage == "receipt" else "result_reference"]
        content = (run_root / reference).read_bytes()
        if stage == "receipt":
            assert content == canonical_bytes(recovered)
        else:
            assert content == b"{}" and recovered["digest"] == final["result_digest"]
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        events = [
            event("external_reference_cut", phase=boundary, stage=side, source=predecessor,
                  outcome=outcome),
            event("original_reference_materialized", phase=target, status="completed",
                  owner="original_producer", target=stage, guard="lookup_fetch_only"),
        ]
        if outcome == "committed_result_replay":
            events.append(event("original_reference_replayed", phase=target, status="completed",
                                owner="original_producer", target=stage, guard="same_reference_bytes"))
        return {"schema_version": "0.1", "events": events}
    finally:
        coordinator.close()


def _reference_gap_watchdog(pipe, output, operation_id):
    coordinator = Coordinator(Path(output), clock=FakeClock(140, 40))
    try:
        backend = RefuseRedispatch(coordinator.root / "fake_backend", clock=lambda: 140)
        containment = DeterministicContainment(coordinator.root / "containment")
        result = CodeWatchdog(coordinator, backend, containment, backend.read_receipt).enforce(operation_id)
        final = ExternalControl(coordinator).read(coordinator.connection, operation_id)
        pipe.send((result, final["operation_phase"], final["operation_status"], final["resolution_owner"]))
    finally:
        coordinator.close()
        pipe.close()


def reference_publication_domain_gap(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert outcome == "non_materializable_domain_gap"
    stage = "receipt" if boundary in ("external.receipt", "external.dispatch_receipt_committed") else "result"
    coordinator, _, operation_id = _prepared_dispatch_source()
    context = multiprocessing.get_context("spawn")
    try:
        if stage == "result":
            backend = FakeCodingBackend(coordinator.root / "fake_backend",
                operation_scenarios={operation_id: "completed"},
                fixtures={"completed": {"status": "completed", "result": b"{}"}}, clock=lambda: 100)
            containment = DeterministicContainment(coordinator.root / "containment",
                fault_by_operation={operation_id: {"kill_all": False}})
            ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                             backend.read_receipt, backend.read_result).dispatch()
        predecessor = "dispatch_authorized" if stage == "receipt" else "dispatch_receipt_committed"
        parent, child = context.Pipe()
        crashed = context.Process(target=_reference_client,
            args=(child, str(coordinator.root), operation_id, boundary, side, stage),
            kwargs={"crash": True, "hook_request": hook_request, "stop_unavailable": stage == "receipt"})
        try:
            crashed.start()
            child.close()
            crashed.join(30)
            assert crashed.exitcode == 97
            if hook_request is not None:
                consume_process_hook(hook_request, crashed, expected_exit=97)
            saved = ExternalControl(coordinator).read(coordinator.connection, operation_id)
            assert saved["operation_phase"] == predecessor
            assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(operation_id)["status"] == "completed"
        finally:
            if crashed.is_alive():
                crashed.kill()
                crashed.join()
            parent.close()
        recovered = None
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=_reference_gap_watchdog,
                args=(child, str(coordinator.root), operation_id))
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == 0
                assert parent.poll(2)
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
        response, phase, status, owner = recovered
        assert response["operation_status"] == "recovery_required"
        assert response["terminal_closure"] == "unavailable" and response["run_status"] is None
        assert (phase, status, owner) == ("external_final_evidence_committed", "recovery_required", "interrupt")
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        return {"schema_version": "0.1", "events": [
            event("external_reference_cut", phase=boundary, stage=side, source=predecessor,
                  outcome=outcome),
            event("original_operation_stopped", phase=phase, status=status, owner=owner,
                  target=stage, guard="unavailable_no_redispatch"),
        ]}
    finally:
        coordinator.close()
