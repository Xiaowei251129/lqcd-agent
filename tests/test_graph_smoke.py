import json
import re
import subprocess
import sys
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
import pytest

from lqcd_agent.graph.analysis_graph import compile_analysis_graph
from lqcd_agent.graph.run_graph import run_mock_graph
from lqcd_agent.graph.state import initialize_state
from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse


class StaticProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.config = LLMProviderConfig(schema_version="0.1", provider="static", dry_run_only=True)

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(provider="static", model="static", content=self.content)


def _assert_current_file(state: dict, field: str, run_dir: Path, relative_path: str) -> None:
    canonical = Path(state[field])
    assert canonical == run_dir / "attempts" / canonical.parent.name / relative_path
    assert canonical.read_bytes() == (run_dir / relative_path).read_bytes()


def _assert_current_directory(state: dict, field: str, run_dir: Path, relative_path: str) -> None:
    canonical = Path(state[field])
    assert canonical == run_dir / "attempts" / canonical.parent.name / relative_path
    projection = run_dir / relative_path
    members = sorted(path.relative_to(canonical) for path in canonical.rglob("*") if path.is_file())
    assert members == sorted(path.relative_to(projection) for path in projection.rglob("*") if path.is_file())
    assert all((canonical / member).read_bytes() == (projection / member).read_bytes() for member in members)


def test_run_mock_graph_generates_timestamp_run_id(tmp_path: Path) -> None:
    result = run_mock_graph(
        case_path="configs/cases/mock_lqcd_goal.yaml",
        output_dir=str(tmp_path),
    )
    state = result["state"]

    assert re.fullmatch(r"run_\d{8}_\d{6}", state["run_id"])
    assert Path(state["output_dir"]).name == state["run_id"]
    assert Path(state["decision_log_path"]).exists()


def test_run_mock_graph_refuses_reused_completed_run_id(tmp_path: Path) -> None:
    result = run_mock_graph(
        case_path="configs/cases/mock_lqcd_goal.yaml",
        output_dir=str(tmp_path),
        run_id="reuse_guard",
    )
    decision_log_path = Path(result["state"]["decision_log_path"])
    original_decision_log = decision_log_path.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError, match="Choose a new --run-id"):
        run_mock_graph(
            case_path="configs/cases/mock_lqcd_goal.yaml",
            output_dir=str(tmp_path),
            run_id="reuse_guard",
        )

    assert decision_log_path.read_text(encoding="utf-8") == original_decision_log


def test_run_mock_graph_accepts_mock_provider_config(tmp_path: Path) -> None:
    result = run_mock_graph(
        case_path="configs/cases/mock_lqcd_goal.yaml",
        output_dir=str(tmp_path),
        run_id="provider_mock",
        llm_provider_config_path="configs/runtime/mock_llm.yaml",
    )
    state = result["state"]
    run_dir = tmp_path / "mock_lqcd_goal" / "provider_mock"
    method_plan = json.loads((run_dir / "method_plan.json").read_text(encoding="utf-8"))
    decision_log = json.loads((run_dir / "decision_log.json").read_text(encoding="utf-8"))

    assert state["status"] == "success"
    assert state["llm_provider_config_path"] == "configs/runtime/mock_llm.yaml"
    assert method_plan["summary"].startswith("Provider-backed mock")
    assert decision_log["summary"].startswith("Provider-backed mock")
    assert decision_log["routing_decision"]["actual_route"] == "memory_report"


