"""One SDK research loop; the Host owns tools, accounting and scientific state."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, replace
import inspect
import json
from typing import Any, Callable, Sequence

from agents import Agent, FunctionTool, Model, ModelSettings, OpenAIResponsesModel, RunConfig, RunHooks, Runner
from agents.agent_output import AgentOutputSchema, AgentOutputSchemaBase
from agents.retry import ModelRetrySettings
from agents.run_config import ToolExecutionConfig
from agents.tool import set_function_tool_failure_error_function
from agents.usage import Usage
from pydantic_core import to_jsonable_python


Observer = Callable[[dict[str, Any]], Any]


def _json(value):
    result = to_jsonable_python(value)
    json.dumps(result, allow_nan=False)
    return result


async def _drain_tasks(tasks):
    """Wait for owned tasks even if the caller receives another cancellation."""
    pending = [task for task in tasks if not task.done()]
    if not pending:
        return
    waiter = asyncio.gather(*pending, return_exceptions=True)
    while not waiter.done():
        try:
            await asyncio.shield(waiter)
        except asyncio.CancelledError:
            # A second cancellation cannot turn an active effect into a settled one.
            continue
    waiter.result()


@dataclass(frozen=True)
class ResearchAgentResult:
    output: Any
    usage: dict[str, Any]
    events: tuple[dict[str, Any], ...]


class _HostHooks(RunHooks):
    def __init__(self, role, observer, cancel_event):
        self.role, self.observer, self.cancel_event = role, observer, cancel_event
        self.events = []
        self.usage = Usage()
        self.model_calls = 0
        self.active = None
        self.effect_error = None
        self.stopping = False

    async def emit(self, kind, **fields):
        event = _json({"event": kind, "role": self.role, **fields})
        self.events.append(event)
        try:
            result = self.observer(event)
            if inspect.isawaitable(result):
                await result
        except BaseException as error:
            self.effect_error = error
            raise

    def check_cancelled(self):
        if self.stopping or (self.cancel_event is not None and self.cancel_event.is_set()):
            raise asyncio.CancelledError()

    async def on_llm_start(self, context, agent, system_prompt, input_items):
        self.check_cancelled()
        self.model_calls += 1
        fields = {"call_index": self.model_calls}
        schema = agent.output_type if isinstance(agent.output_type, AgentOutputSchemaBase) else AgentOutputSchema(agent.output_type)
        await self.emit("model_start", **fields, instructions=system_prompt, input=input_items,
            output_schema=None if schema.is_plain_text() else schema.json_schema(),
            tools=[{"name": tool.name, "description": tool.description, "parameters": tool.params_json_schema}
                   for tool in agent.tools], model_settings=agent.model_settings)
        # A rejected admission must not be reported as an executed model request.
        self.active = ("model", fields)

    async def on_llm_end(self, context, agent, response):
        self.usage.add(response.usage)
        self.active = None
        await self.emit("model_end", call_index=self.model_calls, usage=response.usage,
                        raw_usage=response.raw_usage, response_id=response.response_id,
                        request_id=response.request_id, output=response.to_input_items())

    async def on_tool_start(self, context, agent, tool):
        self.check_cancelled()
        fields = {"tool_name": tool.name, "call_id": context.tool_call_id}
        await self.emit("tool_start", **fields, arguments=context.tool_arguments)
        self.active = ("tool", fields)

    async def on_tool_end(self, context, agent, tool, result):
        self.active = None
        await self.emit("tool_end", tool_name=tool.name, call_id=context.tool_call_id, result=result)

    async def failed(self, error):
        fields = {"error_type": type(error).__name__, "cancelled": isinstance(error, asyncio.CancelledError)}
        if self.active is not None:
            kind, active = self.active
            self.active = None
            try:
                await self.emit(kind + "_error", **active, **fields)
            except BaseException:
                # Preserve the original failure; unsettled Host effects need Host recovery.
                error.add_note("The Host could not record the failed research effect.")
        try:
            await self.emit("run_error", **fields, usage=self.usage)
        except BaseException:
            error.add_note("The Host could not record the failed research turn.")


class ResearchAgentRuntime:
    """Run one specialist with explicitly supplied model, tools and Host callbacks.

    The observer is awaited before each model/tool effect and may refuse admission.
    No SDK session store, automatic handoff or hosted tool can acquire project authority.
    Host tools must be cancellation-aware async functions with JSON-compatible results.
    A failure is propagated unchanged after reporting partial usage to the observer.
    """

    def __init__(self, model: Model, *, max_output_tokens: int):
        if not isinstance(model, Model):
            raise TypeError("A constructed SDK Model is required; implicit provider credentials are forbidden.")
        if type(max_output_tokens) is not int or max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be a positive integer.")
        self.model, self.max_output_tokens = model, max_output_tokens
        self._client = None

    @classmethod
    def from_openai(cls, *, client, model: str, max_output_tokens: int):
        """Take ownership of an application-created client with transport retries disabled."""
        if client.max_retries != 0:
            raise ValueError("Research model clients must disable unaccounted transport retries.")
        runtime = cls(OpenAIResponsesModel(model=model, openai_client=client),
                      max_output_tokens=max_output_tokens)
        runtime._client = client
        return runtime

    async def aclose(self):
        """Close the owned transport in the same event loop used for the attempt."""
        if self._client is not None:
            await self._client.close()

    async def run(self, *, role: str, instructions: str, input: str | list[dict[str, Any]],
                  tools: Sequence[FunctionTool], output_type: Any, max_turns: int,
                  observer: Observer, cancel_event: asyncio.Event | None = None) -> ResearchAgentResult:
        if not role or not instructions or not callable(observer):
            raise ValueError("A role, instructions and Host observer are required.")
        if type(max_turns) is not int or max_turns <= 0:
            raise ValueError("The Host must provide a finite positive max_turns.")
        hooks = _HostHooks(role, observer, cancel_event)
        owned_tools = []
        tool_tasks = set()
        for tool in tools:
            if not isinstance(tool, FunctionTool) or tool.needs_approval is not False:
                raise ValueError("Research tools must be Host function tools without SDK-owned approvals.")
            if tool._is_agent_tool or tool._is_codex_tool:
                raise ValueError("Nested SDK agents cannot bypass Host model accounting.")
            if (not isinstance(tool.is_enabled, bool) or tool.tool_input_guardrails or tool.tool_output_guardrails):
                raise ValueError("Tool admission and checks belong to the Host.")
            # Copy per invocation; changing a shared tool would affect another project.
            owned = replace(tool, timeout_behavior="raise_exception")
            set_function_tool_failure_error_function(owned, None)
            invoke = owned.on_invoke_tool
            async def invoke_host_tool(context, arguments, invoke=invoke):
                # The SDK may detach a cancelled tool while its async cleanup runs.
                # Retain the complete owning task until Host settlement is safe.
                tool_tasks.add(asyncio.current_task())
                try:
                    return await invoke(context, arguments)
                except BaseException as error:
                    hooks.effect_error = error
                    raise
            owned.on_invoke_tool = invoke_host_tool
            owned_tools.append(owned)
        settings = ModelSettings(max_tokens=self.max_output_tokens, store=False,
                                 parallel_tool_calls=False, preserve_raw_usage=True,
                                 retry=ModelRetrySettings(max_retries=0))
        agent = Agent(name=role, instructions=instructions, model=self.model,
                      model_settings=settings, tools=owned_tools, output_type=output_type)
        config = RunConfig(tracing_disabled=True, trace_include_sensitive_data=False,
                           tool_execution=ToolExecutionConfig(max_function_tool_concurrency=1),
                           tool_name_collision_policy="error")
        run_task = cancel_task = None
        try:
            hooks.check_cancelled()
            await hooks.emit("run_start")
            run_task = asyncio.create_task(Runner.run(agent, input, max_turns=max_turns,
                                                     hooks=hooks, run_config=config))
            if cancel_event is not None:
                async def cancel_on_signal():
                    await cancel_event.wait()
                    hooks.stopping = True
                    run_task.cancel()
                cancel_task = asyncio.create_task(cancel_on_signal())
            result = await asyncio.shield(run_task)
            hooks.check_cancelled()
            if result.interruptions:
                raise RuntimeError("Research SDK interruptions cannot replace a Host-owned pause.")
            output = _json(result.final_output)
            usage = _json(hooks.usage)
            await hooks.emit("run_end", usage=usage)
            return ResearchAgentResult(output, usage, tuple(hooks.events))
        except BaseException as error:
            hooks.stopping = True
            if run_task is not None and not run_task.done():
                run_task.cancel()
                await _drain_tasks([run_task])
            await _drain_tasks(tool_tasks)
            original = (error if isinstance(error, asyncio.CancelledError) else
                        hooks.effect_error if hooks.effect_error is not None else error)
            await hooks.failed(original)
            if original is not error:
                # The SDK wraps local tool errors; retain the Host's original classification.
                raise original from None
            raise
        finally:
            if cancel_task is not None:
                cancel_task.cancel()
                with suppress(asyncio.CancelledError):
                    await cancel_task
            if run_task is not None and not run_task.done():
                run_task.cancel()
                await _drain_tasks([run_task])
            await _drain_tasks(tool_tasks)

    def run_sync(self, **kwargs) -> ResearchAgentResult:
        """Synchronous Host entry; async hosts should await run instead."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Use await ResearchAgentRuntime.run() inside an active event loop.")
        return asyncio.run(self.run(**kwargs))
