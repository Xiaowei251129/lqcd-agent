"""Bounded JSON-only prompt builders for provider-backed agents."""

from __future__ import annotations

import json
from typing import Any

from lqcd_agent.llm.base import LLMRequest


MAX_CONTEXT_CHARS = 6000


class ContextLimitError(ValueError):
    code = "context_limit_exceeded"


def _string_schema(enum: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string"}
    if enum is not None:
        schema["enum"] = enum
    return schema


def _object_schema(properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    properties = properties or {}
    return {
        "type": "object",
        "properties": properties,
        "required": required or list(properties),
        "additionalProperties": False,
    }


def _loose_value_schema() -> dict[str, Any]:
    return {
        "anyOf": [
            {"type": "string"},
            {"type": "number"},
            {"type": "integer"},
            {"type": "boolean"},
            {"type": "null"},
            {"type": "array", "items": {"type": "string"}},
        ]
    }


def _record_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "code": {"type": ["string", "null"]},
            "message": {"type": ["string", "null"]},
            "section": {"type": ["string", "null"]},
            "severity": {"type": ["string", "null"]},
            "path": {"type": ["string", "null"]},
            "field": {"type": ["string", "null"]},
            "value": _loose_value_schema(),
            "decision_coordinator_flag": {"type": ["boolean", "null"]},
            "source": {"type": ["string", "null"]},
            "artifact": {"type": ["string", "null"]},
            "action": {"type": ["string", "null"]},
            "primary": {"type": ["boolean", "null"]},
            "target": {"type": ["string", "null"]},
            "status": {"type": ["string", "null"]},
        }
    )


def _loose_object_array_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _record_schema(),
    }


def _string_array_schema() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}}


def _base_artifact_properties(
    *,
    producer: str,
    run_id: str,
    case_id: str,
    status_values: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": _string_schema(["0.1"]),
        "run_id": _string_schema([run_id]),
        "case_id": _string_schema([case_id]),
        "created_at": {"type": "string"},
        "producer": _string_schema([producer]),
        "status": _string_schema(status_values or ["success", "failed", "pending", "needs_more_info"]),
        "summary": {"type": "string"},
        "warnings": _loose_object_array_schema(),
        "errors": _loose_object_array_schema(),
    }


def _artifact_schema(
    *,
    name: str,
    producer: str,
    run_id: str,
    case_id: str,
    fields: dict[str, Any],
    status_values: list[str] | None = None,
) -> dict[str, Any]:
    properties = _base_artifact_properties(
        producer=producer,
        run_id=run_id,
        case_id=case_id,
        status_values=status_values,
    )
    properties.update(fields)
    return {
        "name": name,
        "strict": True,
        "schema": _object_schema(properties),
    }


def _diagnostics_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "status": {"type": "string"},
            "summary": {"type": "string"},
            "evidence": _loose_object_array_schema(),
            "findings": _loose_object_array_schema(),
            "warnings": _loose_object_array_schema(),
            "recommended_checks": _string_array_schema(),
        }
    )


def _method_plan_json_schema(*, run_id: str, case_id: str) -> dict[str, Any]:
    selected_program_schema = _object_schema(
        {
            "name": {"type": "string"},
            "category": {"type": "string"},
            "callable_path": {"type": "string"},
            "input_mapping": _object_schema(
                {
                    "times": {"type": "string"},
                    "correlator_values": {"type": "string"},
                    "correlator_errors": {"type": ["string", "null"]},
                },
            ),
            "output_path": {"type": "string"},
            "required_outputs": _string_array_schema(),
        }
    )
    return _artifact_schema(
        name="method_plan",
        producer="method_planner",
        run_id=run_id,
        case_id=case_id,
        status_values=["success", "failed", "pending", "needs_more_info"],
        fields={
            "physics_goal": {"type": "string"},
            "target_observables": _string_array_schema(),
            "method_steps": _string_array_schema(),
            "required_inputs": _string_array_schema(),
            "required_outputs": _string_array_schema(),
            "implementation_gaps": _string_array_schema(),
            "selected_analysis_programs": {"type": "array", "items": selected_program_schema},
            "code_needed": {"type": "boolean"},
            "coder_task_summary": {"type": ["string", "null"]},
        },
    )


def _scientific_review_json_schema(*, run_id: str, case_id: str) -> dict[str, Any]:
    return _artifact_schema(
        name="scientific_review_report",
        producer="scientific_reviewer",
        run_id=run_id,
        case_id=case_id,
        status_values=["success", "failed", "pending", "needs_more_info"],
        fields={
            "correlator_diagnostics": _diagnostics_schema(),
            "fit_diagnostics": _diagnostics_schema(),
            "matrix_element_diagnostics": _diagnostics_schema(),
            "findings": _loose_object_array_schema(),
            "evidence": _loose_object_array_schema(),
            "recommended_checks": _string_array_schema(),
            "confidence": _string_schema(["high", "medium", "low"]),
        },
    )


