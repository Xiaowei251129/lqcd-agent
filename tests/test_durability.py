"""B02 tests exercise production persistence without claiming product behavior."""
from lqcd_agent.control.storage import execution_scratch_root
from tests.support import mkdtemp
from copy import deepcopy
from pathlib import Path
import multiprocessing
import sqlite3

import pytest

from lqcd_agent.control.budget import policy
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, exclusive_directory, publish_exact
from lqcd_agent.control.operations import select_successor, validate_phase_evidence, validate_reservation
from lqcd_agent.control.strict_json import ControlIntegrityError

from tests.processes import publication_client, reservation_client


@pytest.fixture
def output_root():
    return Path(mkdtemp(prefix="lqcd-agent-b02-", dir=execution_scratch_root()))


def reservation(operation_id, timestamp):
    selected = policy("phase_b_test")
    return {"target_run_identity": {"case_id": "case", "run_id": operation_id},
            "reserved_run_locator": {"case_id": "case", "run_id": operation_id},
            "canonical_budget_policy_bytes": selected.canonical.decode(),
            "budget_policy_digest": selected.value["policy_digest"],
            "budget_policy_profile": "phase_b_test", "budget_policy_version": "0.1",
            "budget_policy_selection_authority": "authenticated_host_profile_selection",
            "initial_invocation_capability_inputs": {"attempt_id": "attempt_000001",
                                                     "target_kind": "method_planner"}}


def reserve(coordinator, *, key="key", worker="worker", payload=None):
    return coordinator.reserve("start_run", "not_applicable", "scope", key,
                               payload or {"root_inputs_digest": "a" * 64}, worker, reservation, lease_seconds=10)


def test_reservation_replay_and_conflict(output_root):
    first = Coordinator(output_root, clock=FakeClock(100, 0))
    second = Coordinator(output_root, clock=FakeClock(100, 0))
    try:
        original = reserve(first)
        assert reserve(second) == original
        assert not (output_root / "case").exists()
        with pytest.raises(ControlIntegrityError, match="Same-key request conflict"):
            reserve(second, payload={"root_inputs_digest": "b" * 64})
        assert second.get(original["operation_id"]) == original
        assert second.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 1
    finally:
        first.close()
        second.close()


def test_operation_lease_fences_old_epoch_and_queries_do_not_renew(output_root):
    clock = FakeClock(100, 0)
    coordinator = Coordinator(output_root, clock=clock)
    try:
        original = reserve(coordinator)
        with pytest.raises(ControlIntegrityError, match="already leased"):
            coordinator.acquire(original["operation_id"], "other", lease_seconds=10)
        clock.advance(10)
        assert coordinator.get(original["operation_id"]) == original
        renewed = coordinator.acquire(original["operation_id"], "other", lease_seconds=10)
        assert renewed["lease_epoch"] == 2
        assert renewed["phase_revision"] == 1
        called = []
        with pytest.raises(ControlIntegrityError, match="Stale"):
            coordinator.step(original["operation_id"], "worker", 1, 1, "run_root_created",
                             lambda *_: called.append(True))
        assert not called
    finally:
        coordinator.close()


def test_exact_publication_rejects_conflict_partial_and_link(output_root):
    path = output_root / "history.jsonl"
    publish_exact(path, b'{"record":1}\n', previous=b"")
    publish_exact(path, b'{"record":1}\n', previous=b"")
    publish_exact(path, b'{"record":1}\n{"record":2}\n', previous=b'{"record":1}\n')
    expected = path.read_bytes()
    for previous, proposed in ((b"", b'{"record":9}\n'), (b'{"record":1}', b'{"record":1}\n'),
                               (expected, expected + b'{"record":3}')):
        with pytest.raises(ControlIntegrityError):
            publish_exact(path, proposed, previous=previous)
        assert path.read_bytes() == expected
    link = output_root / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        publish_exact(link, expected)
    assert path.read_bytes() == expected


