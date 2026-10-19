"""Actual original budget suffixes retain single effects and original ownership."""
from harness.temporary import mkdtemp
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import os
import multiprocessing
import shutil

import pytest

from helpers.control_traces import ControlTrace
from helpers.host_identity_fixture import HostIdentities
from helpers.ordinary_maximum import PassiveClock
from helpers.product_failure_sources import ProductFailureSources
from helpers.trace_sources import current_binding
from harness.trace import normalize
from lqcd_agent.control.capabilities import ArtifactEffectPort, InvocationLeases
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.strict_json import digest, canonical_bytes, loads
from lqcd_agent.graph.nodes import ProductNode
from lqcd_agent.graph.run_graph import run_canonical_graph
from test_b04_product_graph import StructuredOutcomes, diagnostic
from test_b00c13_human_continuation import resume_request, records, files


class BoundaryInterruption(BaseException):
    """A Python interruption is explicitly distinct from a dead process."""


@pytest.mark.parametrize("event", ["failure_observed", "grant_issued"])
@pytest.mark.parametrize("side", ["before", "after"])
def test_budget_suffix_never_reobserves_or_dispatches(event, side):
    for _ in range(2):
        output = Path(mkdtemp(prefix="lqcd-agent-b00c15-budget-", dir="/private/tmp"))
        with HostIdentities("b00c15-budget-" + event + "-" + side).installed(), closing(Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))) as coordinator:
            sources = ProductFailureSources(coordinator)
            capture = ControlTrace(output, version="0.8", ordinary_sources=sources)
            interruptions = []
            def observer(name, when, value):
                sources.observer(capture, name, when, value)
                if name == "budget." + event and when == side:
                    interruptions.append(deepcopy(value))
                    raise BoundaryInterruption()
            coordinator.observer = observer
            failed = diagnostic(status="failed", category="tool_failure", affected_layer="analysis",
                                retryability="retryable", candidates=["analysis_engineer"], risk="low")
            agent = StructuredOutcomes({"analysis_engineer": [failed, diagnostic()]})
            actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
            inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
            with pytest.raises(BoundaryInterruption):
                result = run_canonical_graph(coordinator=coordinator, actor=actor, agent_port=sources.agent(agent),
                    request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"))
                assert event == "grant_issued"
                result["runtime"].resume(resume_request(result, result["state"], "approve_budget_window"), actor=actor)
            assert len(interruptions) == 1
            root, = output.glob("*/*/execution_history.jsonl")
            root = root.parent
            leases = InvocationLeases(coordinator)
            capabilities = [(row[0], row[1]) for row in coordinator.connection.execute("SELECT capability_id,value FROM invocation_capabilities")]
            capability_id, = [key for key, _ in capabilities if any(e["record"] == interruptions[0]["record"] for e in leases.get(key)[1].get("budget_intents", []))]
            _, original = leases.get(capability_id)
            assert original["state"] == "started" and original.get("completion") is None
            port = ArtifactEffectPort(leases, None, capability_id, original["worker_id"], original["invocation_epoch"])
            coordinator.observer = lambda name, when, value: sources.observer(capture, name, when, value)
            journal = deepcopy(original["budget_intents"])
            calls = len(agent.contexts)
            assert calls == 2
            public = [r for r in records(root).values if r.get("event") == event]
            assert len(public) == int(side == "after")
            port.publish_budget()
            port.publish_budget()
            _, restored = leases.get(capability_id)
            assert all(e["published"] for e in restored["budget_intents"])
            assert [{k: v for k, v in e.items() if k != "published"} for e in restored["budget_intents"]] == [
                {k: v for k, v in e.items() if k != "published"} for e in journal]
            public = [r for r in records(root).values if r.get("event") == event]
            assert len(public) == 1 and public[0] == interruptions[0]["record"]
            before = files(root)
            with pytest.raises(ValueError):
                leases.invoke(capability_id, original["worker_id"], original["invocation_epoch"], ProductNode(root, sources.agent(agent)))
            assert len(agent.contexts) == calls and files(root) == before
            assert records(root).projection.value["run_status"] == "running"
            trace = capture.finish(coordinator)
            assert normalize(trace, binding=current_binding())
            (output / "facts.json").write_bytes(canonical_bytes({"event": event, "side": side, "interruption": "python_base_exception",
                "original_owner_suffix": True, "complete_target_facts": False, "reexecution_unavailable": True,
                "resource_effects": calls, "work_after_grant": 0, "B04_owned": False}))


def interrupted_budget_source(output, event, boundary, side, interruption):
    """Persist passive observations before a real exception or process exit."""
    output = Path(output)
    with HostIdentities("c18-budget-" + event + "-" + boundary + "-" + side).installed(), closing(
            Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))) as coordinator:
        sources = ProductFailureSources(coordinator)
        capture = ControlTrace(output, version="0.8", ordinary_sources=sources)
        agent = StructuredOutcomes({"analysis_engineer": [diagnostic(status="failed", category="tool_failure",
            affected_layer="analysis", retryability="retryable", candidates=["analysis_engineer"], risk="low"), diagnostic()]})
        selected = []

        def observer(name, when, value):
            sources.observer(capture, name, when, value)
            if name == "budget." + event and when == "before":
                selected.extend(row[0] for row in coordinator.connection.execute("SELECT capability_id,value FROM invocation_capabilities")
                    if any(e["record"] == value["record"] for e in loads(row[1]).get("budget_intents", [])))
                assert len(selected) == 1
            if not selected or name != boundary or when != side:
                return
            _, capability = InvocationLeases(coordinator).get(selected[0])
            if not boundary.startswith("budget.") and capability.get("completion_intent") is None:
                return
            receipt = {"event": event, "boundary": boundary, "side": side, "interruption": interruption,
                "pid": os.getpid(), "capability_id": selected[0], "calls": len(agent.contexts),
                "advance_operation_id": value["operation_id"] if name.startswith("control.advance_run.") else None,
                "events": capture.events, "observed_records": sorted(capture.observed_records),
                "clock_reads": coordinator.clock.reads,
                "sources": {"calls": sources.calls, "failures": sources.failures, "grants": sources.grants,
                    "epochs": {k: list(v) for k, v in sources.epochs.items()}, "maximum_evidence": sources.maximum_evidence}}
            (output / "fault-receipt.json").write_bytes(canonical_bytes(receipt))
            if interruption == "process_exit":
                os._exit(97)
            raise BoundaryInterruption()

        coordinator.observer = observer
        actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
        inputs = {"root_goal": {"goal": "Validate the synthetic observable"}, "input_snapshot": {"data": "synthetic"}}
        try:
            result = run_canonical_graph(coordinator=coordinator, actor=actor, agent_port=sources.agent(agent),
                request=StartRunRequest("case", inputs, digest(inputs), "start", "balanced_v1"))
            assert event == "grant_issued"
            result["runtime"].resume(resume_request(result, result["state"], "approve_budget_window"), actor=actor)
        except BoundaryInterruption:
            assert interruption == "python_base_exception"
        else:
            raise AssertionError("The original publication boundary was not reached")


