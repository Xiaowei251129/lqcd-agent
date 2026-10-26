"""Numerical checks for the current scientific programs, without a second graph."""
import math
from .analysis_programs.two_point_fit import single_exponential_effective_mass as fit
from .analysis_programs.matrix_element import check_matrix_element_normalization as normalize


def run_benchmark():
    cases = []
    def record(name, output, passed):
        cases.append({'case': name, 'passed': bool(passed), 'output': output})
    value = fit([0, 1, 2], [1, .5, .25])
    record('clean_mass', value, len(value['effective_mass_estimates']) == 2 and all(math.isclose(r['effective_mass'], math.log(2), rel_tol=1e-12) for r in value['effective_mass_estimates']))
    value = fit([0, 2], [1, .5])
    record('time_spacing', value, math.isclose(value['effective_mass_estimates'][0]['effective_mass'], math.log(2) / 2))
    try:
        fit([0, 1], [1])
    except ValueError as error:
        record('invalid_lengths', str(error), True)
    else:
        record('invalid_lengths', None, False)
    value = fit([0, 1], [0, -1])
    record('nonpositive_correlator', value, value['status'] == 'failed' and not value['effective_mass_estimates'])
    value = normalize([{'z': 0, 'Pz': 5, 'component': 'real', 'value': 1.01}])
    record('normalization_pass', value, value['all_passed'])
    value = normalize([{'z': 0, 'Pz': 5, 'component': 'real', 'value': 1.2}])
    record('normalization_failure', value, not value['all_passed'] and value['normalization_diagnostics'][0]['deviation'] > .05)
    value = normalize([{'z': 1, 'Pz': 5, 'component': 'real', 'value': 1}])
    record('missing_normalization_point', value, value['status'] == 'failed' and not value['all_passed'])
    value = fit([0, 1, 2, 3], [1, .82, .60, .385], [.025, .030, .035, .040])
    record('window_contamination', value, value['diagnostic_flags'] == ['fit_window_dependence'])
    value = fit([0, 1, 2, 3], [1, .73, .55, .40], [.060, .065, .070, .080])
    record('noisy_valid_window', value, value['fit_window_diagnostics']['status'] == 'pass')
    return {'kind': 'current_numerical_benchmark', 'passed': len(cases) == 9 and all(r['passed'] for r in cases), 'cases': cases}


if __name__ == '__main__':
    import json
    result = run_benchmark()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
