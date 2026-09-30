"""Started Code consumers never redispatch or reuse Backend stop proof."""
import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case
from harness.strict_json import read
from harness.trace import compare
from lqcd_agent.control.protocol import PROTOCOL
from helpers.b03_uncertain_consumer_cases import UNCERTAIN_PHASES, uncertain_consumer_recovery


SPECS = case_specs(PROTOCOL)
CASES = tuple(cid for cid, spec in SPECS.items() if spec["failpoint_id"] in UNCERTAIN_PHASES)


@pytest.mark.parametrize("case_id", CASES)
def test_uncertain_consumer_case(case_id):
    trace = uncertain_consumer_recovery(case_id)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)