def recover_budget_source(output):
    """Use the durable original owner, never acquire or invoke a new target."""
    receipt = loads((output / "fault-receipt.json").read_bytes())
    with closing(Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))) as coordinator:
        sources = ProductFailureSources(coordinator)
        for name, value in receipt["sources"].items():
            setattr(sources, name, value)
        coordinator.clock.reads[:] = receipt["clock_reads"]
        capture = ControlTrace(output, version="0.8", ordinary_sources=sources)
        capture.events, capture.observed_records = receipt["events"], set(receipt["observed_records"])
        coordinator.observer = lambda name, side, value: sources.observer(capture, name, side, value)
        leases = InvocationLeases(coordinator)
        capability_id = receipt["capability_id"]
        _, original = leases.get(capability_id)
        root = output / original["authorization"]["identity"]["case_id"] / original["authorization"]["identity"]["run_id"]
        (output / "original-journal.json").write_bytes(canonical_bytes(original))
        shutil.copytree(root, output / "before-recovery" / root.parent.name / root.name)
        prefix_trace = capture.finish(coordinator)
        (output / "prefix-raw.json").write_bytes(canonical_bytes(prefix_trace))
        (output / "prefix-normalized.json").write_bytes(canonical_bytes(normalize(prefix_trace, binding=current_binding())))
        assert original["state"] == "started" and receipt["calls"] == 2
        before_budget = deepcopy(original["budget_intents"])
        worker, epoch = original["worker_id"], original["invocation_epoch"]
        frozen = original.get("completion_intent") is not None
        if frozen:
            completion = deepcopy(original["completion_intent"])
            leases.publish_completion(capability_id, worker, epoch)
            published_files = files(root)
            leases.publish_completion(capability_id, worker, epoch)
            assert files(root) == published_files
            _, restored = leases.get(capability_id)
            assert restored["state"] == "finished"
            assert {k: v for k, v in restored["completion_intent"].items() if k != "published"} == {
                k: v for k, v in completion.items() if k != "published"}
        else:
            port = ArtifactEffectPort(leases, None, capability_id, worker, epoch)
            port.publish_budget()
            port.publish_budget()
            with pytest.raises(ValueError, match="Missing frozen invocation completion"):
                leases.publish_completion(capability_id, worker, epoch)
            _, restored = leases.get(capability_id)
            assert restored["state"] == "started" and restored.get("completion_intent") is None
        assert [{k: v for k, v in e.items() if k != "published"} for e in restored["budget_intents"]] == [
            {k: v for k, v in e.items() if k != "published"} for e in before_budget]
        event, = [r for r in records(root).values if r.get("event") == receipt["event"]]
        assert event == before_budget[-1]["record"]
        agent = StructuredOutcomes()
        before = files(root)
        with pytest.raises(ValueError):
            leases.invoke(capability_id, worker, epoch, ProductNode(root, sources.agent(agent)))
        assert not agent.contexts and files(root) == before
        trace = capture.finish(coordinator)
        (output / "raw.json").write_bytes(canonical_bytes(trace))
        normalized = normalize(trace, binding=current_binding())
        (output / "normalized.json").write_bytes(canonical_bytes(normalized))
        facts = {"event": receipt["event"], "boundary": receipt["boundary"], "side": receipt["side"],
            "interruption": receipt["interruption"], "completion_frozen": frozen, "resource_effects": receipt["calls"],
            "original_owner_suffix": True, "new_effects": 0, "run_status": records(root).projection.value["run_status"],
            "B04_owned": False}
        (output / "facts.json").write_bytes(canonical_bytes(facts))
        print("BUDGET_PUBLICATION_EVIDENCE", output)
        return facts


