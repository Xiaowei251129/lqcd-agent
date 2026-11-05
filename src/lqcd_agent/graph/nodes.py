from __future__ import annotations
from pathlib import Path
PRODUCT_FILES = {'method_planner': ('plan', 'method_plan.json', 'method_plan_path'), 'analysis_engineer': ('analysis', 'run_result.json', 'run_result_path'), 'scientific_reviewer': ('review', 'scientific_review_report.json', 'scientific_review_report_path'), 'decision_coordinator': ('decision', 'decision_log.json', 'decision_log_path')}

def product_diagnostic(root, pointer):
    """Read diagnostics only from an immutable, registered domain member."""
    from hashlib import sha256
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import loads, require
    from lqcd_agent.agents.decision_coordinator import validate_product_diagnostic
    require(pointer is not None, 'Product source has no registered domain outcome')
    if pointer['attempt_kind'] == 'code_agent':
        from lqcd_agent.code_agent.artifacts import validate_code_result
        from lqcd_agent.code_agent.schemas import validate_task
        members = {member['logical_name']: member for member in pointer['members']}
        values = {}
        for name in ('code_agent_task.json', 'code_agent_result.json'):
            member = members[name]
            raw = read_regular(Path(root) / member['canonical_path'])
            require(sha256(raw).hexdigest() == member['sha256'], 'Code source digest changed')
            values[name] = raw
        task = validate_task(values['code_agent_task.json']).value
        result = validate_code_result(values['code_agent_result.json'], task).value
        member = members['code_agent_result.json']
        usable = result['status'] == 'success' and result['usable'] is True
        return {'status': 'success' if usable else 'failed', 'category': result['status'], 'affected_layer': 'code', 'evidence': [{'artifact_id': pointer['artifact_id'], 'member': member['canonical_path'], 'sha256': member['sha256']}], 'retryability': 'retryable' if result['status'] in ('failed', 'no_change') else 'not_retryable', 'candidates': [] if usable else ['code_agent'], 'confidence': 'unique', 'fingerprint': None, 'human_need': None, 'risk': 'low' if usable else 'high'}
    name = pointer['attempt_kind'] + '_diagnostic.json'
    member = next((item for item in pointer['members'] if item['logical_name'] == name), None)
    require(member is not None, 'Source lacks structured canonical diagnostics')
    raw = read_regular(Path(root) / member['canonical_path'])
    require(sha256(raw).hexdigest() == member['sha256'], 'Diagnostic source digest changed')
    return validate_product_diagnostic(loads(raw))

def product_human_authorization(records, parent_attempt_id):
    """Derive work scope from a consumed snapshot, never its free text."""
    response = next((row for row in reversed(records) if row['record_type'] == 'human_response' and row['event'] == 'consumed' and (row['authorized_target_attempt_id'] == parent_attempt_id)), None)
    if response is None:
        return None
    request = next((row for row in records if row['record_type'] == 'human_request' and row['human_request_id'] == response['human_request_id'] and (row['event'] == 'created')))
    scope = request['authorization_scope']
    target = 'memory_report' if response['decision'] == 'reject_or_hold' or scope.get('work_target') is None else scope['work_target']
    return {'human_request_id': response['human_request_id'], 'human_response_id': response['human_response_id'], 'response_digest': response['payload_sha256'], 'target_node': target}

