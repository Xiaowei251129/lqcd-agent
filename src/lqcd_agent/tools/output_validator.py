"""Output validation helpers for mock analysis runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence


FORBIDDEN_PATH_PARTS = {"raw_data", "accepted_results"}
SYNTHETIC_OUTPUT_FIELDS = [
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


def _has_forbidden_path_part(path: Path) -> bool:
    return any(part in FORBIDDEN_PATH_PARTS for part in path.parts)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _resolve_expected_output(output_dir: Path, relative_path: str) -> tuple[Path | None, str | None]:
    expected = Path(relative_path)
    if expected.is_absolute():
        return None, "Expected outputs must be relative paths."
    if _has_forbidden_path_part(expected):
        return None, "Expected outputs must not reference raw_data or accepted_results."

    resolved = (output_dir / expected).resolve()
    if not _is_within(resolved, output_dir):
        return None, "Expected outputs must stay under the run output directory."
    return resolved, None


def _validate_synthetic_matrix_elements(
    *, payload: dict[str, Any], path: Path, run_id: str, case_id: str
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for field in SYNTHETIC_OUTPUT_FIELDS:
        if field not in payload:
            errors.append({"field": str(path), "message": f"{field} is missing."})

    if payload.get("run_id") != run_id:
        errors.append({"field": str(path), "message": "run_id does not match the active run."})
    if payload.get("case_id") != case_id:
        errors.append({"field": str(path), "message": "case_id does not match the active case."})
    if payload.get("source_kind") != "synthetic":
        errors.append({"field": str(path), "message": "source_kind must be synthetic for the synthetic matrix-element fixture."})

    for field in ["z_values", "pz_values", "matrix_elements", "diagnostic_flags"]:
        if field in payload and not isinstance(payload.get(field), list):
            errors.append({"field": str(path), "message": f"{field} must be a list."})

    matrix_elements = payload.get("matrix_elements", [])
    if isinstance(matrix_elements, list):
        for index, row in enumerate(matrix_elements):
            if not isinstance(row, dict):
                errors.append({"field": str(path), "message": f"matrix_elements[{index}] must be an object."})
                continue
            for field in ["z", "Pz", "component", "value", "error"]:
                if field not in row:
                    errors.append(
                        {"field": str(path), "message": f"matrix_elements[{index}].{field} is missing."}
                    )

    return errors


def validate_expected_outputs(
    *,
    output_dir: str | Path,
    expected_outputs: Sequence[str],
    run_id: str,
    case_id: str,
) -> dict[str, Any]:
    output_path = Path(output_dir).resolve()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    validated_outputs: list[str] = []
    missing_outputs: list[str] = []

    if not expected_outputs:
        errors.append({"field": "expected_outputs", "message": "At least one expected output is required."})

    for relative_output in expected_outputs:
        resolved, path_error = _resolve_expected_output(output_path, str(relative_output))
        if path_error or resolved is None:
            errors.append({"field": "expected_outputs", "message": path_error or "Invalid output path."})
            continue
        if not resolved.exists():
            missing_outputs.append(str(resolved))
            errors.append({"field": str(resolved), "message": "Expected output is missing."})
            continue
        if not resolved.is_file():
            errors.append({"field": str(resolved), "message": "Expected output is not a file."})
            continue

        validated_outputs.append(str(resolved))
        if resolved.suffix == ".json":
            try:
                payload = json.loads(resolved.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append({"field": str(resolved), "message": f"JSON output is invalid: {exc}."})
                continue
            if resolved.name == "synthetic_matrix_elements.json":
                errors.extend(
                    _validate_synthetic_matrix_elements(
                        payload=payload,
                        path=resolved,
                        run_id=run_id,
                        case_id=case_id,
                    )
                )
        else:
            warnings.append({"field": str(resolved), "message": "Output exists but has no format-specific validator."})

    return {
        "schema_version": "0.1",
        "status": "success" if not errors else "failed",
        "expected_outputs": [str(output) for output in expected_outputs],
        "validated_outputs": validated_outputs,
        "missing_outputs": missing_outputs,
        "warnings": warnings,
        "errors": errors,
    }
