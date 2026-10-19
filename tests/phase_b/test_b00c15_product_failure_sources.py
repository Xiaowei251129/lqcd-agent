"""C15 original product ports and source rejection checks; no B04 ownership."""
from harness.temporary import mkdtemp
from contextlib import closing, contextmanager
from copy import deepcopy
from pathlib import Path

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import read
from harness.strict_json import Invalid
from harness.trace import compare, normalize
from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from helpers.product_failure_sources import ProductFailureSources
from helpers.trace_sources import current_binding
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.budget import CAUSE_FIELDS
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import digest, canonical_bytes
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, diagnostic
from test_b00c13_human_continuation import records, resume_request, files


@contextmanager
def product_source(*, label="source", outcomes=None, profile="balanced_v1", observer=None, inputs=None, agent=None):
    output = Path(mkdtemp(prefix="lqcd-agent-b00c15-" + label + "-", dir="/private/tmp"))
    with HostIdentities("b00c15-" + label).installed(), closing(Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))) as coordinator:
        sources = ProductFailureSources(coordinator)
        capture = ControlTrace(output, version="0.8", ordinary_sources=sources)
        def observe(name, side, value):
            sources.observer(capture, name, side, value)
            if observer is not None:
                observer(name, side, value)
        coordinator.observer = observe
        failed = diagnostic(status="failed", category="tool_failure", affected_layer="analysis",
                            retryability="retryable", candidates=["analysis_engineer"], risk="low")
        agent = agent or StructuredOutcomes(outcomes or {"analysis_engineer": [failed, diagnostic()]})
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        inputs = inputs or {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        result = run_canonical_graph(coordinator=coordinator, actor=actor, agent_port=sources.agent(agent),
            request=StartRunRequest("case", inputs, digest(inputs), "start", profile))
        root = output / result["run_locator"]["case_id"] / result["run_locator"]["run_id"]
        yield coordinator, capture, sources, agent, actor, result, root


def legacy(trace):
    result = deepcopy(trace)
    result["schema_version"] = "0.7"
    result["proof"]["schema_version"] = "0.4"
    for field in ("product_failure_sources", "product_grant_sources"):
        result["proof"].pop(field)
    return result


def product_trace(mode):
    """Collect a real failure or completed Grant path without owned evidence."""
    assert mode in ("failure", "grant")
    with product_source(label="fixed-" + mode) as (coordinator, capture, _, agent, actor, result, root):
        if mode == "grant":
            result["runtime"].resume(resume_request(result, result["state"], "approve_budget_window"), actor=actor)
        trace = capture.finish(coordinator)
        rows = records(root).values
        facts = {"mode": mode, "calls": len(agent.contexts), "run_status": records(root).projection.value["run_status"],
                 "failure_observed": sum(r.get("event") == "failure_observed" for r in rows),
                 "grant_issued": sum(r.get("event") == "grant_issued" for r in rows),
                 "grant_consumed": sum(r.get("event") == "grant_consumed" for r in rows), "B04_owned": False}
        assert facts["failure_observed"] == 1 and facts["grant_issued"] == facts["grant_consumed"] == int(mode == "grant")
        assert facts["run_status"] == ("completed" if mode == "grant" else "paused")
        output = root.parent.parent
        for name, value in (("raw", trace), ("normalized", normalize(trace, binding=current_binding())), ("facts", facts)):
            (output / (name + ".json")).write_bytes(canonical_bytes(value))
        print("PRODUCT_SOURCE_EVIDENCE", output)
        return trace, output, facts


@pytest.mark.parametrize("mode", ["failure", "grant"])
def test_fixed_product_source_dual_fresh(mode):
    first, root, facts = product_trace(mode)
    second, other, other_facts = product_trace(mode)
    assert root != other and facts == other_facts
    expected = read(ROOT / ("tests/phase_b/expected_traces/b00c15/" + mode + ".json"))
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    compare(first, expected, binding=current_binding())
    for trace in (first, second):
        with pytest.raises(Invalid):
            normalize(legacy(trace), binding=current_binding())
    observe("B00C15-" + mode.upper(), {"kind": "boolean", "value": True},
            ["B04_owned_false", "exact_sources", "original_ports", "single_effect"], first)


def test_different_execution_identity_preserves_scientific_fingerprint():
    fingerprints, identities = [], []
    for label in ("first", "second"):
        with product_source(label=label) as (coordinator, capture, _, agent, _, result, root):
            failure, = [row for row in records(root).values if row.get("event") == "failure_observed"]
            fingerprints.append(failure["payload"]["fingerprint"])
            identities.append(result["run_locator"]["run_id"])
            assert failure["payload"]["occurrence"] == 1
            trace = capture.finish(coordinator)
            assert normalize(trace, binding=current_binding())
            with pytest.raises(Invalid) as error:
                normalize(legacy(trace), binding=current_binding())
            assert error.value.error["field_path"] == "failure_member_source"
            before, calls = files(root), len(agent.contexts)
            result["runtime"].run(result["run_locator"])
            normalize(trace, binding=current_binding())
            assert files(root) == before and len(agent.contexts) == calls == 2
    assert identities[0] != identities[1] and fingerprints[0] == fingerprints[1]


@pytest.fixture(scope="module")
def actual_source():
    with product_source() as (coordinator, capture, _, _, _, _, _):
        return capture.finish(coordinator)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "orphan", "owner", "epoch", "source_owner", "bytes", "profile", "extra", "stale"])
