from __future__ import annotations
from typing import TypedDict
from langgraph.graph import END, START, StateGraph

class ProductCursor(TypedDict):
    attempt_id: str
    transition_id: str
    run_locator: dict

class ProductRouteAdapter:
    """Resolve immutable domain facts before the original advance reservation."""

    def __init__(self, coordinator, analysis_handoff=None):
        self.coordinator, self.analysis_handoff = (coordinator, analysis_handoff)

    def admit(self, view):
        from pathlib import Path
        from lqcd_agent.artifacts.contracts import SLOT_BY_ATTEMPT_KIND
        from lqcd_agent.control.coordinator import read_regular
        from lqcd_agent.control.execution import parse_ledger
        from lqcd_agent.control.operations import RouteAdmission
        from lqcd_agent.control.strict_json import loads, require
        from lqcd_agent.graph.nodes import product_diagnostic
        from lqcd_agent.graph.routing import select_product_route
        from lqcd_agent.control.identity import canonical_attempt_kind, stable_attempt_id, stable_transition_id
        root = self.coordinator.root / view['run_locator']['case_id'] / view['run_locator']['run_id']
        records = parse_ledger(read_regular(root / 'execution_history.jsonl')).values
        source = view['source']
        node = source['attempt_kind']
        require(canonical_attempt_kind(source['node_name']) == node, 'Product source physical node/kind mismatch')
        view = {**view, 'source': {**source, 'node_name': node}}
        index = loads(read_regular(root / 'artifact_index.json'))
        pointer = index['current'][SLOT_BY_ATTEMPT_KIND[source['attempt_kind']]]
        response, authorization = (None, None)
        if node in ('human_gate', 'memory_report'):
            diagnostic = {'status': 'success', 'category': 'deterministic_control', 'affected_layer': 'none', 'evidence': [], 'retryability': 'not_retryable', 'candidates': [], 'confidence': 'unique', 'fingerprint': None, 'human_need': None, 'risk': 'low'}
            if node == 'human_gate':
                response = next((row for row in reversed(records) if row['record_type'] == 'human_response'))
        else:
            diagnostic = product_diagnostic(root, pointer)
            if node == 'decision_coordinator':
                content = loads(read_regular(Path(pointer['state_paths']['decision_log_path'])))
                authorization = content.get('human_authorization')
        inbound = next((row for row in records if row['record_type'] == 'transition' and row['target_attempt_id'] == source['attempt_id']))
        code_needed = False
        if node == 'method_planner':
            code_needed = loads(read_regular(Path(pointer['state_paths']['method_plan_path']))).get('code_needed')
            require(type(code_needed) is bool, 'Unstructured Planner code requirement')
        selected = select_product_route(view, diagnostic, code_needed=code_needed, code_usable=node == 'code_agent' and pointer['status'] == 'success' and (diagnostic['status'] == 'success'), human_response=response, human_authorization=authorization, stop_sequence_id=inbound['fields'].get('stop_sequence_id'))
        require(selected['budget_decision']['decision'] == 'allow', 'Terminal budget decision must precede close, not advance')
        preparation = {'preparation_kind': 'not_applicable', 'not_applicable_reason': 'no_code_bundle'}
        if selected['target_node'] == 'analysis_engineer' and view['selected_code'] is not None:
            require(self.analysis_handoff is not None, 'Verified Code requires the original fresh Analysis adapter')
            preparation = self.analysis_handoff.snapshot(view, stable_attempt_id(view['next_attempt_index']), stable_transition_id(view['next_transition_index']))
        return RouteAdmission(selected['target_node'], selected['route'], selected['trigger_reason'], 'canonical_guarded_route', selected['budget_decision'], preparation, selected['human_request'], {'stop_sequence_id': selected['stop_sequence_id']} if selected['stop_sequence_id'] else {})

    def repause(self, view):
        from lqcd_agent.control.operations import RepauseAdmission
        from lqcd_agent.control.strict_json import digest, require
        continuation = view['human_continuation']
        require(set(continuation) == {'mode', 'validator_transition_head', 'stop_sequence_id', 'budget_stop_transition_head'} and continuation['mode'] in ('ordinary', 'terminal') and all((isinstance(continuation[k], str) and len(continuation[k]) == 64 for k in ('validator_transition_head',))), 'Invalid repause continuation')
        terminal = continuation['mode'] == 'terminal'
        require(all((isinstance(continuation[k], str) and len(continuation[k]) == 64 if terminal else continuation[k] is None for k in ('stop_sequence_id', 'budget_stop_transition_head'))), 'Unbound repause capacity mode')
        reserve = view['policy']['terminal_reserve']
        required = {'control_attempts_per_run': 3 if terminal else 1 + reserve['control_attempts'], 'transitions_per_run': 4 if terminal else 1 + reserve['transitions']}
        dimensions = {key: {**row, 'projected_after': row['used'] + required.get(key, 0)} for key, row in view['budget']['dimensions'].items()}
        sufficient = all((required.get(key, 0) <= row['remaining'] for key, row in dimensions.items()))
        failure = view['budget']['active_failure']
        binding = {**view['binding'], 'terminal_tail_capacity': dimensions}
        body = {'schema_version': '0.1', 'proposal_id': digest(binding), 'proposed_action': 'repause', 'target_kind': 'human_gate', 'risk': 'high', 'fingerprint_digest': failure['fingerprint_digest'] if failure else None, 'occurrence': failure['occurrence'] if failure else 0, 'dimensions': dimensions, 'budget_grant_id': None, 'decision': 'allow' if sufficient else 'halt', 'reason_code': 'invalid_response_tail_capacity', 'next_control_action': 'publish_pause' if sufficient else 'close_run'}
        return RepauseAdmission('sufficient' if sufficient else 'insufficient', {**body, 'decision_digest': digest(body)})

    def verify_preparation_source(self, value):
        return self.analysis_handoff.verify_preparation_source(value)

    def materialize_preparation(self, value, port):
        return self.analysis_handoff.materialize_preparation(value, port)

    def verify_preparation(self, value):
        return self.analysis_handoff.verify_preparation(value)

