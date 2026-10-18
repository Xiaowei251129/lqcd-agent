"""Product exceptions and Host measurement failures have exact original sources."""
import pytest

from harness.contracts import ROOT
from harness.strict_json import read
from harness.pytest_evidence import observe
from harness.trace import compare, normalize
from helpers.b04_resource_outcomes import MODES, resource_failure_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes


@pytest.mark.parametrize("mode", MODES)
def test_original_resource_failure_has_exact_safe_closure(mode):
    projected = []
    for _ in range(2):
        raw, output, facts = resource_failure_trace(mode)
        value = normalize(raw, binding=current_binding())
        (output / "normalized.json").write_bytes(canonical_bytes(value))
        projected.append(value)
    assert projected[0] == projected[1]
    compare(raw, read(ROOT / ("tests/phase_b/expected_traces/b04_product/resource-" + mode + ".json")), binding=current_binding())
    observe("B04-RESOURCE-" + mode, {"kind": "boolean", "value": True},
            ["actual_production_path", "dual_fresh_exact", "duplicate_readonly"], raw)
