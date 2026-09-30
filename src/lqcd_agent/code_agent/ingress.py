"""Strict pre-claim validation of untrusted canonical Code delivery bytes."""
from hashlib import sha256

from lqcd_agent.control.strict_json import ValidatedValue, canonical_bytes, closed, digest, digest_value, loads, number, require, text

from .backend import validate_receipt
from .schemas import IDENTITY, relative_path, validate_manifest, validate_task
from .workspace import canonical_patch, tree_digest, validate_changes, validate_tool_audit


STATUSES = frozenset({"success", "no_change", "failed", "needs_input", "needs_human", "budget_exhausted",
                      "policy_blocked"})
RESULT_FIELDS = (*IDENTITY, "schema_version", "result_id", "result_digest", "task_id", "task_digest",
                 "workspace_id", "workspace_manifest_digest", "base_revision", "base_tree_digest",
                 "coding_backend_kind", "backend_version", "provider_operation_reference", "provider_thread_reference",
                 "dispatch_receipt_digest", "workspace_seal_digest", "change_manifest_digest", "tool_audit_digest",
                 "change_blobs", "patch_digest", "declared_status", "backend_verification_claims", "resource_usage",
                 "warnings", "errors", "failure_evidence")
CHANGE_FIELDS = ("schema_version", "task_id", "workspace_id", "base_tree_digest", "final_tree_digest",
                 "changes", "change_manifest_digest")
SEAL_FIELDS = ("schema_version", "workspace_id", "workspace_manifest_digest", "producer_operation_id",
               "coding_backend_kind", "backend_version", "terminal_backend_status", "final_tree_digest",
               "change_manifest_digest", "tool_audit_digest", "stop_proof_digest", "sealed_at",
               "write_lease_revoked", "seal_digest")
ENTRY_FIELDS = ("path", "kind", "before_sha256", "after_sha256", "mode", "blob_digest")


def _decode(value):
    if type(value) in (str, bytes):
        raw = value.encode("utf-8") if type(value) is str else value
        parsed = loads(raw)
        require(raw == canonical_bytes(parsed), "Noncanonical ingress bytes")
        return parsed
    return loads(canonical_bytes(value))


def validate_change_manifest(value, task, manifest):
    value = _decode(value)
    closed(value, CHANGE_FIELDS)
    require(value["schema_version"] == "0.1" and value["task_id"] == task["task_id"] and
            value["workspace_id"] == manifest["workspace_id"] and
            value["base_tree_digest"] == task["base_tree_digest"], "Change manifest source mismatch")
    digest_value(value["final_tree_digest"])
    require(type(value["changes"]) is list, "Missing change entries")
    paths = []
    for item in value["changes"]:
        closed(item, ENTRY_FIELDS)
        relative_path(item["path"])
        require(item["kind"] in ("added", "modified", "deleted") and item["mode"] == "100644",
                "Invalid change kind or mode")
        digest_value(item["before_sha256"], nullable=True)
        digest_value(item["after_sha256"], nullable=True)
        digest_value(item["blob_digest"], nullable=True)
        require(item["blob_digest"] == item["after_sha256"] and
                (item["before_sha256"] is None) == (item["kind"] == "added") and
                (item["after_sha256"] is None) == (item["kind"] == "deleted"), "Invalid change blob identity")
        paths.append(item["path"])
    require(paths == sorted(set(paths)), "Change manifest is not a unique sorted set")
    digest_value(value["change_manifest_digest"])
    require(value["change_manifest_digest"] == digest({k: v for k, v in value.items() if k != "change_manifest_digest"}),
            "Change manifest digest mismatch")
    return ValidatedValue(canonical_bytes(value))


def validate_workspace_seal(value, task, manifest, changes, tool_audit):
    value = _decode(value)
    closed(value, SEAL_FIELDS)
    require(value["schema_version"] == "0.1" and value["workspace_id"] == manifest["workspace_id"] and
            value["workspace_manifest_digest"] == manifest["manifest_digest"] and
            value["producer_operation_id"] == task["producer_operation_id"] and
            value["coding_backend_kind"] == task["coding_backend_kind"] and
            value["backend_version"] == task["backend_version"] and
            value["terminal_backend_status"] in ("completed", "failed") and
            value["write_lease_revoked"] is True, "Workspace seal identity or stop mismatch")
    require(value["final_tree_digest"] == changes["final_tree_digest"] and
            value["change_manifest_digest"] == changes["change_manifest_digest"] and
            value["tool_audit_digest"] == sha256(tool_audit).hexdigest(), "Workspace seal content mismatch")
    digest_value(value["stop_proof_digest"])
    number(value["sealed_at"])
    digest_value(value["seal_digest"])
    require(value["seal_digest"] == digest({k: v for k, v in value.items() if k != "seal_digest"}),
            "Workspace seal digest mismatch")
    return ValidatedValue(canonical_bytes(value))


