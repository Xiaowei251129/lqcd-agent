"""Supplemental B02 boundaries mapped to actual production publications and guards."""
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from pathlib import Path
import tempfile

from harness.trace import event
from harness.pytest_evidence import process_hook_request
from helpers.runtime_cases import SPECS, exercise_phase_case, phase_fixture, run_client, run_files
from lqcd_agent.control.coordinator import TABLES
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads


START = "control.start_run.not_applicable."
CHILD = "control.fork_run.not_applicable."
RESUME = "control.resume_run.continue_execution."
ADVANCE = "control.advance_run.not_applicable."

# Several logical bootstrap records share one frozen append and one fsync.
# Their mappings name that real publication, not invented per-record commits.
PUBLICATIONS = {
    "bootstrap.database_commit": (START + "policy_published", "coordinator.database_commit", 1),
    "bootstrap.database_sync": (START + "policy_published", "coordinator.database_commit", 1),
    "bootstrap.root_exclusive_create": (START + "run_root_created", "bootstrap.root_exclusive_create", 1),
    "bootstrap.parent_directory_sync": (START + "run_root_created", "bootstrap.parent_directory_sync", 1),
    "bootstrap.run_record": (START + "run_ledger_started", "bootstrap.execution_history.jsonl", 1),
    "bootstrap.initializing_lifecycle": (START + "run_ledger_started", "bootstrap.execution_history.jsonl", 1),
    **{name: (START + "bootstrap_records_complete", "bootstrap.execution_history.jsonl", 2) for name in (
        "bootstrap.policy_initialization", "bootstrap.bootstrap_admission", "bootstrap.initial_cycle",
        "bootstrap.planner_attempt", "bootstrap.start_transition")},
    "bootstrap.initial_invalidation": (START + "checkpoint_committed", "bootstrap.artifact_index.json", 1),
    "bootstrap.capability_activation": (START + "result_committed", START + "result_committed", 1),
    "bootstrap.worker_lease_takeover": (START + "policy_published", "coordinator.lease_takeover", 1),
    "child.source_snapshot": (CHILD + "source_snapshot_committed", CHILD + "source_snapshot_committed", 1),
    "child.source_revision_cas": (CHILD + "operation_reserved", "child.source_revision_cas", 1),
    "child.lineage_publication": (CHILD + "child_lineage_recorded", "child.execution_history.jsonl", 2),
    "child.child_policy": (CHILD + "child_policy_published", "child.budget_policy.json", 1),
    "child.child_root": (CHILD + "child_run_root_created", "child.root_exclusive_create", 1),
    "child.child_ledger": (CHILD + "child_run_ledger_started", "child.execution_history.jsonl", 1),
    "child.child_checkpoint": (CHILD + "child_checkpoint_committed", CHILD + "child_checkpoint_committed", 1),
    "child.child_capability_activation": (CHILD + "result_committed", CHILD + "result_committed", 1),
    "recovery.ordinary_target_preparation": (RESUME + "resume_disposition_committed", RESUME + "resume_disposition_committed", 1),
    "recovery.ordinary_target_no_side_effects": (RESUME + "resume_disposition_committed", RESUME + "resume_disposition_committed", 1),
    "capability.initial_commit_activation": (START + "result_committed", START + "result_committed", 1),
    "capability.ordinary_commit_activation": (ADVANCE + "result_committed", ADVANCE + "result_committed", 1),
    "pause.same_key_replay": ("control.resume_run.abandon_and_halt.pause_and_terminal_ownership_reserved", "coordinator.key_lookup", 1),
    "pause.conflicting_key": ("control.resume_run.abandon_and_halt.pause_and_terminal_ownership_reserved", "control.resume_run.abandon_and_halt.pause_and_terminal_ownership_reserved", 1),
    "pause.double_claim": ("control.resume_run.abandon_and_halt.pause_and_terminal_ownership_reserved", "control.resume_run.abandon_and_halt.pause_and_terminal_ownership_reserved", 1),
    "pause.terminal_owner_race": ("control.resume_run.abandon_and_halt.pause_and_terminal_ownership_reserved", "control.resume_run.abandon_and_halt.pause_and_terminal_ownership_reserved", 1),
    "pause.source_owner_race": (CHILD + "source_snapshot_committed", CHILD + "source_snapshot_committed", 1),
    "pause.capability_race": (RESUME + "invocation_authorized", RESUME + "invocation_authorized", 1),
    "pause.cancel_winner_observation": ("control.cancel_pause.not_applicable.resolution_winner_observed", "control.cancel_pause.not_applicable.resolution_winner_observed", 1),
    "pause.normal_cancel_interrupt_all_orderings": ("control.cancel_pause.not_applicable.cancel_arbitrated", "control.cancel_pause.not_applicable.cancel_arbitrated", 1),
}


def rows(coordinator):
    return {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)] for table in TABLES}


