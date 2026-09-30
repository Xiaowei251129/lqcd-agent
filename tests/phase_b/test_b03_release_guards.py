"""All frozen negative canonical release cases preserve original authority."""
from pathlib import Path
import tempfile

import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case, process_hook_request
from harness.strict_json import read
from harness.trace import compare
from lqcd_agent.control.protocol import PROTOCOL
from helpers.b03_release_guards import GUARDS, release_guard


SPECS = case_specs(PROTOCOL)
CASES = tuple(cid for cid, spec in SPECS.items() if spec["failpoint_id"] in GUARDS)


@pytest.mark.parametrize("case_id", CASES)
def test_release_guard(case_id):
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-release-guard-hook-", dir="/private/tmp"))
    trace = release_guard(case_id, hook_request=process_hook_request(case_id, root))
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)
