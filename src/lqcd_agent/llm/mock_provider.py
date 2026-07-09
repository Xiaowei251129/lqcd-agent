"""Deterministic no-network LLM provider used by tests and defaults."""

from __future__ import annotations

import json
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse, ProviderReadiness


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _has_targeted_rerun_warning(warnings: list[Any]) -> bool:
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        code = str(warning.get("code", "")).lower()
        value = str(warning.get("value", "")).lower()
        if "targeted_rerun" in code or "targeted_rerun" in value:
            return True
    return False


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _selected_analysis_programs(case_config: dict[str, Any], repo_inventory: dict[str, Any]) -> list[dict[str, Any]]:
    requested_tags = set(_as_string_list(case_config.get("analysis_program_tags")))
    requested_outputs = set(_as_string_list(case_config.get("target_observables")))
    programs = repo_inventory.get("analysis_programs", [])
    if not isinstance(programs, list) or not case_config.get("raw_data_path"):
        return []

    selected: list[dict[str, Any]] = []
    for program in programs:
        if not isinstance(program, dict):
            continue
        tags = set(_as_string_list(program.get("tags")))
        produced_outputs = _as_string_list(program.get("produced_outputs"))
        output_match = bool(requested_outputs) and bool(requested_outputs & set(produced_outputs))
        tag_match = bool(requested_tags) and requested_tags.issubset(tags)
        if not (tag_match or output_match):
            continue
        required_inputs = set(_as_string_list(program.get("required_inputs")))
        if required_inputs != {"times", "correlator_values"}:
            continue
        output_name = produced_outputs[0] if produced_outputs else str(program.get("name", "analysis_program"))
        input_mapping = {
            "times": "raw_data_csv.t",
            "correlator_values": "raw_data_csv.value",
        }
        if _raw_csv_has_column(case_config, repo_inventory, "error"):
            input_mapping["correlator_errors"] = "raw_data_csv.error"
        selected.append(
            {
                "name": str(program.get("name", "")),
                "category": str(program.get("category", "")),
                "callable_path": str(program.get("callable_path", "")),
                "input_mapping": input_mapping,
                "output_path": f"analysis_outputs/{output_name}.json",
                "required_outputs": produced_outputs,
            }
        )
    return selected


