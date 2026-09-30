"""Frozen stop evidence and monitor takeover recover one original producer."""
from harness.trace import event
from lqcd_agent.control.coordinator import read_regular
from lqcd_agent.control.operations import ExternalControl
from test_external_operation_recovery import _backend_cancel_client, _running_stop_source, RefuseRedispatch
from .b03_analysis_execution_cases import _run


BOUNDARIES = ("external.termination_evidence", "external.termination_evidence_committed",
              "external.external_final_evidence_committed", "external.watchdog_takeover")


def stop_publication_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    coordinator, root, producer = _running_stop_source(containment_fault=outcome == "non_materializable_domain_gap")
    source = ExternalControl(coordinator).read(coordinator.connection, producer)
    args = (str(coordinator.root), producer, side)

    def run(crash=False, hook=None):
        return _run(_backend_cancel_client, args, kwargs={"crash": crash, "hook_request": hook, "boundary": boundary},
                    crash=crash, hook_request=hook)

    try:
        run(True, hook_request)
        cut = ExternalControl(coordinator).read(coordinator.connection, producer)
        prior = "dispatch_receipt_committed" if boundary == "external.watchdog_takeover" else (
            "termination_evidence_committed" if boundary == "external.external_final_evidence_committed" else "interrupt_stop_intent_committed")
        assert cut["operation_phase"] == prior and cut["producer_operation_id"] == source["producer_operation_id"]
        directory = root / "code_agent_control" / cut["attempt_id"]
        candidates = {name: read_regular(directory / name) for name in
                      ("termination_evidence.json", "external_final_evidence.json") if (directory / name).exists()}
        if outcome == "integrity_conflict":
            task = directory / "code_agent_task.json"
            task.write_bytes(b"{}")
        first, second = run(), run()
        assert first == second
        response, phase, owner, missing = first
        assert phase == "external_final_evidence_committed" and owner == "interrupt", first
        positive = outcome in ("committed_result_replay", "materializable_publication_prefix")
        assert (response["operation_status"], response["terminal_closure"], response["run_status"]) == (
            ("committed", "not_applicable", "running") if positive else ("recovery_required", "unavailable", None))
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["dispatch_receipt_digest"] == source["dispatch_receipt_digest"]
        assert value["resolution_owner_operation_id"] == response["operation_id"]
        assert all(read_regular(directory / name) == raw for name, raw in candidates.items())
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        assert RefuseRedispatch(coordinator.root / "fake_backend").lookup(producer)["status"] == "cancelled"
        if outcome == "integrity_conflict":
            assert task.read_bytes() == b"{}"
        return {"schema_version": "0.1", "events": [
            event("external_stop_publication_cut", phase=boundary, stage=side, outcome=outcome, source=prior,
                  accepted=bool(candidates), owner="original_interrupt"),
            event("external_stop_publication_recovered", phase=phase, status=response["operation_status"], owner=owner,
                  target=response["terminal_closure"], guard=proof["proof_kind"]),
            event("external_stop_publication_replayed", accepted=True, guard="immutable_candidate_no_redispatch")]
        }
    finally:
        coordinator.close()
