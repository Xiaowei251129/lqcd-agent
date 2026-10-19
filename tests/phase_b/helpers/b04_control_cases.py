"""Actual product grant and transition faults use the original control owner."""
from harness.temporary import mkdtemp
from functools import partial
from dataclasses import asdict
from pathlib import Path
import multiprocessing
import os

from harness.inventory import case_specs
from harness.pytest_evidence import consume_process_hook, process_hook_request, production_hook
from harness.trace import event, normalize
from helpers.b04_trajectories import trajectory
from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from helpers.ordinary_publication_prefix_sources import PublicationPrefixSources
from helpers.trace_sources import current_binding
from helpers.b04_process_binding import bound_child, retain_probe_sources
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.operations import AdvanceRunRequest
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime, ProductRouteAdapter
from test_b04_product_graph import StructuredOutcomes, diagnostic


ADVANCE = "control.advance_run.not_applicable."
PUBLICATIONS = {
    "budget.decision_before_transition": ADVANCE + "budget_decision_committed",
    "budget.grant_consumed": ADVANCE + "budget_decision_committed",
    "budget.grant_target_allocation": ADVANCE + "target_attempt_scheduled",
    "budget.grant_invalidation": ADVANCE + "target_artifacts_invalidated",
    "budget.grant_transition": ADVANCE + "transition_committed",
    "budget.grant_owner_race": ADVANCE + "budget_decision_committed",
    "budget.terminal_reserve": ADVANCE + "budget_decision_committed",
    "artifact.bundle_before_analysis_transition": ADVANCE + "budget_decision_committed",
    "budget.invalid_response_allow": "invocation.attempt_finished",
    "budget.invalid_response_halt": "invocation.attempt_finished",
}
SPECS = case_specs(PROTOCOL)


def source_receipt(output, case_id, coordinator, capture, sources, *, calls, operation_id, extra=None):
    receipt = {"case_id": case_id, "binding": current_binding(), "process_id": os.getpid(),
        "operation_id": operation_id, "calls": calls, "events": capture.events,
        "observed_records": sorted(capture.observed_records), "clock_reads": coordinator.clock.reads,
        "sources": {key: {k: list(v) for k, v in sources.epochs.items()} if key == "epochs" else getattr(sources, key)
            for key in ("calls", "failures", "grants", "epochs", "maximum_evidence")}, **(extra or {})}
    (coordinator.root / "process-source.json").write_bytes(canonical_bytes(receipt))
    Path(output, "source-root.txt").write_text(str(coordinator.root))
    os._exit(97)


@bound_child
def bundle_cut(output, case_id, hook_request):
    from helpers.b04_code_product import code_product, deliver_product_code
    boundary, side, _ = case_id.rsplit(".", 2)
    hooks, holder = {}, {}
    matched = None
    def observer(name, when, value):
        nonlocal matched
        if name == ADVANCE + "operation_reserved" and when == "after":
            transition = loads(value["reservation"]["canonical_transition_bytes"])
            if transition["source_node"] == "code_agent" and transition["target_node"] == "analysis_engineer":
                matched = value["operation_id"]
                hooks[(PUBLICATIONS[boundary], side)] = (partial(production_hook, case_id, process_request=hook_request),)
        if name == PUBLICATIONS[boundary] and when == side and value["operation_id"] == matched:
            capture = holder["result"]["trace_capture"]
            source_receipt(output, case_id, holder["coordinator"], capture, capture.ordinary_sources,
                calls=len(holder["agent"].contexts), operation_id=matched, extra={"repository": str(holder["host"].base_repository)})
    observer.production_hooks = hooks
    with HostIdentities("b04-bundle-cut-" + case_id).installed():
        coordinator, actor, agent, backend, host, handoff, result = code_product(trace=True, trace_version="0.10", observer=observer)
        holder.update(coordinator=coordinator, agent=agent, host=host, result=result)
        deliver_product_code(coordinator, actor, backend, host, result)
    raise AssertionError("The original Code-to-Analysis publication was not reached")


