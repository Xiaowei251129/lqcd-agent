"""Actual reservation rollback and committed replay, without acceptance credit."""
from harness.temporary import mkdtemp
import multiprocessing

import pytest

from helpers.process_client import start_client
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ControlPlane
from test_bootstrap_control import ACTOR, request, root
from test_pause_control import control
from test_snapshot_loss_control import requests


def run_start(root, boundary):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=start_client, args=(child, str(root), boundary))
    try:
        process.start()
        child.close()
        process.join(20)
        assert not process.is_alive()
        if boundary is not None:
            assert process.exitcode == 84
            with pytest.raises(EOFError):
                parent.recv()
            return None
        assert process.exitcode == 0 and parent.poll(2)
        return parent.recv()
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()


@pytest.mark.parametrize("side", ["before", "after"])
def test_reservation_process_exit_rolls_back_without_an_operation_or_run(root, side):
    run_start(root, ("control.start_run.not_applicable.operation_reserved", side))
    coordinator = Coordinator(root, clock=FakeClock(140, 40))
    try:
        assert coordinator.lookup_key("public_control", "start-key") is None
        for table in ("control_operations", "control_phases", "control_snapshots", "control_publications",
                      "run_controls", "pause_ownership", "run_terminal_closure", "invocation_capabilities"):
            assert coordinator.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        assert not (root / "case").exists()
        result = run_start(root, None)
        assert result["operation_status"] == "committed" and result["run_status"] == "running"
        assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 1
        assert coordinator.get(result["operation_id"])["lease_epoch"] == 1
        assert coordinator.get(result["operation_id"])["worker_owner_id"] == "second"
    finally:
        coordinator.close()


@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_committed_pause_same_key_replay_preserves_its_original_terminal_result(control, fault):
    coordinator, plane, actor, locator = control
    typed = requests(locator)
    plane.publish_pause(typed["publish"], actor=actor)
    result = plane.resume_run(typed["resume"], actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "halted"
    original = coordinator.get(result["operation_id"])
    history = coordinator.history(result["operation_id"])
    owners = {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)]
              for table in ("pause_ownership", "run_terminal_closure")}
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    before = {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    with coordinator.transaction() as db:
        if fault == "missing":
            db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (result["operation_id"],))
        else:
            db.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?", (b'{}', result["operation_id"]))
    assert plane.resume_run(typed["resume"], actor=actor) == result
    assert coordinator.get(result["operation_id"]) == original
    assert coordinator.history(result["operation_id"]) == history
    assert {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)]
            for table in owners} == owners
    assert {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_committed_replay_cannot_be_reclassified_by_lost_materialization_plan(root, fault):
    result = run_start(root, None)
    coordinator = Coordinator(root, clock=FakeClock(180, 80))
    try:
        original = coordinator.get(result["operation_id"])
        history = coordinator.history(result["operation_id"])
        locator = result["result"]["run_locator"]
        run = root / locator["case_id"] / locator["run_id"]
        before = {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()}
        with coordinator.transaction() as db:
            if fault == "missing":
                db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (result["operation_id"],))
            else:
                db.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?", (b'{}', result["operation_id"]))
        plane = ControlPlane(coordinator, worker_id="observer")
        assert plane.start_run(request(), actor=ACTOR) == result
        assert plane.query_operation(result["operation_id"]) == result
        assert coordinator.get(result["operation_id"]) == original
        assert coordinator.history(result["operation_id"]) == history
        assert {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before
    finally:
        coordinator.close()


@pytest.mark.parametrize("side", ["before", "after"])
def test_fork_source_cas_process_exit_is_still_before_reservation_commit(side):
    from pathlib import Path
    from helpers.runtime_cases import phase_fixture, run_client, run_files
    from harness.pytest_evidence import process_hook_request
    from lqcd_agent.control.coordinator import TABLES

    setup = "control.fork_run.not_applicable.operation_reserved.after.reservation_rolled_back"
    with phase_fixture(setup) as (coordinator, config):
        before = {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)] for table in TABLES}
        source = run_files(coordinator.root)
        receipts = Path(mkdtemp(prefix="lqcd-agent-cas-proof-", dir="/private/tmp"))
        receipt = process_hook_request("child.source_revision_cas." + side + ".reservation_rolled_back", receipts)
        fault = run_client(config, 0, fault=("child.source_revision_cas", side), hook_request=receipt)
        assert fault["operation"]["phase"] == "operation_reserved"
        assert {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)] for table in TABLES} == before
        assert run_files(coordinator.root) == source
        recovered = run_client(config, 40)["result"]
        assert recovered["operation_status"] == "committed" and recovered["lease_epoch"] == 1
        assert recovered["operation_id"] != fault["operation"]["operation_id"]
        assert all(run_files(coordinator.root)[path] == content for path, content in source.items())
