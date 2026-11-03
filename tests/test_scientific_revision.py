"""Scientific revision advances the real graph without inventing a failure."""
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from lqcd_agent.control.budget import policy
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
from lqcd_agent.control.storage import execution_scratch_root
from lqcd_agent.control.strict_json import digest, loads
from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
from lqcd_agent.graph.nodes import product_resource
from lqcd_agent.graph.routing import select_product_route
from tests.support import mkdtemp


QUESTIONS = ['Compare the extracted mass across two fit windows.',
             'Explain the covariance sensitivity using the same input ensemble.']


def diagnostic(**changes):
    value = {'status': 'success', 'category': 'scientific_revision', 'affected_layer': 'plan',
        'evidence': [], 'retryability': 'retryable', 'candidates': ['method_planner'],
        'confidence': 'unique', 'fingerprint': None, 'human_need': None, 'risk': 'low'}
    value.update(changes)
    return value


def route_view():
    selected = policy().value
    dimensions = {name: {'used': 0, 'remaining': limit} for name, limit in selected['limits'].items()}
    dimensions['cycles_per_run'] = {'used': 1, 'remaining': selected['limits']['cycles_per_run'] - 1}
    return {'source': {'node_name': 'decision_coordinator', 'attempt_id': 'attempt_000004',
                       'status': 'succeeded'},
        'state': {'run_id': 'run', 'attempt_id': 'attempt_000004', 'budget': {
            'profile_id': selected['profile_id'], 'dimensions': dimensions,
            'active_grant': None, 'active_failure': {'fingerprint_digest': '1' * 64,
                'causal_context_digest': '2' * 64, 'occurrence': 3}}}}


def test_revision_ignores_old_failure_but_never_borrows_its_budget():
    view = route_view()
    selected = select_product_route(view, diagnostic())
    assert selected['target_node'] == 'method_planner' and selected['trigger_reason'] == 'replan'
    assert selected['budget_decision']['dimensions']['automatic_replan_per_run']['projected_after'] == 1
    limits = view['state']['budget']['dimensions']
    limits['automatic_replan_per_run'] = {'used': policy().value['limits']['automatic_replan_per_run'], 'remaining': 0}
    selected = select_product_route(view, diagnostic())
    assert selected['target_node'] == 'memory_report' and selected['trigger_reason'] == 'budget_stop'
    assert selected['human_request'] is None
    assert selected['stop_sequence_id'] is not None


@pytest.mark.parametrize('changes', [
    {'confidence': 'ambiguous'}, {'human_need': 'clarification'},
    {'retryability': 'new_evidence_required'}, {'candidates': ['analysis_engineer']},
    {'candidates': []},
])
def test_revision_requires_the_exact_safe_shape_for_automatic_work(changes):
    selected = select_product_route(route_view(), diagnostic(**changes))
    assert selected['target_node'] == 'memory_report'
    assert selected['human_request'] is None


class ReviewFixture:
    """Offline domain fixture; the actual Host owns every call and transition."""
    timeout_seconds = 10

    def __init__(self, *, resolved=True, failed=False):
        self.resolved, self.failed = resolved, failed
        self.plans, self.reviews, self.calls = [], 0, 0

    def run(self, *args, **kwargs):
        raise AssertionError('A scoped research role must not enter the outer LLM reservation')

    def run_scoped(self, node, context, *, timeout_seconds, port):
        for index in range(1 if node == 'analysis_engineer' else 2):
            self.calls += 1
            product_resource(port, resource_kind='llm_call',
                resource_id='domain-diagnosis' if index == 0 else 'second-role',
                input_digest=digest(context), config_digest=digest({'node': node, 'structured_output': True}),
                timeout_seconds=2, effect=lambda: {'offline_fixture': node})
        if node == 'method_planner':
            self.plans.append(deepcopy(context))
            return {'diagnostic': diagnostic(category='plan', affected_layer='none', candidates=[]),
                    'content': {'code_needed': False, 'purpose': 'Offline control-flow fixture'}}
        if node == 'analysis_engineer':
            return {'diagnostic': diagnostic(category='analysis', affected_layer='none', candidates=[]),
                    'content': {'fixture_result': True}}
        assert node == 'scientific_reviewer'
        self.reviews += 1
        if self.failed:
            value = diagnostic(status='failed', category='scientific_review', affected_layer='review',
                retryability='not_retryable', candidates=[], human_need='approval', risk='high')
        elif self.resolved and self.reviews > 1:
            value = diagnostic(category='scientific_review', affected_layer='review',
                retryability='not_retryable', candidates=[], human_need='approval', risk='high')
        else:
            value = diagnostic()
        return {'diagnostic': value, 'content': {'collaboration': {'challenges': QUESTIONS,
            'summary': 'PI synthesis retains the covariance limitation.',
            'issues': [{'id': 'window', 'question': QUESTIONS[0], 'response': None,
                        'evidence_references': [], 'status': 'open'}],
            'exchanges': [{'role': 'reviewer', 'proposal': {'summary': 'Independent conclusion: inspect the covariance.'},
                           'discussion': {'summary': 'The reviewer requests an independent covariance check.'}},
                          {'role': 'pi', 'discussion': {'summary': 'PI recommends reporting the limitation explicitly.'}}]},
            'warnings': ['Finite-volume study remains outstanding.'],
            'review_context': 'The first fit and its covariance must remain inspectable.'}}


