"""Owned workspace navigation, verified evidence and typed business actions."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import os
import re
import fcntl
import stat
import threading
import tempfile

from lqcd_agent.configuration import read_config
from lqcd_agent.control.coordinator import Coordinator, publish_exact, read_regular, sync_directory
from lqcd_agent.control.pause import runtime_fingerprint
from lqcd_agent.control.storage import execution_scratch_root
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, closed, digest, loads, require
from lqcd_agent.inspection import host_root, list_runs, read_operation, read_snapshot
from lqcd_agent.runtime import ApplicationRequest, create_host, submit
from lqcd_agent.settings import workspace_root
from lqcd_agent.research.projects import ProjectStore
from lqcd_agent.research.library import Library
from .worker import launch_worker, worker_active


class RequestError(ValueError):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code.replace('_', ' '))


def key(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9:_-]{1,128}', value) is None:
        raise RequestError('invalid_operation_key', 400)
    return value


class Workbench:
    def __init__(self, workspace=None):
        self.workspace = workspace_root(workspace)
        directory = self.workspace/'.runtime'
        directory.mkdir(mode=0o700, exist_ok=True)
        require(directory == directory.resolve() and directory.stat().st_uid == os.getuid() and
                not directory.stat().st_mode & 0o022, 'Unsafe workbench navigation directory')
        self.host = self._navigation_host(directory)
        self.projects = ProjectStore(self.workspace)
        self.library = Library(self.workspace)
        self._process = None
        self._lock = threading.Lock()

    @classmethod
    def _navigation_host(cls, directory):
        """Serialize private navigation updates without modifying control projections."""
        descriptor = os.open(directory/'workbench-host.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid() and
                    info.st_mode & 0o077 == 0, 'Unsafe workbench navigation lock')
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            pointer = directory/'workbench-host.json'
            previous = None
            if pointer.exists():
                require(not pointer.stat().st_mode & 0o077, 'Workbench pointer must be private')
                previous = read_regular(pointer)
                identifier = closed(loads(previous), ('host',))['host']
                if not cls._host_missing(identifier):
                    host_root(identifier)
                    return identifier
            root = create_host()
            with closing(Coordinator(root)):
                pass
            identifier = root.name.removeprefix('lqcd-agent-host-')
            content = canonical_bytes({'host': identifier})
            if previous is None:
                publish_exact(pointer, content)
            else:
                require(read_regular(pointer) == previous, 'Workbench navigation changed')
                stage_fd, stage = tempfile.mkstemp(prefix='.workbench-host-', dir=directory)
                try:
                    with os.fdopen(stage_fd, 'wb') as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                    require(read_regular(pointer) == previous, 'Workbench navigation changed')
                    os.replace(stage, pointer)
                    sync_directory(directory)
                finally:
                    if os.path.exists(stage):
                        os.unlink(stage)
            return identifier
        finally:
            os.close(descriptor)

    @staticmethod
    def _host_missing(identifier):
        require(type(identifier) is str and re.fullmatch('[a-z0-9_]{8}', identifier), 'Invalid controlled Host identifier')
        path = execution_scratch_root()/('lqcd-agent-host-'+identifier)
        try:
            path.lstat()
        except FileNotFoundError:
            return True
        return False

    def create_project(self, body):
        closed(body, ('id', 'title', 'goal', 'case_config'))
        return self.projects.create(body['id'], body['title'], body['goal'], body['case_config'])

    def edit_project(self, project_id, body):
        closed(body, ('expected_digest', 'title', 'goal', 'case_config'))
        return self.projects.revise(project_id, **body)

    def contribute(self, project_id, body):
        closed(body, ('expected_digest', 'key', 'kind', 'body', 'evidence_sha256', 'run'))
        if any(row['key'] == body['key'] for row in self.projects.contributions(project_id)):
            return self.projects.contribute(project_id, **body)
        if body['run'] is not None:
            run = closed(body['run'], ('host', 'case_id', 'run_id', 'execution_head'))
            locator = {name: run[name] for name in ('case_id', 'run_id')}
            if not self._host_missing(run['host']):
                snapshot = self.snapshot(run['host'], locator)
                goal = loads(read_regular(snapshot.root/'root_goal.json'))
                require(goal.get('project_id') == project_id, 'Contribution Run belongs to another Project')
                require(snapshot.state['execution_head'] == run['execution_head'], 'Stale contribution Run view')
            else:
                saved = next((row for row in self.projects.runs(project_id) if row['host'] == run['host'] and
                              row['run_locator'] == locator), None)
                require(saved is not None and saved['execution_head'] == run['execution_head'],
                        'Unknown saved contribution Run')
        return self.projects.contribute(project_id, **body)

    def project_runs(self, project_id):
        return [{key: value for key, value in self._project_record(row).items()
                 if key not in ('state', 'evidence')} for row in self.projects.runs(project_id)]

    def _project_record(self, manifest):
        return {**manifest, 'project_run_key': digest({'host': manifest['host'], **manifest['run_locator']}),
                'host_available': not self._host_missing(manifest['host'])}

    def project_view(self, project_id, run_key):
        manifest = next((row for row in self.projects.runs(project_id)
                         if digest({'host': row['host'], **row['run_locator']}) == run_key), None)
        if manifest is None:
            raise RequestError('unknown_project_run', 404)
        if not self._host_missing(manifest['host']):
            result = self.view(manifest['host'], manifest['run_locator'])
            result.update(project_id=project_id, project_run_key=run_key, archived=False)
            return result
        # Saved evidence has no control authority even when the recorded Run was paused.
        state = manifest['state']
        entries = [{**item, 'id': item['sha256']} for item in manifest['evidence']]
        goal = next(item for item in entries if item['source'] == 'input' and item['name'] == 'root_goal.json')
        goal = loads(self.projects.evidence(project_id, goal['sha256']))
        attempts = {item['attempt_id']: {'id': item['attempt_id'], 'kind': {'plan': 'method_planner', 'analysis': 'analysis_engineer', 'review': 'scientific_reviewer', 'code': 'code_agent', 'approval': 'human_gate'}.get(item['slot'], item['slot']),
            'event': 'recorded', 'status': 'recorded'} for item in entries if item['attempt_id'] is not None}
        result = {**self._project_record(manifest), 'archived': True, 'inspection': 'verified',
            'goal': goal['goal'], 'live': goal['live'], 'compatible': False, 'managed': False,
            'can_advance': False, 'needs_recovery': False, 'active_pause': None, 'human_request': None,
            'synthetic': (goal.get('case_config') or {}).get('source_kind', 'synthetic_placeholder') == 'synthetic_placeholder',
            'coding': goal['workflow'] == 'code' or bool((goal.get('case_config') or {}).get('generated_program')),
            'actions': {'cancel': False, 'respond': False}, 'attempts': list(attempts.values()),
            'artifacts': [], 'evidence': entries, 'summaries': {}, 'collaboration': [], 'budget': state['budget']}
        for item in entries:
            name = Path(item['name']).name
            if name in ('method_plan.json', 'run_result.json', 'scientific_review_report.json', 'generated_result.json', 'memory_update.json'):
                value = loads(self.projects.evidence(project_id, item['sha256']), canonical=False)
                self._summary(result, item, name, value)
        return result

    def project_member(self, project_id, identifier):
        raw = self.projects.evidence(project_id, identifier)
        if len(raw) > 4*1024*1024:
            raise RequestError('evidence_too_large', 413)
        item = next((item for run in self.projects.runs(project_id) for item in run['evidence']
                     if item['sha256'] == identifier), None)
        return {'name': item['name'] if item else identifier, 'sha256': identifier}, raw

    def start_project(self, project_id, body):
        closed(body, ('expected_digest', 'live', 'key'))
        operation_key = key(body['key'])
        if type(body['live']) is not bool:
            raise RequestError('invalid_research_request', 400)
        admitted = submit(ApplicationRequest('run', host=self.host, project=project_id,
            project_digest=body['expected_digest'], live=body['live'], key=operation_key))
        status = admitted.status
        return {**status, 'project_id': project_id,
                'project_run_key': digest({'host': status['host'], **status['run_locator']})}

    @staticmethod
    def _summary(result, item, name, value):
        if item['current'] and item['slot'] == 'terminal' and name == 'memory_update.json':
            result.update(scientific_outcome=value['scientific_outcome'], decision_origin=value['decision_origin'])
        if item['current'] and 'domain_result' not in value:
            result['summaries'][name] = value
        if item['source'] == 'artifact' and isinstance(value.get('collaboration'), dict):
            result['collaboration'].append({**value['collaboration'], 'artifact_id': item['artifact_id'],
                'slot': item['slot'], 'current': item['current']})

    def catalog(self):
        from lqcd_agent.research_cases import CASES
        paths = sorted((self.workspace/'configs').glob('*.json'))
        paths += sorted((self.workspace/'configs').glob('*.yaml'))
        paths += [self.workspace/'raw_data/research_cases/cases'/(c['case_id']+'.json') for c in CASES]
        result = {}
        for path in paths:
            if not path.exists():
                continue
            require(path == path.resolve() and path.stat().st_uid == os.getuid() and
                    not path.stat().st_mode & 0o022, 'Unsafe case configuration')
            config = read_config(path)
            name = path.stem
            require(name not in result, 'Duplicate workbench case identifier')
            result[name] = {'id': name, 'case_id': config.get('case_id', name),
                'goal': config.get('physics_goal', ''), 'requires_live': bool(config.get('generated_program')),
                'source_kind': config.get('source_kind', 'unspecified'), 'path': path}
        return result

    def snapshot(self, host, locator):
        snapshot = read_snapshot(host_root(host), locator)
        goal = loads(read_regular(snapshot.root/'root_goal.json'))
        if goal.get('workspace') != str(self.workspace):
            raise RequestError('run_outside_workspace', 403)
        return snapshot

    def runs(self):
        result = []
        for locator in list_runs(host_root(self.host)):
            try:
                result.append(self.view(self.host, locator, details=False))
            except RequestError as error:
                if error.status != 403:
                    raise
            except ControlIntegrityError:
                result.append({'host': self.host, 'run_locator': locator, 'run_status': None,
                               'inspection': 'unavailable'})
        return result

    def evidence(self, snapshot):
        index = loads(read_regular(snapshot.root/'artifact_index.json'))
        pointers = [loads(row)['pointer'] for row in read_regular(snapshot.root/'artifact_history.jsonl').splitlines()
                    if loads(row)['event'] == 'registered']
        result = {}
        for pointer in pointers:
            current = index['current'][pointer['slot']]
            for member in pointer['members']:
                path = snapshot.root/member['canonical_path']
                self._member(path, snapshot.root, member['sha256'])
                identifier = digest([pointer['artifact_id'], member['canonical_path'], member['sha256']])
                result[identifier] = {'id': identifier, 'name': member['logical_name'], 'slot': pointer['slot'],
                    'source': 'artifact',
                    'artifact_id': pointer['artifact_id'], 'current': current is not None and current['artifact_id'] == pointer['artifact_id'],
                    'sha256': member['sha256'], 'path': path, 'scope': snapshot.root}
                if member['logical_name'] not in ('method_plan.json', 'run_result.json', 'scientific_review_report.json'):
                    continue
                value = loads(read_regular(path))
                domain = value.get('domain_result', {})
                scope = snapshot.host/'domain'/pointer['attempt_id']/snapshot.locator['case_id']/snapshot.locator['run_id']
                for relative, expected in domain.get('member_digests', {}).items():
                    target = snapshot.host/relative
                    self._member(target, scope, expected)
                    child = digest([pointer['artifact_id'], relative, expected])
                    result[child] = {'id': child, 'name': str(target.relative_to(scope)), 'slot': pointer['slot'],
                        'source': 'scientific',
                        'artifact_id': pointer['artifact_id'], 'current': result[identifier]['current'],
                        'sha256': expected, 'path': target, 'scope': scope}
        return result

    @staticmethod
    def _member(path, scope, expected):
        require(path == path.resolve() and path.is_relative_to(scope) and scope == scope.resolve(),
                'Evidence escaped its registered producer scope')
        raw = read_regular(path)
        require(sha256(raw).hexdigest() == expected, 'Registered evidence changed')
        return raw

    def member(self, host, locator, identifier):
        snapshot = self.snapshot(host, locator)
        entries = self.evidence(snapshot)
        if identifier not in entries:
            raise RequestError('unknown_evidence', 404)
        item = entries[identifier]
        raw = self._member(item['path'], item['scope'], item['sha256'])
        if len(raw) > 4*1024*1024:
            raise RequestError('evidence_too_large', 413)
        return item, raw

    def view(self, host, locator, *, details=True):
        snapshot = self.snapshot(host, locator)
        status = snapshot.status()
        goal = loads(read_regular(snapshot.root/'root_goal.json'))
        compatible = snapshot.fingerprint == runtime_fingerprint()
        pause = status['active_pause']
        request = None
        if pause and pause['reason'] == 'human_input':
            request = next(r for r in reversed(snapshot.records.values) if r['record_type'] == 'human_request' and
                           r['human_request_id'] == pause['input_contract']['human_request_id'] and r['event'] == 'created')
        result = {**status, 'inspection': 'verified', 'goal': goal['goal'], 'live': goal['live'], 'compatible': compatible,
            'managed': host == self.host, 'can_advance': snapshot.can_advance and compatible,
            'needs_recovery': host == self.host and snapshot.state['run_status'] == 'running' and not snapshot.can_advance and not worker_active(self.host),
            'synthetic': goal.get('case_config', {}).get('source_kind', 'synthetic_placeholder') == 'synthetic_placeholder',
            'coding': goal['workflow'] == 'code' or bool(goal.get('case_config', {}).get('generated_program')),
            'human_request': request, 'actions': {'cancel': host == self.host and pause is not None and pause['status'] == 'opened',
                'respond': host == self.host and compatible and request is not None and pause['status'] == 'opened'},
            'runtime_build': snapshot.fingerprint['application_build']}
        if not details:
            return result
        index = loads(read_regular(snapshot.root/'artifact_index.json'))
        result['artifacts'] = [{'slot': slot, 'status': p['status'], 'artifact_id': p['artifact_id']}
                               for slot, p in index['current'].items() if p is not None]
        failure = status.get('execution_failure', {})
        result.update(scientific_outcome=failure.get('scientific_outcome'),
                      decision_origin=failure.get('decision_origin'))
        attempts = {}
        for row in snapshot.records.values:
            if row['record_type'] == 'attempt':
                attempts[row['attempt_id']] = {'id': row['attempt_id'], 'kind': row['attempt_kind'],
                    'event': row['event'], 'status': row['status']}
        result['attempts'] = list(attempts.values())
        entries = self.evidence(snapshot)
        result['evidence'] = [{k: v for k, v in item.items() if k not in ('path', 'scope')} for item in entries.values()]
        result['summaries'], result['collaboration'] = {}, []
        for item in entries.values():
            if item['name'] in ('method_plan.json', 'run_result.json', 'scientific_review_report.json', 'analysis_outputs/generated_result.json', 'memory_update.json'):
                value = loads(self._member(item['path'], item['scope'], item['sha256']), canonical=False)
                self._summary(result, item, Path(item['name']).name, value)
        result['budget'] = snapshot.state['budget']
        return result

    def operation(self, operation_key):
        operation = read_operation(host_root(self.host), key(operation_key))
        if operation is None:
            raise RequestError('unknown_operation', 404)
        reservation = operation['reservation']
        locator = reservation.get('reserved_run_locator', operation['request'].get('run_locator'))
        if operation['operation_type'] == 'start_run':
            require(operation['request']['root_inputs']['root_goal']['workspace'] == str(self.workspace), 'Operation outside workspace')
        elif locator is not None:
            self.snapshot(self.host, locator)
        result = {'operation_id': operation['operation_id'], 'status': operation['status'],
                'operation_type': operation['operation_type'], 'host': self.host, 'run_locator': locator}
        if operation['operation_type'] == 'start_run':
            project = operation['request']['root_inputs']['root_goal'].get('project_id')
            if project is not None and locator is not None:
                result.update(project_id=project, project_run_key=digest({'host': self.host, **locator}))
        return result

    def start(self, body):
        closed(body, ('case', 'goal', 'live', 'key'))
        operation_key = key(body['key'])
        if type(body['case']) is not str or type(body['goal']) is not str or len(body['goal']) > 4000 or type(body['live']) is not bool:
            raise RequestError('invalid_research_request', 400)
        catalog = self.catalog()
        if body['case'] not in catalog:
            raise RequestError('unknown_case', 404)
        case = catalog[body['case']]
        if case['requires_live'] and not body['live']:
            raise RequestError('explicit_live_activation_required', 400)
        admitted = submit(ApplicationRequest('run', host=self.host, case_config=str(case['path']),
            goal=body['goal'] or None, live=body['live'], key=operation_key))
        return admitted.status

    def action(self, host, locator, action, body):
        if host != self.host:
            raise RequestError('imported_run_is_read_only', 403)
        fields = ('pause', 'head', 'key') if action == 'cancel' else ('pause', 'head', 'key', 'decision', 'conditions', 'reason')
        closed(body, fields)
        operation_key = key(body['key'])
        snapshot = self.snapshot(host, locator)
        previous = read_operation(snapshot.host, operation_key)
        if previous is None:
            active = snapshot.state['active_pause']
            if active is None or active['pause_id'] != body['pause'] or snapshot.state['execution_head'] != body['head']:
                raise RequestError('stale_run_action')
        opened = next((r for r in snapshot.records.values if r.get('event') == 'pause_opened' and r['pause_id'] == body['pause']), None)
        if opened is None:
            raise RequestError('unknown_pause', 404)
        response = None
        if action == 'respond':
            if opened['reason'] != 'human_input':
                raise RequestError('human_response_not_applicable')
            request = next(r for r in snapshot.records.values if r.get('record_type') == 'human_request' and
                           r['human_request_id'] == opened['input_contract']['human_request_id'] and r['event'] == 'created')
            if body['decision'] not in request['authorization_scope']['allowed_decisions']:
                raise RequestError('decision_outside_scope', 400)
            if type(body['conditions']) is not list or not all(type(c) is str for c in body['conditions']) or type(body['reason']) is not str or not body['reason'].strip():
                raise RequestError('invalid_human_response', 400)
            response = canonical_bytes({**locator, 'cycle_id': opened['cycle_id'],
                'human_request_id': request['human_request_id'], 'decision': body['decision'],
                'conditions': body['conditions'], 'reason': body['reason'], 'decided_by': 'operator'}).decode()
        elif action != 'cancel':
            raise RequestError('unknown_action', 404)
        result = submit(ApplicationRequest('cancel' if action == 'cancel' else 'resume', host=host,
            case=locator['case_id'], run=locator['run_id'], pause=body['pause'], key=operation_key, response=response))
        return result.status

    def ensure_worker(self):
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return
            self._process = launch_worker(self.host, self.workspace)
