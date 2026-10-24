"""All frozen trigger classes and product contexts use their unique owner."""
import json
from pathlib import Path

import pytest

from harness.trace import compare, normalize
from harness.pytest_evidence import observe
from helpers.b04_stop_routes import MODES, stop_route_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes


@pytest.mark.parametrize("mode", MODES)
def test_product_stop_context_is_source_bound(mode):
    traces = []
    for _ in range(2):
        raw, output, facts = stop_route_trace(mode, trace_version="0.11")
        normalized = normalize(raw, binding=current_binding())
        (output / "b04-stop-normalized.json").write_bytes(canonical_bytes(normalized))
        traces.append(normalized)
    assert traces[0] == traces[1]
    expected = Path(__file__).parent / "expected_traces" / "b04_product" / ("stop-" + mode + ".json")
    compare(raw, json.loads(expected.read_bytes()), binding=current_binding())
    observe("B04-STOP-" + mode, {"kind": "boolean", "value": True},
            ["actual_production_path", "dual_fresh_exact", "duplicate_readonly"], raw)
