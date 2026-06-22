import json
from pathlib import Path

from lqcd_agent.agents.decision_coordinator import run_decision_coordinator


def _method_plan(*, run_id: str = "run_a", case_id: str = "case_a") -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "method_planner",
        "status": "success",
        "summary": "Method plan is usable.",
        "warnings": [],
        "errors": [],
        "code_needed": False,
    }


def _run_result(*, run_id: str = "run_a", case_id: str = "case_a") -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "analysis_engineer",
        "status": "success",
        "summary": "Run succeeded.",
        "warnings": [],
        "errors": [],
        "run_success": True,
        "failure_type": None,
        "analysis_outputs_dir": "analysis_outputs",
        "produced_outputs": ["analysis_outputs/synthetic_matrix_elements.json"],
    }


def _review_report(*, run_id: str = "run_a", case_id: str = "case_a") -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "scientific_reviewer",
        "status": "success",
        "summary": "Review passed.",
        "warnings": [],
        "errors": [],
        "findings": [{"code": "matrix_elements_checked"}],
        "evidence": [{"path": "analysis_outputs/synthetic_matrix_elements.json", "field": "matrix_elements", "value": "checked"}],
        "recommended_checks": [],
        "confidence": "high",
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_artifacts(
    tmp_path: Path,
    *,
    method_plan: dict[str, object] | None = None,
    run_result: dict[str, object] | None = None,
    review_report: dict[str, object] | None = None,
) -> tuple[Path, Path, Path]:
    method_path = _write_json(tmp_path / "method_plan.json", method_plan or _method_plan())
    run_path = _write_json(tmp_path / "run_result.json", run_result or _run_result())
    review_path = _write_json(tmp_path / "scientific_review_report.json", review_report or _review_report())
    return method_path, run_path, review_path


def _run_decision(tmp_path: Path, *, method_path: Path, run_path: Path, review_path: Path) -> dict[str, object]:
    return run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
    )["decision_log"]


def _assert_one_primary_next_action(decision_log: dict[str, object]) -> None:
    next_actions = decision_log["next_actions"]
    assert isinstance(next_actions, list)
    assert sum(1 for action in next_actions if action["primary"] is True) == 1


def test_low_risk_accepts_mock_result_with_structured_evidence(tmp_path: Path) -> None:
    method_path, run_path, review_path = _write_artifacts(tmp_path)

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "success"
    assert decision_log["risk_level"] == "low"
    assert decision_log["recommended_action"] == "accept_mock_result"
    assert decision_log["human_approval_required"] is False
    assert decision_log["routing_decision"]["actual_route"] == "memory_report"
    assert decision_log["routing_decision"]["fields"]["rerun_requested"] is False
    assert decision_log["routing_decision"]["fields"]["code_fix_requested"] is False
    assert (tmp_path / "decision_log.json").exists()
    _assert_one_primary_next_action(decision_log)


def test_medium_risk_is_pending_and_human_review_recommended(tmp_path: Path) -> None:
    review = _review_report()
    review["warnings"] = [
        {
            "section": "matrix_element_diagnostics",
            "code": "plateau_short",
            "severity": "warning",
            "decision_coordinator_flag": False,
            "message": "Synthetic diagnostic flag needs review.",
            "path": "analysis_outputs/synthetic_matrix_elements.json",
            "field": "diagnostic_flags[0]",
            "value": "plateau_short",
        }
    ]
    review["confidence"] = "medium"
    method_path, run_path, review_path = _write_artifacts(tmp_path, review_report=review)

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "pending"
    assert decision_log["risk_level"] == "medium"
    assert decision_log["recommended_action"] == "human_review_recommended"
    assert decision_log["human_approval_required"] is False
    assert decision_log["routing_decision"]["actual_route"] == "memory_report"
    assert decision_log["routing_decision"]["requested_route"] == "memory_report"
    _assert_one_primary_next_action(decision_log)


def test_high_risk_severe_warning_requires_human_approval(tmp_path: Path) -> None:
    review = _review_report()
    review["warnings"] = [
        {
            "section": "matrix_element_diagnostics",
            "code": "non_positive_error",
            "severity": "severe",
            "decision_coordinator_flag": True,
            "message": "Matrix-element error must be positive.",
            "path": "analysis_outputs/synthetic_matrix_elements.json",
            "field": "matrix_elements[0].error",
            "value": -0.01,
        }
    ]
    review["confidence"] = "low"
    method_path, run_path, review_path = _write_artifacts(tmp_path, review_report=review)

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "pending"
    assert decision_log["risk_level"] == "high"
    assert decision_log["recommended_action"] == "pending_human_approval"
    assert decision_log["human_approval_required"] is True
    assert decision_log["routing_decision"]["actual_route"] == "human_approval_gate"
    assert decision_log["routing_decision"]["requested_route"] == "human_approval_gate"
    _assert_one_primary_next_action(decision_log)


def test_critical_risk_for_missing_required_review_artifact(tmp_path: Path) -> None:
    method_path = _write_json(tmp_path / "method_plan.json", _method_plan())
    run_path = _write_json(tmp_path / "run_result.json", _run_result())
    review_path = tmp_path / "missing_scientific_review_report.json"

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "pending"
    assert decision_log["risk_level"] == "critical"
    assert decision_log["recommended_action"] == "pending_human_approval"
    assert decision_log["human_approval_required"] is True
    assert decision_log["errors"]
    assert decision_log["routing_decision"]["actual_route"] == "human_approval_gate"
    assert decision_log["routing_decision"]["requested_route"] == "human_approval_gate"
    _assert_one_primary_next_action(decision_log)
