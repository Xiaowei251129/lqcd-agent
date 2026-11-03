"""Deterministic research state from verified project evidence, never authority."""
from copy import deepcopy

from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, require
from .projects import ProjectStore


def project_history(workspace, project_id, exclude_locator=None):
    projects = ProjectStore(workspace)
    evidence, observations, conclusions = [], {}, {}
    for run in projects.runs(project_id):
        if exclude_locator is not None and run['run_locator'] == exclude_locator:
            continue
        entries = [entry for entry in run['evidence'] if entry['current'] and
                   entry['source'] == 'scientific' and entry['name'].endswith('/collaboration.json')]
        # Only a review supersedes a plan inside the same Run. Different Runs
        # have no implicit supersession relation, even when one is newer.
        reviews = [entry for entry in entries if entry['slot'] == 'review']
        for entry in reviews or [entry for entry in entries if entry['slot'] == 'plan']:
            source = {'run_locator': run['run_locator'], 'host': run['host'],
                      'manifest_sha256': run['sha256'], 'scientific_outcome': run.get('scientific_outcome'), 'decision_origin': run.get('decision_origin'),
                      'project_revision': run['project_revision'], 'evidence_sha256': entry['sha256']}
            evidence.append(source)
            collaboration = loads(projects.evidence(project_id, entry['sha256']), canonical=False)
            for issue in collaboration.get('issues', []):
                require(type(issue) is dict and type(issue.get('id')) is str and issue['id'],
                        'Stored issues must have Host identifiers')
                require(issue.get('status') in ('open', 'blocked', 'addressed'), 'Unknown stored issue status')
                bucket = observations.setdefault(issue['id'], [])
                require(not bucket or bucket[0]['issue']['question'] == issue['question'],
                        'Stored issue identity changed')
                bucket.append({'issue': issue, 'source': source})
            # Only the verified capture may label a claim accepted. A model's
            # decision/summary cannot promote pending or held evidence.
            if run.get('scientific_outcome') in ('supported', 'qualified') and collaboration.get('summary'):
                key = digest({'statement': collaboration['summary'], 'project_revision': run['project_revision'],
                              'scientific_outcome': run['scientific_outcome'], 'decision_origin': run['decision_origin']})
                value = conclusions.setdefault(key, {'statement': collaboration['summary'],
                    'scientific_outcome': run['scientific_outcome'], 'decision_origin': run['decision_origin'], 'project_revision': run['project_revision'],
                    'sources': []})
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
            'evidence': evidence,
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
            'history_source': "Read full resolutions, conflicting responses and source identities with read_context(section='project_history'); read the original evidence with read_project_evidence(evidence_sha256=...).",
            'scope': 'Prior accepted claims retain their original inputs, scope, limitations and actual review provenance. Read those sources before reuse; no historical claim grants execution or current scientific acceptance.'}
