"""Deterministic no-network LLM provider used by tests and defaults."""

from __future__ import annotations

import json
from typing import Any

from lqcd_agent.analysis_programs.registry import matching_programs
from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse, ProviderReadiness


def _flag_severity(value: Any) -> str:
    text = str(value).lower()
    if "severe" in text or "critical" in text or "fail" in text or "invalid" in text:
        return "severe"
    return "warning"


def _review_warning_from_flag(flag: Any, *, path: Any, index: int) -> dict[str, Any]:
    severity = _flag_severity(flag)
    return {
        "section": "matrix_element",
        "code": "upstream_diagnostic_flag",
        "severity": severity,
        "decision_coordinator_flag": severity == "severe",
        "message": "The provider-backed mock reviewer preserved an upstream diagnostic flag.",
        "path": path,
        "field": f"diagnostic_flags[{index}]",
        "value": flag,
    }


def _has_severe_warning(warnings: list[Any]) -> bool:
    return any(
        isinstance(warning, dict)
        and (warning.get("severity") == "severe" or warning.get("decision_coordinator_flag") is True)
        for warning in warnings
    )


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
            schema_version="0.1",
            provider="mock",
            default_model="deterministic-mock",
            dry_run_only=True,
        )

    def readiness(self) -> ProviderReadiness:
        return ProviderReadiness(
            provider="mock",
            ready=True,
            live_enabled=False,
            missing_env_vars=[],
            model_configured=True,
            api_base_configured=True,
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
        matrix_summary = payload.get("matrix_element_summary")
        if not isinstance(matrix_summary, dict):
            matrix_summary = {}
        review_scope = payload.get("review_scope")
        if not isinstance(review_scope, dict):
            review_scope = {}
        requires_matrix = review_scope.get("requires_matrix_element_validation", True)
        fit_diagnostics = payload.get("fit_diagnostics_summary")
        if not isinstance(fit_diagnostics, dict):
            fit_diagnostics = {"status": "not_populated_mvp"}
        fit_diagnostics = {**fit_diagnostics, 'findings': [
            {'message': item} if isinstance(item, str) else item
            for item in fit_diagnostics.get('findings', [])]}
        run_summary = payload.get("run_result_summary")
        if not isinstance(run_summary, dict):
            run_summary = {}
        warnings: list[dict[str, Any]] = []
        flags = matrix_summary.get("diagnostic_flags", [])
        if requires_matrix and isinstance(flags, list):
            warnings.extend(
                _review_warning_from_flag(flag, path=matrix_summary.get("path"), index=index)
                for index, flag in enumerate(flags)
            )
        if run_summary.get("run_success") is False:
            warnings.append(
                {
                    "section": "run_result",
                    "code": "analysis_run_failed",
                    "severity": "severe",
                    "decision_coordinator_flag": True,
                    "message": "The provider-backed mock reviewer preserved failed-run evidence.",
                    "path": run_summary.get("path"),
                    "field": "run_success",
                    "value": False,
                }
            )
        severe = _has_severe_warning(warnings)
        confidence = "low" if severe else "medium" if warnings else "high"
        matrix_status = (
            "fail"
            if requires_matrix and severe
            else "warning"
            if requires_matrix and warnings
            else "pass"
            if requires_matrix
            else "not_applicable"
        )
        summary = (
            "Provider-backed mock Scientific Reviewer found severe summary evidence."
            if severe
            else "Provider-backed mock Scientific Reviewer found warning summary evidence."
            if warnings
            else "Provider-backed mock Scientific Reviewer completed structured checks."
        )
        return {
            "status": "success",
            "summary": summary,
            "warnings": warnings,
            "errors": [],
            "correlator_diagnostics": {"status": "not_populated_mvp"},
            "fit_diagnostics": fit_diagnostics,
            "matrix_element_diagnostics": (
                {"status": matrix_status}
                if requires_matrix
                else {
                    "status": "not_applicable",
                    "summary": "Matrix-element validation is outside the scope of this case.",
                    "warnings": [],
                    "evidence": [],
                    "findings": [],
                    "recommended_checks": [],
                }
            ),
            "findings": [{"code": "provider_mock_review_complete"}],
            "evidence": [
                {
                    "path": payload.get("analysis_outputs_dir"),
                    "field": "provider_mode",
                    "value": "mock",
                },
                {
                    "path": matrix_summary.get("path"),
                    "field": "diagnostic_flags",
                    "value": flags if isinstance(flags, list) else [],
                }
            ],
            "recommended_checks": [],
            "confidence": confidence,
        }

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
            finish_reason="stop",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
