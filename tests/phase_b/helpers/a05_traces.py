"""Contract-level A05 sources on real B02 prefixes, without B03 runtime credit."""
from copy import deepcopy
from pathlib import Path
import tempfile
import uuid
import os
from unittest.mock import patch
from hashlib import sha256

from harness.a05_trace import typed_source, material_source, CHECKSUMS
from harness.trace import event
from harness.trace_proof import source_object
from lqcd_agent.control.strict_json import digest, canonical_bytes
from lqcd_agent.control.records import build_record
from lqcd_agent.control.clock import Timestamp
from test_b03_task_trace_boundary import immutable_base, task_trace_witness


def prestart_trace(base=None):
    if base is None:
        with patch.dict(os.environ, {"GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
                                     "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00"}):
            base = immutable_base()
    witness = task_trace_witness(base)
    trace = deepcopy(witness["trace"])
    trace["schema_version"] = "0.5"
    proof = trace["proof"]
    proof.update(schema_version="0.2", typed_sources=[], material_sources=[], workspace_roots=[])
    context = {"requirement": witness["task"]["requirements"][0], **base}
    for kind, value in (("task", witness["task"]), ("manifest", witness["manifest"]), ("code_context", context)):
        add_source(trace, kind, value)
    trace["events"][-1].update(task_digest=witness["task"]["task_digest"], manifest_digest=witness["manifest"]["manifest_digest"])
    return trace, witness


def add_source(trace, kind, value):
    trace["proof"]["objects"].append(source_object("canonical_json", value, version="0.4"))
    trace["proof"]["typed_sources"].append(typed_source(kind, value))
    return digest(value)


