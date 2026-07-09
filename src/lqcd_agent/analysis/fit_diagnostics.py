"""Fit-strategy diagnostics for the deterministic Scientific Reviewer."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


FIT_PATTERNS = [
    "fit*.json",
    "fit*.csv",
    "fit*.png",
    "fit*.pdf",
    "plateau*.json",
    "plateau*.csv",
    "plateau*.png",
    "plateau*.pdf",
]


def _discover_fit_artifacts(analysis_outputs_dir: Path) -> list[Path]:
    if not analysis_outputs_dir.exists():
        return []
    artifacts: list[Path] = []
    for pattern in FIT_PATTERNS:
        artifacts.extend(analysis_outputs_dir.glob(pattern))
    return sorted(path for path in artifacts if path.is_file())


def _warning(*, path: Path, field: str, value: Any, code: str, severity: str, message: str) -> dict[str, Any]:
    return {
        "section": "fit_diagnostics",
        "code": code,
        "severity": severity,
        "decision_coordinator_flag": severity == "severe",
        "message": message,
        "path": str(path),
        "field": field,
        "value": value,
    }


def _diagnose_fit_summary(path: Path) -> dict[str, Any]:
    evidence = [{"path": str(path), "field": "exists", "value": path.exists()}]
    warnings: list[dict[str, Any]] = []
    findings: list[str] = []
    recommended_checks: list[str] = []
    if not path.exists():
        return {
            "status": "not_found",
            "summary": "No fit_summary.json artifact was found.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": recommended_checks,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(
            _warning(
                path=path,
                field="$",
                value=f"JSONDecodeError: {exc.msg}",
                code="invalid_fit_summary_json",
                severity="severe",
                message="fit_summary.json is not valid JSON.",
            )
        )
        return {
            "status": "severe",
            "summary": "Fit summary could not be parsed.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": ["Regenerate fit_summary.json before decision coordination."],
        }

    if not isinstance(payload, dict):
        warnings.append(
            _warning(
                path=path,
                field="$",
                value=type(payload).__name__,
                code="invalid_fit_summary_payload",
                severity="severe",
                message="fit_summary.json must contain a JSON object.",
            )
        )
        return {
            "status": "severe",
            "summary": "Fit summary has an invalid shape.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": ["Regenerate fit_summary.json before decision coordination."],
        }

    evidence.extend(
        [
            {"path": str(path), "field": "status", "value": payload.get("status")},
            {"path": str(path), "field": "model", "value": payload.get("model")},
            {"path": str(path), "field": "reduced_chi2", "value": payload.get("reduced_chi2")},
            {"path": str(path), "field": "parameter_estimates", "value": payload.get("parameter_estimates")},
        ]
    )
    if payload.get("status") == "failed":
        warnings.append(
            _warning(
                path=path,
                field="status",
                value=payload.get("status"),
                code="fit_summary_failed",
                severity="severe",
                message="Synthetic benchmark fit summary reports failed status.",
            )
        )

    flags = payload.get("diagnostic_flags", [])
    if isinstance(flags, list):
        for index, flag in enumerate(flags):
            if isinstance(flag, dict):
                code = str(flag.get("code", "fit_diagnostic_flag"))
                severity = str(flag.get("severity", "warning"))
                message = str(flag.get("message", "Synthetic benchmark fit diagnostic flag."))
                value = code
            else:
                code = str(flag)
                severity = "severe" if "severe" in code or "invalid" in code else "warning"
                message = "Synthetic benchmark fit diagnostic flag."
                value = flag
            warnings.append(
                _warning(
                    path=path,
                    field=f"diagnostic_flags[{index}]",
                    value=value,
                    code=code,
                    severity=severity,
                    message=message,
                )
            )

    parameters = payload.get("parameter_estimates", {})
    if isinstance(parameters, dict) and parameters:
        findings.append(
            "Fit summary estimated "
            + ", ".join(f"{key}={value}" for key, value in sorted(parameters.items()) if isinstance(value, (int, float)))
            + "."
        )
    if warnings:
        recommended_checks.append("Inspect fit_summary.json diagnostic flags before accepting this mock result.")
    status = "severe" if any(warning["severity"] == "severe" for warning in warnings) else "warning" if warnings else "pass"
    return {
        "status": status,
        "summary": "Fit summary diagnostics found warnings." if warnings else "Fit summary diagnostics passed.",
        "evidence": evidence,
        "findings": findings,
        "warnings": warnings,
        "recommended_checks": recommended_checks,
    }


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _diagnose_effective_mass_estimates(path: Path) -> dict[str, Any]:
    evidence = [{"path": str(path), "field": "exists", "value": path.exists()}]
    warnings: list[dict[str, Any]] = []
    findings: list[str] = []
    recommended_checks: list[str] = []
    if not path.exists():
        return {
            "status": "not_found",
            "summary": "No effective_mass_estimates.json artifact was found.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": recommended_checks,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(
            _warning(
                path=path,
                field="$",
                value=f"JSONDecodeError: {exc.msg}",
                code="invalid_effective_mass_json",
                severity="severe",
                message="effective_mass_estimates.json is not valid JSON.",
            )
        )
        return {
            "status": "severe",
            "summary": "Effective-mass estimates could not be parsed.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": ["Regenerate effective_mass_estimates.json before decision coordination."],
        }

    if not isinstance(payload, dict):
        warnings.append(
            _warning(
                path=path,
                field="$",
                value=type(payload).__name__,
                code="invalid_effective_mass_payload",
                severity="severe",
                message="effective_mass_estimates.json must contain a JSON object.",
            )
        )
        return {
            "status": "severe",
            "summary": "Effective-mass artifact has an invalid shape.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": ["Regenerate effective_mass_estimates.json before decision coordination."],
        }

    estimates = payload.get("effective_mass_estimates")
    diagnostic_flags = payload.get("diagnostic_flags", [])
    evidence.extend(
        [
            {"path": str(path), "field": "status", "value": payload.get("status")},
            {"path": str(path), "field": "program", "value": payload.get("program")},
            {
                "path": str(path),
                "field": "diagnostic_flags",
                "value": diagnostic_flags if isinstance(diagnostic_flags, list) else [],
            },
            {
                "path": str(path),
                "field": "effective_mass_estimates_count",
                "value": len(estimates) if isinstance(estimates, list) else None,
            },
        ]
    )
    if not isinstance(estimates, list):
        warnings.append(
            _warning(
                path=path,
                field="effective_mass_estimates",
                value=type(estimates).__name__,
                code="invalid_effective_mass_estimates",
                severity="severe",
                message="effective_mass_estimates must be a list.",
            )
        )
        estimates = []

    for index, estimate in enumerate(estimates):
        field = f"effective_mass_estimates[{index}]"
        if not isinstance(estimate, dict):
            warnings.append(
                _warning(
                    path=path,
                    field=field,
                    value=type(estimate).__name__,
                    code="invalid_effective_mass_row",
                    severity="severe",
                    message="Each effective-mass estimate must be an object.",
                )
            )
            continue
        value = estimate.get("effective_mass")
        if not _is_finite_number(value):
            warnings.append(
                _warning(
                    path=path,
                    field=f"{field}.effective_mass",
                    value=value,
                    code="invalid_effective_mass_value",
                    severity="severe",
                    message="Each effective_mass value must be finite numeric evidence.",
                )
            )

    if isinstance(diagnostic_flags, list):
        for index, flag in enumerate(diagnostic_flags):
            severity = "severe" if "severe" in str(flag).lower() or "invalid" in str(flag).lower() else "warning"
            warnings.append(
                _warning(
                    path=path,
                    field=f"diagnostic_flags[{index}]",
                    value=flag,
                    code="upstream_diagnostic_flag",
                    severity=severity,
                    message="Effective-mass analysis artifact carries an upstream diagnostic flag.",
                )
            )

    if estimates:
        findings.append(f"Found {len(estimates)} effective-mass estimate(s).")
    status = "severe" if any(warning["severity"] == "severe" for warning in warnings) else "warning" if warnings else "pass"
    return {
        "status": status,
        "summary": "Effective-mass diagnostics found warnings." if warnings else "Effective-mass diagnostics passed.",
        "evidence": evidence,
        "findings": findings,
        "warnings": warnings,
        "recommended_checks": recommended_checks,
    }


def diagnose_fit_outputs(analysis_outputs_dir: str | Path) -> dict[str, Any]:
    output_dir = Path(analysis_outputs_dir)
    fit_summary = _diagnose_fit_summary(output_dir / "fit_summary.json")
    if fit_summary["status"] != "not_found":
        return fit_summary

    effective_mass = _diagnose_effective_mass_estimates(output_dir / "effective_mass_estimates.json")
    if effective_mass["status"] != "not_found":
        return effective_mass

    artifacts = _discover_fit_artifacts(output_dir)
    evidence = [
        {"path": str(output_dir), "field": "exists", "value": output_dir.exists()},
        {"path": str(output_dir), "field": "fit_artifact_count", "value": len(artifacts)},
    ]

    if not artifacts:
        return {
            "status": "not_populated_mvp",
            "summary": "No fit summary table or fit plot is populated for the mock MVP.",
            "evidence": evidence,
            "findings": ["Fit diagnostics section is present but not populated in this mock run."],
            "warnings": [],
            "recommended_checks": ["Add fit-summary artifacts in a future fit-strategy ticket."],
        }

    evidence.extend(
        {"path": str(path), "field": "artifact_name", "value": path.name}
        for path in artifacts
    )
    return {
        "status": "present",
        "summary": "Optional fit artifacts were found for reviewer context.",
        "evidence": evidence,
        "findings": [f"Found {len(artifacts)} optional fit artifact(s)."],
        "warnings": [],
        "recommended_checks": [],
    }
