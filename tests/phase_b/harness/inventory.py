"""Independent publication inventory and final case semantics from frozen contracts."""
from copy import deepcopy

from .contracts import PROTOCOL_SHA, CATALOG_SHA, EXIT_CHECKS
from .strict_json import keys, require, strings, text, digest, path_in, callable_ref

META_REFS = ["A07-META-006", "A07-META-015"]
OUTCOMES = (
    "committed_result_replay", "materializable_publication_prefix",
    "non_materializable_domain_gap", "integrity_conflict",
)
REJECTION_BOUNDARIES = {
    "recovery.code_agent_rejected", "recovery.legacy_handoff_rejected", "recovery.null_target_abandon_only",
    "recovery.external_result_only", "recovery.human_input_only", "recovery.unchanged_pause_on_rejection",
    "analysis.conflicting_bytes", "analysis.stale_epoch", "analysis.capability_before_preparation",
    "release.conflicting_bytes", "release.stale_generation", "release.stale_epoch", "release.missing_settlement",
    "release.missing_attempt", "release.missing_artifact", "release.forged_not_applicable",
    "consumption_failure.second_stop_owner", "consumption_failure.duplicate_settlement",
    "consumption_failure.forged_artifact", "consumption_failure.backend_proof_not_consumer_proof",
    "consumption_failure.late_writer", "consumption_failure.nonexternal_reason_rejection",
    "bootstrap.stale_epoch_rejection", "external.late_writer", "capability.no_early_redemption",
}
UNCERTAIN_EFFECT_BOUNDARIES = {
    "external.backend_dispatch", "external.backend_cancel", "external.containment_kill_all",
    "analysis.fresh_subprocess", "timeout_completion.no_redispatch",
}
# These are A07 publication boundaries not represented as separate operation phases.
SUPPLEMENTAL = {
    "B02": {
        "bootstrap": ["database_commit", "database_sync", "root_exclusive_create", "parent_directory_sync",
                      "run_record", "initializing_lifecycle", "policy_initialization", "bootstrap_admission",
                      "initial_cycle", "planner_attempt", "initial_invalidation", "start_transition",
                      "capability_activation", "worker_lease_takeover", "stale_epoch_rejection"],
        "child": ["source_snapshot", "source_revision_cas", "lineage_publication", "child_policy",
                  "child_root", "child_ledger", "child_checkpoint", "child_capability_activation"],
        "pause": ["same_key_replay", "conflicting_key", "double_claim", "terminal_owner_race",
                  "source_owner_race", "capability_race", "cancel_winner_observation",
                  "normal_cancel_interrupt_all_orderings"],
        "recovery": ["ordinary_target_preparation", "ordinary_target_no_side_effects", "code_agent_rejected",
                     "legacy_handoff_rejected", "null_target_abandon_only", "external_result_only",
                     "human_input_only", "unchanged_pause_on_rejection"],
        "ingress": ["duplicate_key", "nan", "infinity", "negative_infinity", "overflow",
                    "unknown_field", "missing_field", "wrong_scalar"],
        "capability": ["ordinary_commit_activation", "initial_commit_activation", "no_early_redemption"],
    },
    "B03": {
        "external": ["stub", "task", "unmaterialized_manifest", "aggregate_reservation", "immutable_core_cas",
                     "workspace_materialization", "workspace_lease", "dispatch_authorization", "backend_dispatch",
                     "receipt", "backend_completion", "workspace_seal", "immutable_result", "delivery_snapshot",
                     "resolution_cas", "late_writer", "normal_unavailable_reclassification",
                     "watchdog_takeover", "backend_cancel", "write_lease_revocation", "containment_kill_all",
                     "verify_empty", "bounded_drain", "post_stop_stability", "termination_evidence",
                     "final_evidence", "trusted_verification", "code_attempt_started", "code_attempt_finished",
                     "bundle_members", "bundle_registration", "bundle_current"],
        "analysis": ["spec_exclusive_create", "fresh_workspace", "effective_tree_verification",
                     "preparation_proof", "fresh_subprocess", "artifact_publication",
                     "exact_duplicate", "conflicting_bytes", "stale_epoch", "capability_before_preparation",
                     "no_bundle_not_applicable", "non_analysis_not_applicable"],
        "release": ["normal_delivery", "recoverable_timeout", "settlement", "pause_consumed",
                    "attempt_terminal", "artifact_terminal", "binding_release", "final_checkpoint",
                    "outbound_transition", "end", "second_code_operation", "post_claim_system_stop",
                    "duplicate_proof", "conflicting_bytes", "stale_generation", "stale_epoch",
                    "missing_settlement", "missing_attempt", "missing_artifact", "forged_not_applicable"],
        "consumption_failure": ["failure_intent_worker_race", "second_stop_owner", "duplicate_settlement",
                                "forged_artifact", "backend_proof_not_consumer_proof", "late_writer",
                                "nonexternal_reason_rejection", "detached_close_after_release"],
        "timeout_completion": ["authorization", "attempt_started", "artifact_registered", "attempt_finished",
                               "final_checkpoint", "no_redispatch", "late_integrity", "late_unavailable"],
    },
    "B04": {
        "budget": ["decision_before_transition", "decision_before_resource", "grant_consumed",
                   "grant_target_allocation", "grant_invalidation", "grant_transition", "resource_reserved",
                   "resource_settled", "invalid_response_allow", "invalid_response_halt",
                   "grant_owner_race", "terminal_reserve"],
        "artifact": ["transition_before_target_started", "bundle_before_analysis_transition",
                     "history_publication", "index_publication", "projection_publication", "bounded_state_sync"],
    },
}


