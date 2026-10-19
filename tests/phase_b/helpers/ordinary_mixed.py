"""C10 source meta drivers using original production ports."""
from harness.temporary import mkdtemp
from pathlib import Path

from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_sources import OrdinarySources
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.interfaces import ControlPlane
from lqcd_agent.control.capabilities import ArtifactEffectPort, InvocationLeases, TargetOutcome
from lqcd_agent.control.strict_json import canonical_bytes, digest
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes


def no_code_trace(*, scenario="b00c10-no-code", outcomes=None, agent=None, trace_version="0.6"):
    if trace_version not in ("0.6", "0.8"):
        raise ValueError("Unsupported explicit ordinary trace version")
    output = Path(mkdtemp(prefix="lqcd-agent-b00c10-no-code-", dir="/private/tmp"))
    identities = HostIdentities(scenario)
    with identities.installed():
        coordinator = Coordinator(output, clock=FakeClock(100, 0))
        if trace_version == "0.8":
            from helpers.product_failure_sources import ProductFailureSources
            sources = ProductFailureSources(coordinator)
        else:
            sources = OrdinarySources(coordinator)
        captured = ControlTrace(output, version=trace_version, ordinary_sources=sources)
        coordinator.observer = (lambda name, side, value: sources.observer(captured, name, side, value)) if trace_version == "0.8" else captured.observer
        agent = StructuredOutcomes(outcomes) if agent is None else agent
        inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        try:
            result = run_canonical_graph(coordinator=coordinator,
                request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"),
                actor=ActorContext("operator", "human", ("control.internal", "resume", "start")), agent_port=sources.agent(agent))
            trace = captured.finish(coordinator)
            (output / "raw.json").write_bytes(canonical_bytes(trace))
            (output / "allocations.json").write_bytes(canonical_bytes(identities.allocations))
            return trace, output, agent, result["state"]
        finally:
            coordinator.close()


def primitive_trace(*, kind="llm_call", failure=None, result=None, scenario="b00c10-primitive"):
    output = Path(mkdtemp(prefix="lqcd-agent-b00c10-primitive-", dir="/private/tmp"))
    with HostIdentities(scenario).installed():
        coordinator = Coordinator(output, clock=FakeClock(100, 0))
        sources = OrdinarySources(coordinator)
        captured = ControlTrace(output, version="0.6", ordinary_sources=sources)
        coordinator.observer = captured.observer
        actor = ActorContext("operator", "human", ("start",))
        plane = ControlPlane(coordinator, worker_id="host")
        inputs = {"root_goal": {"goal": "ordinary primitive meta"}, "input_snapshot": {"data": "synthetic"}}
        calls = []
        try:
            started = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "phase_b_test"), actor=actor)
            capability = started["result"]["capability_id"]
            leases = InvocationLeases(coordinator)
            leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)

            def effect():
                calls.append("effect")
                if failure == "exception":
                    raise RuntimeError("Uncertain provider completion")
                coordinator.clock.advance(2)
                return {"output": "bounded"} if result is None else result

            class Target:
                def invoke_scoped(self, identity, port):
                    sources.resource(port, resource_kind=kind, resource_id="call-1", input_value="input",
                                     config_value="config", timeout_seconds=3, effect=effect)
                    return TargetOutcome("succeeded", {"current_artifact_ids": {}})

            if failure is None:
                state = leases.invoke(capability, "consumer", 1, Target())
            else:
                leases.start_intent(capability, "consumer", 1)
                state = leases.publish_started(capability, "consumer", 1)
                port = ArtifactEffectPort(leases, None, capability, "consumer", 1)
                try:
                    sources.resource(port, resource_kind=kind, resource_id="uncertain", input_value="input",
                                     config_value="config", timeout_seconds=1, effect=effect)
                except ValueError:
                    assert failure == "overrun"
                except RuntimeError:
                    assert failure == "exception"
                else:
                    raise AssertionError("Expected the actual effect/clock failure")
            trace = captured.finish(coordinator)
            (output / "raw.json").write_bytes(canonical_bytes(trace))
            return trace, output, calls, state
        finally:
            coordinator.close()


