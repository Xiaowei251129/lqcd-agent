import json
from pathlib import Path

import pytest

from lqcd_agent.demo.server import (
    DemoServerError,
    apply_human_decision,
    case_config_preview,
    case_configs,
    chat_response,
    command_preview,
    resolve_runtime_config_path,
    runtime_configs,
    run_status_payload,
    start_graph_run,
    validate_case_config_request,
    resolve_artifact_path,
    run_question_against_config,
    run_once_smoke,
    write_human_decision_file,
)
from lqcd_agent.graph.analysis_graph import execute_graph_node_transition
from lqcd_agent.graph.nodes import human_approval_gate_node, memory_report_node
from lqcd_agent.graph.routing import select_after_human_approval_gate
from lqcd_agent.graph.state import commit_external_transition, submit_human_response


def test_case_configs_endpoint_returns_repo_case_configs(tmp_path: Path) -> None:
    payload = {"configs": case_configs()}

    assert {config["config_id"] for config in payload["configs"]} >= {"mock_lqcd_goal", "l64c64a076_m140"}
    assert payload["configs"][0]["config_id"] == "clean_fit.input"
    assert "missing_input.input" in {config["config_id"] for config in payload["configs"]}
    missing_input = next(config for config in payload["configs"] if config["config_id"] == "missing_input.input")
    assert missing_input["config_type"] == "json"
    assert missing_input["path"] == "configs/cases/missing_input.input.json"
    assert missing_input["analysis_route"] == "registered_analysis_program"
    assert missing_input["raw_data_status"] == "missing"
    assert "hidden_expected_conclusion_summary" not in json.dumps(payload)


def test_runtime_configs_endpoint_returns_repo_provider_configs() -> None:
    payload = {"runtime_configs": runtime_configs()}

    assert {config["config_id"] for config in payload["runtime_configs"]} >= {"mock_llm", "openai", "deepseek"}
    openai = next(config for config in payload["runtime_configs"] if config["config_id"] == "openai")
    assert openai["path"] == "configs/runtime/openai.yaml"
    assert openai["live_test_env"] == "RUN_LIVE_LLM_TESTS"
    assert openai["provider_mode"] == "live"
    assert openai["recommended"] is True
    assert payload["runtime_configs"][0]["config_id"] == "openai"
    mock = next(config for config in payload["runtime_configs"] if config["config_id"] == "mock_llm")
    assert mock["provider_mode"] == "testing"
    assert "testing/developer" in mock["label"]


def test_validate_config_preview_rejects_missing_config(tmp_path: Path) -> None:
    with pytest.raises(DemoServerError, match="Missing case config"):
        validate_case_config_request(output_root=tmp_path, body={})


def test_validate_pasted_config_returns_preview(tmp_path: Path) -> None:
    payload = validate_case_config_request(
        output_root=tmp_path,
        body={
            "config_text": '\n'.join(
                [
                    'schema_version: "0.1"',
                    'case_id: "pasted_case"',
                    'physics_goal: "Run pasted config."',
                    "analysis_commands:",
                    '- "mock:write_synthetic_matrix_elements"',
                    "expected_outputs:",
                    '- "analysis_outputs/synthetic_matrix_elements.json"',
                ]
            )
        },
    )

    assert payload["config"]["case_id"] == "pasted_case"
    assert payload["config"]["analysis_route"] == "analysis_commands"
    assert payload["config"]["analysis_commands"] == ["mock:write_synthetic_matrix_elements"]


def test_validate_json_config_returns_preview(tmp_path: Path) -> None:
    payload = validate_case_config_request(
        output_root=tmp_path,
        body={"config_id": "missing_input.input"},
    )

    assert payload["config"]["case_id"] == "phase10c_missing_input"
    assert payload["config"]["analysis_route"] == "registered_analysis_program"
    assert payload["config"]["analysis_program_tags"] == ["two_point", "effective_mass"]
    assert payload["config"]["target_observables"] == ["effective_mass_estimates"]
    assert payload["config"]["raw_data_path"] == "raw_data/does_not_exist.csv"
    assert payload["config"]["raw_data_status"] == "missing"
    assert payload["config"]["expected_outputs"] == ["analysis_outputs/effective_mass_estimates.json"]
    assert not any("analysis_commands is missing" in warning for warning in payload["config"]["warnings"])
    assert any("raw_data_path is configured but the file is missing" in warning for warning in payload["config"]["warnings"])


