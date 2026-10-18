"""New product control paths must fit the existing strict source contract."""
import pytest

from harness.trace import normalize
from helpers.b04_product_sources import product_trace
from helpers.trace_sources import current_binding


@pytest.mark.parametrize("mode", ["planner", "exception", "overrun", "epoch"])
def test_product_control_source_is_exact_across_two_fresh_roots(mode):
    first, root, facts = product_trace(mode)
    second, other, other_facts = product_trace(mode)
    assert root != other and facts == other_facts
    assert facts["calls"] == ["method_planner"]
    assert facts["run_status"] == ("paused" if mode == "planner" else "failed")
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
