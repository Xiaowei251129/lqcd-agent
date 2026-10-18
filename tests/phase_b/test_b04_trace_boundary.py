"""A genuine ordinary resource cannot use an A05-only settlement profile."""
from pathlib import Path
import tempfile

import pytest

from harness.strict_json import Invalid
from harness.trace import normalize
from harness.trace_proof import source_object
from helpers.control_traces import ControlTrace
from helpers.trace_sources import current_binding
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes


@pytest.mark.parametrize("fresh_root", ["first", "second"])
def test_trace_0_5_rejects_actual_ordinary_success_settlement(fresh_root):
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-trace-boundary-" + fresh_root + "-", dir="/private/tmp"))
    captured = ControlTrace(output, version="0.5")
    coordinator = Coordinator(output, clock=FakeClock(100, 0), observer=captured.observer)
    actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
    port = StructuredOutcomes()
    try:
        result = run_canonical_graph(coordinator=coordinator,
            request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"), actor=actor, agent_port=port)
        assert result["state"]["run_status"] == "completed"
        trace = captured.finish(coordinator)
        with pytest.raises(Invalid, match="a05_reference:missing_source"):
            normalize(trace, binding=current_binding())
        known = {row["sha256"] for row in trace["proof"]["objects"]}
        for value in port.resource_preimages:
            item = source_object("canonical_json", value, version="0.4")
            if item["sha256"] not in known:
                trace["proof"]["objects"].append(item)
                known.add(item["sha256"])
        settlements = [row["value"] for row in trace["proof"]["objects"] if
                       row["value"].get("record_type") == "budget" and row["value"].get("event") == "resource_settled"]
        assert len(settlements) == 3
        sources = {row["sha256"]: row for row in trace["proof"]["objects"]}
        for settlement in settlements:
            source = sources[settlement["payload"]["evidence_digest"]]
            assert source["kind"] == "canonical_json"
            assert source["value"]["diagnostic"]["status"] == "success"
        with pytest.raises(Invalid, match="a05_reference:kind"):
            normalize(trace, binding=current_binding())
        (output / "counterexample-trace.json").write_bytes(canonical_bytes(trace))
        (output / "counterexample-summary.json").write_bytes(canonical_bytes({
            "fresh_root": fresh_root, "run_locator": result["run_locator"], "run_status": result["state"]["run_status"],
            "settlements": 3, "error_before_preimages": "invalid_evidence:a05_reference:missing_source",
            "error_after_actual_preimages": "invalid_evidence:a05_reference:kind",
            "trace_version": "0.5", "proof_version": "0.2", "trace_sha256": digest(trace)}))
    finally:
        coordinator.close()
