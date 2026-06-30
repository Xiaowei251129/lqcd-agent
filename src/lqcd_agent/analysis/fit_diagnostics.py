"""Fit-strategy diagnostics for the deterministic Scientific Reviewer."""

from __future__ import annotations

import json
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


def diagnose_fit_outputs(analysis_outputs_dir: str | Path) -> dict[str, Any]:
    output_dir = Path(analysis_outputs_dir)
    fit_summary = _diagnose_fit_summary(output_dir / "fit_summary.json")
    if fit_summary["status"] != "not_found":
        return fit_summary

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
