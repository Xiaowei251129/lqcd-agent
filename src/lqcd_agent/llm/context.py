"""Content-addressed context evidence, with role views and verified local reads."""
from pathlib import Path
from hashlib import sha256
from lqcd_agent.control.strict_json import canonical_bytes, digest_value, loads, require
from lqcd_agent.control.coordinator import publish_exact, read_regular


def context_reference(sources):
    return {'sections': sorted(sources), 'sha256': sha256(canonical_bytes(sources)).hexdigest()}


def planner_inventory_view(inventory):
    if inventory is None:
        return None
    view = {key: value for key, value in inventory.items()
            if key not in ('schema_version', 'repo_root', 'allowed_files')}
    if 'analysis_programs' in view:
        view['analysis_programs'] = [{key: value for key, value in program.items()
            if key not in ('callable_path', 'csv_inputs', 'optional_csv_inputs', 'text_columns')}
            for program in view['analysis_programs']]
    return view


def review_context_view(sources):
    view = {key: value for key, value in sources.items() if key not in ('run_result', 'method_plan')}
    for name, fields in (
        ('run_result', ('run_success', 'failure_type')),
        ('method_plan', ('physics_goal', 'target_observables', 'method_steps', 'code_needed', 'implementation_gaps')),
    ):
        source = sources[name]
        summary = {'exists': source is not None, 'path': name}
        if source is not None:
            summary.update({key: source[key] for key in ('status', 'warnings', 'errors', *fields) if key in source})
        view[name + '_summary'] = summary
    evidence = view.get('review_evidence')
    if evidence is not None:
        # Aggregate evidence retains every finding and warning; section lists are duplicates.
        view['review_evidence'] = {key: ({field: value[field] for field in ('status', 'summary') if field in value}
            if key.endswith('_diagnostics') else value) for key, value in evidence.items()}
    return view


def persist_context(output_dir, request):
    root = Path(output_dir).resolve() / 'context_evidence'
    require(root == root.resolve(), 'Context evidence directory cannot be redirected')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    reference = context_reference(request.context_sources)
    publish_exact(root / (reference['sha256'] + '.json'), canonical_bytes(request.context_sources))


def read_context_evidence(output_dir, reference, section, *, fields=None):
    """Read only the referenced digest, optionally selecting named top-level fields."""
    require(type(reference) is dict and set(reference) == {'sections', 'sha256'}, 'Invalid context reference')
    digest_value(reference['sha256'])
    root = Path(output_dir).resolve() / 'context_evidence'
    require(root == root.resolve(), 'Context evidence directory cannot be redirected')
    raw = read_regular(root / (reference['sha256'] + '.json'))
    require(sha256(raw).hexdigest() == reference['sha256'], 'Context evidence changed')
    sources = loads(raw)
    require(type(sources) is dict and sorted(sources) == reference['sections'] and section in sources,
            'Unknown context section')
    value = sources[section]
    if fields is None:
        return value
    require(type(value) is dict and type(fields) in (list, tuple) and
            all(type(field) is str and field in value for field in fields), 'Unknown context field')
    return {field: value[field] for field in fields}
