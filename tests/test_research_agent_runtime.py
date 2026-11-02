"""Exercise the actual SDK runner with deterministic model responses, never live API calls."""
import asyncio
import json

import pytest
import httpx
from agents import Agent, FunctionTool, Model, function_tool
from agents.exceptions import MaxTurnsExceeded, ModelBehaviorError
from agents.items import ModelResponse
from agents.usage import Usage
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from pydantic import BaseModel

from lqcd_agent.research.agent_runtime import ResearchAgentRuntime


class Finding(BaseModel):
    conclusion: str


class ScriptedModel(Model):
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.requests = []

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, **kwargs):
        assert not handoffs and tracing.is_disabled()
        assert model_settings.store is False
        assert model_settings.parallel_tool_calls is True
        assert model_settings.preserve_raw_usage is True
        assert model_settings.retry.max_retries == 0
        assert kwargs["previous_response_id"] is None and kwargs["conversation_id"] is None
        self.requests.append(input)
        output = next(self.outputs)
        if isinstance(output, BaseException):
            raise output
        return ModelResponse(output=output, usage=Usage(requests=1, input_tokens=10,
                             output_tokens=3, total_tokens=13), response_id=f"response-{len(self.requests)}")

    async def stream_response(self, *args, **kwargs):
        raise AssertionError("This adapter uses the awaited SDK runner.")
        yield


def message(conclusion):
    return ResponseOutputMessage(id="message-1", role="assistant", status="completed",
        content=[ResponseOutputText(type="output_text", text=json.dumps({"conclusion": conclusion}), annotations=[])],
        type="message")


def call(call_id="read-1"):
    return ResponseFunctionToolCall(type="function_call", name="read_evidence", arguments='{"reference":"evidence-1"}',
                                    call_id=call_id)


def evidence_tool(handler):
    return FunctionTool(name="read_evidence", description="Read verified project evidence.",
        params_json_schema={"type": "object", "properties": {"reference": {"type": "string"}},
                            "required": ["reference"], "additionalProperties": False},
        on_invoke_tool=handler)


def arguments(observer, tools=()):
    return {"role": "reviewer", "instructions": "Review the supplied evidence.",
            "input": "Check the normalization.", "tools": tools, "output_type": Finding,
            "max_turns": 3, "observer": observer}


def test_sdk_tool_loop_is_host_accounted_and_has_structured_output():
    events, invoked = [], []
    async def read(context, raw):
        assert events[-1]["event"] == "tool_start"
        assert context.tool_call_id == "read-1"
        invoked.append(json.loads(raw)["reference"])
        return {"reference": "evidence-1", "normalization": "not established"}
    model = ScriptedModel([[call()], [message("More evidence is required.")]])
    result = ResearchAgentRuntime(model, max_output_tokens=512).run_sync(**arguments(events.append, [evidence_tool(read)]))
    assert result.output == {"conclusion": "More evidence is required."}
    assert invoked == ["evidence-1"]
    assert result.usage["requests"] == 2 and result.usage["total_tokens"] == 26
    assert [event["event"] for event in events] == ["run_start", "model_start", "model_end",
        "tool_start", "tool_end", "model_start", "model_end", "run_end"]
    assert result.events == tuple(events)
    json.dumps(result.events, allow_nan=False)
    assert any(item.get("type") == "function_call_output" for item in model.requests[1])


@pytest.mark.parametrize("deny_at", ["model_start", "tool_start"])
def test_host_admission_rejection_prevents_effect_and_preserves_exception(deny_at):
    events, invoked = [], []
    denied = PermissionError("Host refused this effect")
    def observe(event):
        events.append(event)
        if event["event"] == deny_at:
            raise denied
    async def read(context, raw):
        invoked.append(True)
        return "evidence"
    model = ScriptedModel([[call()], [message("unexpected")]])
    with pytest.raises(PermissionError) as captured:
        ResearchAgentRuntime(model, max_output_tokens=512).run_sync(**arguments(observe, [evidence_tool(read)]))
    assert captured.value is denied and not invoked
    assert len(model.requests) == (0 if deny_at == "model_start" else 1)
    assert not any(event["event"] == deny_at.replace("_start", "_error") for event in events)


def test_sdk_default_tool_error_handler_cannot_turn_failure_into_evidence():
    failure = ValueError("invalid scientific evidence")
    @function_tool
    async def read_evidence(reference: str) -> str:
        """Read the requested evidence."""
        raise failure
    events = []
    model = ScriptedModel([[call()], [message("incorrectly continued")]])
    with pytest.raises(ValueError) as captured:
        ResearchAgentRuntime(model, max_output_tokens=512).run_sync(**arguments(events.append, [read_evidence]))
    assert captured.value is failure
    assert len(model.requests) == 1
    assert [event["event"] for event in events][-2:] == ["tool_error", "run_error"]
    assert events[-1]["usage"]["requests"] == 1
    assert not any(event["event"] == "tool_end" for event in events)