@pytest.mark.parametrize("event", ["failure_observed", "grant_issued"])
@pytest.mark.parametrize("boundary", ["invocation.completion_intent", "invocation.attempt_finished",
    "invocation.artifact_index_replace", "checkpoint.sqlite_commit"])
@pytest.mark.parametrize("side", ["before", "after"])
def test_frozen_completion_original_suffix_dual_fresh(event, boundary, side):
    facts = []
    for _ in range(2):
        output = Path(mkdtemp(prefix="lqcd-agent-c18-completion-", dir="/private/tmp"))
        interrupted_budget_source(output, event, boundary, side, "python_base_exception")
        facts.append(recover_budget_source(output))
    assert facts[0] == facts[1]


@pytest.mark.parametrize("event", ["failure_observed", "grant_issued"])
@pytest.mark.parametrize("boundary_kind", ["budget", "completion", "finished", "index", "checkpoint"])
@pytest.mark.parametrize("side", ["before", "after"])
def test_real_process_death_preserves_original_budget_prefix(event, boundary_kind, side):
    boundary = {"budget": "budget." + event, "completion": "invocation.completion_intent",
                "finished": "invocation.attempt_finished", "index": "invocation.artifact_index_replace",
                "checkpoint": "checkpoint.sqlite_commit"}[boundary_kind]
    facts = []
    for _ in range(2):
        output = Path(mkdtemp(prefix="lqcd-agent-c18-process-", dir="/private/tmp"))
        process = multiprocessing.get_context("spawn").Process(target=interrupted_budget_source,
            args=(output, event, boundary, side, "process_exit"))
        process.start()
        process.join(60)
        if process.is_alive():
            process.terminate()
            process.join(10)
            pytest.fail("The independent publication process exceeded its bounded wait")
        assert process.exitcode == 97 and process.pid != os.getpid()
        receipt = loads((output / "fault-receipt.json").read_bytes())
        assert receipt["pid"] == process.pid
        facts.append(recover_budget_source(output))
    assert facts[0] == facts[1]


