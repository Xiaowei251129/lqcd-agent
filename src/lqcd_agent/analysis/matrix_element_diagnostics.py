"""Matrix-element diagnostics for the deterministic Scientific Reviewer."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version",
    "run_id",
    "case_id",
    "source_kind",
    "z_values",
    "pz_values",
    "matrix_elements",
    "normalization",
    "uncertainties",
    "diagnostic_flags",
]
REQUIRED_ROW_FIELDS = ["z", "Pz", "component", "value", "error"]
EXPECTED_COMPONENTS = {"real", "imag"}


def _evidence_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def _warning(
    *,
    path: Path,
    field: str,
    value: Any,
    code: str,
    severity: str,
    message: str,
) -> dict[str, Any]:
    return {
        "section": "matrix_element",
        "code": code,
        "severity": severity,
        "decision_coordinator_flag": severity == "severe",
        "message": message,
        "path": str(path),
        "field": field,
        "value": _evidence_value(value),
    }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _as_number(value: Any) -> float | None:
    if not _is_number(value):
        return None
    return float(value)


def _flag_severity(flag: Any) -> str:
    text = str(flag).lower()
    if "severe" in text or "critical" in text or "fail" in text:
        return "severe"
    return "warning"


def _duplicates(values: list[Any]) -> list[Any]:
    seen: set[Any] = set()
    repeated: list[Any] = []
    for value in values:
        try:
            if value in seen and value not in repeated:
                repeated.append(value)
            seen.add(value)
        except TypeError:
            continue
    return repeated


def _check_required_fields(payload: dict[str, Any], path: Path, warnings: list[dict[str, Any]]) -> None:
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            warnings.append(
                _warning(
                    path=path,
                    field=field,
                    value=None,
                    code="missing_required_field",
                    severity="severe",
                    message=f"{field} is missing from the synthetic matrix-element artifact.",
                )
            )


def _check_declared_lists(payload: dict[str, Any], path: Path, warnings: list[dict[str, Any]]) -> None:
    for field in ["z_values", "pz_values", "matrix_elements", "diagnostic_flags"]:
        value = payload.get(field)
        if field in payload and not isinstance(value, list):
            warnings.append(
                _warning(
                    path=path,
                    field=field,
                    value=type(value).__name__,
                    code="invalid_declared_list",
                    severity="severe",
                    message=f"{field} must be a list for structured review.",
                )
            )

    for field in ["z_values", "pz_values"]:
        value = payload.get(field)
        if isinstance(value, list):
            repeated = _duplicates(value)
            if repeated:
                warnings.append(
                    _warning(
                        path=path,
                        field=field,
                        value=repeated,
                        code="duplicate_coordinate_values",
                        severity="warning",
                        message=f"{field} contains duplicate coordinate values.",
                    )
                )


def _check_diagnostic_flags(payload: dict[str, Any], path: Path, warnings: list[dict[str, Any]]) -> None:
    flags = payload.get("diagnostic_flags", [])
    if not isinstance(flags, list):
        return
    for index, flag in enumerate(flags):
        severity = _flag_severity(flag)
        warnings.append(
            _warning(
                path=path,
                field=f"diagnostic_flags[{index}]",
                value=flag,
                code="upstream_diagnostic_flag",
                severity=severity,
                message="The analysis artifact carries an upstream diagnostic flag.",
            )
        )


def _check_row_fields(
    *,
    rows: list[Any],
    z_values: list[Any],
    pz_values: list[Any],
    path: Path,
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    valid_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        row_field = f"matrix_elements[{index}]"
        if not isinstance(row, dict):
            warnings.append(
                _warning(
                    path=path,
                    field=row_field,
                    value=type(row).__name__,
                    code="invalid_matrix_row",
                    severity="severe",
                    message="Each matrix-element row must be an object.",
                )
            )
            continue

        for field in REQUIRED_ROW_FIELDS:
            if field not in row:
                warnings.append(
                    _warning(
                        path=path,
                        field=f"{row_field}.{field}",
                        value=None,
                        code="missing_row_field",
                        severity="severe",
                        message=f"{row_field}.{field} is missing.",
                    )
                )

        if row.get("z") not in z_values:
            warnings.append(
                _warning(
                    path=path,
                    field=f"{row_field}.z",
                    value=row.get("z"),
                    code="undeclared_z_value",
                    severity="warning",
                    message="Matrix-element row uses a z value not listed in z_values.",
                )
            )
        if row.get("Pz") not in pz_values:
            warnings.append(
                _warning(
                    path=path,
                    field=f"{row_field}.Pz",
                    value=row.get("Pz"),
                    code="undeclared_pz_value",
                    severity="warning",
                    message="Matrix-element row uses a Pz value not listed in pz_values.",
                )
            )

        component = row.get("component")
        if component is not None and component not in EXPECTED_COMPONENTS:
            warnings.append(
                _warning(
                    path=path,
                    field=f"{row_field}.component",
                    value=component,
                    code="unexpected_component",
                    severity="warning",
                    message="Matrix-element component is not one of the expected mock components.",
                )
            )

        value = row.get("value")
        error = row.get("error")
        if "value" in row and not _is_number(value):
            warnings.append(
                _warning(
                    path=path,
                    field=f"{row_field}.value",
                    value=value,
                    code="invalid_matrix_value",
                    severity="severe",
                    message="Matrix-element value must be finite numeric evidence.",
                )
            )
        if "error" in row:
            if not _is_number(error):
                warnings.append(
                    _warning(
                        path=path,
                        field=f"{row_field}.error",
                        value=error,
                        code="invalid_matrix_error",
                        severity="severe",
                        message="Matrix-element error must be finite numeric evidence.",
                    )
                )
            elif float(error) <= 0:
                warnings.append(
                    _warning(
                        path=path,
                        field=f"{row_field}.error",
                        value=error,
                        code="non_positive_matrix_error",
                        severity="severe",
                        message="Matrix-element error must be positive.",
                    )
                )

        flags = row.get("flags", [])
        if flags:
            flag_values = flags if isinstance(flags, list) else [flags]
            for flag_index, flag in enumerate(flag_values):
                severity = _flag_severity(flag)
                warnings.append(
                    _warning(
                        path=path,
                        field=f"{row_field}.flags[{flag_index}]",
                        value=flag,
                        code="row_diagnostic_flag",
                        severity=severity,
                        message="Matrix-element row carries a diagnostic flag.",
                    )
                )

        if all(field in row for field in REQUIRED_ROW_FIELDS):
            valid_rows.append(row)
    return valid_rows


def _check_grid_coverage(
    *,
    rows: list[dict[str, Any]],
    z_values: list[Any],
    pz_values: list[Any],
    path: Path,
    warnings: list[dict[str, Any]],
) -> None:
    present = {(row.get("z"), row.get("Pz")) for row in rows}
    for z in z_values:
        for pz in pz_values:
            if (z, pz) not in present:
                warnings.append(
                    _warning(
                        path=path,
                        field="matrix_elements",
                        value={"z": z, "Pz": pz},
                        code="missing_coordinate_pair",
                        severity="warning",
                        message="No matrix-element row covers this declared z/Pz coordinate pair.",
                    )
                )


def _check_mock_unit_normalization(
    *,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
    path: Path,
    warnings: list[dict[str, Any]],
) -> None:
    if payload.get("normalization") != "mock_unit":
        return

    z0_real_rows = [row for row in rows if row.get("z") == 0 and row.get("component") == "real"]
    if not z0_real_rows:
        warnings.append(
            _warning(
                path=path,
                field="matrix_elements",
                value={"z": 0, "component": "real"},
                code="missing_mock_unit_normalization_row",
                severity="severe",
                message="mock_unit normalization requires a real z=0 matrix-element row.",
            )
        )
        return

    for row in z0_real_rows:
        value = _as_number(row.get("value"))
        error = _as_number(row.get("error"))
        if value is None or error is None or error <= 0:
            continue
        tolerance = max(5.0 * error, 0.05)
        if abs(value - 1.0) > tolerance:
            warnings.append(
                _warning(
                    path=path,
                    field="matrix_elements.z0.real.value",
                    value=value,
                    code="mock_unit_normalization_mismatch",
                    severity="severe",
                    message="mock_unit normalization expects the real z=0 value to be consistent with 1.",
                )
            )


def _check_simple_z_consistency(
    *,
    rows: list[dict[str, Any]],
    path: Path,
    warnings: list[dict[str, Any]],
) -> None:
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("component") != "real":
            continue
        if _as_number(row.get("z")) is None or _as_number(row.get("value")) is None:
            continue
        grouped.setdefault(row.get("Pz"), []).append(row)

    for pz, group in grouped.items():
        group.sort(key=lambda row: abs(float(row["z"])))
        if not group or group[0].get("z") != 0:
            continue
        base = group[0]
        base_value = abs(float(base["value"]))
        base_error = _as_number(base.get("error")) or 0.0
        for row in group[1:]:
            value = abs(float(row["value"]))
            error = _as_number(row.get("error")) or 0.0
            tolerance = max(3.0 * math.sqrt(base_error**2 + error**2), 0.05)
            if value > base_value + tolerance:
                warnings.append(
                    _warning(
                        path=path,
                        field="matrix_elements.real.value",
                        value={"Pz": pz, "z": row.get("z"), "value": row.get("value")},
                        code="real_component_grows_with_z",
                        severity="warning",
                        message="Real matrix-element magnitude grows beyond the z=0 reference in the mock sanity check.",
                    )
                )


def diagnose_matrix_elements(path: str | Path) -> dict[str, Any]:
    matrix_path = Path(path)
    evidence = [
        {"path": str(matrix_path), "field": "exists", "value": matrix_path.exists()},
    ]
    warnings: list[dict[str, Any]] = []
    findings: list[str] = []
    recommended_checks: list[str] = []

    if not matrix_path.exists():
        warnings.append(
            _warning(
                path=matrix_path,
                field="exists",
                value=False,
                code="missing_matrix_element_artifact",
                severity="severe",
                message="Synthetic matrix-element artifact is missing.",
            )
        )
        return {
            "status": "severe",
            "summary": "Synthetic matrix-element artifact is missing.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": ["Re-run the Analysis Engineer before scientific review."],
        }

    try:
        payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(
            _warning(
                path=matrix_path,
                field="$",
                value=f"JSONDecodeError: {exc.msg}",
                code="invalid_matrix_element_json",
                severity="severe",
                message="Synthetic matrix-element artifact is not valid JSON.",
            )
        )
        return {
            "status": "severe",
            "summary": "Synthetic matrix-element artifact is not valid JSON.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": ["Regenerate the synthetic matrix-element artifact."],
        }

    if not isinstance(payload, dict):
        warnings.append(
            _warning(
                path=matrix_path,
                field="$",
                value=type(payload).__name__,
                code="invalid_matrix_element_payload",
                severity="severe",
                message="Synthetic matrix-element artifact must be a JSON object.",
            )
        )
        return {
            "status": "severe",
            "summary": "Synthetic matrix-element artifact has an invalid top-level shape.",
            "evidence": evidence,
            "findings": findings,
            "warnings": warnings,
            "recommended_checks": ["Regenerate the synthetic matrix-element artifact."],
        }

    evidence.extend(
        [
            {"path": str(matrix_path), "field": "source_kind", "value": payload.get("source_kind")},
            {
                "path": str(matrix_path),
                "field": "matrix_elements",
                "value": len(payload.get("matrix_elements", []))
                if isinstance(payload.get("matrix_elements"), list)
                else type(payload.get("matrix_elements")).__name__,
            },
            {"path": str(matrix_path), "field": "diagnostic_flags", "value": payload.get("diagnostic_flags")},
        ]
    )

    _check_required_fields(payload, matrix_path, warnings)
    _check_declared_lists(payload, matrix_path, warnings)

    if payload.get("source_kind") != "synthetic":
        warnings.append(
            _warning(
                path=matrix_path,
                field="source_kind",
                value=payload.get("source_kind"),
                code="unexpected_source_kind",
                severity="severe",
                message="Phase 5 reviewer only accepts synthetic matrix-element evidence.",
            )
        )

    _check_diagnostic_flags(payload, matrix_path, warnings)

    z_values = payload.get("z_values", [])
    pz_values = payload.get("pz_values", [])
    rows = payload.get("matrix_elements", [])
    valid_rows: list[dict[str, Any]] = []
    if isinstance(z_values, list) and isinstance(pz_values, list) and isinstance(rows, list):
        valid_rows = _check_row_fields(
            rows=rows,
            z_values=z_values,
            pz_values=pz_values,
            path=matrix_path,
            warnings=warnings,
        )
        _check_grid_coverage(rows=valid_rows, z_values=z_values, pz_values=pz_values, path=matrix_path, warnings=warnings)
        _check_mock_unit_normalization(payload=payload, rows=valid_rows, path=matrix_path, warnings=warnings)
        _check_simple_z_consistency(rows=valid_rows, path=matrix_path, warnings=warnings)

    if valid_rows:
        findings.append(f"Reviewed {len(valid_rows)} matrix-element row(s) across declared z/Pz coordinates.")
    else:
        findings.append("No valid matrix-element rows were available for complete diagnostics.")

    if warnings:
        recommended_checks.append("Inspect cited matrix-element fields before downstream decision coordination.")
    if any(warning["code"] == "upstream_diagnostic_flag" for warning in warnings):
        recommended_checks.append("Resolve upstream diagnostic flags or document why they are acceptable for this mock case.")
    if any(warning["severity"] == "severe" for warning in warnings):
        recommended_checks.append("Treat severe matrix-element warnings as high-risk evidence for Decision Coordinator.")

    has_severe = any(warning["severity"] == "severe" for warning in warnings)
    status = "severe" if has_severe else "warning" if warnings else "pass"
    summary = (
        "Matrix-element diagnostics found severe evidence-backed warnings."
        if has_severe
        else "Matrix-element diagnostics found evidence-backed warnings."
        if warnings
        else "Matrix-element diagnostics passed deterministic mock checks."
    )
    return {
        "status": status,
        "summary": summary,
        "evidence": evidence,
        "findings": findings,
        "warnings": warnings,
        "recommended_checks": recommended_checks,
    }