class CanonicalProductRuntime:
    """Execute the compiled graph while B02 alone owns durable progression."""

    def __init__(self, coordinator, *, worker_id, actor, agent_port, analysis_handoff=None, code_host=None, external_adapter=None):
        from lqcd_agent.control.interfaces import ControlPlane
        self.coordinator, self.worker_id, self.actor, self.agent_port = (coordinator, worker_id, actor, agent_port)
        self.analysis_handoff, self.code_host = (analysis_handoff, code_host)
        self.external_adapter = code_host.consumer if external_adapter is None and code_host is not None else external_adapter
        self.route_adapter = ProductRouteAdapter(coordinator, analysis_handoff)
        self.plane = ControlPlane(coordinator, worker_id=worker_id, route_adapter=self.route_adapter, resume_decision_adapter=self.route_adapter, external_adapter=self.external_adapter, preparation_adapter=analysis_handoff)
        self.app = build_product_graph(self).compile()

    def _records(self, locator):
        from lqcd_agent.control.coordinator import read_regular
        from lqcd_agent.control.execution import parse_ledger
        root = self.coordinator.root / locator['case_id'] / locator['run_id']
        return (root, parse_ledger(read_regular(root / 'execution_history.jsonl')))

    def run(self, locator):
        from lqcd_agent.control.strict_json import require
        _, execution = self._records(locator)
        require(execution.projection.value['schema_version'] == '0.4', 'Canonical entry rejects legacy Runs')
        first = next((row for row in execution.values if row['record_type'] == 'transition' and row['source_node'] == 'START'))
        return self.app.invoke({'run_locator': locator, 'attempt_id': first['target_attempt_id'], 'transition_id': first['transition_id']}, {'recursion_limit': 128})

    def resume(self, request, *, actor):
        previous = self.coordinator.lookup_key('public_control', request.idempotency_key)
        replay = previous is not None and previous['status'] == 'committed'
        result = self.resume_control(request, actor=actor)
        if not replay and result['operation_status'] == 'committed' and (result['run_status'] == 'running'):
            self.run(request.run_locator)
        return result

    def resume_control(self, request, *, actor):
        from lqcd_agent.graph.nodes import ProductNode
        root, _ = self._records(request.run_locator)
        self.plane.resume_target_adapter = self.external_adapter if request.input_kind == 'external_result' else ProductNode(root, self.agent_port)
        return self.plane.resume_run(request, actor=actor)

    def read_route(self, cursor):
        from lqcd_agent.control.strict_json import require
        _, execution = self._records(cursor['run_locator'])
        transition = next((row for row in execution.values if row['record_type'] == 'transition' and row['transition_id'] == cursor['transition_id']))
        require(transition['status'] == 'committed', 'Conditional reader requires a committed Transition')
        return transition['route']

    def _close_failed_attempt(self, locator, attempt_id):
        """Close only a committed failed target with no registered result."""
        from lqcd_agent.artifacts.contracts import SLOT_BY_ATTEMPT_KIND
        from lqcd_agent.control.coordinator import read_regular
        from lqcd_agent.control.operations import CloseRunRequest
        from lqcd_agent.control.strict_json import loads
        root, execution = self._records(locator)
        failed = execution.values[-1]
        if (failed['record_type'] != 'attempt' or failed['event'] != 'finished' or
                failed['attempt_id'] != attempt_id or failed['status'] != 'failed' or failed['error'] is None):
            return None
        index = loads(read_regular(root / 'artifact_index.json'))
        if index['current'][SLOT_BY_ATTEMPT_KIND[failed['attempt_kind']]] is not None:
            return None
        return self.plane.close_run(CloseRunRequest(locator, execution.projection.value['execution_head']),
                                    actor=self.actor)

    def node(self, node_name, cursor):
        from langgraph.types import interrupt
        from lqcd_agent.control.capabilities import InvocationLeases
        from lqcd_agent.control.operations import AdvanceRunRequest, CloseRunRequest
        from lqcd_agent.control.pause import PublishPauseRequest
        from lqcd_agent.control.strict_json import digest, loads, require
        from lqcd_agent.graph.nodes import ProductNode
        locator = cursor['run_locator']
        root, execution = self._records(locator)
        records, attempt_id = (execution.values, cursor['attempt_id'])
        life = [row for row in records if row['record_type'] == 'attempt' and row['attempt_id'] == attempt_id]
        require(life and life[0]['node_name'] == node_name, 'Graph cursor does not match its original target')
        outbound = next((row for row in records if row['record_type'] == 'transition' and row['source_attempt_id'] == attempt_id), None)
        if node_name == 'human_gate' and life[-1]['status'] == 'pending':
            request = next((row for row in records if row['record_type'] == 'human_request' and row['requesting_attempt_id'] == life[0]['parent_attempt_id']))
            response = next((row for row in reversed(records) if row['record_type'] == 'human_response' and row['human_request_id'] == request['human_request_id'] and (row['status'] in ('validated', 'consumed'))), None)
            if response is not None:
                attempt_id = response['validator_attempt_id']
                life = [row for row in records if row['record_type'] == 'attempt' and row['attempt_id'] == attempt_id]
                outbound = next((row for row in records if row['record_type'] == 'transition' and row['source_attempt_id'] == attempt_id), None)
        if outbound is not None:
            return {'attempt_id': outbound['target_attempt_id'], 'transition_id': outbound['transition_id']}
        state = execution.projection.value
        if state['run_status'] == 'paused':
            pause = state['active_pause']
            interrupt({'run_locator': locator, **({'pause_id': pause['pause_id']} if pause is not None else {'run_status': state['run_status']})})
        if state['run_status'] in ('halted', 'failed'):
            interrupt({'run_locator': locator, 'run_status': state['run_status']})
        if life[-1]['event'] == 'finished':
            completions = [(row['capability_id'], value) for row in self.coordinator.connection.execute('SELECT capability_id,value FROM invocation_capabilities') for value in [loads(row['value'])]]
            completions = [(key, value) for key, value in completions if value['authorization']['identity'] == {**locator, 'attempt_id': attempt_id, 'attempt_kind': life[-1]['attempt_kind']} and value['state'] == 'started' and (value.get('completion_intent') is not None) and ('external_consumption' not in value['authorization'])]
            if completions:
                require(len(completions) == 1, 'Finished target has conflicting completion owners')
                (capability_id, completion), = completions
                leases = InvocationLeases(self.coordinator, decision_adapter=self.route_adapter, preparation_adapter=self.route_adapter)
                leases.publish_completion(capability_id, self.worker_id, completion['invocation_epoch'])
                _, execution = self._records(locator)
                records = execution.values
        if life[-1]['event'] != 'finished':
            rows = self.coordinator.connection.execute('SELECT capability_id,value FROM invocation_capabilities').fetchall()
            matches = [(row['capability_id'], loads(row['value'])) for row in rows if loads(row['value'])['authorization']['identity']['attempt_id'] == attempt_id and all((loads(row['value'])['authorization']['identity'][key] == locator[key] for key in locator))]
            require(len(matches) == 1, 'Target requires its original single capability')
            capability_id, capability = matches[0]
            if node_name == 'code_agent':
                require(self.code_host is not None, 'Canonical Code requires the trusted B03 parent adapter')
                self.code_host.prepare(capability_id, worker_id=self.worker_id, actor=self.actor)
                interrupt({'run_locator': locator, 'reason': 'external_result'})
            leases = InvocationLeases(self.coordinator, decision_adapter=self.route_adapter, preparation_adapter=self.route_adapter)
            if capability['started_intent'] is not None:
                require(capability.get('completion_intent') is not None, 'Started or uncertain target requires explicit recovery')
                state = leases.publish_completion(capability_id, self.worker_id, capability['invocation_epoch'])
            else:
                leased = leases.acquire(capability_id, self.worker_id, expected_epoch=capability['invocation_epoch'], lease_seconds=max(30, getattr(self.agent_port, 'timeout_seconds', 1) + (self.analysis_handoff.timeout_seconds if node_name == 'analysis_engineer' and self.analysis_handoff is not None else 0) + 30))
                preparation = capability['authorization'].get('target_preparation')
                try:
                    state = leases.invoke(capability_id, self.worker_id, leased['invocation_epoch'], ProductNode(root, self.agent_port, analysis_handoff=self.analysis_handoff, preparation=preparation))
                except Exception as error:
                    try:
                        self._close_failed_attempt(locator, attempt_id)
                    except Exception as closure_error:
                        raise error from closure_error
                    raise
            _, execution = self._records(locator)
            records = execution.values
            life = [row for row in records if row['record_type'] == 'attempt' and row['attempt_id'] == attempt_id]
        if records[-1]['record_type'] == 'budget' and records[-1]['payload'].get('decision') == 'halt':
            result = self.plane.close_run(CloseRunRequest(locator, digest(records[-1])), actor=self.actor)
            interrupt(result)
        if life[-1]['event'] == 'finished' and life[-1]['status'] == 'failed':
            result = self._close_failed_attempt(locator, attempt_id)
            if result is not None:
                interrupt(result)
        if node_name == 'human_gate' and life[-1]['status'] == 'pending':
            state = execution.projection.value
            self.plane.publish_pause(PublishPauseRequest(locator, 'human_input', attempt_id, None, {'kind': 'human_response', 'human_request_id': state['active_human_request_id']}, {'actor_type': 'human', 'scopes': ['resume']}, 'product-pause:' + digest(locator) + ':' + attempt_id), actor=self.actor)
            interrupt({'run_locator': locator, 'reason': 'human_input'})
        advanced = self.plane.advance_run(AdvanceRunRequest(locator, attempt_id, 'product-advance:' + digest(locator) + ':' + attempt_id), actor=self.actor)
        require(advanced['operation_status'] == 'committed', 'Canonical advance did not commit')
        _, execution = self._records(locator)
        transition = next((row for row in reversed(execution.values) if row['record_type'] == 'transition'))
        if transition['target_attempt_id'] is None:
            self.plane.close_run(CloseRunRequest(locator, digest(transition)), actor=self.actor)
        return {'attempt_id': transition['target_attempt_id'], 'transition_id': transition['transition_id']}

def build_product_graph(runtime):
    """The canonical A01 topology has exactly seventeen declared edges."""
    from lqcd_agent.graph.routing import PRODUCT_ROUTES
    graph = StateGraph(ProductCursor)
    for node in PRODUCT_ROUTES:
        if node != 'START':
            graph.add_node(node, lambda cursor, node_name=node: runtime.node(node_name, cursor))
    graph.add_edge(START, 'method_planner')
    for node, targets in PRODUCT_ROUTES.items():
        if node != 'START':
            graph.add_conditional_edges(node, runtime.read_route, {target: END if target == 'end' else target for target in targets})
    return graph
