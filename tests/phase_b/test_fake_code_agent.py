"""Durable Fake backend port checks; canonical orchestration is separate."""
from copy import deepcopy
from functools import partial
from hashlib import sha256
import multiprocessing
import os
from pathlib import Path

import pytest

from harness.pytest_evidence import observe, production_hook
from lqcd_agent.code_agent.backend import validate_receipt, validate_result_reference, validate_status
from lqcd_agent.code_agent.artifacts import bundle_members, canonical_result
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.external_operation import CodeExternalStop, CodeWatchdog, ExternalDispatch, ExternalNormalFinal
from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
from lqcd_agent.code_agent.ingress import preflight_result
from lqcd_agent.code_agent.prestart import CodePrestart
from lqcd_agent.code_agent.subgraph import CodeAgentSubgraph
from lqcd_agent.code_agent.verification import TrustedVerifier, build_verification_results
from lqcd_agent.code_agent.workspace import WorkspaceProvider, canonical_patch, immutable_git_tree, seal_workspace
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.pause import CancelPauseRequest, PublishPauseRequest, ResolveExternalInterruptRequest, ResumeRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest
from helpers.code_workspace import immutable_base_repository
from helpers.canonical_code import timeout_prestart_source
from test_b03_task_trace_boundary import immutable_base, task_trace_witness


@pytest.fixture(scope="module")
def canonical_inputs():
    witness = task_trace_witness(immutable_base())
    return witness["task"], witness["manifest"]


def test_fake_backend_exact_dispatch_restart_lookup_and_immutable_result(tmp_path, canonical_inputs):
    task, manifest = canonical_inputs
    operation_id = task["producer_operation_id"]
    content = b'{"declared_status":"success"}'
    backend = FakeCodingBackend(tmp_path / "backend", operation_scenarios={operation_id: "success"},
                                fixtures={"success": {"status": "completed", "result": content}}, clock=lambda: 42)
    assert backend.lookup(operation_id)["status"] == "unknown"
    receipt = backend.dispatch(task, manifest, operation_id)
    assert validate_receipt(receipt, task, manifest).value == receipt
    assert backend.dispatch(task, manifest, operation_id) == receipt
    restarted = FakeCodingBackend(tmp_path / "backend", clock=lambda: 43)
    status = restarted.lookup(operation_id)
    assert validate_status(status).value == status
    assert status["status"] == "completed" and status["receipt_digest"] == sha256(canonical_bytes(receipt)).hexdigest()
    assert restarted.read_receipt(status["receipt_reference"]) == receipt
    reference = restarted.fetch_result(operation_id)
    assert validate_result_reference(reference).value == reference
    assert restarted.read_result(reference) == content
    assert restarted.cancel(operation_id, "operator_cancel")["status"] == "completed"
    observe("b03-construction-backend-lookup", {"kind": "boolean", "value": True},
            sorted(["immutable_receipt_and_result", "lookup_same_operation", "no_provider_budget_authority"]))


def test_fake_backend_rejects_missing_fixture_and_conflicting_dispatch(tmp_path, canonical_inputs):
    task, manifest = canonical_inputs
    operation_id = task["producer_operation_id"]
    absent = FakeCodingBackend(tmp_path / "backend", fixtures={"one": {"status": "running", "result": None}})
    with pytest.raises(ControlIntegrityError):
        absent.dispatch(task, manifest, operation_id)
    first = FakeCodingBackend(tmp_path / "backend", operation_scenarios={operation_id: "one"},
                              fixtures={"one": {"status": "running", "result": None}})
    first.dispatch(task, manifest, operation_id)
    changed = FakeCodingBackend(tmp_path / "backend", operation_scenarios={operation_id: "two"},
                                fixtures={"two": {"status": "completed", "result": b"{}"}})
    with pytest.raises(ControlIntegrityError, match="Conflicting"):
        changed.dispatch(task, manifest, operation_id)
    with pytest.raises(ControlIntegrityError):
        first.fetch_result(operation_id)
    observe("b03-construction-dispatch-conflict", {"kind": "boolean", "value": True},
            sorted(["duplicate_dispatch_exact", "conflicting_dispatch_rejected", "unknown_result_rejected"]))


def test_fake_backend_cancel_is_exact_and_does_not_dispatch(tmp_path, canonical_inputs):
    task, manifest = canonical_inputs
    operation_id = task["producer_operation_id"]
    backend = FakeCodingBackend(tmp_path / "backend", operation_scenarios={operation_id: "waiting"},
                                fixtures={"waiting": {"status": "running", "result": None}}, clock=lambda: 3)
    assert backend.cancel(operation_id, "operator_cancel")["status"] == "unknown"
    assert backend.lookup(operation_id)["receipt_reference"] is None
    backend.dispatch(task, manifest, operation_id)
    assert backend.cancel(operation_id, "operator_cancel")["status"] == "cancelled"
    assert backend.cancel(operation_id, "operator_cancel")["status"] == "cancelled"
    with pytest.raises(ControlIntegrityError, match="Conflicting"):
        backend.cancel(operation_id, "hard_limit")
    with pytest.raises(ControlIntegrityError):
        backend.fetch_result(operation_id)


def test_fake_backend_receipt_and_status_tamper_fail_closed(tmp_path, canonical_inputs):
    task, manifest = canonical_inputs
    operation_id = task["producer_operation_id"]
    backend = FakeCodingBackend(tmp_path / "backend", operation_scenarios={operation_id: "success"},
                                fixtures={"success": {"status": "completed", "result": b"{}"}}, clock=lambda: 0)
    receipt = backend.dispatch(task, manifest, operation_id)
    changed = deepcopy(receipt)
    changed["task_digest"] = manifest["manifest_digest"]
    with pytest.raises(ControlIntegrityError):
        validate_receipt(changed, task, manifest)
    status = backend.lookup(operation_id)
    status["status"] = "unknown"
    with pytest.raises(ControlIntegrityError):
        validate_status(status)


