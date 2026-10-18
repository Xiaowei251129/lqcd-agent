"""C12 formal B00 source identities and all shared evidence consumers."""
from copy import deepcopy
import pytest

from harness.inputs import load_inputs
from harness.matrix import selected_scenarios
from harness.pytest_evidence import run_pytest, validate_pytest, validate_observations
from harness.session import Session
from harness.strict_json import Invalid
from test_b00c11_trace_consumers import test_new_source_four_evidence_paths as check_consumers


@pytest.mark.parametrize("kind", ["maximum", "receipt", "human"])
def test_three_source_kinds_have_all_four_consumers(tmp_path, kind):
    check_consumers(tmp_path, kind)


def test_formal_source_meta_uses_complete_matrix_and_current_session(tmp_path):
    inputs = load_inputs()
    identifiers = {"B00C11-MAXIMUM", "B00C11-HUMAN", "B00C12-MAXIMUM-HOST-RECEIPT"}
    scenarios = [s for s in selected_scenarios(inputs["matrix"], "final", None) if s["scenario_id"] in identifiers]
    assert {s["scenario_id"] for s in scenarios} == identifiers
    assert all(s["implementation_ticket_id"] == "B00" and s["validation_stage"] == "final" for s in scenarios)
    selection = sorted({n for s in scenarios for n in s["pytest_nodeids"]})
    session = Session(inputs["root"], tmp_path / "source-session", inputs["digests"])
    value = run_pytest(session, selection)
    validate_pytest(value, session, selection)
    assert validate_observations(value, scenarios, inputs["root"], all_scenarios=inputs["matrix"]["scenarios"]) == identifiers
    assert {r["scenario_id"] for r in value["observations"]} == identifiers
    assert not value["hook_events"] and not value["case_results"]
    for fault in ("unknown", "duplicate", "missing"):
        bad = deepcopy(value)
        if fault == "unknown": bad["observations"][0]["scenario_id"] = "unknown-source"
        elif fault == "duplicate": bad["observations"].append(deepcopy(bad["observations"][0]))
        else: bad["observations"].pop()
        with pytest.raises(Invalid):
            validate_observations(bad, scenarios, inputs["root"], all_scenarios=inputs["matrix"]["scenarios"])
    session.unchanged()
