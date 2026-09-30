"""Source-complete Code fixture for B02 control ordering and B03 ingress tests."""
from hashlib import sha256
from pathlib import Path
import shutil

from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.external_operation import ExternalDispatch, ExternalNormalFinal
from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
from lqcd_agent.code_agent.prestart import CodePrestart
from lqcd_agent.code_agent.workspace import WorkspaceProvider, canonical_patch, immutable_git_tree, seal_workspace
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.pause import PublishPauseRequest, ResumeRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest
from helpers.code_workspace import immutable_base_repository
from test_b03_task_trace_boundary import task_trace_witness


def canonical_source(*, success=False, finalize=True, containment_fault=None):
    repository, base_info = immutable_base_repository()
    witness = task_trace_witness(base_info, control_worker_id="worker")
    task, manifest = witness["task"], witness["manifest"]
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    output = root.parent.parent
    preserved_base = output / "base_repository"
    shutil.copytree(repository, preserved_base)
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    actor = ActorContext("operator", "human", ("control.internal", "resume"))
    plane = ControlPlane(coordinator, worker_id="worker")
    base = immutable_git_tree(preserved_base, task["base_revision"])
    preview = WorkspaceProvider(output / "preview_workspace")
    preview_witness = preview.materialize(manifest, base, lambda: None)
    changed_content = b"def value():\n    return 2\n"
    if success:
        (preview.path(manifest["workspace_id"]) / "sample.py").write_bytes(changed_content)
    spec = task["tool_policy"][0]
    audit_event = {"tool_event_index": 1, "task_id": task["task_id"], "workspace_id": manifest["workspace_id"],
                   "tool_id": spec["spec_id"], "argv_digest": digest(spec["argv"]), "cwd": spec["cwd"],
                   "start_at": 100, "end_at": 100, "status": "completed", "affected_paths": ["sample.py"],
                   "output_digest": digest(""),
                   "resource_usage": {"llm_calls": 0, "tool_calls": 1, "active_seconds": 0}}
    audit = canonical_bytes(audit_event) + b"\n" if success else b""
    stop_proof = {"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
                  "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}
    changes, seal = seal_workspace(preview, task, manifest, preview_witness, base, backend_status="completed",
                                   stop_proof=stop_proof, tool_audit=audit, sealed_at=0, fence=lambda: None)
    patch = canonical_patch(base, preview.verify_sealed(manifest, preview_witness, seal["final_tree_digest"]),
                            changes["changes"]) if success else None
    receipt = FakeCodingBackend._receipt(task, manifest)
    external = {key: task[key] for key in ("case_id", "run_id", "cycle_id", "attempt_id", "transition_id",
                                          "producer_operation_id")}
    external.update(schema_version="0.1", result_id=task["attempt_id"] + ":external_result",
                    task_id=task["task_id"], task_digest=task["task_digest"], workspace_id=manifest["workspace_id"],
                    workspace_manifest_digest=manifest["manifest_digest"], base_revision=task["base_revision"],
                    base_tree_digest=task["base_tree_digest"], coding_backend_kind="fake", backend_version="0.1",
                    provider_operation_reference=None, provider_thread_reference=None,
                    dispatch_receipt_digest=sha256(canonical_bytes(receipt)).hexdigest(),
                    workspace_seal_digest=seal["seal_digest"], change_manifest_digest=changes["change_manifest_digest"],
                    tool_audit_digest=seal["tool_audit_digest"],
                    change_blobs=[{"path": item["path"], "sha256": item["after_sha256"]} for item in changes["changes"]
                                  if item["after_sha256"] is not None],
                    patch_digest=sha256(patch).hexdigest() if patch is not None else None,
                    declared_status="success" if success else "needs_input", backend_verification_claims=[],
                    resource_usage={"llm_calls": 0, "tool_calls": int(success), "verification_commands": 0, "active_seconds": 0},
                    warnings=[], errors=[], failure_evidence=None)
    external["result_digest"] = digest(external)
    producer = task["producer_operation_id"]
    scenario = "success" if success else "needs_input"
    backend = FakeCodingBackend(output / "fake_backend", operation_scenarios={producer: scenario},
                                fixtures={scenario: {"status": "completed", "result": canonical_bytes(external)}},
                                clock=lambda: 100)
    containment = DeterministicContainment(output / "containment",
        fault_by_operation={producer: containment_fault} if containment_fault else None)
    prestart = CodePrestart(coordinator, producer, "host", 1)
    prestart.commit_task(task)
    prestart.commit_manifest(manifest)
    prestart.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
        "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10, config_digest=digest("config"))
    prestart.commit_core()
    prestart.materialize_workspace(preserved_base)
    locator = {key: task[key] for key in ("case_id", "run_id")}
    paused = plane.publish_pause(PublishPauseRequest(locator, "external_result", task["attempt_id"], task["attempt_id"],
        {"kind": "external_result", "producer_operation_id": producer},
        {"actor_type": "human", "scopes": ["resume"]}, "publish-canonical-code"), actor=actor)
    dispatch = ExternalDispatch(coordinator, producer, "host", 1, backend, containment,
                                backend.read_receipt, backend.read_result)
    dispatch.dispatch()
    if success:
        (WorkspaceProvider(output / "code_workspaces").path(manifest["workspace_id"]) / "sample.py").write_bytes(changed_content)
        containment.record_tool(producer)
    dispatch.publish_result_reference()
    if not finalize:
        return coordinator, plane, actor, locator, dispatch, preserved_base, audit, patch
    final = ExternalNormalFinal(dispatch, preserved_base).commit(tool_audit=audit, patch=patch)
    payload = {"producer_operation_id": producer, "external_final_digest": final["terminal_evidence_digest"]}
    request = ResumeRunRequest(locator, paused["result"]["pause_id"], "consume-normal", "external_result", payload,
                               digest(payload))
    return coordinator, plane, actor, locator, request, preserved_base


def needs_input_source():
    return canonical_source(success=False)


def success_source():
    return canonical_source(success=True)


def timeout_prestart_source():
    repository, base_info = immutable_base_repository()
    witness = task_trace_witness(base_info, control_worker_id="worker")
    task, manifest = witness["task"], witness["manifest"]
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    output = root.parent.parent
    preserved_base = output / "base_repository"
    shutil.copytree(repository, preserved_base)
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    actor = ActorContext("operator", "human", ("cancel", "control.internal", "resume"))
    plane = ControlPlane(coordinator, worker_id="worker")
    producer = task["producer_operation_id"]
    prestart = CodePrestart(coordinator, producer, "host", 1)
    prestart.commit_task(task)
    prestart.commit_manifest(manifest)
    prestart.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
        "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10, config_digest=digest("config"))
    prestart.commit_core()
    prestart.materialize_workspace(preserved_base)
    locator = {key: task[key] for key in ("case_id", "run_id")}
    plane.publish_pause(PublishPauseRequest(locator, "external_result", task["attempt_id"], task["attempt_id"],
        {"kind": "external_result", "producer_operation_id": producer},
        {"actor_type": "human", "scopes": ["resume"]}, "publish-timeout-code"), actor=actor)
    backend = FakeCodingBackend(output / "fake_backend", operation_scenarios={producer: "waiting"},
        fixtures={"waiting": {"status": "running", "result": None}}, clock=lambda: 100)
    containment = DeterministicContainment(output / "containment")
    ExternalDispatch(coordinator, producer, "host", 1, backend, containment,
                     backend.read_receipt, backend.read_result).authorize()
    return coordinator, plane, actor, locator, root, task, manifest
