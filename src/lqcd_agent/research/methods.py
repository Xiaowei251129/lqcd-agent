"""Freeze reviewed reuse inputs for one Run; they never become a second executor."""
from dataclasses import dataclass
from hashlib import sha256
from lqcd_agent.control.strict_json import closed, require
from .library import Library


def snapshot_methods(config, workspace):
    dependencies = config.get('method_dependencies', [])
    require(type(dependencies) is list and len(dependencies) <= 8, 'Use at most eight explicit method dependencies')
    result = []
    library = Library(workspace)
    for dependency in dependencies:
        closed(dependency, ('id', 'revision', 'sha256'))
        record, raw = library.method_snapshot(dependency['id'])
        require(all(record[key] == dependency[key] for key in dependency), 'Method dependency needs current review')
        require(len(raw) <= 128*1024, 'Reusable method source exceeds 128 KiB')
        result.append({'id': record['id'], 'revision': record['revision'], 'asset_sha256': record['sha256'],
                       'source_sha256': sha256(raw).hexdigest(), 'source': raw.decode('utf-8'),
                       'scope': {'declared': record['scope'], 'validated_family': record['implementation']['family'],
                                 'limitations': record['implementation']['limitations']},
                       'validation': record['implementation']['validation']})
    require(len({r['id'] for r in result}) == len(result), 'Duplicate method dependency')
    return result


def method_files(snapshots):
    files = {}
    for snapshot in snapshots:
        from lqcd_agent.control.coordinator import component
        component(snapshot['id'])
        raw = snapshot['source'].encode('utf-8')
        require(sha256(raw).hexdigest() == snapshot['source_sha256'], 'Frozen reusable source changed')
        files['reused/'+snapshot['id']+'.py'] = raw
    return files


# Only the executing Host factory creates this in-process witness. Serialized
# reports remain evidence; supplying a JSON file cannot recreate execution.
_EXECUTED = object()


@dataclass(frozen=True)
class ExecutedMethodValidation:
    record: bytes
    authority: object

    def __post_init__(self):
        from lqcd_agent.control.strict_json import loads
        require(self.authority is _EXECUTED, 'Method validation must execute through the Host')
        loads(self.record)


def executed_assessment(assessment, source_digest):
    from lqcd_agent.control.strict_json import loads
    require(type(assessment) is ExecutedMethodValidation and assessment.authority is _EXECUTED,
            'Method validation must execute through the Host, not an uploaded report')
    report = loads(assessment.record)
    require(report['source_sha256'] == source_digest, 'Executed validation source changed')
    return report


def validate_assessment_record(report, source_digest):
    from lqcd_agent.control.strict_json import canonical_bytes, digest_value
    from lqcd_agent.analysis.generated_diagnostics import check_c2, check_normalization
    closed(report, ('kind', 'source_sha256', 'family', 'validator_sha256', 'validator_runtime_fingerprint',
                    'checks', 'passed', 'limitations'))
    names = {'c2': ['two_state_ground_low', 'two_state_ground_high', 'fixed_ground'],
             'normalization': ['paired_complex', 'failed_replica', 'missing_reference']}
    require(report['kind'] == 'host_executed_method_validation' and report['family'] in names and
            report['source_sha256'] == source_digest and report['passed'] is True and
            type(report['checks']) is list and [r['name'] for r in report['checks']] == names[report['family']] and
            type(report['limitations']) is list and bool(report['limitations']),
            'Method needs passing executed calibration for this exact source')
    digest_value(report['validator_sha256'])
    require(type(report['validator_runtime_fingerprint']) is dict, 'Missing Host validation runtime')
    digest_value(report['validator_runtime_fingerprint'].get('application_build'))
    for check in report['checks']:
        require(check.get('passed') is True and type(check.get('execution')) is dict,
                'Method validation lacks a completed numerical execution')
        execution = check['execution']
        require(execution['program_sha256'] == source_digest and execution['input_sha256'] == check['input_sha256'],
                'Method execution identity differs from validation')
        for key in ('program_sha256', 'input_sha256', 'stdout_sha256', 'stderr_sha256'):
            digest_value(execution[key])
        digest_value(check['result_sha256'])
        require(sha256(canonical_bytes(check['input'])).hexdigest() == check['input_sha256'] and
                sha256(canonical_bytes(check['result'])).hexdigest() == check['result_sha256'],
                'Stored method calibration evidence changed')
        if report['family'] == 'c2':
            check_c2(check['input'], check['result'], known_ground=check['expected_ground'])
        else:
            check_normalization(check['input'], check['result'])
        require(type(execution['libraries']) is dict and bool(execution['python']) and bool(execution['prefix']),
                'Method validation lacks its scientific runtime identity')


