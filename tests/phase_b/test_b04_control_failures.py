"""Early control paths retain real upstream evidence and cannot accept absent science."""
import pytest

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, canonical, diagnostic


@pytest.mark.parametrize("updates", [
    {"risk": "critical", "human_need": "approval"},
    {"status": "failed", "category": "planning_failure", "affected_layer": "plan",
     "retryability": "not_retryable", "human_need": "clarification"},
    {"confidence": "ambiguous"},
])
def test_planner_control_prefix_has_only_real_dependencies(updates):
    coordinator, _, agent, result = canonical({"method_planner": diagnostic(**updates)})
    try:
        assert result["state"]["run_status"] == "paused"
        root, execution = result["runtime"]._records(result["run_locator"])
        index = loads((root / "artifact_index.json").read_bytes())["current"]
        assert index["analysis"] is None and index["review"] is None
        assert index["decision"]["dependencies"] == [index["plan"]["artifact_id"]]
        assert index["approval"] is not None and index["terminal"] is None
        assert [node for node, _ in agent.contexts] == ["method_planner"]
        assert [(r["source_node"], r["target_node"]) for r in execution.values if r["record_type"] == "transition"] == [
            ("START", "method_planner"), ("method_planner", "decision_coordinator"), ("decision_coordinator", "human_gate")]
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        result["runtime"].run(result["run_locator"])
        assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert len(agent.contexts) == 1
    finally:
        coordinator.close()


@pytest.mark.parametrize("decision,terminal", [("approve_with_conditions", "pending"), ("reject_or_hold", "rejected")])
def test_early_human_response_never_accepts_missing_analysis(decision, terminal):
    coordinator, actor, agent, result = canonical({"method_planner": diagnostic(risk="critical", human_need="approval")})
    try:
        state = result["state"]
        payload = {**result["run_locator"], "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
                   "decision": decision, "conditions": [], "reason": "Review the early planning evidence", "decided_by": "operator"}
        request = ResumeRunRequest(result["run_locator"], state["active_pause"]["pause_id"], "resume-early", "human_response",
                                   payload, digest(payload))
        resumed = result["runtime"].resume(request, actor=actor)
        assert resumed["operation_status"] == "committed"
        root, execution = result["runtime"]._records(result["run_locator"])
        assert execution.projection.value["run_status"] == "completed"
        index = loads((root / "artifact_index.json").read_bytes())["current"]
        assert index["analysis"] is None and index["review"] is None
        assert index["terminal"]["status"] == terminal
        member = next(m for m in index["terminal"]["members"] if m["logical_name"] == "memory_update.json")
        assert loads((root / member["canonical_path"]).read_bytes())["accepted_result"] is False
        assert [node for node, _ in agent.contexts] == ["method_planner"]
        responses = [r for r in execution.values if r["record_type"] == "human_response"]
        assert [r["event"] for r in responses] == ["submitted", "validated", "consumed"]
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        result["runtime"].resume(request, actor=actor)
        assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert len(agent.contexts) == 1
    finally:
        coordinator.close()


@pytest.mark.parametrize("mode", ["exception", "overrun", "epoch", "analysis_exception"])
def test_ended_resource_failure_settles_once_and_closes_original_run(tmp_path, mode):
    clock = FakeClock(100, 0)
    coordinator = Coordinator(tmp_path, clock=clock)
    actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
    returned = []

    class Port(StructuredOutcomes):
        def run(self, node, context, *, timeout_seconds):
            result = super().run(node, context, timeout_seconds=timeout_seconds)
            if mode == "analysis_exception" and node == "method_planner":
                returned.append(result)
                return result
            if mode in ("exception", "analysis_exception"):
                raise RuntimeError("Actual controlled port exception")
            if mode == "overrun":
                clock.advance(2)
            else:
                clock.epoch_id = "fake_clock_epoch_2"
            returned.append(result)
            return result

    agent = Port()
    try:
        result = run_canonical_graph(coordinator=coordinator, actor=actor, agent_port=agent,
            request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"))
        root, execution = result["runtime"]._records(result["run_locator"])
        assert execution.projection.value["run_status"] == "failed"
        reservations = [r for r in execution.values if r.get("event") == "resource_reserved"]
        settlements = [r for r in execution.values if r.get("event") == "resource_settled"]
        assert len(reservations) == len(settlements) == len(agent.contexts) == (2 if mode == "analysis_exception" else 1)
        payload = settlements[-1]["payload"]
        assert payload["actual"] is None
        assert payload["resource_operation_id"] == reservations[-1]["payload"]["resource_operation_id"]
        assert payload["tokens"] == payload["cost"] == {"state": "unknown", "value": None}
        if mode in ("exception", "analysis_exception"):
            receipt = {"schema_version": "0.1", "resource_operation_id": payload["resource_operation_id"],
                       "exception": {"type": "RuntimeError", "message": "Actual controlled port exception"}}
            assert payload["evidence_digest"] == digest(receipt)
        assert len(returned) == (0 if mode == "exception" else 1)
        failed = [r for r in execution.values if r.get("record_type") == "attempt" and r.get("event") == "finished"][-1]
        assert failed["status"] == "failed" and failed["error"]["type"] == "OrdinaryResourceFailure"
        index = loads((root / "artifact_index.json").read_bytes())["current"]
        assert index["analysis"] is None and index["terminal"] is None
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        result["runtime"].run(result["run_locator"])
        assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert len(agent.contexts) == len(reservations)
    finally:
        coordinator.close()


def test_expired_resource_owner_keeps_unsettled_without_redispatch(tmp_path):
    clock = FakeClock(100, 0)
    coordinator = Coordinator(tmp_path, clock=clock)
    actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}

    class Port(StructuredOutcomes):
        def run(self, node, context, *, timeout_seconds):
            value = super().run(node, context, timeout_seconds=timeout_seconds)
            clock.advance(31)
            return value

    agent = Port()
    request = StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1")
    try:
        with pytest.raises(ControlIntegrityError):
            run_canonical_graph(coordinator=coordinator, actor=actor, agent_port=agent, request=request)
        ledger, = tmp_path.glob("case/*/execution_history.jsonl")
        execution = parse_ledger(ledger.read_bytes())
        assert execution.projection.value["run_status"] == "running"
        assert len([r for r in execution.values if r.get("event") == "resource_reserved"]) == 1
        assert not any(r.get("event") == "resource_settled" for r in execution.values)
        assert not any(r.get("event") == "finished" for r in execution.values)
        before = {p.relative_to(ledger.parent).as_posix(): p.read_bytes() for p in ledger.parent.rglob("*") if p.is_file()}
        with pytest.raises(ControlIntegrityError, match="explicit recovery"):
            run_canonical_graph(coordinator=coordinator, actor=actor, agent_port=agent, request=request)
        assert before == {p.relative_to(ledger.parent).as_posix(): p.read_bytes() for p in ledger.parent.rglob("*") if p.is_file()}
        assert len(agent.contexts) == 1
    finally:
        coordinator.close()
