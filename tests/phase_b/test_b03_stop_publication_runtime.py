"""Physical stop publication and takeover cases use production process receipts."""
from pathlib import Path
import tempfile

import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case, process_hook_request
from harness.strict_json import read
from harness.trace import compare
from lqcd_agent.control.protocol import PROTOCOL
from helpers.b03_stop_publication_cases import BOUNDARIES, stop_publication_recovery


SPECS = case_specs(PROTOCOL)
CASES = tuple(cid for cid, spec in SPECS.items() if spec["failpoint_id"] in BOUNDARIES and
              not (spec["failpoint_id"].endswith("_committed") and spec["outcome"] == "committed_result_replay"))


@pytest.mark.parametrize("case_id", CASES)
def test_stop_publication_case(case_id):
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-stop-publication-hook-", dir="/private/tmp"))
    trace = stop_publication_recovery(case_id, hook_request=process_hook_request(case_id, root))
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)