def execute_review(agent, *, expected_error=None):
    host = Path(mkdtemp(prefix='lqcd-revision-', dir=execution_scratch_root()))
    with closing(Coordinator(host, clock=FakeClock(100, 0))) as coordinator:
        actor = ActorContext('operator', 'human', ('control.internal', 'resume', 'start'))
        runtime = CanonicalProductRuntime(coordinator, worker_id='worker', actor=actor, agent_port=agent)
        inputs = {'root_goal': {'goal': 'Compare two fit explanations'},
                  'input_snapshot': {'kind': 'offline_revision_fixture'}}
        started = runtime.plane.start_run(StartRunRequest('case', inputs, digest(inputs), 'revision'), actor=actor)
        locator = started['result']['run_locator']
        if expected_error is None:
            runtime.run(locator)
        else:
            with pytest.raises(expected_error):
                runtime.run(locator)
        root = host / locator['case_id'] / locator['run_id']
        control = loads(coordinator.connection.execute('SELECT value FROM run_controls').fetchone()[0])
        validate_run_root(root, manifest=control['manifest'], projection=control['projection'])
        return root, parse_ledger((root / 'execution_history.jsonl').read_bytes()), loads((root / 'artifact_index.json').read_bytes())


@pytest.mark.parametrize('resolved', [True, False])
def test_scoped_review_replans_with_questions_and_closes_without_a_person(resolved):
    agent = ReviewFixture(resolved=resolved)
    root, execution, index = execute_review(agent)
    state, records = execution.projection.value, execution.values
    assert state['run_status'] == ('completed' if resolved else 'halted') and state['cycle_index'] == 2
    assert len(agent.plans) == agent.reviews == 2
    assert not any(row.get('event') == 'failure_observed' for row in records)
    assert state['budget']['dimensions']['automatic_replan_per_run']['used'] == 1
    resources = [row for row in records if row.get('event') == 'resource_reserved']
    assert len(resources) == agent.calls == 10
    assert len([row for row in records if row.get('event') == 'resource_settled']) == len(resources)
    assert all(row['status'] == 'succeeded' for row in records if row['record_type'] == 'attempt'
               and row['event'] == 'finished' and row['attempt_kind'] != 'human_gate')
    remediation = agent.plans[1]['remediation']
    assert remediation['success_criteria'] == QUESTIONS
    reviews = [loads(line)['pointer'] for line in (root / 'artifact_history.jsonl').read_bytes().splitlines()
               if loads(line)['event'] == 'registered' and loads(line)['slot'] == 'review']
    original = next(member for member in reviews[0]['members'] if member['logical_name'] == 'scientific_review_report.json')
    evidence = {'artifact_id': reviews[0]['artifact_id'], 'member': original['canonical_path'], 'sha256': original['sha256']}
    assert evidence in remediation['evidence'] and evidence in agent.plans[1]['current_evidence']
    raw = (root / original['canonical_path']).read_bytes()
    assert sha256(raw).hexdigest() == original['sha256']
    assert loads(raw)['review_context'].startswith('The first fit')
    assert index['current']['terminal'] is not None and index['current']['approval'] is None
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in records)
    if resolved:
        decision = loads(Path(index['current']['decision']['state_paths']['decision_log_path']).read_bytes())
        assert decision['risk_level'] == 'high'
    else:
        inbound = next(row for row in records if row['record_type'] == 'transition'
                       and row['target_attempt_id'] == index['current']['terminal']['attempt_id'])
        assert inbound['trigger_reason'] == 'budget_stop'