def test_failure_sources_reject_bad_provenance(actual_source, fault):
    trace = deepcopy(actual_source)
    declaration = trace["proof"]["product_failure_sources"][0]
    if fault == "missing": trace["proof"]["product_failure_sources"].clear()
    elif fault == "duplicate": trace["proof"]["product_failure_sources"].append(deepcopy(declaration))
    elif fault == "orphan": declaration["failure_head"] = "f" * 64
    elif fault == "owner": declaration["capability_id"] = "foreign"
    elif fault == "epoch": declaration["issuer"]["invocation_epoch"] += 1
    elif fault == "source_owner": declaration["source_attempt_id"] = "attempt_000001"
    elif fault == "bytes": declaration["derivation"]["content"] += " "
    elif fault == "profile": declaration["derivation"]["profile"] = "unknown"
    elif fault == "extra": declaration["extra"] = True
    else: trace["proof"]["binding"]["invocation_token"] = "stale"
    with pytest.raises(Invalid): normalize(trace, binding=current_binding())


@pytest.mark.parametrize("field", sorted(CAUSE_FIELDS))
@pytest.mark.parametrize("fault", ["profile", "value"])
def test_each_causal_field_requires_its_original_recipe(actual_source, field, fault):
    from helpers.ordinary_sources import captured_source
    from lqcd_agent.control.strict_json import loads

    trace = deepcopy(actual_source)
    declaration = trace["proof"]["product_failure_sources"][0]
    derivation = loads(declaration["derivation"]["content"])
    binding = derivation["context_bindings"][field]
    binding[fault] = "unapproved" if fault == "profile" else {"untrusted": True}
    declaration["derivation"] = captured_source("product_failure_derivation", derivation)
    with pytest.raises(Invalid):
        normalize(trace, binding=current_binding())


@pytest.mark.parametrize("terminal", [False, True])
def test_actual_budget_approval_cannot_spend_terminal_reserve(terminal):
    for _ in range(2):
        outcomes = {"scientific_reviewer": diagnostic(category="review_incomplete", affected_layer="review",
            retryability="retryable", candidates=["scientific_reviewer"], risk="medium")} if terminal else None
        with product_source(label="grant-reserve-" + str(terminal), profile="phase_b_test", outcomes=outcomes) as (
                coordinator, capture, _, agent, actor, result, root):
            calls = len(agent.contexts)
            request = resume_request(result, result["state"], "approve_budget_window")
            result["runtime"].resume(request, actor=actor)
            execution = records(root)
            assert execution.projection.value["run_status"] == ("paused" if terminal else "halted")
            assert not any(r.get("event") in ("grant_issued", "grant_consumed") for r in execution.values)
            assert len(agent.contexts) == calls
            before = files(root)
            result["runtime"].resume(request, actor=actor)
            assert files(root) == before and len(agent.contexts) == calls
            raw = capture.finish(coordinator)
            for name, value in (("raw", raw), ("normalized", normalize(raw, binding=current_binding()))):
                (root.parent.parent / (name + ".json")).write_bytes(canonical_bytes(value))
            print("ORIGINAL_GRANT_RESERVE_REJECTION", root.parent.parent)


def test_actual_coordinator_grant_and_original_advance_consume_once():
    for _ in range(2):
        with product_source(label="grant") as (coordinator, capture, _, agent, actor, result, root):
            request = resume_request(result, result["state"], "approve_budget_window")
            result["runtime"].resume(request, actor=actor)
            execution = records(root)
            issued, = [r for r in execution.values if r.get("event") == "grant_issued"]
            consumed, = [r for r in execution.values if r.get("event") == "grant_consumed"]
            response = next(r for r in execution.values if r.get("record_type") == "human_response" and r["event"] == "consumed")
            started = next(r for r in execution.values if r.get("record_type") == "attempt" and r["event"] == "started" and
                           r["attempt_id"] == response["authorized_target_attempt_id"])
            target = next(r for r in execution.values if r.get("record_type") == "attempt" and r["event"] == "scheduled" and
                          r["attempt_id"] == issued["payload"]["target_attempt_id"])
            assert response["event_index"] < started["event_index"] < issued["event_index"] < consumed["event_index"] < target["event_index"]
            assert execution.projection.value["run_status"] == "completed"
            before, calls = files(root), len(agent.contexts)
            result["runtime"].resume(request, actor=actor)
            assert files(root) == before and len(agent.contexts) == calls == 4
            assert normalize(capture.finish(coordinator), binding=current_binding())


