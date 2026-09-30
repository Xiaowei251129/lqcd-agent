"""A verified Code bundle prepares a separate Analysis process."""
from dataclasses import replace
from hashlib import sha256
import multiprocessing
import os
from pathlib import Path
import sys

import pytest

from harness.pytest_evidence import observe
from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import AdvanceRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, loads
from test_advance_control import SyntheticDomainRoute
from test_external_consumption_control import success_external


class CanonicalAnalysisRoute(SyntheticDomainRoute):
    def __init__(self, handoff):
        super().__init__("analysis_engineer")
        self.handoff = handoff

    def admit(self, view):
        admitted = super().admit(view)
        attempt = f"attempt_{view['next_attempt_index']:06d}"
        transition = f"transition_{view['next_transition_index']:06d}"
        return replace(admitted, target_preparation=self.handoff.snapshot(view, attempt, transition))

    def __getattr__(self, name):
        return getattr(self.handoff, name)


@pytest.fixture
def fresh_handoff(success_external):
    coordinator, plane, actor, locator, resume, consumer = success_external
    assert plane.resume_run(resume, actor=actor)["operation_status"] == "committed"
    command = [sys.executable, "-I", "-S", "-c",
               "import runpy; print(runpy.run_path('sample.py')['value']())"]
    handoff = AnalysisHandoff(coordinator, coordinator.root / "base_repository",
                              allowed_command=command)
    plane.route_adapter = CanonicalAnalysisRoute(handoff)
    return coordinator, plane, actor, locator, handoff


def test_registered_success_prepares_fresh_workspace_and_process(fresh_handoff):
    coordinator, plane, actor, locator, handoff = fresh_handoff
    result = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "prepare-analysis"), actor=actor)
    assert result["operation_status"] == "committed", result
    leases = InvocationLeases(coordinator, preparation_adapter=plane.route_adapter)
    capability = result["result"]["capability_id"]
    value = leases.get(capability)[1]["authorization"]["target_preparation"]
    output = handoff.execute(value)
    assert output["stdout_sha256"] == sha256(b"2\n").hexdigest()
    assert handoff.provider.path(value["fresh_workspace_identity"]) != coordinator.root / "code_workspaces" / "workspace_attempt_000002"
    observe("b03-construction-analysis-handoff", {"kind": "boolean", "value": True},
            sorted(["current_success_bundle", "fresh_analysis_workspace", "fresh_subprocess"]))


@pytest.mark.parametrize("member", ["changes.patch", "code_agent_result.json"])
def test_source_member_tamper_blocks_analysis_before_transition(fresh_handoff, member):
    coordinator, plane, actor, locator, handoff = fresh_handoff
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    target = root / "attempts" / "attempt_000002" / member
    target.write_bytes(b"tampered")
    with pytest.raises((ControlIntegrityError, ValueError)):
        plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "prepare-bad"), actor=actor)
    assert coordinator.lookup_key("internal_advance", "prepare-bad") is None


def test_source_member_parent_symlink_blocks_analysis_before_transition(fresh_handoff):
    coordinator, plane, actor, locator, handoff = fresh_handoff
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    directory = root / "attempts" / "attempt_000002"
    moved = directory.with_name(directory.name + "_moved")
    directory.rename(moved)
    directory.symlink_to(moved, target_is_directory=True)
    try:
        selected = loads((root / "artifact_index.json").read_bytes())["current"]["code"]
        with pytest.raises(ControlIntegrityError, match="member escaped"):
            handoff._source(locator, selected)
        with pytest.raises(ControlIntegrityError, match="symlink|member escaped"):
            plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "prepare-symlink"), actor=actor)
        assert coordinator.lookup_key("internal_advance", "prepare-symlink") is None
    finally:
        directory.unlink()
        moved.rename(directory)


def test_prepared_workspace_tamper_blocks_execution(fresh_handoff):
    coordinator, plane, actor, locator, handoff = fresh_handoff
    result = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "prepare-analysis"), actor=actor)
    value = InvocationLeases(coordinator).get(result["result"]["capability_id"])[1]["authorization"]["target_preparation"]
    (handoff.provider.path(value["fresh_workspace_identity"]) / "sample.py").write_bytes(b"def value():\n    return 3\n")
    with pytest.raises((ControlIntegrityError, ValueError)):
        handoff.execute(value)


def _analysis_client(pipe, output, locator, *, crash=False):
    coordinator = Coordinator(Path(output), clock=FakeClock(100 if crash else 140, 0 if crash else 40,
                                                   epoch_id="analysis_process_1" if crash else "analysis_process_2"))
    command = [sys.executable, "-I", "-S", "-c",
               "import runpy; print(runpy.run_path('sample.py')['value']())"]
    adapter = CanonicalAnalysisRoute(AnalysisHandoff(coordinator, coordinator.root / "base_repository",
                                                      allowed_command=command))
    plane = ControlPlane(coordinator, worker_id="analysis-host", route_adapter=adapter)
    if crash:
        def observer(name, side, value):
            if (name, side) == ("control.advance_run.not_applicable.transition_heads_verified", "after"):
                os._exit(93)
        coordinator.observer = observer
    result = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "fresh-analysis-recovery"),
                               actor=ActorContext("operator", "human", ("control.internal",)))
    if not crash:
        value = InvocationLeases(coordinator).get(result["result"]["capability_id"])[1]["authorization"]["target_preparation"]
        pipe.send((result["operation_status"], adapter.handoff.execute(value)["stdout_sha256"]))
    coordinator.close()
    pipe.close()


def test_fresh_process_recovers_same_analysis_preparation(fresh_handoff):
    coordinator, _, _, locator, _ = fresh_handoff
    context = multiprocessing.get_context("spawn")
    for crash in (True, False):
        parent, child = context.Pipe()
        process = context.Process(target=_analysis_client, args=(child, str(coordinator.root), locator),
                                  kwargs={"crash": crash})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive() and process.exitcode == (93 if crash else 0)
            if not crash:
                assert parent.recv() == ("committed", sha256(b"2\n").hexdigest())
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
    observe("b03-construction-analysis-recovery", {"kind": "boolean", "value": True},
            sorted(["same_preparation_after_restart", "one_transition", "same_fresh_tree"]))
