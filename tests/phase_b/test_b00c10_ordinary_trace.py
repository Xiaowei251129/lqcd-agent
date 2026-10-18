"""Actual ordinary source closure, old-version rejection and material sensitivity."""
from copy import deepcopy

import pytest

from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.ordinary_mixed import no_code_trace, primitive_trace, mixed_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import loads, canonical_bytes
from test_b04_product_graph import diagnostic, StructuredOutcomes
from harness.pytest_evidence import observe
from harness.contracts import ROOT


@pytest.fixture(scope="module")
def no_code():
    return no_code_trace()


def projected(trace):
    return normalize(trace, binding=current_binding())


def test_compiled_no_code_is_exact_across_fresh_roots_and_preserves_identities(no_code):
    first, out, agent, state = no_code
    second, other, other_agent, other_state = no_code_trace()
    assert out != other and state["run_status"] == other_state["run_status"] == "completed"
    assert len(agent.contexts) == len(other_agent.contexts) == 3
    assert projected(first) == projected(second)
    assert first["events"][0]["run_id"] == projected(first)["events"][0]["run_id"]
    assert first["proof"]["ordinary_calls"][1]["outcome"]["content"] == '{"content":{"domain":"validated"},"diagnostic":{"affected_layer":"none","candidates":[],"category":"validated_domain","confidence":"unique","evidence":[],"fingerprint":null,"human_need":null,"retryability":"not_retryable","risk":"low","status":"success"}}'
    assert any(loads(row["content"]).get("evidence") for row in first["proof"]["ordinary_members"] if row["member"].endswith("_diagnostic.json"))
    for trace, root in ((first, out), (second, other)):
        (root / "normalized.json").write_bytes(canonical_bytes(projected(trace)))
        compare(trace, read(ROOT / "tests/phase_b/expected_traces/b00c10/no_code.json"), binding=current_binding())
    observe("B00C10-ORDINARY", {"kind": "boolean", "value": True},
            ["exact_ordinary_sources", "literal_host_identity", "session_bound_proof"], first)


def test_same_run_mixed_uses_original_b03_ports_with_fresh_analysis():
    first, output, agent, state = mixed_trace()
    second, other, other_agent, other_state = mixed_trace()
    assert state["attempt_status"] == other_state["attempt_status"] == "succeeded"
    assert len(agent.contexts) == len(other_agent.contexts) == 2
    assert projected(first) == projected(second)
    assert len({e["run_id"] for e in first["events"] if e["run_id"] is not None}) == 1
    kinds = {r["value"]["payload"]["resource_kind"] for r in first["proof"]["objects"] if
             r["value"].get("event") == "resource_reserved"}
    assert kinds == {"llm_call", "tool_call", "code_backend_operation", "verification_command"}
    for trace, root in ((first, output), (second, other)):
        (root / "normalized.json").write_bytes(canonical_bytes(projected(trace)))
        compare(trace, read(ROOT / "tests/phase_b/expected_traces/b00c10/mixed.json"), binding=current_binding())
    observe("B00C10-MIXED", {"kind": "boolean", "value": True},
            ["exact_mixed_sources", "original_b03_ports", "session_bound_proof"], first)


@pytest.mark.parametrize("kind", ["llm_call", "tool_call"])
def test_actual_ordinary_success_and_unknown_usage(kind):
    trace, _, calls, state = primitive_trace(kind=kind)
    assert calls == ["effect"] and state["attempt_status"] == "succeeded"
    assert projected(trace)
    settlements = [r["value"]["payload"] for r in trace["proof"]["objects"] if r["value"].get("event") == "resource_settled"]
    assert len(settlements) == 1 and settlements[0]["tokens"] == settlements[0]["cost"] == {"state": "unknown", "value": None}
    assert settlements[0]["actual"]["active_seconds"] == 2


@pytest.mark.parametrize("failure", ["exception", "overrun"])
def test_actual_unsettled_prefix_keeps_maximum_and_observation(failure):
    from lqcd_agent.control.execution import replay
    trace, root, calls, _ = primitive_trace(failure=failure)
    assert calls == ["effect"]
    assert not any(r["value"].get("event") == "resource_settled" for r in trace["proof"]["objects"])
    assert projected(trace)
    records = [row["value"] for row in trace["proof"]["objects"] if row["kind"] == "execution_0_4"]
    state = replay(sorted(records, key=lambda row: row["event_index"])).projection.value
    assert state["budget"]["dimensions"]["active_seconds_per_attempt"]["used"] == 1
    assert state["budget"]["dimensions"]["llm_calls_per_attempt"]["used"] == 1
    persisted = loads((root / "raw.json").read_bytes())
    assert projected(persisted) == projected(trace)
    assert calls == ["effect"]


