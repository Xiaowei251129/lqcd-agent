"""Source-bound trace projection; never a runtime hash or mutation authority.

Raw canonical objects are checked before any projection. Only Execution clock
literals and paths below proven Run roots are projected away. Other content,
including identities and material digests, remains in the semantic hash.
"""
from collections import defaultdict
from pathlib import Path

from lqcd_agent.control.execution import replay
from lqcd_agent.control.projections import checkpoint_manifest
from lqcd_agent.control.strict_json import digest as raw_digest

from .session import validate_digests
from .strict_json import Invalid, keys, require, text


KINDS = {"execution_0_4", "canonical_json", "checkpoint_manifest"}
HISTORICAL_KINDS = {"historical_execution_0_3", "historical_checkpoint_manifest_0_3"}
REFERENCE_KINDS = {
    "previous_execution_head": "execution_0_4", "execution_head": "execution_0_4",
    "previous_artifact_head": "canonical_json", "artifact_head": "canonical_json",
    "checkpoint_head": "checkpoint_manifest", "state_digest": "canonical_json",
    "checkpoint_digest": "canonical_json",
}
EVENT_HEADS = {"execution_head": "execution_0_4", "artifact_head": "canonical_json",
               "checkpoint_head": "checkpoint_manifest"}
SEMANTIC_PREFIX = "semantic_sha256:"


def sha_value(value, obj):
    require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), obj, "sha256")


def source_digest(kind, value):
    if kind in ("checkpoint_manifest", "historical_checkpoint_manifest_0_3"):
        return raw_digest({k: v for k, v in value.items() if k != "checkpoint_head"})
    return raw_digest(value)


def reference_paths(value, *, kind, prefix=(), version="0.2"):
    """Enumerate structural head references, not arbitrary hexadecimal strings."""
    result = []
    if version == "0.4" and kind == "execution_0_4" and not prefix and type(value) is dict:
        if value.get("record_type") == "pause" and value.get("event") == "pause_prepared" and value.get("reason") == "external_result":
            head = value["proof"]["dependency"]["reservation_digest"]
            sha_value(head, "reservation_reference")
            result.append((("proof", "dependency", "reservation_digest"), head))
    if type(value) is dict:
        for key in sorted(value):
            item = value[key]
            path = prefix + (key,)
            derived = version in ("0.3", "0.4") and key in ("lineage_snapshot_digest", "source_revision_cas", "request_digest", "source_head_digest")
            if (key in REFERENCE_KINDS or derived) and item is not None:
                if kind in ("checkpoint_manifest", "historical_checkpoint_manifest_0_3") and path == ("checkpoint_head",):
                    continue
                sha_value(item, "source_reference")
                result.append((path, item))
            else:
                result.extend(reference_paths(item, kind=kind, prefix=path, version=version))
    elif type(value) is list:
        for index, item in enumerate(value):
            result.extend(reference_paths(item, kind=kind, prefix=prefix + (index,), version=version))
    return result


def source_object(kind, value, *, version="0.2"):
    """Capture content only. Validation and eligibility happen on both consumers."""
    require(kind in (KINDS | HISTORICAL_KINDS if version in ("0.3", "0.4") else KINDS) and type(value) is dict, "source", "kind")
    return {"kind": kind, "sha256": source_digest(kind, value), "value": value,
            "references": [{"path": list(path), "sha256": head}
                           for path, head in reference_paths(value, kind=kind, version=version)]}


def _binding(actual, expected):
    keys(actual, {"invocation_token", "digests"}, "trace_binding")
    text(actual["invocation_token"], "trace_binding", "invocation_token")
    validate_digests(actual["digests"])
    require(expected is not None, "trace_binding", "trusted_session_required", "invalid_evidence")
    require(actual["invocation_token"] == expected["invocation_token"] and actual["digests"] == expected["digests"],
            "trace_binding", "session", "invalid_evidence")