def _fresh_receipt_reader(pipe, output, operation_id):
    output = Path(output)
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    backend = FakeCodingBackend(output / "fake_backend", clock=lambda: 102)
    containment = DeterministicContainment(output / "containment")
    try:
        receipt = ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                                   backend.read_receipt, backend.read_result).dispatch()
        pipe.send({"receipt": receipt, "status": backend.lookup(operation_id)})
    finally:
        coordinator.close()
        pipe.close()


def test_dispatch_requires_public_pause_and_recovers_only_original_receipt():
    repository, base = immutable_base_repository()
    witness = task_trace_witness(base)
    task, manifest = witness["task"], witness["manifest"]
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(100, 0))
    operation_id = task["producer_operation_id"]
    backend_root = root.parent.parent / "fake_backend"
    backend = FakeCodingBackend(backend_root, operation_scenarios={operation_id: "success"},
                                fixtures={"success": {"status": "completed", "result": b"{}"}}, clock=lambda: 100)
    containment = DeterministicContainment(root.parent.parent / "containment")
    try:
        service = CodePrestart(coordinator, operation_id, "host", 1)
        service.commit_task(task)
        service.commit_manifest(manifest)
        service.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
            "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10, config_digest=digest("config"))
        service.commit_core()
        service.materialize_workspace(repository)
        dispatch = ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                                    backend.read_receipt, backend.read_result)
        with pytest.raises(ControlIntegrityError):
            dispatch.dispatch()
        assert backend.lookup(operation_id)["status"] == "unknown"
        locator = {key: task[key] for key in ("case_id", "run_id")}
        target = task["attempt_id"]
        paused = ControlPlane(coordinator, worker_id="host").publish_pause(
            PublishPauseRequest(locator, "external_result", target, target,
                {"kind": "external_result", "producer_operation_id": operation_id},
                {"actor_type": "human", "scopes": ["resume"]}, "publish-backend-test"),
            actor=ActorContext("operator", "human", ("control.internal",)))
        assert paused["run_status"] == "paused"
        receipt = dispatch.dispatch()
        assert dispatch.dispatch() == receipt
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=_fresh_receipt_reader, args=(child, str(root.parent.parent), operation_id))
        try:
            process.start()
            child.close()
            process.join(20)
            assert process.exitcode == 0 and parent.poll(2)
            recovered = parent.recv()
            assert recovered["receipt"] == receipt and recovered["status"]["status"] == "completed"
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
        result_reference = dispatch.publish_result_reference()
        assert dispatch.publish_result_reference() == result_reference
        with pytest.raises(ControlIntegrityError):
            ExternalDispatch(coordinator, operation_id, "host", 2, backend, containment,
                             backend.read_receipt, backend.read_result).dispatch()
    finally:
        coordinator.close()
    reopened = Coordinator(root.parent.parent, clock=FakeClock(100, 0))
    original = FakeCodingBackend(backend_root, clock=lambda: 101)
    try:
        continued = ExternalDispatch(reopened, operation_id, "host", 1, original, containment,
                                     original.read_receipt, original.read_result)
        assert continued.publish_result_reference() == result_reference
    finally:
        reopened.close()
    observe("b03-construction-dispatch-recovery", {"kind": "boolean", "value": True},
            sorted(["public_pause_before_dispatch", "same_receipt_after_restart", "stale_epoch_fenced"]))


