"""Independent local checks of verified Codex programs; never physics acceptance."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import tempfile
from types import SimpleNamespace

from .control.coordinator import publish_exact, read_regular
from .control.pause import runtime_fingerprint
from .control.strict_json import canonical_bytes, loads, require
from .inspection import host_root, read_snapshot
from .research_cases import CASES, _grouped, pack_root, verify_pack
from .settings import child_environment


def sandbox_command(command, cwd, interpreter_roots, *, timeout=120):
    """Apply the pinned runtime's explicit OS permission profile without a model."""
    from codex_cli_bin import bundled_codex_path
    cwd = Path(cwd)
    home = cwd.parent/(cwd.name+'-sdk-home')
    home.mkdir(mode=0o700)
    profile = {':root': 'deny', ':minimal': 'read', ':workspace_roots': {'.': 'write'},
               ':tmpdir': 'write', ':slash_tmp': 'deny',
               **{str(Path(root).resolve()): 'read' for root in interpreter_roots}}
    environment = child_environment()
    environment.update(CODEX_HOME=str(home), CODEX_SQLITE_HOME=str(home), TMPDIR=str(cwd))
    overrides = ('permissions.research_grade.filesystem='+json.dumps(profile).replace(': ', ' = '),
        'permissions.research_grade.network.enabled=true')
    argv = [str(bundled_codex_path())]
    for override in overrides:
        argv.extend(['--config', override])
    argv.extend(['sandbox', '--permission-profile', 'research_grade', '--cd', str(cwd), '--', *command])
    launcher = ('import os,resource,sys; '
        'resource.setrlimit(resource.RLIMIT_CORE,(0,0)); '
        'resource.setrlimit(resource.RLIMIT_CPU,('+str(timeout)+','+str(timeout)+')); '
        'resource.setrlimit(resource.RLIMIT_FSIZE,(2000000,2000000)); os.execv(sys.argv[1],sys.argv[1:])')
    import sys
    with (cwd/'stdout.log').open('wb') as stdout, (cwd/'stderr.log').open('wb') as stderr:
        process = subprocess.Popen([sys.executable, '-I', '-S', '-c', launcher, *argv],
            cwd=cwd, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # A timed-out leader has not been reaped, so its group ID cannot be reused.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
    return SimpleNamespace(exit_code=process.returncode,
        stdout=(cwd/'stdout.log').read_text(), stderr=(cwd/'stderr.log').read_text())


def execute_candidate(program, payload, python):
    """The candidate sees its inputs and libraries, never reference results or keys."""
    metadata = loads(subprocess.check_output([str(python), '-I', '-B', '-c',
        'import json,sys;print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix}))'],
        env=child_environment(), timeout=15), canonical=False)
    interpreter_roots = set(metadata.values())
    executable = Path(python).absolute()
    while True:
        for path in (executable, *executable.parents):
            if path.is_symlink():
                interpreter_roots.add(str(path.parent))
        interpreter_roots.add(str(executable.parent))
        if not executable.is_symlink():
            break
        link = executable.readlink()
        executable = (executable.parent/link).absolute() if not link.is_absolute() else link
    root = Path(tempfile.mkdtemp(prefix='lqcd-research-grade-', dir='/private/tmp'))
    publish_exact(root/'analysis.py', program)
    input_bytes = canonical_bytes(payload)
    publish_exact(root/'input.json', input_bytes)
    reply = sandbox_command([str(python), '-I', '-B', str(root/'analysis.py'), str(root/'input.json')],
                            root, interpreter_roots)
    require(read_regular(root/'analysis.py') == program and read_regular(root/'input.json') == input_bytes,
            'Candidate changed its sealed source or input')
    require(reply.exit_code == 0, 'Candidate execution failed: '+reply.stderr[:1500])
    result = loads(reply.stdout, canonical=False)
    require(type(result) is dict, 'Candidate must produce a JSON object')
    return result, {'root': str(root), 'program_sha256': sha256(program).hexdigest(),
                    'input_sha256': sha256(input_bytes).hexdigest(), 'python': str(python),
                    'runtime_roots': sorted(str(Path(p).resolve()) for p in interpreter_roots), **metadata}


def _close(actual, expected):
    require(type(actual) in (int, float) and math.isfinite(actual) and
            math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-8), 'Numerical result differs from independent reference')


def _percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered)-1)*fraction
    lower, upper = math.floor(index), math.ceil(index)
    return ordered[lower]+(ordered[upper]-ordered[lower])*(index-lower)


