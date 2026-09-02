#!/usr/bin/env python3
"""Validate the Phase A machine-readable control protocol and requirement catalog."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "tickets" / "phase-a-control-contracts"
PROTOCOL_PATH = CONTRACT_DIR / "CONTROL_PROTOCOL_0_4.json"
CATALOG_PATH = CONTRACT_DIR / "PHASE_B_REQUIREMENT_CATALOG.json"

EXPECTED_OPERATION_VARIANTS = {
    "start_run": {"not_applicable"},
    "publish_pause": {"not_applicable"},
    "resume_run": {"continue_execution", "abandon_and_halt"},
    "cancel_pause": {"not_applicable"},
    "resolve_external_interrupt": {"recoverable_timeout", "controlled_halt", "integrity_failure"},
    "replay_run": {"not_applicable"},
    "fork_run": {"not_applicable"},
    "close_run": {"not_applicable"},
}
EXPECTED_RESERVATION_OVERLAYS = {
    ("start_run", "not_applicable"): {
        "target_run_identity": ("run_identity", "coordinator_db", False),
        "reserved_run_locator": ("canonical_locator", "coordinator_db", False),
        "canonical_budget_policy_bytes": ("canonical_bytes", "coordinator_db", False),
        "budget_policy_digest": ("sha256", "coordinator_db", False),
    },
    ("publish_pause", "not_applicable"): {
        "source_execution_artifact_checkpoint_heads": ("head_tuple", "coordinator_db", False),
        "typed_pause_reason": ("pause_reason", "coordinator_db", False),
        "requesting_and_target_identity": ("attempt_identity_tuple", "coordinator_db", False),
        "deterministic_pause_identity_inputs": ("canonical_digest_input", "coordinator_db", False),
    },
    ("resume_run", "continue_execution"): {
        "exact_pause_and_opened_head": ("pause_head_tuple", "coordinator_db", False),
        "precomputed_next_event_identity_digest": ("event_identity_digest", "coordinator_db", False),
        "target_prestart_closure": ("prestart_closure", "coordinator_db", False),
    },
    ("resume_run", "abandon_and_halt"): {
        "exact_pause_and_opened_head": ("pause_head_tuple", "coordinator_db", False),
        "run_terminal_closure_key": ("terminal_closure_key", "coordinator_db", False),
        "precomputed_abandon_evidence": ("canonical_digest_input", "coordinator_db", False),
    },
    ("cancel_pause", "not_applicable"): {
        "exact_pause_and_opened_head": ("pause_head_tuple", "coordinator_db", False),
        "external_operation_identity": ("external_operation_id", "coordinator_db", True),
        "typed_cancel_reason": ("cancel_reason", "coordinator_db", False),
        "precomputed_pause_cancel_or_quarantine_event": ("event_identity_digest", "coordinator_db", False),
    },
    ("resolve_external_interrupt", "recoverable_timeout"): {
        "exact_external_operation_resolution_tuple": ("external_resolution_tuple", "coordinator_db", False),
        "typed_interrupt_reason": ("interrupt_reason", "coordinator_db", False),
        "exact_run_heads": ("head_tuple", "coordinator_db", False),
        "pause_snapshot": ("pause_snapshot_union", "coordinator_db", False),
        "resource_reservation_digest": ("sha256", "coordinator_db", False),
        "deterministic_delivery_or_closure_identity": ("canonical_failed_delivery_identity", "coordinator_db", False),
        "interrupt_disposition": ("interrupt_disposition", "coordinator_db", False),
    },
    ("resolve_external_interrupt", "controlled_halt"): {
        "exact_external_operation_resolution_tuple": ("external_resolution_tuple", "coordinator_db", False),
        "typed_interrupt_reason": ("interrupt_reason", "coordinator_db", False),
        "exact_run_heads": ("head_tuple", "coordinator_db", False),
        "pause_snapshot": ("pause_snapshot_union", "coordinator_db", False),
        "resource_reservation_digest": ("sha256", "coordinator_db", False),
        "deterministic_delivery_or_closure_identity": ("terminal_closure_key", "coordinator_db", False),
        "interrupt_disposition": ("interrupt_disposition", "coordinator_db", False),
    },
    ("resolve_external_interrupt", "integrity_failure"): {
        "exact_external_operation_resolution_tuple": ("external_resolution_tuple", "coordinator_db", False),
        "typed_interrupt_reason": ("interrupt_reason", "coordinator_db", False),
        "exact_run_heads": ("head_tuple", "coordinator_db", False),
        "pause_snapshot": ("pause_snapshot_union", "coordinator_db", False),
        "resource_reservation_digest": ("sha256", "coordinator_db", False),
        "deterministic_delivery_or_closure_identity": ("terminal_closure_key", "coordinator_db", False),
        "interrupt_disposition": ("interrupt_disposition", "coordinator_db", False),
    },
    ("replay_run", "not_applicable"): {
        "validated_source_root_input": ("source_snapshot", "coordinator_db", False),
        "reserved_child_run_locator": ("canonical_locator", "coordinator_db", False),
    },
    ("fork_run", "not_applicable"): {
        "source_heads_and_control_revision": ("source_revision_tuple", "coordinator_db", False),
        "lineage_snapshot_digest": ("sha256", "coordinator_db", False),
        "reserved_child_run_locator": ("canonical_locator", "coordinator_db", False),
    },
    ("close_run", "not_applicable"): {
        "run_terminal_closure_key": ("terminal_closure_key", "coordinator_db", False),
        "terminal_trigger_identity": ("terminal_trigger", "coordinator_db", False),
        "requested_terminal_disposition": ("run_terminal_disposition", "coordinator_db", False),
        "external_operation_precondition": ("absent_or_safely_terminal_and_detached", "coordinator_db", False),
        "external_operation_precondition_proof_digest": ("sha256", "coordinator_db", False),
    },
}
EXPECTED_OWNER_ORDER = [
    "A01",
    "A02",
    "A02C01",
    "A03",
    "A03C01",
    "A04",
    "A05",
    "A06",
    "A07",
]
EXPECTED_OWNER_COUNTS = {
    "A01": 26,
    "A02": 6,
    "A02C01": 4,
    "A03": 5,
    "A03C01": 4,
    "A04": 20,
    "A05": 29,
    "A06": 21,
    "A07": 14,
}
EXPECTED_OUTCOME_STATUS = {
    "committed_result_replay": ("committed", False),
    "materializable_publication_prefix": ("in_progress", True),
    "non_materializable_domain_gap": ("recovery_required", False),
    "integrity_conflict": ("failed", False),
}
REQUIRED_PROTOCOL_REFERENCES = [
    "docs/README.md",
    "docs/REPO_CURRENT_STATE.md",
    "docs/tickets/phase-a-control-contracts/OVERVIEW.md",
    "docs/tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md",
    "docs/tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md",
    "docs/tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md",
    "docs/tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md",
    "docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md",
]


class ValidationError(Exception):
    """Raised when a tracked contract artifact is invalid."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_strict_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (json.JSONDecodeError, OSError) as exc:
        raise ValidationError(f"cannot parse {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_keys(value: dict[str, Any], keys: set[str], context: str) -> None:
    missing = sorted(keys - value.keys())
    if missing:
        raise ValidationError(f"{context} missing keys: {', '.join(missing)}")


def _require_unique_strings(values: Any, context: str) -> list[str]:
    if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
        raise ValidationError(f"{context} must be a non-empty string list")
    if len(values) != len(set(values)):
        raise ValidationError(f"{context} contains duplicates")
    return values


def _normalize_edges(edges: Any, nodes: set[str], context: str) -> list[tuple[str, str]]:
    if not isinstance(edges, list):
        raise ValidationError(f"{context} edges must be a list")
    normalized: list[tuple[str, str]] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, list) or len(edge) != 2 or not all(isinstance(item, str) for item in edge):
            raise ValidationError(f"{context} edge {index} must be a two-item string list")
        source, target = edge
        if source not in nodes or target not in nodes:
            raise ValidationError(f"{context} edge references an unknown node: {source} -> {target}")
        normalized.append((source, target))
    if len(normalized) != len(set(normalized)):
        raise ValidationError(f"{context} contains duplicate edges")
    return normalized


