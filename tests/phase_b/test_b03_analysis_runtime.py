"""Frozen runtime cases for canonical fresh Analysis preparation."""
from pathlib import Path
import tempfile

import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case, process_hook_request
from harness.strict_json import read
from harness.trace import compare
from helpers.b03_analysis_cases import PREPARATION_BOUNDARIES, preparation_recovery
from lqcd_agent.control.protocol import PROTOCOL


SPECS = case_specs(PROTOCOL)
PREPARATION_CASES = tuple(case_id for case_id, spec in SPECS.items()
                          if spec["failpoint_id"] in PREPARATION_BOUNDARIES)


@pytest.mark.parametrize("case_id", PREPARATION_CASES)
def test_preparation_case(case_id):
    directory = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-analysis-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = preparation_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)
