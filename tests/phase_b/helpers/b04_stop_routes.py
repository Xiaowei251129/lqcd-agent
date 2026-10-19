"""Product stop contexts delegate to the original typed control operations."""
from harness.temporary import mkdtemp
from pathlib import Path

from helpers.b04_code_product import code_product
from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from helpers.ordinary_publication_prefix_sources import PublicationPrefixSources
from lqcd_agent.code_agent.external_operation import CodeExternalStop, CodeWatchdog
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.operations import CloseRunRequest
from lqcd_agent.control.pause import CancelPauseRequest, ResolveExternalInterruptRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
from test_b04_product_graph import StructuredOutcomes, diagnostic


MODES = ("cancel", "timeout", "live_halt", "live_integrity", "ordinary_halt", "normal_end", "attached_halt")


def stop_route_trace(mode, *, trace_version="0.10"):
    assert mode in MODES
    with HostIdentities("b04-stop-" + mode).installed():
        external = mode in ("timeout", "live_halt", "live_integrity", "attached_halt")
        if external:
            coordinator, actor, agent, backend, host, handoff, result = code_product(
                status="failed" if mode == "timeout" else "success", trace=True, trace_version=trace_version)
            runtime, locator, capture = result["runtime"], result["run_locator"], result["trace_capture"]
            producer, = backend.dispatches
            runtime.plane.external_adapter = CodeExternalStop(coordinator, backend, host.containment, backend.read_receipt)
        else:
            output = Path(mkdtemp(prefix="lqcd-agent-b04-stop-", dir="/private/tmp"))
            coordinator = Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))
            if trace_version == "0.11":
                from helpers.unconsumed_code_final_sources import UnconsumedCodeSources
                sources = UnconsumedCodeSources(coordinator)
            else:
                sources = PublicationPrefixSources(coordinator)
            capture = ControlTrace(output, version=trace_version, ordinary_sources=sources)
            coordinator.observer = lambda name, side, value: sources.observer(capture, name, side, value)
            actor = ActorContext("operator", "human", ("cancel", "control.internal", "resume", "start"))
            agent = StructuredOutcomes({"method_planner": diagnostic(human_need="approval", risk="critical")} if mode == "cancel" else {})
            runtime = CanonicalProductRuntime(coordinator, worker_id="product-host", actor=actor, agent_port=sources.agent(agent))
            inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
            started = runtime.plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"), actor=actor)
            locator = started["result"]["run_locator"]
        try:
            if mode in ("cancel", "normal_end"):
                runtime.run(locator)
            root, execution = runtime._records(locator)
            state = execution.projection.value
            if mode == "cancel":
                request = CancelPauseRequest(locator, state["active_pause"]["pause_id"], "b04-stop-cancel", "operator_cancel")
                run = lambda: runtime.plane.cancel_pause(request, actor=actor)
            elif mode == "timeout":
                coordinator.clock.subject.advance(11)
                watchdog = CodeWatchdog(coordinator, backend, host.containment, backend.read_receipt)
                run = lambda: watchdog.enforce(producer)
            elif mode in ("live_halt", "live_integrity"):
                reason = "terminal_operator_stop" if mode == "live_halt" else "proven_integrity_trigger"
                trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": reason}
                reference = "product_stop_trigger.json"
                (root / reference).write_bytes(canonical_bytes(trigger))
                request = ResolveExternalInterruptRequest(locator, producer, reason, reference, digest(trigger))
                run = lambda: runtime.plane.resolve_external_interrupt(request, actor=actor)
            elif mode == "attached_halt":
                audit, patch = backend.deliveries[producer]
                assert host.finalize(producer, tool_audit=audit, patch=patch)["operation_status"] == "completed"
                _, execution = runtime._records(locator)
                request = CloseRunRequest(locator, execution.projection.value["execution_head"], "terminal_operator_stop")
                run = lambda: runtime.plane.close_run(request, actor=actor)
            elif mode == "ordinary_halt":
                request = CloseRunRequest(locator, state["execution_head"], "terminal_operator_stop")
                run = lambda: runtime.plane.close_run(request, actor=actor)
            else:
                owner, = [coordinator.get(row[0]) for row in coordinator.connection.execute(
                    "SELECT operation_id FROM control_operations WHERE operation_type='close_run'")]
                request = CloseRunRequest(locator, owner["request"]["trigger"]["execution_head"])
                run = lambda: runtime.plane.close_run(request, actor=actor)
            result = run()
            assert result["operation_status"] == "committed"
            stable = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            calls = len(agent.contexts)
            assert run() == result
            assert stable == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            assert len(agent.contexts) == calls
            owner = coordinator.get(result["operation_id"])
            assert owner["operation_type"] == ("cancel_pause" if mode == "cancel" else "resolve_external_interrupt" if mode in (
                "timeout", "live_halt", "live_integrity") else "close_run")
            if mode == "timeout":
                assert result["run_status"] == "running" and owner["operation_variant"] == "recoverable_timeout"
                runtime.run(locator)
                _, after = runtime._records(locator)
                assert after.projection.value["run_status"] == "paused"
                transition = next(row for row in after.values if row["record_type"] == "transition" and row["source_node"] == "code_agent")
                assert transition["target_node"] == "decision_coordinator"
                capability = next(loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM invocation_capabilities")
                    if loads(row[0])["authorization"]["identity"]["attempt_id"] == transition["target_attempt_id"])
                assert coordinator.get(capability["authorization"]["producer_operation_id"])["operation_type"] == "advance_run"
            elif mode.startswith("live_"):
                assert result["run_status"] == ("halted" if mode == "live_halt" else "failed")
                before = list(coordinator.connection.execute("SELECT operation_id FROM control_operations"))
                try:
                    runtime.plane.close_run(CloseRunRequest(locator, runtime._records(locator)[1].projection.value["execution_head"],
                        "terminal_operator_stop"), actor=actor)
                except ControlIntegrityError:
                    pass
                else:
                    raise AssertionError("An interrupt winner acquired a second terminal operation")
                assert before == list(coordinator.connection.execute("SELECT operation_id FROM control_operations"))
            raw = capture.finish(coordinator)
            facts = {"mode": mode, "operation_type": owner["operation_type"], "variant": owner["operation_variant"],
                "run_status": runtime._records(locator)[1].projection.value["run_status"], "duplicate_readonly": True}
            for name, value in (("raw", raw), ("facts", facts)):
                (coordinator.root / ("b04-stop-" + name + ".json")).write_bytes(canonical_bytes(value))
            return raw, coordinator.root, facts
        finally:
            coordinator.close()
