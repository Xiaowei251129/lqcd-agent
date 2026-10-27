import json
from pathlib import Path

from lqcd_agent.agents.scientific_reviewer import run_scientific_reviewer
from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse
from lqcd_agent.llm.mock_provider import MockLLMProvider, mock_proposal


class StaticProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.config = LLMProviderConfig(schema_version="0.1", provider="static", dry_run_only=True)

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(provider="static", model="static", content=self.content)


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


def _write_effective_mass_artifacts(
    tmp_path: Path,
    *,
    estimates: object | None = None,
    diagnostic_flags: list[str] | None = None,
    run_id: str = "run_fit",
    case_id: str = "case_fit",
) -> tuple[Path, Path, Path]:
    run_dir = tmp_path / case_id / run_id
    analysis_dir = run_dir / "analysis_outputs"
    analysis_dir.mkdir(parents=True)
    output_path = analysis_dir / "effective_mass_estimates.json"
    output_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "run_id": run_id,
                "case_id": case_id,
                "producer": "analysis_engineer",
                "status": "success",
                "program": "single_exponential_effective_mass",
                "diagnostic_flags": diagnostic_flags or [],
                "fit_window_diagnostics": {
                    "status": "warning" if diagnostic_flags else "pass",
                    "fit_window_dependence": "fit_window_dependence" in (diagnostic_flags or []),
                },
                "effective_mass_estimates": estimates
                if estimates is not None
                else [
                    {"t_start": 0, "t_end": 1, "effective_mass": 0.3},
                    {"t_start": 1, "t_end": 2, "effective_mass": 0.31},
                ],
            }
        ),
        encoding="utf-8",
    )
    run_result = {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "analysis_engineer",
        "status": "success",
        "summary": "Analysis Engineer completed the effective-mass analysis run.",
        "warnings": [],
        "errors": [],
        "run_success": True,
        "failure_type": None,
        "analysis_outputs_dir": str(analysis_dir),
        "expected_outputs": ["analysis_outputs/effective_mass_estimates.json"],
        "produced_outputs": [str(output_path)],
        "validation_results": {"status": "success"},
        "command_references": [],
        "commands": [],
        "run_log_path": str(run_dir / "run.log"),
        "manifest_path": str(run_dir / "manifest.json"),
    }
    run_result_path = run_dir / "run_result.json"
    run_result_path.write_text(json.dumps(run_result), encoding="utf-8")
    method_plan = {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "producer": "method_planner",
        "status": "success",
        "target_observables": ["effective_mass_estimates"],
        "required_outputs": ["analysis_outputs/effective_mass_estimates.json"],
        "code_needed": False,
    }
    method_plan_path = run_dir / "method_plan.json"
    method_plan_path.write_text(json.dumps(method_plan), encoding="utf-8")
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


