import json
from pathlib import Path

from lqcd_agent.agents.scientific_reviewer import run_scientific_reviewer


def _good_matrix_payload(*, run_id: str = "run_a", case_id: str = "case_a") -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "analysis_engineer",
        "status": "success",
        "summary": "Mock synthetic matrix elements without real raw data.",
        "warnings": [],
        "errors": [],
        "source_kind": "synthetic",
        "z_values": [0, 1],
        "pz_values": [1],
        "matrix_elements": [
            {"z": 0, "Pz": 1, "component": "real", "value": 1.0, "error": 0.01},
            {"z": 1, "Pz": 1, "component": "real", "value": 0.5, "error": 0.02},
        ],
        "normalization": "mock_unit",
        "uncertainties": "deterministic_mock",
        "diagnostic_flags": [],
    }


def _write_run_artifacts(tmp_path: Path, matrix_payload: dict[str, object]) -> tuple[Path, Path, Path]:
    run_dir = tmp_path / str(matrix_payload["case_id"]) / str(matrix_payload["run_id"])
    analysis_dir = run_dir / "analysis_outputs"
    analysis_dir.mkdir(parents=True)
    matrix_path = analysis_dir / "synthetic_matrix_elements.json"
    matrix_path.write_text(json.dumps(matrix_payload), encoding="utf-8")
    run_result = {
        "schema_version": "0.1",
        "run_id": matrix_payload["run_id"],
        "case_id": matrix_payload["case_id"],
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "analysis_engineer",
        "status": "success",
        "summary": "Analysis Engineer completed the mock analysis run.",
        "warnings": [],
        "errors": [],
        "run_success": True,
        "failure_type": None,
        "analysis_outputs_dir": str(analysis_dir),
        "expected_outputs": ["analysis_outputs/synthetic_matrix_elements.json"],
        "produced_outputs": [str(matrix_path)],
        "validation_results": {"status": "success"},
        "command_references": [],
        "commands": [],
        "run_log_path": str(run_dir / "run.log"),
        "manifest_path": str(run_dir / "manifest.json"),
    }
    run_result_path = run_dir / "run_result.json"
    run_result_path.write_text(json.dumps(run_result), encoding="utf-8")
    method_plan_path = run_dir / "method_plan.json"
    method_plan_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "run_id": matrix_payload["run_id"],
                "case_id": matrix_payload["case_id"],
                "producer": "method_planner",
                "status": "success",
            }
        ),
        encoding="utf-8",
    )
    return run_dir, run_result_path, method_plan_path


def _run_review(tmp_path: Path, matrix_payload: dict[str, object]) -> dict[str, object]:
    run_dir, run_result_path, method_plan_path = _write_run_artifacts(tmp_path, matrix_payload)
    result = run_scientific_reviewer(
        run_id=str(matrix_payload["run_id"]),
        case_id=str(matrix_payload["case_id"]),
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
    )
    return result["report"]


def test_good_mock_matrix_table_has_all_sections_without_warnings(tmp_path: Path) -> None:
    report = _run_review(tmp_path, _good_matrix_payload())

    assert report["warnings"] == []
    assert report["confidence"] == "high"
    assert report["correlator_diagnostics"]["status"] == "not_populated_mvp"
    assert report["fit_diagnostics"]["status"] == "not_populated_mvp"
    assert report["matrix_element_diagnostics"]["status"] == "pass"
    assert report["findings"]
    assert report["evidence"]


def test_ambiguous_mock_table_has_non_severe_evidence_warning(tmp_path: Path) -> None:
    payload = _good_matrix_payload()
    payload["diagnostic_flags"] = ["plateau_short"]

    report = _run_review(tmp_path, payload)

    assert report["confidence"] == "medium"
    assert len(report["warnings"]) == 1
    warning = report["warnings"][0]
    assert warning["severity"] == "warning"
    assert warning["decision_coordinator_flag"] is False
    assert warning["path"]
    assert warning["field"] == "diagnostic_flags[0]"
    assert warning["value"] == "plateau_short"


def test_bad_mock_table_has_severe_warning_for_decision_coordinator(tmp_path: Path) -> None:
    payload = _good_matrix_payload()
    rows = payload["matrix_elements"]
    assert isinstance(rows, list)
    rows[0]["error"] = -0.01

    report = _run_review(tmp_path, payload)

    severe_warnings = [warning for warning in report["warnings"] if warning["severity"] == "severe"]
    assert report["confidence"] == "low"
    assert severe_warnings
    assert severe_warnings[0]["decision_coordinator_flag"] is True
    assert severe_warnings[0]["field"] == "matrix_elements[0].error"
    assert severe_warnings[0]["value"] == -0.01
