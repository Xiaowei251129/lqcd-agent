"""Every sealed B02 case has its own process trigger and reviewed expected trace."""
import pytest

from harness.contracts import ROOT
from harness.inputs import load_inputs
from harness.inventory import expected_inventory
from harness.pytest_evidence import observe, observe_case
from harness.strict_json import read
from harness.trace import compare
from helpers.runtime_cases import SPECS, exercise_phase_case
from helpers.supplemental_cases import exercise_supplemental_case
from lqcd_agent.control.protocol import PROTOCOL


BOUNDARIES = frozenset(row["failpoint_id"] for row in expected_inventory(PROTOCOL) if row["boundary_owner"] == "B02")
CASES = tuple(cid for cid, spec in SPECS.items() if spec["failpoint_id"] in BOUNDARIES)


def test_b02_bindings_equal_independently_sealed_cases():
    inputs = load_inputs()
    entries = [row for row in inputs["registry"]["entries"] if row["boundary_owner"] == "B02"]
    assert {row["failpoint_id"] for row in entries} == BOUNDARIES
    bound = [binding["case_id"] for entry in entries for binding in entry["case_bindings"]]
    assert sorted(bound) == list(CASES) and len(bound) == len(set(bound))
    assert all(entry["hook_ref"] == "src/lqcd_agent/control/coordinator.py:boundary" for entry in entries)
    assert len(inputs["slices"]["B02"]) == 30 and set(inputs["slices"]["B02"]) <= set(inputs["covered"])


@pytest.mark.parametrize("case_id", CASES)
def test_independent_case(case_id):
    trace = exercise_phase_case(case_id) if case_id.startswith("control.") else exercise_supplemental_case(case_id)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b02_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b02-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)
