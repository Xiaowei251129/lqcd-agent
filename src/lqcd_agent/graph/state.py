from __future__ import annotations
import hashlib
from copy import deepcopy
from pathlib import Path
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
