"""Canonical Code outcome and content-addressed bundle members."""
from hashlib import sha256

from lqcd_agent.control.strict_json import ValidatedValue, canonical_bytes, closed, digest, digest_value, loads, number, require, text

from .backend import validate_receipt
from .ingress import validate_change_manifest, validate_workspace_seal
from .schemas import IDENTITY, validate_manifest, validate_task
from .verification import build_verification_results


FAILURE_CLASSES = frozenset({"none", "task_invalid", "base_mismatch", "workspace_setup", "tool_error",
                             "verification_failed", "scope_violation", "policy_violation", "dependency_unavailable",
                             "timeout", "external_interruption", "no_safe_change", "result_invalid"})
RETRYABILITY = frozenset({"not_retryable", "new_attempt_allowed", "new_evidence_required", "human_required"})
RESULT_FIELDS = (*IDENTITY, "schema_version", "result_id", "result_origin", "task_id", "task_digest",
                 "external_result_digest", "dispatch_receipt_digest", "workspace_manifest_digest",
                 "workspace_seal_digest", "change_manifest_digest", "verification_results_digest",
                 "tool_audit_digest", "patch_digest", "status", "usable", "failure_class", "retryability",
                 "recommended_action", "summary", "resource_usage", "result_digest")
TIMEOUT_RESULT_FIELDS = (*RESULT_FIELDS, "interrupt_evidence_digest", "backend_absence")
TIMEOUT_ABSENCE = {name: {"tag": "not_applicable", "reason": "host_timeout"} for name in
                   ("external_result", "workspace_seal", "tool_audit", "patch")}


def validate_code_result(value, task):
    task = validate_task(task).value
    value = loads(value) if type(value) in (str, bytes) else loads(canonical_bytes(value))
    origin = value.get("result_origin")
    closed(value, TIMEOUT_RESULT_FIELDS if origin == "host_timeout" else RESULT_FIELDS)
    require(value["schema_version"] == "0.1" and origin in ("backend_delivery", "host_timeout") and
            value["result_id"] == task["attempt_id"] + ":code_result" and
            value["task_id"] == task["task_id"] and value["task_digest"] == task["task_digest"] and
            all(value[name] == task[name] for name in IDENTITY), "Code result identity changed")
    require(value["status"] in ("success", "no_change", "failed", "needs_input", "needs_human",
                                "budget_exhausted", "policy_blocked") and
            value["usable"] is (value["status"] == "success") and
            value["failure_class"] in FAILURE_CLASSES and value["retryability"] in RETRYABILITY,
            "Invalid canonical Code outcome")
    require((value["status"] == "success") == (value["failure_class"] == "none") and
            (value["status"] != "no_change" or value["failure_class"] == "no_safe_change"),
            "Code result diagnostic contradicts status")
    if origin == "host_timeout":
        require(value["status"] == "failed" and value["usable"] is False and
                value["failure_class"] == "timeout" and value["retryability"] == "new_attempt_allowed" and
                value["external_result_digest"] is None and value["workspace_seal_digest"] is None and
                value["tool_audit_digest"] is None and value["patch_digest"] is None and
                value["backend_absence"] == TIMEOUT_ABSENCE,
                "Invalid host-timeout result shape")
        digest_value(value["interrupt_evidence_digest"])
    else:
        digest_value(value["external_result_digest"])
        digest_value(value["workspace_seal_digest"])
        digest_value(value["tool_audit_digest"])
    for name in ("workspace_manifest_digest", "change_manifest_digest", "verification_results_digest"):
        digest_value(value[name])
    digest_value(value["dispatch_receipt_digest"], nullable=origin == "host_timeout")
    digest_value(value["patch_digest"], nullable=True)
    for name in ("recommended_action", "summary"):
        text(value[name])
        require(len(value[name]) <= 4096, "Unbounded Code advice")
    usage = closed(value["resource_usage"], ("llm_calls", "tool_calls", "verification_commands", "active_seconds"))
    for name, amount in usage.items():
        number(amount, integer=name != "active_seconds", minimum=0)
    digest_value(value["result_digest"])
    require(value["result_digest"] == digest({k: v for k, v in value.items() if k != "result_digest"}),
            "Canonical Code result digest mismatch")
    return ValidatedValue(canonical_bytes(value))


