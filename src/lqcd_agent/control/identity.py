"""Canonical Run and Attempt identities, independent of orchestration and I/O."""
from __future__ import annotations
from typing import Literal


def execution_id(prefix: str, index: int, *, width: int = 6) -> str:
    return f"{prefix}_{index:0{width}d}"


AttemptKind = Literal['method_planner', 'code_agent', 'analysis_engineer', 'scientific_reviewer', 'decision_coordinator', 'human_gate', 'memory_report']


ATTEMPT_KIND_BY_NODE: dict[str, AttemptKind] = {'method_planner': 'method_planner', 'code_agent': 'code_agent', 'analysis_engineer': 'analysis_engineer', 'scientific_reviewer': 'scientific_reviewer', 'decision_coordinator': 'decision_coordinator', 'human_approval_gate': 'human_gate', 'human_gate': 'human_gate', 'memory_report': 'memory_report'}


def stable_checkpoint_thread_id(case_id: str, run_id: str) -> str:
    return f'{case_id}:{run_id}'


def stable_cycle_id(cycle_index: int) -> str:
    return f'cycle_{cycle_index:04d}'


def stable_attempt_id(attempt_index: int) -> str:
    return f'attempt_{attempt_index:06d}'


def stable_transition_id(transition_index: int) -> str:
    return f'transition_{transition_index:06d}'


def stable_human_request_id(request_index: int) -> str:
    return f'human_request_{request_index:06d}'


def stable_human_response_id(response_index: int) -> str:
    return f'human_response_{response_index:06d}'


def canonical_attempt_kind(node_name: str) -> AttemptKind:
    try:
        return ATTEMPT_KIND_BY_NODE[node_name]
    except KeyError as exc:
        raise ValueError(f'Unsupported graph node for Attempt identity: {node_name}') from exc
