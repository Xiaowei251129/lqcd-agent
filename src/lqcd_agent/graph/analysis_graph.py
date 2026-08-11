"""LangGraph StateGraph assembly for the mock runtime."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from lqcd_agent.graph.nodes import (
    analysis_engineer_node,
    codex_handoff_node,
    decision_coordinator_node,
    human_approval_gate_node,
    memory_report_node,
    method_planner_node,
    scientific_reviewer_node,
)
from lqcd_agent.graph.routing import (
    RouteSelection,
    committed_route,
    route_target_contract,
    select_after_analysis_engineer,
    select_after_codex_handoff,
    select_after_decision_coordinator,
    select_after_human_approval_gate,
    select_after_method_planner,
)
from lqcd_agent.graph.state import (
    AnalysisState,
    AttemptKind,
    commit_transition,
    execute_scheduled_attempt,
)


RouteSelector = Callable[[AnalysisState], RouteSelection]
RouteTargets = dict[str, tuple[str, AttemptKind] | None]


def _fixed_selection(route: str, reason: str) -> RouteSelector:
    def select(state: AnalysisState) -> RouteSelection:
        return {
            "route": route,
            **route_target_contract(route),
            "reason": reason,
            "fields": {"status": state["status"]},
            "evidence_references": {
                "scientific_review_report_path": state.get("scientific_review_report_path"),
                "memory_update_path": state.get("memory_update_path"),
                "final_report_path": state.get("final_report_path"),
            },
            "state_updates": {},
            "trigger_reason": "forward",
            "new_cycle": False,
        }

    return select


def execute_graph_node_transition(
    state: AnalysisState,
    *,
    node_name: str,
    attempt_kind: AttemptKind,
    node: Callable[[AnalysisState], AnalysisState],
    route_selector: RouteSelector,
    route_targets: RouteTargets,
) -> AnalysisState:
    completed = execute_scheduled_attempt(
        state,
        node_name=node_name,
        attempt_kind=attempt_kind,
        node=node,
    )
    selector_input = deepcopy(completed)
    selector_snapshot = deepcopy(selector_input)
    selection = route_selector(selector_input)
    if selector_input != selector_snapshot:
        raise ValueError("Route selector modified its input state.")
    route = selection["route"]
    if route not in route_targets:
        raise ValueError(f"Route {route} is not declared for {node_name}.")
    target = route_targets[route]
    target_node = target[0] if target else None
    target_kind = target[1] if target else None
    selected_target = (
        selection.get("target_node"),
        selection.get("target_attempt_kind"),
    )
    declared_target = (target_node, target_kind)
    if any(key in selection for key in ("target_node", "target_attempt_kind")):
        if selected_target != declared_target:
            raise ValueError(
                f"Route selection target {selected_target} does not match declared target {declared_target}."
            )
    else:
        selection["target_node"] = target_node
        selection["target_attempt_kind"] = target_kind
    return commit_transition(
        completed,
        source_node=node_name,
        route=route,
        reason=selection["reason"],
        fields=selection.get("fields", {}),
        evidence_references=selection.get("evidence_references", {}),
        state_updates=selection.get("state_updates", {}),
        target_node=target_node,
        target_attempt_kind=target_kind,
        trigger_reason=selection.get("trigger_reason", "forward"),
        new_cycle=selection.get("new_cycle", False),
        human_request_kind=selection.get("human_request_kind"),
        human_authorization_scope=selection.get("human_authorization_scope"),
    )


def _with_attempt_identity(
    node_name: str,
    attempt_kind: AttemptKind,
    node: Callable[[AnalysisState], AnalysisState],
    route_selector: RouteSelector,
    route_targets: RouteTargets,
) -> Callable[[AnalysisState], AnalysisState]:
    def wrapped(state: AnalysisState) -> AnalysisState:
        return execute_graph_node_transition(
            state,
            node_name=node_name,
            attempt_kind=attempt_kind,
            node=node,
            route_selector=route_selector,
            route_targets=route_targets,
        )

    return wrapped


def build_state_graph() -> StateGraph:
    graph = StateGraph(AnalysisState)
    graph.add_node(
        "method_planner",
        _with_attempt_identity(
            "method_planner",
            "method_planner",
            method_planner_node,
            select_after_method_planner,
            {
                "analysis_engineer": ("analysis_engineer", "analysis_engineer"),
                "codex_handoff": ("codex_handoff", "legacy_codex_handoff"),
                "decision_coordinator": ("decision_coordinator", "decision_coordinator"),
                "end": None,
            },
        ),
    )
    graph.add_node(
        "codex_handoff",
        _with_attempt_identity(
            "codex_handoff",
            "legacy_codex_handoff",
            codex_handoff_node,
            select_after_codex_handoff,
            {
                "analysis_engineer": ("analysis_engineer", "analysis_engineer"),
                "end": None,
            },
        ),
    )
    graph.add_node(
        "analysis_engineer",
        _with_attempt_identity(
            "analysis_engineer",
            "analysis_engineer",
            analysis_engineer_node,
            select_after_analysis_engineer,
            {
                "scientific_reviewer": ("scientific_reviewer", "scientific_reviewer"),
                "codex_handoff": ("codex_handoff", "legacy_codex_handoff"),
                "method_planner": ("method_planner", "method_planner"),
                "decision_coordinator": ("decision_coordinator", "decision_coordinator"),
            },
        ),
    )
    graph.add_node(
        "scientific_reviewer",
        _with_attempt_identity(
            "scientific_reviewer",
            "scientific_reviewer",
            scientific_reviewer_node,
            _fixed_selection("decision_coordinator", "Scientific review always returns control to the Coordinator."),
            {"decision_coordinator": ("decision_coordinator", "decision_coordinator")},
        ),
    )
    graph.add_node(
        "decision_coordinator",
        _with_attempt_identity(
            "decision_coordinator",
            "decision_coordinator",
            decision_coordinator_node,
            select_after_decision_coordinator,
            {
                "human_approval_gate": ("human_approval_gate", "human_gate"),
                "memory_report": ("memory_report", "memory_report"),
            },
        ),
    )
    graph.add_node(
        "human_approval_gate",
        _with_attempt_identity(
            "human_approval_gate",
            "human_gate",
            human_approval_gate_node,
            select_after_human_approval_gate,
            {
                "analysis_engineer": ("analysis_engineer", "analysis_engineer"),
                "codex_handoff": ("codex_handoff", "legacy_codex_handoff"),
                "memory_report": ("memory_report", "memory_report"),
                "end": None,
            },
        ),
    )
    graph.add_node(
        "memory_report",
        _with_attempt_identity(
            "memory_report",
            "memory_report",
            memory_report_node,
            _fixed_selection("end", "Memory and Report is the terminal graph sink."),
            {"end": None},
        ),
    )

    graph.add_edge(START, "method_planner")
    graph.add_conditional_edges(
        "method_planner",
        committed_route,
        {
            "analysis_engineer": "analysis_engineer",
            "codex_handoff": "codex_handoff",
            "decision_coordinator": "decision_coordinator",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "codex_handoff",
        committed_route,
        {
            "analysis_engineer": "analysis_engineer",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "analysis_engineer",
        committed_route,
        {
            "scientific_reviewer": "scientific_reviewer",
            "codex_handoff": "codex_handoff",
            "method_planner": "method_planner",
            "decision_coordinator": "decision_coordinator",
        },
    )
    graph.add_edge("scientific_reviewer", "decision_coordinator")
    graph.add_conditional_edges(
        "decision_coordinator",
        committed_route,
        {
            "human_approval_gate": "human_approval_gate",
            "memory_report": "memory_report",
        },
    )
    graph.add_conditional_edges(
        "human_approval_gate",
        committed_route,
        {
            "analysis_engineer": "analysis_engineer",
            "codex_handoff": "codex_handoff",
            "memory_report": "memory_report",
            "end": END,
        },
    )
    graph.add_edge("memory_report", END)
    return graph


def compile_analysis_graph(checkpointer: Any):
    return build_state_graph().compile(checkpointer=checkpointer)
