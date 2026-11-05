"""A shared research-task quota in the existing Host coordinator transaction domain.

Related Runs inherit one immutable account. Unknown requests retain their maximum
reservation; creating a new Run or reconnecting a worker cannot replenish it.
"""
from .budget import BudgetExhausted
from .coordinator import read_regular
from .strict_json import canonical_bytes, closed, digest, loads, number, require


class DuplicateExperiment(ValueError):
    """An equivalent automatic analysis is already admitted to this task."""


class ResearchBudget:
    def __init__(self, coordinator, locator):
        self.coordinator, self.locator = coordinator, dict(locator)
        self.goal = loads(read_regular(coordinator.root / locator['case_id'] / locator['run_id'] / 'root_goal.json'))
        self.binding = self.goal['research_task']
        closed(self.binding, ('id', 'limits', 'deadline', 'parent'))
        self.task_id = self.binding['id']

    @classmethod
    def for_run(cls, coordinator, locator):
        goal = loads(read_regular(coordinator.root / locator['case_id'] / locator['run_id'] / 'root_goal.json'))
        return cls(coordinator, locator) if 'research_task' in goal else None

    def _account(self, db):
        row = db.execute('SELECT value FROM research_tasks WHERE task_id=?', (self.task_id,)).fetchone()
        require(row is not None, 'Research task has no original quota')
        value = loads(row[0])
        closed(value, ('id', 'limits', 'deadline', 'runs', 'unexecuted_experiments'))
        require(value['id'] == self.task_id and value['limits'] == self.binding['limits'] and
                value['deadline'] == self.binding['deadline'], 'Research quota identity changed')
        require(any(r['locator'] == self.locator for r in value['runs']), 'Run is not admitted to this research quota')
        return value

    def decline_experiment(self, proposal_sha256, reason):
        with self.coordinator.transaction() as db:
            value = self._account(db)
            value['unexecuted_experiments'][digest(self.locator)] = {
                'parent': self.locator, 'proposal_sha256': proposal_sha256, 'reason': reason}
            db.execute('UPDATE research_tasks SET value=? WHERE task_id=?', (canonical_bytes(value), self.task_id))

    def snapshot(self):
        value = self._account(self.coordinator.connection)
        return account_snapshot(self.coordinator.connection, value)

    def reserve(self, request_id, input_tokens, output_limit, *, fence=None):
        number(input_tokens, integer=True, minimum=0)
        number(output_limit, integer=True, minimum=1)
        reserved = input_tokens + output_limit
        with self.coordinator.transaction() as db:
            if fence is not None:
                fence(db)
            value = self._account(db)
            if self.coordinator._time().monotonic_seconds >= value['deadline']:
                raise BudgetExhausted('Research task deadline exhausted')
            require(db.execute('SELECT 1 FROM research_requests WHERE request_id=?', (request_id,)).fetchone() is None,
                    'A research model request cannot be redispatched')
            used = db.execute('SELECT COUNT(*),COALESCE(SUM(COALESCE(charged_tokens,reserved_tokens)),0) '
                              'FROM research_requests WHERE task_id=?', (self.task_id,)).fetchone()
            if used[0] >= value['limits']['model_calls'] or used[1] + reserved > value['limits']['tokens']:
                raise BudgetExhausted('Research task model/token quota exhausted')
            db.execute('INSERT INTO research_requests VALUES (?,?,?,?,?,NULL)',
                       (request_id, self.task_id, canonical_bytes(self.locator), reserved,
                        digest({'input_tokens': input_tokens, 'output_limit': output_limit})))
        return request_id

    def settle(self, ticket, usage_tokens=None, *, fence=None):
        if usage_tokens is not None:
            number(usage_tokens, integer=True, minimum=0)
        with self.coordinator.transaction() as db:
            if fence is not None:
                fence(db)
            self._account(db)
            row = db.execute('SELECT task_id,run_locator,reserved_tokens,charged_tokens FROM research_requests '
                             'WHERE request_id=?', (ticket,)).fetchone()
            require(row is not None and row['task_id'] == self.task_id and
                    loads(row['run_locator']) == self.locator, 'Unknown research reservation')
            if usage_tokens is None:
                return
            require(usage_tokens <= row['reserved_tokens'], 'Provider usage exceeded its admitted token reservation')
            require(row['charged_tokens'] is None or row['charged_tokens'] == usage_tokens,
                    'Conflicting research usage settlement')
            db.execute('UPDATE research_requests SET charged_tokens=? WHERE request_id=?', (usage_tokens, ticket))


def account_snapshot(db, value):
    rows = db.execute('SELECT request_id,reserved_tokens,charged_tokens FROM research_requests WHERE task_id=?',
                      (value['id'],)).fetchall()
    charged = sum(row['charged_tokens'] if row['charged_tokens'] is not None else row['reserved_tokens'] for row in rows)
    return {'id': value['id'], 'limits': value['limits'], 'deadline': value['deadline'],
            'runs': value['runs'],
            'unexecuted_experiments': value['unexecuted_experiments'], 'model_calls': len(rows),
            'charged_tokens': charged, 'unknown_requests': sum(row['charged_tokens'] is None for row in rows),
            'remaining_runs': max(0, value['limits']['runs'] - len(value['runs'])),
            'remaining_model_calls': max(0, value['limits']['model_calls'] - len(rows)),
            'remaining_tokens': max(0, value['limits']['tokens'] - charged)}


def plan_exhausted(account, now):
    return now >= account['deadline'] or min(account[key] for key in
        ('remaining_runs', 'remaining_model_calls', 'remaining_tokens')) == 0