@pytest.mark.parametrize("fail_stop", [False, True])
def test_host_normal_final_requires_exact_seal_and_is_single_winner(tmp_path, fail_stop):
    repository, base_info = immutable_base_repository()
    witness = task_trace_witness(base_info)
    task, manifest = witness["task"], witness["manifest"]
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(100, 0))
    operation_id = task["producer_operation_id"]
    base = immutable_git_tree(repository, task["base_revision"])
    preview = WorkspaceProvider(tmp_path / "preview")
    preview_witness = preview.materialize(manifest, base, lambda: None)
    stop_proof = {"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
                  "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}
    changes, seal = seal_workspace(preview, task, manifest, preview_witness, base, backend_status="completed",
                                   stop_proof=stop_proof, tool_audit=b"", sealed_at=0, fence=lambda: None)
    receipt = FakeCodingBackend._receipt(task, manifest)
    result = {key: task[key] for key in ("case_id", "run_id", "cycle_id", "attempt_id", "transition_id",
                                          "producer_operation_id")}
    result.update(schema_version="0.1", result_id=task["attempt_id"] + ":external_result",
                  task_id=task["task_id"], task_digest=task["task_digest"], workspace_id=manifest["workspace_id"],
                  workspace_manifest_digest=manifest["manifest_digest"], base_revision=task["base_revision"],
                  base_tree_digest=task["base_tree_digest"], coding_backend_kind="fake", backend_version=task["backend_version"],
                  provider_operation_reference=None, provider_thread_reference=None,
                  dispatch_receipt_digest=sha256(canonical_bytes(receipt)).hexdigest(),
                  workspace_seal_digest=seal["seal_digest"], change_manifest_digest=changes["change_manifest_digest"],
                  tool_audit_digest=seal["tool_audit_digest"], change_blobs=[], patch_digest=None,
                  declared_status="needs_input", backend_verification_claims=[],
                  resource_usage={"llm_calls": 0, "tool_calls": 0, "verification_commands": 0, "active_seconds": 0},
                  warnings=[], errors=[], failure_evidence=None)
    result["result_digest"] = digest(result)
    backend = FakeCodingBackend(root.parent.parent / "fake_backend", operation_scenarios={operation_id: "needs_input"},
                                fixtures={"needs_input": {"status": "completed", "result": canonical_bytes(result)}},
                                clock=lambda: 100)
    containment = DeterministicContainment(root.parent.parent / "containment",
        fault_by_operation={operation_id: {"kill_all": False}} if fail_stop else None)
    try:
        service = CodePrestart(coordinator, operation_id, "host", 1)
        service.commit_task(task)
        service.commit_manifest(manifest)
        service.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
            "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10, config_digest=digest("config"))
        service.commit_core()
        service.materialize_workspace(repository)
        locator = {key: task[key] for key in ("case_id", "run_id")}
        plane = ControlPlane(coordinator, worker_id="host")
        paused = plane.publish_pause(PublishPauseRequest(locator, "external_result", task["attempt_id"], task["attempt_id"],
            {"kind": "external_result", "producer_operation_id": operation_id},
            {"actor_type": "human", "scopes": ["resume"]}, "publish-normal-final-test"),
            actor=ActorContext("operator", "human", ("control.internal", "resume")))
        dispatch = ExternalDispatch(coordinator, operation_id, "host", 1, backend, containment,
                                    backend.read_receipt, backend.read_result)
        dispatch.dispatch()
        dispatch.publish_result_reference()
        finalizer = ExternalNormalFinal(dispatch, repository)
        committed = finalizer.commit(tool_audit=b"", patch=None)
        if fail_stop:
            assert committed["operation_status"] == "recovery_required" and committed["terminal_closure"] == "unavailable"
            value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, operation_id)
            assert value["resolution_owner"] == "interrupt" and proof["proof_kind"] == "unavailable"
            assert finalizer.commit(tool_audit=b"", patch=None) == committed
            observe("b03-construction-unavailable-final", {"kind": "boolean", "value": True},
                    sorted(["unavailable_candidate_reclassified", "normal_cas_not_won", "same_final_evidence"]))
            return
        assert committed["resolution_owner"] == "normal"
        verified, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, operation_id)
        assert verified == committed and proof["proof_kind"] == "safe_stop"
        delivery = CodeAgentSubgraph(coordinator, repository).preflight_delivery(
            {"tag": "normal_final", "value": verified, "final": proof})
        assert delivery[8].value["declared_status"] == "needs_input"
        patch_path = root / "code_agent_control" / task["attempt_id"] / "changes.patch"
        patch_path.symlink_to("missing.patch")
        with pytest.raises(ControlIntegrityError, match="symlink"):
            CodeAgentSubgraph(coordinator, repository).preflight_delivery(
                {"tag": "normal_final", "value": verified, "final": proof})
        with pytest.raises(ControlIntegrityError, match="symlink"):
            finalizer.commit(tool_audit=b"", patch=None)
        patch_path.unlink()
        directory = patch_path.parent
        moved = directory.with_name(directory.name + "_moved")
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        try:
            with pytest.raises(ControlIntegrityError, match="directory escaped"):
                CodeAgentSubgraph(coordinator, repository).preflight_delivery(
                    {"tag": "normal_final", "value": verified, "final": proof})
        finally:
            directory.unlink()
            moved.rename(directory)
        assert finalizer.commit(tool_audit=b"", patch=None) == committed
        with pytest.raises(ControlIntegrityError, match="replay changed"):
            finalizer.commit(tool_audit=b"forged\n", patch=None)
        with pytest.raises(ControlIntegrityError):
            dispatch.publish_result_reference()
        plane.resume_target_adapter = plane.external_adapter = CodeAgentSubgraph(coordinator, repository)
        payload = {"producer_operation_id": operation_id, "external_final_digest": committed["terminal_evidence_digest"]}
        request = ResumeRunRequest(locator, paused["result"]["pause_id"], "tampered-code-preclaim",
                                   "external_result", payload, digest(payload))
        seal_path = root / "code_agent_control" / task["attempt_id"] / "workspace_seal.json"
        seal_path.write_bytes(b"{}")
        with pytest.raises(ControlIntegrityError):
            plane.resume_run(request, actor=ActorContext("operator", "human", ("control.internal", "resume")))
        assert coordinator.lookup_key("public_control", "tampered-code-preclaim") is None
        observe("b03-construction-normal-final", {"kind": "boolean", "value": True},
                sorted(["request_owned_safe_stop", "one_final_evidence", "preclaim_tamper_rejected"]))
    finally:
        coordinator.close()


@pytest.mark.parametrize("start_witness,safe", [(False, True), (True, False)])
def test_host_timeout_stop_uses_containment_witness_and_original_owner(start_witness, safe):
    coordinator, plane, actor, locator, root, task, manifest = timeout_prestart_source()
    producer = task["producer_operation_id"]
    backend = FakeCodingBackend(coordinator.root / "fake_backend", clock=lambda: 100)
    containment = DeterministicContainment(coordinator.root / "containment",
        fault_by_operation={producer: {"kill_all": False}} if start_witness else None)
    if start_witness:
        containment.start(producer, manifest["workspace_id"])
    plane.external_adapter = CodeExternalStop(coordinator, backend, containment, backend.read_receipt)
    trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
    (root / "timeout_trigger.json").write_bytes(canonical_bytes(trigger))
    request = ResolveExternalInterruptRequest(locator, producer, "operation_timeout", "timeout_trigger.json", digest(trigger))
    try:
        result = plane.resolve_external_interrupt(request, actor=actor)
        assert result["operation_status"] == ("committed" if safe else "recovery_required")
        assert result["terminal_closure"] == ("not_applicable" if safe else "unavailable")
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["resolution_owner"] == "interrupt" and value["proof_kind"] == ("safe_stop" if safe else "unavailable")
        assert proof["stop_proof"]["termination_or_not_dispatched"] == (
            {"tag": "not_dispatched"} if safe else "unknown")
        assert plane.resolve_external_interrupt(request, actor=actor) == result
    finally:
        coordinator.close()