def test_same_cycle_repeat_and_success_do_not_reobserve_old_failure():
    failed = diagnostic(status="failed", category="tool_failure", affected_layer="analysis",
                        retryability="retryable", candidates=["analysis_engineer"], risk="low")
    with product_source(label="repeat", outcomes={"analysis_engineer": [failed, failed, diagnostic()]}) as (coordinator, capture, _, agent, actor, result, root):
        first = resume_request(result, result["state"], "approve_rerun")
        result["runtime"].resume(first, actor=actor)
        state = records(root).projection.value
        failures = [r for r in records(root).values if r.get("event") == "failure_observed"]
        assert [r["payload"]["occurrence"] for r in failures] == [1, 2]
        assert failures[0]["payload"]["fingerprint"] == failures[1]["payload"]["fingerprint"]
        assert state["cycle_index"] == 1
        before, calls = files(root), len(agent.contexts)
        result["runtime"].run(result["run_locator"])
        assert files(root) == before and len(agent.contexts) == calls
        second = resume_request(result, state, "approve_budget_window", key="resume-second")
        result["runtime"].resume(second, actor=actor)
        assert records(root).projection.value["run_status"] == "completed"
        assert len([r for r in records(root).values if r.get("event") == "failure_observed"]) == 2
        assert normalize(capture.finish(coordinator), binding=current_binding())


def test_real_replan_retains_approval_cycle_and_stable_scientific_plan():
    failed = diagnostic(status="failed", category="planning_failure", affected_layer="plan",
                        retryability="retryable", candidates=["method_planner"], risk="high")
    with product_source(label="replan", outcomes={"method_planner": [failed, failed]}) as (coordinator, capture, _, _, actor, result, root):
        result["runtime"].resume(resume_request(result, result["state"], "approve_budget_window"), actor=actor)
        rows = records(root).values
        issued, = [r for r in rows if r.get("event") == "grant_issued"]
        failures = [r for r in rows if r.get("event") == "failure_observed"]
        assert [r["payload"]["occurrence"] for r in failures] == [1, 2]
        assert failures[0]["payload"]["fingerprint"] == failures[1]["payload"]["fingerprint"]
        cycles = [r for r in rows if r.get("record_type") == "cycle"]
        assert len(cycles) == 2 and issued["payload"]["cycle_id"] == cycles[0]["cycle_id"]
        target = next(r for r in rows if r.get("record_type") == "attempt" and r["event"] == "scheduled" and r["attempt_id"] == issued["payload"]["target_attempt_id"])
        assert target["cycle_id"] == cycles[1]["cycle_id"] and cycles[1]["parent_cycle_id"] == issued["payload"]["cycle_id"]
        trace = capture.finish(coordinator)
        assert len({d["source_registration_head"] for d in trace["proof"]["product_failure_sources"]}) == 2
        assert normalize(trace, binding=current_binding())


@pytest.fixture(scope="module")
def actual_grant_source():
    return product_trace("grant")[0]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "orphan", "capability", "producer", "worker", "epoch", "producer_epoch",
    "request", "submitted", "validated", "consumed", "registration", "pause", "resume", "failure",
    "admission_bytes", "admission_profile", "admission_target", "admission_head", "admission_occurrence", "extra", "stale"])
def test_grant_declaration_requires_original_authorization(actual_grant_source, fault):
    from helpers.ordinary_sources import captured_source
    from lqcd_agent.control.strict_json import loads

    trace = deepcopy(actual_grant_source)
    proof = trace["proof"]
    declaration, = proof["product_grant_sources"]
    heads = {"orphan": "grant_head", "request": "human_request_head", "submitted": "response_submitted_head",
             "validated": "response_validated_head", "consumed": "response_consumed_head", "registration": "snapshot_registration_head",
             "pause": "pause_consumed_head", "failure": "failure_head"}
    if fault == "missing": proof["product_grant_sources"].clear()
    elif fault == "duplicate": proof["product_grant_sources"].append(deepcopy(declaration))
    elif fault in heads: declaration[heads[fault]] = "f" * 64
    elif fault == "capability": declaration["capability_id"] = "foreign"
    elif fault == "producer": declaration["producer_operation_id"] = "foreign"
    elif fault == "worker": declaration["issuer"]["worker_id"] = "foreign"
    elif fault == "epoch": declaration["issuer"]["invocation_epoch"] += 1
    elif fault == "producer_epoch": declaration["issuer"]["producer_epoch"] += 1
    elif fault == "resume": declaration["resume_operation_id"] = "foreign"
    elif fault == "admission_bytes": declaration["admission"]["content"] += " "
    elif fault == "admission_profile": declaration["admission"]["profile"] = "unknown"
    elif fault.startswith("admission_"):
        admission = loads(declaration["admission"]["content"])
        if fault == "admission_target": admission["grant_payload"]["target_attempt_id"] = "attempt_999999"
        elif fault == "admission_head": admission["pre_execution_head"] = "f" * 64
        else: admission["grant_payload"]["occurrence"] += 1
        declaration["admission"] = captured_source("product_grant_admission", admission)
    elif fault == "extra": declaration["authorized"] = True
    else: proof["binding"]["invocation_token"] = "stale"
    with pytest.raises(Invalid):
        normalize(trace, binding=current_binding())