def test_effective_mass_case_marks_matrix_diagnostics_not_applicable(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_effective_mass_artifacts(tmp_path)

    result = run_scientific_reviewer(
        run_id="run_fit",
        case_id="case_fit",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
    )
    report = result["report"]

    assert result["status"] == "success"
    assert report["warnings"] == []
    assert report["confidence"] == "high"
    assert report["fit_diagnostics"]["status"] == "pass"
    assert report["matrix_element_diagnostics"]["status"] == "not_applicable"
    assert "synthetic_matrix_elements" not in json.dumps(report)


def test_effective_mass_case_reports_malformed_estimates(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_effective_mass_artifacts(
        tmp_path,
        estimates=[{"t_start": 0, "t_end": 1, "effective_mass": "bad"}],
    )

    result = run_scientific_reviewer(
        run_id="run_fit",
        case_id="case_fit",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
    )
    report = result["report"]

    assert report["confidence"] == "low"
    assert report["fit_diagnostics"]["status"] == "severe"
    assert report["warnings"][0]["code"] == "invalid_effective_mass_value"
    assert report["matrix_element_diagnostics"]["status"] == "not_applicable"


def test_effective_mass_diagnostic_flags_become_structured_warnings(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_effective_mass_artifacts(
        tmp_path,
        diagnostic_flags=["fit_window_dependence"],
    )

    result = run_scientific_reviewer(
        run_id="run_fit",
        case_id="case_fit",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
    )
    report = result["report"]

    assert result["status"] == "success"
    assert report["confidence"] == "medium"
    assert report["fit_diagnostics"]["status"] == "warning"
    assert report["matrix_element_diagnostics"]["status"] == "not_applicable"
    assert report["warnings"][0]["code"] == "upstream_diagnostic_flag"
    assert report["warnings"][0]["section"] == "fit_diagnostics"
    assert report["warnings"][0]["severity"] == "warning"
    assert report["warnings"][0]["decision_coordinator_flag"] is False
    assert report["warnings"][0]["field"] == "diagnostic_flags[0]"
    assert report["warnings"][0]["value"] == "fit_window_dependence"


def test_provider_backed_effective_mass_flags_lower_confidence(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_effective_mass_artifacts(
        tmp_path,
        diagnostic_flags=["fit_window_dependence"],
    )

    result = run_scientific_reviewer(
        run_id="run_fit",
        case_id="case_fit",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
        provider=MockLLMProvider(),
    )
    report = result["report"]

    assert result["status"] == "success"
    assert report["confidence"] == "medium"
    assert report["warnings"][0]["value"] == "fit_window_dependence"


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


def test_provider_backed_scientific_reviewer_accepts_valid_mock_output(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_run_artifacts(tmp_path, _good_matrix_payload())

    result = run_scientific_reviewer(
        run_id="run_a",
        case_id="case_a",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
        provider=MockLLMProvider(),
    )
    report = json.loads((run_dir / "scientific_review_report.json").read_text(encoding="utf-8"))

    assert result["status"] == "success"
    assert report["producer"] == "scientific_reviewer"
    assert report["confidence"] == "high"
    assert report["summary"].startswith("Provider-backed mock")
    trace = json.loads((run_dir / "llm_calls" / "scientific_reviewer.json").read_text(encoding="utf-8"))
    assert trace["agent"] == "scientific_reviewer"
    assert trace["provider"]["provider"] == "mock"
    assert trace["parsed_payload_path"] == str(run_dir / "scientific_review_report.json")
    assert trace["response"]["content"]


def test_provider_backed_effective_mass_case_marks_matrix_not_applicable(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_effective_mass_artifacts(tmp_path)

    result = run_scientific_reviewer(
        run_id="run_fit",
        case_id="case_fit",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
        provider=MockLLMProvider(),
    )
    report = json.loads((run_dir / "scientific_review_report.json").read_text(encoding="utf-8"))

    assert result["status"] == "success"
    assert report["confidence"] == "high"
    assert report["fit_diagnostics"]["status"] == "pass"
    assert report["matrix_element_diagnostics"]["status"] == "not_applicable"
    assert "synthetic_matrix_elements" not in json.dumps(report["warnings"])


def test_invalid_provider_scientific_reviewer_cannot_inject_warnings(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_run_artifacts(tmp_path, _good_matrix_payload())
    result = run_scientific_reviewer(
        run_id="run_a",
        case_id="case_a",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
        provider=StaticProvider(
            '{"status": "success", "warnings": [{"message": "free form severe route"}]}'
        ),
    )
    report = json.loads((run_dir / "scientific_review_report.json").read_text(encoding="utf-8"))

    assert result["status"] == "failed"
    assert report["status"] == "failed"
    assert report["warnings"] == []
    assert "free form severe route" not in json.dumps(report)


def test_provider_scientific_reviewer_rejects_string_warning_items(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_run_artifacts(tmp_path, _good_matrix_payload())
    valid_except_warning_shape = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "scientific_reviewer",
        "status": "success",
        "summary": "Invalid warning shape.",
        "warnings": ["warning text is not structured evidence"],
        "errors": [],
        "correlator_diagnostics": {"status": "not_populated_mvp"},
        "fit_diagnostics": {"status": "not_populated_mvp"},
        "matrix_element_diagnostics": {"status": "pass"},
        "findings": [{"code": "checked"}],
        "evidence": [{"field": "x", "value": "y"}],
        "recommended_checks": [],
        "confidence": "high",
    }

    result = run_scientific_reviewer(
        run_id="run_a",
        case_id="case_a",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
        provider=StaticProvider(json.dumps(mock_proposal(valid_except_warning_shape, 'scientific_review_report'))),
    )
    report = json.loads((run_dir / "scientific_review_report.json").read_text(encoding="utf-8"))

    assert result["status"] == "failed"
    assert report["errors"][0]["code"] == "provider_schema_error"


def test_provider_scientific_reviewer_filters_context_only_warnings(tmp_path: Path) -> None:
    run_dir, run_result_path, method_plan_path = _write_run_artifacts(tmp_path, _good_matrix_payload())
    payload = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "scientific_reviewer",
        "status": "success",
        "summary": "Synthetic benchmark output is usable.",
        "warnings": [
            {"type": "context", "message": "Matrix elements are synthetic with mock_unit normalization."},
            {"code": "warning_monitoring", "message": "Monitor fit stability."},
        ],
        "errors": [],
        "correlator_diagnostics": {"status": "not_populated_mvp"},
        "fit_diagnostics": {"status": "not_populated_mvp"},
        "matrix_element_diagnostics": {"status": "pass"},
        "findings": [{"code": "checked"}],
        "evidence": [{"field": "x", "value": "y"}],
        "recommended_checks": [],
        "confidence": "high",
    }

    result = run_scientific_reviewer(
        run_id="run_a",
        case_id="case_a",
        run_output_dir=run_dir,
        run_result_path=run_result_path,
        method_plan_path=method_plan_path,
        provider=StaticProvider(json.dumps(mock_proposal(payload, 'scientific_review_report'))),
    )

    assert result["status"] == "success"
    assert result["warnings"] == []