def test_clean_fit_preview_uses_registered_program_schema_without_legacy_warning() -> None:
    preview = case_config_preview("configs/cases/clean_fit.input.json")

    assert preview["case_id"] == "clean_fit_raw"
    assert preview["analysis_route"] == "registered_analysis_program"
    assert preview["analysis_commands"] == []
    assert preview["raw_data_path"] == "raw_data/clean_decay.csv"
    assert preview["raw_data_status"] == "exists"
    assert preview["analysis_program_tags"] == ["two_point", "effective_mass"]
    assert preview["target_observables"] == ["effective_mass_estimates"]
    assert preview["warnings"] == []


def test_run_config_writes_core_artifacts_and_report(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run a local config-backed smoke test.",
        config_id="mock_lqcd_goal",
        output_root=tmp_path,
        run_id_prefix="test_ui_config",
    )
    artifact = next(item for item in payload["artifacts"] if item["name"] == "final_report")
    artifact_path = resolve_artifact_path(output_root=tmp_path, requested_path=artifact["path"])
    artifact_text = artifact_path.read_text(encoding="utf-8")

    assert payload["summary"]["risk_level"] == "low"
    assert Path(payload["run_dir"], "method_plan.json").exists()
    assert Path(payload["run_dir"], "final_report.md").exists()
    assert "hidden_expected_conclusion_summary" not in artifact_text


def test_artifact_endpoint_rejects_paths_outside_output_root(tmp_path: Path) -> None:
    with pytest.raises(DemoServerError, match="outside the demo output root"):
        resolve_artifact_path(output_root=tmp_path, requested_path="/etc/passwd")


def test_start_graph_run_returns_pollable_run_payload(tmp_path: Path) -> None:
    payload = start_graph_run(
        config_id="mock_lqcd_goal",
        output_root=tmp_path,
        run_id_prefix="test_async_run",
    )
    polled = run_status_payload(output_root=tmp_path, case_id=payload["case_id"], run_id=payload["run_id"])

    assert polled["case_id"] == "mock_lqcd_goal"
    assert polled["summary"]["status"] in {"running", "success"}


def test_start_graph_run_accepts_terminal_equivalent_payload(tmp_path: Path) -> None:
    payload = start_graph_run(
        config_id="missing_input.input",
        output_root=tmp_path,
        output_dir=tmp_path,
        run_id="fit_demo_001",
        llm_provider_config_path="configs/runtime/mock_llm.yaml",
    )
    polled = run_status_payload(output_root=tmp_path, case_id=payload["case_id"], run_id=payload["run_id"])

    assert payload["case_id"] == "phase10c_missing_input"
    assert payload["run_id"] == "fit_demo_001"
    assert "--case configs/cases/missing_input.input.json" in payload["command_preview"]
    assert "--run-id fit_demo_001" in payload["command_preview"]
    assert "--llm-provider-config configs/runtime/mock_llm.yaml" in payload["command_preview"]
    assert Path(polled["run_dir"], "graph_state.json").exists() or polled["job_status"] == "running"


def test_start_graph_run_blocks_live_provider_when_env_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_LIVE_LLM_TESTS", raising=False)

    with pytest.raises(DemoServerError, match="RUN_LIVE_LLM_TESTS=1 is required"):
        start_graph_run(
            config_id="clean_fit.input",
            output_root=tmp_path,
            run_id="clean_fit_live_demo_001",
            llm_provider_config_path="configs/runtime/openai.yaml",
        )


def test_runtime_provider_path_rejects_paths_outside_runtime_configs() -> None:
    with pytest.raises(DemoServerError, match="Unknown runtime config"):
        resolve_runtime_config_path("/etc/passwd")