def _sources(proof, *, version="0.2"):
    require(type(proof["objects"]) is list and bool(proof["objects"]), "trace_proof", "objects")
    sources = {}
    executions = defaultdict(list)
    for row in proof["objects"]:
        keys(row, {"kind", "sha256", "value", "references"}, "source")
        require(type(row["kind"]) is str and row["kind"] in (KINDS | HISTORICAL_KINDS if version in ("0.3", "0.4") else KINDS) and type(row["value"]) is dict,
                "source", "kind")
        sha_value(row["sha256"], "source")
        require(row["sha256"] not in sources, "source", "duplicate")
        require(source_digest(row["kind"], row["value"]) == row["sha256"], "source", "raw_digest", "invalid_evidence")
        if row["kind"] in ("checkpoint_manifest", "historical_checkpoint_manifest_0_3"):
            require(row["value"].get("checkpoint_head") == row["sha256"], "source", "checkpoint_self_head")
        expected_refs = [{"path": list(path), "sha256": head}
                         for path, head in reference_paths(row["value"], kind=row["kind"], version=version)]
        require(row["references"] == expected_refs, "source", "exact_references", "invalid_evidence")
        sources[row["sha256"]] = row
        if row["kind"] in ("execution_0_4", "historical_execution_0_3"):
            value = row["value"]
            require(type(value.get("case_id")) is str and type(value.get("run_id")) is str, "source", "run_identity")
            executions[value["case_id"], value["run_id"]].append(value)
    require(bool(executions), "trace_proof", "execution_sources")
    for identity, records in executions.items():
        require(all(type(row.get("event_index")) is int for row in records), "source", "event_index")
        records.sort(key=lambda row: row["event_index"])
        if records[0].get("schema_version") == "0.3" and version in ("0.3", "0.4"):
            require(all(sources[raw_digest(r)]["kind"] == "historical_execution_0_3" for r in records), "historical", "record_kind")
            _historical_execution(records)
        else:
            require(all(sources[raw_digest(r)]["kind"] == "execution_0_4" for r in records), "source", "execution_kind")
            replay(records)
    historical_refs = _historical_reference_contexts(sources, executions) if version in ("0.3", "0.4") else set()
    for row in sources.values():
        for ref in row["references"]:
            target = sources.get(ref["sha256"])
            require(target is not None, "source", "missing_reference", "invalid_evidence")
            expected_kind = REFERENCE_KINDS.get(ref["path"][-1], "canonical_json")
            if version == "0.4" and row["kind"] == "execution_0_4" and ref["path"] == ["proof", "dependency", "reservation_digest"]:
                expected_kind = "execution_0_4"
                reservation, pause = target["value"], row["value"]
                require(reservation.get("record_type") == "budget" and reservation.get("event") == "resource_reserved",
                        "reservation_reference", "record_kind", "invalid_evidence")
                require(all(reservation.get(k) == pause.get(k) for k in ("case_id", "run_id")) and
                        reservation["event_index"] < pause["event_index"] and
                        reservation["payload"]["attempt_id"] == pause["target_attempt_id"] and
                        reservation["payload"]["producer_operation_id"] == pause["proof"]["dependency"]["producer_operation_id"],
                        "reservation_reference", "identity", "invalid_evidence")
            if version in ("0.3", "0.4") and ref["path"][-1] == "source_head_digest":
                expected_kind = "execution_0_4"
            if (row["sha256"], tuple(ref["path"])) in historical_refs:
                expected_kind = {"execution_0_4": "historical_execution_0_3", "checkpoint_manifest": "historical_checkpoint_manifest_0_3"}.get(expected_kind, expected_kind)
            require(target["kind"] == expected_kind, "source", "reference_kind", "invalid_evidence")
            if row["kind"] == "execution_0_4" and ref["path"] == ["previous_execution_head"]:
                before, after = target["value"], row["value"]
                require((before["run_id"], before["case_id"], before["event_index"] + 1) ==
                        (after["run_id"], after["case_id"], after["event_index"]), "source", "execution_chain")
    return sources, executions


