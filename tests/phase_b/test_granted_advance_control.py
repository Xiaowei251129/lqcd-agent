"""B02 binds a validated B04 grant input without issuing budget windows."""
from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from lqcd_agent.artifacts.registry import ARTIFACT_SLOTS
from lqcd_agent.control.execution import replay
from lqcd_agent.control.operations import AdvanceOperations
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from test_advance_control import SyntheticDomainRoute
from test_execution_0_4_foundation import DIGEST, POLICY, attempt, bootstrap, failure, rechain, transition


def granted_source(*, replan=False):
    ledger = bootstrap()
    attempt(ledger, "started")
    attempt(ledger, "finished")
    attempt(ledger, "scheduled", identity=2, node="decision_coordinator")
    transition(ledger, 2, "decision_coordinator", "method_planner")
    attempt(ledger, "started", identity=2, node="decision_coordinator")
    attempt(ledger, "finished", identity=2, node="decision_coordinator")
    return_node = "decision_coordinator" if replan else "analysis_engineer"
    scope = {"allowed_decisions": ["approve_budget_window"], "allowed_target_nodes": [return_node],
             "decision_transition_routes": {"approve_budget_window": return_node},
             "decision_transition_targets": {"approve_budget_window": return_node}}
    ledger.add("human_request", "created", cycle_id="cycle_0001", human_request_id="human_request_000001", request_index=1,
               request_kind="approval", requesting_attempt_id="attempt_000002", packet_reference=None, status="open", authorization_scope=scope)
    attempt(ledger, "scheduled", identity=3, node="human_approval_gate")
    transition(ledger, 3, "human_approval_gate", "decision_coordinator")
    attempt(ledger, "started", identity=3, node="human_approval_gate")
    response = dict(cycle_id="cycle_0001", human_request_id="human_request_000001", human_response_id="human_response_000001",
                    response_index=1, payload_reference="human_responses/human_response_000001/payload.json", payload_sha256=DIGEST,
                    validator_attempt_id=None, consumer_attempt_id=None, authorized_target_attempt_id=None,
                    decision=None, authorized_route=None, authorized_transition_route=None, authorized_transition_target=None)
    ledger.add("human_response", "submitted", **response, status="submitted", submitted_payload_reference="incoming",
               payload_snapshot={"decision": "approve_budget_window"})
    response.update(validator_attempt_id="attempt_000003", decision="approve_budget_window", authorized_route=return_node,
                    authorized_transition_route=return_node, authorized_transition_target=return_node)
    ledger.add("human_response", "validated", **response, status="validated", error=None)
    fp = failure().value
    ledger.budget("failure_observed", fingerprint=fp, occurrence=1)
    if replan:
        attempt(ledger, "finished", identity=3, node="human_approval_gate")
        attempt(ledger, "scheduled", identity=4, node="decision_coordinator")
        record = transition(ledger, 4, "decision_coordinator", "human_approval_gate")
        record.update(human_request_id=response["human_request_id"], human_response_id=response["human_response_id"])
        consumed = {**response, "consumer_attempt_id": "attempt_000003", "authorized_target_attempt_id": "attempt_000004"}
        ledger.add("human_response", "consumed", **consumed, status="consumed")
        original = next(r for r in ledger.records if r["record_type"] == "human_request")
        from lqcd_agent.control.records import FIELDS
        ledger.add("human_request", "satisfied", **{**{key: original[key] for key in FIELDS["human_request"]}, "status": "satisfied"})
        attempt(ledger, "started", identity=4, node="decision_coordinator")
        attempt(ledger, "finished", identity=4, node="decision_coordinator")
    target_index = 5 if replan else 4
    target_node = "method_planner" if replan else "analysis_engineer"
    grant = dict(budget_grant_id="budget_grant_000001", budget_grant_index=1, cycle_id="cycle_0001",
                 human_request_id="human_request_000001", human_response_id="human_response_000001", pause_id="pause_000001",
                 response_reference=response["payload_reference"], response_digest=DIGEST,
                 route_dimension="automatic_replan_per_run" if replan else "automatic_analysis_rerun_per_cycle", fingerprint_digest=fp["fingerprint_digest"], occurrence=1,
                 target_attempt_id=f"attempt_{target_index:06d}", target_attempt_kind=target_node, target_node=target_node,
                 transition_id=f"transition_{target_index:06d}", additional_opportunities=1, actor_scope=["approve_budget_window"])
    ledger.budget("grant_issued", **grant)
    if not replan:
        attempt(ledger, "finished", identity=3, node="human_approval_gate")
    state = {**replay(ledger.records).projection.value, "checkpoint_head": DIGEST, "artifact_head": None, "artifact_event_index": 0}
    admitted = SyntheticDomainRoute(target_node).admit({"state": state})
    if replan:
        admitted = replace(admitted, trigger_reason="replan")
        admitted.budget_decision["dimensions"]["cycles_per_run"]["projected_after"] += 1
    decision = {**admitted.budget_decision, "budget_grant_id": grant["budget_grant_id"],
                "fingerprint_digest": grant["fingerprint_digest"], "occurrence": grant["occurrence"]}
    decision["decision_digest"] = digest({k: v for k, v in decision.items() if k != "decision_digest"})
    return ledger, state, replace(admitted, budget_decision=decision), grant


