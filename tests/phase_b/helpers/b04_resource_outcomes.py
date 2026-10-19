"""Real product resource failures retain returns and the original settlement owner."""
from harness.temporary import mkdtemp
from pathlib import Path

from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from helpers.ordinary_publication_prefix_sources import PublicationPrefixSources
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes


MODES = ("exception", "overrun", "epoch", "analysis_exception")


def resource_failure_trace(mode):
    assert mode in MODES
    output = Path(mkdtemp(prefix="lqcd-agent-b04-resource-outcome-", dir="/private/tmp"))
    with HostIdentities("b04-resource-outcome-" + mode).installed():
        coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
        try:
            sources = PublicationPrefixSources(coordinator)
            capture = ControlTrace(output, version="0.10", ordinary_sources=sources)
            coordinator.observer = lambda name, side, value: sources.observer(capture, name, side, value)
            class Port(StructuredOutcomes):
                def run(self, node, context, *, timeout_seconds):
                    result = super().run(node, context, timeout_seconds=timeout_seconds)
                    if mode == "analysis_exception" and node == "method_planner": return result
                    if mode in ("exception", "analysis_exception"):
                        raise RuntimeError("Actual bounded product provider failure")
                    if mode == "overrun": coordinator.clock.subject.advance(2)
                    else: coordinator.clock.subject.epoch_id = "changed_clock_epoch"
                    return result
            agent = Port()
            actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
            inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
            result = run_canonical_graph(coordinator=coordinator, request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"),
                actor=actor, agent_port=sources.agent(agent))
            runtime, locator = result["runtime"], result["run_locator"]
            root, execution = runtime._records(locator)
            assert execution.projection.value["run_status"] == "failed"
            reservations = [row for row in execution.values if row.get("event") == "resource_reserved"]
            settlements = [row for row in execution.values if row.get("event") == "resource_settled"]
            assert len(reservations) == len(settlements) == len(agent.contexts) == (2 if mode == "analysis_exception" else 1)
            last = settlements[-1]["payload"]
            assert last["actual"] is None and last["tokens"] == last["cost"] == {"state": "unknown", "value": None}
            assert last["resource_operation_id"] == reservations[-1]["payload"]["resource_operation_id"]
            if mode in ("exception", "analysis_exception"):
                assert sources.calls[-1]["outcome"] is None and sources.calls[-1]["exception"] is not None
            else:
                assert sources.calls[-1]["outcome"] is not None and sources.calls[-1]["exception"] is None
            closures = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM run_terminal_closure")]
            assert len(closures) == 1 and closures[0]["terminal_closure"] == "committed"
            stable = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            runtime.run(locator)
            assert len(agent.contexts) == len(reservations)
            assert stable == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            raw = capture.finish(coordinator)
            facts = {"mode": mode, "calls": len(agent.contexts), "reservations": len(reservations),
                     "settlements": len(settlements), "run_status": "failed", "closures": len(closures), "duplicate_readonly": True}
            for name, value in (("raw", raw), ("facts", facts)):
                (output / (name + ".json")).write_bytes(canonical_bytes(value))
            return raw, output, facts
        finally:
            coordinator.close()
