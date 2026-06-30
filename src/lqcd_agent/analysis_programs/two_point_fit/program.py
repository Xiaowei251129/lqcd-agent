"""Reusable two-point correlator fit helpers."""

from __future__ import annotations

import math
from typing import Sequence


def single_exponential_effective_mass(
    times: Sequence[float],
    correlator_values: Sequence[float],
) -> dict[str, object]:
    if len(times) != len(correlator_values):
        raise ValueError("times and correlator_values must have the same length.")
    if len(times) < 2:
        raise ValueError("At least two correlator points are required.")

    estimates: list[dict[str, float]] = []
    for index in range(len(correlator_values) - 1):
        current = float(correlator_values[index])
        following = float(correlator_values[index + 1])
        delta_t = float(times[index + 1]) - float(times[index])
        if current <= 0 or following <= 0 or delta_t <= 0:
            continue
        estimates.append(
            {
                "t_mid": (float(times[index]) + float(times[index + 1])) / 2.0,
                "effective_mass": math.log(current / following) / delta_t,
            }
        )

    status = "success" if estimates else "failed"
    return {
        "schema_version": "0.1",
        "program": "single_exponential_effective_mass",
        "status": status,
        "effective_mass_estimates": estimates,
    }
