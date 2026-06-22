"""Fit-strategy diagnostics for the deterministic Scientific Reviewer."""

from __future__ import annotations

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


def diagnose_fit_outputs(analysis_outputs_dir: str | Path) -> dict[str, Any]:
    output_dir = Path(analysis_outputs_dir)
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
