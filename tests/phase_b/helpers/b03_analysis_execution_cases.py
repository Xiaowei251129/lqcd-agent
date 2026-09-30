"""Fresh Analysis execution uncertainty and preparation authority rejection."""
from dataclasses import asdict, replace
from functools import partial
from hashlib import sha256
import multiprocessing
import os
from pathlib import Path
import sys

from harness.pytest_evidence import consume_process_hook, production_hook
from harness.trace import event
from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import AdvanceRunRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, loads
from test_advance_control import SyntheticDomainRoute
from test_b03_analysis_handoff import CanonicalAnalysisRoute, fresh_handoff
from test_external_consumption_control import success_external
from .b03_analysis_cases import _preparation_client
from .runtime_cases import exercise_phase_case


COMMAND = [sys.executable, "-I", "-S", "-c", "import runpy; print(runpy.run_path('sample.py')['value']())"]
GUARDS = ("analysis.conflicting_bytes", "analysis.stale_epoch", "analysis.capability_before_preparation")
NOT_APPLICABLE = ("analysis.no_bundle_not_applicable", "analysis.non_analysis_not_applicable")


class NotApplicableRoute(SyntheticDomainRoute):
    def __init__(self, target, reason):
        super().__init__(target)
        self.reason = reason

    def admit(self, view):
        return replace(super().admit(view), target_preparation={
            "preparation_kind": "not_applicable", "not_applicable_reason": self.reason})


def _analysis_client(pipe, output, capability, locator, actor, action, boundary, side, hook_request=None):
    def observer(name, observed_side, value):
        if action == "execute" and (name, observed_side) == (boundary, side):
            if side == "after":
                assert value == {"returncode": 0, "stdout_sha256": sha256(b"2\n").hexdigest()}
            os._exit(97)

    if hook_request is not None:
        observer.production_hooks = {(boundary, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0) if action in ("execute", "lease") else FakeClock(140, 40), observer=observer)
    handoff = AnalysisHandoff(coordinator, coordinator.root / "base_repository", allowed_command=COMMAND)
    route = CanonicalAnalysisRoute(handoff)
    leases = InvocationLeases(coordinator, preparation_adapter=route)
    try:
        if action == "lease":
            value = leases.acquire(capability, "first", expected_epoch=0, lease_seconds=10)
            pipe.send({"state": value["state"], "epoch": value["invocation_epoch"]})
        elif action == "execute":
            value = leases.acquire(capability, "analysis", expected_epoch=0, lease_seconds=10)
            preparation = value["authorization"]["target_preparation"]

            class Analysis:
                def invoke(self, identity):
                    assert identity == preparation["target_attempt_identity"]
                    assert handoff.execute(preparation)["stdout_sha256"] == sha256(b"2\n").hexdigest()
                    return TargetOutcome("pending", {"current_artifact_ids": {}})

            leases.invoke(capability, "analysis", 1, Analysis())
            raise AssertionError("The requested Analysis subprocess cut did not fire")
        else:
            try:
                leases.acquire(capability, "recovery", expected_epoch=0, lease_seconds=10)
            except (ControlIntegrityError, OSError) as error:
                rejected = str(error)
            else:
                raise AssertionError("Invalid or uncertain Analysis was acquired")
            coordinator.observer = None
            result = {"rejected": rejected}
            if action == "query":
                plane = ControlPlane(coordinator, worker_id="analysis", route_adapter=route)
                result["response"] = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "analysis-execution"),
                    actor=ActorContext(**{**actor, "scopes": tuple(actor["scopes"])}))
                assert route.calls == 0
            pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def _run(client, args, *, kwargs=None, crash=False, hook_request=None):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=client, args=(child, *args), kwargs=kwargs or {})
    try:
        process.start()
        child.close()
        result = None
        if not crash:
            assert parent.poll(30)
            result = parent.recv()
        process.join(30)
        assert process.exitcode == (97 if crash else 0)
        if hook_request is not None:
            consume_process_hook(hook_request, process, expected_exit=97 if crash else 0)
        return result
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()


