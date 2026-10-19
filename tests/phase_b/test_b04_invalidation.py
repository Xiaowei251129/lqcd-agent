"""Repeated product targets freeze every source cleared by the A03 policy."""
from harness.temporary import mkdtemp
from dataclasses import replace
from pathlib import Path

import pytest

from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import AdvanceRunRequest
from lqcd_agent.control.strict_json import loads
from test_advance_control import SyntheticDomainRoute
from test_bootstrap_control import start
from test_invocation_artifacts import ArtifactTarget


class ReplanRoute(SyntheticDomainRoute):
    def admit(self, view):
        admitted = super().admit(view)
        dimensions = admitted.budget_decision["dimensions"]
        dimensions["cycles_per_run"]["projected_after"] += 1
        from lqcd_agent.control.strict_json import digest
        decision = {key: value for key, value in admitted.budget_decision.items() if key != "decision_digest"}
        return replace(admitted, trigger_reason="replan", budget_decision={**decision, "decision_digest": digest(decision)})


@pytest.mark.parametrize("target", ["analysis_engineer", "decision_coordinator", "method_planner"])
def test_repeat_target_preserves_invalidation_sources_and_history(target):
    output = Path(mkdtemp(prefix="lqcd-agent-b04-repeat-", dir="/private/tmp"))
    coordinator, _, source = start(output)
    locator = source["result"]["run_locator"]
    root = output / locator["case_id"] / locator["run_id"]
    actor = ActorContext("operator", "human", ("control.internal",))
    leases = InvocationLeases(coordinator)
    capability = source["result"]["capability_id"]
    try:
        for position, (slot, next_node) in enumerate((("plan", "analysis_engineer"),
                                                     ("analysis", "decision_coordinator"),
                                                     ("decision", target)), 1):
            leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
            state = leases.invoke(capability, "consumer", 1, ArtifactTarget(slot, root))
            before = loads((root / "artifact_index.json").read_bytes())["current"]
            history = (root / "artifact_history.jsonl").read_bytes()
            adapter = ReplanRoute(next_node) if next_node == "method_planner" else SyntheticDomainRoute(next_node)
            plane = ControlPlane(coordinator, worker_id="worker", route_adapter=adapter)
            result = plane.advance_run(AdvanceRunRequest(locator, state["attempt_id"], f"advance-{position}"), actor=actor)
            assert result["operation_status"] == "committed", result
            capability = result["result"]["capability_id"]
        from lqcd_agent.artifacts.registry import INVALIDATED_SLOTS_BY_TARGET_KIND
        expected = {slot: before[slot]["artifact_id"] for slot in INVALIDATED_SLOTS_BY_TARGET_KIND[target]
                    if before[slot] is not None}
        records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        allocated = next(row for row in records if row["record_type"] == "attempt" and
                         row["event"] == "scheduled" and row["attempt_id"] == "attempt_000004")
        assert allocated["input_references"]["current_artifact_ids"] == expected
        assert (root / "artifact_history.jsonl").read_bytes().startswith(history)
        cleared = [loads(line) for line in (root / "artifact_history.jsonl").read_bytes()[len(history):].splitlines()]
        assert {row["slot"]: row["prior_artifact_id"] for row in cleared} == expected
        for slot in expected:
            for member in before[slot]["members"]:
                assert (root / member["canonical_path"]).is_file()
        assert allocated["cycle_id"] == ("cycle_0002" if target == "method_planner" else "cycle_0001")
    finally:
        coordinator.close()
