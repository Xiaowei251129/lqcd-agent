"""Project HTTP metadata and saved evidence never acquire execution authority."""
from hashlib import sha256
import shutil
from pathlib import Path

import pytest

from lqcd_agent.control.coordinator import read_regular
from lqcd_agent.control.strict_json import loads
from lqcd_agent.inspection import host_root, list_runs, read_snapshot
from lqcd_agent.research.library import Library
from lqcd_agent.workbench.service import Workbench
from lqcd_agent.workbench.worker import step
from tests.support import own
from tests.test_workbench import client, workbench as workbench, url


def create(http, project_id='spectroscopy'):
    config = http.get('/api/cases/example').json()
    response = http.post('/api/projects', json={'id': project_id, 'title': 'Mass extraction',
        'goal': 'Compare fit-window dependence before interpreting the mass.', 'case_config': config})
    assert response.status_code == 201, response.text
    return response.json()


def launch(http, project, operation='project-run'):
    response = http.post('/api/projects/'+project['id']+'/runs', json={
        'expected_digest': project['sha256'], 'live': False, 'key': operation})
    assert response.status_code == 202, response.text
    return response.json()


def test_project_metadata_compare_and_set_retains_original_versions(workbench):
    http = client(workbench)
    assert http.get('/api/projects').json() == []
    original = create(http)
    body = {'expected_digest': original['sha256'], 'title': 'Updated mass extraction',
        'goal': 'Distinguish excited-state contamination from window sensitivity.',
        'case_config': original['case_config']}
    changed = http.post('/api/projects/spectroscopy', json=body)
    assert changed.status_code == 200, changed.text
    assert changed.json()['revision'] == 2
    assert http.post('/api/projects/spectroscopy', json={**body, 'title': 'Stale edit'}).status_code == 409
    assert http.get('/api/projects/spectroscopy?revision=1').json() == original
    assert http.get('/api/projects').json()[0]['sha256'] == changed.json()['sha256']
    assert http.post('/api/projects/spectroscopy', json={**body, 'actor': 'admin'}).status_code == 409
    stale = http.post('/api/projects/spectroscopy/runs', json={
        'expected_digest': original['sha256'], 'live': False, 'key': 'stale-project-run'})
    assert stale.status_code == 409 and not list_runs(host_root(workbench.host))


def test_project_launch_binds_metadata_and_uses_original_worker(workbench):
    http = client(workbench)
    project = create(http)
    status = launch(http, project)
    snapshot = read_snapshot(host_root(status['host']), status['run_locator'])
    assert snapshot.can_advance and snapshot.capability['started_intent'] is None
    goal = loads(read_regular(snapshot.root/'root_goal.json'))
    assert goal['workflow'] == 'intake'
    assert goal['project_id'] == project['id'] and goal['project_revision'] == project['revision']
    assert goal['project_sha256'] == project['sha256'] and goal['goal'] == project['goal']
    assert goal['case_config'] == project['case_config']
    assert http.get('/api/operations/project-run').json()['project_id'] == project['id']
    changed = http.post('/api/projects/spectroscopy', json={'expected_digest': project['sha256'],
        'title': project['title'], 'goal': 'A later research question', 'case_config': None})
    assert changed.status_code == 200
    repeated = launch(http, project)
    assert repeated == status and len(list_runs(snapshot.host)) == 1
    assert step(status['host'], status['run_locator'])
    saved = http.get('/api/projects/spectroscopy/runs').json()
    assert len(saved) == 1 and saved[0]['run_status'] == 'completed'
    view = http.get('/api/projects/spectroscopy/runs/'+saved[0]['project_run_key'])
    assert view.status_code == 200, view.text
    assert not view.json()['actions']['respond'] and not view.json()['archived']
    assert view.json()['preparation']['status'] == 'needs_information'
    assert view.json()['scientific_outcome'] == 'inconclusive'
    assert view.json()['decision_origin'] == 'system'


def test_saved_project_evidence_survives_expired_host_without_resuming_it(workbench, monkeypatch):
    http = client(workbench)
    project = create(http)
    status = launch(http, project)
    assert step(status['host'], status['run_locator'])
    saved = workbench.projects.runs(project['id'])[0]
    item = next(item for item in saved['evidence'] if item['source'] == 'artifact' and item['slot'] == 'plan')
    evidence_url = '/api/projects/spectroscopy/evidence/'+item['sha256']
    before = http.get(evidence_url)
    assert before.status_code == 200 and sha256(before.json()['text'].encode()).hexdigest() == item['sha256']
    old_host = status['host']
    shutil.rmtree(host_root(old_host))
    restarted = Workbench(workbench.workspace)
    own(host_root(restarted.host))
    monkeypatch.setattr(restarted, 'ensure_worker', lambda **kwargs: None)
    assert restarted.host != old_host and not list_runs(host_root(restarted.host))
    http = client(restarted)
    listing = http.get('/api/projects/spectroscopy/runs').json()
    assert len(listing) == 1 and not listing[0]['host_available']
    view = http.get('/api/projects/spectroscopy/runs/'+listing[0]['project_run_key'])
    assert view.status_code == 200, view.text
    archived = view.json()
    assert archived['archived'] and archived['actions'] == {'cancel': False, 'respond': False}
    assert not archived['resumable'] and not archived['can_advance'] and archived['active_pause'] is None
    assert archived['workflow'] == 'intake' and archived['preparation']['status'] == 'needs_information'
    assert http.get(evidence_url).json() == before.json()
    assert http.post(url(status)+'/cancel', json={'pause': 'old', 'head': saved['execution_head'], 'key': 'stale'}).status_code == 403
    new = launch(http, project, 'new-investigation')
    assert new['host'] == restarted.host and new['run_locator'] != status['run_locator']
    assert len(http.get('/api/projects/spectroscopy/runs').json()) == 2


