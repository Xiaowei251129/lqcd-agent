"""Immutable Coordinator inputs fence every fallback before its next effect."""
from harness.temporary import mkdtemp
from pathlib import Path

import pytest

from harness import pytest_evidence
from harness.pytest_evidence import observe
from harness.strict_json import write_new, sha
from helpers.b04_code_product import code_product, deliver_product_code
from helpers.trace_sources import current_binding
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
from lqcd_agent.graph.state import product_context
from test_b04_product_graph import StructuredOutcomes, diagnostic


TARGETS = ("scientific_reviewer", "analysis_engineer", "code_agent", "method_planner")
FAULTS = ("target", "parent", "evidence", "budget_scope", "human_authorization", "full_audit", "member")


class GuardCut(BaseException):
    """Stop at a committed production boundary before entering the new target."""


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("fault", FAULTS)
def test_fallback_packet_tampering_has_no_new_target_effect(target, fault):
    holder, transitions = {}, []

    def observer(name, side, value):
        if holder and name == "control.advance_run.not_applicable.result_committed" and side == "after":
            transition = loads(holder["coordinator"].snapshot(value["operation_id"])["reservation"]["canonical_transition_bytes"])
            if transition["source_node"] == "decision_coordinator" and transition["target_node"] == target:
                transitions.append(transition)
        if transitions and name == "coordinator.database_commit" and side == "after":
            raise GuardCut()

    layer = {"scientific_reviewer": "review", "analysis_engineer": "analysis", "code_agent": "code", "method_planner": "plan"}[target]
    failure = diagnostic(category="method_revision" if layer == "plan" else "implementation_failure",
        affected_layer=layer, retryability="retryable", candidates=[target], risk="medium")
    outcomes = {"scientific_reviewer": [failure, diagnostic()]}
    backend = None
    if target == "code_agent":
        coordinator, actor, agent, backend, host, _, result = code_product(outcomes=outcomes, observer=observer)
        runtime, locator = result["runtime"], result["run_locator"]
    else:
        output = Path(mkdtemp(prefix="lqcd-agent-b04-packet-guard-", dir="/private/tmp"))
        coordinator = Coordinator(output, clock=FakeClock(100, 0), observer=observer)
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        agent = StructuredOutcomes(outcomes)
        runtime = CanonicalProductRuntime(coordinator, worker_id="product-host", actor=actor, agent_port=agent)
        inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        started = runtime.plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"), actor=actor)
        locator = started["result"]["run_locator"]
    holder["coordinator"] = coordinator
    try:
        try:
            if backend is not None:
                deliver_product_code(coordinator, actor, backend, host, result)
            else:
                runtime.run(locator)
            _, execution = runtime._records(locator)
            state = execution.projection.value
            assert state["run_status"] == "paused"
            payload = {**locator, "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
                "decision": "request_code_change" if target == "code_agent" else "approve_rerun",
                "conditions": [], "reason": "Authorize the original bounded remediation", "decided_by": "operator"}
            request = ResumeRunRequest(locator, state["active_pause"]["pause_id"], "b04-guard-approval",
                                       "human_response", payload, digest(payload))
            runtime.resume(request, actor=actor)
        except GuardCut:
            pass
        else:
            raise AssertionError("The original product target boundary was not reached")
        coordinator.observer = None
        transition, = transitions
        root, _ = runtime._records(locator)
        identity = {**locator, "attempt_id": transition["target_attempt_id"], "attempt_kind": target}
        context = product_context(root, identity)
        assert context["remediation"]["target_node"] == target
        assert context["remediation"]["parent_attempt_id"] == context["direct_parent_attempt_id"]
        assert len(context["relevant_history"]) <= 4
        assert not ({"event_log", "route_trace", "checkpoint_state", "grant_authority"} & context.keys())
        history = [loads(line) for line in (root / "artifact_history.jsonl").read_bytes().splitlines()]
        pointer = next(row["pointer"] for row in history if row["event"] == "registered" and
                       row["attempt_id"] == transition["source_attempt_id"])
        member = Path(pointer["state_paths"]["decision_log_path"])
        original = member.read_bytes()
        value = loads(original)
        packet = value["remediation"]
        if fault == "target": packet["target_node"] = "memory_report"
        elif fault == "parent": packet["parent_attempt_id"] = "foreign"
        elif fault == "evidence": packet["evidence"][0]["sha256"] = "f" * 64
        elif fault == "budget_scope": packet["budget_policy_digest"] = "f" * 64
        elif fault == "human_authorization":
            packet["human_authorization"] = {"human_request_id": "foreign", "human_response_id": "foreign",
                                            "response_digest": "f" * 64, "target_node": target}
        elif fault == "full_audit": packet["event_log"] = [{"route": "method_planner"}]
        member.write_bytes(b"{" if fault == "member" else canonical_bytes(value))
        snapshot = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        calls, dispatches = len(agent.contexts), len(backend.dispatches) if backend is not None else 0
        errors = []
        for _ in range(2):
            with pytest.raises(ControlIntegrityError) as refused:
                runtime.run(locator)
            errors.append({"type": type(refused.value).__name__, "message": str(refused.value)})
            assert len(agent.contexts) == calls
            assert (len(backend.dispatches) if backend is not None else 0) == dispatches
            assert snapshot == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        capability, = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM invocation_capabilities")
                       if loads(row[0])["authorization"]["identity"] == identity]
        assert capability["started_intent"] is None
        assert runtime._records(locator)[1].projection.value["run_status"] == "running"
        (coordinator.root / "guard-original-decision.json").write_bytes(original)
        (coordinator.root / "guard-tampered-decision.bin").write_bytes(member.read_bytes())
        (coordinator.root / "guard-result.json").write_bytes(canonical_bytes({"target": target, "fault": fault,
            "binding": current_binding(), "errors": errors, "calls": calls, "dispatches": dispatches,
            "no_new_effect": True, "repeat_readonly": True, "B04_owned_case": False}))
        (coordinator.root / "guard-context-before.json").write_bytes(canonical_bytes(context))
        (coordinator.root / "guard-transition.json").write_bytes(canonical_bytes(transition))
        writer = pytest_evidence.ACTIVE
        if writer is not None:
            retained = sorted(coordinator.root.glob("guard-*"))
            write_new(writer.output.parent / ("b04-packet-" + target + "-" + fault + ".json"),
                {"nodeid": writer.nodeid, "binding": current_binding(), "root": str(coordinator.root),
                 "files": [{"path": str(path), "sha256": sha(path.read_bytes())} for path in retained],
                 "B04_owned_case": False})
        observe("B04-PACKET-" + target + "-" + fault, {"kind": "boolean", "value": True},
                ["actual_production_path", "no_new_effect", "original_authority_rejected"])
    finally:
        coordinator.close()
