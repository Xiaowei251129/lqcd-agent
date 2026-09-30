"""B02 consumption with an explicit external/domain adapter, not A05 evidence.

The domain fixture publishes ordinary A03 synthetic members. It does not model
Code Bundle schemas, a Backend, trusted verification, or Analysis execution.
"""
from hashlib import sha256
from pathlib import Path
import tempfile

import pytest

from harness import pytest_evidence
from harness.pytest_evidence import observe
from lqcd_agent.control.capabilities import ArtifactOutput, CodeConsumptionProof, InvocationLeases, TargetOutcome
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext
from lqcd_agent.control.operations import AdvanceRunRequest, ExternalControl
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from test_advance_control import SyntheticDomainRoute
from test_bootstrap_control import start
from test_external_control import SyntheticExternalStop, external_pause_request, external_source
from test_invocation_artifacts import ArtifactTarget
from helpers.canonical_code import needs_input_source, success_source
from lqcd_agent.code_agent.subgraph import CodeAgentSubgraph


class ExternalDomainConsumer:
    """A typed control-half adapter, never a substitute for the B03 verifier."""

    def __init__(self, root):
        self.root, self.calls = root, 0

    def consume_external(self, identity, binding, port):
        self.calls += 1
        records = parse_ledger((self.root / "execution_history.jsonl").read_bytes()).values
        assert records[-1]["record_type"] == "attempt" and records[-1]["event"] == "started"
        settled = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"]
        assert len(settled) == 1 and settled[0]["payload"]["evidence_digest"] == binding["value"]["terminal_evidence_digest"]
        paths = (port.write_member("control_domain_summary.md", b"external/domain adapter evidence only\n"),
                 port.write_member("control_domain_status.json", b'{"evidence_class":"external/domain adapter"}'))
        index = loads((self.root / "artifact_index.json").read_bytes())
        refs = {slot: pointer["artifact_id"] for slot, pointer in index["current"].items() if pointer is not None}
        refs["code"] = identity["attempt_id"] + ":code"
        return TargetOutcome("succeeded", {"current_artifact_ids": refs}, artifact=ArtifactOutput("code", paths,
            {"code_change_summary_path": str(paths[0]), "tests_status_path": str(paths[1])}, "external/domain adapter"))

    def verify_consumption(self, identity, binding, outcome):
        members = [{"path": str(path.relative_to(self.root)), "sha256": sha256(path.read_bytes()).hexdigest()} for path in outcome.artifact.member_paths]
        return CodeConsumptionProof(binding["value"]["producer_operation_id"], binding["value"]["terminal_evidence_digest"],
                                    identity["attempt_id"], digest(members), outcome.status)


class ExternalDomainFailure(ExternalDomainConsumer):
    def __init__(self, root, *, safe=True, appendable=True):
        super().__init__(root)
        self.safe, self.appendable = safe, appendable

    def consume_external(self, identity, binding, port):
        from lqcd_agent.control.strict_json import ControlIntegrityError
        self.calls += 1
        if not self.appendable:
            (self.root / "artifact_index.json").write_bytes(b"{}")
        raise ControlIntegrityError("Synthetic verifier integrity rejection")

    def stop_consumption(self, coordinator, intent):
        from lqcd_agent.control.pause import ConsumerStopObservation
        assert coordinator.get(intent["consumer_capability_id"].removeprefix("capability_"))["phase"] == "consumption_failure_ownership_reserved"
        return ConsumerStopObservation({"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
            "verify_empty": self.safe, "bounded_drain": True, "post_stop_stability": True}, {})


class CanonicalDomainConsumer(CodeAgentSubgraph):
    """Count canonical consumption while preserving B02 ordering assertions."""

    def __init__(self, coordinator, repository):
        super().__init__(coordinator, repository)
        self.calls = 0

    def consume_external(self, identity, binding, port):
        self.calls += 1
        records = parse_ledger((self.coordinator.root / identity["case_id"] / identity["run_id"] /
                                "execution_history.jsonl").read_bytes()).values
        assert records[-1]["record_type"] == "attempt" and records[-1]["event"] == "started"
        settled = [row for row in records if row["record_type"] == "budget" and row["event"] == "resource_settled"]
        assert len(settled) == 1 and settled[0]["payload"]["evidence_digest"] == binding["value"]["terminal_evidence_digest"]
        return super().consume_external(identity, binding, port)


