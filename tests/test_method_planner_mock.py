import json
from pathlib import Path

from lqcd_agent.agents.method_planner import run_method_planner
from lqcd_agent.analysis_programs.registry import program_inventory
from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse
from lqcd_agent.llm.mock_provider import MockLLMProvider


class StaticProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.config = LLMProviderConfig(provider="static")

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(provider="static", model="static", content=self.content)


def _case_config() -> dict[str, str]:
    return {
        "schema_version": "0.1",
        "case_id": "mock_lqcd_goal",
        "source_kind": "synthetic_placeholder",
        "physics_goal": "Plan a mock-only pion quasi-DA analysis support run.",
    }


def test_mock_goal_generates_valid_method_plan(tmp_path: Path) -> None:
    result = run_method_planner(
        user_goal="Plan a mock-only pion quasi-DA analysis support run.",
        case_config=_case_config(),
        repo_inventory={"schema_version": "0.1", "implementation_gaps": []},
        output_dir=tmp_path,
        run_id="unit_run",
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))

    assert result["status"] == "success"
    assert result["code_needed"] is False
    assert method_plan["status"] == "success"
    assert method_plan["physics_goal"] == _case_config()["physics_goal"]
    assert method_plan["target_observables"]
    assert method_plan["method_steps"]
    assert method_plan["required_inputs"]
    assert method_plan["required_outputs"]
    assert method_plan["implementation_gaps"] == []
    assert method_plan["selected_analysis_programs"] == []
    assert method_plan["code_needed"] is False
    assert method_plan["coder_task_summary"] is None


def test_selects_registered_analysis_program_from_inventory(tmp_path: Path) -> None:
    case_config = {
        "schema_version": "0.1",
        "case_id": "clean_fit_raw",
        "source_kind": "raw_clean_fit_csv",
        "physics_goal": "Recover effective-mass estimates from raw clean-fit CSV data.",
        "raw_data_path": "raw_data/clean_decay.csv",
        "analysis_program_tags": ["two_point", "effective_mass"],
        "target_observables": ["effective_mass_estimates"],
    }
    result = run_method_planner(
        user_goal="Recover effective-mass estimates from raw clean-fit CSV data.",
        case_config=case_config,
        repo_inventory={
            "schema_version": "0.1",
            "implementation_gaps": [],
            "analysis_programs": program_inventory(),
        },
        output_dir=tmp_path,
        run_id="unit_run",
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))
    selected = method_plan["selected_analysis_programs"]

    assert result["status"] == "success"
    assert result["code_needed"] is False
    assert selected[0]["name"] == "single_exponential_effective_mass"
    assert selected[0]["input_mapping"] == {
        "times": "raw_data_csv.t",
        "correlator_values": "raw_data_csv.value",
    }
    assert selected[0]["output_path"] == "analysis_outputs/effective_mass_estimates.json"


def test_selects_optional_correlator_error_mapping_when_csv_has_error_column(tmp_path: Path) -> None:
    raw_data_dir = tmp_path / "raw_data"
    raw_data_dir.mkdir()
    (raw_data_dir / "clean_decay.csv").write_text(
        "t,value,error\n0,1.0,0.02\n1,0.7,0.03\n",
        encoding="utf-8",
    )
    case_config = {
        "schema_version": "0.1",
        "case_id": "clean_fit_raw",
        "source_kind": "raw_clean_fit_csv",
        "physics_goal": "Recover effective-mass estimates from raw clean-fit CSV data.",
        "raw_data_path": "raw_data/clean_decay.csv",
        "analysis_program_tags": ["two_point", "effective_mass"],
        "target_observables": ["effective_mass_estimates"],
    }

    result = run_method_planner(
        user_goal="Recover effective-mass estimates from raw clean-fit CSV data.",
        case_config=case_config,
        repo_inventory={
            "schema_version": "0.1",
            "repo_root": str(tmp_path),
            "implementation_gaps": [],
            "analysis_programs": program_inventory(),
        },
        output_dir=tmp_path,
        run_id="unit_run",
    )
    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))

    assert result["status"] == "success"
    assert method_plan["selected_analysis_programs"][0]["input_mapping"] == {
        "times": "raw_data_csv.t",
        "correlator_values": "raw_data_csv.value",
        "correlator_errors": "raw_data_csv.error",
    }


