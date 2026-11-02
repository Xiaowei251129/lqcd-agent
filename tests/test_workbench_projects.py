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
    assert len(saved) == 1 and saved[0]['run_status'] == 'paused'
    view = http.get('/api/projects/spectroscopy/runs/'+saved[0]['project_run_key'])
    assert view.status_code == 200, view.text
    assert view.json()['actions']['respond'] and not view.json()['archived']


def test_saved_project_evidence_survives_expired_host_without_resuming_it(workbench, monkeypatch):
    http = client(workbench)
    project = create(http)
    status = launch(http, project)
    assert step(status['host'], status['run_locator'])
    saved = workbench.projects.runs(project['id'])[0]
    item = next(item for item in saved['evidence'] if item['source'] == 'artifact' and item['slot'] == 'review')
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
