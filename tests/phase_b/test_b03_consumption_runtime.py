"""Independent B03 cases with real canonical Code and host-timeout bundles."""
import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case
from harness.strict_json import read
from harness.trace import compare
from lqcd_agent.control.protocol import PROTOCOL
from helpers.b03_consumption_cases import CONSUMPTION_PHASES, consumption_recovery


SPECS = case_specs(PROTOCOL)
CONSUMPTION_CASES = tuple(cid for cid, spec in SPECS.items() if spec["failpoint_id"] in CONSUMPTION_PHASES)


@pytest.mark.parametrize("case_id", CONSUMPTION_CASES)
def test_canonical_consumption_case(case_id):
    trace = consumption_recovery(case_id)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)
