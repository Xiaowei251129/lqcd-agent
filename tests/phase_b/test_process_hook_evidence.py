"""Real crash receipts bind production triggers to the parent pytest session."""
from harness.temporary import mkdtemp
from copy import deepcopy
from pathlib import Path
import multiprocessing

import pytest

from harness.contracts import ROOT, load_contracts
from harness.inventory import case_specs
from harness.pytest_evidence import (consume_process_hook, observe, observe_case, process_hook_request,
                                    production_hook, run_pytest_batches, validate_pytest)
from harness.strict_json import Invalid, canonical, read
from harness.trace import compare, event
from helpers.process_client import start_client
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from test_b02_reservation_boundaries import run_start


INVARIANTS = ["durable_child_trigger", "fresh_session_binding", "reservation_rollback_verified"]


def crash_receipt(side):
    root = Path(mkdtemp(prefix="lqcd-agent-hook-process-", dir="/private/tmp"))
    boundary = "control.start_run.not_applicable.operation_reserved"
    request = process_hook_request(boundary + "." + side + ".reservation_rolled_back", root)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=start_client, args=(child, str(root), (boundary, side)), kwargs={"hook_request": request})
    try:
        process.start()
        child.close()
        process.join(20)
        assert not process.is_alive() and process.exitcode == 84
        with pytest.raises(EOFError):
            parent.recv()
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()
    return root, request, process


@pytest.mark.parametrize("side", ["before", "after"])
def test_process_hook_roundtrip(side):
    root, request, process = crash_receipt(side)
    trigger = consume_process_hook(request, process, expected_exit=84)
    assert trigger["hook_ref"] == "src/lqcd_agent/control/coordinator.py:boundary"
    with pytest.raises(Invalid, match="duplicate_receipt"):
        consume_process_hook(request, process, expected_exit=84)
    coordinator = Coordinator(root, clock=FakeClock(140, 40))
    try:
        assert coordinator.lookup_key("public_control", "start-key") is None
        for table in ("control_operations", "control_phases", "control_snapshots", "control_publications",
                      "run_controls", "pause_ownership", "run_terminal_closure", "invocation_capabilities"):
            assert coordinator.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        assert not (root / "case").exists()
        result = run_start(root, None)
        assert result["operation_status"] == "committed" and result["lease_epoch"] == 1
    finally:
        coordinator.close()
    trace = {"schema_version": "0.1", "events": [event("reservation_rolled_back", phase="operation_reserved", source=side,
             outcome="reservation_rolled_back", owner="no_durable_operation")]}
    compare(trace, read(ROOT / f"tests/phase_b/expected_traces/reservation_rollback_{side}.json"))
    observe("B00-PROCESS-HOOK-" + side.upper(), {"kind": "boolean", "value": True}, INVARIANTS, trace)
    observe("b02-reservation-counterexample-" + side, {"kind": "boolean", "value": True}, INVARIANTS, trace)
    spec = case_specs(load_contracts()[0])[request["case_id"]]
    observe_case(request["case_id"], spec["outcome"], sorted(spec["invariants"]), trace)
    from harness import pytest_evidence
    from harness.failpoints import validate_runtime
    if pytest_evidence.ACTIVE:
        value = pytest_evidence.ACTIVE.value
        selected = {**value, **{key: [row for row in value[key] if row["nodeid"] == request["nodeid"]]
                              for key in ("hook_events", "case_results")}}
        scenario = {"scenario_id": "receipt", "pytest_nodeids": [request["nodeid"]],
                    "expected_trace_fixture": f"tests/phase_b/expected_traces/reservation_rollback_{side}.json"}
        registry = {"entries": [{"hook_ref": request["hook_ref"],
                                  "case_bindings": [{"case_id": request["case_id"], "scenario_ids": ["receipt"]}]}]}
        assert validate_runtime(selected, registry, {request["case_id"]: spec}, [scenario], ROOT) == [request["case_id"]]
        assert validate_runtime({**selected, "hook_events": []}, registry, {request["case_id"]: spec}, [scenario], ROOT) == []


@pytest.mark.parametrize("fault", ["session", "node", "case", "process_token", "pid", "hook", "exit"])
def test_child_receipt_cannot_be_rebound(fault):
    _, request, process = crash_receipt("before")
    if fault in ("session", "node", "case", "process_token"):
        field = {"session": "invocation_token", "node": "nodeid", "case": "case_id", "process_token": "process_token"}[fault]
        request = {**request, field: "foreign"}
    elif fault in ("pid", "hook"):
        path = Path(request["receipt_path"])
        receipt = read(path)
        receipt["process_id" if fault == "pid" else "hook_ref"] = 0 if fault == "pid" else "src/lqcd_agent/control/coordinator.py:Coordinator.get"
        path.write_bytes(canonical(receipt))
    with pytest.raises(Invalid):
        consume_process_hook(request, process, expected_exit=0 if fault == "exit" else 84)


def test_test_side_callback_cannot_impersonate_production():
    root = Path(mkdtemp(prefix="lqcd-agent-hook-spoof-", dir="/private/tmp"))
    request = process_hook_request("test-case", root)
    with pytest.raises(Invalid, match="production_source"):
        production_hook(request["case_id"], process_request=request)
    assert not Path(request["receipt_path"]).exists()


def test_bounded_batches_preserve_the_complete_session(tmp_path):
    from test_evidence_and_final import session_for
    root = tmp_path / "batched-project"
    (root / "tests").mkdir(parents=True)
    (root / "tests/test_batch.py").write_text("def test_one():\n    assert True\n\ndef test_two():\n    assert True\n")
    session = session_for(root, tmp_path / "batch-evidence")
    selection = ["tests/test_batch.py::test_one", "tests/test_batch.py::test_two"]
    evidence = run_pytest_batches(session, selection, batch_size=1)
    validate_pytest(evidence, session, selection)
    for field in ("collected", "nodes"):
        bad = deepcopy(evidence)
        bad[field].pop()
        with pytest.raises(Invalid):
            validate_pytest(bad, session, selection)