def test_openai_command_preview_includes_live_env_hint_when_env_missing(tmp_path: Path) -> None:
    command = command_preview(
        case_path=Path("configs/cases/missing_input.input.json"),
        output_dir=tmp_path,
        run_id="fit_demo_001",
        llm_provider_config_path=Path("configs/runtime/openai.yaml"),
    )

    assert "--llm-provider-config configs/runtime/openai.yaml" in command
    assert command.startswith("RUN_LIVE_LLM_TESTS=1 ") or "RUN_LIVE_LLM_TESTS=1" not in command


def test_once_smoke_runs_clean_case(tmp_path: Path) -> None:
    result = run_once_smoke(tmp_path)

    assert result["ok"] is True
    assert result["case_id"] == "mock_lqcd_goal"
    assert Path(result["run_dir"], "final_report.md").exists()


def test_chat_requires_explicit_evidence_context(tmp_path: Path) -> None:
    with pytest.raises(DemoServerError, match="Missing case config"):
        chat_response(message="Is this result acceptable?", config_id=None, output_root=tmp_path)


def test_chat_runs_langgraph_with_question_as_physics_goal_from_config(tmp_path: Path) -> None:
    question = "Can this selected config produce a report?"

    payload = chat_response(
        message=question,
        config_id="mock_lqcd_goal",
        output_root=tmp_path,
        run_id_prefix="test_chat_question",
    )
    run = payload["run"]
    method_plan = json.loads(Path(run["run_dir"], "method_plan.json").read_text(encoding="utf-8"))

    assert payload["mode"] == "single"
    assert run["summary"]["risk_level"] == "low"
    assert run["summary"]["human_approval_required"] is False
    assert method_plan["physics_goal"] == question
    assert "运行了 LangGraph" in payload["content"]


def test_golden_config_payload_marks_pending_human_approval(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run the golden example through the UI.",
        config_id="l64c64a076_m140",
        output_root=tmp_path,
        run_id_prefix="test_golden_ui",
    )

    assert payload["summary"]["human_approval_required"] is True
    assert payload["approval"]["pending"] is True
    assert payload["approval"]["packet"]["decision_options"]


