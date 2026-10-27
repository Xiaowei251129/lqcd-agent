"""One schema for model proposals; Host identity is added only after validation."""
from datetime import datetime, timezone
import math


def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def role_schema(role):
    from lqcd_agent.analysis_programs.registry import PROGRAMS
    strings = {'type': 'array', 'items': {'type': 'string'}}
    records = {'type': 'array', 'items': {'$ref': '#/$defs/record'}}
    properties = {'status': {'type': 'string', 'enum': ['success', 'failed', 'pending', 'needs_more_info']},
                  'summary': {'type': 'string'}, 'warnings': records, 'errors': records}
    if role == 'method_plan':
        properties.update(physics_goal={'type': 'string'}, target_observables=strings, method_steps=strings,
            required_inputs=strings, implementation_gaps=strings,
            selected_analysis_programs={'type': 'array', 'items': {'type': 'string', 'enum': [p.name for p in PROGRAMS]}},
            code_needed={'type': 'boolean'}, coder_task_summary={'type': ['string', 'null']})
    elif role == 'scientific_review_report':
        properties.update({name: {'$ref': '#/$defs/diagnostics'}
                           for name in ('correlator_diagnostics', 'fit_diagnostics', 'matrix_element_diagnostics')})
        properties.update(findings=records, evidence=records, recommended_checks=strings,
                          confidence={'type': 'string', 'enum': ['high', 'medium', 'low']})
    else:
        raise ValueError('Unsupported model role')
    record = object_schema({name: {'type': ['string', 'null']} for name in
                            ('code', 'message', 'section', 'severity', 'path', 'field')})
    record['properties'].update(value={'anyOf': [{'type': ['string', 'number', 'boolean', 'null']}, strings]},
                                decision_coordinator_flag={'type': ['boolean', 'null']})
    record['required'] = list(record['properties'])
    schema = object_schema(properties)
    schema['$defs'] = {'record': record}
    if role == 'scientific_review_report':
        schema['$defs']['diagnostics'] = object_schema({'status': {'type': 'string'}, 'summary': {'type': 'string'},
            'evidence': records, 'findings': records, 'warnings': records, 'recommended_checks': strings})
    return {'name': role, 'strict': True, 'schema': schema}


def validate_proposal(payload, role):
    """Validate exactly the JSON Schema subset emitted above, including mock providers."""
    root = role_schema(role)['schema']
    types = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'null': type(None)}

    def check(value, schema, path):
        if '$ref' in schema:
            return check(value, root['$defs'][schema['$ref'].rsplit('/', 1)[1]], path)
        if 'anyOf' in schema:
            return [] if any(not check(value, branch, path) for branch in schema['anyOf']) else [path + ': invalid value']
        kinds = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any((type(value) is int or (type(value) is float and math.isfinite(value))) if kind == 'number'
                   else type(value) is types[kind] for kind in kinds):
            return [path + ': invalid type']
        if 'enum' in schema and value not in schema['enum']:
            return [path + ': unknown value']
        errors = []
        if type(value) is dict:
            if set(value) != set(schema['properties']):
                errors.append(path + ': missing or unexpected fields')
            for name in value.keys() & schema['properties'].keys():
                errors.extend(check(value[name], schema['properties'][name], path + '.' + name))
        elif type(value) is list:
            for index, item in enumerate(value):
                errors.extend(check(item, schema['items'], f'{path}[{index}]'))
        return errors

    return check(payload, root, '$')


def artifact_payload(payload, *, run_id, case_id, producer):
    return {**payload, 'schema_version': '0.1', 'run_id': run_id, 'case_id': case_id,
            'producer': producer, 'created_at': datetime.now(timezone.utc).isoformat()}
