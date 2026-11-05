"""Research-state projection over store fixtures; project capture verifies authority separately."""
import json

from lqcd_agent.control.strict_json import canonical_bytes, digest
from lqcd_agent.research.history import project_history, project_state_view


def evidence_fixture(monkeypatch, observations, *, extra_blobs=None, contributions=()):
    rows, blobs = [], extra_blobs if extra_blobs is not None else {}
    for index, (outcome, revision, collaboration) in enumerate(observations):
        identifier = digest(collaboration)
        blobs[identifier] = canonical_bytes(collaboration)
        rows.append({'run_locator': {'case_id': 'case', 'run_id': f'run-{index}'},
                     'host': f'host-{index}', 'sha256': digest({'run': index}),
                     'project_revision': revision, 'scientific_outcome': outcome,
                     'decision_origin': 'system' if outcome is not None else None,
                     'evidence': [{'current': True, 'source': 'scientific', 'slot': 'review',
                                   'name': 'review/collaboration.json', 'sha256': identifier}]})

    class Store:
        def __init__(self, workspace):
            pass

        def contributions(self, project_id):
            return contributions

        def runs(self, project_id):
            assert project_id == 'project'
            return rows

        def evidence(self, project_id, identifier):
            assert project_id == 'project'
            return blobs[identifier]

    monkeypatch.setattr('lqcd_agent.research.history.ProjectStore', Store)
    return rows


def issue(**updates):
    return {'id': 'issue-reference', 'question': 'Does the reference preserve the paired resampling plan?',
            'response': None, 'evidence_references': [], 'status': 'open', **updates}


def test_long_project_history_becomes_state_without_dropping_unresolved_questions(monkeypatch):
    observations = [(None, 1, {'summary': 'Irrelevant old discussion. ' * 100,
                                  'issues': [issue()]}) for _ in range(300)]
    observations.append((None, 1, {'summary': 'A later answer is not automatic supersession.',
        'issues': [issue(status='addressed', response='An independent check found the plan.',
                         evidence_references=['reference-proof'])]}))
    rows = evidence_fixture(monkeypatch, observations)
    state = project_history('workspace', 'project')
    assert len(canonical_bytes(state)) > 24000
    view = project_state_view(state)
    assert len(canonical_bytes(view)) < 4000
    assert view['counts']['evidence_records'] == 301
    assert view['issues'] == [issue()]
    assert state['conflicts'][0]['variants'][0]['sources']
    assert {variant['issue']['status'] for variant in state['conflicts'][0]['variants']} == {'open', 'addressed'}
    assert 'Irrelevant old discussion' not in json.dumps(view)
    rows.reverse()
    assert project_history('workspace', 'project') == state


def test_acceptance_comes_only_from_verified_capture_and_keeps_revision_scope(monkeypatch):
    observations = [
        (None, 1, {'summary': 'The model declares acceptance.', 'decision': 'recommend_proceed',
                   'scientific_outcome': 'supported', 'decision_origin': 'human', 'issues': []}),
        ('inconclusive', 1, {'summary': 'An inconclusive interpretation.', 'issues': []}),
        ('qualified', 1, {'summary': 'The constrained result holds for these inputs.', 'issues': []}),
        ('qualified', 1, {'summary': 'The constrained result holds for these inputs.', 'issues': []}),
        ('qualified', 2, {'summary': 'The constrained result holds for these inputs.', 'issues': []}),
    ]
    rows = evidence_fixture(monkeypatch, observations)
    state = project_history('workspace', 'project')
    view = project_state_view(state)
    assert len(view['conclusions']) == 2
    assert {item['project_revision'] for item in view['conclusions']} == {1, 2}
    assert sorted(item['source_count'] for item in view['conclusions']) == [1, 2]
    assert all(item['scientific_outcome'] == 'qualified' and item['decision_origin'] == 'system'
               for item in view['conclusions'])
    assert 'model declares' not in json.dumps(view) and 'inconclusive interpretation' not in json.dumps(view)
    excluded = project_history('workspace', 'project', rows[-1]['run_locator'])
    assert excluded['counts']['accepted_claims'] == 1