def _decision_log_json_schema(*, run_id: str, case_id: str) -> dict[str, Any]:
    routing_fields_schema = _object_schema(
        {
            "risk_level": _string_schema(["low", "medium", "high", "critical"]),
            "recommended_action": {"type": "string"},
            "human_approval_required": {"type": "boolean"},
            "rerun_requested": {"type": "boolean"},
            "rerun_target": {"type": ["string", "null"]},
            "code_fix_requested": {"type": "boolean"},
        }
    )
    return _artifact_schema(
        name="decision_log",
        producer="decision_coordinator",
        run_id=run_id,
        case_id=case_id,
        status_values=["success", "failed", "pending", "needs_more_info"],
        fields={
            "risk_level": _string_schema(["low", "medium", "high", "critical"]),
            "recommended_action": {"type": "string"},
            "human_approval_required": {"type": "boolean"},
            "reasons": _loose_object_array_schema(),
            "evidence": _loose_object_array_schema(),
            "next_actions": _loose_object_array_schema(),
            "routing_decision": _object_schema(
                {
                    "actual_route": _string_schema(["human_approval_gate", "memory_report"]),
                    "requested_route": _string_schema(
                        ["human_approval_gate", "memory_report", "analysis_engineer", "codex_handoff"]
                    ),
                    "proposed_follow_up_route": _string_schema(
                        ["human_approval_gate", "memory_report", "analysis_engineer", "codex_handoff"]
                    ),
                    "fields": routing_fields_schema,
                }
            ),
        },
    )


def _bounded_json(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(text) > MAX_CONTEXT_CHARS:
        raise ContextLimitError(
            f"Prompt context exceeds {MAX_CONTEXT_CHARS} characters; reduce the supplied context before retrying.")
    return text


def _request(*, agent_name: str, payload: dict[str, Any], json_schema: dict[str, Any]) -> LLMRequest:
    output_contract = payload.get("output_contract")
    if isinstance(output_contract, dict):
        output_contract["schema_name"] = json_schema["name"]
        output_contract["strict_json_schema"] = True
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
        response_format="json_schema",
        json_schema=json_schema,
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
        json_schema=_method_plan_json_schema(run_id=run_id, case_id=case_id),
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
                "selected_analysis_programs",
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
                    "selected_analysis_programs",
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
                "registered_program_policy": (
                    "If repo_inventory.analysis_programs contains reusable programs whose tags, required_inputs, "
                    "and produced_outputs satisfy case_config, put those programs in selected_analysis_programs. "
                    "Each selected item must include name, category, callable_path, input_mapping, output_path, "
                    "and required_outputs. Set code_needed=false when selected reusable programs are sufficient. "
                    "Use selected_analysis_programs=[] when no registered program is suitable. "
                    "For raw CSV inputs, input_mapping values must be executable source selectors of the form "
                    "raw_data_csv.<exact_column_name>, for example raw_data_csv.t and raw_data_csv.value. "
                    "If an error column is available for a two-point correlator program, include "
                    "correlator_errors=raw_data_csv.error as an optional propagated-uncertainty input. "
                    "Never use natural-language descriptions such as 'CSV time coordinate column'."
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
                    "selected_analysis_programs": (
                        "array of objects; each input_mapping value must be raw_data_csv.<exact_column_name> "
                        "when mapping from raw_data_path CSV data; correlator_errors may be included when an error column exists"
                    ),
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
    fit_diagnostics_summary: dict[str, Any] | None = None,
    matrix_element_summary: dict[str, Any] | None = None,
    method_plan_summary: dict[str, Any] | None = None,
    review_scope: dict[str, Any] | None = None,
) -> LLMRequest:
    return _request(
        agent_name="Scientific Reviewer Agent",
        json_schema=_scientific_review_json_schema(run_id=run_id, case_id=case_id),
        payload={
            "schema_version": "0.1",
            "artifact_type": "scientific_review_report",
            "run_id": run_id,
            "case_id": case_id,
            "run_result_path": run_result_path,
            "analysis_outputs_dir": analysis_outputs_dir,
            "method_plan_path": method_plan_path,
            "run_result_summary": run_result_summary,
            "fit_diagnostics_summary": fit_diagnostics_summary,
            "matrix_element_summary": matrix_element_summary,
            "method_plan_summary": method_plan_summary,
            "review_scope": review_scope,
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
                "scope_policy": (
                    "Use review_scope to decide which diagnostics apply. If "
                    "requires_matrix_element_validation is false, keep matrix_element_diagnostics present but set "
                    "status=not_applicable and do not warn about missing synthetic_matrix_elements.json. "
                    "For effective-mass outputs, validate the fit_diagnostics evidence instead."
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
        json_schema=_decision_log_json_schema(run_id=run_id, case_id=case_id),
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
