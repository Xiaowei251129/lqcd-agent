import csv
import importlib.util
from pathlib import Path

import pytest


RUNNER_PATH = Path("evaluation/run_evaluation.py")
SPEC = importlib.util.spec_from_file_location("phase8_evaluation_runner", RUNNER_PATH)
assert SPEC is not None
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


def test_loads_phase8_synthetic_cases() -> None:
    cases = runner.load_cases("evaluation/cases")

    assert {case["case_id"] for case in cases} == {
        "phase8_eval_good",
        "phase8_eval_ambiguous",
        "phase8_eval_bad",
    }


def test_evaluation_harness_writes_summary_csv(tmp_path: Path) -> None:
    summary_path = tmp_path / "evaluation_summary.csv"

    result = runner.run_evaluation(
        cases_dir="evaluation/cases",
        output_dir=tmp_path / "runs",
        summary_path=summary_path,
        run_id_prefix="test_eval",
    )

    rows = list(csv.DictReader(summary_path.open(encoding="utf-8")))
    assert result["passed"] is True
    assert len(rows) == 3
    assert {row["passed"] for row in rows} == {"true"}
    by_case = {row["case_id"]: row for row in rows}
    assert by_case["phase8_eval_good"]["actual_memory_status"] == "accepted"
    assert by_case["phase8_eval_ambiguous"]["actual_memory_status"] == "pending"
    assert by_case["phase8_eval_bad"]["actual_memory_status"] == "pending"
    assert by_case["phase8_eval_bad"]["actual_approval_packet"] == "true"


def test_evaluation_refuses_existing_run_directory_without_force_clean(tmp_path: Path) -> None:
    case = next(case for case in runner.load_cases("evaluation/cases") if case["case_id"] == "phase8_eval_good")
    run_dir = tmp_path / "runs" / "phase8_eval_good" / "repeat_phase8_eval_good"
    run_dir.mkdir(parents=True)
    sentinel = run_dir / "sentinel.txt"
    sentinel.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="force_clean"):
        runner.run_case(case, output_dir=tmp_path / "runs", run_id_prefix="repeat")

    assert sentinel.read_text(encoding="utf-8") == "keep me\n"


def test_evaluation_force_clean_removes_existing_run_directory(tmp_path: Path) -> None:
    case = next(case for case in runner.load_cases("evaluation/cases") if case["case_id"] == "phase8_eval_good")
    run_dir = tmp_path / "runs" / "phase8_eval_good" / "repeat_phase8_eval_good"
    run_dir.mkdir(parents=True)
    sentinel = run_dir / "sentinel.txt"
    sentinel.write_text("remove me\n", encoding="utf-8")

    row = runner.run_case(
        case,
        output_dir=tmp_path / "runs",
        run_id_prefix="repeat",
        force_clean=True,
    )

    assert row["passed"] == "true"
    assert not sentinel.exists()
    assert (run_dir / "memory_update.json").exists()
