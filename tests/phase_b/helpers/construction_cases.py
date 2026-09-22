"""Construction scenarios reuse reviewed production assertions and durable phase facts."""
from contextlib import ExitStack
import importlib
from itertools import permutations
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from harness.trace import event
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.clock import FakeClock


def check(module, name, fixture=None, **arguments):
    return {"module": "test_" + module, "function": "test_" + name, "fixture": fixture, "arguments": arguments}


CASES = {
    "A02-TRANSITION-001": [check("advance_control", "advance_allocates_then_prepares_and_activates_exact_capability", target="decision_coordinator")],
    "A02-CONSUME-001": [check("bootstrap_control", "invocation_start_order_stale_lease_and_no_intent_takeover", "root")],
    "A02-HUMAN-001": [check("human_control", "human_claim_then_allocate_consume_start_and_validate", "human_pause")],
    "A02C01-BOOTSTRAP-001": [check("bootstrap_control", "start_bootstrap_produces_real_separate_checkpoint_and_inactive_then_active_capability", "root")],
    "A02C01-BOOTSTRAP-002": [check("durable_control_operations", "operation_lease_fences_old_epoch_and_queries_do_not_renew", "output_root"), check("bootstrap_control", "start_each_phase_recovers_in_fresh_process", "root", phase="run_root_created")],
    "A02C01-BOOTSTRAP-003": [check("bootstrap_control", "bootstrap_integrity_failure_has_durable_unique_terminal_owner", "root", corruption="partial"), check("durable_control_operations", "fresh_process_crash_materializes_only_committed_plan", "output_root")],
    "A02C01-BOOT-004": [check("pause_control", "null_external_cancel_owns_pause_and_terminal_together", "control"), check("durable_control_operations", "closed_coordinator_schema_and_consistent_backup", "output_root")],
    "A04-PAUSE-001": [check("pause_control", "pause_real_process_restart_preserves_published_producers", "control", action="abandon", phase="pause_claimed_recorded", side="after"), check("human_control", "human_fresh_process_recovery_preserves_claim_and_never_reinvokes_started", "human_pause", crash_boundary=("control.resume_run.continue_execution.pause_claimed_recorded", "after")), check("external_consumption_control", "normal_consumption_fresh_process_continues_without_redispatch", "normal_external", crash_boundary=("control.resume_run.continue_execution.pause_claimed_recorded", "after"))],
    "A04-PAUSE-002": [check("human_control", "two_real_processes_reserve_before_competing_for_one_human_claim", "human_pause", same_key=same) for same in (False, True)],
    "A04-PAUSE-003": [check("bootstrap_control", "start_rejects_untrusted_inputs_before_operation_or_run_identity", "root", mutation=value) for value in ("scope", "digest", "path")] + [check("pause_control", "null_recovery_resume_abandons_without_attempt_or_expires_without_mutation", "control", elapsed=60)],
    "A04-PAUSE-004": [check("human_control", "invalid_response_repauses_until_reserved_terminal_capacity_requires_halt", "human_pause", profile="balanced_v1")],
    "A04-PAUSE-005": [check("pause_control", "recovery_continue_only_reuses_an_allowed_ordinary_target", "control", target=target) for target in ("decision_coordinator", "code_agent", "codex_handoff")],
    "A04-PAUSE-006": [check("target_preparation_control", "analysis_recovery_preserves_original_preparation", "prepared_source"), check("pause_control", "null_recovery_resume_abandons_without_attempt_or_expires_without_mutation", "control", elapsed=59)],
    "A04-PAUSE-007": [check("legacy_source_compatibility", "legacy_fork_and_resume_remain_rejected", "legacy_control"), check("historical_source_control", "historical_invalid_source_rejects_before_child_reservation", "historical", fault="claimed")],
    "A04-PAUSE-008": [check("failure_closure_regressions", "corrupt_pause_log_closes_original_operation_after_restart", "control", action=action) for action in ("publish", "cancel", "resume")] + [check("snapshot_loss_control", "pause_plan_loss_is_terminal_and_preserves_existing_owners_after_process_restart", "control", action="publish", missing=True)],
    "A04-PAUSE-009": [check("external_control", "external_pause_binds_only_after_real_prepared_publication", "control"), check("external_consumption_control", "normal_external_consumption_releases_before_final_checkpoint", "normal_external")],
    "A04-PAUSE-010": [check("pause_control", "recovery_pause_publication_has_exact_two_checkpoint_closure", "control")],
    "A04-PAUSE-011": [check("child_control", "child_bootstrap_reuses_admission_and_never_mutates_source", "child_control", fork=fork) for fork in (False, True)] + [check("legacy_source_compatibility", "real_legacy_replay_preserves_source_and_records_historical_absence", "legacy_control")],
    "A04-PAUSE-012": [check("historical_source_control", "historical_fork_snapshot_and_claim_serialize_in_two_processes", "historical", fork_first=first) for first in (False, True)] + [check("historical_source_control", "historical_invalid_source_rejects_before_child_reservation", "historical", fault="stale_head")],
    "A04-PAUSE-013": [check("child_control", "child_bootstrap_reuses_admission_and_never_mutates_source", "child_control", fork=True)],
    "A04-PAUSE-014": [check("durable_control_operations", "frozen_publications_are_immutable_and_lease_fenced", "output_root"), check("advance_control", "advance_allocates_then_prepares_and_activates_exact_capability", target="code_agent")],
    "A04-PAUSE-015": [check("terminal_control", "runtime_failure_close_is_unique_and_replays_without_new_bytes", "control"), check("external_consumption_control", "normal_final_system_stop_detaches_without_consuming", "normal_external")],
    "A04-PAUSE-016": [check("pause_control", "null_recovery_resume_abandons_without_attempt_or_expires_without_mutation", "control", elapsed=59)],
    "A04-PAUSE-017": [check("external_consumption_control", "post_claim_consumer_failure_preserves_normal_final_and_original_owner", "normal_external", safe=safe, appendable=True) for safe in (False, True)] + [check("external_consumption_control", "normal_final_close_and_resume_have_one_owner_across_processes", "normal_external", close_first=first) for first in (False, True)],
    "A04-PAUSE-018": [check("external_control", "external_cancel_resolves_from_verified_stop_not_backend_status", "control", case=value) for value in ("cancel_safe", "cancel_violation", "cancel_unavailable", "normal_safe", "normal_violation")],
    "A04-PAUSE-019": [check("timeout_consumption_control", "safe_timeout_consumes_same_failed_attempt_before_outbound", "timeout_source"), check("external_control", "external_interrupt_owns_typed_terminal_tail", "control", reason="proven_integrity_trigger", safe=False, violation=False, opened=True)],
    "A04-PAUSE-020": [check("external_control", "cancel_observes_existing_winner_without_consuming_final_or_acquiring_owners", "control", winner_kind=kind, safe=safe) for kind in ("cancel", "interrupt") for safe in (False, True)],
    "A04-PAUSE-021": [check("target_preparation_control", "fresh_preparation_bound_to_committed_transition_before_capability", "prepared_source")],
    "A06-BUDGET-012": [check("pause_control", "null_recovery_resume_abandons_without_attempt_or_expires_without_mutation", "control", elapsed=elapsed) for elapsed in (59, 60, 61)],
    "A06-BUDGET-014": [check("legacy_source_compatibility", "real_legacy_replay_preserves_source_and_records_historical_absence", "legacy_control"), check("historical_source_control", "historical_source_creates_fresh_child_without_source_mutation", "historical", fork=True), check("child_control", "child_bootstrap_reuses_admission_and_never_mutates_source", "child_control", fork=False)],
}