@pytest.mark.parametrize("fault,dimension", [
    ("kill_all", "verify_empty"),
    ("bounded_drain", "bounded_drain"),
    ("post_stop_stability", "post_stop_stability"),
])
def test_host_timeout_containment_gap_is_unavailable(fault, dimension):
    coordinator, plane, actor, locator, root, task, manifest = timeout_prestart_source()
    producer = task["producer_operation_id"]
    backend = FakeCodingBackend(coordinator.root / "fake_backend", clock=lambda: 100)
    containment = DeterministicContainment(coordinator.root / "containment",
        fault_by_operation={producer: {fault: False}})
    containment.start(producer, manifest["workspace_id"])
    plane.external_adapter = CodeExternalStop(coordinator, backend, containment, backend.read_receipt)
    trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
    (root / "timeout_gap_trigger.json").write_bytes(canonical_bytes(trigger))
    request = ResolveExternalInterruptRequest(locator, producer, "operation_timeout",
                                             "timeout_gap_trigger.json", digest(trigger))
    try:
        result = plane.resolve_external_interrupt(request, actor=actor)
        assert result["operation_status"] == "recovery_required" and result["terminal_closure"] == "unavailable"
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["proof_kind"] == proof["proof_kind"] == "unavailable"
        assert proof["stop_proof"][dimension] is False and dimension in proof["missing_proof_dimensions"]
        assert plane.resolve_external_interrupt(request, actor=actor) == result
    finally:
        coordinator.close()


def test_host_timeout_stops_original_dispatched_backend_without_redispatch():
    coordinator, plane, actor, locator, root, task, manifest = timeout_prestart_source()
    producer = task["producer_operation_id"]
    backend = FakeCodingBackend(coordinator.root / "fake_backend",
        operation_scenarios={producer: "waiting"}, fixtures={"waiting": {"status": "running", "result": None}},
        clock=lambda: 100)
    containment = DeterministicContainment(coordinator.root / "containment")
    containment.start(producer, manifest["workspace_id"])
    receipt = backend.dispatch(task, manifest, producer)
    plane.external_adapter = CodeExternalStop(coordinator, backend, containment, backend.read_receipt)
    trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
    (root / "timeout_trigger.json").write_bytes(canonical_bytes(trigger))
    request = ResolveExternalInterruptRequest(locator, producer, "operation_timeout", "timeout_trigger.json", digest(trigger))
    try:
        result = plane.resolve_external_interrupt(request, actor=actor)
        assert result["operation_status"] == "committed" and result["terminal_closure"] == "not_applicable"
        assert backend.lookup(producer)["status"] == "cancelled"
        assert backend.read_receipt("fake-receipt:" + producer) == receipt
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert proof["stop_proof"]["termination_or_not_dispatched"] == "confirmed"
        assert value["dispatch_receipt_reference"] is None and value["resolution_owner"] == "interrupt"
        assert plane.resolve_external_interrupt(request, actor=actor) == result
    finally:
        coordinator.close()


def test_host_cancel_uses_original_resolution_and_stops_before_dispatch():
    coordinator, plane, actor, locator, root, task, _ = timeout_prestart_source()
    producer = task["producer_operation_id"]
    backend = FakeCodingBackend(coordinator.root / "fake_backend", clock=lambda: 100)
    containment = DeterministicContainment(coordinator.root / "containment")
    plane.external_adapter = CodeExternalStop(coordinator, backend, containment, backend.read_receipt)
    request = CancelPauseRequest(locator, "pause_000001", "cancel-host-code", "operator_cancel")
    try:
        result = plane.cancel_pause(request, actor=actor)
        assert result["operation_status"] == "committed" and result["terminal_closure"] == "committed"
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["resolution_owner"] == "cancel" and proof["stop_proof"]["termination_or_not_dispatched"] == {"tag": "not_dispatched"}
        assert backend.lookup(producer)["status"] == "unknown"
        assert plane.cancel_pause(request, actor=actor) == result
    finally:
        coordinator.close()
    observe("b03-construction-host-cancel", {"kind": "boolean", "value": True},
            sorted(["typed_cancel_intent", "original_producer_owner", "no_backend_dispatch"]))


def _host_resolution_client(pipe, output, locator, producer, action):
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0))
    backend = FakeCodingBackend(coordinator.root / "fake_backend", clock=lambda: 100)
    containment = DeterministicContainment(coordinator.root / "containment")
    plane = ControlPlane(coordinator, worker_id="host-" + action)
    plane.external_adapter = CodeExternalStop(coordinator, backend, containment, backend.read_receipt)
    actor = ActorContext("operator", "human", ("cancel", "control.internal", "resume"))
    try:
        pipe.send("ready")
        assert pipe.recv() == "go"
        try:
            if action == "cancel":
                result = plane.cancel_pause(CancelPauseRequest(locator, "pause_000001", "cancel-host-race", "operator_cancel"), actor=actor)
            else:
                result = plane.resolve_external_interrupt(ResolveExternalInterruptRequest(locator, producer,
                    "terminal_operator_stop", "host_race_trigger.json", digest({"run_locator": locator,
                    "producer_operation_id": producer, "reason": "terminal_operator_stop"})), actor=actor)
            pipe.send({"result": result})
        except ControlIntegrityError as error:
            pipe.send({"rejected": str(error)})
    finally:
        coordinator.close()
        pipe.close()


