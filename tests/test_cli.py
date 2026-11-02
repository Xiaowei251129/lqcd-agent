"""Real independent CLI processes verify durable canonical control material."""
from contextlib import closing
from copy import deepcopy
import json
import sqlite3
import pytest
from tests.support import command
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from lqcd_agent.inspection import host_root

def arguments(result):
    return ('--host', result['host'], '--case', result['run_locator']['case_id'], '--run', result['run_locator']['run_id'])

def assert_owned_journals_reject_tampering(host):
    from lqcd_agent.control.capabilities import invocation_prefix
    with closing(sqlite3.connect('file:' + str(host / '.lqcd/control_operations.sqlite') + '?mode=ro', uri=True)) as db:
        values = [loads(row[0]) for row in db.execute('SELECT value FROM invocation_capabilities')]
    for name in ('budget_intents', 'verification_intents'):
        value = next(v for v in values if len(v.get(name, [])) >= 2)
        assert invocation_prefix(value)['content'] == value[name][-1]['content']
        for field in ('previous', 'content', 'record'):
            changed = deepcopy(value)
            entry = changed[name][-1]
            if field == 'record':
                entry['record']['previous_execution_head'] = '0' * 64
                entry['content'] = entry['previous'] + canonical_bytes(entry['record']).decode() + '\n'
                entry['index'] = canonical_bytes({**loads(entry['previous_index']),
                    'execution_head': digest(entry['record'])}).decode()
            else:
                entry[field] += '\n'
            entry['intent_digest'] = digest({k: v for k, v in entry.items() if k not in ('intent_digest', 'published')})
            with pytest.raises(ControlIntegrityError):
                invocation_prefix(changed)
        assert invocation_prefix(value)['content'] == value[name][-1]['content']

def persisted(result):
    root = host_root(result['host'])
    run = root / result['run_locator']['case_id'] / result['run_locator']['run_id']
    with closing(sqlite3.connect('file:' + str(root / '.lqcd/control_operations.sqlite') + '?mode=ro', uri=True)) as db:
        row, = db.execute('SELECT value FROM run_controls WHERE run_key=?', (digest(result['run_locator']),)).fetchone()
        if result['run_status'] in ('completed', 'halted', 'failed'):
            closure, = db.execute('SELECT value FROM run_terminal_closure WHERE run_key=?', (digest(result['run_locator']),)).fetchone()
            closure = loads(closure)
            assert closure['terminal_closure'] == 'committed' and closure['run_status'] == result['run_status']
            assert closure['terminal_closure_owner_operation_id']
    control = loads(row)
    validate_run_root(run, manifest=control['manifest'], projection=control['projection'])
    execution = parse_ledger((run / 'execution_history.jsonl').read_bytes())
    state = execution.projection.value
    assert state['run_status'] == result['run_status']
    assert state['execution_head'] == result['execution_head'] == control['projection']['execution_head']
    index = loads((run / 'artifact_index.json').read_bytes())
    assert index['artifact_head'] == control['projection']['artifact_head']
    assert (run / 'budget_policy.json').is_file() and state['budget']['policy_digest']
    assert control['projection']['checkpoint_head'] == control['manifest']['checkpoint_head']
    if index['current']['terminal'] is not None and index['current']['terminal']['status'] == 'accepted':
        history = [loads(line) for line in (run / 'artifact_history.jsonl').read_bytes().splitlines()]
        assert any((row['event'] == 'protected_snapshot_registered' and row.get('protected_kind') == 'accepted_result' and (row['artifact_id'] == index['current']['terminal']['artifact_id']) for row in history))
    return (run, execution, index)

def test_multiple_runs_same_host_and_exact_repeated_start():
    first = command('start', '--key', 'first')
    assert first['run_status'] == 'completed'
    root, _, index = persisted(first)
    assert index['current']['terminal']['status'] == 'accepted'
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert command('start', '--host', first['host'], '--key', 'first') == first
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    second = command('start', '--host', first['host'], '--key', 'second')
    assert second['run_status'] == 'completed' and second['run_locator'] != first['run_locator']
    persisted(second)
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

