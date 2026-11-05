"""Read-only inspection of existing authority, without constructing an executor."""
from contextlib import closing, contextmanager
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import sqlite3
import stat
from .control.coordinator import component, local_filesystem, read_regular, validate_coordinator_schema
from .control.execution import parse_ledger
from .control.integrity import validate_advanced_run_root, validate_run_root
from .control.storage import execution_scratch_root
from .control.strict_json import canonical_bytes, digest, loads, require


def host_root(identifier):
    require(type(identifier) is str and re.fullmatch('[a-z0-9_]{8}', identifier), 'Invalid controlled Host identifier')
    root = execution_scratch_root()/('lqcd-agent-host-'+identifier)
    require(root.is_dir() and root == root.resolve() and not root.is_symlink(), 'Unknown controlled Host')
    identity = root.stat()
    require(identity.st_uid == os.getuid() and identity.st_mode & 0o077 == 0, 'Host must be an owned private directory')
    return root


@dataclass(frozen=True)
class RunSnapshot:
    host: Path
    locator: dict
    root: Path
    control: dict
    closure: dict | None
    records: object
    state: dict
    fingerprint: dict | None = None
    capability: dict | None = None

    @property
    def can_advance(self):
        if self.state['run_status'] != 'running':
            return False
        life = [r for r in self.records.values if r['record_type'] == 'attempt' and
                r['attempt_id'] == self.state['attempt_id']]
        return bool(life and (life[-1]['event'] == 'finished' or self.capability is not None and
                    (self.capability['started_intent'] is None or self.capability.get('completion_intent') is not None)))

    def status(self):
        inputs = {name: loads(read_regular(self.root/(name+'.json'))) for name in ('root_goal', 'input_snapshot')}
        active = self.state.get('active_pause')
        next_action = 'archive' if self.state['run_status'] in ('completed', 'failed', 'halted') else 'inspect'
        if active:
            next_action = 'provide_human_response' if active['reason'] == 'human_input' else 'inspect_external_result' if active['reason'] == 'external_result' else 'resolve_recovery_decision'
        result = {'host': self.host.name.removeprefix('lqcd-agent-host-'), 'run_locator': self.locator,
            'run_status': self.state['run_status'], 'execution_head': self.state['execution_head'],
            'root_inputs_digest': digest(inputs), 'active_pause': active, 'next_action': next_action}
        result['workflow'] = inputs['root_goal'].get('workflow')
        if result['workflow'] == 'intake':
            selected = read_preparation(self.root)
            result['preparation'] = selected[0] if selected else None
            if selected and selected[0]['status'] == 'needs_information' and self.state['run_status'] == 'completed':
                result['next_action'] = 'clarify_project'
        if self.state['run_status'] in ('failed', 'halted') and self.closure is not None:
            result['execution_failure'] = {
                'scientific_outcome': 'inconclusive', 'decision_origin': 'system',
                'source': 'committed_control_closure', 'closure_sha256': digest(self.closure),
                'summary': 'Execution ended without establishing a scientific final conclusion.',
                'run_status': self.state['run_status']}
        if 'research_task' in inputs['root_goal']:
            from .control.research_budget import inspect_budget
            result['research_task'] = inspect_budget(self.host, self.locator)
        if inputs['root_goal']['live']:
            result['coding_backend'] = None
            if active and active['reason'] == 'external_result':
                from .code_agent.codex_backend import lookup_codex_job, JOBS_DIRECTORY
                opened = next(r for r in reversed(self.records.values) if r.get('event') == 'pause_opened' and r['pause_id'] == active['pause_id'])
                result['coding_backend'] = lookup_codex_job(self.host/JOBS_DIRECTORY, opened['input_contract']['producer_operation_id'])
        return result


def read_preparation(root):
    """Read only the current, registered preparation; no model or executor imports."""
    pointer = loads(read_regular(root/'artifact_index.json'))['current']['plan']
    if pointer is None:
        return None
    member = next(item for item in pointer['members'] if item['logical_name'] == 'method_plan.json')
    path = root/member['canonical_path']
    require(path == path.resolve() and path.is_relative_to(root), 'Preparation evidence escaped its Run')
    raw = read_regular(path)
    require(sha256(raw).hexdigest() == member['sha256'], 'Preparation evidence changed')
    value = loads(raw).get('domain_result', {}).get('preparation')
    if value is None:
        return None
    require(type(value) is dict and value.get('status') in ('ready', 'needs_information'),
            'Invalid preparation result')
    require((value['status'] == 'ready') == (type(value.get('case_config')) is dict),
            'Preparation readiness has no matching configuration')
    return value, member['sha256']


