"""Original Human continuations preserve capacity and terminal protection."""
import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import read
from harness.trace import compare, normalize
from helpers.trace_sources import current_binding
from test_b00c18_ordinary_repause_handoff import repause_trace


@pytest.mark.parametrize("mode", ["ordinary_corrected", "ordinary_insufficient", "terminal_corrected"])
def test_product_capacity_continuation_never_restarts_work(mode):
    first, root, facts = repause_trace(mode)
    second, other, repeated = repause_trace(mode)
    assert root != other and facts == repeated and facts["duplicate_readonly"]
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    compare(first, read(ROOT / ("tests/phase_b/expected_traces/b00c18/" + mode + ".json")),
            binding=current_binding())
    observe("B04-CAPACITY-" + mode, {"kind": "boolean", "value": True},
            ["actual_production_path", "dual_fresh_exact", "no_new_work"], first)