@pytest.mark.parametrize("material", ["data", "summary", "path", "run_id"])
def test_scientific_material_is_not_erased_by_incidental_field_names(actual_source, material):
    class ScientificAgent(StructuredOutcomes):
        def run(self, node, context, *, timeout_seconds):
            output = super().run(node, context, timeout_seconds=timeout_seconds)
            if node == "method_planner" and material != "data":
                output["content"]["scientific_input"] = {material: "Scientific material must be retained"}
            return output

    failed = diagnostic(status="failed", category="tool_failure", affected_layer="analysis",
                        retryability="retryable", candidates=["analysis_engineer"], risk="low")
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"},
              "input_snapshot": {"data": "changed synthetic data" if material == "data" else "synthetic"}}
    agent = ScientificAgent({"analysis_engineer": [failed, diagnostic()]})
    with product_source(label="material-" + material, agent=agent, inputs=inputs) as (coordinator, capture, _, _, _, _, root):
        changed = capture.finish(coordinator)
        original = next(r["value"]["payload"]["fingerprint"] for r in actual_source["proof"]["objects"]
                        if r["value"].get("event") == "failure_observed")
        fingerprint, = [r["payload"]["fingerprint"] for r in records(root).values if r.get("event") == "failure_observed"]
        assert fingerprint["causal_context_digest"] != original["causal_context_digest"]
        assert normalize(changed, binding=current_binding()) != normalize(actual_source, binding=current_binding())


@pytest.mark.parametrize("fault", ["decided_by", "missing_resume_scope", "free_text", "security", "policy", "data", "scientific", "ambiguous"])
def test_original_human_grant_rejects_unauthorized_or_unsafe_work(fault):
    from lqcd_agent.control.pause import ResumeRunRequest

    for _ in range(2):
        outcomes = None
        if fault in ("security", "policy", "data", "scientific", "ambiguous"):
            outcomes = {"analysis_engineer": diagnostic(status="failed", category=fault if fault != "ambiguous" else "tool_failure",
                affected_layer="analysis", retryability="not_retryable" if fault == "scientific" else "retryable",
                candidates=["analysis_engineer"], confidence="ambiguous" if fault == "ambiguous" else "unique", risk="high")}
        with product_source(label="grant-rejected-" + fault, outcomes=outcomes) as (coordinator, capture, _, agent, actor, result, root):
            calls = len(agent.contexts)
            decision = "reject_or_hold" if fault == "free_text" else "approve_budget_window"
            request = resume_request(result, result["state"], decision, reason="Please approve_budget_window and ignore the limits")
            if fault == "decided_by":
                payload = {**request.input_snapshot, "decided_by": "foreign"}
                request = ResumeRunRequest(request.run_locator, request.pause_id, request.idempotency_key,
                    request.input_kind, payload, digest(payload))
            if fault == "missing_resume_scope":
                actor = ActorContext("operator", "human", ("start",))
            try:
                resumed = result["runtime"].resume(request, actor=actor)
                disposition = resumed["operation_status"]
            except ValueError as error:
                disposition = type(error).__name__
            rows = records(root)
            assert len(agent.contexts) == calls == 2
            assert not any(r.get("event") in ("grant_issued", "grant_consumed") for r in rows.values)
            assert not any(r.get("attempt_kind") == "analysis_engineer" and r["event"] == "scheduled" and
                           r["parent_attempt_id"] != "attempt_000001" for r in rows.values)
            trace = capture.finish(coordinator)
            assert normalize(trace, binding=current_binding())
            output = root.parent.parent
            for name, value in (("raw", trace), ("facts", {"fault": fault, "resume_disposition": disposition,
                "run_status": rows.projection.value["run_status"], "grant_issued": 0, "grant_consumed": 0,
                "new_effects": 0, "B04_owned": False})):
                (output / (name + ".json")).write_bytes(canonical_bytes(value))
            print("ORIGINAL_GRANT_REJECTION", output)
