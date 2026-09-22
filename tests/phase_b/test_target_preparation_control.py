"""B02 preparation control; synthetic receipts do not claim A05 worktree proof."""
from dataclasses import replace
from pathlib import Path

import pytest

from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome
from lqcd_agent.control.coordinator import publish_exact, read_regular
from lqcd_agent.control.operations import AdvanceRunRequest, PreparationVerification
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from test_advance_control import SyntheticDomainRoute
from test_external_consumption_control import normal_external


class DomainPreparation(SyntheticDomainRoute):
    """An external/domain adapter witnesses ordering, not scientific execution."""

    def __init__(self, root, mutation=None):
        super().__init__("analysis_engineer")
        self.root, self.mutation, self.prepared = Path(root), mutation, 0

    def admit(self, view):
        admitted = super().admit(view)
        attempt = f"attempt_{view['next_attempt_index']:06d}"
        transition = f"transition_{view['next_transition_index']:06d}"
        spec = {"evidence_class": "external/domain adapter", "target": attempt, "transition": transition}
        manifest = {"evidence_class": "external/domain adapter", "workspace": attempt + ":fresh"}
        value = {"preparation_kind": "analysis_fresh", "target_attempt_identity": {**view["run_locator"], "attempt_id": attempt, "attempt_kind": "analysis_engineer"},
            "inbound_transition_identity": transition, "analysis_execution_spec_id": attempt + ":analysis_execution_spec",
            "canonical_spec_bytes": canonical_bytes(spec).decode(), "spec_digest": digest(spec), "fresh_workspace_identity": manifest["workspace"],
            "canonical_workspace_manifest_bytes": canonical_bytes(manifest).decode(), "workspace_manifest_digest": digest(manifest),
            "source_code_bundle_id_digest": {"artifact_id": view["selected_code"]["artifact_id"], "digest": digest(view["selected_code"])},
            "base_revision_tree": {"revision": "external/domain adapter", "tree": digest("synthetic base")},
            "verified_change_digest": digest("synthetic change"), "expected_effective_tree_digest": digest("synthetic effective tree"),
            "runtime_policy_digest": digest("synthetic runtime")}
        if self.mutation is not None:
            self.mutation(value)
        return replace(admitted, target_preparation=value)

    def receipt(self, value):
        return PreparationVerification(digest(value), value["workspace_manifest_digest"], value["expected_effective_tree_digest"])

    def verify_preparation_source(self, value):
        return self.receipt(value)

    def witness(self, value):
        return self.root / "attempts" / value["target_attempt_identity"]["attempt_id"] / "control" / "domain_preparation.json"

    def materialize_preparation(self, value, port):
        port.fence()
        namespace = self.witness(value).parent
        assert read_regular(namespace / "analysis_execution_spec.json") == value["canonical_spec_bytes"].encode()
        assert read_regular(namespace / "analysis_workspace_manifest.json") == value["canonical_workspace_manifest_bytes"].encode()
        publish_exact(self.witness(value), canonical_bytes(self.receipt(value).__dict__))
        port.fence()
        self.prepared += 1
        return self.receipt(value)

    def verify_preparation(self, value):
        if read_regular(self.witness(value)) != canonical_bytes(self.receipt(value).__dict__):
            raise ControlIntegrityError("Synthetic workspace witness changed")
        return self.receipt(value)


@pytest.fixture
def prepared_source(normal_external):
    coordinator, plane, actor, locator, resume, consumer = normal_external
    assert plane.resume_run(resume, actor=actor)["operation_status"] == "committed"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    plane.route_adapter = DomainPreparation(root)
    yield coordinator, plane, actor, locator, root


def test_fresh_preparation_bound_to_committed_transition_before_capability(prepared_source):
    coordinator, plane, actor, locator, root = prepared_source
    result = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "prepare"), actor=actor)
    assert result["operation_status"] == "committed" and plane.route_adapter.prepared == 1
    capability = result["result"]["capability_id"]
    with pytest.raises(ControlIntegrityError, match="verification port"):
        InvocationLeases(coordinator).acquire(capability, "analysis", expected_epoch=0, lease_seconds=20)
    leases = InvocationLeases(coordinator, preparation_adapter=plane.route_adapter)
    leases.acquire(capability, "analysis", expected_epoch=0, lease_seconds=20)
    class Analysis:
        def invoke(self, identity):
            return TargetOutcome("pending", {"current_artifact_ids": {}})
    state = leases.invoke(capability, "analysis", 1, Analysis())
    assert state["attempt_status"] == "pending"
    assert len([r for r in coordinator.history(result["operation_id"]) if r["phase"] == "target_preparation_committed"]) == 1


@pytest.mark.parametrize("fault", ["target", "transition", "spec_digest", "code", "missing", "extra"])
def test_bad_preparation_rejected_before_transition_reservation(prepared_source, fault):
    coordinator, plane, actor, locator, root = prepared_source
    def mutate(value):
        if fault == "target":
            value["target_attempt_identity"]["attempt_id"] = "attempt_000099"
        elif fault == "transition":
            value["inbound_transition_identity"] = "transition_000099"
        elif fault == "spec_digest":
            value["spec_digest"] = digest("wrong")
        elif fault == "code":
            value["source_code_bundle_id_digest"]["digest"] = digest("wrong")
        elif fault == "missing":
            del value["canonical_spec_bytes"]
        else:
            value["not_applicable_reason"] = "forbidden"
    plane.route_adapter = DomainPreparation(root, mutate)
    original = (root / "execution_history.jsonl").read_bytes()
    with pytest.raises(ControlIntegrityError):
        plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "prepare"), actor=actor)
    assert (root / "execution_history.jsonl").read_bytes() == original
    assert coordinator.lookup_key("internal_advance", "prepare") is None


