"""Deterministic research state from verified project evidence, never authority."""
from copy import deepcopy

from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, require
from .c2_evidence import selection_text
from .projects import ProjectStore


def project_history(workspace, project_id, exclude_locator=None):
    projects = ProjectStore(workspace)
    evidence, observations, conclusions, c2_results = [], {}, {}, []
    corrections = {}
    for note in projects.contributions(project_id):
        if note['kind'] == 'correction':
            scope = note['run']
            corrections.setdefault((scope['host'], scope['case_id'], scope['run_id']), []).append(
                {field: note[field] for field in ('sha256', 'target', 'body', 'author', 'revision')})
    for run in projects.runs(project_id):
        if exclude_locator is not None and run['run_locator'] == exclude_locator:
            continue
        identity = {'run_locator': run['run_locator'], 'host': run['host'],
                    'manifest_sha256': run['sha256'], 'scientific_outcome': run.get('scientific_outcome'),
                    'decision_origin': run.get('decision_origin'), 'project_revision': run['project_revision']}
        numerical = next((entry for entry in run['evidence'] if entry['current'] and entry['slot'] == 'analysis'
                          and entry['source'] == 'artifact' and entry['name'].endswith('/analysis_outputs/generated_result.json')), None)
        terminal = next((entry for entry in run['evidence'] if entry['current'] and entry['slot'] == 'terminal'
                         and entry['source'] == 'artifact' and entry['name'].endswith('/memory_update.json')), None)
        chain = None
        notes = corrections.get((run['host'], run['run_locator']['case_id'], run['run_locator']['run_id']), [])
        if terminal and numerical:
            memory = loads(projects.evidence(project_id, terminal['sha256']))
            chain = memory.get('c2_evidence')
            if chain:
                require(chain['result_sha256'] == numerical['sha256'], 'Captured C2 conclusion cites a different result')
        is_c2 = bool(chain or notes)
        if numerical and terminal and not is_c2:
            goal = next(item for item in run['evidence'] if item['source'] == 'input' and item['name'] == 'root_goal.json')
            config = loads(projects.evidence(project_id, goal['sha256'])).get('case_config', {})
            is_c2 = (config.get('generated_program') or {}).get('result_kind') == 'c2'
        if numerical and is_c2:
            require(all(note['target']['sha256'] == numerical['sha256'] for note in notes),
                    'C2 correction cites a different captured result')
            c2_results.append({**identity, 'result_sha256': numerical['sha256'],
                               'terminal_sha256': terminal['sha256'] if terminal else None,
                               'selection': chain['selection'] if chain else {'status': 'unassessed', 'fit_pointer': None},
                               'corrections': notes})
        entries = [entry for entry in run['evidence'] if entry['current'] and
                   entry['source'] == 'scientific' and entry['name'].endswith('/collaboration.json')]
        # Only a review supersedes a plan inside the same Run. Different Runs
        # have no implicit supersession relation, even when one is newer.
        reviews = [entry for entry in entries if entry['slot'] == 'review']
        role_statements = []
        for entry in reviews or [entry for entry in entries if entry['slot'] == 'plan']:
            source = {**identity, 'evidence_sha256': entry['sha256']}
            evidence.append(source)
            collaboration = loads(projects.evidence(project_id, entry['sha256']), canonical=False)
            if collaboration.get('summary'):
                role_statements.append((collaboration['summary'], source))
            for issue in collaboration.get('issues', []):
                require(type(issue) is dict and type(issue.get('id')) is str and issue['id'],
                        'Stored issues must have Host identifiers')
                require(issue.get('status') in ('open', 'blocked', 'addressed'), 'Unknown stored issue status')
                bucket = observations.setdefault(issue['id'], [])
                require(not bucket or bucket[0]['issue']['question'] == issue['question'],
                        'Stored issue identity changed')
                bucket.append({'issue': issue, 'source': source})
        # For C2 the terminal interpretation is authoritative. Keep original role
        # statements reachable through evidence rather than reusing their reported numbers.
        if run.get('scientific_outcome') in ('supported', 'qualified'):
            statements = role_statements
            if is_c2:
                # A field correction can change a comparison involving several
                # rows. Keep the original conclusion for inspection until a new
                # analysis assesses that correction.
                statements = []
                if chain and not notes and chain['selection']['status'] != 'unassessed':
                    statements = [(selection_text(chain), {**identity, 'evidence_sha256': terminal['sha256']})]
            for statement, source in statements:
                key = digest({'statement': statement, 'project_revision': run['project_revision'],
                              'scientific_outcome': run['scientific_outcome'], 'decision_origin': run['decision_origin']})
                value = conclusions.setdefault(key, {'statement': statement,
                    'scientific_outcome': run['scientific_outcome'], 'decision_origin': run['decision_origin'],
                    'project_revision': run['project_revision'], 'sources': []})
                value['sources'].append(source)

    issues, resolved, conflicts = [], [], []
    for identifier, rows in sorted(observations.items()):
        variants = {}
        for row in rows:
            key = digest(row['issue'])
            variant = variants.setdefault(key, {'issue': row['issue'], 'sources': []})
            variant['sources'].append(row['source'])
        variants = [variants[key] for key in sorted(variants)]
        for variant in variants:
            variant['sources'].sort(key=canonical_bytes)
        statuses = {variant['issue']['status'] for variant in variants}
        answers = {variant['issue'].get('response') for variant in variants}
        conflict = len(statuses) > 1 or len(answers) > 1
        if conflict:
            conflicts.append({'id': identifier, 'question': rows[0]['issue']['question'], 'variants': variants})
        status = 'blocked' if 'blocked' in statuses else 'open' if 'open' in statuses or conflict else 'addressed'
        if status == 'addressed':
            resolved.append({'id': identifier, 'question': rows[0]['issue']['question'], 'variants': variants})
        else:
            eligible = [v['issue'] for v in variants if v['issue']['status'] == status]
            value = deepcopy(eligible[0] if eligible else variants[0]['issue'])
            value['status'] = status
            if conflict:
                value.update(response=None, evidence_references=[])
            issues.append(value)

    evidence.sort(key=canonical_bytes)
    accepted = [conclusions[key] for key in sorted(conclusions)]
    for conclusion in accepted:
        conclusion['sources'].sort(key=canonical_bytes)
    return {'issues': issues, 'conclusions': accepted, 'resolved': resolved, 'conflicts': conflicts,
            'evidence': evidence, 'c2_results': sorted(c2_results, key=canonical_bytes),
            'counts': {'evidence_records': len(evidence), 'unresolved_issues': len(issues),
                       'resolved_questions': len(resolved), 'conflicting_questions': len(conflicts),
                       'accepted_claims': len(accepted)}}