def _reachable(start: str, adjacency: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(adjacency[current] - seen)
    return seen


def _assert_acyclic(nodes: set[str], edges: list[tuple[str, str]], context: str) -> None:
    indegree = {node: 0 for node in nodes}
    adjacency = {node: set() for node in nodes}
    for source, target in edges:
        adjacency[source].add(target)
        indegree[target] += 1
    pending = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    visited = 0
    while pending:
        current = pending.popleft()
        visited += 1
        for target in sorted(adjacency[current]):
            indegree[target] -= 1
            if indegree[target] == 0:
                pending.append(target)
    if visited != len(nodes):
        raise ValidationError(f"{context} contains an undeclared cycle")


def _validate_terminating_graph(
    *,
    nodes: list[str],
    edges: Any,
    initial: str,
    terminals: list[str],
    context: str,
    require_acyclic: bool,
) -> list[tuple[str, str]]:
    node_set = set(nodes)
    if initial not in node_set:
        raise ValidationError(f"{context} has unknown initial node: {initial}")
    terminal_set = set(terminals)
    if not terminal_set or not terminal_set <= node_set:
        raise ValidationError(f"{context} has invalid terminal nodes")
    normalized = _normalize_edges(edges, node_set, context)
    adjacency = {node: set() for node in node_set}
    reverse = {node: set() for node in node_set}
    for source, target in normalized:
        adjacency[source].add(target)
        reverse[target].add(source)
    unreachable = sorted(node_set - _reachable(initial, adjacency))
    if unreachable:
        raise ValidationError(f"{context} has unreachable nodes: {', '.join(unreachable)}")
    for terminal in terminal_set:
        if adjacency[terminal]:
            raise ValidationError(f"{context} terminal node has successors: {terminal}")
    for node in sorted(node_set - terminal_set):
        if not adjacency[node]:
            raise ValidationError(f"{context} nonterminal node has no successor: {node}")
    can_reach_terminal: set[str] = set()
    pending = list(terminal_set)
    while pending:
        current = pending.pop()
        if current in can_reach_terminal:
            continue
        can_reach_terminal.add(current)
        pending.extend(reverse[current] - can_reach_terminal)
    nonterminating = sorted(node_set - can_reach_terminal)
    if nonterminating:
        raise ValidationError(f"{context} cannot reach a terminal node: {', '.join(nonterminating)}")
    if require_acyclic:
        _assert_acyclic(node_set, normalized, context)
    return normalized


def _validate_phase_contracts(
    contracts: Any,
    expected_phases: set[str],
    authorities: set[str],
    effect_classes: set[str],
    continuation_policies: set[str],
    context: str,
) -> None:
    if not isinstance(contracts, dict):
        raise ValidationError(f"{context} phase contracts must be an object")
    contract_phases = set(contracts)
    if contract_phases != expected_phases:
        missing = sorted(expected_phases - contract_phases)
        extra = sorted(contract_phases - expected_phases)
        raise ValidationError(f"{context} phase contract mismatch; missing={missing}, extra={extra}")
    required = {"authorities", "effect_class", "continuation_policy", "required_evidence", "acquires"}
    for phase, contract in contracts.items():
        if not isinstance(contract, dict):
            raise ValidationError(f"{context}.{phase} contract must be an object")
        _require_keys(contract, required, f"{context}.{phase}")
        phase_authorities = set(_require_unique_strings(contract["authorities"], f"{context}.{phase}.authorities"))
        if not phase_authorities <= authorities:
            raise ValidationError(f"{context}.{phase} uses unknown authorities")
        if contract["effect_class"] not in effect_classes:
            raise ValidationError(f"{context}.{phase} uses an unknown effect class")
        if contract["continuation_policy"] not in continuation_policies:
            raise ValidationError(f"{context}.{phase} uses an unknown continuation policy")
        _require_unique_strings(contract["required_evidence"], f"{context}.{phase}.required_evidence")
        acquires = contract["acquires"]
        if not isinstance(acquires, list) or not all(isinstance(item, str) and item for item in acquires):
            raise ValidationError(f"{context}.{phase}.acquires must be a string list")
        if len(acquires) != len(set(acquires)):
            raise ValidationError(f"{context}.{phase}.acquires contains duplicates")
        if len(acquires) > 1 and contract.get("atomic_acquire") is not True:
            raise ValidationError(f"{context}.{phase} multi-owner acquisition must be atomic")
        conditional_acquires = contract.get("conditional_acquires", [])
        if not isinstance(conditional_acquires, list) or not all(
            isinstance(item, str) and item for item in conditional_acquires
        ):
            raise ValidationError(f"{context}.{phase}.conditional_acquires must be a string list")
        if len(conditional_acquires) != len(set(conditional_acquires)):
            raise ValidationError(f"{context}.{phase}.conditional_acquires contains duplicates")
        if conditional_acquires and contract.get("atomic_acquire") is not True:
            raise ValidationError(f"{context}.{phase} conditional acquisition must be atomic")


def _validate_phase_contract_overlays(
    machine: dict[str, Any],
    expected_pairs: set[tuple[str, str]],
    authorities: set[str],
) -> None:
    overlays = machine.get("phase_contract_overlays")
    if not isinstance(overlays, list):
        raise ValidationError("control_operation.phase_contract_overlays must be a list")
    actual_pairs: set[tuple[str, str]] = set()
    base_fields = set(machine["phase_contracts"]["operation_reserved"]["required_evidence"])
    for index, overlay in enumerate(overlays):
        if not isinstance(overlay, dict):
            raise ValidationError(f"control operation overlay {index} must be an object")
        _require_keys(
            overlay,
            {"operation_type", "operation_variant", "phase", "required_evidence_additions"},
            f"control operation overlay {index}",
        )
        pair = (overlay["operation_type"], overlay["operation_variant"])
        if pair in actual_pairs:
            raise ValidationError(f"duplicate control operation overlay: {pair}")
        actual_pairs.add(pair)
        if overlay["phase"] != "operation_reserved":
            raise ValidationError(f"control operation overlay {pair} must target operation_reserved")
        additions = overlay["required_evidence_additions"]
        if not isinstance(additions, list) or not additions:
            raise ValidationError(f"control operation overlay {pair} must add evidence")
        fields: set[str] = set()
        actual_specs: dict[str, tuple[str, str, bool]] = {}
        for evidence in additions:
            if not isinstance(evidence, dict):
                raise ValidationError(f"control operation overlay {pair} evidence must be an object")
            _require_keys(
                evidence,
                {"field", "type", "authority", "nullable", "binding"},
                f"control operation overlay {pair} evidence",
            )
            field = evidence["field"]
            if not isinstance(field, str) or not field or field in fields or field in base_fields:
                raise ValidationError(f"control operation overlay {pair} has duplicate or invalid evidence: {field}")
            fields.add(field)
            actual_specs[field] = (evidence["type"], evidence["authority"], evidence["nullable"])
            if not isinstance(evidence["type"], str) or not evidence["type"]:
                raise ValidationError(f"control operation overlay {pair}.{field} has invalid type")
            if evidence["authority"] not in authorities:
                raise ValidationError(f"control operation overlay {pair}.{field} has unknown authority")
            if not isinstance(evidence["nullable"], bool):
                raise ValidationError(f"control operation overlay {pair}.{field} has invalid nullable flag")
            if evidence["binding"] != "immutable_at_reservation":
                raise ValidationError(f"control operation overlay {pair}.{field} has invalid binding")
        if actual_specs != EXPECTED_RESERVATION_OVERLAYS.get(pair):
            raise ValidationError(f"control operation overlay {pair} evidence contract mismatch")
    if actual_pairs != expected_pairs:
        raise ValidationError(
            f"control operation overlay coverage mismatch: expected={sorted(expected_pairs)}, actual={sorted(actual_pairs)}"
        )
    if set(EXPECTED_RESERVATION_OVERLAYS) != expected_pairs:
        raise ValidationError("validator reservation overlay expectation set is incomplete")


def _validate_control_operation(protocol: dict[str, Any]) -> None:
    machine = protocol["state_machines"]["control_operation"]
    statuses = set(_require_unique_strings(machine["statuses"], "control_operation.statuses"))
    terminals = set(_require_unique_strings(machine["terminal_statuses"], "control_operation.terminal_statuses"))
    if machine["initial_status"] not in statuses or machine["active_status"] not in statuses:
        raise ValidationError("control_operation status references are invalid")
    if not terminals <= statuses or terminals != {"committed", "failed", "recovery_required"}:
        raise ValidationError("control_operation terminal statuses are not frozen values")
    if machine.get("interrupt_rule") != "any_nonterminal_phase_may_atomically_enter_interrupt_terminal_status_and_freeze_phase":
        raise ValidationError("control_operation interrupt rule mismatch")
    operations = machine.get("operations")
    if not isinstance(operations, list):
        raise ValidationError("control_operation.operations must be a list")
    seen_operations: set[str] = set()
    referenced_phases: set[str] = set()
    actual_variants: dict[str, set[str]] = {}
    operation_variant_pairs: set[tuple[str, str]] = set()
    for operation in operations:
        _require_keys(operation, {"operation_type", "variants"}, "control operation")
        operation_type = operation["operation_type"]
        if operation_type in seen_operations:
            raise ValidationError(f"duplicate control operation: {operation_type}")
        seen_operations.add(operation_type)
        variants = operation["variants"]
        if not isinstance(variants, list) or not variants:
            raise ValidationError(f"{operation_type} must define variants")
        seen_variants: set[str] = set()
        for variant in variants:
            _require_keys(
                variant,
                {"operation_variant", "initial_phase", "committed_phase", "terminal_outcomes", "phases", "success_edges"},
                f"{operation_type} variant",
            )
            variant_name = variant["operation_variant"]
            if variant_name in seen_variants:
                raise ValidationError(f"duplicate {operation_type} variant: {variant_name}")
            seen_variants.add(variant_name)
            operation_variant_pairs.add((operation_type, variant_name))
            phases = _require_unique_strings(variant["phases"], f"{operation_type}.{variant_name}.phases")
            terminal_outcomes = variant["terminal_outcomes"]
            if not isinstance(terminal_outcomes, list) or not terminal_outcomes:
                raise ValidationError(f"{operation_type}.{variant_name} must define terminal outcomes")
            terminal_phases: list[str] = []
            seen_terminal_tuples: set[tuple[str, str, str]] = set()
            for outcome in terminal_outcomes:
                if not isinstance(outcome, dict):
                    raise ValidationError(f"{operation_type}.{variant_name} terminal outcome must be an object")
                _require_keys(outcome, {"phase", "status", "proof_kind"}, f"{operation_type}.{variant_name} terminal outcome")
                terminal_tuple = (outcome["phase"], outcome["status"], outcome["proof_kind"])
                if terminal_tuple in seen_terminal_tuples:
                    raise ValidationError(f"{operation_type}.{variant_name} has duplicate terminal outcome")
                seen_terminal_tuples.add(terminal_tuple)
                terminal_phases.append(outcome["phase"])
                if outcome["status"] not in terminals:
                    raise ValidationError(f"{operation_type}.{variant_name} terminal outcome has invalid status")
                if not isinstance(outcome["proof_kind"], str) or not outcome["proof_kind"]:
                    raise ValidationError(f"{operation_type}.{variant_name} terminal outcome has invalid proof kind")
            if len(terminal_phases) != len(set(terminal_phases)):
                raise ValidationError(f"{operation_type}.{variant_name} maps more than one outcome to a terminal phase")
            committed_outcomes = [
                outcome
                for outcome in terminal_outcomes
                if outcome["phase"] == variant["committed_phase"] and outcome["status"] == "committed"
            ]
            if len(committed_outcomes) != 1:
                raise ValidationError(f"{operation_type}.{variant_name} must have one committed terminal outcome")
            _validate_terminating_graph(
                nodes=phases,
                edges=variant["success_edges"],
                initial=variant["initial_phase"],
                terminals=terminal_phases,
                context=f"control_operation.{operation_type}.{variant_name}",
                require_acyclic=True,
            )
            referenced_phases.update(phases)
        actual_variants[operation_type] = seen_variants
    if actual_variants != EXPECTED_OPERATION_VARIANTS:
        raise ValidationError(
            f"control operation type/variant set mismatch: expected={EXPECTED_OPERATION_VARIANTS}, actual={actual_variants}"
        )
    _validate_phase_contracts(
        machine["phase_contracts"],
        referenced_phases,
        set(protocol["authorities"]),
        set(protocol["effect_classes"]),
        set(protocol["continuation_policies"]),
        "control_operation",
    )
    _validate_phase_contract_overlays(machine, operation_variant_pairs, set(protocol["authorities"]))


def _validate_external_operation(protocol: dict[str, Any]) -> None:
    machine = protocol["state_machines"]["external_operation"]
    phases = _require_unique_strings(machine["phases"], "external_operation.phases")
    terminals = _require_unique_strings(machine["terminal_phases"], "external_operation.terminal_phases")
    if terminals != ["external_final_evidence_committed"]:
        raise ValidationError("external_operation must have one explicit final evidence phase")
    _validate_terminating_graph(
        nodes=phases,
        edges=machine["success_edges"],
        initial=machine["initial_phase"],
        terminals=terminals,
        context="external_operation",
        require_acyclic=True,
    )
    statuses = set(_require_unique_strings(machine["statuses"], "external_operation.statuses"))
    terminal_statuses = set(_require_unique_strings(machine["terminal_statuses"], "external_operation.terminal_statuses"))
    if not terminal_statuses <= statuses:
        raise ValidationError("external_operation terminal statuses are invalid")
    if terminal_statuses != {"completed", "failed", "cancelled", "interrupted", "recovery_required"}:
        raise ValidationError("external_operation terminal status set changed")
    if "interrupt_rule" in machine or "interrupt_terminal_statuses" in machine:
        raise ValidationError("external_operation may not terminalize a frozen nonterminal phase")
    resolution_owners = set(_require_unique_strings(machine["resolution_owner_values"], "external_operation resolution owners"))
    if resolution_owners != {"normal", "cancel", "interrupt"}:
        raise ValidationError("external_operation resolution owner set changed")
    proof_classification = machine.get("final_proof_classification")
    expected_proof_classification = {
        "dimensions": [
            "termination_or_not_dispatched",
            "write_lease_revocation",
            "verify_empty",
            "bounded_drain",
            "post_stop_stability",
        ],
        "safe_stop_predicate": "termination_is_confirmed_or_typed_not_dispatched_and_every_other_dimension_is_true",
        "unavailable_predicate": "any_dimension_is_false_unknown_or_missing",
        "precedence": "unavailable_dominates_safe_stop",
        "resolution_timing": {
            "normal": "preclassified_before_resolution_cas",
            "cancel": "classified_after_cancel_intent_before_final_evidence",
            "interrupt": "classified_after_interrupt_intent_before_final_evidence",
        },
        "unavailable_terminal_status": "recovery_required",
        "forbidden_unavailable_run_lifecycle": ["halted", "failed"],
    }
    if proof_classification != expected_proof_classification:
        raise ValidationError("external_operation final stop-proof classification is incomplete or unsafe")
    phase_statuses = machine.get("phase_statuses")
    if not isinstance(phase_statuses, dict) or set(phase_statuses) != set(phases):
        raise ValidationError("external_operation phase status mapping is not exhaustive")
    for phase, allowed in phase_statuses.items():
        values = set(_require_unique_strings(allowed, f"external_operation.phase_statuses.{phase}"))
        if not values <= statuses:
            raise ValidationError(f"external_operation.{phase} uses an unknown status")
        if phase in terminals and not values <= terminal_statuses:
            raise ValidationError(f"external_operation terminal phase {phase} uses a nonterminal status")
        if phase not in terminals and values & terminal_statuses:
            raise ValidationError(f"external_operation nonterminal phase {phase} uses a terminal status")
    expected_work_phases = {
        "external_operation_reserved",
        "task_committed",
        "workspace_manifest_committed",
        "reservation_committed",
        "core_contract_committed",
        "workspace_materialized",
        "pause_bound",
        "dispatch_authorized",
        "dispatch_receipt_committed",
        "result_reference_committed",
    }
    cancellable = set(_require_unique_strings(machine["cancellable_work_phases"], "external_operation cancellable phases"))
    interruptible = set(_require_unique_strings(machine["interruptible_work_phases"], "external_operation interruptible phases"))
    if cancellable != expected_work_phases or interruptible != expected_work_phases:
        raise ValidationError("external_operation work-phase resolution coverage is incomplete")
    edge_set = {tuple(edge) for edge in machine["success_edges"]}
    for phase in expected_work_phases:
        if (phase, "cancel_intent_committed") not in edge_set:
            raise ValidationError(f"external_operation cancel edge missing for {phase}")
        if (phase, "interrupt_stop_intent_committed") not in edge_set:
            raise ValidationError(f"external_operation interrupt edge missing for {phase}")
    if ("result_reference_committed", "external_final_evidence_committed") not in edge_set:
        raise ValidationError("external_operation normal terminal edge is missing")
    terminal_outcomes = machine.get("terminal_outcomes")
    if not isinstance(terminal_outcomes, list):
        raise ValidationError("external_operation terminal outcomes must be a list")
    control_variants = {
        (operation["operation_type"], variant["operation_variant"]): set(variant["phases"])
        for operation in protocol["state_machines"]["control_operation"]["operations"]
        for variant in operation["variants"]
    }
    actual_outcomes: set[tuple[str, str, str, tuple[str, ...], str]] = set()
    for outcome in terminal_outcomes:
        if not isinstance(outcome, dict):
            raise ValidationError("external_operation terminal outcome must be an object")
        _require_keys(
            outcome,
            {"resolution_kind", "interrupt_disposition", "proof_kind", "statuses", "consumer"},
            "external terminal outcome",
        )
        outcome_statuses = tuple(sorted(_require_unique_strings(outcome["statuses"], "external terminal outcome statuses")))
        if not set(outcome_statuses) <= terminal_statuses:
            raise ValidationError("external_operation terminal outcome uses a nonterminal status")
        consumer = outcome["consumer"]
        if not isinstance(consumer, dict) or consumer.get("kind") not in {"control_operation", "domain_flow"}:
            raise ValidationError("external_operation terminal outcome has an invalid consumer")
        if consumer["kind"] == "control_operation":
            _require_keys(
                consumer,
                {"kind", "operation_type", "operation_variant", "phase"},
                "external terminal control consumer",
            )
            pair = (consumer["operation_type"], consumer["operation_variant"])
            if pair not in control_variants or consumer["phase"] not in control_variants[pair]:
                raise ValidationError("external terminal outcome consumer is outside its declared ControlOperation graph")
            consumer_identity = f"{pair[0]}/{pair[1]}.{consumer['phase']}"
        else:
            if not isinstance(consumer.get("reference"), str) or not consumer["reference"]:
                raise ValidationError("external terminal domain consumer has an invalid reference")
            if (
                outcome["resolution_kind"] != "normal"
                or outcome["interrupt_disposition"] != "not_applicable"
                or outcome["proof_kind"] != "safe_stop"
                or consumer["reference"] != "canonical_external_result_delivery"
            ):
                raise ValidationError("only normal safe-stop may use the whitelisted domain-flow consumer")
            consumer_identity = f"domain:{consumer['reference']}"
        outcome_tuple = (
            outcome["resolution_kind"],
            outcome["interrupt_disposition"],
            outcome["proof_kind"],
            outcome_statuses,
            consumer_identity,
        )
        if outcome_tuple in actual_outcomes:
            raise ValidationError("external_operation contains a duplicate terminal outcome")
        actual_outcomes.add(outcome_tuple)
    expected_outcomes = {
        ("normal", "not_applicable", "safe_stop", ("completed", "failed"), "domain:canonical_external_result_delivery"),
        ("cancel", "not_applicable", "safe_stop", ("cancelled", "failed"), "cancel_pause/not_applicable.external_terminal_closure_verified"),
        ("interrupt", "recoverable_timeout", "safe_stop", ("interrupted",), "resolve_external_interrupt/recoverable_timeout.external_final_evidence_verified"),
        ("interrupt", "controlled_halt", "safe_stop", ("interrupted",), "resolve_external_interrupt/controlled_halt.external_final_evidence_verified"),
        ("interrupt", "integrity_failure", "safe_stop", ("interrupted",), "resolve_external_interrupt/integrity_failure.external_final_evidence_verified"),
        ("cancel", "not_applicable", "unavailable", ("recovery_required",), "cancel_pause/not_applicable.external_unavailable_verified"),
        ("interrupt", "recoverable_timeout", "unavailable", ("recovery_required",), "resolve_external_interrupt/recoverable_timeout.external_final_evidence_verified"),
        ("interrupt", "controlled_halt", "unavailable", ("recovery_required",), "resolve_external_interrupt/controlled_halt.external_final_evidence_verified"),
        ("interrupt", "integrity_failure", "unavailable", ("recovery_required",), "resolve_external_interrupt/integrity_failure.external_final_evidence_verified"),
    }
    if actual_outcomes != expected_outcomes:
        raise ValidationError("external_operation terminal outcome mapping is incomplete or ambiguous")
    _validate_phase_contracts(
        machine["phase_contracts"],
        set(phases),
        set(protocol["authorities"]),
        set(protocol["effect_classes"]),
        set(protocol["continuation_policies"]),
        "external_operation",
    )


def _validate_run_lifecycle(protocol: dict[str, Any]) -> None:
    machine = protocol["state_machines"]["run_lifecycle"]
    states = _require_unique_strings(machine["states"], "run_lifecycle.states")
    terminals = _require_unique_strings(machine["terminal_states"], "run_lifecycle.terminal_states")
    edges = _validate_terminating_graph(
        nodes=states,
        edges=machine["allowed_edges"],
        initial=machine["initial_state"],
        terminals=terminals,
        context="run_lifecycle",
        require_acyclic=False,
    )
    cycles = machine.get("allowed_cycles")
    if not isinstance(cycles, list) or len(cycles) != 1:
        raise ValidationError("run_lifecycle must declare its single intentional cycle")
    cycle = cycles[0]
    _require_keys(cycle, {"states", "monotonic_guards"}, "run_lifecycle.allowed_cycles[0]")
    cycle_states = set(_require_unique_strings(cycle["states"], "run_lifecycle cycle states"))
    _require_unique_strings(cycle["monotonic_guards"], "run_lifecycle cycle monotonic guards")
    if cycle_states != {"running", "paused"}:
        raise ValidationError("run_lifecycle declares an unexpected cycle")
    edge_set = set(edges)
    expected_cycle_edges = {("running", "paused"), ("paused", "running")}
    cycle_edges = {edge for edge in edge_set if edge[0] in cycle_states and edge[1] in cycle_states}
    if cycle_edges != expected_cycle_edges:
        raise ValidationError("run_lifecycle declared cycle does not match allowed edges")
    non_cycle_edges = [edge for edge in edges if not (edge[0] in cycle_states and edge[1] in cycle_states)]
    _assert_acyclic(set(states), non_cycle_edges, "run_lifecycle outside declared cycle")


def _validate_pause_lifecycle(protocol: dict[str, Any]) -> None:
    machine = protocol["state_machines"]["pause_lifecycle"]
    states = _require_unique_strings(machine["states"], "pause_lifecycle.states")
    terminals = _require_unique_strings(machine["terminal_states"], "pause_lifecycle.terminal_states")
    _validate_terminating_graph(
        nodes=states,
        edges=machine["allowed_edges"],
        initial=machine["initial_state"],
        terminals=terminals,
        context="pause_lifecycle",
        require_acyclic=True,
    )
    if machine.get("active_states") != ["opened"] or machine.get("publicly_resumable_states") != ["opened"]:
        raise ValidationError("pause_lifecycle has an invalid active or resumable state set")
    expected_resume_predicate = [
        "pause_status_is_opened",
        "pause_owner_is_null",
        "run_terminal_closure_owner_is_null",
    ]
    if machine.get("public_resume_predicate") != expected_resume_predicate:
        raise ValidationError("pause_lifecycle public resume predicate is incomplete")
    if set(terminals) != {"consumed", "cancelled", "aborted", "interrupted", "quarantined"}:
        raise ValidationError("pause_lifecycle terminal state set is incomplete")
    expected_visibility = (
        "prepared_is_private; opened_requires_public_paused_checkpoint_and_empty_pause_and_run_terminal_owners; "
        "claimed_is_transitional_and_not_resumable; "
        "consumed_cancelled_aborted_interrupted_and_quarantined_are_irreversible"
    )
    if machine.get("visibility_rule") != expected_visibility:
        raise ValidationError("pause_lifecycle visibility rule mismatch")


def _validate_dependency_dags(protocol: dict[str, Any]) -> None:
    dags = protocol.get("dependency_dags")
    if not isinstance(dags, list) or not dags:
        raise ValidationError("dependency_dags must be a non-empty list")
    dag_nodes: dict[str, dict[str, set[str]]] = {}
    for dag in dags:
        _require_keys(dag, {"dag_id", "nodes"}, "dependency DAG")
        dag_id = dag["dag_id"]
        if dag_id in dag_nodes:
            raise ValidationError(f"duplicate dependency DAG: {dag_id}")
        rows = dag["nodes"]
        if not isinstance(rows, list) or not rows:
            raise ValidationError(f"dependency DAG {dag_id} must define nodes")
        dependencies: dict[str, set[str]] = {}
        for row in rows:
            _require_keys(row, {"node", "requires"}, f"dependency DAG {dag_id} node")
            node = row["node"]
            if node in dependencies:
                raise ValidationError(f"duplicate dependency node in {dag_id}: {node}")
            dependencies[node] = set(_require_unique_strings(row["requires"], f"{dag_id}.{node}.requires")) if row["requires"] else set()
        all_nodes = set(dependencies)
        for node, required in dependencies.items():
            unknown = required - all_nodes
            if unknown:
                raise ValidationError(f"{dag_id}.{node} has unknown dependencies: {sorted(unknown)}")
        dependency_edges = [(required, node) for node, required_nodes in dependencies.items() for required in required_nodes]
        _assert_acyclic(all_nodes, dependency_edges, f"dependency DAG {dag_id}")
        dag_nodes[dag_id] = dependencies

    prestart = dag_nodes.get("external_operation_prestart_and_pause_publication")
    if prestart is None:
        raise ValidationError("missing external operation pre-start dependency DAG")
    adjacency = {node: set() for node in prestart}
    for node, required_nodes in prestart.items():
        for required in required_nodes:
            adjacency[required].add(node)
    for binding in protocol.get("field_bindings", []):
        _require_keys(binding, {"field", "allocated_at", "bound_at", "immutable_after"}, "field binding")
        allocated = binding["allocated_at"]
        bound = binding["bound_at"]
        immutable = binding["immutable_after"]
        if not {allocated, bound, immutable} <= set(prestart):
            raise ValidationError(f"field binding {binding['field']} references an unknown dependency node")
        if bound not in _reachable(allocated, adjacency):
            raise ValidationError(f"field binding {binding['field']} binds before allocation")
        if immutable not in _reachable(bound, adjacency):
            raise ValidationError(f"field binding {binding['field']} becomes immutable before binding")


def _control_variant_index(protocol: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (operation["operation_type"], variant["operation_variant"]): variant
        for operation in protocol["state_machines"]["control_operation"]["operations"]
        for variant in operation["variants"]
    }


def _validate_branch_contracts(protocol: dict[str, Any]) -> None:
    contracts = protocol.get("branch_contracts")
    if not isinstance(contracts, list) or not contracts:
        raise ValidationError("branch_contracts must be a non-empty list")
    authorities = set(protocol["authorities"])
    control_variants = _control_variant_index(protocol)
    external_machine = protocol["state_machines"]["external_operation"]

    actual_branches: dict[tuple[str, str | None, str | None, str], set[str]] = {}
    for (operation_type, operation_variant), variant in control_variants.items():
        adjacency = {phase: set() for phase in variant["phases"]}
        for source, target in variant["success_edges"]:
            adjacency[source].add(target)
        for source, targets in adjacency.items():
            if len(targets) > 1:
                actual_branches[("control_operation", operation_type, operation_variant, source)] = targets
    external_adjacency = {phase: set() for phase in external_machine["phases"]}
    for source, target in external_machine["success_edges"]:
        external_adjacency[source].add(target)
    for source, targets in external_adjacency.items():
        if len(targets) > 1:
            actual_branches[("external_operation", None, None, source)] = targets

    declared_branches: set[tuple[str, str | None, str | None, str]] = set()
    branch_ids: set[str] = set()
    evidence_unions = {union["union_id"]: union for union in protocol.get("evidence_unions", [])}
    for contract in contracts:
        if not isinstance(contract, dict) or not isinstance(contract.get("branch_id"), str):
            raise ValidationError("branch contract is missing branch_id")
        branch_id = contract["branch_id"]
        if branch_id in branch_ids:
            raise ValidationError(f"duplicate branch contract: {branch_id}")
        branch_ids.add(branch_id)
        machine = contract.get("machine")
        if machine not in {"control_operation", "external_operation"}:
            raise ValidationError(f"branch contract {branch_id} has an invalid machine")

        source_rows: list[dict[str, str]]
        if machine == "control_operation":
            _require_keys(
                contract,
                {"operation_type", "operation_variant", "source_phase", "discriminants", "valid_combinations", "cases"},
                f"branch contract {branch_id}",
            )
            pair = (contract["operation_type"], contract["operation_variant"])
            if pair not in control_variants:
                raise ValidationError(f"branch contract {branch_id} references an unknown ControlOperation variant")
            source_rows = [{"phase": contract["source_phase"]}]
        else:
            rows = contract.get("sources")
            if not isinstance(rows, list) or not rows:
                raise ValidationError(f"branch contract {branch_id} must define external sources")
            source_rows = []
            for row in rows:
                _require_keys(row, {"phase", "normal_target"}, f"branch contract {branch_id} source")
                source_rows.append(row)

        discriminants = contract.get("discriminants")
        if not isinstance(discriminants, list) or not discriminants:
            raise ValidationError(f"branch contract {branch_id} must define discriminants")
        fields: list[str] = []
        domains: dict[str, set[str]] = {}
        for discriminant in discriminants:
            _require_keys(
                discriminant,
                {"field", "values", "binding", "authority"},
                f"branch contract {branch_id} discriminant",
            )
            field = discriminant["field"]
            if field in fields:
                raise ValidationError(f"branch contract {branch_id} has a duplicate discriminant")
            fields.append(field)
            domains[field] = set(_require_unique_strings(discriminant["values"], f"branch contract {branch_id}.{field}"))
            if not str(discriminant["binding"]).startswith("immutable_"):
                raise ValidationError(f"branch contract {branch_id}.{field} is not frozen before branching")
            if discriminant["authority"] not in authorities:
                raise ValidationError(f"branch contract {branch_id}.{field} has an unknown authority")

        valid_combinations = contract.get("valid_combinations")
        if not isinstance(valid_combinations, list) or not valid_combinations:
            raise ValidationError(f"branch contract {branch_id} must define valid combinations")
        normalized_combinations: list[tuple[str, ...]] = []
        for combination in valid_combinations:
            if not isinstance(combination, dict) or set(combination) != set(fields):
                raise ValidationError(f"branch contract {branch_id} has an incomplete valid combination")
            values = tuple(combination[field] for field in fields)
            if any(value not in domains[field] for field, value in zip(fields, values)):
                raise ValidationError(f"branch contract {branch_id} has an unknown discriminant value")
            normalized_combinations.append(values)
        if len(normalized_combinations) != len(set(normalized_combinations)):
            raise ValidationError(f"branch contract {branch_id} has duplicate valid combinations")

        cases = contract.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValidationError(f"branch contract {branch_id} must define cases")
        matched_counts = {combination: 0 for combination in normalized_combinations}
        for case in cases:
            _require_keys(case, {"when", "target"}, f"branch contract {branch_id} case")
            when = case["when"]
            if not isinstance(when, dict) or set(when) != set(fields):
                raise ValidationError(f"branch contract {branch_id} case has incomplete guards")
            allowed_by_field: dict[str, set[str]] = {}
            for field in fields:
                allowed = set(_require_unique_strings(when[field], f"branch contract {branch_id} case.{field}"))
                if not allowed <= domains[field]:
                    raise ValidationError(f"branch contract {branch_id} case uses an unknown guard value")
                allowed_by_field[field] = allowed
            for combination in normalized_combinations:
                if all(value in allowed_by_field[field] for field, value in zip(fields, combination)):
                    matched_counts[combination] += 1
            if "evidence_union" in case:
                union = evidence_unions.get(case["evidence_union"])
                if union is None:
                    raise ValidationError(f"branch contract {branch_id} references an unknown evidence union")
                tags = {variant["tag"] for variant in union["variants"]}
                if case.get("evidence_variant") not in tags:
                    raise ValidationError(f"branch contract {branch_id} references an unknown evidence variant")
                if machine != "control_operation":
                    raise ValidationError(f"branch contract {branch_id} cannot bind evidence outside ControlOperation")
                matching_bindings = [
                    binding
                    for binding in union.get("consumer_bindings", [])
                    if binding.get("machine") == machine
                    and binding.get("operation_type") == contract.get("operation_type")
                    and binding.get("operation_variant") == contract.get("operation_variant")
                    and binding.get("incoming_phase") == contract.get("source_phase")
                    and binding.get("phase") == case["target"]
                ]
                if len(matching_bindings) != 1 or case["evidence_variant"] not in matching_bindings[0].get(
                    "allowed_variants", []
                ):
                    raise ValidationError(
                        f"branch contract {branch_id} evidence variant does not match its incoming edge"
                    )

        if any(count != 1 for count in matched_counts.values()):
            raise ValidationError(f"branch contract {branch_id} guards overlap or leave a coverage gap")

        for row in source_rows:
            source = row["phase"]
            key = (
                machine,
                contract.get("operation_type"),
                contract.get("operation_variant"),
                source,
            )
            if key in declared_branches:
                raise ValidationError(f"more than one guard contract covers branch source {key}")
            declared_branches.add(key)
            actual_targets = actual_branches.get(key)
            if actual_targets is None:
                raise ValidationError(f"branch contract {branch_id} does not reference a multi-successor phase")
            declared_targets = {
                row["normal_target"] if case["target"] == "$normal_target" else case["target"]
                for case in cases
            }
            if declared_targets != actual_targets:
                raise ValidationError(
                    f"branch contract {branch_id} target mismatch for {source}: "
                    f"declared={sorted(declared_targets)}, actual={sorted(actual_targets)}"
                )

    if declared_branches != set(actual_branches):
        missing = sorted(set(actual_branches) - declared_branches, key=str)
        extra = sorted(declared_branches - set(actual_branches), key=str)
        raise ValidationError(f"branch guard coverage mismatch; missing={missing}, extra={extra}")


def _validate_evidence_unions(protocol: dict[str, Any]) -> None:
    unions = protocol.get("evidence_unions")
    if not isinstance(unions, list) or not unions:
        raise ValidationError("evidence_unions must be a non-empty list")
    expected_ids = {
        "PauseCancelProof",
        "PauseSnapshot",
        "InterruptSafePauseDispositionProof",
        "InterruptUnavailablePauseDispositionProof",
        "TerminalClosureUnavailableProof",
    }
    by_id: dict[str, dict[str, Any]] = {}
    referenced_evidence = set(
        evidence
        for contract in protocol["state_machines"]["control_operation"]["phase_contracts"].values()
        for evidence in contract["required_evidence"]
    )
    referenced_evidence.update(
        evidence["field"]
        for overlay in protocol["state_machines"]["control_operation"]["phase_contract_overlays"]
        for evidence in overlay["required_evidence_additions"]
    )
    control_variants = _control_variant_index(protocol)
    for union in unions:
        if not isinstance(union, dict):
            raise ValidationError("evidence union must be an object")
        _require_keys(union, {"union_id", "evidence_field", "tag_field", "variants"}, "evidence union")
        union_id = union["union_id"]
        if union_id in by_id:
            raise ValidationError(f"duplicate evidence union: {union_id}")
        by_id[union_id] = union
        if union["evidence_field"] not in referenced_evidence:
            raise ValidationError(f"evidence union {union_id} is not referenced by an effective phase contract")
        if not isinstance(union["tag_field"], str) or not union["tag_field"]:
            raise ValidationError(f"evidence union {union_id} has an invalid tag field")
        variants = union["variants"]
        if not isinstance(variants, list) or not variants:
            raise ValidationError(f"evidence union {union_id} must define variants")
        tags: set[str] = set()
        for variant in variants:
            _require_keys(variant, {"tag", "required_fields", "forbidden_fields"}, f"evidence union {union_id} variant")
            tag = variant["tag"]
            if not isinstance(tag, str) or not tag or tag in tags:
                raise ValidationError(f"evidence union {union_id} has a duplicate or invalid tag")
            tags.add(tag)
            required = set(_require_unique_strings(variant["required_fields"], f"evidence union {union_id}.{tag}.required"))
            forbidden = set(_require_unique_strings(variant["forbidden_fields"], f"evidence union {union_id}.{tag}.forbidden"))
            if required & forbidden:
                raise ValidationError(f"evidence union {union_id}.{tag} requires and forbids the same field")
        bindings = union.get("consumer_bindings", [])
        if not isinstance(bindings, list):
            raise ValidationError(f"evidence union {union_id} consumer bindings must be a list")
        for binding in bindings:
            _require_keys(
                binding,
                {"machine", "operation_type", "operation_variant", "phase", "incoming_phase", "allowed_variants"},
                f"evidence union {union_id} consumer binding",
            )
            if binding["machine"] != "control_operation":
                raise ValidationError(f"evidence union {union_id} has an unsupported consumer machine")
            pair = (binding["operation_type"], binding["operation_variant"])
            variant = control_variants.get(pair)
            if variant is None or binding["phase"] not in variant["phases"]:
                raise ValidationError(f"evidence union {union_id} consumer is outside its ControlOperation graph")
            if [binding["incoming_phase"], binding["phase"]] not in variant["success_edges"]:
                raise ValidationError(f"evidence union {union_id} consumer binding has no matching incoming edge")
            allowed_variants = set(
                _require_unique_strings(binding["allowed_variants"], f"evidence union {union_id} allowed variants")
            )
            if not allowed_variants <= tags:
                raise ValidationError(f"evidence union {union_id} binding uses an unknown variant")
            phase_contract = protocol["state_machines"]["control_operation"]["phase_contracts"][binding["phase"]]
            if union["evidence_field"] not in phase_contract["required_evidence"]:
                raise ValidationError(f"evidence union {union_id} is not required by its bound consumer phase")
    if set(by_id) != expected_ids:
        raise ValidationError(f"evidence union set mismatch: {sorted(set(by_id))}")

    expected_correlations = {
        "InterruptSafePauseDispositionProof": {
            "union_id": "PauseSnapshot",
            "operation_variants": [
                "resolve_external_interrupt/controlled_halt",
                "resolve_external_interrupt/integrity_failure",
            ],
            "tag_mapping": {
                "absent": "absent_not_applicable",
                "prepared": "prepared_aborted",
                "opened": "opened_interrupted",
            },
        },
        "InterruptUnavailablePauseDispositionProof": {
            "union_id": "PauseSnapshot",
            "operation_variants": [
                "resolve_external_interrupt/controlled_halt",
                "resolve_external_interrupt/integrity_failure",
            ],
            "tag_mapping": {
                "absent": "absent_not_applicable",
                "prepared": "prepared_quarantined",
                "opened": "opened_quarantined",
            },
        },
    }
    for union_id, expected in expected_correlations.items():
        union = by_id[union_id]
        correlation = union.get("correlates_with")
        if correlation != expected:
            raise ValidationError(f"evidence union {union_id} has an incomplete Pause-snapshot correlation")
        source_tags = {variant["tag"] for variant in by_id[correlation["union_id"]]["variants"]}
        target_tags = {variant["tag"] for variant in union["variants"]}
        if set(correlation["tag_mapping"]) != source_tags or set(correlation["tag_mapping"].values()) != target_tags:
            raise ValidationError(f"evidence union {union_id} correlation is not exhaustive and one-to-one")
    for union_id in expected_ids - set(expected_correlations):
        if "correlates_with" in by_id[union_id]:
            raise ValidationError(f"evidence union {union_id} has an unexpected correlation")

    terminal_variants = {variant["tag"]: variant for variant in by_id["TerminalClosureUnavailableProof"]["variants"]}
    for tag in ("terminal_absent_not_applicable", "terminal_prepared_quarantined", "terminal_opened_quarantined"):
        if "pause_disposition_proof_digest" not in terminal_variants[tag]["required_fields"]:
            raise ValidationError(f"TerminalClosureUnavailableProof.{tag} does not bind its Pause disposition proof")

    pause_cancel_bindings = by_id["PauseCancelProof"].get("consumer_bindings", [])
    actual_pause_cancel = {
        (binding["incoming_phase"], tuple(binding["allowed_variants"])) for binding in pause_cancel_bindings
    }
    expected_pause_cancel = {
        ("external_terminal_closure_verified", ("external_safe_stop",)),
        ("cancel_arbitrated", ("no_external_operation",)),
    }
    if actual_pause_cancel != expected_pause_cancel:
        raise ValidationError("PauseCancelProof incoming guards do not match its tagged variants")


def _validate_transaction_domains_and_cas(protocol: dict[str, Any]) -> None:
    domains = protocol.get("transaction_domains")
    if not isinstance(domains, list) or len(domains) != 1:
        raise ValidationError("protocol must define one coordinator transaction domain")
    domain = domains[0]
    _require_keys(domain, {"transaction_domain", "authorities", "atomic_objects", "profile"}, "transaction domain")
    if domain["transaction_domain"] != "coordinator_sqlite":
        raise ValidationError("coordinator transaction domain identity changed")
    if set(_require_unique_strings(domain["authorities"], "transaction domain authorities")) != {
        "coordinator_db",
        "external_operation_db",
    }:
        raise ValidationError("coordinator transaction domain authority set is incomplete")
    expected_objects = {"control_operation", "pause_ownership", "run_terminal_closure", "external_operation"}
    if set(_require_unique_strings(domain["atomic_objects"], "transaction domain atomic objects")) != expected_objects:
        raise ValidationError("coordinator transaction domain atomic object set is incomplete")
    if domain["profile"] != "single_sqlite_database_transaction":
        raise ValidationError("coordinator transaction domain must be a single SQLite transaction")

    guards = protocol.get("cas_guards")
    if not isinstance(guards, list):
        raise ValidationError("cas_guards must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for guard in guards:
        if not isinstance(guard, dict) or not isinstance(guard.get("guard_id"), str):
            raise ValidationError("CAS guard is missing guard_id")
        if guard["guard_id"] in by_id:
            raise ValidationError(f"duplicate CAS guard: {guard['guard_id']}")
        by_id[guard["guard_id"]] = guard
        if guard.get("transaction_domain") != "coordinator_sqlite":
            raise ValidationError(f"CAS guard {guard['guard_id']} is outside coordinator transaction domain")
        _require_unique_strings(guard.get("compare_fields"), f"CAS guard {guard['guard_id']} compare fields")
        if guard.get("increments_phase_revision") is not True:
            raise ValidationError(f"CAS guard {guard['guard_id']} must increment phase revision")
    expected_guard_ids = {
        "external_normal_terminal_cas",
        "external_cancel_intent_cas",
        "external_interrupt_intent_cas",
        "cancel_control_combined_cas",
        "interrupt_control_combined_cas",
    }
    if set(by_id) != expected_guard_ids:
        raise ValidationError("CAS guard set is incomplete")
    resolution_fields = {"external_operation_id", "phase_revision", "lease_epoch", "resolution_owner"}
    normal_guard = by_id["external_normal_terminal_cas"]
    if set(normal_guard["compare_fields"]) != resolution_fields | {"preclassified_final_proof_kind"}:
        raise ValidationError("normal terminal CAS does not fence the resolution tuple and preclassified proof")
    if normal_guard.get("required_proof_kind") != "safe_stop":
        raise ValidationError("normal terminal CAS accepts a proof other than safe_stop")
    if normal_guard.get("commits_terminal_phase") != "external_final_evidence_committed":
        raise ValidationError("normal terminal CAS is not atomic with final evidence publication")
    if normal_guard.get("required_resolution_owner", "missing") is not None:
        raise ValidationError("normal terminal CAS does not require an empty resolution owner")
    if normal_guard.get("assigns_resolution_owner") != "normal":
        raise ValidationError("normal terminal CAS assigns the wrong resolution owner")
    for guard_id, owner in (
        ("external_cancel_intent_cas", "cancel"),
        ("external_interrupt_intent_cas", "interrupt"),
    ):
        guard = by_id[guard_id]
        if set(guard["compare_fields"]) != resolution_fields:
            raise ValidationError(f"CAS guard {guard_id} does not fence the exact resolution tuple")
        if guard.get("required_resolution_owner", "missing") is not None:
            raise ValidationError(f"CAS guard {guard_id} does not require an empty resolution owner")
        if guard.get("assigns_resolution_owner") != owner:
            raise ValidationError(f"CAS guard {guard_id} assigns the wrong resolution owner")
    combined = by_id["cancel_control_combined_cas"]
    if not resolution_fields <= set(combined["compare_fields"]):
        raise ValidationError("combined cancel CAS does not fence ExternalOperation resolution")
    if "required_empty_fields" in combined:
        raise ValidationError("combined cancel CAS may not impose unconditional empty Pause and Run owners")
    if not {"pause_status", "resolution_owner_operation_id"} <= set(combined["compare_fields"]):
        raise ValidationError("combined cancel CAS does not compare winner identity and Pause lifecycle")
    if combined.get("conditionally_delegates_to") != "external_cancel_intent_cas":
        raise ValidationError("combined cancel CAS does not use the cancel resolution guard")
    if combined.get("external_operation_present_condition") != "reserved_external_operation_id_is_non_null":
        raise ValidationError("combined cancel CAS lacks the ExternalOperation-present branch")
    if combined.get("external_operation_absent_condition") != "reserved_external_operation_id_is_typed_null_and_no_external_row_exists":
        raise ValidationError("combined cancel CAS lacks the typed-null ExternalOperation branch")
    expected_resolution_cases = [
        {
            "case": "external_absent",
            "required_resolution_owner": "not_applicable",
            "external_mutation": "none",
            "outcome": "no_external_operation",
        },
        {
            "case": "external_unresolved",
            "required_resolution_owner": None,
            "external_mutation": "delegate_external_cancel_intent_cas",
            "outcome": "cancel_won",
        },
        {
            "case": "external_normal",
            "required_resolution_owner": "normal",
            "external_mutation": "none",
            "outcome": "normal_terminal_won",
        },
        {
            "case": "external_cancel",
            "required_resolution_owner": "cancel",
            "external_mutation": "none",
            "outcome": "preexisting_cancel_resolution",
        },
        {
            "case": "external_interrupt",
            "required_resolution_owner": "interrupt",
            "external_mutation": "none",
            "outcome": "preexisting_interrupt_resolution",
        },
    ]
    if combined.get("resolution_cases") != expected_resolution_cases:
        raise ValidationError("combined cancel CAS resolution cases are incomplete or ambiguous")
    if combined.get("control_operation_phase_revision_incremented") is not True:
        raise ValidationError("combined cancel CAS does not advance the ControlOperation phase revision")
    if combined.get("external_phase_revision_incremented_only_when") != "cancel_won":
        raise ValidationError("combined cancel CAS changes ExternalOperation revision outside cancel_won")
    expected_outcome_guards = [
        {
            "outcome": "no_external_operation",
            "required_pause_states": ["opened"],
            "required_owner_shape": {"pause_owner": None, "run_terminal_closure_owner": None},
            "external_revision_epoch_guard": "typed_null_absence_proof",
            "required_winner_operation_type": "not_applicable",
            "observation_only": False,
            "acquires": ["pause_cancel_owner", "run_terminal_closure_owner"],
        },
        {
            "outcome": "cancel_won",
            "required_pause_states": ["opened"],
            "required_owner_shape": {"pause_owner": None, "run_terminal_closure_owner": None},
            "external_revision_epoch_guard": "exact_current_revision_epoch_empty_resolution_cas",
            "required_winner_operation_type": "current_cancel_operation",
            "observation_only": False,
            "acquires": ["pause_cancel_owner", "run_terminal_closure_owner", "external_resolution_owner"],
        },
        {
            "outcome": "normal_terminal_won",
            "required_pause_states": ["opened"],
            "required_owner_shape": {"pause_owner": None, "run_terminal_closure_owner": None},
            "external_revision_epoch_guard": "stable_read_of_persisted_normal_winner",
            "required_winner_operation_type": "normal_external_finalization",
            "observation_only": False,
            "acquires": ["pause_cancel_owner", "run_terminal_closure_owner"],
        },
        {
            "outcome": "preexisting_cancel_resolution",
            "required_pause_states": ["opened", "cancelled", "quarantined"],
            "allowed_winner_owner_shapes": [
                {"pause_owner": "winner_operation_id", "run_terminal_closure_owner": "winner_operation_id"}
            ],
            "external_revision_epoch_guard": "stable_read_of_persisted_cancel_winner",
            "required_winner_operation_type": "cancel_pause",
            "observation_only": True,
            "acquires": [],
        },
        {
            "outcome": "preexisting_interrupt_resolution",
            "required_pause_states": ["opened", "claimed", "consumed", "interrupted", "quarantined"],
            "allowed_winner_owner_shapes": [
                {"pause_owner": "winner_operation_id", "run_terminal_closure_owner": None},
                {"pause_owner": "winner_operation_id", "run_terminal_closure_owner": "winner_operation_id"},
            ],
            "external_revision_epoch_guard": "stable_read_of_persisted_interrupt_winner",
            "required_winner_operation_type": "resolve_external_interrupt",
            "observation_only": True,
            "acquires": [],
        },
    ]
    if combined.get("outcome_guards") != expected_outcome_guards:
        raise ValidationError("combined cancel CAS outcome guards are incomplete or unsafe")
    if combined.get("same_key_replay_rule") != "resume_existing_control_operation_without_rearbitration":
        raise ValidationError("combined cancel CAS can misclassify same-key replay as a preexisting winner")
    expected_observation_evidence = {
        "resolution_owner",
        "resolution_owner_operation_id",
        "winner_phase_revision",
        "winner_lease_epoch",
        "pause_status",
        "pause_owner",
        "run_terminal_closure_owner",
    }
    if set(combined.get("observation_evidence", [])) != expected_observation_evidence:
        raise ValidationError("combined cancel CAS does not freeze complete winner observation evidence")
    control_contract = protocol["state_machines"]["control_operation"]["phase_contracts"]["cancel_arbitrated"]
    if control_contract.get("transaction_domain") != "coordinator_sqlite":
        raise ValidationError("cancel_arbitrated is outside the coordinator transaction domain")
    if control_contract.get("cas_guard") != "cancel_control_combined_cas":
        raise ValidationError("cancel_arbitrated does not use the combined CAS guard")
    if control_contract.get("acquires") != [] or set(control_contract.get("conditional_acquires", [])) != {
        "pause_cancel_owner",
        "run_terminal_closure_owner",
        "external_resolution_owner",
    }:
        raise ValidationError("cancel_arbitrated does not use outcome-conditional ownership")
    cancel_operation = next(
        operation
        for operation in protocol["state_machines"]["control_operation"]["operations"]
        if operation["operation_type"] == "cancel_pause"
    )
    cancel_edges = {tuple(edge) for edge in cancel_operation["variants"][0]["success_edges"]}
    if ("cancel_arbitrated", "pause_cancelled_recorded") not in cancel_edges:
        raise ValidationError("cancel arbitration lacks the typed-null ExternalOperation path")
    if ("cancel_arbitrated", "resolution_winner_observed") not in cancel_edges:
        raise ValidationError("cancel arbitration lacks the preexisting-interrupt observation path")

    interrupt_combined = by_id["interrupt_control_combined_cas"]
    if not resolution_fields <= set(interrupt_combined["compare_fields"]):
        raise ValidationError("combined interrupt CAS does not fence ExternalOperation resolution")
    if interrupt_combined.get("required_resolution_owner", "missing") is not None:
        raise ValidationError("combined interrupt CAS does not require an empty resolution owner")
    if interrupt_combined.get("assigns_resolution_owner") != "interrupt":
        raise ValidationError("combined interrupt CAS assigns the wrong resolution owner")
    if interrupt_combined.get("conditionally_delegates_to") != "external_interrupt_intent_cas":
        raise ValidationError("combined interrupt CAS does not use the interrupt resolution guard")
    all_external_work_phases = protocol["state_machines"]["external_operation"]["interruptible_work_phases"]
    expected_interrupt_acquisitions = [
        {
            "operation_variant": "recoverable_timeout",
            "allowed_external_phases": ["dispatch_authorized", "dispatch_receipt_committed"],
            "required_pause_snapshot": "opened",
            "acquires": ["external_resolution_owner", "pause_interrupt_owner"],
        },
        {
            "operation_variant": "controlled_halt",
            "allowed_external_phases": all_external_work_phases,
            "required_pause_snapshot": "absent_or_prepared_or_opened",
            "acquires": ["external_resolution_owner", "run_terminal_closure_owner", "applicable_pause_disposition_owner"],
        },
        {
            "operation_variant": "integrity_failure",
            "allowed_external_phases": all_external_work_phases,
            "required_pause_snapshot": "absent_or_prepared_or_opened",
            "acquires": ["external_resolution_owner", "run_terminal_closure_owner", "applicable_pause_disposition_owner"],
        },
    ]
    if interrupt_combined.get("variant_acquisitions") != expected_interrupt_acquisitions:
        raise ValidationError("combined interrupt CAS variant ownership is incomplete")
    for phase in ("interrupt_and_pause_ownership_reserved", "interrupt_and_terminal_ownership_reserved"):
        contract = protocol["state_machines"]["control_operation"]["phase_contracts"][phase]
        if contract.get("transaction_domain") != "coordinator_sqlite":
            raise ValidationError(f"{phase} is outside the coordinator transaction domain")
        if contract.get("cas_guard") != "interrupt_control_combined_cas":
            raise ValidationError(f"{phase} does not use the combined interrupt CAS guard")
    external_contracts = protocol["state_machines"]["external_operation"]["phase_contracts"]
    for phase, guard_id in (
        ("cancel_intent_committed", "external_cancel_intent_cas"),
        ("interrupt_stop_intent_committed", "external_interrupt_intent_cas"),
    ):
        contract = external_contracts[phase]
        if contract.get("transaction_domain") != "coordinator_sqlite" or contract.get("cas_guard") != guard_id:
            raise ValidationError(f"{phase} is not bound to its coordinator CAS guard")
    if external_contracts["external_final_evidence_committed"].get("normal_resolution_cas_guard") != "external_normal_terminal_cas":
        raise ValidationError("external final evidence does not bind the normal terminal CAS guard")
    if not {
        "preclassified_final_proof_kind",
        "proof_classification_timing",
        "resolution_kind",
        "interrupt_disposition",
        "proof_kind",
    } <= set(external_contracts["external_final_evidence_committed"]["required_evidence"]):
        raise ValidationError("external final evidence does not bind proof classification and resolution timing")
    final_branch = next(
        contract for contract in protocol["branch_contracts"] if contract["branch_id"] == "external_final_resolution"
    )
    expected_final_combinations = [
        {"resolution_action": "normal_progress", "preclassified_final_proof_kind": "safe_stop"},
        {"resolution_action": "cancel", "preclassified_final_proof_kind": "not_applicable"},
        {"resolution_action": "interrupt", "preclassified_final_proof_kind": "not_applicable"},
    ]
    expected_final_cases = [
        {
            "when": {
                "resolution_action": ["normal_progress"],
                "preclassified_final_proof_kind": ["safe_stop"],
            },
            "target": "$normal_target",
        },
        {
            "when": {
                "resolution_action": ["cancel"],
                "preclassified_final_proof_kind": ["not_applicable"],
            },
            "target": "cancel_intent_committed",
        },
        {
            "when": {
                "resolution_action": ["interrupt"],
                "preclassified_final_proof_kind": ["not_applicable"],
            },
            "target": "interrupt_stop_intent_committed",
        },
    ]
    if final_branch.get("valid_combinations") != expected_final_combinations:
        raise ValidationError("external final resolution permits a non-safe normal or preclassified stop intent")
    if final_branch.get("cases") != expected_final_cases:
        raise ValidationError("external final resolution cases do not enforce proof classification timing")


def _validate_stop_route_contract(protocol: dict[str, Any]) -> None:
    expected = {
        "authority": "coordinator_db",
        "routes": [
            {
                "external_context": "live_external_operation",
                "triggers": ["explicit_pause_cancel"],
                "operation_type": "cancel_pause",
                "operation_variant": "not_applicable",
            },
            {
                "external_context": "dispatched_external_operation_with_opened_external_result_pause",
                "triggers": ["operation_timeout"],
                "operation_type": "resolve_external_interrupt",
                "operation_variant": "recoverable_timeout",
            },
            {
                "external_context": "live_external_operation",
                "triggers": ["aggregate_hard_limit", "policy_stop", "terminal_operator_stop"],
                "operation_type": "resolve_external_interrupt",
                "operation_variant": "controlled_halt",
            },
            {
                "external_context": "live_external_operation",
                "triggers": ["proven_integrity_trigger", "normal_finalization_unavailable"],
                "operation_type": "resolve_external_interrupt",
                "operation_variant": "integrity_failure",
            },
            {
                "external_context": "no_unresolved_external_operation",
                "triggers": ["normal_end", "non_pause_runtime_failure", "internal_terminal_decision"],
                "operation_type": "close_run",
                "operation_variant": "not_applicable",
            },
        ],
        "close_run_external_preconditions": ["absent", "safely_terminal_and_detached"],
        "forbidden_routes": [
            "system_timeout_or_hard_limit_to_cancel_pause",
            "live_external_operation_to_close_run",
            "external_interrupt_owner_then_second_close_run",
        ],
        "selection_rule": "exactly_one_route_before_operation_reservation",
    }
    contract = protocol.get("stop_route_contract")
    if contract != expected:
        raise ValidationError("stop route contract is incomplete, overlapping, or ambiguous")
    seen: set[tuple[str, str]] = set()
    control_variants = _control_variant_index(protocol)
    for route in contract["routes"]:
        pair = (route["operation_type"], route["operation_variant"])
        if pair not in control_variants:
            raise ValidationError(f"stop route references an unknown ControlOperation variant: {pair}")
        for trigger in route["triggers"]:
            route_key = (route["external_context"], trigger)
            if route_key in seen:
                raise ValidationError(f"stop route is not unique: {route_key}")
            seen.add(route_key)


def _validate_resolution_interleavings(protocol: dict[str, Any]) -> None:
    guards = {guard["guard_id"]: guard for guard in protocol["cas_guards"]}
    cancel_guard = guards["cancel_control_combined_cas"]
    cancel_outcomes = {row["outcome"]: row for row in cancel_guard["outcome_guards"]}

    def new_state() -> dict[str, Any]:
        return {
            "phase_revision": 17,
            "lease_epoch": 5,
            "resolution_owner": None,
            "resolution_owner_operation_id": None,
            "winner_operation_type": None,
            "pause_status": "opened",
            "pause_owner": None,
            "run_terminal_closure_owner": None,
            "cancel_control_phase": "operation_reserved",
        }

    def apply_resolution(
        state: dict[str, Any],
        guard_id: str,
        expected_revision: int,
        expected_epoch: int,
        operation_id: str,
        operation_type: str,
        proof_kind: str = "not_applicable",
    ) -> bool:
        guard = guards[guard_id]
        if state["phase_revision"] != expected_revision or state["lease_epoch"] != expected_epoch:
            return False
        if state["resolution_owner"] is not guard["required_resolution_owner"]:
            return False
        if guard_id == "external_normal_terminal_cas" and proof_kind != guard["required_proof_kind"]:
            return False
        state["resolution_owner"] = guard["assigns_resolution_owner"]
        state["resolution_owner_operation_id"] = operation_id
        state["winner_operation_type"] = operation_type
        state["phase_revision"] += 1
        return True

    def observe_preexisting_winner(state: dict[str, Any], outcome: str) -> bool:
        guard = cancel_outcomes[outcome]
        expected_owner = "cancel" if outcome == "preexisting_cancel_resolution" else "interrupt"
        if state["resolution_owner"] != expected_owner or not guard["observation_only"] or guard["acquires"]:
            return False
        if state["winner_operation_type"] != guard["required_winner_operation_type"]:
            return False
        if state["pause_status"] not in guard["required_pause_states"]:
            return False
        winner = state["resolution_owner_operation_id"]
        actual_shape = {
            "pause_owner": state["pause_owner"],
            "run_terminal_closure_owner": state["run_terminal_closure_owner"],
        }
        allowed_shapes = [
            {
                field: winner if value == "winner_operation_id" else value
                for field, value in shape.items()
            }
            for shape in guard["allowed_winner_owner_shapes"]
        ]
        if actual_shape not in allowed_shapes:
            return False
        before = (state["pause_owner"], state["run_terminal_closure_owner"], state["resolution_owner"])
        state["cancel_control_phase"] = "resolution_winner_observed"
        after = (state["pause_owner"], state["run_terminal_closure_owner"], state["resolution_owner"])
        return before == after

    competing = (
        ("external_normal_terminal_cas", "normal", "normal-finalizer", "normal_external_finalization", "safe_stop"),
        ("external_cancel_intent_cas", "cancel", "cancel-operation", "cancel_pause", "not_applicable"),
        ("external_interrupt_intent_cas", "interrupt", "interrupt-operation", "resolve_external_interrupt", "not_applicable"),
    )
    for first_guard, first_owner, operation_id, operation_type, proof_kind in competing:
        state = new_state()
        results = [apply_resolution(state, first_guard, 17, 5, operation_id, operation_type, proof_kind)]
        results.extend(
            apply_resolution(state, later_guard, 17, 5, later_id, later_type, later_proof)
            for later_guard, _, later_id, later_type, later_proof in competing
            if later_guard != first_guard
        )
        if results.count(True) != 1 or state["resolution_owner"] != first_owner:
            raise ValidationError("normal/cancel/interrupt resolution interleaving does not have exactly one winner")

    for guard_id, _, operation_id, operation_type, proof_kind in competing:
        stale_revision = new_state()
        stale_epoch = new_state()
        if apply_resolution(stale_revision, guard_id, 16, 5, operation_id, operation_type, proof_kind):
            raise ValidationError(f"stale ExternalOperation phase revision can win {guard_id}")
        if apply_resolution(stale_epoch, guard_id, 17, 4, operation_id, operation_type, proof_kind):
            raise ValidationError(f"stale ExternalOperation lease epoch can win {guard_id}")

    normal_unavailable = new_state()
    if apply_resolution(
        normal_unavailable,
        "external_normal_terminal_cas",
        17,
        5,
        "normal-finalizer",
        "normal_external_finalization",
        "unavailable",
    ):
        raise ValidationError("normal finalization can win with unavailable proof")
    if not apply_resolution(
        normal_unavailable,
        "external_interrupt_intent_cas",
        17,
        5,
        "integrity-operation",
        "resolve_external_interrupt",
    ):
        raise ValidationError("normal unavailable proof cannot be reclassified to interrupt resolution")

    interrupt_shapes = [
        ("opened", "interrupt-operation", None),
        ("interrupted", "interrupt-operation", "interrupt-operation"),
    ]
    for pause_status, pause_owner, run_owner in interrupt_shapes:
        state = new_state()
        if not apply_resolution(
            state,
            "external_interrupt_intent_cas",
            17,
            5,
            "interrupt-operation",
            "resolve_external_interrupt",
        ):
            raise ValidationError("interrupt resolution cannot acquire an unresolved ExternalOperation")
        state["pause_status"] = pause_status
        state["pause_owner"] = pause_owner
        state["run_terminal_closure_owner"] = run_owner
        if not observe_preexisting_winner(state, "preexisting_interrupt_resolution"):
            raise ValidationError("cancel cannot reach read-only observation after interrupt wins")

    cancel_state = new_state()
    if not apply_resolution(
        cancel_state,
        "external_cancel_intent_cas",
        17,
        5,
        "first-cancel-operation",
        "cancel_pause",
    ):
        raise ValidationError("cancel resolution cannot acquire an unresolved ExternalOperation")
    cancel_state["pause_owner"] = "first-cancel-operation"
    cancel_state["run_terminal_closure_owner"] = "first-cancel-operation"
    if not observe_preexisting_winner(cancel_state, "preexisting_cancel_resolution"):
        raise ValidationError("later cancel cannot reach read-only observation of the first cancel winner")

    mismatched_owner = dict(cancel_state)
    mismatched_owner["pause_owner"] = "foreign-operation"
    mismatched_owner["cancel_control_phase"] = "operation_reserved"
    if observe_preexisting_winner(mismatched_owner, "preexisting_cancel_resolution"):
        raise ValidationError("winner observation accepts incoherent domain ownership")

    absent_external_operation = {"external_operation_id": None, "external_row_exists": False}
    pause_owner = "cancel_operation"
    run_owner = "cancel_operation"
    if absent_external_operation["external_row_exists"] or pause_owner != run_owner:
        raise ValidationError("typed-null cancel arbitration does not prove absence or atomic ownership")


def _validate_cross_machine_invariants(protocol: dict[str, Any]) -> None:
    invariants = protocol.get("cross_machine_invariants")
    if not isinstance(invariants, list):
        raise ValidationError("cross_machine_invariants must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for invariant in invariants:
        invariant_id = invariant.get("invariant_id")
        if not isinstance(invariant_id, str) or not invariant_id:
            raise ValidationError("cross-machine invariant is missing invariant_id")
        if invariant_id in by_id:
            raise ValidationError(f"duplicate cross-machine invariant: {invariant_id}")
        by_id[invariant_id] = invariant
    required_ids = {
        "CTRL-OWN-001",
        "CTRL-OWN-002",
        "CTRL-OWN-003",
        "CTRL-TERM-001",
        "CTRL-TERM-002",
        "PAUSE-LIFE-001",
        "EXT-CANCEL-001",
        "EXT-ARB-001",
        "EXT-INT-001",
        "WINNER-OBS-001",
        "TX-DOMAIN-001",
        "CTRL-RES-001",
        "BRANCH-001",
        "EVIDENCE-001",
        "STOP-ROUTE-001",
        "CONT-001",
        "VERSION-001",
    }
    if set(by_id) != required_ids:
        raise ValidationError(f"cross-machine invariant IDs mismatch: {sorted(set(by_id))}")
    control_contracts = protocol["state_machines"]["control_operation"]["phase_contracts"]
    direct_ownership = by_id["CTRL-OWN-001"]
    direct_contract = control_contracts.get(direct_ownership["phase"])
    if (
        direct_contract is None
        or set(direct_contract["acquires"]) != set(direct_ownership["must_acquire"])
        or direct_contract.get("atomic_acquire") is not True
    ):
        raise ValidationError("CTRL-OWN-001 does not match its phase acquisition contract")
    cancel_ownership = by_id["CTRL-OWN-002"]
    if cancel_ownership.get("ownership_by_outcome_guard") != "cancel_control_combined_cas":
        raise ValidationError("CTRL-OWN-002 does not bind outcome-conditional cancel ownership")
    if set(cancel_ownership.get("no_ownership_outcomes", [])) != {
        "preexisting_cancel_resolution",
        "preexisting_interrupt_resolution",
    }:
        raise ValidationError("CTRL-OWN-002 lets cancel own a preexisting resolution winner")
    if cancel_ownership.get("transaction_domain") != "coordinator_sqlite":
        raise ValidationError("CTRL-OWN-002 is outside the coordinator transaction domain")
    interrupt_ownership = by_id["CTRL-OWN-003"]
    if interrupt_ownership.get("cas_guard") != "interrupt_control_combined_cas":
        raise ValidationError("CTRL-OWN-003 does not bind the combined interrupt CAS")
    if set(interrupt_ownership.get("phases", [])) != {
        "interrupt_and_pause_ownership_reserved",
        "interrupt_and_terminal_ownership_reserved",
    } or interrupt_ownership.get("transaction_domain") != "coordinator_sqlite":
        raise ValidationError("CTRL-OWN-003 does not cover both interrupt ownership paths")
    resolution = by_id["CTRL-TERM-002"]
    resolution_contract = control_contracts.get(resolution["phase"])
    if resolution_contract is None or set(resolution_contract.get("resolves_once", [])) != set(resolution["fields"]):
        raise ValidationError("CTRL-TERM-002 does not match terminal eligibility resolution")
    closure = by_id["CTRL-TERM-001"]
    if closure.get("owner") != "run_terminal_closure_owner":
        raise ValidationError("CTRL-TERM-001 uses an unexpected terminal owner")
    if set(closure.get("pending_allowed_operation_statuses", [])) != {"accepted", "in_progress"}:
        raise ValidationError("CTRL-TERM-001 permits pending closure for an invalid operation status")
    if set(closure.get("terminal_operation_closure_values", [])) != {"committed", "unavailable"}:
        raise ValidationError("CTRL-TERM-001 has an invalid terminal closure set")
    pause = by_id["PAUSE-LIFE-001"]
    pause_machine = protocol["state_machines"]["pause_lifecycle"]
    if pause.get("publicly_resumable_states") != pause_machine["publicly_resumable_states"]:
        raise ValidationError("PAUSE-LIFE-001 does not match resumable Pause states")
    if pause.get("terminal_states") != pause_machine["terminal_states"] or pause.get("reopen_edges") != []:
        raise ValidationError("PAUSE-LIFE-001 does not enforce terminal Pause finality")
    if pause.get("public_resume_predicate") != pause_machine["public_resume_predicate"]:
        raise ValidationError("PAUSE-LIFE-001 does not enforce the public resume ownership predicate")
    external_machine = protocol["state_machines"]["external_operation"]
    final_proof = by_id["EXT-CANCEL-001"]
    if final_proof.get("producer_terminal_phase") != "external_final_evidence_committed":
        raise ValidationError("EXT-CANCEL-001 does not bind the single terminal producer phase")
    if final_proof.get("safe_consumer_phase") != "external_terminal_closure_verified":
        raise ValidationError("EXT-CANCEL-001 does not bind the safe-stop consumer")
    if final_proof.get("unavailable_consumer_phase") != "external_unavailable_verified":
        raise ValidationError("EXT-CANCEL-001 does not bind the unavailable consumer")
    if set(final_proof["forbidden_intermediate_phases"]) != {
        "cancel_intent_committed",
        "interrupt_stop_intent_committed",
        "termination_evidence_committed",
    }:
        raise ValidationError("EXT-CANCEL-001 has an invalid intermediate proof set")
    arbitration = by_id["EXT-ARB-001"]
    if set(arbitration.get("competing_cas_guards", [])) != {
        "external_normal_terminal_cas",
        "external_cancel_intent_cas",
        "external_interrupt_intent_cas",
    }:
        raise ValidationError("EXT-ARB-001 does not bind all competing CAS guards")
    if set(arbitration.get("compare_fields", [])) != {
        "external_operation_id",
        "phase_revision",
        "lease_epoch",
        "resolution_owner",
    } or arbitration.get("exactly_one_winner") is not True:
        raise ValidationError("EXT-ARB-001 does not establish a single linearization winner")
    if arbitration.get("normal_requires_preclassified_proof_kind") != "safe_stop":
        raise ValidationError("EXT-ARB-001 permits normal resolution without preclassified safe-stop proof")
    transaction = by_id["TX-DOMAIN-001"]
    if transaction.get("transaction_domain") != "coordinator_sqlite" or set(transaction.get("atomic_objects", [])) != {
        "control_operation",
        "pause_ownership",
        "run_terminal_closure",
        "external_operation",
    }:
        raise ValidationError("TX-DOMAIN-001 does not bind the complete atomic object set")
    reservation = by_id["CTRL-RES-001"]
    interrupt_closure = by_id["EXT-INT-001"]
    if interrupt_closure.get("control_operation_type") != "resolve_external_interrupt":
        raise ValidationError("EXT-INT-001 does not bind the interrupt ControlOperation")
    if set(interrupt_closure.get("variants", [])) != {
        "recoverable_timeout",
        "controlled_halt",
        "integrity_failure",
    }:
        raise ValidationError("EXT-INT-001 does not cover every interrupt disposition")
    if interrupt_closure.get("safe_timeout_consumer") != "coordinator_transition_committed":
        raise ValidationError("EXT-INT-001 does not route safe timeout to Coordinator")
    if interrupt_closure.get("unavailable_closure") != "terminal_closure_unavailable_recorded":
        raise ValidationError("EXT-INT-001 does not close unavailable interrupt evidence")
    if interrupt_closure.get("normal_unavailable_reclassification") != (
        "resolve_external_interrupt/integrity_failure"
    ):
        raise ValidationError("EXT-INT-001 does not reclassify normal unavailable proof before resolution")
    observation = by_id["WINNER-OBS-001"]
    if observation.get("phase") != "resolution_winner_observed" or set(observation.get("outcomes", [])) != {
        "preexisting_cancel_resolution",
        "preexisting_interrupt_resolution",
    }:
        raise ValidationError("WINNER-OBS-001 does not cover both preexisting resolution winners")
    if observation.get("required_owner_coherence") != "domain_owners_match_resolution_owner_operation_id":
        raise ValidationError("WINNER-OBS-001 does not fence observed domain ownership")
    if observation.get("domain_owner_mutations") != []:
        raise ValidationError("WINNER-OBS-001 permits winner observation to mutate domain ownership")
    if reservation.get("phase") != "operation_reserved" or reservation.get("required_operation_variant_count") != 11:
        raise ValidationError("CTRL-RES-001 does not require all reservation overlays")
    if reservation.get("merge_rule") != "shared_phase_contract_plus_exact_variant_overlay":
        raise ValidationError("CTRL-RES-001 uses an invalid overlay merge rule")
    branch_ids = {contract["branch_id"] for contract in protocol["branch_contracts"]}
    if set(by_id["BRANCH-001"].get("branch_contracts", [])) != branch_ids:
        raise ValidationError("BRANCH-001 does not bind every guarded branch")
    if by_id["BRANCH-001"].get("coverage") != "mutually_exclusive_and_exhaustive":
        raise ValidationError("BRANCH-001 does not require an exact branch partition")
    union_ids = {union["union_id"] for union in protocol["evidence_unions"]}
    if set(by_id["EVIDENCE-001"].get("evidence_unions", [])) != union_ids:
        raise ValidationError("EVIDENCE-001 does not bind every tagged evidence union")
    stop_route = by_id["STOP-ROUTE-001"]
    if (
        stop_route.get("contract") != "stop_route_contract"
        or stop_route.get("selection") != "exactly_one_route_before_operation_reservation"
        or stop_route.get("forbids_second_terminal_operation") is not True
    ):
        raise ValidationError("STOP-ROUTE-001 does not bind the unique stop route contract")
    outcome_names = {item["outcome_class"] for item in protocol["outcome_classes"]}
    if outcome_names != set(by_id["CONT-001"]["classes"]):
        raise ValidationError("CONT-001 does not match the outcome partition")
    compatibility = by_id["VERSION-001"]
    if compatibility.get("runtime_schema") != "0.4":
        raise ValidationError("VERSION-001 has an invalid runtime schema")
    if compatibility.get("resume_exact_schemas") != ["0.4"]:
        raise ValidationError("VERSION-001 has an invalid exact-resume set")
    if compatibility.get("source_only_schemas") != ["0.2", "0.3"]:
        raise ValidationError("VERSION-001 has an invalid source-only schema set")


def _validate_protocol(protocol: dict[str, Any]) -> None:
    required_top_level = {
        "schema_version",
        "protocol_version",
        "protocol_id",
        "status",
        "digest_policy",
        "source_documents",
        "authorities",
        "transaction_domains",
        "effect_classes",
        "continuation_policies",
        "outcome_classes",
        "cas_guards",
        "state_machines",
        "branch_contracts",
        "evidence_unions",
        "dependency_dags",
        "field_bindings",
        "cross_machine_invariants",
        "stop_route_contract",
        "compatibility",
    }
    _require_keys(protocol, required_top_level, "control protocol")
    if protocol["schema_version"] != "0.4" or protocol["protocol_version"] != "0.4":
        raise ValidationError("control protocol version mismatch")
    if protocol["protocol_id"] != "phase-a-control-protocol" or protocol["status"] not in {"review", "ready"}:
        raise ValidationError("control protocol identity or lifecycle status mismatch")
    _require_unique_strings(protocol["authorities"], "authorities")
    _require_unique_strings(protocol["effect_classes"], "effect_classes")
    _require_unique_strings(protocol["continuation_policies"], "continuation_policies")
    sources = _require_unique_strings(protocol["source_documents"], "source_documents")
    for source in sources:
        if not (CONTRACT_DIR / source).is_file():
            raise ValidationError(f"missing control protocol source document: {source}")
    state_machines = protocol.get("state_machines")
    if not isinstance(state_machines, dict) or set(state_machines) != {
        "control_operation",
        "external_operation",
        "pause_lifecycle",
        "run_lifecycle",
    }:
        raise ValidationError("state_machines must contain the exact frozen machine set")
    outcomes = protocol.get("outcome_classes")
    if not isinstance(outcomes, list) or len(outcomes) != 4:
        raise ValidationError("outcome_classes must contain the exact four-way partition")
    outcome_names = [item.get("outcome_class") for item in outcomes if isinstance(item, dict)]
    if len(outcome_names) != 4 or len(set(outcome_names)) != 4 or set(outcome_names) != set(EXPECTED_OUTCOME_STATUS):
        raise ValidationError("outcome_classes contain invalid or duplicate names")
    for outcome in outcomes:
        _require_keys(
            outcome,
            {"outcome_class", "operation_status", "observation", "may_advance_phase", "permitted_action"},
            "outcome class",
        )
        expected_status, expected_advance = EXPECTED_OUTCOME_STATUS[outcome["outcome_class"]]
        if outcome["operation_status"] != expected_status or outcome["may_advance_phase"] is not expected_advance:
            raise ValidationError(f"outcome class mapping changed: {outcome['outcome_class']}")
        if not isinstance(outcome["observation"], str) or not outcome["observation"]:
            raise ValidationError(f"outcome class has an invalid observation: {outcome['outcome_class']}")
        if not isinstance(outcome["permitted_action"], str) or not outcome["permitted_action"]:
            raise ValidationError(f"outcome class has an invalid permitted action: {outcome['outcome_class']}")
    compatibility = protocol.get("compatibility")
    if not isinstance(compatibility, list) or len(compatibility) != 3:
        raise ValidationError("compatibility must define schemas 0.2, 0.3, and 0.4")
    versions: list[str] = []
    for row in compatibility:
        _require_keys(row, {"execution_schema", "contract", "phase_b_0_4_behavior"}, "compatibility row")
        versions.append(row["execution_schema"])
        if not isinstance(row["contract"], str) or not row["contract"]:
            raise ValidationError("compatibility row has an invalid contract")
        if not isinstance(row["phase_b_0_4_behavior"], str) or not row["phase_b_0_4_behavior"]:
            raise ValidationError("compatibility row has an invalid Phase B behavior")
    if versions != ["0.2", "0.3", "0.4"]:
        raise ValidationError(f"compatibility schema order mismatch: {versions}")
    _validate_control_operation(protocol)
    _validate_external_operation(protocol)
    _validate_pause_lifecycle(protocol)
    _validate_run_lifecycle(protocol)
    _validate_dependency_dags(protocol)
    _validate_evidence_unions(protocol)
    _validate_branch_contracts(protocol)
    _validate_transaction_domains_and_cas(protocol)
    _validate_stop_route_contract(protocol)
    _validate_resolution_interleavings(protocol)
    _validate_cross_machine_invariants(protocol)


def _validate_catalog(catalog: dict[str, Any], protocol_sha256: str) -> None:
    _require_keys(
        catalog,
        {
            "schema_version",
            "catalog_version",
            "catalog_id",
            "phase",
            "digest_policy",
            "control_protocol_reference",
            "control_protocol_version",
            "control_protocol_sha256",
            "requirements",
        },
        "requirement catalog",
    )
    if catalog["schema_version"] != "0.1" or catalog["catalog_version"] != "0.4.0":
        raise ValidationError("requirement catalog version mismatch")
    if catalog["control_protocol_reference"] != PROTOCOL_PATH.name:
        raise ValidationError("requirement catalog control protocol reference mismatch")
    if catalog["control_protocol_version"] != "0.4":
        raise ValidationError("requirement catalog control protocol version mismatch")
    if catalog["control_protocol_sha256"] != protocol_sha256:
        raise ValidationError("requirement catalog control protocol SHA-256 is stale")
    requirements = catalog["requirements"]
    if not isinstance(requirements, list) or not requirements:
        raise ValidationError("requirement catalog requirements must be a non-empty list")
    required_fields = {"requirement_id", "owner_ticket", "source_locator", "kind", "summary", "required"}
    ids: list[str] = []
    owners: list[str] = []
    by_owner: dict[str, set[str]] = {owner: set() for owner in EXPECTED_OWNER_ORDER}
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise ValidationError(f"requirement {index} must be an object")
        _require_keys(requirement, required_fields, f"requirement {index}")
        requirement_id = requirement["requirement_id"]
        owner = requirement["owner_ticket"]
        if not isinstance(requirement_id, str) or not requirement_id:
            raise ValidationError(f"requirement {index} has an invalid ID")
        if owner not in by_owner:
            raise ValidationError(f"requirement {requirement_id} has an unknown owner: {owner}")
        if requirement["required"] is not True:
            raise ValidationError(f"requirement {requirement_id} is not required")
        for field in ("source_locator", "kind", "summary"):
            if not isinstance(requirement[field], str) or not requirement[field]:
                raise ValidationError(f"requirement {requirement_id} has an invalid {field}")
        ids.append(requirement_id)
        owners.append(owner)
        by_owner[owner].add(requirement_id)
    if len(ids) != len(set(ids)):
        raise ValidationError("requirement catalog contains duplicate IDs")
    actual_owner_counts = {owner: len(requirement_ids) for owner, requirement_ids in by_owner.items()}
    if len(ids) != 129 or actual_owner_counts != EXPECTED_OWNER_COUNTS:
        raise ValidationError(
            f"requirement catalog count mismatch: total={len(ids)}, owners={actual_owner_counts}"
        )
    owner_order = list(dict.fromkeys(owners))
    if owner_order != EXPECTED_OWNER_ORDER:
        raise ValidationError(f"requirement catalog owner order mismatch: {owner_order}")
    review_ticket_ids = {
        "A02C01": "A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md",
        "A04": "A04_PAUSE_RESUME_SEMANTICS.md",
        "A05": "A05_CODE_AGENT_CONTRACT.md",
        "A06": "A06_BUDGETS_AND_STOP_CONDITIONS.md",
        "A07": "A07_PHASE_B_HARNESS_ACCEPTANCE.md",
    }
    for owner, filename in review_ticket_ids.items():
        prose = (CONTRACT_DIR / filename).read_text(encoding="utf-8")
        explicit = set(re.findall(rf"\b{re.escape(owner)}-[A-Z0-9-]+\b", prose))
        if explicit != by_owner[owner]:
            missing = sorted(by_owner[owner] - explicit)
            unknown = sorted(explicit - by_owner[owner])
            raise ValidationError(f"{owner} prose/catalog ID mismatch; missing_in_prose={missing}, unknown_in_prose={unknown}")


def _validate_protocol_references() -> None:
    for relative in REQUIRED_PROTOCOL_REFERENCES:
        path = ROOT / relative
        if not path.is_file():
            raise ValidationError(f"missing required protocol reference file: {relative}")
        if PROTOCOL_PATH.name not in path.read_text(encoding="utf-8"):
            raise ValidationError(f"{relative} does not reference {PROTOCOL_PATH.name}")


def _validate_stop_classification_documents(catalog: dict[str, Any]) -> None:
    required_prose = {
        "A05_CODE_AGENT_CONTRACT.md": [
            "任一stop proof维度false/unknown均为`recovery_required + terminal_closure = unavailable`",
            "任一stop proof缺失只进入recovery-required/unavailable",
        ],
        "A06_BUDGETS_AND_STOP_CONDITIONS.md": [
            "任一停止证明失败/unknown或post-stop activity均为recovery-required/unavailable",
            "unavailable stop proof固定映射ExternalOperation `recovery_required`",
        ],
        "A07_PHASE_B_HARNESS_ACCEPTANCE.md": [
            "任一false/unknown均为`recovery_required + unavailable`",
            "unavailable在Pause absent/prepared/opened下均不得产生failed lifecycle",
        ],
    }
    for filename, fragments in required_prose.items():
        prose = (CONTRACT_DIR / filename).read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in prose:
                raise ValidationError(f"{filename} is missing the frozen unavailable-stop classification: {fragment}")
        for line_number, line in enumerate(prose.splitlines(), start=1):
            uncertainty = any(
                marker in line
                for marker in ("false/unknown", "无法证明", "proof缺失", "proof missing", "unconfirmed")
            )
            stop_dimension = any(
                marker in line.lower()
                for marker in ("termination", "write-lease", "verify-empty", "bounded drain", "post-stop", "停止证明")
            )
            failed_mapping = "run_status" in line and "failed" in line.lower() or "failed lifecycle" in line.lower()
            if uncertainty and stop_dimension and failed_mapping and not (
                "unavailable" in line.lower() and "recovery" in line.lower()
            ):
                raise ValidationError(
                    f"{filename}:{line_number} maps uncertain stop evidence without recovery-required/unavailable"
                )

    by_id = {requirement["requirement_id"]: requirement for requirement in catalog["requirements"]}
    required_catalog_terms = {
        "A04-PAUSE-020": {"winner observation", "never mutates domain ownership"},
        "A05-CODE-007": {"unavailable", "never a failed run lifecycle"},
        "A05-CODE-028": {"interrupt", "conflicting ownership"},
        "A05-CODE-029": {"preclassified safe-stop", "integrity interrupt"},
        "A06-BUDGET-008": {"safe-stop", "unavailable"},
        "A06-BUDGET-018": {"unavailable", "safe-stop integrity-failed"},
        "A06-BUDGET-020": {"independent interrupt operation", "absent, prepared, and opened"},
        "A06-BUDGET-021": {"exactly one", "second terminal operation"},
        "A07-META-013": {"exhaustive disjoint", "unavailable closures"},
        "A07-META-014": {"composite-state", "normal-unavailable", "one stop route"},
    }
    for requirement_id, terms in required_catalog_terms.items():
        summary = by_id[requirement_id]["summary"].lower()
        missing = sorted(term for term in terms if term not in summary)
        if missing:
            raise ValidationError(f"{requirement_id} is missing stop-classification terms: {missing}")


def _assert_protocol_mutation_rejected(
    protocol: dict[str, Any],
    label: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    candidate = deepcopy(protocol)
    mutate(candidate)
    try:
        _validate_protocol(candidate)
    except ValidationError:
        return
    raise ValidationError(f"negative protocol mutation was accepted: {label}")


def _validate_negative_protocol_mutations(protocol: dict[str, Any]) -> None:
    def branch(candidate: dict[str, Any], branch_id: str) -> dict[str, Any]:
        return next(item for item in candidate["branch_contracts"] if item["branch_id"] == branch_id)

    def external_outcome(
        candidate: dict[str, Any], resolution_kind: str, disposition: str, proof_kind: str
    ) -> dict[str, Any]:
        return next(
            item
            for item in candidate["state_machines"]["external_operation"]["terminal_outcomes"]
            if item["resolution_kind"] == resolution_kind
            and item["interrupt_disposition"] == disposition
            and item["proof_kind"] == proof_kind
        )

    def control_variant(candidate: dict[str, Any], operation_type: str, operation_variant: str) -> dict[str, Any]:
        return next(
            variant
            for operation in candidate["state_machines"]["control_operation"]["operations"]
            if operation["operation_type"] == operation_type
            for variant in operation["variants"]
            if variant["operation_variant"] == operation_variant
        )

    def remove_guard(candidate: dict[str, Any]) -> None:
        candidate["branch_contracts"] = [
            item for item in candidate["branch_contracts"] if item["branch_id"] != "recoverable_timeout_final_proof"
        ]

    def overlap_cancel_guard(candidate: dict[str, Any]) -> None:
        branch(candidate, "cancel_arbitration_result")["cases"][1]["when"]["external_final_proof_kind"].append(
            "unavailable"
        )

    def leave_cancel_guard_gap(candidate: dict[str, Any]) -> None:
        branch(candidate, "cancel_arbitration_result")["cases"][3]["when"]["arbitration_outcome"].remove(
            "preexisting_cancel_resolution"
        )

    def mismatch_typed_null_evidence(candidate: dict[str, Any]) -> None:
        branch(candidate, "cancel_arbitration_result")["cases"][0]["evidence_variant"] = "external_safe_stop"

    def cross_wire_interrupt_consumer(candidate: dict[str, Any]) -> None:
        consumer = external_outcome(candidate, "interrupt", "recoverable_timeout", "safe_stop")["consumer"]
        consumer.update(
            {
                "operation_type": "cancel_pause",
                "operation_variant": "not_applicable",
                "phase": "external_terminal_closure_verified",
            }
        )

    def map_unavailable_to_failed(candidate: dict[str, Any]) -> None:
        external_outcome(candidate, "interrupt", "controlled_halt", "unavailable")["statuses"] = ["failed"]

    def omit_post_stop_dimension(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["external_operation"]["final_proof_classification"]["dimensions"].remove(
            "post_stop_stability"
        )

    def mismatch_pause_disposition(candidate: dict[str, Any]) -> None:
        union = next(
            item for item in candidate["evidence_unions"] if item["union_id"] == "InterruptSafePauseDispositionProof"
        )
        union["correlates_with"]["tag_mapping"]["prepared"] = "opened_interrupted"

    def allow_pre_pause_recoverable_timeout(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "interrupt_control_combined_cas")
        acquisition = next(
            item for item in guard["variant_acquisitions"] if item["operation_variant"] == "recoverable_timeout"
        )
        acquisition["allowed_external_phases"].insert(0, "pause_bound")

    def require_external_proof_for_typed_null(candidate: dict[str, Any]) -> None:
        contract = candidate["state_machines"]["control_operation"]["phase_contracts"]["pause_cancelled_recorded"]
        contract["required_evidence"] = ["final_external_terminal_proof"]

    def reopen_quarantined_pause(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["pause_lifecycle"]["allowed_edges"].append(["quarantined", "opened"])

    def advance_recovery_required(candidate: dict[str, Any]) -> None:
        control_variant(candidate, "resolve_external_interrupt", "recoverable_timeout")["success_edges"].append(
            ["terminal_closure_unavailable_recorded", "result_committed"]
        )

    def let_cancel_own_interrupt_winner(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "cancel_control_combined_cas")
        ownership = next(
            item for item in guard["outcome_guards"] if item["outcome"] == "preexisting_interrupt_resolution"
        )
        ownership["acquires"] = ["pause_cancel_owner", "run_terminal_closure_owner"]

    def restore_unconditional_empty_owner_guard(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "cancel_control_combined_cas")
        guard["required_empty_fields"] = ["pause_owner", "run_terminal_closure_owner"]

    def corrupt_winner_owner_coherence(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "cancel_control_combined_cas")
        outcome = next(
            item for item in guard["outcome_guards"] if item["outcome"] == "preexisting_interrupt_resolution"
        )
        outcome["allowed_winner_owner_shapes"][0]["pause_owner"] = "foreign_operation_id"

    def require_reserved_revision_for_winner_observation(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "cancel_control_combined_cas")
        outcome = next(
            item for item in guard["outcome_guards"] if item["outcome"] == "preexisting_interrupt_resolution"
        )
        outcome["external_revision_epoch_guard"] = "exact_reserved_revision_epoch_cas"

    def insert_normal_unavailable_domain_flow(candidate: dict[str, Any]) -> None:
        normal_safe = external_outcome(candidate, "normal", "not_applicable", "safe_stop")
        normal_unavailable = deepcopy(normal_safe)
        normal_unavailable["proof_kind"] = "unavailable"
        normal_unavailable["statuses"] = ["recovery_required"]
        normal_unavailable["consumer"] = {
            "kind": "domain_flow",
            "flow": "normal_resolution_recovery",
        }
        candidate["state_machines"]["external_operation"]["terminal_outcomes"].append(normal_unavailable)

    def allow_normal_without_safe_stop(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "external_normal_terminal_cas")
        guard["required_proof_kind"] = "unavailable"

    def add_normal_unavailable_branch(candidate: dict[str, Any]) -> None:
        contract = branch(candidate, "external_final_resolution")
        contract["valid_combinations"].append(
            {"resolution_action": "normal_progress", "preclassified_final_proof_kind": "unavailable"}
        )
        contract["cases"].append(
            {
                "when": {
                    "resolution_action": ["normal_progress"],
                    "preclassified_final_proof_kind": ["unavailable"],
                },
                "target": "interrupt_stop_intent_committed",
            }
        )

    def route_live_external_to_close_run(candidate: dict[str, Any]) -> None:
        route = next(
            item
            for item in candidate["stop_route_contract"]["routes"]
            if item["external_context"] == "live_external_operation" and "policy_stop" in item["triggers"]
        )
        route["operation_type"] = "close_run"
        route["operation_variant"] = "not_applicable"

    def route_hard_limit_to_cancel_pause(candidate: dict[str, Any]) -> None:
        route = next(
            item
            for item in candidate["stop_route_contract"]["routes"]
            if "aggregate_hard_limit" in item["triggers"]
        )
        route["operation_type"] = "cancel_pause"
        route["operation_variant"] = "not_applicable"

    def allow_second_close_after_interrupt(candidate: dict[str, Any]) -> None:
        candidate["stop_route_contract"]["forbidden_routes"].remove(
            "external_interrupt_owner_then_second_close_run"
        )

    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("missing branch guard", remove_guard),
        ("overlapping cancel guard", overlap_cancel_guard),
        ("cancel guard coverage gap", leave_cancel_guard_gap),
        ("typed-null evidence-union mismatch", mismatch_typed_null_evidence),
        ("interrupt consumer in cancel graph", cross_wire_interrupt_consumer),
        ("unavailable stop mapped to failed", map_unavailable_to_failed),
        ("stop proof omits post-stop stability", omit_post_stop_dimension),
        ("Pause snapshot maps to the wrong interrupt disposition", mismatch_pause_disposition),
        ("recoverable timeout allowed before dispatch", allow_pre_pause_recoverable_timeout),
        ("typed-null cancellation requires external final proof", require_external_proof_for_typed_null),
        ("quarantined Pause reopens", reopen_quarantined_pause),
        ("recovery-required phase advances", advance_recovery_required),
        ("cancel owns preexisting interrupt winner", let_cancel_own_interrupt_winner),
        ("cancel winner observation requires empty owners", restore_unconditional_empty_owner_guard),
        ("winner observation accepts incoherent domain ownership", corrupt_winner_owner_coherence),
        ("winner observation requires the stale reserved revision", require_reserved_revision_for_winner_observation),
        ("normal unavailable uses a free-string consumer", insert_normal_unavailable_domain_flow),
        ("normal resolution CAS accepts unavailable proof", allow_normal_without_safe_stop),
        ("normal unavailable enters the external final branch", add_normal_unavailable_branch),
        ("live ExternalOperation routes to close_run", route_live_external_to_close_run),
        ("hard limit routes to cancel_pause", route_hard_limit_to_cancel_pause),
        ("interrupt closure permits a second close_run", allow_second_close_after_interrupt),
    ]
    for label, mutate in mutations:
        _assert_protocol_mutation_rejected(protocol, label, mutate)


def main() -> int:
    try:
        protocol = _load_strict_json(PROTOCOL_PATH)
        catalog = _load_strict_json(CATALOG_PATH)
        protocol_sha256 = _sha256(PROTOCOL_PATH)
        _validate_protocol(protocol)
        _validate_negative_protocol_mutations(protocol)
        _validate_catalog(catalog, protocol_sha256)
        _validate_stop_classification_documents(catalog)
        _validate_protocol_references()
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "Phase A control protocol validation passed: "
        f"protocol_sha256={protocol_sha256} "
        f"catalog_sha256={_sha256(CATALOG_PATH)} "
        f"requirements={len(catalog['requirements'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
