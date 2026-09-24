"""Expose the missing durable active-time handoff; not B03 acceptance credit."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from lqcd_agent.code_agent.prestart import CodePrestart
from lqcd_agent.control.budget import validate_budget_payload
from lqcd_agent.control.clock import FakeClock, measure
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger, replay
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.pause import PublishPauseRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from helpers.code_workspace import immutable_base_repository
from test_b03_task_trace_boundary import task_trace_witness
from test_execution_0_4_foundation import bootstrap, attempt, reserve, DIGEST


def setup_clock_witness():
    repository, base = immutable_base_repository()
    witness = task_trace_witness(base)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    clock = FakeClock(100, 0)
    coordinator = Coordinator(root.parent.parent, clock=clock)
    try:
        service = CodePrestart(coordinator, witness["task"]["producer_operation_id"], "host", 1)
        start = clock.now()
        service.commit_task(witness["task"])
        clock.advance(3)
        service.commit_manifest(witness["manifest"])
        expected = measure("host_setup", start, clock.now())
        before = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        before_dimensions = replay(before).projection.value["budget"]["dimensions"]
        reservation = service.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
            "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10, config_digest=digest("config"))
        service.commit_core()
        service.materialize_workspace(repository)
        locator = {key: witness["task"][key] for key in ("case_id", "run_id")}
        target = witness["task"]["attempt_id"]
        paused = ControlPlane(coordinator, worker_id="host").publish_pause(
            PublishPauseRequest(locator, "external_result", target, target,
                {"kind": "external_result", "producer_operation_id": service.producer},
                {"actor_type": "human", "scopes": ["resume"]}, "publish-clock-witness"),
            actor=ActorContext("operator", "human", ("control.internal",)))
        assert paused["operation_status"] == "committed" and paused["run_status"] == "paused"
        after = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        return {"root": str(root), "expected_setup_charge": asdict(expected),
                "before_dimensions": before_dimensions,
                "after_dimensions": replay(after).projection.value["budget"]["dimensions"],
                "reservation": reservation, "records": after, "pause": paused}
    finally:
        coordinator.close()


def test_host_setup_clock_is_not_in_the_authoritative_budget_projection():
    value = setup_clock_witness()
    assert value["expected_setup_charge"] == {"stage": "host_setup", "run_seconds": 3, "attempt_seconds": 0}
    assert value["before_dimensions"]["active_seconds_per_run"]["used"] == 0
    assert value["before_dimensions"]["active_seconds_per_attempt"]["used"] == 0
    assert value["after_dimensions"]["active_seconds_per_run"]["used"] == 10
    assert value["after_dimensions"]["active_seconds_per_attempt"]["used"] == 10
    assert not any(record["record_type"] == "attempt" and record["event"] == "started" and
                   record["attempt_id"] == value["reservation"]["payload"]["attempt_id"] for record in value["records"])


def test_finished_attempt_without_calls_loses_its_active_interval():
    ledger = bootstrap()
    started = attempt(ledger, "started")
    ledger.clock.advance(5)
    finished = attempt(ledger, "finished")
    elapsed = finished["created_at"]["monotonic_seconds"] - started["created_at"]["monotonic_seconds"]
    assert elapsed == 6
    dimensions = replay(ledger.records).projection.value["budget"]["dimensions"]
    assert dimensions["active_seconds_per_run"]["used"] == dimensions["active_seconds_per_attempt"]["used"] == 0


@pytest.mark.parametrize("proposal", ["new_kind", "run_only_vector", "new_event"])
def test_existing_closed_budget_wire_cannot_encode_run_only_setup(proposal):
    ledger = bootstrap()
    attempt(ledger, "started")
    value = deepcopy(reserve(ledger)["payload"])
    event = "resource_reserved"
    if proposal == "new_kind":
        value["resource_kind"] = "host_setup"
    elif proposal == "run_only_vector":
        value["maximum_charge"]["run_active_seconds"] = 3
    else:
        event = "active_time_recorded"
    with pytest.raises(ControlIntegrityError):
        validate_budget_payload(event, value)


def test_adding_setup_to_resource_seconds_also_charges_target_attempt():
    ledger = bootstrap()
    attempt(ledger, "started")
    reserve(ledger)
    ledger.budget("resource_settled", resource_operation_id="resource_1",
        actual={"llm_calls": 1, "tool_calls": 0, "verification_commands": 0, "active_seconds": 7},
        tokens={"state": "unknown", "value": None}, cost={"state": "unknown", "value": None},
        evidence_digest=DIGEST, operation_id="owner", lease_epoch=1, phase_revision=1)
    dimensions = replay(ledger.records).projection.value["budget"]["dimensions"]
    assert dimensions["active_seconds_per_run"]["used"] == dimensions["active_seconds_per_attempt"]["used"] == 7