def test_multiple_tools_execute_serially_even_if_model_emits_them_together():
    active = 0
    observed = []
    async def read(context, raw):
        nonlocal active
        active += 1
        assert active == 1
        observed.append(context.tool_call_id)
        await asyncio.sleep(0)
        active -= 1
        return "evidence"
    events = []
    model = ScriptedModel([[call("first"), call("second")], [message("Checked both.")]])
    result = ResearchAgentRuntime(model, max_output_tokens=512).run_sync(**arguments(events.append, [evidence_tool(read)]))
    assert observed == ["first", "second"]
    assert result.usage["requests"] == 2
    assert [e["event"] for e in events if e["event"].startswith("tool_")] == ["tool_start", "tool_end"] * 2


def test_model_failure_is_reported_without_implicit_retry():
    failure = ConnectionError("transport failure")
    events = []
    model = ScriptedModel([failure, [message("unexpected retry")]])
    with pytest.raises(ConnectionError) as captured:
        ResearchAgentRuntime(model, max_output_tokens=512).run_sync(**arguments(events.append))
    assert captured.value is failure and len(model.requests) == 1
    assert [e["event"] for e in events] == ["run_start", "model_start", "model_error", "run_error"]


def test_host_turn_limit_stops_after_completed_tool_without_repeating_it():
    invoked = []
    async def read(context, raw):
        invoked.append(context.tool_call_id)
        return "evidence"
    events = []
    model = ScriptedModel([[call()], [message("beyond budget")]])
    options = arguments(events.append, [evidence_tool(read)]) | {"max_turns": 1}
    with pytest.raises(MaxTurnsExceeded):
        ResearchAgentRuntime(model, max_output_tokens=512).run_sync(**options)
    assert invoked == ["read-1"] and len(model.requests) == 1
    assert events[-1]["event"] == "run_error" and events[-1]["usage"]["requests"] == 1


def test_cancellation_interrupts_active_model_and_reports_unfinished_effect():
    async def check():
        entered, cancelled = asyncio.Event(), asyncio.Event()
        released = []
        class WaitingModel(ScriptedModel):
            async def get_response(self, *args, **kwargs):
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    released.append(True)
        model, events = WaitingModel([]), []
        runtime = ResearchAgentRuntime(model, max_output_tokens=512)
        task = asyncio.create_task(runtime.run(**arguments(events.append), cancel_event=cancelled))
        await asyncio.wait_for(entered.wait(), 3)
        cancelled.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert released == [True]
        assert [e["event"] for e in events][-2:] == ["model_error", "run_error"]
        assert events[-1]["cancelled"] is True
    asyncio.run(check())


def test_cancellation_during_tool_waits_for_tool_cleanup():
    async def check():
        entered, cancelled = asyncio.Event(), asyncio.Event()
        released, events = [], []
        async def read(context, raw):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                released.append(True)
        model = ScriptedModel([[call()], [message("unexpected continuation")]])
        runtime = ResearchAgentRuntime(model, max_output_tokens=512)
        task = asyncio.create_task(runtime.run(**arguments(events.append, [evidence_tool(read)]), cancel_event=cancelled))
        await asyncio.wait_for(entered.wait(), 3)
        cancelled.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert released == [True] and len(model.requests) == 1
        assert [e["event"] for e in events][-2:] == ["tool_error", "run_error"]
    asyncio.run(check())


def test_application_client_must_disable_transport_retries():
    async def check():
        async with AsyncOpenAI(api_key="offline-test", max_retries=2) as client:
            with pytest.raises(ValueError, match="unaccounted transport retries"):
                ResearchAgentRuntime.from_openai(client=client, model="test-model", max_output_tokens=512)
        async with AsyncOpenAI(api_key="offline-test", max_retries=0) as client:
            runtime = ResearchAgentRuntime.from_openai(client=client, model="test-model", max_output_tokens=512)
            assert runtime.model.model == "test-model"
    asyncio.run(check())


