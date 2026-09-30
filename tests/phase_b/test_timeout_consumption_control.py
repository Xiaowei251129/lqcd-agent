"""B02 safe-timeout materialization with explicit external/domain bytes only."""
from pathlib import Path
import tempfile

import pytest

from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.operations import AdvanceRunRequest, ExternalControl
from lqcd_agent.control.pause import ResolveExternalInterruptRequest, TimeoutDelivery
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from test_advance_control import SyntheticDomainRoute
from test_external_control import SyntheticExternalStop, external_pause_request, external_source
from test_bootstrap_control import start
from test_invocation_artifacts import ArtifactTarget
from lqcd_agent.control.interfaces import ActorContext
from helpers.canonical_code import timeout_prestart_source
from lqcd_agent.code_agent.artifacts import timeout_bundle
from lqcd_agent.code_agent.schemas import validate_manifest, validate_task
from lqcd_agent.control.coordinator import read_regular


class DomainTimeout(SyntheticExternalStop):
    def __init__(self, coordinator=None, **kwargs):
        super().__init__(**kwargs)
        self.coordinator = coordinator
        self.deliveries = 0

    def prepare_timeout_delivery(self, view):
        self.deliveries += 1
        assert view["external"]["resolution_owner"] == "interrupt"
        value = view["external"]
        root = self.coordinator.root / value["run_locator"]["case_id"] / value["run_locator"]["run_id"]
        directory = root / "code_agent_control" / value["attempt_id"]
        task = validate_task(read_regular(directory / "code_agent_task.json")).value
        manifest = validate_manifest(read_regular(directory / "workspace_manifest.json"), task).value
        members, result = timeout_bundle(task, manifest, value, view["final"],
                                         dispatch_phase=view["original_dispatch"]["external_phase"])
        return TimeoutDelivery({name: content.decode() for name, content in members.items()},
            {"code_change_summary_path": None, "tests_status_path": None,
             "code_agent_task_path": "code_agent_task.json", "code_agent_result_path": "code_agent_result.json",
             "code_change_manifest_path": "change_manifest.json",
             "code_verification_results_path": "verification_results.json"}, result["status"],
            dict(PROTOCOL["state_machines"]["control_operation"]["recoverable_code_consumption_contract"]["result"]))


@pytest.fixture
def timeout_source():
    coordinator, plane, actor, locator, root, task, manifest = timeout_prestart_source()
    producer = task["producer_operation_id"]
    trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
    (root / "timeout_trigger.json").write_bytes(canonical_bytes(trigger))
    request = ResolveExternalInterruptRequest(locator, producer, "operation_timeout", "timeout_trigger.json", digest(trigger))
    plane.external_adapter = DomainTimeout(coordinator)
    try:
        yield coordinator, plane, actor, locator, root, request
    finally:
        coordinator.close()


def test_safe_timeout_consumes_same_failed_attempt_before_outbound(timeout_source):
    from harness import pytest_evidence
    from harness.pytest_evidence import observe
    coordinator, plane, actor, locator, root, request = timeout_source
    result = plane.resolve_external_interrupt(request, actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "running" and result["domain_status"] == "failed", result
    assert result["terminal_closure"] == "not_applicable"
    assert plane.external_adapter.calls == 1 and plane.external_adapter.deliveries == 1
    assert plane.resolve_external_interrupt(request, actor=actor) == result
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    target = [r for r in records if r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002"]
    assert [r["status"] for r in target] == ["scheduled", "running", "failed"]
    assert target[-1]["error"]["type"] == "OperationTimeout"
    assert not any(r["record_type"] == "transition" and r["source_attempt_id"] == "attempt_000002" for r in records)
    assert ExternalControl(coordinator).attached(coordinator.connection, locator) == []
    capability = InvocationLeases(coordinator).get("capability_" + result["operation_id"])[1]
    assert capability["state"] == "finished" and capability["authorization"]["scope"] == "deterministic_failed_result_consumption_only"
    plane.route_adapter = SyntheticDomainRoute("decision_coordinator")
    assert plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "after-timeout"), actor=actor)["operation_status"] == "committed"
    if pytest_evidence.ACTIVE is None or pytest_evidence.ACTIVE.nodeid == (
            "tests/phase_b/test_timeout_consumption_control.py::test_safe_timeout_consumes_same_failed_attempt_before_outbound"):
        observe("b03-construction-timeout-consumer", {"kind": "boolean", "value": True},
                sorted(["independent_failed_result_consumer", "same_resolution_tuple", "outbound_after_consumption"]))