@bound_child
def invalid_response_cut(output, case_id, hook_request):
    boundary, side, _ = case_id.rsplit(".", 2)
    hooks = {}
    matched = None
    with HostIdentities("b04-invalid-response-" + case_id).installed():
        coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
        sources = PublicationPrefixSources(coordinator)
        capture = ControlTrace(Path(output), version="0.10", ordinary_sources=sources)
        agent = StructuredOutcomes({"analysis_engineer": diagnostic(status="failed", category="tool_failure",
            affected_layer="analysis", retryability="retryable", candidates=["analysis_engineer"], risk="low")})
        submitted = None
        def observer(name, when, value):
            nonlocal matched
            sources.observer(capture, name, when, value)
            if name == "control.resume_run.continue_execution.invocation_authorized" and when == "after":
                matched = value["operation_id"]
                hooks[(PUBLICATIONS[boundary], side)] = (partial(production_hook, case_id, process_request=hook_request),)
            if name == PUBLICATIONS[boundary] and when == side and matched is not None:
                source_receipt(output, case_id, coordinator, capture, sources, calls=len(agent.contexts),
                    operation_id=matched, extra={"resume_request": asdict(submitted)})
        observer.production_hooks = hooks
        coordinator.observer = observer
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        runtime = CanonicalProductRuntime(coordinator, worker_id="product-host", actor=actor, agent_port=sources.agent(agent))
        inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        started = runtime.plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start",
            "balanced_v1" if boundary.endswith("allow") else "phase_b_test"), actor=actor)
        locator = started["result"]["run_locator"]
        runtime.run(locator)
        _, execution = runtime._records(locator)
        state = execution.projection.value
        assert state["run_status"] == "paused"
        payload = {**locator, "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
            "decision": "request_code_change", "conditions": [], "reason": "A real out-of-scope Human decision", "decided_by": "operator"}
        submitted = ResumeRunRequest(locator, state["active_pause"]["pause_id"], "b04-invalid-response", "human_response", payload, digest(payload))
        runtime.resume(submitted, actor=actor)
    raise AssertionError("The original invalid-response publication was not reached")


