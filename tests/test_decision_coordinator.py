import json
from pathlib import Path

from lqcd_agent.agents.decision_coordinator import run_decision_coordinator
from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse
from lqcd_agent.llm.mock_provider import MockLLMProvider


class StaticProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.config = LLMProviderConfig(schema_version="0.1", provider="static", dry_run_only=True)

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(provider="static", model="static", content=self.content)


def _method_plan(*, run_id: str = "run_a", case_id: str = "case_a") -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "method_planner",
        "status": "success",
        "summary": "Method plan is usable.",
        "warnings": [],
        "errors": [],
        "code_needed": False,
    }


def _run_result(*, run_id: str = "run_a", case_id: str = "case_a") -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "analysis_engineer",
        "status": "success",
        "summary": "Run succeeded.",
        "warnings": [],
        "errors": [],
        "run_success": True,
        "failure_type": None,
        "analysis_outputs_dir": "analysis_outputs",
        "produced_outputs": ["analysis_outputs/synthetic_matrix_elements.json"],
    }


def _review_report(*, run_id: str = "run_a", case_id: str = "case_a") -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "scientific_reviewer",
        "status": "success",
        "summary": "Review passed.",
        "warnings": [],
        "errors": [],
        "findings": [{"code": "matrix_elements_checked"}],
        "evidence": [{"path": "analysis_outputs/synthetic_matrix_elements.json", "field": "matrix_elements", "value": "checked"}],
        "recommended_checks": [],
        "confidence": "high",
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_artifacts(
    tmp_path: Path,
    *,
    method_plan: dict[str, object] | None = None,
    run_result: dict[str, object] | None = None,
    review_report: dict[str, object] | None = None,
) -> tuple[Path, Path, Path]:
    method_path = _write_json(tmp_path / "method_plan.json", method_plan or _method_plan())
    run_path = _write_json(tmp_path / "run_result.json", run_result or _run_result())
    review_path = _write_json(tmp_path / "scientific_review_report.json", review_report or _review_report())
    return method_path, run_path, review_path


def _run_decision(tmp_path: Path, *, method_path: Path, run_path: Path, review_path: Path) -> dict[str, object]:
    return run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
    )["decision_log"]


def _assert_one_primary_next_action(decision_log: dict[str, object]) -> None:
    next_actions = decision_log["next_actions"]
    assert isinstance(next_actions, list)
    assert sum(1 for action in next_actions if action["primary"] is True) == 1


def test_low_risk_accepts_mock_result_with_structured_evidence(tmp_path: Path) -> None:
    method_path, run_path, review_path = _write_artifacts(tmp_path)

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "success"
    assert decision_log["risk_level"] == "low"
    assert decision_log["recommended_action"] == "accept_mock_result"
    assert decision_log["human_approval_required"] is False
    assert decision_log["routing_decision"]["actual_route"] == "memory_report"
    assert decision_log["routing_decision"]["fields"]["rerun_requested"] is False
    assert decision_log["routing_decision"]["fields"]["code_fix_requested"] is False
    assert (tmp_path / "decision_log.json").exists()
    _assert_one_primary_next_action(decision_log)


def test_advisory_normalization_warning_does_not_raise_risk(tmp_path: Path) -> None:
    review = _review_report()
    review["warnings"] = [
        {
            "section": "method_plan",
            "code": "selected_analysis_programs_normalized",
            "severity": "info",
            "decision_coordinator_flag": False,
            "message": "Provider selected registered analysis program(s), and runtime normalized mappings.",
            "programs": ["single_exponential_effective_mass"],
            "changed_fields": [
                {
                    "name": "single_exponential_effective_mass",
                    "changed_fields": ["input_mapping"],
                }
            ],
        }
    ]
    review["evidence"].append(
        {
            "source": "method_plan_advisory",
            "code": "selected_analysis_programs_normalized",
            "severity": "info",
            "decision_coordinator_flag": False,
        }
    )
    review["confidence"] = "high"
    method_path, run_path, review_path = _write_artifacts(tmp_path, review_report=review)

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "success"
    assert decision_log["risk_level"] == "low"
    assert decision_log["recommended_action"] == "accept_mock_result"
    assert decision_log["human_approval_required"] is False
    _assert_one_primary_next_action(decision_log)


