"""Repeat canonical Code targets retain the exact A03 invalidation source."""
from itertools import count
import multiprocessing
import os
import sys
from pathlib import Path
from unittest.mock import patch
import uuid

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import read
from harness.trace import compare, normalize
from helpers.canonical_code import needs_input_source
from helpers.control_traces import ControlTrace
from helpers.trace_sources import current_binding
from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
from lqcd_agent.code_agent.external_operation import ExternalProducer
from lqcd_agent.code_agent.subgraph import CodeAgentSubgraph
from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ControlPlane
from lqcd_agent.control.operations import AdvanceOperations, AdvanceRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, loads
from test_advance_control import SyntheticDomainRoute
from test_b03_analysis_handoff import CanonicalAnalysisRoute
from test_b03_reservation_boundaries import make_code_target
from test_external_consumption_control import normal_external, success_external
from test_invocation_artifacts import ArtifactTarget


def _repeat_client(pipe, output, locator, actor, key, *, cut=None, barrier=None):
    coordinator = Coordinator(Path(output), clock=FakeClock(100 if cut else 140, 0 if cut else 40))
    try:
        if cut is not None:
            def observer(name, side, value):
                if name == "control.advance_run.not_applicable." + cut and side == "after":
                    pipe.send({"operation_id": value["operation_id"], "phase": value["phase"]})
                    os._exit(93)
            coordinator.observer = observer
        if barrier is not None:
            barrier.wait(timeout=30)
        plane = ControlPlane(coordinator, worker_id="repeat-" + str(os.getpid()),
                             route_adapter=SyntheticDomainRoute("code_agent"))
        result = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", key), actor=actor)
        pipe.send({"operation_id": result["operation_id"], "status": result["operation_status"]})
    finally:
        coordinator.close()
        pipe.close()


def test_first_code_target_keeps_empty_prior_references():
    coordinator, locator, advanced = make_code_target()
    try:
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        scheduled = [row for row in parse_ledger((root / "execution_history.jsonl").read_bytes()).values
                     if row["record_type"] == "attempt" and row["event"] == "scheduled" and
                     row["attempt_id"] == "attempt_000002"]
        assert advanced["operation_status"] == "committed" and len(scheduled) == 1
        assert scheduled[0]["input_references"]["current_artifact_ids"] == {}
    finally:
        coordinator.close()


def test_second_canonical_code_target_freezes_prior_ids(normal_external):
    coordinator, plane, actor, locator, resume, _ = normal_external
    assert plane.resume_run(resume, actor=actor)["operation_status"] == "committed"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    old_index = loads((root / "artifact_index.json").read_bytes())
    old_pointer = old_index["current"]["code"]
    old_history = (root / "artifact_history.jsonl").read_bytes()
    old_members = {member["canonical_path"]: (root / member["canonical_path"]).read_bytes()
                   for member in old_pointer["members"]}
    assert old_pointer["attempt_kind"] == "code_agent" and old_pointer["status"] == "needs_input"

    plane.route_adapter = SyntheticDomainRoute("code_agent")
    result = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "repeat-code"), actor=actor)
    assert result["operation_status"] == "committed", result

    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    scheduled = next(row for row in records if row["record_type"] == "attempt" and
                     row["event"] == "scheduled" and row["attempt_id"] == "attempt_000003")
    assert scheduled["input_references"]["current_artifact_ids"] == {"code": old_pointer["artifact_id"]}
    history = (root / "artifact_history.jsonl").read_bytes()
    assert history.startswith(old_history)
    assert all((root / path).read_bytes() == value for path, value in old_members.items())
    cleared = [loads(line) for line in history[len(old_history):].splitlines()]
    assert {(row["slot"], row["prior_artifact_id"]) for row in cleared if row["event"] == "current_cleared"} == {
        ("code", old_pointer["artifact_id"])}
    assert loads((root / "artifact_index.json").read_bytes())["current"]["code"] is None
    old_workspace = loads((root / "attempts" / "attempt_000002" / "workspace_manifest.json").read_bytes())
    producer = ExternalProducer(coordinator).reserve(result["result"]["capability_id"], backend_kind="fake",
                                                      backend_version="0.1", hard_deadline=20,
                                                      worker_id="host", lease_seconds=10)
    assert producer["attempt_id"] == "attempt_000003"
    assert producer["producer_operation_id"] != resume.input_snapshot["producer_operation_id"]
    assert producer["workspace_id"] != old_workspace["workspace_id"]
    observe("b03-construction-repeat-code", {"kind": "boolean", "value": True},
            sorted(["frozen_prior_artifact_ids", "immutable_old_members", "distinct_producer_and_workspace"]))


