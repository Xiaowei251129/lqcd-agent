"""Bounded JSON-only prompt builders for provider-backed agents."""

from __future__ import annotations

import json
from typing import Any

from lqcd_agent.llm.base import LLMRequest


MAX_CONTEXT_CHARS = 6000


def _bounded_json(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True)
    if len(text) <= MAX_CONTEXT_CHARS:
        return text
    truncated = {
        "schema_version": payload.get("schema_version", "0.1"),
        "artifact_type": payload.get("artifact_type"),
        "run_id": payload.get("run_id"),
        "case_id": payload.get("case_id"),
        "truncated": True,
        "summary": "Prompt context exceeded the Phase 10B bound; use artifact paths and summaries only.",
    }
    return json.dumps(truncated, sort_keys=True)


def _request(*, agent_name: str, payload: dict[str, Any]) -> LLMRequest:
    return LLMRequest(
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are the {agent_name}. Return exactly one JSON object. "
                    "Do not include markdown, prose, secrets, or raw numeric data. "
                    "The object must satisfy output_contract exactly, including exact_values."
                ),
            },
            {"role": "user", "content": _bounded_json(payload)},
        ],
        response_format="json_object",
    )


def _output_contract(
    *,
    producer: str,
    run_id: str,
    case_id: str,
    fields: list[str],
    status_values: list[str] | None = None,
) -> dict[str, Any]:
    base_fields = [
        "schema_version",
        "run_id",
        "case_id",
        "producer",
        "status",
        "summary",
        "warnings",
        "errors",
    ]
    return {
        "required_fields": base_fields + fields,
        "exact_values": {
            "schema_version": "0.1",
            "run_id": run_id,
            "case_id": case_id,
            "producer": producer,
        },
        "field_types": {
            "schema_version": "string",
            "run_id": "string",
            "case_id": "string",
            "producer": "string",
            "status": "string",
            "summary": "string",
            "warnings": "array of objects, not strings",
            "errors": "array of objects, not strings",
        },
        "allowed_status_values": status_values or ["success", "failed", "pending", "needs_more_info"],
    }


def build_method_planner_request(
    *,
    run_id: str,
    case_id: str,
    user_goal: str | None,
    case_config: dict[str, Any] | None,
    repo_inventory: dict[str, Any] | None,
) -> LLMRequest:
    return _request(
        agent_name="Method Planner Agent",
        payload={
            "schema_version": "0.1",
            "artifact_type": "method_plan",
            "run_id": run_id,
            "case_id": case_id,
            "user_goal": user_goal,
            "case_config": case_config,
            "repo_inventory": repo_inventory,
            "required_output_fields": [
                "physics_goal",
                "target_observables",
                "method_steps",
                "required_inputs",
                "required_outputs",
                "implementation_gaps",
                "code_needed",
                "coder_task_summary",
            ],
            "output_contract": _output_contract(
                producer="method_planner",
                run_id=run_id,
                case_id=case_id,
                fields=[
                    "physics_goal",
                    "target_observables",
                    "method_steps",
                    "required_inputs",
                    "required_outputs",
                    "implementation_gaps",
                    "code_needed",
                    "coder_task_summary",
                ],
                status_values=["success", "failed", "pending", "needs_more_info"],
            )
            | {
                "status_policy": (
                    "Use status=success when the plan can proceed to analysis. "
                    "Use needs_more_info or pending only when critical inputs are missing and downstream analysis must stop."
                ),
                "field_types": {
                    **_output_contract(
                        producer="method_planner",
                        run_id=run_id,
                        case_id=case_id,
                        fields=[],
                    )["field_types"],
                    "physics_goal": "string",
                    "target_observables": "array",
                    "method_steps": "array",
                    "required_inputs": "array",
                    "required_outputs": "array",
                    "implementation_gaps": "array",
                    "code_needed": "boolean",
                    "coder_task_summary": "string or null",
                }
            },
        },
    )


