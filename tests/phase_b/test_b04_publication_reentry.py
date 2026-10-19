"""Product reentry completes frozen publication before admitting another target."""
from harness.temporary import mkdtemp
from pathlib import Path

import pytest

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
from test_b04_product_graph import StructuredOutcomes


class PublicationInterruption(BaseException):
    """A Python boundary interruption is distinct from a terminated process."""


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("node", ["method_planner", "analysis_engineer", "scientific_reviewer"])
@pytest.mark.parametrize("fault", [None, "expired", "member"])
def test_finished_ledger_reentry_uses_original_completion_without_reexecution(side, node, fault):
    output = Path(mkdtemp(prefix="lqcd-agent-b04-publication-", dir="/private/tmp"))
    clock = FakeClock(100, 0)
    agent = StructuredOutcomes()
    interrupted = []

    def observer(name, when, value):
        if name == "invocation.attempt_finished" and when == side and agent.contexts[-1][0] == node and not interrupted:
            interrupted.append(value)
            raise PublicationInterruption()

    coordinator = Coordinator(output, clock=clock, observer=observer)
    actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
    runtime = CanonicalProductRuntime(coordinator, worker_id="product-host", actor=actor, agent_port=agent)
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
    try:
        started = runtime.plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"), actor=actor)
        locator = started["result"]["run_locator"]
        with pytest.raises(PublicationInterruption):
            runtime.run(locator)
        root, _ = runtime._records(locator)
        started_caps = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM invocation_capabilities")
                        if loads(row[0])["state"] == "started"]
        completion, = started_caps
        assert completion["completion_intent"] is not None
        if fault == "expired":
            clock.advance(31)
        elif fault == "member":
            member, *_ = completion["completion_intent"]["artifact_publication"]["projections"]
            (root / member["canonical_path"]).write_bytes(b"changed")
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        calls = len(agent.contexts)
        if fault is not None:
            with pytest.raises(ControlIntegrityError):
                runtime.run(locator)
            assert len(agent.contexts) == calls
        else:
            runtime.run(locator)
            _, execution = runtime._records(locator)
            assert execution.projection.value["run_status"] == "completed"
            assert [name for name, _ in agent.contexts] == ["method_planner", "analysis_engineer", "scientific_reviewer"]
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            runtime.run(locator)
            assert len(agent.contexts) == 3
        assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    finally:
        coordinator.close()