CASE_VERSION = "0.2"


def expected_inventory(protocol, *, version=CASE_VERSION):
    """Return immutable expectations independently of matrix or registry input."""
    require(version in ("0.1", CASE_VERSION), "inventory", "case_version")
    control = protocol["state_machines"]["control_operation"]
    entries = []

    def add(identifier, owner, locator, effect, precondition, outcomes):
        entries.append({
            "failpoint_id": identifier, "source_locator": locator, "boundary_owner": owner,
            "implementation_ticket_id": owner, "effect_class": effect, "precondition": precondition,
            "allowed_exact_outcomes": sorted(outcomes), "contract_refs": META_REFS,
            "hook_ref": None, "case_bindings": [],
        })

    for operation in control["operations"]:
        for variant in operation["variants"]:
            can_commit = {"result_committed"}
            while True:
                reachable = can_commit | {source for source, target in variant["success_edges"] if target in can_commit}
                if reachable == can_commit:
                    break
                can_commit = reachable
            for phase in variant["phases"]:
                contract = control["phase_contracts"][phase]
                outcomes = list(OUTCOMES)
                if contract["continuation_policy"] != "materialize_if_precomputed":
                    outcomes.remove("materializable_publication_prefix")
                if version == CASE_VERSION and phase == "operation_reserved":
                    outcomes = ["reservation_rolled_back"]
                elif version == CASE_VERSION and phase not in can_commit:
                    outcomes = ["terminal_tombstone_replay" if outcome == "committed_result_replay" else outcome for outcome in outcomes]
                add(f"control.{operation['operation_type']}.{variant['operation_variant']}.{phase}",
                    "B02", "A07#fault-injection-and-crash-outcomes",
                    contract["effect_class"], contract["continuation_policy"], outcomes)
    external = protocol["state_machines"]["external_operation"]
    for phase in external["phases"]:
        contract = external["phase_contracts"][phase]
        outcomes = [outcome for outcome in OUTCOMES if outcome != "materializable_publication_prefix"
                    or contract["continuation_policy"] == "materialize_if_precomputed"]
        add(f"external.{phase}", "B03", "A07#fault-injection-and-crash-outcomes",
            contract["effect_class"], contract["continuation_policy"], outcomes)
    for owner, groups in SUPPLEMENTAL.items():
        for group, boundaries in groups.items():
            for boundary in boundaries:
                fp = f"{group}.{boundary}"
                outcomes = list(OUTCOMES)
                if fp in REJECTION_BOUNDARIES or group == "ingress":
                    outcomes = ["integrity_conflict"]
                elif version == CASE_VERSION and fp == "child.source_revision_cas":
                    outcomes = ["reservation_rolled_back"]
                elif fp in UNCERTAIN_EFFECT_BOUNDARIES:
                    outcomes.remove("materializable_publication_prefix")
                add(f"{group}.{boundary}", owner, "A07#fault-injection-and-crash-outcomes",
                    "verification", f"{group}.{boundary}:frozen_source_and_authority_verified", outcomes)
    for phase in control["consumption_failure_contract"]["entry_phases"]:
        add(f"post_claim.{phase}", "B03", "A07#post-claim-integrity-failure",
            "verification", "same_resume_owner_normal_external_resolution",
            ["failed_closure", "unavailable_closure"])
    return sorted(entries, key=lambda x: x["failpoint_id"])