def _roots(proof, executions):
    require(type(proof["output_roots"]) is list, "trace_proof", "output_roots")
    roots = {}
    for row in proof["output_roots"]:
        keys(row, {"case_id", "run_id", "path"}, "trace_root")
        for name in row:
            text(row[name], "trace_root", name)
        identity = row["case_id"], row["run_id"]
        require(identity in executions and identity not in roots, "trace_root", "identity")
        path = Path(row["path"])
        require(path.is_absolute() and str(path) == row["path"] and path.resolve() == path and path.is_dir(),
                "trace_root", "canonical_path")
        temporary = Path("/private/tmp").resolve()
        require(path.is_relative_to(temporary) and path != temporary and
                path.relative_to(temporary).parts[0].startswith("lqcd-agent-"), "trace_root", "temporary_containment")
        require(executions[identity][0]["canonical_output_root"] == str(path), "trace_root", "run_binding")
        require(all(not path.is_relative_to(other) and not other.is_relative_to(path) for other in roots.values()),
                "trace_root", "overlapping_roots")
        roots[identity] = path
    require(set(roots) == set(executions), "trace_root", "complete_bindings")
    return roots


def _checkpoint_sources(sources, executions):
    for row in sources.values():
        if row["kind"] != "checkpoint_manifest":
            continue
        manifest = row["value"]
        identity = manifest.get("case_id"), manifest.get("run_id")
        require(identity in executions, "checkpoint_proof", "run_identity")
        count = manifest.get("execution_event_index")
        require(type(count) is int and 1 <= count <= len(executions[identity]), "checkpoint_proof", "execution_index")
        execution = replay(executions[identity][:count])
        expected = checkpoint_manifest(execution, artifact_head=manifest.get("artifact_head"),
                                       artifact_event_index=manifest.get("artifact_event_index"),
                                       checkpoint_id=manifest.get("checkpoint_id"), checkpoint_digest=manifest.get("checkpoint_digest"),
                                       state_digest=manifest.get("state_digest"))
        require(expected.value == manifest, "checkpoint_proof", "manifest", "invalid_evidence")
        state = sources[manifest["state_digest"]]["value"]
        for field in ("case_id", "run_id", "execution_head", "execution_event_index", "artifact_head", "artifact_event_index"):
            require(state.get(field) == manifest[field], "checkpoint_proof", field, "invalid_evidence")


def project(events, proof, binding, *, version="0.2"):
    """Validate raw provenance before computing a versioned semantic digest DAG."""
    try:
        keys(proof, {"schema_version", "binding", "objects", "output_roots"}, "trace_proof")
        require(proof["schema_version"] == "0.1", "trace_proof", "schema_version")
        _binding(proof["binding"], binding)
        sources, executions = _sources(proof, version=version)
        roots = _roots(proof, executions)
        _checkpoint_sources(sources, executions)
        if version in ("0.3", "0.4"):
            _historical_source_files(sources, executions, roots)
        return _project_events(events, sources, roots, version=version)
    except Invalid:
        raise
    except (ValueError, TypeError, KeyError, IndexError, OSError, RecursionError) as error:
        raise Invalid("trace_proof", "source_validation", "invalid_evidence") from error