def product_failure_material(root, source, diagnostic, records, coordinator):
    """Derive scientific inputs independently of execution identity."""
    from hashlib import sha256
    from lqcd_agent.control.budget import fingerprint, semantic_context
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, require
    root = Path(root)
    history = [loads(line) for line in read_regular(root / 'artifact_history.jsonl').splitlines()]
    registrations = {row['artifact_id']: row for row in history if row['event'] == 'registered'}
    registration = registrations[source['artifact_id']]
    scheduled = next((row for row in records if row['record_type'] == 'attempt' and row['event'] == 'scheduled' and (row['attempt_id'] == source['attempt_id'])))
    resources = [row for row in records if row.get('event') == 'resource_reserved'
                 and row['payload']['attempt_id'] == source['attempt_id']]
    calls = [row for row in resources if (row['payload']['resource_kind'] == 'code_backend_operation'
             if source['attempt_kind'] == 'code_agent'
             else row['payload']['resource_operation_id'].endswith(':domain-diagnosis'))]
    require(len(calls) <= 1, 'Failure has conflicting resource anchors')
    call = calls[0] if calls else None
    if call is None:
        require(source['attempt_kind'] != 'code_agent' and all(
                row['payload']['resource_kind'] == 'tool_call' for row in resources),
                'Failure lacks its original resource anchor')
        # Request construction can fail before any external effect. Bind that
        # failure to the actual started attempt, never an invented model call.
        anchor, = [row for row in records if row.get('record_type') == 'attempt'
                   and row['event'] == 'started' and row['attempt_id'] == source['attempt_id']]
    else:
        anchor = call
    selected = {}
    for row in history:
        if row['event_index'] > anchor['artifact_event_index']:
            break
        if row['event'] == 'current_set':
            selected[row['slot']] = registrations[row['artifact_id']]
        elif row['event'] == 'current_cleared':
            selected.pop(row['slot'], None)
    for slot, artifact in scheduled['input_references']['current_artifact_ids'].items():
        selected.setdefault(slot, registrations[artifact])
    selected[source['slot']] = registration
    config = {'node': source['attempt_kind'], 'structured_output': True}
    if call is None:
        config['phase'] = 'before_resource'
    elif source['attempt_kind'] != 'code_agent':
        require(call['payload']['config_digest'] == digest(config), 'Failure configuration changed')
    policy = next((row for row in records if row.get('event') == 'policy_initialized'))

    def input_ref(kind, head, member=None, registration_head=None, path=()):
        return {'kind': kind, 'head': head, 'registration_head': registration_head, 'member': member, 'path': list(path)}

    def binding(profile, inputs, projection, value, reason=None):
        raw = canonical_bytes(projection)
        unique_inputs = {canonical_bytes(item): item for item in inputs}
        return {'profile': profile, 'inputs': [unique_inputs[key] for key in sorted(unique_inputs)], 'projection': {'schema_version': '0.1', 'profile': 'failure_projection', 'sha256': sha256(raw).hexdigest(), 'content': raw.decode()}, 'value': value, 'not_applicable_reason': reason}
    metadata = {'schema_version', 'case_id', 'run_id', 'attempt_id', 'attempt_kind', 'producer', 'status'}
    leaves, inputs, plan_binding = ([], [], None)
    for name in ('input_snapshot.json', 'root_goal.json'):
        raw = read_regular(root / name)
        value = loads(raw)
        leaves.append({'member_id': name, 'content_digest': digest(value)})
        inputs.append(input_ref('root_input', sha256(raw).hexdigest(), name))
    main_names = {'plan': 'method_plan.json', 'analysis': 'run_result.json', 'review': 'scientific_review_report.json'}
    for slot in main_names:
        if slot not in selected:
            continue
        row = selected[slot]
        pointer = row['pointer']
        member = next((m for m in pointer['members'] if m['logical_name'] == main_names[slot]))
        raw = read_regular(root / member['canonical_path'])
        require(sha256(raw).hexdigest() == member['sha256'], 'Failure domain input changed')
        value = loads(raw)
        require(value['schema_version'] == '0.1' and value['producer'] == pointer['attempt_kind'] and all((value[k] == row[k] for k in ('case_id', 'run_id'))) and all((value[k] == pointer[k] for k in ('attempt_id', 'attempt_kind'))), 'Failure domain owner changed')
        scientific = {k: v for k, v in value.items() if k not in metadata}
        ref = input_ref('member', member['sha256'], member['logical_name'], digest(row))
        leaves.append({'member_id': slot + '/' + member['logical_name'], 'content_digest': digest(scientific)})
        inputs.append(ref)
        if slot == 'plan':
            plan_binding = binding('domain_v1', [ref], scientific, digest(scientific))
    code_values, code_inputs, code_science, code_context, code_config = ({}, [], None, None, None)
    if 'code' in selected:
        from lqcd_agent.code_agent.artifacts import validate_code_result
        from lqcd_agent.code_agent.schemas import POLICIES, validate_task, validate_manifest
        from lqcd_agent.code_agent.ingress import validate_change_manifest
        from lqcd_agent.code_agent.verification import build_verification_results
        code_registration = selected['code']
        for member in code_registration['members']:
            if member['logical_name'] not in ('code_agent_task.json', 'code_agent_result.json', 'workspace_manifest.json', 'change_manifest.json', 'verification_results.json'):
                continue
            raw = read_regular(root / member['canonical_path'])
            require(sha256(raw).hexdigest() == member['sha256'], 'Code causal member changed')
            code_values[member['logical_name']] = loads(raw)
            code_inputs.append(input_ref('member', member['sha256'], member['logical_name'], digest(code_registration)))
        task = validate_task(code_values['code_agent_task.json']).value
        result = validate_code_result(code_values['code_agent_result.json'], task).value
        manifest = validate_manifest(code_values['workspace_manifest.json'], task).value
        changes = validate_change_manifest(code_values['change_manifest.json'], task, manifest).value
        verification = code_values['verification_results.json']
        require(verification == build_verification_results(task, verification['spec_results']), 'Code verification source changed')
        code_science = {'base_revision': task['base_revision'], 'base_tree_digest': task['base_tree_digest'], 'final_tree_digest': changes['final_tree_digest'], 'changes': changes['changes'], 'patch_digest': result['patch_digest']}
        change_science = {k: code_science[k] for k in ('base_tree_digest', 'final_tree_digest', 'changes')}

        def prior_code_science(prior):
            from lqcd_agent.control.operations import ExternalControl
            transition = next((r for r in records if r.get('record_type') == 'transition' and r['transition_id'] == task['transition_id']))
            parent = coordinator.snapshot(task['external_producer_contract']['parent_control_operation_id'])
            require(task['task_origin'] == 'coordinator_code_fix' and (prior['case_id'], prior['run_id']) == (task['case_id'], task['run_id']) and (prior['event_index'] <= transition['artifact_event_index']) and (parent['original_index']['current']['code'] == prior['pointer']) and (transition['source_attempt_id'] == task['source_attempt_id']) and (transition['target_attempt_id'] == task['attempt_id']), 'Historical Code evidence source changed')
            decision_source = next((r for r in registrations.values() if r['slot'] == 'decision' and r['attempt_id'] == task['source_attempt_id']))
            decision_member = next((m for m in decision_source['members'] if m['logical_name'] == 'decision_log.json'))
            decision_raw = read_regular(root / decision_member['canonical_path'])
            require(sha256(decision_raw).hexdigest() == decision_member['sha256'], 'Code remediation bytes changed')
            packet = loads(decision_raw)['remediation']
            require(packet['target_node'] == 'code_agent' and packet['parent_attempt_id'] == task['source_attempt_id'] and ({'artifact_id': evidence['artifact_id'], 'member': evidence['path'], 'sha256': evidence['sha256']} in packet['evidence']), 'Historical Code is outside its original packet')
            prior_values = {}
            for name in ('code_agent_task.json', 'code_agent_result.json', 'workspace_manifest.json', 'change_manifest.json', 'verification_results.json'):
                member = next((m for m in prior['members'] if m['logical_name'] == name))
                raw = read_regular(root / member['canonical_path'])
                require(sha256(raw).hexdigest() == member['sha256'] and len(raw) == member['size_bytes'], 'Historical Code member changed')
                prior_values[name] = loads(raw)
                code_inputs.append(input_ref('member', member['sha256'], name, digest(prior)))
            prior_task = validate_task(prior_values['code_agent_task.json']).value
            prior_result = validate_code_result(prior_values['code_agent_result.json'], prior_task).value
            prior_manifest = validate_manifest(prior_values['workspace_manifest.json'], prior_task).value
            prior_changes = validate_change_manifest(prior_values['change_manifest.json'], prior_task, prior_manifest).value
            prior_verification = prior_values['verification_results.json']
            require(prior_verification == build_verification_results(prior_task, prior_verification['spec_results']), 'Historical Code verification changed')
            external = ExternalControl(coordinator)
            producer = external.read(coordinator.connection, prior_task['producer_operation_id'])
            release = producer['consumption_release']
            require(producer['proof_kind'] == 'safe_stop' and producer['active_binding_status'] == 'released' and (release is not None) and (producer['run_locator'] == {k: task[k] for k in ('case_id', 'run_id')}) and (producer['attempt_id'] == prior['attempt_id'] == prior_task['attempt_id']) and (producer['task_digest'] == prior_task['task_digest']) and (producer['workspace_manifest_digest'] == prior_manifest['manifest_digest']), 'Historical Code producer or safe consumption changed')
            require(coordinator.get(release['consumption_operation_id'])['status'] == 'committed' and external.detached(coordinator.connection, producer), 'Historical Code consumption proof changed')
            finished = next((r for r in records if r.get('record_type') == 'attempt' and r['event'] == 'finished' and (r['attempt_id'] == prior_task['attempt_id'])))
            require(finished['output_references']['current_artifact_ids']['code'] == prior['artifact_id'] and finished['event_index'] < transition['event_index'], 'Historical Code registration is not consumed')
            final_raw = read_regular(root / producer['terminal_evidence_reference'])
            require(sha256(final_raw).hexdigest() == producer['terminal_evidence_digest'], 'Historical Code final changed')
            code_inputs.append(input_ref('typed_source', producer['terminal_evidence_digest']))
            return {'base_revision': prior_task['base_revision'], 'base_tree_digest': prior_task['base_tree_digest'], 'final_tree_digest': prior_changes['final_tree_digest'], 'changes': prior_changes['changes'], 'patch_digest': prior_result['patch_digest']}
        evidence_digests = []
        for evidence in task['evidence']:
            evidence_registration = registrations[evidence['artifact_id']]
            evidence_member = next((m for m in evidence_registration['members'] if m['canonical_path'] == evidence['path']))
            require(evidence_member['sha256'] == evidence['sha256'], 'Code evidence owner changed')
            slot = evidence_registration['slot']
            if slot == 'code':
                require(evidence_member['logical_name'] == 'code_agent_result.json', 'Code evidence is not its canonical result')
                science = prior_code_science(evidence_registration)
            else:
                require(slot in main_names and evidence_member['logical_name'] == main_names[slot], 'Code evidence lacks a scientific profile')
                raw = read_regular(root / evidence_member['canonical_path'])
                require(sha256(raw).hexdigest() == evidence_member['sha256'], 'Code evidence bytes changed')
                science = {k: v for k, v in loads(raw).items() if k not in metadata}
            evidence_digests.append(digest(science))
            code_inputs.append(input_ref('member', evidence_member['sha256'], evidence_member['logical_name'], digest(evidence_registration)))
        code_context = {'requirements': sorted(set(task['requirements'])), 'acceptance_criteria': sorted(set(task['acceptance_criteria'])), 'input_evidence_digests': sorted(set(evidence_digests)), 'base_revision': task['base_revision'], 'base_tree_digest': task['base_tree_digest'], 'backend_kind': task['coding_backend_kind'], 'runtime_digest': digest({'backend_version': task['backend_version'], 'backend_runtime_fingerprint': task['backend_runtime_fingerprint']}), 'policy_digest': task['budget_policy_digest'], 'path_policy_digest': digest({k: task[k] for k in ('read_paths', 'write_paths', 'forbidden_paths', 'filesystem_policy')}), 'tool_policy_digest': digest(task['tool_policy']), 'network_policy_digest': digest(task['network_policy'])}
        code_config = {k: task[k] for k in ('task_origin', 'task_summary', 'requirements', 'acceptance_criteria', 'base_revision', 'base_tree_digest', 'coding_backend_kind', 'backend_version', 'backend_runtime_fingerprint', 'source_runtime_fingerprint', *POLICIES, 'verification_specs', 'budget_policy_version', 'budget_profile_id', 'budget_policy_digest', 'expected_result_schema')}
        leaves.append({'member_id': 'code/code_agent_result.json', 'content_digest': digest(code_science)})
        inputs.extend(code_inputs)
    leaves.sort(key=lambda row: row['member_id'])
    scheduled_ref = input_ref('execution_record', digest(scheduled), path=('attempt_kind',))
    call_ref = (input_ref('ordinary_call', digest(call), path=('config',)) if call is not None
                else input_ref('execution_record', digest(anchor), path=('attempt_kind',)))
    tool_ids = ['domain-diagnosis'] if call is not None else []
    bindings = {'program_ids': binding('host_ids_v1', [scheduled_ref], [source['attempt_kind']], [source['attempt_kind']]), 'tool_ids': binding('host_ids_v1', [call_ref], tool_ids, tool_ids), 'verification_ids': binding('host_ids_v1', [scheduled_ref], [], []), 'input_members': binding('input_members_v1', inputs, leaves, leaves), 'plan_digest': plan_binding or binding('not_applicable_v1', [], None, None, 'no_plan'), 'code_digest': binding('not_applicable_v1', [], None, None, 'no_code'), 'base_revision': binding('not_applicable_v1', [], None, None, 'no_immutable_base'), 'base_tree_digest': binding('not_applicable_v1', [], None, None, 'no_immutable_base'), 'config_digest': binding('host_config_v1', [call_ref], config, digest(config)), 'policy_digest': binding('policy_v1', [input_ref('execution_record', digest(policy), path=('payload', 'policy'))], policy['payload']['policy'], policy['payload']['policy']['policy_digest']), 'code_task_context_digest': binding('not_applicable_v1', [], None, None, 'no_code'), 'analysis_execution_context_digest': binding('not_applicable_v1', [], None, None, 'no_fresh_analysis')}
    if code_science is not None:
        task_input = next((r for r in code_inputs if r['member'] == 'code_agent_task.json'))
        bindings['code_digest'] = binding('code_causal_v1', code_inputs, code_science, digest(code_science))
        bindings['code_task_context_digest'] = binding('code_causal_v1', code_inputs, code_context, semantic_context('code', code_context))
        bindings['base_revision'] = binding('host_ids_v1', [task_input], task['base_revision'], task['base_revision'])
        bindings['base_tree_digest'] = binding('host_ids_v1', [task_input], task['base_tree_digest'], task['base_tree_digest'])
        bindings['verification_ids'] = binding('host_ids_v1', [task_input], sorted((spec['spec_id'] for spec in task['verification_specs'])), sorted((spec['spec_id'] for spec in task['verification_specs'])))
        if source['attempt_kind'] == 'code_agent':
            bindings['tool_ids'] = binding('host_ids_v1', [task_input], sorted((spec['spec_id'] for spec in task['tool_policy'])), sorted((spec['spec_id'] for spec in task['tool_policy'])))
            bindings['config_digest'] = binding('host_config_v1', [task_input], code_config, digest(code_config))
    analysis_spec = None
    if code_science is not None and 'analysis' in selected:
        from lqcd_agent.control.operations import validate_target_preparation
        from lqcd_agent.code_agent.analysis_handoff import SPEC_FIELDS
        from lqcd_agent.control.strict_json import closed
        import sys
        analysis_registration = selected['analysis']
        analysis_owner = {**{k: analysis_registration[k] for k in ('case_id', 'run_id')}, **{k: analysis_registration['pointer'][k] for k in ('attempt_id', 'attempt_kind')}}
        analysis_scheduled = next((row for row in records if row['record_type'] == 'attempt' and row['event'] == 'scheduled' and (row['attempt_id'] == analysis_owner['attempt_id'])))
        source_capability, = [loads(row[0]) for row in coordinator.connection.execute('SELECT value FROM invocation_capabilities') if loads(row[0])['authorization']['identity'] == analysis_owner]
        preparation = source_capability['authorization']['target_preparation']
        validate_target_preparation(preparation, {k: analysis_registration[k] for k in ('case_id', 'run_id')}, 'analysis_engineer', analysis_owner['attempt_id'], analysis_scheduled['inbound_transition_id'], selected['code']['pointer'])
        require(preparation['preparation_kind'] == 'analysis_fresh', 'Code Analysis lacks its actual fresh specification')
        analysis_spec = loads(preparation['canonical_spec_bytes'])
        closed(analysis_spec, SPEC_FIELDS)
        runtime = {'python': sys.version, 'executable': sys.executable}
        require(analysis_spec['analysis_runtime_fingerprint'] == digest(runtime), 'Analysis causal runtime changed')
        analysis_config = {'runtime': runtime, 'environment': analysis_spec['environment_policy'], 'command': analysis_spec['allowed_command'], 'outputs': analysis_spec['expected_outputs']}
        require(digest(analysis_config) == preparation['runtime_policy_digest'], 'Analysis configuration source changed')
        tool_call, = [row for row in records if row.get('event') == 'resource_reserved' and row['payload']['attempt_id'] == analysis_owner['attempt_id'] and row['payload']['resource_operation_id'].endswith(':analysis-subprocess')]
        require(tool_call['payload']['input_digest'] == digest(preparation) and tool_call['payload']['config_digest'] == digest(analysis_config), 'Analysis causal call changed')
        spec_input = input_ref('typed_source', digest(analysis_spec))
        selected_leaves = []
        for slot, selected_input in analysis_spec['selected_input_artifacts'].items():
            require(slot in selected and selected_input == {'artifact_id': selected[slot]['artifact_id'], 'digest': digest(selected[slot]['pointer'])}, 'Analysis selected scientific input changed')
            selected_leaves.extend((leaf['content_digest'] for leaf in leaves if leaf['member_id'].startswith(slot + '/')))
        analysis_context = {'verified_change_digest': digest(change_science), 'effective_tree_digest': changes['final_tree_digest'], 'base_revision': task['base_revision'], 'base_tree_digest': task['base_tree_digest'], 'input_code_digest': digest(code_science), 'input_artifact_digests': sorted(set(selected_leaves)), 'runtime_digest': digest(analysis_config), 'policy_digest': policy['payload']['policy']['policy_digest']}
        bindings['analysis_execution_context_digest'] = binding('analysis_causal_v1', code_inputs + inputs + [spec_input], analysis_context, semantic_context('analysis', analysis_context))
        scientific_config = {'agent': config, 'code': code_config, 'analysis': analysis_config}
        bindings['config_digest'] = binding('host_config_v1', [call_ref, task_input, spec_input], scientific_config, digest(scientific_config))
    category = diagnostic['category']
    layer = next((name for name in ('security', 'policy', 'data', 'scientific', 'provider', 'verification', 'tool') if category == name or category.startswith((name + '.', name + '_'))), 'tool' if category == 'analysis_execution' else 'control')
    diagnostics = {'exit_code': None, 'signal': None, 'failing_test_ids': [], 'validator_errors': []}
    failure_class, code = (diagnostic['status'], category)
    if analysis_spec is not None:
        main = next((m for m in analysis_registration['members'] if m['logical_name'] == 'run_result.json'))
        actual_return = loads(read_regular(root / main['canonical_path']))['execution']
        diagnostics['exit_code'] = actual_return['returncode']
    if source['attempt_kind'] == 'code_agent':
        failure_class, code = (result['failure_class'], result['status'])
        layer = {'scope_violation': 'security', 'policy_violation': 'policy', 'verification_failed': 'verification', 'tool_error': 'tool', 'timeout': 'control', 'external_interruption': 'control'}.get(failure_class, 'code')
        diagnostics['failing_test_ids'] = sorted((r['spec_id'] for r in verification['spec_results'] if r['status'] == 'failed'))
    derivation = {'schema_version': '0.1', 'layer': layer, 'failure_class': failure_class, 'code': code, 'diagnostics': diagnostics, 'context_bindings': bindings}
    fp = fingerprint(layer=layer, failure_class=failure_class, code=code, context={k: v['value'] for k, v in bindings.items()}, diagnostics=diagnostics).value
    return (fp, derivation, registration)

