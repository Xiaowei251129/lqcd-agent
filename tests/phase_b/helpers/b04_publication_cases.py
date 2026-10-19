"""Original product process cuts and invocation-owned publication recovery."""
from harness.temporary import mkdtemp
from functools import partial
from pathlib import Path
import inspect
import multiprocessing
import os

from harness.inventory import case_specs
from harness.pytest_evidence import consume_process_hook, process_hook_request, production_hook
from harness.trace import event, normalize
from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from helpers.ordinary_sources import captured_source
from helpers.ordinary_publication_prefix_sources import PublicationPrefixSources
from helpers.trace_sources import current_binding
from helpers.b04_process_binding import bound_child, retain_probe_sources
from lqcd_agent.control.capabilities import ArtifactEffectPort, InvocationLeases
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
from test_b04_product_graph import StructuredOutcomes


PUBLICATIONS = {
    "budget.resource_settled": "budget.resource_settled",
    "budget.resource_reserved": "budget.resource_reserved",
    "budget.decision_before_resource": "budget.decision_before_resource",
    "artifact.transition_before_target_started": "invocation.attempt_started",
    "artifact.projection_publication": "invocation.artifact_projection",
    "artifact.history_publication": "invocation.artifact_registration",
    "artifact.index_publication": "invocation.artifact_index_replace",
    "artifact.bounded_state_sync": "checkpoint.sqlite_commit",
}
SPECS = case_specs(PROTOCOL)


class InvocationCaseSources(PublicationPrefixSources):
    """Retain an actual admitted request before the callee can be entered."""

    def pending_request(self, entry):
        record = entry["record"]
        if any(call["reservation_head"] == digest(record) for call in self.calls):
            return
        frame = inspect.currentframe().f_back
        try:
            from lqcd_agent.graph.nodes import ProductNode
            while frame is not None and frame.f_code is not ProductNode.invoke_scoped.__code__:
                frame = frame.f_back
            assert frame is not None
            context = frame.f_locals["context"]
            port = frame.f_locals["port"]
            config = {"node": frame.f_locals["node"], "structured_output": True}
            assert digest(context) == record["payload"]["input_digest"]
            assert digest(config) == record["payload"]["config_digest"]
            authorization = port.leases.get(port.capability_id)[1]["authorization"]
            self.calls.append({"schema_version": "0.1", "profile": "scoped_llm", "reservation_head": digest(record),
                "capability_id": port.capability_id, "authorization": authorization,
                "producer": self.coordinator.get(authorization["producer_operation_id"]),
                "input": captured_source("input", context), "config": captured_source("config", config),
                "outcome": None, "exception": None})
        finally:
            del frame

    def finish(self, trace):
        public = {row["sha256"] for row in trace["proof"]["objects"] if row["kind"] == "execution_0_4"}
        original = self.calls
        self.calls = [row for row in original if row["reservation_head"] in public]
        try:
            return super().finish(trace)
        finally:
            self.calls = original


@bound_child
def invocation_cut(output, case_id, request):
    boundary, side, _ = case_id.rsplit(".", 2)
    with HostIdentities("b04-publication-" + case_id).installed():
        coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
        sources = InvocationCaseSources(coordinator)
        capture = ControlTrace(Path(output), version="0.10", ordinary_sources=sources)
        agent = StructuredOutcomes()
        locator = None
        armed = not boundary.startswith("artifact.") or boundary == "artifact.transition_before_target_started"
        hooks = {(PUBLICATIONS[boundary], side): (partial(production_hook, case_id, process_request=request),)}

        def observer(name, when, value):
            nonlocal armed
            sources.observer(capture, name, when, value)
            if name == "invocation.completion_intent" and when == "after":
                armed = True
                observer.production_hooks = hooks
            if armed and (name, when) == (PUBLICATIONS[boundary], side):
                if name == "budget.resource_reserved":
                    sources.pending_request(value)
                elif name == "budget.decision_before_resource" and when == "after":
                    cap = next(loads(row[0]) for row in coordinator.connection.execute(
                        "SELECT value FROM invocation_capabilities") if loads(row[0])["state"] == "started")
                    sources.pending_request(cap["budget_intents"][-1])
                receipt = {"case_id": case_id, "binding": current_binding(), "locator": locator,
                    "process_id": os.getpid(), "calls": len(agent.contexts), "events": capture.events,
                    "observed_records": sorted(capture.observed_records), "clock_reads": coordinator.clock.reads,
                    "sources": {key: {k: list(v) for k, v in sources.epochs.items()} if key == "epochs" else getattr(sources, key) for key in
                        ("calls", "failures", "grants", "epochs", "maximum_evidence")}}
                (Path(output) / "process-source.json").write_bytes(canonical_bytes(receipt))
                os._exit(97)

        observer.production_hooks = hooks if armed else {}
        coordinator.observer = observer
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        runtime = CanonicalProductRuntime(coordinator, worker_id="product-host", actor=actor,
                                          agent_port=sources.agent(agent))
        inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        started = runtime.plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"), actor=actor)
        locator = started["result"]["run_locator"]
        runtime.run(locator)
        raise AssertionError("The original product publication did not reach its cut")


