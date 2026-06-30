import json
from pathlib import Path

import pytest

from lqcd_agent.demo.server import (
    DemoServerError,
    case_configs,
    chat_response,
    resolve_artifact_path,
    run_question_against_config,
    run_once_smoke,
)


def test_case_configs_endpoint_returns_repo_case_configs(tmp_path: Path) -> None:
    payload = {"configs": case_configs()}

    assert {config["config_id"] for config in payload["configs"]} >= {"mock_lqcd_goal", "l64c64a076_m140"}
    assert "hidden_expected_conclusion_summary" not in json.dumps(payload)


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
