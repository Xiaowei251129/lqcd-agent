"""Synthetic advisor-demo benchmark models and artifact writers."""

from __future__ import annotations

import csv
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BENCHMARK_SCHEMA_VERSION = "0.1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Scenario input must be a JSON object.")
    return payload


def _benchmark_root(scenario_path: Path) -> Path:
    for parent in [scenario_path.parent, *scenario_path.parents]:
        if parent.name == "synthetic_benchmarks":
            return parent
    raise ValueError("Scenario input must live under evaluation/synthetic_benchmarks/.")


def _resolve_data_path(scenario_path: Path, scenario: dict[str, Any]) -> Path:
    data_path = scenario.get("data_path")
    if not isinstance(data_path, str) or not data_path:
        raise ValueError("Scenario input is missing data_path.")
    candidate = Path(data_path)
    if not candidate.is_absolute():
        candidate = _benchmark_root(scenario_path) / candidate
    candidate = candidate.resolve()
    root = _benchmark_root(scenario_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Synthetic benchmark data must stay under evaluation/synthetic_benchmarks/.") from exc
    if not candidate.exists():
        raise FileNotFoundError(f"Synthetic data fixture is missing: {candidate}")
    return candidate


def _read_data_rows(data_path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with data_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, 1):
            try:
                rows.append(
                    {
                        "t": float(row["t"]),
                        "value": float(row["value"]),
                        "error": float(row["error"]),
                    }
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid synthetic CSV row {index}: {row}") from exc
    if not rows:
        raise ValueError("Synthetic data fixture must contain at least one row.")
    return rows


def _weighted_linear_fit(points: list[dict[str, float]]) -> dict[str, float]:
    weights = [1.0 / (row["error"] ** 2) for row in points]
    xs = [row["t"] for row in points]
    ys = [math.log(row["value"]) for row in points]
    sum_w = sum(weights)
    sum_x = sum(w * x for w, x in zip(weights, xs))
    sum_y = sum(w * y for w, y in zip(weights, ys))
    sum_xx = sum(w * x * x for w, x in zip(weights, xs))
    sum_xy = sum(w * x * y for w, x, y in zip(weights, xs, ys))
    denominator = sum_w * sum_xx - sum_x * sum_x
    if denominator == 0:
        raise ValueError("Synthetic fit is singular.")
    slope = (sum_w * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / sum_w
    amplitude = math.exp(intercept)
    mass = -slope
    return {"amplitude": amplitude, "mass": mass, "intercept": intercept, "slope": slope}


def _fit_summary(
    *,
    scenario: dict[str, Any],
    rows: list[dict[str, float]],
    run_id: str,
    case_id: str,
    data_path: Path,
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    flags = list(scenario.get("diagnostic_flags", [])) if isinstance(scenario.get("diagnostic_flags"), list) else []
    if any(row["error"] <= 0 for row in rows):
        flags.append(
            {
                "code": "invalid_uncertainty",
                "severity": "severe",
                "message": "At least one synthetic fixture row has a non-positive uncertainty.",
            }
        )
    if any(row["value"] <= 0 for row in rows):
        flags.append(
            {
                "code": "invalid_fit_value",
                "severity": "severe",
                "message": "The exponential fit requires positive values.",
            }
        )

    valid_for_fit = [row for row in rows if row["error"] > 0 and row["value"] > 0]
    parameters: dict[str, float] = {}
    reduced_chi2: float | None = None
    status = "success"
    if len(valid_for_fit) < 2:
        status = "failed"
        errors.append({"field": "synthetic_data", "message": "At least two valid rows are required for fitting."})
    else:
        parameters = _weighted_linear_fit(valid_for_fit)
        degrees_of_freedom = max(len(valid_for_fit) - 2, 1)
        chi2 = 0.0
        for row in valid_for_fit:
            predicted = parameters["amplitude"] * math.exp(-parameters["mass"] * row["t"])
            chi2 += ((row["value"] - predicted) / row["error"]) ** 2
        reduced_chi2 = chi2 / degrees_of_freedom
        if reduced_chi2 > 4.0:
            flags.append(
                {
                    "code": "large_reduced_chi2",
                    "severity": "warning",
                    "message": "The synthetic fit has a large reduced chi-square.",
                }
            )

    for flag in flags:
        if not isinstance(flag, dict):
            continue
        severity = str(flag.get("severity", "warning"))
        item = {
            "code": str(flag.get("code", "synthetic_benchmark_flag")),
            "severity": severity,
            "message": str(flag.get("message", "Synthetic benchmark diagnostic flag.")),
        }
        if severity == "severe":
            warnings.append(item)
        else:
            warnings.append(item)

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": utc_now(),
        "producer": "analysis_engineer",
        "status": status,
        "summary": f"Synthetic benchmark fit for {case_id}.",
        "warnings": warnings,
        "errors": errors,
        "scenario_id": scenario.get("case_id", case_id),
        "scenario_goal": scenario.get("goal"),
        "source_data_path": str(data_path),
        "model": "single_exponential_log_linear",
        "row_count": len(rows),
        "parameter_estimates": parameters,
        "reduced_chi2": reduced_chi2,
        "diagnostic_flags": flags,
    }


def _flag_texts(flags: list[Any]) -> list[str]:
    values: list[str] = []
    for flag in flags:
        if isinstance(flag, dict):
            values.append(str(flag.get("code", "synthetic_benchmark_flag")))
        else:
            values.append(str(flag))
    return values


def _matrix_payload(
    *,
    scenario: dict[str, Any],
    rows: list[dict[str, float]],
    fit_summary: dict[str, Any],
    run_id: str,
    case_id: str,
) -> dict[str, Any]:
    matrix_config = scenario.get("matrix_element")
    if not isinstance(matrix_config, dict):
        matrix_config = {}
    pz = float(matrix_config.get("Pz", 1.0))
    normalization = str(matrix_config.get("normalization", "mock_unit"))
    z0_override = matrix_config.get("z0_real_value")
    error_override = matrix_config.get("error_override")
    flags = _flag_texts(fit_summary.get("diagnostic_flags", []))
    extra_flags = matrix_config.get("diagnostic_flags", [])
    if isinstance(extra_flags, list):
        flags.extend(str(flag) for flag in extra_flags)

    matrix_rows = []
    z_values = []
    amplitude = fit_summary.get("parameter_estimates", {}).get("amplitude") or rows[0]["value"]
    for row in rows:
        z = int(row["t"]) if row["t"].is_integer() else row["t"]
        z_values.append(z)
        value = row["value"] / amplitude if amplitude else row["value"]
        if z == 0 and z0_override is not None:
            value = float(z0_override)
        error = row["error"] / abs(amplitude) if amplitude else row["error"]
        if error_override is not None and z == 0:
            error = float(error_override)
        matrix_rows.append(
            {
                "z": z,
                "Pz": pz,
                "component": "real",
                "value": value,
                "error": error,
            }
        )

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": utc_now(),
        "producer": "analysis_engineer",
        "status": "success",
        "summary": "Scenario-specific synthetic matrix elements for the advisor-demo benchmark.",
        "warnings": [],
        "errors": [],
        "source_kind": "synthetic",
        "z_values": z_values,
        "pz_values": [pz],
        "matrix_elements": matrix_rows,
        "normalization": normalization,
        "uncertainties": "synthetic_benchmark_fixture",
        "diagnostic_flags": sorted(set(flags)),
        "benchmark_scenario": {
            "case_id": scenario.get("case_id", case_id),
            "category": scenario.get("category"),
        },
    }


def write_synthetic_benchmark_artifacts(
    *,
    scenario_input_path: str | Path,
    output_dir: str | Path,
    run_id: str,
    case_id: str,
    force: bool = False,
) -> dict[str, Any]:
    scenario_path = Path(scenario_input_path).resolve()
    scenario = _read_json(scenario_path)
    if scenario.get("case_id") != case_id:
        raise ValueError("Scenario case_id must match the active graph case_id.")

    data_path = _resolve_data_path(scenario_path, scenario)
    rows = _read_data_rows(data_path)
    run_dir = Path(output_dir).resolve()
    analysis_dir = run_dir / "analysis_outputs"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {
        "scenario": analysis_dir / "synthetic_benchmark_input.json",
        "data": analysis_dir / "synthetic_data.csv",
        "fit": analysis_dir / "fit_summary.json",
        "matrix": analysis_dir / "synthetic_matrix_elements.json",
    }
    existing = [path for path in output_paths.values() if path.exists()]
    if existing and not force:
        raise FileExistsError("Refusing to overwrite synthetic benchmark artifacts without force.")

    output_paths["scenario"].write_text(json.dumps(scenario, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copyfile(data_path, output_paths["data"])
    fit = _fit_summary(scenario=scenario, rows=rows, run_id=run_id, case_id=case_id, data_path=data_path)
    matrix = _matrix_payload(scenario=scenario, rows=rows, fit_summary=fit, run_id=run_id, case_id=case_id)
    output_paths["fit"].write_text(json.dumps(fit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_paths["matrix"].write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "scenario": scenario,
        "fit_summary": fit,
        "matrix_elements": matrix,
        "produced_files": [str(output_paths["matrix"])],
        "support_files": [str(output_paths[key]) for key in ["scenario", "data", "fit"]],
    }