@pytest.fixture
def normal_external():
    coordinator, plane, actor, locator, request, repository = needs_input_source()
    try:
        adapter = CanonicalDomainConsumer(coordinator, repository)
        plane.resume_target_adapter = plane.external_adapter = adapter
        yield coordinator, plane, actor, locator, request, adapter
    finally:
        coordinator.close()


@pytest.fixture
def success_external():
    coordinator, plane, actor, locator, request, repository = success_source()
    try:
        adapter = CanonicalDomainConsumer(coordinator, repository)
        plane.resume_target_adapter = plane.external_adapter = adapter
        yield coordinator, plane, actor, locator, request, adapter
    finally:
        coordinator.close()


def test_normal_external_consumption_releases_before_final_checkpoint(normal_external):
    coordinator, plane, actor, locator, request, adapter = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    observed = []

    def observer(name, side, value):
        if name == "control.resume_run.continue_execution.external_consumption_released" and side == "after":
            released = ExternalControl(coordinator).read(coordinator.connection, request.input_snapshot["producer_operation_id"])
            assert released["active_binding_status"] == "released"
            assert not (root / "checkpoints" / (released["consumption_release"]["consumption_operation_id"] + "_external_consumed.json")).exists()
            observed.append(released["consumption_release"])

    coordinator.observer = observer
    result = plane.resume_run(request, actor=actor)
    assert result["operation_status"] == "committed" and result["domain_status"] == "succeeded", result
    assert result["run_status"] == "running" and adapter.calls == 1 and len(observed) == 1
    from lqcd_agent.code_agent.artifacts import validate_code_result
    from lqcd_agent.code_agent.schemas import validate_task
    pointer = loads((root / "artifact_index.json").read_bytes())["current"]["code"]
    task = validate_task((root / "attempts" / "attempt_000002" / "code_agent_task.json").read_bytes()).value
    outcome = validate_code_result((root / "attempts" / "attempt_000002" / "code_agent_result.json").read_bytes(), task).value
    assert pointer["status"] == outcome["status"] == "needs_input" and outcome["usable"] is False
    assert set(pointer["state_paths"]) == {"code_change_summary_path", "tests_status_path",
        "code_agent_task_path", "code_agent_result_path", "code_change_manifest_path",
        "code_verification_results_path"}
    assert pointer["state_paths"]["code_change_summary_path"] is None
    assert pointer["state_paths"]["tests_status_path"] is None
    assert (root / "checkpoints" / (result["operation_id"] + "_external_consumed.json")).is_file()
    assert not (root / "checkpoints" / ("capability_" + result["operation_id"] + "_finished.json")).exists()
    assert plane.resume_run(request, actor=actor) == result and adapter.calls == 1
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert [r["status"] for r in records if r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002"] == ["scheduled", "running", "succeeded"]
    assert ExternalControl(coordinator).attached(coordinator.connection, locator) == []
    plane.route_adapter = SyntheticDomainRoute("scientific_reviewer")
    advanced = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "after-consumption"), actor=actor)
    assert advanced["operation_status"] == "committed"
    assert ExternalControl(coordinator).attached(coordinator.connection, locator) == []
    if pytest_evidence.ACTIVE is None or pytest_evidence.ACTIVE.nodeid.startswith(
            "tests/phase_b/test_external_consumption_control.py::test_normal_external_consumption_releases_before_final_checkpoint"):
        observe("b03-construction-code-consumption", {"kind": "boolean", "value": True},
                sorted(["same_resume_owner", "one_attempt_and_bundle", "release_before_final_checkpoint"]))


CONSUMPTION_BOUNDARIES = [("control.resume_run.continue_execution." + phase, side)
    for phase in ("resume_disposition_committed", "pause_ownership_reserved", "pause_claimed_recorded", "prestart_records_committed",
                  "pause_consumed_recorded", "running_lifecycle_recorded", "resume_checkpoint_committed", "invocation_authorized",
                  "external_consumption_released", "stable_boundary_committed", "result_committed") for side in ("before", "after")]
CONSUMPTION_BOUNDARIES += [("invocation.completion_intent", "after"), ("invocation.attempt_finished.file_sync", "after")]