def test_medium_risk_is_pending_and_human_review_recommended(tmp_path: Path) -> None:
    review = _review_report()
    review["warnings"] = [
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
    ]
    review["confidence"] = "medium"
    method_path, run_path, review_path = _write_artifacts(tmp_path, review_report=review)

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "pending"
    assert decision_log["risk_level"] == "medium"
    assert decision_log["recommended_action"] == "human_review_recommended"
    assert decision_log["human_approval_required"] is False
    assert decision_log["routing_decision"]["actual_route"] == "memory_report"
    assert decision_log["routing_decision"]["requested_route"] == "memory_report"
    _assert_one_primary_next_action(decision_log)


def test_high_risk_severe_warning_requires_human_approval(tmp_path: Path) -> None:
    review = _review_report()
    review["warnings"] = [
        {
            "section": "matrix_element_diagnostics",
            "code": "non_positive_error",
            "severity": "severe",
            "decision_coordinator_flag": True,
            "message": "Matrix-element error must be positive.",
            "path": "analysis_outputs/synthetic_matrix_elements.json",
            "field": "matrix_elements[0].error",
            "value": -0.01,
        }
    ]
    review["confidence"] = "low"
    method_path, run_path, review_path = _write_artifacts(tmp_path, review_report=review)

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "pending"
    assert decision_log["risk_level"] == "high"
    assert decision_log["recommended_action"] == "pending_human_approval"
    assert decision_log["human_approval_required"] is True
    assert decision_log["routing_decision"]["actual_route"] == "human_approval_gate"
    assert decision_log["routing_decision"]["requested_route"] == "human_approval_gate"
    _assert_one_primary_next_action(decision_log)


def test_critical_risk_for_missing_required_review_artifact(tmp_path: Path) -> None:
    method_path = _write_json(tmp_path / "method_plan.json", _method_plan())
    run_path = _write_json(tmp_path / "run_result.json", _run_result())
    review_path = tmp_path / "missing_scientific_review_report.json"

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "pending"
    assert decision_log["risk_level"] == "critical"
    assert decision_log["recommended_action"] == "pending_human_approval"
    assert decision_log["human_approval_required"] is True
    assert decision_log["errors"]
    assert decision_log["routing_decision"]["actual_route"] == "human_approval_gate"
    assert decision_log["routing_decision"]["requested_route"] == "human_approval_gate"
    _assert_one_primary_next_action(decision_log)


def test_config_or_data_failure_does_not_require_scientific_review_artifact(tmp_path: Path) -> None:
    run_result = _run_result()
    run_result.update(
        {
            "status": "failed",
            "summary": "Analysis Engineer recorded a failed analysis run.",
            "run_success": False,
            "failure_type": "config_or_data",
            "errors": [
                {
                    "field": "analysis_commands",
                    "message": "raw_data_path does not exist or is not a file.",
                    "command_id": "analysis_program_0",
                    "status": "blocked",
                    "return_code": None,
                }
            ],
        }
    )
    method_path = _write_json(tmp_path / "method_plan.json", _method_plan())
    run_path = _write_json(tmp_path / "run_result.json", run_result)
    review_path = tmp_path / "missing_scientific_review_report.json"

    decision_log = _run_decision(tmp_path, method_path=method_path, run_path=run_path, review_path=review_path)

    assert decision_log["status"] == "pending"
    assert decision_log["risk_level"] == "critical"
    assert decision_log["recommended_action"] == "pending_human_approval"
    assert decision_log["human_approval_required"] is True
    assert decision_log["routing_decision"]["actual_route"] == "human_approval_gate"
    assert decision_log["routing_decision"]["fields"]["rerun_requested"] is False
    assert decision_log["routing_decision"]["fields"]["code_fix_requested"] is False
    assert decision_log["errors"] == []
    assert {reason["code"] for reason in decision_log["reasons"]} == {
        "config_or_data_failure",
        "missing_required_input",
    }


def test_provider_backed_decision_coordinator_accepts_valid_mock_output(tmp_path: Path) -> None:
    method_path, run_path, review_path = _write_artifacts(tmp_path)

    result = run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
        provider=MockLLMProvider(),
    )
    decision_log = result["decision_log"]

    assert result["status"] == "success"
    assert decision_log["producer"] == "decision_coordinator"
    assert decision_log["risk_level"] == "low"
    assert decision_log["routing_decision"]["actual_route"] == "memory_report"
    trace = json.loads((tmp_path / "llm_calls" / "decision_coordinator.json").read_text(encoding="utf-8"))
    assert trace["agent"] == "decision_coordinator"
    assert trace["provider"]["provider"] == "mock"
    assert trace["parsed_payload_path"] == str(tmp_path / "decision_log.json")
    assert trace["response"]["content"]
    _assert_one_primary_next_action(decision_log)