def product_observe_failure(root, source, diagnostic, port, records):
    """Publish one occurrence for new Work, never for a Human continuation."""
    fp, derivation, registration = product_failure_material(root, source, diagnostic, records, port.leases.coordinator)
    occurrence = 1 + sum((row['payload']['fingerprint']['fingerprint_digest'] == fp['fingerprint_digest'] for row in records if row.get('event') == 'failure_observed'))
    failure = port.append_budget('failure_observed', {'fingerprint': fp, 'occurrence': occurrence})
    return failure

def product_issue_grant(root, identity, diagnostic, authorization, port, records, state, sequence):
    """Issue a validated budget window only in its started Coordinator."""
    from lqcd_agent.control.capabilities import invocation_prefix
    from lqcd_agent.control.strict_json import digest, loads, require
    from lqcd_agent.graph.routing import PRODUCT_FALLBACKS, is_scientific_revision, select_product_route
    from lqcd_agent.control.identity import stable_attempt_id, stable_transition_id
    if authorization is None:
        return None
    response = next((row for row in records if row.get('record_type') == 'human_response' and row['event'] == 'consumed' and (row['human_response_id'] == authorization['human_response_id'])))
    if response['decision'] != 'approve_budget_window':
        return None
    require(not is_scientific_revision(diagnostic), 'Scientific revision cannot borrow a failure grant')
    require(sequence is None, 'Terminal reserve cannot issue a budget window')
    require(response['authorized_target_attempt_id'] == identity['attempt_id'] and response['cycle_id'] == state['cycle_id'], 'Budget response does not authorize this Coordinator')
    prior = [row for row in records if row.get('event') == 'grant_issued' and row['payload']['human_response_id'] == response['human_response_id']]
    require(len(prior) <= 1, 'Budget response has duplicate grants')
    if prior:
        return prior[0]
    request = next((row for row in records if row.get('record_type') == 'human_request' and row['event'] == 'created' and (row['human_request_id'] == response['human_request_id'])))
    scope = request['authorization_scope']
    target = authorization['target_node']
    require(target in PRODUCT_FALLBACKS and scope.get('work_target') == target and ('approve_budget_window' in scope['allowed_decisions']) and (scope.get('failure_fingerprint') is not None) and (scope['failure_fingerprint'] == state['budget']['active_failure']), 'Budget window does not match the exact Work failure')
    category = diagnostic['category']
    require(not any((category == name or category.startswith((name + '.', name + '_')) for name in ('security', 'policy', 'data'))), 'Budget window cannot override a hard safety gate')
    require(not (category.startswith('scientific') and diagnostic['status'] != 'success' and (diagnostic['retryability'] != 'retryable')), 'Budget window cannot override scientific acceptance')
    require(diagnostic['confidence'] == 'unique' and diagnostic['candidates'] == [target], 'Budget target is ambiguous')
    pause = next((row for row in records if row.get('event') == 'pause_consumed' and row['input_contract'].get('human_request_id') == request['human_request_id']))
    operation = port.leases.coordinator.get(pause['operation_id'])
    resume = operation['request']
    actor = resume['actor']
    snapshot = response['payload_sha256']
    require(operation['operation_type'] == 'resume_run' and operation['status'] == 'committed' and (operation['request_digest'] == pause['proof']['request_digest']) and (resume['input_kind'] == 'human_response') and (resume['pause_id'] == pause['pause_id']) and (resume['input_digest'] == snapshot) and (digest(resume['input_snapshot']) == snapshot) and (pause['proof']['actor'] == actor) and (actor['actor_type'] == pause['authorization_scope']['actor_type']) and (set(pause['authorization_scope']['scopes']) <= set(actor['scopes'])) and (resume['input_snapshot']['decided_by'] == actor['actor_id']), 'Budget actor or protected response mismatch')
    failure = state['budget']['active_failure']
    position = state['budget']['budget_grant_index'] + 1
    grant = {'budget_grant_id': f'budget_grant_{position:06d}', 'budget_grant_index': position, 'cycle_id': response['cycle_id'], 'human_request_id': request['human_request_id'], 'human_response_id': response['human_response_id'], 'pause_id': pause['pause_id'], 'response_reference': response['payload_reference'], 'response_digest': snapshot, 'route_dimension': PRODUCT_FALLBACKS[target][1], 'fingerprint_digest': failure['fingerprint_digest'], 'occurrence': failure['occurrence'], 'target_attempt_id': stable_attempt_id(state['attempt_index'] + 1), 'target_attempt_kind': target, 'target_node': target, 'transition_id': stable_transition_id(state['transition_index'] + 1), 'additional_opportunities': 1, 'actor_scope': ['approve_budget_window']}
    view = {'source': {'node_name': 'decision_coordinator', 'attempt_id': identity['attempt_id'], 'status': 'succeeded' if diagnostic['status'] == 'success' else 'failed'}, 'state': state}
    selected = select_product_route(view, diagnostic, human_authorization=authorization, proposed_grant=grant)
    require(selected['target_node'] == target and selected['budget_decision']['decision'] == 'allow' and (selected['stop_sequence_id'] is None), 'Budget window failed its full route preflight')
    port.leases.require_effect_authority(port.capability_id, port.worker, port.epoch)
    _, capability = port.leases.get(port.capability_id)
    prefix = invocation_prefix(capability)
    index = loads(prefix['index'])
    admission = {'schema_version': '0.1', 'coordinator_attempt_id': identity['attempt_id'], 'pre_execution_head': state['execution_head'], 'pre_artifact_head': index['artifact_head'], 'pre_checkpoint_head': capability['authorization']['heads']['checkpoint_head'], 'grant_payload': grant, 'budget_decision': selected['budget_decision']}
    issued = port.append_budget('grant_issued', grant)
    return issued

