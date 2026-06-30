"""Reusable matrix-element diagnostic helpers."""

from __future__ import annotations

from typing import Any, Sequence


def check_matrix_element_normalization(
    matrix_elements: Sequence[dict[str, Any]],
    *,
    target: float = 1.0,
    tolerance: float = 0.05,
) -> dict[str, object]:
    diagnostics: list[dict[str, object]] = []
    for row in matrix_elements:
        if row.get("z") != 0 or row.get("component") != "real":
            continue
        value = row.get("value")
        if not isinstance(value, (int, float)):
            continue
        deviation = abs(float(value) - target)
        diagnostics.append(
            {
                "z": row.get("z"),
                "Pz": row.get("Pz"),
                "value": float(value),
                "target": target,
                "deviation": deviation,
                "passed": deviation <= tolerance,
            }
        )

    return {
        "schema_version": "0.1",
        "program": "matrix_element_normalization_check",
        "status": "success" if diagnostics else "failed",
        "normalization_diagnostics": diagnostics,
        "all_passed": bool(diagnostics) and all(bool(item["passed"]) for item in diagnostics),
    }