def test_invalid_provider_decision_output_cannot_force_low_risk_route(tmp_path: Path) -> None:
    method_path, run_path, review_path = _write_artifacts(tmp_path)

    result = run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
        provider=StaticProvider('{"risk_level": "low", "recommended_action": "accept_mock_result"}'),
    )
    decision_log = result["decision_log"]

    assert result["status"] == "pending"
    assert decision_log["risk_level"] == "critical"
    assert decision_log["human_approval_required"] is True
    assert decision_log["routing_decision"]["actual_route"] == "human_approval_gate"
    assert decision_log["errors"][0]["code"] == "provider_schema_error"


def test_provider_decision_cannot_lower_severe_review_floor(tmp_path: Path) -> None:
    review = _review_report()
    review["warnings"] = [
        {
            "section": "matrix_element",
            "code": "upstream_diagnostic_flag",
            "severity": "severe",
            "decision_coordinator_flag": True,
            "message": "Severe diagnostic flag requires human approval.",
            "path": "analysis_outputs/synthetic_matrix_elements.json",
            "field": "diagnostic_flags[0]",
            "value": "severe_demo_requires_human_approval",
        }
    ]
    review["confidence"] = "low"
    method_path, run_path, review_path = _write_artifacts(tmp_path, review_report=review)
    provider_low_decision = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "decision_coordinator",
        "status": "success",
        "summary": "Provider tried to classify the run as low risk.",
        "warnings": [],
        "errors": [],
        "risk_level": "low",
        "recommended_action": "accept_mock_result",
        "human_approval_required": False,
        "reasons": [{"code": "provider_low", "message": "Provider proposed low risk."}],
        "evidence": [],
        "next_actions": [
            {
                "action": "accept_mock_result",
                "primary": True,
                "target": "memory_report",
                "status": "ready",
            }
        ],
        "routing_decision": {
            "actual_route": "memory_report",
            "requested_route": "memory_report",
            "proposed_follow_up_route": "memory_report",
            "fields": {
                "risk_level": "low",
                "recommended_action": "accept_mock_result",
                "human_approval_required": False,
                "rerun_requested": False,
                "rerun_target": None,
                "code_fix_requested": False,
            },
        },
    }

    result = run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
        provider=StaticProvider(json.dumps(provider_low_decision)),
    )
    decision_log = result["decision_log"]

    assert result["status"] == "pending"
    assert decision_log["risk_level"] == "high"
    assert decision_log["human_approval_required"] is True
    assert decision_log["routing_decision"]["actual_route"] == "human_approval_gate"
    assert decision_log["reasons"][0]["code"] == "provider_safety_floor"


def test_provider_decision_cannot_raise_nonsevere_warning_to_human_gate(tmp_path: Path) -> None:
    review = _review_report()
    review["warnings"] = [
        {
            "section": "matrix_element",
            "code": "upstream_diagnostic_flag",
            "severity": "warning",
            "decision_coordinator_flag": False,
            "message": "Non-severe fit-window dependence requires review but not Human Gate.",
            "path": "analysis_outputs/synthetic_matrix_elements.json",
            "field": "diagnostic_flags[0]",
            "value": "fit_window_dependence",
        }
    ]
    method_path, run_path, review_path = _write_artifacts(tmp_path, review_report=review)
    provider_high_decision = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "decision_coordinator",
        "status": "pending",
        "summary": "Provider over-routes a non-severe warning.",
        "warnings": [],
        "errors": [],
        "risk_level": "high",
        "recommended_action": "pending_human_approval",
        "human_approval_required": True,
        "reasons": [{"code": "provider_high", "message": "Provider requests Human Gate."}],
        "evidence": [],
        "next_actions": [{"action": "pending_human_approval", "primary": True, "target": "human_approval_gate"}],
        "routing_decision": {
            "actual_route": "human_approval_gate",
            "requested_route": "human_approval_gate",
            "proposed_follow_up_route": "memory_report",
            "fields": {
                "risk_level": "high",
                "human_approval_required": True,
                "rerun_requested": False,
                "rerun_target": None,
                "code_fix_requested": False,
            },
        },
    }

    result = run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
        provider=StaticProvider(json.dumps(provider_high_decision)),
    )
    decision_log = result["decision_log"]

    assert decision_log["risk_level"] == "medium"
    assert decision_log["recommended_action"] == "human_review_recommended"
    assert decision_log["human_approval_required"] is False
    assert decision_log["reasons"][0]["code"] == "provider_unsupported_human_gate"