def canonical_result(task, external, receipt, manifest, seal, changes, verification, *, failure_class,
                     retryability, recommended_action, summary, trusted_usage):
    """The Host decides status from verified evidence, never from Backend pass claims."""
    require(type(external) is ValidatedValue, "External result has not passed Host ingress preflight")
    external = external.value
    task = validate_task(task).value
    manifest = validate_manifest(manifest, task).value
    require(verification == build_verification_results(task, verification["spec_results"]),
            "Trusted verification result changed")
    require(external["task_digest"] == task["task_digest"] and
            external["result_digest"] == digest({k: v for k, v in external.items() if k != "result_digest"}) and
            receipt["task_digest"] == task["task_digest"] and
            seal["workspace_manifest_digest"] == manifest["manifest_digest"] and
            changes["change_manifest_digest"] == seal["change_manifest_digest"],
            "Canonical result source changed")
    declared = external["declared_status"]
    has_change = bool(changes["changes"])
    if declared == "success":
        status = "success" if has_change and verification["all_required_passed"] else "failed"
    elif declared == "no_change":
        status = "no_change" if not has_change else "failed"
    elif declared in ("needs_input", "needs_human", "budget_exhausted", "policy_blocked"):
        status = declared if not has_change else "failed"
    else:
        status = "failed"
    require(failure_class in FAILURE_CLASSES and retryability in RETRYABILITY, "Unknown canonical diagnostic")
    if status == "success":
        require(failure_class == "none", "Success cannot have a failure class")
    elif status == "no_change":
        require(failure_class == "no_safe_change", "No-change diagnosis mismatch")
    else:
        require(failure_class != "none", "Non-success requires a failure class")
    if declared == "success" and status == "failed":
        require(failure_class == "verification_failed", "Failed success candidate lost verifier diagnosis")
    for value in (recommended_action, summary):
        text(value)
        require(len(value) <= 4096, "Unbounded Code advice")
    require(type(trusted_usage) is dict and set(trusted_usage) ==
            {"llm_calls", "tool_calls", "verification_commands", "active_seconds"},
            "Missing trusted resource usage")
    for name, amount in trusted_usage.items():
        number(amount, integer=name != "active_seconds", minimum=0)
    value = {key: task[key] for key in IDENTITY}
    value.update(schema_version="0.1", result_id=task["attempt_id"] + ":code_result",
                 result_origin="backend_delivery", task_id=task["task_id"], task_digest=task["task_digest"],
                 external_result_digest=external["result_digest"],
                 dispatch_receipt_digest=sha256(canonical_bytes(receipt)).hexdigest(),
                 workspace_manifest_digest=manifest["manifest_digest"], workspace_seal_digest=seal["seal_digest"],
                 change_manifest_digest=changes["change_manifest_digest"],
                 verification_results_digest=verification["verification_results_digest"],
                 tool_audit_digest=seal["tool_audit_digest"], patch_digest=external["patch_digest"],
                 status=status, usable=status == "success", failure_class=failure_class,
                 retryability=retryability, recommended_action=recommended_action, summary=summary,
                 resource_usage=trusted_usage)
    value["result_digest"] = digest(value)
    return validate_code_result(value, task).value


def bundle_members(task, result, receipt, manifest, seal, changes, verification, tool_audit, patch):
    """Return exact regular-delivery member bytes for one Attempt namespace."""
    task = validate_task(task).value
    manifest = validate_manifest(manifest, task).value
    receipt = validate_receipt(receipt, task, manifest).value
    changes = validate_change_manifest(changes, task, manifest).value
    seal = validate_workspace_seal(seal, task, manifest, changes, tool_audit).value
    require(verification == build_verification_results(task, verification["spec_results"]),
            "Bundle verification result changed")
    result = validate_code_result(result, task).value
    require(result["dispatch_receipt_digest"] == sha256(canonical_bytes(receipt)).hexdigest() and
            result["workspace_manifest_digest"] == manifest["manifest_digest"] and
            result["workspace_seal_digest"] == seal["seal_digest"] and
            result["change_manifest_digest"] == changes["change_manifest_digest"] and
            result["verification_results_digest"] == verification["verification_results_digest"],
            "Code bundle member source changed")
    require(result["status"] != "success" or bool(changes["changes"]) and verification["all_required_passed"],
            "Success bundle lacks change or trusted verification")
    require(result["status"] != "no_change" or not changes["changes"],
            "No-change bundle contains a change")
    members = {"code_agent_task.json": canonical_bytes(task), "code_agent_result.json": canonical_bytes(result),
               "backend_dispatch_receipt.json": canonical_bytes(receipt),
               "workspace_manifest.json": canonical_bytes(manifest), "workspace_seal.json": canonical_bytes(seal),
               "change_manifest.json": canonical_bytes(changes),
               "verification_results.json": canonical_bytes(verification), "tool_audit.jsonl": tool_audit}
    require(type(tool_audit) is bytes and sha256(tool_audit).hexdigest() == result["tool_audit_digest"],
            "Bundle tool audit changed")
    if changes["changes"]:
        require(type(patch) is bytes and sha256(patch).hexdigest() == result["patch_digest"],
                "Bundle patch changed")
        members["changes.patch"] = patch
    else:
        require(patch is None and result["patch_digest"] is None, "Empty bundle has a patch")
    return members