CASES["A04-PAUSE-003"] = [check("resume_admission_regressions", "resume_admission_mismatch_preserves_all_authority", "control", mutation=mutation)
                            for mutation in ("actor", "scope", "run", "pause", "payload_digest", "reason")]
CASES["A04-PAUSE-007"] += [check("resume_admission_regressions", "resume_admission_mismatch_preserves_all_authority", "control", mutation=mutation)
                             for mutation in ("prepared", "terminal")]
CASES["A04-PAUSE-015"].append(check("invocation_artifacts", "real_registered_outputs_reach_end_then_unique_completed_closure"))
CASES["A04-PAUSE-018"] += [check("resolution_orderings", "normal_cancel_interrupt_orderings_preserve_one_resolution_and_terminal_owner", "control", ordering=order)
                             for order in permutations(("normal", "cancel", "interrupt"))]

FIXTURES = {"control": "test_pause_control", "human_pause": "test_human_control", "normal_external": "test_external_consumption_control",
            "child_control": "test_child_control", "legacy_control": "test_legacy_source_compatibility", "historical": "test_historical_source_control",
            "timeout_source": "test_timeout_consumption_control", "prepared_source": "test_target_preparation_control"}


def fixture_value(name, stack, *, profile="phase_b_test"):
    if name in ("root", "output_root"):
        return Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-construction-", dir="/private/tmp"))
    function = getattr(importlib.import_module(FIXTURES[name]), name).__wrapped__
    args = (SimpleNamespace(param=profile),) if name == "human_pause" else (fixture_value("normal_external", stack),) if name == "prepared_source" else ()
    generator = function(*args)
    value = next(generator)
    stack.callback(generator.close)
    return value


def construction_trace(requirement):
    events = []
    close = Coordinator.close
    for number, spec in enumerate(CASES[requirement]):
        snapshots = {}
        def capture(coordinator):
            rows = []
            for row in coordinator.connection.execute("SELECT operation_id FROM control_operations ORDER BY operation_type,operation_variant,status,phase_revision,rowid").fetchall():
                operation = coordinator.get(row[0])
                rows.extend(event("control_phase", source=operation["operation_type"], target=operation["operation_variant"],
                                  phase=phase["phase"], phase_revision=phase["revision"], lease_epoch=phase["lease_epoch"])
                            for phase in coordinator.history(row[0]))
                rows.append(event("control_result", source=operation["operation_type"], target=operation["operation_variant"], status=operation["status"], phase=operation["phase"],
                                  phase_revision=operation["phase_revision"], lease_epoch=operation["lease_epoch"]))
            snapshots[str(coordinator.root)] = rows
            close(coordinator)
        with patch.object(Coordinator, "close", capture), ExitStack() as stack:
            arguments = dict(spec["arguments"])
            profile = arguments.pop("profile", "phase_b_test")
            if spec["fixture"]:
                arguments[spec["fixture"]] = fixture_value(spec["fixture"], stack, profile=profile)
            getattr(importlib.import_module(spec["module"]), spec["function"])(**arguments)
            if not snapshots and spec["fixture"] in ("root", "output_root"):
                Coordinator(arguments[spec["fixture"]], clock=FakeClock(200, 100)).close()
        assert snapshots, "Construction requires actual coordinator evidence"
        for rows in snapshots.values():
            events.extend(rows)
        events.append(event("assertions_completed", stage=spec["module"] + ":" + spec["function"], index=number,
                            outcome="verified", invariants=[requirement]))
    return {"schema_version": "0.1", "events": events}
