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
from lqcd_agent.llm.schemas import validate_proposal
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
    if (run_result or {}).get('generated_execution') is not None:
        requires_matrix_elements = False
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


def _not_applicable_diagnostics(summary) -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "summary": summary,
        "evidence": [],
        "findings": [],
        "warnings": [],
        "recommended_checks": [],
    }


def _unique_items(values):
    unique = []
    for value in values:
        if value not in unique:
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


def run_scientific_reviewer(
    *,
    run_id: str,
    case_id: str,
    run_output_dir: str | Path,
    run_result_path: str | Path | None,
    analysis_outputs_dir: str | Path | None = None,
    method_plan_path: str | Path | None = None,
    provider: LLMProvider | None = None,
    research_context: dict[str, Any] | None = None,
    generated_input: dict | None = None,
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

    if run_result is not None and run_result.get('run_success') is False:
        context_warnings.append(_warning(path=run_result_path, field='run_success', value=False,
            code='analysis_run_failed', severity='severe', message='Scientific review received a failed analysis Run.'))

    generated = run_result is not None and run_result.get('generated_execution') is not None
    correlator_diagnostics = (_not_applicable_diagnostics('Generated output uses its scientific numerical contract.')
        if generated else diagnose_correlator_outputs(resolved_analysis_outputs_dir))
    fit_diagnostics = (_not_applicable_diagnostics('Generated output uses its scientific numerical contract.')
        if generated else diagnose_fit_outputs(resolved_analysis_outputs_dir))
    matrix_element_diagnostics = (
        diagnose_matrix_elements(matrix_path)
        if review_scope["requires_matrix_element_validation"]
        else _not_applicable_diagnostics('Matrix-element validation is outside the scope of this case.')
    )
    sections = [correlator_diagnostics, fit_diagnostics, matrix_element_diagnostics]
    generated_diagnostics = None
    if generated:
        from lqcd_agent.analysis.generated_diagnostics import diagnose_generated_output
        generated_diagnostics = diagnose_generated_output(resolved_analysis_outputs_dir/'generated_result.json',
            run_result['generated_execution']['result_kind'], generated_input)
        sections.append(generated_diagnostics)

    warnings = context_warnings + _flatten_section_values(sections, "warnings")
    findings = _flatten_section_values(sections, "findings")
    evidence = context_evidence + _flatten_section_values(sections, "evidence")
    recommended_checks = _unique_items(
        [str(check) for check in _flatten_section_values(sections, "recommended_checks")]
    )
    if context_warnings:
        recommended_checks = _unique_items(
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
    request = response = error = None
    if generated_diagnostics is not None:
        report['generated_diagnostics'] = generated_diagnostics
    if provider is not None:
        try:
            request = build_scientific_reviewer_request(
                run_result=run_result, method_plan=method_plan, review_scope=review_scope,
                research_context=research_context,
                review_evidence={key: report[key] for key in (
                    'correlator_diagnostics', 'fit_diagnostics', 'matrix_element_diagnostics',
                    'generated_diagnostics', 'warnings', 'findings', 'evidence', 'recommended_checks', 'confidence') if key in report})
            persist_context(run_dir, request)
            evidence = read_context_evidence(run_dir, context_reference(request.context_sources), 'review_evidence')
            report.update(evidence)
            response = provider.generate(request)
            payload, error = parse_json_object(response.content, producer='scientific_reviewer',
                                               run_id=run_id, case_id=case_id)
            if error is None:
                errors = validate_proposal(payload, 'scientific_review_report')
                if errors:
                    error = validation_error_artifact(producer='scientific_reviewer',
                        run_id=run_id, case_id=case_id, errors=errors)
        except Exception as exc:
            error = provider_exception_artifact(producer='scientific_reviewer', run_id=run_id,
                case_id=case_id, code=getattr(exc, 'code', 'provider_call_failed'), message=str(exc))
        if error is not None:
            report.update(status='failed', summary=error['summary'], errors=error['errors'], confidence='low')
        else:
            report.update(status=payload['status'], summary=payload['summary'], errors=payload['errors'])
            additions = [warning for warning in payload['warnings']
                if not _is_ungrounded_provider_warning(warning) and
                (review_scope['requires_matrix_element_validation'] or not _is_out_of_scope_matrix_warning(warning))]
            report['warnings'] = _unique_items([*report['warnings'], *additions])
            for key in ('findings', 'evidence', 'recommended_checks'):
                report[key] = _unique_items([*report[key], *payload[key]])
            report['confidence'] = _lower_confidence(payload['confidence'], _confidence_from_warnings(report['warnings']))
    report_path = _write_report(run_dir / 'scientific_review_report.json', report)
    if provider is not None:
        write_llm_call_trace(output_dir=run_dir, agent='scientific_reviewer', provider=provider,
            request=request, response=response, parsed_payload_path=report_path, status=report['status'], error=error)
    return {'status': report['status'], 'report_path': report_path, 'scientific_review_report_path': report_path,
            'report': report, 'warnings': report['warnings'], 'errors': report['errors'], 'confidence': report['confidence']}
