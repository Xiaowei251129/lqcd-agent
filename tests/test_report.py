import json
from pathlib import Path

from lqcd_agent.graph.state import initialize_state
from lqcd_agent.report.generate_report import write_final_report


def _write_json(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _state(tmp_path: Path):
    state = initialize_state(
        case_id="case_a",
        run_id="run_a",
        user_goal="mock goal",
        case_config_path="case.yaml",
        output_dir=str(tmp_path),
        checkpoint_backend="memory",
    )
    state["risk_level"] = "low"
    state["recommended_action"] = "accept_mock_result"
    state["method_plan_path"] = _write_json(
        tmp_path / "method_plan.json",
        {"schema_version": "0.1", "run_id": "run_a", "case_id": "case_a", "status": "success", "summary": "Plan."},
    )
    state["run_result_path"] = _write_json(
        tmp_path / "run_result.json",
        {
            "schema_version": "0.1",
            "run_id": "run_a",
            "case_id": "case_a",
            "status": "success",
            "run_success": True,
            "failure_type": None,
        },
    )
    state["scientific_review_report_path"] = _write_json(
        tmp_path / "scientific_review_report.json",
        {
            "schema_version": "0.1",
            "run_id": "run_a",
            "case_id": "case_a",
            "status": "success",
            "summary": "Review.",
            "warnings": [],
            "confidence": "high",
        },
    )
    state["decision_log_path"] = _write_json(
        tmp_path / "decision_log.json",
        {
            "schema_version": "0.1",
            "run_id": "run_a",
            "case_id": "case_a",
            "status": "success",
            "next_actions": [{"action": "accept_mock_result", "primary": True, "status": "ready"}],
        },
    )
    return state


def _decision_file(tmp_path: Path, decision: str) -> Path:
    packet_dir = tmp_path / "approval_packet"
    packet_dir.mkdir(parents=True, exist_ok=True)
    path = packet_dir / "07_human_decision.yaml"
    path.write_text(
        "\n".join(
            [
                'schema_version: "0.1"',
                'run_id: "run_a"',
                'case_id: "case_a"',
                f'decision: "{decision}"',
                'conditions: ""',
                'reason: "Reviewed by test."',
                'decided_by: "tester"',
                'decided_at: "2026-06-19T00:00:00+00:00"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_final_report_includes_required_sections(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["memory_update_path"] = str(tmp_path / "memory_update.json")
    memory_update = {"memory_status": "accepted", "accepted_result": True}

    result = write_final_report(state, memory_update)

    report = Path(result["final_report_path"]).read_text(encoding="utf-8")
    for heading in [
        "## Metadata",
        "## Method Plan",
        "## Run Summary",
        "## Scientific Review",
        "## Coordinator Decision",
        "## Approval Status",
        "## Memory Update",
        "## Reproducibility",
    ]:
        assert heading in report
    assert "- memory_status: accepted" in report
    assert "- risk_level: low" in report


def test_final_report_records_missing_artifact_warnings(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["scientific_review_report_path"] = str(tmp_path / "missing_review.json")
    memory_update = {"memory_status": "pending", "accepted_result": False}

    result = write_final_report(state, memory_update)

    report = Path(result["final_report_path"]).read_text(encoding="utf-8")
    assert "- scientific_review_report: file missing" in report
    assert "- memory_status: pending" in report


def test_final_report_names_approved_human_decision(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["human_approval_required"] = True
    state["human_decision_path"] = str(_decision_file(tmp_path, "approve_with_conditions"))
    memory_update = {"memory_status": "accepted", "accepted_result": True}

    result = write_final_report(state, memory_update)

    report = Path(result["final_report_path"]).read_text(encoding="utf-8")
    assert "Approved human decision: `approve_with_conditions`." in report
    assert "Human decision status: `approved`." not in report
