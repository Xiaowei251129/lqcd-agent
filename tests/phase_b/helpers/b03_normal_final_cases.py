"""Normal winner publication recovers only one original Backend operation."""
from functools import partial
import multiprocessing
import os
from pathlib import Path

from harness.pytest_evidence import consume_process_hook, production_hook
from harness.trace import event
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.external_operation import CodeWatchdog, ExternalDispatch, ExternalNormalFinal
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import ControlIntegrityError
from test_external_operation_recovery import RefuseRedispatch, UnavailableLookupBackend
from .canonical_code import canonical_source


NORMAL_FINAL_BOUNDARIES = ("external.workspace_seal", "external.final_evidence", "external.resolution_cas")


def _normal_final_client(pipe, output, producer, boundary, side, audit, patch, *, crash, hook_request, stop=False):
    def observer(name, observed_side, value):
        if crash and (name, observed_side) == (boundary, side):
            os._exit(97)

    if hook_request is not None:
        observer.production_hooks = {(boundary, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(140, 40) if stop else FakeClock(100, 0), observer=observer)
    try:
        backend = (UnavailableLookupBackend if stop else RefuseRedispatch)(
            coordinator.root / "fake_backend", clock=lambda: 140 if stop else 100)
        containment = DeterministicContainment(coordinator.root / "containment")
        dispatch = ExternalDispatch(coordinator, producer, "host", 1, backend, containment,
                                    backend.read_receipt, backend.read_result)
        if stop:
            result = CodeWatchdog(coordinator, backend, containment, backend.read_receipt).enforce(producer)
            pipe.send({"response": result, "external": ExternalControl(coordinator).read(coordinator.connection, producer)})
        else:
            try:
                result = ExternalNormalFinal(dispatch, coordinator.root / "base_repository").commit(tool_audit=audit, patch=patch)
            except (ControlIntegrityError, OSError) as error:
                pipe.send({"rejected": str(error)})
            else:
                pipe.send({"external": result})
    finally:
        coordinator.close()
        pipe.close()


def normal_final_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in NORMAL_FINAL_BOUNDARIES
    coordinator, _, _, locator, dispatch, _, audit, patch = canonical_source(success=True, finalize=False)
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    producer = dispatch.producer
    context = multiprocessing.get_context("spawn")

    def run(*, crash=False, hook=None, stop=False):
        parent, child = context.Pipe()
        process = context.Process(target=_normal_final_client,
            args=(child, str(coordinator.root), producer, boundary, side, audit, patch),
            kwargs={"crash": crash, "hook_request": hook, "stop": stop})
        try:
            process.start()
            child.close()
            result = None
            if not crash:
                assert parent.poll(30)
                result = parent.recv()
            process.join(30)
            assert process.exitcode == (97 if crash else 0)
            if crash:
                if hook is not None:
                    consume_process_hook(hook, process, expected_exit=97)
            else:
                return result
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()

    try:
        before = read_regular(root / "execution_history.jsonl")
        source = ExternalControl(coordinator).read(coordinator.connection, producer)
        run(crash=True, hook=hook_request)
        cut = ExternalControl(coordinator).read(coordinator.connection, producer)
        assert cut == source and cut["operation_phase"] == "result_reference_committed"
        directory = root / "code_agent_control" / source["attempt_id"]
        candidate = directory / "external_final_evidence.json"
        present = candidate.exists()
        assert present is (boundary == "external.resolution_cas" or boundary == "external.final_evidence" and side == "after")
        saved_candidate = candidate.read_bytes() if present else None
        if outcome == "integrity_conflict":
            member = directory / "code_agent_task.json"
            member.write_bytes(b"{}")
            first = run()
            assert first.get("rejected") and ExternalControl(coordinator).read(coordinator.connection, producer) == cut
            second = run()
            assert first == second and member.read_bytes() == b"{}"
        else:
            first = run(stop=outcome == "non_materializable_domain_gap")
            second = run(stop=outcome == "non_materializable_domain_gap")
            assert first == second
            value = first["external"]
            if outcome == "non_materializable_domain_gap":
                assert first["response"]["terminal_closure"] == "unavailable", first
                assert first["response"]["run_status"] is None
                assert value["operation_phase"] == "external_final_evidence_committed" and value["proof_kind"] == "unavailable", first["response"]
            else:
                assert value["resolution_owner"] == "normal" and value["proof_kind"] == "safe_stop"
                assert value["dispatch_receipt_digest"] == source["dispatch_receipt_digest"]
                assert value["result_digest"] == source["result_digest"]
                final, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
                assert final == value and proof["result_digest"] == source["result_digest"]
                assert (root / value["terminal_evidence_reference"]).read_bytes() == candidate.read_bytes()
        if saved_candidate is not None:
            assert candidate.read_bytes() == saved_candidate
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        assert read_regular(root / "execution_history.jsonl").startswith(before)
        assert RefuseRedispatch(coordinator.root / "fake_backend").lookup(producer)["status"] == "completed"
        return {"schema_version": "0.1", "events": [
            event("normal_final_cut", phase=boundary, stage=side, outcome=outcome,
                  source="result_reference_committed", accepted=present, owner="original_producer"),
            event("normal_final_recovered", status="rejected" if outcome == "integrity_conflict" else
                  first["response"]["operation_status"] if outcome == "non_materializable_domain_gap" else "completed",
                  owner="original_producer" if outcome == "integrity_conflict" else first["external"]["resolution_owner"],
                  target="unavailable" if outcome == "non_materializable_domain_gap" else "same_source",
                  guard="no_redispatch_immutable_candidate"),
            event("normal_final_replayed", accepted=True, guard="same_original_operation")]
        }
    finally:
        coordinator.close()