def build_scientific_reviewer_request(
    *,
    run_id: str,
    case_id: str,
    run_result_path: str | None,
    analysis_outputs_dir: str | None,
    method_plan_path: str | None,
    run_result_summary: dict[str, Any] | None = None,
    matrix_element_summary: dict[str, Any] | None = None,
    method_plan_summary: dict[str, Any] | None = None,
) -> LLMRequest:
    return _request(
        agent_name="Scientific Reviewer Agent",
        payload={
            "schema_version": "0.1",
            "artifact_type": "scientific_review_report",
            "run_id": run_id,
            "case_id": case_id,
            "run_result_path": run_result_path,
            "analysis_outputs_dir": analysis_outputs_dir,
            "method_plan_path": method_plan_path,
            "run_result_summary": run_result_summary,
            "matrix_element_summary": matrix_element_summary,
            "method_plan_summary": method_plan_summary,
            "required_output_fields": [
                "correlator_diagnostics",
                "fit_diagnostics",
                "matrix_element_diagnostics",
                "findings",
                "evidence",
                "recommended_checks",
                "confidence",
            ],
            "output_contract": _output_contract(
                producer="scientific_reviewer",
                run_id=run_id,
                case_id=case_id,
                fields=[
                    "correlator_diagnostics",
                    "fit_diagnostics",
                    "matrix_element_diagnostics",
                    "findings",
                    "evidence",
                    "recommended_checks",
                    "confidence",
                ],
                status_values=["success", "failed", "pending", "needs_more_info"],
            )
            | {
                "status_policy": (
                    "Use status=success when the review artifact is complete, even if it contains warnings. "
                    "Warnings belong in warnings; they do not make the artifact status pending."
                ),
                "field_types": {
                    **_output_contract(
                        producer="scientific_reviewer",
                        run_id=run_id,
                        case_id=case_id,
                        fields=[],
                    )["field_types"],
                    "correlator_diagnostics": "object",
                    "fit_diagnostics": "object",
                    "matrix_element_diagnostics": "object",
                    "findings": "array of objects, not strings",
                    "evidence": "array of objects, not strings",
                    "recommended_checks": "array",
                    "confidence": "high | medium | low",
                }
            },
        },
    )


def build_decision_coordinator_request(
    *,
    run_id: str,
    case_id: str,
    method_plan_path: str | None,
    run_result_path: str | None,
    scientific_review_report_path: str | None,
    method_plan_summary: dict[str, Any] | None = None,
    run_result_summary: dict[str, Any] | None = None,
    scientific_review_summary: dict[str, Any] | None = None,
) -> LLMRequest:
    return _request(
        agent_name="Decision Coordinator Agent",
        payload={
            "schema_version": "0.1",
            "artifact_type": "decision_log",
            "run_id": run_id,
            "case_id": case_id,
            "method_plan_path": method_plan_path,
            "run_result_path": run_result_path,
            "scientific_review_report_path": scientific_review_report_path,
            "method_plan_summary": method_plan_summary,
            "run_result_summary": run_result_summary,
            "scientific_review_summary": scientific_review_summary,
            "allowed_actual_routes": ["human_approval_gate", "memory_report"],
            "output_contract": _output_contract(
                producer="decision_coordinator",
                run_id=run_id,
                case_id=case_id,
                fields=[
                    "risk_level",
                    "recommended_action",
                    "human_approval_required",
                    "reasons",
                    "evidence",
                    "next_actions",
                    "routing_decision",
                ],
                status_values=["success", "failed", "pending", "needs_more_info"],
            )
            | {
                "status_policy": (
                    "Use status=success only for low risk. Use status=pending for medium, high, or critical risk. "
                    "Set human_approval_required=true for high or critical risk."
                ),
                "field_types": {
                    **_output_contract(
                        producer="decision_coordinator",
                        run_id=run_id,
                        case_id=case_id,
                        fields=[],
                    )["field_types"],
                    "risk_level": "low | medium | high | critical",
                    "recommended_action": "string",
                    "human_approval_required": "boolean",
                    "reasons": "array of objects, not strings",
                    "evidence": "array of objects, not strings",
                    "next_actions": "array of objects with exactly one primary=true item",
                    "routing_decision": "object with actual_route, requested_route, proposed_follow_up_route, fields",
                },
                "routing_decision_contract": {
                    "allowed_actual_routes": ["human_approval_gate", "memory_report"],
                    "allowed_follow_up_routes": ["human_approval_gate", "memory_report", "analysis_engineer", "codex_handoff"],
                    "fields_must_include": [
                        "risk_level",
                        "recommended_action",
                        "human_approval_required",
                        "rerun_requested",
                        "rerun_target",
                        "code_fix_requested",
                    ],
                },
            },
        },
    )