def _raw_csv_has_column(case_config: dict[str, Any], repo_inventory: dict[str, Any], column_name: str) -> bool:
    raw_value = case_config.get("raw_data_path")
    repo_root = repo_inventory.get("repo_root")
    if not raw_value or not repo_root:
        return False
    raw_path = Path(str(raw_value))
    if raw_path.is_absolute():
        return False
    try:
        with (Path(str(repo_root)) / raw_path).resolve().open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return bool(reader.fieldnames and column_name in reader.fieldnames)
    except OSError:
        return False


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
        selected_programs = _selected_analysis_programs(case_config, repo_inventory)
        program_requested = bool(case_config.get("raw_data_path")) and bool(
            _as_string_list(case_config.get("analysis_program_tags"))
            or _as_string_list(case_config.get("target_observables"))
        )
        missing_requested_program = program_requested and not selected_programs
        code_needed = bool(implementation_gaps) or missing_requested_program
        required_outputs = ["method_plan.json", "run_result.json"]
        if selected_programs:
            required_outputs.extend(str(program["output_path"]) for program in selected_programs)
        required_outputs.extend(["scientific_review_report.json", "decision_log.json"])
        return {
            "schema_version": "0.1",
            "run_id": str(payload.get("run_id", "mock_run")),
            "case_id": str(payload.get("case_id", "mock_case")),
            "created_at": _utc_now(),
            "producer": "method_planner",
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
            "required_outputs": required_outputs,
            "implementation_gaps": implementation_gaps,
            "selected_analysis_programs": selected_programs,
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
            "schema_version": "0.1",
            "run_id": str(payload.get("run_id", "mock_run")),
            "case_id": str(payload.get("case_id", "mock_case")),
            "created_at": _utc_now(),
            "producer": "scientific_reviewer",
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

    def _decision_log(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id", "mock_run"))
        case_id = str(payload.get("case_id", "mock_case"))
        method_summary = payload.get("method_plan_summary")
        if not isinstance(method_summary, dict):
            method_summary = {}
        run_summary = payload.get("run_result_summary")
        if not isinstance(run_summary, dict):
            run_summary = {}
        review_summary = payload.get("scientific_review_summary")
        if not isinstance(review_summary, dict):
            review_summary = {}
        review_warnings = review_summary.get("warnings", [])
        if not isinstance(review_warnings, list):
            review_warnings = []

        if method_summary.get("status") and method_summary.get("status") != "success":
            risk_level = "critical"
            recommended_action = "pending_human_approval"
            human_approval_required = True
            reason = {
                "code": "provider_mock_method_not_success",
                "message": "Mock provider preserved non-success method-plan summary evidence.",
            }
        elif run_summary.get("run_success") is False:
            risk_level = "high"
            recommended_action = "code_fix" if run_summary.get("failure_type") == "code" else "targeted_rerun"
            human_approval_required = True
            reason = {
                "code": "provider_mock_run_failed",
                "message": "Mock provider preserved failed-run summary evidence.",
            }
        elif _has_severe_warning(review_warnings):
            risk_level = "high"
            recommended_action = "pending_human_approval"
            human_approval_required = True
            reason = {
                "code": "provider_mock_severe_warning",
                "message": "Mock provider preserved severe review warning evidence.",
            }
        elif _has_targeted_rerun_warning(review_warnings):
            risk_level = "medium"
            recommended_action = "targeted_rerun"
            human_approval_required = False
            reason = {
                "code": "provider_mock_targeted_rerun",
                "message": "Mock provider preserved targeted-rerun review evidence.",
            }
        elif review_warnings or review_summary.get("confidence") == "medium":
            risk_level = "medium"
            recommended_action = "human_review_recommended"
            human_approval_required = False
            reason = {
                "code": "provider_mock_warning_or_medium_confidence",
                "message": "Mock provider preserved warning or medium-confidence review evidence.",
            }
        else:
            risk_level = "low"
            recommended_action = "accept_mock_result"
            human_approval_required = False
            reason = {"code": "provider_mock_low_risk", "message": "Validated mock provider output."}

        actual_route = "human_approval_gate" if human_approval_required else "memory_report"
        if recommended_action == "code_fix":
            proposed_follow_up_route = "codex_handoff"
            rerun_requested = False
            rerun_target = None
            code_fix_requested = True
        elif recommended_action == "targeted_rerun":
            proposed_follow_up_route = "analysis_engineer"
            rerun_requested = True
            rerun_target = "analysis_engineer"
            code_fix_requested = False
        else:
            proposed_follow_up_route = actual_route
            rerun_requested = False
            rerun_target = None
            code_fix_requested = False

        return {
            "schema_version": "0.1",
            "run_id": run_id,
            "case_id": case_id,
            "created_at": _utc_now(),
            "producer": "decision_coordinator",
            "status": "success" if risk_level == "low" else "pending",
            "summary": f"Provider-backed mock Decision Coordinator classified the run as {risk_level} risk.",
            "warnings": review_warnings,
            "errors": [],
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "human_approval_required": human_approval_required,
            "reasons": [reason],
            "evidence": [
                {"artifact": "method_plan", "path": payload.get("method_plan_path")},
                {"artifact": "run_result", "path": payload.get("run_result_path")},
                {"artifact": "scientific_review_report", "path": payload.get("scientific_review_report_path")},
            ],
            "next_actions": [
                {
                    "action": recommended_action,
                    "primary": True,
                    "target": actual_route if human_approval_required else proposed_follow_up_route,
                    "status": "ready" if risk_level == "low" else "pending",
                }
            ],
            "routing_decision": {
                "actual_route": actual_route,
                "requested_route": actual_route,
                "proposed_follow_up_route": proposed_follow_up_route,
                "fields": {
                    "risk_level": risk_level,
                    "recommended_action": recommended_action,
                    "human_approval_required": human_approval_required,
                    "rerun_requested": rerun_requested,
                    "rerun_target": rerun_target,
                    "code_fix_requested": code_fix_requested,
                },
            },
        }

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = self._request_payload(request)
        if payload and payload.get("artifact_type") == "method_plan":
            content = json.dumps(self._method_plan(payload), sort_keys=True)
        elif payload and payload.get("artifact_type") == "scientific_review_report":
            content = json.dumps(self._scientific_review(payload), sort_keys=True)
        elif payload and payload.get("artifact_type") == "decision_log":
            content = json.dumps(self._decision_log(payload), sort_keys=True)
        else:
            content = json.dumps(
                {
                    "schema_version": "0.1",
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
