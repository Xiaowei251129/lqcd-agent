"""Real Fake Backend stop intents and late canonical timeout publications."""
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import loads
from test_external_operation_recovery import RefuseRedispatch

from .b03_consumption_cases import _canonical_evidence
from .runtime_cases import exercise_phase_case


STOP_TIMEOUT_PHASES = {
    "external.cancel_intent_committed": "control.cancel_pause.not_applicable.cancel_arbitrated",
    "external.interrupt_stop_intent_committed": "control.resolve_external_interrupt.recoverable_timeout.interrupt_and_pause_ownership_reserved",
    "timeout_completion.late_integrity": "control.resolve_external_interrupt.recoverable_timeout.external_consumption_released",
    "timeout_completion.late_unavailable": "control.resolve_external_interrupt.recoverable_timeout.interrupted_code_checkpoint_committed",
    "timeout_completion.no_redispatch": "control.resolve_external_interrupt.recoverable_timeout.interrupted_code_invocation_authorized",
}


def _stopped_original(coordinator, config, before_rows, recovered):
    source = loads(before_rows["external_operations"][0][-1])
    value = ExternalControl(coordinator).read(coordinator.connection, source["producer_operation_id"])
    assert value["producer_operation_id"] == source["producer_operation_id"]
    assert value["task_digest"] == source["task_digest"] and value["active_binding_generation"] == 1
    assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
    if config["method"] == "resolve_external_interrupt" and config["request"]["reason"] == "operation_timeout":
        _canonical_evidence(coordinator, config, before_rows, recovered)
    if recovered["operation_status"] == "committed":
        assert value["resolution_owner"] == ("cancel" if config["method"] == "cancel_pause" else "interrupt")
        assert value["resolution_owner_operation_id"] == recovered["operation_id"]
        assert value["operation_phase"] == "external_final_evidence_committed" and value["proof_kind"] == "safe_stop"
        assert RefuseRedispatch(coordinator.root / "fake_backend").lookup(value["producer_operation_id"])["status"] == "cancelled"
    if config["late_timeout"]:
        assert RefuseRedispatch(coordinator.root / "fake_backend").lookup(value["producer_operation_id"])["status"] == "cancelled"


def stop_timeout_recovery(case_id):
    boundary, side, outcome = case_id.rsplit(".", 2)
    phase = STOP_TIMEOUT_PHASES[boundary]

    def evidence(coordinator, config, before_rows, recovered):
        config["late_timeout"] = boundary.startswith("timeout_completion.")
        _stopped_original(coordinator, config, before_rows, recovered)

    return exercise_phase_case(case_id, fixture_case=f"{phase}.{side}.{outcome}", fault_point=phase,
        canonical_backend_stop=True, evidence_check=evidence)