def full_trace(base=None, *, outcome="normal", clock=100):
    trace, witness = prestart_trace(base)
    task, manifest = witness["task"], witness["manifest"]
    owner = {k: task[k] for k in ("case_id", "run_id", "attempt_id", "producer_operation_id")}
    owner["workspace_id"] = manifest["workspace_id"]
    values = {}

    def add(kind, **fields):
        value = {"schema_version": "0.1", **owner, **fields}
        checksum = CHECKSUMS[kind]
        if checksum:
            value[checksum] = digest(value)
        head = add_source(trace, kind, value)
        values[kind] = value
        return value[checksum] if checksum else head

    core = add("core", task_digest=task["task_digest"], workspace_manifest_digest=manifest["manifest_digest"],
               reservation_digest=digest(witness["reservation"]))
    pause_binding = add("pause_binding", pause_id="pause_000001", task_digest=task["task_digest"],
        workspace_manifest_digest=manifest["manifest_digest"], operation_contract_digest=core,
        reservation_digest=digest(witness["reservation"]), status="opened")
    workspace = Path(tempfile.mkdtemp(prefix="lqcd-agent-a05-workspace-", dir="/private/tmp"))
    workspace_evidence = add("workspace_evidence", workspace_path=str(workspace), manifest_digest=manifest["manifest_digest"],
        managed_root_identity=manifest["managed_root_identity"], created_at=clock)
    trace["proof"]["workspace_roots"].append({"evidence_digest": workspace_evidence, "path": str(workspace)})
    patch_head = None
    changes = []
    if outcome == "normal":
        changes = [{"path": "sample.py", "kind": "modified", "mode": "100644",
                    "before_sha256": sha256(b"def value():\n    return 1\n").hexdigest(),
                    "after_sha256": sha256(b"def value():\n    return 2\n").hexdigest()}]
        patch = b"--- a/sample.py\n+++ b/sample.py\n@@ -1,2 +1,2 @@\n def value():\n-    return 1\n+    return 2\n"
        patch_source = material_source("material", patch, owner)
        trace["proof"]["material_sources"].append(patch_source)
        patch_head = patch_source["sha256"]
    change = add("change_manifest", task_digest=task["task_digest"], changes=changes)
    verification = add("verification", task_digest=task["task_digest"], workspace_manifest_digest=manifest["manifest_digest"],
        results=[{"spec_id": "fixture-check", "argv": task["verification_specs"][0]["argv"], "cwd": str(workspace),
                  "started_at": clock + 3, "finished_at": clock + 4, "duration": 1,
                  "status": "passed" if outcome == "normal" else "not_run"}])
    receipt = seal = external_result = None
    if outcome == "normal":
        provider = "job_" + uuid.uuid4().hex
        receipt = add("receipt", task_digest=task["task_digest"], workspace_manifest_digest=manifest["manifest_digest"],
            operation_contract_digest=core, provider_operation_reference=provider, accepted_at=clock, lease_epoch=1)
        audit = [{**owner, "tool_event_index": 1, "argv_digest": digest(["fixture-tool"]), "cwd": str(workspace),
                  "started_at": clock, "finished_at": clock + 1, "status": "completed"}]
        audit_source = material_source("tool_audit", b"".join(canonical_bytes(r) + b"\n" for r in audit), owner)
        trace["proof"]["material_sources"].append(audit_source)
        seal = add("seal", task_digest=task["task_digest"], workspace_manifest_digest=manifest["manifest_digest"],
            change_manifest_digest=change, tool_audit_digest=audit_source["sha256"], sealed_at=clock + 1,
            write_lease_revoked=True, final_tree_digest=manifest["base_tree_digest"])
        external_result = add("external_result", task_digest=task["task_digest"], workspace_manifest_digest=manifest["manifest_digest"],
            dispatch_receipt_digest=receipt, workspace_seal_digest=seal, tool_audit_digest=audit_source["sha256"],
            provider_operation_reference=provider, declared_status="success")
    final = add("external_final", task_digest=task["task_digest"], workspace_manifest_digest=manifest["manifest_digest"],
        operation_contract_digest=core, result_digest=external_result, dispatch_receipt_digest=receipt,
        pause_id="pause_000001", pause_binding_digest=pause_binding,
        proof_kind="safe_stop" if outcome != "unavailable" else "unavailable", lease_epoch=1, created_at=clock + 2)
    add("external_operation", task_digest=task["task_digest"], workspace_manifest_digest=manifest["manifest_digest"],
        reservation_digest=digest(witness["reservation"]), operation_contract_digest=core, pause_id="pause_000001",
        pause_binding_digest=pause_binding, terminal_evidence_digest=final, result_digest=external_result,
        operation_phase="external_final_evidence_committed", phase_revision=10, lease_epoch=1,
        status="completed" if outcome == "normal" else "recovery_required" if outcome == "unavailable" else "interrupted")
    envelope = {"operation_type": "resume_run", "operation_variant": "consume_external_result",
        "request": {"run_locator": {k: owner[k] for k in ("case_id", "run_id")}, "pause_id": "pause_000001",
                    "input_snapshot": {"producer_operation_id": owner["producer_operation_id"], "external_final_digest": final}},
        "task_snapshot": deepcopy(task), "external_operation_snapshot": deepcopy(values["external_operation"])}
    envelope_head = digest(envelope)
    trace["proof"]["objects"].append(source_object("canonical_json", envelope, version="0.4"))
    trace["events"].append(event("consumption_envelope_contract", run_id=owner["run_id"],
        binding_digest=envelope_head, outcome="contract_only"))
    def settle(evidence):
        reserved = witness["reservation"]
        settlement = build_record("budget", "resource_settled", **{k: reserved[k] for k in ("case_id", "run_id")},
            event_index=reserved["event_index"] + 1, previous_execution_head=digest(reserved),
            artifact_head=reserved["artifact_head"], artifact_event_index=reserved["artifact_event_index"],
            timestamp=Timestamp(**reserved["created_at"]), budget_event_id="budget_event_000005", budget_event_index=5,
            policy_version="0.1", policy_digest=reserved["policy_digest"],
            payload={"resource_operation_id": reserved["payload"]["resource_operation_id"],
                     "actual": {"llm_calls": 1, "tool_calls": 1, "verification_commands": 0, "active_seconds": 2},
                     "tokens": {"state": "unknown", "value": None}, "cost": {"state": "unknown", "value": None},
                     "evidence_digest": evidence, "operation_id": "contract_consumption", "lease_epoch": 1, "phase_revision": 10}).value
        trace["proof"]["objects"].append(source_object("execution_0_4", settlement, version="0.4"))
        trace["events"].append(event("resource_settlement_contract", run_id=owner["run_id"], execution_head=digest(settlement), outcome="contract_only"))
    if outcome in ("normal", "timeout"):
        settle(final)
    interrupt = None
    if outcome != "normal":
        interrupt = add("interrupt_evidence", task_digest=task["task_digest"], terminal_evidence_digest=final,
                        disposition="recoverable_timeout" if outcome == "timeout" else "integrity_failure")
    if outcome in ("failed", "unavailable"):
        failure_id = add_source(trace, "failure_identity", {"owner": "contract_consumption", "source_phase": "target_started",
            "source_revision": 9, "epoch": 1, "cause_type": "IntegrityError", "cause": "Contract fixture rejection"})
        failure = add("failure_evidence", task_digest=task["task_digest"], terminal_evidence_digest=final,
                      interrupt_evidence_digest=interrupt, change_manifest_digest=change,
                      failure_id_digest=failure_id, operation_id="contract_consumption",
                      consumer_stop="safe_stop" if outcome == "failed" else "unavailable")
        if outcome == "failed":
            settle(failure_id)
        trace["events"].append(event("consumption_failure", run_id=owner["run_id"], attempt_id=owner["attempt_id"],
            external_operation_id=owner["producer_operation_id"], workspace_id=owner["workspace_id"],
            binding_digest=failure, result_digest=verification, outcome=outcome))
        return trace, values
    result = add("code_result", result_origin="backend_delivery" if outcome == "normal" else "host_timeout",
        task_digest=task["task_digest"], workspace_manifest_digest=manifest["manifest_digest"],
        dispatch_receipt_digest=receipt, workspace_seal_digest=seal, change_manifest_digest=change,
        verification_results_digest=verification, interrupt_evidence_digest=interrupt,
        tool_audit_digest=audit_source["sha256"] if outcome == "normal" else None,
        terminal_evidence_digest=final, patch_digest=patch_head, status="success" if outcome == "normal" else "failed", usable=outcome == "normal",
        failure_class="none" if outcome == "normal" else "timeout",
        seal_absence=None if outcome == "normal" else {"tag": "not_applicable", "reason": "host_timeout"})
    selected = {"task": task, "manifest": manifest, "code_result": values["code_result"],
                "verification": values["verification"], "change_manifest": values["change_manifest"]}
    selected.update({k: values[k] for k in (("receipt", "seal") if outcome == "normal" else ("interrupt_evidence",))})
    names = {"task": "code_agent_task", "manifest": "workspace_manifest", "code_result": "code_agent_result",
             "verification": "verification_results", "receipt": "backend_dispatch_receipt", "seal": "workspace_seal"}
    members = [{"canonical_path": "attempts/" + owner["attempt_id"] + "/" + names.get(kind, kind) + ".json",
                "sha256": digest(value), "size_bytes": len(canonical_bytes(value))} for kind, value in selected.items()]
    if outcome == "normal":
        members.extend([{"canonical_path": "attempts/" + owner["attempt_id"] + "/" + name,
                         "sha256": source["sha256"], "size_bytes": len(source["content"].encode())}
                        for name, source in (("changes.patch", patch_source), ("tool_audit.jsonl", audit_source))])
    bundle = {**owner, "schema_version": "0.1", "slot": "code", "event": "registered", "members": members,
              "artifact_id": owner["attempt_id"] + ":code", "execution_head": digest(witness["reservation"])}
    bundle["pointer"] = {k: deepcopy(bundle[k]) for k in ("slot", "artifact_id", "attempt_id", "members")}
    run_root = Path(trace["proof"]["output_roots"][0]["path"])
    paths = {"code_change_summary_path": None, "tests_status_path": None}
    paths.update({field: str(run_root / "attempts" / owner["attempt_id"] / name) for field, name in (
        ("code_agent_task_path", "code_agent_task.json"),
        ("code_agent_result_path", "code_agent_result.json"),
        ("code_change_manifest_path", "change_manifest.json"),
        ("code_verification_results_path", "verification_results.json"))})
    bundle["pointer"].update(attempt_kind="code_agent", status=values["code_result"]["status"],
        state_paths=paths)
    bundle_head = digest(bundle)
    trace["proof"]["objects"].append(source_object("canonical_json", bundle, version="0.4"))
    index = {"schema_version": "0.1", "case_id": owner["case_id"], "run_id": owner["run_id"],
             "artifact_head": bundle_head, "current": {"code": deepcopy(bundle["pointer"])}}
    index_head = digest(index)
    trace["proof"]["objects"].append(source_object("canonical_json", index, version="0.4"))
    delivery = add("delivery", result_digest=result, terminal_evidence_digest=final)
    trace["events"].append(event("canonical_bundle", run_id=owner["run_id"], attempt_id=owner["attempt_id"],
        external_operation_id=owner["producer_operation_id"], workspace_id=owner["workspace_id"],
        result_digest=result, seal_digest=seal, bundle_digest=bundle_head, binding_digest=delivery, artifact_head=index_head,
        artifacts=[{"slot": "code", "artifact_id": bundle["artifact_id"], "digest": bundle_head, "current": True, "protected": False}],
        outcome=outcome))
    if outcome == "normal":
        spec = {"schema_version": "0.1", **owner, "attempt_id": "attempt_000003", "workspace_id": "analysis_workspace",
                "source_code_attempt_id": owner["attempt_id"], "bundle_digest": bundle_head, "code_digest": result,
                "base_revision": manifest["base_revision"], "effective_tree_digest": manifest["base_tree_digest"]}
        spec["spec_digest"] = digest(spec)
        add_source(trace, "analysis_spec", spec)
        trace["events"].append(event("analysis_preparation_contract", run_id=owner["run_id"], attempt_id=spec["attempt_id"],
            workspace_id=spec["workspace_id"], analysis_spec_digest=spec["spec_digest"], outcome="contract_only"))
    return trace, values