def mixed_trace(*, scenario="b00c10-mixed"):
    """Compose real ports in one Run; this is no B04 route acceptance."""
    from hashlib import sha256
    import shutil
    import sys
    from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
    from lqcd_agent.code_agent.containment import DeterministicContainment
    from lqcd_agent.code_agent.external_operation import ExternalDispatch, ExternalNormalFinal, ExternalProducer
    from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
    from lqcd_agent.code_agent.prestart import CodePrestart
    from lqcd_agent.code_agent.subgraph import CodeAgentSubgraph
    from lqcd_agent.code_agent.workspace import WorkspaceProvider, canonical_patch, immutable_git_tree, seal_workspace
    from lqcd_agent.control.execution import parse_ledger
    from lqcd_agent.control.operations import AdvanceRunRequest
    from lqcd_agent.control.pause import PublishPauseRequest, ResumeRunRequest, runtime_fingerprint
    from lqcd_agent.control.strict_json import loads
    from lqcd_agent.graph.nodes import ProductNode
    from helpers.code_workspace import immutable_base_repository
    from test_advance_control import SyntheticDomainRoute
    from test_b03_analysis_handoff import CanonicalAnalysisRoute

    output = Path(mkdtemp(prefix="lqcd-agent-b00c10-mixed-", dir="/private/tmp"))
    repository, base_info = immutable_base_repository()
    preserved_base = output / "base_repository"
    shutil.copytree(repository, preserved_base)
    identities = HostIdentities(scenario)
    with identities.installed():
        coordinator = Coordinator(output, clock=FakeClock(100, 0))
        sources = OrdinarySources(coordinator)
        captured = ControlTrace(output, version="0.6", ordinary_sources=sources)
        coordinator.observer = captured.observer
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        plane = ControlPlane(coordinator, worker_id="host", route_adapter=SyntheticDomainRoute("code_agent"))
        inputs = {"root_goal": {"goal": "same Run ordinary and canonical Code source meta"}, "input_snapshot": {"data": "synthetic"}}
        agent = StructuredOutcomes()
        try:
            started = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"), actor=actor)
            locator = started["result"]["run_locator"]
            root = output / locator["case_id"] / locator["run_id"]
            leases = InvocationLeases(coordinator)
            capability = started["result"]["capability_id"]
            leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=30)
            leases.invoke(capability, "consumer", 1, ProductNode(root, sources.agent(agent)))
            advanced = plane.advance_run(AdvanceRunRequest(locator, "attempt_000001", "code-target"), actor=actor)
            producer = ExternalProducer(coordinator).reserve(advanced["result"]["capability_id"],
                backend_kind="fake", backend_version="0.1", hard_deadline=20, worker_id="external-host", lease_seconds=10)
            records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
            index = loads((root / "artifact_index.json").read_bytes())
            transition = records[-1]
            decision = [r for r in records if r["record_type"] == "budget" and r["event"] == "decision_recorded"][-1]
            policy = loads((root / "budget_policy.json").read_bytes())
            plan = index["current"]["plan"]
            evidence = [{"artifact_id": plan["artifact_id"], "path": m["canonical_path"], "sha256": m["sha256"]}
                        for m in plan["members"] if m["logical_name"] == "method_plan.json"]
            identity = {**locator, "cycle_id": transition["target_cycle_id"], "attempt_id": transition["target_attempt_id"],
                        "transition_id": transition["transition_id"], "producer_operation_id": producer["producer_operation_id"]}
            spec = {"spec_id": "fixture-check", "argv": ["python", "-m", "compileall", "sample.py"], "cwd": ".",
                    "timeout_seconds": 1, "required": True, "expected_exit_codes": [0], "environment_keys": []}
            task = {**identity, **base_info, "schema_version": "0.1", "task_id": identity["attempt_id"] + ":code_task",
                "source_attempt_id": transition["source_attempt_id"], "attempt_kind": "code_agent", "node_name": "code_agent",
                "task_origin": "planner_gap", "task_summary": "Check the fixture", "requirements": ["Return the fixture value"],
                "acceptance_criteria": ["Required verification passes"], "evidence": evidence,
                "execution_head": digest(records[-1]), "artifact_head": index["artifact_head"],
                "source_runtime_fingerprint": runtime_fingerprint(), "read_paths": ["sample.py"], "write_paths": ["sample.py"],
                "forbidden_paths": [".git"], "tool_policy": [spec], "network_policy": {"enabled": False},
                "filesystem_policy": {"binary_changes": False, "executable_changes": False, "ephemeral_paths": ["__pycache__"]},
                "verification_specs": [spec], "budget_policy_version": policy["schema_version"],
                "budget_profile_id": policy["profile_id"], "budget_policy_digest": policy["policy_digest"],
                "budget_envelope_ref": {"path": "execution_history.jsonl", "event_id": decision["event_id"]},
                "budget_envelope_digest": digest(decision), "human_authorization_ref": None,
                "coding_backend_kind": "fake", "backend_version": "0.1", "backend_runtime_fingerprint": digest("fake-0.1"),
                "external_producer_contract": {"schema_version": "0.1", "parent_control_operation_id": advanced["operation_id"]},
                "expected_result_schema": "0.1"}
            task["task_digest"] = digest(task)
            policy_names = ("read_paths", "write_paths", "forbidden_paths", "tool_policy", "network_policy", "filesystem_policy")
            manifest = {**identity, **base_info, "schema_version": "0.1", "workspace_id": producer["workspace_id"],
                "workspace_generation": 1, "task_id": task["task_id"], "task_digest": task["task_digest"],
                "source_runtime_fingerprint": task["source_runtime_fingerprint"], "coding_backend_kind": "fake", "backend_version": "0.1",
                "backend_runtime_fingerprint": task["backend_runtime_fingerprint"], "workspace_implementation": "deterministic_fixture",
                "policy_digests": {k: digest(task[k]) for k in policy_names}, "created_at": 100, "owner": "external-host",
                "managed_root_identity": producer["managed_workspace_locator_digest"]}
            manifest["manifest_digest"] = digest(manifest)
            base = immutable_git_tree(preserved_base, task["base_revision"])
            preview = WorkspaceProvider(output / "preview_workspace")
            witness = preview.materialize(manifest, base, lambda: None)
            changed_content = b"def value():\n    return 2\n"
            (preview.path(manifest["workspace_id"]) / "sample.py").write_bytes(changed_content)
            audit = b""
            stop_proof = {"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
                          "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}
            changes, seal = seal_workspace(preview, task, manifest, witness, base, backend_status="completed",
                stop_proof=stop_proof, tool_audit=audit, sealed_at=0, fence=lambda: None)
            patch = canonical_patch(base, preview.verify_sealed(manifest, witness, seal["final_tree_digest"]), changes["changes"])
            receipt = FakeCodingBackend._receipt(task, manifest)
            external = {**identity, "schema_version": "0.1", "result_id": task["attempt_id"] + ":external_result",
                "task_id": task["task_id"], "task_digest": task["task_digest"], "workspace_id": manifest["workspace_id"],
                "workspace_manifest_digest": manifest["manifest_digest"], **base_info, "coding_backend_kind": "fake",
                "backend_version": "0.1", "provider_operation_reference": None, "provider_thread_reference": None,
                "dispatch_receipt_digest": sha256(canonical_bytes(receipt)).hexdigest(), "workspace_seal_digest": seal["seal_digest"],
                "change_manifest_digest": changes["change_manifest_digest"], "tool_audit_digest": seal["tool_audit_digest"],
                "change_blobs": [{"path": item["path"], "sha256": item["after_sha256"]} for item in changes["changes"] if item["after_sha256"] is not None],
                "patch_digest": sha256(patch).hexdigest(), "declared_status": "success", "backend_verification_claims": [],
                "resource_usage": {"llm_calls": 0, "tool_calls": 0, "verification_commands": 0, "active_seconds": 0},
                "warnings": [], "errors": [], "failure_evidence": None}
            external["result_digest"] = digest(external)
            producer_id = producer["producer_operation_id"]
            backend = FakeCodingBackend(output / "fake_backend", operation_scenarios={producer_id: "success"},
                fixtures={"success": {"status": "completed", "result": canonical_bytes(external)}}, clock=lambda: 100)
            containment = DeterministicContainment(output / "containment")
            prestart = CodePrestart(coordinator, producer_id, "external-host", 1)
            prestart.commit_task(task); prestart.commit_manifest(manifest)
            prestart.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1, "verification_commands": 0, "active_seconds": 10},
                                      timeout_seconds=10, config_digest=digest("config"))
            prestart.commit_core(); prestart.materialize_workspace(preserved_base)
            paused = plane.publish_pause(PublishPauseRequest(locator, "external_result", task["attempt_id"], task["attempt_id"],
                {"kind": "external_result", "producer_operation_id": producer_id}, {"actor_type": "human", "scopes": ["resume"]},
                "publish-canonical-code"), actor=actor)
            dispatch = ExternalDispatch(coordinator, producer_id, "external-host", 1, backend, containment, backend.read_receipt, backend.read_result)
            dispatch.dispatch()
            (WorkspaceProvider(output / "code_workspaces").path(manifest["workspace_id"]) / "sample.py").write_bytes(changed_content)
            dispatch.publish_result_reference()
            final = ExternalNormalFinal(dispatch, preserved_base).commit(tool_audit=audit, patch=patch)
            payload = {"producer_operation_id": producer_id, "external_final_digest": final["terminal_evidence_digest"]}
            request = ResumeRunRequest(locator, paused["result"]["pause_id"], "consume-normal", "external_result", payload, digest(payload))
            consumer = CodeAgentSubgraph(coordinator, preserved_base)
            plane.resume_target_adapter = plane.external_adapter = consumer
            consumed = plane.resume_run(request, actor=actor)
            assert consumed["operation_status"] == "committed" and consumed["domain_status"] == "succeeded", consumed
            command = [sys.executable, "-I", "-S", "-c", "import runpy; print(runpy.run_path('sample.py')['value']())"]
            handoff = AnalysisHandoff(coordinator, preserved_base, allowed_command=command)
            plane.route_adapter = CanonicalAnalysisRoute(handoff)
            advanced = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "prepare-analysis"), actor=actor)
            assert advanced["operation_status"] == "committed", advanced
            leases = InvocationLeases(coordinator, preparation_adapter=plane.route_adapter)
            capability = advanced["result"]["capability_id"]
            preparation = leases.get(capability)[1]["authorization"]["target_preparation"]
            spec, _ = handoff._frozen(preparation)
            config = {"runtime": {"python": sys.version, "executable": sys.executable}, "environment": spec["environment_policy"],
                      "command": handoff.allowed_command, "outputs": handoff.expected_outputs}
            class Tool:
                def execute(self, value):
                    return sources.invoke(capability, value, config, lambda: handoff.execute(value), profile="analysis_tool")
            leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=30)
            state = leases.invoke(capability, "consumer", 1,
                ProductNode(root, sources.agent(agent), analysis_handoff=Tool(), preparation=preparation))
            assert state["attempt_status"] == "succeeded", state
            trace = captured.finish(coordinator)
            (output / "raw.json").write_bytes(canonical_bytes(trace))
            (output / "allocations.json").write_bytes(canonical_bytes(identities.allocations))
            return trace, output, agent, state
        finally:
            coordinator.close()
