"""Measure fixed offline prompt sizes and the current small numerical workload."""
import json
from pathlib import Path
import statistics
from time import perf_counter
from lqcd_agent.analysis_programs.two_point_fit.program import single_exponential_effective_mass
from lqcd_agent.llm.prompts import build_method_planner_request, build_scientific_reviewer_request
from lqcd_agent.tools.repo_inventory import build_repo_inventory


def main():
    config = {'case_id': 'measurement', 'physics_goal': 'Estimate effective mass and check stability.',
              'raw_data_path': 'raw_data/correlator.csv', 'target_observables': ['effective_mass_estimates']}
    planner = build_method_planner_request(user_goal=config['physics_goal'], case_config=config,
                                          repo_inventory=build_repo_inventory(Path.cwd()))
    reviewer = build_scientific_reviewer_request(run_result={'status': 'success', 'run_success': True},
        review_evidence={'fit_diagnostics': {'status': 'pass'}}, review_scope={
            'requires_matrix_element_validation': False, 'has_effective_mass_outputs': True})
    samples = []
    for _ in range(50):
        started = perf_counter()
        single_exponential_effective_mass(times=range(8), correlator_values=[.7**n for n in range(8)])
        samples.append(perf_counter() - started)
    result = {'prompt_chars': {name: {
        'messages': sum(len(m['content']) for m in request.messages),
        'schema': len(json.dumps(request.json_schema, sort_keys=True, separators=(',', ':')))}
        for name, request in [('planner', planner), ('reviewer', reviewer)]},
        'registered_calculation_median_seconds': statistics.median(samples),
        'calculation_samples': len(samples), 'paid_calls': 0}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