def test_same_statement_preserves_outcome_and_origin_independent_of_capture_order(monkeypatch):
    summary = {'summary': 'The same recorded claim.', 'issues': []}
    rows = evidence_fixture(monkeypatch, [('supported', 1, summary), ('qualified', 1, summary),
                                         ('supported', 1, summary), ('qualified', 1, summary)])
    rows[2]['decision_origin'] = 'human'
    state = project_history('workspace', 'project')
    view = project_state_view(state)
    conclusions = {(item['scientific_outcome'], item['decision_origin']): item['source_count']
                   for item in view['conclusions']}
    assert conclusions == {('supported', 'system'): 1, ('qualified', 'system'): 2,
                           ('supported', 'human'): 1}
    rows.reverse()
    assert project_history('workspace', 'project') == state


def test_conflicting_answered_units_remain_open_with_original_responses(monkeypatch):
    first = issue(status='addressed', response='The mass is 0.1 in lattice units.', evidence_references=['lattice-proof'])
    second = issue(status='addressed', response='The mass is 0.1 GeV.', evidence_references=['physical-proof'])
    evidence_fixture(monkeypatch, [(None, 1, {'summary': 'First analysis', 'issues': [first]}),
                                  (None, 1, {'summary': 'Conflicting analysis', 'issues': [second]})])
    state = project_history('workspace', 'project')
    assert state['issues'] == [issue()]
    assert state['resolved'] == []
    variants = state['conflicts'][0]['variants']
    assert {variant['issue']['response'] for variant in variants} == {first['response'], second['response']}
    assert {tuple(variant['issue']['evidence_references']) for variant in variants} == {('lattice-proof',), ('physical-proof',)}
    assert all(variant['sources'][0]['evidence_sha256'] for variant in variants)


def test_c2_reuse_requires_sealed_conclusion_and_keeps_corrections_attributed(monkeypatch):
    summary = {'summary': 'Role claimed an incorrect uncertainty of 99.', 'issues': []}
    blobs, notes = {}, []
    [run] = evidence_fixture(monkeypatch, [('qualified', 1, summary)], extra_blobs=blobs, contributions=notes)
    def entry(name, slot, value):
        identifier = digest(value)
        blobs[identifier] = canonical_bytes(value)
        return {'slot': slot, 'source': 'input' if slot is None else 'artifact', 'current': True,
                'name': name, 'sha256': identifier}
    goal = entry('root_goal.json', None, {'case_config': {'generated_program': {'result_kind': 'c2'}}})
    result = entry('analysis/analysis_outputs/generated_result.json', 'analysis', {'fits': []})
    terminal = entry('terminal/memory_update.json', 'terminal', {})
    run['evidence'].extend([goal, result, terminal])
    legacy = project_history('workspace', 'project')
    assert not legacy['conclusions'] and legacy['c2_results'][0]['selection']['status'] == 'unassessed'
    chain = {'result_sha256': result['sha256'], 'fits': [{'pointer': '/fits/0', 'nstates': 1,
             'tmin': 4, 'tmax': 8, 'estimate': 'aE₀ = 0.2 ± 0.01'}],
             'selection': {'status': 'selected', 'fit_pointer': '/fits/0'}}
    terminal.update(entry(terminal['name'], 'terminal', {'c2_evidence': chain}))
    state = project_history('workspace', 'project')
    [claim] = state['conclusions']
    assert '0.2 ± 0.01' in claim['statement'] and claim['sources'][0]['evidence_sha256'] == terminal['sha256']
    notes.append({'kind': 'correction', 'author': 'operator', 'revision': 1, 'sha256': digest('note'),
                  'target': {'sha256': result['sha256'], 'pointer': '/fits/0/E0_error'},
                  'run': {**run['run_locator'], 'host': run['host']}, 'body': 'Check the resampling method.'})
    corrected = project_history('workspace', 'project')
    assert not corrected['conclusions']
    [item] = project_state_view(corrected)['c2_results']
    assert item['selection'] == chain['selection'] and item['corrections'] == [
        {k: notes[0][k] for k in ('sha256', 'target', 'author', 'revision')}]
    assert corrected['c2_results'][0]['corrections'][0]['body'] == notes[0]['body']
