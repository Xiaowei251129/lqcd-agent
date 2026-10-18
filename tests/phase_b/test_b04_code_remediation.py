"""Code fallback and rerun use new advance owners and real fresh subprocesses."""
import pytest

from harness.contracts import ROOT
from harness.strict_json import read
from harness.pytest_evidence import observe
from harness.trace import compare, normalize
from helpers.b04_code_remediation import MODES, remediation_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes


@pytest.mark.parametrize("mode", MODES)
def test_actual_code_fallback_is_exact_across_fresh_roots(mode):
    projected = []
    for _ in range(2):
        raw, output, facts = remediation_trace(mode)
        assert facts["run_status"] == "completed"
        value = normalize(raw, binding=current_binding())
        (output / "b04-remediation-normalized.json").write_bytes(canonical_bytes(value))
        projected.append(value)
    assert projected[0] == projected[1]
    compare(raw, read(ROOT / ("tests/phase_b/expected_traces/b04_product/" + mode + ".json")), binding=current_binding())
    observe("B04-REMEDIATION-" + mode, {"kind": "boolean", "value": True},
            ["actual_production_path", "dual_fresh_exact", "duplicate_readonly"], raw)