def check_normalization(payload, result):
    required = {(0, payload['target_bT'], 0), (payload['target_pz'], 0, 0), (0, 0, 0)}
    available = {(r['pz'], r['bT'], r['bz']) for r in payload['records']}
    if payload['omit_reference'] or not required <= available:
        require(result.get('status') == 'needs_more_info' and result.get('results') == [],
                'Missing reference was not reported without fabricated results')
        return
    require(result.get('status') == 'ok', 'Normalization did not succeed')
    records = {(r['pz'], r['bT'], r['bz'], r['sample_id']): r for r in payload['records']}
    require(len(records) == len(payload['records']), 'Duplicate input replica')
    expected = {}
    pz, bt = payload['target_pz'], payload['target_bT']
    for row in payload['records']:
        if row['pz'] != pz or row['bT'] != bt or row['bz'] not in payload['bz_values']:
            continue
        sid, bz = row['sample_id'], row['bz']
        for mode in ('mode2', 'mode3'):
            keys = [(pz, bt, bz, sid), (0, bt, 0, sid)]
            if mode == 'mode3':
                keys += [(pz, 0, 0, sid), (0, 0, 0, sid)]
            values = [records.get(key) for key in keys]
            valid = all(v and v['success'] and v['real'] is not None and v['imag'] is not None for v in values)
            z = [complex(v['real'], v['imag']) for v in values] if valid else []
            valid = valid and z[1] != 0 and (mode == 'mode2' or z[2] != 0)
            expected[(mode, bz, sid)] = (z[0]/z[1] if mode == 'mode2' else (z[0]/z[2])*(z[3]/z[1])) if valid else None
    actual = {}
    for row in result['results']:
        require(type(row['sample_id']) is int, 'Replica identity must remain an integer')
        key = (row['mode'], row['bz'], row['sample_id'])
        require(key not in actual, 'Candidate duplicated a replica')
        actual[key] = row
    require(actual.keys() == expected.keys(), 'Candidate dropped, added or renumbered replicas')
    for key, value in expected.items():
        row = actual[key]
        require(type(row['success']) is bool and row['success'] == (value is not None), 'Replica failure mask changed')
        if value is None:
            require(row['real'] is None and row['imag'] is None, 'Failed replica was replaced')
        else:
            _close(row['real'], value.real)
            _close(row['imag'], value.imag)
    summaries = {(r['mode'],r['bz'],r['component']):r for r in result['summaries']}
    keys = {(mode,bz,component) for mode,bz,_ in expected for component in ('real','imag')}
    require(summaries.keys() == keys and len(summaries) == len(result['summaries']), 'Incomplete/duplicate uncertainty summaries')
    for mode,bz,component in keys:
        values = [getattr(z,component) for (m,b,_),z in expected.items() if m == mode and b == bz and z is not None]
        row = summaries[(mode,bz,component)]
        require(type(row['n_valid']) is int and row['n_valid'] == len(values), 'Uncertainty sample count changed')
        if values:
            low, high = _percentile(values,.16), _percentile(values,.84)
            _close(row['mean'],(low+high)/2)
            _close(row['error'],(high-low)/2)
        else:
            require(row['mean'] is None and row['error'] is None, 'Uncertainty fabricated without valid replicas')


def check_c2(payload, result, *, known_ground=None):
    require(result.get('status') in ('ok', 'partial') and result.get('ground_energy_fixed') is payload['fixed_ground_energy'],
            'C2 execution or constraint declaration failed')
    fits = result['fits']
    require({(r['nstates'], r['tmin'], r['tmax']) for r in fits} ==
            {(n, t, payload['tmax']) for n in (1, 2) for t in payload['tmins']} and
            len(fits) == 2*len(payload['tmins']), 'C2 scan is incomplete or duplicated')
    for row in fits:
        require(type(row['bootstrap_total']) is int and type(row['bootstrap_successes']) is int and
                row['bootstrap_total'] == payload['bootstrap_samples'] and
                0 < row['bootstrap_successes'] <= row['bootstrap_total'], 'C2 replica accounting failed')
        failed = row['failed_sample_ids']
        require(type(failed) is list and all(type(i) is int and 0 <= i < row['bootstrap_total'] for i in failed) and
                len(set(failed)) == len(failed) == row['bootstrap_total']-row['bootstrap_successes'],
                'C2 failed replicas are not explicitly accounted for')
        require(all(type(row[k]) in (int, float) and math.isfinite(row[k]) for k in ('E0', 'E0_error', 'chi2_dof')) and
                row['E0'] > 0 and row['E0_error'] >= 0 and row['chi2_dof'] >= 0, 'Invalid C2 fit')
        if payload['fixed_ground_energy']:
            _close(row['E0'], math.hypot(payload['ground_energy_at_rest'], 2*math.pi*payload['pz']/payload['ns']))
        elif known_ground is not None and row['nstates'] == 2:
            require(abs(row['E0']-known_ground) < .01, 'Synthetic ground state not recovered')
    require(result.get('dispersion_independently_tested') is False,
            'A single-momentum fit was presented as a completed independent dispersion test')


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
               for m in pointer['members'] if m['logical_name'] in ('workspace_manifest.json', 'workspace_seal.json', 'code_agent_task.json')}
    task = members['code_agent_task.json']
    require(task['task_summary'] == 'Independent research program: '+family, 'Wrong research family')
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
        'scientific_acceptance': 'pending_human_review', 'physics_accepted': False,
        'scope': 'Independent case assessment; this report does not advance or close the canonical Run.'}
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
