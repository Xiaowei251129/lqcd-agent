"""Unique close ownership derives disposition from actual committed evidence."""
from dataclasses import replace

import pytest

from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.operations import CloseRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest, loads
from test_pause_control import control


def test_runtime_failure_close_is_unique_and_replays_without_new_bytes(control):
    coordinator, plane, actor, locator = control
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    before = (root / "execution_history.jsonl").read_bytes()
    records = parse_ledger(before).values
    request = CloseRunRequest(locator, digest(records[-1]))
    result = plane.close_run(request, actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "failed"
    assert result["terminal_closure"] == "committed"
    after = (root / "execution_history.jsonl").read_bytes()
    assert after.startswith(before) and len(parse_ledger(after).values) == len(records) + 1
    assert plane.close_run(request, actor=actor) == result
    assert (root / "execution_history.jsonl").read_bytes() == after
    with pytest.raises(ControlIntegrityError, match="Competing terminal trigger"):
        plane.close_run(replace(request, trigger_execution_head=digest(records[-2])), actor=actor)
    closure = loads(coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0])
    assert closure["terminal_closure_owner_operation_id"] == result["operation_id"]
    assert closure["resolved_terminal_disposition"] == "failed"


def test_close_rejects_non_current_trigger_before_ownership(control):
    coordinator, plane, actor, locator = control
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    before = (root / "execution_history.jsonl").read_bytes()
    records = parse_ledger(before).values
    with pytest.raises(ControlIntegrityError, match="exact latest head"):
        plane.close_run(CloseRunRequest(locator, digest(records[-2])), actor=actor)
    assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 0
    assert (root / "execution_history.jsonl").read_bytes() == before