def test_publication_crash_reopens_exact_prefix_without_second_identity(output_root):
    clock = FakeClock(100, 0)
    coordinator = Coordinator(output_root, clock=clock)
    operation = reserve(coordinator)
    run_root = output_root / "case" / operation["operation_id"]

    def materialize(db, current):
        exclusive_directory(run_root.parent)
        exclusive_directory(run_root)
        raise RuntimeError("crash after root sync before phase commit")

    with pytest.raises(RuntimeError, match="crash"):
        coordinator.step(operation["operation_id"], "worker", 1, 1, "run_root_created", materialize)
    assert run_root.is_dir()
    assert coordinator.get(operation["operation_id"]) == operation
    coordinator.close()
    restarted = Coordinator(output_root, clock=FakeClock(110, 10))
    try:
        acquired = restarted.acquire(operation["operation_id"], "new-worker", lease_seconds=10)

        def complete(db, current):
            exclusive_directory(run_root)
            return {"reserved_run_locator": current["reservation"]["reserved_run_locator"],
                    "current_lease_epoch": current["lease_epoch"]}

        finished = restarted.step(acquired["operation_id"], "new-worker", 2, 1, "run_root_created", complete)
        assert finished["phase_revision"] == 2 and finished["phase"] == "run_root_created"
        assert [row["phase"] for row in restarted.history(finished["operation_id"])] == [
            "operation_reserved", "run_root_created"]
        assert list(run_root.parent.iterdir()) == [run_root]
    finally:
        restarted.close()


def test_closed_coordinator_schema_and_consistent_backup(output_root):
    coordinator = Coordinator(output_root, clock=FakeClock(100, 0))
    original = reserve(coordinator)
    assert coordinator.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert coordinator.connection.execute("PRAGMA synchronous").fetchone()[0] == 2
    assert coordinator.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    backup = output_root / "backup.sqlite"
    coordinator.backup(backup)
    saved = sqlite3.connect(backup)
    try:
        assert saved.execute("SELECT operation_id FROM control_operations").fetchone()[0] == original["operation_id"]
        assert saved.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        saved.close()
    coordinator.connection.execute("CREATE TABLE unexpected (value TEXT)")
    coordinator.close()
    with pytest.raises(ControlIntegrityError, match="schema"):
        Coordinator(output_root, clock=FakeClock(100, 0))


def test_closed_overlay_and_guarded_branch():
    value = reservation("operation", None)
    validate_reservation("start_run", "not_applicable", value)
    for bad in ({**value, "allow": True}, {key: val for key, val in value.items() if key != "budget_policy_digest"},
                {**value, "budget_policy_digest": None}):
        with pytest.raises(ControlIntegrityError):
            validate_reservation("start_run", "not_applicable", bad)
    operation = {"operation_type": "advance_run", "operation_variant": "not_applicable",
                 "phase": "transition_heads_verified", "phase_revision": 9,
                 "reservation": {"transition_target_kind": "attempt"}}
    assert select_successor(operation, "target_preparation_committed", {"transition_target_kind": "attempt"})
    for target, fields in (("result_committed", {"transition_target_kind": "attempt"}),
                           ("result_committed", {"transition_target_kind": "end"}),
                           ("invocation_capability_prepared", {"transition_target_kind": "attempt"}),
                           ("target_preparation_committed", {})):
        with pytest.raises(ControlIntegrityError):
            select_successor(operation, target, fields)
    end = deepcopy(operation)
    end["reservation"]["transition_target_kind"] = "end"
    assert select_successor(end, "result_committed", {"transition_target_kind": "end"})
    with pytest.raises(ControlIntegrityError):
        validate_phase_evidence(end, "result_committed", {"exact_public_or_internal_result": {}, "final_phase_revision": 9})


def test_durability_preflight_precedes_database_and_run_bytes(output_root, monkeypatch):
    from lqcd_agent.control import coordinator as storage

    def reject(_):
        raise ControlIntegrityError("Not a writable local filesystem")

    monkeypatch.setattr(storage, "local_filesystem", reject)
    with pytest.raises(ControlIntegrityError, match="local filesystem"):
        Coordinator(output_root)
    assert list((output_root / ".lqcd").iterdir()) == []
    assert not (output_root / "case").exists()


@pytest.mark.parametrize("boundary", ["preflight.old.file_sync", "preflight.new.directory_sync",
                                      "preflight.atomic_replace"])
