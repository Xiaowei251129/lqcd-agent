"""Phase 10C synthetic advisor-demo benchmark runner."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lqcd_agent.graph.run_graph import run_mock_graph


BENCHMARK_ROOT = Path(__file__).resolve().parent
SCENARIOS_DIR = BENCHMARK_ROOT / "scenarios"
EXPECTED_DIR = BENCHMARK_ROOT / "expected"
CASE_SETS_DIR = BENCHMARK_ROOT / "case_sets"
MOCK_PROVIDER_CONFIG = REPO_ROOT / "configs" / "runtime" / "mock_llm.yaml"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_prefix() -> str:
    return datetime.now(timezone.utc).strftime("phase10c_%Y%m%d_%H%M%S")


def read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def load_scenarios() -> dict[str, dict[str, Any]]:
    scenarios: dict[str, dict[str, Any]] = {}
    for path in sorted(SCENARIOS_DIR.glob("*.input.json")):
        payload = read_json(path)
        case_id = str(payload["case_id"])
        payload["scenario_input_path"] = str(path)
        scenarios[case_id] = payload
    return scenarios


def load_expected_behavior(case_id: str) -> dict[str, Any]:
    return read_json(EXPECTED_DIR / f"{case_id}.expected.json")


def load_case_set(case_set: str) -> list[dict[str, Any]]:
    case_set_payload = read_json(CASE_SETS_DIR / f"{case_set}.json")
    scenario_by_id = load_scenarios()
    cases = []
    for case_id in case_set_payload["case_ids"]:
        scenario = scenario_by_id[str(case_id)]
        expected = load_expected_behavior(str(case_id))
        cases.append({"scenario": scenario, "expected": expected})
    return cases


def _write_case_config(
    *,
    scenario: dict[str, Any],
    output_dir: Path,
) -> Path:
    case_id = str(scenario["case_id"])
    generated_dir = output_dir / "_generated_cases"
    generated_dir.mkdir(parents=True, exist_ok=True)
    case_path = generated_dir / f"{case_id}.yaml"
    scenario_path = Path(str(scenario["scenario_input_path"])).resolve()
    if scenario.get("category") == "code_fix_branch":
        command = "mock:fail"
        expected_outputs = ['analysis_outputs/synthetic_matrix_elements.json']
        allowed_commands: list[str] = []
    else:
        command = f"analysis:run_synthetic_benchmark:{scenario_path}"
        expected_outputs = ["analysis_outputs/synthetic_matrix_elements.json"]
        allowed_commands = [command]
    lines = [
        'schema_version: "0.1"',
        f'case_id: "{case_id}"',
        f'physics_goal: "{scenario["goal"]}"',
        "analysis_commands:",
        f'- "{command}"',
        "expected_outputs:",
        *[f'- "{path}"' for path in expected_outputs],
    ]
    if allowed_commands:
        lines.extend(["allowed_analysis_commands:", *[f'- "{command}"' for command in allowed_commands]])
    case_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return case_path


def _read_json_object(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    json_path = Path(path)
    if not json_path.exists():
        return None
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _memory_status(run_dir: Path) -> str:
    payload = _read_json_object(run_dir / "memory_update.json")
    if not payload:
        return "none"
    return str(payload.get("memory_status", "none"))


def _route_nodes(state: dict[str, Any]) -> list[str]:
    nodes: list[str] = []
    for event in state.get("event_log", []):
        if isinstance(event, dict) and event.get("node"):
            nodes.append(str(event["node"]))
    for decision in state.get("route_decisions", []):
        if isinstance(decision, dict):
            if decision.get("source"):
                nodes.append(str(decision["source"]))
            if decision.get("route") and decision.get("route") != "end":
                nodes.append(str(decision["route"]))
    if state.get("current_node"):
        nodes.append(str(state["current_node"]))
    unique: list[str] = []
    for node in nodes:
        if node not in unique:
            unique.append(node)
    return unique


def _review_warning_codes(review: dict[str, Any] | None) -> list[str]:
    if not review:
        return []
    warnings = review.get("warnings", [])
    if not isinstance(warnings, list):
        return []
    return [str(warning.get("code")) for warning in warnings if isinstance(warning, dict)]


def _review_warning_values(review: dict[str, Any] | None) -> list[str]:
    if not review:
        return []
    warnings = review.get("warnings", [])
    if not isinstance(warnings, list):
        return []
    return [str(warning.get("value")) for warning in warnings if isinstance(warning, dict)]


def _fit_mass(fit_summary: dict[str, Any] | None) -> float | None:
    if not fit_summary:
        return None
    parameters = fit_summary.get("parameter_estimates", {})
    if not isinstance(parameters, dict):
        return None
    mass = parameters.get("mass")
    return float(mass) if isinstance(mass, (int, float)) else None


def _z0_real_value(matrix_payload: dict[str, Any] | None) -> float | None:
    if not matrix_payload:
        return None
    rows = matrix_payload.get("matrix_elements", [])
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("z") == 0 and row.get("component") == "real":
            value = row.get("value")
            return float(value) if isinstance(value, (int, float)) else None
    return None


def _numeric_checks(
    *,
    expected: dict[str, Any],
    fit_summary: dict[str, Any] | None,
    matrix_payload: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    tolerances = expected.get("numeric_tolerances", {})
    if not isinstance(tolerances, dict):
        return True, []
    actuals = {
        "mass": _fit_mass(fit_summary),
        "z0_real_value": _z0_real_value(matrix_payload),
    }
    failures: list[str] = []
    for field, spec in tolerances.items():
        if not isinstance(spec, dict):
            continue
        actual = actuals.get(str(field))
        expected_value = spec.get("expected")
        tolerance = spec.get("absolute_tolerance")
        if not isinstance(actual, (int, float)) or not isinstance(expected_value, (int, float)) or not isinstance(
            tolerance, (int, float)
        ):
            failures.append(str(field))
            continue
        if abs(float(actual) - float(expected_value)) > float(tolerance):
            failures.append(str(field))
    return not failures, failures


def _item(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def build_checklist(
    *,
    scenario: dict[str, Any],
    expected: dict[str, Any],
    state: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    method_plan = _read_json_object(state.get("method_plan_path"))
    run_result = _read_json_object(state.get("run_result_path"))
    review = _read_json_object(state.get("scientific_review_report_path"))
    decision = _read_json_object(state.get("decision_log_path"))
    memory_status = _memory_status(run_dir)
    final_report_path = run_dir / "final_report.md"
    final_report = final_report_path.read_text(encoding="utf-8") if final_report_path.exists() else ""
    fit_summary = _read_json_object(run_dir / "analysis_outputs" / "fit_summary.json")
    matrix_payload = _read_json_object(run_dir / "analysis_outputs" / "synthetic_matrix_elements.json")
    scenario_copy = _read_json_object(run_dir / "analysis_outputs" / "synthetic_benchmark_input.json")
    route_nodes = _route_nodes(state)
    warning_codes = _review_warning_codes(review)
    warning_values = _review_warning_values(review)
    numeric_passed, numeric_failures = _numeric_checks(
        expected=expected,
        fit_summary=fit_summary,
        matrix_payload=matrix_payload,
    )
    expected_route = expected.get("expected_route_contains", [])
    route_passed = all(node in route_nodes for node in expected_route if isinstance(node, str))
    required_codes = expected.get("required_warning_codes", [])
    required_values = expected.get("required_warning_values", [])
    forbidden_codes = expected.get("forbidden_warning_codes", [])
    warnings_passed = all(code in warning_codes for code in required_codes) and all(
        value in warning_values for value in required_values
    ) and not any(code in warning_codes for code in forbidden_codes)
    approval_packet = (run_dir / "approval_packet" / "approval_packet.json").exists()
    expected_rerun = expected.get("expected_rerun_requested")
    rerun_passed = True
    if expected_rerun is not None:
        rerun_passed = bool(state.get("rerun_requested")) == bool(expected_rerun)
        if expected.get("expected_rerun_target") is not None:
            rerun_passed = rerun_passed and state.get("rerun_target") == expected.get("expected_rerun_target")
    actual_command_recorded = False
    if run_result and isinstance(run_result.get("commands"), list):
        actual_command_recorded = any(
            str(command.get("command", "")).startswith("analysis:run_synthetic_benchmark:")
            and command.get("command_kind") == "analysis"
            for command in run_result["commands"]
        )
        if scenario.get("category") == "code_fix_branch":
            actual_command_recorded = any(str(command.get("command")) == "mock:fail" for command in run_result["commands"])

    items = [
        _item("input_understood", bool(method_plan), "method_plan.json exists."),
        _item("method_plan_written", bool(method_plan and method_plan.get("run_id") == state.get("run_id")), "Method plan belongs to this run."),
        _item(
            "analysis_engineer_consumed_scenario_data",
            bool(scenario_copy and scenario_copy.get("case_id") == scenario.get("case_id"))
            or scenario.get("category") in {"code_fix_branch", "missing_input"},
            "Scenario input was copied into analysis outputs.",
        ),
        _item(
            "analysis_command_recorded",
            actual_command_recorded or scenario.get("category") == "missing_input",
            "Run result records the synthetic benchmark command, unless the scenario stops before analysis.",
        ),
        _item(
            "case_specific_fit_summary_produced",
            bool(fit_summary and fit_summary.get("scenario_id") == scenario.get("case_id"))
            or scenario.get("category") in {"code_fix_branch", "missing_input"},
            "fit_summary.json is case-specific when analysis reaches fitting.",
        ),
        _item(
            "reviewer_findings_grounded",
            bool(review and isinstance(review.get("evidence"), list) and review.get("evidence"))
            or "scientific_reviewer" not in expected_route,
            "Scientific review includes structured evidence when expected.",
        ),
        _item(
            "decision_reasons_structured",
            bool(decision and isinstance(decision.get("reasons"), list))
            or "decision_coordinator" not in expected_route,
            "Decision log contains structured reasons when expected.",
        ),
        _item(
            "expected_conclusion_observed",
            state.get("risk_level") == expected.get("expected_risk_level")
            and state.get("recommended_action") == expected.get("expected_recommended_action")
            and bool(state.get("human_approval_required")) == bool(expected.get("expected_human_approval_required"))
            and rerun_passed
            and numeric_passed,
            "Risk/action/gate/rerun/numeric checks match expected behavior.",
        ),
        _item("expected_route_observed", route_passed, f"Observed route nodes: {route_nodes}."),
        _item("review_warning_expectations_observed", warnings_passed, f"Warnings: {warning_codes}; values: {warning_values}."),
        _item(
            "human_gate_behavior_correct",
            approval_packet == bool(expected.get("expected_approval_packet")),
            f"approval_packet={approval_packet}.",
        ),
        _item(
            "memory_status_correct",
            memory_status == str(expected.get("expected_memory_status")),
            f"memory_status={memory_status}.",
        ),
        _item(
            "final_report_coherent",
            (final_report_path.exists() or scenario.get("category") == "code_fix_branch")
            and str(expected.get("hidden_expected_conclusion_summary")) not in final_report,
            "Final report exists when expected and does not expose hidden expected notes.",
        ),
    ]
    passed = all(item["passed"] for item in items)
    return {
        "schema_version": "0.1",
        "created_at": utc_now(),
        "case_id": scenario["case_id"],
        "scenario_goal": scenario["goal"],
        "passed": passed,
        "review_needed": not passed,
        "actual": {
            "risk_level": state.get("risk_level"),
            "recommended_action": state.get("recommended_action"),
            "human_approval_required": state.get("human_approval_required"),
            "rerun_requested": state.get("rerun_requested"),
            "rerun_target": state.get("rerun_target"),
            "memory_status": memory_status,
            "approval_packet": approval_packet,
            "route_nodes": route_nodes,
            "warning_codes": warning_codes,
            "warning_values": warning_values,
            "numeric_failures": numeric_failures,
        },
        "expected": {
            "qualitative_conclusion": expected.get("expected_qualitative_conclusion"),
            "risk_level": expected.get("expected_risk_level"),
            "recommended_action": expected.get("expected_recommended_action"),
            "human_approval_required": expected.get("expected_human_approval_required"),
            "memory_status": expected.get("expected_memory_status"),
            "approval_packet": expected.get("expected_approval_packet"),
            "route_contains": expected.get("expected_route_contains"),
        },
        "items": items,
        "artifact_paths": {
            "method_plan": state.get("method_plan_path"),
            "run_result": state.get("run_result_path"),
            "fit_summary": str(run_dir / "analysis_outputs" / "fit_summary.json"),
            "scientific_review": state.get("scientific_review_report_path"),
            "decision_log": state.get("decision_log_path"),
            "memory_update": state.get("memory_update_path"),
            "final_report": state.get("final_report_path"),
            "checklist": str(run_dir / "demonstration_checklist.json"),
        },
    }


def write_checklist(run_dir: Path, checklist: dict[str, Any]) -> Path:
    path = run_dir / "demonstration_checklist.json"
    path.write_text(json.dumps(checklist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_case(
    *,
    scenario: dict[str, Any],
    expected: dict[str, Any],
    output_dir: str | Path,
    run_id_prefix: str,
    provider_config_path: str | Path,
    force_clean: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    case_id = str(scenario["case_id"])
    run_id = f"{run_id_prefix}_{case_id}"
    run_dir = output_root / case_id / run_id
    if run_dir.exists() and force_clean:
        shutil.rmtree(run_dir)
    case_config = _write_case_config(scenario=scenario, output_dir=output_root)
    result = run_mock_graph(
        case_path=str(case_config),
        output_dir=str(output_root),
        run_id=run_id,
        llm_provider_config_path=str(provider_config_path),
    )
    state = result["state"]
    checklist = build_checklist(scenario=scenario, expected=expected, state=state, run_dir=run_dir)
    checklist_path = write_checklist(run_dir, checklist)
    checklist["artifact_paths"]["checklist"] = str(checklist_path)
    return {"scenario": scenario, "expected": expected, "state": state, "checklist": checklist, "run_dir": str(run_dir)}


def _key_fit_result(run_dir: Path) -> str:
    fit = _read_json_object(run_dir / "analysis_outputs" / "fit_summary.json")
    if not fit:
        return "fit unavailable"
    mass = _fit_mass(fit)
    reduced_chi2 = fit.get("reduced_chi2")
    return f"mass={mass:.4f}, reduced_chi2={reduced_chi2:.3f}" if isinstance(mass, float) and isinstance(reduced_chi2, (int, float)) else "fit summary written"


def write_rehearsal_summary(*, output_dir: str | Path, rows: list[dict[str, Any]]) -> Path:
    path = Path(output_dir) / "synthetic_rehearsal_summary.md"
    lines = [
        "# Phase 10C Synthetic Rehearsal Summary",
        "",
        f"- created_at: {utc_now()}",
        f"- case_count: {len(rows)}",
        f"- passed_checklists: {sum(1 for row in rows if row['checklist']['passed'])}",
        "",
    ]
    for row in rows:
        checklist = row["checklist"]
        actual = checklist["actual"]
        artifacts = checklist["artifact_paths"]
        run_dir = Path(row["run_dir"])
        lines.extend(
            [
                f"## {checklist['case_id']}",
                f"- scenario_goal: {checklist['scenario_goal']}",
                f"- route_path: {', '.join(actual['route_nodes'])}",
                f"- key_fit_result: {_key_fit_result(run_dir)}",
                f"- reviewer_warnings: {', '.join(actual['warning_codes']) or 'none'}",
                f"- decision: risk={actual['risk_level']}, action={actual['recommended_action']}",
                f"- memory_status: {actual['memory_status']}",
                f"- checklist_status: {'passed' if checklist['passed'] else 'review-needed'}",
                f"- actual_vs_expected: {checklist['expected']['qualitative_conclusion']}",
                f"- artifacts: {artifacts}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_advisor_demo_report(*, output_dir: str | Path, rows: list[dict[str, Any]]) -> Path:
    path = Path(output_dir) / "advisor_demo_report.md"
    lines = [
        "# Advisor Demo Report",
        "",
        f"- created_at: {utc_now()}",
        "",
    ]
    for row in rows:
        scenario = row["scenario"]
        expected = row["expected"]
        checklist = row["checklist"]
        actual = checklist["actual"]
        artifacts = checklist["artifact_paths"]
        lines.extend(
            [
                f"## {scenario['case_id']}",
                f"- scenario_question: {scenario['goal']}",
                f"- hidden_expected_conclusion_summary: {expected.get('hidden_expected_conclusion_summary')}",
                f"- actual_agent_conclusion: risk={actual['risk_level']}, action={actual['recommended_action']}, memory={actual['memory_status']}",
                f"- expected_route: {', '.join(expected.get('expected_route_contains', []))}",
                f"- actual_route: {', '.join(actual['route_nodes'])}",
                f"- expected_risk_action: risk={expected.get('expected_risk_level')}, action={expected.get('expected_recommended_action')}",
                f"- actual_risk_action: risk={actual['risk_level']}, action={actual['recommended_action']}",
                f"- status: {'pass' if checklist['passed'] else 'review-needed'}",
                f"- artifact_links: {artifacts}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_benchmarks(
    *,
    case_set: str,
    output_dir: str | Path,
    provider: str | None = "mock",
    provider_config: str | Path | None = None,
    run_id_prefix: str | None = None,
    force_clean: bool = False,
) -> dict[str, Any]:
    if provider_config is not None:
        if os.environ.get("RUN_LIVE_LLM_TESTS") != "1":
            raise RuntimeError("Live-provider rehearsal requires RUN_LIVE_LLM_TESTS=1.")
        provider_config_path = Path(provider_config)
        live_mode = True
    elif provider == "mock":
        provider_config_path = MOCK_PROVIDER_CONFIG
        live_mode = False
    else:
        raise ValueError("Use --provider mock or --provider-config PATH.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    prefix = run_id_prefix or _timestamp_prefix()
    rows = [
        run_case(
            scenario=case["scenario"],
            expected=case["expected"],
            output_dir=output_path,
            run_id_prefix=prefix,
            provider_config_path=provider_config_path,
            force_clean=force_clean,
        )
        for case in load_case_set(case_set)
    ]
    summary_path = write_rehearsal_summary(output_dir=output_path, rows=rows)
    advisor_report_path = write_advisor_demo_report(output_dir=output_path, rows=rows) if live_mode else None
    return {
        "passed": all(row["checklist"]["passed"] for row in rows),
        "case_count": len(rows),
        "rows": rows,
        "summary_path": str(summary_path),
        "advisor_demo_report_path": str(advisor_report_path) if advisor_report_path else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 10C synthetic advisor-demo benchmarks.")
    parser.add_argument("--provider", choices=["mock"], default=None)
    parser.add_argument("--provider-config", default=None)
    parser.add_argument("--case-set", choices=["demo", "full"], required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id-prefix", default=None)
    parser.add_argument("--force-clean", action="store_true")
    args = parser.parse_args()
    try:
        result = run_benchmarks(
            case_set=args.case_set,
            output_dir=args.output_dir,
            provider=args.provider,
            provider_config=args.provider_config,
            run_id_prefix=args.run_id_prefix,
            force_clean=args.force_clean,
        )
    except (FileExistsError, RuntimeError, ValueError) as exc:
        parser.exit(status=2, message=f"error: {exc}\n")
    print(f"passed={result['passed']}")
    print(f"case_count={result['case_count']}")
    print(f"synthetic_rehearsal_summary={result['summary_path']}")
    if result["advisor_demo_report_path"]:
        print(f"advisor_demo_report={result['advisor_demo_report_path']}")


if __name__ == "__main__":
    main()
