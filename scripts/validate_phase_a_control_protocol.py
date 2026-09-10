#!/usr/bin/env python3
"""Validate the Phase A machine-readable control protocol and requirement catalog."""

from __future__ import annotations

import hashlib
import json
import math
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
    "advance_run": {"not_applicable"},
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
        "budget_policy_profile": ("budget_policy_profile", "coordinator_db", False),
        "budget_policy_version": ("schema_version", "coordinator_db", False),
        "budget_policy_selection_authority": ("policy_selection_authority", "coordinator_db", False),
        "initial_invocation_capability_inputs": ("invocation_capability_inputs", "coordinator_db", False),
    },
    ("publish_pause", "not_applicable"): {
        "source_execution_artifact_checkpoint_heads": ("head_tuple", "coordinator_db", False),
        "typed_pause_reason": ("pause_reason", "coordinator_db", False),
        "requesting_and_target_identity": ("attempt_identity_tuple", "coordinator_db", False),
        "deterministic_pause_identity_inputs": ("canonical_digest_input", "coordinator_db", False),
    },
    ("advance_run", "not_applicable"): {
        "source_run_attempt_and_heads": ("source_transition_context", "coordinator_db", False),
        "proposed_route": ("route", "coordinator_db", False),
        "canonical_budget_decision_bytes": ("canonical_bytes", "coordinator_db", False),
        "budget_decision_digest": ("sha256", "coordinator_db", False),
        "grant_consumption_or_not_applicable": ("grant_consumption_union", "coordinator_db", False),
        "transition_target_kind": ("transition_target_kind", "coordinator_db", False),
        "target_attempt_identity_or_typed_null": ("target_attempt_union", "coordinator_db", False),
        "human_request_or_not_applicable": ("human_request_union", "coordinator_db", False),
        "required_invalidation_set": ("artifact_invalidation_set", "coordinator_db", False),
        "invalidation_set_digest": ("sha256", "coordinator_db", False),
        "transition_identity": ("transition_identity", "coordinator_db", False),
        "canonical_transition_bytes": ("canonical_bytes", "coordinator_db", False),
        "transition_digest": ("sha256", "coordinator_db", False),
        "expected_post_transition_heads": ("head_tuple", "coordinator_db", False),
        "target_preparation_snapshot": ("target_preparation_snapshot_union", "coordinator_db", False),
        "terminal_closure_revision": ("revision", "coordinator_db", False),
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
        "terminal_disposition_contract_digest": ("sha256", "coordinator_db", False),
    },
    ("cancel_pause", "not_applicable"): {
        "exact_pause_and_opened_head": ("pause_head_tuple", "coordinator_db", False),
        "external_operation_identity": ("external_operation_id", "coordinator_db", True),
        "typed_cancel_reason": ("cancel_reason", "coordinator_db", False),
        "precomputed_pause_cancel_or_quarantine_event": ("event_identity_digest", "coordinator_db", False),
        "terminal_disposition_contract_digest": ("sha256", "coordinator_db", False),
    },
    ("resolve_external_interrupt", "recoverable_timeout"): {
        "exact_external_operation_resolution_tuple": ("external_resolution_tuple", "coordinator_db", False),
        "typed_interrupt_reason": ("interrupt_reason", "coordinator_db", False),
        "exact_run_heads": ("head_tuple", "coordinator_db", False),
        "pause_snapshot": ("pause_snapshot_union", "coordinator_db", False),
        "resource_reservation_snapshot": ("external_resource_reservation_snapshot_union", "coordinator_db", False),
        "deterministic_delivery_or_closure_identity": ("canonical_failed_delivery_identity", "coordinator_db", False),
        "terminal_disposition_contract_digest": ("sha256", "coordinator_db", False),
    },
    ("resolve_external_interrupt", "controlled_halt"): {
        "exact_external_operation_resolution_tuple": ("external_resolution_tuple", "coordinator_db", False),
        "typed_interrupt_reason": ("interrupt_reason", "coordinator_db", False),
        "exact_run_heads": ("head_tuple", "coordinator_db", False),
        "pause_snapshot": ("pause_snapshot_union", "coordinator_db", False),
        "resource_reservation_snapshot": ("external_resource_reservation_snapshot_union", "coordinator_db", False),
        "deterministic_delivery_or_closure_identity": ("terminal_closure_key", "coordinator_db", False),
        "terminal_disposition_contract_digest": ("sha256", "coordinator_db", False),
    },
    ("resolve_external_interrupt", "integrity_failure"): {
        "exact_external_operation_resolution_tuple": ("external_resolution_tuple", "coordinator_db", False),
        "typed_interrupt_reason": ("interrupt_reason", "coordinator_db", False),
        "exact_run_heads": ("head_tuple", "coordinator_db", False),
        "pause_snapshot": ("pause_snapshot_union", "coordinator_db", False),
        "resource_reservation_snapshot": ("external_resource_reservation_snapshot_union", "coordinator_db", False),
        "deterministic_delivery_or_closure_identity": ("terminal_closure_key", "coordinator_db", False),
        "terminal_disposition_contract_digest": ("sha256", "coordinator_db", False),
    },
    ("replay_run", "not_applicable"): {
        "reserved_child_run_locator": ("canonical_locator", "coordinator_db", False),
        "source_snapshot_proof": ("source_snapshot_proof_union", "coordinator_db", False),
        "source_policy_classification_proof": ("source_policy_classification_proof", "coordinator_db", False),
        "canonical_child_policy_bytes": ("canonical_bytes", "coordinator_db", False),
        "child_policy_digest": ("sha256", "coordinator_db", False),
        "child_policy_profile": ("budget_policy_profile", "coordinator_db", False),
        "child_policy_version": ("schema_version", "coordinator_db", False),
        "child_policy_selection_authority": ("policy_selection_authority", "coordinator_db", False),
        "initial_invocation_capability_inputs": ("invocation_capability_inputs", "coordinator_db", False),
    },
    ("fork_run", "not_applicable"): {
        "reserved_child_run_locator": ("canonical_locator", "coordinator_db", False),
        "source_snapshot_proof": ("source_snapshot_proof_union", "coordinator_db", False),
        "canonical_child_policy_bytes": ("canonical_bytes", "coordinator_db", False),
        "child_policy_digest": ("sha256", "coordinator_db", False),
        "child_policy_profile": ("budget_policy_profile", "coordinator_db", False),
        "child_policy_version": ("schema_version", "coordinator_db", False),
        "child_policy_selection_authority": ("policy_selection_authority", "coordinator_db", False),
        "initial_invocation_capability_inputs": ("invocation_capability_inputs", "coordinator_db", False),
    },
    ("close_run", "not_applicable"): {
        "run_terminal_closure_key": ("terminal_closure_key", "coordinator_db", False),
        "terminal_trigger_identity": ("terminal_trigger", "coordinator_db", False),
        "requested_terminal_disposition": ("run_terminal_disposition", "coordinator_db", False),
        "external_operation_precondition": ("close_external_precondition", "coordinator_db", False),
        "close_source_snapshot": ("close_source_snapshot", "coordinator_db", False),
        "external_operation_precondition_proof_digest": ("sha256", "coordinator_db", False),
        "terminal_disposition_contract_digest": ("sha256", "coordinator_db", False),
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
    "A04": 21,
    "A05": 29,
    "A06": 21,
    "A07": 15,
}
EXPECTED_OUTCOME_STATUS = {
    "committed_result_replay": ("committed", False),
    "materializable_publication_prefix": ("in_progress", True),
    "non_materializable_domain_gap": ("recovery_required", False),
    "integrity_conflict": ("failed", False),
}
EXPECTED_CONTROL_GRAPH_SHA256 = "c52ea4dbc544d8fa5190dd4022e2c7580fc998e130e53a4beab00e8336376b3c"
EXPECTED_NEGATIVE_MUTATION_COUNT = 104
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


def _reject_json_constant(value: str) -> Any:
    raise ValidationError(f"non-JSON numeric constant: {value}")


def _finite_json_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError(f"non-finite JSON number: {value}")
    return result


def _parse_strict_json(value: str) -> Any:
    return json.loads(value, object_pairs_hook=_strict_object,
                      parse_constant=_reject_json_constant, parse_float=_finite_json_float)


def _load_strict_json(path: Path) -> dict[str, Any]:
    try:
        payload = _parse_strict_json(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValidationError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"{path} must contain a JSON object")
    return payload


