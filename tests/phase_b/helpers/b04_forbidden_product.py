"""Forbidden proposals cross the actual product graph, never a patched selector."""
from pathlib import Path
import tempfile

from helpers.b04_trajectories import trajectory
from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from helpers.ordinary_publication_prefix_sources import PublicationPrefixSources
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, diagnostic


MODES = ("analysis_authority", "reviewer_authority", "human_authority", "terminal_sink", "free_advice",
         "old_result", "risk_gate", "single_use_human", "permanent_policy")


def forbidden_trace(mode):
    assert mode in MODES
    delegated = {"human_authority": "rerun", "old_result": "re_review", "risk_gate": "high_risk",
                 "single_use_human": "grant"}.get(mode)
    if delegated:
        raw, output, facts = trajectory(delegated, trace_version="0.10")
        records = [row["value"] for row in raw["proof"]["objects"] if row["kind"] == "execution_0_4"]
        transitions = [row for row in records if row["record_type"] == "transition"]
        if mode == "human_authority":
            assert all(row["target_node"] == "decision_coordinator" for row in transitions
                       if row["source_node"] in ("human_gate", "human_approval_gate"))
        elif mode == "old_result":
            registrations = [row["value"] for row in raw["proof"]["objects"] if
                row["value"].get("event") == "registered" and row["value"].get("slot") == "review"]
            assert len(registrations) == 2 and registrations[0]["artifact_id"] != registrations[1]["artifact_id"]
            members = [member for row in registrations for member in row["members"]]
            assert len({m["canonical_path"] for m in members}) == len(members)
        elif mode == "risk_gate":
            assert facts["run_status"] == "paused"
            assert all(row["target_node"] not in ("code_agent", "method_planner", "analysis_engineer", "scientific_reviewer")
                       for row in transitions if row["source_node"] == "decision_coordinator")
        else:
            assert facts["grant_issues"] == facts["grant_consumes"] == 1
        return raw, output, {**facts, "forbidden": mode}
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-forbidden-", dir="/private/tmp"))
    with HostIdentities("b04-forbidden-" + mode).installed():
        coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
        try:
            sources = PublicationPrefixSources(coordinator)
            capture = ControlTrace(output, version="0.10", ordinary_sources=sources)
            coordinator.observer = lambda name, side, value: sources.observer(capture, name, side, value)
            outcomes = {}
            if mode == "analysis_authority":
                outcomes["analysis_engineer"] = diagnostic(status="failed", category="implementation_failure", affected_layer="code",
                    candidates=["code_agent", "method_planner"], retryability="retryable", confidence="ambiguous", risk="high")
            elif mode == "reviewer_authority":
                outcomes["scientific_reviewer"] = diagnostic(category="review_incomplete", affected_layer="review",
                    candidates=["analysis_engineer", "code_agent", "method_planner"], retryability="retryable", confidence="ambiguous", risk="high")
            class Port(StructuredOutcomes):
                def run(self, node, context, *, timeout_seconds):
                    assert node not in ("memory_report", "decision_coordinator", "human_gate")
                    result = super().run(node, context, timeout_seconds=timeout_seconds)
                    if mode in ("free_advice", "permanent_policy"):
                        result["content"].update(route="code_agent", proposed_follow_up_route="method_planner",
                            event_log=[{"route": "code_agent"}], routing_policy={"analysis_engineer": "code_agent"},
                            skills={"next_action": "unbounded_loop"})
                    return result
            agent = Port(outcomes)
            actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
            inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
            result = run_canonical_graph(coordinator=coordinator, request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"),
                actor=actor, agent_port=sources.agent(agent))
            runtime, locator = result["runtime"], result["run_locator"]
            root, execution = runtime._records(locator)
            policy = (root / "budget_policy.json").read_bytes()
            transitions = [row for row in execution.values if row["record_type"] == "transition"]
            if mode in ("analysis_authority", "reviewer_authority"):
                source = "analysis_engineer" if mode == "analysis_authority" else "scientific_reviewer"
                assert [row["target_node"] for row in transitions if row["source_node"] == source] == ["decision_coordinator"]
                assert execution.projection.value["run_status"] == "paused"
                assert not any(row["source_node"] == "decision_coordinator" and row["target_node"] in
                    ("code_agent", "method_planner", "analysis_engineer", "scientific_reviewer") for row in transitions)
            else:
                assert [row["target_node"] for row in transitions] == ["method_planner", "analysis_engineer", "scientific_reviewer",
                    "decision_coordinator", "memory_report", None]
                assert execution.projection.value["run_status"] == "completed"
            for _, context in agent.contexts:
                assert set(context) == {"identity", "direct_parent_attempt_id", "root_goal", "current_evidence",
                                       "remediation", "relevant_history", "budget_summary"}
                assert len(context["relevant_history"]) <= 4
                assert not ({"event_log", "route_trace", "checkpoint_state", "capability_id", "grant_authority"} & context.keys())
            snapshot = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            calls = len(agent.contexts)
            runtime.run(locator)
            assert len(agent.contexts) == calls and policy == (root / "budget_policy.json").read_bytes()
            assert snapshot == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            raw = capture.finish(coordinator)
            facts = {"forbidden": mode, "run_status": execution.projection.value["run_status"], "calls": calls,
                     "duplicate_readonly": True, "policy_unchanged": True}
            for name, value in (("raw", raw), ("facts", facts)):
                (output / (name + ".json")).write_bytes(canonical_bytes(value))
            return raw, output, facts
        finally:
            coordinator.close()