def case_specs(protocol, *, version=CASE_VERSION):
    """Freeze the meaning of each case, including the 7 by 4 failure product."""
    cases = {}
    for entry in expected_inventory(protocol, version=version):
        fp = entry["failpoint_id"]
        if fp.startswith("post_claim."):
            for choice in protocol["state_machines"]["control_operation"]["consumption_failure_contract"]["classification"]:
                case_id = f"{fp}.{choice['consumer_stop']}.{choice['run_authority']}"
                cases[case_id] = {
                    "failpoint_id": fp, "outcome": choice["outcome"],
                    "invariants": [f"consumer_stop:{choice['consumer_stop']}", f"run_authority:{choice['run_authority']}",
                                   "same_resume_owner", "normal_external_resolution_immutable"],
                }
        else:
            # Each permitted recovery class is tested with its own deterministic authority/evidence context.
            for side in ("before", "after"):
                for outcome in entry["allowed_exact_outcomes"]:
                    case_id = f"{fp}.{side}.{outcome}"
                    invariants = [f"publication_side:{side}", "frozen_outcome_classification"]
                    if outcome == "reservation_rolled_back":
                        invariants.extend(["authority_context:initial_reservation_before_commit", "no_durable_operation",
                                           "no_owner_or_capability", "no_domain_mutation", "fresh_request_readmission"])
                    if outcome == "terminal_tombstone_replay":
                        invariants.extend(["authority_context:unavailable_only_successor_graph", "immutable_terminal_tombstone",
                                           "no_fabricated_committed_result", "no_target_reexecution"])
                    if fp in REJECTION_BOUNDARIES or fp.startswith("ingress."):
                        invariants.extend(["no_domain_mutation", "no_automatic_stop", "no_capability_or_dispatch"])
                    if fp.startswith("recovery."):
                        invariants.append("original_target_preparation_and_authorization")
                    if fp in UNCERTAIN_EFFECT_BOUNDARIES:
                        invariants.append("no_redispatch_or_target_reexecution")
                    cases[case_id] = {"failpoint_id": fp, "outcome": outcome, "invariants": invariants}
    return dict(sorted(cases.items()))


def expected_obligations(protocol, *, version=CASE_VERSION):
    specs = case_specs(protocol, version=version)
    obligations = []
    for entry in expected_inventory(protocol, version=version):
        fp = entry["failpoint_id"]
        obligations.append({
            "obligation_id": fp, "contract_refs": META_REFS, "source_locator": entry["source_locator"],
            "case_ids": [cid for cid, spec in specs.items() if spec["failpoint_id"] == fp],
            "failpoint_ids": [fp],
        })
    return {"schema_version": version, "control_protocol_sha256": PROTOCOL_SHA,
            "requirement_catalog_sha256": CATALOG_SHA, "runtime_obligations": obligations,
            "exit_check_ids": list(EXIT_CHECKS)}


def registry_skeleton(protocol, *, version=CASE_VERSION):
    return {"schema_version": version, "control_protocol_sha256": PROTOCOL_SHA,
            "requirement_catalog_sha256": CATALOG_SHA, "entries": expected_inventory(protocol, version=version)}