@pytest.mark.parametrize("ordering", [("cancel", "interrupt"), ("interrupt", "cancel")])
def test_host_cancel_interrupt_two_processes_preserve_one_resolution(ordering):
    coordinator, _, _, locator, root, task, _ = timeout_prestart_source()
    producer = task["producer_operation_id"]
    trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "terminal_operator_stop"}
    (root / "host_race_trigger.json").write_bytes(canonical_bytes(trigger))
    context = multiprocessing.get_context("spawn")
    clients = {}
    try:
        for action in ordering:
            parent, child = context.Pipe()
            process = context.Process(target=_host_resolution_client,
                args=(child, str(coordinator.root), locator, producer, action))
            process.start()
            child.close()
            clients[action] = (process, parent)
            assert parent.poll(30) and parent.recv() == "ready"
        results = {}
        for action in ordering:
            _, pipe = clients[action]
            pipe.send("go")
            assert pipe.poll(30)
            results[action] = pipe.recv()
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["resolution_owner"] == ordering[0] and proof["proof_kind"] == "safe_stop"
        assert value["resolution_owner_operation_id"] == results[ordering[0]]["result"]["operation_id"]
        assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(producer)["status"] == "unknown"
        assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 1
        records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        assert sum(row["record_type"] == "budget" and row["event"] == "resource_settled" and
                   row["payload"]["resource_operation_id"] == value["reservation_id"] for row in records) == 1
    finally:
        for process, pipe in clients.values():
            if process.is_alive():
                process.kill()
                process.join()
            pipe.close()
        coordinator.close()
    observe("b03-construction-resolution-race", {"kind": "boolean", "value": True},
            sorted(["one_resolution_winner", "one_terminal_closure", "one_resource_settlement"]))


def _host_timeout_process(pipe, output, request, crash_phase, hook_request=None, crash_side="after"):
    def observer(name, side, value):
        selected = (crash_phase if crash_phase is not None and crash_phase.startswith("external.") else
                    "control.resolve_external_interrupt.recoverable_timeout." + str(crash_phase))
        if crash_phase is not None and name == selected and side == crash_side:
            os._exit(97)
    if hook_request is not None:
        observer.production_hooks = {(crash_phase, crash_side):
            (partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0), observer=observer)
    backend = FakeCodingBackend(coordinator.root / "fake_backend", clock=lambda: 100)
    containment = DeterministicContainment(coordinator.root / "containment")
    plane = ControlPlane(coordinator, worker_id="host")
    plane.external_adapter = CodeExternalStop(coordinator, backend, containment, backend.read_receipt)
    actor = ActorContext("operator", "human", ("cancel", "control.internal", "resume"))
    try:
        result = plane.resolve_external_interrupt(ResolveExternalInterruptRequest(**request), actor=actor)
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


@pytest.mark.parametrize("crash_phase", ["interrupt_and_pause_ownership_reserved",
    "external.termination_evidence_committed", "external.external_final_evidence_committed",
    "canonical_failed_delivery_committed"])
def test_host_timeout_process_restart_keeps_original_stop_and_delivery(crash_phase):
    from dataclasses import asdict
    coordinator, _, _, locator, root, task, _ = timeout_prestart_source()
    producer = task["producer_operation_id"]
    trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
    (root / "timeout_trigger.json").write_bytes(canonical_bytes(trigger))
    request = asdict(ResolveExternalInterruptRequest(locator, producer, "operation_timeout", "timeout_trigger.json", digest(trigger)))
    context = multiprocessing.get_context("spawn")
    try:
        frozen = None
        for cut in (crash_phase, None):
            parent, child = context.Pipe()
            process = context.Process(target=_host_timeout_process, args=(child, str(coordinator.root), request, cut))
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == (97 if cut else 0)
                if cut == "canonical_failed_delivery_committed":
                    frozen = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)[0]["terminal_evidence_digest"]
                if cut is None:
                    assert parent.poll(2)
                    result = parent.recv()
                    assert result["operation_status"] == "committed" and result["terminal_closure"] == "not_applicable"
            finally:
                if process.is_alive():
                    process.kill()
                    process.join()
                parent.close()
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["terminal_evidence_digest"] == (frozen or value["terminal_evidence_digest"])
        assert proof["stop_proof"]["termination_or_not_dispatched"] == {"tag": "not_dispatched"}
        assert FakeCodingBackend(coordinator.root / "fake_backend").lookup(producer)["status"] == "unknown"
    finally:
        coordinator.close()
    observe("b03-construction-timeout-restart", {"kind": "boolean", "value": True},
            sorted(["crash_recovers_original_stop", "no_redispatch", "same_terminal_evidence"]))


def test_watchdog_fences_original_backend_at_trusted_timeout():
    coordinator, _, _, locator, root, task, _ = timeout_prestart_source()
    producer = task["producer_operation_id"]
    backend = FakeCodingBackend(coordinator.root / "fake_backend", clock=lambda: 100)
    containment = DeterministicContainment(coordinator.root / "containment")
    watchdog = CodeWatchdog(coordinator, backend, containment, backend.read_receipt)
    try:
        assert watchdog.inspect(producer) is None
        coordinator.clock.advance(10)
        assert watchdog.inspect(producer) == "operation_timeout"
        result = watchdog.enforce(producer)
        assert result["operation_status"] == "committed" and result["terminal_closure"] == "not_applicable"
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["lease_epoch"] == 2 and value["resolution_owner"] == "interrupt"
        assert proof["stop_proof"]["termination_or_not_dispatched"] == {"tag": "not_dispatched"}
        assert backend.lookup(producer)["status"] == "unknown"
        assert watchdog.enforce(producer) == result
    finally:
        coordinator.close()
    observe("b03-construction-watchdog", {"kind": "boolean", "value": True},
            sorted(["trusted_deadline", "fenced_interrupt", "exact_backend_operation"]))


def _watchdog_process(pipe, output, producer, crash_phase):
    def observer(name, side, value):
        if crash_phase is not None and name == "control.resolve_external_interrupt.recoverable_timeout." + crash_phase and side == "after":
            os._exit(97)
    coordinator = Coordinator(Path(output), clock=FakeClock(110, 10), observer=observer)
    backend = FakeCodingBackend(coordinator.root / "fake_backend", clock=lambda: 110)
    containment = DeterministicContainment(coordinator.root / "containment")
    try:
        result = CodeWatchdog(coordinator, backend, containment, backend.read_receipt).enforce(producer)
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


