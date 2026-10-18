"""Every forbidden class is observed in the compiled product and exact source trace."""
import pytest

from harness.contracts import ROOT
from harness.strict_json import read
from harness.pytest_evidence import observe
from harness.trace import compare, normalize
from helpers.b04_forbidden_product import MODES, forbidden_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes


@pytest.mark.parametrize("mode", MODES)
def test_forbidden_product_authority_is_exact_across_fresh_roots(mode):
    traces = []
    for _ in range(2):
        raw, output, facts = forbidden_trace(mode)
        projected = normalize(raw, binding=current_binding())
        (output / "b04-forbidden-normalized.json").write_bytes(canonical_bytes(projected))
        traces.append(projected)
    assert traces[0] == traces[1]
    compare(raw, read(ROOT / ("tests/phase_b/expected_traces/b04_product/forbidden-" + mode + ".json")), binding=current_binding())
    observe("B04-FORBID-" + mode, {"kind": "boolean", "value": True},
            ["actual_production_path", "dual_fresh_exact", "duplicate_readonly"], raw)