def project_state_view(state):
    """Keep current questions and conditional accepted claims, not every exchange."""
    return {'issues': state['issues'], 'counts': state['counts'],
            'conclusions': [{'statement': value['statement'],
                'scientific_outcome': value['scientific_outcome'], 'decision_origin': value['decision_origin'],
                'project_revision': value['project_revision'],
                'representative_evidence': min(source['evidence_sha256'] for source in value['sources']),
                'source_count': len(value['sources'])}
                for value in state['conclusions']],
            'conflicts': [{'id': value['id'], 'question': value['question'],
                           'variant_count': len(value['variants'])} for value in state['conflicts']],
            'c2_results': [{'host': item['host'], 'run_locator': item['run_locator'],
                            'terminal_sha256': item['terminal_sha256'], 'result_sha256': item['result_sha256'],
                            'selection': item['selection'], 'scientific_outcome': item['scientific_outcome'],
                            'corrections': [{k: note[k] for k in ('sha256', 'target', 'author', 'revision')}
                                            for note in item['corrections']]}
                           for item in state.get('c2_results', [])],
            'history_source': "Read field-targeted operator corrections, full resolutions, conflicting responses and source identities with read_context(section='project_history'); read the original evidence with read_project_evidence(evidence_sha256=...).",
            'scope': 'Prior accepted claims retain their original inputs, scope, limitations and actual review provenance. Read those sources before reuse; no historical claim grants execution or current scientific acceptance.'}