def state_projection_trace(base=None, *, outcome="normal", clock=100):
    """Attach bounded state and a checkpoint copy to the contract trace."""
    trace, values = full_trace(base, outcome=outcome, clock=clock)
    bundle = next(row["value"] for row in trace["proof"]["objects"] if
                  row["kind"] == "canonical_json" and row["value"].get("slot") == "code" and
                  row["value"].get("event") == "registered")
    pointer = deepcopy(bundle["pointer"])
    state = {"schema_version": "0.4", "case_id": bundle["case_id"], "run_id": bundle["run_id"],
             "current_artifacts": {"code": pointer}, **pointer["state_paths"],
             "code_agent_status": values["code_result"]["status"],
             "code_agent_usable": values["code_result"]["usable"]}
    for name, value in (("bounded_state_contract", state),
                        ("checkpoint_copy_contract", {"channel_values": {"control": deepcopy(state)}})):
        head = digest(value)
        trace["proof"]["objects"].append(source_object("canonical_json", value, version="0.4"))
        trace["events"].append(event(name, run_id=bundle["run_id"], binding_digest=head,
                                     outcome="contract_only"))
    return trace, values


def rebind(trace, kind, mutate):
    """Rehash a changed fixture DAG so negative tests reach provenance checks."""
    trace = deepcopy(trace)
    rows = {r["sha256"]: r for r in trace["proof"]["objects"]}
    profiles = {r["source_sha256"]: r["kind"] for r in trace["proof"]["typed_sources"]}
    aliases = {h: h for h in rows}
    for h, profile in profiles.items():
        checksum = CHECKSUMS[profile]
        if checksum:
            aliases[rows[h]["value"][checksum]] = h
    selected = next(h for h in rows if profiles.get(h) == kind or
                    kind == "code_bundle" and rows[h]["value"].get("slot") == "code" and rows[h]["value"].get("event") == "registered" or
                    kind == "bounded_state" and rows[h]["value"].get("schema_version") == "0.4" and "current_artifacts" in rows[h]["value"] or
                    kind == "checkpoint_copy" and "channel_values" in rows[h]["value"] or
                    kind == "control_envelope" and rows[h]["value"].get("operation_type") == "resume_run")
    mutate(rows[selected]["value"])
    done, digests = {}, {}

    def walk(value, current=None, checksum=None, path=()):
        if path == (checksum,):
            return value
        if type(value) is str and value in aliases:
            target = aliases[value]
            build(target)
            return digests[value]
        if type(value) is list:
            return [walk(v, current, checksum, path + (i,)) for i, v in enumerate(value)]
        if type(value) is dict:
            changed = {k: walk(v, current, checksum, path + (k,)) for k, v in value.items()}
            if "canonical_path" in changed and value.get("sha256") in aliases and "size_bytes" in changed and changed["sha256"] != value["sha256"]:
                changed["size_bytes"] = len(canonical_bytes(done[aliases[value["sha256"]]]["value"]))
            return changed
        return value

    def build(head):
        if head in done:
            return
        row = rows[head]
        checksum = CHECKSUMS.get(profiles.get(head))
        if row["kind"] in ("checkpoint_manifest", "historical_checkpoint_manifest_0_3"):
            checksum = "checkpoint_head"
        value = walk(row["value"], head, checksum)
        if checksum:
            logical = digest({k: v for k, v in value.items() if k != checksum})
            digests[row["value"][checksum]] = logical
            value[checksum] = logical
        done[head] = source_object(row["kind"], value, version="0.4")
        digests[head] = done[head]["sha256"]

    for head in rows:
        build(head)
    trace["proof"]["objects"] = [done[h] for h in rows]
    for row in trace["proof"]["typed_sources"]:
        row["source_sha256"] = digests[row["source_sha256"]]
    for row in trace["proof"]["workspace_roots"]:
        row["evidence_digest"] = digests[row["evidence_digest"]]
    trace["events"] = walk(trace["events"])
    return trace
