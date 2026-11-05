import json
from pathlib import Path

import pytest

from lqcd_agent.agents.analysis_engineer import run_analysis_engineer
from lqcd_agent.analysis_programs.registry import selected_analysis_programs
from lqcd_agent.tools.dataset import snapshot_dataset
from lqcd_agent.tools.repo_inventory import build_repo_inventory


def _write_case(tmp_path: Path, lines: list[str]) -> Path:
    case_path = tmp_path / "case.yaml"
    case_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return case_path


def _base_case_lines(case_id: str = "case_a") -> list[str]:
    return [
        'schema_version: "0.1"',
        f'case_id: "{case_id}"',
        'physics_goal: "Run a mock-only analysis."',
    ]


def test_success_command_returns_run_success_true(tmp_path: Path) -> None:
    case_path = _write_case(tmp_path, _base_case_lines())

    result = run_analysis_engineer(
        case_config_path=case_path,
        case_id="case_a",
        run_id="run_a",
        run_output_dir=tmp_path / "case_a" / "run_a",
        repo_root=tmp_path,
    )
    run_dir = tmp_path / "case_a" / "run_a"
    run_result = json.loads((run_dir / "run_result.json").read_text(encoding="utf-8"))

    assert result["run_success"] is True
    assert run_result["run_success"] is True
    assert run_result["failure_type"] is None
    assert (run_dir / "analysis_outputs" / "synthetic_matrix_elements.json").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "run.log").exists()


def test_missing_output_returns_config_or_data_failure(tmp_path: Path) -> None:
    case_path = _write_case(
        tmp_path,
        _base_case_lines()
        + [
            "analysis_commands:",
            '- "mock:success"',
            "expected_outputs:",
            '- "analysis_outputs/missing.json"',
        ],
    )

    result = run_analysis_engineer(
        case_config_path=case_path,
        case_id="case_a",
        run_id="run_a",
        run_output_dir=tmp_path / "case_a" / "run_a",
        repo_root=tmp_path,
    )
    run_result = json.loads((tmp_path / "case_a" / "run_a" / "run_result.json").read_text(encoding="utf-8"))

    assert result["run_success"] is False
    assert result["failure_type"] == "config_or_data"
    assert run_result["failure_type"] == "config_or_data"
    assert run_result["validation_results"]["missing_outputs"]


def test_command_failure_records_return_code_and_stderr(tmp_path: Path) -> None:
    case_path = _write_case(
        tmp_path,
        _base_case_lines()
        + [
            "analysis_commands:",
            '- "mock:fail"',
        ],
    )

    result = run_analysis_engineer(
        case_config_path=case_path,
        case_id="case_a",
        run_id="run_a",
        run_output_dir=tmp_path / "case_a" / "run_a",
        repo_root=tmp_path,
    )
    run_result = json.loads((tmp_path / "case_a" / "run_a" / "run_result.json").read_text(encoding="utf-8"))
    command = run_result["commands"][0]

    assert result["run_success"] is False
    assert result["failure_type"] == "code"
    assert command["return_code"] == 1
    assert command["stderr"] == "Configured mock command failed."


@pytest.mark.parametrize("has_input", [True, False], ids=["raw-csv", "missing-input"])
def test_selected_two_point_program_executes_its_registered_mapping(tmp_path, has_input):
    raw_path = "raw_data/clean_decay.csv"
    if has_input:
        raw = tmp_path / raw_path
        raw.parent.mkdir()
        raw.write_text("t,value,error\n0,1,.020\n1,.741,.020\n2,.549,.025\n3,.407,.030\n")
    output = "analysis_outputs/effective_mass_estimates.json"
    config = {"raw_data_path": raw_path, "target_observables": ["effective_mass_estimates"],
              "expected_outputs": [output]}
    inventory = {**build_repo_inventory(tmp_path), "dataset_snapshot": snapshot_dataset(config, tmp_path)}
    selected = selected_analysis_programs(config, inventory)
    case = tmp_path / "case.json"
    case.write_text(json.dumps(config))
    plan = tmp_path / "method_plan.json"
    plan.write_text(json.dumps({"selected_analysis_programs": selected}))
    run_dir = tmp_path / "case" / "run"
    result = run_analysis_engineer(case_config_path=case, case_id="case", run_id="run",
                                  run_output_dir=run_dir, method_plan_path=plan, repo_root=tmp_path)
    record = json.loads((run_dir / "run_result.json").read_text())
    assert result["run_success"] is has_input
    if has_input:
        payload = json.loads((run_dir / output).read_text())
        assert record["commands"][0]["command_kind"] == "analysis_program"
        assert payload["program"] == "single_exponential_effective_mass"
        assert len(payload["effective_mass_estimates"]) == 3
        assert payload["effective_mass_estimates"][0]["effective_mass_error"] > 0
        assert payload["diagnostic_flags"] == []
        assert payload["raw_data_path"] == raw_path
    else:
        assert result["failure_type"] == record["failure_type"] == "config_or_data"
        assert record["commands"][0]["status"] == "blocked"
        assert "raw_data_path does not exist" in record["commands"][0]["stderr"]
        assert record["validation_results"]["missing_outputs"]


def test_existing_run_artifacts_are_not_overwritten(tmp_path: Path) -> None:
    case_path = _write_case(tmp_path, _base_case_lines())
    first = run_analysis_engineer(
        case_config_path=case_path,
        case_id="case_a",
        run_id="run_a",
        run_output_dir=tmp_path / "case_a" / "run_a",
        repo_root=tmp_path,
    )
    second = run_analysis_engineer(
        case_config_path=case_path,
        case_id="case_a",
        run_id="run_a",
        run_output_dir=tmp_path / "case_a" / "run_a",
        repo_root=tmp_path,
    )

    assert first["run_success"] is True
    assert second["run_success"] is False
    assert second["failure_type"] == "workflow"
    assert second["run_result_path"] is None
    assert "Refusing to overwrite" in second["errors"][0]["message"]
