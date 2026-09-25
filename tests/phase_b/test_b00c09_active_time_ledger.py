"""Independent replay checks for the B00C09 active-time ledger extension."""
from dataclasses import asdict

import pytest

from lqcd_agent.control.clock import Timestamp
from lqcd_agent.control.execution import parse_ledger, replay
from lqcd_agent.control.records import FIELDS, build_record
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from test_b03_reservation_boundaries import make_code_target


def _append(rows, kind, event, timestamp, **fields):
    previous = rows[-1]
    common = {key: previous[key] for key in ("run_id", "case_id", "artifact_head", "artifact_event_index")}
    if kind == "budget":
        budget = [row for row in rows if row["record_type"] == "budget"]
        fields = {"budget_event_id": f"budget_event_{len(budget) + 1:06d}", "budget_event_index": len(budget) + 1,
                  "policy_version": "0.1", "policy_digest": budget[0]["policy_digest"], "payload": fields,}
    record = build_record(kind, event, **common, event_index=len(rows) + 1,
                          previous_execution_head=digest(previous), timestamp=timestamp, **fields).value
    rows.append(record)
    replay(rows)
    return record


def _interval(rows, timestamp, *, stage, attempt, maximum, producer="external_test", owner="external_test"):
    budget = replay(rows).projection.value["budget"]["dimensions"]
    payload = {"schema_version": "active_time_0.1", "interval_id": producer + ":" + stage,
               "stage": stage, "attempt_id": attempt, "producer_operation_id": producer,
               "owner_operation_id": owner, "clock_epoch_id": "fake_epoch_1", "start_at": asdict(timestamp),
               "maximum_seconds": maximum, "run_remaining_before": budget["active_seconds_per_run"]["remaining"],
               "attempt_remaining_before": budget["active_seconds_per_attempt"]["remaining"] if stage == "attempt_active" else None,
               "deadline_monotonic_seconds": timestamp.monotonic_seconds + maximum}
    return _append(rows, "budget", "active_interval_reserved", timestamp, **payload)


def _settle(rows, timestamp, reservation, *, disposition="actual"):
    source = reservation["payload"]
    payload = {key: source[key] for key in ("schema_version", "interval_id", "stage", "attempt_id",
                                             "producer_operation_id", "owner_operation_id", "clock_epoch_id")}
    payload.update(settlement_operation_id=source["owner_operation_id"] if source["stage"] == "attempt_active" else "publisher",
                   lease_epoch=1, phase_revision=1,
                   end_at=asdict(timestamp) if disposition == "actual" else None,
                   actual_seconds=timestamp.monotonic_seconds - source["start_at"]["monotonic_seconds"] if disposition == "actual" else None,
                   disposition=disposition, evidence_digest=digest("stop-proof"))
    return _append(rows, "budget", "active_interval_settled", timestamp, **payload)


def test_setup_is_run_only_and_no_call_attempt_is_charged():
    coordinator, locator, advanced = make_code_target()
    try:
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        attempt = advanced["result"]["target_attempt_id"] if "target_attempt_id" in advanced["result"] else rows[-1]["target_attempt_id"]
        clock = coordinator.clock
        setup = _interval(rows, clock.now(), stage="host_setup", attempt=attempt, maximum=10)
        clock.advance(3)
        _settle(rows, clock.now(), setup)
        dimensions = replay(rows).projection.value["budget"]["dimensions"]
        assert dimensions["active_seconds_per_run"]["used"] == 3
        assert dimensions["active_seconds_per_attempt"]["used"] == 0
        active = _interval(rows, clock.now(), stage="attempt_active", attempt=attempt, maximum=6, owner="resume_test")
        scheduled = next(row for row in rows if row["record_type"] == "attempt" and row["attempt_id"] == attempt)
        fields = {key: scheduled[key] for key in FIELDS["attempt"]}
        _append(rows, "attempt", "started", clock.now(), **{**fields, "status": "running"})
        foreign = rows[:]
        _settle(foreign, clock.now(), active)
        foreign[-1]["payload"]["settlement_operation_id"] = "foreign"
        with pytest.raises(ControlIntegrityError):
            replay(foreign)
        clock.advance(6)
        _settle(rows, clock.now(), active)
        _append(rows, "attempt", "finished", clock.now(), **{**fields, "status": "succeeded"})
        dimensions = replay(rows).projection.value["budget"]["dimensions"]
        assert dimensions["active_seconds_per_run"]["used"] == 9
        assert dimensions["active_seconds_per_attempt"]["used"] == 6
    finally:
        coordinator.close()


def test_foreign_settlement_and_clock_regression_are_rejected():
    coordinator, locator, advanced = make_code_target()
    try:
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        attempt = rows[-1]["target_attempt_id"]
        setup = _interval(rows, coordinator.clock.now(), stage="host_setup", attempt=attempt, maximum=10)
        bad = {**setup["payload"], "interval_id": "foreign"}
        with pytest.raises(ControlIntegrityError):
            _append(rows[:], "budget", "active_interval_settled", coordinator.clock.now(),
                    **{**bad, "settlement_operation_id": "publisher", "lease_epoch": 1, "phase_revision": 1,
                       "end_at": None, "actual_seconds": None, "disposition": "conservative_maximum",
                       "evidence_digest": digest("stop-proof")})
        rollback = Timestamp("deterministic_harness", 99, 0)
        with pytest.raises(ControlIntegrityError):
            _settle(rows[:], rollback, setup)
        overage = Timestamp("deterministic_harness", 111, 11)
        with pytest.raises(ControlIntegrityError):
            _settle(rows[:], overage, setup)
    finally:
        coordinator.close()