class ProductResourceFailure(RuntimeError):
    """An ended ordinary call whose original reservation retained its maximum."""

def product_resource(port, **request):
    """Keep conservative product settlement separate from the resource primitive."""
    from lqcd_agent.control.budget import BudgetExhausted, settle_resource_failure
    effect = request.pop('effect')
    ended = False

    def call():
        nonlocal ended
        try:
            return effect()
        finally:
            ended = True
    try:
        return port.run_resource(**request, effect=call)
    except BudgetExhausted:
        raise
    except BaseException as error:
        if not ended:
            raise
        settle_resource_failure(port, resource_id=request['resource_id'], error=error)
        if not isinstance(error, Exception):
            raise
        raise ProductResourceFailure(str(error) or type(error).__name__) from error

def product_final_report(root, context, index, classification, response):
    """Render registered scientific conclusions without adding model judgments."""
    import json
    from hashlib import sha256
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import loads, require

    evidence = list(context['current_evidence'])
    sections = ['# LQCD research report', '## Recorded decision',
                classification['scientific_outcome'], classification['classification_reason'],
                'Decision origin: ' + classification['decision_origin'] + '.',
                '## Research question', context['root_goal'].get('goal', '')]
    documents = {}
    for slot, kind in (('plan', 'method_planner'), ('analysis', 'analysis_engineer'),
                       ('review', 'scientific_reviewer'), ('decision', 'decision_coordinator')):
        pointer = index['current'][slot]
        if pointer is None:
            continue
        member = next(item for item in pointer['members'] if item['logical_name'] == PRODUCT_FILES[kind][1])
        raw = read_regular(root / member['canonical_path'])
        require(sha256(raw).hexdigest() == member['sha256'], 'Final report source changed')
        documents[slot] = loads(raw)
        reference = {'artifact_id': pointer['artifact_id'], 'member': member['canonical_path'], 'sha256': member['sha256']}
        if reference not in evidence:
            evidence.append(reference)

    def include(title, value):
        if value:
            rendered = value if type(value) is str else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            sections.extend(['## ' + title, rendered])

    preparation = documents.get('plan', {}).get('domain_result', {}).get('preparation')
    if preparation is not None:
        include('Research preparation', preparation)

    if response is not None:
        raw = read_regular(root / response['payload_reference'])
        require(sha256(raw).hexdigest() == response['payload_sha256'], 'Final report Human response changed')
        human = loads(raw)
        include('Authorization decision and conditions', {key: human[key] for key in ('decision', 'decided_by', 'reason', 'conditions')})
        sections.append('Authorization response: `' + response['payload_reference'] + '` · SHA-256 `' + response['payload_sha256'] + '`.')
    for slot, title, field in (('plan', 'Research plan', 'method_plan'),
                               ('analysis', 'Analysis result', 'run_result'),
                               ('review', 'Scientific review with Host diagnostics', 'report')):
        envelope = documents.get(slot, {})
        domain = envelope.get('domain_result', envelope)
        value = domain.get(field, domain)
        include(title, {key: value[key] for key in ('summary', 'method_steps', 'findings', 'warnings', 'errors',
                                                   'recommended_checks', 'confidence') if value.get(key)})
    issues, challenges = {}, []
    for slot in ('plan', 'review'):
        collaboration = documents.get(slot, {}).get('collaboration', {})
        for exchange in collaboration.get('exchanges', []):
            role = exchange['role']
            discussion = exchange.get('discussion', exchange.get('brief', {}).get('discussion', {}))
            label = {'pi': 'PI', 'postdoc': 'Postdoc', 'reviewer': 'Independent Reviewer'}[role]
            if discussion.get('summary'):
                include(label + (' — planning' if slot == 'plan' else ' — review'), discussion['summary'])
            if role == 'reviewer':
                include('Independent Reviewer conclusion', exchange.get('proposal', {}).get('summary'))
        include('Collaboration recommendation — ' + slot, collaboration.get('summary'))
        for issue in collaboration.get('issues', []):
            issues[issue['id']] = issue
        if collaboration:
            challenges = collaboration.get('challenges', [])
    outstanding = [item for item in issues.values() if item['status'] != 'addressed']
    include('Open questions and limitations', outstanding or challenges)
    sections.extend(['## Traceable evidence', '\n'.join('- `' + item['member'] + '` · artifact `' +
        item['artifact_id'] + '` · SHA-256 `' + item['sha256'] + '`' for item in evidence)])
    sections.append('This report assembles recorded evidence and recommendations. It does not add an independent physics validation.')
    return '\n\n'.join(sections) + '\n', evidence