def test_repeat_code_clears_every_populated_downstream_slot(success_external):
    coordinator, plane, actor, locator, resume, _ = success_external
    assert plane.resume_run(resume, actor=actor)["operation_status"] == "committed"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    command = [sys.executable, "-I", "-S", "-c", "import runpy; print(runpy.run_path('sample.py')['value']())"]
    plane.route_adapter = CanonicalAnalysisRoute(AnalysisHandoff(coordinator, coordinator.root / "base_repository",
                                                                  allowed_command=command))
    analysis = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "analysis-before-repeat"), actor=actor)
    assert analysis["operation_status"] == "committed"
    leases = InvocationLeases(coordinator, preparation_adapter=plane.route_adapter)
    capability = analysis["result"]["capability_id"]
    leases.acquire(capability, "analysis", expected_epoch=0, lease_seconds=10)
    state = leases.invoke(capability, "analysis", 1, ArtifactTarget("analysis", root))
    assert state["attempt_status"] == "succeeded"
    before = loads((root / "artifact_index.json").read_bytes())["current"]
    assert before["code"] is not None and before["analysis"] is not None

    plane.route_adapter = SyntheticDomainRoute("code_agent")
    repeated = plane.advance_run(AdvanceRunRequest(locator, "attempt_000003", "repeat-after-analysis"), actor=actor)
    assert repeated["operation_status"] == "committed", repeated
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    scheduled = next(row for row in records if row["record_type"] == "attempt" and
                     row["event"] == "scheduled" and row["attempt_id"] == "attempt_000004")
    assert scheduled["input_references"]["current_artifact_ids"] == {
        slot: before[slot]["artifact_id"] for slot in ("code", "analysis")}
    after = loads((root / "artifact_index.json").read_bytes())["current"]
    assert after["code"] is None and after["analysis"] is None


@pytest.mark.parametrize("cut", ["route_admission", "reservation_snapshot"])
def test_changed_index_bytes_before_reservation_are_rejected(normal_external, monkeypatch, cut):
    coordinator, plane, actor, locator, resume, _ = normal_external
    assert plane.resume_run(resume, actor=actor)["operation_status"] == "committed"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    path = root / "artifact_index.json"
    original = path.read_bytes()
    original_ledger = (root / "execution_history.jsonl").read_bytes()

    if cut == "route_admission":
        class MutatingRoute(SyntheticDomainRoute):
            def admit(self, view):
                result = super().admit(view)
                path.write_bytes(original + b" ")
                return result
        plane.route_adapter = MutatingRoute("code_agent")
    else:
        plane.route_adapter = SyntheticDomainRoute("code_agent")
        original_snapshot = AdvanceOperations._snapshot

        def mutate_during_snapshot(self, *args):
            result = original_snapshot(self, *args)
            path.write_bytes(original + b" ")
            return result

        monkeypatch.setattr(AdvanceOperations, "_snapshot", mutate_during_snapshot)
    try:
        with pytest.raises(ControlIntegrityError, match="artifact index changed"):
            plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "changed-index-" + cut), actor=actor)
        assert coordinator.lookup_key("internal_advance", "changed-index-" + cut) is None
        assert (root / "execution_history.jsonl").read_bytes() == original_ledger
    finally:
        path.write_bytes(original)
    control = coordinator.connection.execute("SELECT value FROM run_controls").fetchone()
    assert control is not None
    assert validate_run_root(root, manifest=loads(control[0])["manifest"]).value["run_status"] == "running"


