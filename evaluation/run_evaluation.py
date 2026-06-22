"""Synthetic Phase 8 evaluation harness."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lqcd_agent.graph import nodes
from lqcd_agent.graph.run_graph import run_mock_graph


DEFAULT_CASES_DIR = REPO_ROOT / "evaluation" / "cases"
DEFAULT_OUTPUT_DIR = Path("/private/tmp/lqcd-agent-phase8-evaluation")
SUMMARY_FIELDS = [
    "case_id",
    "passed",
    "expected_risk_level",
    "actual_risk_level",
    "expected_recommended_action",
    "actual_recommended_action",
    "expected_human_approval_required",
    "actual_human_approval_required",
    "expected_status",
    "actual_status",
    "expected_current_node",
    "actual_current_node",
    "expected_memory_status",
    "actual_memory_status",
    "expected_approval_packet",
    "actual_approval_packet",
    "run_output_dir",
    "notes",
]


def _parse_scalar(value: str) -> Any:
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def read_case(path: str | Path) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        payload[key.strip()] = _parse_scalar(value.strip())
    return payload


def load_cases(cases_dir: str | Path = DEFAULT_CASES_DIR) -> list[dict[str, Any]]:
    cases = []
    for path in sorted(Path(cases_dir).glob("*.yaml")):
        case = read_case(path)
        case["case_path"] = str(path)
        cases.append(case)
    return cases


def _review_report(*, run_id: str, case_id: str, variant: str, report_path: Path) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    confidence = "high"
    if variant == "ambiguous":
        confidence = "medium"
        warnings.append(
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
        )
    elif variant == "bad":
        confidence = "low"
        warnings.append(
            {
                "section": "matrix_element_diagnostics",
                "code": "non_positive_matrix_error",
                "severity": "severe",
                "decision_coordinator_flag": True,
                "message": "Matrix-element error must be positive.",
                "path": "analysis_outputs/synthetic_matrix_elements.json",
                "field": "matrix_elements[0].error",
                "value": -0.01,
            }
        )

    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "producer": "scientific_reviewer",
        "status": "success",
        "summary": f"Synthetic {variant} scientific review for Phase 8 evaluation.",
        "warnings": warnings,
        "errors": [],
        "correlator_diagnostics": {"status": "not_populated_mvp"},
        "fit_diagnostics": {"status": "not_populated_mvp"},
        "matrix_element_diagnostics": {"status": "pass" if variant == "good" else "warning"},
        "findings": [{"code": "synthetic_phase8_evaluation"}],
        "evidence": [{"path": str(report_path), "field": "synthetic_review", "value": variant}],
        "recommended_checks": [],
        "confidence": confidence,
    }


@contextmanager
def _synthetic_reviewer(variant: str) -> Iterator[None]:
    original = nodes.run_scientific_reviewer

    if variant == "good":
        yield
        return

    def fake_review(**kwargs: Any) -> dict[str, Any]:
        report_path = Path(kwargs["run_output_dir"]) / "scientific_review_report.json"
        report = _review_report(
            run_id=str(kwargs["run_id"]),
            case_id=str(kwargs["case_id"]),
            variant=variant,
            report_path=report_path,
        )
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "status": "success",
            "report_path": str(report_path),
            "scientific_review_report_path": str(report_path),
            "report": report,
            "warnings": report["warnings"],
            "errors": [],
            "confidence": report["confidence"],
        }

    nodes.run_scientific_reviewer = fake_review
    try:
        yield
    finally:
        nodes.run_scientific_reviewer = original


def _memory_status(run_output_dir: Path) -> str:
    path = run_output_dir / "memory_update.json"
    if not path.exists():
        return "none"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("memory_status"))


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def run_case(
    case: dict[str, Any],
    *,
    output_dir: str | Path,
    run_id_prefix: str,
    force_clean: bool = False,
) -> dict[str, str]:
    case_path = Path(case["case_path"])
    case_id = str(case["case_id"])
    run_id = f"{run_id_prefix}_{case_id}"
    variant = str(case.get("synthetic_review", "good"))
    run_output_dir = Path(output_dir) / case_id / run_id

    if run_output_dir.exists() and not force_clean:
        raise FileExistsError(
            "Refusing to delete existing evaluation run directory without force_clean: "
            f"{run_output_dir}. Use a new run_id_prefix or pass --force-clean."
        )
    if run_output_dir.exists():
        shutil.rmtree(run_output_dir)

    with _synthetic_reviewer(variant):
        result = run_mock_graph(case_path=str(case_path), output_dir=str(output_dir), run_id=run_id)
    state = result["state"]

    actual_memory_status = _memory_status(run_output_dir)
    actual_approval_packet = (run_output_dir / "approval_packet" / "approval_packet.json").exists()
    comparisons = {
        "risk_level": str(state["risk_level"]) == str(case["expected_risk_level"]),
        "recommended_action": str(state["recommended_action"]) == str(case["expected_recommended_action"]),
        "human_approval_required": bool(state["human_approval_required"])
        == bool(case["expected_human_approval_required"]),
        "status": str(state["status"]) == str(case["expected_status"]),
        "current_node": str(state["current_node"]) == str(case["expected_current_node"]),
        "memory_status": actual_memory_status == str(case["expected_memory_status"]),
        "approval_packet": actual_approval_packet == bool(case["expected_approval_packet"]),
    }
    notes = "; ".join(name for name, passed in comparisons.items() if not passed)
    return {
        "case_id": case_id,
        "passed": _bool_text(all(comparisons.values())),
        "expected_risk_level": str(case["expected_risk_level"]),
        "actual_risk_level": str(state["risk_level"]),
        "expected_recommended_action": str(case["expected_recommended_action"]),
        "actual_recommended_action": str(state["recommended_action"]),
        "expected_human_approval_required": _bool_text(case["expected_human_approval_required"]),
        "actual_human_approval_required": _bool_text(state["human_approval_required"]),
        "expected_status": str(case["expected_status"]),
        "actual_status": str(state["status"]),
        "expected_current_node": str(case["expected_current_node"]),
        "actual_current_node": str(state["current_node"]),
        "expected_memory_status": str(case["expected_memory_status"]),
        "actual_memory_status": actual_memory_status,
        "expected_approval_packet": _bool_text(case["expected_approval_packet"]),
        "actual_approval_packet": _bool_text(actual_approval_packet),
        "run_output_dir": str(run_output_dir),
        "notes": notes,
    }


def write_summary(rows: list[dict[str, str]], summary_path: str | Path) -> str:
    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def run_evaluation(
    *,
    cases_dir: str | Path = DEFAULT_CASES_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    summary_path: str | Path | None = None,
    run_id_prefix: str | None = None,
    force_clean: bool = False,
) -> dict[str, Any]:
    resolved_output_dir = Path(output_dir)
    resolved_summary_path = Path(summary_path) if summary_path else resolved_output_dir / "evaluation_summary.csv"
    prefix = run_id_prefix or datetime.now(timezone.utc).strftime("eval_%Y%m%d_%H%M%S")
    cases = load_cases(cases_dir)
    rows = [
        run_case(
            case,
            output_dir=resolved_output_dir,
            run_id_prefix=prefix,
            force_clean=force_clean,
        )
        for case in cases
    ]
    summary = write_summary(rows, resolved_summary_path)
    return {"rows": rows, "summary_path": summary, "passed": all(row["passed"] == "true" for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 8 synthetic evaluation cases.")
    parser.add_argument("--cases-dir", default=str(DEFAULT_CASES_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--summary-path", default=None)
    parser.add_argument(
        "--force-clean",
        action="store_true",
        help="Delete existing evaluation run directories for this run id prefix before running.",
    )
    args = parser.parse_args()
    result = run_evaluation(
        cases_dir=args.cases_dir,
        output_dir=args.output_dir,
        summary_path=args.summary_path,
        force_clean=args.force_clean,
    )
    print(f"evaluation_summary={result['summary_path']}")
    print(f"passed={result['passed']}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
