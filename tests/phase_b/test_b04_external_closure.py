"""The product preserves real external finals across safe and unsafe closure."""
import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import read
from harness.trace import compare, normalize
from helpers.trace_sources import current_binding
from helpers.unconsumed_code_final_sources import product_unconsumed_trace


MODES = ("normal", "non_success", "attached", "halt", "integrity", "late_integrity", "usage_overage",
         "missing_termination", "missing_writes", "missing_empty", "missing_drain", "missing_stability",
         "resume_failure", "consumer_overrun", "consumer_unsafe", "consumer_authority")


@pytest.mark.parametrize("mode", MODES)
def test_product_external_closure_preserves_the_original_final(mode):
    projected = []
    for _ in range(2):
        raw, _, facts = product_unconsumed_trace(mode)
        assert facts["readonly_replay"] and facts["dispatches"] == 1
        assert not facts["Code_registered"] and not facts["Analysis_registered"]
        projected.append(normalize(raw, binding=current_binding()))
    assert projected[0] == projected[1]
    compare(raw, read(ROOT / ("tests/phase_b/expected_traces/b00c24/" + mode + ".json")),
            binding=current_binding())
    observe("B04-EXTERNAL-" + mode, {"kind": "boolean", "value": True},
            ["actual_production_path", "dual_fresh_exact", "original_final_preserved"], raw)
