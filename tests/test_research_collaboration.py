"""Offline SDK collaboration through the real Host; fixtures do not validate physics."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

from agents import Model
from agents.items import ModelResponse
from agents.exceptions import ModelBehaviorError
import asyncio
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputRefusal, ResponseOutputText
import pytest
import httpx
from openai import APIConnectionError, APIStatusError

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.budget import BudgetExhausted, policy
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import StartRunRequest
from lqcd_agent.control.storage import execution_scratch_root
from lqcd_agent.control.strict_json import digest, loads
from lqcd_agent.inspection import read_snapshot
from lqcd_agent.research.agent_runtime import ResearchAgentRuntime
from lqcd_agent.research.collaboration import (CollaborationAgent, Discussion, ProposalDiscussion,
    ResearchOutput, _RoleProvider, _merge_issues, _prior_issues, _review_recommendation)
from lqcd_agent.runtime import assemble
from lqcd_agent.tools.dataset import snapshot_dataset
from tests.support import mkdtemp


def discussion(**changes):
    return {'summary': 'Offline scientific discussion.', 'issues': [], 'decision': 'recommend_proceed', **changes}


def issue(**changes):
    return {'id': '', 'question': 'Does the selected window change the result?', 'response': None,
            'evidence_references': [], 'status': 'open', **changes}


def proposal(role):
    result = {'status': 'success', 'summary': 'Offline schema fixture.', 'warnings': [], 'errors': []}
    if role == 'method_plan':
        return {**result, 'physics_goal': 'Inspect synthetic normalization evidence.',
            'target_observables': ['synthetic matrix element'], 'method_steps': ['Run the Host synthetic fixture.'],
            'required_inputs': [], 'implementation_gaps': [], 'selected_analysis_programs': [],
            'code_needed': False, 'coder_task_summary': None}
    return {**result, 'findings': [], 'evidence': [], 'recommended_checks': [], 'confidence': 'high'}


class CollaborationModel(Model):
    def __init__(self, calls, *, fail=False, refusal=None, need_information=False, code_needed=False,
                 pi_need_information=False, read_sections=('catalog',), postdoc_read=False):
        self.calls, self.fail, self.read = calls, fail, 0
        self.read_sections, self.postdoc_read = read_sections, postdoc_read
        self.need_information, self.code_needed = need_information, code_needed
        self.pi_need_information, self.refusal = pi_need_information, refusal

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, **kwargs):
        assert tracing.is_disabled() and not handoffs
        self.calls.append({'schema': output_schema.name(), 'input': deepcopy(input), 'instructions': system_instructions})
        if self.fail:
            raise self.fail
        name = output_schema.name()
        if self.refusal is not None:
            output = [ResponseOutputMessage(type='message', id='answer', role='assistant', status='completed',
                content=[ResponseOutputRefusal(type='refusal', refusal=self.refusal)])]
        elif name == 'ResearchBrief' and self.read < len(self.read_sections):
            section = self.read_sections[self.read]
            self.read += 1
            output = [ResponseFunctionToolCall(type='function_call', name='read_context',
                arguments=json.dumps({'section': section, 'offset': 0}), call_id='read-'+section)]
        elif name == 'method_plan_discussion' and self.postdoc_read:
            self.postdoc_read = False
            output = [ResponseFunctionToolCall(type='function_call', name='read_context',
                arguments='{"section":"case_config","offset":0}', call_id='postdoc-read')]
        else:
            if name == 'ResearchBrief':
                value = {'physics_question': 'PI-BRIEF-PRIVATE-MARKER', 'competing_explanations': ['Missing scale information'],
                    'discriminating_checks': ['Inspect the Host diagnostics.'], 'success_criteria': ['All inputs attributable'],
                    'discussion': discussion()}
                if self.pi_need_information:
                    value['discussion'] = discussion(decision='need_information',
                        summary='The required ensemble is missing.',
                        issues=[issue(question='Supply the required input ensemble.', status='open')])
            elif name in ('method_plan_discussion', 'scientific_review_report_discussion'):
                value = {'proposal': proposal(name.removesuffix('_discussion')), 'discussion': discussion()}
                if name == 'method_plan_discussion':
                    value['proposal'].update(code_needed=self.code_needed,
                        coder_task_summary='Implement the prescribed analysis.' if self.code_needed else None)
                    if self.need_information:
                        value['discussion'] = discussion(decision='need_information', summary='Supply a missing input ensemble.')
            else:
                assert name == 'Discussion'
                value = discussion()
            output = [ResponseOutputMessage(type='message', id='answer', role='assistant', status='completed',
                content=[ResponseOutputText(type='output_text', text=json.dumps(value), annotations=[])])]
        return ModelResponse(output=output, usage=Usage(requests=1, input_tokens=10, output_tokens=3, total_tokens=13),
            raw_usage=None if len(self.calls) == 1 else {'input_tokens': 10, 'output_tokens': 3, 'total_tokens': 13},
            response_id=f'response-{len(self.calls)}')

    async def stream_response(self, *args, **kwargs):
        raise AssertionError('No streaming fixture')
        yield


def execute_collaboration(workspace, *, fail=False, refusal=None, need_information=False, pi_need_information=False,
                          read_sections=('catalog',), postdoc_read=False, runtime_factory=None, request_timeout_seconds=10):
    host = Path(mkdtemp(prefix='lqcd-agent-host-', dir=execution_scratch_root()))
    calls, closed = [], []
    class ClosingRuntime(ResearchAgentRuntime):
        async def aclose(self):
            closed.append(True)
    def factory():
        return ClosingRuntime(CollaborationModel(calls, fail=fail, refusal=refusal, need_information=need_information,
            pi_need_information=pi_need_information, read_sections=read_sections, postdoc_read=postdoc_read), max_output_tokens=2048)
    config = {'schema_version': '0.1', 'case_id': 'sdk-collaboration', 'source_kind': 'synthetic_placeholder',
              'physics_goal': 'Inspect synthetic normalization evidence.'}
    with closing(Coordinator(host, clock=FakeClock(100, 0))) as coordinator:
        agent = CollaborationAgent(host, config, workspace=workspace, runtime_factory=runtime_factory or factory, request_timeout_seconds=request_timeout_seconds)
        runtime, actor, _ = assemble(coordinator, agent, workflow='scientific', initialize=True)
        goal = {'goal': config['physics_goal'], 'workflow': 'scientific', 'live': False, 'workspace': str(workspace),
                'case_config': config, 'dataset_snapshot': snapshot_dataset(config, workspace)}
        inputs = {'root_goal': goal, 'input_snapshot': {'kind': 'scientific_case', 'case_config': config}}
        started = runtime.plane.start_run(StartRunRequest(config['case_id'], inputs, digest(inputs), 'sdk-offline'), actor=actor)
        locator = started['result']['run_locator']
        runtime.run(locator)
    return read_snapshot(host, locator), calls, closed


def test_actual_sdk_collaboration_uses_host_resources_preserves_review_and_concludes(tmp_path):
    snapshot, calls, closed = execute_collaboration(tmp_path)
    assert snapshot.state['run_status'] == 'completed' and snapshot.state.get('active_pause') is None and len(closed) == 2
    assert [call['schema'] for call in calls] == ['ResearchBrief', 'ResearchBrief', 'method_plan_discussion',
                                              'scientific_review_report_discussion', 'Discussion']
    reviewer = calls[3]['input']
    assert 'PI-BRIEF-PRIVATE-MARKER' not in json.dumps(reviewer)
    records = parse_ledger((snapshot.root/'execution_history.jsonl').read_bytes()).values
    reserved = [row['payload'] for row in records if row.get('event') == 'resource_reserved']
    settled = [row['payload'] for row in records if row.get('event') == 'resource_settled']
    assert len(reserved) == len(settled) == 7
    assert [row['resource_kind'] for row in reserved].count('llm_call') == 5
    assert [row['resource_kind'] for row in reserved].count('tool_call') == 2
    assert settled[0]['tokens'] == {'state': 'unknown', 'value': None}
    assert sum(row['tokens']['value'] or 0 for row in settled) == 52
    review_paths = list((snapshot.host/'domain').rglob('scientific_review_report.json'))
    assert len(review_paths) == 1
    report = loads(review_paths[0].read_bytes(), canonical=False)
    assert report['confidence'] != 'high' or not report['warnings']
    events = [loads(line, canonical=False) for path in (snapshot.host/'domain').rglob('research_events.jsonl')
              for line in path.read_bytes().splitlines()]
    starts = [event for event in events if event['event'] == 'model_start']
    assert all(event['output_schema'] and event['tools'] and event['model_settings']['store'] is False for event in starts)
    assert all(event['resource_id'] == 'domain-diagnosis' for event in starts if event['role'] in ('reviewer',) and event['call_index'] == 1)
    # Scientific sidecars are inside the same content-bound canonical result.
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    member = next(m for m in index['current']['review']['members'] if m['logical_name'] == 'scientific_review_report.json')
    content = loads((snapshot.root/member['canonical_path']).read_bytes())
    assert any(path.endswith('collaboration.json') for path in content['domain_result']['member_digests'])
    assert any(path.endswith('research_events.jsonl') for path in content['domain_result']['member_digests'])
    assert content['collaboration']['decision'] == 'recommend_proceed'
    terminal = loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_bytes())
    assert terminal['decision_origin'] == 'system' and terminal['authorization_decision'] is None
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in records)


@pytest.mark.parametrize('postdoc_read', [False, True])
def test_roles_share_the_host_call_allowance_preserving_the_second_role(tmp_path, postdoc_read):
    snapshot, calls, _ = execute_collaboration(tmp_path, read_sections=('catalog', 'case_config'),
                                             postdoc_read=postdoc_read)
    allowance = policy().value['limits']['llm_calls_per_attempt']
    assert [call['schema'] for call in calls[:4]] == ['ResearchBrief'] * 3 + ['method_plan_discussion']
    assert f'at most {(allowance + 1)//2} model turns' in calls[0]['instructions']
    assert f'at most {allowance - 3} model turns' in calls[3]['instructions']
    records = parse_ledger((snapshot.root/'execution_history.jsonl').read_bytes()).values
    first_attempt = next(row['attempt_id'] for row in records if row.get('event') == 'scheduled')
    reserved = [row['payload'] for row in records if row.get('event') == 'resource_reserved'
                and row['payload']['attempt_id'] == first_attempt and row['payload']['resource_kind'] == 'llm_call']
    assert len(reserved) == (5 if postdoc_read else 4) <= allowance
    assert all(row['applicable_limits']['llm_calls'] == allowance for row in reserved)
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    assert snapshot.state['run_status'] == 'completed' and len(calls) == (7 if postdoc_read else 6)
    assert index['current']['plan']['status'] == index['current']['review']['status'] == 'success'
    terminal = loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_bytes())
    assert terminal['decision_origin'] == 'system' and terminal['authorization_decision'] is None
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in records)


@pytest.mark.parametrize('exhausted', ['calls', 'deadline'])
def test_role_without_budget_refuses_before_sdk_invocation(tmp_path, recwarn, exhausted):
    calls, events = [], []
    runtime = ResearchAgentRuntime(CollaborationModel(calls), max_output_tokens=2048)
    context = {'budget_summary': {'dimensions': {
        'llm_calls_per_attempt': {'remaining': 4}, 'llm_calls_per_run': {'remaining': 32}}}}
    class ExhaustedMeter:
        model_calls = 4 if exhausted == 'calls' else 0
        def __call__(self, event):
            events.append(event)
        def remaining_seconds(self):
            raise BudgetExhausted('Research attempt deadline exhausted')
    with asyncio.Runner() as runner:
        provider = _RoleProvider(SimpleNamespace(request_timeout_seconds=10), 'method_planner', context, tmp_path,
                                 runtime, runner, ExhaustedMeter())
        with pytest.raises(BudgetExhausted):
            provider._run('postdoc', 'Conclude.', [], Discussion, [])
    assert calls == events == []
    assert not recwarn.list


@pytest.mark.parametrize('failure', [
    ConnectionError('Offline transport fixture'),
    APIConnectionError(message='private-provider-error', request=httpx.Request('POST', 'https://example.invalid')),
    APIStatusError('private-provider-error', response=httpx.Response(429,
        request=httpx.Request('POST', 'https://example.invalid')), body={'secret': 'private-provider-error'}),
    ModelBehaviorError('Invalid schema: private-provider-error'),
])
def test_sdk_failure_is_conservatively_settled_without_retry_or_fake_result(tmp_path, failure):
    snapshot, calls, closed = execute_collaboration(tmp_path, fail=failure)
    assert len(calls) == len(closed) == 1
    records = parse_ledger((snapshot.root/'execution_history.jsonl').read_bytes()).values
    reserved = [row['payload'] for row in records if row.get('event') == 'resource_reserved']
    settled = [row['payload'] for row in records if row.get('event') == 'resource_settled']
    assert len(reserved) == len(settled) == 1 and settled[0]['actual'] is None
    assert settled[0]['tokens'] == {'state': 'unknown', 'value': None}
    assert not list((snapshot.host/'domain').rglob('scientific_review_report.json'))
    events = [loads(line, canonical=False) for path in (snapshot.host/'domain').rglob('research_events.jsonl')
              for line in path.read_bytes().splitlines()]
    assert next(event for event in events if event['event'] == 'model_error')['error_type'] == type(failure).__name__
    artifacts = [path.read_bytes() for path in snapshot.host.rglob('*') if path.is_file()]
    assert all(b'private-provider-error' not in content for content in artifacts)
    if isinstance(failure, (APIConnectionError, APIStatusError, ModelBehaviorError)):
        plans = list((snapshot.host/'domain').rglob('method_plan.json'))
        assert len(plans) == 1 and type(failure).__name__ in plans[0].read_text()


def test_sdk_refusal_preserves_model_evidence_without_copying_it_to_error_records(tmp_path):
    refusal = 'private-refusal-body'
    snapshot, calls, closed = execute_collaboration(tmp_path, refusal=refusal)
    assert len(calls) == len(closed) == 1
    records = parse_ledger((snapshot.root/'execution_history.jsonl').read_bytes()).values
    settled = [row['payload'] for row in records if row.get('event') == 'resource_settled']
    assert len(settled) == 1 and settled[0]['actual']['llm_calls'] == 1
    assert settled[0]['tokens'] == {'state': 'unknown', 'value': None}
    events = [loads(line, canonical=False) for path in (snapshot.host/'domain').rglob('research_events.jsonl')
              for line in path.read_bytes().splitlines()]
    # Model evidence remains attributable even when no scientific proposal is produced.
    ended = next(event for event in events if event['event'] == 'model_end')
    assert ended['output'][0]['content'] == [{'type': 'refusal', 'refusal': refusal}]
    assert events[-1]['event'] == 'run_error' and events[-1]['error_type'] == 'ModelRefusalError'
    assert not list((snapshot.host/'domain').rglob('scientific_review_report.json'))
    plans = list((snapshot.host/'domain').rglob('method_plan.json'))
    assert len(plans) == 1 and 'ModelRefusalError' in plans[0].read_text()
    # Derived errors and Host state must not repeat the provider's private refusal text.
    derived = [path.read_bytes() for path in snapshot.host.rglob('*')
               if path.is_file() and path.name != 'research_events.jsonl']
    assert all(refusal.encode() not in content for content in derived)


def test_unanswered_issues_survive_omission_and_require_response_and_evidence():
    original = _merge_issues([], [issue()])
    assert _merge_issues(original, []) == original
    pending = _merge_issues(original, [{**original[0], 'status': 'addressed', 'response': 'Checked.'}])
    assert pending[0]['status'] == 'open'
    invented = _merge_issues(original, [{**original[0], 'status': 'addressed', 'response': 'Claimed.',
        'evidence_references': ['invented-reference']}])
    assert invented[0]['status'] == 'open' and 'Host:' in invented[0]['response']
    closed = _merge_issues(original, [{**original[0], 'status': 'addressed', 'response': 'Compared two windows.',
                                    'evidence_references': ['verified-window-comparison']}], known_evidence={'verified-window-comparison'})
    assert closed[0]['status'] == 'addressed'
    with pytest.raises(ModelBehaviorError, match='cannot be replaced'):
        _merge_issues(original, [{**original[0], 'question': 'A different question'}])


def test_resolved_host_issue_can_be_revisited_only_with_its_original_question_and_current_evidence():
    original = _merge_issues([], [issue()])[0]
    known = MappingProxyType({original['id']: original['question'], 'issue-other': 'A separate resolved question.'})
    context = {'project_history': {'issues': [], 'resolved': [
        {'id': key, 'question': value} for key, value in known.items()]}}
    assert _prior_issues(context) == []
    assert _merge_issues([], [], known_questions=known) == []
    answer = {**original, 'status': 'addressed', 'response': 'Rechecked for this Run.',
              'evidence_references': ['current-evidence']}
    pending = _merge_issues([], [answer], known_questions=known)
    assert len(pending) == 1 and pending[0]['status'] == 'open'
    checked = _merge_issues([], [answer], known_questions=known, known_evidence={'current-evidence'})
    assert checked == [answer]
    with pytest.raises(ModelBehaviorError, match='cannot be replaced'):
        _merge_issues([], [{**answer, 'question': 'A replacement question.'}], known_questions=known,
                      known_evidence={'current-evidence'})
    with pytest.raises(ModelBehaviorError, match='cannot invent'):
        _merge_issues([], [{**answer, 'id': 'issue-invented'}], known_questions=known,
                      known_evidence={'current-evidence'})


@pytest.mark.parametrize('warnings,errors', [([], []), ([{'severity': 'severe'}], []),
    ([{'severity': 'warning'}], []), ([], [{'code': 'failed_check'}])])
def test_pi_revision_preserves_warnings_and_cannot_override_errors(warnings, errors):
    outcome = {'diagnostic': {'status': 'success', 'category': 'scientific_review', 'risk': 'high', 'human_need': None},
               'content': {'domain_result': {'report': {'status': 'success', 'warnings': warnings, 'errors': errors}}}}
    _review_recommendation(outcome, {'decision': 'revise', 'challenges': ['Inspect a second window.']})
    assert outcome['content']['domain_result']['report']['warnings'] == warnings
    assert outcome['content']['domain_result']['report']['errors'] == errors
    if not errors:
        assert outcome['diagnostic']['category'] == 'scientific_revision'
        assert outcome['diagnostic']['candidates'] == ['method_planner']
    else:
        assert outcome['diagnostic']['category'] == 'scientific_review' and outcome['diagnostic']['risk'] == 'high'


@pytest.mark.parametrize('role', ['pi', 'postdoc'])
def test_planner_requests_missing_information_before_any_analysis(tmp_path, role):
    # For the PI case, Postdoc omits the PI's open question and recommends proceeding.
    # That omission must not authorize an analysis with the missing input.
    snapshot, calls, closed = execute_collaboration(tmp_path, need_information=role == 'postdoc',
                                                   pi_need_information=role == 'pi')
    assert snapshot.state['run_status'] == 'completed' and snapshot.state.get('active_pause') is None and len(closed) == 1
    assert not any(call['schema'] == 'scientific_review_report_discussion' for call in calls)
    records = parse_ledger((snapshot.root/'execution_history.jsonl').read_bytes()).values
    assert not any(row.get('event') == 'scheduled' and row.get('attempt_kind') == 'analysis_engineer' for row in records)
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in records)
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    terminal = loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_bytes())
    assert terminal['scientific_outcome'] == 'inconclusive' and terminal['decision_origin'] == 'system'
    plan = loads(next((snapshot.host/'domain').rglob('method_plan.json')).read_bytes(), canonical=False)
    assert plan['status'] == 'needs_more_info' and plan['code_needed'] is False


def test_pi_checks_and_prior_questions_reach_the_actual_coding_request(tmp_path):
    from lqcd_agent.agents.method_planner import run_method_planner
    class Observer:
        def __init__(self):
            self.events = []
            self.model_calls = 0
            self.write_scope = None  # This direct read-only fixture has no Host publication authority.
        def __call__(self, event):
            self.events.append(event)
            if event['event'] == 'model_start':
                self.model_calls += 1
        def remaining_seconds(self):
            return 10
    config = {'case_id': 'test', 'generated_program': {'requirements': ['Keep the specified JSON contract.']}}
    context = {'identity': {'case_id': 'test', 'run_id': 'run'},
        'budget_summary': {'dimensions': {'llm_calls_per_attempt': {'remaining': 4},
                                          'llm_calls_per_run': {'remaining': 32}}},
        'remediation': {'success_criteria': ['Compare the fit windows.', 'All inputs attributable']}}
    output = tmp_path/'output'
    runtime = ResearchAgentRuntime(CollaborationModel([], code_needed=True), max_output_tokens=2048)
    agent = CollaborationAgent(tmp_path/'host', config, workspace=tmp_path,
        runtime_factory=lambda: runtime, request_timeout_seconds=10)
    with asyncio.Runner() as runner:
        provider = _RoleProvider(agent, 'method_planner', context, output, runtime, runner, Observer())
        result = run_method_planner(user_goal='Analyze the frozen data contract.', case_config=config,
            repo_inventory={'repo_root': str(tmp_path), 'analysis_programs': [], 'implementation_gaps': ['Implement the contract.']},
            output_dir=output, provider=provider)
        assert provider.failure is None
    assert result['status'] == 'success' and result['code_needed']
    requirements = result['code_request']['requirements']
    assert 'Inspect the Host diagnostics.' in requirements
    assert 'Compare the fit windows.' in requirements
    assert requirements.count('All inputs attributable') == 1
    assert result['method_plan']['method_steps'] == requirements


def test_current_run_answers_inherited_open_issue_only_with_current_evidence():
    opened = _merge_issues([], [issue()])[0]
    context = {'project_history': {'issues': [opened]}}
    retained = _prior_issues(context)
    answered = _merge_issues(retained, [{**opened, 'status': 'addressed',
        'response': 'Checked in this Run.', 'evidence_references': ['current-evidence']}],
        known_evidence={'current-evidence'})
    assert answered[0]['status'] == 'addressed'
    assert _prior_issues(context, {'collaboration': {'issues': answered}}) == answered


@pytest.mark.parametrize('raw', ['', '{', '{"summary":"a","summary":"b","issues":[],"decision":"recommend_proceed"}',
    '{"summary":" ","issues":[],"decision":"recommend_proceed"}',
    '{"summary":"Review","issues":[{"id":"","question":" ","response":null,"evidence_references":[],"status":"open"}],"decision":"revise"}'])
def test_invalid_or_empty_research_output_is_a_model_failure(raw):
    with pytest.raises(ModelBehaviorError):
        ResearchOutput(Discussion).validate_json(raw)


def test_duplicate_proposal_keys_are_rejected_before_host_interpretation():
    from lqcd_agent.llm.schemas import role_schema
    value = json.dumps(proposal('method_plan'))
    with pytest.raises(ModelBehaviorError):
        ProposalDiscussion(role_schema('method_plan')).validate_json(
            '{"proposal":'+value+',"proposal":'+value+',"discussion":'+json.dumps(discussion())+'}')


def test_missing_input_block_requires_a_verified_answer_not_a_status_change():
    blocked = _merge_issues([], [issue(status='blocked')])
    for answer in ({**blocked[0], 'status': 'open'},
                   {**blocked[0], 'status': 'addressed', 'response': 'Claimed fixed.',
                    'evidence_references': ['unverified']}):
        assert _merge_issues(blocked, [answer])[0]['status'] == 'blocked'
    resolved = _merge_issues(blocked, [{**blocked[0], 'status': 'addressed', 'response': 'Input is present.',
        'evidence_references': ['read-input']}], known_evidence={'read-input'})
    assert resolved[0]['status'] == 'addressed'
