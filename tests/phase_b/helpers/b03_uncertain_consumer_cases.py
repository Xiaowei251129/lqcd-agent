"""Canonical consumer cuts with a distinct deterministic Host stop witness."""
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.coordinator import read_regular
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.pause import ConsumerStopObservation
from lqcd_agent.control.strict_json import ControlIntegrityError, loads
from test_external_consumption_control import CanonicalDomainConsumer

from .runtime_cases import exercise_phase_case


UNCERTAIN_PHASES = {
    "external.code_attempt_started": "invocation.attempt_started",
    "external.trusted_verification": "external.trusted_verification",
}


class CanonicalConsumerHost(CanonicalDomainConsumer):
    """Fake Host evidence is bound to the consumer, never the Backend worker."""

    def __init__(self, coordinator, repository, *, safe=True, reject=False):
        super().__init__(coordinator, repository)
        self.safe = safe
        self.reject = reject

    def consume_external(self, identity, binding, port):
        key = "consumer_" + port.capability_id
        containment = DeterministicContainment(self.coordinator.root / "consumer_containment",
            fault_by_operation={key: {"kill_all": False}} if not self.safe else None)
        containment.start(key, identity["attempt_id"] + "_consumer")
        if self.reject:
            self.preflight_delivery(binding)
            raise ControlIntegrityError("Deterministic Host consumer integrity rejection")
        return super().consume_external(identity, binding, port)

    def stop_consumption(self, coordinator, intent):
        assert coordinator is self.coordinator
        capability = intent["consumer_capability_id"]
        value = InvocationLeases(coordinator).get(capability)[1]
        assert value["state"] == "uncertain" and value["invocation_epoch"] > 1
        key = "consumer_" + capability
        operation = coordinator.get(intent["control_operation_id"])
        assert key != operation["reservation"]["target_prestart_closure"]["external"]["value"]["producer_operation_id"]
        containment = DeterministicContainment(coordinator.root / "consumer_containment")
        if containment.never_started(key):
            assert not value.get("verification_intents")
            proof = {"termination_or_not_dispatched": {"tag": "not_dispatched"}, "write_lease_revocation": True,
                     "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}
        else:
            containment.revoke_writes(key)
            containment.terminate(key)
            containment.kill_all(key)
            containment.drain(key)
            proof = containment.proof(key)
        return ConsumerStopObservation(proof, {})


def _failure_evidence(coordinator, config, before_rows, recovered):
    source = loads(before_rows["external_operations"][0][-1])
    value = ExternalControl(coordinator).read(coordinator.connection, source["producer_operation_id"])
    assert value["resolution_owner"] == source["resolution_owner"] == "normal"
    assert value["terminal_evidence_digest"] == source["terminal_evidence_digest"]
    assert value["result_digest"] == source["result_digest"]
    closure = loads(coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0])
    assert closure["terminal_closure_owner_operation_id"] == recovered["operation_id"]
    cap = InvocationLeases(coordinator).get("capability_" + recovered["operation_id"])[1]
    assert cap["state"] == "uncertain" and cap.get("completion_intent") is None
    if recovered["operation_status"] == "committed":
        assert recovered["run_status"] == "failed" and value["active_binding_status"] == "released"
        root = coordinator.root / source["run_locator"]["case_id"] / source["run_locator"]["run_id"]
        records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
        assert not any(r["record_type"] == "transition" and r["source_attempt_id"] == source["attempt_id"] for r in records)
        assert loads(read_regular(root / "artifact_index.json"))["current"]["code"] is None
        pending = {r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved"}
        settled = [r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"]
        assert set(settled) == pending and len(settled) == len(set(settled))
    else:
        assert recovered["run_status"] is None and closure["terminal_closure"] == "unavailable"
    assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1


def uncertain_consumer_recovery(case_id):
    boundary, side, outcome = case_id.rsplit(".", 2)
    phase = UNCERTAIN_PHASES[boundary]
    fixture = "control.resume_run.continue_execution.external_consumption_released"
    return exercise_phase_case(case_id, fixture_case=f"{fixture}.{side}.{outcome}", fault_point=phase,
        canonical_resume="success", canonical_consumer_stop={"safe": outcome != "non_materializable_domain_gap"},
        evidence_check=_failure_evidence)
