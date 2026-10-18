"""Real product graph with deterministic external result and tool fixtures."""
from hashlib import sha256
from pathlib import Path
import sys
import tempfile

from helpers.code_workspace import immutable_base_repository
from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
from lqcd_agent.code_agent.schemas import IDENTITY
from lqcd_agent.code_agent.subgraph import ProductCodeHost
from lqcd_agent.code_agent.workspace import WorkspaceProvider, canonical_patch, immutable_git_tree, seal_workspace
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes


class CodeOutcomes(StructuredOutcomes):
    def __init__(self, outcomes=None, *, requirement="Compute the approved synthetic observable"):
        super().__init__(outcomes)
        self.requirement = requirement

    def run(self, node, context, *, timeout_seconds):
        value = super().run(node, context, timeout_seconds=timeout_seconds)
        if node == "method_planner":
            value["content"].update(code_needed=True, requirements=[self.requirement])
        return value


class ProductFakeBackend(FakeCodingBackend):
    """Inject only an actual Fake workspace effect and immutable external result."""

    def __init__(self, coordinator, repository, containment, status, *, first_failure_change=None):
        super().__init__(coordinator.root / "fake_backend", clock=lambda: 100)
        self.coordinator, self.repository, self.containment = coordinator, repository, containment
        self.candidate_status = status
        self.dispatches = []
        self.deliveries = {}
        self.first_failure_change = first_failure_change
        self.capture_claims = False

    def dispatch(self, task, manifest, producer):
        self.dispatches.append(producer)
        provider = WorkspaceProvider(self.coordinator.root / "code_workspaces")
        base = immutable_git_tree(self.repository, task["base_revision"])
        status = self.candidate_status.pop(0) if isinstance(self.candidate_status, list) else self.candidate_status
        success = status == "success"
        change = b"def value():\n    return 2\n" if success else self.first_failure_change if len(self.dispatches) == 1 else None
        audit = b""
        if change is not None:
            self.containment.record_tool(producer)
            (provider.path(manifest["workspace_id"]) / "sample.py").write_bytes(change)
            tool = task["tool_policy"][0]
            audit = canonical_bytes({"tool_event_index": 1, "task_id": task["task_id"], "workspace_id": manifest["workspace_id"],
                "tool_id": tool["spec_id"], "argv_digest": digest(tool["argv"]), "cwd": ".", "start_at": 100, "end_at": 100,
                "status": "completed", "affected_paths": ["sample.py"], "output_digest": digest(""),
                "resource_usage": {"llm_calls": 0, "tool_calls": 1, "active_seconds": 0}}) + b"\n"
        witness = provider._public_witness(manifest)
        stop = {"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
                "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}
        changes, seal = seal_workspace(provider, task, manifest, witness, base, backend_status="completed",
            stop_proof=stop, tool_audit=audit, sealed_at=self.coordinator._time().monotonic_seconds, fence=lambda: None)
        final_tree = provider.verify_sealed(manifest, witness, seal["final_tree_digest"])
        patch = canonical_patch(base, final_tree, changes["changes"]) if changes["changes"] else None
        receipt = self._receipt(task, manifest)
        result = {**{k: task[k] for k in IDENTITY}, "schema_version": "0.1", "result_id": task["attempt_id"] + ":external_result",
            "task_id": task["task_id"], "task_digest": task["task_digest"], "workspace_id": manifest["workspace_id"],
            "workspace_manifest_digest": manifest["manifest_digest"], "base_revision": task["base_revision"],
            "base_tree_digest": task["base_tree_digest"], "coding_backend_kind": "fake", "backend_version": "0.1",
            "provider_operation_reference": None, "provider_thread_reference": None, "dispatch_receipt_digest": digest(receipt),
            "workspace_seal_digest": seal["seal_digest"], "change_manifest_digest": changes["change_manifest_digest"],
            "tool_audit_digest": seal["tool_audit_digest"],
            "change_blobs": [{"path": c["path"], "sha256": c["after_sha256"]} for c in changes["changes"] if c["after_sha256"] is not None],
            "patch_digest": sha256(patch).hexdigest() if patch is not None else None,
            "declared_status": status, "backend_verification_claims": [],
            "resource_usage": {"llm_calls": 0, "tool_calls": int(change is not None), "verification_commands": 0, "active_seconds": 0},
            "warnings": [], "errors": [], "failure_evidence": None}
        result["result_digest"] = digest(result)
        self.operation_scenarios[producer] = producer
        self.fixtures[producer] = {"status": "completed", "result": canonical_bytes(result)}
        self.deliveries[producer] = (audit, patch)
        dispatched = super().dispatch(task, manifest, producer)
        if self.capture_claims:
            from helpers.trace_sources import current_binding
            directory = self.coordinator.root / "trace_backend_claims"
            directory.mkdir(exist_ok=True)
            snapshot = {"schema_version": "0.1", "profile": "unaccepted_backend_claim", "binding": current_binding(),
                "producer_operation_id": producer, "task": task, "manifest": manifest, "receipt": receipt,
                "result": result, "change_manifest": changes, "seal": seal, "tool_audit": audit.decode(),
                "patch": patch.decode() if patch is not None else None}
            with (directory / (producer + ".json")).open("xb") as stream:
                stream.write(canonical_bytes(snapshot))
        return dispatched


def code_product(*, status="success", outcomes=None, observer=None, trace=False, trace_version="0.8",
                 requirement="Compute the approved synthetic observable", first_failure_change=None, stop_fault=None):
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-code-product-", dir="/private/tmp"))
    repository, base = immutable_base_repository()
    from helpers.ordinary_maximum import PassiveClock
    coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)) if trace else FakeClock(100, 0), observer=observer)
    sources, capture = None, None
    if trace:
        from helpers.control_traces import ControlTrace
        from helpers.product_failure_sources import ProductFailureSources
        assert trace_version in ("0.8", "0.9", "0.10", "0.11")
        if trace_version == "0.11":
            from helpers.unconsumed_code_final_sources import UnconsumedCodeSources
            sources = UnconsumedCodeSources(coordinator)
        elif trace_version == "0.10":
            from helpers.ordinary_publication_prefix_sources import PublicationPrefixSources
            sources = PublicationPrefixSources(coordinator)
        elif trace_version == "0.9":
            from helpers.prior_code_evidence_sources import PriorCodeSources
            sources = PriorCodeSources(coordinator)
        else:
            sources = ProductFailureSources(coordinator)
        capture = ControlTrace(output, version=trace_version, ordinary_sources=sources)
        def collect(name, side, value):
            sources.observer(capture, name, side, value)
            if observer is not None:
                observer(name, side, value)
        collect.production_hooks = getattr(observer, "production_hooks", {})
        coordinator.observer = collect
    actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
    class Containment(DeterministicContainment):
        def start(self, operation_id, workspace_id):
            if stop_fault is not None:
                assert stop_fault in ("kill_all", "bounded_drain", "post_stop_stability")
                self.faults[operation_id] = {stop_fault: False}
            return super().start(operation_id, workspace_id)
    containment = Containment(output / "containment")
    backend = ProductFakeBackend(coordinator, repository, containment, status, first_failure_change=first_failure_change)
    backend.capture_claims = trace and trace_version == "0.11"
    tool = {"spec_id": "synthetic-update", "argv": ["fixture:write", "sample.py"], "cwd": ".", "timeout_seconds": 1,
            "required": True, "expected_exit_codes": [0], "environment_keys": []}
    verification = {**tool, "spec_id": "syntax", "argv": ["python", "-m", "compileall", "sample.py"]}
    policy = {**base, "task_summary": "Implement the approved synthetic observable", "acceptance_criteria": ["Trusted syntax check passes"],
        "read_paths": ["sample.py"], "write_paths": ["sample.py"], "forbidden_paths": [".git"], "tool_policy": [tool],
        "network_policy": {"enabled": False}, "filesystem_policy": {"binary_changes": False, "executable_changes": False,
        "ephemeral_paths": ["__pycache__"]}, "verification_specs": [verification], "coding_backend_kind": "fake",
        "backend_version": "0.1", "backend_runtime_fingerprint": digest("fake-0.1")}
    host = ProductCodeHost(coordinator, repository, backend, containment, task_policy=policy,
        maximum_charge={"llm_calls": 1, "tool_calls": 1, "verification_commands": 0}, timeout_seconds=20)
    class ObservedAnalysis(AnalysisHandoff):
        def execute(self, value):
            if sources is None:
                return super().execute(value)
            spec = loads(value["canonical_spec_bytes"])
            configuration = {"runtime": {"python": sys.version, "executable": sys.executable},
                "environment": spec["environment_policy"], "command": spec["allowed_command"], "outputs": spec["expected_outputs"]}
            cap = next(r[0] for r in coordinator.connection.execute("SELECT capability_id,value FROM invocation_capabilities")
                       if loads(r[1])["authorization"]["identity"] == {k: spec["target_attempt_identity"][k]
                           for k in ("case_id", "run_id", "attempt_id", "attempt_kind")})
            return sources.invoke(cap, value, configuration, lambda: super(ObservedAnalysis, self).execute(value), profile="analysis_tool")
    handoff = ObservedAnalysis(coordinator, repository, allowed_command=[sys.executable, "-I", "-S", "-c",
        "import runpy; print(runpy.run_path('sample.py')['value']())"])
    agent = CodeOutcomes(outcomes, requirement=requirement)
    inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
    try:
        result = run_canonical_graph(coordinator=coordinator, request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"),
            actor=actor, agent_port=sources.agent(agent) if sources is not None else agent, code_host=host, analysis_handoff=handoff)
        result["trace_capture"] = capture
    except BaseException:
        coordinator.close()
        raise
    return coordinator, actor, agent, backend, host, handoff, result


def deliver_product_code(coordinator, actor, backend, host, result, *, producer=None):
    if producer is None:
        producer, = backend.dispatches
    audit, patch = backend.deliveries[producer]
    final = host.finalize(producer, tool_audit=audit, patch=patch)
    payload = {"producer_operation_id": producer, "external_final_digest": final["terminal_evidence_digest"]}
    key = "product-code-consume" if len(backend.dispatches) == 1 else "product-code-consume:" + producer
    resume = ResumeRunRequest(result["run_locator"], final["pause_id"], key, "external_result", payload, digest(payload))
    return result["runtime"].resume(resume, actor=actor), resume