def _project_events(events, sources, roots, *, version="0.2"):
    visiting, visited, projected = set(), set(), {}

    def project_source(head):
        require(head in sources, "trace_proof", "event_source", "invalid_evidence")
        if head in projected:
            visited.add(head)
            return projected[head]
        require(head not in visiting, "trace_proof", "cyclic_reference", "invalid_evidence")
        visiting.add(head)
        row = sources[head]
        refs = {tuple(ref["path"]): ref["sha256"] for ref in row["references"]}

        def encode(value, path=()):
            if path in refs:
                return ["digest_reference", project_source(refs[path])]
            if row["kind"] in ("checkpoint_manifest", "historical_checkpoint_manifest_0_3") and path == ("checkpoint_head",):
                return ["self_digest"]
            if row["kind"] in ("execution_0_4", "historical_execution_0_3") and path in (("created_at",), ("committed_at",)):
                return ["validated_clock", value["source"]]
            if type(value) is dict:
                return ["object", [[key, encode(value[key], path + (key,))] for key in sorted(value)]]
            if type(value) is list:
                return ["array", [encode(item, path + (index,)) for index, item in enumerate(value)]]
            if type(value) is str:
                for identity, root in roots.items():
                    if value == str(root) or value.startswith(str(root) + "/"):
                        physical = Path(value)
                        require(str(physical) == value and physical.resolve() == physical and physical.is_relative_to(root),
                                "trace_proof", "path_escape", "invalid_evidence")
                        return ["physical_path", list(identity), physical.relative_to(root).as_posix()]
            return ["literal", value]

        value = {"projection_version": version, "source_kind": row["kind"], "content": encode(row["value"])}
        result = SEMANTIC_PREFIX + raw_digest(value)
        projected[head] = result
        visiting.remove(head)
        visited.add(head)
        return result

    result = []
    for event in events:
        value = {key: item for key, item in event.items() if key != "ephemeral"}
        for field, kind in EVENT_HEADS.items():
            head = value[field]
            if head is not None:
                accepted = {kind}
                if version in ("0.3", "0.4"):
                    accepted.add({"execution_0_4": "historical_execution_0_3", "checkpoint_manifest": "historical_checkpoint_manifest_0_3"}.get(kind, kind))
                require(head in sources and sources[head]["kind"] in accepted, "trace_proof", field, "invalid_evidence")
                source = sources[head]["value"]
                if event["run_id"] is not None and "run_id" in source:
                    require(event["run_id"] == source["run_id"], "trace_proof", "event_run_binding", "invalid_evidence")
                value[field] = project_source(head)
        for field in ("result_digest", "manifest_digest", "binding_digest"):
            if value[field] in sources:
                value[field] = project_source(value[field])
        result.append(value)
    require(visited == set(sources), "trace_proof", "orphan_sources", "invalid_evidence")
    return result


