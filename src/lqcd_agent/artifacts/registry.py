"""Run-local immutable artifact registry and current-result projection."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


ARTIFACT_SCHEMA_VERSION = "0.1"
ARTIFACT_SLOTS = (
    "plan",
    "code",
    "analysis",
    "review",
    "decision",
    "approval",
    "terminal",
)
SLOT_BY_ATTEMPT_KIND = {
    "method_planner": "plan",
    "code_agent": "code",
    "analysis_engineer": "analysis",
    "scientific_reviewer": "review",
    "decision_coordinator": "decision",
    "human_gate": "approval",
    "memory_report": "terminal",
}
INVALIDATED_SLOTS_BY_TARGET_KIND = {
    "method_planner": ARTIFACT_SLOTS,
    "code_agent": ARTIFACT_SLOTS[1:],
    "analysis_engineer": ARTIFACT_SLOTS[2:],
    "scientific_reviewer": ARTIFACT_SLOTS[3:],
    "decision_coordinator": ARTIFACT_SLOTS[4:],
    "memory_report": ARTIFACT_SLOTS[6:],
}
STATE_FIELDS_BY_SLOT = {
    "plan": ("method_plan_path", "coder_task_packet_path"),
    "code": ("code_change_summary_path", "tests_status_path"),
    "analysis": ("run_result_path", "analysis_outputs_dir"),
    "review": ("scientific_review_report_path",),
    "decision": ("decision_log_path",),
    "approval": ("approval_packet_dir", "human_decision_path"),
    "terminal": ("memory_update_path", "final_report_path"),
}
CANONICAL_CODE_PATH_FIELDS = (
    "code_agent_task_path",
    "code_agent_result_path",
    "code_change_manifest_path",
    "code_verification_results_path",
)
CODE_STATE_PATH_FIELDS = (*STATE_FIELDS_BY_SLOT["code"], *CANONICAL_CODE_PATH_FIELDS)
CODE_MEMBER_BY_STATE_FIELD = dict(zip(CANONICAL_CODE_PATH_FIELDS, (
    "code_agent_task.json", "code_agent_result.json", "change_manifest.json", "verification_results.json")))


def state_fields_for_slot(slot: str, schema_version: str) -> tuple[str, ...]:
    if slot == "code" and schema_version == "0.4":
        return CODE_STATE_PATH_FIELDS
    return STATE_FIELDS_BY_SLOT[slot]
POINTER_FIELDS = {
    "artifact_id",
    "slot",
    "cycle_id",
    "attempt_id",
    "attempt_kind",
    "status",
    "dependencies",
    "members",
    "state_paths",
}
LEGACY_PROJECTION_ROOTS = (
    "method_plan.json",
    "coder_task_packet.yaml",
    "code_change_summary.md",
    "tests_status.json",
    "analysis_outputs",
    "run_result.json",
    "manifest.json",
    "run.log",
    "scientific_review_report.json",
    "decision_log.json",
    "approval_packet",
    "memory_update.json",
    "final_report.md",
    "llm_calls",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _event_id(index: int) -> str:
    return f"artifact_event_{index:06d}"


def _execution_id(prefix: str, index: int, *, width: int = 6) -> str:
    return f"{prefix}_{index:0{width}d}"


def _validate_execution_index_sequence(
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
            or identity != _execution_id(prefix, raw_index, width=width)
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


def _run_root(state: dict[str, Any]) -> Path:
    return Path(str(state["output_dir"])).resolve()


def _history_path(state: dict[str, Any]) -> Path:
    return _run_root(state) / "artifact_history.jsonl"


def _index_path(state: dict[str, Any]) -> Path:
    return _run_root(state) / "artifact_index.json"


def attempt_output_dir(state: dict[str, Any]) -> Path:
    attempt_id = state.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id:
        raise ValueError("Artifact output requires an active Attempt identity.")
    return _run_root(state) / "attempts" / attempt_id


def _assert_active_attempt(state: dict[str, Any]) -> None:
    if state.get("attempt_status") != "running":
        raise ValueError("Artifact output requires a running Attempt.")
    history_path = Path(str(state.get("execution_history_path", "")))
    if not history_path.is_file():
        raise ValueError("Artifact output requires an execution ledger.")
    records = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    attempts = [
        record
        for record in records
        if record.get("record_type") == "attempt" and record.get("attempt_id") == state.get("attempt_id")
    ]
    if not attempts or attempts[-1].get("event") != "started" or attempts[-1].get("status") != "running":
        raise ValueError("Artifact output requires the latest started Attempt ledger record.")
    field_pairs = (
        ("run_id", "run_id"),
        ("case_id", "case_id"),
        ("cycle_id", "cycle_id"),
        ("attempt_kind", "attempt_kind"),
        ("node_name", "attempt_node"),
    )
    for ledger_field, state_field in field_pairs:
        if attempts[-1].get(ledger_field) != state.get(state_field):
            raise ValueError(f"Artifact producing Attempt disagrees with the execution ledger: {state_field}")


def _read_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line, object_pairs_hook=_reject_duplicate_object_keys)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid artifact history JSON on line {line_number}: {path}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Artifact history line {line_number} is not an object: {path}")
        records.append(record)
    return records


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"Duplicate JSON object key is not allowed: {key}")
        payload[key] = value
    return payload


def _execution_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    history_path = Path(str(state.get("execution_history_path", "")))
    if not history_path.is_file():
        raise ValueError("Artifact registry requires an execution ledger.")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(history_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line, object_pairs_hook=_reject_duplicate_object_keys)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid execution ledger JSON on line {line_number}: {history_path}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Execution ledger line {line_number} is not an object: {history_path}")
        records.append(record)
    return records


def _execution_attempt_lifecycle_records(
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


def _execution_attempt_provenance(state: dict[str, Any], attempt_id: str) -> dict[str, Any]:
    attempts = _execution_attempt_lifecycle_records(_execution_records(state), attempt_id)
    return _attempt_provenance_from_lifecycle(attempts, attempt_id)


def _attempt_provenance_from_lifecycle(
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
        or expected["cycle_id"] != _execution_id("cycle", cycle_index, width=4)
        or not isinstance(attempt_index, int)
        or isinstance(attempt_index, bool)
        or attempt_index < 1
        or expected["attempt_id"] != _execution_id("attempt", attempt_index)
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


def _execution_attempt_identity(state: dict[str, Any], attempt_id: str) -> dict[str, Any]:
    provenance = _execution_attempt_provenance(state, attempt_id)
    return {
        field: provenance[field]
        for field in ("run_id", "case_id", "cycle_id", "attempt_id", "attempt_kind", "node_name")
    }


def _execution_transition_provenance(
    state: dict[str, Any],
    transition_id: str,
) -> dict[str, Any]:
    return _committed_transition_record(_execution_records(state), transition_id)


def _committed_transition_record(
    records: list[dict[str, Any]],
    transition_id: str,
) -> dict[str, Any]:
    transitions = [
        record
        for record in records
        if record.get("record_type") == "transition"
        and record.get("event") == "committed"
        and record.get("transition_id") == transition_id
    ]
    if len(transitions) != 1:
        raise ValueError(f"Artifact invalidation requires one committed Transition: {transition_id}")
    transition = transitions[0]
    if transition.get("status") != "committed":
        raise ValueError(f"Artifact invalidation Transition is not committed: {transition_id}")
    return transition


def _execution_human_response_submission(
    state: dict[str, Any],
    response_id: str,
) -> dict[str, Any]:
    submissions = [
        record
        for record in _execution_records(state)
        if record.get("record_type") == "human_response"
        and record.get("event") == "submitted"
        and record.get("human_response_id") == response_id
    ]
    if len(submissions) != 1:
        raise ValueError(f"Human Response snapshot requires one submitted ledger record: {response_id}")
    return submissions[0]


def _validate_human_response_snapshot(
    state: dict[str, Any],
    record: dict[str, Any],
) -> None:
    response_id = record.get("human_response_id")
    if not isinstance(response_id, str) or not response_id:
        raise ValueError("Human Response snapshot is missing its response identity.")
    if record.get("artifact_id") != f"{response_id}:payload" or record.get("slot") is not None:
        raise ValueError("Human Response snapshot artifact identity is inconsistent.")
    if record.get("reason_code") != "human_response_submitted" or record.get("dependencies") != []:
        raise ValueError("Human Response snapshot metadata is inconsistent.")
    members = record.get("members")
    if not isinstance(members, list) or len(members) != 1 or not isinstance(members[0], dict):
        raise ValueError("Human Response snapshot must contain exactly one payload member.")
    member = members[0]
    expected_relative = f"human_responses/{response_id}/payload.json"
    if (
        member.get("logical_name") != "payload.json"
        or member.get("canonical_path") != expected_relative
        or member.get("projection_path") is not None
        or member.get("media_type") != "application/json"
    ):
        raise ValueError("Human Response snapshot member mapping is inconsistent.")
    submission = _execution_human_response_submission(state, response_id)
    expected_path = (_run_root(state) / expected_relative).resolve()
    if (
        submission.get("run_id") != record.get("run_id")
        or submission.get("case_id") != record.get("case_id")
        or submission.get("cycle_id") != record.get("cycle_id")
        or submission.get("human_request_id") != record.get("human_request_id")
        or Path(str(submission.get("payload_reference", ""))).resolve() != expected_path
        or submission.get("payload_sha256") != member.get("sha256")
    ):
        raise ValueError("Human Response snapshot does not match its submitted execution ledger record.")


def _validate_registered_pointer(
    state: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    if record.get("reason_code") != "attempt_output_registered":
        raise ValueError("Registered artifact reason code is inconsistent.")
    pointer = record.get("pointer")
    if not isinstance(pointer, dict) or set(pointer) != POINTER_FIELDS:
        raise ValueError("Registered artifact pointer does not match the typed pointer contract.")
    slot = record.get("slot")
    attempt_id = record.get("attempt_id")
    artifact_id = record.get("artifact_id")
    if not isinstance(slot, str) or slot not in ARTIFACT_SLOTS:
        raise ValueError("Registered artifact pointer has an invalid slot.")
    if not isinstance(attempt_id, str) or artifact_id != f"{attempt_id}:{slot}":
        raise ValueError("Registered artifact ID does not match its Attempt and slot.")
    expected_values = {
        "artifact_id": artifact_id,
        "slot": slot,
        "cycle_id": record.get("cycle_id"),
        "attempt_id": attempt_id,
        "status": record.get("status"),
        "dependencies": record.get("dependencies"),
        "members": record.get("members"),
    }
    for field, expected in expected_values.items():
        if pointer.get(field) != expected:
            raise ValueError(f"Registered artifact pointer disagrees with history field {field}.")
    attempt_kind = pointer.get("attempt_kind")
    if SLOT_BY_ATTEMPT_KIND.get(str(attempt_kind)) != slot:
        raise ValueError("Registered artifact pointer Attempt kind does not match its slot.")
    execution_identity = _execution_attempt_identity(state, attempt_id)
    lifecycle = _execution_attempt_lifecycle_records(_execution_records(state), attempt_id)
    if not any(record.get("event") == "started" for record in lifecycle):
        raise ValueError("Registered artifact producing Attempt was never started.")
    registered_identity = {
        "run_id": record.get("run_id"),
        "case_id": record.get("case_id"),
        "cycle_id": pointer.get("cycle_id"),
        "attempt_id": pointer.get("attempt_id"),
        "attempt_kind": attempt_kind,
        "node_name": record.get("node_name"),
    }
    if registered_identity != execution_identity:
        raise ValueError("Registered artifact pointer identity does not match the execution ledger.")
    dependencies = pointer.get("dependencies")
    if not isinstance(dependencies, list) or any(not isinstance(value, str) for value in dependencies):
        raise ValueError("Registered artifact pointer dependencies are invalid.")
    state_paths = pointer.get("state_paths")
    expected_state_fields = set(state_fields_for_slot(slot, state.get("schema_version")))
    if not isinstance(state_paths, dict) or set(state_paths) != expected_state_fields:
        raise ValueError("Registered artifact pointer state paths do not match its slot.")

    run_root = _run_root(state)
    attempt_root = (run_root / "attempts" / attempt_id).resolve()
    members = pointer.get("members")
    if not isinstance(members, list) or not members or any(not isinstance(member, dict) for member in members):
        raise ValueError("Registered artifact pointer members are invalid.")
    member_paths: set[Path] = set()
    for member in members:
        relative = Path(str(member.get("canonical_path", "")))
        canonical = (run_root / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not _is_within(canonical, attempt_root):
            raise ValueError("Registered artifact member escapes its producing Attempt.")
        projection = member.get("projection_path")
        if (
            not isinstance(projection, str)
            or not projection
            or canonical.relative_to(attempt_root).as_posix() != projection
            or member.get("logical_name") != projection
        ):
            raise ValueError("Registered artifact member path mapping is inconsistent.")
        _projection_target(run_root, projection)
        _assert_no_symlink(run_root / relative, attempt_root)
        member_paths.add(canonical)
    for field, value in state_paths.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ValueError(f"Registered artifact pointer state path {field} is invalid.")
        path = Path(value).resolve()
        if field == "human_decision_path":
            expected_ingress = (run_root / "approval_packet" / "07_human_decision.yaml").resolve()
            if slot != "approval" or path != expected_ingress:
                raise ValueError("Human decision state path does not match the managed ingress path.")
            continue
        if not _is_within(path, attempt_root):
            raise ValueError(f"Registered artifact pointer state path escapes its Attempt: {field}")
        if not field.endswith("_dir") and path not in member_paths:
            raise ValueError(f"Registered artifact pointer file is not a bundle member: {field}")
    if slot == "code" and state.get("schema_version") == "0.4":
        legacy = attempt_kind == "legacy_codex_handoff"
        for field in (CANONICAL_CODE_PATH_FIELDS if legacy else STATE_FIELDS_BY_SLOT["code"]):
            if state_paths[field] is not None:
                raise ValueError("Code pointer crossed its producer path boundary.")
        if not legacy:
            for field, name in CODE_MEMBER_BY_STATE_FIELD.items():
                if state_paths[field] != str(attempt_root / name):
                    raise ValueError("Canonical Code pointer has a missing or substituted member path.")
            from lqcd_agent.code_agent.artifacts import validate_code_result
            from lqcd_agent.code_agent.schemas import validate_task
            from lqcd_agent.control.coordinator import read_regular
            task = validate_task(read_regular(attempt_root / "code_agent_task.json")).value
            result = validate_code_result(read_regular(attempt_root / "code_agent_result.json"), task).value
            if result["status"] != pointer["status"] or result["attempt_id"] != attempt_id:
                raise ValueError("Canonical Code pointer disagrees with its validated result.")
    return deepcopy(pointer)


def _transition_creates_human_request(
    execution_records: list[dict[str, Any]],
    transition: dict[str, Any],
) -> bool:
    request_id = transition.get("human_request_id")
    if not isinstance(request_id, str) or not request_id:
        return False
    requests = [
        record
        for record in execution_records
        if record.get("record_type") == "human_request"
        and record.get("event") == "created"
        and record.get("human_request_id") == request_id
    ]
    if len(requests) != 1:
        raise ValueError(f"Human Gate Transition has an invalid Human Request ledger identity: {request_id}")
    request = requests[0]
    return (
        request.get("run_id") == transition.get("run_id")
        and request.get("case_id") == transition.get("case_id")
        and request.get("cycle_id") == transition.get("source_cycle_id")
        and request.get("requesting_attempt_id") == transition.get("source_attempt_id")
    )


def _human_response_lifecycle_records(
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
        or response_id != _execution_id("human_response", response_index)
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


def _human_request_lifecycle_records(
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
        or request_id != _execution_id("human_request", request_index)
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


def _validate_reverse_history_completeness(
    state: dict[str, Any],
    registered_pointers: dict[str, dict[str, Any]],
    cleared_by_attempt: dict[str, dict[str, str]],
    protected_keys: set[tuple[str, str]],
    *,
    allow_pending_invalidation_attempt_id: str | None,
    allow_pending_accepted_protection_artifact_id: str | None,
    allow_pending_human_response_id: str | None,
) -> None:
    execution_records = _execution_records(state)
    cycle_records = [
        record for record in execution_records if record.get("record_type") == "cycle"
    ]
    if not cycle_records or any(
        any(
            field not in record
            for field in ("cycle_id", "cycle_index", "parent_cycle_id")
        )
        or record.get("event") != "created"
        or record.get("status") != "active"
        or record.get("run_id") != state.get("run_id")
        or record.get("case_id") != state.get("case_id")
        for record in cycle_records
    ):
        raise ValueError("Execution ledger Cycle lifecycle is invalid for the active Run.")
    latest_cycle_id, latest_cycle_index = _validate_execution_index_sequence(
        (
            (record.get("cycle_id"), record.get("cycle_index"))
            for record in cycle_records
        ),
        label="Cycle",
        prefix="cycle",
        width=4,
    )
    cycles_by_id = {str(record["cycle_id"]): record for record in cycle_records}
    for cycle_index in range(1, latest_cycle_index + 1):
        cycle = cycles_by_id[_execution_id("cycle", cycle_index, width=4)]
        expected_parent = (
            _execution_id("cycle", cycle_index - 1, width=4)
            if cycle_index > 1
            else None
        )
        if cycle.get("parent_cycle_id") != expected_parent:
            raise ValueError("Execution ledger Cycle parent chain is inconsistent.")
    latest_cycle = cycles_by_id[str(latest_cycle_id)]
    if any(
        field not in state or state[field] != value
        for field, value in {
            "cycle_id": latest_cycle_id,
            "cycle_index": latest_cycle_index,
            "parent_cycle_id": latest_cycle.get("parent_cycle_id"),
        }.items()
    ):
        raise ValueError("State Cycle identity is not the latest execution ledger head.")

    for transition in (
        record for record in execution_records if record.get("record_type") == "transition"
    ):
        transition_id = transition.get("transition_id")
        target_attempt_id = transition.get("target_attempt_id")
        if target_attempt_id is None:
            if any(
                field not in transition
                for field in (
                    "target_attempt_id",
                    "target_node",
                    "target_cycle_id",
                    "target_attempt_kind",
                )
            ) or transition.get("route") not in {"end", "__end__"} or any(
                transition.get(field) is not None
                for field in ("target_node", "target_cycle_id", "target_attempt_kind")
            ):
                raise ValueError(
                    f"Committed Transition has an invalid terminal target shape: {transition_id}"
                )
        elif any(
            not isinstance(transition.get(field), str) or not transition.get(field)
            for field in ("target_node", "target_cycle_id", "target_attempt_kind")
        ):
            raise ValueError(
                f"Committed Transition has an incomplete target shape: {transition_id}"
            )

    attempt_ids: list[str] = []
    for record in execution_records:
        if record.get("record_type") != "attempt":
            continue
        attempt_id = record.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise ValueError("Execution ledger contains an Attempt without an identity.")
        if attempt_id not in attempt_ids:
            attempt_ids.append(attempt_id)

    ordinary_ids = set(registered_pointers)
    attempt_lifecycles: dict[str, list[dict[str, Any]]] = {}
    for attempt_id in attempt_ids:
        lifecycle = _execution_attempt_lifecycle_records(execution_records, attempt_id)
        attempt_lifecycles[attempt_id] = lifecycle
        provenance = _attempt_provenance_from_lifecycle(lifecycle, attempt_id)
        if provenance["run_id"] != state.get("run_id") or provenance["case_id"] != state.get("case_id"):
            raise ValueError(f"Execution ledger Attempt belongs to another Run: {attempt_id}")
        slot = SLOT_BY_ATTEMPT_KIND.get(str(provenance["attempt_kind"]))
        if slot is None:
            raise ValueError(f"Execution ledger Attempt kind has no artifact slot policy: {attempt_id}")
        artifact_id = f"{attempt_id}:{slot}"
        finished = [record for record in lifecycle if record.get("event") == "finished"]
        if finished:
            output_references = finished[0].get("output_references")
            if not isinstance(output_references, dict):
                raise ValueError(f"Finished Attempt output references are invalid: {attempt_id}")
            current_ids = output_references.get("current_artifact_ids", {})
            if not isinstance(current_ids, dict):
                raise ValueError(f"Finished Attempt current artifact references are invalid: {attempt_id}")
            output_artifact_id = current_ids.get(slot)
            if output_artifact_id is None:
                if artifact_id in ordinary_ids:
                    raise ValueError(f"Registered artifact is missing from producing Attempt output: {artifact_id}")
            elif output_artifact_id != artifact_id or artifact_id not in ordinary_ids:
                raise ValueError(f"Producing Attempt output is missing its registered artifact: {artifact_id}")

        if attempt_id == allow_pending_invalidation_attempt_id:
            continue
        scheduled = lifecycle[0]
        input_references = scheduled.get("input_references")
        if not isinstance(input_references, dict):
            raise ValueError(f"Scheduled Attempt input references are invalid: {attempt_id}")
        current_ids = input_references.get("current_artifact_ids")
        if not isinstance(current_ids, dict):
            raise ValueError(f"Scheduled Attempt current artifact references are invalid: {attempt_id}")
        if any(
            slot_name not in ARTIFACT_SLOTS
            or not isinstance(input_artifact_id, str)
            or input_artifact_id not in ordinary_ids
            for slot_name, input_artifact_id in current_ids.items()
        ):
            raise ValueError(f"Scheduled Attempt references unknown current artifacts: {attempt_id}")
        transition = _committed_transition_record(
            execution_records,
            str(provenance["inbound_transition_id"]),
        )
        if (
            transition.get("run_id") != provenance["run_id"]
            or transition.get("case_id") != provenance["case_id"]
            or transition.get("target_cycle_id") != provenance["cycle_id"]
            or transition.get("target_attempt_id") != attempt_id
            or transition.get("target_attempt_kind") != provenance["attempt_kind"]
            or transition.get("target_node") != provenance["node_name"]
        ):
            raise ValueError(f"Scheduled Attempt does not match its committed Transition: {attempt_id}")
        new_human_request = (
            provenance["attempt_kind"] == "human_gate"
            and _transition_creates_human_request(execution_records, transition)
        )
        policy_slots = _slots_for_target(
            str(provenance["attempt_kind"]),
            new_human_request=new_human_request,
        )
        expected_clears = {
            slot_name: str(current_ids[slot_name])
            for slot_name in policy_slots
            if slot_name in current_ids
        }
        if cleared_by_attempt.get(attempt_id, {}) != expected_clears:
            raise ValueError(f"Artifact history does not contain the exact required invalidation: {attempt_id}")

    latest_attempt_id, latest_attempt_index = _validate_execution_index_sequence(
        (
            (
                attempt_id,
                _attempt_provenance_from_lifecycle(lifecycle, attempt_id)["attempt_index"],
            )
            for attempt_id, lifecycle in attempt_lifecycles.items()
        ),
        label="Attempt",
        prefix="attempt",
    )
    if latest_attempt_id is None:
        raise ValueError("Execution ledger does not contain an Attempt head.")
    for attempt_id, lifecycle in attempt_lifecycles.items():
        provenance = _attempt_provenance_from_lifecycle(lifecycle, attempt_id)
        parent_attempt_id = provenance["parent_attempt_id"]
        if parent_attempt_id is None:
            if provenance["attempt_index"] != 1:
                raise ValueError("Execution ledger Attempt parent chain is incomplete.")
            continue
        parent = attempt_lifecycles.get(str(parent_attempt_id))
        if parent is None or _attempt_provenance_from_lifecycle(
            parent,
            str(parent_attempt_id),
        )["attempt_index"] >= provenance["attempt_index"]:
            raise ValueError("Execution ledger Attempt parent chain is inconsistent.")

    transition_records = [
        record for record in execution_records if record.get("record_type") == "transition"
    ]
    if any(
        transition.get("event") != "committed"
        or transition.get("status") != "committed"
        or transition.get("run_id") != state.get("run_id")
        or transition.get("case_id") != state.get("case_id")
        for transition in transition_records
    ):
        raise ValueError("Execution ledger Transition lifecycle is invalid for the active Run.")
    latest_transition_id, latest_transition_index = _validate_execution_index_sequence(
        (
            (record.get("transition_id"), record.get("transition_index"))
            for record in transition_records
        ),
        label="Transition",
        prefix="transition",
    )
    transitions_by_id = {
        str(transition["transition_id"]): transition for transition in transition_records
    }
    for transition in transition_records:
        transition_id = transition.get("transition_id")
        target_attempt_id = transition.get("target_attempt_id")
        if target_attempt_id is None:
            if transition.get("route") not in {"end", "__end__"} or any(
                transition.get(field) is not None
                for field in ("target_node", "target_cycle_id", "target_attempt_kind")
            ):
                raise ValueError(
                    f"Committed Transition has an invalid terminal target shape: {transition_id}"
                )
            continue
        if (
            not isinstance(target_attempt_id, str)
            or target_attempt_id not in attempt_lifecycles
            or any(
                not isinstance(transition.get(field), str) or not transition.get(field)
                for field in ("target_node", "target_cycle_id", "target_attempt_kind")
            )
        ):
            raise ValueError(f"Committed Transition target Attempt is missing: {transition_id}")
        provenance = _attempt_provenance_from_lifecycle(
            attempt_lifecycles[target_attempt_id],
            target_attempt_id,
        )
        if (
            provenance["inbound_transition_id"] != transition_id
            or provenance["run_id"] != transition.get("run_id")
            or provenance["case_id"] != transition.get("case_id")
            or provenance["cycle_id"] != transition.get("target_cycle_id")
            or provenance["attempt_kind"] != transition.get("target_attempt_kind")
            or provenance["node_name"] != transition.get("target_node")
        ):
            raise ValueError(f"Committed Transition target Attempt identity is inconsistent: {transition_id}")

    latest_attempt_lifecycle = attempt_lifecycles[latest_attempt_id]
    latest_attempt = _attempt_provenance_from_lifecycle(
        latest_attempt_lifecycle,
        latest_attempt_id,
    )
    expected_attempt_state = {
        "cycle_id": latest_attempt["cycle_id"],
        "cycle_index": latest_attempt["cycle_index"],
        "attempt_id": latest_attempt_id,
        "attempt_index": latest_attempt_index,
        "parent_attempt_id": latest_attempt["parent_attempt_id"],
        "attempt_kind": latest_attempt["attempt_kind"],
        "attempt_node": latest_attempt["node_name"],
        "attempt_trigger": latest_attempt["attempt_trigger"],
        "attempt_status": latest_attempt_lifecycle[-1].get("status"),
        "inbound_transition_id": latest_attempt["inbound_transition_id"],
    }
    if any(
        field not in state or state[field] != value
        for field, value in expected_attempt_state.items()
    ):
        raise ValueError("State Attempt identity is not the latest execution ledger head.")

    latest_transition = (
        transitions_by_id[str(latest_transition_id)]
        if latest_transition_id is not None
        else None
    )
    expected_transition_state = {
        "transition_index": latest_transition_index,
        "committed_transition_id": latest_transition_id,
        "committed_route": latest_transition.get("route") if latest_transition else None,
    }
    if any(
        field not in state or state[field] != value
        for field, value in expected_transition_state.items()
    ):
        raise ValueError("State Transition identity is not the latest execution ledger head.")

    request_ids: list[str] = []
    for record in execution_records:
        if record.get("record_type") != "human_request":
            continue
        request_id = record.get("human_request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("Execution ledger contains a Human Request without an identity.")
        if request_id not in request_ids:
            request_ids.append(request_id)
    request_lifecycles = {
        request_id: _human_request_lifecycle_records(execution_records, request_id)
        for request_id in request_ids
    }
    latest_request_id, latest_request_index = _validate_execution_index_sequence(
        (
            (request_id, lifecycle[0].get("request_index"))
            for request_id, lifecycle in request_lifecycles.items()
        ),
        label="Human Request",
        prefix="human_request",
    )
    for request_id, lifecycle in request_lifecycles.items():
        request = lifecycle[0]
        if (
            request.get("run_id") != state.get("run_id")
            or request.get("case_id") != state.get("case_id")
            or request.get("cycle_id") not in cycles_by_id
            or request.get("requesting_attempt_id") not in attempt_lifecycles
        ):
            raise ValueError(f"Human Request belongs to an unknown execution identity: {request_id}")
    if latest_request_id is None:
        expected_request_state = {
            "human_request_index": 0,
            "active_human_request_id": None,
            "human_requesting_attempt_id": None,
            "human_request_kind": None,
            "human_request_status": None,
            "human_request_authorization_scope": None,
        }
    else:
        latest_request_lifecycle = request_lifecycles[latest_request_id]
        latest_request = latest_request_lifecycle[0]
        expected_request_state = {
            "human_request_index": latest_request_index,
            "active_human_request_id": latest_request_id,
            "human_requesting_attempt_id": latest_request.get("requesting_attempt_id"),
            "human_request_kind": latest_request.get("request_kind"),
            "human_request_status": latest_request_lifecycle[-1].get("status"),
            "human_request_authorization_scope": latest_request.get("authorization_scope"),
        }
    if any(
        field not in state or state[field] != value
        for field, value in expected_request_state.items()
    ):
        raise ValueError("State Human Request identity is not the latest execution ledger head.")

    response_ids: list[str] = []
    for record in execution_records:
        if record.get("record_type") != "human_response":
            continue
        response_id = record.get("human_response_id")
        if not isinstance(response_id, str) or not response_id:
            raise ValueError("Execution ledger contains a Human Response without an identity.")
        if response_id not in response_ids:
            response_ids.append(response_id)
    response_lifecycles = {
        response_id: _human_response_lifecycle_records(execution_records, response_id)
        for response_id in response_ids
    }
    _, latest_response_index = _validate_execution_index_sequence(
        (
            (response_id, lifecycle[0].get("response_index"))
            for response_id, lifecycle in response_lifecycles.items()
        ),
        label="Human Response",
        prefix="human_response",
    )
    for response_id, lifecycle in response_lifecycles.items():
        response = lifecycle[0]
        request = request_lifecycles.get(str(response.get("human_request_id")))
        if (
            response.get("run_id") != state.get("run_id")
            or response.get("case_id") != state.get("case_id")
            or request is None
            or response.get("cycle_id") != request[0].get("cycle_id")
        ):
            raise ValueError(f"Human Response belongs to an unknown execution identity: {response_id}")

    latest_request_responses = [
        (response_id, lifecycle)
        for response_id, lifecycle in response_lifecycles.items()
        if lifecycle[0].get("human_request_id") == latest_request_id
    ]
    latest_active_response = (
        max(
            latest_request_responses,
            key=lambda item: int(item[1][0]["response_index"]),
        )
        if latest_request_responses
        else None
    )
    active_response_id = state.get("active_human_response_id")
    if active_response_id == allow_pending_human_response_id and active_response_id is not None:
        expected_pending_state = {
            "human_response_index": latest_response_index + 1,
            "active_human_response_id": _execution_id(
                "human_response",
                latest_response_index + 1,
            ),
            "human_response_status": "submitted",
            "human_response_decision": None,
            "human_response_authorized_route": None,
            "human_response_authorized_transition_route": None,
            "human_response_authorized_transition_target": None,
            "human_response_validator_attempt_id": None,
            "human_response_consumer_attempt_id": None,
            "human_response_target_attempt_id": None,
        }
        if (
            latest_request_id is None
            or state.get("human_request_status") != "open"
            or any(
                field not in state or state[field] != value
                for field, value in expected_pending_state.items()
            )
            ):
                raise ValueError("Pending Human Response preflight identity is invalid.")
    else:
        if latest_active_response is None and active_response_id is not None:
            raise ValueError("State active Human Response is missing from the execution ledger.")
        if state.get("human_response_index") != latest_response_index:
            raise ValueError("State Human Response counter is not the latest execution ledger head.")
        if latest_active_response is None:
            expected_response_state = {
                "active_human_response_id": None,
                "human_response_status": None,
                "human_response_decision": None,
                "human_response_authorized_route": None,
                "human_response_authorized_transition_route": None,
                "human_response_authorized_transition_target": None,
                "human_response_validator_attempt_id": None,
                "human_response_consumer_attempt_id": None,
                "human_response_target_attempt_id": None,
            }
        else:
            latest_active_response_id, active_lifecycle = latest_active_response
            latest = active_lifecycle[-1]
            expected_response_state = {
                "active_human_response_id": latest_active_response_id,
                "human_response_status": latest.get("status"),
                "human_response_decision": latest.get("decision"),
                "human_response_authorized_route": latest.get("authorized_route"),
                "human_response_authorized_transition_route": latest.get(
                    "authorized_transition_route"
                ),
                "human_response_authorized_transition_target": latest.get(
                    "authorized_transition_target"
                ),
                "human_response_validator_attempt_id": latest.get("validator_attempt_id"),
                "human_response_consumer_attempt_id": latest.get("consumer_attempt_id"),
                "human_response_target_attempt_id": latest.get("authorized_target_attempt_id"),
            }
        if any(
            field not in state or state[field] != value
            for field, value in expected_response_state.items()
        ):
            raise ValueError("State Human Response identity is not the latest request response head.")

    expected_human_protections = {
        (f"{response_id}:payload", "human_response")
        for response_id in response_lifecycles
    }
    actual_human_protections = {
        key for key in protected_keys if key[1] == "human_response"
    }
    if actual_human_protections != expected_human_protections:
        raise ValueError("Artifact history does not exactly cover submitted Human Response snapshots.")

    expected_accepted_protections = {
        (artifact_id, "accepted_result")
        for artifact_id, pointer in registered_pointers.items()
        if pointer.get("slot") == "terminal" and pointer.get("status") == "accepted"
    }
    if allow_pending_accepted_protection_artifact_id is not None:
        expected_accepted_protections.discard(
            (allow_pending_accepted_protection_artifact_id, "accepted_result")
        )
    actual_accepted_protections = {
        key for key in protected_keys if key[1] == "accepted_result"
    }
    if actual_accepted_protections != expected_accepted_protections:
        raise ValueError("Artifact history does not exactly cover accepted terminal artifacts.")


def _validate_history(
    state: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    allow_pending_invalidation_attempt_id: str | None = None,
    allow_pending_accepted_protection_artifact_id: str | None = None,
    allow_pending_human_response_id: str | None = None,
) -> tuple[set[str], dict[str, dict[str, Any] | None]]:
    run_root = _run_root(state)
    registered_ids: set[str] = set()
    registered_pointers: dict[str, dict[str, Any]] = {}
    current_set_ids: set[str] = set()
    protected_keys: set[tuple[str, str]] = set()
    cleared_by_attempt: dict[str, dict[str, str]] = {}
    pending_current_set: str | None = None
    replayed_current: dict[str, dict[str, Any] | None] = {
        slot: None for slot in ARTIFACT_SLOTS
    }
    for expected_index, record in enumerate(records, 1):
        if record.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("Artifact history schema_version is unsupported.")
        if record.get("event_index") != expected_index or record.get("event_id") != _event_id(expected_index):
            raise ValueError("Artifact history event sequence is inconsistent.")
        if record.get("run_id") != state.get("run_id") or record.get("case_id") != state.get("case_id"):
            raise ValueError("Artifact history identity does not match the active Run.")
        event = record.get("event")
        if event not in {"registered", "current_set", "current_cleared", "protected_snapshot_registered"}:
            raise ValueError(f"Artifact history contains an unknown event: {event}")
        slot = record.get("slot")
        if slot is not None and slot not in ARTIFACT_SLOTS:
            raise ValueError(f"Artifact history contains an unknown slot: {slot}")
        artifact_id = record.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError("Artifact history record is missing artifact_id.")
        if pending_current_set is not None and (
            event != "current_set" or artifact_id != pending_current_set
        ):
            raise ValueError("Registered artifact must be followed immediately by its current_set event.")
        if event == "registered":
            if artifact_id in registered_ids:
                raise ValueError(f"Artifact history registers an artifact twice: {artifact_id}")
            pointer = _validate_registered_pointer(state, record)
            dependencies = pointer["dependencies"]
            base_dependencies = _dependency_ids_from_current(
                replayed_current, str(slot), schema_version=state.get("schema_version")
            )
            extra_dependencies = dependencies[len(base_dependencies) :]
            if (
                dependencies[: len(base_dependencies)] != base_dependencies
                or len(dependencies) != len(set(dependencies))
                or any(dependency not in registered_ids for dependency in extra_dependencies)
            ):
                raise ValueError("Registered artifact dependencies do not match replayed current history.")
            registered_ids.add(artifact_id)
            registered_pointers[artifact_id] = pointer
            pending_current_set = artifact_id
        elif event == "protected_snapshot_registered" and record.get("protected_kind") == "human_response":
            if artifact_id in registered_ids:
                raise ValueError(f"Artifact history registers a protected payload twice: {artifact_id}")
            _validate_human_response_snapshot(state, record)
            registered_ids.add(artifact_id)
        elif artifact_id not in registered_ids:
            raise ValueError(f"Artifact history references an unregistered artifact: {artifact_id}")
        if event == "current_set":
            pointer = registered_pointers.get(artifact_id)
            if pointer is None or pointer.get("slot") != slot:
                raise ValueError("Artifact current_set does not match its registered pointer.")
            if artifact_id in current_set_ids:
                raise ValueError("Artifact current_set can occur only once after registration.")
            if replayed_current[slot] is not None:
                raise ValueError(f"Artifact current_set would overwrite occupied slot {slot}.")
            if (
                record.get("reason_code") != "attempt_output_current"
                or record.get("cycle_id") != pointer["cycle_id"]
                or record.get("attempt_id") != pointer["attempt_id"]
                or record.get("dependencies") != pointer["dependencies"]
                or record.get("status") != pointer["status"]
            ):
                raise ValueError("Artifact current_set metadata does not match its registered pointer.")
            replayed_current[slot] = deepcopy(pointer)
            current_set_ids.add(artifact_id)
            pending_current_set = None
        elif event == "current_cleared":
            pointer = replayed_current.get(str(slot))
            if not isinstance(pointer, dict) or pointer.get("artifact_id") != artifact_id:
                raise ValueError("Artifact current_cleared does not match the replayed current slot.")
            if record.get("prior_artifact_id") != artifact_id:
                raise ValueError("Artifact current_cleared prior artifact is inconsistent.")
            target_attempt_id = record.get("target_attempt_id")
            if not isinstance(target_attempt_id, str) or record.get("attempt_id") != target_attempt_id:
                raise ValueError("Artifact current_cleared target Attempt identity is inconsistent.")
            provenance = _execution_attempt_provenance(state, target_attempt_id)
            transition_id = record.get("transition_id")
            if not isinstance(transition_id, str) or not transition_id:
                raise ValueError("Artifact current_cleared is missing its triggering Transition.")
            transition = _execution_transition_provenance(state, transition_id)
            allowed_slots = _slots_for_target(
                str(provenance["attempt_kind"]),
                new_human_request=provenance["attempt_kind"] == "human_gate",
            )
            if (
                provenance["run_id"] != state.get("run_id")
                or provenance["case_id"] != state.get("case_id")
                or record.get("cycle_id") != provenance["cycle_id"]
                or transition_id != provenance["inbound_transition_id"]
                or record.get("reason_code") != f"target_{provenance['attempt_kind']}"
                or slot not in allowed_slots
                or transition.get("run_id") != provenance["run_id"]
                or transition.get("case_id") != provenance["case_id"]
                or transition.get("target_cycle_id") != provenance["cycle_id"]
                or transition.get("target_attempt_id") != target_attempt_id
                or transition.get("target_attempt_kind") != provenance["attempt_kind"]
                or transition.get("target_node") != provenance["node_name"]
            ):
                raise ValueError("Artifact current_cleared does not match its target Attempt provenance.")
            attempt_clears = cleared_by_attempt.setdefault(target_attempt_id, {})
            if str(slot) in attempt_clears:
                raise ValueError("Artifact current_cleared repeats a slot for the same target Attempt.")
            attempt_clears[str(slot)] = artifact_id
            replayed_current[str(slot)] = None
        elif event == "protected_snapshot_registered":
            protected_kind = record.get("protected_kind")
            if protected_kind not in {"human_response", "accepted_result"}:
                raise ValueError(f"Artifact history contains an unknown protected kind: {protected_kind}")
            protected_key = (artifact_id, protected_kind)
            if protected_key in protected_keys:
                raise ValueError(f"Artifact protection is registered twice: {artifact_id} {protected_kind}")
            protected_keys.add(protected_key)
            if protected_kind == "human_response":
                if slot is not None:
                    raise ValueError("Human Response snapshots cannot occupy an artifact slot.")
            else:
                pointer = registered_pointers.get(artifact_id)
                current_pointer = replayed_current.get("terminal")
                if (
                    slot != "terminal"
                    or pointer is None
                    or pointer.get("slot") != slot
                    or not isinstance(current_pointer, dict)
                    or current_pointer.get("artifact_id") != artifact_id
                    or pointer.get("status") != "accepted"
                    or record.get("cycle_id") != pointer.get("cycle_id")
                    or record.get("attempt_id") != pointer.get("attempt_id")
                    or record.get("reason_code") != "protected_accepted_result"
                ):
                    raise ValueError("Accepted-result protection does not match a registered pointer.")
                if record.get("members") != pointer["members"] or record.get("dependencies") != pointer["dependencies"]:
                    raise ValueError("Accepted-result protection metadata is inconsistent.")
        if event not in {"registered", "protected_snapshot_registered"}:
            continue
        members = record.get("members")
        if not isinstance(members, list) or not members:
            raise ValueError(f"Artifact history member list is invalid: {artifact_id}")
        for member in members:
            if not isinstance(member, dict):
                raise ValueError(f"Artifact history member is not an object: {artifact_id}")
            relative = Path(str(member.get("canonical_path", "")))
            path = (run_root / relative).resolve()
            if relative.is_absolute() or not _is_within(path, run_root) or not path.is_file():
                raise ValueError(f"Artifact history member path is invalid: {relative}")
            if _sha256_file(path) != member.get("sha256") or path.stat().st_size != member.get("size_bytes"):
                raise ValueError(f"Artifact history member digest changed: {path}")
    if pending_current_set is not None:
        raise ValueError("Artifact history ends before a registered artifact becomes current.")
    _validate_reverse_history_completeness(
        state,
        registered_pointers,
        cleared_by_attempt,
        protected_keys,
        allow_pending_invalidation_attempt_id=allow_pending_invalidation_attempt_id,
        allow_pending_accepted_protection_artifact_id=(
            allow_pending_accepted_protection_artifact_id
        ),
        allow_pending_human_response_id=allow_pending_human_response_id,
    )
    return registered_ids, replayed_current


def _read_index(state: dict[str, Any]) -> dict[str, Any]:
    path = _index_path(state)
    if not path.exists():
        raise ValueError(f"Artifact index is missing: {path}")
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_object_keys,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"Artifact index is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Artifact index is not an object: {path}")
    if payload.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ValueError("Artifact index schema_version is unsupported.")
    for field in ("run_id", "case_id"):
        if payload.get(field) != state.get(field):
            raise ValueError(f"Artifact index {field} does not match the active Run.")
    current = payload.get("current")
    if not isinstance(current, dict) or set(current) != set(ARTIFACT_SLOTS):
        raise ValueError("Artifact index current slots do not match the canonical registry.")
    managed = payload.get("managed_projections")
    if not isinstance(managed, dict):
        raise ValueError("Artifact index managed_projections must be an object.")
    return payload


def _validate_registry_head(
    state: dict[str, Any],
    *,
    allow_pending_invalidation_attempt_id: str | None = None,
    allow_pending_accepted_protection_artifact_id: str | None = None,
    allow_pending_human_response_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    index = _read_index(state)
    history = _read_history(_history_path(state))
    registered_ids, replayed_current = _validate_history(
        state,
        history,
        allow_pending_invalidation_attempt_id=allow_pending_invalidation_attempt_id,
        allow_pending_accepted_protection_artifact_id=(
            allow_pending_accepted_protection_artifact_id
        ),
        allow_pending_human_response_id=allow_pending_human_response_id,
    )
    latest_id = history[-1].get("event_id") if history else None
    latest_index = int(history[-1].get("event_index", 0)) if history else 0
    if index.get("last_event_id") != latest_id or int(index.get("revision", -1)) != latest_index:
        raise ValueError("Artifact history and current index heads do not match.")
    if int(state.get("artifact_event_index", -1)) != latest_index:
        raise ValueError("Artifact event counter is not the current registry head.")
    if index["current"] != replayed_current:
        raise ValueError("Artifact index current pointers do not match replayed artifact history.")
    expected_projections: dict[str, str] = {}
    for pointer in replayed_current.values():
        if not isinstance(pointer, dict):
            continue
        artifact_id = str(pointer["artifact_id"])
        for member in pointer["members"]:
            projection = member.get("projection_path")
            if not isinstance(projection, str) or not projection:
                raise ValueError("Current artifact member has an invalid projection path.")
            _projection_target(_run_root(state), projection)
            if projection in expected_projections:
                raise ValueError(f"Current artifacts publish the same projection twice: {projection}")
            expected_projections[projection] = artifact_id
    managed = index["managed_projections"]
    for projection, owner in managed.items():
        if not isinstance(projection, str) or not projection or not isinstance(owner, str):
            raise ValueError("Artifact index contains an invalid managed projection entry.")
        _projection_target(_run_root(state), projection)
        if owner not in registered_ids:
            raise ValueError(f"Artifact index projection owner is not registered: {owner}")
    if managed != expected_projections:
        raise ValueError("Artifact index managed projections do not match replayed current artifacts.")
    for slot, pointer in index["current"].items():
        if pointer is None:
            continue
        if not isinstance(pointer, dict) or pointer.get("slot") != slot:
            raise ValueError(f"Artifact index pointer is invalid for slot {slot}.")
        if pointer.get("artifact_id") not in registered_ids:
            raise ValueError(f"Artifact index references an unregistered artifact in slot {slot}.")
        dependencies = pointer.get("dependencies")
        if not isinstance(dependencies, list) or any(value not in registered_ids for value in dependencies):
            raise ValueError(f"Artifact index dependencies are invalid for slot {slot}.")
    return index, history


def _code_scalar_projection(state: dict[str, Any], index: dict[str, Any], *, run_root=None) -> dict[str, Any]:
    if state.get("schema_version") != "0.4":
        return {}
    pointer = index["current"].get("code")
    if not isinstance(pointer, dict) or pointer.get("attempt_kind") != "code_agent":
        return {"code_agent_status": None, "code_agent_usable": None}
    from lqcd_agent.code_agent.artifacts import validate_code_result
    from lqcd_agent.code_agent.schemas import validate_task
    from lqcd_agent.control.coordinator import read_regular
    attempt_root = (Path(run_root) if run_root is not None else _run_root(state)) / "attempts" / pointer["attempt_id"]
    task = validate_task(read_regular(attempt_root / "code_agent_task.json")).value
    result = validate_code_result(read_regular(attempt_root / "code_agent_result.json"), task).value
    if result["status"] != pointer["status"]:
        raise ValueError("Canonical Code scalar status differs from pointer.")
    return {"code_agent_status": result["status"], "code_agent_usable": result["usable"]}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _assert_no_symlink(path: Path, root: Path) -> None:
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError(f"Artifact member cannot traverse a symlink: {path}")
        current = current.parent


def _member_records(state: dict[str, Any], member_paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    run_root = _run_root(state)
    attempt_root = attempt_output_dir(state).resolve()
    files: set[Path] = set()
    for value in member_paths:
        candidate = Path(value)
        if not candidate.exists():
            raise ValueError(f"Artifact member does not exist: {candidate}")
        if candidate.is_symlink():
            raise ValueError(f"Artifact member cannot be a symlink: {candidate}")
        if candidate.is_dir():
            files.update(path for path in candidate.rglob("*") if path.is_file())
        elif candidate.is_file():
            files.add(candidate)
        else:
            raise ValueError(f"Artifact member is not a regular file or directory: {candidate}")
    if not files:
        raise ValueError("Artifact bundle must contain at least one file.")

    records: list[dict[str, Any]] = []
    for path in sorted(files):
        resolved = path.resolve()
        if not _is_within(resolved, attempt_root):
            raise ValueError(f"Artifact member escapes the active Attempt directory: {path}")
        _assert_no_symlink(path, attempt_root)
        canonical = resolved.relative_to(run_root)
        projection = resolved.relative_to(attempt_root)
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        records.append(
            {
                "logical_name": projection.as_posix(),
                "canonical_path": canonical.as_posix(),
                "projection_path": projection.as_posix(),
                "sha256": _sha256_file(resolved),
                "size_bytes": resolved.stat().st_size,
                "media_type": mime_type,
            }
        )
    return records


def _registered_artifact_ids(history: list[dict[str, Any]]) -> set[str]:
    return {
        str(record["artifact_id"])
        for record in history
        if record.get("event") in {"registered", "protected_snapshot_registered"}
    }


def _dependency_ids_from_current(
    current: dict[str, dict[str, Any] | None],
    slot: str,
    *,
    schema_version: str | None = None,
) -> list[str]:
    if slot == "plan":
        dependency_slots: tuple[str, ...] = ()
    elif slot == "code":
        dependency_slots = ("plan",)
    elif slot == "analysis":
        dependency_slots = ("plan", "code")
    elif slot == "review":
        dependency_slots = ("analysis",)
    else:
        dependency_slots = ARTIFACT_SLOTS[: ARTIFACT_SLOTS.index(slot)]
    dependencies = [
        str(current[name]["artifact_id"])
        for name in dependency_slots
        if isinstance(current.get(name), dict)
    ]
    required = {
        "code": ("plan",),
        "analysis": ("plan",),
        "review": ("analysis",),
        "decision": ("plan", "analysis"),
        "approval": ("decision",),
        "terminal": ("decision",),
    }.get(slot, ())
    if slot == "decision" and schema_version == "0.4" and current.get("review") is None:
        required = ("plan",)
    missing = [name for name in required if not isinstance(current.get(name), dict)]
    if missing:
        raise ValueError(f"Artifact slot {slot} is missing current dependencies: {missing}")
    return dependencies


def _dependency_ids(index: dict[str, Any], slot: str, *, schema_version: str | None = None) -> list[str]:
    return _dependency_ids_from_current(index["current"], slot, schema_version=schema_version)


def _projection_target(run_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Compatibility projection path is not Run-relative: {relative_path}")
    target = (run_root / relative_path).resolve()
    if not _is_within(target, run_root) or target == run_root:
        raise ValueError(f"Compatibility projection escapes the Run root: {relative_path}")
    normalized = target.relative_to(run_root).as_posix()
    if normalized in {
        "artifact_history.jsonl",
        "artifact_index.json",
        "execution_history.jsonl",
        "graph_state.json",
    }:
        raise ValueError(f"Compatibility projection targets a protected control path: {relative_path}")
    protected_roots = {
        "attempts",
        "human_responses",
        "checkpoints",
        "context",
        "raw_data",
        "accepted_results",
    }
    if Path(normalized).parts[0] in protected_roots:
        raise ValueError(f"Compatibility projection targets a protected control path: {relative_path}")
    return target


def preflight_control_registration(
    state: dict[str, Any], *, slot: str, member_paths: Iterable[str | Path],
    state_paths: dict[str, str | None], status: str, created_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read-only A03 preflight for the fenced 0.4 publication adapter.

    The caller owns the execution/artifact cross-head envelope, exact-byte
    publication and checkpoint. Slot, namespace and dependency rules stay A03.
    """
    _assert_active_attempt(state)
    if slot not in ARTIFACT_SLOTS or SLOT_BY_ATTEMPT_KIND.get(str(state.get("attempt_kind"))) != slot:
        raise ValueError("Control registration does not match the producing Attempt slot.")
    index, history = _validate_registry_head(state)
    artifact_id = f"{state['attempt_id']}:{slot}"
    if index["current"][slot] is not None or artifact_id in _registered_artifact_ids(history):
        raise ValueError("Control registration would overwrite an allocated artifact.")
    if set(state_paths) != set(state_fields_for_slot(slot, state.get("schema_version"))):
        raise ValueError("Control registration has incomplete state paths.")
    members = _member_records(state, member_paths)
    dependencies = _dependency_ids(index, slot, schema_version=state.get("schema_version"))
    pointer = {"artifact_id": artifact_id, "slot": slot, "cycle_id": state["cycle_id"],
               "attempt_id": state["attempt_id"], "attempt_kind": state["attempt_kind"], "status": status,
               "dependencies": dependencies, "members": members, "state_paths": dict(state_paths)}
    records = []

    def event(name: str, reason: str, **fields: Any) -> dict[str, Any]:
        position = int(index["revision"]) + len(records) + 1
        row = {"schema_version": ARTIFACT_SCHEMA_VERSION, "event_id": _event_id(position),
               "event_index": position, "event": name, "run_id": state["run_id"], "case_id": state["case_id"],
               "cycle_id": state["cycle_id"], "attempt_id": state["attempt_id"], "transition_id": None,
               "human_request_id": state.get("active_human_request_id"), "human_response_id": state.get("active_human_response_id"),
               "slot": slot, "artifact_id": artifact_id, "reason_code": reason, "created_at": created_at, **fields}
        records.append(row)
        return row

    registered = event("registered", "attempt_output_registered",
                       canonical_root=attempt_output_dir(state).resolve().relative_to(_run_root(state)).as_posix(),
                       members=members, dependencies=dependencies, status=status, pointer=deepcopy(pointer),
                       node_name=state.get("attempt_node"))
    _validate_registered_pointer(state, registered)
    event("current_set", "attempt_output_current", dependencies=dependencies, status=status)
    if slot == "terminal" and status == "accepted":
        event("protected_snapshot_registered", "protected_accepted_result", protected_kind="accepted_result",
              members=members, dependencies=dependencies)
    index["current"][slot] = pointer
    for member in members:
        projection = member["projection_path"]
        _projection_target(_run_root(state), projection)
        if projection in index["managed_projections"]:
            raise ValueError("Control registration conflicts with a managed projection.")
        index["managed_projections"][projection] = artifact_id
    index.update(revision=records[-1]["event_index"], last_event_id=records[-1]["event_id"])
    return index, records