TIMEOUT_BOUNDARIES = [("control.resolve_external_interrupt.recoverable_timeout." + phase, side)
    for phase in ("interrupt_and_pause_ownership_reserved", "external_final_evidence_verified", "resource_disposition_committed",
                  "resolved_interrupt_outcome_committed", "canonical_failed_delivery_committed", "pause_claimed_recorded", "pause_consumed_recorded",
                  "running_lifecycle_recorded", "resume_checkpoint_committed", "interrupted_code_invocation_authorized", "interrupted_code_attempt_started",
                  "interrupted_code_result_registered", "interrupted_code_attempt_finished", "external_consumption_released",
                  "interrupted_code_checkpoint_committed", "result_committed") for side in ("before", "after")]
TIMEOUT_BOUNDARIES += [("invocation.started_intent", "after"), ("interrupt.timeout_member.file_sync", "after")]


@pytest.mark.parametrize("crash_boundary", TIMEOUT_BOUNDARIES)
def test_safe_timeout_process_restart_materializes_only_original_suffix(timeout_source, crash_boundary):
    import multiprocessing
    from dataclasses import asdict
    from helpers.process_client import timeout_client
    coordinator, plane, actor, locator, root, request = timeout_source
    context = multiprocessing.get_context("spawn")
    for boundary, elapsed in ((crash_boundary, 0), (None, 40)):
        parent, child = context.Pipe()
        process = context.Process(target=timeout_client, args=(child, str(coordinator.root), asdict(request), boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary:
                assert process.exitcode == 96
            else:
                assert process.exitcode == 0
                result, stops, deliveries = parent.recv()
                assert result["operation_status"] == "committed" and result["run_status"] == "running" and result["domain_status"] == "failed", result
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert [r["status"] for r in records if r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002"] == ["scheduled", "running", "failed"]
    assert sum(r["record_type"] == "budget" and r["event"] == "resource_settled" for r in records) == 1
    assert ExternalControl(coordinator).attached(coordinator.connection, locator) == []


@pytest.mark.parametrize("safe,violation", [(True, True), (False, False)])
def test_timeout_classification_closes_without_failed_delivery(timeout_source, safe, violation):
    coordinator, plane, actor, locator, root, request = timeout_source
    plane.external_adapter = DomainTimeout(coordinator, safe=safe, violation=violation)
    result = plane.resolve_external_interrupt(request, actor=actor)
    assert result["operation_status"] == ("committed" if safe else "recovery_required"), result
    assert result["run_status"] == ("failed" if safe else None)
    assert result["terminal_closure"] == ("committed" if safe else "unavailable")
    assert plane.external_adapter.deliveries == 0
    assert not coordinator.connection.execute("SELECT 1 FROM invocation_capabilities WHERE capability_id=?", ("capability_" + result["operation_id"],)).fetchone()


@pytest.mark.parametrize("fault", ["success", "promotion", "missing_member", "traversal"])
def test_invalid_timeout_delivery_never_starts_target(timeout_source, fault):
    from dataclasses import replace
    coordinator, plane, actor, locator, root, request = timeout_source
    class BadDelivery(DomainTimeout):
        def prepare_timeout_delivery(self, view):
            value = super().prepare_timeout_delivery(view)
            if fault == "success":
                return replace(value, result_semantics={**value.result_semantics, "status": "success"})
            if fault == "promotion":
                return replace(value, result_semantics={**value.result_semantics, "change_promotion": "allowed"})
            if fault == "missing_member":
                return replace(value, state_members={**value.state_members, "code_agent_result_path": "missing.json"})
            return replace(value, member_contents={**value.member_contents, "../escaped.json": "{}"})
    plane.external_adapter = BadDelivery(coordinator)
    result = plane.resolve_external_interrupt(request, actor=actor)
    assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable", result
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert not any(r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002" and r["event"] == "started" for r in records)


def test_timeout_authorization_rejects_business_effect_port(timeout_source):
    from lqcd_agent.control.strict_json import ControlIntegrityError
    coordinator, plane, actor, locator, root, request = timeout_source
    checked = []
    def observer(name, side, operation):
        if name == "control.resolve_external_interrupt.recoverable_timeout.interrupted_code_invocation_authorized" and side == "after":
            leases = InvocationLeases(coordinator)
            with pytest.raises(ControlIntegrityError, match="cannot invoke a consumer"):
                leases._effect_authority(coordinator.connection, "capability_" + operation["operation_id"], "foreign", 0)
            checked.append(True)
    coordinator.observer = observer
    result = plane.resolve_external_interrupt(request, actor=actor)
    assert result["operation_status"] == "committed" and checked == [True]