def _historical_execution(records):
    """Validate the archived 0.3 record format without using the 0.4 replayer."""
    import math
    from lqcd_agent.control.children import validate_source_fingerprint
    base = {'schema_version', 'record_type', 'event', 'case_id', 'run_id', 'event_index',
            'previous_execution_head', 'artifact_head', 'artifact_event_index', 'created_at'}
    fields = {
        ('run', 'created'): {'parent_run_id', 'creation_reason', 'status', 'canonical_output_root', 'checkpoint_thread_id',
                            'runtime_fingerprint', 'root_goal_reference', 'input_snapshot_reference'},
        ('cycle', 'created'): {'cycle_id', 'cycle_index', 'parent_cycle_id', 'trigger_reason', 'created_by_attempt_id', 'status'},
        ('attempt', 'scheduled'): {'attempt_id', 'attempt_index', 'cycle_id', 'cycle_index', 'attempt_kind', 'node_name', 'status', 'inbound_transition_id'},
        ('attempt', 'started'): {'attempt_id', 'status'},
        ('attempt', 'finished'): {'attempt_id', 'status', 'error'},
        ('transition', 'committed'): {'transition_id', 'transition_index', 'source', 'source_attempt_id', 'target_attempt_id', 'target_node', 'target_cycle_id', 'status'},
        ('pause', 'pause_prepared'): {'pause_id', 'pause_index', 'status', 'reason', 'runtime_fingerprint'},
        ('pause', 'pause_opened'): {'pause_id', 'pause_index', 'status', 'reason', 'runtime_fingerprint'},
    }
    root = records[0]
    identity = {key: root[key] for key in ('case_id', 'run_id')}
    for name, value in identity.items():
        text(value, 'historical', name)
    run_status, last_time, prior = 'initializing', None, None
    cycles, attempts, transitions, pauses = {}, {}, {}, {}
    latest_pause = None
    for position, row in enumerate(records, 1):
        require(row['schema_version'] == '0.3' and all(row[k] == v for k, v in identity.items()) and
                type(row['event_index']) is int and row['event_index'] == position and row['previous_execution_head'] == prior,
                'historical', 'execution_chain', 'invalid_evidence')
        key = row['record_type'], row['event']
        expected = fields.get(key)
        if key == ('run_lifecycle', 'transitioned'):
            expected = {'from_status', 'to_status', 'operation_id'} | ({'pause_id'} if 'pause_id' in row else set())
        require(expected is not None, 'historical', 'unsupported_record')
        keys(row, base | expected, 'historical_record')
        stamp = row['created_at']
        keys(stamp, {'source', 'wall_seconds', 'monotonic_seconds'}, 'historical_clock')
        text(stamp['source'], 'historical_clock', 'source')
        require(all(type(stamp[k]) in (int, float) and math.isfinite(stamp[k]) and stamp[k] >= 0
                    for k in ('wall_seconds', 'monotonic_seconds')), 'historical_clock', 'number')
        require(last_time is None or stamp['source'] == last_time['source'] and
                all(stamp[k] >= last_time[k] for k in ('wall_seconds', 'monotonic_seconds')), 'historical_clock', 'regression')
        last_time = stamp
        # This archived encoding predates the artifact cross-head extension.
        # Other encodings require their own validator, never a schema relabel.
        require(row['artifact_head'] is None and type(row['artifact_event_index']) is int and row['artifact_event_index'] == 0,
                'historical', 'unsupported_artifact_encoding')
        if key == ('run', 'created'):
            require(position == 1 and row['creation_reason'] == 'root' and row['parent_run_id'] is None and row['status'] == 'initializing' and
                    row['checkpoint_thread_id'] == row['case_id'] + ':' + row['run_id'], 'historical', 'root')
            validate_source_fingerprint(row['runtime_fingerprint'], '0.3', 'fork_of')
        elif key == ('cycle', 'created'):
            require(run_status == 'initializing' and type(row['cycle_index']) is int and row['cycle_index'] == len(cycles) + 1 and row['cycle_id'] not in cycles and
                    row['status'] == 'active' and (row['trigger_reason'], row['parent_cycle_id'], row['created_by_attempt_id']) == ('initial', None, None) and
                    not cycles, 'historical', 'cycle')
            cycles[row['cycle_id']] = row
        elif key == ('attempt', 'scheduled'):
            require(run_status == 'initializing' and not attempts and type(row['attempt_index']) is int and row['attempt_index'] == 1 and row['attempt_id'] not in attempts and
                    row['cycle_id'] in cycles and row['cycle_index'] == cycles[row['cycle_id']]['cycle_index'] and
                    row['attempt_kind'] == row['node_name'] == 'method_planner' and row['status'] == 'scheduled', 'historical', 'attempt')
            attempts[row['attempt_id']] = dict(row)
        elif key == ('transition', 'committed'):
            target = attempts.get(row['target_attempt_id'])
            require(run_status == 'initializing' and type(row['transition_index']) is int and row['transition_index'] == len(transitions) + 1 and row['transition_id'] not in transitions and
                    target is not None and target['inbound_transition_id'] == row['transition_id'] and target['cycle_id'] == row['target_cycle_id'] and
                    target['node_name'] == row['target_node'] and row['source'] == 'START' and row['source_attempt_id'] is None and not transitions and
                    row['status'] == 'committed', 'historical', 'transition')
            transitions[row['transition_id']] = row
        elif key == ('attempt', 'started'):
            target = attempts.get(row['attempt_id'])
            require(target is not None and target['status'] == 'scheduled' and row['status'] == 'running' and run_status == 'running' and
                    target['inbound_transition_id'] in transitions, 'historical', 'start_authority')
            target['status'] = row['status']
        elif key == ('attempt', 'finished'):
            target = attempts.get(row['attempt_id'])
            require(target is not None and target['status'] == 'running' and row['status'] in ('failed', 'succeeded', 'pending'), 'historical', 'attempt_finish')
            if row['status'] == 'failed':
                keys(row['error'], {'type', 'message'}, 'historical_error')
                for name in row['error']:
                    text(row['error'][name], 'historical_error', name)
            else:
                require(row['error'] is None, 'historical', 'unexpected_error')
            target['status'] = row['status']
        elif key[0] == 'pause':
            require(row['reason'] == 'recovery_decision' and row['runtime_fingerprint'] == root['runtime_fingerprint'], 'historical', 'pause_identity')
            if key[1] == 'pause_prepared':
                require(run_status == 'running' and row['status'] == 'prepared' and row['pause_id'] not in pauses and
                        type(row['pause_index']) is int and row['pause_index'] == len(pauses) + 1 and
                        bool(attempts) and all(a['status'] == 'failed' for a in attempts.values()), 'historical', 'pause_prepare')
                pauses[row['pause_id']] = row
            else:
                prepared = pauses.get(row['pause_id'])
                require(prepared is not None and prepared['pause_index'] == row['pause_index'] and prepared['status'] == 'prepared' and
                        row['status'] == 'opened' and run_status == 'paused' and records[position - 2]['record_type'] == 'run_lifecycle' and
                        records[position - 2].get('pause_id') == row['pause_id'], 'historical', 'pause_open')
                pauses[row['pause_id']] = row
            latest_pause = row
        else:
            edge = row['from_status'], row['to_status']
            require(row['from_status'] == run_status and edge in (('initializing', 'running'), ('running', 'paused'),
                    ('running', 'failed'), ('running', 'halted'), ('running', 'completed')), 'historical', 'lifecycle')
            text(row['operation_id'], 'historical', 'operation_id')
            if row['to_status'] == 'paused':
                require(latest_pause is not None and latest_pause['status'] == 'prepared' and row.get('pause_id') == latest_pause['pause_id'],
                        'historical', 'pause_lifecycle')
            if row['from_status'] == 'initializing':
                require(len(transitions) == len(attempts) == len(cycles) == 1, 'historical', 'bootstrap_closure')
            run_status = row['to_status']
        prior = raw_digest(row)
    require(run_status in ('paused', 'failed', 'halted', 'completed'), 'historical', 'fork_status')
    active = None
    if run_status == 'paused':
        require(latest_pause is not None and latest_pause['status'] == 'opened' and records[-1] == latest_pause, 'historical', 'stable_pause')
        active = {'pause_id': latest_pause['pause_id'], 'status': 'opened'}
    else:
        require(records[-1]['record_type'] == 'run_lifecycle' and bool(attempts) and
                all(a['status'] in ('failed', 'succeeded', 'pending') for a in attempts.values()), 'historical', 'stable_terminal')
    return {**identity, 'checkpoint_thread_id': root['checkpoint_thread_id'], 'run_status': run_status,
            'execution_head': prior, 'execution_event_index': len(records), 'artifact_head': None, 'artifact_event_index': 0, 'active_pause': active}


