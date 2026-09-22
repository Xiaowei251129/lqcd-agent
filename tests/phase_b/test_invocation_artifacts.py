"""Actual A03 bundles flow through the fenced B02 invocation publication port."""
from pathlib import Path
import tempfile

import pytest

from lqcd_agent.artifacts.registry import STATE_FIELDS_BY_SLOT
from lqcd_agent.control.capabilities import ArtifactOutput, InvocationLeases, TargetOutcome
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import AdvanceRunRequest, CloseRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from test_advance_control import SyntheticDomainRoute
from test_bootstrap_control import start


class ArtifactTarget:
    """Synthetic domain content with real canonical membership and registration."""

    FILES = {"plan": ("method_plan.json", "coder_task_packet.yaml"),
             "analysis": ("run_result.json", "analysis_outputs/result.json"),
             "decision": ("decision_log.json",), "terminal": ("memory_update.md", "final_report.md")}

    def __init__(self, slot, root, *, status="synthetic"):
        self.slot, self.root, self.status = slot, root, status

    def invoke_with_artifacts(self, identity, port):
        paths = tuple(port.write_member(name, b'{"synthetic": true}\n') for name in self.FILES[self.slot])
        state_paths = dict(zip(STATE_FIELDS_BY_SLOT[self.slot], map(str, paths)))
        if self.slot == "analysis":
            state_paths["analysis_outputs_dir"] = str(paths[-1].parent)
        current = loads((self.root / "artifact_index.json").read_bytes())["current"]
        refs = {slot: pointer["artifact_id"] for slot, pointer in current.items() if pointer is not None}
        refs[self.slot] = identity["attempt_id"] + ":" + self.slot
        return TargetOutcome("succeeded", {"current_artifact_ids": refs},
                             artifact=ArtifactOutput(self.slot, paths, state_paths, self.status))


def test_real_registered_outputs_reach_end_then_unique_completed_closure():
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-artifacts-", dir="/private/tmp"))
    coordinator, _, source = start(output)
    locator = source["result"]["run_locator"]
    root = output / locator["case_id"] / locator["run_id"]
    actor = ActorContext("operator", "human", ("control.internal",))
    leases = InvocationLeases(coordinator)
    try:
        capability = source["result"]["capability_id"]
        for position, (slot, next_node) in enumerate((("plan", "analysis_engineer"), ("analysis", "decision_coordinator"),
                                                      ("decision", "memory_report"), ("terminal", None)), 1):
            leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
            state = leases.invoke(capability, "consumer", 1, ArtifactTarget(slot, root, status="accepted" if slot == "terminal" else "synthetic"))
            assert state["current_artifacts"][slot]["attempt_id"] == f"attempt_{position:06d}"
            plane = ControlPlane(coordinator, worker_id="worker", route_adapter=SyntheticDomainRoute(next_node))
            advanced = plane.advance_run(AdvanceRunRequest(locator, state["attempt_id"], f"advance-{position}"), actor=actor)
            assert advanced["operation_status"] == "committed" and advanced["run_status"] == "running"
            capability = advanced["result"]["capability_id"]
        assert capability is None
        records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        assert records[-1]["target_attempt_id"] is None and records[-1]["source_node"] == "memory_report"
        request = CloseRunRequest(locator, digest(records[-1]))
        result = plane.close_run(request, actor=actor)
        assert result["run_status"] == "completed" and result["terminal_closure"] == "committed"
        assert plane.close_run(request, actor=actor) == result
        assert loads((root / "artifact_index.json").read_bytes())["current"]["terminal"]["status"] == "accepted"
    finally:
        coordinator.close()


def test_artifact_effect_port_is_fenced_again_after_trusted_clock_expires():
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-artifact-expiry-", dir="/private/tmp"))
    coordinator, _, source = start(output)
    leases = InvocationLeases(coordinator)
    capability = source["result"]["capability_id"]
    locator = source["result"]["run_locator"]
    root = output / locator["case_id"] / locator["run_id"]

    class Target:
        def invoke_with_artifacts(self, identity, port):
            coordinator.clock.advance(10)
            port.write_member("method_plan.json", b"{}")
            raise AssertionError("Expired effect was executed")

    try:
        leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
        with pytest.raises(ControlIntegrityError, match="expired"):
            leases.invoke(capability, "consumer", 1, Target())
        assert not (root / "attempts" / "attempt_000001" / "method_plan.json").exists()
        assert leases.get(capability)[1]["started_intent"] is not None
        with pytest.raises(ControlIntegrityError):
            leases.acquire(capability, "replacement", expected_epoch=1, lease_seconds=10)
    finally:
        coordinator.close()
