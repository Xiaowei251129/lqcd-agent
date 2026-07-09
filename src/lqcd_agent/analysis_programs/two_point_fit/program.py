"""Reusable two-point correlator fit helpers."""

from __future__ import annotations

import math
from typing import Sequence


def single_exponential_effective_mass(
    times: Sequence[float],
    correlator_values: Sequence[float],
    correlator_errors: Sequence[float] | None = None,
) -> dict[str, object]:
    if len(times) != len(correlator_values):
        raise ValueError("times and correlator_values must have the same length.")
    if correlator_errors is not None and len(times) != len(correlator_errors):
        raise ValueError("times and correlator_errors must have the same length.")
    if len(times) < 2:
        raise ValueError("At least two correlator points are required.")

    estimates: list[dict[str, float]] = []
    for index in range(len(correlator_values) - 1):
        current = float(correlator_values[index])
        following = float(correlator_values[index + 1])
        delta_t = float(times[index + 1]) - float(times[index])
        if current <= 0 or following <= 0 or delta_t <= 0:
            continue
        estimate = {
            "t_mid": (float(times[index]) + float(times[index + 1])) / 2.0,
            "effective_mass": math.log(current / following) / delta_t,
        }
        if correlator_errors is not None:
            current_error = float(correlator_errors[index])
            following_error = float(correlator_errors[index + 1])
            if current_error >= 0 and following_error >= 0:
                estimate["effective_mass_error"] = (
                    math.sqrt((current_error / current) ** 2 + (following_error / following) ** 2) / delta_t
                )
        estimates.append(estimate)

    status = "success" if estimates else "failed"
    diagnostic_flags: list[str] = []
    fit_window_diagnostics = _fit_window_diagnostics(estimates)
    if fit_window_diagnostics["fit_window_dependence"]:
        diagnostic_flags.append("fit_window_dependence")
    return {
        "schema_version": "0.1",
        "program": "single_exponential_effective_mass",
        "status": status,
        "effective_mass_estimates": estimates,
        "fit_window_diagnostics": fit_window_diagnostics,
        "diagnostic_flags": diagnostic_flags,
    }


def _fit_window_diagnostics(estimates: list[dict[str, float]]) -> dict[str, object]:
    usable = [
        estimate
        for estimate in estimates
        if "effective_mass_error" in estimate and float(estimate["effective_mass_error"]) > 0
    ]
    if len(usable) < 3:
        return {
            "status": "not_evaluated",
            "fit_window_dependence": False,
            "reason": "At least three effective-mass estimates with propagated errors are required.",
        }

    early = usable[0]
    late = usable[1:]
    weights = [1.0 / float(estimate["effective_mass_error"]) ** 2 for estimate in late]
    total_weight = sum(weights)
    if total_weight <= 0:
        return {
            "status": "not_evaluated",
            "fit_window_dependence": False,
            "reason": "Late-window uncertainty weights are not positive.",
        }

    late_weighted_mass = sum(
        weight * float(estimate["effective_mass"]) for weight, estimate in zip(weights, late, strict=True)
    ) / total_weight
    late_weighted_error = math.sqrt(1.0 / total_weight)
    early_mass = float(early["effective_mass"])
    early_error = float(early["effective_mass_error"])
    combined_error = math.sqrt(early_error**2 + late_weighted_error**2)
    mass_shift = abs(early_mass - late_weighted_mass)
    threshold = max(2.0 * combined_error, 0.12)
    threshold_tolerance = max(0.005, 0.02 * threshold)
    fit_window_dependence = mass_shift > 0.12 and mass_shift >= threshold - threshold_tolerance

    return {
        "status": "warning" if fit_window_dependence else "pass",
        "fit_window_dependence": fit_window_dependence,
        "early_mass": early_mass,
        "early_error": early_error,
        "late_weighted_mass": late_weighted_mass,
        "late_weighted_error": late_weighted_error,
        "mass_shift": mass_shift,
        "combined_error": combined_error,
        "threshold": threshold,
        "threshold_tolerance": threshold_tolerance,
    }