def recover_grant_advance(output):
    """Complete the frozen original Transition before running its one target."""
    from lqcd_agent.control.interfaces import ControlPlane
    from lqcd_agent.control.operations import AdvanceRunRequest
    from lqcd_agent.graph.analysis_graph import ProductRouteAdapter

    receipt = loads((output / "fault-receipt.json").read_bytes())
    with closing(Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))) as coordinator:
        sources = ProductFailureSources(coordinator)
        for name, value in receipt["sources"].items():
            setattr(sources, name, value)
        coordinator.clock.reads[:] = receipt["clock_reads"]
        capture = ControlTrace(output, version="0.8", ordinary_sources=sources)
        capture.events, capture.observed_records = receipt["events"], set(receipt["observed_records"])
        coordinator.observer = lambda name, side, value: sources.observer(capture, name, side, value)
        original = coordinator.get(receipt["advance_operation_id"])
        assert original["operation_type"] == "advance_run" and original["status"] == "in_progress"
        snapshot = coordinator.snapshot(original["operation_id"])
        (output / "original-operation.json").write_bytes(canonical_bytes(original))
        (output / "original-snapshot.json").write_bytes(canonical_bytes(snapshot))
        locator = original["request"]["run_locator"]
        root = output / locator["case_id"] / locator["run_id"]
        shutil.copytree(root, output / "before-recovery" / root.parent.name / root.name)
        prefix = records(root)
        issued, = [r for r in prefix.values if r.get("event") == "grant_issued"]
        target = issued["payload"]["target_attempt_id"]
        assert receipt["calls"] == 2 and not any(r.get("attempt_id") == target and r["event"] == "started" for r in prefix.values)
        raw = capture.finish(coordinator)
        (output / "prefix-raw.json").write_bytes(canonical_bytes(raw))
        (output / "prefix-normalized.json").write_bytes(canonical_bytes(normalize(raw, binding=current_binding())))
        actor = ActorContext(**{**original["request"]["actor"], "scopes": tuple(original["request"]["actor"]["scopes"])})
        request = AdvanceRunRequest(locator, original["request"]["source_attempt_id"], original["idempotency_key"])
        plane = ControlPlane(coordinator, worker_id=original["worker_owner_id"], route_adapter=ProductRouteAdapter(coordinator))
        result = plane.advance_run(request, actor=actor)
        assert result["operation_id"] == original["operation_id"] and result["operation_status"] == "committed"
        assert coordinator.snapshot(original["operation_id"]) == snapshot
        rows = records(root).values
        consumed, = [r for r in rows if r.get("event") == "grant_consumed"]
        transition, = [r for r in rows if r.get("transition_id") == issued["payload"]["transition_id"] and r["record_type"] == "transition"]
        allocation, = [r for r in rows if r.get("attempt_id") == target and r["event"] == "scheduled"]
        assert consumed["event_index"] < allocation["event_index"] < transition["event_index"]
        before, operation = files(root), coordinator.get(original["operation_id"])
        assert plane.advance_run(request, actor=actor) == result
        assert files(root) == before and coordinator.get(original["operation_id"]) == operation
        leases = InvocationLeases(coordinator)
        capability_id = result["result"]["capability_id"]
        _, value = leases.get(capability_id)
        leases.acquire(capability_id, original["worker_owner_id"], expected_epoch=value["invocation_epoch"], lease_seconds=10)
        _, leased = leases.get(capability_id)
        agent = StructuredOutcomes()
        leases.invoke(capability_id, leased["worker_id"], leased["invocation_epoch"], ProductNode(root, sources.agent(agent)))
        before = files(root)
        with pytest.raises(ValueError):
            leases.invoke(capability_id, leased["worker_id"], leased["invocation_epoch"], ProductNode(root, sources.agent(agent)))
        assert len(agent.contexts) == 1 and files(root) == before
        assert sum(r.get("event") == "grant_issued" for r in records(root).values) == 1
        assert sum(r.get("event") == "grant_consumed" for r in records(root).values) == 1
        trace = capture.finish(coordinator)
        (output / "raw.json").write_bytes(canonical_bytes(trace))
        (output / "normalized.json").write_bytes(canonical_bytes(normalize(trace, binding=current_binding())))
        committed = [e for e in trace["events"] if e["operation_id"] == original["operation_id"] and e["phase"] == "result_committed"]
        assert len(committed) == 1
        if receipt["boundary"].endswith(".result_committed") and receipt["side"] == "after":
            from harness.strict_json import Invalid
            observed = [e for e in capture.events if e["operation_id"] == original["operation_id"] and e["phase"] == "result_committed"]
            assert len(observed) == 2 and observed[0] == observed[1] == committed[0]
            assert len([p for p in coordinator.history(original["operation_id"]) if p["phase"] == "result_committed"]) == 1
            duplicate = deepcopy(trace)
            duplicate["events"].append(deepcopy(committed[0]))
            with pytest.raises(Invalid, match="producer_phase"):
                normalize(duplicate, binding=current_binding())
        facts = {"boundary": receipt["boundary"], "side": receipt["side"], "interruption": receipt["interruption"],
                 "original_operation_suffix": True, "work_before_activation": 0, "work_after_activation": 1,
                 "grant_issued": 1, "grant_consumed": 1, "B04_owned": False}
        (output / "facts.json").write_bytes(canonical_bytes(facts))
        print("GRANT_ADVANCE_EVIDENCE", output)
        return facts


