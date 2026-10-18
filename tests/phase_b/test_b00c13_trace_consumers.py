"""C13 current Session evidence across all four strict source consumers."""
import pytest

from harness.inputs import load_inputs
from harness.matrix import selected_scenarios
from harness.pytest_evidence import run_pytest, validate_observations, validate_pytest
from harness.session import Session
from test_b00c11_trace_consumers import test_new_source_four_evidence_paths as check_consumers


@pytest.mark.parametrize("decision", ["approve_rerun", "reject_or_hold"])
def test_successful_human_has_all_four_consumers(tmp_path, decision):
    check_consumers(tmp_path, decision)


def test_formal_continuation_meta_uses_current_session(tmp_path):
    inputs = load_inputs()
    identifiers = {"B00C13-APPROVE_RERUN", "B00C13-REJECT_OR_HOLD"}
    scenarios = [s for s in selected_scenarios(inputs["matrix"], "final", None) if s["scenario_id"] in identifiers]
    assert {s["scenario_id"] for s in scenarios} == identifiers
    assert all(s["implementation_ticket_id"] == "B00" for s in scenarios)
    selection = sorted({node for s in scenarios for node in s["pytest_nodeids"]})
    session = Session(inputs["root"], tmp_path / "source-session", inputs["digests"])
    value = run_pytest(session, selection)
    validate_pytest(value, session, selection)
    assert validate_observations(value, scenarios, inputs["root"], all_scenarios=inputs["matrix"]["scenarios"]) == identifiers
    assert not value["hook_events"] and not value["case_results"]
    session.unchanged()
