"""Pure execution lifecycle validation shared by replay and artifact validation."""
from __future__ import annotations
from typing import Any, Iterable
from .identity import execution_id


def validate_execution_index_sequence(
    identities: Iterable[tuple[Any, Any]],
    *,
    label: str,
    prefix: str,
    width: int = 6,
) -> tuple[str | None, int]:
    by_index: dict[int, str] = {}
    seen_ids: set[str] = set()
    for identity, raw_index in identities:
        if (
            not isinstance(identity, str)
            or not identity
            or not isinstance(raw_index, int)
            or isinstance(raw_index, bool)
            or raw_index < 1
            or identity != execution_id(prefix, raw_index, width=width)
            or identity in seen_ids
            or raw_index in by_index
        ):
            raise ValueError(f"Execution ledger contains an invalid or duplicate {label} identity.")
        seen_ids.add(identity)
        by_index[raw_index] = identity
    if not by_index:
        return None, 0
    latest_index = max(by_index)
    if set(by_index) != set(range(1, latest_index + 1)):
        raise ValueError(f"Execution ledger {label} indexes are not contiguous.")
    return by_index[latest_index], latest_index


def attempt_lifecycle_records(
    records: list[dict[str, Any]],
    attempt_id: str,
) -> list[dict[str, Any]]:
    attempts = [
        record
        for record in records
        if record.get("record_type") == "attempt" and record.get("attempt_id") == attempt_id
    ]
    if not attempts:
        raise ValueError(f"Registered artifact Attempt is missing from the execution ledger: {attempt_id}")
    events = tuple(record.get("event") for record in attempts)
    allowed_events = {
        ("scheduled",),
        ("scheduled", "abandoned"),
        ("scheduled", "started"),
        ("scheduled", "started", "finished"),
    }
    if events not in allowed_events:
        raise ValueError(f"Attempt lifecycle is incomplete or out of order in the execution ledger: {attempt_id}")
    expected_statuses = {
        "scheduled": {"scheduled"},
        "started": {"running"},
        "finished": {"succeeded", "failed", "pending"},
        "abandoned": {"abandoned"},
    }
    if any(record.get("status") not in expected_statuses[str(record.get("event"))] for record in attempts):
        raise ValueError(f"Attempt lifecycle status is inconsistent in the execution ledger: {attempt_id}")
    return attempts


def attempt_provenance(
    attempts: list[dict[str, Any]],
    attempt_id: str,
) -> dict[str, Any]:
    required_identity_fields = (
        "run_id",
        "case_id",
        "cycle_id",
        "attempt_id",
        "attempt_kind",
        "node_name",
        "inbound_transition_id",
    )
    stable_fields = required_identity_fields + (
        "cycle_index",
        "attempt_index",
        "parent_attempt_id",
        "attempt_trigger",
    )
    if any(field not in record for record in attempts for field in stable_fields):
        raise ValueError(f"Registered artifact Attempt identity is incomplete in the execution ledger: {attempt_id}")
    expected = {field: attempts[0].get(field) for field in stable_fields}
    if any(
        not isinstance(expected[field], str) or not expected[field]
        for field in required_identity_fields
    ):
        raise ValueError(f"Registered artifact Attempt identity is incomplete in the execution ledger: {attempt_id}")
    if any({field: record.get(field) for field in stable_fields} != expected for record in attempts[1:]):
        raise ValueError(f"Registered artifact Attempt identity changes in the execution ledger: {attempt_id}")
    cycle_index = expected["cycle_index"]
    attempt_index = expected["attempt_index"]
    if (
        not isinstance(cycle_index, int)
        or isinstance(cycle_index, bool)
        or cycle_index < 1
        or expected["cycle_id"] != execution_id("cycle", cycle_index, width=4)
        or not isinstance(attempt_index, int)
        or isinstance(attempt_index, bool)
        or attempt_index < 1
        or expected["attempt_id"] != execution_id("attempt", attempt_index)
        or not isinstance(expected["attempt_trigger"], str)
        or not expected["attempt_trigger"]
        or (
            expected["parent_attempt_id"] is not None
            and (
                not isinstance(expected["parent_attempt_id"], str)
                or not expected["parent_attempt_id"]
            )
        )
    ):
        raise ValueError(f"Registered artifact Attempt index identity is invalid in the execution ledger: {attempt_id}")
    return expected


