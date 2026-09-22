"""Reviewed complete source-bound B02 paths through the unchanged trace checker."""
import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import read
from harness.trace import compare, normalize
from helpers.b02_source_traces import TRAJECTORIES, source_trace
from helpers.trace_sources import current_binding


@pytest.mark.parametrize("name", sorted(TRAJECTORIES))
def test_source_bound_trajectory(name):
    first, second = source_trace(name), source_trace(name)
    assert first["proof"]["output_roots"] != second["proof"]["output_roots"]
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    compare(first, read(ROOT / "tests/phase_b/expected_traces" / ("b02_source_" + name + ".json")), binding=current_binding())
    requirement, _ = TRAJECTORIES[name]
    observe("b02-source-" + name, {"kind": "boolean", "value": True}, sorted([requirement, "source_bound_heads"]), first)
