"""Independent local checks of verified Codex programs; never physics acceptance."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random
import math

from .control.coordinator import publish_exact, read_regular
from .control.pause import runtime_fingerprint
from .control.strict_json import canonical_bytes, loads, require
from .inspection import host_root, read_snapshot
from .research_cases import CASES, _grouped, pack_root, verify_pack
from .code_agent.execution import execute_candidate
from .analysis.generated_diagnostics import check_c2, check_normalization, _close


def calibration(family):
    if family == 'normalization':
        records = []
        for sid in (7, 13):
            for pz, bt, value in ((6, 2, 2+4j), (6, 0, 1+1j), (0, 2, 2-1j), (0, 0, 3+.5j)):
                records.append({'pz': pz, 'bT': bt, 'bz': 0, 'sample_id': sid, 'success': True,
                                'real': value.real, 'imag': value.imag})
        return {'records': records, 'target_pz': 6, 'target_bT': 2, 'bz_values': [0], 'omit_reference': False}
    rng = random.Random(57)
    mean = [1.2*(math.exp(-.27*t)+math.exp(-.27*(64-t)))+
            .8*(math.exp(-.73*t)+math.exp(-.73*(64-t))) for t in range(64)]
    return {'configurations': [[value+rng.gauss(0, .0001) for value in mean] for _ in range(200)],
        'configuration_ids': list(range(200)), 'nt': 64, 'ns': 64, 'pz': 0, 'lattice_spacing_fm': .076,
        'binsize': 10, 'bootstrap_samples': 200, 'seed': 2026, 'tmins': [4, 5, 6], 'tmax': 13,
        'ground_energy_at_rest': .15, 'fixed_ground_energy': False}


def evaluate(host, case, run, family, python):
    root, manifest = host_root(host), verify_pack()
    locator = {'case_id': case, 'run_id': run}
    snapshot = read_snapshot(root, locator)
    run_root = root/case/run
    index = loads(read_regular(run_root/'artifact_index.json'))
    pointer = index['current']['code']
    require(pointer is not None and pointer['status'] == 'success', 'Research evaluation needs verified current Code')
    members = {m['logical_name']: loads(read_regular(run_root/m['canonical_path']))
               for m in pointer['members'] if m['logical_name'] in ('workspace_manifest.json', 'workspace_seal.json')}
    from .code_agent.workspace import WorkspaceProvider
    provider = WorkspaceProvider(root/'code_workspaces')
    workspace = members['workspace_manifest.json']
    files = provider.verify_sealed(workspace, provider._public_witness(workspace), members['workspace_seal.json']['final_tree_digest'])
    program = files['analysis.py']
    results = []
    check = check_c2 if family == 'c2' else check_normalization
    def assess(case_id, payload, validate):
        record = {'case_id': case_id, 'passed': False, 'input_sha256': sha256(canonical_bytes(payload)).hexdigest()}
        results.append(record)
        try:
            value, execution = execute_candidate(program, payload, python)
            record.update(execution=execution, result=value)
            validate(value)
            record['passed'] = True
        except Exception as error:
            record.update(error_type=type(error).__name__, error=str(error))
        return record['passed']

    payload = calibration(family)
    calibrated = assess(family+'-synthetic-calibration', payload,
        lambda value: check(payload, value, known_ground=.27) if family == 'c2' else check(payload, value))
    original = loads(read_regular(pack_root()/f'inputs/{family}.json'))
    for definition in CASES:
        if definition['family'] != family:
            continue
        if not calibrated:
            results.append({'case_id': definition['case_id'], 'passed': False, 'not_run': 'synthetic_calibration_failed'})
            continue
        payload = {**deepcopy(original), **definition['parameters']}
        missing_reference = family == 'normalization' and payload['omit_reference']
        if missing_reference:
            payload['records'] = [r for r in payload['records'] if (r['pz'], r['bT'], r['bz']) != (0, payload['target_bT'], 0)]
            payload['omit_reference'] = False
        def validate(value):
            check(payload, value)
            if family == 'c2' and not payload['fixed_ground_energy']:
                reference = {int(r['tmin']): r for r in loads(read_regular(pack_root()/'references/c2_1state.json'))}
                for row in value['fits']:
                    if row['nstates'] == 1:
                        expected = reference[row['tmin']]
                        require(abs(row['E0']-expected['E0_mean']) <= max(5*expected['E0_err'], .002),
                                'Real-data one-state energy differs from the withheld comparison')
            if family != 'normalization' or missing_reference:
                return
            for mode in ('mode2', 'mode3'):
                reference = {(int(r['bz']), int(r['sample_id'])): r for r in
                    _grouped(read_regular(pack_root()/f'references/{mode}_real.txt')) if int(r['bz']) in payload['bz_values']}
                for row in value['results']:
                    if row['mode'] == mode and row['success']:
                        _close(row['real'], float(reference[(row['bz'], row['sample_id'])]['m0']))
        assess(definition['case_id'], payload, validate)
    require(verify_pack()['manifest_digest'] == manifest['manifest_digest'], 'Case pack changed during evaluation')
    passed = all(r['passed'] for r in results)
    report = {'family': family, 'source_run': {**locator, 'host': host, 'status': snapshot.state['run_status']},
        'code_artifact_id': pointer['artifact_id'], 'program_sha256': sha256(program).hexdigest(),
        'validator_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'validator_runtime_fingerprint': runtime_fingerprint(),
        'case_manifest_digest': manifest['manifest_digest'], 'checks': results, 'numerical_checks_passed': passed,
        'scientific_acceptance': 'not_system_reviewed', 'assessment_kind': 'independent_check_only',
        'physics_accepted': False,
        'scope': 'Independent numerical checks only; no system acceptance or physical-validity claim. '
                 'This report cannot advance or close the canonical Run.'}
    destination = pack_root()/f'{family}-{sha256(canonical_bytes(report)).hexdigest()}-assessment.json'
    publish_exact(destination, canonical_bytes(report))
    return {'report': str(destination), 'numerical_checks_passed': passed, 'physics_accepted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--family', choices=('c2', 'normalization'), required=True)
    parser.add_argument('--python', type=Path, required=True, help='Trusted local interpreter with NumPy and SciPy')
    args = parser.parse_args()
    result = evaluate(args.host, args.case, args.run, args.family, args.python)
    print(json.dumps(result, indent=2))
    if not result['numerical_checks_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
