"""Correlator diagnostics for the deterministic Scientific Reviewer."""

from __future__ import annotations

from pathlib import Path
from typing import Any


CORRELATOR_PATTERNS = [
    "correlator*.json",
    "correlator*.csv",
    "correlator*.png",
    "correlator*.pdf",
]


def _discover_correlator_artifacts(analysis_outputs_dir: Path) -> list[Path]:
    if not analysis_outputs_dir.exists():
        return []
    artifacts: list[Path] = []
    for pattern in CORRELATOR_PATTERNS:
        artifacts.extend(analysis_outputs_dir.glob(pattern))
    return sorted(path for path in artifacts if path.is_file())


def diagnose_correlator_outputs(analysis_outputs_dir: str | Path) -> dict[str, Any]:
    output_dir = Path(analysis_outputs_dir)
    artifacts = _discover_correlator_artifacts(output_dir)
    evidence = [
        {"path": str(output_dir), "field": "exists", "value": output_dir.exists()},
        {"path": str(output_dir), "field": "correlator_artifact_count", "value": len(artifacts)},
    ]

    if not artifacts:
        return {
            "status": "not_populated_mvp",
            "summary": "No correlator summary table or plot is populated for the mock MVP.",
            "evidence": evidence,
            "findings": ["Correlator diagnostics section is present but not populated in this mock run."],
            "warnings": [],
            "recommended_checks": ["Add correlator summary artifacts in a future correlator-focused ticket."],
        }

    evidence.extend(
        {"path": str(path), "field": "artifact_name", "value": path.name}
        for path in artifacts
    )
    return {
        "status": "present",
        "summary": "Optional correlator artifacts were found for reviewer context.",
        "evidence": evidence,
        "findings": [f"Found {len(artifacts)} optional correlator artifact(s)."],
        "warnings": [],
        "recommended_checks": [],
    }