def test_human_decision_approve_with_conditions_updates_memory(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run the golden example and approve it.",
        config_id="l64c64a076_m140",
        output_root=tmp_path,
        run_id_prefix="test_approve_ui",
    )
    state_before = json.loads(Path(payload["run_dir"], "graph_state.json").read_text(encoding="utf-8"))

    updated = apply_human_decision(
        output_root=tmp_path,
        case_id=payload["case_id"],
        run_id=payload["run_id"],
        decision="approve_with_conditions",
        conditions="UI approval test.",
        reason="Reviewed packet.",
        decided_by="pytest",
    )
    memory = json.loads(Path(updated["run_dir"], "memory_update.json").read_text(encoding="utf-8"))
    state_after = json.loads(Path(updated["run_dir"], "graph_state.json").read_text(encoding="utf-8"))

    assert updated["approval"]["pending"] is False
    assert updated["approval"]["decision"]["decision"] == "approve_with_conditions"
    assert memory["memory_status"] == "accepted"
    assert state_after["attempt_index"] == state_before["attempt_index"] + 2
    assert state_after["attempt_kind"] == "memory_report"
    assert state_after["parent_attempt_id"] == f"attempt_{state_after['attempt_index'] - 1:06d}"
    assert state_after["active_human_request_id"] == "human_request_000001"
    assert state_after["active_human_response_id"] == "human_response_000001"
    assert state_after["human_response_status"] == "consumed"
    assert state_after["human_request_status"] == "satisfied"
    assert state_after["human_response_validator_attempt_id"] == state_after["parent_attempt_id"]
    assert state_after["human_response_consumer_attempt_id"] == state_after["parent_attempt_id"]
    assert state_after["human_response_target_attempt_id"] == state_after["attempt_id"]
    history = [
        json.loads(line)
        for line in Path(updated["run_dir"], "execution_history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    response_records = [record for record in history if record["record_type"] == "human_response"]
    assert [record["event"] for record in response_records] == ["submitted", "validated", "consumed"]
    assert response_records[0]["payload_reference"] == "inline:demo_api_request"
    assert response_records[0]["payload_snapshot"]["decision"] == "approve_with_conditions"
    assert response_records[1]["validator_attempt_id"] == state_after["parent_attempt_id"]
    assert response_records[2]["consumer_attempt_id"] == state_after["parent_attempt_id"]
    assert response_records[2]["authorized_target_attempt_id"] == state_after["attempt_id"]
    request_records = [record for record in history if record["record_type"] == "human_request"]
    assert request_records[0]["event"] == "created"
    assert request_records[-1]["event"] == "satisfied"
    assert request_records[-1]["status"] == "satisfied"
    assert request_records[-1]["authorization_scope"]["allowed_target_nodes"]

    run_dir = Path(updated["run_dir"])
    memory_before_duplicate = (run_dir / "memory_update.json").read_bytes()
    report_before_duplicate = (run_dir / "final_report.md").read_bytes()
    ledger_before_duplicate = (run_dir / "execution_history.jsonl").read_bytes()
    identity_before_duplicate = {
        field: state_after[field]
        for field in (
            "attempt_index",
            "transition_index",
            "human_request_index",
            "human_response_index",
        )
    }
    with pytest.raises(DemoServerError) as exc_info:
        apply_human_decision(
            output_root=tmp_path,
            case_id=payload["case_id"],
            run_id=payload["run_id"],
            decision="approve_with_conditions",
            conditions="Duplicate submission.",
            reason="This must not run again.",
            decided_by="pytest",
        )
    assert exc_info.value.status.value == 409
    state_after_duplicate = json.loads(Path(updated["run_dir"], "graph_state.json").read_text(encoding="utf-8"))
    assert {
        field: state_after_duplicate[field]
        for field in identity_before_duplicate
    } == identity_before_duplicate
    assert (run_dir / "execution_history.jsonl").read_bytes() == ledger_before_duplicate
    assert (run_dir / "memory_update.json").read_bytes() == memory_before_duplicate
    assert (run_dir / "final_report.md").read_bytes() == report_before_duplicate


def test_invalid_demo_decision_does_not_consume_response_identity(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run the golden example before correcting an invalid decision.",
        config_id="l64c64a076_m140",
        output_root=tmp_path,
        run_id_prefix="test_invalid_decision_ui",
    )
    state_path = Path(payload["run_dir"], "graph_state.json")
    before = json.loads(state_path.read_text(encoding="utf-8"))

    with pytest.raises(DemoServerError) as exc_info:
        apply_human_decision(
            output_root=tmp_path,
            case_id=payload["case_id"],
            run_id=payload["run_id"],
            decision="ship_it",
        )

    assert exc_info.value.status.value == 400
    after_invalid = json.loads(state_path.read_text(encoding="utf-8"))
    assert after_invalid["human_response_index"] == before["human_response_index"]
    assert after_invalid["active_human_response_id"] is None
    updated = apply_human_decision(
        output_root=tmp_path,
        case_id=payload["case_id"],
        run_id=payload["run_id"],
        decision="reject_or_hold",
        reason="Corrected decision.",
    )
    assert updated["approval"]["decision"]["decision"] == "reject_or_hold"


def test_invalid_identified_response_can_be_replaced_and_consumed_once(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run the golden example through an invalid and corrected response.",
        config_id="l64c64a076_m140",
        output_root=tmp_path,
        run_id_prefix="test_invalid_response_lifecycle",
    )
    run_dir = Path(payload["run_dir"])
    state = json.loads((run_dir / "graph_state.json").read_text(encoding="utf-8"))
    decision_path = Path(str(state["human_decision_path"]))
    state = submit_human_response(
        state,
        payload={
            "decision": "approve_with_conditions",
            "human_request_id": state["active_human_request_id"],
        },
        payload_reference="inline:test_invalid_response",
    )
    first_response_id = state["active_human_response_id"]
    write_human_decision_file(
        path=decision_path,
        run_id=state["run_id"],
        case_id=state["case_id"],
        cycle_id=state["cycle_id"],
        human_request_id="human_request_999999",
        requesting_attempt_id=state["human_requesting_attempt_id"],
        human_response_id=first_response_id,
        decision="approve_with_conditions",
    )
    state = commit_external_transition(
        state,
        source_name="HUMAN_RESPONSE",
        route="human_approval_gate",
        reason="Validate an identity-mismatched response.",
        fields={"human_response_id": first_response_id},
        target_node="human_approval_gate",
        target_attempt_kind="human_gate",
        trigger_reason="human_response",
    )
    state = execute_graph_node_transition(
        state,
        node_name="human_approval_gate",
        attempt_kind="human_gate",
        node=human_approval_gate_node,
        route_selector=select_after_human_approval_gate,
        route_targets={
            "analysis_engineer": ("analysis_engineer", "analysis_engineer"),
            "codex_handoff": ("codex_handoff", "legacy_codex_handoff"),
            "memory_report": ("memory_report", "memory_report"),
            "end": None,
        },
    )

    assert state["human_response_status"] == "invalid"
    assert state["human_request_status"] == "open"
    invalid_attempt_index = state["attempt_index"]
    state = submit_human_response(
        state,
        payload={
            "decision": "approve_with_conditions",
            "human_request_id": state["active_human_request_id"],
        },
        payload_reference="inline:test_corrected_response",
    )
    second_response_id = state["active_human_response_id"]
    write_human_decision_file(
        path=decision_path,
        run_id=state["run_id"],
        case_id=state["case_id"],
        cycle_id=state["cycle_id"],
        human_request_id=state["active_human_request_id"],
        requesting_attempt_id=state["human_requesting_attempt_id"],
        human_response_id=second_response_id,
        decision="approve_with_conditions",
    )
    state = commit_external_transition(
        state,
        source_name="HUMAN_RESPONSE",
        route="human_approval_gate",
        reason="Validate the corrected response.",
        fields={"human_response_id": second_response_id},
        target_node="human_approval_gate",
        target_attempt_kind="human_gate",
        trigger_reason="human_response",
    )
    state = execute_graph_node_transition(
        state,
        node_name="human_approval_gate",
        attempt_kind="human_gate",
        node=human_approval_gate_node,
        route_selector=select_after_human_approval_gate,
        route_targets={
            "analysis_engineer": ("analysis_engineer", "analysis_engineer"),
            "codex_handoff": ("codex_handoff", "legacy_codex_handoff"),
            "memory_report": ("memory_report", "memory_report"),
            "end": None,
        },
    )
    state = execute_graph_node_transition(
        state,
        node_name="memory_report",
        attempt_kind="memory_report",
        node=memory_report_node,
        route_selector=lambda completed: {
            "route": "end",
            "reason": "Memory and Report is the terminal graph sink.",
            "fields": {"status": completed["status"]},
            "state_updates": {},
        },
        route_targets={"end": None},
    )
    history = [
        json.loads(line)
        for line in (run_dir / "execution_history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    response_events = {
        response_id: [
            record["event"]
            for record in history
            if record["record_type"] == "human_response"
            and record["human_response_id"] == response_id
        ]
        for response_id in (first_response_id, second_response_id)
    }

    assert first_response_id == "human_response_000001"
    assert second_response_id == "human_response_000002"
    assert response_events[first_response_id] == ["submitted", "invalid"]
    assert response_events[second_response_id] == ["submitted", "validated", "consumed"]
    assert state["human_response_status"] == "consumed"
    assert state["human_request_status"] == "satisfied"
    assert state["attempt_index"] == invalid_attempt_index + 2


def test_human_decision_reject_or_hold_updates_memory(tmp_path: Path) -> None:
    payload = run_question_against_config(
        question="Run the golden example and reject it.",
        config_id="l64c64a076_m140",
        output_root=tmp_path,
        run_id_prefix="test_reject_ui",
    )

    updated = apply_human_decision(
        output_root=tmp_path,
        case_id=payload["case_id"],
        run_id=payload["run_id"],
        decision="reject_or_hold",
        reason="Hold for review.",
        decided_by="pytest",
    )
    memory = json.loads(Path(updated["run_dir"], "memory_update.json").read_text(encoding="utf-8"))

    assert updated["approval"]["pending"] is False
    assert updated["approval"]["decision"]["decision"] == "reject_or_hold"
    assert memory["memory_status"] == "rejected"
