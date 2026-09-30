"""The A05 coding backend port and its closed Host-facing receipts."""
from typing import Protocol

from lqcd_agent.control.strict_json import ValidatedValue, canonical_bytes, closed, digest, digest_value, loads, number, require, text


BACKEND_STATUSES = frozenset({"accepted", "running", "completed", "failed", "cancelled", "unknown"})
RECEIPT_FIELDS = ("schema_version", "producer_operation_id", "task_id", "task_digest", "workspace_id",
                  "workspace_manifest_digest", "backend_kind", "backend_version", "provider_operation_reference",
                  "provider_thread_reference", "dispatch_status", "receipt_digest")
STATUS_FIELDS = ("schema_version", "producer_operation_id", "backend_kind", "backend_version", "status",
                 "receipt_reference", "receipt_digest", "queried_at")
RESULT_REFERENCE_FIELDS = ("schema_version", "producer_operation_id", "reference", "digest", "size")


class CodingBackend(Protocol):
    def dispatch(self, task_ref, workspace_manifest_ref, producer_operation_id): ...

    def lookup(self, producer_operation_id): ...

    def fetch_result(self, producer_operation_id): ...

    def cancel(self, producer_operation_id, typed_reason): ...


def validate_receipt(value, task, manifest):
    value = loads(value) if type(value) in (str, bytes) else loads(canonical_bytes(value))
    closed(value, RECEIPT_FIELDS)
    require(value["schema_version"] == "0.1" and value["dispatch_status"] == "accepted", "Invalid dispatch receipt")
    expected = {"producer_operation_id": task["producer_operation_id"], "task_id": task["task_id"],
                "task_digest": task["task_digest"], "workspace_id": manifest["workspace_id"],
                "workspace_manifest_digest": manifest["manifest_digest"], "backend_kind": task["coding_backend_kind"],
                "backend_version": task["backend_version"]}
    require(all(value[key] == item for key, item in expected.items()), "Dispatch receipt identity mismatch")
    for name in ("provider_operation_reference", "provider_thread_reference"):
        require(value[name] is None or type(value[name]) is str and bool(value[name]), "Invalid provider audit identity")
    digest_value(value["receipt_digest"])
    require(value["receipt_digest"] == digest({key: item for key, item in value.items() if key != "receipt_digest"}),
            "Dispatch receipt digest mismatch")
    return ValidatedValue(canonical_bytes(value))


def validate_status(value):
    value = loads(value) if type(value) in (str, bytes) else loads(canonical_bytes(value))
    closed(value, STATUS_FIELDS)
    require(value["schema_version"] == "0.1" and value["status"] in BACKEND_STATUSES, "Invalid backend status")
    for name in ("producer_operation_id", "backend_kind", "backend_version"):
        text(value[name])
    number(value["queried_at"])
    if value["status"] == "unknown":
        require(value["receipt_reference"] is value["receipt_digest"] is None, "Unknown operation claimed a receipt")
    else:
        text(value["receipt_reference"])
        digest_value(value["receipt_digest"])
    return ValidatedValue(canonical_bytes(value))


def validate_result_reference(value):
    value = loads(value) if type(value) in (str, bytes) else loads(canonical_bytes(value))
    closed(value, RESULT_REFERENCE_FIELDS)
    require(value["schema_version"] == "0.1", "Invalid backend result reference")
    text(value["producer_operation_id"])
    text(value["reference"])
    digest_value(value["digest"])
    number(value["size"], integer=True, minimum=1)
    return ValidatedValue(canonical_bytes(value))