def test_two_code_runs_have_independent_pause_verification_and_analysis():
    host = None
    roots = []
    for key in ('code-first', 'code-second'):
        extra = () if host is None else ('--host', host)
        paused = command('start', '--workflow', 'code', '--key', key, *extra)
        host = paused['host']
        assert paused['run_status'] == 'paused'
        _, execution, _ = persisted(paused)
        pause = next((row for row in reversed(execution.values) if row['record_type'] == 'pause'))
        finished = command('resume', *arguments(paused), '--pause', pause['pause_id'], '--key', key + '-consume')
        assert finished['run_status'] == 'completed'
        root, execution, index = persisted(finished)
        assert index['current']['code']['status'] == 'success'
        assert index['current']['terminal']['status'] == 'accepted'
        assert command('resume', *arguments(paused), '--pause', pause['pause_id'], '--key', key + '-consume') == finished
        roots.append(root)
    assert roots[0] != roots[1]
    persisted(finished)
    assert_owned_journals_reject_tampering(host_root(host))

def test_human_cancel_and_replay_preserve_the_source():
    paused = command('start', '--workflow', 'human', '--key', 'human')
    assert paused['run_status'] == 'paused'
    _, execution, _ = persisted(paused)
    pause = next((row for row in reversed(execution.values) if row['record_type'] == 'pause'))
    child = command('fork', *arguments(paused), '--source-digest', paused['execution_head'], '--key', 'fork')
    assert child['run_locator'] != paused['run_locator'] and child['run_status'] == 'paused'
    _, child_execution, _ = persisted(child)
    assert child_execution.values[0]['creation_reason'] == 'fork_of'
    cancelled = command('cancel', *arguments(paused), '--pause', pause['pause_id'], '--key', 'cancel')
    assert cancelled['run_status'] == 'halted'
    root, _, _ = persisted(cancelled)
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    replayed = command('replay', *arguments(cancelled), '--source-digest', cancelled['root_inputs_digest'], '--key', 'replay')
    assert replayed['run_locator'] != paused['run_locator']
    _, replay_execution, _ = persisted(replayed)
    assert replay_execution.values[0]['creation_reason'] == 'replay_of'
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

def test_human_business_response_and_authority_rejection():
    paused = command('start', '--workflow', 'human', '--key', 'human-response')
    root, execution, _ = persisted(paused)
    state = execution.projection.value
    pause = next((row for row in reversed(execution.values) if row['record_type'] == 'pause'))
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    command('resume', *arguments(paused), '--pause', pause['pause_id'], '--key', 'bad-authority', '--response', '{"allow":true}', expected_exit=1, rejection='Non-closed object')
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    response = {**paused['run_locator'], 'cycle_id': state['cycle_id'], 'human_request_id': state['active_human_request_id'], 'decision': 'approve_with_conditions', 'conditions': ['Synthetic fixture only'], 'reason': 'Approve the synthetic review', 'decided_by': 'operator'}
    finished = command('resume', *arguments(paused), '--pause', pause['pause_id'], '--key', 'human-consume', '--response', json.dumps(response))
    assert finished['run_status'] == 'completed'
    _, execution, _ = persisted(finished)
    assert [row['event'] for row in execution.values if row['record_type'] == 'human_response'] == ['submitted', 'validated', 'consumed']
    assert command('resume', *arguments(paused), '--pause', pause['pause_id'], '--key', 'human-consume', '--response', json.dumps(response)) == finished

def test_external_pause_cancel_uses_original_stop_owner_and_rejects_late_delivery():
    paused = command('start', '--workflow', 'code', '--key', 'external-cancel')
    _, execution, _ = persisted(paused)
    pause = next((row for row in reversed(execution.values) if row['record_type'] == 'pause'))
    cancelled = command('cancel', *arguments(paused), '--pause', pause['pause_id'], '--key', 'external-stop')
    assert cancelled['run_status'] == 'halted'
    root, _, _ = persisted(cancelled)
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert command('cancel', *arguments(paused), '--pause', pause['pause_id'], '--key', 'external-stop') == cancelled
    command('resume', *arguments(paused), '--pause', pause['pause_id'], '--key', 'late-delivery', expected_exit=1, rejection='A different resolution already owns')
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

@pytest.mark.parametrize('arguments,rejection,code', [(('start', '--key', 'invalid', '--host', '../../escape'), 'Invalid controlled Host identifier', 1), (('start', '--key', 'invalid', '--case', '../escape'), 'Invalid managed path component', 1), (('start', '--key', 'invalid', '--allow'), 'unrecognized arguments', 2), (('start', '--key', 'invalid', '--output-root', '/private/tmp'), 'unrecognized arguments', 2)])
def test_cli_rejects_caller_authority_and_root_escape(arguments, rejection, code):
    command(*arguments, expected_exit=code, rejection=rejection)