@pytest.mark.parametrize("fault", ["spec", "manifest", "workspace"])
def test_preparation_tamper_revokes_unstarted_invocation(prepared_source, fault):
    coordinator, plane, actor, locator, root = prepared_source
    result = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "prepare"), actor=actor)
    leases = InvocationLeases(coordinator, preparation_adapter=plane.route_adapter)
    capability = result["result"]["capability_id"]
    value = leases.get(capability)[1]["authorization"]["target_preparation"]
    filename = {"spec": "analysis_execution_spec.json", "manifest": "analysis_workspace_manifest.json", "workspace": "domain_preparation.json"}[fault]
    (plane.route_adapter.witness(value).parent / filename).write_bytes(b"{}")
    with pytest.raises(ControlIntegrityError):
        leases.acquire(capability, "analysis", expected_epoch=0, lease_seconds=20)
    assert leases.get(capability)[1]["started_intent"] is None


def test_analysis_recovery_preserves_original_preparation(prepared_source):
    from lqcd_agent.control.pause import PublishPauseRequest, ResumeRunRequest
    coordinator, plane, actor, locator, root = prepared_source
    preparation_adapter = plane.route_adapter
    plane.route_adapter = SyntheticDomainRoute("decision_coordinator")
    decision = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "decision"), actor=actor)
    class FailedDecision:
        def invoke(self, identity):
            return TargetOutcome("failed", {"current_artifact_ids": {}}, {"type": "SyntheticRecovery", "message": "external/domain adapter"})
    invocation = InvocationLeases(coordinator)
    invocation.acquire(decision["result"]["capability_id"], "decision", expected_epoch=0, lease_seconds=20)
    invocation.invoke(decision["result"]["capability_id"], "decision", 1, FailedDecision())
    plane.route_adapter = preparation_adapter
    advance = plane.advance_run(AdvanceRunRequest(locator, "attempt_000003", "prepare"), actor=actor)
    paused = plane.publish_pause(PublishPauseRequest(locator, "recovery_decision", "attempt_000003", "attempt_000004",
        {"kind": "recovery_decision", "actions": ["continue_existing_target", "abandon_and_halt"]},
        {"actor_type": "human", "scopes": ["resume"]}, "analysis-pause"), actor=actor)
    class Analysis:
        def invoke(self, identity):
            return TargetOutcome("pending", {"current_artifact_ids": {}})
    plane.resume_target_adapter = Analysis()
    plane.preparation_adapter = plane.route_adapter
    payload = {"action": "continue_existing_target"}
    result = plane.resume_run(ResumeRunRequest(locator, paused["result"]["pause_id"], "analysis-resume", "recovery_decision", payload, digest(payload)), actor=actor)
    assert result["operation_status"] == "committed" and result["domain_status"] == "pending", result
    leases = InvocationLeases(coordinator)
    original = leases.get(advance["result"]["capability_id"])[1]["authorization"]
    resumed = leases.get("capability_" + result["operation_id"])[1]["authorization"]
    assert resumed["target_preparation"] == original["target_preparation"]
    assert resumed["preparation_receipt"] == original["preparation_receipt"]


@pytest.mark.parametrize("crash_boundary", [("control.advance_run.not_applicable." + phase, side)
    for phase in ("transition_committed", "transition_heads_verified", "target_preparation_committed", "invocation_capability_prepared", "result_committed")
    for side in ("before", "after")])
def test_preparation_restart_reuses_frozen_snapshot_without_route_reselection(prepared_source, crash_boundary):
    import multiprocessing
    from helpers.process_client import preparation_client
    coordinator, plane, actor, locator, root = prepared_source
    context = multiprocessing.get_context("spawn")
    for boundary, elapsed in ((crash_boundary, 0), (None, 40)):
        parent, child = context.Pipe()
        process = context.Process(target=preparation_client, args=(child, str(coordinator.root), locator, boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary:
                assert process.exitcode == 95
            else:
                assert process.exitcode == 0
                result, calls = parent.recv()
                assert result["operation_status"] == "committed" and calls == 0, result
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
    assert len([r for r in coordinator.history(result["operation_id"]) if r["phase"] == "target_preparation_committed"]) == 1


@pytest.mark.parametrize("broken_authority", [False, True])
def test_preparation_conflict_closes_without_start_abandon_or_retarget(prepared_source, broken_authority):
    from lqcd_agent.control.execution import parse_ledger
    coordinator, plane, actor, locator, root = prepared_source

    class ConflictingPreparation(DomainPreparation):
        def materialize_preparation(self, value, port):
            port.fence()
            if broken_authority:
                (root / "artifact_index.json").write_bytes(b"{}")
            raise ControlIntegrityError("Synthetic effective tree mismatch")

    plane.route_adapter = ConflictingPreparation(root)
    request = AdvanceRunRequest(locator, "attempt_000002", "prepare-conflict")
    result = plane.advance_run(request, actor=actor)
    assert result["operation_status"] == "failed", result
    assert result["terminal_closure"] == ("unavailable" if broken_authority else "committed"), result
    assert result["run_status"] == (None if broken_authority else "failed"), result
    assert plane.advance_run(request, actor=actor) == result
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    target = [r for r in rows if r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000003"]
    assert [r["status"] for r in target] == ["scheduled"]
    assert len([r for r in rows if r["record_type"] == "transition" and r["source_attempt_id"] == "attempt_000002"]) == 1
    assert coordinator.connection.execute("SELECT count(*) FROM invocation_capabilities WHERE capability_id=?", ("capability_" + result["operation_id"],)).fetchone()[0] == 0
