"""Original Human snapshot prefixes produced by scoped publication faults."""
from harness.temporary import mkdtemp
from pathlib import Path

from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, diagnostic


def human_trace(*, reason="Synthetic approved rerun", decision="approve_rerun", risk="low", unpublished=False, fault="publication"):
    output = Path(mkdtemp(prefix="lqcd-agent-b00c11-human-", dir="/private/tmp"))
    identities = HostIdentities("b00c11-human")
    with identities.installed():
        coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
        from helpers.product_failure_sources import ProductFailureSources
        sources = ProductFailureSources(coordinator)
        capture = ControlTrace(output, version="0.8", ordinary_sources=sources)
        class UnpublishedPrefix(BaseException):
            pass
        armed, receipts = False, []
        def observer(name, side, value):
            sources.observer(capture, name, side, value)
            if armed and not receipts and side == "after" and name == (
                    "invocation.attempt_finished" if fault == "publication" else "invocation.attempt_started"):
                from lqcd_agent.control.execution import parse_ledger
                records = parse_ledger(next(output.glob("*/*/execution_history.jsonl")).read_bytes()).values
                attempt = next(r for r in reversed(records) if r["record_type"] == "attempt")
                if attempt["attempt_kind"] == "human_gate" and attempt["node_name"] == "human_approval_gate":
                    from lqcd_agent.control.capabilities import InvocationLeases
                    capability, stored = next((r["capability_id"], loads(r["value"])) for r in
                        coordinator.connection.execute("SELECT capability_id,value FROM invocation_capabilities")
                        if loads(r["value"])["authorization"]["identity"]["attempt_id"] == attempt["attempt_id"])
                    producer = coordinator.get(stored["authorization"]["producer_operation_id"])
                    assert producer["operation_type"] == "resume_run" and producer["request"]["input_kind"] == "human_response"
                    receipts.append({"boundary": name, "side": side, "identity": stored["authorization"]["identity"],
                        "capability_id": capability, "producer_operation_id": producer["operation_id"],
                        "human_request_id": producer["request"]["input_snapshot"]["human_request_id"],
                        "completion_frozen": stored.get("completion_intent") is not None, "effect_count": len(agent.contexts)})
                    raise RuntimeError("Synthetic Human validator " + fault + " fault")
            if unpublished and side == "after" and name.startswith("control.advance_run.") and name.endswith(".result_committed"):
                capability = value["result"].get("capability_id")
                if capability:
                    from lqcd_agent.control.capabilities import InvocationLeases
                    _, stored = InvocationLeases(coordinator).get(capability)
                    if stored["authorization"]["identity"]["attempt_kind"] == "human_gate":
                        raise UnpublishedPrefix()
        coordinator.observer = observer
        agent = StructuredOutcomes({"analysis_engineer": diagnostic(status="failed", category="tool_failure",
            affected_layer="analysis", retryability="retryable", candidates=["analysis_engineer"], risk=risk)})
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        try:
            try:
                result = run_canonical_graph(coordinator=coordinator,
                    request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"), actor=actor, agent_port=sources.agent(agent))
            except UnpublishedPrefix:
                trace = capture.finish(coordinator)
                resumed = {"operation_status": "not_submitted", "contract_only": False, "B04_owned": False}
                (output / "raw.json").write_bytes(canonical_bytes(trace))
                (output / "resume.json").write_bytes(canonical_bytes(resumed))
                (output / "allocations.json").write_bytes(canonical_bytes(identities.allocations))
                return trace, output, resumed
            state = result["state"]
            payload = {**result["run_locator"], "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
                "decision": decision, "conditions": [], "reason": reason, "decided_by": "operator"}
            armed = True
            resumed = result["runtime"].resume(ResumeRunRequest(result["run_locator"], state["active_pause"]["pause_id"],
                "resume", "human_response", payload, digest(payload)), actor=actor)
            assert receipts and resumed["operation_status"] == ("in_progress" if fault == "publication" else "recovery_required")
            (output / "fault-receipt.json").write_bytes(canonical_bytes(receipts))
            trace = capture.finish(coordinator)
            (output / "raw.json").write_bytes(canonical_bytes(trace))
            (output / "resume.json").write_bytes(canonical_bytes(resumed))
            (output / "allocations.json").write_bytes(canonical_bytes(identities.allocations))
            return trace, output, resumed
        finally:
            coordinator.close()