def test_structured_domain_failure_is_settled_and_source_bound():
    trace, _, _, state = no_code_trace(trace_version="0.8", outcomes={"analysis_engineer": diagnostic(status="failed", category="tool_failure",
        affected_layer="analysis", retryability="retryable", candidates=["analysis_engineer"], risk="low")})
    assert state["run_status"] == "paused" and projected(trace)
    assert loads(trace["proof"]["ordinary_calls"][1]["outcome"]["content"])["diagnostic"]["status"] == "failed"


@pytest.mark.parametrize("fault", ["input_bytes", "config_bytes", "outcome_bytes", "missing_return", "missing_request",
                                  "duplicate_call", "profile", "foreign_attempt", "producer_epoch", "reservation_head",
                                  "member_size", "member_identity", "member_role", "duplicate_member", "foreign_packet",
                                  "capability_id", "producer_revision", "pre_execution_head", "wrong_resource_kind", "duplicate_settlement",
                                  "base_input_alias", "base_config_alias", "base_outcome_alias", "input_content_type", "member_content_type",
                                  "producer_worker", "producer_phase", "producer_variant", "producer_coupled_worker", "producer_epoch_type"])
def test_forged_ordinary_source_is_rejected(no_code, fault):
    trace = deepcopy(no_code[0]); call = trace["proof"]["ordinary_calls"][0]
    if fault.endswith("_bytes"):
        call[fault.removesuffix("_bytes")]["content"] += " "
    elif fault == "missing_return":
        call["outcome"] = None
    elif fault == "missing_request":
        trace["proof"]["ordinary_calls"].pop()
    elif fault == "duplicate_call":
        trace["proof"]["ordinary_calls"].append(deepcopy(call))
    elif fault == "profile":
        call["profile"] = "verification"
    elif fault == "foreign_attempt":
        call["authorization"]["identity"]["attempt_id"] = "foreign"
    elif fault == "producer_epoch":
        call["producer"]["lease_epoch"] += 1
    elif fault == "reservation_head":
        call["reservation_head"] = "a" * 64
    elif fault == "capability_id":
        call["capability_id"] += "foreign"
    elif fault == "producer_revision":
        call["producer"]["phase_revision"] += 1
    elif fault == "pre_execution_head":
        call["authorization"]["heads"]["execution_head"] = "b" * 64
    elif fault == "wrong_resource_kind":
        call["profile"] = "analysis_tool"
    elif fault == "duplicate_settlement":
        row = next(r for r in trace["proof"]["objects"] if r["value"].get("event") == "resource_settled")
        trace["proof"]["objects"].append(deepcopy(row))
    elif fault.startswith("base_"):
        from harness.trace_proof import source_object
        field = fault.removeprefix("base_").removesuffix("_alias")
        trace["proof"]["objects"].append(source_object("canonical_json", loads(call[field]["content"]), version="0.4"))
    elif fault == "input_content_type":
        call["input"]["content"] = 1
    elif fault == "member_content_type":
        trace["proof"]["ordinary_members"][0]["content"] = 1
    elif fault in ("producer_worker", "producer_phase", "producer_variant"):
        field = {"producer_worker": "worker_owner_id", "producer_phase": "phase", "producer_variant": "operation_variant"}[fault]
        call["producer"][field] = "foreign"
    elif fault == "producer_coupled_worker":
        call["producer"]["worker_owner_id"] = "foreign"
        for event in trace["events"]:
            if event["operation_id"] == call["producer"]["operation_id"]:
                event["owner"] = "foreign"
    elif fault == "producer_epoch_type":
        call["producer"]["lease_epoch"] = True
    elif fault == "member_size":
        trace["proof"]["ordinary_members"][0]["content"] += " "
    elif fault == "member_identity":
        member = next(r for r in trace["proof"]["ordinary_members"] if r["member"] == "method_plan.json")
        value = loads(member["content"]);value["run_id"] = "foreign"; member["content"] = canonical_bytes(value).decode()
    elif fault == "member_role":
        trace["proof"]["ordinary_members"][0]["member"] = "arbitrary.json"
    elif fault == "duplicate_member":
        trace["proof"]["ordinary_members"].append(deepcopy(trace["proof"]["ordinary_members"][0]))
    else:
        call["input"]["content"] = call["input"]["content"].replace('"remediation":null', '"remediation":{"parent_attempt_id":"foreign"}')
    with pytest.raises(Invalid):
        projected(trace)


