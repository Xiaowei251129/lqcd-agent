"""Actual compiled product trajectories with passive, versioned source evidence."""
from harness.temporary import mkdtemp
from copy import deepcopy
from pathlib import Path

from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from helpers.prior_code_evidence_sources import PriorCodeSources
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, diagnostic


MODES = ("forward", "planner_input", "planner_failure", "analysis_failure", "re_review", "rerun",
         "replan", "repetition", "grant", "high_risk", "ambiguous", "held")


def trajectory(mode, *, trace_version="0.9", observer=None):
    assert mode in MODES
    assert trace_version in ("0.9", "0.10")
    fallback = {"re_review": "scientific_reviewer", "rerun": "analysis_engineer", "replan": "method_planner",
                "repetition": "scientific_reviewer", "grant": "analysis_engineer"}.get(mode)
    outcomes = {}
    if fallback is not None:
        value = diagnostic(category="method_revision" if mode == "replan" else "review_incomplete",
            affected_layer="plan" if mode == "replan" else "analysis" if fallback == "analysis_engineer" else "review",
            retryability="retryable", candidates=[fallback], risk="medium")
        outcomes["scientific_reviewer"] = [value, deepcopy(value) if mode in ("repetition", "grant") else diagnostic(), diagnostic()]
    elif mode in ("planner_input", "planner_failure", "held"):
        outcomes["method_planner"] = diagnostic(status="needs_input" if mode == "planner_input" else
            "failed" if mode == "planner_failure" else "pending", category="planning_failure",
            affected_layer="plan", human_need="clarification" if mode == "planner_input" else "approval")
    elif mode == "analysis_failure":
        outcomes["analysis_engineer"] = diagnostic(status="failed", category="tool_failure", affected_layer="analysis",
                                                    human_need="approval")
    elif mode in ("high_risk", "ambiguous"):
        outcomes["analysis_engineer"] = diagnostic(**({"risk": "high"} if mode == "high_risk" else {"confidence": "ambiguous"}))
    output = Path(mkdtemp(prefix="lqcd-agent-b04-trajectory-" + mode + "-", dir="/private/tmp"))
    with HostIdentities("b04-trajectory-" + mode).installed():
        coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
        try:
            if trace_version == "0.10":
                from helpers.ordinary_publication_prefix_sources import PublicationPrefixSources
                sources = PublicationPrefixSources(coordinator)
            else:
                sources = PriorCodeSources(coordinator)
            capture = ControlTrace(output, version=trace_version, ordinary_sources=sources)
            def collect(name, side, value):
                sources.observer(capture, name, side, value)
                if observer is not None:
                    observer(name, side, value, coordinator, capture, sources, agent)
            collect.production_hooks = getattr(observer, "production_hooks", {})
            coordinator.observer = collect
            agent = StructuredOutcomes(outcomes)
            actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
            inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
            result = run_canonical_graph(coordinator=coordinator, request=StartRunRequest("case", inputs, digest(inputs),
                "start", "balanced_v1"), actor=actor, agent_port=sources.agent(agent))
            runtime, locator = result["runtime"], result["run_locator"]
            decisions = ["approve_rerun", "approve_budget_window"] if mode == "grant" else ["approve_rerun"] if mode == "rerun" else [
                "approve_with_conditions" if mode == "planner_input" else "reject_or_hold"] if mode in (
                    "planner_input", "planner_failure", "analysis_failure", "held") else []
            requests = []
            for position, decision in enumerate(decisions):
                _, execution = runtime._records(locator)
                state = execution.projection.value
                assert state["run_status"] == "paused"
                payload = {**locator, "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
                    "decision": decision, "conditions": [], "reason": "A bounded response to the original work", "decided_by": "operator"}
                request = ResumeRunRequest(locator, state["active_pause"]["pause_id"], "b04-response:" + str(position),
                                          "human_response", payload, digest(payload))
                requests.append(request)
                assert runtime.resume(request, actor=actor)["operation_status"] == "committed"
            root, execution = runtime._records(locator)
            state = execution.projection.value
            index = loads((root / "artifact_index.json").read_bytes())
            transitions = [row for row in execution.values if row["record_type"] == "transition"]
            scheduled = [row for row in execution.values if row["record_type"] == "attempt" and row["event"] == "scheduled"]
            counts = len(agent.contexts)
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            runtime.run(locator)
            if requests:
                runtime.resume(requests[-1], actor=actor)
            assert len(agent.contexts) == counts
            assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            assert index["current"]["code"] is None
            assert state["run_status"] == ("paused" if mode in ("repetition", "high_risk", "ambiguous") else "completed")
            if fallback is not None:
                targets = [row for row in scheduled if row["attempt_kind"] == fallback]
                expected = 3 if mode == "grant" else 2
                assert len(targets) == expected and len({row["attempt_id"] for row in targets}) == expected
                assert len({row["cycle_id"] for row in targets}) == (2 if mode == "replan" else 1)
                contexts = [context for node, context in agent.contexts if node == fallback]
                for context in contexts[1:]:
                    packet = context["remediation"]
                    assert packet["target_node"] == fallback and packet["parent_attempt_id"] == context["direct_parent_attempt_id"]
                    assert packet["evidence"] and len(context["relevant_history"]) <= 4
                    assert set(context) == {"identity", "direct_parent_attempt_id", "root_goal", "current_evidence",
                                            "remediation", "relevant_history", "budget_summary"}
            issues = [row for row in execution.values if row.get("event") == "grant_issued"]
            consumes = [row for row in execution.values if row.get("event") == "grant_consumed"]
            assert len(issues) == len(consumes) == int(mode == "grant")
            if issues:
                assert issues[0]["payload"]["budget_grant_id"] == consumes[0]["payload"]["budget_grant_id"]
                assert any(row["transition_id"] == consumes[0]["payload"]["transition_id"] and
                           row["target_attempt_id"] == issues[0]["payload"]["target_attempt_id"] for row in transitions)
            if mode == "repetition":
                failures = [row["payload"] for row in execution.values if row.get("event") == "failure_observed"]
                assert [row["occurrence"] for row in failures] == [1, 2]
                assert failures[0]["fingerprint"] == failures[1]["fingerprint"]
            terminal = index["current"]["terminal"]
            if mode in ("planner_input", "planner_failure", "analysis_failure", "held"):
                assert terminal["status"] == ("pending" if mode == "planner_input" else "rejected")
                member = next(m for m in terminal["members"] if m["logical_name"] == "memory_update.json")
                assert not loads((root / member["canonical_path"]).read_bytes())["accepted_result"]
            trace = capture.finish(coordinator)
            facts = {"mode": mode, "run_status": state["run_status"], "calls": [node for node, _ in agent.contexts],
                     "routes": [[row["source_node"], row["target_node"]] for row in transitions],
                     "cycles": state["cycle_index"], "grant_issues": len(issues), "grant_consumes": len(consumes),
                     "duplicate_readonly": True}
            for name, value in (("raw", trace), ("facts", facts),
                                ("contexts", [[node, context] for node, context in agent.contexts])):
                (output / (name + ".json")).write_bytes(canonical_bytes(value))
            return trace, output, facts
        finally:
            coordinator.close()
