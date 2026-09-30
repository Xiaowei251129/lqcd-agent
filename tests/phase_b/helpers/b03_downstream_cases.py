"""Generic control admission after exact canonical Code consumption release."""
from lqcd_agent.code_agent.external_operation import ExternalProducer
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.coordinator import read_regular
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import digest, loads

from .runtime_cases import exercise_phase_case


DOWNSTREAM_PHASES = {
    "release.outbound_transition": "control.advance_run.not_applicable.transition_heads_verified",
    "release.second_code_operation": "control.advance_run.not_applicable.invocation_capability_prepared",
    "release.end": "control.advance_run.not_applicable.terminal_transition_committed",
    "consumption_failure.detached_close_after_release": "control.close_run.not_applicable.terminal_checkpoint_committed",
}


def _released_source(coordinator, config, before_rows, recovered):
    external = ExternalControl(coordinator)
    source = loads(before_rows["external_operations"][0][-1])
    value = external.read(coordinator.connection, source["producer_operation_id"])
    assert value == source and value["active_binding_status"] == "released"
    proof = value["consumption_release"]
    assert proof["release_kind"] == "external_consumed"
    resume = coordinator.get(proof["consumption_operation_id"])
    assert resume["status"] == "committed" and resume["operation_type"] == "resume_run"
    assert recovered["operation_id"] != resume["operation_id"]
    locator = value["run_locator"]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    if recovered["operation_status"] != "committed":
        assert recovered["run_status"] is None
        return
    records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
    finished = [r for r in records if r["record_type"] == "attempt" and r["event"] == "finished" and
                r["attempt_id"] == value["attempt_id"]]
    settled = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled" and
               r["payload"]["resource_operation_id"] == value["reservation_id"]]
    assert len(finished) == len(settled) == 1
    assert digest(finished[0]) == proof["terminal_code_attempt_head"]
    assert digest(settled[0]) == proof["resource_settlement_digest"]
    if config["method"] == "close_run":
        assert recovered["run_status"] == "halted" and recovered["terminal_closure"] == "committed"
        assert external.attached(coordinator.connection, locator) == []
    else:
        transitions = [r for r in records if r["record_type"] == "transition" and
                       r["source_attempt_id"] == config["request"]["source_attempt_id"]]
        assert len(transitions) == 1 and transitions[0]["event_index"] > finished[0]["event_index"]
        if config["route"] is None:
            assert transitions[0]["target_node"] is None and transitions[0]["target_attempt_id"] is None
            assert recovered["run_status"] == "running" and recovered["terminal_closure"] == "not_applicable"
        elif config["route"] == "code_agent":
            scheduled = next(r for r in records if r["record_type"] == "attempt" and r["event"] == "scheduled" and
                             r["attempt_id"] == transitions[0]["target_attempt_id"])
            prior = loads(read_regular(root / "attempts" / value["attempt_id"] / "code_agent_result.json"))
            assert prior["status"] == "needs_input" and prior["usable"] is False
            assert scheduled["input_references"]["current_artifact_ids"] == {"code":
                next(r["artifact_id"] for r in [loads(line) for line in read_regular(root / "artifact_history.jsonl").splitlines()]
                     if r["event"] == "registered" and r["attempt_id"] == value["attempt_id"])}
            reservation = ExternalProducer(coordinator).reserve(recovered["result"]["capability_id"], backend_kind="fake",
                backend_version="0.1", hard_deadline=200, worker_id="second", lease_seconds=10)
            duplicate = ExternalProducer(coordinator).reserve(recovered["result"]["capability_id"], backend_kind="fake",
                backend_version="0.1", hard_deadline=200, worker_id="second", lease_seconds=10)
            assert reservation == duplicate and reservation["producer_operation_id"] != value["producer_operation_id"]
            assert reservation["workspace_id"] != value["workspace_id"]
            assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 2
            assert reservation["dispatch_receipt_digest"] is None
    assert external.read(coordinator.connection, value["producer_operation_id"]) == source


def downstream_recovery(case_id):
    boundary, side, outcome = case_id.rsplit(".", 2)
    phase = DOWNSTREAM_PHASES[boundary]
    return exercise_phase_case(case_id, fixture_case=f"{phase}.{side}.{outcome}", fault_point=phase,
        canonical_advance="needs_input", route_target="code_agent" if boundary == "release.second_code_operation" else None,
        evidence_check=_released_source)