@pytest.mark.parametrize("crash_phase", ["operation_reserved", "interrupt_and_pause_ownership_reserved"])
def test_watchdog_restart_resumes_same_interrupt_owner(crash_phase):
    coordinator, _, _, _, _, task, _ = timeout_prestart_source()
    producer = task["producer_operation_id"]
    context = multiprocessing.get_context("spawn")
    try:
        for cut in (crash_phase, None):
            parent, child = context.Pipe()
            process = context.Process(target=_watchdog_process, args=(child, str(coordinator.root), producer, cut))
            try:
                process.start()
                child.close()
                process.join(30)
                assert process.exitcode == (97 if cut else 0)
                if cut is None:
                    assert parent.poll(2)
                    result = parent.recv()
                    assert result["operation_status"] == "committed" and result["terminal_closure"] == "not_applicable"
            finally:
                if process.is_alive():
                    process.kill()
                    process.join()
                parent.close()
        value, proof = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
        assert value["lease_epoch"] == 2 and value["resolution_owner_operation_id"] == result["operation_id"]
        assert proof["stop_proof"]["termination_or_not_dispatched"] == {"tag": "not_dispatched"}
    finally:
        coordinator.close()


def test_deterministic_containment_proves_stop_after_restart(tmp_path):
    root = tmp_path / "containment"
    first = DeterministicContainment(root)
    first.start("external_one", "workspace_one")
    first.record_tool("external_one")
    first.revoke_writes("external_one")
    first.terminate("external_one")
    restarted = DeterministicContainment(root)
    restarted.kill_all("external_one")
    restarted.drain("external_one")
    assert restarted.proof("external_one") == {
        "termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
        "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}
    with pytest.raises(ControlIntegrityError):
        restarted.record_tool("external_one")
    with pytest.raises(ControlIntegrityError):
        restarted.start("external_one", "workspace_two")
    observe("b03-construction-containment", {"kind": "boolean", "value": True},
            sorted(["kill_all_and_drain", "write_lease_revoked", "restart_safe_stop_proof"]))


@pytest.mark.parametrize("fault,dimension", [("kill_all", "verify_empty"),
    ("bounded_drain", "bounded_drain"), ("post_stop_stability", "post_stop_stability")])
def test_deterministic_containment_faults_never_claim_safe_stop(tmp_path, fault, dimension):
    fixture = DeterministicContainment(tmp_path / "containment", fault_by_operation={"external_one": {fault: False}})
    fixture.start("external_one", "workspace_one")
    fixture.revoke_writes("external_one")
    fixture.terminate("external_one")
    fixture.kill_all("external_one")
    fixture.drain("external_one")
    proof = DeterministicContainment(tmp_path / "containment").proof("external_one")
    assert proof[dimension] is False
    assert not (proof["termination_or_not_dispatched"] == "confirmed" and all(
        value is True for name, value in proof.items() if name != "termination_or_not_dispatched"))


def test_host_seal_uses_complete_workspace_tree_and_stop_proof(tmp_path):
    repository, base_info = immutable_base_repository()
    witness = task_trace_witness(base_info)
    task, manifest = witness["task"], witness["manifest"]
    base = immutable_git_tree(repository, task["base_revision"])
    provider = WorkspaceProvider(tmp_path / "workspaces")
    identity = provider.materialize(manifest, base, lambda: None)
    containment = DeterministicContainment(tmp_path / "containment")
    operation_id = task["producer_operation_id"]
    containment.start(operation_id, manifest["workspace_id"])
    with pytest.raises(ControlIntegrityError):
        seal_workspace(provider, task, manifest, identity, base, backend_status="completed",
                       stop_proof=containment.proof(operation_id), tool_audit=b"", sealed_at=101, fence=lambda: None)
    containment.revoke_writes(operation_id)
    containment.terminate(operation_id)
    containment.kill_all(operation_id)
    containment.drain(operation_id)
    changes, seal = seal_workspace(provider, task, manifest, identity, base, backend_status="completed",
                                   stop_proof=containment.proof(operation_id), tool_audit=b"", sealed_at=101,
                                   fence=lambda: None)
    assert changes["changes"] == [] and seal["final_tree_digest"] == task["base_tree_digest"]
    (provider.path(manifest["workspace_id"]) / "sample.py").write_bytes(b"changed after seal\n")
    with pytest.raises(ControlIntegrityError):
        provider.verify_sealed(manifest, identity, seal["final_tree_digest"])


def _delivery(tmp_path, *, changed=False):
    repository, base_info = immutable_base_repository()
    witness = task_trace_witness(base_info)
    task, manifest = witness["task"], witness["manifest"]
    base = immutable_git_tree(repository, task["base_revision"])
    provider = WorkspaceProvider(tmp_path / "workspaces")
    workspace_witness = provider.materialize(manifest, base, lambda: None)
    backend = FakeCodingBackend(tmp_path / "backend", operation_scenarios={task["producer_operation_id"]: "no_change"},
                                fixtures={"no_change": {"status": "completed", "result": b"{}"}})
    receipt = backend.dispatch(task, manifest, task["producer_operation_id"])
    containment = DeterministicContainment(tmp_path / "containment")
    containment.start(task["producer_operation_id"], manifest["workspace_id"])
    audit = b""
    if changed:
        (provider.path(manifest["workspace_id"]) / "sample.py").write_bytes(b"value = 2\n")
        containment.record_tool(task["producer_operation_id"])
        spec = task["tool_policy"][0]
        audit_event = {"tool_event_index": 1, "task_id": task["task_id"], "workspace_id": manifest["workspace_id"],
                       "tool_id": spec["spec_id"], "argv_digest": digest(spec["argv"]), "cwd": spec["cwd"],
                       "start_at": 100, "end_at": 101, "status": "completed", "affected_paths": ["sample.py"],
                       "output_digest": digest(""),
                       "resource_usage": {"llm_calls": 0, "tool_calls": 1, "active_seconds": 1}}
        audit = canonical_bytes(audit_event) + b"\n"
    containment.revoke_writes(task["producer_operation_id"])
    containment.terminate(task["producer_operation_id"])
    containment.kill_all(task["producer_operation_id"])
    containment.drain(task["producer_operation_id"])
    changes, seal = seal_workspace(provider, task, manifest, workspace_witness, base,
                                   backend_status="completed", stop_proof=containment.proof(task["producer_operation_id"]),
                                   tool_audit=audit, sealed_at=101, fence=lambda: None)
    final = provider.verify_sealed(manifest, workspace_witness, seal["final_tree_digest"])
    patch = canonical_patch(base, final, changes["changes"]) if changed else None
    result = {key: task[key] for key in ("case_id", "run_id", "cycle_id", "attempt_id", "transition_id",
                                          "producer_operation_id")}
    result.update(schema_version="0.1", result_id=task["attempt_id"] + ":external_result",
                  task_id=task["task_id"], task_digest=task["task_digest"], workspace_id=manifest["workspace_id"],
                  workspace_manifest_digest=manifest["manifest_digest"], base_revision=task["base_revision"],
                  base_tree_digest=task["base_tree_digest"], coding_backend_kind=task["coding_backend_kind"],
                  backend_version=task["backend_version"], provider_operation_reference=None,
                  provider_thread_reference=None, dispatch_receipt_digest=sha256(canonical_bytes(receipt)).hexdigest(),
                  workspace_seal_digest=seal["seal_digest"], change_manifest_digest=changes["change_manifest_digest"],
                  tool_audit_digest=seal["tool_audit_digest"],
                  change_blobs=[{"path": item["path"], "sha256": item["after_sha256"]} for item in changes["changes"]
                                if item["after_sha256"] is not None],
                  patch_digest=sha256(patch).hexdigest() if patch is not None else None,
                  declared_status="success" if changed else "no_change", backend_verification_claims=[],
                  resource_usage={"llm_calls": 0, "tool_calls": int(changed), "verification_commands": 0,
                                  "active_seconds": int(changed)},
                  warnings=[], errors=[], failure_evidence=None)
    result["result_digest"] = digest(result)
    return task, manifest, receipt, seal, changes, provider, workspace_witness, base, result, audit, patch


def test_ingress_preflight_binds_host_seal_and_rejects_rehashed_foreign_result(tmp_path):
    task, manifest, receipt, seal, changes, provider, witness, base, result, audit, patch = _delivery(tmp_path)
    args = (task, manifest, receipt, seal, changes, audit, patch, provider, witness, base)
    assert preflight_result(canonical_bytes(result), *args).value == result
    altered = deepcopy(result)
    altered["attempt_id"] = "attempt_foreign"
    altered["result_digest"] = digest({key: value for key, value in altered.items() if key != "result_digest"})
    with pytest.raises(ControlIntegrityError, match="target"):
        preflight_result(canonical_bytes(altered), *args)
    (provider.path(manifest["workspace_id"]) / "sample.py").write_bytes(b"value = 99\n")
    with pytest.raises(ControlIntegrityError):
        preflight_result(canonical_bytes(result), *args)
    observe("b03-construction-ingress", {"kind": "boolean", "value": True},
            sorted(["foreign_attempt_rejected", "post_seal_change_rejected", "validated_delivery_only"]))


def test_ingress_success_requires_exact_host_patch_and_tool_audit(tmp_path):
    task, manifest, receipt, seal, changes, provider, witness, base, result, audit, patch = _delivery(tmp_path, changed=True)
    args = (task, manifest, receipt, seal, changes, audit, patch, provider, witness, base)
    assert preflight_result(canonical_bytes(result), *args).value == result
    tampered = b"--- a/sample.py\n+++ b/sample.py\n@@ forged @@\n"
    altered = deepcopy(result)
    altered["patch_digest"] = sha256(tampered).hexdigest()
    altered["result_digest"] = digest({key: value for key, value in altered.items() if key != "result_digest"})
    with pytest.raises(ControlIntegrityError, match="Patch"):
        preflight_result(canonical_bytes(altered), task, manifest, receipt, seal, changes, audit, tampered,
                         provider, witness, base)
    with pytest.raises(ControlIntegrityError):
        preflight_result(canonical_bytes(result), task, manifest, receipt, seal, changes, b"", patch,
                         provider, witness, base)


def test_trusted_verifier_uses_fresh_tree_and_fixed_command_registry(tmp_path):
    task, manifest, receipt, seal, changes, provider, witness, base, result, audit, patch = _delivery(tmp_path, changed=True)
    preflight_result(canonical_bytes(result), task, manifest, receipt, seal, changes, audit, patch,
                     provider, witness, base)
    final = provider.verify_sealed(manifest, witness, seal["final_tree_digest"])
    verifier = TrustedVerifier(tmp_path / "verification")
    checked_task, fresh_manifest, fresh_witness, effective = verifier.prepare(task, base, final, lambda: None)
    root = verifier.provider.verify_identity(fresh_manifest, fresh_witness)
    assert root != provider.path(manifest["workspace_id"]) and effective == final
    spec = task["verification_specs"][0]
    command = verifier._command(checked_task, spec)
    assert command is not None
    assert verifier._run_command(root, spec, command, effective)["status"] == "passed"
    with pytest.raises(ControlIntegrityError, match="durable resource port"):
        verifier.execute(checked_task, fresh_manifest, fresh_witness, effective, spec, port=None)
    blocked = deepcopy(spec)
    blocked["argv"] = ["python", "-c", "import socket"]
    assert verifier._command(checked_task, blocked) is None
    absent = verifier.verify_all(task, base, final, candidate_status="needs_input", fence=lambda: None, port=None)
    assert absent["all_required_passed"] is False and absent["spec_results"][0]["status"] == "not_run"
    with pytest.raises(ControlIntegrityError, match="durable resource port"):
        verifier.verify_all(task, base, final, candidate_status="success", fence=lambda: None, port=None)
    with pytest.raises(ControlIntegrityError):
        build_verification_results(task, [])
    observe("b03-construction-trusted-verification", {"kind": "boolean", "value": True},
            sorted(["fresh_verification_tree", "fixed_command_registry", "backend_claim_not_authority"]))


def test_canonical_bundle_requires_trusted_verifier_and_conditional_patch(tmp_path):
    task, manifest, receipt, seal, changes, provider, witness, base, external, audit, patch = _delivery(tmp_path, changed=True)
    validated = preflight_result(canonical_bytes(external), task, manifest, receipt, seal, changes, audit, patch,
                                 provider, witness, base)
    final = provider.verify_sealed(manifest, witness, seal["final_tree_digest"])
    verifier = TrustedVerifier(tmp_path / "verification")
    checked_task, fresh_manifest, fresh_witness, effective = verifier.prepare(task, base, final, lambda: None)
    spec = task["verification_specs"][0]
    command = verifier._command(checked_task, spec)
    observed = verifier._run_command(verifier.provider.verify_identity(fresh_manifest, fresh_witness),
                                     spec, command, effective)
    verification = build_verification_results(task, [observed])
    assert verification["all_required_passed"] is True
    with pytest.raises(ControlIntegrityError, match="ingress preflight"):
        canonical_result(task, external, receipt, manifest, seal, changes, verification,
                         failure_class="none", retryability="not_retryable", recommended_action="review",
                         summary="Unvalidated candidate", trusted_usage=external["resource_usage"])
    result = canonical_result(task, validated, receipt, manifest, seal, changes, verification,
                              failure_class="none", retryability="not_retryable", recommended_action="review",
                              summary="Verified fixture change", trusted_usage=external["resource_usage"])
    members = bundle_members(task, result, receipt, manifest, seal, changes, verification, audit, patch)
    assert result["status"] == "success" and result["usable"] is True
    assert set(members) == {"code_agent_task.json", "code_agent_result.json", "backend_dispatch_receipt.json",
                            "workspace_manifest.json", "workspace_seal.json", "change_manifest.json",
                            "verification_results.json", "tool_audit.jsonl", "changes.patch"}
    blocked = deepcopy(observed)
    blocked["status"] = "failed"
    blocked["reason"] = "unexpected_exit"
    verification = build_verification_results(task, [blocked])
    failed = canonical_result(task, validated, receipt, manifest, seal, changes, verification,
                              failure_class="verification_failed", retryability="new_attempt_allowed",
                              recommended_action="review", summary="Verification failed",
                              trusted_usage=external["resource_usage"])
    assert failed["status"] == "failed" and failed["usable"] is False
    with pytest.raises(ControlIntegrityError):
        canonical_result(task, validated, receipt, manifest, seal, changes, verification,
                         failure_class="none", retryability="not_retryable", recommended_action="review",
                         summary="Invalid success", trusted_usage=external["resource_usage"])
    observe("b03-construction-canonical-bundle", {"kind": "boolean", "value": True},
            sorted(["verified_success_only", "exact_bundle_members", "failed_verification_not_usable"]))


def test_no_change_bundle_has_no_patch_and_is_not_usable(tmp_path):
    task, manifest, receipt, seal, changes, provider, witness, base, external, audit, patch = _delivery(tmp_path)
    validated = preflight_result(canonical_bytes(external), task, manifest, receipt, seal, changes, audit, patch,
                                 provider, witness, base)
    spec = task["verification_specs"][0]
    verification = build_verification_results(task, [TrustedVerifier.not_run(spec, "no_change")])
    result = canonical_result(task, validated, receipt, manifest, seal, changes, verification,
                              failure_class="no_safe_change", retryability="new_evidence_required",
                              recommended_action="review", summary="No safe change",
                              trusted_usage=external["resource_usage"])
    members = bundle_members(task, result, receipt, manifest, seal, changes, verification, audit, patch)
    assert result["status"] == "no_change" and result["usable"] is False and "changes.patch" not in members


@pytest.mark.parametrize("status,diagnosis,retryability", [
    ("needs_input", "dependency_unavailable", "new_evidence_required"),
    ("needs_human", "dependency_unavailable", "human_required"),
    ("budget_exhausted", "dependency_unavailable", "new_evidence_required"),
    ("policy_blocked", "policy_violation", "human_required"),
])
def test_safe_prechange_status_bundle_keeps_verification_unrun(tmp_path, status, diagnosis, retryability):
    task, manifest, receipt, seal, changes, provider, witness, base, external, audit, patch = _delivery(tmp_path)
    external["declared_status"] = status
    external["backend_verification_claims"] = [{"spec_id": task["verification_specs"][0]["spec_id"],
                                                 "status": "passed"}]
    external["result_digest"] = digest({key: value for key, value in external.items() if key != "result_digest"})
    validated = preflight_result(canonical_bytes(external), task, manifest, receipt, seal, changes, audit, patch,
                                 provider, witness, base)
    final = provider.verify_sealed(manifest, witness, seal["final_tree_digest"])
    verification = TrustedVerifier(tmp_path / "verification").verify_all(
        task, base, final, candidate_status=status, fence=lambda: None, port=None)
    assert verification["all_required_passed"] is False
    assert [(item["status"], item["reason"]) for item in verification["spec_results"]] == [
        ("not_run", status) for _ in task["verification_specs"]]
    result = canonical_result(task, validated, receipt, manifest, seal, changes, verification,
                              failure_class=diagnosis, retryability=retryability,
                              recommended_action="review", summary="Safe pre-change stop",
                              trusted_usage=external["resource_usage"])
    members = bundle_members(task, result, receipt, manifest, seal, changes, verification, audit, patch)
    assert result["status"] == status and result["usable"] is False
    assert result["failure_class"] == diagnosis and result["retryability"] == retryability
    assert "changes.patch" not in members
