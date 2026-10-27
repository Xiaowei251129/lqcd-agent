"""Read-only inspection of existing authority, without constructing an executor."""
from contextlib import closing
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sqlite3
import stat
from .control.coordinator import component, local_filesystem, read_regular, validate_coordinator_schema
from .control.execution import parse_ledger
from .control.integrity import validate_run_root
from .control.storage import execution_scratch_root
from .control.strict_json import digest, loads, require


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

    def status(self):
        inputs = {name: loads(read_regular(self.root/(name+'.json'))) for name in ('root_goal', 'input_snapshot')}
        active = self.state.get('active_pause')
        next_action = 'archive' if self.state['run_status'] in ('completed', 'failed', 'halted') else 'inspect'
        if active:
            next_action = 'provide_human_response' if active['reason'] == 'human_input' else 'inspect_external_result' if active['reason'] == 'external_result' else 'resolve_recovery_decision'
        result = {'host': self.host.name.removeprefix('lqcd-agent-host-'), 'run_locator': self.locator,
            'run_status': self.state['run_status'], 'execution_head': self.state['execution_head'],
            'root_inputs_digest': digest(inputs), 'active_pause': active, 'next_action': next_action}
        if inputs['root_goal']['live']:
            result['coding_backend'] = None
            if active and active['reason'] == 'external_result':
                from .code_agent.codex_backend import lookup_codex_job, JOBS_DIRECTORY
                opened = next(r for r in reversed(self.records.values) if r.get('event') == 'pause_opened' and r['pause_id'] == active['pause_id'])
                result['coding_backend'] = lookup_codex_job(self.host/JOBS_DIRECTORY, opened['input_contract']['producer_operation_id'])
        return result


def read_snapshot(host, locator):
    root = Path(host)
    require(host_root(root.name.removeprefix('lqcd-agent-host-')) == root, 'Invalid Host path')
    for name in ('case_id', 'run_id'):
        component(locator[name])
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
        db.execute('BEGIN')
        validate_coordinator_schema(db, root)
        row = db.execute('SELECT value FROM run_controls WHERE run_key=?', (digest(locator),)).fetchone()
        require(row is not None, 'Unknown Run')
        control = loads(row[0])
        require(control['locator'] == locator, 'Run control locator mismatch')
        closure_row = db.execute('SELECT value FROM run_terminal_closure WHERE run_key=?', (digest(locator),)).fetchone()
        closure = loads(closure_row[0]) if closure_row else None
        run = root/locator['case_id']/locator['run_id']
        require(run == run.resolve(), 'Run path was redirected')
        validate_run_root(run, manifest=control['manifest'], projection=control['projection'])
        records = parse_ledger(read_regular(run/'execution_history.jsonl'))
        state = records.projection.value
        require(state['execution_head'] == control['projection']['execution_head'], 'Run changed during inspection')
        if state['run_status'] in ('completed', 'failed', 'halted'):
            require(closure is not None and closure['terminal_closure'] == 'committed' and
                    closure['run_status'] == state['run_status'], 'Run terminal closure is not committed')
        db.execute('COMMIT')
        require(db.execute('SELECT value FROM run_controls WHERE run_key=?', (digest(locator),)).fetchone() == row,
                'Run changed during inspection; query again')
    return RunSnapshot(root, dict(locator), run, control, closure, records, state)
