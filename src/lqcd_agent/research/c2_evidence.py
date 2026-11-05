"""Bind scientific interpretations to the exact plan and numerical fit rows."""
from hashlib import sha256
from pathlib import Path
import re

from lqcd_agent.control.coordinator import read_regular
from lqcd_agent.control.strict_json import digest, loads, require


_TARGET = re.compile(r'/fits/(0|[1-9][0-9]{0,8})(?:/(nstates|tmin|tmax|E0|E0_error|chi2_dof|bootstrap_successes|bootstrap_total|failed_sample_ids))?')


def resolve_c2_target(result, pointer):
    """Resolve only public fit rows and fields, using canonical JSON Pointer indices."""
    match = _TARGET.fullmatch(pointer) if type(pointer) is str else None
    fits = result.get('fits') if type(result) is dict else None
    require(match and type(fits) is list and int(match[1]) < len(fits), 'Unknown C2 fit pointer')
    row = fits[int(match[1])]
    require(type(row) is dict and (match[2] is None or match[2] in row), 'Unknown C2 fit field')
    return row if match[2] is None else row[match[2]]


def c2_review_reference(host, context, sources):
    """Join the diagnostic witness to the immutable numerical member of this Run."""
    if ((sources.get('run_result') or {}).get('generated_execution') or {}).get('result_kind') != 'c2':
        return None
    diagnostic = (sources.get('review_evidence') or {}).get('generated_diagnostics') or {}
    witnesses = {(row.get('path'), row.get('value')) for row in diagnostic.get('evidence', []) if row.get('field') == 'sha256'}
    identity = context['identity']
    for ref in context.get('current_evidence', []):
        attempt, _, slot = ref['artifact_id'].rpartition(':')
        member = Path('analysis_outputs/generated_result.json')
        if slot != 'analysis' or ref['member'] != str(Path('attempts') / attempt / member):
            continue
        producer = Path(host) / 'domain' / attempt / identity['case_id'] / identity['run_id'] / member
        if (str(producer), ref['sha256']) in witnesses:
            return ref
    return None


def c2_facts(root, goal, plan, plan_sha, ref):
    """The same Host projection supplies independent review, synthesis and publication."""
    target = root / ref['member']
    require(target == target.resolve() and target.is_relative_to(root), 'C2 evidence escaped Run')
    raw = read_regular(target)
    require(sha256(raw).hexdigest() == ref['sha256'], 'C2 numerical evidence changed')
    result = loads(raw, canonical=False)
    fits = []
    for i, row in enumerate(result['fits']):
        fits.append({'pointer': f'/fits/{i}', 'nstates': row['nstates'], 'tmin': row['tmin'], 'tmax': row['tmax'],
                     'estimate': f"aE₀ = {row['E0']} ± {row['E0_error']}",
                     'replicas': f"{row['bootstrap_successes']} / {row['bootstrap_total']}"})

    criteria = []
    prepared = goal.get('preparation')
    if prepared is not None:
        require(plan.get('domain_result', {}).get('preparation_sha256') == prepared['plan_sha256'] and
                digest(prepared['proposal']) == prepared['proposal_sha256'], 'Selected C2 plan binding changed')
        plan_sha = prepared['plan_sha256']
        briefs = [('/domain_result/preparation/brief', prepared['proposal']['brief'])]
    else:
        briefs = [(f'/collaboration/exchanges/{i}/brief', exchange['brief'])
                  for i, exchange in enumerate(plan.get('collaboration', {}).get('exchanges', [])) if 'brief' in exchange]
    for prefix, brief in briefs:
        for i, sentence in enumerate(brief['success_criteria']):
            criteria.append({'text': sentence, 'pointer': f'{prefix}/success_criteria/{i}',
                             'assessment': None, 'fit_pointers': []})
    return {'plan_sha256': plan_sha, 'result_sha256': ref['sha256'], 'criteria': criteria, 'fits': fits,
            'fixed_ground_energy': result['ground_energy_fixed'],
            'selection': {'status': 'unassessed', 'fit_pointer': None}}


def bind_c2_interpretation(facts, interpretation):
    """Validate model-selected citations. Numerical values always come from the Host."""
    if interpretation is None:
        return facts
    criteria = {item['pointer']: item for item in facts['criteria']}
    fits = {row['pointer'] for row in facts['fits']}
    evaluated = set()
    for choice in interpretation['assessments']:
        key, refs = choice['criterion'], choice['fit_pointers']
        require(key in criteria and key not in evaluated, 'Unknown or duplicate C2 criterion')
        require(refs and len(set(refs)) == len(refs) and set(refs) <= fits, 'Invalid C2 criterion fit reference')
        require(choice['assessment'] in ('supports', 'limits', 'contradicts'), 'Invalid C2 criterion assessment')
        evaluated.add(key)
        criteria[key].update(assessment=choice['assessment'], fit_pointers=refs)
    status, preferred = interpretation['selection'], interpretation['preferred_fit']
    if status == 'selected':
        require(preferred in fits and any(preferred in criteria[k]['fit_pointers'] and
                criteria[k]['assessment'] == 'supports' for k in evaluated),
                'Preferred C2 fit needs a supporting plan criterion and its cited row')
    else:
        require(status in ('no_preference', 'unassessed') and preferred is None,
                'C2 selection status conflicts with preferred fit')
    facts['selection'] = {'status': status, 'fit_pointer': preferred}
    return facts


def selection_text(facts):
    selection = facts['selection']
    if selection['status'] == 'selected':
        row = next(r for r in facts['fits'] if r['pointer'] == selection['fit_pointer'])
        return f"Research Manager preferred {row['nstates']}-state [{row['tmin']}, {row['tmax']}], {row['estimate']}."
    if selection['status'] == 'no_preference':
        return 'The Research Manager reported no preferred ground-state energy.'
    return 'No fit selection was assessed in the structured conclusion.'


def c2_report(facts):
    lines = [selection_text(facts), 'Plan SHA-256: ' + facts['plan_sha256'],
             'Analysis result SHA-256: ' + facts['result_sha256'], '',
             'Research Manager assessments of the scientific decision criteria:']
    for item in facts['criteria']:
        lines.append(f"- {item['text']} [plan {item['pointer']}] — {item['assessment'] or 'unassessed'}"
                     + ('; result ' + ', '.join(item['fit_pointers']) if item['fit_pointers'] else ''))
    if not facts['criteria']:
        lines.append('No explicit decision criteria were recorded.')
    lines.extend(['', 'Host numerical values from the sealed Analysis result (lattice units):'])
    if facts['fixed_ground_energy']:
        lines.append('Fixed ground energy: uncertainty is conditional on the imposed constraint.')
    for row in facts['fits']:
        lines.append(f"- {row['nstates']}-state [{row['tmin']}, {row['tmax']}]: {row['estimate']}; "
                     f"valid replicas {row['replicas']} [result {row['pointer']}/E0, {row['pointer']}/E0_error]")
    return '\n'.join(lines)