def test_actual_scoped_review_failure_keeps_its_original_failure_anchor():
    agent = ReviewFixture(failed=True)
    _, execution, _ = execute_review(agent)
    assert execution.projection.value['run_status'] == 'completed'
    failures = [row for row in execution.values if row.get('event') == 'failure_observed']
    assert len(failures) == 1 and failures[0]['payload']['occurrence'] == 1
    assert len(agent.plans) == 1


def test_system_final_report_preserves_independent_review_and_unresolved_limitations():
    root, execution, index = execute_review(ReviewFixture())
    assert execution.projection.value['run_status'] == 'completed'
    terminal = index['current']['terminal']
    assert terminal['status'] == 'accepted'
    report = Path(terminal['state_paths']['final_report_path']).read_text()
    for required in ('PI recommends reporting the limitation explicitly.',
                     'Independent conclusion: inspect the covariance.', QUESTIONS[0],
                     'Finite-volume study remains outstanding.', 'Decision origin: system.'):
        assert required in report
    for slot in ('plan', 'analysis', 'review'):
        pointer = index['current'][slot]
        name = {'plan': 'method_plan.json', 'analysis': 'run_result.json', 'review': 'scientific_review_report.json'}[slot]
        member = next(item for item in pointer['members'] if item['logical_name'] == name)
        assert pointer['artifact_id'] in report and member['sha256'] in report
    history = [loads(line) for line in (root/'artifact_history.jsonl').read_bytes().splitlines()]
    assert any(row['event'] == 'protected_snapshot_registered' and row.get('protected_kind') == 'accepted_result'
               and row['artifact_id'] == terminal['artifact_id'] for row in history)


def test_first_model_budget_denial_has_no_fabricated_execution_or_failure():
    calls = []

    class DeniedResearch:
        timeout_seconds = 1

        def run_scoped(self, node, context, *, timeout_seconds, port):
            assert node == 'method_planner'
            return product_resource(port, resource_kind='llm_call', resource_id='domain-diagnosis',
                input_digest=digest(context), config_digest=digest({'node': node, 'structured_output': True}),
                timeout_seconds=policy().value['limits']['active_seconds_per_attempt'] + 1,
                effect=lambda: calls.append('should not execute'))

    _, execution, index = execute_review(DeniedResearch())
    assert execution.projection.value['run_status'] == 'halted'
    assert not calls
    assert not any(row.get('event') in ('resource_reserved', 'resource_settled', 'failure_observed')
                   for row in execution.values)
    planner = loads(Path(index['current']['plan']['state_paths']['method_plan_path']).read_bytes())
    assert planner['status'] == 'failed' and planner['resource_admission'] == 'denied'
    assert planner['code_needed'] is False
    decision = loads(Path(index['current']['decision']['state_paths']['decision_log_path']).read_bytes())
    assert decision['reasons'] == ['budget'] and decision['risk_level'] == 'high'
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in execution.values)
    terminal = index['current']['terminal']
    conclusion = loads(Path(terminal['state_paths']['memory_update_path']).read_bytes())
    assert terminal['status'] == 'rejected' and conclusion['scientific_outcome'] == 'inconclusive'


@pytest.mark.parametrize('risk', ['high', 'critical'])
def test_scientific_risk_alone_does_not_require_permission(risk):
    selected = select_product_route(route_view(), diagnostic(risk=risk))
    assert selected['target_node'] == 'method_planner' and selected['human_request'] is None


@pytest.mark.parametrize('category', ['data', 'security', 'policy', 'integrity.seal'])
def test_hard_failure_cannot_be_overridden_by_an_approval(category):
    selected = select_product_route(route_view(), diagnostic(category=category),
        human_authorization={'target_node': 'method_planner'})
    assert selected['target_node'] == 'memory_report' and selected['human_request'] is None


def test_only_explicit_host_authorization_opens_a_human_gate():
    selected = select_product_route(route_view(), diagnostic(category='authorization',
        human_need='approval', risk='high'))
    assert selected['target_node'] == 'human_gate'
    assert selected['human_request']['request_kind'] == 'approval'
    assert selected['human_request']['authorization_scope']['work_target'] == 'method_planner'