@bound_child
def advance_cut(output, case_id, hook_request):
    boundary, side, _ = case_id.rsplit(".", 2)
    hooks = {}
    matched = None

    def observer(name, when, value, coordinator, capture, sources, agent):
        nonlocal matched
        if name.startswith(ADVANCE) and name.endswith(".operation_reserved") and when == "after":
            reservation = value["reservation"]
            transition = loads(reservation["canonical_transition_bytes"])
            grant = reservation["grant_consumption_or_not_applicable"]
            wanted = (grant.get("event") == "grant_consumed" if boundary.startswith("budget.grant_") else
                      transition["fields"].get("stop_sequence_id") is not None if boundary == "budget.terminal_reserve" else
                      transition["source_node"] == "method_planner")
            if wanted:
                matched = value["operation_id"]
                hooks[(PUBLICATIONS[boundary], side)] = (partial(production_hook, case_id, process_request=hook_request),)
        if name == PUBLICATIONS[boundary] and when == side and value["operation_id"] == matched:
            receipt = {"case_id": case_id, "binding": current_binding(), "process_id": os.getpid(),
                "operation_id": matched, "calls": len(agent.contexts), "events": capture.events,
                "observed_records": sorted(capture.observed_records), "clock_reads": coordinator.clock.reads,
                "sources": {key: {k: list(v) for k, v in sources.epochs.items()} if key == "epochs" else getattr(sources, key)
                    for key in ("calls", "failures", "grants", "epochs", "maximum_evidence")}}
            (coordinator.root / "process-source.json").write_bytes(canonical_bytes(receipt))
            Path(output, "source-root.txt").write_text(str(coordinator.root))
            os._exit(97)

    observer.production_hooks = hooks
    if boundary.startswith("budget.grant_"):
        trajectory("grant", trace_version="0.10", observer=observer)
    else:
        with HostIdentities("b04-control-" + case_id).installed():
            coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
            sources = PublicationPrefixSources(coordinator)
            capture = ControlTrace(Path(output), version="0.10", ordinary_sources=sources)
            outcomes = {"scientific_reviewer": diagnostic(category="review_incomplete", affected_layer="review",
                retryability="retryable", candidates=["scientific_reviewer"], risk="medium")} if boundary == "budget.terminal_reserve" else None
            agent = StructuredOutcomes(outcomes)
            def collect(name, when, value):
                sources.observer(capture, name, when, value)
                observer(name, when, value, coordinator, capture, sources, agent)
            collect.production_hooks = hooks
            coordinator.observer = collect
            runtime = CanonicalProductRuntime(coordinator, worker_id="product-host",
                actor=ActorContext("operator", "human", ("control.internal", "resume", "start")), agent_port=sources.agent(agent))
            inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
            started = runtime.plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start",
                "phase_b_test" if boundary == "budget.terminal_reserve" else "balanced_v1"), actor=runtime.actor)
            runtime.run(started["result"]["run_locator"])
    raise AssertionError("The original control publication was not reached")


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def grant_racer(pipe, root, request, worker, barrier, capture=None):
    coordinator = Coordinator(root, clock=FakeClock(140, 40))
    try:
        plane = ControlPlane(coordinator, worker_id=worker, route_adapter=ProductRouteAdapter(coordinator))
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        barrier.wait(timeout=30)
        try:
            result = {"result": plane.advance_run(AdvanceRunRequest(**request), actor=actor)}
        except ControlIntegrityError as error:
            result = {"rejected": str(error)}
        if capture is not None:
            result = {**result, "call": {**capture, "entry": "ControlPlane.advance_run", "request": request,
                "actor": asdict(actor), "worker_id": worker, "process_id": os.getpid(),
                "return": result.get("result"), "exception": None if "result" in result else
                    {"type": "ControlIntegrityError", "message": result["rejected"]}}}
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def race_grant(root, request, fault_capture=None):
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(3)
    running = []
    try:
        for position in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=grant_racer, args=(child, root, asdict(request),
                "b04-grant-racer-" + str(position), barrier, None if fault_capture is None else
                {"binding": fault_capture.binding, "case_id": fault_capture.request["case_id"]}))
            process.start()
            child.close()
            running.append((process, parent))
        barrier.wait(timeout=30)
        results = []
        for process, pipe in running:
            assert pipe.poll(60), "The grant contender did not return"
            result = pipe.recv()
            if fault_capture is not None:
                assert result["call"]["process_id"] == process.pid != os.getpid()
                fault_capture.contenders.append(result["call"])
                result = {key: value for key, value in result.items() if key != "call"}
            results.append(result)
            process.join(10)
            assert process.exitcode == 0
        accepted = [value["result"] for value in results if "result" in value]
        (Path(root) / "race-observations.json").write_bytes(canonical_bytes(results))
        terminal = [value for value in accepted if value["operation_status"] != "in_progress"]
        assert terminal and all(value == terminal[0] for value in terminal), results
        for value in accepted:
            assert value["operation_id"] == terminal[0]["operation_id"]
            if value["operation_status"] == "in_progress":
                assert value["result"] is None and value["error"] is None
                assert value["publication_status"] == "materialization_pending" and value["run_status"] is None
                assert value["lease_epoch"] == terminal[0]["lease_epoch"]
                assert value["phase_revision"] <= terminal[0]["phase_revision"]
        return terminal[0], results
    finally:
        for process, pipe in running:
            if process.is_alive():
                process.terminate()
                process.join(10)
            pipe.close()