def test_sync_preflight_failure_never_authorizes_run(output_root, boundary):
    def fail(name, side, value):
        if name == boundary and side == "after":
            raise OSError("injected durability failure")

    with pytest.raises(OSError, match="durability failure"):
        Coordinator(output_root, observer=fail)
    assert not (output_root / ".lqcd/control_operations.sqlite").exists()
    assert not (output_root / "case").exists()


def test_frozen_publications_are_immutable_and_lease_fenced(output_root):
    clock = FakeClock(100, 0)
    coordinator = Coordinator(output_root, clock=clock)
    try:
        operation = reserve(coordinator)
        path = output_root / "case" / "run" / "marker"
        args = (operation["operation_id"], "worker", 1, 1, "run_root_created", path)
        coordinator.freeze_publication(*args, b"frozen")
        coordinator.freeze_publication(*args, b"frozen")
        assert not path.parent.exists()
        with pytest.raises(ControlIntegrityError, match="changed"):
            coordinator.freeze_publication(*args, b"different")
        with pytest.raises(ControlIntegrityError, match="escaped"):
            coordinator.freeze_publication(*args[:-1], coordinator.path, b"replace database")
        with pytest.raises(ControlIntegrityError, match="immediate"):
            coordinator.freeze_publication(*args[:4], "checkpoint_committed", path, b"skip")
        clock.advance(9)
        renewed = coordinator.renew(operation["operation_id"], "worker", 1, 1, lease_seconds=10)
        assert renewed["lease_expires"] == 19 and renewed["phase_revision"] == 1
        clock.advance(10)
        with pytest.raises(ControlIntegrityError, match="expired"):
            coordinator.renew(operation["operation_id"], "worker", 1, 1, lease_seconds=10)
        coordinator.acquire(operation["operation_id"], "replacement", lease_seconds=10)
        with pytest.raises(ControlIntegrityError, match="Stale"):
            coordinator.freeze_publication(*args, b"frozen")
        assert not path.exists()
    finally:
        coordinator.close()


@pytest.mark.parametrize("different", [False, True])
def test_two_process_reservation_arbitration(output_root, different):
    Coordinator(output_root, clock=FakeClock(100, 0)).close()
    context = multiprocessing.get_context("spawn")
    overlay = reservation("run", None)
    workers = []
    try:
        for i in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=reservation_client, args=(child, str(output_root), overlay,
                                                                      {"input": i if different else 0}))
            process.start()
            child.close()
            workers.append((process, parent))
        for _, pipe in workers:
            assert pipe.poll(20) and pipe.recv() == "ready"
        for _, pipe in workers:
            pipe.send("go")
        results = []
        for process, pipe in workers:
            assert pipe.poll(20)
            results.append(pipe.recv())
            process.join(20)
            assert process.exitcode == 0
        if different:
            assert sorted(row[0] for row in results) == ["rejected", "reserved"]
        else:
            assert results[0] == results[1] and results[0][0] == "reserved"
        coordinator = Coordinator(output_root, clock=FakeClock(100, 0))
        try:
            assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 1
            assert not (output_root / "case").exists()
        finally:
            coordinator.close()
    finally:
        for process, pipe in workers:
            if process.is_alive():
                process.terminate()
                process.join(5)
            pipe.close()


def test_fresh_process_crash_materializes_only_committed_plan(output_root):
    context = multiprocessing.get_context("spawn")
    overlay = reservation("run", None)
    for crash in (True, False):
        parent, child = context.Pipe()
        process = context.Process(target=publication_client, args=(child, str(output_root), overlay, crash))
        try:
            process.start()
            child.close()
            if not crash:
                assert parent.poll(20)
                operation, history = parent.recv()
                assert operation["phase"] == "policy_published" and operation["lease_epoch"] == 2
                assert [row["phase"] for row in history] == ["operation_reserved", "run_root_created", "policy_published"]
            process.join(20)
            assert process.exitcode == (83 if crash else 0)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
        assert (output_root / "case/run/budget_policy.json").read_bytes() == overlay["canonical_budget_policy_bytes"].encode()
    assert list((output_root / "case").iterdir()) == [output_root / "case/run"]
