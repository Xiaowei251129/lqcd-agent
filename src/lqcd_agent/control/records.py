"""Closed Execution 0.4 records, reusing A02 identity formats and node mapping.

Sources: A02 sections 2--7, A04 Run Lifecycle, A02C01 bootstrap and A06
Execution Ledger and Event Identity. Builders are pure, not write authority.
"""
from dataclasses import asdict

from lqcd_agent.artifacts.registry import ARTIFACT_SLOTS, STATE_FIELDS_BY_SLOT, CODE_STATE_PATH_FIELDS
from lqcd_agent.graph.state import (canonical_attempt_kind, stable_attempt_id, stable_cycle_id,
                                  stable_human_request_id, stable_human_response_id, stable_transition_id,
                                  stable_checkpoint_thread_id)

from .budget import validate_budget_payload
from .clock import Timestamp
from .protocol import PROTOCOL
from .pause import FIELDS as PAUSE_FIELDS, validate_pause_record
from .strict_json import (ValidatedValue, closed, digest_value, loads,
                          number, require, text)


SOURCE_LOCATORS = {
    "identities": "A02_RUN_CYCLE_ATTEMPT_MODEL.md#2-canonical-identity-formats",
    "records": "A02_RUN_CYCLE_ATTEMPT_MODEL.md#4-append-only-execution-ledger",
    "transition": "A02_RUN_CYCLE_ATTEMPT_MODEL.md#6-source-wrapper-transition-commit",
    "human": "A02_RUN_CYCLE_ATTEMPT_MODEL.md#7-human-request--response-identity",
    "run_lifecycle": "A04_PAUSE_RESUME_SEMANTICS.md#append-only-run-lifecycle-authority",
    "bootstrap": "A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md",
}

COMMON = ("schema_version", "record_type", "event", "run_id", "case_id", "event_id", "event_index",
          "previous_execution_head", "artifact_head", "artifact_event_index", "created_at")
FIELDS = {
    "run": ("parent_run_id", "creation_reason", "root_goal_reference", "input_snapshot_reference",
            "canonical_output_root", "checkpoint_thread_id", "status", "policy_version", "policy_digest"),
    "cycle": ("cycle_id", "cycle_index", "parent_cycle_id", "trigger_reason", "created_by_attempt_id", "status"),
    "attempt": ("cycle_id", "cycle_index", "attempt_id", "attempt_index", "parent_attempt_id", "attempt_kind",
                "node_name", "attempt_trigger", "inbound_transition_id", "status", "input_references",
                "output_references", "error"),
    "transition": ("transition_id", "transition_index", "source", "source_node", "source_cycle_id",
                   "source_attempt_id", "route", "target_node", "target_cycle_id", "target_attempt_id",
                   "target_attempt_kind", "human_request_id", "human_response_id", "trigger_reason", "reason",
                   "fields", "evidence_references", "applied_state_update_keys", "applied_state_updates_sha256",
                   "status", "committed_at"),
    "human_request": ("cycle_id", "human_request_id", "request_index", "request_kind", "requesting_attempt_id",
                      "authorization_scope", "packet_reference", "status"),
    "human_response": ("cycle_id", "human_request_id", "human_response_id", "response_index", "payload_reference",
                       "payload_sha256", "validator_attempt_id", "consumer_attempt_id", "authorized_target_attempt_id",
                       "decision", "authorized_route", "authorized_transition_route", "authorized_transition_target",
                       "status"),
    "run_lifecycle": ("from_status", "to_status", "reason_code", "operation_id", "attempt_id", "pause_id", "budget_event_id"),
    "budget": ("budget_event_id", "budget_event_index", "policy_version", "policy_digest", "payload"),
    "pause": PAUSE_FIELDS,
    "lineage": ("creation_reason", "parent_operation_id", "source_snapshot_proof", "lineage_snapshot_digest",
                "source_runtime_fingerprint", "target_runtime_fingerprint"),
}
RESPONSE_EXTRA = {"submitted": ("submitted_payload_reference", "payload_snapshot"),
                  "validated": ("error",), "invalid": ("error",), "consumed": ()}
IDENTITIES = {"cycle": ("cycle_id", "cycle_index", stable_cycle_id),
              "attempt": ("attempt_id", "attempt_index", stable_attempt_id),
              "transition": ("transition_id", "transition_index", stable_transition_id),
              "human_request": ("human_request_id", "request_index", stable_human_request_id),
              "human_response": ("human_response_id", "response_index", stable_human_response_id)}


def _timestamp(value):
    closed(value, ("source", "wall_seconds", "monotonic_seconds"))
    return Timestamp(**value)


