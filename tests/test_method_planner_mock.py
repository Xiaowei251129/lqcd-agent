import json
from pathlib import Path

from lqcd_agent.agents.method_planner import run_method_planner


def _case_config() -> dict[str, str]:
    return {
        "schema_version": "0.1",
        "case_id": "mock_lqcd_goal",
        "source_kind": "synthetic_placeholder",
        "physics_goal": "Plan a mock-only pion quasi-DA analysis support run.",
    }


def test_mock_goal_generates_valid_method_plan(tmp_path: Path) -> None:
    result = run_method_planner(
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config=_case_config(),
        repo_inventory={"schema_version": "0.1", "implementation_gaps": []},
        output_dir=tmp_path,
        run_id="unit_run",
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))

    assert result["status"] == "success"
    assert result["code_needed"] is False
    assert method_plan["status"] == "success"
    assert method_plan["physics_goal"] == _case_config()["physics_goal"]
    assert method_plan["target_observables"]
    assert method_plan["method_steps"]
    assert method_plan["required_inputs"]
    assert method_plan["required_outputs"]
    assert method_plan["implementation_gaps"] == []
    assert method_plan["code_needed"] is False
    assert method_plan["coder_task_summary"] is None


def test_code_needed_generates_valid_task_packet(tmp_path: Path) -> None:
    result = run_method_planner(
        user_goal="Plan the mock run and hand off missing implementation gaps.",
        case_config=_case_config(),
        repo_inventory={
            "schema_version": "0.1",
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/agents/method_planner.py"],
        },
        output_dir=tmp_path,
        run_id="unit_run",
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))
    packet_text = (tmp_path / "coder_task_packet.yaml").read_text(encoding="utf-8")

    assert result["status"] == "success"
    assert result["code_needed"] is True
    assert result["coder_task_packet_path"] == str(tmp_path / "coder_task_packet.yaml")
    assert method_plan["code_needed"] is True
    assert "schema_version: \"0.1\"" in packet_text
    assert "status: \"pending\"" in packet_text
    assert "task_summary:" in packet_text
    assert "- \"pytest tests/test_method_planner_mock.py -q\"" in packet_text


def test_missing_critical_fields_produce_needs_more_info(tmp_path: Path) -> None:
    result = run_method_planner(
        user_goal="",
        case_config={"schema_version": "0.1"},
        repo_inventory={"schema_version": "0.1"},
        output_dir=tmp_path,
        run_id="unit_run",
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))

    assert result["status"] == "needs_more_info"
    assert result["coder_task_packet_path"] is None
    assert method_plan["status"] == "needs_more_info"
    assert method_plan["errors"]
    assert {error["field"] for error in method_plan["errors"]} == {"user_goal", "case_config.case_id"}
