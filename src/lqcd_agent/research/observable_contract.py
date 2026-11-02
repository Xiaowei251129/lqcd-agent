"""Explicit replica-observable contract, independent of any particular fit model."""
import math
from lqcd_agent.control.strict_json import closed, number, require, text


CONTRACT = '''For result_kind=replica_observables the frozen JSON input must contain replica_groups
([{id, sample_ids, method, provenance}], method bootstrap or jackknife) and observable_contracts
([{id, definition, unit, group, kinematics}]). Return exactly {status, observables, assumptions, limitations}.
status is ok, partial or needs_more_info. Each observable is exactly {id, samples, mean, error},
samples contains exactly one {sample_id, value} for EVERY original group sample_id; null means failure.
Keep failed samples explicit. For >=2 valid bootstrap samples report their mean and sample std(ddof=1).
For jackknife report their mean and sqrt((N-1)/N * sum((x-mean)^2)); all samples must be valid.
If insufficient or failed jackknife samples prevent an estimate, mean/error must both be null.
Do not invent data, alter replica identities, infer pairing from matching integers, or claim independent
physical validation from passing arithmetic checks. assumptions and limitations are lists of strings.'''


def check_observables(payload, result):
    """Check definitions, accounting and uncertainty arithmetic, not physics suitability."""
    closed(result, ('status', 'observables', 'assumptions', 'limitations'))
    require(result['status'] in ('ok', 'partial', 'needs_more_info'), 'Invalid observable status')
    for field in ('assumptions', 'limitations'):
        require(type(result[field]) is list and all(type(s) is str and s for s in result[field]), 'Invalid '+field)
    groups = {}
    require(type(payload.get('replica_groups')) is list and payload['replica_groups'], 'Missing replica groups')
    for group in payload['replica_groups']:
        closed(group, ('id', 'sample_ids', 'method', 'provenance'))
        text(group['id']); text(group['provenance'])
        require(group['id'] not in groups and group['method'] in ('bootstrap', 'jackknife'), 'Invalid replica group')
        ids = group['sample_ids']
        require(type(ids) is list and len(ids) >= 2 and all(type(i) in (str, int) for i in ids) and
                len({(type(i), i) for i in ids}) == len(ids), 'Invalid original replica identities')
        groups[group['id']] = group
    contracts = {}
    require(type(payload.get('observable_contracts')) is list and payload['observable_contracts'], 'Missing observable definitions')
    for contract in payload['observable_contracts']:
        closed(contract, ('id', 'definition', 'unit', 'group', 'kinematics'))
        for field in ('id', 'definition', 'unit', 'group'):
            text(contract[field])
        require(type(contract['kinematics']) is dict and contract['group'] in groups and
                contract['id'] not in contracts, 'Invalid physical observable definition')
        contracts[contract['id']] = contract
    require(type(result['observables']) is list, 'Missing observable outputs')
    if result['status'] == 'needs_more_info':
        require(result['observables'] == [] and result['limitations'], 'Missing inputs must not fabricate observables')
        return {'valid_observables': 0, 'failed_replicas': 0, 'groups': groups, 'contracts': contracts}
    actual = {}
    failed = 0
    for observable in result['observables']:
        closed(observable, ('id', 'samples', 'mean', 'error'))
        name = observable['id']
        require(name in contracts and name not in actual, 'Unknown or duplicated observable')
        actual[name] = observable
        group = groups[contracts[name]['group']]
        require(type(observable['samples']) is list, 'Missing replica values')
        values, ids = [], []
        for sample in observable['samples']:
            closed(sample, ('sample_id', 'value'))
            require(type(sample['sample_id']) in (str, int), 'Invalid sample identity type')
            ids.append((type(sample['sample_id']), sample['sample_id']))
            if sample['value'] is not None:
                require(type(sample['value']) in (int, float) and math.isfinite(sample['value']), 'Invalid replica value')
                values.append(sample['value'])
        require(len(ids) == len(set(ids)) and set(ids) == {(type(i), i) for i in group['sample_ids']},
                'Observable dropped, added, duplicated or renumbered replicas')
        missing = len(ids)-len(values)
        failed += missing
        if len(values) < 2 or group['method'] == 'jackknife' and missing:
            require(observable['mean'] is None and observable['error'] is None,
                    'Insufficient replicas must not produce an uncertainty')
            continue
        mean = sum(values)/len(values)
        variance_sum = sum((x-mean)**2 for x in values)
        variance = variance_sum/(len(values)-1) if group['method'] == 'bootstrap' else (len(values)-1)/len(values)*variance_sum
        for field, expected in (('mean', mean), ('error', math.sqrt(variance))):
            number(observable[field], minimum=-(2**53-1))
            require(math.isclose(observable[field], expected, rel_tol=1e-6, abs_tol=1e-10),
                    'Observable '+field+' differs from independent replica arithmetic')
    require(actual.keys() == contracts.keys(), 'Observable contract is incomplete')
    require(result['status'] != 'ok' or failed == 0, 'Failed replicas require partial status')
    return {'valid_observables': len(actual), 'failed_replicas': failed, 'groups': groups, 'contracts': contracts}