@pytest.mark.parametrize("cut", ["target_attempt_scheduled", "target_artifacts_invalidated", "transition_committed"])
def test_repeat_code_crash_replays_frozen_prior_ids(normal_external, cut):
    coordinator, plane, actor, locator, resume, _ = normal_external
    assert plane.resume_run(resume, actor=actor)["operation_status"] == "committed"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    old_code = loads((root / "artifact_index.json").read_bytes())["current"]["code"]["artifact_id"]
    context = multiprocessing.get_context("spawn")
    key = "repeat-crash-" + cut
    for crash in (True, False):
        parent, child = context.Pipe()
        process = context.Process(target=_repeat_client,
                                  args=(child, str(coordinator.root), locator, actor, key),
                                  kwargs={"cut": cut if crash else None})
        try:
            process.start()
            child.close()
            assert parent.poll(30)
            observed = parent.recv()
            process.join(30)
            assert process.exitcode == (93 if crash else 0)
            if crash:
                assert observed["phase"] == cut
            else:
                assert observed["status"] == "committed"
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    scheduled = [row for row in rows if row["record_type"] == "attempt" and row["event"] == "scheduled" and
                 row["attempt_id"] == "attempt_000003"]
    assert len(scheduled) == 1
    assert scheduled[0]["input_references"]["current_artifact_ids"] == {"code": old_code}


def test_repeat_code_two_processes_share_one_scheduled_target(normal_external):
    coordinator, plane, actor, locator, resume, _ = normal_external
    assert plane.resume_run(resume, actor=actor)["operation_status"] == "committed"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    old_code = loads((root / "artifact_index.json").read_bytes())["current"]["code"]["artifact_id"]
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(3)
    clients = []
    try:
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=_repeat_client,
                                      args=(child, str(coordinator.root), locator, actor, "repeat-race"),
                                      kwargs={"barrier": barrier})
            process.start()
            child.close()
            clients.append((process, parent))
        barrier.wait(timeout=30)
        observed = []
        for process, parent in clients:
            assert parent.poll(30)
            observed.append(parent.recv())
            process.join(30)
            assert process.exitcode == 0
        assert len({row["operation_id"] for row in observed}) == 1
    finally:
        for process, parent in clients:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    scheduled = [row for row in rows if row["record_type"] == "attempt" and row["event"] == "scheduled" and
                 row["attempt_id"] == "attempt_000003"]
    assert len(scheduled) == 1
    assert scheduled[0]["input_references"]["current_artifact_ids"] == {"code": old_code}


def _repeat_code_trace():
    identities = count(1000)
    with patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=next(identities))):
        coordinator, plane, actor, locator, request, repository = needs_input_source()
        try:
            adapter = CodeAgentSubgraph(coordinator, repository)
            plane.resume_target_adapter = plane.external_adapter = adapter
            assert plane.resume_run(request, actor=actor)["operation_status"] == "committed"
            trace = ControlTrace(coordinator.root, version="0.5")
            coordinator.observer = trace.observer
            plane.route_adapter = SyntheticDomainRoute("code_agent")
            advanced = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "repeat-trace"), actor=actor)
            assert advanced["operation_status"] == "committed"
            return trace.finish(coordinator)
        finally:
            coordinator.close()


def test_repeat_code_trace_is_source_bound_and_fresh_root_stable():
    first, second = _repeat_code_trace(), _repeat_code_trace()
    assert first["proof"]["output_roots"] != second["proof"]["output_roots"]
    assert canonical_bytes(normalize(first, binding=current_binding())) == canonical_bytes(
        normalize(second, binding=current_binding()))
    expected = read(ROOT / "tests/phase_b/expected_traces/b03_repeat_code.json")
    compare(first, expected, binding=current_binding())
    compare(second, expected, binding=current_binding())
