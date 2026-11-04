"""One SDK research loop; the Host owns tools, accounting and scientific state."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, replace
import inspect
import json
import math
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
    def __init__(self, role, observer, cancel_event, model_call_limit, allowance):
        self.role, self.observer, self.cancel_event = role, observer, cancel_event
        self.events = []
        self.usage = Usage()
        self.model_calls = 0
        self.model_call_limit = model_call_limit
        self.active = None
        self.effect_error = None
        self.stopping = False
        self.allowance = allowance
        self.deferred_calls = set()
        self.tool_timeouts = {}
        self.request_prepared = False
        self.final_model_dispatched = False

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

    def prepare_model_settings(self, agent, *, count_pending=False):
        # A final model allowance must produce a conclusion, not another tool loop.
        closing = self.model_calls + 1 >= self.model_call_limit
        if self.allowance is not None:
            closing |= self.allowance.must_finalize(count_pending=count_pending)
        agent.model_settings.tool_choice = 'none' if closing else None

    async def start_model(self, *, operation=None, **request):
        from lqcd_agent.control.budget import BudgetExhausted
        self.check_cancelled()
        # A compact call must leave room for the scientific response it enables.
        required = 2 if operation == "compact" else 1
        if self.model_calls + required > self.model_call_limit:
            raise BudgetExhausted("Research role cannot fund this model effect and its conclusion")
        self.model_calls += 1
        fields = {"call_index": self.model_calls}
        if operation is not None:
            fields["operation"] = operation
        await self.emit("model_start", **fields, **request)
        # A rejected admission must not be reported as an executed model request.
        self.active = ("model", fields)
        self.check_cancelled()
        return fields

    async def on_llm_start(self, context, agent, system_prompt, input_items):
        # The filter already counted this exact tool policy. Transport timeouts
        # may change here, but changing tool_choice would invalidate that count.
        if not self.request_prepared:
            self.prepare_model_settings(agent)
        self.request_prepared = False
        if self.allowance is not None:
            agent.model_settings.timeout = self.allowance.timeout_seconds('model',
                closing=agent.model_settings.tool_choice == 'none')
        self.final_model_dispatched = agent.model_settings.tool_choice == 'none'
        schema = agent.output_type if isinstance(agent.output_type, AgentOutputSchemaBase) else AgentOutputSchema(agent.output_type)
        await self.start_model(instructions=system_prompt, input=input_items,
            output_schema=None if schema.is_plain_text() else schema.json_schema(),
            tools=[{"name": tool.name, "description": tool.description, "parameters": tool.params_json_schema}
                   for tool in agent.tools], model_settings=agent.model_settings,
            **({'timeout_seconds': agent.model_settings.timeout} if self.allowance is not None else {}))

    async def on_llm_end(self, context, agent, response):
        self.usage.add(response.usage)
        self.active = None
        await self.emit("model_end", call_index=self.model_calls, usage=response.usage,
                        raw_usage=response.raw_usage, response_id=response.response_id,
                        request_id=response.request_id, output=response.to_input_items())

    async def on_tool_start(self, context, agent, tool):
        from lqcd_agent.control.budget import BudgetExhausted
        self.check_cancelled()
        if self.final_model_dispatched or self.model_calls >= self.model_call_limit:
            error = BudgetExhausted('Final research turn cannot start another evidence read')
            self.effect_error = error
            raise error
        fields = {"tool_name": tool.name, "call_id": context.tool_call_id}
        if self.allowance is not None:
            try:
                timeout = self.allowance.tool_timeout()
                admitted = timeout is not None
            except BaseException as error:
                self.effect_error = error
                raise
            if not admitted:
                self.deferred_calls.add(context.tool_call_id)
                await self.emit('tool_not_executed', **fields, status='not_executed',
                                reason='finalization_budget_reserved')
                return
            self.tool_timeouts[context.tool_call_id] = timeout
            fields['timeout_seconds'] = timeout
        await self.emit("tool_start", **fields, arguments=context.tool_arguments)
        self.active = ("tool", fields)

    async def on_tool_end(self, context, agent, tool, result):
        if context.tool_call_id in self.deferred_calls:
            self.deferred_calls.remove(context.tool_call_id)
            return
        self.tool_timeouts.pop(context.tool_call_id, None)
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
        self.request_timeout_seconds = None

    @classmethod
    def from_openai(cls, *, client, model: str, max_output_tokens: int):
        """Take ownership of an application-created client with transport retries disabled."""
        if client.max_retries != 0:
            raise ValueError("Research model clients must disable unaccounted transport retries.")
        timeout = getattr(client.timeout, "read", client.timeout)
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Research model clients must provide a finite positive request timeout.")
        runtime = cls(OpenAIResponsesModel(model=model, openai_client=client),
                      max_output_tokens=max_output_tokens)
        runtime._client = client
        runtime.request_timeout_seconds = timeout
        return runtime

    async def aclose(self):
        """Close the owned transport in the same event loop used for the attempt."""
        if self._client is not None:
            await self._client.close()

    async def run(self, *, role: str, instructions: str, input: str | list[dict[str, Any]],
                  tools: Sequence[FunctionTool], output_type: Any, max_turns: int,
                  observer: Observer, cancel_event: asyncio.Event | None = None,
                  allowance=None) -> ResearchAgentResult:
        if not role or not instructions or not callable(observer):
            raise ValueError("A role, instructions and Host observer are required.")
        if type(max_turns) is not int or max_turns <= 0:
            raise ValueError("The Host must provide a finite positive max_turns.")
        hooks = _HostHooks(role, observer, cancel_event, max_turns, allowance)
        owned_tools = []
        tool_tasks = set()
        for tool in tools:
            if not isinstance(tool, FunctionTool) or tool.needs_approval is not False:
                raise ValueError("Research tools must be Host function tools without SDK-owned approvals.")
            if tool._is_agent_tool or tool._is_codex_tool:
                raise ValueError("Nested SDK agents cannot bypass Host model accounting.")
            if (not isinstance(tool.is_enabled, bool) or tool.tool_input_guardrails or tool.tool_output_guardrails
                    or tool.custom_data_extractor is not None or tool.output_json_schema is not None
                    or tool._output_type_adapter is not None):
                raise ValueError("Tool admission and checks belong to the Host.")
            if tool.is_enabled is False:
                continue
            # Copy per invocation; changing a shared tool would affect another project.
            limits = [limit for limit in (self.request_timeout_seconds, tool.timeout_seconds) if limit is not None]
            tool_timeout = min(limits) if limits else None
            owned = replace(tool, timeout_seconds=None, timeout_behavior="raise_exception")
            set_function_tool_failure_error_function(owned, None)
            invoke = owned.on_invoke_tool
            async def invoke_host_tool(context, arguments, invoke=invoke, timeout_seconds=tool_timeout):
                hooks.check_cancelled()
                if context.tool_call_id in hooks.deferred_calls:
                    return json.dumps({'status': 'not_executed', 'reason': 'finalization_budget_reserved'})
                admitted_timeout = hooks.tool_timeouts.get(context.tool_call_id)
                if admitted_timeout is not None:
                    timeout_seconds = min(timeout_seconds, admitted_timeout) if timeout_seconds is not None else admitted_timeout
                # The SDK may detach a cancelled tool while its async cleanup runs.
                # Retain the complete owning task until Host settlement is safe.
                tool_tasks.add(asyncio.current_task())
                try:
                    # One timeout owner preserves shorter tool deadlines and
                    # reports TimeoutError after cooperative tool cleanup.
                    async with asyncio.timeout(timeout_seconds):
                        return await invoke(context, arguments)
                except BaseException as error:
                    hooks.effect_error = error
                    raise
            owned.on_invoke_tool = invoke_host_tool
            owned_tools.append(owned)
        settings = ModelSettings(max_tokens=self.max_output_tokens, store=False, timeout=self.request_timeout_seconds,
                                 parallel_tool_calls=True, preserve_raw_usage=True, truncation="disabled",
                                 retry=ModelRetrySettings(max_retries=0))
        agent = Agent(name=role, instructions=instructions, model=self.model,
                      model_settings=settings, tools=owned_tools, output_type=output_type, reset_tool_choice=False)
        config = RunConfig(tracing_disabled=True, trace_include_sensitive_data=False,
                           tool_execution=ToolExecutionConfig(max_function_tool_concurrency=1),
                           tool_name_collision_policy="error")
        if self._client is not None:
            from .context_window import ContextWindow
            pinned = [{'role': 'user', 'content': input}] if isinstance(input, str) else input
            config.call_model_input_filter = ContextWindow(self._client, self.model, hooks, pinned,
                                                          request_timeout_seconds=self.request_timeout_seconds)
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