def _historical_reference_contexts(sources, executions):
    """Permit historical links only from verified lineage and checkpoint roles."""
    contexts, approved = set(), []
    historical = {identity: rows for identity, rows in executions.items() if rows[0]['schema_version'] == '0.3'}
    linked = set()
    for row in sources.values():
        value = row['value']
        if row['kind'] != 'execution_0_4' or value.get('record_type') != 'lineage':
            continue
        proof = value['source_snapshot_proof']
        require(sources.get(value['lineage_snapshot_digest'], {}).get('value') == proof, 'lineage', 'snapshot_preimage', 'invalid_evidence')
        if proof['source_snapshot_kind'] != 'fork_head':
            continue
        cas = {'source_run_identity': proof['source_run_identity'], 'revision': proof['source_control_revision'], 'heads': proof['source_latest_heads']}
        require(sources.get(proof['source_revision_cas'], {}).get('value') == cas, 'lineage', 'revision_preimage', 'invalid_evidence')
        if proof['source_schema'] != '0.3':
            continue
        identity = tuple(proof['source_run_identity'][k] for k in ('case_id', 'run_id'))
        require(identity in historical, 'historical', 'source_identity', 'invalid_evidence')
        records = historical[identity]
        state = _historical_execution(records)
        require(proof['source_run_status'] == state['run_status'] and proof['source_latest_heads']['execution_head'] == state['execution_head'] and
                proof['source_latest_heads']['artifact_head'] == state['artifact_head'] and
                value['source_runtime_fingerprint'] == records[0]['runtime_fingerprint'], 'historical', 'lineage_binding', 'invalid_evidence')
        manifest_row = sources.get(proof['source_latest_heads']['checkpoint_head'])
        require(manifest_row is not None and manifest_row['kind'] == 'historical_checkpoint_manifest_0_3', 'historical', 'checkpoint_kind', 'invalid_evidence')
        manifest = manifest_row['value']
        keys(manifest, {'case_id', 'run_id', 'checkpoint_thread_id', 'checkpoint_id', 'checkpoint_digest', 'state_digest',
                        'execution_head', 'execution_event_index', 'artifact_head', 'artifact_event_index', 'checkpoint_head'}, 'historical_manifest')
        require(all(manifest[k] == state[k] for k in ('case_id', 'run_id', 'checkpoint_thread_id', 'execution_head', 'execution_event_index', 'artifact_head', 'artifact_event_index')) and
                raw_digest(state) == manifest['state_digest'], 'historical', 'checkpoint_state', 'invalid_evidence')
        require(sources[manifest['state_digest']]['value'] == state, 'historical', 'state_preimage', 'invalid_evidence')
        payload = sources[manifest['checkpoint_digest']]['value']
        keys(payload, {'v', 'id', 'ts', 'channel_values', 'channel_versions', 'versions_seen', 'pending_sends', 'updated_channels',
                       'lqcd_control_operation_id'}, 'historical_checkpoint')
        require(payload['v'] == 4 and type(payload['v']) is int and payload['id'] == manifest['checkpoint_id'] and
                payload['channel_values'] == {'control': state} and payload['channel_versions'] == {'control': 1} and
                payload['versions_seen'] == {} and payload['pending_sends'] == [] and payload['updated_channels'] == ['control'] and
                payload['lqcd_control_operation_id'] == next(r['operation_id'] for r in reversed(records) if r['record_type'] == 'run_lifecycle'),
                'historical', 'checkpoint_payload', 'invalid_evidence')
        text(payload['ts'], 'historical_checkpoint', 'ts')
        approved.extend((proof, cas, state, payload, manifest))
        for candidate in sources.values():
            request = candidate['value']
            if (candidate['kind'] == 'canonical_json' and request.get('operation_type') == 'fork_run' and
                    request.get('request', {}).get('source_run_locator') == proof['source_run_identity']):
                require(request['request']['source_head_digest'] == state['execution_head'], 'historical', 'request_source_head', 'invalid_evidence')
                approved.append(request)
        linked.add(identity)
    require(linked == set(historical), 'historical', 'unbound_source', 'invalid_evidence')
    for row in sources.values():
        def visit(value, path=()):
            if row['kind'] == 'historical_execution_0_3' and not path or any(value == allowed for allowed in approved):
                for ref_path, _ in reference_paths(value, kind=row['kind'], version='0.3'):
                    if ref_path[-1] in ('execution_head', 'previous_execution_head', 'checkpoint_head', 'source_head_digest'):
                        contexts.add((row['sha256'], path + ref_path))
                return
            if type(value) is dict:
                for key, child in value.items():
                    visit(child, path + (key,))
            elif type(value) is list:
                for index, child in enumerate(value):
                    visit(child, path + (index,))
        visit(row['value'])
    return contexts