def preflight_result(raw, task, manifest, receipt, seal, change_manifest, tool_audit, patch,
                     provider, witness, base):
    """Reject ingress before Pause claim; backend verification claims are audit only."""
    task = validate_task(task).value
    manifest = validate_manifest(manifest, task).value
    receipt = validate_receipt(receipt, task, manifest).value
    changes = validate_change_manifest(change_manifest, task, manifest).value
    require(type(tool_audit) is bytes, "Missing immutable tool audit")
    validate_tool_audit(tool_audit, task, manifest)
    seal = validate_workspace_seal(seal, task, manifest, changes, tool_audit).value
    final = provider.verify_sealed(manifest, witness, seal["final_tree_digest"])
    require(tree_digest(base) == task["base_tree_digest"] and
            validate_changes(task, base, final) == changes["changes"], "Workspace change evidence drifted")
    value = _decode(raw)
    closed(value, RESULT_FIELDS)
    require(value["schema_version"] == "0.1" and
            value["result_id"] == task["attempt_id"] + ":external_result", "Invalid external result identity")
    for name in IDENTITY:
        require(value[name] == task[name], "External result target mismatch")
    for name, expected in (("task_id", task["task_id"]), ("task_digest", task["task_digest"]),
                           ("workspace_id", manifest["workspace_id"]),
                           ("workspace_manifest_digest", manifest["manifest_digest"]),
                           ("base_revision", task["base_revision"]), ("base_tree_digest", task["base_tree_digest"]),
                           ("coding_backend_kind", task["coding_backend_kind"]),
                           ("backend_version", task["backend_version"]),
                           ("provider_operation_reference", receipt["provider_operation_reference"]),
                           ("provider_thread_reference", receipt["provider_thread_reference"]),
                           ("dispatch_receipt_digest", sha256(canonical_bytes(receipt)).hexdigest()),
                           ("workspace_seal_digest", seal["seal_digest"]),
                           ("change_manifest_digest", changes["change_manifest_digest"]),
                           ("tool_audit_digest", seal["tool_audit_digest"])):
        require(value[name] == expected, "External result source mismatch")
    require(value["declared_status"] in STATUSES, "Unknown external result status")
    blobs = [{"path": item["path"], "sha256": item["after_sha256"]} for item in changes["changes"]
             if item["after_sha256"] is not None]
    require(value["change_blobs"] == blobs, "External change blobs differ from Host observation")
    require((patch is None and value["patch_digest"] is None and not changes["changes"]) or
            (type(patch) is bytes and bool(changes["changes"]) and patch == canonical_patch(base, final, changes["changes"]) and
             value["patch_digest"] == sha256(patch).hexdigest()), "Patch presence or content mismatch")
    claims = value["backend_verification_claims"]
    require(type(claims) is list and all(type(item) is dict and set(item) == {"spec_id", "status"} and
            type(item["spec_id"]) is str and item["status"] in ("passed", "failed", "blocked", "timeout", "not_run")
            for item in claims) and len({item["spec_id"] for item in claims}) == len(claims),
            "Malformed untrusted verification claims")
    usage = closed(value["resource_usage"], ("llm_calls", "tool_calls", "verification_commands", "active_seconds"))
    for name, amount in usage.items():
        number(amount, integer=name != "active_seconds", minimum=0)
    for name in ("warnings", "errors"):
        messages = value[name]
        require(type(messages) is list and len(messages) <= 128 and
                all(type(item) is str and len(item) <= 4096 for item in messages), "Unbounded external diagnostics")
    if value["failure_evidence"] is not None:
        closed(value["failure_evidence"], ("kind", "digest"))
        text(value["failure_evidence"]["kind"])
        digest_value(value["failure_evidence"]["digest"])
    require(value["declared_status"] != "success" or bool(changes["changes"]),
            "Empty change cannot be a success candidate")
    require(value["declared_status"] != "policy_blocked" or not changes["changes"],
            "Policy-blocked result contains a change")
    digest_value(value["result_digest"])
    require(value["result_digest"] == digest({k: v for k, v in value.items() if k != "result_digest"}),
            "External result digest mismatch")
    return ValidatedValue(canonical_bytes(value))
