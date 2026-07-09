import json
from pathlib import Path

from lqcd_agent.agents.analysis_engineer import run_analysis_engineer


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
        output_root=tmp_path,
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
        output_root=tmp_path,
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
        output_root=tmp_path,
        repo_root=tmp_path,
    )
    run_result = json.loads((tmp_path / "case_a" / "run_a" / "run_result.json").read_text(encoding="utf-8"))
    command = run_result["commands"][0]

    assert result["run_success"] is False
    assert result["failure_type"] == "code"
    assert command["return_code"] == 1
    assert command["stderr"] == "Configured mock command failed."


def test_selected_registered_program_runs_from_raw_csv(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    raw_data_dir = repo_root / "raw_data"
    raw_data_dir.mkdir(parents=True)
    (raw_data_dir / "clean_decay.csv").write_text(
        "t,value,error\n"
        "0,1.000,0.020\n"
        "1,0.741,0.020\n"
        "2,0.549,0.025\n"
        "3,0.407,0.030\n",
        encoding="utf-8",
    )
    case_path = repo_root / "configs" / "cases" / "clean_fit.input.json"
    case_path.parent.mkdir(parents=True)
    case_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "case_id": "clean_fit_raw",
                "physics_goal": "Recover effective-mass estimates.",
                "raw_data_path": "raw_data/clean_decay.csv",
                "expected_outputs": ["analysis_outputs/effective_mass_estimates.json"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "clean_fit_raw" / "run_a"
    run_dir.mkdir(parents=True)
    method_plan_path = run_dir / "method_plan.json"
    method_plan_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "run_id": "run_a",
                "case_id": "clean_fit_raw",
                "producer": "method_planner",
                "status": "success",
                "summary": "Select registered program.",
                "warnings": [],
                "errors": [],
                "physics_goal": "Recover effective-mass estimates.",
                "target_observables": ["effective_mass_estimates"],
                "method_steps": ["Run registered program."],
                "required_inputs": ["case_config", "repo_inventory", "raw data"],
                "required_outputs": ["analysis_outputs/effective_mass_estimates.json"],
                "implementation_gaps": [],
                "selected_analysis_programs": [
                    {
                        "name": "single_exponential_effective_mass",
                        "category": "two_point_fit",
                        "callable_path": (
                            "lqcd_agent.analysis_programs.two_point_fit.program."
                            "single_exponential_effective_mass"
                        ),
                        "input_mapping": {
                            "times": "raw_data_csv.t",
                            "correlator_values": "raw_data_csv.value",
                            "correlator_errors": "raw_data_csv.error",
                        },
                        "output_path": "analysis_outputs/effective_mass_estimates.json",
                        "required_outputs": ["effective_mass_estimates"],
                    }
                ],
                "code_needed": False,
                "coder_task_summary": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_analysis_engineer(
        case_config_path=case_path,
        case_id="clean_fit_raw",
        run_id="run_a",
        run_output_dir=run_dir,
        method_plan_path=method_plan_path,
        repo_root=repo_root,
    )
    output = json.loads((run_dir / "analysis_outputs" / "effective_mass_estimates.json").read_text(encoding="utf-8"))
    run_result = json.loads((run_dir / "run_result.json").read_text(encoding="utf-8"))

    assert result["run_success"] is True
    assert run_result["commands"][0]["command_kind"] == "analysis_program"
    assert output["program"] == "single_exponential_effective_mass"
    assert len(output["effective_mass_estimates"]) == 3
    assert output["effective_mass_estimates"][0]["effective_mass_error"] > 0
    assert output["diagnostic_flags"] == []
    assert output["raw_data_path"] == "raw_data/clean_decay.csv"


def test_selected_registered_program_records_missing_raw_csv_failure(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "configs" / "cases").mkdir(parents=True)
    case_path = repo_root / "configs" / "cases" / "missing_input.input.json"
    case_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "case_id": "missing_input",
                "physics_goal": "Stop safely when raw data is missing.",
                "raw_data_path": "raw_data/does_not_exist.csv",
                "expected_outputs": ["analysis_outputs/effective_mass_estimates.json"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "missing_input" / "run_a"
    run_dir.mkdir(parents=True)
    method_plan_path = run_dir / "method_plan.json"
    method_plan_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "run_id": "run_a",
                "case_id": "missing_input",
                "producer": "method_planner",
                "status": "success",
                "summary": "Select registered program.",
                "warnings": [],
                "errors": [],
                "physics_goal": "Stop safely when raw data is missing.",
                "target_observables": ["effective_mass_estimates"],
                "method_steps": ["Run registered program."],
                "required_inputs": ["case_config", "repo_inventory", "raw data"],
                "required_outputs": ["analysis_outputs/effective_mass_estimates.json"],
                "implementation_gaps": [],
                "selected_analysis_programs": [
                    {
                        "name": "single_exponential_effective_mass",
                        "category": "two_point_fit",
                        "callable_path": (
                            "lqcd_agent.analysis_programs.two_point_fit.program."
                            "single_exponential_effective_mass"
                        ),
                        "input_mapping": {
                            "times": "raw_data_csv.t",
                            "correlator_values": "raw_data_csv.value",
                        },
                        "output_path": "analysis_outputs/effective_mass_estimates.json",
                        "required_outputs": ["effective_mass_estimates"],
                    }
                ],
                "code_needed": False,
                "coder_task_summary": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_analysis_engineer(
        case_config_path=case_path,
        case_id="missing_input",
        run_id="run_a",
        run_output_dir=run_dir,
        method_plan_path=method_plan_path,
        repo_root=repo_root,
    )
    run_result = json.loads((run_dir / "run_result.json").read_text(encoding="utf-8"))

    assert result["run_success"] is False
    assert result["failure_type"] == "config_or_data"
    assert run_result["failure_type"] == "config_or_data"
    assert run_result["commands"][0]["status"] == "blocked"
    assert "raw_data_path does not exist" in run_result["commands"][0]["stderr"]
    assert run_result["validation_results"]["missing_outputs"]


def test_existing_run_artifacts_are_not_overwritten_without_force(tmp_path: Path) -> None:
    case_path = _write_case(tmp_path, _base_case_lines())
    first = run_analysis_engineer(
        case_config_path=case_path,
        case_id="case_a",
        run_id="run_a",
        output_root=tmp_path,
        repo_root=tmp_path,
    )
    second = run_analysis_engineer(
        case_config_path=case_path,
        case_id="case_a",
        run_id="run_a",
        output_root=tmp_path,
        repo_root=tmp_path,
    )

    assert first["run_success"] is True
    assert second["run_success"] is False
    assert second["failure_type"] == "workflow"
    assert second["run_result_path"] is None
    assert "Refusing to overwrite" in second["errors"][0]["message"]