def test_provider_decision_route_fields_are_normalized(tmp_path: Path) -> None:
    method_path, run_path, review_path = _write_artifacts(tmp_path)
    payload = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "decision_coordinator",
        "status": "success",
        "summary": "Provider low-risk decision with inconsistent route fields.",
        "warnings": [],
        "errors": [],
        "risk_level": "low",
        "recommended_action": "accept_mock_result",
        "human_approval_required": False,
        "reasons": [{"code": "low", "message": "Low risk."}],
        "evidence": [],
        "next_actions": [{"action": "accept_mock_result", "primary": True, "target": "memory_report"}],
        "routing_decision": {
            "actual_route": "memory_report",
            "requested_route": "memory_report",
            "proposed_follow_up_route": "memory_report",
            "fields": {
                "risk_level": "medium",
                "human_approval_required": True,
                "rerun_requested": False,
                "rerun_target": None,
                "code_fix_requested": False,
            },
        },
    }

    result = run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
        provider=StaticProvider(json.dumps(payload)),
    )
    decision_log = result["decision_log"]

    assert result["status"] == "success"
    assert decision_log["routing_decision"]["fields"]["risk_level"] == "low"
    assert decision_log["routing_decision"]["fields"]["human_approval_required"] is False


def test_provider_medium_approval_action_normalizes_to_human_review(tmp_path: Path) -> None:
    method_path, run_path, review_path = _write_artifacts(tmp_path)
    payload = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "decision_coordinator",
        "status": "pending",
        "summary": "Provider requests pending human approval for a medium-risk case.",
        "warnings": [],
        "errors": [],
        "risk_level": "medium",
        "recommended_action": "pending_human_approval",
        "human_approval_required": False,
        "reasons": [{"code": "medium", "message": "Medium risk."}],
        "evidence": [],
        "next_actions": [{"action": "pending_human_approval", "primary": True, "target": "memory_report"}],
        "routing_decision": {
            "actual_route": "memory_report",
            "requested_route": "memory_report",
            "proposed_follow_up_route": "memory_report",
            "fields": {
                "risk_level": "medium",
                "human_approval_required": False,
                "rerun_requested": False,
                "rerun_target": None,
                "code_fix_requested": False,
            },
        },
    }

    result = run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
        provider=StaticProvider(json.dumps(payload)),
    )

    assert result["decision_log"]["recommended_action"] == "human_review_recommended"


def test_provider_targeted_rerun_target_is_canonical(tmp_path: Path) -> None:
    method_path, run_path, review_path = _write_artifacts(tmp_path)
    payload = {
        "schema_version": "0.1",
        "run_id": "run_a",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "decision_coordinator",
        "status": "pending",
        "summary": "Provider requests a targeted rerun of an artifact.",
        "warnings": [],
        "errors": [],
        "risk_level": "medium",
        "recommended_action": "targeted rerun",
        "human_approval_required": False,
        "reasons": [{"code": "targeted_rerun", "message": "Targeted rerun requested."}],
        "evidence": [],
        "next_actions": [{"action": "targeted_rerun", "primary": True, "target": "analysis_outputs/result.json"}],
        "routing_decision": {
            "actual_route": "memory_report",
            "requested_route": "memory_report",
            "proposed_follow_up_route": "memory_report",
            "fields": {
                "risk_level": "medium",
                "human_approval_required": False,
                "rerun_requested": False,
                "rerun_target": "analysis_outputs/result.json",
                "code_fix_requested": False,
            },
        },
    }

    result = run_decision_coordinator(
        run_id="run_a",
        case_id="case_a",
        output_dir=tmp_path,
        method_plan_path=method_path,
        run_result_path=run_path,
        scientific_review_report_path=review_path,
        provider=StaticProvider(json.dumps(payload)),
    )

    assert result["recommended_action"] == "targeted_rerun"
    assert result["rerun_requested"] is True
    assert result["rerun_target"] == "analysis_engineer"
