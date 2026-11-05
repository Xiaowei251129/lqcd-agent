"""Context operations use the real canonical Host budget and failure closure."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time

import httpx
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
import pytest

from lqcd_agent.control.strict_json import loads
from lqcd_agent.control.budget import policy
from lqcd_agent.research.agent_runtime import ResearchAgentRuntime
from lqcd_agent.research import context_window
from tests.test_context_window import USAGE
from tests.test_research_collaboration import discussion, execute_collaboration, proposal


def model_message(value):
    return ResponseOutputMessage(type='message', id='answer', role='assistant', status='completed',
        content=[ResponseOutputText(type='output_text', text=json.dumps(value), annotations=[])])


def factory(transport, *, request_timeout_seconds=10):
    def create():
        client = AsyncOpenAI(api_key='offline-test', max_retries=0, timeout=request_timeout_seconds,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport)))
        return ResearchAgentRuntime.from_openai(client=client, model='test-model', max_output_tokens=512)
    return create


def planning_response():
    return {'brief':{'physics_question':'Inspect the synthetic analysis.',
            'competing_explanations':['Unknown covariance effects'], 'discriminating_checks':['Read Host warnings.'],
            'success_criteria':['Retain uncertainties.']}, 'proposal':proposal('method_plan'), 'discussion':discussion()}


@pytest.mark.parametrize('behavior', ['valid', 'ignore_final', 'repair_final'])
def test_compaction_shares_real_budget_with_the_planning_pi(tmp_path, monkeypatch, behavior):
    monkeypatch.setattr(context_window, 'INPUT_TOKEN_LIMIT', 100)
    monkeypatch.setattr(context_window, 'COMPACT_TOKEN_LIMIT', 80)
    counts, pi_calls, compact_calls = 0, 0, 0
    request_timeout_seconds = 0.5
    generated = []
    async def transport(request):
        nonlocal counts, pi_calls, compact_calls
        assert request.extensions['timeout']['read'] == request_timeout_seconds
        body = json.loads(request.content)
        if request.url.path.endswith('/input_tokens'):
            counts += 1
            return httpx.Response(200, json={'object': 'response.input_tokens',
                                            'input_tokens': 90 if counts == 2 else 20})
        if request.url.path.endswith('/compact'):
            compact_calls += 1
            return httpx.Response(200, json={'id': 'compact-response', 'created_at': 0,
                'object': 'response.compaction', 'usage': USAGE,
                'output': [{'type': 'compaction', 'id': 'compact-state', 'encrypted_content': 'fixture-only'}]})
        schema = body['text']['format']['schema']
        assert body['text']['format']['name'] == 'final_output'
        if 'proposal' in schema['properties']:
            fields = schema['properties']['proposal']['properties']
            name = ('method_plan' if 'physics_goal' in fields else 'scientific_review_report')+'_discussion'
        else:
            name = schema['title']
        generated.append(name)
        if name == 'method_plan_discussion':
            pi_calls += 1
            closing = body.get('tool_choice') == 'none'
            if pi_calls == 1 or behavior == 'ignore_final' or (behavior == 'repair_final' and not closing):
                output = [ResponseFunctionToolCall(type='function_call', name='read_context',
                    call_id=f'pi-read-{pi_calls}', arguments='{"section":"case_config","offset":0}')]
            else:
                plan = planning_response()
                if behavior == 'repair_final' and body.get('tools'):
                    plan['brief']['success_criteria'] = []
                output = [model_message(plan)]
        elif name.endswith('_discussion'):
            output = [model_message({'proposal': proposal(name.removesuffix('_discussion')),
                                     'discussion': discussion()})]
        else:
            assert name == 'Discussion'
            output = [model_message(discussion())]
        response = Response(id=f'response-{len(generated)}', created_at=0, model='test-model', object='response',
            output=output, parallel_tool_calls=True, tool_choice='auto', tools=[], status='completed', usage=USAGE)
        return httpx.Response(200, json=response.model_dump(mode='json'))

    started = time.monotonic()
    snapshot, _, _ = execute_collaboration(tmp_path,
        runtime_factory=factory(transport, request_timeout_seconds=request_timeout_seconds),
        request_timeout_seconds=request_timeout_seconds)
    assert time.monotonic() - started > request_timeout_seconds
    records = snapshot.records.values
    planning = next(r['attempt_id'] for r in records if r.get('event') == 'scheduled')
    reserved = [r['payload'] for r in records if r.get('event') == 'resource_reserved'
                and r['payload']['attempt_id'] == planning]
    assert all(r['timeout_seconds'] <= request_timeout_seconds for r in reserved)
    with closing(sqlite3.connect(f'file:{snapshot.host}/.lqcd/control_operations.sqlite?mode=ro', uri=True)) as db:
        capability = next(value for raw, in db.execute('SELECT value FROM invocation_capabilities')
            if (value := loads(raw))['authorization']['identity']['attempt_id'] == planning)
    original_remaining = capability['authorization']['projection']['budget']['dimensions']
    maximum_window = min(original_remaining[name]['remaining'] for name in
        ('active_seconds_per_attempt', 'active_seconds_per_run'))
    acquired = capability['started_intent']['record']['created_at']['monotonic_seconds']
    assert 0 < capability['expires_at'] - acquired <= maximum_window <= 900
    assert capability['expires_at'] <= capability['deadline'] <= acquired + maximum_window
    assert capability['invocation_epoch'] == 1
    models = [r for r in reserved if r['resource_kind'] == 'llm_call']
    allowance = policy().value['limits']['llm_calls_per_attempt']
    assert compact_calls == 1 and len(models) == {'valid':3, 'ignore_final':allowance-1, 'repair_final':allowance}[behavior]
    assert all(r['applicable_limits']['llm_calls'] == allowance for r in models)
    events = [loads(line, canonical=False) for path in (snapshot.host/'domain'/planning).rglob('research_events.jsonl')
              for line in path.read_bytes().splitlines()]
    starts = [e for e in events if e['event'] == 'model_start']
    pi_starts = [e for e in starts if e['role'] == 'pi'][:3]
    assert len(pi_starts) == 3 and [e.get('operation') for e in pi_starts] == [None, 'compact', None]
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    terminal = loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_bytes())
    assert terminal['decision_origin'] == 'system' and terminal['authorization_decision'] is None
    assert not any(r['record_type'] in ('human_request', 'human_response') for r in records)
    if behavior == 'ignore_final':
        # One shared model slot is still available for a correction of a completed draft.
        # This model called a tool on its final turn and never submitted that draft.
        assert generated == ['method_plan_discussion'] * (allowance - 2)
        assert models[-1]['remaining_before']['llm_calls'] == allowance - len(models) + 1
        assert terminal['scientific_outcome'] == 'inconclusive' and index['current']['analysis'] is None
    else:
        assert generated[:2] == ['method_plan_discussion'] * 2
        assert models[-1]['remaining_before']['llm_calls'] == allowance - len(models) + 1
        assert snapshot.state['run_status'] == 'completed' and snapshot.state.get('active_pause') is None
        assert index['current']['review']['status'] == 'success'
        if behavior == 'repair_final':
            assert generated.count('method_plan_discussion') == allowance-1
            assert starts[-1]['model_settings']['tool_choice'] == 'none' and not starts[-1]['tools']
            assert 'host_corrections' in starts[-1]['input'][-1]['content']


@pytest.mark.parametrize('failure', ['http_error', 'input_limit'])
def test_count_failure_before_any_model_closes_without_a_fabricated_model_anchor(tmp_path, failure):
    requests = []
    async def transport(request):
        requests.append(request.url.path)
        assert request.url.path.endswith('/input_tokens')
        if failure == 'http_error':
            return httpx.Response(500, json={'error': {'message': 'private-provider-error', 'type': 'server_error'}})
        return httpx.Response(200, json={'object': 'response.input_tokens', 'input_tokens': 256_001})
    snapshot, _, _ = execute_collaboration(tmp_path, runtime_factory=factory(transport))
    assert snapshot.state['run_status'] == 'completed' and snapshot.state.get('active_pause') is None and len(requests) == 1
    records = snapshot.records.values
    reserved = [r['payload'] for r in records if r.get('event') == 'resource_reserved']
    settled = [r['payload'] for r in records if r.get('event') == 'resource_settled']
    assert len(reserved) == len(settled) == 1
    assert reserved[0]['resource_kind'] == 'tool_call'
    if failure == 'http_error':
        assert settled[0]['actual'] is None
        assert settled[0]['cost'] == settled[0]['tokens'] == {'state': 'unknown', 'value': None}
    else:
        assert settled[0]['actual']['llm_calls'] == 0 and settled[0]['actual']['tool_calls'] == 1
    assert not any(r['record_type'] in ('human_request', 'human_response') for r in records)
    assert len([r for r in records if r.get('event') == 'failure_observed']) == 1
    assert not any(r['resource_kind'] == 'llm_call' for r in reserved)
    assert 'StopIteration' not in (snapshot.root/'execution_history.jsonl').read_text()
    assert 'private-provider-error' not in (snapshot.root/'execution_history.jsonl').read_text()
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    assert index['current']['plan']['status'] == 'failed'
    assert index['current']['terminal']['status'] == 'rejected'
    terminal = loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_bytes())
    assert terminal['scientific_outcome'] == 'inconclusive' and terminal['decision_origin'] == 'system'
    reports = list((snapshot.host/'domain').rglob('method_plan.json'))
    assert len(reports) == 1 and loads(reports[0].read_bytes(), canonical=False)['status'] == 'failed'


@pytest.mark.parametrize('closing_reason', ['tools', 'time'])
def test_batched_tools_leave_real_reviewer_and_pi_counts_and_conclusions(tmp_path, monkeypatch, closing_reason):
    """Use actual SDK batches and Host effects; refused calls are never evidence."""
    monkeypatch.setattr(context_window, 'INPUT_TOKEN_LIMIT', 100)
    monkeypatch.setattr(context_window, 'COMPACT_TOKEN_LIMIT', 80)
    current, calls, counted, generated = {}, {}, [], []

    class ObservedRuntime(ResearchAgentRuntime):
        async def run(self, **kwargs):
            current['meter'] = kwargs['observer']
            return await super().run(**kwargs)

    def schema_name(body):
        schema = body['text']['format']['schema']
        if 'proposal' in schema['properties']:
            fields = schema['properties']['proposal']['properties']
            return ('method_plan' if 'physics_goal' in fields else 'scientific_review_report') + '_discussion'
        return schema['title']

    async def transport(request):
        body = json.loads(request.content)
        assert not request.url.path.endswith('/compact')
        name = schema_name(body)
        if request.url.path.endswith('/input_tokens'):
            counted.append(body)
            # Spend part of the existing first role window in two real effects,
            # each within its own requested timeout, then require soft closing.
            if closing_reason == 'time' and name == 'scientific_review_report_discussion' and not calls.get(name):
                assert request.extensions['timeout']['read'] >= 100
                current['meter'].port.leases.coordinator.clock.advance(100)
            return httpx.Response(200, json={'object': 'response.input_tokens',
                'input_tokens': 90 if body.get('tool_choice') == 'none' else 20})
        assert counted[-1] == {key: body[key] for key in counted[-1]}
        generated.append(body)
        calls[name] = calls.get(name, 0) + 1
        if name in ('scientific_review_report_discussion', 'Discussion') and calls[name] == 1:
            assert body.get('tool_choice') != 'none'
            if closing_reason == 'time' and name == 'scientific_review_report_discussion':
                assert request.extensions['timeout']['read'] >= 155
                current['meter'].port.leases.coordinator.clock.advance(155)
            output = [ResponseFunctionToolCall(type='function_call', name='read_context',
                call_id=f'{name}-batch-{index:02d}', arguments='{"section":"catalog","offset":0}')
                for index in range(40)]
        else:
            if name in ('scientific_review_report_discussion', 'Discussion'):
                assert body['tool_choice'] == 'none'
                refusals = [json.loads(item['output']) for item in body['input']
                    if item.get('type') == 'function_call_output' and 'not_executed' in item['output']]
                assert refusals and all(result == {'status': 'not_executed',
                    'reason': 'finalization_budget_reserved'} for result in refusals)
            if name == 'method_plan_discussion':
                value = planning_response()
            elif name.endswith('_discussion'):
                value = {'proposal': proposal(name.removesuffix('_discussion')), 'discussion': discussion()}
            else:
                assert name == 'Discussion'
                value = discussion()
            output = [model_message(value)]
        response = Response(id=f'response-{len(generated)}', created_at=0, model='test-model', object='response',
            output=output, parallel_tool_calls=True, tool_choice='auto', tools=[], status='completed', usage=USAGE)
        return httpx.Response(200, json=response.model_dump(mode='json'))

    def create():
        client = AsyncOpenAI(api_key='offline-test', max_retries=0, timeout=180,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport)))
        return ObservedRuntime.from_openai(client=client, model='test-model', max_output_tokens=512)

    snapshot, _, _ = execute_collaboration(tmp_path, runtime_factory=create, request_timeout_seconds=180)
    assert snapshot.state['run_status'] == 'completed' and snapshot.state.get('active_pause') is None
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    assert index['current']['review']['status'] == 'success'
    records = snapshot.records.values
    review_attempt = next(row['attempt_id'] for row in records
        if row.get('event') == 'scheduled' and row.get('attempt_kind') == 'scientific_reviewer')
    reserved = [row['payload'] for row in records if row.get('event') == 'resource_reserved'
        and row['payload']['attempt_id'] == review_attempt]
    assert sum(row['resource_kind'] == 'tool_call' for row in reserved) == 32
    assert sum(row['resource_kind'] == 'llm_call' for row in reserved) == 4 <= 8
    events = [loads(line, canonical=False) for path in (snapshot.host/'domain'/review_attempt).rglob('research_events.jsonl')
        for line in path.read_bytes().splitlines()]
    denied = {event['call_id'] for event in events if event['event'] == 'tool_not_executed'}
    assert denied and all(event.get('call_id') not in denied for event in events
        if event['event'] in ('tool_start', 'tool_end'))
    assert len([event for event in events if event['event'] == 'tool_start']) == 32
    for role in ('reviewer', 'pi'):
        assert sum(event['event'] == 'model_end' and event['role'] == role for event in events) == 2
        assert sum(event['event'] == 'run_end' and event['role'] == role for event in events) == 1
    pressure = [event for event in events if event['event'] == 'context_pressure']
    assert len(pressure) == 2 and all(event['reason'] == 'finalization_budget_reserved' for event in pressure)
    if closing_reason == 'time':
        assert not any(event['event'] == 'tool_start' and event['role'] == 'reviewer'
            and event['tool_name'] != 'context_token_count' for event in events)
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in records)
    terminal = loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_bytes())
    assert terminal['decision_origin'] == 'system' and terminal['authorization_decision'] is None
