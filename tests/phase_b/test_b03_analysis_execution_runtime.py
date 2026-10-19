"""Frozen Analysis authority and execution uncertainty cases."""
from harness.temporary import mkdtemp
from pathlib import Path

import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case, process_hook_request
from harness.strict_json import read
from harness.trace import compare
from lqcd_agent.control.protocol import PROTOCOL
from helpers.b03_analysis_execution_cases import (GUARDS, NOT_APPLICABLE, analysis_guard,
                                                 analysis_execution_recovery, not_applicable_recovery)


SPECS = case_specs(PROTOCOL)
CASES = tuple(cid for cid, spec in SPECS.items() if spec["failpoint_id"] in (*GUARDS, *NOT_APPLICABLE, "analysis.fresh_subprocess"))


@pytest.mark.parametrize("case_id", CASES)
def test_analysis_execution_case(case_id):
    boundary = SPECS[case_id]["failpoint_id"]
    if boundary in NOT_APPLICABLE:
        trace = not_applicable_recovery(case_id)
    else:
        directory = Path(mkdtemp(prefix="lqcd-agent-b03-analysis-execution-hook-", dir="/private/tmp"))
        request = process_hook_request(case_id, directory)
        trace = (analysis_guard if boundary in GUARDS else analysis_execution_recovery)(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)