def expected_dispositions(protocol):
    """Account for every old B02 obligation without claiming it has runtime evidence."""
    owned = {row["failpoint_id"] for row in expected_inventory(protocol, version="0.1") if row["boundary_owner"] == "B02"}
    rows = []
    current = case_specs(protocol)
    for case_id, spec in case_specs(protocol, version="0.1").items():
        fp = spec["failpoint_id"]
        if fp not in owned:
            continue
        side = case_id.removeprefix(fp + ".").split(".", 1)[0]
        rollback = fp.endswith(".operation_reserved") or fp == "child.source_revision_cas"
        tombstone = not rollback and case_id not in current
        replaced = rollback or tombstone
        context = "initial_reservation_before_commit" if rollback else "unavailable_only_successor_graph" if tombstone else (
            "no_owned_mutation_rejection" if fp in REJECTION_BOUNDARIES or fp.startswith("ingress.")
            else "existing_operation_authority_and_frozen_outcome")
        rows.append({"old_case_id": case_id, "disposition": "replaced" if replaced else "retained",
                     "new_case_ids": [fp + "." + side + ".reservation_rolled_back"] if rollback else [fp + "." + side + ".terminal_tombstone_replay"] if tombstone else [case_id],
                     "authority_context": context, "contract_locator": "A02C01#reference-durability-profile" if rollback else "A07#fault-injection-and-crash-outcomes",
                     "counterexample_nodeid": "tests/phase_b/test_b02_reservation_boundaries.py::test_fork_source_cas_process_exit_is_still_before_reservation_commit[" + side + "]" if fp == "child.source_revision_cas" else
                         "tests/phase_b/test_b02_reservation_boundaries.py::test_reservation_process_exit_rolls_back_without_an_operation_or_run[" + side + "]" if rollback else
                         "tests/phase_b/test_reservation_case_semantics.py::test_unavailable_branch_cannot_replay_a_committed_result[" + fp.split(".")[1] + "." + fp.split(".")[2] + "]" if tombstone else None})
    return {"schema_version": CASE_VERSION, "previous_case_version": "0.1", "boundary_owner": "B02", "dispositions": rows}


def inventory_projection(registry):
    result = deepcopy(registry)
    for entry in result["entries"]:
        entry["hook_ref"] = None
        entry["case_bindings"] = []
    return result


def validate_inventory(registry, obligations, protocol, root, scenarios):
    from .seals import REGISTRY_INVENTORY_SHA256, FINAL_OBLIGATIONS_SHA256
    keys(registry, {"schema_version", "control_protocol_sha256", "requirement_catalog_sha256", "entries"}, "registry")
    require(registry["schema_version"] == CASE_VERSION and obligations.get("schema_version") == CASE_VERSION,
            "inventory", "case_version")
    require(type(registry["entries"]) is list, "registry", "entries")
    fields = set(expected_inventory(protocol)[0])
    for entry in registry["entries"]:
        keys(entry, fields, "failpoint")
    require(digest(inventory_projection(registry)) == REGISTRY_INVENTORY_SHA256, "registry", "inventory_seal")
    require(digest(obligations) == FINAL_OBLIGATIONS_SHA256, "obligations", "independent_seal")
    require(inventory_projection(registry) == registry_skeleton(protocol), "registry", "inventory")
    require(obligations == expected_obligations(protocol), "obligations", "case_semantics")
    from .strict_json import read
    dispositions = read(path_in(root, "tests/phase_b/reservation_case_dispositions.json"))
    require(dispositions == expected_dispositions(protocol), "dispositions", "complete_old_to_new")
    specs = case_specs(protocol)
    scenario_index = {s["scenario_id"]: s for s in scenarios}
    for entry in registry["entries"]:
        fp = entry["failpoint_id"]
        hook = entry["hook_ref"]
        if hook is not None:
            text(hook, fp, "hook_ref")
            relative, separator, qualname = hook.partition(":")
            require(separator and qualname and relative.startswith("src/lqcd_agent/"), fp, "hook_ref")
            callable_ref(root, hook)
        require(type(entry["case_bindings"]) is list, fp, "case_bindings")
        seen = []
        for binding in entry["case_bindings"]:
            keys(binding, {"case_id", "scenario_ids"}, fp)
            cid = binding["case_id"]
            require(cid in specs and specs[cid]["failpoint_id"] == fp, fp, "case_id")
            strings(binding["scenario_ids"], fp, "scenario_ids")
            refs = set()
            for sid in binding["scenario_ids"]:
                require(sid in scenario_index, fp, "scenario_ids")
                scenario = scenario_index[sid]
                require(scenario["required"] and scenario["validation_stage"] == "final", fp, "scenario_stage")
                require(bool(scenario["expected_trace_fixture"]), fp, "expected_trace_fixture")
                refs.update(scenario["contract_refs"])
            require(set(entry["contract_refs"]) <= refs, fp, "required_contract_refs")
            seen.append(cid)
        strings(seen, fp, "case_bindings", nonempty=False)
    return specs
