"""C11 passive Clock/source capture and original-port maximum meta scenarios."""
from harness.temporary import mkdtemp
from copy import deepcopy
from pathlib import Path
import sys

from helpers.ordinary_sources import OrdinarySources, captured_source
from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from lqcd_agent.control.capabilities import InvocationLeases, ArtifactEffectPort, TargetOutcome
from lqcd_agent.control.clock import FakeClock, Timestamp
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.operations import CloseRunRequest
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.strict_json import canonical_bytes, digest
from lqcd_agent.control.budget import usage


class PassiveClock:
    def __init__(self, subject):
        self.subject, self.reads = subject, []

    @property
    def epoch_id(self):
        return self.subject.epoch_id

    def now(self):
        caller = sys._getframe(1).f_back
        resource = caller.f_locals.get("stable_id") if caller.f_code.co_name == "run_resource" else None
        try:
            stamp = self.subject.now()
        except BaseException as error:
            self.reads.append({"resource": resource, "timestamp": None, "error": {"type": type(error).__name__, "message": str(error)}})
            raise
        self.reads.append({"resource": resource, "timestamp": deepcopy(vars(stamp)), "error": None})
        return stamp


class MaximumSources(OrdinarySources):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.epochs, self.maximum_evidence = {}, {}

    def invoke(self, capability_id, input_value, config_value, effect, *, profile="primitive"):
        epoch = self.coordinator.clock.epoch_id
        try:
            return super().invoke(capability_id, input_value, config_value, effect, profile=profile)
        finally:
            self.epochs[self.calls[-1]["reservation_head"]] = (epoch, self.coordinator.clock.epoch_id)

    def settle(self, port, error, *, host_receipt=False):
        call = self.calls[-1]
        producer = self.coordinator.get(call["authorization"]["producer_operation_id"])
        resource = next(r["payload"]["resource_operation_id"] for r in parse_ledger(
            (self.coordinator.root / call["authorization"]["identity"]["case_id"] / call["authorization"]["identity"]["run_id"] / "execution_history.jsonl").read_bytes()).values
            if digest(r) == call["reservation_head"])
        evidence = {"type": type(error).__name__, "message": str(error)}
        if host_receipt:
            assert call["exception"] == evidence and call["outcome"] is None
            evidence = {"schema_version": "0.1", "resource_operation_id": resource, "exception": evidence}
        port.append_budget("resource_settled", {"resource_operation_id": resource, "actual": None, "tokens": usage(), "cost": usage(),
            "evidence_digest": digest(evidence), **{k: producer[k] for k in ("operation_id", "lease_epoch", "phase_revision")}})
        self.maximum_evidence[call["reservation_head"]] = captured_source("maximum_evidence", evidence)

    def finish(self, trace):
        super().finish(trace)
        proof = trace["proof"]
        proof.update(schema_version="0.4", ordinary_maximum_settlements=[])
        records = {r["sha256"]: r["value"] for r in proof["objects"] if r["kind"] == "execution_0_4"}
        for call in self.calls:
            record = records[call["reservation_head"]]
            payload = record["payload"]
            settled = [r for r in records.values() if r.get("event") == "resource_settled" and
                       r["case_id"] == record["case_id"] and r["run_id"] == record["run_id"] and
                       r["payload"]["resource_operation_id"] == payload["resource_operation_id"] and r["payload"]["actual"] is None]
            if not settled:
                continue
            assert len(settled) == 1
            reads = [r for r in self.coordinator.clock.reads if r["resource"] == payload["resource_operation_id"]]
            assert reads and reads[0]["timestamp"] is not None
            start = reads[0]["timestamp"]
            end = reads[1]["timestamp"] if len(reads) == 2 else None
            raised = call["exception"] is not None
            before, after = self.epochs[call["reservation_head"]]
            clock_error = reads[-1]["error"]
            state = "callee_raised_before_end" if raised else "read_failed" if clock_error else "complete"
            assert len(reads) == (1 if raised else 2)
            bad = clock_error or before != after or end is not None and (start["source"] != end["source"] or
                   end["wall_seconds"] < start["wall_seconds"] or end["monotonic_seconds"] < start["monotonic_seconds"])
            duration = None if bad or end is None else end["monotonic_seconds"] - start["monotonic_seconds"]
            reason = "clock_untrusted" if bad else "callee_exception" if raised else "duration_overrun"
            measurement = {"llm_calls": int(payload["resource_kind"] == "llm_call"), "tool_calls": int(payload["resource_kind"] == "tool_call"),
                           "verification_commands": 0, "active_seconds": duration}
            observation = {"schema_version": "0.1", "resource_operation_id": payload["resource_operation_id"],
                "call_disposition": "raised" if raised else "returned", "clock_read_state": state,
                "clock_epoch_before": before, "clock_epoch_after": after, "start_at": start, "end_at": end,
                "hard_usage": {"state": "unknown" if duration is None else "known", "value": None if duration is None else measurement},
                "host_error": clock_error}
            proof["ordinary_maximum_settlements"].append({"schema_version": "0.1", "reservation_head": call["reservation_head"],
                "settlement_head": digest(settled[0]), "capability_id": call["capability_id"], "reason_code": reason,
                "evidence": deepcopy(self.maximum_evidence[call["reservation_head"]]), "observation": captured_source("maximum_observation", observation)})
        return trace


