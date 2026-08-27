#!/usr/bin/env python3
"""Validate the Phase A machine-readable control protocol and requirement catalog."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "tickets" / "phase-a-control-contracts"
PROTOCOL_PATH = CONTRACT_DIR / "CONTROL_PROTOCOL_0_4.json"
CATALOG_PATH = CONTRACT_DIR / "PHASE_B_REQUIREMENT_CATALOG.json"

EXPECTED_OPERATION_VARIANTS = {
    "start_run": {"not_applicable"},
    "publish_pause": {"not_applicable"},
    "resume_run": {"continue_execution", "abandon_and_halt"},
    "cancel_pause": {"not_applicable"},
    "replay_run": {"not_applicable"},
    "fork_run": {"not_applicable"},
    "close_run": {"not_applicable"},
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
                {"operation_variant", "initial_phase", "committed_phase", "phases", "success_edges"},
                f"{operation_type} variant",
            )
            variant_name = variant["operation_variant"]
            if variant_name in seen_variants:
                raise ValidationError(f"duplicate {operation_type} variant: {variant_name}")
            seen_variants.add(variant_name)
            phases = _require_unique_strings(variant["phases"], f"{operation_type}.{variant_name}.phases")
            _validate_terminating_graph(
                nodes=phases,
                edges=variant["success_edges"],
                initial=variant["initial_phase"],
                terminals=[variant["committed_phase"]],
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


def _validate_external_operation(protocol: dict[str, Any]) -> None:
    machine = protocol["state_machines"]["external_operation"]
    phases = _require_unique_strings(machine["phases"], "external_operation.phases")
    terminals = _require_unique_strings(machine["terminal_phases"], "external_operation.terminal_phases")
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
    interrupt_statuses = set(
        _require_unique_strings(machine["interrupt_terminal_statuses"], "external_operation.interrupt_terminal_statuses")
    )
    if not terminal_statuses <= statuses:
        raise ValidationError("external_operation terminal statuses are invalid")
    if interrupt_statuses != {"failed", "recovery_required"} or not interrupt_statuses <= terminal_statuses:
        raise ValidationError("external_operation interrupt terminal statuses are invalid")
    if machine.get("interrupt_rule") != "any_nonterminal_phase_may_atomically_enter_interrupt_terminal_status_and_freeze_phase":
        raise ValidationError("external_operation interrupt rule mismatch")
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
    expected_visibility = (
        "prepared_is_private; opened_requires_public_paused_checkpoint; "
        "claimed_is_transitional_and_not_resumable; consumed_and_cancelled_are_irreversible"
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
        "CTRL-TERM-001",
        "CTRL-TERM-002",
        "PAUSE-LIFE-001",
        "EXT-CANCEL-001",
        "CONT-001",
        "VERSION-001",
    }
    if set(by_id) != required_ids:
        raise ValidationError(f"cross-machine invariant IDs mismatch: {sorted(set(by_id))}")
    control_contracts = protocol["state_machines"]["control_operation"]["phase_contracts"]
    for invariant_id in ("CTRL-OWN-001", "CTRL-OWN-002"):
        invariant = by_id[invariant_id]
        phase = invariant["phase"]
        must_acquire = set(invariant["must_acquire"])
        contract = control_contracts.get(phase)
        if contract is None or set(contract["acquires"]) != must_acquire or contract.get("atomic_acquire") is not True:
            raise ValidationError(f"{invariant_id} does not match its phase acquisition contract")
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
    external_machine = protocol["state_machines"]["external_operation"]
    final_proof = by_id["EXT-CANCEL-001"]
    if set(final_proof["producer_terminal_phases"]) != set(external_machine["terminal_phases"]):
        raise ValidationError("EXT-CANCEL-001 does not exhaust the terminal producer phases")
    if set(final_proof["forbidden_intermediate_phases"]) != {"termination_evidence_committed"}:
        raise ValidationError("EXT-CANCEL-001 has an invalid intermediate proof set")
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
        "effect_classes",
        "continuation_policies",
        "outcome_classes",
        "state_machines",
        "dependency_dags",
        "field_bindings",
        "cross_machine_invariants",
        "compatibility",
    }
    _require_keys(protocol, required_top_level, "control protocol")
    if protocol["schema_version"] != "0.1" or protocol["protocol_version"] != "0.4":
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
    if catalog["schema_version"] != "0.1" or catalog["catalog_version"] != "0.1.0":
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


def main() -> int:
    try:
        protocol = _load_strict_json(PROTOCOL_PATH)
        catalog = _load_strict_json(CATALOG_PATH)
        protocol_sha256 = _sha256(PROTOCOL_PATH)
        _validate_protocol(protocol)
        _validate_catalog(catalog, protocol_sha256)
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