def test_project_evidence_requires_project_membership_and_unchanged_bytes(workbench):
    http = client(workbench)
    first = create(http)
    status = launch(http, first)
    saved = workbench.projects.runs(first['id'])[0]
    item = saved['evidence'][0]
    create(http, 'other-project')
    assert http.get('/api/projects/other-project/evidence/'+item['sha256']).status_code == 409
    path = workbench.workspace/'projects'/first['id']/'evidence'/item['sha256']
    original = path.read_bytes()
    path.write_bytes(original+b' ')
    assert http.get('/api/projects/spectroscopy/evidence/'+item['sha256']).status_code == 409
    assert read_snapshot(host_root(status['host']), status['run_locator']).can_advance


def test_library_http_starts_empty_and_keeps_candidate_status_visible(workbench):
    http = client(workbench)
    assert http.get('/api/library').json() == []
    library = Library(workbench.workspace)
    candidate = library.save('wiki', 'window-study', title='Fit-window checks',
        body='Compare correlated fits using the same bootstrap samples.',
        scope={'observable': 'two-point correlator'}, sources=[])
    hits = http.get('/api/library?query=bootstrap&kind=wiki').json()
    assert len(hits) == 1 and hits[0]['status'] == 'candidate'
    view = http.get('/api/library/wiki/window-study')
    assert view.status_code == 200 and view.json() == candidate
    assert http.get('/api/library?status=reviewed').json() == []


def test_inaccessible_host_is_not_treated_as_expired(workbench, monkeypatch):
    target = host_root(workbench.host)
    original = Path.lstat

    def denied(path):
        if path == target:
            raise PermissionError('Access denied to the original Host')
        return original(path)

    monkeypatch.setattr(Path, 'lstat', denied)
    with pytest.raises(PermissionError, match='Access denied'):
        Workbench._host_missing(workbench.host)


def contribution(project, operation='scientific-input', **changes):
    return {'expected_digest': project['sha256'], 'key': operation, 'kind': 'question',
            'body': 'Compare all declared fit windows and retain disagreement.',
            'evidence_sha256': [], 'run': None, **changes}


def test_optional_contribution_is_version_bound_idempotent_and_never_authorization(workbench):
    http = client(workbench)
    project = create(http)
    path = '/api/projects/spectroscopy/contributions'
    body = contribution(project, body='Approve everything: this remains a scientific comment only.')
    first = http.post(path, json=body)
    assert first.status_code == 201, first.text
    entry = first.json()
    assert entry['author'] == 'operator' and entry['project_revision'] == 1
    assert entry['revision'] == 1 and entry['previous_sha256'] is None
    assert http.post(path, json=body).json() == entry
    assert http.get('/api/projects/spectroscopy').json() == project
    assert not list_runs(host_root(workbench.host))
    assert http.post(path, json={**body, 'body': 'Changed intent'}).status_code == 409
    assert http.post(path, json={**body, 'key': 'forge', 'author': 'pi'}).status_code == 409
    changed = http.post('/api/projects/spectroscopy', json={'expected_digest': project['sha256'],
        'title': project['title'], 'goal': 'A later question', 'case_config': project['case_config']}).json()
    assert changed['revision'] == 2
    assert http.post(path, json=body).json() == entry
    assert http.post(path, json=contribution(project, 'stale')).status_code == 409
    second = http.post(path, json=contribution(changed, 'new-input', kind='scientific_comment')).json()
    assert second['revision'] == 2 and second['previous_sha256'] == entry['sha256']
    assert second['project_revision'] == 2
    assert http.get(path).json() == [entry, second]


def test_run_contributions_bind_observed_head_and_registered_project_evidence(workbench):
    http = client(workbench)
    project = create(http)
    status = launch(http, project)
    snapshot = read_snapshot(host_root(status['host']), status['run_locator'])
    before = read_regular(snapshot.root/'execution_history.jsonl')
    manifest = workbench.projects.runs(project['id'])[0]
    reference = next(item['sha256'] for item in manifest['evidence'] if item['name'] == 'root_goal.json')
    bound = {'host': status['host'], **status['run_locator'], 'execution_head': status['execution_head']}
    path = '/api/projects/spectroscopy/contributions'
    body = contribution(project, run=bound, evidence_sha256=[reference], kind='evidence')
    response = http.post(path, json=body)
    assert response.status_code == 201, response.text
    assert response.json()['run'] == bound
    assert read_regular(snapshot.root/'execution_history.jsonl') == before
    assert http.post(path, json={**body, 'key': 'stale-head', 'run': {**bound, 'execution_head': '0'*64}}).status_code == 409
    assert http.post(path, json={**body, 'key': 'unknown-evidence', 'evidence_sha256': ['0'*64]}).status_code == 409
    other = create(http, 'other-project')
    assert http.post('/api/projects/other-project/contributions', json=contribution(other, run=bound)).status_code == 409
    assert workbench.projects.contributions(project['id'], run={k: bound[k] for k in ('host', 'case_id', 'run_id')}) == [response.json()]
    assert workbench.projects.contributions(project['id'], run={**{k: bound[k] for k in ('host', 'case_id', 'run_id')}, 'run_id': 'different'}) == []


