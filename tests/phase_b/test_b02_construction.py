"""Fixed construction evidence for the thirty B02-owned requirements."""
import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import read
from harness.trace import compare
from helpers.construction_cases import CASES, construction_trace


@pytest.mark.parametrize("requirement", sorted(CASES))
def test_requirement(requirement):
    trace = construction_trace(requirement)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b02_construction" / (requirement + ".json")))
    observe("b02-" + requirement, {"kind": "boolean", "value": True}, sorted([requirement, "durable_control_evidence"]), trace)
