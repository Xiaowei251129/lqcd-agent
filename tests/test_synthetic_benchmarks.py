import importlib.util
import json
from pathlib import Path

import pytest


RUNNER_PATH = Path("evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py")
SPEC = importlib.util.spec_from_file_location("phase10c_synthetic_benchmark_runner", RUNNER_PATH)
assert SPEC is not None
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


def test_loads_scenarios_and_instructor_only_expected_behavior() -> None:
    cases = runner.load_case_set("demo")

    assert {case["scenario"]["case_id"] for case in cases} == {
        "phase10c_clean_fit",
        "phase10c_noisy_valid_fit",
        "phase10c_fit_window_contamination",
        "phase10c_normalization_violation",
        "phase10c_targeted_rerun",
    }
    for case in cases:
        assert "hidden_expected_conclusion_summary" not in case["scenario"]
        assert "hidden_expected_conclusion_summary" in case["expected"]


def test_mock_provider_demo_writes_checklists_and_summary(tmp_path: Path) -> None:
    result = runner.run_benchmarks(
        case_set="demo",
        output_dir=tmp_path,
        provider="mock",
        run_id_prefix="test_demo",
    )

    assert result["passed"] is True
    assert Path(result["summary_path"]).exists()
    assert result["advisor_demo_report_path"] is None
    for row in result["rows"]:
        checklist_path = Path(row["checklist"]["artifact_paths"]["checklist"])
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
        assert checklist["passed"] is True
        assert checklist["items"]


def test_mock_provider_full_case_set_passes(tmp_path: Path) -> None:
    result = runner.run_benchmarks(
        case_set="full",
        output_dir=tmp_path,
        provider="mock",
        run_id_prefix="test_full",
    )

    assert result["passed"] is True
    assert result["case_count"] == 9


def test_scenario_data_is_consumed_without_exposing_expected_notes(tmp_path: Path) -> None:
    result = runner.run_benchmarks(
        case_set="demo",
        output_dir=tmp_path,
        provider="mock",
        run_id_prefix="test_data",
    )
    clean = next(row for row in result["rows"] if row["scenario"]["case_id"] == "phase10c_clean_fit")
    run_dir = Path(clean["run_dir"])
    fit_summary = json.loads((run_dir / "analysis_outputs" / "fit_summary.json").read_text(encoding="utf-8"))
    matrix = json.loads((run_dir / "analysis_outputs" / "synthetic_matrix_elements.json").read_text(encoding="utf-8"))
    run_result = json.loads((run_dir / "run_result.json").read_text(encoding="utf-8"))
    final_report = (run_dir / "final_report.md").read_text(encoding="utf-8")

    assert fit_summary["scenario_id"] == "phase10c_clean_fit"
    assert fit_summary["parameter_estimates"]["mass"] == pytest.approx(0.30, abs=0.08)
    assert len(matrix["matrix_elements"]) == 4
    assert run_result["commands"][0]["command"].startswith("analysis:run_synthetic_benchmark:")
    assert run_result["commands"][0]["command_kind"] == "analysis"
    assert run_result["produced_outputs"] == [str(run_dir / "analysis_outputs" / "synthetic_matrix_elements.json")]
    assert run_result["warnings"] == []
    assert "hidden_expected_conclusion_summary" not in final_report
    assert clean["expected"]["hidden_expected_conclusion_summary"] not in final_report


def test_normalization_violation_requires_human_gate_and_pending_memory(tmp_path: Path) -> None:
    result = runner.run_benchmarks(
        case_set="demo",
        output_dir=tmp_path,
        provider="mock",
        run_id_prefix="test_gate",
    )
    row = next(item for item in result["rows"] if item["scenario"]["case_id"] == "phase10c_normalization_violation")
    run_dir = Path(row["run_dir"])
    memory = json.loads((run_dir / "memory_update.json").read_text(encoding="utf-8"))

    assert row["state"]["risk_level"] == "high"
    assert row["state"]["human_approval_required"] is True
    assert (run_dir / "approval_packet" / "approval_packet.json").exists()
    assert memory["memory_status"] == "pending"
    assert memory["accepted_result"] is False


def test_live_provider_rehearsal_requires_explicit_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_LIVE_LLM_TESTS", raising=False)

    with pytest.raises(RuntimeError, match="RUN_LIVE_LLM_TESTS=1"):
        runner.run_benchmarks(
            case_set="demo",
            output_dir=tmp_path,
            provider=None,
            provider_config="configs/runtime/mock_llm.yaml",
            run_id_prefix="test_live_guard",
        )
