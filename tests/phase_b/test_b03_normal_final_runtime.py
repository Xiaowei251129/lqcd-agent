"""Frozen normal-final crash cases retain one resolution and immutable bytes."""
from pathlib import Path
import tempfile

import pytest

from harness.contracts import ROOT
from harness.inventory import case_specs
from harness.pytest_evidence import observe, observe_case, process_hook_request
from harness.strict_json import read
from harness.trace import compare
from helpers.b03_normal_final_cases import NORMAL_FINAL_BOUNDARIES, normal_final_recovery
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.external_operation import CodeWatchdog
from test_external_operation_recovery import RefuseRedispatch, _running_stop_source


SPECS = case_specs(PROTOCOL)
NORMAL_FINAL_CASES = tuple(cid for cid, spec in SPECS.items() if spec["failpoint_id"] in NORMAL_FINAL_BOUNDARIES)


@pytest.mark.parametrize("case_id", NORMAL_FINAL_CASES)
def test_normal_final_case(case_id):
    directory = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-normal-final-hook-", dir="/private/tmp"))
    request = process_hook_request(case_id, directory)
    trace = normal_final_recovery(case_id, hook_request=request)
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b03_runtime" / (case_id + ".json")))
    spec = SPECS[case_id]
    invariants = sorted(spec["invariants"])
    observe("b03-runtime-" + case_id, {"kind": "boolean", "value": True}, invariants, trace)
    observe_case(case_id, spec["outcome"], invariants, trace)


def test_stop_rejects_unbound_conflicting_final_bytes():
    original, root, producer = _running_stop_source(containment_fault=None)
    value = ExternalControl(original).read(original.connection, producer)
    candidate = root / "code_agent_control" / value["attempt_id"] / "external_final_evidence.json"
    candidate.write_bytes(b"{}")
    output = original.root
    original.close()
    coordinator = Coordinator(output, clock=FakeClock(140, 40))
    try:
        backend = RefuseRedispatch(output / "fake_backend", clock=lambda: 140)
        result = CodeWatchdog(coordinator, backend, DeterministicContainment(output / "containment"),
                              backend.read_receipt).enforce(producer)
        assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable"
        assert result["error"]["message"] == "Conflicting external final candidate"
        assert candidate.read_bytes() == b"{}"
        assert ExternalControl(coordinator).read(coordinator.connection, producer)["operation_phase"] == "termination_evidence_committed"
        assert not list(candidate.parent.glob("external_final_evidence_control_*.json"))
    finally:
        coordinator.close()


@pytest.mark.parametrize("raw", [b"{}", b"[]"])
def test_stop_rejects_unbound_conflicting_termination_bytes(raw):
    original, root, producer = _running_stop_source(containment_fault=None)
    value = ExternalControl(original).read(original.connection, producer)
    candidate = root / "code_agent_control" / value["attempt_id"] / "termination_evidence.json"
    candidate.write_bytes(raw)
    output = original.root
    original.close()
    coordinator = Coordinator(output, clock=FakeClock(140, 40))
    try:
        backend = RefuseRedispatch(output / "fake_backend", clock=lambda: 140)
        result = CodeWatchdog(coordinator, backend, DeterministicContainment(output / "containment"),
                              backend.read_receipt).enforce(producer)
        assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable"
        assert result["error"]["message"] == "Conflicting termination candidate"
        assert candidate.read_bytes() == raw
        assert not (candidate.parent / "termination_evidence_unavailable.json").exists()
        assert ExternalControl(coordinator).read(coordinator.connection, producer)["operation_phase"] == "interrupt_stop_intent_committed"
    finally:
        coordinator.close()
