"""B02 child bootstrap: immutable source proofs, one coordinator, fresh authority."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import uuid
from .budget import policy
from .checkpoints import persist_checkpoint, verify_checkpoint, verify_source_checkpoint
from .coordinator import boundary, component, exclusive_directory, read_regular
from .integrity import validate_run_root
from .pause import runtime_fingerprint, validate_fingerprint
from .protocol import PROTOCOL, operation_variant
from .strict_json import ControlIntegrityError, canonical_bytes, closed, digest, digest_value, loads, number, require, text
SOURCE_CONTRACT = next((row for row in PROTOCOL['evidence_unions'] if row['union_id'] == 'SourceSnapshotProof'))

def validate_source_proof(proof, creation_reason):
    require(type(proof) is dict, 'Missing SourceSnapshotProof')
    tag = 'replay_root' if creation_reason == 'replay_of' else 'fork_head'
    variant = next((row for row in SOURCE_CONTRACT['variants'] if row['tag'] == tag))
    closed(proof, (SOURCE_CONTRACT['tag_field'], *variant['required_fields']))
    combination = {key: proof[key] for key in ('source_snapshot_kind', 'source_schema', 'source_control_revision_proof')}
    require(any((combination == dict(row) for row in SOURCE_CONTRACT['valid_schema_revision_combinations'])), 'Unsupported source schema/revision proof')
    require(proof['source_snapshot_kind'] == tag, 'Wrong source proof variant')
    closed(proof['source_run_identity'], ('case_id', 'run_id'))
    for value in proof['source_run_identity'].values():
        component(value)
    if tag == 'replay_root':
        closed(proof['immutable_root_input'], ('root_goal', 'input_snapshot'))
        require(digest(proof['immutable_root_input']) == proof['root_input_digest'], 'Source root digest mismatch')
        validate_fingerprint(proof['runtime_fingerprint'])
    else:
        require(proof['source_run_status'] in SOURCE_CONTRACT['fork_head_run_status_contract']['allowed_values'], 'Ineligible fork status')
        number(proof['source_control_revision'], integer=True, minimum=1)
        closed(proof['source_latest_heads'], ('execution_head', 'artifact_head', 'checkpoint_head'))
        for key, value in proof['source_latest_heads'].items():
            digest_value(value, nullable=key == 'artifact_head')
        require(proof['source_revision_cas'] == digest({'source_run_identity': proof['source_run_identity'], 'revision': proof['source_control_revision'], 'heads': proof['source_latest_heads']}), 'Fork revision binding mismatch')
        require(type(proof['eligible_artifact_snapshot']) is list, 'Invalid fork evidence snapshot')
    return proof

@dataclass(frozen=True)
class ReplayRunRequest:
    source_run_locator: dict
    idempotency_key: str
    source_root_input_digest: str

@dataclass(frozen=True)
class ForkRunRequest:
    source_run_locator: dict
    idempotency_key: str
    source_head_digest: str
    artifact_ids: tuple[str, ...] = ()
    profile_id: str = 'balanced_v1'

class ChildOperations:

    def __init__(self, coordinator, worker, lease_seconds):
        self.coordinator, self.worker, self.lease_seconds = (coordinator, worker, lease_seconds)

    def create(self, request, actor):
        require(type(request) in (ReplayRunRequest, ForkRunRequest), 'Expected typed child request')
        fork = type(request) is ForkRunRequest
        operation_type = 'fork_run' if fork else 'replay_run'
        identity = actor.authorize('fork' if fork else 'replay')
        if fork:
            actor.authorize('policy.select')
            digest_value(request.source_head_digest)
            require(type(request.artifact_ids) is tuple and request.artifact_ids == tuple(sorted(set(request.artifact_ids))), 'Non-canonical fork evidence selection')
        else:
            digest_value(request.source_root_input_digest)
        text(request.idempotency_key)
        closed(request.source_run_locator, ('case_id', 'run_id'))
        for item in request.source_run_locator.values():
            component(item)
        canonical = {**asdict(request), 'actor': identity}
        canonical.pop('idempotency_key')
        if fork:
            canonical['artifact_ids'] = list(request.artifact_ids)
        coordinator = self.coordinator
        with coordinator.transaction() as db:
            old = coordinator.lookup_key('public_control', request.idempotency_key, db=db)
            if old is not None:
                require(old['request_digest'] == digest({'operation_type': operation_type, 'operation_variant': 'not_applicable', 'request': canonical}), 'Same-key request conflict')
                operation = old
            else:
                try:
                    proof, source_inputs, fingerprint, source_policy, classification = self._source(db, request)
                except (OSError, UnicodeError, KeyError, TypeError) as error:
                    raise ControlIntegrityError('Source input evidence is unavailable') from error
                selected = policy(request.profile_id).value if fork else source_policy
                child = {'creation_reason': 'fork_of' if fork else 'replay_of', 'source_run_identity': request.source_run_locator, 'root_inputs': source_inputs, 'source_runtime_fingerprint': fingerprint, 'target_runtime_fingerprint': runtime_fingerprint()}

                def reserve(operation_id, stamp):
                    value = {'reserved_child_run_locator': {'case_id': request.source_run_locator['case_id'], 'run_id': 'run_' + uuid.uuid4().hex}, 'source_snapshot_proof': proof, 'canonical_child_policy_bytes': canonical_bytes(selected).decode(), 'child_policy_digest': selected['policy_digest'], 'child_policy_profile': selected['profile_id'], 'child_policy_version': selected['schema_version'], 'child_policy_selection_authority': 'authenticated_host_profile_selection' if fork else 'validated_source_policy', 'initial_invocation_capability_inputs': {'attempt_id': 'attempt_000001', 'target_kind': 'method_planner'}}
                    from .research_budget import admit_research_run
                    admit_research_run(db, source_inputs['root_goal'], value['reserved_child_run_locator'],
                                       operation_id, stamp, parent=request.source_run_locator)
                    if not fork:
                        value['source_policy_classification_proof'] = classification
                    return value

                def snapshot(operation):
                    from .interfaces import _bootstrap_snapshot
                    return {**_bootstrap_snapshot(coordinator.root, operation, child=child), 'child': child}
                operation = coordinator.reserve_in_transaction(db, operation_type, 'not_applicable', 'public_control', request.idempotency_key, canonical, self.worker, reserve, lease_seconds=self.lease_seconds, build_snapshot=snapshot)
                if fork:
                    boundary(coordinator.observer, 'child.source_revision_cas', 'before', operation)
                    row = db.execute('SELECT revision,value FROM run_controls WHERE run_key=?', (digest(request.source_run_locator),)).fetchone()
                    require(row is not None and row['revision'] == proof['source_control_revision'] and ({key: loads(row['value'])['projection'][key] for key in proof['source_latest_heads']} == proof['source_latest_heads']), 'Fork source revision CAS lost')
                    boundary(coordinator.observer, 'child.source_revision_cas', 'after', operation)
        from .operations import TerminalOperations
        terminal = TerminalOperations(coordinator, self.worker, self.lease_seconds)
        if operation['status'] != 'in_progress' and operation['error'] is not None and ('close_operation_id' in operation['error']):
            terminal.continue_close(operation['error']['close_operation_id'])
        try:
            return self._materialize(operation)
        except (ControlIntegrityError, OSError) as error:
            terminal.fail_bootstrap(operation, error)
            return coordinator.get(operation['operation_id'])

    def _source(self, db, request):
        """Read replay roots without consuming current heads; fork consumes a stable head."""
        from .records import validate_record
        locator = request.source_run_locator
        root = self.coordinator.root / locator['case_id'] / locator['run_id']
        require(root == root.resolve() and root.is_dir(), 'Missing or escaped source root')
        raw = read_regular(root / 'execution_history.jsonl')
        require(b'\n' in raw, 'Source has no complete Run record')
        boundary(self.coordinator.observer, 'ingress.source_record', 'before')
        try:
            created = loads(raw.split(b'\n', 1)[0])
            validate_record(created)
        finally:
            boundary(self.coordinator.observer, 'ingress.source_record', 'after')
        require(created['record_type'] == 'run' and created['event_index'] == 1 and (created['previous_execution_head'] is None) and (created['canonical_output_root'] == str(root)) and ({k: created[k] for k in locator} == locator), 'Source identity mismatch')
        inputs = {}
        for name in ('root_goal', 'input_snapshot'):
            reference = created[name + '_reference']
            path = root / reference['reference']
            require(path == path.resolve() and path.is_relative_to(root), 'Source reference escaped Run')
            data = read_regular(path)
            require(sha256(data).hexdigest() == reference['sha256'], 'Source input bytes changed')
            inputs[name] = loads(data)
        sources = []
        for row in db.execute("SELECT operation_id FROM control_operations WHERE operation_type IN ('start_run','replay_run','fork_run')"):
            operation = self.coordinator.get(row[0], db=db)
            target = operation['reservation'].get('reserved_run_locator', operation['reservation'].get('reserved_child_run_locator'))
            if target == locator:
                sources.append(self.coordinator.snapshot(operation['operation_id'], db=db))
        require(len(sources) == 1 and sources[0]['records'][0] == created, 'Source creation proof is unavailable')
        fingerprint = sources[0]['runtime_fingerprint']
        validate_fingerprint(fingerprint)
        saved = loads(read_regular(root / 'budget_policy.json'))
        selected = policy(saved['profile_id']).value
        require(saved == selected and created['policy_digest'] == selected['policy_digest'], 'Unsupported source policy')
        if type(request) is ReplayRunRequest:
            require(digest(inputs) == request.source_root_input_digest, 'Replay source root input digest changed')
            proof = {'source_snapshot_kind': 'replay_root', 'source_run_identity': locator, 'immutable_root_input': inputs, 'root_input_digest': digest(inputs), 'source_schema': '0.4', 'runtime_fingerprint': fingerprint, 'source_control_revision_proof': 'versioned_control_revision_not_consumed_for_root_replay'}
        else:
            row = db.execute('SELECT revision,value FROM run_controls WHERE run_key=?', (digest(locator),)).fetchone()
            require(row is not None, 'Unknown source control revision')
            control = loads(row['value'])
            require(control['projection'] is not None, 'Source checkpoint unavailable')
            verify_source_checkpoint(self.coordinator, db, root, control['manifest'])
            state = validate_run_root(root, manifest=control['manifest'], projection=control['projection']).value
            require(state['execution_head'] == request.source_head_digest, 'Fork source head changed')
            from .operations import TerminalOperations
            closure = TerminalOperations(self.coordinator, self.worker, self.lease_seconds).closure(locator, db=db)
            if state['run_status'] == 'paused':
                pause = state.get('active_pause')
                require(pause is not None and pause['status'] == 'opened' and (closure is None), 'Source Pause is not stable')
                owner = db.execute('SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?', (digest(locator), pause['pause_id'])).fetchone()
                require(owner is not None and loads(owner[0])['owner'] is None and (loads(owner[0])['status'] == 'opened'), 'Source Pause was claimed')
            else:
                require(state['run_status'] in ('completed', 'failed', 'halted') and closure is not None and (closure['terminal_closure'] == 'committed') and (closure['run_status'] == state['run_status']), 'Source is not a committed terminal head')
            index = loads(read_regular(root / 'artifact_index.json'))
            pointers = {pointer['artifact_id']: pointer for pointer in index['current'].values() if pointer is not None}
            require(set(request.artifact_ids) <= set(pointers), 'Selected fork evidence is not current validated evidence')
            evidence = [{'source_run_identity': locator, 'pointer': pointers[item]} for item in request.artifact_ids]
            heads = {key: state[key] for key in ('execution_head', 'artifact_head', 'checkpoint_head')}
            proof = {'source_snapshot_kind': 'fork_head', 'source_run_identity': locator, 'source_schema': '0.4', 'source_run_status': state['run_status'], 'source_latest_heads': heads, 'source_control_revision': row['revision'], 'source_control_revision_proof': 'exact_source_control_revision', 'source_revision_cas': digest({'source_run_identity': locator, 'revision': row['revision'], 'heads': heads}), 'eligible_artifact_snapshot': evidence}
            inputs = {'root_goal': inputs['root_goal'], 'input_snapshot': {'source_provenance': locator, 'immutable_evidence': evidence}}
        validate_source_proof(proof, 'fork_of' if type(request) is ForkRunRequest else 'replay_of')
        classification = {'classification': 'supported', 'source_run_identity': locator, 'source_schema': '0.4', 'canonical_policy_bytes': canonical_bytes(selected).decode(), 'policy_digest': selected['policy_digest'], 'profile_id': selected['profile_id'], 'policy_version': selected['schema_version'], 'supported_set_digest': digest([policy(name).value for name in ('balanced_v1', 'phase_b_test')])}
        return (proof, inputs, fingerprint, selected, classification)

    def _materialize(self, operation):
        from .capabilities import prepare_capability
        from .interfaces import ControlPlane
        coordinator = self.coordinator
        if operation['status'] != 'in_progress':
            return operation
        if coordinator._time().monotonic_seconds >= operation['lease_expires']:
            operation = coordinator.acquire(operation['operation_id'], self.worker, lease_seconds=self.lease_seconds)
        elif operation['worker_owner_id'] != self.worker:
            return operation
        with coordinator.failure_context(operation):
            snapshot = coordinator.snapshot(operation['operation_id'])
        reserved = operation['reservation']
        locator = reserved['reserved_child_run_locator']
        root = coordinator.root / locator['case_id'] / locator['run_id']
        records, manifest = (snapshot['records'], snapshot['manifest'])
        ledger = lambda count: b''.join((canonical_bytes(row) + b'\n' for row in records[:count]))
        plans = {'child_run_root_created': [(name + '.json', canonical_bytes(value), None) for name, value in snapshot['child']['root_inputs'].items()], 'child_policy_published': [('budget_policy.json', reserved['canonical_child_policy_bytes'].encode(), None)], 'child_run_ledger_started': [('execution_history.jsonl', ledger(1), b'')], 'child_lineage_recorded': [('execution_history.jsonl', ledger(2), ledger(1))], 'child_bootstrap_records_complete': [('execution_history.jsonl', ledger(7), ledger(2)), ('artifact_history.jsonl', b'', None)], 'child_running_lifecycle_recorded': [('execution_history.jsonl', ledger(8), ledger(7))], 'child_checkpoint_committed': [('artifact_index.json', canonical_bytes(snapshot['artifact_index']), None), ('checkpoints/' + manifest['checkpoint_id'] + '.json', canonical_bytes(manifest), None)]}
        declaration = operation_variant(operation['operation_type'], 'not_applicable')
        while operation['status'] == 'in_progress':
            with coordinator.failure_context(operation):
                phase = next((target for source, target in declaration['success_edges'] if source == operation['phase']))
                for path, content, previous in plans.get(phase, []):
                    coordinator.freeze_publication(operation['operation_id'], self.worker, operation['lease_epoch'], operation['phase_revision'], phase, root / path, content, previous=previous)

                def publish(db, current):
                    from .operations import BootstrapIntegrityError
                    try:
                        ControlPlane._verify_start_prefix(root, plans, declaration, current, phase)
                        if declaration['phases'].index(current['phase']) >= declaration['phases'].index('child_checkpoint_committed'):
                            verify_checkpoint(root, manifest)
                            validate_run_root(root, manifest=manifest, projection=snapshot['projection'])
                    except (ControlIntegrityError, OSError) as error:
                        raise BootstrapIntegrityError(str(error)) from error
                    if phase == 'source_snapshot_committed':
                        validate_source_proof(reserved['source_snapshot_proof'], snapshot['child']['creation_reason'])
                        return {'source_snapshot_proof': reserved['source_snapshot_proof'], 'lineage_snapshot_digest': digest(reserved['source_snapshot_proof']), 'source_policy_classification_or_not_applicable': reserved.get('source_policy_classification_proof', {'tag': 'not_applicable'})}
                    if phase == 'child_run_root_created':
                        exclusive_directory(root.parent)
                        exclusive_directory(root, observer=coordinator.observer, name='child')
                    if phase == 'child_checkpoint_committed':
                        persist_checkpoint(coordinator, db, current, root, snapshot['checkpoint'], {'source': 'input', 'step': 0, 'parents': {}, 'operation_id': current['operation_id']})
                    for path, _, _ in plans.get(phase, []):
                        coordinator.materialize_publication(db, current, phase, root / path, name='child.' + path)
                    evidence = {'child_run_root_created': {'reserved_child_locator': locator, 'lineage_snapshot_digest': digest(reserved['source_snapshot_proof'])}, 'child_policy_published': {'canonical_child_policy': reserved['canonical_child_policy_bytes'], 'child_policy_digest': reserved['child_policy_digest'], 'child_policy_selection_proof': reserved['child_policy_selection_authority']}, 'child_run_ledger_started': {'child_run_created_initializing': snapshot['run_creation_binding']}, 'child_lineage_recorded': {'root_or_replay_or_fork_lineage': records[1]}, 'child_bootstrap_records_complete': {'child_bootstrap_closure': records[2:7]}, 'child_running_lifecycle_recorded': {'child_initializing_to_running': records[7]}}
                    if phase in evidence:
                        return evidence[phase]
                    verify_checkpoint(root, manifest)
                    state = validate_run_root(root, manifest=manifest, projection=snapshot['projection']).value
                    if phase == 'child_checkpoint_committed':
                        db.execute('INSERT INTO run_controls VALUES (?,?,?)', (digest(locator), 1, canonical_bytes({'locator': locator, 'projection': state, 'manifest': manifest})))
                        return {'child_running_resulting_head': manifest['execution_head']}
                    if phase == 'invocation_capability_prepared':
                        return prepare_capability(coordinator, db, current, root, manifest, state)
                    require(phase == 'result_committed', 'Unknown child phase')
                    result = {'run_locator': locator, 'run_status': 'running', 'terminal_closure': 'not_applicable', 'domain_status': None, **{key: manifest[key] for key in ('execution_head', 'artifact_head', 'checkpoint_head')}, 'pause_id': None, 'capability_id': 'capability_' + current['operation_id'], 'request_digest': current['request_digest']}
                    return {'exact_public_or_internal_result': result, 'final_phase_revision': current['phase_revision'] + 1}
                operation = coordinator.step(operation['operation_id'], self.worker, operation['lease_epoch'], operation['phase_revision'], phase, publish)
        return operation