class ProductNode:
    """Host wrapper; the Agent receives only context and returns domain facts."""

    def __init__(self, root, agent_port, *, analysis_handoff=None, preparation=None):
        self.root, self.agent_port = (Path(root), agent_port)
        self.analysis_handoff, self.preparation = (analysis_handoff, preparation)

    def invoke_scoped(self, identity, port):
        from hashlib import sha256
        from lqcd_agent.agents.decision_coordinator import product_coordinator_diagnosis, validate_product_diagnostic
        from lqcd_agent.artifacts.contracts import SLOT_BY_ATTEMPT_KIND
        from lqcd_agent.control.budget import BudgetExhausted
        from lqcd_agent.control.capabilities import ArtifactOutput, HumanResponseVerdict, TargetOutcome
        from lqcd_agent.control.coordinator import read_regular
        from lqcd_agent.control.execution import parse_ledger
        from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, closed, digest, loads, require
        from lqcd_agent.graph.routing import is_scientific_revision, select_product_route
        from lqcd_agent.graph.state import product_context
        node = identity['attempt_kind']
        execution = parse_ledger(read_regular(self.root / 'execution_history.jsonl'))
        records, state = execution.values, execution.projection.value
        index = loads(read_regular(self.root / 'artifact_index.json'))
        context = product_context(self.root, identity, execution, index)
        if context['root_goal'].get('workflow') == 'intake':
            require(node in ('method_planner', 'decision_coordinator', 'memory_report', 'human_gate'),
                    'Research preparation cannot execute Code, numerical analysis or scientific review')
        refs = {slot: pointer['artifact_id'] for slot, pointer in index['current'].items() if pointer is not None}
        refs[SLOT_BY_ATTEMPT_KIND[node]] = identity['attempt_id'] + ':' + SLOT_BY_ATTEMPT_KIND[node]
        if node == 'human_gate':
            response = next((row for row in reversed(records) if row['record_type'] == 'human_response' and row['human_request_id'] == state['active_human_request_id']), None)
            if response is not None and response['status'] == 'submitted':
                payload = loads(read_regular(self.root / response['payload_reference']))
                request = next((row for row in records if row['record_type'] == 'human_request' and row['human_request_id'] == response['human_request_id'] and (row['event'] == 'created')))
                valid = payload['decision'] in request['authorization_scope']['allowed_decisions']
                from lqcd_agent.graph.routing import product_budget_decision
                inbound = next((r for r in records if r['record_type'] == 'transition' and r['target_attempt_id'] == identity['attempt_id']))
                decision = product_budget_decision(state, target='decision_coordinator', trigger='human_response', risk='low', stop_sequence_id=inbound['fields'].get('stop_sequence_id'))
                return TargetOutcome('succeeded' if valid else 'failed', {'current_artifact_ids': {slot: pointer['artifact_id'] for slot, pointer in index['current'].items() if pointer is not None and slot != 'approval'}}, human_response_verdict=HumanResponseVerdict(valid, None if valid else 'Decision is outside frozen scope'), terminal_decision=decision if valid and decision['decision'] == 'halt' else None)
            request = next((row for row in reversed(records) if row['record_type'] == 'human_request'))
            path = port.write_member('approval_packet/request.json', canonical_bytes(request))
            return TargetOutcome('pending', {'current_artifact_ids': refs}, human_request_packet=str(path), artifact=ArtifactOutput('approval', (path,), {'approval_packet_dir': str(path.parent), 'human_decision_path': None}, 'pending'))
        if node == 'memory_report':
            from lqcd_agent.memory.store import classify_memory_update
            inbound = next((r for r in records if r['record_type'] == 'transition' and r['target_attempt_id'] == identity['attempt_id']))
            decision = product_diagnostic(self.root, index['current']['decision'])
            response = next((row for row in reversed(records) if row['record_type'] == 'human_response' and row['status'] == 'consumed'), None)
            complete = all(index['current'][slot] is not None and index['current'][slot]['status'] == 'success'
                           for slot in ('plan', 'analysis', 'review'))
            review = {}
            if index['current']['review'] is not None:
                pointer = index['current']['review']
                member = next(item for item in pointer['members'] if item['logical_name'] == PRODUCT_FILES['scientific_reviewer'][1])
                raw = read_regular(self.root / member['canonical_path'])
                require(sha256(raw).hexdigest() == member['sha256'], 'Closure Review source changed')
                review = loads(raw)
            domain = review.get('domain_result', review)
            report = domain.get('report', domain)
            warnings = report.get('warnings', [])
            issues = review.get('collaboration', {}).get('issues', [])
            blocked = (decision['status'] != 'success' or
                bool(decision['candidates']) and decision['category'] != 'authorization' or
                decision['human_need'] == 'clarification' or decision['category'] == 'budget' or
                any(decision['category'] == name or decision['category'].startswith((name + '.', name + '_'))
                    for name in ('security', 'policy', 'data', 'integrity')) or
                bool(report.get('errors')) or any(item.get('status') == 'blocked' for item in issues) or
                any(type(item) is dict and (item.get('decision_coordinator_flag') is True or
                    item.get('severity') in ('severe', 'critical')) for item in warnings) or
                inbound['fields'].get('stop_sequence_id') is not None)
            classification = classify_memory_update(complete_evidence=complete, blocked=blocked,
                limitations=bool(warnings or any(item.get('status') != 'addressed' for item in issues)),
                authorization_decision=response['decision'] if response else None)
            if context['root_goal'].get('workflow') == 'intake':
                from lqcd_agent.inspection import read_preparation
                selected = read_preparation(self.root)
                classification.update(accepted_result=False, scientific_outcome='inconclusive',
                    preparation_status=selected[0]['status'] if selected else 'failed',
                    classification_reason='Research preparation only; no numerical result or physics acceptance is asserted.')
            report_text, report_evidence = product_final_report(self.root, context, index, classification, response)
            payload = {'schema_version': '0.1', **identity, 'producer': node, 'status': classification['memory_status'], **classification, 'evidence': report_evidence}
            memory = port.write_member('memory_update.json', canonical_bytes(payload))
            report = port.write_member('final_report.md', report_text.encode())
            terminal_decision = None
            if inbound['fields'].get('stop_sequence_id') is not None:
                from lqcd_agent.graph.routing import product_budget_decision
                terminal_decision = product_budget_decision(state, target=None, trigger='budget_stop', risk=decision['risk'], stop_sequence_id=inbound['fields']['stop_sequence_id'])
                terminal_decision.update(decision='halt', reason_code='terminal_budget_stop', next_control_action='close_run')
                terminal_decision['decision_digest'] = digest({k: v for k, v in terminal_decision.items() if k != 'decision_digest'})
            return TargetOutcome('succeeded', {'current_artifact_ids': refs}, artifact=ArtifactOutput('terminal', (memory, report), {'memory_update_path': str(memory), 'final_report_path': str(report)}, classification['memory_status']), terminal_decision=terminal_decision)
        require(node in PRODUCT_FILES, 'Code executes through its original external owner')
        generated_output = None
        if node == 'decision_coordinator':
            parent = context['direct_parent_attempt_id']
            registered = [loads(line)['pointer'] for line in read_regular(self.root / 'artifact_history.jsonl').splitlines() if loads(line)['event'] == 'registered']
            source = next((pointer for pointer in reversed(registered) if pointer['attempt_id'] == parent), None)
            if source is not None and source['attempt_kind'] == 'human_gate':
                request = next((row for row in reversed(records) if row['record_type'] == 'human_request'))
                source = next((pointer for pointer in reversed(registered) if pointer['attempt_id'] == request['requesting_attempt_id']))
            elif source is None:
                request = next((row for row in reversed(records) if row['record_type'] == 'human_request'))
                source = next((pointer for pointer in reversed(registered) if pointer['attempt_id'] == request['requesting_attempt_id']))
            previous = product_diagnostic(self.root, source)
            floor = 'critical' if previous['affected_layer'] == 'plan' and previous['status'] != 'success' else 'high' if previous['status'] == 'failed' or previous['candidates'] in (['analysis_engineer'], ['code_agent']) else previous['risk']
            diagnostic = product_coordinator_diagnosis([previous], local_risk_floor=floor)
            content = {'reasons': [diagnostic['category']], 'evidence': diagnostic['evidence'], 'risk_level': diagnostic['risk']}
            if is_scientific_revision(diagnostic):
                member = next(item for item in source['members'] if item['logical_name'] == PRODUCT_FILES[source['attempt_kind']][1])
                raw = read_regular(self.root / member['canonical_path'])
                require(sha256(raw).hexdigest() == member['sha256'], 'Scientific revision source changed')
                collaboration = loads(raw).get('collaboration')
                require(type(collaboration) is dict and type(collaboration.get('challenges')) is list and collaboration['challenges'] and all(type(item) is str and item.strip() for item in collaboration['challenges']), 'Scientific revision requires specific review questions')
                content['collaboration'] = collaboration
                reference = {'artifact_id': source['artifact_id'], 'member': member['canonical_path'], 'sha256': member['sha256']}
                if reference not in diagnostic['evidence']:
                    diagnostic['evidence'].append(reference)
        else:

            if node == 'analysis_engineer' and index['current']['code'] is not None:
                require(self.analysis_handoff is not None and self.preparation is not None,
                        'Verified Code requires a fresh Analysis preparation')
            timeout = getattr(self.agent_port, 'timeout_seconds', 1)
            def effect():
                return self.agent_port.run(node, context, timeout_seconds=timeout)
            try:
                if node == 'analysis_engineer' and index['current']['code'] is not None:
                    context['analysis_execution'] = product_resource(port, resource_kind='tool_call',
                        resource_id='analysis-subprocess', input_digest=digest(self.preparation),
                        config_digest=self.preparation['runtime_policy_digest'],
                        timeout_seconds=self.analysis_handoff.timeout_seconds,
                        effect=lambda: self.analysis_handoff.execute(self.preparation))
                    spec = loads(self.preparation['canonical_spec_bytes'])
                    if spec['environment_policy'].get('generated_program') is not None:
                        require(spec['expected_outputs'] == ['analysis_outputs/generated_result.json'],
                                'Generated Analysis must use its frozen numerical output path')
                        generated_output = (spec['expected_outputs'][0],
                                            canonical_bytes(context['analysis_execution']['result']))
                if hasattr(self.agent_port, 'run_scoped'):
                    outcome = self.agent_port.run_scoped(node, context, timeout_seconds=timeout, port=port)
                else:
                    outcome = product_resource(port, resource_kind='llm_call', resource_id='domain-diagnosis', input_digest=digest(context), config_digest=digest({'node': node, 'structured_output': True}), timeout_seconds=timeout, effect=effect)
                closed(outcome, ('diagnostic', 'content'))
                require(type(outcome['content']) is dict and type(outcome['diagnostic']) is dict, 'Unstructured Agent output')
                diagnostic, content = (outcome['diagnostic'], outcome['content'])
                reserved = {'schema_version', 'producer', 'status', 'case_id', 'run_id', 'cycle_id', 'attempt_id', 'attempt_kind', 'node_name', 'transition_id', 'parent_attempt_id'} | set(identity)
                require(not reserved & content.keys(), 'Agent content includes reserved Host fields')
                require(diagnostic.get('fingerprint') is None, 'Agent cannot assign a failure fingerprint')
            except ProductResourceFailure as error:
                cause = error
                while cause is not None:
                    if isinstance(cause, ControlIntegrityError):
                        raise cause
                    cause = cause.__cause__
                # Only an ended, conservatively settled effect reaches this branch.
                # Publish the actual failure so closure can report it without rerunning it.
                diagnostic = {'status': 'failed', 'category': 'execution_failure',
                    'affected_layer': {'method_planner': 'plan', 'analysis_engineer': 'analysis',
                                       'scientific_reviewer': 'review'}[node],
                    'evidence': [], 'retryability': 'not_retryable', 'candidates': [],
                    'confidence': 'unique', 'fingerprint': None, 'human_need': None, 'risk': 'high'}
                content = {'summary': 'The scoped execution failed; no successful scientific result is asserted.',
                    'errors': [{'type': 'OrdinaryResourceFailure', 'message': str(error)}]}
                if node == 'method_planner':
                    content['code_needed'] = False
            except BudgetExhausted:
                diagnostic = {'status': 'failed', 'category': 'budget', 'affected_layer': 'none', 'evidence': [], 'retryability': 'not_retryable', 'candidates': [], 'confidence': 'unique', 'fingerprint': None, 'human_need': None, 'risk': 'high'}
                content = {'resource_admission': 'denied'}
                if node == 'method_planner':
                    content['code_needed'] = False
            if 'analysis_execution' in context:
                content['execution'] = {k: v for k, v in context['analysis_execution'].items() if k != 'result'}
                if context['analysis_execution']['returncode'] != 0:
                    diagnostic.update(status='failed', category='analysis_execution', affected_layer='analysis', candidates=['analysis_engineer'], risk='high')
        state = parse_ledger(read_regular(self.root / 'execution_history.jsonl')).projection.value
        inbound = next((row for row in reversed(records) if row['record_type'] == 'transition' and row['target_attempt_id'] == identity['attempt_id']))
        sequence = inbound['fields'].get('stop_sequence_id')
        authorization = product_human_authorization(records, identity['attempt_id']) if node == 'decision_coordinator' else None
        view = {'source': {'node_name': node, 'attempt_id': identity['attempt_id'], 'status': 'succeeded' if diagnostic['status'] == 'success' else 'failed'}, 'state': state}
        selection = None
        if node == 'decision_coordinator':
            if authorization is None and sequence is None and previous['category'] != 'budget' and not is_scientific_revision(previous) and (previous['status'] != 'success' or previous['candidates']):
                product_observe_failure(self.root, source, previous, port, records)
                execution = parse_ledger(read_regular(self.root / 'execution_history.jsonl'))
                records, state = execution.values, execution.projection.value
                view['state'] = state
            issued = product_issue_grant(self.root, identity, diagnostic, authorization, port, records, state, sequence)
            if issued is not None:
                execution = parse_ledger(read_regular(self.root / 'execution_history.jsonl'))
                records, state = execution.values, execution.projection.value
                view['state'] = state
            selection = select_product_route(view, diagnostic, human_authorization=authorization, stop_sequence_id=sequence)
            target = selection['target_node']
            content['human_authorization'] = authorization
            content['remediation'] = None if target not in ('method_planner', 'code_agent', 'analysis_engineer', 'scientific_reviewer') else {'target_node': target, 'problem': diagnostic['category'], 'evidence': diagnostic['evidence'], 'constraints': ['Preserve the approved scientific method, immutable inputs and path policy.'], 'success_criteria': ['Resolve the diagnosed issue and provide attributable structured evidence.'], 'parent_attempt_id': identity['attempt_id'], 'budget_policy_digest': state['budget']['policy_digest'], 'human_authorization': authorization}
            if content['remediation'] is not None and is_scientific_revision(diagnostic):
                content['remediation'].update(problem='Resolve the scientific questions in the cited review.', constraints=['Preserve the research goal, immutable inputs and path policy.', 'Keep prior results and distinguish new evidence from revised interpretations.'], success_criteria=content['collaboration']['challenges'])
        slot, filename, field = PRODUCT_FILES[node]
        path = port.write_member(filename, canonical_bytes({'schema_version': '0.1', **identity, 'producer': node, 'status': diagnostic['status'], **content}))
        reference = {'artifact_id': refs[slot], 'member': str(path.relative_to(self.root)), 'sha256': sha256(read_regular(path)).hexdigest()}
        if not diagnostic.get('evidence'):
            diagnostic['evidence'] = [reference]
        else:
            allowed = context['current_evidence'] + [reference]
            require(all((item in allowed for item in diagnostic['evidence'])), 'Agent evidence exceeds scoped context')
        diagnostic = validate_product_diagnostic(diagnostic)
        members = [path]
        state_paths = {field: str(path)}
        if node == 'method_planner':
            require(type(content.get('code_needed')) is bool, 'Planner requires a typed code-needed result')
            state_paths['coder_task_packet_path'] = None
        if node == 'analysis_engineer':
            if generated_output is not None:
                output = port.write_member(*generated_output)
            else:
                output = port.write_member('analysis_outputs/result.json', canonical_bytes(content))
            members.append(output)
            state_paths['analysis_outputs_dir'] = str(output.parent)
        diagnostic_path = port.write_member(node + '_diagnostic.json', canonical_bytes(diagnostic))
        members.append(diagnostic_path)
        if selection is None:
            selection = select_product_route(view, diagnostic, code_needed=content.get('code_needed', False), stop_sequence_id=sequence)
        return TargetOutcome('succeeded' if diagnostic['status'] == 'success' else 'failed', {'current_artifact_ids': refs}, artifact=ArtifactOutput(slot, tuple(members), state_paths, diagnostic['status']), terminal_decision=selection['budget_decision'] if selection['budget_decision']['decision'] == 'halt' else None)