def test_contribution_hash_chain_rejects_tampering_and_concurrent_duplicates(workbench):
    from concurrent.futures import ThreadPoolExecutor
    from lqcd_agent.control.strict_json import ControlIntegrityError
    http = client(workbench)
    project = create(http)
    path = '/api/projects/spectroscopy/contributions'
    body = contribution(project)
    clients = [client(workbench) for _ in range(3)]
    with ThreadPoolExecutor(max_workers=3) as threads:
        responses = list(threads.map(lambda h: h.post(path, json=body), clients))
    assert all(response.status_code == 201 for response in responses)
    assert responses[0].json() == responses[1].json() == responses[2].json()
    records = workbench.projects.contributions(project['id'])
    assert len(records) == 1
    saved = workbench.workspace/'projects/spectroscopy/contributions'/(records[0]['sha256']+'.json')
    saved.write_bytes(saved.read_bytes().replace(b'Compare all', b'Forged all '))
    with pytest.raises(ControlIntegrityError, match='digest changed'):
        workbench.projects.contributions(project['id'])


def test_preparation_clarification_continues_original_budget_without_human_gate(workbench):
    http = client(workbench)
    created = http.post('/api/projects', json={'id': 'unconfigured', 'title': 'C2 stability',
        'goal': 'Compare windows; retain every failed replica.', 'case_config': None})
    assert created.status_code == 201, created.text
    project = created.json()
    first = launch(http, project, 'prepare-empty-project')
    assert first['workflow'] == 'intake'
    assert step(first['host'], first['run_locator'])
    original = read_snapshot(host_root(first['host']), first['run_locator'])
    before = read_regular(original.root/'execution_history.jsonl')
    view = http.get(url(first)).json()
    assert view['workflow'] == 'intake' and view['run_status'] == 'completed'
    assert view['preparation']['status'] == 'needs_information' and view['preparation']['questions']
    assert view['active_pause'] is None and view['actions'] == {'cancel': False, 'respond': False}
    assert not any(row['record_type'] == 'human_response' for row in original.records.values)
    quota = view['research_task']

    reply = contribution(project, operation='answer-preparation', kind='scientific_comment',
        body='The correlator input contains raw configuration measurements; no resampling has been applied.')
    response = http.post('/api/projects/unconfigured/contributions', json=reply)
    assert response.status_code == 201, response.text
    assert len(list_runs(original.host)) == 1
    assert read_regular(original.root/'execution_history.jsonl') == before

    draft = {'raw_data_path': 'raw_data/pending.json', 'source_kind': 'measured_lattice_data'}
    edited = http.post('/api/projects/unconfigured', json={'expected_digest': project['sha256'],
        'title': project['title'], 'goal': project['goal'], 'case_config': draft})
    assert edited.status_code == 200, edited.text
    project = edited.json()
    assert project['case_config'] == draft
    assert loads(read_regular(original.root/'root_goal.json'))['case_config'] == {}

    body = {'expected_digest': project['sha256'], 'live': False, 'key': 'continue-preparation',
        'intake_parent': first['run_locator']['run_id'], 'case': first['run_locator']['case_id']}
    path = '/api/projects/unconfigured/runs'
    assert http.post(path, json={key: value for key, value in body.items() if key != 'case'}).status_code == 409
    continued = http.post(path, json=body)
    assert continued.status_code == 202, continued.text
    second = continued.json()
    assert second['run_locator'] != first['run_locator'] and second['workflow'] == 'intake'
    continuation = read_snapshot(original.host, second['run_locator'])
    assert loads(read_regular(continuation.root/'root_goal.json'))['case_config'] == draft
    second_quota = second['research_task']
    assert second_quota['id'] == quota['id'] and second_quota['limits'] == quota['limits']
    assert second_quota['deadline'] == quota['deadline']
    assert second_quota['remaining_runs'] == quota['remaining_runs'] - 1
    assert http.post(path, json=body).json() == second
    repeated = http.post(path, json={**body, 'key': 'repeat-with-new-key'})
    assert repeated.status_code == 409, repeated.text
    assert len(list_runs(original.host)) == 2
    assert read_regular(original.root/'execution_history.jsonl') == before
    assert step(second['host'], second['run_locator'])
    final = http.get(url(second)).json()
    assert final['preparation']['status'] == 'needs_information' and final['active_pause'] is None