def run_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def exercise_invocation_case(case_id):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in PUBLICATIONS
    output = Path(mkdtemp(prefix="lqcd-agent-b04-case-", dir="/private/tmp"))
    request = process_hook_request(case_id, output)
    process = multiprocessing.get_context("spawn").Process(target=invocation_cut, args=(output, case_id, request))
    process.start()
    process.join(60)
    if process.is_alive():
        process.terminate()
        process.join(10)
        raise AssertionError("The product publication process exceeded its bounded wait")
    consume_process_hook(request, process, expected_exit=97)
    observed = loads((output / "process-source.json").read_bytes())
    assert observed["process_id"] == process.pid != os.getpid()
    assert observed["binding"] == current_binding()
    expected_calls = int(boundary == "budget.resource_settled" or
                         boundary.startswith("artifact.") and boundary != "artifact.transition_before_target_started")
    assert observed["calls"] == expected_calls
    coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
    try:
        sources = InvocationCaseSources(coordinator)
        for key, value in observed["sources"].items():
            setattr(sources, key, value)
        coordinator.clock.reads[:] = observed["clock_reads"]
        capture = ControlTrace(output, version="0.10", ordinary_sources=sources)
        capture.events, capture.observed_records = observed["events"], set(observed["observed_records"])
        coordinator.observer = lambda name, when, value: sources.observer(capture, name, when, value)
        locator = observed["locator"]
        root = output / locator["case_id"] / locator["run_id"]
        key, value = next((row[0], loads(row[1])) for row in coordinator.connection.execute(
            "SELECT capability_id,value FROM invocation_capabilities") if loads(row[1])["state"] == "started")
        completion = value.get("completion_intent")
        leases = InvocationLeases(coordinator)
        port = ArtifactEffectPort(leases, None, key, value["worker_id"], value["invocation_epoch"])
        recover = partial(leases.publish_completion, key, value["worker_id"], value["invocation_epoch"]) if completion else (
            partial(leases.publish_started, key, value["worker_id"], value["invocation_epoch"])
            if boundary == "artifact.transition_before_target_started" else port.publish_budget)
        before_raw = capture.finish(coordinator)
        before_normalized = normalize(before_raw, binding=current_binding())
        (output / "before-raw.json").write_bytes(canonical_bytes(before_raw))
        (output / "before-normalized.json").write_bytes(canonical_bytes(before_normalized))
        from helpers.b04_fault_sources import before_fault
        fault_capture = before_fault(coordinator, output, request, process, before_raw, capture)
        if fault_capture is not None:
            recover = fault_capture.observe(recover)
        failed = False
        if outcome == "integrity_conflict":
            if completion:
                (root / completion["artifact_publication"]["projections"][0]["canonical_path"]).write_bytes(b"changed")
            else:
                (root / "artifact_index.json").write_bytes(b"{")
        elif outcome == "non_materializable_domain_gap":
            with coordinator.transaction() as db:
                db.execute("DELETE FROM invocation_capabilities WHERE capability_id=?", (key,))
        snapshot = run_bytes(root)
        if fault_capture is not None:
            fault_capture.after_fault()
        try:
            recover()
        except ControlIntegrityError:
            failed = True
        if fault_capture is not None:
            fault_capture.recovered()
        assert failed == (outcome in ("integrity_conflict", "non_materializable_domain_gap"))
        if failed:
            after = run_bytes(root)
            changed = {name for name in snapshot if snapshot[name] != after[name]}
            assert set(after) == set(snapshot)
            assert changed <= {"execution_history.jsonl"}
            if changed:
                assert outcome == "integrity_conflict"
                frozen = value["started_intent"] if boundary == "artifact.transition_before_target_started" else value["budget_intents"][-1]
                assert after["execution_history.jsonl"] == frozen["content"].encode()
            snapshot = after
            try:
                recover()
            except ControlIntegrityError:
                pass
            else:
                raise AssertionError("Missing or conflicting original authority was accepted")
            assert run_bytes(root) == snapshot
        else:
            snapshot = run_bytes(root)
            recover()
            assert run_bytes(root) == snapshot
            raw = capture.finish(coordinator)
            normalized = normalize(raw, binding=current_binding())
            (output / "after-raw.json").write_bytes(canonical_bytes(raw))
            (output / "after-normalized.json").write_bytes(canonical_bytes(normalized))
            if boundary == "budget.resource_settled":
                assert len(raw["proof"]["ordinary_publication_prefixes"]) == 1
        ledger = parse_ledger((root / "execution_history.jsonl").read_bytes())
        assert ledger.projection.value["run_status"] == "running"
        if completion is None:
            assert not any(row.get("event") == "finished" for row in ledger.values)
            probe = StructuredOutcomes()
            runtime = CanonicalProductRuntime(coordinator, worker_id=value["worker_id"],
                actor=ActorContext("operator", "human", ("control.internal", "resume", "start")), agent_port=probe)
            stable = run_bytes(root)
            reenter = runtime.run if fault_capture is None else fault_capture.observe(runtime.run)
            for _ in range(2):
                try:
                    reenter(locator)
                except ControlIntegrityError:
                    pass
                else:
                    raise AssertionError("Uncertain product work was reentered")
            assert not probe.contexts and run_bytes(root) == stable
        assert observed["calls"] == expected_calls
        if fault_capture is not None:
            fault_capture.repeated()
        error = "rejected_original_authority" if failed else "exact_budget_suffix_only"
        trace = {"schema_version": "0.1", "events": [
            event("product_publication_cut", target=boundary, phase=PUBLICATIONS[boundary], stage=side,
                  outcome="actual_process_exit", result_digest=digest(before_normalized)),
            event("original_suffix_recovery", target=boundary, stage=side, run_status="running", guard=error,
                  outcome=outcome, invariants=sorted(SPECS[case_id]["invariants"]))]}
        (output / "case-trace.json").write_bytes(canonical_bytes(trace))
        retain_probe_sources(output, request)
        return trace if fault_capture is None else fault_capture.finish()
    finally:
        coordinator.close()