def test_graph_invalid_provider_output_stops_safely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lqcd_agent.agents.method_planner.create_provider_from_config_path",
        lambda path: StaticProvider('{"status": "success", "free_text_route": "analysis_engineer"}'),
    )
    run_dir = tmp_path / "mock_lqcd_goal" / "invalid_provider"
    state = initialize_state(
        case_id="mock_lqcd_goal",
        run_id="invalid_provider",
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path="configs/cases/mock_lqcd_goal.yaml",
        output_dir=str(run_dir),
        checkpoint_backend="memory",
        llm_provider_config_path="invalid-provider.yaml",
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(MemorySaver())

    final_state = app.invoke(state, config=config)
    method_plan = json.loads((run_dir / "method_plan.json").read_text(encoding="utf-8"))

    assert final_state["status"] == "halted"
    assert final_state["current_node"] == "method_planner"
    assert final_state["route_decisions"][-1]["route"] == "end"
    assert method_plan["status"] == "failed"
    assert method_plan["errors"][0]["code"] == "provider_schema_error"


def test_cli_accepts_mock_provider_config(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lqcd_agent.graph.run_graph",
            "--case",
            "configs/cases/mock_lqcd_goal.yaml",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "cli_provider_mock",
            "--llm-provider-config",
            "configs/runtime/mock_llm.yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "status=success" in result.stdout
    decision_log = json.loads(
        (tmp_path / "mock_lqcd_goal" / "cli_provider_mock" / "decision_log.json").read_text(encoding="utf-8")
    )
    assert decision_log["summary"].startswith("Provider-backed mock")


def test_mock_graph_runs_to_end_and_checkpoint_can_be_inspected(tmp_path: Path) -> None:
    run_dir = tmp_path / "mock_lqcd_goal" / "smoke"
    checkpointer = MemorySaver()
    state = initialize_state(
        case_id="mock_lqcd_goal",
        run_id="smoke",
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path="configs/cases/mock_lqcd_goal.yaml",
        output_dir=str(run_dir),
        checkpoint_backend="memory",
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(checkpointer)

    final_state = app.invoke(state, config=config)
    checkpoints = list(checkpointer.list(config))
    graph_state = json.loads((run_dir / "graph_state.json").read_text(encoding="utf-8"))

    assert final_state["status"] == "success"
    assert final_state["final_report_path"]
    assert "## Method Plan" in Path(final_state["final_report_path"]).read_text(encoding="utf-8")
    assert checkpoints
    assert graph_state["checkpoint_backend"] == "memory"
    assert graph_state["checkpoint_thread_id"] == "mock_lqcd_goal:smoke"
    assert graph_state["route_decisions"]
    assert graph_state["checkpoint_db_path"] is None
    _assert_current_file(final_state, "run_result_path", run_dir, "run_result.json")
    assert (run_dir / "manifest.json").exists()
    _assert_current_file(
        final_state,
        "scientific_review_report_path",
        run_dir,
        "scientific_review_report.json",
    )
    _assert_current_file(final_state, "decision_log_path", run_dir, "decision_log.json")
    memory_update = json.loads((run_dir / "memory_update.json").read_text(encoding="utf-8"))
    decision_log = json.loads((run_dir / "decision_log.json").read_text(encoding="utf-8"))
    assert memory_update["memory_status"] == "accepted"
    assert memory_update["accepted_result"] is True
    assert decision_log["risk_level"] == "low"
    assert decision_log["recommended_action"] == "accept_mock_result"
    review_report = json.loads((run_dir / "scientific_review_report.json").read_text(encoding="utf-8"))
    for field in [
        "correlator_diagnostics",
        "fit_diagnostics",
        "matrix_element_diagnostics",
        "findings",
        "evidence",
        "warnings",
        "recommended_checks",
        "confidence",
    ]:
        assert field in review_report
    assert review_report["matrix_element_diagnostics"]["status"] == "pass"


def _review_report(
    *,
    run_id: str,
    case_id: str,
    warnings: list[dict[str, object]],
    confidence: str,
) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "scientific_reviewer",
        "status": "success",
        "summary": "Fake review report for graph smoke risk routing.",
        "warnings": warnings,
        "errors": [],
        "correlator_diagnostics": {"status": "not_populated_mvp"},
        "fit_diagnostics": {"status": "not_populated_mvp"},
        "matrix_element_diagnostics": {"status": "pass"},
        "findings": [{"code": "matrix_elements_checked"}],
        "evidence": [{"path": "analysis_outputs/synthetic_matrix_elements.json", "field": "matrix_elements", "value": "checked"}],
        "recommended_checks": [],
        "confidence": confidence,
    }


def _run_graph_with_fake_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    report: dict[str, object],
    write_report: bool = True,
):
    run_dir = tmp_path / str(report["case_id"]) / str(report["run_id"])

    def fake_review(**kwargs):
        report_path = Path(kwargs["run_output_dir"]) / "scientific_review_report.json"
        if write_report:
            report_path.write_text(json.dumps(report), encoding="utf-8")
        return {
            "status": "success",
            "report_path": str(report_path),
            "scientific_review_report_path": str(report_path),
            "report": report,
            "warnings": report["warnings"],
            "errors": [],
            "confidence": report["confidence"],
        }

    monkeypatch.setattr("lqcd_agent.graph.nodes.run_scientific_reviewer", fake_review)
    checkpointer = MemorySaver()
    state = initialize_state(
        case_id=str(report["case_id"]),
        run_id=str(report["run_id"]),
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path="configs/cases/mock_lqcd_goal.yaml",
        output_dir=str(run_dir),
        checkpoint_backend="memory",
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(checkpointer)
    return app.invoke(state, config=config), run_dir


def test_medium_risk_graph_writes_pending_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _review_report(
        run_id="medium",
        case_id="mock_lqcd_goal",
        warnings=[
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
        ],
        confidence="medium",
    )

    final_state, run_dir = _run_graph_with_fake_review(tmp_path, monkeypatch, report=report)
    memory_update = json.loads((run_dir / "memory_update.json").read_text(encoding="utf-8"))

    assert final_state["status"] == "pending"
    assert final_state["risk_level"] == "medium"
    assert final_state["recommended_action"] == "human_review_recommended"
    assert final_state["human_approval_required"] is False
    assert not (run_dir / "approval_packet").exists()
    assert memory_update["memory_status"] == "pending"
    assert memory_update["accepted_result"] is False


def test_high_risk_graph_cannot_enter_accepted_memory_without_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _review_report(
        run_id="high",
        case_id="mock_lqcd_goal",
        warnings=[
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
        ],
        confidence="low",
    )

    final_state, run_dir = _run_graph_with_fake_review(tmp_path, monkeypatch, report=report)
    human_transition = next(
        decision
        for decision in final_state["route_decisions"]
        if decision["source"] == "human_approval_gate"
    )
    route_fields = human_transition["fields"]

    assert final_state["status"] == "pending"
    assert final_state["current_node"] == "memory_report"
    assert final_state["risk_level"] == "high"
    assert final_state["human_approval_required"] is True
    _assert_current_directory(final_state, "approval_packet_dir", run_dir, "approval_packet")
    assert (run_dir / "approval_packet" / "approval_packet.json").exists()
    assert (run_dir / "approval_packet" / "07_human_decision.yaml").exists()
    assert (run_dir / "final_report.md").exists()
    memory_update = json.loads((run_dir / "memory_update.json").read_text(encoding="utf-8"))
    assert memory_update["memory_status"] == "pending"
    assert memory_update["accepted_result"] is False
    assert route_fields["actual_route"] == "memory_report"
    assert route_fields["requested_route"] == "human_approval_gate"
    assert final_state["active_human_request_id"] == "human_request_000001"
    history = [
        json.loads(line)
        for line in Path(final_state["execution_history_path"]).read_text(encoding="utf-8").splitlines()
    ]
    request_position = next(
        index for index, record in enumerate(history) if record["record_type"] == "human_request"
    )
    gate_position = next(
        index
        for index, record in enumerate(history)
        if record["record_type"] == "attempt"
        and record.get("attempt_kind") == "human_gate"
        and record["event"] == "scheduled"
    )
    assert request_position < gate_position


def test_critical_risk_graph_cannot_enter_accepted_memory_without_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _review_report(
        run_id="critical",
        case_id="mock_lqcd_goal",
        warnings=[],
        confidence="high",
    )

    final_state, run_dir = _run_graph_with_fake_review(
        tmp_path,
        monkeypatch,
        report=report,
        write_report=False,
    )

    assert final_state["status"] == "pending"
    assert final_state["current_node"] == "memory_report"
    assert final_state["risk_level"] == "critical"
    assert final_state["human_approval_required"] is True
    _assert_current_directory(final_state, "approval_packet_dir", run_dir, "approval_packet")
    assert (run_dir / "approval_packet" / "approval_packet.json").exists()
    assert (run_dir / "approval_packet" / "07_human_decision.yaml").exists()
    assert (run_dir / "final_report.md").exists()
    memory_update = json.loads((run_dir / "memory_update.json").read_text(encoding="utf-8"))
    assert memory_update["memory_status"] == "pending"
    assert memory_update["accepted_result"] is False


def test_golden_demo_graph_writes_pending_report_and_approval_packet(tmp_path: Path) -> None:
    result = run_mock_graph(
        case_path="configs/cases/l64c64a076_m140.yaml",
        output_dir=str(tmp_path),
        run_id="golden",
    )
    state = result["state"]
    run_dir = tmp_path / "l64c64a076_m140" / "golden"
    run_result = json.loads((run_dir / "run_result.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    decision_log = json.loads((run_dir / "decision_log.json").read_text(encoding="utf-8"))
    memory_update = json.loads((run_dir / "memory_update.json").read_text(encoding="utf-8"))
    matrix = json.loads((run_dir / "analysis_outputs" / "synthetic_matrix_elements.json").read_text(encoding="utf-8"))

    assert state["status"] == "pending"
    assert state["current_node"] == "memory_report"
    assert state["risk_level"] == "high"
    assert state["human_approval_required"] is True
    _assert_current_directory(state, "approval_packet_dir", run_dir, "approval_packet")
    _assert_current_file(state, "final_report_path", run_dir, "final_report.md")
    _assert_current_file(state, "memory_update_path", run_dir, "memory_update.json")
    assert matrix["source_kind"] == "synthetic"
    assert matrix["golden_example"]["case_id"] == "l64c64a076_m140"
    assert "severe_demo_requires_human_approval" in matrix["diagnostic_flags"]
    assert run_result["golden_reference_files"]
    assert all(Path(path).exists() for path in run_result["golden_reference_files"])
    assert any(
        record["path"].endswith("analysis/README.md") and record["exists"]
        for record in manifest["input_files"]
    )
    assert decision_log["recommended_action"] == "pending_human_approval"
    assert memory_update["memory_status"] == "pending"
    assert memory_update["accepted_result"] is False
    assert (run_dir / "graph_state.json").exists()
    assert (run_dir / "approval_packet" / "approval_packet.json").exists()
    assert (run_dir / "approval_packet" / "07_human_decision.yaml").exists()

    with pytest.raises(FileExistsError, match="Choose a new --run-id"):
        run_mock_graph(
            case_path="configs/cases/l64c64a076_m140.yaml",
            output_dir=str(tmp_path),
            run_id="golden",
        )


def test_provider_golden_demo_keeps_human_gate_and_pending_memory(tmp_path: Path) -> None:
    result = run_mock_graph(
        case_path="configs/cases/l64c64a076_m140.yaml",
        output_dir=str(tmp_path),
        run_id="provider_golden",
        llm_provider_config_path="configs/runtime/mock_llm.yaml",
    )
    state = result["state"]
    run_dir = tmp_path / "l64c64a076_m140" / "provider_golden"
    decision_log = json.loads((run_dir / "decision_log.json").read_text(encoding="utf-8"))
    memory_update = json.loads((run_dir / "memory_update.json").read_text(encoding="utf-8"))
    review_report = json.loads((run_dir / "scientific_review_report.json").read_text(encoding="utf-8"))

    assert state["status"] == "pending"
    assert state["risk_level"] == "high"
    assert state["human_approval_required"] is True
    _assert_current_directory(state, "approval_packet_dir", run_dir, "approval_packet")
    assert decision_log["routing_decision"]["actual_route"] == "human_approval_gate"
    assert decision_log["recommended_action"] == "pending_human_approval"
    assert memory_update["accepted_result"] is False
    assert memory_update["memory_status"] == "pending"
    assert review_report["warnings"][0]["severity"] == "severe"
    assert (run_dir / "approval_packet" / "approval_packet.json").exists()


def test_graph_stops_when_planner_needs_more_info(tmp_path: Path) -> None:
    case_path = tmp_path / "needs_more_info.yaml"
    case_path.write_text('schema_version: "0.1"\n', encoding="utf-8")
    run_dir = tmp_path / "needs_more_info" / "smoke"
    checkpointer = MemorySaver()
    state = initialize_state(
        case_id="needs_more_info",
        run_id="smoke",
        user_goal="",
        case_config_path=str(case_path),
        output_dir=str(run_dir),
        checkpoint_backend="memory",
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(checkpointer)

    final_state = app.invoke(state, config=config)
    method_plan = json.loads((run_dir / "method_plan.json").read_text(encoding="utf-8"))

    assert final_state["status"] == "pending"
    assert final_state["current_node"] == "method_planner"
    assert final_state["run_result_path"] is None
    assert final_state["analysis_outputs_dir"] is None
    assert method_plan["status"] == "needs_more_info"
    assert {error["field"] for error in final_state["errors"]} == {
        "user_goal",
        "case_config.case_id",
    }
    assert final_state["route_decisions"][-1]["route"] == "end"


def test_missing_input_reaches_human_gate_with_structured_failure(tmp_path: Path) -> None:
    result = run_mock_graph(
        case_path="configs/cases/missing_input.input.json",
        output_dir=str(tmp_path),
        run_id="missing_input_smoke",
        llm_provider_config_path="configs/runtime/mock_llm.yaml",
    )
    final_state = result["state"]
    run_dir = tmp_path / "phase10c_missing_input" / "missing_input_smoke"
    route_nodes = [decision["source"] for decision in final_state["route_decisions"]]
    run_result = json.loads((run_dir / "run_result.json").read_text(encoding="utf-8"))
    decision_log = json.loads((run_dir / "decision_log.json").read_text(encoding="utf-8"))

    assert route_nodes[:5] == [
        "START",
        "method_planner",
        "analysis_engineer",
        "decision_coordinator",
        "human_approval_gate",
    ]
    assert final_state["current_node"] == "memory_report"
    assert final_state["status"] == "pending"
    assert final_state["scientific_review_report_path"] is None
    assert not (run_dir / "scientific_review_report.json").exists()
    assert run_result["run_success"] is False
    assert run_result["failure_type"] == "config_or_data"
    assert decision_log["risk_level"] == "critical"
    assert decision_log["recommended_action"] == "pending_human_approval"
    assert decision_log["human_approval_required"] is True
    assert {reason["code"] for reason in decision_log["reasons"]} >= {"config_or_data_failure"}
    assert (run_dir / "approval_packet" / "approval_packet.json").exists()


def test_graph_stops_at_codex_handoff_when_results_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_path = tmp_path / "code_needed.yaml"
    case_path.write_text(
        '\n'.join(
            [
                'schema_version: "0.1"',
                'case_id: "code_needed"',
                'physics_goal: "Plan a mock-only pion quasi-DA analysis support run."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "code_needed" / "smoke"

    def fake_repo_inventory(root: Path) -> dict[str, object]:
        return {
            "schema_version": "0.1",
            "repo_root": str(root),
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/graph/nodes.py"],
        }

    monkeypatch.setattr("lqcd_agent.graph.nodes.build_repo_inventory", fake_repo_inventory)
    monkeypatch.setattr(
        "lqcd_agent.graph.nodes.run_worker",
        lambda **kwargs: pytest.fail("run_worker should not be called unless auto_codex_handoff is enabled."),
    )
    checkpointer = MemorySaver()
    state = initialize_state(
        case_id="code_needed",
        run_id="smoke",
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path=str(case_path),
        output_dir=str(run_dir),
        checkpoint_backend="memory",
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(checkpointer)

    final_state = app.invoke(state, config=config)
    method_plan = json.loads((run_dir / "method_plan.json").read_text(encoding="utf-8"))

    assert final_state["status"] == "pending"
    assert final_state["current_node"] == "codex_handoff"
    assert final_state["code_needed"] is True
    _assert_current_file(final_state, "coder_task_packet_path", run_dir, "coder_task_packet.yaml")
    assert (run_dir / "coder_task_packet.yaml").exists()
    assert final_state["run_result_path"] is None
    assert final_state["analysis_outputs_dir"] is None
    assert method_plan["status"] == "success"
    assert method_plan["code_needed"] is True
    assert final_state["route_decisions"][-2]["route"] == "codex_handoff"
    assert final_state["route_decisions"][-1]["route"] == "end"


def test_legacy_codex_safe_stop_can_continue_same_run_with_new_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_path = tmp_path / "code_needed_continuation.yaml"
    case_path.write_text(
        "\n".join(
            [
                'schema_version: "0.1"',
                'case_id: "code_needed_continuation"',
                'physics_goal: "Plan a mock-only pion quasi-DA analysis support run."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_repo_inventory(root: Path) -> dict[str, object]:
        return {
            "schema_version": "0.1",
            "repo_root": str(root),
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/graph/nodes.py"],
        }

    monkeypatch.setattr("lqcd_agent.graph.nodes.build_repo_inventory", fake_repo_inventory)
    first = run_mock_graph(
        case_path=str(case_path),
        output_dir=str(tmp_path),
        run_id="continuation",
    )
    first_state = first["state"]
    run_dir = Path(first_state["output_dir"])
    assert first_state["status"] == "pending"
    assert first_state["attempt_kind"] == "legacy_codex_handoff"
    first_attempt_index = first_state["attempt_index"]
    first_transition_index = first_state["transition_index"]
    (run_dir / "code_change_summary.md").write_text(
        "Implemented the externally requested mock-only code change.\n",
        encoding="utf-8",
    )
    tests_status = {
        "schema_version": "0.1",
        "run_id": "continuation",
        "case_id": "code_needed_continuation",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "test_runner",
        "status": "tests_passed",
        "summary": "All configured verification commands passed.",
        "warnings": [],
        "errors": [],
        "commands": [],
    }
    (run_dir / "tests_status.json").write_text(json.dumps(tests_status), encoding="utf-8")

    second = run_mock_graph(
        case_path=str(case_path),
        output_dir=str(tmp_path),
        run_id="continuation",
    )
    second_state = second["state"]
    history = [
        json.loads(line)
        for line in (run_dir / "execution_history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    source_attempt_ids = [
        record["source_attempt_id"]
        for record in history
        if record["record_type"] == "transition" and record.get("source_attempt_id")
    ]

    assert second_state["status"] == "success"
    assert second_state["attempt_kind"] == "memory_report"
    assert second_state["attempt_index"] > first_attempt_index
    assert second_state["transition_index"] > first_transition_index
    assert len(source_attempt_ids) == len(set(source_attempt_ids))
    assert len([record for record in history if record["record_type"] == "run"]) == 1
    assert any(
        record["record_type"] == "transition"
        and record["source_node"] == "START"
        and record["source_attempt_id"] is None
        and record["fields"].get("trigger") == "legacy_reentry"
        for record in history
    )


def test_auto_codex_handoff_runs_worker_and_reaches_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_path = tmp_path / "code_needed.yaml"
    case_path.write_text(
        "\n".join(
            [
                'schema_version: "0.1"',
                'case_id: "code_needed"',
                'physics_goal: "Plan a mock-only pion quasi-DA analysis support run."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "code_needed" / "auto"

    def fake_repo_inventory(root: Path) -> dict[str, object]:
        return {
            "schema_version": "0.1",
            "repo_root": str(root),
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/graph/nodes.py"],
        }

    def fake_run_worker(**kwargs):
        output_dir = Path(kwargs["run_dir"])
        (output_dir / "code_change_summary.md").write_text(
            "Implemented the automatically requested mock-only code change.\n",
            encoding="utf-8",
        )
        tests_status = {
            "schema_version": "0.1",
            "run_id": "auto",
            "case_id": "code_needed",
            "created_at": "2026-06-10T00:00:00+00:00",
            "producer": "test_runner",
            "status": "tests_passed",
            "summary": "All configured verification commands passed.",
            "warnings": [],
            "errors": [],
            "commands": [
                {
                    "command": "pytest tests/test_coder_task_packet.py -q",
                    "working_directory": str(tmp_path),
                    "timeout_seconds": 60,
                    "return_code": 0,
                    "stdout": "passed",
                    "stderr": "",
                    "produced_files": [],
                    "status": "passed",
                }
            ],
        }
        (output_dir / "tests_status.json").write_text(json.dumps(tests_status), encoding="utf-8")
        return {
            "status": "tests_passed",
            "tests_status_path": str(output_dir / "tests_status.json"),
            "code_change_summary_path": str(output_dir / "code_change_summary.md"),
        }

    monkeypatch.setattr("lqcd_agent.graph.nodes.build_repo_inventory", fake_repo_inventory)
    monkeypatch.setattr("lqcd_agent.graph.nodes.run_worker", fake_run_worker)
    checkpointer = MemorySaver()
    state = initialize_state(
        case_id="code_needed",
        run_id="auto",
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path=str(case_path),
        output_dir=str(run_dir),
        checkpoint_backend="memory",
        auto_codex_handoff=True,
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(checkpointer)

    final_state = app.invoke(state, config=config)

    assert final_state["status"] == "success"
    assert final_state["current_node"] == "memory_report"
    assert final_state["code_needed"] is False
    _assert_current_file(final_state, "code_change_summary_path", run_dir, "code_change_summary.md")
    _assert_current_file(final_state, "tests_status_path", run_dir, "tests_status.json")
    assert (run_dir / "run_result.json").exists()
    assert any(
        decision["source"] == "codex_handoff" and decision["route"] == "analysis_engineer"
        for decision in final_state["route_decisions"]
    )


def test_auto_codex_handoff_tests_failed_stops_safely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_path = tmp_path / "code_needed.yaml"
    case_path.write_text(
        "\n".join(
            [
                'schema_version: "0.1"',
                'case_id: "code_needed"',
                'physics_goal: "Plan a mock-only pion quasi-DA analysis support run."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "code_needed" / "auto_failed"

    def fake_repo_inventory(root: Path) -> dict[str, object]:
        return {
            "schema_version": "0.1",
            "repo_root": str(root),
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/graph/nodes.py"],
        }

    def fake_run_worker(**kwargs):
        output_dir = Path(kwargs["run_dir"])
        tests_status = {
            "schema_version": "0.1",
            "run_id": "auto_failed",
            "case_id": "code_needed",
            "created_at": "2026-06-10T00:00:00+00:00",
            "producer": "test_runner",
            "status": "tests_failed",
            "summary": "Verification failed.",
            "warnings": [],
            "errors": [{"field": "verification", "message": "tests failed"}],
            "commands": [
                {
                    "command": "pytest tests/test_coder_task_packet.py -q",
                    "working_directory": str(tmp_path),
                    "timeout_seconds": 60,
                    "return_code": 1,
                    "stdout": "",
                    "stderr": "failed",
                    "produced_files": [],
                    "status": "failed",
                }
            ],
        }
        (output_dir / "tests_status.json").write_text(json.dumps(tests_status), encoding="utf-8")
        return {"status": "tests_failed", "tests_status_path": str(output_dir / "tests_status.json")}

    monkeypatch.setattr("lqcd_agent.graph.nodes.build_repo_inventory", fake_repo_inventory)
    monkeypatch.setattr("lqcd_agent.graph.nodes.run_worker", fake_run_worker)
    checkpointer = MemorySaver()
    state = initialize_state(
        case_id="code_needed",
        run_id="auto_failed",
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path=str(case_path),
        output_dir=str(run_dir),
        checkpoint_backend="memory",
        auto_codex_handoff=True,
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(checkpointer)

    final_state = app.invoke(state, config=config)

    assert final_state["status"] == "pending"
    assert final_state["current_node"] == "codex_handoff"
    assert final_state["code_fix_requested"] is True
    assert final_state["failure_type"] == "code"
    assert final_state["run_result_path"] is None
    assert final_state["route_decisions"][-1]["route"] == "end"
    assert final_state["route_decisions"][-1]["fields"]["tests_status"] == "tests_failed"


def test_auto_codex_handoff_worker_exception_records_structured_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_path = tmp_path / "code_needed.yaml"
    case_path.write_text(
        "\n".join(
            [
                'schema_version: "0.1"',
                'case_id: "code_needed"',
                'physics_goal: "Plan a mock-only pion quasi-DA analysis support run."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "code_needed" / "auto_exception"

    def fake_repo_inventory(root: Path) -> dict[str, object]:
        return {
            "schema_version": "0.1",
            "repo_root": str(root),
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/graph/nodes.py"],
        }

    def fake_run_worker(**kwargs):
        raise FileNotFoundError("codex executable was not found")

    monkeypatch.setattr("lqcd_agent.graph.nodes.build_repo_inventory", fake_repo_inventory)
    monkeypatch.setattr("lqcd_agent.graph.nodes.run_worker", fake_run_worker)
    checkpointer = MemorySaver()
    state = initialize_state(
        case_id="code_needed",
        run_id="auto_exception",
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path=str(case_path),
        output_dir=str(run_dir),
        checkpoint_backend="memory",
        auto_codex_handoff=True,
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(checkpointer)

    final_state = app.invoke(state, config=config)

    assert final_state["status"] == "pending"
    assert final_state["current_node"] == "codex_handoff"
    assert final_state["tests_status_path"] is None
    assert final_state["errors"][-1]["field"] == "auto_codex_handoff"
    assert "codex executable was not found" in final_state["errors"][-1]["message"]
    assert final_state["route_decisions"][-1]["route"] == "end"


def test_graph_reaches_analysis_after_structured_handoff_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_path = tmp_path / "code_needed.yaml"
    case_path.write_text(
        '\n'.join(
            [
                'schema_version: "0.1"',
                'case_id: "code_needed"',
                'physics_goal: "Plan a mock-only pion quasi-DA analysis support run."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "code_needed" / "smoke"
    run_dir.mkdir(parents=True)
    (run_dir / "code_change_summary.md").write_text(
        "Implemented the externally requested mock-only code change.\n",
        encoding="utf-8",
    )
    tests_status = {
        "schema_version": "0.1",
        "run_id": "smoke",
        "case_id": "code_needed",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "test_runner",
        "status": "tests_passed",
        "summary": "All configured verification commands passed.",
        "warnings": [],
        "errors": [],
        "commands": [
            {
                "command": "pytest tests/test_coder_task_packet.py -q",
                "working_directory": str(tmp_path),
                "timeout_seconds": 60,
                "return_code": 0,
                "stdout": "passed",
                "stderr": "",
                "produced_files": [],
                "status": "passed",
            }
        ],
    }
    (run_dir / "tests_status.json").write_text(json.dumps(tests_status), encoding="utf-8")

    def fake_repo_inventory(root: Path) -> dict[str, object]:
        return {
            "schema_version": "0.1",
            "repo_root": str(root),
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/graph/nodes.py"],
        }

    monkeypatch.setattr("lqcd_agent.graph.nodes.build_repo_inventory", fake_repo_inventory)
    checkpointer = MemorySaver()
    state = initialize_state(
        case_id="code_needed",
        run_id="smoke",
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config_path=str(case_path),
        output_dir=str(run_dir),
        checkpoint_backend="memory",
    )
    config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
    app = compile_analysis_graph(checkpointer)

    final_state = app.invoke(state, config=config)

    assert final_state["status"] == "success"
    assert final_state["code_needed"] is False
    assert final_state["current_node"] == "memory_report"
    _assert_current_file(final_state, "code_change_summary_path", run_dir, "code_change_summary.md")
    _assert_current_file(final_state, "tests_status_path", run_dir, "tests_status.json")
    _assert_current_file(final_state, "run_result_path", run_dir, "run_result.json")
    assert final_state["analysis_outputs_dir"]
    assert (run_dir / "manifest.json").exists()
    assert any(
        decision["source"] == "codex_handoff" and decision["route"] == "analysis_engineer"
        for decision in final_state["route_decisions"]
    )


def test_run_mock_graph_allows_preexisting_handoff_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_path = tmp_path / "code_needed.yaml"
    case_path.write_text(
        "\n".join(
            [
                'schema_version: "0.1"',
                'case_id: "code_needed"',
                'physics_goal: "Plan a mock-only pion quasi-DA analysis support run."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "code_needed" / "handoff_open"
    run_dir.mkdir(parents=True)
    (run_dir / "code_change_summary.md").write_text(
        "Implemented the externally requested mock-only code change.\n",
        encoding="utf-8",
    )
    tests_status = {
        "schema_version": "0.1",
        "run_id": "handoff_open",
        "case_id": "code_needed",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "test_runner",
        "status": "tests_passed",
        "summary": "All configured verification commands passed.",
        "warnings": [],
        "errors": [],
        "commands": [
            {
                "command": "pytest tests/test_coder_task_packet.py -q",
                "working_directory": str(tmp_path),
                "timeout_seconds": 60,
                "return_code": 0,
                "stdout": "passed",
                "stderr": "",
                "produced_files": [],
                "status": "passed",
            }
        ],
    }
    (run_dir / "tests_status.json").write_text(json.dumps(tests_status), encoding="utf-8")

    def fake_repo_inventory(root: Path) -> dict[str, object]:
        return {
            "schema_version": "0.1",
            "repo_root": str(root),
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/graph/nodes.py"],
        }

    monkeypatch.setattr("lqcd_agent.graph.nodes.build_repo_inventory", fake_repo_inventory)

    result = run_mock_graph(
        case_path=str(case_path),
        output_dir=str(tmp_path),
        run_id="handoff_open",
    )
    state = result["state"]

    assert state["status"] == "success"
    assert state["current_node"] == "memory_report"
    _assert_current_file(state, "code_change_summary_path", run_dir, "code_change_summary.md")
    _assert_current_file(state, "tests_status_path", run_dir, "tests_status.json")
    assert (run_dir / "run_result.json").exists()