@pytest.mark.parametrize("crash_boundary", CONSUMPTION_BOUNDARIES)
def test_normal_consumption_fresh_process_continues_without_redispatch(normal_external, crash_boundary):
    import multiprocessing
    from dataclasses import asdict
    from helpers.process_client import external_resume_client
    coordinator, plane, actor, locator, request, adapter = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    context = multiprocessing.get_context("spawn")

    def run(boundary, elapsed):
        parent, child = context.Pipe()
        process = context.Process(target=external_resume_client, args=(child, str(coordinator.root), asdict(request), boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary:
                assert process.exitcode == 93
                return None
            assert process.exitcode == 0 and parent.poll(2)
            return parent.recv()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()

    run(crash_boundary, 0)
    prefix = (root / "execution_history.jsonl").read_bytes()
    result, calls = run(None, 40)
    assert result["operation_status"] == "committed", result
    assert (root / "execution_history.jsonl").read_bytes().startswith(prefix)
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert sum(r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002" and r["event"] == "started" for r in records) == 1
    assert sum(r["record_type"] == "budget" and r["event"] == "resource_settled" for r in records) == 1
    assert sum(r["record_type"] == "pause" and r["event"] == "pause_consumed" for r in records) == 1
    assert ExternalControl(coordinator).attached(coordinator.connection, locator) == []
    if crash_boundary[0] in ("invocation.completion_intent", "invocation.attempt_finished.file_sync") or crash_boundary[0].endswith(
            ("external_consumption_released", "stable_boundary_committed", "result_committed")):
        assert calls == 0
    if pytest_evidence.ACTIVE is None or pytest_evidence.ACTIVE.nodeid.startswith(
            "tests/phase_b/test_external_consumption_control.py::test_normal_consumption_fresh_process_continues_without_redispatch["):
        observe("b03-construction-delivery-restart", {"kind": "boolean", "value": True},
                sorted(["one_attempt_start", "one_pause_consumption", "one_settlement", "same_operation_after_restart"]))


@pytest.mark.parametrize("safe,appendable", [(True, True), (True, False), (False, True), (False, False)])
def test_post_claim_consumer_failure_preserves_normal_final_and_original_owner(normal_external, safe, appendable):
    from lqcd_agent.control.pause import ConsumerStopObservation
    from lqcd_agent.control.strict_json import ControlIntegrityError
    coordinator, plane, actor, locator, request, adapter = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    original = ExternalControl(coordinator).read(coordinator.connection, request.input_snapshot["producer_operation_id"])
    final_bytes = (root / original["terminal_evidence_reference"]).read_bytes()

    class FailingConsumer(ExternalDomainConsumer):
        def consume_external(self, identity, binding, port):
            self.calls += 1
            if not appendable:
                (root / "artifact_index.json").write_bytes(b"{}")
            raise ControlIntegrityError("Synthetic verifier integrity rejection")

        def stop_consumption(self, coordinator, intent):
            assert coordinator.get(intent["consumer_capability_id"].removeprefix("capability_"))["phase"] == "consumption_failure_ownership_reserved"
            return ConsumerStopObservation({"termination_or_not_dispatched": "confirmed", "write_lease_revocation": True,
                "verify_empty": safe, "bounded_drain": True, "post_stop_stability": True}, {})

    failed = FailingConsumer(root)
    plane.external_adapter = plane.resume_target_adapter = failed
    result = plane.resume_run(request, actor=actor)
    assert failed.calls == 1 and result["terminal_closure"] == ("committed" if safe and appendable else "unavailable"), result
    assert result["run_status"] == ("failed" if safe and appendable else None), result
    closure = loads(coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchone()[0])
    assert closure["terminal_closure_owner_operation_id"] == result["operation_id"]
    assert (root / original["terminal_evidence_reference"]).read_bytes() == final_bytes
    external = ExternalControl(coordinator).read(coordinator.connection, request.input_snapshot["producer_operation_id"])
    assert external["resolution_owner"] == "normal" and external["terminal_evidence_digest"] == original["terminal_evidence_digest"]
    assert external["consumption_release"] is None
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert sum(r["record_type"] == "budget" and r["event"] == "resource_settled" for r in rows) == 1
    assert [r["status"] for r in rows if r["record_type"] == "pause"] == ["prepared", "opened", "claimed", "consumed"]
    assert not any(r["record_type"] == "run_lifecycle" and r["to_status"] == "failed" for r in rows) or safe and appendable
    assert plane.resume_run(request, actor=actor) == result and failed.calls == 1
    assert not any(op[0] in ("close_run", "resolve_external_interrupt") for op in coordinator.connection.execute("SELECT operation_type FROM control_operations"))


@pytest.mark.parametrize("source_phase,next_phase", [
    ("pause_ownership_reserved", "pause_claimed_recorded"),
    ("pause_claimed_recorded", "prestart_records_committed"),
    ("prestart_records_committed", "pause_consumed_recorded"),
    ("pause_consumed_recorded", "running_lifecycle_recorded"),
    ("running_lifecycle_recorded", "resume_checkpoint_committed"),
    ("resume_checkpoint_committed", "invocation_authorized"),
    ("invocation_authorized", "external_consumption_released")])
def test_failure_cas_at_each_claimed_phase_closes_same_operation(normal_external, source_phase, next_phase):
    from lqcd_agent.control.pause import ConsumerStopObservation
    from lqcd_agent.control.strict_json import ControlIntegrityError
    coordinator, plane, actor, locator, request, adapter = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    fired = []

    def observer(name, side, value):
        if name == "control.resume_run.continue_execution." + next_phase and side == "before" and not fired:
            fired.append(name)
            raise ControlIntegrityError("Synthetic failure before successor commit")

    adapter.stop_consumption = lambda coordinator, intent: ConsumerStopObservation({"termination_or_not_dispatched": "confirmed",
        "write_lease_revocation": True, "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}, {})
    coordinator.observer = observer
    result = plane.resume_run(request, actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "failed", result
    history = coordinator.history(result["operation_id"])
    failure = next(row for row in history if row["phase"] == "consumption_failure_ownership_reserved")
    assert failure["evidence"]["frozen_failure_snapshot_and_disposition_contract"]["source_phase"] == source_phase
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert sum(r["record_type"] == "budget" and r["event"] == "resource_settled" for r in rows) == 1
    assert sum(r["record_type"] == "pause" and r["event"] == "pause_consumed" for r in rows) <= 1
    assert rows[-1]["record_type"] == "run_lifecycle" and rows[-1]["to_status"] == "failed"
    assert ExternalControl(coordinator).attached(coordinator.connection, locator) == []
    assert plane.resume_run(request, actor=actor) == result


FAILURE_BOUNDARIES = [(True, phase, side) for phase in (
    "consumption_failure_ownership_reserved", "consumption_failure_stop_verified", "consumption_failure_classified",
    "consumption_failure_disposition_committed", "terminal_eligibility_verified", "terminal_lifecycle_recorded",
    "terminal_checkpoint_committed", "result_committed") for side in ("before", "after")]
FAILURE_BOUNDARIES += [(False, phase, side) for phase in (
    "consumption_failure_ownership_reserved", "consumption_failure_stop_verified", "consumption_failure_classified",
    "consumption_failure_unavailable_recorded") for side in ("before", "after")]


@pytest.mark.parametrize("safe,phase,side", FAILURE_BOUNDARIES)
def test_consumption_failure_tail_fresh_process_never_reinvokes_verifier(normal_external, safe, phase, side):
    import multiprocessing
    from dataclasses import asdict
    from helpers.process_client import external_resume_client
    coordinator, plane, actor, locator, request, adapter = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    context = multiprocessing.get_context("spawn")

    def run(boundary, elapsed):
        parent, child = context.Pipe()
        process = context.Process(target=external_resume_client, args=(child, str(coordinator.root), asdict(request), boundary),
                                  kwargs={"elapsed": elapsed, "failure": True, "safe": safe})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary:
                assert process.exitcode == 93
                return None
            assert process.exitcode == 0 and parent.poll(2)
            return parent.recv()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()

    run(("control.resume_run.continue_execution." + phase, side), 0)
    prefix = (root / "execution_history.jsonl").read_bytes()
    result, calls = run(None, 40)
    assert calls == 0 and result["terminal_closure"] == ("committed" if safe else "unavailable"), result
    assert (root / "execution_history.jsonl").read_bytes().startswith(prefix)
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert sum(r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002" and r["event"] == "started" for r in rows) == 1
    assert sum(r["record_type"] == "budget" and r["event"] == "resource_settled" for r in rows) == 1
    assert sum(r["record_type"] == "pause" and r["event"] == "pause_consumed" for r in rows) == 1


def test_normal_final_system_stop_detaches_without_consuming(normal_external):
    from lqcd_agent.control.operations import CloseRunRequest
    coordinator, plane, actor, locator, request, adapter = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    original = ExternalControl(coordinator).read(coordinator.connection, request.input_snapshot["producer_operation_id"])
    final = (root / original["terminal_evidence_reference"]).read_bytes()
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    stop = CloseRunRequest(locator, digest(records[-1]), "terminal_operator_stop")
    result = plane.close_run(stop, actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "halted", result
    assert adapter.calls == 0
    assert plane.close_run(stop, actor=actor) == result
    changed = ExternalControl(coordinator).read(coordinator.connection, request.input_snapshot["producer_operation_id"])
    assert {k: v for k, v in changed.items() if k not in ("active_binding_status", "close_disposition")} == {
        k: v for k, v in original.items() if k not in ("active_binding_status", "close_disposition")}
    assert (root / original["terminal_evidence_reference"]).read_bytes() == final
    assert ExternalControl(coordinator).attached(coordinator.connection, locator) == []
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert [r["status"] for r in records if r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002"] == ["scheduled", "abandoned"]
    assert [r["status"] for r in records if r["record_type"] == "pause"] == ["prepared", "opened", "interrupted"]
    assert len([r for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"]) == 1
    from lqcd_agent.control.strict_json import ControlIntegrityError
    with pytest.raises(ControlIntegrityError):
        plane.resume_run(request, actor=actor)


@pytest.mark.parametrize("crash_boundary", [("control.close_run.not_applicable." + phase, side)
    for phase in ("terminal_ownership_reserved", "resource_disposition_committed", "close_source_disposition_committed",
                  "terminal_eligibility_verified", "terminal_lifecycle_recorded", "terminal_checkpoint_committed", "result_committed")
    for side in ("before", "after")])
def test_normal_final_close_fresh_process_exact_suffix(normal_external, crash_boundary):
    import multiprocessing
    from dataclasses import asdict
    from helpers.process_client import close_client
    from lqcd_agent.control.operations import CloseRunRequest
    coordinator, plane, actor, locator, request, adapter = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    stop = CloseRunRequest(locator, digest(records[-1]), "terminal_operator_stop")
    context = multiprocessing.get_context("spawn")
    for boundary, elapsed in ((crash_boundary, 0), (None, 40)):
        parent, child = context.Pipe()
        process = context.Process(target=close_client, args=(child, str(coordinator.root), asdict(stop), boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary:
                assert process.exitcode == 94
            else:
                assert process.exitcode == 0
                result = parent.recv()
                assert result["operation_status"] == "committed" and result["run_status"] == "halted", result
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert sum(r["record_type"] == "pause" and r["status"] == "interrupted" for r in records) == 1
    assert sum(r["record_type"] == "budget" and r["event"] == "resource_settled" for r in records) == 1
    assert not any(r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000002" and r["event"] == "started" for r in records)
    assert ExternalControl(coordinator).attached(coordinator.connection, locator) == []


@pytest.mark.parametrize("close_first", [False, True])
def test_normal_final_close_and_resume_have_one_owner_across_processes(normal_external, close_first):
    import multiprocessing
    from dataclasses import asdict
    from helpers.process_client import close_client
    from lqcd_agent.control.operations import CloseRunRequest
    from lqcd_agent.control.strict_json import ControlIntegrityError
    coordinator, plane, actor, locator, request, adapter = normal_external
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    stop = CloseRunRequest(locator, digest(records[-1]), "terminal_operator_stop")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    phase = "terminal_ownership_reserved" if close_first else "operation_reserved"
    process = context.Process(target=close_client, args=(child, str(coordinator.root), asdict(stop)), kwargs={"hold_phase": phase})
    try:
        process.start()
        child.close()
        assert parent.poll(15)
        held, operation_id = parent.recv()
        assert held == "held"
        if close_first:
            with pytest.raises(ControlIntegrityError):
                plane.resume_run(request, actor=actor)
        else:
            resumed = plane.resume_run(request, actor=actor)
            assert resumed["operation_status"] == "committed"
        parent.send("continue")
        assert parent.poll(15)
        result = parent.recv()
        process.join(10)
        assert process.exitcode == 0
        assert result["operation_status"] == ("committed" if close_first else "failed"), result
        assert result["operation_id"] == operation_id
        closures = coordinator.connection.execute("SELECT value FROM run_terminal_closure").fetchall()
        assert len(closures) == int(close_first)
        if close_first:
            assert loads(closures[0][0])["terminal_closure"] == "committed"
        assert len([r for r in parse_ledger((root / "execution_history.jsonl").read_bytes()).values
                    if r["record_type"] == "budget" and r["event"] == "resource_settled"]) == 1
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()