def _historical_source_files(sources, executions, roots):
    """Check immutable archived bytes and the real child reservation read-only."""
    from hashlib import sha256
    import sqlite3
    from tempfile import TemporaryDirectory
    from lqcd_agent.control.checkpoints import verify_checkpoint
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import canonical_bytes, loads
    for identity, records in executions.items():
        if records[0]['schema_version'] != '0.3':
            continue
        root = roots[identity]
        def content(relative):
            from .strict_json import path_in
            path = path_in(root, relative)
            require(path.resolve() == path, 'historical_file', 'symlink')
            return read_regular(path)
        raw = content('execution_history.jsonl')
        require(raw == b''.join(canonical_bytes(row) + b'\n' for row in records), 'historical_file', 'execution_bytes', 'invalid_evidence')
        require(not (root / 'budget_policy.json').exists() and not (root / 'budget_policy.json').is_symlink(), 'historical_file', 'pre_a06')
        for name in ('root_goal', 'input_snapshot'):
            ref = records[0][name + '_reference']
            keys(ref, {'reference', 'sha256'}, 'historical_input')
            raw_input = content(ref['reference'])
            require(sha256(raw_input).hexdigest() == ref['sha256'] and type(loads(raw_input, canonical=False)) is dict,
                    'historical_file', 'root_input', 'invalid_evidence')
        index = loads(content('artifact_index.json'), canonical=False)
        keys(index, {'schema_version', 'case_id', 'run_id', 'execution_head', 'artifact_head', 'revision', 'current'}, 'historical_artifacts')
        require(index == {'schema_version': '0.1', 'case_id': identity[0], 'run_id': identity[1], 'execution_head': raw_digest(records[-1]),
                          'artifact_head': None, 'revision': 0, 'current': {}} and content('artifact_history.jsonl') == b'',
                'historical_file', 'artifact_snapshot', 'invalid_evidence')
        for row in sources.values():
            lineage = row['value']
            if row['kind'] != 'execution_0_4' or lineage.get('record_type') != 'lineage':
                continue
            proof = lineage['source_snapshot_proof']
            if proof.get('source_schema') != '0.3' or proof.get('source_snapshot_kind') != 'fork_head' or tuple(proof['source_run_identity'][k] for k in ('case_id', 'run_id')) != identity:
                continue
            require(proof['eligible_artifact_snapshot'] == [], 'historical', 'unsupported_artifact_snapshot')
            manifest = sources[proof['source_latest_heads']['checkpoint_head']]['value']
            require(loads(content('checkpoints/' + manifest['checkpoint_id'] + '.json')) == manifest, 'historical_file', 'manifest', 'invalid_evidence')
            names = ('graph_checkpoints.sqlite', 'graph_checkpoints.sqlite-wal', 'graph_checkpoints.sqlite-shm')
            unit = {name: content('checkpoints/' + name) if (root / 'checkpoints' / name).exists() else None for name in names}
            with TemporaryDirectory(prefix='lqcd-agent-historical-proof-', dir='/private/tmp') as directory:
                temporary = Path(directory)
                (temporary / 'checkpoints').mkdir()
                for name, raw_file in unit.items():
                    if raw_file is not None:
                        (temporary / 'checkpoints' / name).write_bytes(raw_file)
                require(verify_checkpoint(temporary, manifest) == sources[manifest['state_digest']]['value'], 'historical_file', 'checkpoint', 'invalid_evidence')
            require(unit == {name: content('checkpoints/' + name) if (root / 'checkpoints' / name).exists() else None for name in names},
                    'historical_file', 'changed_during_read', 'invalid_evidence')
            child_root = roots[lineage['case_id'], lineage['run_id']]
            require(child_root.parent.parent == root.parent.parent, 'historical_file', 'coordinator_domain')
            database = root.parent.parent / '.lqcd/control_operations.sqlite'
            require(database.resolve() == database and database.is_file(), 'historical_file', 'coordinator_path')
            connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
            try:
                operation = connection.execute('SELECT operation_type,operation_variant,request,reservation FROM control_operations WHERE operation_id=?', (lineage['parent_operation_id'],)).fetchone()
                require(operation is not None and operation[0] == 'fork_run', 'historical_file', 'fork_operation', 'invalid_evidence')
                reservation, request = loads(operation[3]), loads(operation[2])
                require(reservation['source_snapshot_proof'] == proof and
                        reservation['reserved_child_run_locator'] == {k: lineage[k] for k in ('case_id', 'run_id')} and
                        request['source_run_locator'] == proof['source_run_identity'] and
                        request['source_head_digest'] == proof['source_latest_heads']['execution_head'],
                        'historical_file', 'reservation_proof', 'invalid_evidence')
                envelope = {'operation_type': operation[0], 'operation_variant': operation[1], 'request': request}
                require(sources.get(raw_digest(envelope), {}).get('value') == envelope, 'historical_file', 'request_preimage', 'invalid_evidence')
            except sqlite3.Error as error:
                raise Invalid('historical_file', 'coordinator_read', 'invalid_evidence') from error
            finally:
                connection.close()
