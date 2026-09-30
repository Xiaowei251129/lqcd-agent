"""Normal-unavailable recovery preserves the original integrity interrupt."""
from pathlib import Path
import tempfile

import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case, process_hook_request
from harness.strict_json import read
from harness.trace import compare
from lqcd_agent.control.protocol import PROTOCOL
from helpers.b03_reclassification_cases import reclassification_recovery
from helpers.canonical_code import canonical_source
from lqcd_agent.code_agent.external_operation import ExternalNormalFinal
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import ControlIntegrityError


SPECS = case_specs(PROTOCOL)
CASES = tuple(cid for cid in SPECS if cid.startswith("external.normal_unavailable_reclassification."))


@pytest.mark.parametrize("case_id", CASES)
def test_reclassification_case(case_id):
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-reclassification-hook-", dir="/private/tmp"))
    trace = reclassification_recovery(case_id, hook_request=process_hook_request(case_id, root))
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


@pytest.mark.parametrize("raw", [b"{}", b"[]"])
def test_conflicting_normal_unavailable_handoff_rejected(raw):
    coordinator, _, _, locator, dispatch, _, audit, patch = canonical_source(success=True, finalize=False)
    try:
        source = ExternalControl(coordinator).read(coordinator.connection, dispatch.producer)
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        path = root / "code_agent_control" / source["attempt_id"] / "normal_unavailable_trigger.json"
        path.write_bytes(raw)
        with pytest.raises(ControlIntegrityError, match="Conflicting publication bytes"):
            ExternalNormalFinal(dispatch, coordinator.root / "base_repository").commit(tool_audit=audit, patch=patch)
        assert path.read_bytes() == raw
        assert ExternalControl(coordinator).read(coordinator.connection, dispatch.producer) == source
        assert coordinator.connection.execute("SELECT count(*) FROM control_operations WHERE operation_type='resolve_external_interrupt'").fetchone()[0] == 0
    finally:
        coordinator.close()