@pytest.mark.parametrize('occurrence,target', [(1, 'analysis_engineer'), (2, 'memory_report')])
def test_confirmed_failure_retries_once_without_requesting_scientific_approval(occurrence, target):
    view = route_view()
    view['state']['budget']['active_failure']['occurrence'] = occurrence
    selected = select_product_route(view, diagnostic(status='failed', category='analysis_execution',
        candidates=['analysis_engineer'], affected_layer='analysis', risk='high',
        evidence=[{'artifact_id': 'analysis', 'member': 'result.json', 'sha256': '1' * 64}]))
    assert selected['target_node'] == target and selected['human_request'] is None


@pytest.mark.parametrize('resource_kind,resource_id', [
    ('llm_call', 'domain-diagnosis'), ('tool_call', 'research-context-count')])
def test_ended_execution_failure_concludes_with_real_failure_evidence(resource_kind, resource_id):
    calls = []
    class FailedResearch:
        timeout_seconds = 1
        def run_scoped(self, node, context, *, timeout_seconds, port):
            def fail():
                calls.append(node)
                raise RuntimeError('Offline failure: no scientific output was produced.')
            return product_resource(port, resource_kind=resource_kind, resource_id=resource_id,
                input_digest=digest(context), config_digest=digest({'node': node, 'structured_output': True}),
                timeout_seconds=1, effect=fail)
    root, execution, index = execute_review(FailedResearch())
    assert calls == ['method_planner']
    assert execution.projection.value['run_status'] == 'completed'
    assert index['current']['analysis'] is None and index['current']['review'] is None
    assert not any(row['record_type'] in ('human_request', 'human_response') for row in execution.values)
    terminal = index['current']['terminal']
    conclusion = loads(Path(terminal['state_paths']['memory_update_path']).read_bytes())
    assert terminal['status'] == 'rejected' and conclusion['scientific_outcome'] == 'inconclusive'
    assert conclusion['decision_origin'] == 'system' and not conclusion['accepted_result']
    report = Path(terminal['state_paths']['final_report_path']).read_text()
    assert 'Offline failure: no scientific output was produced.' in report
    planner = loads(Path(index['current']['plan']['state_paths']['method_plan_path']).read_bytes())
    assert planner['status'] == 'failed' and planner['code_needed'] is False
    reservations = [row['payload'] for row in execution.values if row.get('event') == 'resource_reserved']
    assert len(reservations) == 1 and reservations[0]['resource_kind'] == resource_kind
    assert reservations[0]['resource_operation_id'].endswith(':' + resource_id)
    settlements = [row['payload'] for row in execution.values if row.get('event') == 'resource_settled']
    assert len(settlements) == 1 and settlements[0]['actual'] is None


def test_integrity_failure_is_not_reclassified_as_an_ordinary_research_result():
    from lqcd_agent.control.strict_json import ControlIntegrityError
    class CorruptResearch:
        timeout_seconds = 1
        def run_scoped(self, node, context, *, timeout_seconds, port):
            def fail():
                raise ControlIntegrityError('Fixture evidence identity changed.')
            return product_resource(port, resource_kind='llm_call', resource_id='domain-diagnosis',
                input_digest=digest(context), config_digest=digest({'fixture': 'integrity_failure'}),
                timeout_seconds=1, effect=fail)
    _, execution, index = execute_review(CorruptResearch(), expected_error=ControlIntegrityError)
    assert execution.projection.value['run_status'] == 'failed'
    failed = next(row for row in reversed(execution.values) if row['record_type'] == 'attempt')
    assert failed['event'] == 'finished' and failed['status'] == 'failed'
    assert failed['error'] == {'type': 'ControlIntegrityError', 'message': 'Fixture evidence identity changed.'}
    assert index['current']['terminal'] is None
    assert not any(row['record_type'] == 'human_response' for row in execution.values)


@pytest.mark.parametrize('permission', [None, 'approve_with_conditions', 'reject_or_hold'])
def test_permission_choice_does_not_change_a_supported_scientific_conclusion(permission):
    from lqcd_agent.memory.store import classify_memory_update
    result = classify_memory_update(complete_evidence=True, blocked=False, limitations=True,
                                   authorization_decision=permission)
    assert result['scientific_outcome'] == 'qualified' and result['accepted_result']
    assert result['decision_origin'] == 'system' and result['authorization_decision'] == permission
    missing = classify_memory_update(complete_evidence=False, blocked=True, limitations=True,
                                    authorization_decision=permission)
    assert missing['scientific_outcome'] == 'inconclusive' and not missing['accepted_result']