def test_rehashed_noncanonical_source_declaration_is_rejected(no_code):
    from hashlib import sha256
    from harness.ordinary_trace import OrdinaryProjection
    from lqcd_agent.control.strict_json import ControlIntegrityError
    extension = OrdinaryProjection({})
    extension.base_sources = {}
    declaration = deepcopy(no_code[0]["proof"]["ordinary_calls"][0]["input"])
    declaration["content"] += " "
    declaration["sha256"] = sha256(declaration["content"].encode()).hexdigest()
    with pytest.raises(ControlIntegrityError, match="Non-canonical JSON encoding"):
        extension.add(declaration, {"case_id": "case", "run_id": "run"})


def test_risk_is_material_in_valid_actual_sources(no_code):
    changed, _, _, _ = no_code_trace(outcomes={"scientific_reviewer": diagnostic(risk="medium")})
    expected = projected(no_code[0])
    assert projected(changed) != expected
    with pytest.raises(Invalid, match="trace:exact"):
        compare(changed, expected, binding=current_binding())


def test_actual_agent_host_identity_override_is_rejected(no_code, tmp_path):
    from hashlib import sha256
    from harness.ordinary_trace import OrdinaryProjection
    from harness.trace_proof import _sources, _roots, source_object
    from lqcd_agent.control.clock import FakeClock
    from lqcd_agent.control.coordinator import Coordinator
    from lqcd_agent.control.execution import parse_ledger
    from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
    from lqcd_agent.control.strict_json import ControlIntegrityError, digest
    from lqcd_agent.graph.run_graph import run_canonical_graph

    returns = []
    class Foreign(StructuredOutcomes):
        def run(self, node, context, *, timeout_seconds):
            result = super().run(node, context, timeout_seconds=timeout_seconds)
            if node == "method_planner":
                result["content"]["run_id"] = "foreign-run"
            returns.append(deepcopy(result))
            return result

    output = tmp_path / "original-port"
    output.mkdir()
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    agent = Foreign()
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
    try:
        with pytest.raises(ControlIntegrityError, match="reserved Host fields") as rejected:
            run_canonical_graph(coordinator=coordinator, agent_port=agent,
                actor=ActorContext("operator", "human", ("control.internal", "resume", "start")),
                request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"))
        ledger, = output.glob("case/*/execution_history.jsonl")
        root = ledger.parent
        records = parse_ledger(ledger.read_bytes()).values
        assert [node for node, _ in agent.contexts] == ["method_planner"]
        assert len(returns) == 1 and returns[0]["content"]["run_id"] == "foreign-run"
        reservations = [row for row in records if row.get("event") == "resource_reserved"]
        settlements = [row for row in records if row.get("event") == "resource_settled"]
        assert len(reservations) == len(settlements) == 1
        payload = settlements[0]["payload"]
        assert payload["resource_operation_id"] == reservations[0]["payload"]["resource_operation_id"]
        assert payload["actual"] == {"active_seconds": 0, "llm_calls": 1, "tool_calls": 0, "verification_commands": 0}
        assert payload["tokens"] == payload["cost"] == {"state": "unknown", "value": None}
        assert payload["evidence_digest"] == digest(returns[0])
        assert all(pointer is None for pointer in loads((root / "artifact_index.json").read_bytes())["current"].values())
        assert not any(loads(line).get("event") == "registered" for line in (root / "artifact_history.jsonl").read_bytes().splitlines())
        assert not list(root.glob("attempts/*/method_plan.json"))
        assert not list(root.glob("attempts/*/method_planner_diagnostic.json"))
        assert [(row["source_node"], row["target_node"]) for row in records if row["record_type"] == "transition"] == [
            ("START", "method_planner")]
        assert [row["attempt_kind"] for row in records if row["record_type"] == "attempt" and row["event"] == "scheduled"] == [
            "method_planner"]
        assert not (root / "memory_update.json").exists()
        (tmp_path / "host-rejection-facts.json").write_bytes(canonical_bytes({"error": str(rejected.value),
            "effect_count": len(returns), "reservation_count": len(reservations), "settlement": payload,
            "domain_publication": False, "next_work": False, "output_root": str(root), "B04_owned": False}))
    finally:
        coordinator.close()

    # Isolate the member identity contract using a verified positive source.
    trace, output, _, state = no_code
    assert state["run_status"] == "completed" and projected(trace)
    original = canonical_bytes(trace)
    run = next(output.glob("case/*/execution_history.jsonl")).parent
    preserved = {path: path.read_bytes() for path in (run / "execution_history.jsonl", run / "artifact_history.jsonl",
        run / "artifact_index.json", run / "attempts/attempt_000001/method_plan.json")}
    for field in ("run_id", "case_id", "attempt_id", "producer", "attempt_kind", "schema_version"):
        proof = deepcopy(trace["proof"])
        sources, executions = _sources(proof, version="0.4")
        roots = _roots(proof, executions)
        member = next(row for row in proof["ordinary_members"] if row["member"] == "method_plan.json")
        old_head = member["registration_head"]
        registration = deepcopy(sources.pop(old_head)["value"])
        value = loads(member["content"])
        value[field] = "foreign"
        raw = canonical_bytes(value)
        member.update(content=raw.decode(), sha256=sha256(raw).hexdigest())
        for members in (registration["members"], registration["pointer"]["members"]):
            registered = next(row for row in members if row["logical_name"] == "method_plan.json")
            registered.update(sha256=member["sha256"], size_bytes=len(raw))
        declaration = source_object("canonical_json", registration, version="0.4")
        sources[declaration["sha256"]] = declaration
        for row in proof["ordinary_members"]:
            if row["registration_head"] == old_head:
                row["registration_head"] = declaration["sha256"]
        with pytest.raises(Invalid, match="^invalid_evidence:ordinary_trace:host_identity$"):
            OrdinaryProjection(proof).validate(sources, executions, roots, trace["events"])
    assert canonical_bytes(trace) == original
    assert all(path.read_bytes() == content for path, content in preserved.items())


@pytest.mark.parametrize("material", ["science", "category", "nested_identity", "usage", "problem"])
def test_valid_actual_material_changes_fail_fixed_exact_comparison(no_code, material):
    class Changed(StructuredOutcomes):
        def run(self, node, context, *, timeout_seconds):
            result = super().run(node, context, timeout_seconds=timeout_seconds)
            if node == "scientific_reviewer":
                if material == "category":
                    result["diagnostic"]["category"] = "different_scientific_problem"
                elif material == "usage":
                    result["content"]["usage"] = {"tokens": 3, "cost": 0.05}
                elif material == "problem":
                    result["content"]["problem"] = "A changed observable requires a different interpretation"
                else:
                    result["content"][material] = {"run_id": "material", "path": "/material/path", "value": 3.14, "digest": "f" * 64}
            return result
    trace, _, _, _ = no_code_trace(agent=Changed())
    assert projected(trace) != projected(no_code[0])
    with pytest.raises(Invalid, match="trace:exact"):
        compare(trace, projected(no_code[0]), binding=current_binding())


def test_maximum_settlement_is_contract_only_and_preserves_unknown_usage():
    from lqcd_agent.control.budget import validate_budget_payload
    from lqcd_agent.control.execution import replay
    from lqcd_agent.control.records import build_record, FIELDS
    from lqcd_agent.control.clock import Timestamp
    trace, root, calls, _ = primitive_trace()
    records = sorted((r["value"] for r in trace["proof"]["objects"] if r["kind"] == "execution_0_4"), key=lambda r: r["event_index"])
    actual = next(r for r in records if r["event"] == "resource_settled")
    payload = {**actual["payload"], "actual": None}
    validate_budget_payload("resource_settled", payload)
    fields = {k: actual[k] for k in FIELDS["budget"]}
    fields["payload"] = payload
    maximum = build_record("budget", "resource_settled", case_id=actual["case_id"], run_id=actual["run_id"],
        event_index=actual["event_index"], previous_execution_head=actual["previous_execution_head"],
        artifact_head=actual["artifact_head"], artifact_event_index=actual["artifact_event_index"],
        timestamp=Timestamp(**actual["created_at"]), **fields).value
    prefix = [r for r in records if r["event_index"] < actual["event_index"]]
    conservative = replay([*prefix, maximum]).projection.value
    assert conservative["budget"]["dimensions"]["active_seconds_per_run"]["used"] == 3
    assert payload["tokens"] == payload["cost"] == {"state": "unknown", "value": None}
    assert calls == ["effect"] and loads((root / "raw.json").read_bytes()) == trace


@pytest.mark.parametrize("fault", [None, "foreign_response", "occurrence", "scope", "duplicate_consumption", "fingerprint"])
def test_fingerprint_grant_source_closure_is_contract_only(fault):
    from hashlib import sha256
    from harness.ordinary_trace import OrdinaryProjection
    from harness.trace_proof import source_object
    from lqcd_agent.control.strict_json import digest
    from test_granted_advance_control import granted_source, snapshot
    from test_execution_0_4_foundation import rechain
    from lqcd_agent.control.execution import replay
    from lqcd_agent.control.budget import validate_budget_payload
    from test_execution_0_4_foundation import failure
    ledger, state, admitted, grant = granted_source()
    rows = snapshot(ledger, state, admitted)["records"]
    observed = next(r for r in rows if r.get("event") == "failure_observed")
    original = observed["payload"]["fingerprint"]
    closed = failure(context={**original["context"], "plan_digest": None, "code_digest": None}).value
    observed["payload"]["fingerprint"] = closed
    for row in rows:
        if row["record_type"] == "budget" and row["payload"].get("fingerprint_digest") == original["fingerprint_digest"]:
            row["payload"]["fingerprint_digest"] = closed["fingerprint_digest"]
            if "decision_digest" in row["payload"]:
                row["payload"]["decision_digest"] = digest({k: v for k, v in row["payload"].items() if k != "decision_digest"})
    payload = {"decision": "approve_budget_window"}
    import json
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    head = sha256(raw).hexdigest()
    issued = next(r for r in rows if r.get("event") == "grant_issued")
    consumed = next(r for r in rows if r.get("event") == "grant_consumed")
    issued["payload"]["response_digest"] = head
    consumed["payload"]["grant_digest"] = digest(issued["payload"])
    for response in rows:
        if response["record_type"] == "human_response":
            response["payload_sha256"] = head
    rows = rechain(rows)
    replay(rows)
    for row in rows:
        if row["record_type"] == "budget":
            validate_budget_payload(row["event"], row["payload"])
    issued = next(r for r in rows if r.get("event") == "grant_issued")
    if fault == "foreign_response":
        issued["payload"]["human_response_id"] = "foreign"
    elif fault == "occurrence":
        issued["payload"]["occurrence"] += 1
    elif fault == "scope":
        next(r for r in rows if r["record_type"] == "human_request")["authorization_scope"]["allowed_decisions"] = []
    elif fault == "duplicate_consumption":
        rows.append(deepcopy(next(r for r in rows if r.get("event") == "grant_consumed")))
    elif fault == "fingerprint":
        next(r for r in rows if r.get("event") == "failure_observed")["payload"]["fingerprint"]["diagnostics"]["exit_code"] = 255
    extension = OrdinaryProjection({})
    extension.base_sources = {digest(r): source_object("execution_0_4", r, version="0.4") for r in rows}
    extension.human_snapshots["case", "run", grant["human_response_id"]] = (head, payload, grant["response_reference"])
    if fault is None:
        extension.failure_and_grant_sources(extension.base_sources, {("case", "run"): rows})
        assert extension.sources and extension.refs
    else:
        with pytest.raises((Invalid, ValueError, KeyError)):
            extension.failure_and_grant_sources(extension.base_sources, {("case", "run"): rows})


@pytest.mark.parametrize("fault", [None, "foreign_snapshot", "foreign_target", "foreign_attempt", "missing_snapshot"])
def test_human_source_scope_is_contract_only(fault):
    from harness.ordinary_trace import OrdinaryProjection
    from test_granted_advance_control import granted_source, snapshot
    ledger, state, admitted, _ = granted_source()
    rows = snapshot(ledger, state, admitted)["records"]
    response = next(r for r in rows if r["record_type"] == "human_response" and r["event"] == "consumed")
    authorization = {"human_request_id": response["human_request_id"], "human_response_id": response["human_response_id"],
                     "response_digest": response["payload_sha256"], "target_node": "memory_report"}
    extension = OrdinaryProjection({})
    extension.base_sources = {"source": {}}
    extension.executions = {("case", "run"): rows}
    extension.human_snapshots["case", "run", response["human_response_id"]] = (
        response["payload_sha256"], {"decision": response["decision"]}, response["payload_reference"])
    identity = {"case_id": "case", "run_id": "run", "attempt_id": response["authorized_target_attempt_id"]}
    if fault == "foreign_snapshot":
        authorization["response_digest"] = "f" * 64
    elif fault == "foreign_target":
        authorization["target_node"] = "analysis_engineer"
    elif fault == "foreign_attempt":
        identity["attempt_id"] = "foreign"
    elif fault == "missing_snapshot":
        extension.human_snapshots.clear()
    if fault is None:
        extension.human_authorization("source", authorization, identity, ("human_authorization",))
        assert extension.refs_at
    else:
        with pytest.raises((Invalid, KeyError)):
            extension.human_authorization("source", authorization, identity, ("human_authorization",))