@pytest.mark.parametrize("phase", ["budget_decision_committed", "target_attempt_scheduled", "target_artifacts_invalidated",
                                  "transition_committed", "result_committed"])
@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("interruption", ["python_base_exception", "process_exit"])
def test_original_grant_consumption_prefix_dual_fresh(phase, side, interruption):
    facts = []
    for _ in range(2):
        output = Path(mkdtemp(prefix="lqcd-agent-c18-grant-advance-", dir="/private/tmp"))
        boundary = "control.advance_run.not_applicable." + phase
        args = (output, "grant_issued", boundary, side, interruption)
        if interruption == "process_exit":
            process = multiprocessing.get_context("spawn").Process(target=interrupted_budget_source, args=args)
            process.start()
            process.join(60)
            if process.is_alive():
                process.terminate()
                process.join(10)
                pytest.fail("The independent Grant process exceeded its bounded wait")
            assert process.exitcode == 97 and process.pid != os.getpid()
            assert loads((output / "fault-receipt.json").read_bytes())["pid"] == process.pid
        else:
            interrupted_budget_source(*args)
        facts.append(recover_grant_advance(output))
    assert facts[0] == facts[1]


@pytest.mark.parametrize("fault", ["worker", "epoch", "expired", "producer_activation", "missing_completion",
                                  "completion_ledger", "completion_checkpoint", "budget_intent", "public_head"])
def test_budget_completion_rejects_lost_authority_or_tampered_facts(fault):
    for _ in range(2):
        output = Path(mkdtemp(prefix="lqcd-agent-c18-completion-rejection-", dir="/private/tmp"))
        interrupted_budget_source(output, "grant_issued", "invocation.completion_intent", "after", "python_base_exception")
        receipt = loads((output / "fault-receipt.json").read_bytes())
        clock = PassiveClock(FakeClock(100, 0))
        with closing(Coordinator(output, clock=clock)) as coordinator:
            leases = InvocationLeases(coordinator)
            identifier = receipt["capability_id"]
            _, value = leases.get(identifier)
            (output / "original-journal.json").write_bytes(canonical_bytes(value))
            root = output / value["authorization"]["identity"]["case_id"] / value["authorization"]["identity"]["run_id"]
            shutil.copytree(root, output / "before-fault" / root.parent.name / root.name)
            worker, epoch = value["worker_id"], value["invocation_epoch"]
            if fault == "worker": worker = "foreign"
            elif fault == "epoch": epoch += 1
            elif fault == "expired": clock.subject.advance(100)
            elif fault == "producer_activation":
                producer = coordinator.get(value["authorization"]["producer_operation_id"])
                producer["result"]["capability_id"] = "foreign"
                coordinator.connection.execute("UPDATE control_operations SET result=? WHERE operation_id=?",
                                               (canonical_bytes(producer["result"]), producer["operation_id"]))
            elif fault == "public_head":
                index = loads((root / "artifact_index.json").read_bytes())
                index["execution_head"] = "f" * 64
                (root / "artifact_index.json").write_bytes(canonical_bytes(index))
            else:
                if fault == "missing_completion": value["completion_intent"] = None
                elif fault == "completion_ledger": value["completion_intent"]["content"] += "{}\n"
                elif fault == "completion_checkpoint": value["completion_intent"]["checkpoint"]["channel_values"]["control"]["run_status"] = "completed"
                else: value["budget_intents"][-1]["intent_digest"] = "f" * 64
                coordinator.connection.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?",
                                               (canonical_bytes(value), identifier))
            agent = StructuredOutcomes()
            with pytest.raises((ValueError, KeyError)):
                leases.publish_completion(identifier, worker, epoch)
            with pytest.raises((ValueError, KeyError)):
                leases.invoke(identifier, worker, epoch, ProductNode(root, agent))
            assert not agent.contexts
            # A corrupt frozen ledger can leave an integrity-invalid prefix.
            # Raw inspection here never claims that this prefix is replayable.
            raw_rows = [loads(line) for line in (root / "execution_history.jsonl").read_bytes().splitlines()]
            assert sum(r.get("event") == "grant_issued" for r in raw_rows) == 1
            assert not any(r.get("event") == "grant_consumed" for r in raw_rows)
            assert not any(r.get("record_type") == "run_lifecycle" and r["to_status"] in ("completed", "failed", "halted") for r in raw_rows)
            assert leases.get(identifier)[1]["state"] == "started"
            try:
                assert records(root).projection.value["run_status"] == "running"
                prefix_classification = "running_without_authorized_suffix"
            except ValueError:
                prefix_classification = "unreplayable_integrity_prefix"
            (output / "facts.json").write_bytes(canonical_bytes({"fault": fault, "rejected": True,
                "new_effects": 0, "grant_issued": 1, "grant_consumed": 0, "prefix_classification": prefix_classification,
                "fake_terminal": False, "B04_owned": False}))
            print("BUDGET_COMPLETION_REJECTION", output)


