"""Passive C15 witnesses of the original fenced Host derivation and admission."""
from copy import deepcopy
import inspect

from helpers.b04_product_sources import ProductSources
from helpers.ordinary_sources import captured_source
from lqcd_agent.control.strict_json import digest, loads
from lqcd_agent.graph.nodes import product_observe_failure, product_issue_grant


class ProductFailureSources(ProductSources):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.failures, self.grants = [], []

    def observer(self, capture, name, side, value):
        super().observer(capture, name, side, value)
        if side != "before" or name not in ("budget.failure_observed", "budget.grant_issued"):
            return
        operation = product_observe_failure if name == "budget.failure_observed" else product_issue_grant
        frame = inspect.currentframe().f_back
        try:
            while frame is not None and frame.f_code is not operation.__code__:
                frame = frame.f_back
            assert frame is not None
            facts = frame.f_locals
            port = facts["port"]
            _, capability = port.leases.get(port.capability_id)
            auth = capability["authorization"]
            producer = self.coordinator.get(auth["producer_operation_id"])
            issuer = {"worker_id": port.worker, "invocation_epoch": port.epoch,
                      "producer_epoch": producer["lease_epoch"], "producer_revision": producer["phase_revision"]}
            declaration = {"schema_version": "0.1", "capability_id": port.capability_id,
                           "producer_operation_id": producer["operation_id"], "issuer": issuer}
            head = digest(value["record"])
            if name == "budget.failure_observed":
                source, registration = facts["source"], facts["registration"]
                name = "code_agent_result.json" if source["attempt_kind"] == "code_agent" else source["attempt_kind"] + "_diagnostic.json"
                member = next(m for m in source["members"] if m["logical_name"] == name)
                declaration.update(failure_head=head, source_attempt_id=source["attempt_id"],
                    source_registration_head=digest(registration), diagnostic_binding={"kind": "canonical_code_result" if source["attempt_kind"] == "code_agent" else "ordinary_diagnostic",
                    "registration_head": digest(registration), "member": member["logical_name"], "sha256": member["sha256"]},
                    derivation=captured_source("product_failure_derivation", deepcopy(facts["derivation"])))
                assert value["record"]["payload"]["fingerprint"] == facts["fp"]
                self.failures.append(declaration)
            else:
                records, response, request, pause = facts["records"], facts["response"], facts["request"], facts["pause"]
                response_rows = {r["event"]: r for r in records if r.get("record_type") == "human_response" and
                                 r["human_response_id"] == response["human_response_id"]}
                registrations = [loads(line) for line in (facts["root"] / "artifact_history.jsonl").read_bytes().splitlines()]
                registration, = [r for r in registrations if r["event"] == "protected_snapshot_registered" and
                                 r["protected_kind"] == "human_response" and
                                 r.get("human_response_id") == response["human_response_id"]]
                failure, = [r for r in records if r.get("event") == "failure_observed" and
                    r["payload"]["fingerprint"]["fingerprint_digest"] == facts["grant"]["fingerprint_digest"] and
                    r["payload"]["occurrence"] == facts["grant"]["occurrence"]]
                declaration.update(grant_head=head, human_request_head=digest(request),
                    response_submitted_head=digest(response_rows["submitted"]), response_validated_head=digest(response_rows["validated"]),
                    response_consumed_head=digest(response), snapshot_registration_head=digest(registration),
                    pause_consumed_head=digest(pause), resume_operation_id=pause["operation_id"], failure_head=digest(failure),
                    admission=captured_source("product_grant_admission", deepcopy(facts["admission"])))
                assert value["record"]["payload"] == facts["admission"]["grant_payload"]
                self.grants.append(declaration)
        finally:
            del frame

    def finish(self, trace):
        super().finish(trace)
        proof = trace["proof"]
        public = {row["sha256"] for row in proof["objects"] if row["kind"] == "execution_0_4"}
        proof.update(schema_version="0.5",
                     product_failure_sources=[deepcopy(row) for row in self.failures if row["failure_head"] in public],
                     product_grant_sources=[deepcopy(row) for row in self.grants if row["grant_head"] in public])
        return trace