def timeout_bundle(task, manifest, value, final, *, dispatch_phase, receipt=None):
    """Derive the closed host-timeout member set from the interrupt winner."""
    task = validate_task(task).value
    manifest = validate_manifest(manifest, task).value
    require(value["resolution_owner"] == "interrupt" and value["proof_kind"] == final["proof_kind"] == "safe_stop" and
            value["operation_phase"] == "external_final_evidence_committed" and
            final["resolution_owner"] == "interrupt" and not final["proven_policy_violation"] and
            final["interrupt_disposition"] == "recoverable_timeout" and
            final["stop_proof"]["termination_or_not_dispatched"] in ("confirmed", {"tag": "not_dispatched"}) and
            all(final["stop_proof"][name] is True for name in
                ("write_lease_revocation", "verify_empty", "bounded_drain", "post_stop_stability")),
            "Timeout lacks a trusted recoverable safe-stop winner")
    require(all(task[name] == value["run_locator"][name] for name in ("case_id", "run_id")) and
            all(task[name] == value[name] for name in ("cycle_id", "attempt_id", "producer_operation_id")) and
            manifest["workspace_id"] == value["workspace_id"] and
            task["task_digest"] == value["task_digest"] and
            manifest["manifest_digest"] == value["workspace_manifest_digest"],
            "Timeout task or workspace source changed")
    if receipt is None:
        require(value["dispatch_receipt_reference"] is None and value["dispatch_receipt_digest"] is None,
                "Timeout omitted an existing receipt")
        require(dispatch_phase == "dispatch_authorized", "Timeout receipt absence has the wrong dispatch phase")
        receipt_digest = None
    else:
        require(dispatch_phase == "dispatch_receipt_committed", "Timeout receipt has the wrong dispatch phase")
        receipt = validate_receipt(receipt, task, manifest).value
        receipt_digest = sha256(canonical_bytes(receipt)).hexdigest()
        require(receipt_digest == value["dispatch_receipt_digest"], "Timeout receipt changed")
    changes = {"schema_version": "0.1", "task_id": task["task_id"], "workspace_id": manifest["workspace_id"],
               "base_tree_digest": task["base_tree_digest"], "final_tree_digest": task["base_tree_digest"],
               "changes": []}
    changes["change_manifest_digest"] = digest(changes)
    changes = validate_change_manifest(changes, task, manifest).value
    from .verification import TrustedVerifier
    verification = build_verification_results(task, [TrustedVerifier.not_run(spec, "operation_timeout")
                                                     for spec in task["verification_specs"]])
    evidence = {"schema_version": "0.1", "producer_operation_id": value["producer_operation_id"],
                "case_id": task["case_id"], "run_id": task["run_id"], "cycle_id": task["cycle_id"],
                "attempt_id": task["attempt_id"], "winner_operation_id": value["resolution_owner_operation_id"],
                "external_final_digest": value["terminal_evidence_digest"],
                "stop_proof_digest": digest(final["stop_proof"]), "resource_actual": final["resource_actual"],
                "dispatch_phase": dispatch_phase,
                "dispatch_receipt_digest": receipt_digest}
    evidence["interrupt_evidence_digest"] = digest(evidence)
    result = {key: task[key] for key in IDENTITY}
    result.update(schema_version="0.1", result_id=task["attempt_id"] + ":code_result",
                  result_origin="host_timeout", task_id=task["task_id"], task_digest=task["task_digest"],
                  external_result_digest=None, dispatch_receipt_digest=receipt_digest,
                  workspace_manifest_digest=manifest["manifest_digest"], workspace_seal_digest=None,
                  change_manifest_digest=changes["change_manifest_digest"],
                  verification_results_digest=verification["verification_results_digest"],
                  tool_audit_digest=None, patch_digest=None, status="failed", usable=False,
                  failure_class="timeout", retryability="new_attempt_allowed",
                  recommended_action="Review the timeout before retrying", summary="Trusted operation timeout",
                  resource_usage=final["resource_actual"],
                  interrupt_evidence_digest=evidence["interrupt_evidence_digest"], backend_absence=TIMEOUT_ABSENCE)
    result["result_digest"] = digest(result)
    result = validate_code_result(result, task).value
    members = {"code_agent_task.json": canonical_bytes(task), "code_agent_result.json": canonical_bytes(result),
               "workspace_manifest.json": canonical_bytes(manifest), "interrupt_evidence.json": canonical_bytes(evidence),
               "change_manifest.json": canonical_bytes(changes),
               "verification_results.json": canonical_bytes(verification)}
    if receipt is not None:
        members["backend_dispatch_receipt.json"] = canonical_bytes(receipt)
    return members, result