def test_missing_raw_data_is_deferred_to_analysis_engineer(tmp_path: Path) -> None:
    case_config = {
        "schema_version": "0.1",
        "case_id": "missing_input",
        "source_kind": "missing_raw_decay_csv",
        "physics_goal": "Stop safely when raw data is missing.",
        "raw_data_path": "raw_data/does_not_exist.csv",
        "analysis_program_tags": ["two_point", "effective_mass"],
        "target_observables": ["effective_mass_estimates"],
    }

    result = run_method_planner(
        user_goal="Stop safely when raw data is missing.",
        case_config=case_config,
        repo_inventory={
            "schema_version": "0.1",
            "repo_root": str(tmp_path),
            "implementation_gaps": [],
            "analysis_programs": program_inventory(),
        },
        output_dir=tmp_path,
        run_id="unit_run",
    )
    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))

    assert result["status"] == "success"
    assert result["code_needed"] is False
    assert method_plan["status"] == "success"
    assert method_plan["errors"] == []
    assert method_plan["selected_analysis_programs"]
    assert method_plan["warnings"][0]["code"] == "runtime_input_validation_deferred_to_analysis_engineer"


def test_code_needed_returns_domain_request_without_control_authority(tmp_path: Path) -> None:
    result = run_method_planner(
        user_goal="Plan the mock run and hand off missing implementation gaps.",
        case_config=_case_config(),
        repo_inventory={
            "schema_version": "0.1",
            "implementation_gaps": ["Missing deterministic synthetic output validator."],
            "allowed_files": ["src/lqcd_agent/agents/method_planner.py"],
        },
        output_dir=tmp_path,
        run_id="unit_run",
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))
    request = result["code_request"]
    assert request["summary"] == method_plan["coder_task_summary"]
    assert request["requirements"] == method_plan["method_steps"]
    assert set(request) == {"summary", "requirements", "proposed_paths"}
    assert not (tmp_path / "coder_task_packet.yaml").exists()


def test_missing_critical_fields_produce_needs_more_info(tmp_path: Path) -> None:
    result = run_method_planner(
        user_goal="",
        case_config={"schema_version": "0.1"},
        repo_inventory={"schema_version": "0.1"},
        output_dir=tmp_path,
        run_id="unit_run",
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))

    assert result["status"] == "needs_more_info"
    assert result["code_request"] is None
    assert method_plan["status"] == "needs_more_info"
    assert method_plan["errors"]
    assert {error["field"] for error in method_plan["errors"]} == {"user_goal", "case_config.case_id"}


def test_provider_backed_method_plan_accepts_valid_mock_output(tmp_path: Path) -> None:
    result = run_method_planner(
        user_goal="Plan through a mock provider.",
        case_config=_case_config(),
        repo_inventory={"schema_version": "0.1", "implementation_gaps": []},
        output_dir=tmp_path,
        run_id="unit_run",
        provider=MockLLMProvider(),
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))

    assert result["status"] == "success"
    assert result["code_needed"] is False
    assert method_plan["producer"] == "method_planner"
    assert method_plan["summary"].startswith("Provider-backed mock")
    trace = json.loads((tmp_path / "llm_calls" / "method_planner.json").read_text(encoding="utf-8"))
    assert trace["agent"] == "method_planner"
    assert trace["provider"]["provider"] == "mock"
    assert trace["parsed_payload_path"] == str(tmp_path / "method_plan.json")
    assert trace["response"]["content"]






def test_invalid_provider_method_plan_writes_failed_artifact(tmp_path: Path) -> None:
    result = run_method_planner(
        user_goal="Plan through an invalid provider.",
        case_config=_case_config(),
        repo_inventory={"schema_version": "0.1", "implementation_gaps": []},
        output_dir=tmp_path,
        run_id="unit_run",
        provider=StaticProvider('{"status": "success", "free_text_route": "analysis_engineer"}'),
    )

    method_plan = json.loads((tmp_path / "method_plan.json").read_text(encoding="utf-8"))

    assert result["status"] == "failed"
    assert result["code_needed"] is False
    assert method_plan["status"] == "failed"
    assert method_plan["errors"][0]["code"] == "provider_schema_error"