def code_product_trace(*, success=False, requirement="Return the fixture value", changed_content=b"def value():\n    return 2\n", command=None, label="code", repeat=False, clock_time=100, audit_time=None, audit_fault=None):
    """Compose original B03 ports after an actual product Planner route."""
    from contextlib import closing
    from hashlib import sha256
    from pathlib import Path
    import shutil
    import sys
    import tempfile
    from helpers.code_workspace import immutable_base_repository
    from helpers.control_traces import ControlTrace
    from helpers.host_identity_fixture import HostIdentities
    from helpers.ordinary_maximum import PassiveClock
    from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
    from lqcd_agent.code_agent.containment import DeterministicContainment
    from lqcd_agent.code_agent.external_operation import ExternalProducer, ExternalDispatch, ExternalNormalFinal
    from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
    from lqcd_agent.code_agent.prestart import CodePrestart
    from lqcd_agent.code_agent.subgraph import CodeAgentSubgraph
    from lqcd_agent.code_agent.workspace import WorkspaceProvider, immutable_git_tree, seal_workspace, canonical_patch
    from lqcd_agent.control.clock import FakeClock
    from lqcd_agent.control.capabilities import InvocationLeases
    from lqcd_agent.control.coordinator import Coordinator
    from lqcd_agent.control.execution import parse_ledger
    from lqcd_agent.control.pause import runtime_fingerprint
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
    from lqcd_agent.control.operations import AdvanceRunRequest
    from lqcd_agent.control.pause import PublishPauseRequest, ResumeRunRequest
    from lqcd_agent.control.strict_json import canonical_bytes
    from lqcd_agent.graph.analysis_graph import ProductRouteAdapter
    from lqcd_agent.graph.nodes import ProductNode
    from test_b04_product_graph import StructuredOutcomes, diagnostic

    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b00c15-code-", dir="/private/tmp"))
    base_repository, base_info = immutable_base_repository()
    repository = output / "base_repository"
    shutil.copytree(base_repository, repository)
    with HostIdentities("b00c15-code-" + str(success) + "-" + label).installed(), closing(Coordinator(output, clock=PassiveClock(FakeClock(clock_time, 0)))) as coordinator:
        sources = ProductFailureSources(coordinator)
        capture = ControlTrace(output, version="0.8", ordinary_sources=sources)
        dispatches = []
        def observer(name, side, value):
            sources.observer(capture, name, side, value)
            if name == "external.backend_dispatch" and side == "after":
                dispatches.append(value["producer_operation_id"])
        coordinator.observer = observer
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        route = ProductRouteAdapter(coordinator)
        plane = ControlPlane(coordinator, worker_id="host", route_adapter=route)
        inputs = {"root_goal": {"goal": requirement}, "input_snapshot": {"data": "synthetic"}}
        started = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"), actor=actor)
        locator = started["result"]["run_locator"]
        root = output / locator["case_id"] / locator["run_id"]
        class Agent(StructuredOutcomes):
            def run(self, node, context, *, timeout_seconds):
                result = super().run(node, context, timeout_seconds=timeout_seconds)
                if node == "method_planner":
                    result["content"] = {"code_needed": True, "requirements": [requirement]}
                return result
        failed = diagnostic(status="failed", category="tool_failure", affected_layer="analysis", retryability="retryable", candidates=["code_agent"] if repeat else ["analysis_engineer"], risk="low")
        agent = Agent({"analysis_engineer": failed})
        leases = InvocationLeases(coordinator)
        cap = started["result"]["capability_id"]
        leases.acquire(cap, "host", expected_epoch=0, lease_seconds=10)
        leases.invoke(cap, "host", 1, ProductNode(root, sources.agent(agent)))
        advanced = plane.advance_run(AdvanceRunRequest(locator, "attempt_000001", "code"), actor=actor)
        assert advanced["operation_status"] == "committed"
        for code_round in range(2 if repeat else 1):
            producer = ExternalProducer(coordinator).reserve(advanced["result"]["capability_id"], backend_kind="fake", backend_version="0.1",
                hard_deadline=20, worker_id="host", lease_seconds=10)
            rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
            transition = next(r for r in reversed(rows) if r["record_type"] == "transition")
            decision = next(r for r in reversed(rows) if r.get("event") == "decision_recorded")
            index = loads((root / "artifact_index.json").read_bytes())
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
                "task_origin": "coordinator_code_fix" if code_round else "planner_gap", "task_summary": "Check the fixture", "requirements": [requirement],
                "acceptance_criteria": ["Required verification passes"], "evidence": evidence, "execution_head": digest(transition),
                "artifact_head": index["artifact_head"], "source_runtime_fingerprint": runtime_fingerprint(), "read_paths": ["sample.py"],
                "write_paths": ["sample.py"], "forbidden_paths": [".git"], "tool_policy": [spec], "network_policy": {"enabled": False},
                "filesystem_policy": {"binary_changes": False, "executable_changes": False, "ephemeral_paths": ["__pycache__"]},
                "verification_specs": [spec], "budget_policy_version": "0.1", "budget_profile_id": policy["profile_id"],
                "budget_policy_digest": policy["policy_digest"], "budget_envelope_ref": {"path": "execution_history.jsonl", "event_id": decision["event_id"]},
                "budget_envelope_digest": digest(decision), "human_authorization_ref": None, "coding_backend_kind": "fake", "backend_version": "0.1",
                "backend_runtime_fingerprint": digest("fake-0.1"), "external_producer_contract": {"schema_version": "0.1", "parent_control_operation_id": advanced["operation_id"]},
                "expected_result_schema": "0.1"}
            task["task_digest"] = digest(task)
            policy_fields = ("read_paths", "write_paths", "forbidden_paths", "tool_policy", "network_policy", "filesystem_policy")
            manifest = {**identity, **base_info, "schema_version": "0.1", "workspace_id": producer["workspace_id"], "workspace_generation": 1,
                "task_id": task["task_id"], "task_digest": task["task_digest"], "source_runtime_fingerprint": task["source_runtime_fingerprint"],
                "coding_backend_kind": "fake", "backend_version": "0.1", "backend_runtime_fingerprint": task["backend_runtime_fingerprint"],
                "workspace_implementation": "deterministic_fixture", "policy_digests": {k: digest(task[k]) for k in policy_fields},
                "created_at": clock_time, "owner": "host", "managed_root_identity": producer["managed_workspace_locator_digest"]}
            manifest["manifest_digest"] = digest(manifest)
            base = immutable_git_tree(repository, task["base_revision"])
            preview = WorkspaceProvider(output / "preview_workspace")
            preview_witness = preview.materialize(manifest, base, lambda: None)
            if success:
                (preview.path(manifest["workspace_id"]) / "sample.py").write_bytes(changed_content)
            audit_clock = FakeClock(clock_time if audit_time is None else audit_time, 0)
            audit_event = {"tool_event_index": 1, "task_id": task["task_id"], "workspace_id": manifest["workspace_id"], "tool_id": spec["spec_id"],
                "argv_digest": digest(spec["argv"]), "cwd": ".", "start_at": audit_clock.now().wall_seconds,
                "end_at": audit_clock.now().wall_seconds, "status": "completed", "affected_paths": ["sample.py"],
                "output_digest": digest(""), "resource_usage": {"llm_calls": 0, "tool_calls": 1, "active_seconds": 0}}
            audit = canonical_bytes(audit_event) + b"\n" if success else b""
            if audit_fault == "argv":
                audit = canonical_bytes({**audit_event, "argv_digest": digest(["wrong-command"])}) + b"\n"
            elif audit_fault == "extra_event":
                audit += canonical_bytes({**audit_event, "tool_event_index": 2}) + b"\n"
            stop = {"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True, "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}
            changes, seal = seal_workspace(preview, task, manifest, preview_witness, base, backend_status="completed",
                                           stop_proof=stop, tool_audit=audit, sealed_at=0, fence=lambda: None)
            patch = canonical_patch(base, preview.verify_sealed(manifest, preview_witness, seal["final_tree_digest"]), changes["changes"]) if success else None
            receipt = FakeCodingBackend._receipt(task, manifest)
            external = {**identity, "schema_version": "0.1", "result_id": task["attempt_id"] + ":external_result", "task_id": task["task_id"],
                "task_digest": task["task_digest"], "workspace_id": manifest["workspace_id"], "workspace_manifest_digest": manifest["manifest_digest"],
                **base_info, "coding_backend_kind": "fake", "backend_version": "0.1", "provider_operation_reference": None, "provider_thread_reference": None,
                "dispatch_receipt_digest": digest(receipt), "workspace_seal_digest": seal["seal_digest"], "change_manifest_digest": changes["change_manifest_digest"],
                "tool_audit_digest": seal["tool_audit_digest"], "change_blobs": [{"path": item["path"], "sha256": item["after_sha256"]} for item in changes["changes"] if item["after_sha256"] is not None],
                "patch_digest": sha256(patch).hexdigest() if patch is not None else None, "declared_status": "success" if success else "needs_input",
                "backend_verification_claims": [], "resource_usage": {"llm_calls": 0, "tool_calls": int(success), "verification_commands": 0, "active_seconds": 0},
                "warnings": [], "errors": [], "failure_evidence": None}
            external["result_digest"] = digest(external)
            backend = FakeCodingBackend(output / "fake_backend", operation_scenarios={producer["producer_operation_id"]: "code"},
                                        fixtures={"code": {"status": "completed", "result": canonical_bytes(external)}}, clock=lambda: clock_time)
            containment = DeterministicContainment(output / "containment")
            prestart = CodePrestart(coordinator, producer["producer_operation_id"], "host", 1)
            prestart.commit_task(task)
            prestart.commit_manifest(manifest)
            prestart.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1, "verification_commands": 0, "active_seconds": 10},
                                       timeout_seconds=10, config_digest=digest("config"))
            prestart.commit_core()
            prestart.materialize_workspace(repository)
            paused = plane.publish_pause(PublishPauseRequest(locator, "external_result", task["attempt_id"], task["attempt_id"],
                {"kind": "external_result", "producer_operation_id": producer["producer_operation_id"]}, {"actor_type": "human", "scopes": ["resume"]}, "code-pause-" + str(code_round)), actor=actor)
            dispatch = ExternalDispatch(coordinator, producer["producer_operation_id"], "host", 1, backend, containment, backend.read_receipt, backend.read_result)
            dispatch.dispatch()
            if success:
                (WorkspaceProvider(output / "code_workspaces").path(manifest["workspace_id"]) / "sample.py").write_bytes(changed_content)
                containment.record_tool(producer["producer_operation_id"])
            dispatch.publish_result_reference()
            final = ExternalNormalFinal(dispatch, repository).commit(tool_audit=audit, patch=patch)
            payload = {"producer_operation_id": producer["producer_operation_id"], "external_final_digest": final["terminal_evidence_digest"]}
            plane.external_adapter = plane.resume_target_adapter = CodeAgentSubgraph(coordinator, repository)
            resumed = plane.resume_run(ResumeRunRequest(locator, paused["result"]["pause_id"], "code-consume-" + str(code_round), "external_result", payload, digest(payload)), actor=actor)
            assert resumed["operation_status"] == "committed"
            if success:
                allowed = command or [sys.executable, "-I", "-S", "-c", "import runpy; print(runpy.run_path('sample.py')['value']())"]
                handoff = AnalysisHandoff(coordinator, repository, allowed_command=allowed)
                route = plane.route_adapter = ProductRouteAdapter(coordinator, handoff)
                plane.preparation_adapter = handoff
                advanced = plane.advance_run(AdvanceRunRequest(locator, task["attempt_id"], "fresh-analysis-" + str(code_round)), actor=actor)
                assert advanced["operation_status"] == "committed"
                cap = advanced["result"]["capability_id"]
                leases = InvocationLeases(coordinator, preparation_adapter=route)
                preparation = leases.get(cap)[1]["authorization"]["target_preparation"]
                class PassiveAnalysis:
                    def execute(self, value):
                        frozen = loads(value["canonical_spec_bytes"])
                        configuration = {"runtime": {"python": sys.version, "executable": sys.executable}, "environment": frozen["environment_policy"],
                                         "command": frozen["allowed_command"], "outputs": frozen["expected_outputs"]}
                        return sources.invoke(cap, value, configuration, lambda: handoff.execute(value), profile="analysis_tool")
                leases.acquire(cap, "host", expected_epoch=0, lease_seconds=10)
                leases.invoke(cap, "host", 1, ProductNode(root, sources.agent(agent), analysis_handoff=PassiveAnalysis(), preparation=preparation))
                parent = leases.get(cap)[1]["authorization"]["identity"]["attempt_id"]
            else:
                parent = task["attempt_id"]
            advanced = plane.advance_run(AdvanceRunRequest(locator, parent, "coordinator-" + str(code_round)), actor=actor)
            assert advanced["operation_status"] == "committed"
            cap = advanced["result"]["capability_id"]
            leases = InvocationLeases(coordinator)
            leases.acquire(cap, "host", expected_epoch=0, lease_seconds=10)
            leases.invoke(cap, "host", 1, ProductNode(root, sources.agent(agent)))
            if repeat and code_round == 0:
                coordinator_attempt = leases.get(cap)[1]["authorization"]["identity"]["attempt_id"]
                human = plane.advance_run(AdvanceRunRequest(locator, coordinator_attempt, "repeat-human"), actor=actor)
                assert human["operation_status"] == "committed"
                cap = human["result"]["capability_id"]
                leases.acquire(cap, "host", expected_epoch=0, lease_seconds=10)
                leases.invoke(cap, "host", 1, ProductNode(root, sources.agent(agent)))
                state = parse_ledger((root / "execution_history.jsonl").read_bytes()).projection.value
                plane.publish_pause(PublishPauseRequest(locator, "human_input", state["attempt_id"], None,
                    {"kind": "human_response", "human_request_id": state["active_human_request_id"]},
                    {"actor_type": "human", "scopes": ["resume"]}, "repeat-human-pause"), actor=actor)
                state = parse_ledger((root / "execution_history.jsonl").read_bytes()).projection.value
                response = {**locator, "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
                            "decision": "request_code_change", "conditions": [], "reason": "Retry the original Code task", "decided_by": "operator"}
                plane.resume_target_adapter = ProductNode(root, sources.agent(agent))
                plane.resume_decision_adapter = route
                resumed = plane.resume_run(ResumeRunRequest(locator, state["active_pause"]["pause_id"], "repeat-approval", "human_response",
                                                           response, digest(response)), actor=actor)
                assert resumed["operation_status"] == "committed"
                state = parse_ledger((root / "execution_history.jsonl").read_bytes()).projection.value
                approved = plane.advance_run(AdvanceRunRequest(locator, state["attempt_id"], "repeat-coordinator"), actor=actor)
                assert approved["operation_status"] == "committed"
                cap = approved["result"]["capability_id"]
                leases.acquire(cap, "host", expected_epoch=0, lease_seconds=10)
                leases.invoke(cap, "host", 1, ProductNode(root, sources.agent(agent)))
                parent = leases.get(cap)[1]["authorization"]["identity"]["attempt_id"]
                advanced = plane.advance_run(AdvanceRunRequest(locator, parent, "repeat-code"), actor=actor)
                assert advanced["operation_status"] == "committed"
        trace = capture.finish(coordinator)
        facts = {"Code_parent_delivered": False, "B04_owned": False, "Code_target_from_product_selector": True,
                 "original_Code_ports": True, "fresh_analysis": success, "calls": [node for node, _ in agent.contexts],
                 "same_Run_Code_attempts": 2 if repeat else 1, "dispatches": dispatches}
        return trace, output, facts
