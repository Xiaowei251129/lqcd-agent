"""Actual SDK wire admission and compaction with private-free HTTP fixtures."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json

import httpx
from openai import AsyncOpenAI, InternalServerError
from openai.types.responses import Response
import pytest

from lqcd_agent.llm.prompts import ContextLimitError
from lqcd_agent.research.agent_runtime import ResearchAgentRuntime
from lqcd_agent.research import context_window
from lqcd_agent.settings import ApplicationSettings
from tests.test_research_agent_runtime import arguments, call, evidence_tool, message


PINNED = [{'role': 'user', 'content': json.dumps({
    'unit': 'lattice units, not GeV',
    'warning': 'Original paired resampling indices are unavailable.',
    'counterexample': 'The short-window fit disagrees with the reference.',
    'unresolved': 'Determine whether the covariance treatment changes the result.',
    'source': 'sha256:fixture-evidence-only',
})}]
USAGE = {'input_tokens': 10, 'output_tokens': 3, 'total_tokens': 13,
         'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
         'output_tokens_details': {'reasoning_tokens': 0}}


class Wire:
    def __init__(self, counts, outputs, *, compact_status=200, carriers=True, wait_at=None):
        self.counts, self.outputs = iter(counts), iter(outputs)
        self.compact_status, self.carriers, self.wait_at = compact_status, carriers, wait_at
        self.requests = []
        self.compactions = 0
        self.entered, self.released = asyncio.Event(), []

    async def __call__(self, request):
        kind = ('count' if request.url.path.endswith('/input_tokens') else
                'compact' if request.url.path.endswith('/compact') else 'generate')
        body = json.loads(request.content)
        self.requests.append((kind, body))
        if kind == self.wait_at:
            self.entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.released.append(kind)
        if kind == 'count':
            return httpx.Response(200, json={'object': 'response.input_tokens',
                                           'input_tokens': next(self.counts)})
        if kind == 'compact':
            self.compactions += 1
            if self.compact_status != 200:
                return httpx.Response(self.compact_status,
                    json={'error': {'message': 'Fixture compaction failure', 'type': 'server_error'}})
            output = [{'type': 'compaction', 'id': f'compact-{self.compactions}',
                       'encrypted_content': f'fixture-ciphertext-{self.compactions}'}] if self.carriers else []
            return httpx.Response(200, json={'id': f'compaction-response-{self.compactions}',
                'created_at': 0, 'object': 'response.compaction', 'output': output, 'usage': USAGE})
        response = Response(id=f'response-{len(self.requests)}', created_at=0, model='test-model',
            object='response', output=next(self.outputs), parallel_tool_calls=True,
            tool_choice='auto', tools=[], status='completed', usage=USAGE)
        return httpx.Response(200, json=response.model_dump(mode='json'))

    def bodies(self, kind):
        return [body for name, body in self.requests if name == kind]


async def run(wire, events, *, observer=None, cancelled=None):
    async def read(context, raw):
        return {'evidence': context.tool_call_id, 'finding': 'Synthetic counterevidence remains unresolved.'}
    async with AsyncOpenAI(api_key='offline-test', max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(wire))) as client:
        runtime = ResearchAgentRuntime.from_openai(client=client, model='test-model', max_output_tokens=512)
        return await runtime.run(**(arguments(observer or events.append, [evidence_tool(read),
                replace(evidence_tool(read), name='disabled_evidence', is_enabled=False)]) |
            {'input': deepcopy(PINNED), 'max_turns': 5}), cancel_event=cancelled)


@pytest.fixture
def small_window(monkeypatch):
    monkeypatch.setattr(context_window, 'INPUT_TOKEN_LIMIT', 100)
    monkeypatch.setattr(context_window, 'COMPACT_TOKEN_LIMIT', 80)


def test_sdk_compacts_twice_without_resurrecting_old_history_and_keeps_scientific_state(small_window):
    wire, events = Wire([20, 90, 30, 90, 30], [[call('first')], [call('second')], [message('Need evidence.')]]), []
    result = asyncio.run(run(wire, events))
    assert result.output == {'conclusion': 'Need evidence.'}
    assert [kind for kind, _ in wire.requests] == [
        'count', 'generate', 'count', 'compact', 'count', 'generate', 'count', 'compact', 'count', 'generate']
    generated, counted, compacted = (wire.bodies(kind) for kind in ('generate', 'count', 'compact'))
    # Count the SDK's complete serialized request, including structured-output and tool schemas.
    for measured, sent in zip((counted[0], counted[2], counted[4]), generated):
        assert measured == {key: sent[key] for key in measured}
        assert measured['input'][:len(PINNED)] == PINNED
        assert [tool['name'] for tool in measured['tools']] == ['read_evidence']
        assert measured['text']['format']['type'] == 'json_schema'
        assert measured['instructions'] == 'Review the supplied evidence.'
        assert measured['truncation'] == 'disabled'
    assert generated[1]['input'] == PINNED + [{'type': 'compaction', 'id': 'compact-1',
        'encrypted_content': 'fixture-ciphertext-1'}]
    assert generated[2]['input'] == PINNED + [{'type': 'compaction', 'id': 'compact-2',
        'encrypted_content': 'fixture-ciphertext-2'}]
    second_history = compacted[1]['input']
    assert any(item.get('id') == 'compact-1' for item in second_history)
    assert any(item.get('call_id') == 'second' for item in second_history)
    assert not any(item.get('call_id') == 'first' for item in second_history)
    summaries = [event for event in events if event['event'] == 'context_compacted']
    assert [(e['input_tokens_before'], e['input_tokens_after']) for e in summaries] == [(90, 30), (90, 30)]
    assert all(e['protected_items'] == len(PINNED) for e in summaries)
    assert len([e for e in events if e['event'] == 'model_start' and e.get('operation') == 'compact']) == 2
    assert result.usage['requests'] == 5 and result.usage['total_tokens'] == 65


@pytest.mark.parametrize('after_tool', [False, True])
def test_256k_input_ceiling_rejects_generation_and_compaction(after_tool):
    wire = Wire([20, 256_001] if after_tool else [256_001], [[call()], [message('Must not run.')]])
    events = []
    with pytest.raises(ContextLimitError, match='input (token )?limit'):
        asyncio.run(run(wire, events))
    assert len(wire.bodies('generate')) == int(after_tool)
    assert not wire.bodies('compact')
    assert events[-1]['event'] == 'run_error'


def test_protected_state_above_soft_threshold_is_not_lossily_compacted(small_window):
    wire, events = Wire([90], [[message('Required state read.')]]), []
    asyncio.run(run(wire, events))
    assert wire.bodies('generate')[0]['input'] == PINNED
    assert not wire.bodies('compact')
    pressure, = [e for e in events if e['event'] == 'context_pressure']
    assert pressure['reason'] == 'protected_state_only' and pressure['input_tokens'] == 90


@pytest.mark.parametrize('failure', ['http', 'missing_carrier', 'no_headroom'])
def test_failed_compaction_stops_without_retry_or_another_generation(small_window, failure):
    wire = Wire([20, 90, 85], [[call()], [message('Must not run.')]],
                compact_status=500 if failure == 'http' else 200, carriers=failure != 'missing_carrier')
    events = []
    with pytest.raises(InternalServerError if failure == 'http' else ContextLimitError):
        asyncio.run(run(wire, events))
    assert len(wire.bodies('compact')) == len(wire.bodies('generate')) == 1
    assert not any(e['event'] in ('run_end', 'context_compacted') for e in events)
    assert events[-1]['event'] == 'run_error'


@pytest.mark.parametrize('denied_at', ['count', 'compact', 'recount'])
def test_host_can_refuse_count_compact_and_recount_before_the_http_effect(small_window, denied_at):
    wire, events = Wire([20, 90, 30], [[call()], [message('Must not run.')]]), []
    denial = PermissionError('Host rejected the context operation')
    counts = 0
    def observe(event):
        nonlocal counts
        events.append(event)
        if event['event'] == 'tool_start' and event.get('tool_name') == 'context_token_count':
            counts += 1
            if denied_at == 'count' or denied_at == 'recount' and counts == 3:
                raise denial
        if denied_at == 'compact' and event['event'] == 'model_start' and event.get('operation') == 'compact':
            raise denial
    with pytest.raises(PermissionError) as caught:
        asyncio.run(run(wire, events, observer=observe))
    assert caught.value is denial
    assert len(wire.bodies('count')) == (0 if denied_at == 'count' else 2)
    assert len(wire.bodies('compact')) == int(denied_at == 'recount')
    assert len(wire.bodies('generate')) == int(denied_at != 'count')
    assert events[-1]['event'] == 'run_error'
    assert not any(e['event'] in ('model_error', 'tool_error') for e in events)


@pytest.mark.parametrize('cancel_at', ['count', 'compact'])
def test_cancellation_drains_context_http_operation_before_returning(small_window, cancel_at):
    async def check():
        wire = Wire([20, 90, 30], [[call()], [message('Must not run.')]], wait_at=cancel_at)
        events, cancelled = [], asyncio.Event()
        task = asyncio.create_task(run(wire, events, cancelled=cancelled))
        await asyncio.wait_for(wire.entered.wait(), 5)
        cancelled.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert wire.released == [cancel_at]
        assert len(wire.bodies('generate')) == int(cancel_at == 'compact')
        assert events[-1]['event'] == 'run_error' and events[-1]['cancelled']
        failure = events[-2]
        assert failure['event'] == ('tool_error' if cancel_at == 'count' else 'model_error')
        assert failure['cancelled']
        if cancel_at == 'compact':
            assert failure['operation'] == 'compact'
    asyncio.run(check())


@pytest.mark.parametrize('blocked_at', ['count', 'compact', 'generate', 'tool', 'shorter_tool'])
def test_effect_timeout_drains_cleanup_and_prevents_later_requests(small_window, blocked_at):
    from agents.exceptions import ModelTimeoutError

    async def check():
        phase = 'tool' if blocked_at == 'shorter_tool' else blocked_at
        request_timeout = 10 if blocked_at == 'shorter_tool' else 0.05
        cleaning, finish_cleanup = asyncio.Event(), asyncio.Event()
        released, events = [], []
        wire = Wire([20, 90, 30], [[call()], [message('Must not run.')]])

        async def blocked():
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                # The native model deadline may cancel twice. Its owner must
                # drain the transport's cooperative cleanup before settlement.
                while not finish_cleanup.is_set():
                    try:
                        await finish_cleanup.wait()
                    except asyncio.CancelledError:
                        pass
                released.append(phase)

        async def transport(request):
            kind = ('count' if request.url.path.endswith('/input_tokens') else
                    'compact' if request.url.path.endswith('/compact') else 'generate')
            if kind == phase:
                wire.requests.append((kind, json.loads(request.content)))
                await blocked()
            return await wire(request)

        async def read(context, raw):
            if phase == 'tool':
                await blocked()
            return {'evidence': 'fixture'}

        def observe(event):
            if event['event'] in ('tool_error', 'model_error', 'run_error'):
                assert released == [phase]
            events.append(event)

        tool = evidence_tool(read)
        if blocked_at == 'shorter_tool':
            tool = replace(tool, timeout_seconds=0.05)
        async with AsyncOpenAI(api_key='offline-test', max_retries=0, timeout=request_timeout,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport))) as client:
            runtime = ResearchAgentRuntime.from_openai(client=client, model='test-model', max_output_tokens=512)
            task = asyncio.create_task(runtime.run(**(arguments(observe, [tool]) |
                {'input': deepcopy(PINNED), 'max_turns': 5})))
            try:
                await asyncio.wait_for(cleaning.wait(), 1)
                assert not task.done()
                finish_cleanup.set()
                with pytest.raises(ModelTimeoutError if phase == 'generate' else TimeoutError):
                    await asyncio.wait_for(task, 2)
            finally:
                finish_cleanup.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        expected = {'count': ['count'], 'generate': ['count', 'generate'],
            'compact': ['count', 'generate', 'count', 'compact'], 'tool': ['count', 'generate']}
        assert [kind for kind, _ in wire.requests] == expected[phase]
        failure = events[-2]
        assert failure['event'] == ('tool_error' if phase in ('count', 'tool') else 'model_error')
        assert failure['error_type'] == ('ModelTimeoutError' if phase == 'generate' else 'TimeoutError')
        assert not failure['cancelled']
        assert events[-1]['event'] == 'run_error' and not events[-1]['cancelled']
    asyncio.run(check())


@pytest.mark.parametrize('compact', [False, True])
def test_final_allowance_forces_conclusion_on_counted_wire_even_after_compact(small_window, compact):
    async def check():
        wire = Wire([20, 90, 30] if compact else [20, 30], [[call()], [message('Evidence remains unresolved.')]])
        events, reads = [], []
        async def read(context, raw):
            reads.append(True)
            return {'finding': 'Unresolved covariance choice.'}
        async with AsyncOpenAI(api_key='offline-test', max_retries=0,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(wire))) as client:
            runtime = ResearchAgentRuntime.from_openai(client=client, model='test-model', max_output_tokens=512)
            result = await runtime.run(**(arguments(events.append, [evidence_tool(read)]) |
                {'input': deepcopy(PINNED), 'max_turns': 3 if compact else 2}))
        assert result.output['conclusion'] == 'Evidence remains unresolved.' and reads == [True]
        assert wire.bodies('generate')[-1]['tool_choice'] == 'none'
        assert wire.bodies('count')[-1] == {key: wire.bodies('generate')[-1][key]
            for key in wire.bodies('count')[-1]}
        assert len([event for event in events if event['event']=='model_start']) == (3 if compact else 2)
    asyncio.run(check())


@pytest.mark.parametrize('next_input_tokens,compact', [(194_560, False), (194_561, True)])
def test_application_token_policy_reaches_actual_sdk_requests(monkeypatch, next_input_tokens, compact):
    wire = Wire([20, next_input_tokens, 20], [[call()], [message('Scientific evidence remains unresolved.')]])
    monkeypatch.setattr('openai.AsyncOpenAI', lambda **kwargs: AsyncOpenAI(**kwargs,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(wire))))
    async def check():
        async def read(context, raw):
            return {'finding': 'Scientific evidence remains unresolved.'}
        runtime = ApplicationSettings(api_key='offline-test', model='test-model').research_runtime()
        try:
            result = await runtime.run(**arguments(lambda event: None, [evidence_tool(read)]))
        finally:
            await runtime.aclose()
        assert result.output == {'conclusion': 'Scientific evidence remains unresolved.'}
        assert len(wire.bodies('compact')) == int(compact)
        assert [kind for kind, _ in wire.requests] == (
            ['count', 'generate', 'count', 'compact', 'count', 'generate'] if compact else
            ['count', 'generate', 'count', 'generate'])
        assert all(body['max_output_tokens'] == 32_768 and body['truncation'] == 'disabled'
                   for body in wire.bodies('generate'))
    asyncio.run(check())