@pytest.mark.parametrize("fault", ["foreign_worker", "missing_snapshot", "corrupt_snapshot", "changed_request"])
def test_grant_advance_uncertain_prefix_does_not_activate_work(fault):
    from lqcd_agent.control.interfaces import ControlPlane
    from lqcd_agent.control.operations import AdvanceRunRequest
    from lqcd_agent.graph.analysis_graph import ProductRouteAdapter

    for _ in range(2):
        output = Path(mkdtemp(prefix="lqcd-agent-c18-grant-rejection-", dir="/private/tmp"))
        interrupted_budget_source(output, "grant_issued", "control.advance_run.not_applicable.budget_decision_committed",
                                  "after", "python_base_exception")
        receipt = loads((output / "fault-receipt.json").read_bytes())
        with closing(Coordinator(output, clock=PassiveClock(FakeClock(100, 0)))) as coordinator:
            original = coordinator.get(receipt["advance_operation_id"])
            (output / "original-operation.json").write_bytes(canonical_bytes(original))
            (output / "original-snapshot.json").write_bytes(canonical_bytes(coordinator.snapshot(original["operation_id"])))
            locator = original["request"]["run_locator"]
            root = output / locator["case_id"] / locator["run_id"]
            request = AdvanceRunRequest(locator, original["request"]["source_attempt_id"], original["idempotency_key"])
            actor = ActorContext(**{**original["request"]["actor"], "scopes": tuple(original["request"]["actor"]["scopes"])})
            worker = "foreign" if fault == "foreign_worker" else original["worker_owner_id"]
            if fault == "missing_snapshot":
                coordinator.connection.execute("DELETE FROM control_snapshots WHERE operation_id=?", (original["operation_id"],))
            elif fault == "corrupt_snapshot":
                coordinator.connection.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?", (b"{}", original["operation_id"]))
            elif fault == "changed_request":
                request = AdvanceRunRequest(locator, "attempt_999999", original["idempotency_key"])
            plane = ControlPlane(coordinator, worker_id=worker, route_adapter=ProductRouteAdapter(coordinator))
            before = files(root)
            if fault == "changed_request":
                with pytest.raises(ValueError, match="Same-key request conflict"):
                    plane.advance_run(request, actor=actor)
                disposition = "request_conflict"
            else:
                result = plane.advance_run(request, actor=actor)
                disposition = {"foreign_worker": "in_progress", "missing_snapshot": "recovery_required", "corrupt_snapshot": "failed"}[fault]
                assert result["operation_status"] == disposition
                assert plane.advance_run(request, actor=actor) == result
            assert files(root) == before
            rows = records(root).values
            issued, = [r for r in rows if r.get("event") == "grant_issued"]
            consumed, = [r for r in rows if r.get("event") == "grant_consumed"]
            assert consumed["payload"]["budget_grant_id"] == issued["payload"]["budget_grant_id"]
            assert not any(r.get("attempt_id") == issued["payload"]["target_attempt_id"] for r in rows if r["record_type"] == "attempt")
            assert not any(r.get("record_type") == "run_lifecycle" and r["to_status"] in ("completed", "failed", "halted") for r in rows)
            assert not coordinator.connection.execute("SELECT 1 FROM invocation_capabilities WHERE capability_id=?",
                ("capability_" + original["operation_id"],)).fetchone()
            (output / "facts.json").write_bytes(canonical_bytes({"fault": fault, "disposition": disposition,
                "grant_issued": 1, "grant_consumed": 1, "work_effects": 0, "fake_terminal": False, "B04_owned": False}))
            print("GRANT_ADVANCE_REJECTION", output)
