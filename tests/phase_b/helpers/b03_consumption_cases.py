"""Canonical Code evidence at existing B02 durable consumption boundaries."""
from lqcd_agent.control.coordinator import read_regular
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import digest, loads

from .runtime_cases import exercise_phase_case


CONSUMPTION_PHASES = {
    "release.normal_delivery": "control.resume_run.continue_execution.resume_disposition_committed",
    "release.settlement": "control.resume_run.continue_execution.prestart_records_committed",
    "release.pause_consumed": "control.resume_run.continue_execution.pause_consumed_recorded",
    "release.binding_release": "control.resume_run.continue_execution.external_consumption_released",
    "release.final_checkpoint": "control.resume_run.continue_execution.stable_boundary_committed",
    "external.delivery_snapshot": "control.resume_run.continue_execution.resume_disposition_committed",
    "external.bundle_members": "invocation.artifact_projection",
    "external.bundle_registration": "invocation.artifact_registration",
    "external.bundle_current": "invocation.artifact_index_replace",
    "external.code_attempt_finished": "invocation.attempt_finished",
    "release.artifact_terminal": "invocation.artifact_registration",
    "release.attempt_terminal": "invocation.attempt_finished",
    "release.duplicate_proof": "control.resume_run.continue_execution.external_consumption_released",
    "release.recoverable_timeout": "control.resolve_external_interrupt.recoverable_timeout.canonical_failed_delivery_committed",
    "timeout_completion.authorization": "control.resolve_external_interrupt.recoverable_timeout.interrupted_code_invocation_authorized",
    "timeout_completion.attempt_started": "control.resolve_external_interrupt.recoverable_timeout.interrupted_code_attempt_started",
    "timeout_completion.artifact_registered": "control.resolve_external_interrupt.recoverable_timeout.interrupted_code_result_registered",
    "timeout_completion.attempt_finished": "control.resolve_external_interrupt.recoverable_timeout.interrupted_code_attempt_finished",
    "timeout_completion.final_checkpoint": "control.resolve_external_interrupt.recoverable_timeout.interrupted_code_checkpoint_committed",
}


def _canonical_evidence(coordinator, config, before_rows, recovered, *, duplicate=False):
    locator = config["request"]["run_locator"]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    before = loads(before_rows["external_operations"][0][-1])
    external = ExternalControl(coordinator)
    value = external.read(coordinator.connection, before["producer_operation_id"])
    assert value["producer_operation_id"] == before["producer_operation_id"]
    assert value["active_binding_generation"] == before["active_binding_generation"] == 1
    assert value["task_digest"] == before["task_digest"]
    if config["method"] == "resume_run":
        assert value["resolution_owner"] == before["resolution_owner"] == "normal"
        assert value["terminal_evidence_digest"] == before["terminal_evidence_digest"]
        assert value["result_digest"] == before["result_digest"]
    if recovered["operation_status"] != "committed":
        assert recovered["run_status"] is None
        return
    assert recovered["run_status"] == "running" and recovered["terminal_closure"] == "not_applicable"
    proof = value["consumption_release"]
    assert value["active_binding_status"] == "released" and proof["release_kind"] == "external_consumed"
    assert proof["consumption_operation_id"] == recovered["operation_id"]
    records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
    settled = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"
               and r["payload"]["resource_operation_id"] == value["reservation_id"]]
    consumed = [r for r in records if r["record_type"] == "pause" and r["event"] == "pause_consumed"]
    attempts = [r for r in records if r["record_type"] == "attempt" and r["attempt_id"] == value["attempt_id"]]
    assert len(settled) == len(consumed) == 1
    assert [r["event"] for r in attempts] == ["scheduled", "started", "finished"]
    assert settled[0]["event_index"] < consumed[0]["event_index"] < attempts[-1]["event_index"]
    assert proof["resource_settlement_digest"] == digest(settled[0])
    assert proof["pause_consumed_head"] == digest(consumed[0])
    assert proof["terminal_code_attempt_head"] == digest(attempts[-1])
    index = loads(read_regular(root / "artifact_index.json"))
    pointer = index["current"]["code"]
    assert pointer["attempt_id"] == value["attempt_id"] and pointer["attempt_kind"] == "code_agent"
    assert proof["canonical_code_artifact_head"] == index["artifact_head"] == attempts[-1]["artifact_head"]
    result = loads(read_regular(root / "attempts" / value["attempt_id"] / "code_agent_result.json"))
    timeout = config["method"] == "resolve_external_interrupt"
    assert result["result_origin"] == ("host_timeout" if timeout else "backend_delivery")
    assert result["status"] == ("failed" if timeout else "needs_input") and result["usable"] is False
    assert not any(r["record_type"] == "transition" and r["source_attempt_id"] == value["attempt_id"] for r in records)
    control = loads(coordinator.connection.execute("SELECT value FROM run_controls").fetchone()[0])
    validate_run_root(root, manifest=control["manifest"], projection=control["projection"])
    assert external.attached(coordinator.connection, locator) == []
    assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
    if duplicate:
        from lqcd_agent.control.strict_json import ControlIntegrityError
        saved = external.read(coordinator.connection, value["producer_operation_id"])
        stable_ledger = read_regular(root / "execution_history.jsonl")
        try:
            with coordinator.transaction() as db:
                external.release_consumption(db, coordinator.get(recovered["operation_id"], db=db), proof)
        except ControlIntegrityError as error:
            assert str(error) == "External binding release CAS lost"
        else:
            raise AssertionError("A duplicate release performed another CAS")
        assert external.read(coordinator.connection, value["producer_operation_id"]) == saved
        assert read_regular(root / "execution_history.jsonl") == stable_ledger


def consumption_recovery(case_id):
    from functools import partial
    boundary, side, outcome = case_id.rsplit(".", 2)
    phase = CONSUMPTION_PHASES[boundary]
    fixture_phase = ("control.resume_run.continue_execution.external_consumption_released"
                     if phase.startswith("invocation.") else phase)
    return exercise_phase_case(case_id, fixture_case=f"{fixture_phase}.{side}.{outcome}",
                               fault_point=phase,
                               arm_after=["invocation.artifact_registration", "after"]
                               if boundary == "external.bundle_current" else None,
                               evidence_check=partial(
                                   _canonical_evidence, duplicate=boundary == "release.duplicate_proof"))
