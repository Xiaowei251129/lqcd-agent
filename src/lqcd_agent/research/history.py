"""Verified prior research context, without importing prior control authority."""
from lqcd_agent.control.strict_json import canonical_bytes, loads
from .projects import ProjectStore


def project_history(workspace, project_id, exclude_locator=None):
    projects = ProjectStore(workspace)
    result = []
    for run in projects.runs(project_id):
        if exclude_locator is not None and run['run_locator'] == exclude_locator:
            continue
        entries = [entry for entry in run['evidence'] if entry['current'] and
                   entry['source'] == 'scientific' and entry['name'].endswith('/collaboration.json')]
        # A review carries the disposition of the plan questions; retain a plan only
        # when this Run has not yet produced review evidence.
        reviews = [entry for entry in entries if entry['slot'] == 'review']
        for entry in reviews or [entry for entry in entries if entry['slot'] == 'plan']:
            collaboration = loads(projects.evidence(project_id, entry['sha256']), canonical=False)
            collaboration = {'summary': collaboration.get('summary', ''),
                             'issues': collaboration.get('issues', [])}
            result.append({'run_locator': run['run_locator'], 'host': run['host'],
                           'manifest_sha256': run['sha256'], 'scientific_acceptance': run['scientific_acceptance'],
                           'evidence_sha256': entry['sha256'], 'collaboration': collaboration})
    if len(canonical_bytes(result)) > 24000:
        from lqcd_agent.llm.prompts import ContextLimitError
        raise ContextLimitError('Project issue context exceeds 24000 bytes; narrow the project scope before starting a new research cycle.')
    return result
