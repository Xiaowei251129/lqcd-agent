"""Managed workspace authority and original public Pause binding recovery."""
from functools import partial
import os
from pathlib import Path

from harness.pytest_evidence import production_hook
from harness.trace import event
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.pause import PublishPauseRequest
from test_b03_runtime_cases import prestart_publication_recovery, prestart_domain_gap
from test_external_operation_recovery import _prepared_dispatch_source
from .b03_analysis_execution_cases import _run


BOUNDARIES = ("external.workspace_lease", "external.pause_bound")


def workspace_recovery(case_id, *, hook_request=None):
    _, side, outcome = case_id.rsplit(".", 2)
    source = "external.workspace_materialization." + side + "." + outcome
    driver = prestart_domain_gap if outcome == "non_materializable_domain_gap" else prestart_publication_recovery
    return driver(case_id, hook_request=hook_request, fixture_case=source)


def _pause_client(pipe, output, producer, side, elapsed, crash=False, hook_request=None):
    def observer(name, observed_side, value):
        if crash and (name, observed_side) == ("external.pause_binding", side):
            os._exit(97)

    if hook_request is not None:
        observer.production_hooks = {("external.pause_binding", side): (
            partial(production_hook, hook_request["case_id"], process_request=hook_request),)}
    coordinator = Coordinator(Path(output), clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    try:
        value = ExternalControl(coordinator).read(coordinator.connection, producer)
        request = PublishPauseRequest(value["run_locator"], "external_result", value["attempt_id"], value["attempt_id"],
            {"kind": "external_result", "producer_operation_id": producer},
            {"actor_type": "human", "scopes": ["resume"]}, "b03-pause-binding")
        response = ControlPlane(coordinator, worker_id="host", lease_seconds=1).publish_pause(request,
            actor=ActorContext("operator", "human", ("control.internal",)))
        pipe.send(response)
    finally:
        coordinator.close()
        pipe.close()


def pause_binding_recovery(case_id, *, hook_request=None):
    boundary, side, outcome = case_id.rsplit(".", 2)
    coordinator, root, producer = _prepared_dispatch_source(publish=False)
    source = ExternalControl(coordinator).read(coordinator.connection, producer)
    try:
        args = (str(coordinator.root), producer, side)
        _run(_pause_client, (*args, 0, True, hook_request), crash=True, hook_request=hook_request)
        cut = ExternalControl(coordinator).read(coordinator.connection, producer)
        assert cut == source and cut["operation_phase"] == "workspace_materialized" and cut["pause_id"] is None
        operation = coordinator.lookup_key("internal_pause", "b03-pause-binding")
        assert operation is not None and operation["status"] == "in_progress"
        if outcome == "integrity_conflict":
            with (root / "execution_history.jsonl").open("ab") as stream:
                stream.write(b"{")
        elif outcome == "non_materializable_domain_gap":
            with coordinator.transaction() as db:
                db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (operation["operation_id"],))
        first = _run(_pause_client, (*args, 2))
        second = _run(_pause_client, (*args, 4))
        assert first == second and first["operation_id"] == operation["operation_id"]
        positive = outcome in ("committed_result_replay", "materializable_publication_prefix")
        if positive:
            value = ExternalControl(coordinator).read(coordinator.connection, producer)
            assert value["operation_phase"] == "pause_bound" and value["pause_id"] == first["result"]["pause_id"]
            assert first["operation_status"] == "committed" and first["run_status"] == "paused"
            records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
            assert [r["event"] for r in records if r["record_type"] == "pause"] == ["pause_prepared", "pause_opened"]
            assert not any(r["record_type"] == "attempt" and r["attempt_id"] == source["attempt_id"] and
                           r["event"] == "started" for r in records)
        else:
            assert first["operation_status"] in ("failed", "recovery_required") and first["run_status"] is None
        assert not (coordinator.root / "fake_backend").exists()
        assert coordinator.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
        return {"schema_version": "0.1", "events": [
            event("public_external_pause_cut", phase="external.pause_binding", stage=side, outcome=outcome,
                  source="workspace_materialized", owner="original_pause"),
            event("public_external_pause_recovered", status=first["operation_status"], target=first["terminal_closure"],
                  run_status=first["run_status"], owner="original_pause", guard="scheduled_code_no_dispatch"),
            event("public_external_pause_replayed", accepted=True, guard="same_original_producer_and_pause")]
        }
    finally:
        coordinator.close()