def assess_method(program, family, python, *, cancel_event=None):
    """Execute finite independent cases in the canonical scientific sandbox."""
    from copy import deepcopy
    import math
    from pathlib import Path
    import random
    import secrets
    from lqcd_agent.analysis.generated_diagnostics import check_c2, check_normalization
    from lqcd_agent.code_agent.execution import execute_candidate, interpreter_identity
    from lqcd_agent.control.strict_json import canonical_bytes
    from lqcd_agent.research_evaluation import calibration
    from lqcd_agent.control.pause import runtime_fingerprint

    require(family in ('c2', 'normalization'), 'No independent calibration for this method contract')
    require(type(program) is bytes and 0 < len(program) <= 128*1024, 'Method source exceeds 128 KiB')
    python = Path(python)
    require(python.is_absolute() and python.is_file(), 'Use an existing absolute scientific interpreter')
    runtime = interpreter_identity(python)
    rng = random.Random(secrets.randbits(128))
    payload = calibration(family)
    if family == 'c2':
        # New hidden ground energies reject programs that merely print a fixture answer.
        ground = rng.uniform(.18, .23)
        def configurations(energy):
            excited = energy + rng.uniform(.35, .5)
            mean = [1.2*(math.exp(-energy*t)+math.exp(-energy*(64-t))) +
                    .8*(math.exp(-excited*t)+math.exp(-excited*(64-t))) for t in range(64)]
            return [[value+rng.gauss(0, .00002) for value in mean] for _ in range(96)]
        payload.update(configurations=configurations(ground), configuration_ids=list(range(96)),
                       binsize=4, bootstrap_samples=24, tmins=[4, 6])
        higher_ground = rng.uniform(.32, .38)
        higher = {**deepcopy(payload), 'configurations': configurations(higher_ground)}
        fixed = deepcopy(payload)
        fixed.update(fixed_ground_energy=True, ground_energy_at_rest=rng.uniform(.13, .2), pz=1)
        fixed['configurations'] = configurations(math.hypot(fixed['ground_energy_at_rest'], 2*math.pi/64))
        cases = [('two_state_ground_low', payload, ground),
                 ('two_state_ground_high', higher, higher_ground), ('fixed_ground', fixed, None)]
    else:
        for row in payload['records']:
            row.update(real=rng.uniform(.5, 3), imag=rng.uniform(-2, 2))
        failed = deepcopy(payload)
        row = next(r for r in failed['records'] if (r['pz'], r['bT']) ==
                   (failed['target_pz'], failed['target_bT']))
        row.update(success=False, real=None, imag=None)
        missing = deepcopy(payload)
        missing['records'] = [r for r in missing['records'] if (r['pz'], r['bT'], r['bz']) !=
                              (0, missing['target_bT'], 0)]
        cases = [('paired_complex', payload, None), ('failed_replica', failed, None),
                 ('missing_reference', missing, None)]
    source_digest = sha256(program).hexdigest()
    checks = []
    for name, value, ground in cases:
        check = {'name': name, 'passed': False, 'input': value, 'expected_ground': ground,
                 'input_sha256': sha256(canonical_bytes(value)).hexdigest()}
        checks.append(check)
        if cancel_event is not None and cancel_event.is_set():
            check['not_run'] = 'cancelled'
            continue
        try:
            result, execution = execute_candidate(program, value, python, timeout=30, expected_runtime=runtime)
            check.update(execution=execution, result=result, result_sha256=sha256(canonical_bytes(result)).hexdigest())
            if family == 'c2':
                check_c2(value, result, known_ground=ground)
            else:
                check_normalization(value, result)
            check['passed'] = True
        except Exception as error:
            check.update(error_type=type(error).__name__, reason=str(error)[:1500])
    return ExecutedMethodValidation(canonical_bytes({'kind': 'host_executed_method_validation',
        'source_sha256': source_digest, 'family': family,
        'validator_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'validator_runtime_fingerprint': runtime_fingerprint(), 'checks': checks,
        'passed': all(r['passed'] for r in checks),
        'limitations': ['Finite independent synthetic calibration and output-contract checks only.',
                        'Applicability, physical models, units and original resampling provenance remain scoped review judgments.']}), _EXECUTED)