def inspect_budget(host, locator):
    """Read the existing task quota without constructing writers or renewing authority."""
    from contextlib import closing
    import sqlite3
    from .coordinator import validate_coordinator_schema
    goal = loads(read_regular(host / locator['case_id'] / locator['run_id'] / 'root_goal.json'))
    if 'research_task' not in goal:
        return None
    binding = goal['research_task']
    with closing(sqlite3.connect(f'file:{host}/.lqcd/control_operations.sqlite?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        validate_coordinator_schema(db, host)
        row = db.execute('SELECT value FROM research_tasks WHERE task_id=?', (binding['id'],)).fetchone()
        require(row is not None, 'Missing research quota')
        value = loads(row[0])
        require(value['limits'] == binding['limits'] and value['deadline'] == binding['deadline'] and
                any(row['locator'] == locator for row in value['runs']), 'Research quota binding changed')
        return account_snapshot(db, value)


def admit_research_run(db, goal, locator, operation_id, stamp, *, parent=None):
    """Bind quota and Run identity atomically in the original start reservation."""
    binding = goal.get('research_task')
    if binding is None:
        return
    from lqcd_agent.settings import RESEARCH_TASK_LIMITS
    from .strict_json import digest_value
    closed(binding, ('id', 'limits', 'deadline', 'parent'))
    digest_value(binding['id'])
    closed(binding['limits'], ('runs', 'model_calls', 'tokens', 'seconds'))
    for name, amount in binding['limits'].items():
        number(amount, integer=True, minimum=1)
        require(amount <= RESEARCH_TASK_LIMITS[name], 'Research quota exceeds the installed authorization scope')
    number(binding['deadline'])
    automatic_experiment = parent is None and goal.get('experiment') is not None
    parent = binding['parent'] if parent is None else parent
    row = db.execute('SELECT value FROM research_tasks WHERE task_id=?', (binding['id'],)).fetchone()
    if row is None:
        require(parent is None, 'A child cannot create a fresh research quota')
        require(binding['deadline'] <= stamp.monotonic_seconds + binding['limits']['seconds'],
                'Research task deadline exceeds its original scope')
        value = {'id': binding['id'], 'limits': binding['limits'], 'deadline': binding['deadline'],
                 'runs': [], 'unexecuted_experiments': {}}
        db.execute('INSERT INTO research_tasks VALUES (?,?)', (binding['id'], canonical_bytes(value)))
    else:
        value = loads(row[0])
        require(value['limits'] == binding['limits'] and value['deadline'] == binding['deadline'],
                'A child changed its inherited research quota')
        require(parent is not None and any(row['locator'] == parent for row in value['runs']),
                'Research parent is not admitted to this quota')
    action = goal.get('request_intent', {}).get('plan_action')
    if action is not None and binding['parent'] == parent:
        # A revised plan, accepted plan and renewed root compete for the same source.
        # Reserve the winner together with Run creation, including across task accounts.
        source_account = value
        source_parent = parent
        if action == 'renew':
            origin = goal['plan_origin']
            require(parent is None and origin['task_id'] != binding['id'], 'Renewal requires a new root account')
            source_row = db.execute('SELECT value FROM research_tasks WHERE task_id=?', (origin['task_id'],)).fetchone()
            require(source_row is not None, 'Source plan quota is unavailable')
            source_account = loads(source_row[0])
            source_parent = origin['parent']
            original = account_snapshot(db, source_account)
            require(plan_exhausted(original, stamp.monotonic_seconds), 'Original plan quota remains available')
        expected = (goal.get('previous_plan') or goal.get('preparation') or {})['parent']
        require(source_parent == expected, 'Changed source plan locator')
        source_run = next((r for r in source_account['runs'] if r['locator'] == source_parent), None)
        require(source_run is not None and 'renewed_by' not in source_run and
                not any(r['parent'] == source_parent for r in source_account['runs']),
                'This plan already has a successor; select the latest plan')
        if action == 'renew':
            source_run['renewed_by'] = {'task_id': binding['id'], 'locator': locator}
            db.execute('UPDATE research_tasks SET value=? WHERE task_id=?',
                       (canonical_bytes(source_account), source_account['id']))
        else:
            remaining = account_snapshot(db, value)
            if action == 'revise' and remaining['remaining_runs'] <= 1:
                raise BudgetExhausted('Last Run slot is reserved for execution; start a new task to revise again')
            if not remaining['remaining_model_calls'] or not remaining['remaining_tokens']:
                raise BudgetExhausted('Research task model/token quota exhausted')
    config = goal.get('case_config') or {}
    parameters_sha = digest(config.get('generated_program', {}).get('parameters', {}))
    methods_sha = digest(goal.get('method_sources', []))
    if automatic_experiment and any(
            row['parameters_sha256'] == parameters_sha and row['methods_sha256'] == methods_sha
            for row in value['runs']):
        raise DuplicateExperiment('Equivalent automatic analysis is already admitted')
    if len(value['runs']) >= value['limits']['runs'] or stamp.monotonic_seconds >= value['deadline']:
        raise BudgetExhausted('Research task Run/deadline quota exhausted')
    value['runs'].append({'locator': locator, 'parent': parent, 'operation_id': operation_id,
        'parameters_sha256': parameters_sha, 'methods_sha256': methods_sha})
    db.execute('UPDATE research_tasks SET value=? WHERE task_id=?', (canonical_bytes(value), binding['id']))
