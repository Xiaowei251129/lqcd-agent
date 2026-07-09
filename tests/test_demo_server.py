import json
from pathlib import Path

import pytest

from lqcd_agent.demo.server import (
    DemoServerError,
    apply_human_decision,
    case_configs,
    chat_response,
    run_status_payload,
    start_graph_run,
    validate_case_config_request,
    resolve_artifact_path,
    run_question_against_config,
    run_once_smoke,
)


def test_case_configs_endpoint_returns_repo_case_configs(tmp_path: Path) -> None:
    payload = {"configs": case_configs()}

    assert {config["config_id"] for config in payload["configs"]} >= {"mock_lqcd_goal", "l64c64a076_m140"}
    assert "hidden_expected_conclusion_summary" not in json.dumps(payload)


def test_validate_config_preview_rejects_missing_config(tmp_path: Path) -> None:
    with pytest.raises(DemoServerError, match="Missing case config"):
        validate_case_config_request(output_root=tmp_path, body={})


def test_validate_pasted_config_returns_preview(tmp_path: Path) -> None:
    payload = validate_case_config_request(
        output_root=tmp_path,
        body={
            "config_text": '\n'.join(
                [
                    'schema_version: "0.1"',
                    'case_id: "pasted_case"',
                    'physics_goal: "Run pasted config."',
                    "analysis_commands:",
                    '- "mock:write_synthetic_matrix_elements"',
                    "expected_outputs:",
                    '- "analysis_outputs/synthetic_matrix_elements.json"',
                ]
            )
        },
    )

    assert payload["config"]["case_id"] == "pasted_case"
    assert payload["config"]["analysis_commands"] == ["mock:write_synthetic_matrix_elements"]


def test_run_config_writes_core_artifacts_and_report(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run a local config-backed smoke test.",
        config_id="mock_lqcd_goal",
        output_root=tmp_path,
        run_id_prefix="test_ui_config",
    )
    artifact = next(item for item in payload["artifacts"] if item["name"] == "final_report")
    artifact_path = resolve_artifact_path(output_root=tmp_path, requested_path=artifact["path"])
    artifact_text = artifact_path.read_text(encoding="utf-8")

    assert payload["summary"]["risk_level"] == "low"
    assert Path(payload["run_dir"], "method_plan.json").exists()
    assert Path(payload["run_dir"], "final_report.md").exists()
    assert "hidden_expected_conclusion_summary" not in artifact_text


def test_artifact_endpoint_rejects_paths_outside_output_root(tmp_path: Path) -> None:
    with pytest.raises(DemoServerError, match="outside the demo output root"):
        resolve_artifact_path(output_root=tmp_path, requested_path="/etc/passwd")


def test_start_graph_run_returns_pollable_run_payload(tmp_path: Path) -> None:
    payload = start_graph_run(
        config_id="mock_lqcd_goal",
        output_root=tmp_path,
        run_id_prefix="test_async_run",
    )
    polled = run_status_payload(output_root=tmp_path, case_id=payload["case_id"], run_id=payload["run_id"])

    assert polled["case_id"] == "mock_lqcd_goal"
    assert polled["summary"]["status"] in {"running", "success"}


def test_once_smoke_runs_clean_case(tmp_path: Path) -> None:
    result = run_once_smoke(tmp_path)

    assert result["ok"] is True
    assert result["case_id"] == "mock_lqcd_goal"
    assert Path(result["run_dir"], "final_report.md").exists()


def test_chat_requires_explicit_evidence_context(tmp_path: Path) -> None:
    with pytest.raises(DemoServerError, match="Missing case config"):
        chat_response(message="Is this result acceptable?", config_id=None, output_root=tmp_path)


def test_chat_runs_langgraph_with_question_as_physics_goal_from_config(tmp_path: Path) -> None:
    question = "Can this selected config produce a report?"

    payload = chat_response(
        message=question,
        config_id="mock_lqcd_goal",
        output_root=tmp_path,
        run_id_prefix="test_chat_question",
    )
    run = payload["run"]
    method_plan = json.loads(Path(run["run_dir"], "method_plan.json").read_text(encoding="utf-8"))

    assert payload["mode"] == "single"
    assert run["summary"]["risk_level"] == "low"
    assert run["summary"]["human_approval_required"] is False
    assert method_plan["physics_goal"] == question
    assert "运行了 LangGraph" in payload["content"]


def test_golden_config_payload_marks_pending_human_approval(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run the golden example through the UI.",
        config_id="l64c64a076_m140",
        output_root=tmp_path,
        run_id_prefix="test_golden_ui",
    )

    assert payload["summary"]["human_approval_required"] is True
    assert payload["approval"]["pending"] is True
    assert payload["approval"]["packet"]["decision_options"]


def test_human_decision_approve_with_conditions_updates_memory(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run the golden example and approve it.",
        config_id="l64c64a076_m140",
        output_root=tmp_path,
        run_id_prefix="test_approve_ui",
    )

    updated = apply_human_decision(
        output_root=tmp_path,
        case_id=payload["case_id"],
        run_id=payload["run_id"],
        decision="approve_with_conditions",
        conditions="UI approval test.",
        reason="Reviewed packet.",
        decided_by="pytest",
    )
    memory = json.loads(Path(updated["run_dir"], "memory_update.json").read_text(encoding="utf-8"))

    assert updated["approval"]["pending"] is False
    assert updated["approval"]["decision"]["decision"] == "approve_with_conditions"
    assert memory["memory_status"] == "accepted"


def test_human_decision_reject_or_hold_updates_memory(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run the golden example and reject it.",
        config_id="l64c64a076_m140",
        output_root=tmp_path,
        run_id_prefix="test_reject_ui",
    )

    updated = apply_human_decision(
        output_root=tmp_path,
        case_id=payload["case_id"],
        run_id=payload["run_id"],
        decision="reject_or_hold",
        reason="Hold for review.",
        decided_by="pytest",
    )
    memory = json.loads(Path(updated["run_dir"], "memory_update.json").read_text(encoding="utf-8"))

    assert updated["approval"]["pending"] is False
    assert updated["approval"]["decision"]["decision"] == "reject_or_hold"
    assert memory["memory_status"] == "rejected"
