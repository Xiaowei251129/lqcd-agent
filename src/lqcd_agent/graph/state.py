from __future__ import annotations
import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
AttemptKind = Literal['method_planner', 'code_agent', 'analysis_engineer', 'scientific_reviewer', 'decision_coordinator', 'human_gate', 'memory_report']
ATTEMPT_KIND_BY_NODE: dict[str, AttemptKind] = {'method_planner': 'method_planner', 'code_agent': 'code_agent', 'analysis_engineer': 'analysis_engineer', 'scientific_reviewer': 'scientific_reviewer', 'decision_coordinator': 'decision_coordinator', 'human_approval_gate': 'human_gate', 'human_gate': 'human_gate', 'memory_report': 'memory_report'}
PRODUCT_CONTEXT_SLOTS = {'method_planner': ('plan',), 'code_agent': ('plan', 'code'), 'analysis_engineer': ('plan', 'code', 'analysis'), 'scientific_reviewer': ('plan', 'analysis', 'review'), 'decision_coordinator': ('plan', 'code', 'analysis', 'review', 'decision', 'approval'), 'human_gate': ('decision', 'approval'), 'memory_report': ('review', 'decision', 'approval')}

def product_context(root, identity, execution, index):
    """Resolve bounded input references for one fenced canonical invocation."""
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import loads, require
    root = Path(root)
    state, records = (execution.projection.value, execution.values)
    require(state['schema_version'] == '0.4' and all((state[k] == identity[k] for k in identity)), 'Context does not belong to the current canonical Attempt')
    scheduled = next((row for row in records if row['record_type'] == 'attempt' and row['event'] == 'scheduled' and (row['attempt_id'] == identity['attempt_id'])))
    registered = {row['artifact_id']: row['pointer'] for row in (loads(line) for line in read_regular(root / 'artifact_history.jsonl').splitlines()) if row['event'] == 'registered'}
    current = index['current']
    selected = {slot: pointer for slot, pointer in current.items() if pointer is not None}
    for slot, artifact_id in scheduled['input_references']['current_artifact_ids'].items():
        require(artifact_id in registered, 'Context references an unregistered source')
        selected.setdefault(slot, registered[artifact_id])
    parent = scheduled['parent_attempt_id']
    decision = selected.get('decision')
    packet = None
    if decision is not None and decision['attempt_id'] == parent:
        path = decision['state_paths']['decision_log_path']
        value = loads(read_regular(Path(path)))
        packet = value.get('remediation')
        if packet is not None:
            validate_remediation_packet(packet, identity=identity, parent_attempt_id=parent, registered=registered, policy_digest=state['budget']['policy_digest'])
    slots = PRODUCT_CONTEXT_SLOTS[identity['attempt_kind']]
    evidence = []
    for slot in slots:
        pointer = selected.get(slot)
        if pointer is None:
            continue
        for member in pointer['members']:
            raw = read_regular(root / member['canonical_path'])
            require(hashlib.sha256(raw).hexdigest() == member['sha256'], 'Context evidence digest changed')
            evidence.append({'artifact_id': pointer['artifact_id'], 'member': member['canonical_path'], 'sha256': member['sha256']})
    if packet is not None:
        evidence.extend((reference for reference in packet['evidence'] if reference not in evidence))
    relevant = [{'artifact_id': pointer['artifact_id'], 'attempt_id': pointer['attempt_id'], 'slot': pointer['slot'], 'status': pointer['status']} for pointer in registered.values() if pointer['slot'] in slots and (pointer['attempt_id'] == parent or (packet is not None and pointer['artifact_id'] in {item['artifact_id'] for item in packet['evidence']}))][-4:]
    return {'identity': {**deepcopy(identity), 'cycle_id': state['cycle_id']}, 'direct_parent_attempt_id': parent, 'root_goal': loads(read_regular(root / 'root_goal.json')), 'current_evidence': evidence, 'remediation': deepcopy(packet), 'relevant_history': relevant, 'budget_summary': {'policy_digest': state['budget']['policy_digest'], 'dimensions': deepcopy(state['budget']['dimensions'])}}

