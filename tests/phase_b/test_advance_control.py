"""B02 advances deterministic typed domain ports without selecting product routes."""
from harness.temporary import mkdtemp
from pathlib import Path

import pytest

from lqcd_agent.control.budget import WORK_KINDS
from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.operations import AdvanceRunRequest, RouteAdmission
from lqcd_agent.control.protocol import operation_variant
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from lqcd_agent.graph.state import canonical_attempt_kind


class SyntheticDomainRoute:
    """Harness-only domain input; B02 still verifies capacity, heads and ordering."""

    def __init__(self, target):
        self.target, self.calls = target, 0

    def admit(self, view):
        self.calls += 1
        state = view["state"]
        kind = canonical_attempt_kind(self.target) if self.target is not None else None
        changes = {"work_attempts_per_run": int(kind in WORK_KINDS),
                   "control_attempts_per_run": int(kind is not None and kind not in WORK_KINDS), "transitions_per_run": 1}
        dimensions = {key: {**value, "projected_after": value["used"] + changes.get(key, 0)}
                      for key, value in state["budget"]["dimensions"].items()}
        body = {"schema_version": "0.1", "proposal_id": digest({"source_attempt": state["attempt_id"], "target": self.target}),
                "proposed_action": "route", "target_kind": kind, "risk": "low", "fingerprint_digest": None,
                "occurrence": 0, "dimensions": dimensions, "budget_grant_id": None, "decision": "allow",
                "reason_code": "deterministic_external_domain_adapter", "next_control_action": "advance"}
        return RouteAdmission(self.target, self.target or "end", "control_harness", "deterministic_external_domain_adapter",
                              {**body, "decision_digest": digest(body)}, {"preparation_kind": "not_applicable", "not_applicable_reason": "no_code_bundle"})


@pytest.mark.parametrize("target", ["decision_coordinator", "code_agent", "analysis_engineer", "scientific_reviewer", "memory_report"])
def test_advance_allocates_then_prepares_and_activates_exact_capability(target):
    root = Path(mkdtemp(prefix="lqcd-agent-b02-advance-", dir="/private/tmp"))
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    actor = ActorContext("operator", "human", ("control.internal", "start"))
    adapter = SyntheticDomainRoute(target)
    plane = ControlPlane(coordinator, worker_id="worker", route_adapter=adapter)
    inputs = {"root_goal": {"goal": "synthetic"}, "input_snapshot": {"data": "synthetic"}}
    source = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "phase_b_test"), actor=actor)
    locator = source["result"]["run_locator"]
    leases = InvocationLeases(coordinator)

    class Target:
        def invoke(self, identity):
            return TargetOutcome("pending", {"current_artifact_ids": {}})

    try:
        original = source["result"]["capability_id"]
        leases.acquire(original, "consumer", expected_epoch=0, lease_seconds=10)
        leases.invoke(original, "consumer", 1, Target())
        request = AdvanceRunRequest(locator, "attempt_000001", "advance")
        result = plane.advance_run(request, actor=actor)
        assert result["operation_status"] == "committed"
        assert adapter.calls == 1 and plane.advance_run(request, actor=actor) == result and adapter.calls == 1
        phases = [row["phase"] for row in coordinator.history(result["operation_id"])]
        assert phases == [phase for phase in operation_variant("advance_run", "not_applicable")["phases"] if phase != "terminal_transition_committed"]
        run = root / locator["case_id"] / locator["run_id"]
        records = parse_ledger((run / "execution_history.jsonl").read_bytes()).values
        assert [row["record_type"] for row in records[-3:]] == ["budget", "attempt", "transition"]
        assert records[-2]["status"] == "scheduled" and records[-2]["attempt_id"] == "attempt_000002"
        capability = result["result"]["capability_id"]
        if target == "code_agent":
            assert leases.get(capability)[1]["authorization"]["scope"] == "external_prestart_only"
            with pytest.raises(ControlIntegrityError, match="scope"):
                leases.acquire(capability, "code", expected_epoch=0, lease_seconds=10)
        else:
            leases.acquire(capability, "ordinary", expected_epoch=0, lease_seconds=10)
            finished = leases.invoke(capability, "ordinary", 1, Target())
            assert finished["attempt_id"] == "attempt_000002" and finished["attempt_status"] == "pending"
    finally:
        coordinator.close()
