"""Real product retries retain closed Code and protected authorization origins."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.prior_code_evidence_sources import product_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, loads


MODES = ("retry_success", "retry_failed", "triple_success", "no_change", "needs_input", "needs_human",
         "budget_exhausted", "policy_blocked", "timeout_retry")
INVARIANTS = sorted(["B04_owned_false", "bound_human_scope", "exact_code_origins", "original_ports", "single_consumption"])


@pytest.mark.parametrize("mode", MODES)
def test_product_retry_has_exact_sources(mode):
    expected = read(ROOT / "tests/phase_b/expected_traces/b00c21" / (mode + ".json"))
    values = []
    for _ in range(2):
        trace, root, facts = product_trace(mode)
        assert not facts["B04_owned"] and facts["Code_attempts"] == facts["dispatches"]
        assert len(trace["proof"]["code_evidence_sources"]) == facts["Code_attempts"] - 1
        assert len(trace["proof"]["code_task_authorizations"]) == facts["human_consumed"] == facts["Code_attempts"] - 1
        if mode == "triple_success":
            assert facts["grants_issued"] == facts["grants_consumed"] == 1
        compare(trace, expected, binding=current_binding())
        value = normalize(trace, binding=current_binding())
        (root / "c21-normalized.json").write_bytes(canonical_bytes(value))
        values.append(value)
        print("C21_PRODUCT_EVIDENCE", mode, root)
    assert values[0] == values[1]
    observe("B00C21-" + mode.upper(), {"kind": "boolean", "value": True}, INVARIANTS, trace)


@pytest.fixture(scope="module")
def retry_source():
    return product_trace("retry_failed")[0]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "foreign", "future", "result", "producer", "orphan", "stale"])
def test_code_origin_rejects_unproven_declaration(retry_source, fault):
    raw = deepcopy(retry_source)
    proof = raw["proof"]
    source = proof["code_evidence_sources"][0]
    if fault == "missing": proof["code_evidence_sources"].clear()
    elif fault == "duplicate": proof["code_evidence_sources"].append(deepcopy(source))
    elif fault == "foreign": source["source_registration_head"] = "a" * 64
    elif fault == "future": source["source_task_head"] = source["consumer_task_head"]
    elif fault == "result": source["source_result_head"] = source["source_task_head"]
    elif fault == "producer": source["source_producer_operation_id"] = "foreign"
    elif fault == "orphan": source["evidence_index"] += 100
    else: proof["binding"]["invocation_token"] = "stale"
    with pytest.raises(Invalid): normalize(raw, binding=current_binding())


@pytest.mark.parametrize("field", ["human_request_head", "response_submitted_head", "response_validated_head",
    "response_consumed_head", "snapshot_registration_head", "resume_operation_id", "parent_transition_head",
    "consumer_transition_head"])
def test_task_authorization_rejects_foreign_origin(retry_source, field):
    raw = deepcopy(retry_source)
    raw["proof"]["code_task_authorizations"][0][field] = "foreign" if field.endswith("_id") else "a" * 64
    with pytest.raises(Invalid): normalize(raw, binding=current_binding())


@pytest.mark.parametrize("fault", ["missing", "duplicate", "extra_field"])
def test_task_authorization_is_closed_and_set_equal(retry_source, fault):
    raw = deepcopy(retry_source)
    values = raw["proof"]["code_task_authorizations"]
    if fault == "missing": values.clear()
    elif fault == "duplicate": values.append(deepcopy(values[0]))
    else: values[0]["fabricated_authority"] = True
    with pytest.raises(Invalid): normalize(raw, binding=current_binding())


def test_old_version_keeps_rejecting_new_code_leaf(retry_source):
    raw = deepcopy(retry_source)
    raw["schema_version"] = "0.8"
    raw["proof"]["schema_version"] = "0.5"
    for field in ("code_evidence_sources", "code_task_authorizations"):
        raw["proof"].pop(field)
    with pytest.raises(Invalid, match="product_code_evidence"):
        normalize(raw, binding=current_binding())


def test_scientific_fingerprints_ignore_execution_identity():
    fingerprints = []
    for label in ("c21-science-first-owner", "c21-science-second-owner"):
        trace, _, _ = product_trace("retry_failed", label=label)
        normalize(trace, binding=current_binding())
        fingerprints.append([r["value"]["payload"]["fingerprint"] for r in trace["proof"]["objects"]
                             if r["value"].get("event") == "failure_observed"])
    assert fingerprints[0] == fingerprints[1]


@pytest.mark.parametrize("change", ["requirement", "historical_change"])
def test_material_changes_reach_the_real_scientific_key(retry_source, change):
    options = {"requirement": "Compute the changed approved observable"} if change == "requirement" else {
        "first_failure_change": b"def value():\n    return 3\n"}
    varied, _, _ = product_trace("retry_failed", **options)
    assert normalize(varied, binding=current_binding()) != normalize(retry_source, binding=current_binding())
    def last_fingerprint(raw):
        rows = [r["value"] for r in raw["proof"]["objects"] if r["value"].get("event") == "failure_observed"]
        return max(rows, key=lambda r: r["event_index"])["payload"]["fingerprint"]
    original, actual = last_fingerprint(retry_source), last_fingerprint(varied)
    assert original["fingerprint_digest"] != actual["fingerprint_digest"]
    assert original["context"]["code_task_context_digest"] != actual["context"]["code_task_context_digest"]


@pytest.mark.parametrize("fault", ["kill_all", "bounded_drain", "post_stop_stability"])
def test_unsafe_final_has_no_canonical_code_or_new_work(fault):
    from helpers.b04_code_product import code_product
    coordinator, actor, agent, backend, host, _, result = code_product(
        status="failed", trace=True, trace_version="0.9", stop_fault=fault)
    try:
        producer, = backend.dispatches
        audit, patch = backend.deliveries[producer]
        final = host.finalize(producer, tool_audit=audit, patch=patch)
        assert final["operation_status"] == "recovery_required" and final["terminal_closure"] == "unavailable"
        assert host.finalize(producer, tool_audit=audit, patch=patch) == final
        root, _ = result["runtime"]._records(result["run_locator"])
        assert loads((root / "artifact_index.json").read_bytes())["current"]["code"] is None
        assert len(backend.dispatches) == len(agent.contexts) == 1
        trace = result["trace_capture"].finish(coordinator)
        assert trace["proof"]["code_evidence_sources"] == trace["proof"]["code_task_authorizations"] == []
        assert normalize(trace, binding=current_binding())
        assert len(backend.dispatches) == 1
    finally:
        coordinator.close()


class PublicationInterruption(BaseException):
    """A Python boundary interruption, distinct from actual process exit."""


@pytest.mark.parametrize("reason", ["terminal_operator_stop", "proven_integrity_trigger"])
def test_safe_interrupt_retains_original_terminal_classification(reason):
    from helpers.b04_code_product import code_product
    from lqcd_agent.code_agent.external_operation import CodeExternalStop
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.pause import ResolveExternalInterruptRequest
    from lqcd_agent.control.strict_json import digest

    coordinator, _, agent, backend, host, _, result = code_product(status="failed", trace=True, trace_version="0.9")
    try:
        runtime, locator = result["runtime"], result["run_locator"]
        root, _ = runtime._records(locator)
        producer, = backend.dispatches
        trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": reason}
        (root / "c21-interrupt-trigger.json").write_bytes(canonical_bytes(trigger))
        request = ResolveExternalInterruptRequest(locator, producer, reason, "c21-interrupt-trigger.json", digest(trigger))
        plane = ControlPlane(coordinator, worker_id="code_host", external_adapter=CodeExternalStop(
            coordinator, backend, host.containment, backend.read_receipt))
        actor = ActorContext("operator", "human", ("control.internal",))
        first = plane.resolve_external_interrupt(request, actor=actor)
        status = "halted" if reason == "terminal_operator_stop" else "failed"
        assert first["operation_status"] == "committed" and first["run_status"] == status
        assert plane.resolve_external_interrupt(request, actor=actor) == first
        runtime.run(locator)
        assert runtime._records(locator)[1].projection.value["run_status"] == status
        trace = result["trace_capture"].finish(coordinator)
        assert normalize(trace, binding=current_binding())
        assert len(backend.dispatches) == 1
        assert len([c for node, c in agent.contexts if node == "method_planner"]) == 1
    finally:
        coordinator.close()


@pytest.mark.parametrize("boundary", ["budget.failure_observed", "invocation.completion_intent", "invocation.attempt_finished"])
@pytest.mark.parametrize("side", ["before", "after"])
def test_retry_failure_publication_materializes_only_original_facts(boundary, side):
    from helpers.b04_code_product import code_product, deliver_product_code
    from lqcd_agent.control.capabilities import ArtifactEffectPort, InvocationLeases
    from lqcd_agent.control.pause import ResumeRunRequest
    from lqcd_agent.control.strict_json import digest

    armed, receipts = False, []
    def fault(name, when, value):
        if not armed or receipts or name != boundary or when != side:
            return
        if name.startswith("invocation."):
            active = [loads(r[0]) for r in coordinator.connection.execute("SELECT value FROM invocation_capabilities")]
            if not any(r["state"] == "started" and r["authorization"]["identity"]["attempt_kind"] == "decision_coordinator" for r in active):
                return
        receipts.append(deepcopy(value))
        raise PublicationInterruption()
    coordinator, actor, agent, backend, host, _, result = code_product(
        status=["failed", "failed"], trace=True, trace_version="0.9", observer=fault)
    try:
        runtime, locator = result["runtime"], result["run_locator"]
        deliver_product_code(coordinator, actor, backend, host, result)
        _, execution = runtime._records(locator)
        state = execution.projection.value
        response = {**locator, "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
            "decision": "request_code_change", "conditions": [], "reason": "Bounded original Code retry", "decided_by": "operator"}
        runtime.resume(ResumeRunRequest(locator, state["active_pause"]["pause_id"], "c21-fault-approval",
                                       "human_response", response, digest(response)), actor=actor)
        armed = True
        with pytest.raises(PublicationInterruption):
            deliver_product_code(coordinator, actor, backend, host, result, producer=backend.dispatches[-1])
        capture = result["trace_capture"]
        coordinator.observer = lambda n, s, v: capture.ordinary_sources.observer(capture, n, s, v)
        leases = InvocationLeases(coordinator, decision_adapter=runtime.route_adapter, preparation_adapter=runtime.route_adapter)
        key, value = next((r[0], loads(r[1])) for r in coordinator.connection.execute("SELECT capability_id,value FROM invocation_capabilities")
                          if loads(r[1])["authorization"]["identity"]["attempt_kind"] == "decision_coordinator" and
                          loads(r[1])["state"] == "started")
        frozen = value.get("completion_intent") is not None
        if frozen:
            leases.publish_completion(key, value["worker_id"], value["invocation_epoch"])
            leases.publish_completion(key, value["worker_id"], value["invocation_epoch"])
            runtime.run(locator)
        else:
            port = ArtifactEffectPort(leases, None, key, value["worker_id"], value["invocation_epoch"])
            port.publish_budget()
            port.publish_budget()
            with pytest.raises(ControlIntegrityError, match="explicit recovery"):
                runtime.run(locator)
        assert len(receipts) == 1 and len(backend.dispatches) == 2 and len(agent.contexts) == 1
        trace = capture.finish(coordinator)
        assert normalize(trace, binding=current_binding())
        (coordinator.root / "c21-publication-facts.json").write_bytes(canonical_bytes({
            "boundary": boundary, "side": side, "complete_facts": frozen, "dispatches": 2, "B04_owned": False}))
    finally:
        coordinator.close()
