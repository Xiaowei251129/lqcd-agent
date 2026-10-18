"""Production work targets cannot replace Host identities or bypass guards."""
from pathlib import Path
import tempfile

import pytest

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, canonical, diagnostic


@pytest.mark.parametrize("field", ["run_id", "attempt_id", "producer", "status", "schema_version"])
@pytest.mark.parametrize("same_value", [False, True])
def test_agent_reserved_content_is_rejected_before_domain_publication(field, same_value):
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-host-boundary-", dir="/private/tmp"))
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}

    class ReservedContent(StructuredOutcomes):
        def run(self, node, context, *, timeout_seconds):
            result = super().run(node, context, timeout_seconds=timeout_seconds)
            host_value = {**context["identity"], "producer": node, "status": "success", "schema_version": "0.1"}[field]
            result["content"][field] = host_value if same_value else "foreign"
            return result

    agent = ReservedContent()
    try:
        with pytest.raises(ControlIntegrityError, match="reserved Host fields"):
            run_canonical_graph(coordinator=coordinator, actor=actor, agent_port=agent,
                request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"))
        ledger_path, = output.glob("case/*/execution_history.jsonl")
        root = ledger_path.parent
        records = parse_ledger(ledger_path.read_bytes()).values
        assert [node for node, _ in agent.contexts] == ["method_planner"]
        assert len([row for row in records if row.get("event") == "resource_reserved"]) == 1
        settlements = [row for row in records if row.get("event") == "resource_settled"]
        assert len(settlements) == 1 and settlements[0]["payload"]["actual"] is not None
        assert all(pointer is None for pointer in loads((root / "artifact_index.json").read_bytes())["current"].values())
        assert not list(root.glob("attempts/*/method_plan.json"))
        assert [(row["source_node"], row["target_node"]) for row in records if row["record_type"] == "transition"] == [
            ("START", "method_planner")]
        assert not (root / "memory_update.json").exists()
    finally:
        coordinator.close()


@pytest.mark.parametrize("updates", [
    {"risk": "high"},
    {"risk": "critical"},
    {"confidence": "ambiguous"},
    {"confidence": "insufficient"},
    {"human_need": "clarification"},
    {"human_need": "approval"},
    {"human_need": "external_action"},
    {"category": "security"},
    {"category": "policy"},
    {"category": "data"},
    {"category": "scientific_method", "status": "failed"},
])
def test_analysis_guard_escalates_before_next_work_target(updates):
    node = "analysis_engineer"
    coordinator, _, agent, result = canonical({node: diagnostic(**updates)})
    try:
        assert result["state"]["run_status"] == "paused"
        root, execution = result["runtime"]._records(result["run_locator"])
        expected_work = ["method_planner", "analysis_engineer"]
        assert [name for name, _ in agent.contexts] == expected_work
        transitions = [row for row in execution.values if row["record_type"] == "transition"]
        assert [(row["source_node"], row["target_node"]) for row in transitions[-2:]] == [
            (node, "decision_coordinator"), ("decision_coordinator", "human_gate")]
        attempts = [row for row in execution.values if row["record_type"] == "attempt" and row["event"] == "scheduled"]
        assert [row["attempt_kind"] for row in attempts] == expected_work + ["decision_coordinator", "human_gate"]
        current = loads((root / "artifact_index.json").read_bytes())["current"]
        assert current["review"] is None and current["terminal"] is None
        assert current["plan"] is not None
        assert current["analysis"] is not None
        assert not (root / "memory_update.json").exists()
    finally:
        coordinator.close()
