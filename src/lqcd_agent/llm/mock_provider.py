"""Deterministic no-network LLM provider used by tests and defaults."""

from __future__ import annotations

import json
from typing import Any

from lqcd_agent.analysis_programs.registry import matching_programs
from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def mock_proposal(value, role):
    """Fill deterministic mock records using the same wire schema as a real provider."""
    from .schemas import role_schema
    root = role_schema(role)['schema']

    def shape(value, schema):
        if '$ref' in schema:
            schema = root['$defs'][schema['$ref'].rsplit('/', 1)[1]]
        kind = schema.get('type')
        if kind == 'object' and isinstance(value, dict):
            return {key: shape(value.get(key, [] if spec.get('type') == 'array' else
                        '' if spec.get('type') == 'string' else None), spec)
                    for key, spec in schema['properties'].items()}
        if kind == 'array' and isinstance(value, list):
            return [shape(item, schema['items']) for item in value]
        return value

    return shape(value, root)


class MockLLMProvider:
    def __init__(self, config: LLMProviderConfig | None = None) -> None:
        self.config = config or LLMProviderConfig(
            provider="mock",
            default_model="deterministic-mock",
        )

    def _request_payload(self, request: LLMRequest) -> dict[str, Any] | None:
        if not request.messages:
            return None
        content = request.messages[-1].get("content", "")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _method_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        case_config = payload.get("case_config") if isinstance(payload.get("case_config"), dict) else {}
        repo_inventory = payload.get("repo_inventory") if isinstance(payload.get("repo_inventory"), dict) else {}
        gaps = repo_inventory.get("implementation_gaps", [])
        implementation_gaps = [str(gap) for gap in gaps] if isinstance(gaps, list) else []
        selected_programs = matching_programs(case_config, repo_inventory) if case_config.get('raw_data_path') else []
        program_requested = bool(case_config.get("raw_data_path")) and bool(
            _as_string_list(case_config.get("analysis_program_tags"))
            or _as_string_list(case_config.get("target_observables"))
        )
        missing_requested_program = program_requested and not selected_programs
        code_needed = bool(implementation_gaps) or missing_requested_program
        return {
            "status": "success",
            "summary": "Provider-backed mock Method Planner produced a structured method plan.",
            "warnings": [],
            "errors": [],
            "physics_goal": str(case_config.get("physics_goal") or payload.get("user_goal") or ""),
            "target_observables": _as_string_list(case_config.get("target_observables"))
            or ["provider_backed_mock_matrix_elements"],
            "method_steps": (
                ["Use selected registered analysis program(s) in provider-backed mock mode."]
                if selected_programs
                else ["Use validated provider-backed structured output in mock mode."]
            ),
            "required_inputs": ["case_config", "repo_inventory"],
            "implementation_gaps": implementation_gaps,
            "selected_analysis_programs": [p["name"] for p in selected_programs],
            "code_needed": code_needed,
            "coder_task_summary": (
                "Implement a reusable registered analysis program for the requested raw-data analysis."
                if missing_requested_program
                else "Address provider-reported implementation gaps."
                if code_needed
                else None
            ),
        }

    def _scientific_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence = payload.get('review_evidence') or {}
        return {'status': 'success', 'summary': 'Provider-backed mock Scientific Reviewer interpreted Host diagnostics.',
                'warnings': [], 'errors': [], 'findings': [], 'evidence': [], 'recommended_checks': [],
                'confidence': evidence.get('confidence', 'high')}

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = self._request_payload(request)
        if payload and payload.get("artifact_type") == "method_plan":
            content = json.dumps(mock_proposal(self._method_plan(payload), 'method_plan'), sort_keys=True)
        elif payload and payload.get("artifact_type") == "scientific_review_report":
            content = json.dumps(mock_proposal(self._scientific_review(payload), 'scientific_review_report'), sort_keys=True)
        else:
            content = json.dumps(
                {
                            "provider": "mock",
                    "status": "success",
                    "summary": "Deterministic mock LLM response.",
                    "message_count": len(request.messages),
                    "warnings": [],
                    "errors": [],
                },
                sort_keys=True,
            )
        return LLMResponse(
            provider="mock",
            model=self.config.default_model or "deterministic-mock",
            content=content,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
