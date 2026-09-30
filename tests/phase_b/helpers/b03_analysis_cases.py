"""Real canonical Code-to-Analysis preparation crash and recovery cases."""
from dataclasses import asdict
from functools import partial
import multiprocessing
import os
from pathlib import Path
import sys

from harness.pytest_evidence import consume_process_hook, production_hook
from harness.trace import event
from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import AdvanceRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, loads
from test_b03_analysis_handoff import CanonicalAnalysisRoute, fresh_handoff
from test_external_consumption_control import success_external


PREPARATION_BOUNDARIES = ("analysis.spec_exclusive_create", "analysis.fresh_workspace",
                          "analysis.effective_tree_verification", "analysis.preparation_proof",
                          "analysis.artifact_publication", "analysis.exact_duplicate")


def _preparation_client(pipe, output, locator, actor, boundary, side, *, crash, hook_request, elapsed):
    def observer(name, observed_side, value):
        if crash and (name, observed_side) == (boundary, side):
            os._exit(97)

    if hook_request is not None:
        observer.production_hooks = {(boundary, side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    command = [sys.executable, "-I", "-S", "-c",
               "import runpy; print(runpy.run_path('sample.py')['value']())"]
    handoff = AnalysisHandoff(coordinator, coordinator.root / "base_repository", allowed_command=command)

    class ObservedRoute(CanonicalAnalysisRoute):
        calls = 0

        def admit(self, view):
            self.calls += 1
            return super().admit(view)

    route = ObservedRoute(handoff)
    try:
        plane = ControlPlane(coordinator, worker_id="analysis-host", route_adapter=route)
        result = plane.advance_run(AdvanceRunRequest(locator, "attempt_000002", "b03-analysis-preparation"),
                                  actor=ActorContext(**{**actor, "scopes": tuple(actor["scopes"])}))
        assert route.calls == 0
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def preparation_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    assert boundary in PREPARATION_BOUNDARIES
    fixture = success_external.__wrapped__()
    source = next(fixture)
    coordinator, _, actor, locator, handoff = fresh_handoff.__wrapped__(source)
    context = multiprocessing.get_context("spawn")
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    baseline = (root / "execution_history.jsonl").read_bytes()
    source_pointer = loads((root / "artifact_index.json").read_bytes())["current"]["code"]

    def run(*, crash, elapsed, hook=None):
        parent, child = context.Pipe()
        process = context.Process(target=_preparation_client,
            args=(child, str(coordinator.root), locator, asdict(actor), boundary, side),
            kwargs={"crash": crash, "hook_request": hook, "elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(30)
            assert process.exitcode == (97 if crash else 0)
            if crash:
                if hook is not None:
                    consume_process_hook(hook, process, expected_exit=97)
            else:
                assert parent.poll(2)
                return parent.recv()
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()

    try:
        run(crash=True, elapsed=0, hook=hook_request)
        operation = coordinator.lookup_key("internal_advance", "b03-analysis-preparation")
        assert operation["phase"] == "transition_heads_verified" and operation["status"] == "in_progress"
        preparation = operation["reservation"]["target_preparation_snapshot"]
        frozen_bytes = canonical_bytes(preparation)
        namespace = handoff.witness(preparation).parent
        created = (namespace / "analysis_execution_spec.json").exists()
        assert created is (boundary not in ("analysis.spec_exclusive_create", "analysis.artifact_publication") or side == "after")
        assert coordinator.connection.execute("SELECT count(*) FROM invocation_capabilities WHERE capability_id=?",
            ("capability_" + operation["operation_id"],)).fetchone()[0] == 0
        if outcome == "integrity_conflict":
            tampered = root / "attempts" / "attempt_000002" / "code_agent_result.json"
            tampered.write_bytes(b"{}")
        elif outcome == "non_materializable_domain_gap":
            with coordinator.transaction() as db:
                db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (operation["operation_id"],))
        first = run(crash=False, elapsed=40)
        stable = (root / "execution_history.jsonl").read_bytes()
        second = run(crash=False, elapsed=80)
        assert first == second and (root / "execution_history.jsonl").read_bytes() == stable
        assert stable.startswith(baseline)
        assert first["operation_id"] == operation["operation_id"]
        current = coordinator.get(operation["operation_id"])
        assert canonical_bytes(current["reservation"]["target_preparation_snapshot"]) == frozen_bytes
        records = parse_ledger(stable).values
        target = [row for row in records if row["record_type"] == "attempt" and row["attempt_id"] == "attempt_000003"]
        assert len(target) == 1 and target[0]["status"] == "scheduled"
        transitions = [row for row in records if row["record_type"] == "transition" and
                       row["source_attempt_id"] == "attempt_000002"]
        assert len(transitions) == 1 and transitions[0]["target_attempt_id"] == "attempt_000003"
        assert loads((root / "artifact_index.json").read_bytes())["current"]["code"] == source_pointer
        if outcome in ("materializable_publication_prefix", "committed_result_replay"):
            assert (first["operation_status"], first["terminal_closure"], first["run_status"]) == (
                "committed", "not_applicable", "running")
            assert handoff.verify_preparation(preparation) == handoff.receipt(preparation)
            capability = InvocationLeases(coordinator, preparation_adapter=CanonicalAnalysisRoute(handoff)).get(
                first["result"]["capability_id"])[1]
            assert capability["started_intent"] is None and capability["state"] == "unclaimed"
            assert capability["authorization"]["target_preparation"] == preparation
            assert (namespace / "analysis_execution_spec.json").read_bytes() == preparation["canonical_spec_bytes"].encode()
        else:
            assert first["terminal_closure"] == ("unavailable" if outcome == "integrity_conflict" else "not_applicable"), first
            assert first["run_status"] is None
            assert first["operation_status"] == ("failed" if outcome == "integrity_conflict" else "recovery_required")
            assert coordinator.connection.execute("SELECT count(*) FROM invocation_capabilities WHERE capability_id=?",
                ("capability_" + operation["operation_id"],)).fetchone()[0] == 0
            if outcome == "integrity_conflict":
                assert tampered.read_bytes() == b"{}"
            else:
                assert first["error"]["kind"] == "missing_materialization_snapshot"
                assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 0
        events = [event("analysis_preparation_cut", phase=boundary, stage=side, outcome=outcome,
                        source="transition_heads_verified", started=False,
                        accepted=created, owner="original_advance"),
                  event("analysis_preparation_recovered", phase=first["operation_phase"],
                        status=first["operation_status"], target=first["terminal_closure"],
                        run_status=first["run_status"], started=False, owner="original_advance",
                        guard="frozen_preparation_no_reselection"),
                  event("analysis_preparation_replayed", phase=first["operation_phase"],
                        status=first["operation_status"], target=first["terminal_closure"],
                        owner="original_advance", guard="one_transition_no_subprocess")]
        return {"schema_version": "0.1", "events": events}
    finally:
        fixture.close()
