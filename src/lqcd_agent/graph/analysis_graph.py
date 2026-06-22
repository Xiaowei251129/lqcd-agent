"""LangGraph StateGraph assembly for the mock runtime."""

from __future__ import annotations

from typing import Any

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
    route_after_analysis_engineer,
    route_after_codex_handoff,
    route_after_decision_coordinator,
    route_after_human_approval_gate,
    route_after_method_planner,
)
from lqcd_agent.graph.state import AnalysisState


def build_state_graph() -> StateGraph:
    graph = StateGraph(AnalysisState)
    graph.add_node("method_planner", method_planner_node)
    graph.add_node("codex_handoff", codex_handoff_node)
    graph.add_node("analysis_engineer", analysis_engineer_node)
    graph.add_node("scientific_reviewer", scientific_reviewer_node)
    graph.add_node("decision_coordinator", decision_coordinator_node)
    graph.add_node("human_approval_gate", human_approval_gate_node)
    graph.add_node("memory_report", memory_report_node)

    graph.add_edge(START, "method_planner")
    graph.add_conditional_edges(
        "method_planner",
        route_after_method_planner,
        {
            "analysis_engineer": "analysis_engineer",
            "codex_handoff": "codex_handoff",
            "decision_coordinator": "decision_coordinator",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "codex_handoff",
        route_after_codex_handoff,
        {
            "analysis_engineer": "analysis_engineer",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "analysis_engineer",
        route_after_analysis_engineer,
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
        route_after_decision_coordinator,
        {
            "human_approval_gate": "human_approval_gate",
            "memory_report": "memory_report",
        },
    )
    graph.add_conditional_edges(
        "human_approval_gate",
        route_after_human_approval_gate,
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
