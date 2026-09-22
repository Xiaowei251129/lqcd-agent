"""Exercise a production B02 flow through the unchanged B00 exact-trace checker."""
from harness.trace import normalize, compare
from harness.contracts import ROOT
from harness.strict_json import read
from helpers.control_traces import fresh_recovery_trace
from helpers.trace_sources import current_binding


def test_real_control_trace_stays_exact_across_fresh_roots():
    first, second = fresh_recovery_trace(), fresh_recovery_trace()
    assert first["proof"]["output_roots"] != second["proof"]["output_roots"]
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    compare(first, read(ROOT / "tests/phase_b/expected_traces/b02_recovery_control.json"), binding=current_binding())
    names = [row["event"] for row in first["events"]]
    assert "pause:pause_opened" in names and "pause:pause_consumed" in names
    assert "control.resume_run.abandon_and_halt.result_committed" in names