def human_response_lifecycle_records(
    execution_records: list[dict[str, Any]],
    response_id: str,
) -> list[dict[str, Any]]:
    responses = [
        record
        for record in execution_records
        if record.get("record_type") == "human_response"
        and record.get("human_response_id") == response_id
    ]
    events = tuple(record.get("event") for record in responses)
    if events not in {
        ("submitted",),
        ("submitted", "validated"),
        ("submitted", "invalid"),
        ("submitted", "validated", "consumed"),
    }:
        raise ValueError(f"Human Response lifecycle is incomplete or out of order: {response_id}")
    identity_fields = (
        "run_id",
        "case_id",
        "cycle_id",
        "human_request_id",
        "human_response_id",
        "response_index",
        "payload_reference",
        "payload_sha256",
    )
    expected = {field: responses[0].get(field) for field in identity_fields}
    if any({field: record.get(field) for field in identity_fields} != expected for record in responses[1:]):
        raise ValueError(f"Human Response identity changes in the execution ledger: {response_id}")
    if any(record.get("status") != record.get("event") for record in responses):
        raise ValueError(f"Human Response status is inconsistent in the execution ledger: {response_id}")
    response_index = expected["response_index"]
    if (
        not isinstance(response_index, int)
        or isinstance(response_index, bool)
        or response_index < 1
        or response_id != execution_id("human_response", response_index)
        or any(
            not isinstance(expected[field], str) or not expected[field]
            for field in (
                "run_id",
                "case_id",
                "cycle_id",
                "human_request_id",
                "payload_reference",
                "payload_sha256",
            )
        )
    ):
        raise ValueError(f"Human Response index identity is invalid: {response_id}")
    return responses


def human_request_lifecycle_records(
    execution_records: list[dict[str, Any]],
    request_id: str,
) -> list[dict[str, Any]]:
    requests = [
        record
        for record in execution_records
        if record.get("record_type") == "human_request"
        and record.get("human_request_id") == request_id
    ]
    events = tuple(record.get("event") for record in requests)
    if events not in {
        ("created",),
        ("created", "packet_written"),
        ("created", "satisfied"),
        ("created", "packet_written", "satisfied"),
    }:
        raise ValueError(f"Human Request lifecycle is incomplete or out of order: {request_id}")
    identity_fields = (
        "run_id",
        "case_id",
        "cycle_id",
        "human_request_id",
        "request_index",
        "request_kind",
        "requesting_attempt_id",
        "authorization_scope",
    )
    expected = {field: requests[0].get(field) for field in identity_fields}
    if any({field: record.get(field) for field in identity_fields} != expected for record in requests[1:]):
        raise ValueError(f"Human Request identity changes in the execution ledger: {request_id}")
    expected_statuses = {
        "created": "open",
        "packet_written": "open",
        "satisfied": "satisfied",
    }
    if any(record.get("status") != expected_statuses.get(str(record.get("event"))) for record in requests):
        raise ValueError(f"Human Request status is inconsistent in the execution ledger: {request_id}")
    request_index = expected["request_index"]
    if (
        not isinstance(request_index, int)
        or isinstance(request_index, bool)
        or request_index < 1
        or request_id != execution_id("human_request", request_index)
        or any(
            not isinstance(expected[field], str) or not expected[field]
            for field in (
                "run_id",
                "case_id",
                "cycle_id",
                "request_kind",
                "requesting_attempt_id",
            )
        )
        or not isinstance(expected["authorization_scope"], dict)
        or not expected["authorization_scope"]
    ):
        raise ValueError(f"Human Request index identity is invalid: {request_id}")
    return requests
