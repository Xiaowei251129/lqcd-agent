"""Local native consumers cannot turn a diagnostic hook into formal B04 ownership."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT
from harness.failpoints import validate_runtime
from harness.inputs import load_inputs
from harness.pytest_evidence import validate_observations, validate_pytest
from harness.strict_json import Invalid
from test_b00c26_trace_consumers import CASE, native


def test_only_local_bindings_accept_complete_actual_result(native):
    session, value, scenario, registry = native
    validate_pytest(value, session, value["selection"])
    assert validate_observations(value, [scenario], ROOT) == {"B00C26-PROBE"}
    specs = {CASE: {"outcome": CASE.rsplit(".", 1)[1], "invariants": scenario["required_invariants"]}}
    assert validate_runtime(value, registry, specs, [scenario], ROOT) == [CASE]
    path = ROOT / "tests/phase_b/failpoint_registry.json"
    original = path.read_bytes()
    inputs = load_inputs()
    candidate = deepcopy(inputs["registry"])
    entry = next(row for row in candidate["entries"] if row["failpoint_id"] == inputs["specs"][CASE]["failpoint_id"])
    entry["hook_ref"] = registry["entries"][0]["hook_ref"]
    entry["case_bindings"] = [row for row in entry["case_bindings"] if row["case_id"] != CASE]
    with pytest.raises(Invalid, match="hook:case_id"):
        validate_runtime(value, candidate, inputs["specs"], inputs["matrix"]["scenarios"], ROOT)
    entry["case_bindings"].append({"case_id": CASE, "scenario_ids": [scenario["scenario_id"]]})
    scenarios = [row for row in inputs["matrix"]["scenarios"] if row["scenario_id"] != scenario["scenario_id"]] + [scenario]
    assert validate_runtime(value, candidate, inputs["specs"], scenarios, ROOT) == [CASE]
    assert path.read_bytes() == original
    diagnostic = deepcopy(value)
    diagnostic["case_results"] = []
    assert validate_runtime(diagnostic, registry, specs, [scenario], ROOT) == []
    assert validate_runtime(diagnostic, candidate, inputs["specs"], scenarios, ROOT) == []
    unbound = deepcopy(registry)
    unbound["entries"][0]["case_bindings"] = []
    with pytest.raises(Invalid, match="hook:case_id"):
        validate_runtime(diagnostic, unbound, specs, [scenario], ROOT)
    session.unchanged()


@pytest.mark.parametrize("fault", ["outcome", "invariants", "passing_node", "source", "hook", "duplicate"])
def test_case_result_requires_actual_passing_node_and_bound_source(native, fault):
    session, value, scenario, registry = native
    bad = deepcopy(value)
    row = bad["case_results"][0]
    if fault == "outcome": row["outcome"] = "committed_result_replay"
    elif fault == "invariants": row["invariants"] = []
    elif fault == "passing_node": row["nodeid"] = "tests/test_forged.py::test_pass"
    elif fault == "source": row["trace"] = {"schema_version": "0.12", "representation": "raw_with_proof", "events": [], "proof": {}}
    elif fault == "hook": bad["hook_events"] *= 2
    else: bad["case_results"] *= 2
    specs = {CASE: {"outcome": CASE.rsplit(".", 1)[1], "invariants": scenario["required_invariants"]}}
    with pytest.raises(Invalid):
        validate_pytest(bad, session, value["selection"])
        assert validate_runtime(bad, registry, specs, [scenario], ROOT) == [CASE]
