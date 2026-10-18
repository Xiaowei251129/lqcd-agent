"""Canonical routes use production selectors and original control publications."""
from pathlib import Path
from copy import deepcopy
import tempfile

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import digest, loads
from lqcd_agent.graph.routing import PRODUCT_ROUTES
from lqcd_agent.graph.run_graph import run_canonical_graph


def diagnostic(**updates):
    value = {"status": "success", "category": "validated_domain", "affected_layer": "none", "evidence": [],
             "retryability": "not_retryable", "candidates": [], "confidence": "unique", "fingerprint": None,
             "human_need": None, "risk": "low"}
    return {**value, **updates}


class StructuredOutcomes:
    """Inject domain facts only; no control, graph, state or route patches."""

    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.contexts = []
        self.resource_preimages = []

    def run(self, node, context, *, timeout_seconds):
        self.contexts.append((node, context))
        assert timeout_seconds == 1
        assert set(context) == {"identity", "direct_parent_attempt_id", "root_goal", "current_evidence",
                                "remediation", "relevant_history", "budget_summary"}
        assert len(context["relevant_history"]) <= 4
        outcome = self.outcomes.get(node, diagnostic())
        if isinstance(outcome, list):
            outcome = outcome.pop(0)
        result = {"diagnostic": dict(outcome), "content": {"code_needed": False} if node == "method_planner" else {"domain": "validated"}}
        self.resource_preimages.extend([deepcopy(context), deepcopy(result)])
        return result


def canonical(outcomes=None, *, profile="balanced_v1"):
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-product-", dir="/private/tmp"))
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
    port = StructuredOutcomes(outcomes)
    request = StartRunRequest("case", inputs, digest(inputs), "start", profile)
    try:
        result = run_canonical_graph(coordinator=coordinator, request=request, actor=actor, agent_port=port)
    except BaseException:
        coordinator.close()
        raise
    return coordinator, actor, port, result


def test_no_code_completes_in_the_compiled_product_graph_and_replays_without_calls():
    coordinator, _, port, result = canonical()
    try:
        state = result["state"]
        assert state["run_status"] == "completed"
        runtime = result["runtime"]
        root, execution = runtime._records(result["run_locator"])
        transitions = [row for row in execution.values if row["record_type"] == "transition"]
        assert [(row["source_node"], row["target_node"]) for row in transitions] == [
            ("START", "method_planner"), ("method_planner", "analysis_engineer"),
            ("analysis_engineer", "scientific_reviewer"), ("scientific_reviewer", "decision_coordinator"),
            ("decision_coordinator", "memory_report"), ("memory_report", None)]
        assert [node for node, _ in port.contexts] == ["method_planner", "analysis_engineer", "scientific_reviewer"]
        before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        runtime.run(result["run_locator"])
        assert len(port.contexts) == 3
        assert {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before
        index = loads((root / "artifact_index.json").read_bytes())
        assert index["current"]["code"] is None and index["current"]["terminal"]["status"] == "accepted"
        graph = runtime.app.get_graph()
        assert len(graph.edges) == sum(len(targets) for targets in PRODUCT_ROUTES.values()) == 17
        analysis = next(row for row in execution.values if row["record_type"] == "attempt" and row["attempt_kind"] == "analysis_engineer")
        producer = next(loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM invocation_capabilities")
                        if loads(row[0])["authorization"]["identity"]["attempt_id"] == analysis["attempt_id"])
        snapshot = coordinator.snapshot(producer["authorization"]["producer_operation_id"])
        assert snapshot["reservation"]["target_preparation_snapshot"]["preparation_kind"] == "not_applicable"
    finally:
        coordinator.close()


def test_failed_analysis_escalates_to_a_null_target_human_pause():
    coordinator, _, port, result = canonical({"analysis_engineer": diagnostic(status="failed", category="tool_failure",
        affected_layer="analysis", retryability="retryable", candidates=["analysis_engineer"], risk="low")})
    try:
        state = result["state"]
        assert state["run_status"] == "paused"
        _, execution = result["runtime"]._records(result["run_locator"])
        transitions = [row for row in execution.values if row["record_type"] == "transition"]
        assert transitions[-1]["source_node"] == "decision_coordinator" and transitions[-1]["target_node"] == "human_gate"
        pause = next(row for row in reversed(execution.values) if row["record_type"] == "pause")
        assert pause["status"] == "opened" and pause["target_attempt_id"] is None
        assert len(port.contexts) == 2
    finally:
        coordinator.close()


def test_re_review_fallback_has_a_scoped_typed_packet_and_a_new_attempt():
    coordinator, _, port, result = canonical({"scientific_reviewer": [diagnostic(category="review_incomplete", affected_layer="review",
        retryability="retryable", candidates=["scientific_reviewer"], risk="medium"), diagnostic()]})
    try:
        assert result["state"]["run_status"] == "completed"
        reviews = [context for node, context in port.contexts if node == "scientific_reviewer"]
        assert len(reviews) == 2
        packet = reviews[1]["remediation"]
        assert packet["target_node"] == "scientific_reviewer" and packet["human_authorization"] is None
        assert reviews[0]["identity"]["attempt_id"] != reviews[1]["identity"]["attempt_id"]
        assert reviews[0]["identity"]["cycle_id"] == reviews[1]["identity"]["cycle_id"]
        assert result["state"]["budget"]["dimensions"]["automatic_re_review_per_cycle"]["used"] == 1
    finally:
        coordinator.close()