def validate_record(record):
    require(type(record) is dict, "Record is not an object")
    kind, event = record.get("record_type"), record.get("event")
    require(type(kind) is str and kind in FIELDS, "Unknown record union variant")
    text(event)
    extra = ()
    if kind == "human_response":
        require(event in RESPONSE_EXTRA, "Unknown Human Response event")
        extra = RESPONSE_EXTRA[event]
    closed(record, COMMON + FIELDS[kind] + extra)
    require(record["schema_version"] == PROTOCOL["schema_version"], "Unsupported execution schema")
    for key in ("run_id", "case_id", "event"):
        text(record[key])
    number(record["event_index"], integer=True, minimum=1)
    require(record["event_id"] == f"execution_event_{record['event_index']:06d}", "Non-canonical event identity")
    digest_value(record["previous_execution_head"], nullable=True)
    digest_value(record["artifact_head"], nullable=True)
    number(record["artifact_event_index"], integer=True)
    require((record["artifact_head"] is None) == (record["artifact_event_index"] == 0), "Partial artifact head")
    _timestamp(record["created_at"])
    if kind in IDENTITIES:
        identity, index, builder = IDENTITIES[kind]
        number(record[index], integer=True, minimum=1)
        require(record[identity] == builder(record[index]), "Non-canonical A02 identity")
    if kind == "run":
        require(event == "created" and record["status"] == PROTOCOL["state_machines"]["run_lifecycle"]["initial_state"],
                "Invalid Run creation")
        text(record["parent_run_id"], nullable=True)
        require(record["parent_run_id"] != record["run_id"], "Self-parent Run")
        require(record["creation_reason"] in ("root", "replay_of", "fork_of"), "Unknown Run lineage")
        require((record["creation_reason"] == "root") == (record["parent_run_id"] is None), "Partial Run lineage")
        for key in ("root_goal_reference", "input_snapshot_reference"):
            closed(record[key], ("reference", "sha256"))
            text(record[key]["reference"])
            digest_value(record[key]["sha256"])
        text(record["canonical_output_root"])
        require(record["checkpoint_thread_id"] == stable_checkpoint_thread_id(record["case_id"], record["run_id"]),
                "Wrong checkpoint ownership")
        require(record["policy_version"] == "0.1", "Unknown policy version")
        digest_value(record["policy_digest"])
    elif kind == "cycle":
        require(event == "created" and record["status"] == "active", "Invalid Cycle creation")
        for key in ("parent_cycle_id", "created_by_attempt_id"):
            text(record[key], nullable=True)
        text(record["trigger_reason"])
    elif kind == "attempt":
        number(record["cycle_index"], integer=True, minimum=1)
        require(record["cycle_id"] == stable_cycle_id(record["cycle_index"]), "Invalid parent Cycle")
        text(record["node_name"])
        try:
            require(canonical_attempt_kind(record["node_name"]) == record["attempt_kind"], "Node/kind mismatch")
        except ValueError as error:
            require(False, str(error))
        text(record["parent_attempt_id"], nullable=True)
        text(record["attempt_trigger"])
        text(record["inbound_transition_id"])
        statuses = {"scheduled": ("scheduled",), "started": ("running",),
                    "finished": ("succeeded", "failed", "pending"), "abandoned": ("abandoned",)}
        require(event in statuses and record["status"] in statuses[event], "Invalid Attempt lifecycle variant")
        for key in ("input_references", "output_references"):
            require(type(record[key]) is dict, "Invalid evidence references")
            references = record[key]
            allowed = {field for fields in STATE_FIELDS_BY_SLOT.values() for field in fields} | set(CODE_STATE_PATH_FIELDS) | {"current_artifact_ids"}
            require(set(references) <= allowed, "Unknown artifact reference field")
            if "current_artifact_ids" in references:
                require(type(references["current_artifact_ids"]) is dict and
                        set(references["current_artifact_ids"]) <= set(ARTIFACT_SLOTS), "Unknown artifact reference slot")
                for artifact_id in references["current_artifact_ids"].values():
                    text(artifact_id)
            for field, value in references.items():
                if field != "current_artifact_ids":
                    text(value)
        if record["error"] is not None:
            closed(record["error"], ("type", "message"))
            text(record["error"]["type"])
            text(record["error"]["message"])
    elif kind == "transition":
        require(event == "committed" and record["status"] == "committed", "Invalid Transition")
        require(record["source"] == record["source_node"], "Transition source mismatch")
        for key in ("source_node", "route", "trigger_reason", "reason"):
            text(record[key])
        for key in ("source_cycle_id", "source_attempt_id", "human_request_id", "human_response_id"):
            text(record[key], nullable=True)
        target = [record[key] for key in ("target_node", "target_cycle_id", "target_attempt_id", "target_attempt_kind")]
        if record["target_attempt_id"] is None:
            require(target == [None] * 4 and record["route"] in ("end", "__end__"), "Nonterminal or partial null target")
        else:
            for item in target:
                text(item)
            require(canonical_attempt_kind(record["target_node"]) == record["target_attempt_kind"], "Target node/kind mismatch")
            require(record["route"] not in ("end", "__end__"), "Terminal route has a target")
        for key in ("fields", "evidence_references"):
            require(type(record[key]) is dict, "Invalid Transition evidence")
        keys = record["applied_state_update_keys"]
        require(type(keys) is list and all(type(key) is str for key in keys) and keys == sorted(set(keys)),
                "Non-canonical state update keys")
        digest_value(record["applied_state_updates_sha256"])
        require(record["committed_at"] == record["created_at"], "Transition timestamp mismatch")
    elif kind == "human_request":
        require(event in ("created", "packet_written", "satisfied"), "Unknown Human Request event")
        require(record["status"] == ("satisfied" if event == "satisfied" else "open"), "Invalid request status")
        for key in ("cycle_id", "requesting_attempt_id"):
            text(record[key])
        require(record["request_kind"] in ("clarification", "approval", "external_action"), "Unknown request kind")
        require(type(record["authorization_scope"]) is dict and bool(record["authorization_scope"]), "Missing request scope")
        text(record["packet_reference"], nullable=event != "packet_written")
    elif kind == "human_response":
        require(record["status"] == event, "Invalid response status")
        for key in ("cycle_id", "human_request_id", "payload_reference"):
            text(record[key])
        digest_value(record["payload_sha256"])
        for key in ("validator_attempt_id", "consumer_attempt_id", "authorized_target_attempt_id", "decision",
                    "authorized_route", "authorized_transition_route", "authorized_transition_target"):
            text(record[key], nullable=True)
        if event == "submitted":
            text(record["submitted_payload_reference"])
            require(type(record["payload_snapshot"]) is dict, "Missing response snapshot")
            require(all(record[key] is None for key in ("validator_attempt_id", "consumer_attempt_id", "authorized_target_attempt_id",
                                                        "decision", "authorized_route", "authorized_transition_route", "authorized_transition_target")),
                    "Submitted response cannot carry authorization")
        elif event in ("validated", "invalid"):
            text(record["error"], nullable=event == "validated")
            text(record["validator_attempt_id"])
            require(record["consumer_attempt_id"] is None and record["authorized_target_attempt_id"] is None,
                    "Validated response cannot be preconsumed")
            for key in ("decision", "authorized_route", "authorized_transition_route", "authorized_transition_target"):
                if event == "validated":
                    text(record[key])
                else:
                    require(record[key] is None, "Invalid response carries authorization")
        else:
            text(record["validator_attempt_id"])
            text(record["consumer_attempt_id"])
    elif kind == "run_lifecycle":
        require(event == "transitioned", "Unknown lifecycle event")
        require((record["from_status"], record["to_status"]) in
                PROTOCOL["state_machines"]["run_lifecycle"]["allowed_edges"], "Forbidden Run lifecycle edge")
        text(record["reason_code"])
        for key in ("operation_id", "attempt_id", "pause_id", "budget_event_id"):
            text(record[key], nullable=True)
    elif kind == "pause":
        validate_pause_record(record)
    elif kind == "lineage":
        from .pause import validate_fingerprint
        from .children import validate_source_fingerprint, validate_source_proof
        from .strict_json import digest
        require(event == "lineage_initialized" and record["creation_reason"] in ("replay_of", "fork_of"),
                "Invalid child lineage variant")
        text(record["parent_operation_id"])
        validate_source_proof(record["source_snapshot_proof"], record["creation_reason"])
        require(digest(record["source_snapshot_proof"]) == record["lineage_snapshot_digest"], "Lineage digest mismatch")
        proof = record["source_snapshot_proof"]
        validate_source_fingerprint(record["source_runtime_fingerprint"], proof["source_schema"], record["creation_reason"])
        if record["creation_reason"] == "replay_of":
            require(record["source_runtime_fingerprint"] == proof["runtime_fingerprint"], "Lineage source fingerprint mismatch")
        validate_fingerprint(record["target_runtime_fingerprint"])
        require(record["target_runtime_fingerprint"]["execution_schema"] == "0.4", "Child target fingerprint schema mismatch")
    else:
        number(record["budget_event_index"], integer=True, minimum=1)
        require(record["budget_event_id"] == f"budget_event_{record['budget_event_index']:06d}", "Invalid budget event identity")
        require(record["policy_version"] == "0.1", "Unknown budget version")
        digest_value(record["policy_digest"])
        validate_budget_payload(event, record["payload"])
    return ValidatedValue.from_value(record)


def build_record(record_type, event, *, run_id, case_id, event_index, previous_execution_head,
                 artifact_head, artifact_event_index, timestamp, **fields):
    require(type(timestamp) is Timestamp, "A trusted clock timestamp is required")
    number(event_index, integer=True, minimum=1)
    return validate_record({"schema_version": PROTOCOL["schema_version"], "record_type": record_type,
                            "event": event, "run_id": run_id, "case_id": case_id,
                            "event_id": f"execution_event_{event_index:06d}", "event_index": event_index,
                            "previous_execution_head": previous_execution_head, "artifact_head": artifact_head,
                            "artifact_event_index": artifact_event_index, "created_at": asdict(timestamp), **fields})


def parse_record(data):
    return validate_record(loads(data))


def execution_head(record):
    return validate_record(record).digest