@contextmanager
def rejection_fixture(boundary):
    if boundary == "recovery.human_input_only":
        from helpers.construction_cases import fixture_value
        from lqcd_agent.control.pause import ResumeRunRequest
        with ExitStack() as stack:
            coordinator, plane, actor, locator, pause, payload = fixture_value("human_pause", stack)
            payload = {"action": "abandon_and_halt"}
            request = ResumeRunRequest(locator, pause, "rejected", "recovery_decision", payload, digest(payload))
            config = {"root": str(coordinator.root), "method": "resume_run", "request_class": "ResumeRunRequest", "request": asdict(request),
                      "actor": asdict(actor), "safe": True, "failure": False, "route": "decision_coordinator", "variant": "abandon_and_halt",
                      "violation": False, "expect_rejection": True}
            yield coordinator, config, "resume.request"
        return
    recovery_target = {"recovery.code_agent_rejected": "code_agent", "recovery.legacy_handoff_rejected": "codex_handoff"}.get(boundary)
    phase = ("control.replay_run.not_applicable.operation_reserved" if boundary.startswith("ingress.") else
             RESUME + "resume_disposition_committed" if recovery_target or boundary == "recovery.external_result_only" else
             "control.resume_run.abandon_and_halt.pause_and_terminal_ownership_reserved" if boundary.startswith("recovery.") else
             START + "invocation_capability_prepared")
    with phase_fixture(phase + ".before.integrity_conflict", recovery_target=recovery_target) as (coordinator, config):
        hook = "resume.request"
        if boundary.startswith("ingress."):
            hook = "ingress.source_record"
            locator = config["request"]["source_run_locator"]
            ledger = coordinator.root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl"
            lines = ledger.read_bytes().splitlines(keepends=True)
            record = loads(lines[0].rstrip(b"\n"))
            kind = boundary.split(".")[1]
            if kind == "duplicate_key":
                lines[0] = b'{"schema_version":"0.4",' + lines[0][1:]
            elif kind in ("nan", "infinity", "negative_infinity", "overflow"):
                token = {"nan": "NaN", "infinity": "Infinity", "negative_infinity": "-Infinity", "overflow": "1e9999"}[kind]
                lines[0] = canonical_bytes(record).replace(b'"event_index":1', ('"event_index":' + token).encode()) + b"\n"
            else:
                if kind == "unknown_field":
                    record["unknown"] = True
                elif kind == "missing_field":
                    del record["event_index"]
                else:
                    record["event_index"] = "one"
                lines[0] = canonical_bytes(record) + b"\n"
            ledger.write_bytes(b"".join(lines))
        elif boundary in ("bootstrap.stale_epoch_rejection", "capability.no_early_redemption"):
            run_client(config, 0, fault=(START + "result_committed", "before"))
            operation = coordinator.lookup_key("public_control", config["request"]["idempotency_key"])
            if boundary == "bootstrap.stale_epoch_rejection":
                coordinator.clock.advance(31)
                coordinator.acquire(operation["operation_id"], "worker", lease_seconds=30)
                config.update(guard="stale_epoch", fence_arguments={"operation_id": operation["operation_id"], "worker": "worker",
                              "epoch": operation["lease_epoch"], "revision": operation["phase_revision"]})
                hook = "coordinator.operation_fence"
            else:
                config.update(guard="early_capability", capability_id="capability_" + operation["operation_id"])
                hook = "invocation.activation_check"
        elif recovery_target is None:
            payload = {"action": "continue_existing_target"}
            config["request"].update(input_kind="recovery_decision", input_snapshot=payload, input_digest=digest(payload))
        config["expect_rejection"] = True
        yield coordinator, config, hook


def exercise_rejection(case_id):
    spec = SPECS[case_id]
    boundary, side, _ = case_id.rsplit(".", 2)
    with rejection_fixture(boundary) as (coordinator, config, hook):
        before, files = rows(coordinator), run_files(coordinator.root)
        receipt = process_hook_request(case_id, Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-guard-evidence-", dir="/private/tmp")))
        run_client(config, 40, fault=(hook, side), hook_request=receipt)
        assert rows(coordinator) == before and run_files(coordinator.root) == files
        result = run_client(config, 40)["result"]
        assert result["rejected"] is True
        assert run_client(config, 40)["result"] == result
        assert rows(coordinator) == before and run_files(coordinator.root) == files
        return {"schema_version": "0.1", "events": [event("guard_fault", phase=hook, stage=side, target=boundary),
                event("guard_rejected", target=boundary, outcome="integrity_conflict", invariants=sorted(spec["invariants"]))]}


def exercise_supplemental_case(case_id):
    boundary, side, outcome = case_id.rsplit(".", 2)
    if boundary in PUBLICATIONS:
        fixture, hook, occurrence = PUBLICATIONS[boundary]
        trace = exercise_phase_case(case_id, fixture_case=fixture + "." + side + "." + outcome, fault_point=hook, occurrence=occurrence,
            arm_after=[START + "policy_published", "after"] if boundary in ("bootstrap.database_commit", "bootstrap.database_sync") else None,
            recovery_target="decision_coordinator" if boundary.startswith("recovery.") or boundary == "pause.capability_race" else None,
            takeover=boundary == "bootstrap.worker_lease_takeover",
            competition={"pause.same_key_replay": "same_key", "pause.conflicting_key": "double_claim", "pause.double_claim": "double_claim",
                         "pause.terminal_owner_race": "terminal_owner", "pause.source_owner_race": "source_owner", "pause.capability_race": "capability"}.get(boundary))
        if boundary == "pause.normal_cancel_interrupt_all_orderings":
            from helpers.construction_cases import fixture_value
            from test_resolution_orderings import ORDERINGS, test_normal_cancel_interrupt_orderings_preserve_one_resolution_and_terminal_owner
            for ordering in ORDERINGS:
                with ExitStack() as stack:
                    test_normal_cancel_interrupt_orderings_preserve_one_resolution_and_terminal_owner(fixture_value("control", stack), ordering)
                trace["events"].append(event("resolution_ordering_verified", stage="-".join(ordering), outcome="one_winner"))
        return trace
    return exercise_rejection(case_id)