def _slots_for_target(target_attempt_kind: str, *, new_human_request: bool) -> tuple[str, ...]:
    if target_attempt_kind == "human_gate":
        return ("approval", "terminal") if new_human_request else ()
    try:
        return tuple(INVALIDATED_SLOTS_BY_TARGET_KIND[target_attempt_kind])
    except KeyError as exc:
        raise ValueError(f"Unsupported invalidation target kind: {target_attempt_kind}") from exc


def validate_state_artifacts(state: dict[str, Any]) -> None:
    index, _ = _validate_registry_head(state)
    if state.get("artifact_history_path") != str(_history_path(state)):
        raise ValueError("State artifact_history_path does not match the active Run.")
    if state.get("artifact_index_path") != str(_index_path(state)):
        raise ValueError("State artifact_index_path does not match the active Run.")
    if state.get("current_artifacts") != index["current"]:
        raise ValueError("State current_artifacts does not match artifact_index.json.")
    run_root = _run_root(state)
    for slot in STATE_FIELDS_BY_SLOT:
        fields = state_fields_for_slot(slot, state.get("schema_version"))
        pointer = index["current"].get(slot)
        expected_paths = pointer.get("state_paths", {}) if isinstance(pointer, dict) else {}
        for field in fields:
            if state.get(field) != expected_paths.get(field):
                raise ValueError(f"State field {field} does not match current artifact slot {slot}.")
        if slot == "code" and state.get("schema_version") == "0.4":
            for field, value in _code_scalar_projection(state, index).items():
                if state.get(field) != value:
                    raise ValueError(f"State field {field} does not match current Code result.")
        if not isinstance(pointer, dict):
            continue
        for member in pointer["members"]:
            path = run_root / str(member["canonical_path"])
            if not path.is_file() or _sha256_file(path) != member["sha256"]:
                raise ValueError(f"Current artifact member is missing or changed: {path}")
            projection = str(member.get("projection_path") or "")
            if index["managed_projections"].get(projection) != pointer["artifact_id"]:
                raise ValueError(f"Current artifact projection ownership is invalid: {projection}")
            projection_path = _projection_target(run_root, projection)
            if not projection_path.is_file():
                raise ValueError(f"Current artifact projection is missing: {projection_path}")
            if projection in {"code_change_summary.md", "tests_status.json"} or projection.endswith(
                "/07_human_decision.yaml"
            ):
                continue
            if _sha256_file(projection_path) != member["sha256"]:
                raise ValueError(f"Current artifact projection changed: {projection_path}")
