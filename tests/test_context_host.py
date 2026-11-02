"""Context operations use the real canonical Host budget and failure closure."""
from contextlib import closing
import json
import sqlite3
import time

import httpx
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
import pytest

from lqcd_agent.control.strict_json import loads
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


@pytest.mark.parametrize('extra_pi_read', [False, True])
def test_compaction_shares_real_role_budget_and_preserves_second_role_allowance(tmp_path, monkeypatch, extra_pi_read):
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
        if name == 'ResearchBrief':
            pi_calls += 1
            if pi_calls == 1 or extra_pi_read:
                output = [ResponseFunctionToolCall(type='function_call', name='read_context',
                    call_id=f'pi-read-{pi_calls}', arguments='{"section":"case_config","offset":0}')]
            else:
                output = [model_message({'physics_question': 'Inspect the synthetic analysis.',
                    'competing_explanations': ['Unknown covariance effects'],
                    'discriminating_checks': ['Read Host warnings.'], 'success_criteria': ['Retain uncertainties.'],
                    'discussion': discussion()})]
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
    assert compact_calls == 1 and len(models) == (3 if extra_pi_read else 4)
    assert all(r['applicable_limits']['llm_calls'] == 4 for r in models)
    events = [loads(line, canonical=False) for path in (snapshot.host/'domain'/planning).rglob('research_events.jsonl')
              for line in path.read_bytes().splitlines()]
    starts = [e for e in events if e['event'] == 'model_start']
    pi_starts = [e for e in starts if e['role'] == 'pi'][:3]
    assert len(pi_starts) == 3 and [e.get('operation') for e in pi_starts] == [None, 'compact', None]
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    assert index['current']['terminal'] is None or index['current']['terminal']['status'] != 'accepted'
    assert not any(r['record_type'] == 'human_response' for r in records)
    if extra_pi_read:
        assert generated == ['ResearchBrief', 'ResearchBrief']
        assert models[-1]['remaining_before']['llm_calls'] == 2
    else:
        assert generated[:3] == ['ResearchBrief', 'ResearchBrief', 'method_plan_discussion']
        assert models[-1]['remaining_before']['llm_calls'] == 1
        assert snapshot.state['run_status'] == 'paused'
        assert snapshot.state['active_pause']['reason'] == 'human_input'
        assert index['current']['review']['status'] == 'success'


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
    assert snapshot.state['run_status'] == 'failed' and len(requests) == 1
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
    assert not any(r['record_type'] == 'human_response' or r.get('event') == 'failure_observed' for r in records)
    assert 'StopIteration' not in (snapshot.root/'execution_history.jsonl').read_text()
    assert 'private-provider-error' not in (snapshot.root/'execution_history.jsonl').read_text()
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    assert index['current']['plan'] is None
    reports = list((snapshot.host/'domain').rglob('method_plan.json'))
    assert len(reports) == 1 and loads(reports[0].read_bytes(), canonical=False)['status'] == 'failed'