def exercise_control_case(case_id):
    boundary, side, outcome = case_id.rsplit(".", 2)
    output = Path(mkdtemp(prefix="lqcd-agent-b04-control-case-", dir="/private/tmp"))
    request = process_hook_request(case_id, output)
    target = bundle_cut if boundary.startswith("artifact.") else invalid_response_cut if "invalid_response" in boundary else advance_cut
    process = multiprocessing.get_context("spawn").Process(target=target, args=(output, case_id, request))
    process.start()
    process.join(60)
    if process.is_alive():
        process.terminate()
        process.join(10)
        raise AssertionError("The product control process exceeded its bounded wait")
    consume_process_hook(request, process, expected_exit=97)
    source = Path((output / "source-root.txt").read_text())
    observed = loads((source / "process-source.json").read_bytes())
    assert observed["binding"] == current_binding() and observed["process_id"] == process.pid != os.getpid()
    coordinator = Coordinator(source, clock=PassiveClock(FakeClock(100, 0)))
    try:
        sources = PublicationPrefixSources(coordinator)
        for key, value in observed["sources"].items(): setattr(sources, key, value)
        coordinator.clock.reads[:] = observed["clock_reads"]
        capture = ControlTrace(source, version="0.10", ordinary_sources=sources)
        capture.events, capture.observed_records = observed["events"], set(observed["observed_records"])
        coordinator.observer = lambda name, when, value: sources.observer(capture, name, when, value)
        owner = coordinator.get(observed["operation_id"])
        raw = capture.finish(coordinator)
        projected = normalize(raw, binding=current_binding())
        for name, value in (("before-raw", raw), ("before-normalized", projected)):
            (output / (name + ".json")).write_bytes(canonical_bytes(value))
        from helpers.b04_fault_sources import before_fault
        fault_capture = before_fault(coordinator, output, request, process, raw, capture)
        root = source / owner["request"]["run_locator"]["case_id"] / owner["request"]["run_locator"]["run_id"]
        if outcome == "integrity_conflict":
            with (root / "execution_history.jsonl").open("ab") as stream: stream.write(b"{")
            # Corrupt bytes are rejection evidence, never accepted source material.
            coordinator.observer = None
        elif outcome == "non_materializable_domain_gap":
            with coordinator.transaction() as db:
                db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (owner["operation_id"],))
        if fault_capture is not None:
            fault_capture.after_fault()
        coordinator.clock.subject.advance(40)
        handoff = None
        if "repository" in observed:
            from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
            spec = loads(owner["reservation"]["target_preparation_snapshot"]["canonical_spec_bytes"])
            handoff = AnalysisHandoff(coordinator, observed["repository"], allowed_command=spec["allowed_command"])
        adapter = ProductRouteAdapter(coordinator, handoff)
        plane = ControlPlane(coordinator, worker_id="product-host", route_adapter=adapter,
                             resume_decision_adapter=adapter, preparation_adapter=handoff)
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        if "resume_request" in observed:
            from lqcd_agent.graph.nodes import ProductNode
            probe = StructuredOutcomes()
            plane.resume_target_adapter = ProductNode(root, probe)
            control_request = ResumeRunRequest(**observed["resume_request"])
            recover = partial(plane.resume_run, control_request, actor=actor)
        else:
            control_request = AdvanceRunRequest(owner["request"]["run_locator"], owner["request"]["source_attempt_id"], owner["idempotency_key"])
            recover = partial(plane.advance_run, control_request, actor=actor)
        if fault_capture is not None:
            recover = fault_capture.observe(recover)
        if boundary == "budget.grant_owner_race":
            result, contenders = race_grant(source, control_request, fault_capture)
            (output / "race-results.json").write_bytes(canonical_bytes(contenders))
        else:
            result = recover()
        if fault_capture is not None:
            fault_capture.recovered(contenders=contenders if boundary == "budget.grant_owner_race" else None)
        assert result["operation_id"] == owner["operation_id"] and result["operation_status"] != "in_progress"
        if outcome in ("committed_result_replay", "materializable_publication_prefix"):
            assert result["operation_status"] == "committed"
            ledger = parse_ledger((root / "execution_history.jsonl").read_bytes())
            grants = [row for row in ledger.values if row.get("event") == "grant_consumed"]
            assert len(grants) == int(boundary.startswith("budget.grant_"))
            if "resume_request" in observed:
                decisions = [row for row in ledger.values if row.get("event") == "decision_recorded" and row["payload"]["proposed_action"] == "repause"]
                assert len(decisions) == 1 and decisions[0]["payload"]["decision"] == ("allow" if boundary.endswith("allow") else "halt")
                assert not probe.contexts
        else:
            assert result["operation_status"] in ("failed", "recovery_required") and result["run_status"] is None
        stable = files(root)
        assert recover() == result and files(root) == stable
        if fault_capture is not None:
            fault_capture.repeated()
        trace = {"schema_version": "0.1", "events": [
            event("product_control_cut", target=boundary, phase=PUBLICATIONS[boundary], stage=side,
                  result_digest=digest(projected), outcome="actual_process_exit"),
            event("original_control_recovery", target=boundary, status=result["operation_status"],
                  phase=result["operation_phase"], lease_epoch=result["lease_epoch"], run_status=result["run_status"],
                  outcome=outcome, invariants=sorted(SPECS[case_id]["invariants"]))]}
        for name, value in (("result", result), ("case-trace", trace)):
            (output / (name + ".json")).write_bytes(canonical_bytes(value))
        retain_probe_sources(output, request, source=source)
        return trace if fault_capture is None else fault_capture.finish()
    finally:
        coordinator.close()
