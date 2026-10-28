"""Private research inputs and tasks for independently written Codex programs."""
import argparse
import csv
from hashlib import sha256
import io
import json
import math
from pathlib import Path

from .control.coordinator import exclusive_directory, publish_exact, read_regular
from .control.strict_json import canonical_bytes, digest, loads, require
from .settings import workspace_root


CASES = (
    {'case_id': 'c2-fit-comparison', 'family': 'c2', 'parameters': {'fixed_ground_energy': False},
     'question': 'Compare one/two-state fits and adjacent windows; justify a choice or identify insufficient evidence.',
     'review': ['window stability', 'covariance regulation', 'bootstrap failures', 'uncertainty and model assumptions']},
    {'case_id': 'c2-dispersion-constraint', 'family': 'c2', 'parameters': {'fixed_ground_energy': True},
     'question': 'Explain what fixed dispersion-based ground energy does and does not establish.',
     'review': ['explicit fixed-energy provenance', 'no independent dispersion-validation claim']},
    {'case_id': 'normalization-complex', 'family': 'normalization', 'parameters': {'omit_reference': False},
     'question': 'Compute complex mode2/mode3 normalization with paired replicas and both output components.',
     'review': ['reference identity', 'complex arithmetic', 'replica correspondence', 'nonlinear uncertainty']},
    {'case_id': 'normalization-missing-reference', 'family': 'normalization', 'parameters': {'omit_reference': True},
     'question': 'Diagnose the absent zero-momentum reference without inventing it or reporting a successful normalization.',
     'review': ['explicit missing reference', 'no zero/central-value substitution', 'no scientific acceptance']},
)

PROGRAM_REQUIREMENTS = {
    'c2': [
        'Write analysis.py as an independent NumPy/SciPy program. Do not import lqcd_analysis or obtain an existing implementation. '
        'Read a JSON input file given as argv[1], print exactly one finite JSON object, and never modify inputs.',
        'Input: configurations is an Nconfig by Nt real array; configuration_ids identifies its configuration rows in source-column order. '
        'Other fields: nt, ns, pz, lattice_spacing_fm, binsize, bootstrap_samples, seed, tmins, tmax, '
        'ground_energy_at_rest, fixed_ground_energy. The last flag varies by case. '
        'Bin consecutive configurations, disclose any trimmed remainder, fold C(t)=(C(t)+C(Nt-t))/2, '
        'and bootstrap whole binned configurations using numpy.default_rng(seed), with bootstrap_samples draws of Nbin indices.',
        'Fit one and two states with C(t)=sum_j A_j*(exp(-E_j*t)+exp(-E_j*(Nt-t))). '
        'Use positive amplitudes/energies and E1>E0. Compare each requested inclusive [tmin,tmax] window. '
        'Estimate and regulate the correlated covariance transparently. Report regulation and every unsuccessful replica; '
        'do not replace failed replica parameters with central-fit parameters.',
        'When fixed_ground_energy is true, fix E0=sqrt(ground_energy_at_rest**2+(2*pi*pz/ns)**2), '
        'and explicitly state that this does not independently test dispersion. When false, infer E0 from data. '
        'Set dispersion_independently_tested=false in both cases: this program fits a single momentum and does not perform a separate dispersion comparison. '
        'Do not select a preferred fit solely from its smallest chi-squared.',
        'Output status (ok when all fits/replicas succeed, partial when any fail), fits (each with nstates,tmin,tmax,E0,E0_error,chi2_dof,bootstrap_successes,bootstrap_total,failed_sample_ids), '
        'ground_energy_fixed, dispersion_independently_tested, warnings, and method. '
        'Test your program on synthetic finite-Nt one/two-exponential data, including the constrained case. '
        'Use temporary test data only, without any measured research values or reference outputs.',
    ],
    'normalization': [
        'Write analysis.py as an independent Python/NumPy program. Do not import lqcd_analysis or obtain an existing implementation. '
        'Read a JSON input file given as argv[1], print exactly one finite JSON object, and never modify inputs.',
        'Input records contain pz,bT,bz,sample_id,success,real,imag; failed values can be null. '
        'Also supplied: target_pz,target_bT,bz_values,omit_reference. Preserve every original sample_id; '
        'reject duplicate keys and incomplete complex pairs. Never independently shuffle replicas.',
        'For each target h(P,bT,bz), mode2=h(P,bT,bz)/h(0,bT,0). '
        'Mode3=(h(P,bT,bz)/h(P,0,0))*(h(0,0,0)/h(0,bT,0)). '
        'Perform complex arithmetic on matching sample IDs before taking real/imaginary components and summarizing.',
        'If omit_reference is true, remove all records at pz=0,bT=target_bT,bz=0 before analysis. '
        'An absent required reference must yield status needs_more_info and no normalized results. '
        'Preserve explicit failed outcomes for unsuccessful/nonfinite/zero-denominator replicas; never replace them with zero or a central value.',
        'Output status (ok for computed results, needs_more_info for an absent reference), results (rows with mode,bz,sample_id,success,real,imag; failed values null), '
        'summaries (rows with mode,bz,component,mean,error,n_valid), warnings, and method. '
        'In every results and summaries row, mode must be the literal string "mode2" or "mode3", never the integer 2 or 3. '
        'For summaries use midpoint/half-width of the 16th/84th percentiles (linear interpolation) over valid paired replicas; '
        'if none survive, mean/error must be null and n_valid zero. '
        'Test complex arithmetic and the missing-reference case on synthetic inputs. '
        'Calibration: target=2+4j, h(P,0,0)=1+1j, h(0,bT,0)=2-1j, h(0,0,0)=3+0.5j '
        'gives mode2=2j and mode3=2.5+3.5j. No measured research inputs or reference outputs are provided.',
    ],
}