def test_granted_replan_preserves_approval_cycle_and_allocates_exact_new_cycle():
    ledger, state, admitted, grant = granted_source(replan=True)
    plan = snapshot(ledger, state, admitted)
    assert grant["cycle_id"] == "cycle_0001"
    child_cycle = next(row for row in plan["records"] if row["record_type"] == "cycle" and row["cycle_index"] == 2)
    target = next(row for row in plan["records"] if row["record_type"] == "attempt" and row["attempt_id"] == grant["target_attempt_id"])
    assert child_cycle["parent_cycle_id"] == grant["cycle_id"]
    assert target["cycle_id"] == child_cycle["cycle_id"] == "cycle_0002"
    assert child_cycle["created_by_attempt_id"] == target["parent_attempt_id"] == "attempt_000004"
    consumed = next(row for row in plan["records"] if row["record_type"] == "budget" and row["event"] == "grant_consumed")
    edge = next(row for row in plan["records"] if row["record_type"] == "transition" and row["transition_id"] == grant["transition_id"])
    assert consumed["event_index"] < child_cycle["event_index"] < target["event_index"] < edge["event_index"]
    assert replay(plan["records"]).projection.value["budget"]["active_grant"] is None


@pytest.mark.parametrize("fault", ["route_dimension", "other_coordinator", "inbound_transition"])
def test_replan_grant_does_not_authorize_a_different_cycle_creator_or_route(fault):
    ledger, state, admitted, _ = granted_source(replan=True)
    rows = snapshot(ledger, state, admitted)["records"]
    issued = next(row for row in rows if row["record_type"] == "budget" and row["event"] == "grant_issued")
    consumed = next(row for row in rows if row["record_type"] == "budget" and row["event"] == "grant_consumed")
    if fault == "route_dimension":
        issued["payload"]["route_dimension"] = "automatic_analysis_rerun_per_cycle"
    elif fault == "other_coordinator":
        next(row for row in rows if row["record_type"] == "cycle" and row["cycle_index"] == 2)["created_by_attempt_id"] = "attempt_000002"
    else:
        issued["payload"]["transition_id"] = "transition_000004"
        consumed["payload"]["transition_id"] = "transition_000004"
    consumed["payload"]["grant_digest"] = digest(issued["payload"])
    with pytest.raises(ControlIntegrityError):
        replay(rechain(rows))


def snapshot(ledger, state, admitted):
    index = {"schema_version": "0.1", "run_id": "run", "case_id": "case", "revision": 0, "last_event_id": None,
             "current": dict.fromkeys(ARTIFACT_SLOTS), "managed_projections": {}, "execution_head": state["execution_head"], "artifact_head": None}
    operation = {"operation_id": "grant-advance", "operation_type": "advance_run", "operation_variant": "not_applicable",
                 "created_at": asdict(ledger.clock.now()), "lease_epoch": 1, "phase_revision": 1,
                 "request": {"run_locator": {"run_id": "run", "case_id": "case"}}}
    return AdvanceOperations(None, "worker", 30, None)._snapshot(operation, ledger.records, index, b"",
                {"checkpoint_head": DIGEST}, state, 1, admitted)


def test_granted_route_freezes_consumption_before_target_and_transition():
    ledger, state, admitted, grant = granted_source()
    plan = snapshot(ledger, state, admitted)
    rows = plan["records"]
    consumed = next(r for r in rows if r["record_type"] == "budget" and r["event"] == "grant_consumed")
    target = next(r for r in rows if r["record_type"] == "attempt" and r["attempt_id"] == grant["target_attempt_id"])
    committed = next(r for r in rows if r["record_type"] == "transition" and r["transition_id"] == grant["transition_id"])
    assert consumed["event_index"] < target["event_index"] < committed["event_index"]
    assert consumed["payload"]["grant_digest"] == digest(grant)
    assert replay(rows).projection.value["budget"]["active_grant"] is None
    assert plan["reservation"]["grant_consumption_or_not_applicable"] == consumed
    assert plan["steps"][0]["evidence"]["grant_consumed_or_not_applicable"] == consumed
    assert snapshot(ledger, state, admitted)["records"] == rows


@pytest.mark.parametrize("fault", ["grant_id", "fingerprint", "occurrence", "target", "transition", "cycle", "consumed", "missing", "duplicate", "hard_ceiling"])
def test_granted_route_rejects_cross_wired_or_reused_opportunity(fault):
    ledger, state, admitted, grant = granted_source()
    if fault in ("grant_id", "fingerprint", "occurrence"):
        field = {"grant_id": "budget_grant_id", "fingerprint": "fingerprint_digest", "occurrence": "occurrence"}[fault]
        admitted.budget_decision[field] = 2 if fault == "occurrence" else "b" * 64
        admitted.budget_decision["decision_digest"] = digest({k: v for k, v in admitted.budget_decision.items() if k != "decision_digest"})
    elif fault in ("target", "transition", "cycle"):
        field = {"target": "target_attempt_id", "transition": "transition_id", "cycle": "cycle_id"}[fault]
        state["budget"]["active_grant"] = {**grant, field: "foreign"}
    elif fault == "consumed":
        ledger.budget("grant_consumed", budget_grant_id=grant["budget_grant_id"], transition_id=grant["transition_id"],
                      target_attempt_id=grant["target_attempt_id"], grant_digest=digest(grant))
    elif fault == "missing":
        state["budget"]["active_grant"] = None
    elif fault == "duplicate":
        ledger.records.append(deepcopy(next(r for r in ledger.records if r["record_type"] == "budget" and r["event"] == "grant_issued")))
    else:
        admitted.budget_decision["dimensions"]["work_attempts_per_run"]["projected_after"] = POLICY["limits"]["work_attempts_per_run"] + 1
        admitted.budget_decision["decision_digest"] = digest({k: v for k, v in admitted.budget_decision.items() if k != "decision_digest"})
    with pytest.raises(ControlIntegrityError):
        snapshot(ledger, state, admitted)