def validate_remediation_packet(packet, *, identity, parent_attempt_id, registered, policy_digest):
    """Check the Coordinator packet against existing identity and artifact authority."""
    from lqcd_agent.control.strict_json import closed, require, text
    closed(packet, ('target_node', 'problem', 'evidence', 'constraints', 'success_criteria', 'parent_attempt_id', 'budget_policy_digest', 'human_authorization'))
    require(packet['target_node'] == identity['attempt_kind'] and packet['parent_attempt_id'] == parent_attempt_id and (packet['budget_policy_digest'] == policy_digest), 'Remediation target, parent or budget scope changed')
    text(packet['problem'])
    for key in ('constraints', 'success_criteria'):
        require(type(packet[key]) is list and packet[key] and all((type(item) is str and item for item in packet[key])), 'Missing remediation constraints or success criteria')
    require(type(packet['evidence']) is list and packet['evidence'], 'Remediation requires registered evidence')
    for reference in packet['evidence']:
        closed(reference, ('artifact_id', 'member', 'sha256'))
        pointer = registered.get(reference['artifact_id'])
        require(pointer is not None and any((member['canonical_path'] == reference['member'] and member['sha256'] == reference['sha256'] for member in pointer['members'])), 'Remediation evidence is outside registered history')
    authorization = packet['human_authorization']
    if authorization is not None:
        closed(authorization, ('human_request_id', 'human_response_id', 'response_digest', 'target_node'))
        require(authorization['target_node'] == packet['target_node'], 'Remediation authorization target changed')
    return packet

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def stable_checkpoint_thread_id(case_id: str, run_id: str) -> str:
    return f'{case_id}:{run_id}'

def stable_cycle_id(cycle_index: int) -> str:
    return f'cycle_{cycle_index:04d}'

def stable_attempt_id(attempt_index: int) -> str:
    return f'attempt_{attempt_index:06d}'

def stable_transition_id(transition_index: int) -> str:
    return f'transition_{transition_index:06d}'

def stable_human_request_id(request_index: int) -> str:
    return f'human_request_{request_index:06d}'

def stable_human_response_id(response_index: int) -> str:
    return f'human_response_{response_index:06d}'

def canonical_attempt_kind(node_name: str) -> AttemptKind:
    try:
        return ATTEMPT_KIND_BY_NODE[node_name]
    except KeyError as exc:
        raise ValueError(f'Unsupported graph node for Attempt identity: {node_name}') from exc
_CONTROL_PLANE_IDENTITY_FIELDS = ('run_id', 'case_id', 'user_goal', 'case_config_path', 'output_dir', 'checkpoint_thread_id', 'checkpoint_backend', 'checkpoint_db_path', 'parent_run_id', 'cycle_id', 'cycle_index', 'parent_cycle_id', 'attempt_id', 'attempt_index', 'parent_attempt_id', 'attempt_kind', 'attempt_node', 'attempt_trigger', 'attempt_status', 'current_node', 'inbound_transition_id', 'committed_transition_id', 'transition_index', 'committed_route', 'execution_history_path')
_HUMAN_CONTROL_FIELDS = ('human_request_index', 'human_response_index', 'active_human_request_id', 'human_requesting_attempt_id', 'human_request_kind', 'human_request_status', 'human_request_authorization_scope', 'active_human_response_id', 'human_response_status', 'human_response_decision', 'human_response_authorized_route', 'human_response_authorized_transition_route', 'human_response_authorized_transition_target', 'human_response_validator_attempt_id', 'human_response_consumer_attempt_id', 'human_response_target_attempt_id')

def validate_control_0_4_node_result(active: dict[str, Any], result: dict[str, Any]) -> None:
    """Keep the separately validated 0.4 control projection out of Agent writes.

    This pure adapter does not validate a Run root or grant execution authority.
    Domain output remains separate from the current control projection.
    """
    from lqcd_agent.control.strict_json import canonical_bytes, require
    require(active.get('schema_version') == result.get('schema_version') == '0.4', 'Unsupported control projection version')
    for field in _CONTROL_PLANE_IDENTITY_FIELDS + _HUMAN_CONTROL_FIELDS:
        require(active.get(field) == result.get(field), 'Graph node modified control-plane identity')
    require(canonical_bytes(active) == canonical_bytes(result), 'Graph node modified control-plane projection')