def pack_root():
    return workspace_root() / 'raw_data/research_cases'


def _grouped(raw):
    lines = raw.decode().splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith('bz\t')), None)
    require(start is not None, 'Missing research table header')
    reader = csv.DictReader(lines[start:], delimiter='\t')
    require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), 'Invalid research table header')
    rows = list(reader)
    require(rows and all(None not in row and all(v is not None for v in row.values()) for row in rows),
            'Empty or malformed research table')
    return rows


def extract(project, correlator, *, workspace=None):
    """Read source bytes once; publish a fresh private pack without overwriting."""
    root = workspace_root(workspace) / 'raw_data/research_cases'
    root.parent.mkdir(exist_ok=True)
    exclusive_directory(root)
    sources, assets = [], {}

    def source(path, role):
        path = Path(path)
        raw = read_regular(path)
        sources.append({'path': str(path), 'sha256': sha256(raw).hexdigest(), 'role': role})
        return raw

    def asset(name, content):
        destination = root/name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        publish_exact(destination, content)
        assets[name] = sha256(content).hexdigest()

    raw = source(correlator, 'original_correlator')
    reader = csv.reader(io.StringIO(raw.decode()))
    require(next(reader) == ["['csv']"], 'Expected the source correlator CSV format')
    rows = [[float(value) for value in row] for row in reader if row]
    require(len(rows) == 64 and all(row[0] == i and len(row) == len(rows[0]) for i, row in enumerate(rows)),
            'Correlator time/configuration axes changed')
    require(all(math.isfinite(value) for row in rows for value in row), 'Nonfinite source correlator')
    configurations = [list(values) for values in zip(*(row[1:] for row in rows), strict=True)]
    c2 = {'source_kind': 'measured_lattice_data', 'configurations': configurations,
          'configuration_ids': list(range(len(configurations))), 'configuration_id_kind': 'source_column_index',
          'nt': 64, 'ns': 64, 'pz': 6, 'lattice_spacing_fm': .076, 'binsize': 10,
          'bootstrap_samples': 200, 'seed': 2026, 'tmins': [4, 5, 6], 'tmax': 13,
          'ground_energy_at_rest': .0539202}
    asset('inputs/c2.json', canonical_bytes(c2))
    project = Path(project)
    records = []
    for pz in (0, 6):
        title = f'l64c64a076_m140_fit_pz{pz}'
        for bt in (0, 2):
            components = {}
            for component in ('real', 'imag'):
                name = f'{title}_T5_eta0_bT{bt}_{component}_2state_samples.txt'
                path = project/'2-bm-new/results_fit_nst2'/title/'samples'/name
                values = {}
                for row in _grouped(source(path, 'fitted_bootstrap_input')):
                    key = (int(row['bz']), int(row['sample_id']))
                    if key[0] not in (0, 2, 4):
                        continue
                    require(key not in values, 'Duplicate bootstrap identity')
                    values[key] = (int(row['success']), float(row['m0']))
                components[component] = values
            require(components['real'].keys() == components['imag'].keys(), 'Complex replica identities differ')
            for (bz, sid), (success, real) in sorted(components['real'].items()):
                imag_success, imag = components['imag'][(bz, sid)]
                valid = success == imag_success == 1 and math.isfinite(real) and math.isfinite(imag)
                records.append({'pz': pz, 'bT': bt, 'bz': bz, 'sample_id': sid, 'success': valid,
                                'real': real if valid else None, 'imag': imag if valid else None})
    norm = {'source_kind': 'fitted_measured_bootstrap', 'records': records,
            'target_pz': 6, 'target_bT': 2, 'bz_values': [0, 2, 4],
            'lineage_limit': 'Matching source sample IDs are retained; the original resampling-index plan is unavailable.'}
    asset('inputs/normalization.json', canonical_bytes(norm))
    for mode in ('mode2', 'mode3'):
        title = 'l64c64a076_m140_fit_pz6'
        path = project/'3-normalize-new'/title/'samples'/f'{title}_T5_eta0_bT2_{mode}_real_2state_samples.txt'
        asset(f'references/{mode}_real.txt', source(path, 'withheld_existing_result'))
    title = 'l64c64a076_m140_fit_pz6'
    path = project/'1-c2pt-fit/results_nstate_fit_1state'/title/'tables'/f'{title}_symmetric_1state_tmax13_fits.txt'
    lines = source(path, 'withheld_existing_fit').decode().splitlines()
    header = lines[0].removeprefix('#').split()
    reference = [dict(zip(header, map(float, line.split()), strict=True)) for line in lines[1:] if line.strip()]
    asset('references/c2_1state.json', canonical_bytes([row for row in reference if row['tmin'] in (4, 5, 6)]))
    for name in ('nstate_fit_k6.ipynb', 'nstate_fit_k6_2state.ipynb'):
        source(project/'1-c2pt-fit'/name, 'original_configuration')
    for item in sources:
        require(sha256(read_regular(item['path'])).hexdigest() == item['sha256'], 'Original source changed during extraction')
    manifest = {'schema_version': '0.1', 'cases': list(CASES), 'assets': assets, 'sources': sources,
                'scientific_acceptance': 'pending_human_review',
                'reference_status': 'comparison_only_not_certified_truth',
                'generation_context': 'Task definitions and synthetic calibration only; measured inputs and references withheld.'}
    manifest['manifest_digest'] = digest(manifest)
    publish_exact(root/'manifest.json', canonical_bytes(manifest))
    return {'pack': str(root), 'manifest_digest': manifest['manifest_digest'], 'cases': [c['case_id'] for c in CASES]}


