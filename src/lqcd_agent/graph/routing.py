from __future__ import annotations
PRODUCT_ROUTES = {'START': ('method_planner',), 'method_planner': ('analysis_engineer', 'code_agent', 'decision_coordinator'), 'code_agent': ('analysis_engineer', 'decision_coordinator'), 'analysis_engineer': ('scientific_reviewer', 'decision_coordinator'), 'scientific_reviewer': ('decision_coordinator',), 'decision_coordinator': ('scientific_reviewer', 'analysis_engineer', 'code_agent', 'method_planner', 'human_gate', 'memory_report'), 'human_gate': ('decision_coordinator',), 'memory_report': ('end',)}
PRODUCT_FALLBACKS = {'method_planner': ('replan', 'automatic_replan_per_run'), 'code_agent': ('code_fix', 'automatic_code_fix_per_cycle'), 'analysis_engineer': ('analysis_rerun', 'automatic_analysis_rerun_per_cycle'), 'scientific_reviewer': ('re_review', 'automatic_re_review_per_cycle')}

def product_budget_decision(state, *, target, trigger, risk, stop_sequence_id=None, proposed_grant=None):
    """Admit an exact route from replayed counters without modifying the input."""
    from lqcd_agent.control.budget import WORK_KINDS, validate_budget_payload
    from lqcd_agent.control.strict_json import digest, require
    budget = state['budget']
    changes = {'cycles_per_run': int(trigger == 'replan'), 'work_attempts_per_run': int(target in WORK_KINDS), 'control_attempts_per_run': int(target is not None and target not in WORK_KINDS), 'transitions_per_run': 1}
    route_dimension = PRODUCT_FALLBACKS.get(target, (None, None))[1] if trigger in {row[0] for row in PRODUCT_FALLBACKS.values()} else None
    if route_dimension is not None:
        changes[route_dimension] = 1
    dimensions = {key: {**value, 'projected_after': value['used'] + changes.get(key, 0)} for key, value in budget['dimensions'].items()}
    failure = budget['active_failure']
    grant = budget['active_grant']
    if proposed_grant is not None:
        require(grant is None and stop_sequence_id is None, 'Proposed grant cannot replace an active grant or terminal reserve')
        validate_budget_payload('grant_issued', proposed_grant)
        grant = proposed_grant
    if grant is not None:
        require(grant['target_node'] == target and grant['route_dimension'] == route_dimension and (failure is not None) and (grant['fingerprint_digest'] == failure['fingerprint_digest']) and (grant['occurrence'] == failure['occurrence']), 'Active grant does not match this route proposal')
    exceeded = [key for key, value in dimensions.items() if changes.get(key, 0) > value['remaining'] and (not (grant is not None and key == route_dimension))]
    if stop_sequence_id is None:
        for key, reserve in (('control_attempts_per_run', 5), ('transitions_per_run', 6)):
            if changes.get(key, 0) + reserve > dimensions[key]['remaining']:
                exceeded.append(key)
    else:
        require(target not in WORK_KINDS, 'Terminal reserve cannot dispatch work')
    action = 'halt' if exceeded else 'allow'
    body = {'schema_version': '0.1', 'proposal_id': digest({'source': state['attempt_id'], 'target': target, 'trigger': trigger, 'stop_sequence_id': stop_sequence_id}), 'proposed_action': 'route', 'target_kind': target, 'risk': risk, 'fingerprint_digest': failure['fingerprint_digest'] if failure else None, 'occurrence': failure['occurrence'] if failure else 0, 'dimensions': dimensions, 'budget_grant_id': grant['budget_grant_id'] if grant else None, 'decision': action, 'reason_code': 'capacity_exhausted' if exceeded else 'canonical_route_admitted', 'next_control_action': 'close_run' if exceeded else 'advance'}
    result = {**body, 'decision_digest': digest(body)}
    validate_budget_payload('decision_recorded', result)
    return result