# Freeze every object key and scalar type in the pre-freeze protocol/catalog.
# This supplements semantic checks without duplicating a full schema document.
def _object_layout_sha256(value: Any) -> str:
    def layout(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: layout(child) for key, child in item.items()}
        if isinstance(item, list):
            return [layout(child) for child in item]
        if isinstance(item, float) and not math.isfinite(item):
            raise ValidationError("non-finite number in protocol/catalog")
        return type(item).__name__
    return hashlib.sha256(json.dumps(layout(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


EXPECTED_PROTOCOL_LAYOUT_SHA256 = "c3e2a6e318169467a8d4489b2e2ece341f8193d0d815e43dbe0031290ab7335c"
EXPECTED_CATALOG_LAYOUT_SHA256 = "a6ee775330ceec5c5f44573f6acb0ae2b3f5a0ffc1bdd75c1c374ae7df6f7f9c"


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


def _validate_phase_dependencies(
    variant: dict[str, Any],
    edges: list[tuple[str, str]],
    context: str,
) -> None:
    nodes = set(variant["phases"])
    initial = variant["initial_phase"]
    rows = variant.get("phase_dependencies")
    if not isinstance(rows, list):
        raise ValidationError(f"{context}.phase_dependencies must be a list")
    dependencies: dict[str, str] = {}
    for row in rows:
        _require_keys(row, {"producer_phase", "consumer_phase"}, f"{context} phase dependency")
        producer = row["producer_phase"]
        consumer = row["consumer_phase"]
        if producer not in nodes or consumer not in nodes or producer == consumer:
            raise ValidationError(f"{context} has an invalid phase dependency: {producer} -> {consumer}")
        if consumer in dependencies:
            raise ValidationError(f"{context} has duplicate dependency coverage for {consumer}")
        dependencies[consumer] = producer
    if set(dependencies) != nodes - {initial}:
        raise ValidationError(f"{context} phase dependencies do not cover every noninitial phase")

    predecessors = {node: set() for node in nodes}
    for source, target in edges:
        predecessors[target].add(source)
    dominators = {node: ({node} if node == initial else set(nodes)) for node in nodes}
    changed = True
    while changed:
        changed = False
        for node in nodes - {initial}:
            updated = {node} | set.intersection(*(dominators[parent] for parent in predecessors[node]))
            if updated != dominators[node]:
                dominators[node] = updated
                changed = True
    for consumer, producer in dependencies.items():
        if producer not in dominators[consumer]:
            raise ValidationError(
                f"{context} dependency producer does not dominate consumer: {producer} -> {consumer}"
            )


def _control_graph_sha256(protocol: dict[str, Any]) -> str:
    rows = []
    for operation in protocol["state_machines"]["control_operation"]["operations"]:
        for variant in operation["variants"]:
            rows.append(
                {
                    "operation_type": operation["operation_type"],
                    "operation_variant": variant["operation_variant"],
                    "initial_phase": variant["initial_phase"],
                    "committed_phase": variant["committed_phase"],
                    "terminal_outcomes": variant["terminal_outcomes"],
                    "phases": variant["phases"],
                    "success_edges": variant["success_edges"],
                    "phase_dependencies": variant["phase_dependencies"],
                }
            )
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
                {
                    "operation_variant",
                    "initial_phase",
                    "committed_phase",
                    "terminal_outcomes",
                    "phases",
                    "success_edges",
                    "phase_dependencies",
                },
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
            edges = _validate_terminating_graph(
                nodes=phases,
                edges=variant["success_edges"],
                initial=variant["initial_phase"],
                terminals=terminal_phases,
                context=f"control_operation.{operation_type}.{variant_name}",
                require_acyclic=True,
            )
            _validate_phase_dependencies(variant, edges, f"control_operation.{operation_type}.{variant_name}")
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
            "normal": "candidate_classified_in_normal_request_before_cas",
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
        "ExternalResourceReservationSnapshot",
        "SourceSnapshotProof",
        "TargetPreparationSnapshot",
        "ExternalConsumptionReleaseProof",
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
                "resolve_external_interrupt/recoverable_timeout",
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
                "resolve_external_interrupt/recoverable_timeout",
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

    resource = by_id["ExternalResourceReservationSnapshot"]
    if resource.get("settlement_mapping") != {
        "present": "settle_actual_or_maximum",
        "absent_before_reservation": "resource_settlement_not_applicable",
    }:
        raise ValidationError("ExternalResourceReservationSnapshot does not close pre-reservation interrupts")
    resource_variants = {variant["tag"]: variant for variant in resource["variants"]}
    expected_resource_variants = {
        "present": {
            "tag": "present",
            "required_fields": [
                "external_operation_id",
                "external_phase",
                "external_phase_revision",
                "external_lease_epoch",
                "reservation_id",
                "reservation_digest",
                "reservation_status",
                "reservation_binding_digest",
            ],
            "forbidden_fields": ["reservation_fields_are_null", "no_budget_event_proof"],
        },
        "absent_before_reservation": {
            "tag": "absent_before_reservation",
            "required_fields": [
                "external_operation_id",
                "external_phase",
                "external_phase_revision",
                "external_lease_epoch",
                "reservation_fields_are_null",
                "no_budget_event_proof",
            ],
            "forbidden_fields": [
                "reservation_id",
                "reservation_digest",
                "reservation_status",
                "reservation_binding_digest",
            ],
        },
    }
    if resource_variants != expected_resource_variants:
        raise ValidationError("ExternalResourceReservationSnapshot variants are incomplete")
    expected_resolution_binding = {
        "overlay_field": "exact_external_operation_resolution_tuple",
        "match_fields": [
            "external_operation_id",
            "external_phase",
            "external_phase_revision",
            "external_lease_epoch",
        ],
        "present_reservation_binding_digest_includes": [
            "external_operation_id",
            "reservation_id",
            "reservation_digest",
        ],
        "consumer_phase": "resource_disposition_committed",
    }
    if resource.get("resolution_tuple_binding") != expected_resolution_binding:
        raise ValidationError("ExternalResourceReservationSnapshot is not bound to its ExternalOperation tuple")
    expected_resource_bindings = {
        (
            "resolve_external_interrupt/recoverable_timeout",
            ("dispatch_authorized", "dispatch_receipt_committed"),
            ("present",),
        ),
        (
            "resolve_external_interrupt/controlled_halt",
            ("external_operation_reserved", "task_committed", "workspace_manifest_committed"),
            ("absent_before_reservation",),
        ),
        (
            "resolve_external_interrupt/controlled_halt",
            (
                "reservation_committed",
                "core_contract_committed",
                "workspace_materialized",
                "pause_bound",
                "dispatch_authorized",
                "dispatch_receipt_committed",
                "result_reference_committed",
            ),
            ("present",),
        ),
        (
            "resolve_external_interrupt/integrity_failure",
            ("external_operation_reserved", "task_committed", "workspace_manifest_committed"),
            ("absent_before_reservation",),
        ),
        (
            "resolve_external_interrupt/integrity_failure",
            (
                "reservation_committed",
                "core_contract_committed",
                "workspace_materialized",
                "pause_bound",
                "dispatch_authorized",
                "dispatch_receipt_committed",
                "result_reference_committed",
            ),
            ("present",),
        ),
    }
    actual_resource_bindings = {
        (
            binding["operation_variant"],
            tuple(binding["external_phases"]),
            tuple(binding["allowed_variants"]),
        )
        for binding in resource.get("reservation_phase_bindings", [])
    }
    if actual_resource_bindings != expected_resource_bindings:
        raise ValidationError("ExternalResourceReservationSnapshot phase/variant correlation is incomplete")
    source = by_id["SourceSnapshotProof"]
    source_variants = {variant["tag"]: variant for variant in source["variants"]}
    expected_source_variants = {
        "replay_root": {
            "tag": "replay_root",
            "required_fields": [
                "source_run_identity",
                "immutable_root_input",
                "root_input_digest",
                "source_schema",
                "runtime_fingerprint",
                "source_control_revision_proof",
            ],
            "forbidden_fields": [
                "source_run_status",
                "source_latest_heads",
                "source_control_revision",
                "source_revision_cas",
                "eligible_artifact_snapshot",
                "source_pause",
                "source_authorization",
                "source_accepted_status",
            ],
        },
        "fork_head": {
            "tag": "fork_head",
            "required_fields": [
                "source_run_identity",
                "source_schema",
                "source_run_status",
                "source_latest_heads",
                "source_control_revision",
                "source_control_revision_proof",
                "source_revision_cas",
                "eligible_artifact_snapshot",
            ],
            "forbidden_fields": [
                "immutable_root_input",
                "root_input_digest",
                "runtime_fingerprint",
                "source_pause",
                "source_authorization",
                "source_accepted_status",
            ],
        },
    }
    if source_variants != expected_source_variants:
        raise ValidationError("SourceSnapshotProof variants are incomplete or overlapping")
    if source.get("source_identity_binding") != {
        "request_field": "source_run_locator",
        "proof_field": "source_run_identity",
        "must_match": True,
        "lineage_digest_includes": [
            "source_run_identity",
            "source_snapshot_kind",
            "source_schema",
            "source_control_revision_proof",
        ],
    }:
        raise ValidationError("SourceSnapshotProof is not bound to its requested source Run and lineage digest")
    if source.get("fork_head_run_status_contract") != {
        "allowed_values": ["paused", "completed", "halted", "failed"],
        "paused_requires": [
            "latest_opened_unclaimed_pause_head",
            "public_paused_checkpoint",
            "run_terminal_closure_owner_is_null",
        ],
        "terminal_requires": ["latest_terminal_lifecycle_head", "terminal_closure_committed"],
        "forbidden_values": ["initializing", "running"],
    }:
        raise ValidationError("SourceSnapshotProof does not restrict fork to a stable paused or terminal head")
    expected_schema_revision_combinations = [
        {
            "source_snapshot_kind": "replay_root",
            "source_schema": "0.2",
            "source_control_revision_proof": "legacy_control_revision_not_applicable",
        },
        {
            "source_snapshot_kind": "replay_root",
            "source_schema": "0.3",
            "source_control_revision_proof": "versioned_control_revision_not_consumed_for_root_replay",
        },
        {
            "source_snapshot_kind": "replay_root",
            "source_schema": "0.4",
            "source_control_revision_proof": "versioned_control_revision_not_consumed_for_root_replay",
        },
        {
            "source_snapshot_kind": "fork_head",
            "source_schema": "0.3",
            "source_control_revision_proof": "exact_source_control_revision",
        },
        {
            "source_snapshot_kind": "fork_head",
            "source_schema": "0.4",
            "source_control_revision_proof": "exact_source_control_revision",
        },
    ]
    if source.get("valid_schema_revision_combinations") != expected_schema_revision_combinations:
        raise ValidationError("SourceSnapshotProof does not bind source schema to revision evidence")
    source_bindings = {
        (binding["operation_type"], tuple(binding["allowed_variants"]))
        for binding in by_id["SourceSnapshotProof"].get("consumer_bindings", [])
    }
    if source_bindings != {("replay_run", ("replay_root",)), ("fork_run", ("fork_head",))}:
        raise ValidationError("SourceSnapshotProof permits replay/fork evidence cross-use")


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
    if set(normal_guard["compare_fields"]) != resolution_fields | {"normal_candidate_digest"}:
        raise ValidationError("normal terminal CAS does not fence the resolution tuple and candidate digest")
    if normal_guard.get("required_candidate_proof_kind") != "safe_stop":
        raise ValidationError("normal terminal CAS accepts a candidate other than safe_stop")
    if normal_guard.get("candidate_authority") != "normal_finalization_request":
        raise ValidationError("normal candidate classification is stored on shared ExternalOperation state")
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
        "resolution_request_kind",
        "normal_candidate_digest_or_not_applicable",
        "resolution_kind",
        "interrupt_disposition",
        "proof_kind",
        "trusted_usage_and_integrity_evidence",
    } <= set(external_contracts["external_final_evidence_committed"]["required_evidence"]):
        raise ValidationError("external final evidence does not bind proof classification and resolution timing")
    final_branch = next(
        contract for contract in protocol["branch_contracts"] if contract["branch_id"] == "external_final_resolution"
    )
    expected_final_combinations = [
        {"resolution_request_kind": "normal_finalize"},
        {"resolution_request_kind": "cancel_intent"},
        {"resolution_request_kind": "interrupt_intent"},
    ]
    expected_final_cases = [
        {
            "when": {
                "resolution_request_kind": ["normal_finalize"],
            },
            "target": "$normal_target",
        },
        {
            "when": {
                "resolution_request_kind": ["cancel_intent"],
            },
            "target": "cancel_intent_committed",
        },
        {
            "when": {
                "resolution_request_kind": ["interrupt_intent"],
            },
            "target": "interrupt_stop_intent_committed",
        },
    ]
    if final_branch.get("valid_combinations") != expected_final_combinations:
        raise ValidationError("external final resolution permits an invalid contender request")
    if final_branch.get("cases") != expected_final_cases:
        raise ValidationError("external final resolution cases do not enforce proof classification timing")


def _validate_stop_route_contract(protocol: dict[str, Any]) -> None:
    expected = {'authority': 'coordinator_db',
 'trigger_precedence': ['explicit_pause_cancel',
                        'recoverable_external_timeout',
                        'terminal_system_stop',
                        'external_integrity_stop',
                        'standalone_terminal'],
 'trigger_classes': [{'trigger_class': 'explicit_pause_cancel',
                      'triggers': ['explicit_pause_cancel'],
                      'required_external_contexts': ['opened_cancelable_pause']},
                     {'trigger_class': 'recoverable_external_timeout',
                      'triggers': ['operation_timeout'],
                      'required_external_contexts': ['dispatched_external_operation_with_opened_external_result_pause']},
                     {'trigger_class': 'terminal_system_stop',
                      'triggers': ['aggregate_hard_limit', 'policy_stop', 'terminal_operator_stop'],
                      'required_external_contexts': ['live_external_operation',
                                                     'no_unresolved_external_operation',
                                                     'normal_terminal_attached_opened_pause']},
                     {'trigger_class': 'external_integrity_stop',
                      'triggers': ['proven_integrity_trigger', 'normal_finalization_unavailable'],
                      'required_external_contexts': ['live_external_operation']},
                     {'trigger_class': 'standalone_terminal',
                      'triggers': ['normal_end', 'non_pause_runtime_failure', 'internal_terminal_decision'],
                      'required_external_contexts': ['no_unresolved_external_operation']}],
 'routes': [{'external_context': 'opened_cancelable_pause',
             'trigger_class': 'explicit_pause_cancel',
             'operation_type': 'cancel_pause',
             'operation_variant': 'not_applicable'},
            {'external_context': 'dispatched_external_operation_with_opened_external_result_pause',
             'trigger_class': 'recoverable_external_timeout',
             'operation_type': 'resolve_external_interrupt',
             'operation_variant': 'recoverable_timeout'},
            {'external_context': 'live_external_operation',
             'trigger_class': 'terminal_system_stop',
             'operation_type': 'resolve_external_interrupt',
             'operation_variant': 'controlled_halt'},
            {'external_context': 'no_unresolved_external_operation',
             'trigger_class': 'terminal_system_stop',
             'operation_type': 'close_run',
             'operation_variant': 'not_applicable'},
            {'external_context': 'live_external_operation',
             'trigger_class': 'external_integrity_stop',
             'operation_type': 'resolve_external_interrupt',
             'operation_variant': 'integrity_failure'},
            {'external_context': 'no_unresolved_external_operation',
             'trigger_class': 'standalone_terminal',
             'operation_type': 'close_run',
             'operation_variant': 'not_applicable'},
            {'external_context': 'normal_terminal_attached_opened_pause',
             'trigger_class': 'terminal_system_stop',
             'operation_type': 'close_run',
             'operation_variant': 'not_applicable'}],
 'close_run_external_preconditions': ['absent',
                                      'safely_terminal_and_detached',
                                      'normal_safe_stop_attached_opened_pause'],
 'forbidden_routes': ['system_timeout_or_hard_limit_to_cancel_pause',
                      'live_external_operation_to_close_run',
                      'run_terminal_interrupt_owner_then_second_close_run'],
 'selection_rule': 'trigger_first_then_exactly_one_context_route_before_operation_reservation',
 'in_operation_failure_dispatch': {'before_new_operation_selection': True,
                                   'condition': 'same_live_external_result_resume_owns_claim_and_normal_external_final_before_release',
                                   'target_contract': 'consumption_failure_contract',
                                   'target_phase': 'consumption_failure_ownership_reserved',
                                   'new_operation': False,
                                   'original_trigger_identity_preserved': True}}
    contract = protocol.get("stop_route_contract")
    if contract != expected:
        raise ValidationError("stop route contract is incomplete, overlapping, or ambiguous")
    trigger_classes = {row["trigger_class"]: row for row in contract["trigger_classes"]}
    if len(trigger_classes) != len(contract["trigger_classes"]):
        raise ValidationError("stop route trigger class is duplicated")
    raw_triggers: set[str] = set()
    required_pairs: set[tuple[str, str]] = set()
    for row in contract["trigger_classes"]:
        triggers = _require_unique_strings(row["triggers"], f"stop route {row['trigger_class']} triggers")
        contexts = _require_unique_strings(
            row["required_external_contexts"], f"stop route {row['trigger_class']} contexts"
        )
        overlap = raw_triggers & set(triggers)
        if overlap:
            raise ValidationError(f"stop route raw trigger has multiple classes: {sorted(overlap)}")
        raw_triggers.update(triggers)
        required_pairs.update((row["trigger_class"], context) for context in contexts)

    seen_pairs: set[tuple[str, str]] = set()
    expanded_routes: set[tuple[str, str]] = set()
    control_variants = _control_variant_index(protocol)
    for route in contract["routes"]:
        pair = (route["operation_type"], route["operation_variant"])
        if pair not in control_variants:
            raise ValidationError(f"stop route references an unknown ControlOperation variant: {pair}")
        trigger_class = route["trigger_class"]
        if trigger_class not in trigger_classes:
            raise ValidationError(f"stop route references an unknown trigger class: {trigger_class}")
        class_context = (trigger_class, route["external_context"])
        if class_context in seen_pairs:
            raise ValidationError(f"stop route is not unique: {class_context}")
        seen_pairs.add(class_context)
        expanded_routes.update(
            (route["external_context"], trigger) for trigger in trigger_classes[trigger_class]["triggers"]
        )
    if seen_pairs != required_pairs:
        missing = sorted(required_pairs - seen_pairs)
        extra = sorted(seen_pairs - required_pairs)
        raise ValidationError(f"stop route totality mismatch; missing={missing}, extra={extra}")
    if len(expanded_routes) != sum(
        len(trigger_classes[route["trigger_class"]]["triggers"]) for route in contract["routes"]
    ):
        raise ValidationError("expanded stop routes overlap")
    close_run_triggers = {
        trigger
        for route in contract["routes"]
        if route["operation_type"] == "close_run"
        for trigger in trigger_classes[route["trigger_class"]]["triggers"]
    }
    direct_terminal_triggers = set(
        protocol["state_machines"]["control_operation"]["direct_terminal_resolution"][
            "close_run_trigger_to_run_status"
        ]
    )
    if close_run_triggers != direct_terminal_triggers:
        raise ValidationError("close_run routes and direct terminal dispositions do not share one trigger domain")


def _validate_consumption_release_and_recovery(protocol: dict[str, Any]) -> None:
    control = protocol["state_machines"]["control_operation"]
    expected = {'phase': 'external_consumption_released',
 'producers': [{'operation_type': 'resume_run',
                'operation_variant': 'continue_execution',
                'input': 'external_result',
                'resolution_owner': 'normal'},
               {'operation_type': 'resolve_external_interrupt',
                'operation_variant': 'recoverable_timeout',
                'input': 'recoverable_delivery',
                'resolution_owner': 'interrupt'}],
 'not_applicable_resume_reasons': ['human_input', 'recovery_decision'],
 'proof_fields': ['run_id',
                  'external_operation_id',
                  'external_final_digest',
                  'external_resolution_owner',
                  'consumption_operation_id',
                  'consumption_epoch',
                  'phase_revision',
                  'active_binding_generation',
                  'resource_settlement_digest',
                  'pause_consumed_head',
                  'terminal_code_attempt_head',
                  'canonical_code_artifact_head'],
 'preconditions': ['same_pause_consumption_owner',
                   'complete_safe_stop',
                   'settled_original_reservation',
                   'pause_consumed',
                   'original_code_attempt_finished',
                   'canonical_code_artifact_registered',
                   'current_heads_match_frozen_proof',
                   'no_conflicting_run_terminal_owner'],
 'atomic_effect': 'cas_exact_active_binding_generation_to_released_and_store_immutable_proof',
 'history_rule': 'retain_external_terminal_row_resolution_and_original_pause_binding_unchanged',
 'retry': 'same_identity_and_exact_proof_is_noop_conflicting_bytes_or_old_epoch_rejected',
 'later_operation_rule': 'new_external_operation_has_new_identity_and_binding_generation_never_reopens_released_binding',
 'ordering': 'release_before_consumption_final_checkpoint_and_outbound_code_transition',
 'close_admission': 'all_external_operations_safely_terminal_with_exact_release_or_close_disposition_proof_and_no_active_binding',
 'normal_resume_race': 'stop_loses_claim_cas_then_reclassifies_only_after_durable_release_at_next_trusted_boundary',
 'recoverable_interrupt_rule': 'external_resolution_owner_is_not_run_terminal_owner_later_independent_close_allowed_after_release',
 'failure': 'uncertain_or_conflicting_release_blocks_advance_and_close_no_fabricated_detachment',
 'active_binding_origin': 'coordinator_projection_created_with_one_time_pause_binding_initial_generation_one',
 'not_applicable_guard': 'exact_reserved_pause_reason_human_input_or_recovery_decision_no_external_consumption',
 'proof_union': 'ExternalConsumptionReleaseProof'}
    if control.get("external_consumption_release_contract") != expected:
        raise ValidationError("external_consumption_release_contract loses its exact ownership or scope boundary")
    expected = {'validation_phase': 'resume_disposition_committed',
 'before_phase': 'pause_ownership_reserved',
 'continue_existing_target': {'allowed_target_kinds': ['method_planner',
                                                       'analysis_engineer',
                                                       'scientific_reviewer',
                                                       'decision_coordinator',
                                                       'human_gate',
                                                       'memory_report'],
                              'required': ['scheduled_never_started',
                                           'unique_committed_inbound_transition',
                                           'exact_heads',
                                           'no_side_effects',
                                           'no_unsettled_resource',
                                           'no_external_operation',
                                           'original_target_preparation_proof_if_analysis_requires_it'],
                              'scope': 'attempt_execution'},
 'rejected_target_kinds': ['code_agent', 'legacy_codex_handoff'],
 'rejection': 'before_pause_claim_no_capability_no_backend_no_attempt_started',
 'code_agent_disposition': 'explicit_abandon_and_halt_only_no_automatic_action_or_scope_escalation',
 'null_target_disposition': 'abandon_and_halt_only',
 'external_result': 'exact_scheduled_code_agent_with_normal_delivery_preflight_and_settlement',
 'human_input': 'new_human_gate_validation_attempt_only',
 'abandon_and_halt': 'no_invocation_for_any_target_kind'}
    if control.get("recovery_target_authorization_contract") != expected:
        raise ValidationError("recovery_target_authorization_contract loses its exact ownership or scope boundary")
    expected_union = {'union_id': 'ExternalConsumptionReleaseProof',
 'evidence_field': 'external_consumption_release_proof',
 'tag_field': 'release_kind',
 'variants': [{'tag': 'external_consumed',
               'required_fields': ['run_id',
                                   'external_operation_id',
                                   'external_final_digest',
                                   'external_resolution_owner',
                                   'consumption_operation_id',
                                   'consumption_epoch',
                                   'phase_revision',
                                   'active_binding_generation',
                                   'resource_settlement_digest',
                                   'pause_consumed_head',
                                   'terminal_code_attempt_head',
                                   'canonical_code_artifact_head'],
               'forbidden_fields': ['not_applicable_reason']},
              {'tag': 'not_applicable',
               'required_fields': ['not_applicable_reason'],
               'forbidden_fields': ['run_id',
                                    'external_operation_id',
                                    'external_final_digest',
                                    'external_resolution_owner',
                                    'consumption_operation_id',
                                    'consumption_epoch',
                                    'phase_revision',
                                    'active_binding_generation',
                                    'resource_settlement_digest',
                                    'pause_consumed_head',
                                    'terminal_code_attempt_head',
                                    'canonical_code_artifact_head']}],
 'consumer_bindings': [{'machine': 'control_operation',
                        'operation_type': 'resume_run',
                        'operation_variant': 'continue_execution',
                        'phase': 'external_consumption_released',
                        'incoming_phase': 'invocation_authorized',
                        'allowed_variants': ['external_consumed', 'not_applicable']},
                       {'machine': 'control_operation',
                        'operation_type': 'resolve_external_interrupt',
                        'operation_variant': 'recoverable_timeout',
                        'phase': 'external_consumption_released',
                        'incoming_phase': 'interrupted_code_attempt_finished',
                        'allowed_variants': ['external_consumed']}]}
    actual_union = next(u for u in protocol["evidence_unions"] if u["union_id"] == "ExternalConsumptionReleaseProof")
    if actual_union != expected_union:
        raise ValidationError("consumption release proof permits wrong reason, owner or N/A evidence")
    variants = _control_variant_index(protocol)
    for key, before, after in [
        (("resume_run", "continue_execution"), "invocation_authorized", "stable_boundary_committed"),
        (("resolve_external_interrupt", "recoverable_timeout"), "interrupted_code_attempt_finished", "interrupted_code_checkpoint_committed"),
    ]:
        outgoing: dict[str, set[str]] = {}
        for source, target in variants[key]["success_edges"]:
            outgoing.setdefault(source, set()).add(target)
        if outgoing.get(before) != ({"external_consumption_released", "consumption_failure_ownership_reserved"} if key == ("resume_run", "continue_execution") else {"external_consumption_released"}) or outgoing.get("external_consumption_released") != {after}:
            raise ValidationError(f"{key}: consumption bypasses binding release")
    if "reason_target_scope_preflight_proof" not in control["phase_contracts"]["resume_disposition_committed"]["required_evidence"]:
        raise ValidationError("recovery scope must be validated before claiming Pause")
    expected_phase = {'authorities': ['coordinator_db'],
 'effect_class': 'deterministic_publication',
 'continuation_policy': 'materialize_if_precomputed',
 'required_evidence': ['external_consumption_release_proof', 'same_consumption_owner_current_epoch'],
 'acquires': []}
    if control["phase_contracts"]["external_consumption_released"] != expected_phase:
        raise ValidationError("consumption release loses its evidence or epoch fence")


def _validate_consumption_failure(protocol: dict[str, Any]) -> None:
    control = protocol["state_machines"]["control_operation"]
    required_safety_rules = {
 'external_resolution': 'normal_final_immutable',
 'entry_rule': 'trusted_failure_at_current_phase_revision_before_successor_commit_nonexternal_reasons_continue_only',
 'snapshot_fields': ['failure_id_digest',
                     'source_phase_revision',
                     'source_resume_owner_epoch',
                     'pause_identity_status_and_claim_owner',
                     'attempt_identity_status_and_started_intent',
                     'original_normal_final_digest',
                     'last_trusted_execution_artifact_checkpoint_heads',
                     'pending_resource_operation_ids_and_settlement_snapshots',
                     'artifact_registration_forbidden_or_exact_existing_audit_snapshot',
                     'active_binding_generation',
                     'terminal_disposition_contract_digest'],
 'atomic_ownership': ['compare_same_live_resume_epoch_and_pause_claim_owner',
                      'cas_empty_run_terminal_owner_to_same_resume',
                      'increment_terminal_closure_revision',
                      'revoke_invocation_epoch',
                      'freeze_failure_snapshot_and_single_failure_intent'],
 'normal_worker_fence': 'every_successor_and_effect_commit_compares_phase_revision_epoch_and_no_failure_intent',
 'stop_scope': 'consumer_verifier_processes_provider_tools_workspace_writes_and_output_readers_not_original_terminal_backend',
 'safe_attempt_disposition': {'scheduled': 'abandoned',
                              'running': 'failed',
                              'terminal': 'retain_exact_existing_terminal_record'},
 'safe_pause_disposition': {'opened_claim_owned': 'interrupted',
                            'claimed': 'interrupted',
                            'consumed': 'retain_consumed_no_second_event'},
 'artifact_rule': 'never_register_invalid_code_result_existing_bytes_quarantined_as_audit_only',
 'resource_rule': 'reuse_existing_settlement_identity_no_double_charge_settle_pending_consumer_resources_once',
 'safe_binding_release': 'same_owner_failure_proof_releases_projection_with_typed_artifact_absence_no_normal_release_proof',
 'unavailable_rule': 'same_owner_tombstone_and_quarantine_no_run_lifecycle_no_safe_detachment',
 'safe_tail': ['consumption_failure_disposition_committed',
               'terminal_eligibility_verified',
               'terminal_lifecycle_recorded',
               'terminal_checkpoint_committed',
               'result_committed'],
 'run_status': 'failed',
 'result_semantics': 'committed_control_result_reports_failed_run_not_successful_domain_consumption',
 'forbidden': ['new_close_run',
               'new_external_interrupt',
               'external_resolution_rewrite',
               'synthetic_code_artifact_for_integrity_failure',
               'reopen_consumed_pause',
               'target_retry',
               'resume_success_suffix_after_failure_intent'],
 'recovery': 'same_owner_current_epoch_materializes_exact_frozen_suffix_only_no_verifier_reexecution',
 'unappendable_control_authority': 'stop_and_quarantine_no_claim_of_durable_closure',
 'after_normal_release': 'use_existing_detached_close_run_path_not_embedded_failure_tail',
 'stop_protocol': ['persist_exact_consumer_stop_intent',
                   'revoke_and_fence',
                   'graceful_cancel',
                   'bounded_grace',
                   'containment_kill_all',
                   'bounded_output_drain',
                   'verify_empty_and_post_stop_stability'],
 'stop_retry': 'same_consumer_resource_identity_idempotent_stop_or_lookup_only_never_redispatch',
 'terminal_resolution': 'terminal_eligibility_resolves_failed_once_from_safe_failure_contract_unavailable_has_no_run_status',
 'failure_artifact_cases': [{'tag': 'registration_forbidden',
                             'artifact_head': None,
                             'requires': 'trusted_rejection_digest_and_no_new_registration'},
                            {'tag': 'already_registered_audit_only',
                             'artifact_head': 'exact_preexisting_head',
                             'requires': 'preserve_registry_history_quarantine_bytes_no_promotion'}],
 'boundary_commit_rule': 'continue_verdict_commits_atomically_with_successor_phase_revision_failure_intent_cas_wins_only_while_source_revision_current'}
    contract = control["consumption_failure_contract"]
    if {key: contract.get(key) for key in required_safety_rules} != required_safety_rules:
        raise ValidationError("consumption failure loses its ownership, stop or disposition contract")
    normal = ['operation_reserved', 'resume_disposition_committed', 'pause_ownership_reserved', 'pause_claimed_recorded', 'prestart_records_committed', 'pause_consumed_recorded', 'running_lifecycle_recorded', 'resume_checkpoint_committed', 'invocation_authorized', 'external_consumption_released', 'stable_boundary_committed', 'result_committed']
    failure = ['consumption_failure_ownership_reserved', 'consumption_failure_stop_verified', 'consumption_failure_classified', 'consumption_failure_disposition_committed', 'terminal_eligibility_verified', 'terminal_lifecycle_recorded', 'terminal_checkpoint_committed', 'consumption_failure_unavailable_recorded']
    entries = normal[2:9]
    if (
        contract["operation"] != "resume_run/continue_execution"
        or contract["input_reason"] != "external_result"
        or contract["entry_phases"] != entries
        or contract["entry_branch_ids"] != ["resume_failure_at_" + phase for phase in entries]
        or [contract[key] for key in ["ownership_phase", "stop_phase", "classification_phase"]] != failure[:3]
    ):
        raise ValidationError("consumption failure metadata is detached from its graph")
    edges = [list(pair) for pair in zip(normal, normal[1:])]
    dependencies = [{"producer_phase": a, "consumer_phase": b} for a, b in edges]
    for row in dependencies:
        if row["consumer_phase"] == "result_committed":
            row["producer_phase"] = "pause_ownership_reserved"
    branches = []
    for source in entries:
        target = normal[normal.index(source) + 1]
        field = "consumption_outcome_at_" + source
        edges.append([source, failure[0]])
        branches.append({
            "branch_id": "resume_failure_at_" + source, "machine": "control_operation",
            "operation_type": "resume_run", "operation_variant": "continue_execution",
            "source_phase": source,
            "discriminants": [{"field": field, "values": ["continue", "consumption_failure"],
                "binding": "immutable_at_exact_phase_revision_boundary_result", "authority": "coordinator_db"}],
            "valid_combinations": [{field: "continue"}, {field: "consumption_failure"}],
            "cases": [{"when": {field: ["continue"]}, "target": target},
                      {"when": {field: ["consumption_failure"]}, "target": failure[0]}],
        })
    tail_edges = [list(pair) for pair in zip(failure[:7], failure[1:7])]
    tail_edges.insert(3, [failure[2], failure[-1]])
    tail_edges.append(["terminal_checkpoint_committed", "result_committed"])
    edges.extend(tail_edges)
    dependencies.extend({"producer_phase": a, "consumer_phase": b} for a, b in
        [("pause_ownership_reserved", failure[0]), *zip(failure[:7], failure[1:7]), (failure[2], failure[-1])])
    expected_variant = {
        "operation_variant": "continue_execution", "initial_phase": "operation_reserved",
        "committed_phase": "result_committed",
        "terminal_outcomes": [
            {"phase": "result_committed", "status": "committed", "proof_kind": "committed_result"},
            {"phase": failure[-1], "status": "recovery_required", "proof_kind": "consumer_stop_or_authority_unavailable"}],
        "phases": normal + failure, "success_edges": edges, "phase_dependencies": dependencies,
    }
    actual = _control_variant_index(protocol)[("resume_run", "continue_execution")]
    if actual != expected_variant:
        raise ValidationError("resume consumption failure graph bypasses its frozen publication order")
    branches.append({'branch_id': 'resume_consumption_failure_outcome',
 'machine': 'control_operation',
 'operation_type': 'resume_run',
 'operation_variant': 'continue_execution',
 'source_phase': 'consumption_failure_classified',
 'discriminants': [{'field': 'consumption_failure_outcome',
                    'values': ['failed_closure', 'unavailable_closure'],
                    'binding': 'immutable_at_consumption_failure_classified',
                    'authority': 'coordinator_db'}],
 'valid_combinations': [{'consumption_failure_outcome': 'failed_closure'},
                        {'consumption_failure_outcome': 'unavailable_closure'}],
 'cases': [{'when': {'consumption_failure_outcome': ['failed_closure']},
            'target': 'consumption_failure_disposition_committed'},
           {'when': {'consumption_failure_outcome': ['unavailable_closure']},
            'target': 'consumption_failure_unavailable_recorded'}]})
    actual_branches = [b for b in protocol["branch_contracts"]
        if b["branch_id"].startswith("resume_failure_at_") or b["branch_id"] == "resume_consumption_failure_outcome"]
    if actual_branches != branches:
        raise ValidationError("consumption failure branching is not total or immutable at the boundary")
    expected_phases = {'consumption_failure_ownership_reserved': {'authorities': ['coordinator_db'],
                                            'effect_class': 'authority_reservation',
                                            'continuation_policy': 'materialize_if_precomputed',
                                            'required_evidence': ['same_in_progress_external_result_resume_and_pause_claim_owner',
                                                                  'exact_source_phase_revision_and_current_epoch',
                                                                  'trusted_failure_intent_and_last_trusted_heads',
                                                                  'empty_run_terminal_owner_cas',
                                                                  'frozen_failure_snapshot_and_disposition_contract',
                                                                  'invocation_epoch_revoked_before_further_effects',
                                                                  'precomputed_consumer_stop_intent_bound_to_original_resource_ids'],
                                            'acquires': ['run_terminal_closure_owner'],
                                            'atomic_acquire': True,
                                            'transaction_domain': 'coordinator_sqlite'},
 'consumption_failure_stop_verified': {'authorities': ['coordinator_db'],
                                       'effect_class': 'external_effect_observation',
                                       'continuation_policy': 'lookup_only_after_uncertain_effect',
                                       'required_evidence': ['same_failure_owner',
                                                             'original_external_normal_final_digest_unchanged',
                                                             'consumer_verifier_containment_stop_and_write_fence_proof',
                                                             'all_pending_resource_usage_or_conservative_charge',
                                                             'run_authority_integrity_proof_or_unavailable'],
                                       'acquires': []},
 'consumption_failure_classified': {'authorities': ['coordinator_db'],
                                    'effect_class': 'verification',
                                    'continuation_policy': 'materialize_if_precomputed',
                                    'required_evidence': ['consumer_failure_stop_proof',
                                                          'run_authority_classification',
                                                          'consumption_failure_outcome'],
                                    'acquires': [],
                                    'resolves_once': ['consumption_failure_outcome']},
 'consumption_failure_disposition_committed': {'authorities': ['coordinator_db',
                                                               'execution_ledger',
                                                               'budget_ledger'],
                                               'effect_class': 'deterministic_publication',
                                               'continuation_policy': 'materialize_if_precomputed',
                                               'required_evidence': ['same_failure_run_and_pause_owner',
                                                                     'safe_consumer_stop_and_intact_run_authority',
                                                                     'frozen_attempt_disposition_and_artifact_absence_or_existing_audit_snapshot',
                                                                     'exact_pending_resource_settlements',
                                                                     'pause_finality_preserving_disposition',
                                                                     'active_binding_failure_release_proof',
                                                                     'failed_disposition_contract_and_exact_preclose_heads'],
                                               'acquires': []},
 'consumption_failure_unavailable_recorded': {'authorities': ['coordinator_db'],
                                              'effect_class': 'terminal_publication',
                                              'continuation_policy': 'no_continuation_after_terminal',
                                              'required_evidence': ['same_failure_run_owner',
                                                                    'consumer_stop_or_run_authority_unavailable',
                                                                    'immutable_failure_tombstone_with_conservative_resource_charges',
                                                                    'active_binding_quarantined_not_safely_detached',
                                                                    'no_fabricated_run_lifecycle_or_code_artifact'],
                                              'acquires': []}}
    if {k: control["phase_contracts"].get(k) for k in expected_phases} != expected_phases:
        raise ValidationError("consumption failure phases lose their exact evidence and owner fences")
    # Independently exercise every failure entry against the stop/authority matrix.
    # Only safe stop plus appendable authority may publish the failed Run lifecycle.
    outcomes = {}
    for row in contract["classification"]:
        key = (row["consumer_stop"], row["run_authority"])
        if key in outcomes:
            raise ValidationError("duplicate consumption failure classification")
        outcomes[key] = row["outcome"]
    domain = {(stop, authority) for stop in ["safe_stop", "unavailable"] for authority in ["appendable", "unavailable"]}
    if set(outcomes) != domain:
        raise ValidationError("consumption failure classification is not exhaustive")
    for key, outcome in outcomes.items():
        safe = key == ("safe_stop", "appendable")
        if outcome != ("failed_closure" if safe else "unavailable_closure"):
            raise ValidationError("unsafe consumer stop or authority permits a failed Run lifecycle")
        for entry in entries:
            path = [entry, *failure[:3]]
            path += contract["safe_tail"] if safe else [failure[-1]]
            if any([a, b] not in actual["success_edges"] for a, b in zip(path, path[1:])):
                raise ValidationError("consumption failure has no legal publication path")
            if not safe and "terminal_lifecycle_recorded" in path:
                raise ValidationError("unavailable consumer failure publishes a Run lifecycle")
    if ["claimed", "interrupted"] not in protocol["state_machines"]["pause_lifecycle"]["allowed_edges"]:
        raise ValidationError("claimed failure cannot safely terminate its Pause")


def _validate_target_execution_paths(protocol: dict[str, Any]) -> None:
    control = protocol["state_machines"]["control_operation"]
    variants = _control_variant_index(protocol)
    expected = {'owner': 'advance_run/not_applicable',
 'freeze_phase': 'operation_reserved',
 'snapshot_union': 'TargetPreparationSnapshot',
 'required_when': 'target_analysis_engineer_and_selected_current_code_bundle_present',
 'not_applicable_when': 'other_target_or_analysis_without_selected_code_bundle',
 'producer_phase': 'target_preparation_committed',
 'capability_consumer': 'invocation_capability_prepared',
 'bindings': ['target_attempt_identity_matches_reserved_target',
              'inbound_transition_identity_matches_reserved_transition',
              'spec_and_manifest_bytes_match_digests',
              'source_code_bundle_and_base_change_runtime_match_frozen_source'],
 'publication_order': ['exclusive_create_spec_and_sync',
                       'materialize_fresh_base_and_apply_verified_change',
                       'verify_manifest_and_effective_tree_digest',
                       'sync_workspace_and_commit_preparation_proof'],
 'fence': 'current_advance_operation_epoch_and_terminal_closure_revision',
 'forbidden_effects': ['repository_code_execution',
                       'analysis_subprocess_start',
                       'domain_artifact_registration',
                       'target_attempt_started',
                       'external_operation_creation'],
 'crash_recovery': 'same_advance_current_epoch_materializes_only_frozen_exact_prefix_no_route_reselection',
 'conflict': 'quarantine_and_integrity_outcome_no_capability_activation',
 'head_rule': 'control_audit_files_only_execution_and_artifact_heads_unchanged',
 'checkpoint_rule': 'execution_authorization_requires_preparation_proof_bound_to_target_and_manifest'}
    if control.get("target_preparation_contract") != expected:
        raise ValidationError("target_preparation_contract loses its exact execution boundary")
    expected = {'owner': 'resolve_external_interrupt/recoverable_timeout',
 'required_outcome': 'recoverable_delivery',
 'consumer': 'consume_code_agent_result',
 'attempt_kind': 'code_agent',
 'attempt_status_sequence': ['scheduled', 'running', 'failed'],
 'result': {'status': 'failed',
            'usable': False,
            'cause': 'operation_timeout',
            'verification_status': 'not_run',
            'change_promotion': 'forbidden',
            'failure_class': 'timeout'},
 'result_authority': 'trusted_host_safe_stop_timeout_evidence_not_backend_claim',
 'freeze_phase': 'canonical_failed_delivery_committed',
 'publication_order': ['resume_checkpoint_committed',
                       'interrupted_code_invocation_authorized',
                       'interrupted_code_attempt_started',
                       'interrupted_code_result_registered',
                       'interrupted_code_attempt_finished',
                       'external_consumption_released',
                       'interrupted_code_checkpoint_committed',
                       'result_committed'],
 'forbidden_effects': ['backend_dispatch',
                       'backend_retry',
                       'provider_call',
                       'verification_command',
                       'coordinator_invocation',
                       'outbound_transition'],
 'recovery': 'same_interrupt_current_epoch_materializes_precomputed_result_lifecycle_checkpoint_suffix_only_no_consumer_reexecution',
 'uncertain_or_conflicting_prefix': 'terminal_recovery_required_or_integrity_failure_no_advance',
 'handoff_requires': ['same_interrupt_committed_result',
                      'source_code_attempt_failed',
                      'canonical_failed_code_artifact',
                      'exact_final_checkpoint_heads',
                      'external_consumption_release_proof'],
 'next_operation': 'advance_run/not_applicable',
 'next_target': 'decision_coordinator',
 'result_source_contract': {'origin': 'host_timeout',
                            'requires': ['same_interrupt_winner',
                                         'external_final_safe_stop_digest',
                                         'trusted_usage_integrity_evidence',
                                         'task_and_workspace_manifest_digests',
                                         'exact_original_code_attempt'],
                            'required_members': ['code_agent_task.json',
                                                 'code_agent_result.json',
                                                 'workspace_manifest.json',
                                                 'interrupt_evidence.json',
                                                 'change_manifest.json',
                                                 'verification_results.json'],
                            'forbidden_members': ['workspace_seal.json', 'tool_audit.jsonl', 'changes.patch'],
                            'receipt': 'present_exact_original_or_typed_absent_before_receipt_commit_bound_to_dispatch_phase',
                            'change_manifest': 'empty_no_workspace_promotion',
                            'verification': 'each_required_spec_not_run_with_operation_timeout_reason',
                            'backend_output_references': 'typed_not_applicable_host_timeout_never_fabricated',
                            'scope': 'only_recoverable_delivery_with_complete_trusted_safe_stop_evidence'}}
    if control.get("recoverable_code_consumption_contract") != expected:
        raise ValidationError("recoverable_code_consumption_contract loses its exact execution boundary")
    expected_snapshot = {'union_id': 'TargetPreparationSnapshot',
 'evidence_field': 'target_preparation_snapshot',
 'tag_field': 'preparation_kind',
 'variants': [{'tag': 'analysis_fresh',
               'required_fields': ['target_attempt_identity',
                                   'inbound_transition_identity',
                                   'analysis_execution_spec_id',
                                   'canonical_spec_bytes',
                                   'spec_digest',
                                   'fresh_workspace_identity',
                                   'canonical_workspace_manifest_bytes',
                                   'workspace_manifest_digest',
                                   'source_code_bundle_id_digest',
                                   'base_revision_tree',
                                   'verified_change_digest',
                                   'expected_effective_tree_digest',
                                   'runtime_policy_digest'],
               'forbidden_fields': ['not_applicable_reason']},
              {'tag': 'not_applicable',
               'required_fields': ['not_applicable_reason'],
               'forbidden_fields': ['target_attempt_identity',
                                    'inbound_transition_identity',
                                    'analysis_execution_spec_id',
                                    'canonical_spec_bytes',
                                    'spec_digest',
                                    'fresh_workspace_identity',
                                    'canonical_workspace_manifest_bytes',
                                    'workspace_manifest_digest',
                                    'source_code_bundle_id_digest',
                                    'base_revision_tree',
                                    'verified_change_digest',
                                    'expected_effective_tree_digest',
                                    'runtime_policy_digest']}],
 'consumer_bindings': [{'machine': 'control_operation',
                        'operation_type': 'advance_run',
                        'operation_variant': 'not_applicable',
                        'phase': 'target_preparation_committed',
                        'incoming_phase': 'transition_heads_verified',
                        'allowed_variants': ['analysis_fresh', 'not_applicable']}]}
    snapshot = next(u for u in protocol["evidence_unions"] if u["union_id"] == "TargetPreparationSnapshot")
    if snapshot != expected_snapshot:
        raise ValidationError("target preparation snapshot loses target, bytes or typed N/A binding")
    for key, order in [
        (("advance_run", "not_applicable"), ["target_preparation_committed", "invocation_capability_prepared", "result_committed"]),
        (("resolve_external_interrupt", "recoverable_timeout"), control["recoverable_code_consumption_contract"]["publication_order"]),
    ]:
        variant = variants[key]
        outgoing: dict[str, set[str]] = {}
        for source, target in variant["success_edges"]:
            outgoing.setdefault(source, set()).add(target)
        for source, target in zip(order, order[1:]):
            if outgoing.get(source) != {target}:
                raise ValidationError(f"{key}: execution publication can bypass {source} -> {target}")
    contracts = control["phase_contracts"]
    expected_phase = {'authorities': ['coordinator_db', 'run_filesystem', 'workspace'],
 'effect_class': 'deterministic_publication',
 'continuation_policy': 'materialize_if_precomputed',
 'required_evidence': ['target_preparation_snapshot',
                       'exact_committed_transition_and_scheduled_target',
                       'current_advance_epoch_and_terminal_revision',
                       'spec_manifest_bytes_and_effective_tree_verified_or_not_applicable',
                       'unchanged_execution_artifact_heads'],
 'acquires': []}
    if contracts["target_preparation_committed"] != expected_phase:
        raise ValidationError("target_preparation_committed loses its producer evidence or side-effect fence")
    expected_phase = {'authorities': ['coordinator_db', 'execution_ledger'],
 'effect_class': 'deterministic_publication',
 'continuation_policy': 'materialize_if_precomputed',
 'required_evidence': ['safe_stop_final_evidence',
                       'canonical_failed_code_agent_delivery',
                       'exact_opened_external_result_pause',
                       'precomputed_failed_result_bytes_digest_and_attempt_completion',
                       'trusted_safe_timeout_classification'],
 'acquires': []}
    if contracts["canonical_failed_delivery_committed"] != expected_phase:
        raise ValidationError("canonical_failed_delivery_committed loses its producer evidence or side-effect fence")
    expected_phase = {'authorities': ['coordinator_db'],
 'effect_class': 'capability_publication',
 'continuation_policy': 'materialize_if_precomputed',
 'required_evidence': ['same_interrupt_winner',
                       'resolved_outcome_recoverable_delivery',
                       'scheduled_code_attempt',
                       'running_checkpoint_head',
                       'canonical_failed_delivery_digest',
                       'invocation_authorization_and_lease'],
 'acquires': []}
    if contracts["interrupted_code_invocation_authorized"] != expected_phase:
        raise ValidationError("interrupted_code_invocation_authorized loses its producer evidence or side-effect fence")
    expected_phase = {'authorities': ['coordinator_db', 'execution_ledger'],
 'effect_class': 'deterministic_publication',
 'continuation_policy': 'materialize_if_precomputed',
 'required_evidence': ['same_interrupt_winner',
                       'exact_code_target_authorization',
                       'invocation_started_intent',
                       'exact_a02_started_record'],
 'acquires': []}
    if contracts["interrupted_code_attempt_started"] != expected_phase:
        raise ValidationError("interrupted_code_attempt_started loses its producer evidence or side-effect fence")
    expected_phase = {'authorities': ['coordinator_db', 'artifact_registry', 'run_filesystem'],
 'effect_class': 'deterministic_publication',
 'continuation_policy': 'materialize_if_precomputed',
 'required_evidence': ['same_interrupt_winner',
                       'a02_started_head',
                       'precomputed_failed_result_bytes_digest_and_attempt_completion',
                       'validated_failed_code_artifact_registration'],
 'acquires': []}
    if contracts["interrupted_code_result_registered"] != expected_phase:
        raise ValidationError("interrupted_code_result_registered loses its producer evidence or side-effect fence")
    expected_phase = {'authorities': ['coordinator_db', 'execution_ledger'],
 'effect_class': 'deterministic_publication',
 'continuation_policy': 'materialize_if_precomputed',
 'required_evidence': ['same_interrupt_winner',
                       'failed_code_artifact_head',
                       'exact_code_attempt_failed_record',
                       'no_outbound_transition'],
 'acquires': []}
    if contracts["interrupted_code_attempt_finished"] != expected_phase:
        raise ValidationError("interrupted_code_attempt_finished loses its producer evidence or side-effect fence")
    expected_phase = {'authorities': ['checkpoint_store'],
 'effect_class': 'deterministic_publication',
 'continuation_policy': 'materialize_if_precomputed',
 'required_evidence': ['failed_code_attempt_head',
                       'failed_code_artifact_head',
                       'running_lifecycle_head',
                       'consumed_pause_head'],
 'acquires': []}
    if contracts["interrupted_code_checkpoint_committed"] != expected_phase:
        raise ValidationError("interrupted_code_checkpoint_committed loses its producer evidence or side-effect fence")


def _validate_publication_order(protocol: dict[str, Any]) -> None:
    variants = _control_variant_index(protocol)
    milestones = {
        ("start_run", "not_applicable"): ["operation_reserved", "run_root_created", "policy_published", "run_ledger_started", "bootstrap_records_complete", "running_lifecycle_recorded", "checkpoint_committed", "invocation_capability_prepared", "result_committed"],
        ("publish_pause", "not_applicable"): ["operation_reserved", "pause_prepared_recorded", "pause_dependencies_bound", "prepared_checkpoint_committed", "paused_lifecycle_recorded", "pause_opened_recorded", "public_paused_checkpoint_committed", "result_committed"],
        ("resume_run", "abandon_and_halt"): ["operation_reserved", "resume_disposition_committed", "pause_and_terminal_ownership_reserved", "pause_claimed_recorded", "pause_consumed_recorded", "target_disposition_committed", "resource_disposition_committed", "terminal_eligibility_verified", "terminal_lifecycle_recorded", "terminal_checkpoint_committed", "result_committed"],
        ("close_run", "not_applicable"): ["operation_reserved", "terminal_ownership_reserved", "resource_disposition_committed", "close_source_disposition_committed", "terminal_eligibility_verified", "terminal_lifecycle_recorded", "terminal_checkpoint_committed", "result_committed"],
    }
    for operation in ["replay_run", "fork_run"]:
        milestones[(operation, "not_applicable")] = ["operation_reserved", "source_snapshot_committed", "child_run_root_created", "child_policy_published", "child_run_ledger_started", "child_lineage_recorded", "child_bootstrap_records_complete", "child_running_lifecycle_recorded", "child_checkpoint_committed", "invocation_capability_prepared", "result_committed"]
    for pair, order in milestones.items():
        variant = variants[pair]
        if variant["initial_phase"] != order[0] or variant["committed_phase"] != order[-1]:
            raise ValidationError(f"{pair} publication endpoints differ from the contract")
        adjacency = {phase: set() for phase in variant["phases"]}
        for source, target in variant["success_edges"]:
            if source not in adjacency or target not in adjacency:
                raise ValidationError(f"{pair} publication edge references an unknown phase")
            adjacency[source].add(target)
        if not set(order) <= set(adjacency):
            raise ValidationError(f"{pair} is missing a required publication milestone")
        if not set(order) <= _reachable(order[0], adjacency):
            raise ValidationError(f"{pair} has an unreachable publication milestone")
        for producer, consumer in zip(order, order[1:]):
            # Each safety producer must dominate its consumer, even when a
            # candidate changes both the graph and its dependency declarations.
            reachable = {variant["initial_phase"]} - {producer}
            while True:
                expanded = reachable | {target for source in reachable for target in adjacency[source] if target != producer}
                if expanded == reachable:
                    break
                reachable = expanded
            if consumer in reachable:
                raise ValidationError(f"{pair} publication order bypasses {producer} before {consumer}")


def _validate_advance_and_interrupt_contracts(protocol: dict[str, Any]) -> None:
    _validate_publication_order(protocol)
    variants = _control_variant_index(protocol)
    advance = variants[("advance_run", "not_applicable")]
    expected_advance_phases = {'budget_decision_committed',
 'invocation_capability_prepared',
 'operation_reserved',
 'result_committed',
 'route_prerequisites_committed',
 'target_artifacts_invalidated',
 'target_attempt_scheduled',
 'target_preparation_committed',
 'terminal_transition_committed',
 'transition_committed',
 'transition_heads_verified',
 'transition_target_classified'}
    expected_advance_edges = {('budget_decision_committed', 'transition_target_classified'),
 ('invocation_capability_prepared', 'result_committed'),
 ('operation_reserved', 'budget_decision_committed'),
 ('route_prerequisites_committed', 'target_attempt_scheduled'),
 ('target_artifacts_invalidated', 'transition_committed'),
 ('target_attempt_scheduled', 'target_artifacts_invalidated'),
 ('target_preparation_committed', 'invocation_capability_prepared'),
 ('terminal_transition_committed', 'transition_heads_verified'),
 ('transition_committed', 'transition_heads_verified'),
 ('transition_heads_verified', 'result_committed'),
 ('transition_heads_verified', 'target_preparation_committed'),
 ('transition_target_classified', 'route_prerequisites_committed'),
 ('transition_target_classified', 'terminal_transition_committed')}
    if set(advance["phases"]) != expected_advance_phases or {
        tuple(edge) for edge in advance["success_edges"]
    } != expected_advance_edges:
        raise ValidationError("advance_run does not preserve target allocation, invalidation, Transition, and capability order")

    contracts = protocol["state_machines"]["control_operation"]["phase_contracts"]
    if not {
        "frozen_budget_decision",
        "grant_consumed_or_not_applicable",
        "exact_source_heads",
    } <= set(contracts["budget_decision_committed"]["required_evidence"]):
        raise ValidationError("advance_run budget phase does not bind admission and grant consumption")
    if not {
        "expected_post_transition_heads",
        "exact_materialized_heads",
        "transition_target_kind",
    } <= set(contracts["transition_heads_verified"]["required_evidence"]):
        raise ValidationError("advance_run cannot verify its post-Transition heads")

    recoverable = variants[("resolve_external_interrupt", "recoverable_timeout")]
    forbidden_recoverable_phases = {
        "prestart_records_committed",
        "invocation_authorized",
        "invocation_capability_prepared",
        "coordinator_transition_committed",
        "stable_boundary_committed",
    }
    if forbidden_recoverable_phases & set(recoverable["phases"]):
        raise ValidationError("recoverable interrupt bypasses advance_run Transition ownership")
    if not {
        ("canonical_failed_delivery_committed", "pause_claimed_recorded"),
        ("pause_claimed_recorded", "pause_consumed_recorded"),
        ("pause_consumed_recorded", "running_lifecycle_recorded"),
        ("running_lifecycle_recorded", "resume_checkpoint_committed"),
        ("resume_checkpoint_committed", "interrupted_code_invocation_authorized"),
    } <= {tuple(edge) for edge in recoverable["success_edges"]}:
        raise ValidationError("recoverable interrupt does not stop at a committed delivery handoff")

    branches = {item["branch_id"]: item for item in protocol["branch_contracts"]}
    expected_outcomes = {
        "recoverable_timeout_resolved_outcome": [
            "recoverable_delivery",
            "failed_closure",
            "unavailable_closure",
        ],
        "recoverable_timeout_terminal_outcome": ["failed_closure", "unavailable_closure"],
        "controlled_halt_terminal_outcome": ["halted_closure", "failed_closure", "unavailable_closure"],
        "integrity_failure_terminal_outcome": ["failed_closure", "unavailable_closure"],
    }
    for branch_id, values in expected_outcomes.items():
        branch = branches.get(branch_id)
        if branch is None or branch.get("valid_combinations") != [
            {"resolved_interrupt_outcome": value} for value in values
        ]:
            raise ValidationError(f"{branch_id} does not cover its exact resolved interrupt outcomes")
    terminal_targets = {
        branch_id: {case["target"] for case in branches[branch_id]["cases"]}
        for branch_id in expected_outcomes
        if branch_id.endswith("terminal_outcome")
    }
    expected_terminal_targets = {
        "interrupt_safe_pause_disposition_committed",
        "interrupt_unavailable_pause_disposition_committed",
    }
    if any(targets != expected_terminal_targets for targets in terminal_targets.values()):
        raise ValidationError("resolved interrupt terminal outcomes do not select exact Pause dispositions")


def _validate_policy_capability_and_terminal_contracts(protocol: dict[str, Any]) -> None:
    expected_policy = {
        "allowlisted_profiles": ["balanced_v1", "phase_b_test"],
        "profile_environment": {
            "balanced_v1": ["runtime", "deterministic_harness"],
            "phase_b_test": ["deterministic_harness"],
        },
        "selection_cases": [
            {
                "operation_variant": "start_run/not_applicable",
                "source_policy_state": "not_applicable",
                "selection": "balanced_v1_default_or_scoped_trusted_host_allowlisted_override",
            },
            {
                "operation_variant": "replay_run/not_applicable",
                "source_policy_state": "pre_a06",
                "selection": "current_balanced_v1",
            },
            {
                "operation_variant": "replay_run/not_applicable",
                "source_policy_state": "supported",
                "selection": "exact_source_canonical_policy_reuse",
            },
            {
                "operation_variant": "replay_run/not_applicable",
                "source_policy_state": "unsupported",
                "selection": "reject_before_operation_reservation",
            },
            {
                "operation_variant": "fork_run/not_applicable",
                "source_policy_state": "any_eligible_source",
                "selection": "scoped_trusted_host_current_allowlisted_target_policy",
            },
        ],
        "selection_authority": "trusted_host_with_profile_selection_scope",
        "source_policy_classifier": {
            "authority": "trusted_host_validated_source_reader",
            "classification_inputs": [
                "source_run_identity",
                "source_schema",
                "source_policy_presence",
                "canonical_source_policy_bytes_or_typed_absence",
                "source_policy_digest_profile_version_or_typed_absence",
                "runtime_supported_policy_set_digest",
            ],
            "states": [
                {
                    "source_policy_state": "pre_a06",
                    "allowed_source_schemas": ["0.2", "0.3"],
                    "required_evidence": "authoritative_policy_absence_proof",
                    "disposition": "accept_with_current_balanced_v1",
                },
                {
                    "source_policy_state": "supported",
                    "allowed_source_schemas": ["0.4"],
                    "required_evidence": "canonical_source_policy_and_runtime_support_proof",
                    "disposition": "accept_with_exact_source_policy",
                },
                {
                    "source_policy_state": "unsupported",
                    "allowed_source_schemas": ["0.4"],
                    "required_evidence": "canonical_source_policy_and_runtime_incompatibility_proof",
                    "disposition": "reject_before_operation_reservation",
                },
            ],
            "output_proof": "source_policy_classification_proof",
            "binding": (
                "source_run_identity_schema_policy_bytes_digest_profile_version_and_runtime_supported_set"
            ),
        },
        "digest_binding": "canonical_policy_bytes_profile_version_and_selection_authority_must_match_digest",
        "freeze_phase": "operation_reserved",
        "child_root_publication_requires_frozen_policy": True,
    }
    if protocol.get("budget_policy_selection_contract") != expected_policy:
        raise ValidationError("budget policy selection is not exhaustively bound to start/replay/fork")
    classifier_states = {
        row["source_policy_state"]: row for row in expected_policy["source_policy_classifier"]["states"]
    }
    replay_selection_states = {
        row["source_policy_state"]
        for row in expected_policy["selection_cases"]
        if row["operation_variant"] == "replay_run/not_applicable"
    }
    if set(classifier_states) != replay_selection_states:
        raise ValidationError("replay policy selection states are not derived from the source-policy classifier")
    if classifier_states["unsupported"]["disposition"] != "reject_before_operation_reservation":
        raise ValidationError("unsupported source policy is not rejected before operation reservation")
    replay_overlay = EXPECTED_RESERVATION_OVERLAYS[("replay_run", "not_applicable")]
    if "source_policy_classification_proof" not in replay_overlay:
        raise ValidationError("accepted replay does not freeze its source-policy classification proof")

    control = protocol["state_machines"]["control_operation"]
    if "source_policy_classification_or_not_applicable" not in control["phase_contracts"][
        "source_snapshot_committed"
    ]["required_evidence"]:
        raise ValidationError("source snapshot publication does not consume its policy classification")
    if "child_policy_selection_proof" not in control["phase_contracts"]["child_policy_published"][
        "required_evidence"
    ]:
        raise ValidationError("child policy publication is not bound to its selection proof")
    expected_capability = {'prepared_then_activated': {'producer_cases': [{'operation_variant': 'start_run/not_applicable',
                                                 'branch': 'all'},
                                                {'operation_variant': 'advance_run/not_applicable',
                                                 'branch': 'transition_target_kind_attempt'},
                                                {'operation_variant': 'replay_run/not_applicable',
                                                 'branch': 'all'},
                                                {'operation_variant': 'fork_run/not_applicable',
                                                 'branch': 'all'}],
                             'forbidden_cases': [{'operation_variant': 'advance_run/not_applicable',
                                                  'branch': 'transition_target_kind_end'}],
                             'preparation_phase': 'invocation_capability_prepared',
                             'activation_phase': 'result_committed',
                             'activation_predicate': 'same_operation_status_committed_and_exact_result_revision',
                             'redemption_requires': ['producer_operation_id',
                                                     'committed_operation_result_revision',
                                                     'exact_attempt_identity',
                                                     'current_terminal_closure_revision',
                                                     'immutable_authorization_anchor',
                                                     'current_invocation_lease_epoch_and_expiry',
                                                     'validated_owned_head_progression']},
 'active_within_resume': {'operation_variants': ['resume_run/continue_execution'],
                          'activation_phase': 'invocation_authorized',
                          'redemption_requires': ['same_in_progress_resume_operation',
                                                  'exact_attempt_identity',
                                                  'current_terminal_closure_revision',
                                                  'immutable_authorization_anchor',
                                                  'current_invocation_lease_epoch_and_expiry',
                                                  'validated_owned_head_progression']},
 'side_effect_fence': 'attempt_execution_requires_attempt_lease_external_prestart_requires_external_operation_authority',
 'execution_lease': {'authority': 'coordinator_db',
                     'transaction_domain': 'coordinator_sqlite',
                     'identity': ['producer_operation_id',
                                  'activation_result_revision_or_resume_phase_revision',
                                  'attempt_id',
                                  'authorization_digest'],
                     'authorization_immutable': True,
                     'lease_independent_of_terminal_producer_worker': True,
                     'states': ['unclaimed', 'leased_not_started', 'started', 'finished', 'uncertain'],
                     'acquire_or_replace_requires': ['producer_activation_valid',
                                                     'target_scheduled',
                                                     'no_started_record',
                                                     'no_side_effect_intent',
                                                     'no_conflicting_owner',
                                                     'current_run_heads_match_authorization_anchor',
                                                     'no_run_terminal_owner',
                                                     'current_terminal_closure_revision',
                                                     'authorization_scope_matches_exact_consumer'],
                     'atomic_acquire_effects': ['compare_authorization_and_current_lease_epoch',
                                                'increment_invocation_epoch',
                                                'assign_worker_and_expiry'],
                     'start_boundary': 'atomic_lease_cas_to_started_intent_before_durable_attempt_started_before_effect',
                     'expired_before_start': 'same_authorization_new_invocation_epoch_only_after_acquire_guards',
                     'expired_after_started_or_uncertain': 'fence_old_worker_no_automatic_reexecution_explicit_recovery',
                     'renew_active': 'same_live_worker_current_epoch_and_owned_progression_only_no_takeover_of_started_execution',
                     'producer_tombstone_mutation': False,
                     'query_mutation': False,
                     'head_rule': 'first_claim_matches_anchor_later_effects_require_validated_same_invocation_owned_append_chain',
                     'old_epoch_effects': 'reject',
                     'terminal_revision_change': 'revoke',
                     'renewal_limit': 'original_attempt_and_run_budget_deadlines_no_budget_reset',
                     'deterministic_publication_recovery': 'control_owner_may_materialize_frozen_started_result_finished_prefix_without_reexecuting_consumer_or_reacquiring_started_invocation'},
 'external_prestart_authority': {'authority': 'external_operation_db',
                                 'attempt_status': 'scheduled',
                                 'parent_authorization': 'committed_advance_target_code_agent_bound_to_external_operation',
                                 'workspace_phase': 'workspace_materialized',
                                 'workspace_requires': ['immutable_core_digest',
                                                        'managed_workspace_locator_digest',
                                                        'current_external_lease_epoch',
                                                        'current_terminal_closure_revision',
                                                        'no_conflicting_stop_owner'],
                                 'dispatch_phase': 'dispatch_authorized',
                                 'dispatch_requires': ['public_paused_checkpoint',
                                                       'immutable_core_digest',
                                                       'current_external_lease_epoch',
                                                       'current_terminal_closure_revision',
                                                       'no_conflicting_stop_owner'],
                                 'attempt_lease_redemption': False,
                                 'attempt_started': False,
                                 'result_consumer': 'resume_run/continue_execution_invocation_authorized',
                                 'forbidden_effects': ['domain_artifact_registration',
                                                       'trusted_post_result_verification',
                                                       'attempt_started'],
                                 'revocation': 'external_stop_owner_or_epoch_change_or_terminal_revision_change_fences_new_backend_effects'},
 'authorization_scopes': {'advance_target_code_agent': 'external_prestart_only',
                          'start_replay_fork_and_other_advance_targets': 'attempt_execution',
                          'resume_continue': 'attempt_execution',
                          'recoverable_interrupt': 'deterministic_failed_result_consumption_only'},
 'active_interrupt_result_consumption': {'operation_variant': 'resolve_external_interrupt/recoverable_timeout',
                                         'required_outcome': 'recoverable_delivery',
                                         'activation_phase': 'interrupted_code_invocation_authorized',
                                         'target_kind': 'code_agent',
                                         'scope': 'deterministic_failed_result_consumption_only',
                                         'redemption_requires': ['same_in_progress_interrupt_winner',
                                                                 'scheduled_code_target',
                                                                 'canonical_failed_delivery_digest',
                                                                 'running_checkpoint_head',
                                                                 'current_invocation_lease_epoch_and_expiry',
                                                                 'current_terminal_closure_revision'],
                                         'forbidden_scope': 'coordinator_invocation_or_backend_execution'}}
    if control.get("invocation_capability_contract") != expected_capability:
        raise ValidationError("invocation capability preparation, activation, or redemption contract changed")
    variant_index = _control_variant_index(protocol)
    for pair in (
        ("start_run", "not_applicable"),
        ("advance_run", "not_applicable"),
        ("replay_run", "not_applicable"),
        ("fork_run", "not_applicable"),
    ):
        variant = variant_index[pair]
        edges = {tuple(edge) for edge in variant["success_edges"]}
        if "invocation_capability_prepared" not in variant["phases"] or (
            "invocation_capability_prepared",
            "result_committed",
        ) not in edges:
            raise ValidationError(f"{pair} does not activate its capability through committed result")

    expected_interrupt_lifecycle = {
        "recoverable_delivery": "not_applicable_running_recovery",
        "halted_closure": "halted",
        "failed_closure": "failed",
        "unavailable_closure": "not_applicable_terminal_closure_unavailable",
    }
    interrupt = control["interrupt_outcome_resolution"]
    if interrupt.get("run_lifecycle_disposition") != expected_interrupt_lifecycle:
        raise ValidationError("resolved interrupt outcome does not select one exact Run lifecycle disposition")

    expected_cancel = {
        "precedence": [
            "unavailable_stop_proof_to_terminal_closure_unavailable",
            "safe_stop_with_proven_overage_tamper_or_policy_violation_to_failed",
            "typed_null_or_safe_stop_without_integrity_failure_to_halted",
            "preexisting_winner_observation_to_not_applicable",
        ],
        "valid_combinations": [
            {"arbitration_outcome": "no_external_operation", "external_final_proof_kind": "not_applicable", "integrity_classification": "clear", "resolution_phase": "terminal_eligibility_verified", "run_lifecycle_disposition": "halted"},
            {"arbitration_outcome": "cancel_won", "external_final_proof_kind": "safe_stop", "integrity_classification": "clear", "resolution_phase": "terminal_eligibility_verified", "run_lifecycle_disposition": "halted"},
            {"arbitration_outcome": "normal_terminal_won", "external_final_proof_kind": "safe_stop", "integrity_classification": "clear", "resolution_phase": "terminal_eligibility_verified", "run_lifecycle_disposition": "halted"},
            {"arbitration_outcome": "cancel_won", "external_final_proof_kind": "safe_stop", "integrity_classification": "proven_overage_tamper_or_policy_violation", "resolution_phase": "terminal_eligibility_verified", "run_lifecycle_disposition": "failed"},
            {"arbitration_outcome": "normal_terminal_won", "external_final_proof_kind": "safe_stop", "integrity_classification": "proven_overage_tamper_or_policy_violation", "resolution_phase": "terminal_eligibility_verified", "run_lifecycle_disposition": "failed"},
            {"arbitration_outcome": "cancel_won", "external_final_proof_kind": "unavailable", "integrity_classification": "unknown_or_not_applicable", "resolution_phase": "terminal_closure_unavailable_recorded", "run_lifecycle_disposition": "not_applicable_terminal_closure_unavailable"},
            {"arbitration_outcome": "preexisting_cancel_resolution", "external_final_proof_kind": "not_applicable", "integrity_classification": "not_applicable", "resolution_phase": "resolution_winner_observed", "run_lifecycle_disposition": "not_applicable_winner_observation"},
            {"arbitration_outcome": "preexisting_interrupt_resolution", "external_final_proof_kind": "not_applicable", "integrity_classification": "not_applicable", "resolution_phase": "resolution_winner_observed", "run_lifecycle_disposition": "not_applicable_winner_observation"},
        ],
        "unavailable_forbids_run_lifecycle": True,
    }
    if control.get("cancel_terminal_resolution") != expected_cancel:
        raise ValidationError("cancel outcome, integrity evidence, and Run lifecycle are not a total function")

    cancel_branch = next(
        branch for branch in protocol["branch_contracts"] if branch["branch_id"] == "cancel_arbitration_result"
    )
    proof_discriminant = next(
        item for item in cancel_branch["discriminants"] if item["field"] == "external_final_proof_kind"
    )
    if proof_discriminant["authority"] != "coordinator_db":
        raise ValidationError("cancel branch discriminator lacks authority when ExternalOperation is absent")
    branch_pairs = {
        (row["arbitration_outcome"], row["external_final_proof_kind"])
        for row in cancel_branch["valid_combinations"]
    }
    terminal_pairs = {
        (row["arbitration_outcome"], row["external_final_proof_kind"])
        for row in expected_cancel["valid_combinations"]
    }
    if branch_pairs != terminal_pairs:
        raise ValidationError("cancel branch inputs and terminal-resolution inputs do not form the same domain")
    cancel_variant = variant_index[("cancel_pause", "not_applicable")]
    cancel_adjacency = {phase: set() for phase in cancel_variant["phases"]}
    for source, target in cancel_variant["success_edges"]:
        cancel_adjacency[source].add(target)
    for outcome, proof_kind in branch_pairs:
        matching_cases = [
            case
            for case in cancel_branch["cases"]
            if outcome in case["when"]["arbitration_outcome"]
            and proof_kind in case["when"]["external_final_proof_kind"]
        ]
        if len(matching_cases) != 1:
            raise ValidationError(f"cancel resolution input has no unique branch case: {(outcome, proof_kind)}")
        resolution_phases = {
            row["resolution_phase"]
            for row in expected_cancel["valid_combinations"]
            if row["arbitration_outcome"] == outcome and row["external_final_proof_kind"] == proof_kind
        }
        if len(resolution_phases) != 1:
            raise ValidationError(f"cancel resolution input has inconsistent resolution phases: {(outcome, proof_kind)}")
        target = matching_cases[0]["target"]
        resolution_phase = next(iter(resolution_phases))
        if resolution_phase not in _reachable(target, cancel_adjacency):
            raise ValidationError(
                f"cancel branch cannot reach its declared resolution phase: "
                f"{(outcome, proof_kind)} -> {resolution_phase}"
            )
    expected_direct_terminal = {'close_run_trigger_to_run_status': {'normal_end': 'completed',
                                     'non_pause_runtime_failure': 'failed',
                                     'internal_terminal_decision': 'halted',
                                     'aggregate_hard_limit': 'halted',
                                     'policy_stop': 'halted',
                                     'terminal_operator_stop': 'halted'},
 'resume_run_abandon_and_halt': 'halted',
 'resolution_phase': 'terminal_eligibility_verified',
 'terminal_lifecycle_requires_exact_resolved_disposition': True,
 'close_system_stop_integrity_override': {'applies_to': ['aggregate_hard_limit',
                                                         'policy_stop',
                                                         'terminal_operator_stop'],
                                          'safe_stop_and_proven_integrity_failure': 'failed',
                                          'resolution_phase': 'terminal_eligibility_verified'},
 'resume_run_consumption_failure': {'operation_variant': 'resume_run/continue_execution',
                                    'required_outcome': 'failed_closure',
                                    'run_status': 'failed',
                                    'resolution_phase': 'terminal_eligibility_verified'}}
    if control.get("direct_terminal_resolution") != expected_direct_terminal:
        raise ValidationError("direct terminal trigger or abandon outcome does not select one exact Run lifecycle")
    terminal_evidence = set(control["phase_contracts"]["terminal_lifecycle_recorded"]["required_evidence"])
    if not {"resolved_terminal_disposition", "terminal_disposition_contract_digest"} <= terminal_evidence:
        raise ValidationError("terminal lifecycle publication is not bound to the resolved disposition contract")


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
        if guard_id == "external_normal_terminal_cas" and proof_kind != guard["required_candidate_proof_kind"]:
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
        "ADVANCE-001",
        "CAPABILITY-001",
        "TERMINAL-DISPOSITION-001",
        "POLICY-SELECTION-001",
        "PHASE-DEP-001",
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
    if arbitration.get("normal_requires_candidate_proof_kind") != "safe_stop" or arbitration.get(
        "candidate_authority"
    ) != "normal_finalization_request":
        raise ValidationError("EXT-ARB-001 does not keep the normal candidate proof on its contender request")
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
    if set(interrupt_closure.get("resolved_outcomes", [])) != {
        "recoverable_delivery",
        "halted_closure",
        "failed_closure",
        "unavailable_closure",
    } or interrupt_closure.get("single_winner_operation") is not True:
        raise ValidationError("EXT-INT-001 does not close every outcome in the same interrupt operation")
    if interrupt_closure.get("late_integrity_precedence") != (
        "safe_stop_with_proven_overage_tamper_or_policy_violation_to_failed_closure"
    ):
        raise ValidationError("EXT-INT-001 does not upgrade late integrity evidence to failed closure")
    interrupt_resolution = protocol["state_machines"]["control_operation"].get("interrupt_outcome_resolution")
    expected_interrupt_resolution = {
        "values": ["recoverable_delivery", "halted_closure", "failed_closure", "unavailable_closure"],
        "precedence": [
            "unavailable_stop_proof_to_unavailable_closure",
            "safe_stop_with_proven_overage_tamper_or_policy_violation_to_failed_closure",
            "safe_recoverable_timeout_without_integrity_failure_to_recoverable_delivery",
            "safe_controlled_halt_without_integrity_failure_to_halted_closure",
            "safe_integrity_trigger_to_failed_closure",
        ],
        "winner_rule": (
            "same_interrupt_control_operation_owns_resolution_settlement_pause_disposition_and_run_closure"
        ),
        "pause_disposition": {
            "recoverable_delivery": "opened_then_claimed_and_consumed",
            "halted_closure": "absent_not_applicable_prepared_aborted_or_opened_interrupted",
            "failed_closure": "absent_not_applicable_prepared_aborted_or_opened_interrupted",
            "unavailable_closure": "absent_not_applicable_or_prepared_opened_quarantined",
        },
        "run_lifecycle_disposition": {
            "recoverable_delivery": "not_applicable_running_recovery",
            "halted_closure": "halted",
            "failed_closure": "failed",
            "unavailable_closure": "not_applicable_terminal_closure_unavailable",
        },
    }
    if interrupt_resolution != expected_interrupt_resolution:
        raise ValidationError("interrupt outcome resolution or late-integrity precedence is incomplete")
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
    if reservation.get("phase") != "operation_reserved" or reservation.get("required_operation_variant_count") != 12:
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
        or stop_route.get("selection") != "trigger_first_then_exactly_one_context_route_before_operation_reservation"
        or stop_route.get("coverage") != "every_trigger_class_required_external_context"
        or stop_route.get("forbids_second_terminal_operation") is not True
    ):
        raise ValidationError("STOP-ROUTE-001 does not bind the unique stop route contract")
    advance = by_id["ADVANCE-001"]
    if advance.get("control_operation") != "advance_run/not_applicable" or advance.get("attempt_order") != [
        "budget_decision_committed",
        "route_prerequisites_committed",
        "target_attempt_scheduled",
        "target_artifacts_invalidated",
        "transition_committed",
        "transition_heads_verified",
        "target_preparation_committed",
        "invocation_capability_prepared",
        "result_committed",
    ] or advance.get("recoverable_interrupt_handoff") != "committed_failed_code_attempt_result_checkpoint_then_new_advance_run":
        raise ValidationError("ADVANCE-001 does not bind the ordinary Transition publication order")
    phase_dependency = by_id["PHASE-DEP-001"]
    if phase_dependency.get("coverage") != "every_noninitial_control_phase" or phase_dependency.get("rule") != (
        "declared_producer_dominates_consumer_on_every_success_path"
    ) or phase_dependency.get("independent_graph_seal") != "validator_control_graph_sha256":
        raise ValidationError("PHASE-DEP-001 does not require complete phase dominance")
    capability = by_id["CAPABILITY-001"]
    if capability != {
        "invariant_id": "CAPABILITY-001",
        "kind": "invocation_capability_activation",
        "contract": "invocation_capability_contract",
        "committed_result_producers": [
            "start_run/not_applicable",
            "advance_run/not_applicable#transition_target_kind_attempt",
            "replay_run/not_applicable",
            "fork_run/not_applicable",
        ],
        "resume_activation": "invocation_authorized",
        "interrupt_result_consumption_activation": "interrupted_code_invocation_authorized",
    }:
        raise ValidationError("CAPABILITY-001 does not bind capability activation to the producer operation")
    terminal_disposition = by_id["TERMINAL-DISPOSITION-001"]
    if terminal_disposition != {
        "invariant_id": "TERMINAL-DISPOSITION-001",
        "kind": "resolved_outcome_to_run_lifecycle",
        "interrupt_contract": "interrupt_outcome_resolution.run_lifecycle_disposition",
        "cancel_contract": "cancel_terminal_resolution",
        "direct_contract": "direct_terminal_resolution",
        "unavailable_forbids_run_lifecycle": True,
    }:
        raise ValidationError("TERMINAL-DISPOSITION-001 does not bind every terminal path")
    policy_selection = by_id["POLICY-SELECTION-001"]
    if policy_selection != {
        "invariant_id": "POLICY-SELECTION-001",
        "kind": "budget_policy_selection",
        "contract": "budget_policy_selection_contract",
        "source_classifier": "source_policy_classifier",
        "freeze_before_root_publication": True,
    }:
        raise ValidationError("POLICY-SELECTION-001 does not bind policy selection before publication")
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


def _validate_stop_handoff_and_execution_lease(protocol: dict[str, Any]) -> None:
    control = protocol["state_machines"]["control_operation"]
    expected_contracts = {'close_source_contract': {'authority': 'coordinator_db',
                           'transaction_domain': 'coordinator_sqlite',
                           'reservation_fields': ['external_operation_precondition',
                                                  'external_operation_precondition_proof_digest',
                                                  'close_source_snapshot'],
                           'normal_attached_snapshot_fields': ['external_operation_id',
                                                               'external_final_evidence_digest',
                                                               'external_phase_revision',
                                                               'external_lease_epoch',
                                                               'resolution_owner',
                                                               'pause_id',
                                                               'opened_execution_head',
                                                               'scheduled_target_attempt',
                                                               'resource_reservation_snapshot',
                                                               'trusted_integrity_classification',
                                                               'precomputed_settlement_and_pause_target_disposition'],
                           'ownership_phase': 'terminal_ownership_reserved',
                           'atomic_compare': ['source_heads',
                                              'pause_status',
                                              'pause_owner',
                                              'run_terminal_closure_owner',
                                              'external_phase_revision',
                                              'external_lease_epoch',
                                              'external_final_evidence_digest'],
                           'normal_attached_requires': {'resolution_owner': 'normal',
                                                        'proof_kind': 'safe_stop',
                                                        'pause_status': 'opened',
                                                        'pause_owner': None,
                                                        'run_terminal_closure_owner': None,
                                                        'attempt_status': 'scheduled'},
                           'atomic_acquires': ['run_terminal_closure_owner',
                                               'applicable_pause_disposition_owner'],
                           'external_resolution_mutation': 'none',
                           'publication_order': ['resource_disposition_committed',
                                                 'close_source_disposition_committed',
                                                 'terminal_eligibility_verified'],
                           'source_disposition': {'normal_safe_stop_attached_opened_pause': 'scheduled_target_abandoned_pause_interrupted_external_detached',
                                                  'absent': 'applicable_prepared_pause_aborted_or_opened_pause_interrupted_and_scheduled_target_abandoned_otherwise_not_applicable',
                                                  'safely_terminal_and_detached': 'not_applicable'},
                           'system_stop_disposition': {'clear': 'halted',
                                                       'proven_overage_tamper_or_policy_violation': 'failed'},
                           'cas_conflict': 'loser_terminal_conflict_without_owner_preserve_trigger_digest_reclassify_with_route_source_revision_key_only_one_closure_winner',
                           'normal_race': 'interrupt_wins_use_same_interrupt_tail_normal_wins_close_same_unconsumed_result',
                           'resume_race': 'resume_wins_do_not_detach_or_consume_again_serialize_stop_at_next_trusted_boundary',
                           'existing_stop_owner': 'observe_same_winner_no_second_closure',
                           'detachment_evidence': 'external_consumption_release_proof_or_same_close_owner_settlement_pause_finality_target_disposition_and_original_normal_final_digest'},
 'settlement_contract': {'authority': 'budget_ledger',
                         'owner_types': ['resume_run',
                                         'cancel_pause',
                                         'resolve_external_interrupt',
                                         'close_run'],
                         'identity': ['reservation_id', 'external_operation_id'],
                         'fence': ['owner_operation_id',
                                   'owner_lease_epoch',
                                   'owner_phase_revision',
                                   'latest_external_final_evidence_digest',
                                   'external_epoch_history'],
                         'exactly_once': 'same_identity_same_bytes_read_existing_different_bytes_conflict',
                         'unavailable_charge': 'reserved_maximum_plus_any_observed_overage_never_clip',
                         'unavailable_phase': 'unavailable_resource_disposition_committed',
                         'unavailable_before': 'pause_quarantined_recorded',
                         'no_reservation': 'typed_not_applicable_only_with_authoritative_absence',
                         'safe_phase': 'resource_disposition_committed',
                         'authority_unappendable': 'freeze_conservative_charge_and_evidence_in_same_owner_unavailable_tombstone_never_forge_ledger_settlement'}}
    for name, expected in expected_contracts.items():
        if control.get(name) != expected:
            raise ValidationError(f"incomplete stop handoff or settlement contract: {name}")
    variants = _control_variant_index(protocol)
    close = variants[("close_run", "not_applicable")]
    cancel = variants[("cancel_pause", "not_applicable")]
    for variant, start, end, required in (
        (close, "terminal_ownership_reserved", "terminal_eligibility_verified", "resource_disposition_committed"),
        (close, "terminal_ownership_reserved", "terminal_eligibility_verified", "close_source_disposition_committed"),
        (cancel, "external_unavailable_verified", "terminal_closure_unavailable_recorded", "unavailable_resource_disposition_committed"),
    ):
        adjacency = {phase: set() for phase in variant["phases"]}
        for source, target in variant["success_edges"]:
            adjacency[source].add(target)
        if end not in _reachable(start, adjacency):
            raise ValidationError("stop publication success path is unreachable")
        cut = {source: targets - {required} for source, targets in adjacency.items() if source != required}
        cut[required] = set()
        if end in _reachable(start, cut):
            raise ValidationError("stop publication bypasses settlement or source disposition")
    phase_contracts = control["phase_contracts"]
    for phase, required in {'close_source_disposition_committed': ['close_source_snapshot',
                                        'same_close_owner',
                                        'resource_settlement_or_not_applicable',
                                        'pause_target_disposition_and_detachment_or_not_applicable'],
 'terminal_ownership_reserved': ['deterministic_terminal_trigger',
                                 'empty_run_terminal_owner_cas',
                                 'terminal_resolution_contracts',
                                 'close_source_snapshot',
                                 'atomic_pause_run_owner_cas',
                                 'normal_final_read_only_or_not_applicable'],
 'unavailable_resource_disposition_committed': ['unavailable_final_evidence',
                                                'resource_settlement_or_not_applicable',
                                                'conservative_charge_including_observed_overage',
                                                'same_cancel_owner']}.items():
        if not set(required) <= set(phase_contracts[phase]["required_evidence"]):
            raise ValidationError(f"missing handoff phase evidence: {phase}")
    owner_phase = phase_contracts["terminal_ownership_reserved"]
    if owner_phase.get("atomic_acquire") is not True or "applicable_pause_disposition_owner" not in owner_phase.get("conditional_acquires", []):
        raise ValidationError("normal-result close does not atomically acquire Pause and Run")
    for phase in ("workspace_materialized", "dispatch_authorized"):
        evidence = protocol["state_machines"]["external_operation"]["phase_contracts"][phase]["required_evidence"]
        if not {"committed_code_target_authorization", "current_terminal_closure_revision", "no_conflicting_stop_owner"} <= set(evidence):
            raise ValidationError("external pre-start effect lacks its own fenced authority")
    route = protocol["stop_route_contract"]
    normal_routes = [row for row in route["routes"] if row["external_context"] == "normal_terminal_attached_opened_pause"]
    if len(normal_routes) != 1 or normal_routes[0]["operation_type"] != "close_run":
        raise ValidationError("normal terminal awaiting delivery has no unique system-stop route")
    if "normal_safe_stop_attached_opened_pause" not in route["close_run_external_preconditions"]:
        raise ValidationError("normal result stop route cannot satisfy close admission")
    override = control["direct_terminal_resolution"].get("close_system_stop_integrity_override", {})
    if override.get("safe_stop_and_proven_integrity_failure") != "failed":
        raise ValidationError("normal winner integrity evidence is lost during close")


def _validate_budget_decision_contract(protocol: dict[str, Any]) -> None:
    contract = protocol["budget_decision_contract"]
    allowed = ["allow", "human_gate", "halt"]
    if contract["decision_values"] != allowed:
        raise ValidationError("BudgetDecision must use the single allow/human_gate/halt enum")
    if contract["invalid_response_proposed_action"] != "repause":
        raise ValidationError("invalid response must bind the exact repause proposal")
    if contract["required_bindings"] != [
        "consumed_old_pause", "finished_validator_attempt", "open_human_request",
        "derived_next_pause_identity", "terminal_tail_capacity", "decision_resulting_execution_head",
    ]:
        raise ValidationError("repause decision is missing its identity/capacity/head binding")
    expected = {
        "sufficient": ("allow", "publish_pause"),
        "insufficient": ("halt", "close_run"),
    }
    seen = set()
    for case in contract["invalid_response_cases"]:
        capacity = case["capacity"]
        if capacity in seen or capacity not in expected:
            raise ValidationError("repause capacity cases must be unique and exhaustive")
        seen.add(capacity)
        if case["decision"] not in allowed or (
            case["decision"], case["next_control_action"]
        ) != expected[capacity]:
            raise ValidationError("repause decision and consumer action do not match capacity")
    if seen != set(expected):
        raise ValidationError("repause is missing a capacity outcome")
    if contract["pause_identity_allocation"] != "publish_pause.pause_prepared_recorded_only":
        raise ValidationError("repause decision cannot allocate the new Pause")
    if contract["old_pause_disposition"] != "retain_consumed_no_reopen":
        raise ValidationError("repause cannot reopen the consumed Pause")


def _validate_budget_decision_documents(protocol: dict[str, Any]) -> None:
    allowed = set(protocol["budget_decision_contract"]["decision_values"])
    for name in ["A04_PAUSE_RESUME_SEMANTICS.md", "A06_BUDGETS_AND_STOP_CONDITIONS.md"]:
        prose = (CONTRACT_DIR / name).read_text(encoding="utf-8")
        for expression in re.findall(r"`([a-z_]+(?:\s*\|\s*[a-z_]+)+)`", prose):
            values = set(re.split(r"\s*\|\s*", expression))
            if values & allowed and not values <= allowed:
                raise ValidationError(f"{name} contains an undeclared budget decision enum: {expression}")
        for expression in re.findall(r"decision_recorded\(([^)]+)\)", prose):
            if not set(expression.split(" | ")) <= allowed:
                raise ValidationError(f"{name} requires an undeclared budget decision: {expression}")
        if "budget_decision_contract.invalid_response_cases" not in prose:
            raise ValidationError(f"{name} does not bind the canonical repause cases")
    prose = (CONTRACT_DIR / "A06_BUDGETS_AND_STOP_CONDITIONS.md").read_text(encoding="utf-8")
    declarations = re.findall(r"`decision = ([^`]+)`", prose)
    if len(declarations) != 1 or set(declarations[0].split(" | ")) != allowed:
        raise ValidationError("A06 BudgetDecision enum differs from the machine contract")


def _validate_protocol_structure(protocol: dict[str, Any]) -> None:
    if _object_layout_sha256(protocol) != EXPECTED_PROTOCOL_LAYOUT_SHA256:
        raise ValidationError("protocol has unknown/missing fields or changed closed schema layout")


def _validate_protocol_freeze(protocol: dict[str, Any]) -> None:
    actual_graph_sha256 = _control_graph_sha256(protocol)
    if actual_graph_sha256 != EXPECTED_CONTROL_GRAPH_SHA256:
        raise ValidationError(
            "control operation graph/dependency semantic seal mismatch: "
            f"expected={EXPECTED_CONTROL_GRAPH_SHA256}, actual={actual_graph_sha256}"
        )


def _validate_protocol(protocol: dict[str, Any]) -> None:
    _validate_protocol_structure(protocol)
    _validate_protocol_semantics(protocol)
    _validate_protocol_freeze(protocol)


def _validate_protocol_semantics(protocol: dict[str, Any]) -> None:
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
        "budget_policy_selection_contract",
        "budget_decision_contract",
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
    _validate_stop_handoff_and_execution_lease(protocol)
    _validate_advance_and_interrupt_contracts(protocol)
    _validate_target_execution_paths(protocol)
    _validate_consumption_failure(protocol)
    _validate_consumption_release_and_recovery(protocol)
    _validate_policy_capability_and_terminal_contracts(protocol)
    _validate_resolution_interleavings(protocol)
    _validate_cross_machine_invariants(protocol)
    _validate_budget_decision_contract(protocol)


def _validate_catalog(catalog: dict[str, Any], protocol_sha256: str) -> None:
    if _object_layout_sha256(catalog) != EXPECTED_CATALOG_LAYOUT_SHA256:
        raise ValidationError("catalog has unknown/missing fields or changed closed schema layout")
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
    if len(ids) != 131 or actual_owner_counts != EXPECTED_OWNER_COUNTS:
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


def _assert_protocol_mutation_rejected(
    protocol: dict[str, Any],
    label: str,
    validator: Callable[[dict[str, Any]], None],
) -> None:
    try:
        validator(protocol)
    except ValidationError:
        return
    raise ValidationError(f"{validator.__name__} accepted negative mutation: {label}")


def _validate_negative_protocol_mutations(protocol: dict[str, Any]) -> None:
    def branch(candidate: dict[str, Any], branch_id: str) -> dict[str, Any]:
        return next(item for item in candidate["branch_contracts"] if item["branch_id"] == branch_id)

    def control_variant(candidate: dict[str, Any], operation_type: str, operation_variant: str) -> dict[str, Any]:
        return next(
            variant
            for operation in candidate["state_machines"]["control_operation"]["operations"]
            if operation["operation_type"] == operation_type
            for variant in operation["variants"]
            if variant["operation_variant"] == operation_variant
        )

    def overlay(candidate: dict[str, Any], operation_type: str, operation_variant: str) -> dict[str, Any]:
        return next(
            item
            for item in candidate["state_machines"]["control_operation"]["phase_contract_overlays"]
            if item["operation_type"] == operation_type and item["operation_variant"] == operation_variant
        )

    def evidence_union(candidate: dict[str, Any], union_id: str) -> dict[str, Any]:
        return next(item for item in candidate["evidence_unions"] if item["union_id"] == union_id)

    def remove_advance_branch(candidate: dict[str, Any]) -> None:
        candidate["branch_contracts"] = [
            item for item in candidate["branch_contracts"] if item["branch_id"] != "advance_run_target"
        ]

    def reverse_start_policy_and_ledger(candidate: dict[str, Any]) -> None:
        variant = control_variant(candidate, "start_run", "not_applicable")
        variant["success_edges"] = [
            edge
            for edge in variant["success_edges"]
            if edge not in [
                ["run_root_created", "policy_published"],
                ["policy_published", "run_ledger_started"],
                ["run_ledger_started", "bootstrap_records_complete"],
            ]
        ] + [
            ["run_root_created", "run_ledger_started"],
            ["run_ledger_started", "policy_published"],
            ["policy_published", "bootstrap_records_complete"],
        ]

    def reverse_resume_checkpoint_and_capability(candidate: dict[str, Any]) -> None:
        variant = control_variant(candidate, "resume_run", "continue_execution")
        variant["success_edges"] = [
            edge
            for edge in variant["success_edges"]
            if edge not in [
                ["running_lifecycle_recorded", "resume_checkpoint_committed"],
                ["resume_checkpoint_committed", "invocation_authorized"],
                ["invocation_authorized", "stable_boundary_committed"],
            ]
        ] + [
            ["running_lifecycle_recorded", "invocation_authorized"],
            ["invocation_authorized", "resume_checkpoint_committed"],
            ["resume_checkpoint_committed", "stable_boundary_committed"],
        ]

    def reverse_start_policy_and_ledger_with_dependencies(candidate: dict[str, Any]) -> None:
        reverse_start_policy_and_ledger(candidate)
        variant = control_variant(candidate, "start_run", "not_applicable")
        replacements = {
            "policy_published": ("run_ledger_started", "policy_published"),
            "run_ledger_started": ("run_root_created", "run_ledger_started"),
            "bootstrap_records_complete": ("policy_published", "bootstrap_records_complete"),
        }
        for dependency in variant["phase_dependencies"]:
            consumer = dependency["consumer_phase"]
            if consumer in replacements:
                dependency["producer_phase"], dependency["consumer_phase"] = replacements[consumer]

    def reverse_resume_checkpoint_and_capability_with_dependencies(candidate: dict[str, Any]) -> None:
        reverse_resume_checkpoint_and_capability(candidate)
        variant = control_variant(candidate, "resume_run", "continue_execution")
        replacements = {
            "resume_checkpoint_committed": ("invocation_authorized", "resume_checkpoint_committed"),
            "invocation_authorized": ("running_lifecycle_recorded", "invocation_authorized"),
            "stable_boundary_committed": ("resume_checkpoint_committed", "stable_boundary_committed"),
        }
        for dependency in variant["phase_dependencies"]:
            consumer = dependency["consumer_phase"]
            if consumer in replacements:
                dependency["producer_phase"], dependency["consumer_phase"] = replacements[consumer]

    def restore_raw_reservation_digest(candidate: dict[str, Any]) -> None:
        fields = overlay(candidate, "resolve_external_interrupt", "controlled_halt")["required_evidence_additions"]
        snapshot = next(item for item in fields if item["field"] == "resource_reservation_snapshot")
        snapshot["field"] = "resource_reservation_digest"
        snapshot["type"] = "sha256"

    def remove_pre_reservation_absence(candidate: dict[str, Any]) -> None:
        union = evidence_union(candidate, "ExternalResourceReservationSnapshot")
        union["variants"] = [item for item in union["variants"] if item["tag"] != "absent_before_reservation"]

    def allow_recoverable_absent_reservation(candidate: dict[str, Any]) -> None:
        union = evidence_union(candidate, "ExternalResourceReservationSnapshot")
        binding = next(
            item
            for item in union["reservation_phase_bindings"]
            if item["operation_variant"] == "resolve_external_interrupt/recoverable_timeout"
        )
        binding["allowed_variants"] = ["present", "absent_before_reservation"]

    def allow_post_reservation_absence(candidate: dict[str, Any]) -> None:
        union = evidence_union(candidate, "ExternalResourceReservationSnapshot")
        binding = next(
            item
            for item in union["reservation_phase_bindings"]
            if item["operation_variant"] == "resolve_external_interrupt/controlled_halt"
            and "reservation_committed" in item["external_phases"]
        )
        binding["allowed_variants"] = ["present", "absent_before_reservation"]

    def allow_present_reservation_null_proof(candidate: dict[str, Any]) -> None:
        union = evidence_union(candidate, "ExternalResourceReservationSnapshot")
        present = next(item for item in union["variants"] if item["tag"] == "present")
        present["forbidden_fields"].remove("reservation_fields_are_null")

    def omit_resource_external_operation_identity(candidate: dict[str, Any]) -> None:
        union = evidence_union(candidate, "ExternalResourceReservationSnapshot")
        present = next(item for item in union["variants"] if item["tag"] == "present")
        present["required_fields"].remove("external_operation_id")

    def detach_resource_resolution_tuple(candidate: dict[str, Any]) -> None:
        union = evidence_union(candidate, "ExternalResourceReservationSnapshot")
        union["resolution_tuple_binding"]["match_fields"].remove("external_phase_revision")

    def store_normal_candidate_on_shared_state(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "external_normal_terminal_cas")
        guard["candidate_authority"] = "external_operation_db"

    def allow_normal_unavailable_candidate(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "external_normal_terminal_cas")
        guard["required_candidate_proof_kind"] = "unavailable"

    def omit_late_integrity_precedence(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["control_operation"]["interrupt_outcome_resolution"]["precedence"].remove(
            "safe_stop_with_proven_overage_tamper_or_policy_violation_to_failed_closure"
        )

    def remove_controlled_halt_failed_outcome(candidate: dict[str, Any]) -> None:
        contract = branch(candidate, "controlled_halt_terminal_outcome")
        contract["valid_combinations"] = [
            item for item in contract["valid_combinations"] if item["resolved_interrupt_outcome"] != "failed_closure"
        ]
        contract["cases"][0]["when"]["resolved_interrupt_outcome"].remove("failed_closure")

    def map_halted_interrupt_to_failed_run(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["control_operation"]["interrupt_outcome_resolution"][
            "run_lifecycle_disposition"
        ]["halted_closure"] = "failed"

    def map_safe_cancel_to_failed_run(candidate: dict[str, Any]) -> None:
        combinations = candidate["state_machines"]["control_operation"]["cancel_terminal_resolution"][
            "valid_combinations"
        ]
        row = next(
            item
            for item in combinations
            if item["arbitration_outcome"] == "cancel_won"
            and item["external_final_proof_kind"] == "safe_stop"
            and item["integrity_classification"] == "clear"
        )
        row["run_lifecycle_disposition"] = "failed"

    def map_normal_end_to_halted_run(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["control_operation"]["direct_terminal_resolution"][
            "close_run_trigger_to_run_status"
        ]["normal_end"] = "halted"

    def restrict_explicit_cancel_to_live_external(candidate: dict[str, Any]) -> None:
        candidate["stop_route_contract"]["routes"][0]["external_context"] = "live_external_operation"

    def omit_no_external_system_stop_route(candidate: dict[str, Any]) -> None:
        candidate["stop_route_contract"]["routes"] = [
            route
            for route in candidate["stop_route_contract"]["routes"]
            if not (
                route["trigger_class"] == "terminal_system_stop"
                and route["external_context"] == "no_unresolved_external_operation"
            )
        ]

    def split_cancel_resolution_domain(candidate: dict[str, Any]) -> None:
        rows = candidate["state_machines"]["control_operation"]["cancel_terminal_resolution"][
            "valid_combinations"
        ]
        row = next(item for item in rows if item["arbitration_outcome"] == "preexisting_cancel_resolution")
        row["external_final_proof_kind"] = "current_resolution"

    def cross_wire_source_snapshot(candidate: dict[str, Any]) -> None:
        binding = next(
            item
            for item in evidence_union(candidate, "SourceSnapshotProof")["consumer_bindings"]
            if item["operation_type"] == "replay_run"
        )
        binding["allowed_variants"] = ["fork_head"]

    def allow_legacy_fork_source(candidate: dict[str, Any]) -> None:
        evidence_union(candidate, "SourceSnapshotProof")["valid_schema_revision_combinations"].append(
            {
                "source_snapshot_kind": "fork_head",
                "source_schema": "0.2",
                "source_control_revision_proof": "legacy_control_revision_not_applicable",
            }
        )

    def allow_modern_replay_with_legacy_revision(candidate: dict[str, Any]) -> None:
        combinations = evidence_union(candidate, "SourceSnapshotProof")["valid_schema_revision_combinations"]
        row = next(
            item
            for item in combinations
            if item["source_snapshot_kind"] == "replay_root" and item["source_schema"] == "0.3"
        )
        row["source_control_revision_proof"] = "legacy_control_revision_not_applicable"

    def allow_replay_proof_to_carry_fork_state(candidate: dict[str, Any]) -> None:
        source = evidence_union(candidate, "SourceSnapshotProof")
        replay = next(item for item in source["variants"] if item["tag"] == "replay_root")
        replay["forbidden_fields"].remove("eligible_artifact_snapshot")

    def allow_fork_proof_to_carry_replay_root(candidate: dict[str, Any]) -> None:
        source = evidence_union(candidate, "SourceSnapshotProof")
        fork = next(item for item in source["variants"] if item["tag"] == "fork_head")
        fork["forbidden_fields"].remove("immutable_root_input")

    def allow_running_fork_source(candidate: dict[str, Any]) -> None:
        contract = evidence_union(candidate, "SourceSnapshotProof")["fork_head_run_status_contract"]
        contract["allowed_values"].append("running")
        contract["forbidden_values"].remove("running")

    def omit_source_run_identity(candidate: dict[str, Any]) -> None:
        source = evidence_union(candidate, "SourceSnapshotProof")
        replay = next(item for item in source["variants"] if item["tag"] == "replay_root")
        replay["required_fields"].remove("source_run_identity")

    def omit_child_policy(candidate: dict[str, Any]) -> None:
        fields = overlay(candidate, "fork_run", "not_applicable")["required_evidence_additions"]
        fields[:] = [item for item in fields if item["field"] != "canonical_child_policy_bytes"]

    def allow_unscoped_fork_policy(candidate: dict[str, Any]) -> None:
        policy = candidate["budget_policy_selection_contract"]
        row = next(item for item in policy["selection_cases"] if item["operation_variant"] == "fork_run/not_applicable")
        row["selection"] = "any_requested_target_policy"

    def change_legacy_replay_policy_default(candidate: dict[str, Any]) -> None:
        policy = candidate["budget_policy_selection_contract"]
        row = next(
            item
            for item in policy["selection_cases"]
            if item["operation_variant"] == "replay_run/not_applicable"
            and item["source_policy_state"] == "pre_a06"
        )
        row["selection"] = "source_requested_profile"

    def allow_test_profile_in_runtime(candidate: dict[str, Any]) -> None:
        candidate["budget_policy_selection_contract"]["profile_environment"]["phase_b_test"].append("runtime")

    def classify_legacy_source_policy_as_supported(candidate: dict[str, Any]) -> None:
        classifier = candidate["budget_policy_selection_contract"]["source_policy_classifier"]
        supported = next(item for item in classifier["states"] if item["source_policy_state"] == "supported")
        supported["allowed_source_schemas"].append("0.3")

    def omit_replay_policy_classification_proof(candidate: dict[str, Any]) -> None:
        fields = overlay(candidate, "replay_run", "not_applicable")["required_evidence_additions"]
        fields[:] = [item for item in fields if item["field"] != "source_policy_classification_proof"]

    def omit_child_policy_selection_proof(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["control_operation"]["phase_contracts"]["child_policy_published"][
            "required_evidence"
        ].remove("child_policy_selection_proof")

    def activate_advance_capability_before_commit(candidate: dict[str, Any]) -> None:
        contract = candidate["state_machines"]["control_operation"]["invocation_capability_contract"][
            "prepared_then_activated"
        ]
        contract["activation_phase"] = "invocation_capability_prepared"
        contract["activation_predicate"] = "same_in_progress_operation"

    def remove_start_capability_preparation(candidate: dict[str, Any]) -> None:
        variant = control_variant(candidate, "start_run", "not_applicable")
        variant["phases"].remove("invocation_capability_prepared")
        variant["success_edges"].remove(["checkpoint_committed", "invocation_capability_prepared"])
        variant["success_edges"].remove(["invocation_capability_prepared", "result_committed"])
        variant["success_edges"].append(["checkpoint_committed", "result_committed"])
        variant["phase_dependencies"] = [
            dependency
            for dependency in variant["phase_dependencies"]
            if dependency["consumer_phase"] != "invocation_capability_prepared"
        ]
        next(
            dependency
            for dependency in variant["phase_dependencies"]
            if dependency["consumer_phase"] == "result_committed"
        )["producer_phase"] = "checkpoint_committed"

    def remove_replay_capability_producer(candidate: dict[str, Any]) -> None:
        contract = candidate["state_machines"]["control_operation"]["invocation_capability_contract"][
            "prepared_then_activated"
        ]
        contract["producer_cases"] = [
            item for item in contract["producer_cases"] if item["operation_variant"] != "replay_run/not_applicable"
        ]

    def allow_advance_end_capability(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["control_operation"]["invocation_capability_contract"][
            "prepared_then_activated"
        ]["forbidden_cases"] = []

    def restore_interrupt_owned_coordinator_transition(candidate: dict[str, Any]) -> None:
        variant = control_variant(candidate, "resolve_external_interrupt", "recoverable_timeout")
        variant["phases"].append("invocation_authorized")
        variant["success_edges"].remove(["resume_checkpoint_committed", "interrupted_code_invocation_authorized"])
        variant["success_edges"].extend(
            [["resume_checkpoint_committed", "invocation_authorized"], ["invocation_authorized", "result_committed"]]
        )
        variant["phase_dependencies"].append(
            {"producer_phase": "resume_checkpoint_committed", "consumer_phase": "invocation_authorized"}
        )

    def remove_advance_operation(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["control_operation"]["operations"] = [
            item
            for item in candidate["state_machines"]["control_operation"]["operations"]
            if item["operation_type"] != "advance_run"
        ]

    def omit_phase_dependency(candidate: dict[str, Any]) -> None:
        control_variant(candidate, "start_run", "not_applicable")["phase_dependencies"].pop()

    def omit_stop_dimension(candidate: dict[str, Any]) -> None:
        candidate["state_machines"]["external_operation"]["final_proof_classification"]["dimensions"].remove(
            "post_stop_stability"
        )

    def mismatch_pause_disposition(candidate: dict[str, Any]) -> None:
        evidence_union(candidate, "InterruptSafePauseDispositionProof")["correlates_with"]["tag_mapping"][
            "prepared"
        ] = "opened_interrupted"

    def allow_second_close(candidate: dict[str, Any]) -> None:
        candidate["stop_route_contract"]["forbidden_routes"].remove(
            "run_terminal_interrupt_owner_then_second_close_run"
        )

    def cancel_owns_interrupt_winner(candidate: dict[str, Any]) -> None:
        guard = next(item for item in candidate["cas_guards"] if item["guard_id"] == "cancel_control_combined_cas")
        outcome = next(
            item for item in guard["outcome_guards"] if item["outcome"] == "preexisting_interrupt_resolution"
        )
        outcome["acquires"] = ["pause_cancel_owner", "run_terminal_closure_owner"]

    def change_handoff(candidate: dict[str, Any], contract: str, field: str, value: Any) -> None:
        candidate["state_machines"]["control_operation"][contract][field] = value

    def change_lease(candidate: dict[str, Any], field: str, value: Any) -> None:
        candidate["state_machines"]["control_operation"]["invocation_capability_contract"]["execution_lease"][field] = value

    mutations: list[tuple[str, Callable[[dict[str, Any]], None], Callable[[dict[str, Any]], None]]] = [
        ("repause introduces an undeclared decision", _validate_budget_decision_contract, lambda p: p["budget_decision_contract"]["decision_values"].__setitem__(0, "allow_repause")),
        ("repause consumes an unknown decision", _validate_budget_decision_contract, lambda p: p["budget_decision_contract"]["invalid_response_cases"][0].__setitem__("decision", "allow_repause")),
        ("insufficient capacity publishes a Pause", _validate_budget_decision_contract, lambda p: p["budget_decision_contract"]["invalid_response_cases"][1].__setitem__("next_control_action", "publish_pause")),
        ("repause loses the exact head binding", _validate_budget_decision_contract, lambda p: p["budget_decision_contract"]["required_bindings"].__setitem__(-1, "arbitrary_head")),
        ("normal verdict freezes before successor CAS", _validate_consumption_failure, lambda p: change_handoff(p, "consumption_failure_contract", "boundary_commit_rule", "freeze_continue_before_successor_commit")),
        ("consumer failure rewrites normal External final", _validate_consumption_failure, lambda p: change_handoff(p, "consumption_failure_contract", "external_resolution", "interrupt")),
        ("consumer failure requires a fake artifact", _validate_consumption_failure, lambda p: change_handoff(p, "consumption_failure_contract", "artifact_rule", "register_failed_code_artifact")),
        ("consumer failure restarts verifier", _validate_consumption_failure, lambda p: change_handoff(p, "consumption_failure_contract", "stop_retry", "retry_verification")),
        ("consumer failure changes consumed Pause", _validate_consumption_failure, lambda p: p["state_machines"]["control_operation"]["consumption_failure_contract"]["safe_pause_disposition"].update(consumed="quarantined")),
        ("consumer failure takes another Run owner", _validate_consumption_failure, lambda p: p["state_machines"]["control_operation"]["consumption_failure_contract"]["atomic_ownership"].remove("cas_empty_run_terminal_owner_to_same_resume")),
        ("consumer failure bypasses stopping", _validate_control_operation, lambda p: control_variant(p, "resume_run", "continue_execution")["success_edges"].append(["consumption_failure_ownership_reserved", "consumption_failure_disposition_committed"])),
        ("unsafe consumer stop publishes failed lifecycle", _validate_consumption_failure, lambda p: p["state_machines"]["control_operation"]["consumption_failure_contract"]["classification"][2].update(outcome="failed_closure")),
        ("consumer failure loses original settlement", _validate_consumption_failure, lambda p: change_handoff(p, "consumption_failure_contract", "resource_rule", "settle_aggregate_again")),
        ("consumer failure permits another close", _validate_consumption_failure, lambda p: p["state_machines"]["control_operation"]["consumption_failure_contract"]["forbidden"].remove("new_close_run")),
        ("consumer failure omits invocation revocation", _validate_consumption_failure, lambda p: p["state_machines"]["control_operation"]["consumption_failure_contract"]["atomic_ownership"].remove("revoke_invocation_epoch")),

        ("external interrupt release accepts N/A", _validate_consumption_release_and_recovery, lambda p: next(u for u in p["evidence_unions"] if u["union_id"] == "ExternalConsumptionReleaseProof")["consumer_bindings"][1]["allowed_variants"].append("not_applicable")),
        ("release drops code artifact proof", _validate_consumption_release_and_recovery, lambda p: next(u for u in p["evidence_unions"] if u["union_id"] == "ExternalConsumptionReleaseProof")["variants"][0]["required_fields"].remove("canonical_code_artifact_head")),
        ("normal consumption omits binding release", _validate_control_operation, lambda p: control_variant(p, "resume_run", "continue_execution")["success_edges"].append(["invocation_authorized", "stable_boundary_committed"])),
        ("timeout consumption skips release", _validate_control_operation, lambda p: control_variant(p, "resolve_external_interrupt", "recoverable_timeout")["success_edges"].append(["interrupted_code_attempt_finished", "interrupted_code_checkpoint_committed"])),
        ("release mutates terminal history", _validate_consumption_release_and_recovery, lambda p: change_handoff(p, "external_consumption_release_contract", "history_rule", "clear_terminal_pause_binding")),
        ("release omits original reservation settlement", _validate_consumption_release_and_recovery, lambda p: p["state_machines"]["control_operation"]["external_consumption_release_contract"]["preconditions"].remove("settled_original_reservation")),
        ("release permits conflicting epochs", _validate_consumption_release_and_recovery, lambda p: change_handoff(p, "external_consumption_release_contract", "retry", "overwrite_any_epoch")),
        ("later END rejects recoverable interrupt owner", _validate_consumption_release_and_recovery, lambda p: change_handoff(p, "external_consumption_release_contract", "recoverable_interrupt_rule", "forbid_any_later_close")),
        ("recovery starts Code Agent without external result", _validate_consumption_release_and_recovery, lambda p: p["state_machines"]["control_operation"]["recovery_target_authorization_contract"]["continue_existing_target"]["allowed_target_kinds"].append("code_agent")),
        ("recovery scope is checked after claim", _validate_consumption_release_and_recovery, lambda p: change_handoff(p, "recovery_target_authorization_contract", "validation_phase", "invocation_authorized")),
        ("unknown protocol root field", _validate_protocol_structure, lambda p: p.update(unknown_schema_field=1)),
        ("unknown nested phase field", _validate_protocol_structure, lambda p: p["state_machines"]["control_operation"]["phase_contracts"]["operation_reserved"].update(unknown_schema_field=1)),
        ("non-finite number in direct protocol input", _validate_protocol_structure, lambda p: p.update(unknown_schema_field=float("nan"))),

        ("host timeout fabricates backend evidence", _validate_target_execution_paths, lambda p: p["state_machines"]["control_operation"]["recoverable_code_consumption_contract"]["result_source_contract"].update(backend_output_references="fabricated_seal_and_audit")),
        ("recoverable source remains scheduled", _validate_target_execution_paths, lambda p: change_handoff(p, "recoverable_code_consumption_contract", "attempt_status_sequence", ["scheduled"])),
        ("recoverable handoff omits failed artifact", _validate_target_execution_paths, lambda p: p["state_machines"]["control_operation"]["recoverable_code_consumption_contract"]["handoff_requires"].remove("canonical_failed_code_artifact")),
        ("timeout consumer reexecutes backend", _validate_target_execution_paths, lambda p: change_handoff(p, "recoverable_code_consumption_contract", "recovery", "retry_backend")),
        ("timeout consumer skips failed Attempt", _validate_branch_contracts, lambda p: control_variant(p, "resolve_external_interrupt", "recoverable_timeout")["success_edges"].append(["interrupted_code_result_registered", "result_committed"])),
        ("timeout consumer skips started Attempt", _validate_control_operation, lambda p: control_variant(p, "resolve_external_interrupt", "recoverable_timeout")["success_edges"].append(["interrupted_code_invocation_authorized", "interrupted_code_result_registered"])),
        ("timeout consumer skips final checkpoint", _validate_branch_contracts, lambda p: control_variant(p, "resolve_external_interrupt", "recoverable_timeout")["success_edges"].append(["interrupted_code_attempt_finished", "result_committed"])),
        ("interrupt authorizes Coordinator execution", _validate_policy_capability_and_terminal_contracts, lambda p: p["state_machines"]["control_operation"]["invocation_capability_contract"]["active_interrupt_result_consumption"].update(target_kind="decision_coordinator")),
        ("analysis snapshot may be absent", _validate_target_execution_paths, lambda p: change_handoff(p, "target_preparation_contract", "not_applicable_when", "any_target")),
        ("analysis preparation executes code", _validate_target_execution_paths, lambda p: p["state_machines"]["control_operation"]["target_preparation_contract"]["forbidden_effects"].remove("repository_code_execution")),
        ("analysis capability precedes preparation", _validate_control_operation, lambda p: control_variant(p, "advance_run", "not_applicable")["success_edges"].append(["transition_heads_verified", "invocation_capability_prepared"])),
        ("analysis loses effective tree binding", _validate_target_execution_paths, lambda p: next(u for u in p["evidence_unions"] if u["union_id"] == "TargetPreparationSnapshot")["variants"][0]["required_fields"].remove("expected_effective_tree_digest")),
        ("analysis preparation lacks epoch fence", _validate_target_execution_paths, lambda p: p["state_machines"]["control_operation"]["phase_contracts"]["target_preparation_committed"]["required_evidence"].remove("current_advance_epoch_and_terminal_revision")),

        ("normal terminal attached Pause loses its stop route", _validate_stop_route_contract, lambda p: p["stop_route_contract"].update(routes=[r for r in p["stop_route_contract"]["routes"] if r["external_context"] != "normal_terminal_attached_opened_pause"])),
        ("cancel unavailable bypasses settlement", _validate_control_operation, lambda p: next(o["variants"][0] for o in p["state_machines"]["control_operation"]["operations"] if o["operation_type"] == "cancel_pause")["success_edges"].append(["external_unavailable_verified", "pause_quarantined_recorded"])),
        ("dispatch omits external authority binding", _validate_stop_handoff_and_execution_lease, lambda p: p["state_machines"]["external_operation"]["phase_contracts"]["dispatch_authorized"]["required_evidence"].remove("committed_code_target_authorization")),
        ("expired lease skips started-record preflight", _validate_policy_capability_and_terminal_contracts, lambda p: p["state_machines"]["control_operation"]["invocation_capability_contract"]["execution_lease"]["acquire_or_replace_requires"].remove("no_started_record")),

        ("normal-result close overwrites the External resolution", _validate_stop_handoff_and_execution_lease, lambda p: change_handoff(p, "close_source_contract", "external_resolution_mutation", "overwrite")),
        ("normal-result close omits Pause ownership", _validate_stop_handoff_and_execution_lease, lambda p: change_handoff(p, "close_source_contract", "atomic_acquires", ["run_terminal_closure_owner"])),
        ("normal-result stop loses observed integrity failure", _validate_stop_handoff_and_execution_lease, lambda p: change_handoff(p, "close_source_contract", "system_stop_disposition", {"clear": "halted", "proven_overage_tamper_or_policy_violation": "halted"})),
        ("expired capability reopens producer tombstone", _validate_policy_capability_and_terminal_contracts, lambda p: change_lease(p, "producer_tombstone_mutation", True)),
        ("started invocation permits automatic lease takeover", _validate_policy_capability_and_terminal_contracts, lambda p: change_lease(p, "expired_after_started_or_uncertain", "automatic_reexecution")),
        ("lease renewal resets the budget", _validate_policy_capability_and_terminal_contracts, lambda p: change_lease(p, "renewal_limit", "reset_budget")),
        ("capability allows stale epoch effects", _validate_policy_capability_and_terminal_contracts, lambda p: change_lease(p, "old_epoch_effects", "allow")),
        ("unavailable accounting clips observed overage", _validate_stop_handoff_and_execution_lease, lambda p: change_handoff(p, "settlement_contract", "unavailable_charge", "clip_to_maximum")),
        ("settlement rejects interrupt or close owners", _validate_stop_handoff_and_execution_lease, lambda p: change_handoff(p, "settlement_contract", "owner_types", ["resume_run", "cancel_pause"])),
        ("pre-start backend may consume the target Attempt", _validate_policy_capability_and_terminal_contracts, lambda p: p["state_machines"]["control_operation"]["invocation_capability_contract"]["external_prestart_authority"].update(attempt_started=True)),
        ("code target may use inbound authorization as an Attempt lease", _validate_policy_capability_and_terminal_contracts, lambda p: p["state_machines"]["control_operation"]["invocation_capability_contract"]["authorization_scopes"].update(advance_target_code_agent="attempt_execution")),
        ("unavailable settlement evidence is missing", _validate_control_operation, lambda p: p["state_machines"]["control_operation"]["phase_contracts"]["unavailable_resource_disposition_committed"].update(required_evidence=[])),

        ("missing advance_run branch guard", _validate_branch_contracts, remove_advance_branch),
        ("start policy and ledger reversed", _validate_control_operation, reverse_start_policy_and_ledger),
        ("resume capability precedes checkpoint", _validate_control_operation, reverse_resume_checkpoint_and_capability),
        ("start graph and dependency declaration are reversed together", _validate_advance_and_interrupt_contracts, reverse_start_policy_and_ledger_with_dependencies),
        ("resume graph and dependency declaration are reversed together", _validate_control_operation, reverse_resume_checkpoint_and_capability_with_dependencies),
        ("pre-reservation interrupt requires a raw reservation digest", _validate_control_operation, restore_raw_reservation_digest),
        ("pre-reservation reservation absence proof is missing", _validate_evidence_unions, remove_pre_reservation_absence),
        ("recoverable timeout accepts a missing reservation", _validate_evidence_unions, allow_recoverable_absent_reservation),
        ("post-reservation interrupt accepts reservation absence", _validate_evidence_unions, allow_post_reservation_absence),
        ("present reservation accepts a null-reservation proof", _validate_evidence_unions, allow_present_reservation_null_proof),
        ("reservation snapshot omits ExternalOperation identity", _validate_evidence_unions, omit_resource_external_operation_identity),
        ("reservation snapshot is detached from the exact resolution tuple", _validate_evidence_unions, detach_resource_resolution_tuple),
        ("normal candidate stored on shared ExternalOperation state", _validate_transaction_domains_and_cas, store_normal_candidate_on_shared_state),
        ("normal unavailable candidate can win resolution", _validate_transaction_domains_and_cas, allow_normal_unavailable_candidate),
        ("late integrity evidence cannot upgrade the interrupt result", _validate_cross_machine_invariants, omit_late_integrity_precedence),
        ("controlled halt cannot upgrade to failed closure", _validate_advance_and_interrupt_contracts, remove_controlled_halt_failed_outcome),
        ("halted interrupt publishes a failed Run lifecycle", _validate_policy_capability_and_terminal_contracts, map_halted_interrupt_to_failed_run),
        ("safe cancel publishes a failed Run lifecycle", _validate_policy_capability_and_terminal_contracts, map_safe_cancel_to_failed_run),
        ("normal END publishes a halted Run lifecycle", _validate_policy_capability_and_terminal_contracts, map_normal_end_to_halted_run),
        ("explicit cancellation requires a live ExternalOperation", _validate_stop_route_contract, restrict_explicit_cancel_to_live_external),
        ("no-external system stop has no route", _validate_stop_route_contract, omit_no_external_system_stop_route),
        ("cancel branch and terminal resolution use different tuple domains", _validate_policy_capability_and_terminal_contracts, split_cancel_resolution_domain),
        ("replay consumes a fork source proof", _validate_evidence_unions, cross_wire_source_snapshot),
        ("legacy schema source can be forked", _validate_evidence_unions, allow_legacy_fork_source),
        ("versioned replay uses legacy revision evidence", _validate_evidence_unions, allow_modern_replay_with_legacy_revision),
        ("replay root proof carries fork-only state", _validate_evidence_unions, allow_replay_proof_to_carry_fork_state),
        ("fork head proof carries replay-only root input", _validate_evidence_unions, allow_fork_proof_to_carry_replay_root),
        ("fork accepts a running source head", _validate_evidence_unions, allow_running_fork_source),
        ("source snapshot omits source Run identity", _validate_evidence_unions, omit_source_run_identity),
        ("fork child policy is not frozen", _validate_control_operation, omit_child_policy),
        ("fork child policy bypasses scoped allowlist selection", _validate_policy_capability_and_terminal_contracts, allow_unscoped_fork_policy),
        ("legacy replay bypasses balanced policy default", _validate_policy_capability_and_terminal_contracts, change_legacy_replay_policy_default),
        ("deterministic test policy is admitted in runtime", _validate_policy_capability_and_terminal_contracts, allow_test_profile_in_runtime),
        ("legacy source policy is mislabeled as supported", _validate_policy_capability_and_terminal_contracts, classify_legacy_source_policy_as_supported),
        ("replay omits its source-policy classification proof", _validate_control_operation, omit_replay_policy_classification_proof),
        ("child policy publication omits its selection proof", _validate_policy_capability_and_terminal_contracts, omit_child_policy_selection_proof),
        ("advance capability activates before operation commit", _validate_policy_capability_and_terminal_contracts, activate_advance_capability_before_commit),
        ("start omits capability preparation", _validate_advance_and_interrupt_contracts, remove_start_capability_preparation),
        ("replay is absent from capability producers", _validate_policy_capability_and_terminal_contracts, remove_replay_capability_producer),
        ("advance END is allowed to produce a capability", _validate_policy_capability_and_terminal_contracts, allow_advance_end_capability),
        ("recoverable interrupt owns a Coordinator invocation", _validate_control_operation, restore_interrupt_owned_coordinator_transition),
        ("ordinary Transition has no ControlOperation", _validate_control_operation, remove_advance_operation),
        ("phase dependency coverage is incomplete", _validate_control_operation, omit_phase_dependency),
        ("stop proof omits post-stop stability", _validate_external_operation, omit_stop_dimension),
        ("Pause snapshot maps to the wrong interrupt disposition", _validate_evidence_unions, mismatch_pause_disposition),
        ("interrupt closure permits a second close_run", _validate_stop_route_contract, allow_second_close),
        ("cancel takes ownership from an interrupt winner", _validate_transaction_domains_and_cas, cancel_owns_interrupt_winner),
    ]
    if len(mutations) != EXPECTED_NEGATIVE_MUTATION_COUNT:
        raise ValidationError(
            "negative mutation suite count changed: "
            f"expected={EXPECTED_NEGATIVE_MUTATION_COUNT}, actual={len(mutations)}"
        )
    # Every rule must first accept the unchanged protocol. Semantic cases call
    # their named rule directly; neither layout nor freeze seals can satisfy them.
    for validator in dict.fromkeys(rule for _, rule, _ in mutations):
        validator(protocol)
    structural = sum(rule is _validate_protocol_structure for _, rule, _ in mutations)
    if structural != 3:
        raise ValidationError("mutation classification changed: expected 3 structural cases")
    for label, validator, mutate in mutations:
        candidate = deepcopy(protocol)
        mutate(candidate)
        _assert_protocol_mutation_rejected(candidate, label, validator)

def _validate_publication_order_mutations(protocol: dict[str, Any]) -> int:
    # Derive mutations from the input graphs, not the validator's safety order.
    # This exercises every linear publication boundary, including future phases.
    _validate_publication_order(protocol)
    count = 0
    covered = set()
    for pair, variant in _control_variant_index(protocol).items():
        phases = variant["phases"]
        if variant["success_edges"] != [list(edge) for edge in zip(phases, phases[1:])]:
            continue
        covered.add(pair)
        for index in range(1, len(phases) - 2):
            candidate = deepcopy(protocol)
            changed = _control_variant_index(candidate)[pair]
            reordered = list(phases)
            reordered[index:index + 2] = reversed(reordered[index:index + 2])
            changed["phases"] = reordered
            changed["success_edges"] = [list(edge) for edge in zip(reordered, reordered[1:])]
            changed["phase_dependencies"] = [
                {"producer_phase": a, "consumer_phase": b} for a, b in changed["success_edges"]
            ]
            _assert_protocol_mutation_rejected(candidate, f"{pair} reversed {phases[index:index + 2]}", _validate_publication_order)
            count += 1
        for index in range(1, len(phases) - 1):
            for mode in ["bypass", "missing", "unreachable"]:
                candidate = deepcopy(protocol)
                changed = _control_variant_index(candidate)[pair]
                before, phase, after = phases[index - 1:index + 2]
                if mode != "unreachable":
                    changed["success_edges"].append([before, after])
                if mode == "missing":
                    changed["phases"].remove(phase)
                    changed["success_edges"] = [edge for edge in changed["success_edges"] if phase not in edge]
                elif mode == "unreachable":
                    changed["success_edges"] = [edge for edge in changed["success_edges"] if edge[1] != phase]
                changed["phase_dependencies"] = [
                    {"producer_phase": a, "consumer_phase": b} for a, b in changed["success_edges"]
                ]
                _assert_protocol_mutation_rejected(candidate, f"{pair} {mode} {phase}", _validate_publication_order)
                count += 1
    if covered != {
        ("start_run", "not_applicable"), ("publish_pause", "not_applicable"),
        ("resume_run", "abandon_and_halt"), ("close_run", "not_applicable"),
        ("replay_run", "not_applicable"), ("fork_run", "not_applicable"),
    }:
        raise ValidationError("publication mutation coverage lost a required variant")
    return count


def _validate_strict_json_rejections(catalog: dict[str, Any], protocol_sha256: str) -> None:
    for number in ["NaN", "Infinity", "-Infinity", "1e999"]:
        try:
            _parse_strict_json('{"value": ' + number + '}')
        except ValidationError:
            continue
        raise ValidationError(f"strict JSON parser accepted {number}")
    for target in ["root", "requirement"]:
        candidate = deepcopy(catalog)
        obj = candidate if target == "root" else candidate["requirements"][0]
        obj["unknown_schema_field"] = True
        try:
            _validate_catalog(candidate, protocol_sha256)
        except ValidationError:
            continue
        raise ValidationError(f"catalog accepted unknown field at {target}")


def main() -> int:
    try:
        protocol = _load_strict_json(PROTOCOL_PATH)
        catalog = _load_strict_json(CATALOG_PATH)
        protocol_sha256 = _sha256(PROTOCOL_PATH)
        _validate_protocol(protocol)
        _validate_negative_protocol_mutations(protocol)
        publication_mutations = _validate_publication_order_mutations(protocol)
        _validate_catalog(catalog, protocol_sha256)
        _validate_strict_json_rejections(catalog, protocol_sha256)
        _validate_protocol_references()
        _validate_budget_decision_documents(protocol)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "Phase A control protocol validation passed: "
        f"protocol_sha256={protocol_sha256} "
        f"catalog_sha256={_sha256(CATALOG_PATH)} "
        f"requirements={len(catalog['requirements'])} "
        "checks=structure,semantics,freeze; mutations=101 semantic + 3 structural; "
        f"publication_order={publication_mutations}; json/catalog=6"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