def maximum_trace(*, mode="exception", kind="llm_call", message="Uncertain provider completion", result="bounded", close=True, scoped=False, host_receipt=False):
    output = Path(mkdtemp(prefix="lqcd-agent-b00c11-maximum-", dir="/private/tmp"))
    clock = PassiveClock(FakeClock(100, 0))
    identities = HostIdentities("b00c11-" + mode + "-" + kind + ("-scoped" if scoped else ""))
    with identities.installed():
        coordinator = Coordinator(output, clock=clock)
        sources = MaximumSources(coordinator)
        capture = ControlTrace(output, version="0.7", ordinary_sources=sources)
        coordinator.observer = capture.observer
        actor = ActorContext("operator", "human", ("control.internal", "start"))
        plane = ControlPlane(coordinator, worker_id="host")
        inputs = {"root_goal": {"goal": "Maximum source meta"}, "input_snapshot": {"data": "synthetic"}}
        calls = []
        try:
            started = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "phase_b_test"), actor=actor)
            capability = started["result"]["capability_id"]
            leases = InvocationLeases(coordinator)
            leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
            def effect():
                calls.append("effect")
                if mode in ("epoch", "exception_epoch"):
                    clock.subject.epoch_id = "fake_clock_epoch_2"
                elif mode == "overrun":
                    clock.subject.advance(2)
                elif mode == "regression":
                    clock.subject._current = Timestamp("deterministic_harness", 99, 0)
                if mode in ("exception", "exception_epoch", "unsettled", "unsafe"):
                    raise RuntimeError(message)
                return result
            class Target:
                def invoke_scoped(self, identity, port):
                    try:
                        if scoped:
                            from lqcd_agent.graph.state import product_context
                            value = product_context(output / identity["case_id"] / identity["run_id"], identity)
                            port.run_resource(resource_kind="llm_call", resource_id="call", input_digest=digest(value),
                                config_digest=digest({"node": identity["attempt_kind"], "structured_output": True}), timeout_seconds=1,
                                effect=lambda: sources.invoke(capability, value, {"node": identity["attempt_kind"], "structured_output": True}, effect, profile="scoped_llm"))
                        else:
                            sources.resource(port, resource_kind=kind, resource_id="call", input_value="input", config_value="config", timeout_seconds=1, effect=effect)
                    except ValueError as error:
                        sources.settle(port, error, host_receipt=host_receipt)
                    except RuntimeError as error:
                        sources.settle(port, error, host_receipt=host_receipt)
                    return TargetOutcome("failed", {"current_artifact_ids": {}}, {"type": "ResourceFailure", "message": "Original maximum retained"})
            if mode in ("unsettled", "unsafe", "regression"):
                leases.start_intent(capability, "consumer", 1)
                state = leases.publish_started(capability, "consumer", 1)
                port = ArtifactEffectPort(leases, None, capability, "consumer", 1)
                try:
                    sources.resource(port, resource_kind=kind, resource_id="call", input_value="input", config_value="config", timeout_seconds=1, effect=effect)
                except (RuntimeError, ValueError):
                    pass
                closure = None
                if mode == "unsafe":
                    clock.subject.advance(11)
                    try:
                        sources.settle(port, RuntimeError(message))
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("Expired authority must not settle")
            else:
                state = leases.invoke(capability, "consumer", 1, Target())
                closure = plane.close_run(CloseRunRequest(started["result"]["run_locator"], state["execution_head"]), actor=actor) if close else None
            trace = capture.finish(coordinator)
            (output / "raw.json").write_bytes(canonical_bytes(trace))
            (output / "allocations.json").write_bytes(canonical_bytes(identities.allocations))
            facts = {"effect_count": len(calls), "state": state, "closure": closure, "clock_reads": clock.reads, "B04_owned": False}
            (output / "facts.json").write_bytes(canonical_bytes(facts))
            return trace, output, facts
        finally:
            coordinator.close()
