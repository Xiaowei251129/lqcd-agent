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