@pytest.mark.parametrize("provider_usage", [None, {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10,
    "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}])
def test_openai_adapter_preserves_usage_presence_without_a_network_call(provider_usage):
    async def check():
        requests, events = [], []
        async def unused_read(context, raw):
            raise AssertionError("The provider returned a conclusion without calling a tool")
        async def transport(request):
            requests.append(json.loads(request.content))
            response = Response(id="response-1", created_at=0, model="test-model", object="response",
                output=[message("Supported under stated conditions.")], parallel_tool_calls=True,
                tool_choice="auto", tools=[], status="completed", usage=provider_usage)
            return httpx.Response(200, json=response.model_dump(mode="json"))
        async with AsyncOpenAI(api_key="offline-test", max_retries=0,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport))) as client:
            runtime = ResearchAgentRuntime.from_openai(client=client, model="test-model", max_output_tokens=512)
            result = await runtime.run(**arguments(events.append, [evidence_tool(unused_read)]))
        assert result.output["conclusion"] == "Supported under stated conditions."
        assert len(requests) == 1 and requests[0]["store"] is False
        assert requests[0]["max_output_tokens"] == 512 and "temperature" not in requests[0]
        assert requests[0]["parallel_tool_calls"] is True
        assert requests[0]["tools"][0]["name"] == "read_evidence"
        assert requests[0]["text"]["format"]["type"] == "json_schema"
        assert requests[0]["text"]["format"]["strict"] is True
        ended = next(event for event in events if event["event"] == "model_end")
        assert ended["raw_usage"] == provider_usage
        assert result.usage["requests"] == 1
    asyncio.run(check())


@pytest.mark.parametrize("status", ["incomplete", "failed"])
def test_incomplete_provider_response_cannot_become_a_scientific_result(status):
    async def check():
        events = []
        async def transport(request):
            response = Response(id="response-1", created_at=0, model="test-model", object="response",
                output=[message("This valid JSON must still be rejected.")], parallel_tool_calls=False,
                tool_choice="auto", tools=[], status=status, incomplete_details={"reason": "max_output_tokens"})
            return httpx.Response(200, json=response.model_dump(mode="json"))
        async with AsyncOpenAI(api_key="offline-test", max_retries=0,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport))) as client:
            runtime = ResearchAgentRuntime.from_openai(client=client, model="test-model", max_output_tokens=512)
            with pytest.raises(ModelBehaviorError):
                await runtime.run(**arguments(events.append))
        assert [e["event"] for e in events] == ["run_start", "model_start", "model_error", "run_error"]
    asyncio.run(check())



def test_nested_sdk_agents_cannot_hide_model_calls_from_host():
    model = ScriptedModel([[message("Must not be called.")]])
    nested = Agent(name="hidden-worker", model=model).as_tool(tool_name="nested", tool_description="Nested agent.")
    with pytest.raises(ValueError, match="Nested SDK agents"):
        ResearchAgentRuntime(model, max_output_tokens=512).run_sync(**arguments(lambda event: None, [nested]))
    assert model.requests == []


@pytest.mark.parametrize('signal', ['event', 'caller'])
def test_cancellation_waits_for_async_tool_cleanup_even_after_repeated_cancel(signal):
    async def check():
        entered, cleanup_started, release, cancelled = (asyncio.Event() for _ in range(4))
        events, finished = [], []
        async def read(context, raw):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await release.wait()
                finished.append(True)
        model = ScriptedModel([[call()], [message('Must not publish after cancellation.')]])
        runtime = ResearchAgentRuntime(model, max_output_tokens=512)
        task = asyncio.create_task(runtime.run(**arguments(events.append, [evidence_tool(read)]),
                                              cancel_event=cancelled))
        await asyncio.wait_for(entered.wait(), 3)
        if signal == 'event':
            cancelled.set()
        else:
            task.cancel()
        await asyncio.wait_for(cleanup_started.wait(), 3)
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and not finished
        assert not any(event['event'] in ('tool_end', 'tool_error', 'run_end') for event in events)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert finished == [True] and len(model.requests) == 1
        assert [event['event'] for event in events][-2:] == ['tool_error', 'run_error']
        assert not any(event['event'] == 'run_end' for event in events)
    asyncio.run(check())


def test_caller_cancellation_stops_new_tools_even_if_model_suppresses_cancellation():
    async def check():
        entered = asyncio.Event()
        invoked, events = [], []
        class SuppressingModel(ScriptedModel):
            async def get_response(self, *args, **kwargs):
                entered.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    return ModelResponse(output=[call()], usage=Usage(requests=1), response_id='after-cancel')
        async def read(context, raw):
            invoked.append(True)
            return 'Must not run'
        runtime = ResearchAgentRuntime(SuppressingModel([]), max_output_tokens=512)
        task = asyncio.create_task(runtime.run(**arguments(events.append, [evidence_tool(read)])))
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert not invoked
        assert not any(event['event'] in ('tool_start', 'tool_end', 'run_end') for event in events)
        assert events[-1]['event'] == 'run_error' and events[-1]['cancelled'] is True
    asyncio.run(check())