def verify_pack(root=None):
    root = Path(root) if root is not None else pack_root()
    value = loads(read_regular(root/'manifest.json'))
    require(value['manifest_digest'] == digest({k: v for k, v in value.items() if k != 'manifest_digest'}),
            'Research manifest changed')
    require(value['cases'] == list(CASES), 'Research case definitions changed')
    require(set(value['assets']) == {'inputs/c2.json','inputs/normalization.json',
        'references/mode2_real.txt','references/mode3_real.txt','references/c2_1state.json'},
        'Research asset catalog is incomplete or unexpected')
    for name, expected in value['assets'].items():
        path = root/name
        require(path == path.resolve() and path.is_relative_to(root.resolve()), 'Research asset escaped its pack')
        require(sha256(read_regular(path)).hexdigest() == expected, 'Research input/reference changed')
    return value


def prepare_cases(python):
    """Publish normal scientific-entry configurations; retain one coding workflow."""
    verify_pack()
    paths = []
    for case in CASES:
        config = {'schema_version': '0.1', 'case_id': case['case_id'], 'physics_goal': case['question'],
            'source_kind': 'measured_lattice_data',
            'raw_data_path': f"raw_data/research_cases/inputs/{case['family']}.json",
            'target_observables': [case['family']+'_scientific_result'],
            'generated_program': {'python': str(python), 'parameters': case['parameters'],
                'requirements': PROGRAM_REQUIREMENTS[case['family']], 'timeout_seconds': 120,
                'result_kind': case['family']}}
        path = pack_root()/'cases'/(case['case_id']+'.json')
        path.parent.mkdir(exist_ok=True, mode=0o700)
        publish_exact(path, canonical_bytes(config))
        paths.append(str(path))
    return {'case_configs': paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('describe')
    commands.add_parser('verify')
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--python', type=Path, required=True)
    command = commands.add_parser('extract')
    command.add_argument('--project', required=True)
    command.add_argument('--correlator', required=True)
    args = parser.parse_args()
    if args.command == 'extract':
        result = extract(args.project, args.correlator)
    elif args.command == 'prepare':
        result = prepare_cases(args.python)
    elif args.command == 'verify':
        result = {'manifest_digest': verify_pack()['manifest_digest'], 'passed': True}
    else:
        result = {'cases': CASES, 'program_requirements': PROGRAM_REQUIREMENTS}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