def analysis_guard(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in GUARDS and outcome == "integrity_conflict"
    fixture = success_external.__wrapped__()
    coordinator, plane, actor, locator, handoff = fresh_handoff.__wrapped__(next(fixture))
    try:
        if boundary == "analysis.capability_before_preparation":
            _run(_preparation_client, (str(coordinator.root), locator, asdict(actor),
                 "control.advance_run.not_applicable.target_preparation_committed", side),
                 kwargs={"crash": True, "hook_request": None, "elapsed": 0}, crash=True)
            operation = coordinator.lookup_key("internal_advance", "b03-analysis-preparation")
            capability = "capability_" + operation["operation_id"]
            assert operation["phase"] == "transition_heads_verified"
            assert coordinator.connection.execute("SELECT count(*) FROM invocation_capabilities WHERE capability_id=?", (capability,)).fetchone()[0] == 0
            hook = "invocation.capability_lookup"
            saved = None
        else:
            prepared = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "analysis-guard"), actor=actor)
            assert prepared["operation_status"] == "committed"
            capability = prepared["result"]["capability_id"]
            if boundary == "analysis.stale_epoch":
                assert _run(_analysis_client, (str(coordinator.root), capability, locator, asdict(actor), "lease", None, None)) == {
                    "state": "leased_not_started", "epoch": 1}
            saved = InvocationLeases(coordinator).get(capability)[1]
            if boundary == "analysis.conflicting_bytes":
                preparation = saved["authorization"]["target_preparation"]
                member = handoff.witness(preparation).parent / "analysis_execution_spec.json"
                member.write_bytes(b"{}")
            hook = "invocation.activation_check"
        ledger = coordinator.root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl"
        original = read_regular(ledger)
        args = (str(coordinator.root), capability, locator, asdict(actor), "guard", hook, side)
        first = _run(_analysis_client, (*args, hook_request), hook_request=hook_request)
        if hook_request is not None:
            receipt = Path(hook_request["receipt_path"])
            assert receipt.exists()
        second = _run(_analysis_client, args)
        assert first == second and read_regular(ledger) == original
        if saved is not None:
            assert InvocationLeases(coordinator).get(capability)[1] == saved
            assert saved["started_intent"] is None
        else:
            assert first["rejected"] == "Unknown invocation capability"
        if boundary == "analysis.stale_epoch":
            assert first["rejected"] == "Stale invocation epoch"
        if boundary == "analysis.conflicting_bytes":
            assert member.read_bytes() == b"{}" and first["rejected"] == "Analysis preparation bytes changed"
        return {"schema_version": "0.1", "events": [
            event("analysis_authority_guard", phase=hook, stage=side, outcome=outcome, target=boundary, started=False),
            event("analysis_authority_rejected", status="rejected", target=boundary, guard="no_start_no_publication"),
            event("analysis_authority_repeated", accepted=True, guard="same_bytes_same_epoch")]
        }
    finally:
        fixture.close()


def analysis_execution_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary == "analysis.fresh_subprocess"
    fixture = success_external.__wrapped__()
    coordinator, plane, actor, locator, handoff = fresh_handoff.__wrapped__(next(fixture))
    try:
        prepared = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "analysis-execution"), actor=actor)
        assert prepared["operation_status"] == "committed"
        capability = prepared["result"]["capability_id"]
        args = (str(coordinator.root), capability, locator, asdict(actor), "execute", boundary, side)
        _run(_analysis_client, (*args, hook_request), crash=True, hook_request=hook_request)
        saved = InvocationLeases(coordinator).get(capability)[1]
        assert saved["started_intent"] is not None and saved.get("completion_intent") is None
        preparation = saved["authorization"]["target_preparation"]
        if outcome == "integrity_conflict":
            damaged = handoff.witness(preparation).parent / "analysis_execution_spec.json"
            damaged.write_bytes(b"{}")
        elif outcome == "non_materializable_domain_gap":
            handoff.witness(preparation).unlink()
        ledger = coordinator.root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl"
        stable = read_regular(ledger)
        args = (str(coordinator.root), capability, locator, asdict(actor), "query", None, None)
        first = _run(_analysis_client, args)
        second = _run(_analysis_client, args)
        assert first == second and first["response"] == prepared
        assert read_regular(ledger) == stable and InvocationLeases(coordinator).get(capability)[1] == saved
        records = parse_ledger(stable).values
        target = [r for r in records if r["record_type"] == "attempt" and r["attempt_id"] == "attempt_000003"]
        assert [r["event"] for r in target] == ["scheduled", "started"]
        assert not any(r["record_type"] == "transition" and r["source_attempt_id"] == "attempt_000003" for r in records)
        assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 0
        if outcome == "integrity_conflict":
            assert damaged.read_bytes() == b"{}"
        elif outcome == "non_materializable_domain_gap":
            assert not handoff.witness(preparation).exists()
        return {"schema_version": "0.1", "events": [
            event("analysis_subprocess_cut", phase=boundary, stage=side, outcome=outcome,
                  started=True, accepted=side == "after", owner="original_advance"),
            event("analysis_uncertain_reacquire_rejected", status="rejected", guard="no_subprocess_retry", owner="original_advance"),
            event("analysis_advance_result_replayed", status="committed", run_status="running",
                  guard="no_abandon_no_retarget_no_second_transition", owner="original_advance")]
        }
    finally:
        fixture.close()


def _not_applicable_evidence(coordinator, config, before_rows, recovered):
    operation = coordinator.get(recovered["operation_id"])
    value = operation["reservation"]["target_preparation_snapshot"]
    assert value == {"preparation_kind": "not_applicable", "not_applicable_reason": config["preparation_reason"]}
    root = coordinator.root / config["request"]["run_locator"]["case_id"] / config["request"]["run_locator"]["run_id"]
    index = loads(read_regular(root / "artifact_index.json"))
    assert (index["current"]["code"] is None) is (config["route"] == "analysis_engineer")
    if index["current"]["code"] is not None:
        assert index["current"]["code"]["status"] == "success"
    assert not (coordinator.root / "analysis_workspaces").exists()
    assert not list((root / "attempts").glob("*/control/analysis_execution_spec.json"))


def not_applicable_recovery(case_id):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in NOT_APPLICABLE
    phase = "control.advance_run.not_applicable.target_preparation_committed"
    return exercise_phase_case(case_id, fixture_case=f"{phase}.{side}.{outcome}", fault_point=phase,
        canonical_advance="success" if boundary == "analysis.non_analysis_not_applicable" else None,
        route_target="scientific_reviewer" if boundary == "analysis.non_analysis_not_applicable" else "analysis_engineer",
        preparation_reason="non_analysis_target" if boundary == "analysis.non_analysis_not_applicable" else "no_code_bundle",
        evidence_check=_not_applicable_evidence)
