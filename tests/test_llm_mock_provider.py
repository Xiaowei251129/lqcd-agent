import json
from pathlib import Path

from lqcd_agent.llm.base import LLMRequest
from lqcd_agent.llm.mock_provider import MockLLMProvider
from lqcd_agent.llm.prompts import build_scientific_reviewer_request
from lqcd_agent.llm.structured_output import parse_json_object, write_error_artifact
from lqcd_agent.llm.trace import write_llm_call_trace


def test_mock_provider_returns_deterministic_json() -> None:
    provider = MockLLMProvider()
    response = provider.generate(
        LLMRequest(messages=[{"role": "user", "content": "Return a structured response."}])
    )
    payload = json.loads(response.content)

    assert response.provider == "mock"
    assert response.model == "deterministic-mock"
    assert payload["status"] == "success"
    assert payload["provider"] == "mock"
    assert payload["message_count"] == 1


def test_invalid_json_output_writes_structured_error_artifact(tmp_path: Path) -> None:
    payload, error = parse_json_object(
        "not-json",
        producer="method_planner",
        run_id="unit_run",
        case_id="unit_case",
    )

    assert payload is None
    assert error is not None
    assert error["schema_version"] == "0.1"
    assert error["run_id"] == "unit_run"
    assert error["case_id"] == "unit_case"
    assert error["status"] == "failed"
    assert error["errors"][0]["code"] == "invalid_json"

    path = write_error_artifact(tmp_path / "provider_error.json", error)
    written = json.loads(Path(path).read_text(encoding="utf-8"))

    assert written["producer"] == "method_planner"
    assert written["summary"] == "Provider output was not valid JSON."


def test_llm_call_trace_records_request_response_without_secret_values(tmp_path: Path) -> None:
    provider = MockLLMProvider()
    request = LLMRequest(messages=[{"role": "user", "content": "Return JSON."}])
    response = provider.generate(request)

    path = write_llm_call_trace(
        output_dir=tmp_path,
        agent="method_planner",
        provider=provider,
        request=request,
        response=response,
        parsed_payload_path=tmp_path / "method_plan.json",
        status="success",
    )
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    assert Path(path).name == "method_planner.json"
    assert payload["agent"] == "method_planner"
    assert payload["request"]["messages"] == request.messages
    assert payload["response"]["content"] == response.content
    assert payload["parsed_payload_path"] == str(tmp_path / "method_plan.json")
    assert "api_key" not in json.dumps(payload).lower()
    assert "sk-" not in json.dumps(payload)






def test_scientific_reviewer_prompt_includes_scope_policy() -> None:
    request = build_scientific_reviewer_request(
        review_evidence={"fit_diagnostics": {"status": "pass"}},
        review_scope={
            "requires_matrix_element_validation": False,
            "has_effective_mass_outputs": True,
        },
    )
    payload = json.loads(request.messages[1]["content"])

    assert request.response_format == "json_schema"
    assert request.json_schema is not None
    assert request.json_schema["name"] == "scientific_review_report"
    assert payload["review_scope"]["requires_matrix_element_validation"] is False
    assert payload["review_evidence"]["fit_diagnostics"]["status"] == "pass"
    assert request.json_schema["strict"] is True
    assert "do not warn about missing synthetic_matrix_elements.json" in request.messages[0]["content"]
