"""Host numerical contracts shared by scientific review and independent case assessment."""
import math
from lqcd_agent.control.strict_json import require


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


def diagnose_generated_output(path, kind, payload):
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import loads
    from hashlib import sha256
    report = {'status': 'pass', 'summary': 'Generated scientific output passed Host numerical checks.',
              'evidence': [], 'findings': [], 'warnings': [], 'recommended_checks': []}
    def warning(code, message, severity='warning'):
        report['warnings'].append({'section': 'generated_diagnostics', 'code': code, 'message': message,
            'severity': severity, 'decision_coordinator_flag': severity == 'severe', 'path': str(path),
            'field': '$', 'value': kind})
    try:
        raw = read_regular(path)
        result = loads(raw, canonical=False)
        report['evidence'].append({'path': str(path), 'field': 'sha256', 'value': sha256(raw).hexdigest()})
        require(kind in ('c2', 'normalization', 'replica_observables'), 'Unknown scientific output contract')
        if kind == 'replica_observables':
            from lqcd_agent.research.observable_contract import check_observables
            checked = check_observables(payload, result)
            report['findings'].append(f"Checked {checked['valid_observables']} defined observables and retained {checked['failed_replicas']} failed replicas.")
            warning('observable_physics_not_validated', 'Host checked identities and uncertainty arithmetic only; definitions, fitting, units and original resampling provenance need independent scientific review.')
            if checked['failed_replicas']:
                warning('failed_observable_replicas', 'Failed replicas remain explicit; assess selection bias and sensitivity.')
            if result['status'] == 'needs_more_info':
                warning('observable_inputs_missing', 'No observable estimate was produced because required information is missing.', 'severe')
            report['recommended_checks'] = ['Validate the physical method on independent calibration data and assess systematic uncertainties.']
        else:
            (check_c2 if kind == 'c2' else check_normalization)(payload, result)
        if kind == 'c2':
            report['findings'].append(f"Input: {len(payload['configurations'])} configurations, Nt={payload['nt']}, Ns={payload['ns']}, pz={payload['pz']}, a={payload['lattice_spacing_fm']} fm, binsize={payload['binsize']}.")
            for fit in result['fits']:
                report['findings'].append(f"{fit['nstates']}-state [{fit['tmin']},{fit['tmax']}]: E0={fit['E0']:.6g}, error={fit['E0_error']:.3g}, chi2/dof={fit['chi2_dof']:.4g}, successful replicas={fit['bootstrap_successes']}/{fit['bootstrap_total']}.")
            if any(row['failed_sample_ids'] for row in result['fits']):
                warning('failed_bootstrap_replicas', 'Some bootstrap fits failed; inspect their retained IDs and uncertainty stability.')
            if payload['fixed_ground_energy']:
                warning('fixed_energy_constraint', 'Energy and uncertainty are conditional on the supplied fixed rest-energy constraint; no independent dispersion comparison was performed.')
            if payload.get('configuration_id_kind') == 'source_column_index':
                warning('configuration_identity_limit', 'Source-column identities do not independently establish physical configuration identity or chronological binning order.')
            report['recommended_checks'] = ['Assess fit-window/model stability and covariance regulation before choosing a fit.']
        elif kind == 'normalization':
            for row in result.get('summaries', []):
                report['findings'].append(f"{row['mode']} bz={row['bz']} {row['component']}: midpoint={row['mean']}, half-width={row['error']}, valid replicas={row['n_valid']}.")
            if payload.get('lineage_limit'):
                warning('resampling_lineage_unverified', payload['lineage_limit'])
            if any(not row['success'] for row in result['results']):
                warning('failed_normalization_replicas', 'Failed paired replicas remain explicit; assess the surviving sample fraction.')
            report['recommended_checks'] = ['Verify reference identity and original paired resampling provenance.']
    except Exception as error:
        warning('generated_output_invalid', str(error), 'severe')
        report['recommended_checks'] = ['Resolve the Host numerical validation failure before scientific acceptance.']
    if report['warnings']:
        report['status'] = 'severe' if any(w['severity'] == 'severe' for w in report['warnings']) else 'warning'
        report['summary'] = 'Generated scientific output requires evidence-backed review.'
    return report
