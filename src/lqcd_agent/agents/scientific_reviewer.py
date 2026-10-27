"""Deterministic Scientific Reviewer Agent for Phase 5."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.analysis.correlator_diagnostics import diagnose_correlator_outputs
from lqcd_agent.analysis.fit_diagnostics import diagnose_fit_outputs
from lqcd_agent.analysis.matrix_element_diagnostics import diagnose_matrix_elements
from lqcd_agent.llm.base import LLMProvider
from lqcd_agent.llm.prompts import build_scientific_reviewer_request
from lqcd_agent.llm.provider_factory import create_provider_from_config_path
from lqcd_agent.llm.schemas import validate_proposal, artifact_payload
from lqcd_agent.llm.structured_output import (
    parse_json_object,
    provider_exception_artifact,
    validation_error_artifact,
)
from lqcd_agent.llm.trace import write_llm_call_trace
from lqcd_agent.llm.context import persist_context, read_context_evidence, context_reference


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_artifact(*, run_id: str, case_id: str, status: str, summary: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": utc_now(),
        "producer": "scientific_reviewer",
        "status": status,
        "summary": summary,
        "warnings": [],
        "errors": [],
    }


def _read_json(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    json_path = Path(path)
    if not json_path.exists():
        return None
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _warning(
    *,
    path: str | Path,
    field: str,
    value: Any,
    code: str,
    severity: str,
    message: str,
) -> dict[str, Any]:
    return {
        "section": "review_context",
        "code": code,
        "severity": severity,
        "decision_coordinator_flag": severity == "severe",
        "message": message,
        "path": str(path),
        "field": field,
        "value": value,
    }


def _resolve_analysis_outputs_dir(
    *, run_output_dir: Path, analysis_outputs_dir: str | Path | None, run_result: dict[str, Any] | None
) -> Path:
    if analysis_outputs_dir:
        return Path(analysis_outputs_dir)
    if run_result and run_result.get("analysis_outputs_dir"):
        return Path(str(run_result["analysis_outputs_dir"]))
    return run_output_dir / "analysis_outputs"


def _resolve_matrix_path(
    *,
    run_output_dir: Path,
    analysis_outputs_dir: Path,
    run_result: dict[str, Any] | None,
) -> Path:
    if run_result:
        for field in ["produced_outputs", "expected_outputs"]:
            outputs = run_result.get(field, [])
            if not isinstance(outputs, list):
                continue
            for output in outputs:
                output_path = Path(str(output))
                if output_path.name != "synthetic_matrix_elements.json":
                    continue
                if output_path.is_absolute():
                    return output_path
                return run_output_dir / output_path
    return analysis_outputs_dir / "synthetic_matrix_elements.json"


def _artifact_strings(payload: dict[str, Any] | None, fields: list[str]) -> list[str]:
    if not payload:
        return []
    values: list[str] = []
    for field in fields:
        field_value = payload.get(field, [])
        if isinstance(field_value, list):
            values.extend(str(value) for value in field_value)
        elif field_value is not None:
            values.append(str(field_value))
    return values


def _review_scope(run_result: dict[str, Any] | None, method_plan: dict[str, Any] | None) -> dict[str, Any]:
    run_artifacts = _artifact_strings(run_result, ["produced_outputs", "expected_outputs"])
    plan_artifacts = _artifact_strings(method_plan, ["target_observables", "required_outputs"])
    combined = [value.lower() for value in run_artifacts + plan_artifacts]
    requires_matrix_elements = any(
        "synthetic_matrix_elements.json" in value or "matrix_element" in value for value in combined
    )
    has_effective_mass = any("effective_mass" in value for value in combined)
    return {
        "requires_matrix_element_validation": requires_matrix_elements,
        "has_effective_mass_outputs": has_effective_mass,
        "matrix_element_policy": (
            "run_matrix_element_diagnostics"
            if requires_matrix_elements
            else "mark_matrix_element_diagnostics_not_applicable"
        ),
    }


def _not_applicable_matrix_element_diagnostics() -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "summary": "Matrix-element validation is outside the scope of this case.",
        "evidence": [],
        "findings": [],
        "warnings": [],
        "recommended_checks": [],
    }


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _flatten_section_values(sections: list[dict[str, Any]], field: str) -> list[Any]:
    values: list[Any] = []
    for section in sections:
        section_values = section.get(field, [])
        if isinstance(section_values, list):
            values.extend(section_values)
    return values


def _confidence_from_warnings(warnings: list[dict[str, Any]]) -> str:
    if any(warning.get("severity") == "severe" for warning in warnings):
        return "low"
    if warnings:
        return "medium"
    return "high"


def _summary_from_warnings(warnings: list[dict[str, Any]]) -> str:
    if any(warning.get("severity") == "severe" for warning in warnings):
        return "Scientific Reviewer found severe evidence-backed warnings."
    if warnings:
        return "Scientific Reviewer found evidence-backed warnings."
    return "Scientific Reviewer completed deterministic diagnostics without warnings."


def _lower_confidence(existing: Any, evidence_confidence: str) -> str:
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    existing_text = str(existing) if existing in confidence_order else "high"
    return evidence_confidence if confidence_order[evidence_confidence] > confidence_order[existing_text] else existing_text


def _write_report(path: Path, report: dict[str, Any]) -> str:
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _artifact_summary(payload: dict[str, Any] | None, *, path: str | Path | None) -> dict[str, Any]:
    if payload is None:
        return {"exists": bool(path and Path(path).exists()), "path": str(path) if path else None}
    return {
        "exists": True,
        "path": str(path) if path else None,
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
    }


def _matrix_element_summary(payload: dict[str, Any] | None, *, path: str | Path | None) -> dict[str, Any]:
    summary = _artifact_summary(payload, path=path)
    if payload is None:
        return summary
    rows = payload.get("matrix_elements", [])
    summary.update(
        {
            "source_kind": payload.get("source_kind"),
            "normalization": payload.get("normalization"),
            "diagnostic_flags": payload.get("diagnostic_flags", []),
            "matrix_element_count": len(rows) if isinstance(rows, list) else None,
            "golden_example": payload.get("golden_example"),
        }
    )
    return summary


def _provider_failure_report(
    *,
    run_id: str,
    case_id: str,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    return {
        **artifact,
        "run_id": run_id,
        "case_id": case_id,
        "correlator_diagnostics": {"status": "provider_validation_failed"},
        "fit_diagnostics": {"status": "provider_validation_failed"},
        "matrix_element_diagnostics": {"status": "provider_validation_failed"},
        "findings": [],
        "evidence": [],
        "recommended_checks": ["Inspect provider validation errors before decision coordination."],
        "confidence": "low",
    }


def _flag_severity(flag: Any) -> str:
    text = str(flag).lower()
    if "severe" in text or "critical" in text or "fail" in text:
        return "severe"
    return "warning"


def _is_ungrounded_provider_warning(warning: dict[str, Any]) -> bool:
    if warning.get("severity") == "severe" or warning.get("decision_coordinator_flag") is True:
        return False
    evidence_fields = ["path", "field", "value"]
    return all(warning.get(field) is None or warning.get(field) == "" for field in evidence_fields)


def _is_out_of_scope_matrix_warning(warning: dict[str, Any]) -> bool:
    text = " ".join(
        str(warning.get(field, ""))
        for field in ["section", "code", "message", "path", "field", "value"]
        if warning.get(field) is not None
    ).lower()
    return "matrix" in text and ("missing" in text or "absent" in text or "synthetic_matrix_elements" in text)


def _normalize_provider_review_payload(
    payload: dict[str, Any],
    *,
    fit_diagnostics: dict[str, Any],
    matrix_summary: dict[str, Any],
    review_scope: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(payload)
    warnings = normalized.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
    preserved_warnings = [
        warning
        for warning in warnings
        if not (
            isinstance(warning, dict)
            and _is_ungrounded_provider_warning(warning)
        )
    ]
    if fit_diagnostics.get("status") not in {None, "not_found", "not_populated_mvp"}:
        normalized["fit_diagnostics"] = fit_diagnostics
        fit_warnings = fit_diagnostics.get("warnings", [])
        if isinstance(fit_warnings, list):
            preserved_warnings.extend(warning for warning in fit_warnings if isinstance(warning, dict))

    if not review_scope.get("requires_matrix_element_validation"):
        preserved_warnings = [
            warning
            for warning in preserved_warnings
            if not (isinstance(warning, dict) and _is_out_of_scope_matrix_warning(warning))
        ]
        normalized["warnings"] = preserved_warnings
        normalized["matrix_element_diagnostics"] = _not_applicable_matrix_element_diagnostics()
        structured_warnings = [warning for warning in preserved_warnings if isinstance(warning, dict)]
        normalized["confidence"] = _lower_confidence(
            normalized.get("confidence"),
            _confidence_from_warnings(structured_warnings),
        )
        return normalized

    structured_warnings = [warning for warning in preserved_warnings if isinstance(warning, dict)]
    existing_values = {str(warning.get("value")) for warning in structured_warnings}
    flags = matrix_summary.get("diagnostic_flags", [])
    if isinstance(flags, list):
        for index, flag in enumerate(flags):
            if str(flag) in existing_values:
                continue
            severity = _flag_severity(flag)
            preserved_warnings.append(
                {
                    "section": "matrix_element",
                    "code": "upstream_diagnostic_flag",
                    "severity": severity,
                    "decision_coordinator_flag": severity == "severe",
                    "message": "The provider-backed reviewer preserved an upstream diagnostic flag.",
                    "path": matrix_summary.get("path"),
                    "field": f"diagnostic_flags[{index}]",
                    "value": flag,
                }
            )
    normalized["warnings"] = preserved_warnings
    structured_warnings = [warning for warning in preserved_warnings if isinstance(warning, dict)]
    normalized["confidence"] = _lower_confidence(
        normalized.get("confidence"),
        _confidence_from_warnings(structured_warnings),
    )
    return normalized


def _run_provider_scientific_reviewer(
    *,
    run_id: str,
    case_id: str,
    run_output_dir: str | Path,
    run_result_path: str | Path | None,
    analysis_outputs_dir: str | Path | None,
    method_plan_path: str | Path | None,
    provider: LLMProvider,
) -> dict[str, Any]:
    run_dir = Path(run_output_dir)
    run_result = _read_json(run_result_path)
    method_plan = _read_json(method_plan_path)
    resolved_analysis_outputs_dir = _resolve_analysis_outputs_dir(
        run_output_dir=run_dir,
        analysis_outputs_dir=analysis_outputs_dir,
        run_result=run_result,
    )
    matrix_path = _resolve_matrix_path(
        run_output_dir=run_dir,
        analysis_outputs_dir=resolved_analysis_outputs_dir,
        run_result=run_result,
    )
    review_scope = _review_scope(run_result, method_plan)
    fit_diagnostics = diagnose_fit_outputs(resolved_analysis_outputs_dir)
    matrix_payload = _read_json(matrix_path)
    matrix_summary = (
        _matrix_element_summary(matrix_payload, path=matrix_path)
        if review_scope["requires_matrix_element_validation"]
        else {"exists": False, "path": None, "applicable": False}
    )
    request = None
    try:
        request = build_scientific_reviewer_request(
            run_result=run_result,
            fit_diagnostics_summary=fit_diagnostics,
            matrix_element_summary=matrix_summary,
            method_plan=method_plan,
            review_scope=review_scope,
        )
        persist_context(run_dir, request)
        fit_diagnostics = read_context_evidence(run_dir, context_reference(request.context_sources), 'fit_diagnostics_summary')
        response = provider.generate(request)
    except Exception as exc:
        report = _provider_failure_report(
            run_id=run_id,
            case_id=case_id,
            artifact=provider_exception_artifact(
                producer="scientific_reviewer",
                run_id=run_id,
                case_id=case_id,
                code=getattr(exc, "code", "provider_call_failed"),
                message=str(exc),
            ),
        )
        report_path = _write_report(run_dir / "scientific_review_report.json", report)
        result = {
            "status": "failed",
            "report_path": report_path,
            "scientific_review_report_path": report_path,
            "report": report,
            "warnings": [],
            "errors": report["errors"],
            "confidence": "low",
        }
        write_llm_call_trace(
            output_dir=run_dir,
            agent="scientific_reviewer",
            provider=provider,
            request=request,
            parsed_payload_path=report_path,
            status="failed",
            error=report,
        )
        return result

    payload, parse_error = parse_json_object(
        response.content,
        producer="scientific_reviewer",
        run_id=run_id,
        case_id=case_id,
    )
    if parse_error is not None:
        report = _provider_failure_report(run_id=run_id, case_id=case_id, artifact=parse_error)
        report_path = _write_report(run_dir / "scientific_review_report.json", report)
        result = {
            "status": "failed",
            "report_path": report_path,
            "scientific_review_report_path": report_path,
            "report": report,
            "warnings": [],
            "errors": report["errors"],
            "confidence": "low",
        }
        write_llm_call_trace(
            output_dir=run_dir,
            agent="scientific_reviewer",
            provider=provider,
            request=request,
            response=response,
            parsed_payload_path=report_path,
            status="failed",
            error=parse_error,
        )
        return result

    assert payload is not None
    validation_errors = validate_proposal(payload, 'scientific_review_report')
    if validation_errors:
        report = _provider_failure_report(
            run_id=run_id,
            case_id=case_id,
            artifact=validation_error_artifact(
                producer="scientific_reviewer",
                run_id=run_id,
                case_id=case_id,
                errors=validation_errors,
            ),
        )
        report_path = _write_report(run_dir / "scientific_review_report.json", report)
        result = {
            "status": "failed",
            "report_path": report_path,
            "scientific_review_report_path": report_path,
            "report": report,
            "warnings": [],
            "errors": report["errors"],
            "confidence": "low",
        }
        write_llm_call_trace(
            output_dir=run_dir,
            agent="scientific_reviewer",
            provider=provider,
            request=request,
            response=response,
            parsed_payload_path=report_path,
            status="failed",
            error=report,
        )
        return result

    payload = artifact_payload(payload, run_id=run_id, case_id=case_id, producer='scientific_reviewer')
    payload = _normalize_provider_review_payload(payload, fit_diagnostics=fit_diagnostics,
        matrix_summary=matrix_summary, review_scope=review_scope)
    report_path = _write_report(run_dir / "scientific_review_report.json", payload)
    write_llm_call_trace(
        output_dir=run_dir,
        agent="scientific_reviewer",
        provider=provider,
        request=request,
        response=response,
        parsed_payload_path=report_path,
        status=payload["status"],
    )
    return {
        "status": payload["status"],
        "report_path": report_path,
        "scientific_review_report_path": report_path,
        "report": payload,
        "warnings": payload["warnings"],
        "errors": payload["errors"],
        "confidence": payload["confidence"],
    }


def run_scientific_reviewer(
    *,
    run_id: str,
    case_id: str,
    run_output_dir: str | Path,
    run_result_path: str | Path | None,
    analysis_outputs_dir: str | Path | None = None,
    method_plan_path: str | Path | None = None,
    provider: LLMProvider | None = None,
    provider_config_path: str | Path | None = None,
) -> dict[str, Any]:
    if provider is None and provider_config_path is not None:
        provider = create_provider_from_config_path(provider_config_path)
    if provider is not None:
        return _run_provider_scientific_reviewer(
            run_id=run_id,
            case_id=case_id,
            run_output_dir=run_output_dir,
            run_result_path=run_result_path,
            analysis_outputs_dir=analysis_outputs_dir,
            method_plan_path=method_plan_path,
            provider=provider,
        )

    run_dir = Path(run_output_dir)
    run_result = _read_json(run_result_path)
    method_plan = _read_json(method_plan_path)
    resolved_analysis_outputs_dir = _resolve_analysis_outputs_dir(
        run_output_dir=run_dir,
        analysis_outputs_dir=analysis_outputs_dir,
        run_result=run_result,
    )
    matrix_path = _resolve_matrix_path(
        run_output_dir=run_dir,
        analysis_outputs_dir=resolved_analysis_outputs_dir,
        run_result=run_result,
    )
    review_scope = _review_scope(run_result, method_plan)

    context_warnings: list[dict[str, Any]] = []
    context_evidence = [
        {"path": str(run_result_path), "field": "exists", "value": bool(run_result_path and Path(run_result_path).exists())},
        {
            "path": str(method_plan_path),
            "field": "exists",
            "value": bool(method_plan_path and Path(method_plan_path).exists()),
        },
        {"path": str(resolved_analysis_outputs_dir), "field": "exists", "value": resolved_analysis_outputs_dir.exists()},
    ]
    if run_result_path and not Path(run_result_path).exists():
        context_warnings.append(
            _warning(
                path=run_result_path,
                field="exists",
                value=False,
                code="missing_run_result",
                severity="severe",
                message="Scientific review requires run_result.json evidence.",
            )
        )
    elif run_result_path and run_result is None:
        context_warnings.append(
            _warning(
                path=run_result_path,
                field="$",
                value="unreadable_json",
                code="invalid_run_result_json",
                severity="severe",
                message="Scientific review could not parse run_result.json evidence.",
            )
        )

    if method_plan_path and Path(method_plan_path).exists() and method_plan is None:
        context_warnings.append(
            _warning(
                path=method_plan_path,
                field="$",
                value="unreadable_json",
                code="invalid_method_plan_json",
                severity="warning",
                message="Scientific review could not parse optional method_plan.json context.",
            )
        )

    correlator_diagnostics = diagnose_correlator_outputs(resolved_analysis_outputs_dir)
    fit_diagnostics = diagnose_fit_outputs(resolved_analysis_outputs_dir)
    matrix_element_diagnostics = (
        diagnose_matrix_elements(matrix_path)
        if review_scope["requires_matrix_element_validation"]
        else _not_applicable_matrix_element_diagnostics()
    )
    sections = [correlator_diagnostics, fit_diagnostics, matrix_element_diagnostics]

    warnings = context_warnings + _flatten_section_values(sections, "warnings")
    findings = _flatten_section_values(sections, "findings")
    evidence = context_evidence + _flatten_section_values(sections, "evidence")
    recommended_checks = _unique_strings(
        [str(check) for check in _flatten_section_values(sections, "recommended_checks")]
    )
    if context_warnings:
        recommended_checks = _unique_strings(
            ["Inspect reviewer input artifacts before downstream decision coordination."] + recommended_checks
        )
    confidence = _confidence_from_warnings(warnings)
    summary = _summary_from_warnings(warnings)

    report = {
        **_base_artifact(run_id=run_id, case_id=case_id, status="success", summary=summary),
        "warnings": warnings,
        "errors": [],
        "correlator_diagnostics": correlator_diagnostics,
        "fit_diagnostics": fit_diagnostics,
        "matrix_element_diagnostics": matrix_element_diagnostics,
        "findings": findings,
        "evidence": evidence,
        "recommended_checks": recommended_checks,
        "confidence": confidence,
    }
    report_path = _write_report(run_dir / "scientific_review_report.json", report)
    return {
        "status": "success",
        "report_path": report_path,
        "scientific_review_report_path": report_path,
        "report": report,
        "warnings": warnings,
        "errors": [],
        "confidence": confidence,
    }
