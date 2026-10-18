"""Passive witnesses for actual product Host maximum-settlement evidence."""
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import inspect
import tempfile

from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import MaximumSources, PassiveClock
from helpers.ordinary_sources import captured_source
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest
from lqcd_agent.graph.nodes import product_resource
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, diagnostic


class ProductSources(MaximumSources):
    """Observe the original Host evidence rather than reconstructing a return."""

    def observer(self, capture, name, side, value):
        capture.observer(name, side, value)
        if name != "budget.resource_settled" or side != "before" or value["record"]["payload"]["actual"] is not None:
            return
        frame = inspect.currentframe().f_back
        try:
            while frame is not None and frame.f_code is not product_resource.__code__:
                frame = frame.f_back
            assert frame is not None
            evidence = deepcopy(frame.f_locals["evidence"])
            reservation, = frame.f_locals["reservations"]
            assert value["record"]["payload"]["evidence_digest"] == digest(evidence)
            assert value["record"]["payload"]["resource_operation_id"] == reservation["payload"]["resource_operation_id"]
            self.maximum_evidence[digest(reservation)] = captured_source("maximum_evidence", evidence)
        finally:
            del frame


def product_trace(mode):
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-source-" + mode + "-", dir="/private/tmp"))
    clock = PassiveClock(FakeClock(100, 0))
    with HostIdentities("b04-source-" + mode).installed(), closing(Coordinator(output, clock=clock)) as coordinator:
        sources = ProductSources(coordinator)
        capture = ControlTrace(output, version="0.7", ordinary_sources=sources)
        coordinator.observer = lambda name, side, value: sources.observer(capture, name, side, value)

        class Port(StructuredOutcomes):
            def run(self, node, context, *, timeout_seconds):
                result = super().run(node, context, timeout_seconds=timeout_seconds)
                if mode == "exception":
                    raise RuntimeError("Actual controlled port exception")
                if mode == "overrun":
                    clock.subject.advance(2)
                if mode == "epoch":
                    clock.subject.epoch_id = "fake_clock_epoch_2"
                return result

        agent = Port({"method_planner": diagnostic(risk="critical", human_need="approval")} if mode == "planner" else {})
        inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        result = run_canonical_graph(coordinator=coordinator, agent_port=sources.agent(agent),
            actor=ActorContext("operator", "human", ("control.internal", "resume", "start")),
            request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"))
        trace = capture.finish(coordinator)
        facts = {"run_status": result["state"]["run_status"], "calls": [node for node, _ in agent.contexts],
                 "review_probe": True, "owned_runtime_evidence": False}
        for name, value in (("raw.json", trace), ("facts.json", facts)):
            (output / name).write_bytes(canonical_bytes(value))
        return trace, output, facts