@contextmanager
def _authority(host):
    root = Path(host)
    require(host_root(root.name.removeprefix('lqcd-agent-host-')) == root, 'Invalid Host path')
    control_root = root/'.lqcd'
    require(control_root == control_root.resolve() and control_root.is_dir(), 'Invalid control root')
    local_filesystem(control_root)
    database = control_root/'control_operations.sqlite'
    identity = database.lstat()
    # The existing writer uses normal SQLite file modes inside the private Host.
    require(stat.S_ISREG(identity.st_mode) and identity.st_nlink == 1 and identity.st_uid == os.getuid(),
            'Invalid authority database')
    with closing(sqlite3.connect('file:'+str(database)+'?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        validate_coordinator_schema(db, root)
        yield db


def list_runs(host):
    with _authority(host) as db:
        return [loads(row[0])['locator'] for row in db.execute('SELECT value FROM run_controls ORDER BY rowid DESC')]


def read_operation(host, key):
    with _authority(host) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM control_operations WHERE idempotency_scope='public_control' AND idempotency_key=?", (key,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        for field in ('request', 'reservation', 'result', 'error', 'created_at', 'updated_at'):
            result[field] = loads(result[field]) if result[field] is not None else None
        return result


def _invocation_view(db, run, control, capability_id, capability, files):
    """Verify a published resource suffix for observation, never for dispatch."""
    from .control.capabilities import CONTRACT, invocation_prefix
    from .control.projections import bounded_projection
    authorization = capability['authorization']
    require(capability_id == 'capability_' + authorization['producer_operation_id'] and
            capability['authorization_digest'] == digest(authorization) and
            authorization['scope'] == 'attempt_execution' and capability['state'] == 'started' and
            capability.get('completion_intent') is None, 'Invalid observed invocation authority')
    require(authorization['manifest'] == control['manifest'] and authorization['projection'] == control['projection'] and
            all(authorization['heads'][key] == authorization['projection'][key]
                for key in ('execution_head', 'artifact_head', 'checkpoint_head')), 'Observed invocation source changed')
    query = 'SELECT * FROM control_operations WHERE operation_id=?'
    cursor = db.execute(query, (authorization['producer_operation_id'],))
    producer_row = cursor.fetchone()
    require(producer_row is not None, 'Observed invocation producer is missing')
    producer = dict(zip((column[0] for column in cursor.description), producer_row))
    producer['request'] = loads(producer['request'])
    producer['result'] = loads(producer['result']) if producer['result'] is not None else None
    require(producer['request_digest'] == digest({key: producer[key] for key in
            ('operation_type', 'operation_variant', 'request')}), 'Observed producer binding changed')
    watched = [(query, (authorization['producer_operation_id'],), producer_row)]
    allowed = {item['operation_variant'] for item in CONTRACT['prepared_then_activated']['producer_cases']}
    require(producer['operation_type'] + '/' + producer['operation_variant'] in allowed and
            authorization.get('activation_kind') is None and producer['status'] == 'committed' and
            producer['phase'] == CONTRACT['prepared_then_activated']['activation_phase'] and
            producer['phase_revision'] == authorization['activation_result_revision'] and
            producer['result']['capability_id'] == capability_id and
            all(producer['result'].get(key) == item for key, item in authorization['heads'].items()),
            'Observed invocation has no committed activation')
    started = capability['started_intent']
    require(started is not None and started['published'] is True, 'Observed Attempt has not been published')
    source = parse_ledger(started['previous'].encode())
    source_index = loads(started['previous_index'])
    source_state = bounded_projection(source, artifact_index=source_index,
        artifact_head=source_index['artifact_head'], artifact_event_index=source_index['revision']).value
    require({**source_state, 'checkpoint_head': control['manifest']['checkpoint_head']} == authorization['projection'],
            'Observed start lost its frozen source')
    execution = source
    interval = started.get('interval_record')
    if interval is not None:
        planned = authorization['active_time']
        require(interval['record_type'] == 'budget' and interval['event'] == 'active_interval_reserved' and
                interval['payload']['owner_operation_id'] == producer['operation_id'] and
                interval['payload']['producer_operation_id'] == planned['producer_operation_id'] and
                interval['payload']['interval_id'] == planned['interval_id'], 'Observed active interval changed')
        execution = execution.append(interval)
    record = started['record']
    require(record['record_type'] == 'attempt' and record['event'] == 'started' and
            all(record[key] == item for key, item in authorization['identity'].items()), 'Observed Attempt identity changed')
    execution = execution.append(record)
    require(execution.canonical.decode() == started['content'] and
            canonical_bytes({**source_index, 'execution_head': digest(record)}).decode() == started['index'],
            'Observed start differs from its frozen publication')
    prefix = invocation_prefix(capability)
    require(files['execution_history.jsonl'] == prefix['content'].encode() and
            files['artifact_index.json'] == prefix['index'].encode() and
            sha256(files['artifact_history.jsonl']).hexdigest() == authorization['artifact_history_digest'],
            'Observed resource suffix differs from its owner')
    for key in ('root_goal_reference', 'input_snapshot_reference'):
        reference = source.values[0][key]
        require(reference['reference'] in files and sha256(files[reference['reference']]).hexdigest() == reference['sha256'],
                'Observed root input changed')
    execution = parse_ledger(prefix['content'].encode())
    reservations = {row['payload']['resource_operation_id']: row['payload'] for row in execution.values
                    if row['record_type'] == 'budget' and row['event'] == 'resource_reserved' and
                    row['payload']['attempt_id'] == authorization['identity']['attempt_id']}
    settlements = {row['payload']['resource_operation_id']: row['payload'] for row in execution.values
                   if row['record_type'] == 'budget' and row['event'] == 'resource_settled' and
                   row['payload']['resource_operation_id'] in reservations}
    active = reservations.keys() - settlements.keys()
    require(len(active) == 1 and reservations[next(iter(active))]['resource_kind'] in ('llm_call', 'tool_call') and
            all(item['actual'] is not None for item in settlements.values()),
            'Observed invocation has no single active ordinary resource or has an unknown settlement')
    index = loads(prefix['index'])
    projection = bounded_projection(execution, artifact_index=index,
        artifact_head=index['artifact_head'], artifact_event_index=index['revision']).value
    validate_advanced_run_root(run, manifest=control['manifest'],
        projection={**projection, 'checkpoint_head': control['manifest']['checkpoint_head']})
    return watched


def read_snapshot(host, locator):
    root = Path(host)
    for name in ('case_id', 'run_id'):
        component(locator[name])
    with _authority(root) as db:
        db.execute('BEGIN')
        row = db.execute('SELECT value FROM run_controls WHERE run_key=?', (digest(locator),)).fetchone()
        require(row is not None, 'Unknown Run')
        control = loads(row[0])
        require(control['locator'] == locator, 'Run control locator mismatch')
        closure_row = db.execute('SELECT value FROM run_terminal_closure WHERE run_key=?', (digest(locator),)).fetchone()
        closure = loads(closure_row[0]) if closure_row else None
        run = root/locator['case_id']/locator['run_id']
        require(run == run.resolve(), 'Run path was redirected')
        files = {name: read_regular(run/name) for name in ('execution_history.jsonl', 'artifact_history.jsonl',
                 'artifact_index.json', 'budget_policy.json', 'root_goal.json', 'input_snapshot.json')}
        records = parse_ledger(files['execution_history.jsonl'])
        state = records.projection.value
        candidates = []
        if state['run_status'] == 'running':
            for cap_row in db.execute('SELECT capability_id,revision,value FROM invocation_capabilities'):
                capability = loads(cap_row[2])
                identity = capability['authorization']['identity']
                if all(identity[key] == locator[key] for key in locator) and identity['attempt_id'] == state['attempt_id']:
                    candidates.append((cap_row, capability))
        executable = [candidate for candidate in candidates if candidate[1]['authorization']['scope'] == 'attempt_execution']
        candidates = executable or candidates
        require(len(candidates) <= 1, 'Conflicting current invocation capabilities')
        capability = candidates[0][1] if candidates else None
        watched = []
        if (capability is not None and capability['state'] == 'started' and
                capability.get('completion_intent') is None and capability.get('budget_intents') and
                capability['authorization'].get('activation_kind') is None):
            require(closure is None, 'Terminal ownership blocks the observed invocation')
            watched = _invocation_view(db, run, control, candidates[0][0][0], capability, files)
        else:
            validate_run_root(run, manifest=control['manifest'], projection=control['projection'])
            require(state['execution_head'] == control['projection']['execution_head'], 'Run changed during inspection')
        creation = next(r for r in records.values if r['record_type'] == 'run_lifecycle' and r['from_status'] == 'initializing')
        original = db.execute('SELECT value,value_digest FROM control_snapshots WHERE operation_id=?', (creation['operation_id'],)).fetchone()
        require(original is not None, 'Missing original Run snapshot')
        bootstrap = loads(original[0])
        require(digest(bootstrap) == original[1] and bootstrap['records'][0] == records.values[0], 'Original Run snapshot changed')
        if state['run_status'] in ('completed', 'failed', 'halted'):
            require(closure is not None and closure['terminal_closure'] == 'committed' and
                    closure['run_status'] == state['run_status'], 'Run terminal closure is not committed')
        db.execute('COMMIT')
        require(db.execute('SELECT value FROM run_controls WHERE run_key=?', (digest(locator),)).fetchone() == row,
                'Run changed during inspection; query again')
        for cap_row, _ in candidates:
            require(db.execute('SELECT capability_id,revision,value FROM invocation_capabilities WHERE capability_id=?',
                    (cap_row[0],)).fetchone() == cap_row, 'Invocation changed during inspection; query again')
        for query, params, expected in watched:
            require(db.execute(query, params).fetchone() == expected, 'Activation changed during inspection; query again')
        require(all(read_regular(run/name) == raw for name, raw in files.items()), 'Run files changed during inspection; query again')
    return RunSnapshot(root, dict(locator), run, control, closure, records, state,
                       bootstrap['runtime_fingerprint'], capability)