def select_product_route(view, diagnostic, *, code_needed=False, code_usable=False, human_response=None, human_authorization=None, stop_sequence_id=None, proposed_grant=None):
    """Select a canonical edge from verified outcomes; Agents cannot select it."""
    from lqcd_agent.agents.decision_coordinator import validate_product_diagnostic
    from lqcd_agent.control.strict_json import digest, require
    diagnostic = validate_product_diagnostic(diagnostic)
    source, state = (view['source'], view['state'])
    node = source['node_name']
    require(node in PRODUCT_ROUTES, 'Legacy node cannot enter the canonical graph')
    success = source['status'] == 'succeeded' and diagnostic['status'] == 'success'
    safety_failure = diagnostic['category'] in ('security', 'policy', 'data') or (diagnostic['category'].startswith('scientific') and diagnostic['status'] != 'success' and (diagnostic['retryability'] != 'retryable'))
    forward = success and diagnostic['risk'] in ('low', 'medium') and (diagnostic['confidence'] == 'unique') and (diagnostic['human_need'] is None and (not safety_failure))
    trigger = 'forward'
    request = None
    if node == 'method_planner':
        target = ('code_agent' if code_needed else 'analysis_engineer') if forward else 'decision_coordinator'
    elif node == 'code_agent':
        target = 'analysis_engineer' if forward and code_usable else 'decision_coordinator'
    elif node == 'analysis_engineer':
        target = 'scientific_reviewer' if forward else 'decision_coordinator'
    elif node == 'scientific_reviewer':
        target = 'decision_coordinator'
    elif node == 'human_gate':
        require(human_response is not None and human_response['status'] == 'validated' and (human_response['validator_attempt_id'] == source['attempt_id']) and (human_response['authorized_transition_target'] == 'decision_coordinator'), 'Human edge requires an exact validated response')
        target, trigger = ('decision_coordinator', 'human_response')
    elif node == 'memory_report':
        require(success, 'END requires a completed deterministic terminal sink')
        target = None
    else:
        from lqcd_agent.control.budget import policy
        candidates = diagnostic['candidates']
        failure = state['budget']['active_failure']
        selected_policy = policy(state['budget']['profile_id']).value
        reserve = selected_policy['terminal_reserve']
        dimensions = state['budget']['dimensions']
        repeat = (diagnostic['status'] != 'success' or bool(diagnostic['candidates'])) and failure is not None and (failure['occurrence'] >= 2)
        needs_human = diagnostic['risk'] in ('high', 'critical') or diagnostic['confidence'] != 'unique' or repeat or (diagnostic['human_need'] is not None) or safety_failure
        if stop_sequence_id is not None:
            target, trigger = ('memory_report', 'budget_stop')
        elif human_authorization is not None:
            require(human_authorization['target_node'] in candidates or human_authorization['target_node'] == 'memory_report', 'Human authorization does not match the diagnosed work scope')
            require(diagnostic['category'] not in ('security', 'policy', 'data'), 'Authorization cannot override a hard safety gate')
            target = human_authorization['target_node']
        elif candidates and (not needs_human) and (diagnostic['retryability'] == 'retryable'):
            require(len(candidates) == 1, 'Ambiguous fallback cannot dispatch work')
            target = candidates[0]
        elif needs_human or candidates:
            target = 'human_gate'
        else:
            target = 'memory_report'
        if target in PRODUCT_FALLBACKS:
            trigger = PRODUCT_FALLBACKS[target][0]
            decision = product_budget_decision(state, target=target, trigger=trigger, risk=diagnostic['risk'], proposed_grant=proposed_grant)
            if decision['decision'] != 'allow':
                route_dimension = PRODUCT_FALLBACKS[target][1]
                grant_possible = human_authorization is None and failure is not None and (state['budget']['active_grant'] is None) and (not safety_failure) and (diagnostic['confidence'] == 'unique') and (diagnostic['retryability'] == 'retryable') and (dimensions[route_dimension]['remaining'] == 0) and all((row['projected_after'] - row['used'] <= row['remaining'] for key, row in decision['dimensions'].items() if key != route_dimension)) and (dimensions['control_attempts_per_run']['remaining'] >= 3 + reserve['control_attempts']) and (dimensions['transitions_per_run']['remaining'] >= 4 + reserve['transitions'])
                target, trigger = ('human_gate', 'forward' if grant_possible else 'budget_stop')
        if target == 'human_gate':
            if any((dimensions[key]['remaining'] < 2 + reserve[reserve_key] for key, reserve_key in (('control_attempts_per_run', 'control_attempts'), ('transitions_per_run', 'transitions')))):
                trigger = 'budget_stop'
            target_scope = candidates[0] if len(candidates) == 1 and trigger != 'budget_stop' else None
            decisions = ['approve_with_conditions', 'reject_or_hold']
            if target_scope is not None:
                decisions.extend(['approve_budget_window', 'approve_rerun' if target_scope == 'analysis_engineer' else 'request_code_change' if target_scope == 'code_agent' else 'approve_with_conditions'])
            decisions = sorted(set(decisions))
            request = {'request_kind': diagnostic['human_need'] or 'approval', 'authorization_scope': {'allowed_decisions': decisions, 'allowed_target_nodes': ['decision_coordinator'], 'decision_transition_routes': dict.fromkeys(decisions, 'decision_coordinator'), 'decision_transition_targets': dict.fromkeys(decisions, 'decision_coordinator'), 'work_target': target_scope, 'failure_fingerprint': failure, 'diagnostic_digest': digest(diagnostic)}}
    require((target or 'end') in PRODUCT_ROUTES[node], 'Undeclared canonical product edge')
    sequence = stop_sequence_id
    if target == 'human_gate' and sequence is None and (trigger == 'budget_stop'):
        sequence = digest({'run_id': state['run_id'], 'source_attempt_id': source['attempt_id'], 'reason': 'budget_stop'})
    decision = product_budget_decision(state, target=target, trigger=trigger, risk=diagnostic['risk'], stop_sequence_id=sequence, proposed_grant=proposed_grant)
    if sequence is not None and target == 'human_gate' and any((state['budget']['dimensions'][key]['remaining'] < needed for key, needed in (('control_attempts_per_run', 4), ('transitions_per_run', 5)))):
        decision.update(decision='halt', reason_code='terminal_tail_capacity', next_control_action='close_run')
        decision['decision_digest'] = digest({k: v for k, v in decision.items() if k != 'decision_digest'})
    if decision['decision'] != 'allow' and node != 'decision_coordinator' and (target not in (None, 'decision_coordinator')):
        target, trigger = ('decision_coordinator', 'budget_stop')
        sequence = digest({'run_id': state['run_id'], 'source_attempt_id': source['attempt_id'], 'reason': 'budget_stop'})
        decision = product_budget_decision(state, target=target, trigger=trigger, risk=diagnostic['risk'], stop_sequence_id=sequence)
    return {'target_node': target, 'route': target or 'end', 'trigger_reason': trigger, 'budget_decision': decision, 'human_request': request, 'stop_sequence_id': sequence}
