"""Trace 0.5 provenance for A05 objects; never runtime authorization.

Profiles are project-owned derivation rules, not replacement wire validators.
Every raw object is checked before a logical checksum or byte hash is used as
an alias. Unlisted fields remain material, including arbitrary hex strings.
"""
from pathlib import Path
from hashlib import sha256

from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.artifacts.registry import STATE_FIELDS_BY_SLOT

from .strict_json import Invalid, keys, require, text
from . import trace_proof as base


# A null checksum means the complete canonical object is content-addressed.
CHECKSUMS = {
    "task": "task_digest", "manifest": "manifest_digest", "core": "operation_contract_digest",
    "receipt": "receipt_digest", "seal": "seal_digest", "external_result": "result_digest",
    "code_result": "result_digest", "analysis_spec": "spec_digest", "verification": None,
    "change_manifest": None, "external_final": None, "interrupt_evidence": None,
    "delivery": None, "failure_evidence": None, "workspace_evidence": None,
    "code_context": None, "analysis_context": None,
    "pause_binding": None, "failure_identity": None,
    "external_operation": None,
}
COMMON = {
    "task_digest": {"task"}, "workspace_manifest_digest": {"manifest"},
    "dispatch_receipt_digest": {"receipt"}, "workspace_seal_digest": {"seal"},
    "change_manifest_digest": {"change_manifest"}, "verification_results_digest": {"verification"},
    "tool_audit_digest": {"tool_audit"}, "operation_contract_digest": {"core"},
    "terminal_evidence_digest": {"external_final"}, "interrupt_evidence_digest": {"interrupt_evidence"},
    "external_final_digest": {"external_final"},
    "failure_id_digest": {"failure_identity"}, "code_task_context_digest": {"code_context"},
    "pause_binding_digest": {"pause_binding"},
    "analysis_execution_context_digest": {"analysis_context"},
    "patch_digest": {"material"},
}
PROFILE_REFS = {
    "task": {"budget_envelope_digest": {"budget_decision"}},
    "core": {"reservation_digest": {"budget_reservation"}},
    "external_final": {"result_digest": {"external_result", "code_result"}},
    "delivery": {"result_digest": {"external_result", "code_result"}},
    "analysis_spec": {"bundle_digest": {"code_bundle"}, "code_digest": {"code_result"}},
    "workspace_evidence": {"manifest_digest": {"manifest"}},
    "pause_binding": {"reservation_digest": {"budget_reservation"}},
    "external_operation": {"reservation_digest": {"budget_reservation"}, "result_digest": {"external_result", "code_result"}},
}
EVENT_REFS = {
    "task_digest": {"task"}, "manifest_digest": {"manifest"}, "seal_digest": {"seal"},
    "bundle_digest": {"code_bundle"}, "analysis_spec_digest": {"analysis_spec"},
    "result_digest": {"external_result", "code_result", "external_final", "verification", "failure_evidence", "interrupt_evidence", "canonical_json"},
    "binding_digest": {"core", "receipt", "delivery", "external_final", "interrupt_evidence", "failure_evidence", "workspace_evidence", "canonical_json"},
}
IDENTITIES = ("case_id", "run_id", "attempt_id", "producer_operation_id", "workspace_id")
CLOCKS = {
    "manifest": {"created_at"}, "seal": {"sealed_at"}, "verification": {"started_at", "finished_at", "duration"},
    "receipt": {"accepted_at"}, "external_final": {"created_at"}, "workspace_evidence": {"created_at"},
    "tool_audit": {"started_at", "finished_at", "duration"},
}
OPAQUE = {"provider_operation_reference", "provider_thread_reference", "provider_session_reference"}
RUN_PATH_FIELDS = {"canonical_output_root", "output_root"} | {field for fields in STATE_FIELDS_BY_SLOT.values() for field in fields}
BUNDLE_MEMBERS = {"code_agent_task.json": "task", "code_agent_result.json": "code_result",
                  "workspace_manifest.json": "manifest", "change_manifest.json": "change_manifest",
                  "verification_results.json": "verification", "backend_dispatch_receipt.json": "receipt",
                  "workspace_seal.json": "seal", "tool_audit.jsonl": "tool_audit",
                  "interrupt_evidence.json": "interrupt_evidence", "changes.patch": "material"}


def clock_path(kind, path):
    if kind == "verification":
        return len(path) == 3 and path[0] == "results" and type(path[1]) is int and path[-1] in CLOCKS[kind]
    if kind == "tool_audit":
        return len(path) == 2 and type(path[0]) is int and path[-1] in CLOCKS[kind]
    return len(path) == 1 and path[0] in CLOCKS.get(kind, set())


def identity(value):
    result = dict(value.get("request", {}).get("run_locator", {}))
    result.update(value.get("run_locator", {}))
    result.update({k: value[k] for k in IDENTITIES if k in value})
    if value.get("record_type") == "budget":
        result.update({k: value["payload"][k] for k in IDENTITIES if value["payload"].get(k) is not None})
    if "target_attempt_id" in value and value["target_attempt_id"] is not None:
        result.setdefault("attempt_id", value["target_attempt_id"])
    if value.get("pause_id") is not None:
        result["pause_id"] = value["pause_id"]
    return result


def source_kind(row):
    value = row["value"]
    if row["kind"] == "execution_0_4" and value.get("record_type") == "budget":
        return {"decision_recorded": "budget_decision", "resource_reserved": "budget_reservation"}.get(value["event"], row["kind"])
    if (row["kind"] == "canonical_json" and value.get("slot") == "code" and value.get("event") == "registered" and
            value.get("pointer", {}).get("attempt_kind") == "code_agent"):
        return "code_bundle"
    return row["kind"]


def typed_source(kind, value):
    """Declare a profile, without supplying reference paths or exclusions."""
    require(kind in CHECKSUMS, "a05_source", "kind")
    return {"kind": kind, "source_sha256": digest(value)}


def material_source(kind, content, owner):
    """Capture exact UTF-8 audit or material bytes, with an explicit owner."""
    require(kind in ("material", "tool_audit") and type(content) is bytes, "a05_material", "kind")
    return {"kind": kind, "sha256": sha256(content).hexdigest(), "content": content.decode("utf-8"), "owner": owner}


def _owner(owner):
    keys(owner, IDENTITIES, "a05_owner")
    for name in IDENTITIES:
        text(owner[name], "a05_owner", name)


def _same_owner(left, right, *, analysis=False):
    for name in (*IDENTITIES, "pause_id"):
        if analysis and name in ("attempt_id", "workspace_id"):
            continue
        if left.get(name) is not None and right.get(name) is not None:
            require(left[name] == right[name], "a05_reference", name, "invalid_evidence")


def project(events, proof, binding):
    try:
        return _project(events, proof, binding)
    except Invalid:
        raise
    except (KeyError, TypeError, ValueError, OSError, RecursionError) as error:
        raise Invalid("a05_trace", "provenance", "invalid_evidence") from error


def _project(events, proof, binding):
    keys(proof, {"schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources", "workspace_roots"}, "a05_proof")
    require(proof["schema_version"] == "0.2", "a05_proof", "schema_version")
    base._binding(proof["binding"], binding)
    sources, executions = base._sources(proof, version="0.4")
    roots = base._roots(proof, executions)
    base._checkpoint_sources(sources, executions)
    base._historical_source_files(sources, executions, roots)
    require(all(type(proof[k]) is list for k in ("typed_sources", "material_sources", "workspace_roots")), "a05_proof", "arrays")
    kinds = {head: source_kind(row) for head, row in sources.items()}
    aliases = {head: head for head in sources}
    checksums, typed, immutable_owners = {}, set(), set()
    for declaration in proof["typed_sources"]:
        keys(declaration, {"kind", "source_sha256"}, "a05_source")
        kind, head = declaration["kind"], declaration["source_sha256"]
        require(kind in CHECKSUMS and head in sources and head not in typed and sources[head]["kind"] == "canonical_json", "a05_source", "profile")
        value = sources[head]["value"]
        if kind == "failure_identity":
            keys(value, {"owner", "source_phase", "source_revision", "epoch", "cause_type", "cause"}, "a05_failure_identity")
            for field in ("owner", "source_phase", "cause_type", "cause"):
                text(value[field], "a05_failure_identity", field)
            require(all(type(value[k]) is int and value[k] >= 0 for k in ("source_revision", "epoch")), "a05_failure_identity", "revision")
        if kind not in ("code_context", "analysis_context", "failure_identity"):
            owner = identity(value)
            require(all(type(owner.get(k)) is str and owner[k] for k in ("case_id", "run_id", "attempt_id")), "a05_source", "identity")
            require((owner["case_id"], owner["run_id"]) in roots, "a05_source", "run")
            require(all(type(owner.get(k)) is str and owner[k] for k in
                        (("producer_operation_id",) if kind == "task" else ("producer_operation_id", "workspace_id"))) or
                    kind == "analysis_spec", "a05_source", "producer_workspace")
        checksum = CHECKSUMS[kind]
        if checksum is not None:
            require(value.get("schema_version") == "0.1", "a05_source", "schema_version")
            logical = value[checksum]
            base.sha_value(logical, "a05_checksum")
            require(logical == digest({k: v for k, v in value.items() if k != checksum}), "a05_source", "checksum", "invalid_evidence")
            require(logical not in aliases or aliases[logical] == head, "a05_source", "ambiguous_alias")
            aliases[logical], checksums[head] = head, checksum
            key = (kind, *(identity(value).get(k) for k in IDENTITIES))
            require(key not in immutable_owners, "a05_source", "conflicting_immutable_identity")
            immutable_owners.add(key)
        kinds[head] = kind
        typed.add(head)
        clock_rows = value.get("results", []) if kind == "verification" else [value]
        require(type(clock_rows) is list, "a05_clock", "rows")
        for clock in clock_rows:
            if "started_at" in clock and "finished_at" in clock:
                require(type(clock["started_at"]) in (int, float) and type(clock["finished_at"]) in (int, float) and
                        0 <= clock["started_at"] <= clock["finished_at"], "a05_clock", "order")
    for head, row in sources.items():
        if row["kind"] == "canonical_json" and row["value"].get("schema_version") == "0.1":
            require(not any(k in row["value"] for k in CHECKSUMS.values() if k is not None) or head in typed,
                    "a05_source", "missing_profile")
    material = {}
    for row in proof["material_sources"]:
        keys(row, {"kind", "sha256", "content", "owner"}, "a05_material")
        require(row["kind"] in ("material", "tool_audit") and type(row["content"]) is str, "a05_material", "encoding")
        raw, head = row["content"].encode(), row["sha256"]
        require(sha256(raw).hexdigest() == head and head not in aliases, "a05_material", "raw_bytes", "invalid_evidence")
        _owner(row["owner"])
        require((row["owner"]["case_id"], row["owner"]["run_id"]) in roots, "a05_material", "run")
        value = None
        if row["kind"] == "tool_audit":
            value = [loads(line) for line in raw.splitlines()]
            require(raw == b"".join(canonical_bytes(v) + b"\n" for v in value), "a05_material", "canonical_jsonl")
            for i, entry in enumerate(value, 1):
                require(entry["tool_event_index"] == i, "a05_material", "audit_order")
                _same_owner(row["owner"], identity(entry))
                require(all(identity(entry).get(k) == row["owner"][k] for k in IDENTITIES), "a05_material", "audit_owner")
                require(type(entry.get("started_at")) in (int, float) and type(entry.get("finished_at")) in (int, float) and
                        0 <= entry["started_at"] <= entry["finished_at"], "a05_clock", "audit_order")
        material[head] = {**row, "value": value}
        aliases[head], kinds[head] = head, row["kind"]

    def resolve(raw, accepted, origin=None, *, member=False):
        base.sha_value(raw, "a05_reference")
        require(raw in aliases, "a05_reference", "missing_source", "invalid_evidence")
        head = aliases[raw]
        require(kinds[head] in accepted, "a05_reference", "kind", "invalid_evidence")
        if head in checksums:
            expected = head if member else sources[head]["value"][checksums[head]]
            require(raw == expected, "a05_reference", "algorithm", "invalid_evidence")
        target = identity(sources[head]["value"]) if head in sources else material[head]["owner"]
        if origin is not None:
            left = identity(sources[origin]["value"])
            _same_owner(left, target, analysis=kinds[origin] == "analysis_spec")
            if kinds[origin] == "analysis_spec" and target.get("attempt_id") is not None:
                require(sources[origin]["value"].get("source_code_attempt_id") == target["attempt_id"], "a05_reference", "analysis_source")
            if kinds[head] == "task" and "task_id" in sources[origin]["value"]:
                require(sources[origin]["value"]["task_id"] == sources[head]["value"]["task_id"], "a05_reference", "task_id")
            if kinds[head] == "failure_identity":
                origin_value = sources[origin]["value"]
                operation = origin_value.get("operation_id") or origin_value.get("payload", {}).get("operation_id")
                require(operation == sources[head]["value"]["owner"], "a05_reference", "failure_owner")
        return head

    workspace_roots = {}
    for row in proof["workspace_roots"]:
        keys(row, {"evidence_digest", "path"}, "a05_workspace")
        head = resolve(row["evidence_digest"], {"workspace_evidence"})
        evidence = sources[head]["value"]
        require(evidence.get("workspace_path") == row["path"], "a05_workspace", "raw_path_binding")
        manifest = resolve(evidence["manifest_digest"], {"manifest"}, head)
        require(evidence.get("managed_root_identity") == sources[manifest]["value"].get("managed_root_identity") and
                evidence.get("managed_root_identity") is not None, "a05_workspace", "managed_identity")
        path = Path(row["path"])
        temporary = Path("/private/tmp").resolve()
        require(path.is_absolute() and str(path) == row["path"] and path.resolve() == path and path.is_dir() and
                path.is_relative_to(temporary) and path != temporary and path.relative_to(temporary).parts[0].startswith("lqcd-agent-"), "a05_workspace", "containment")
        require(all(not path.is_relative_to(p) and not p.is_relative_to(path) for p in [*roots.values(), *workspace_roots]), "a05_workspace", "overlap")
        workspace_roots[path] = (head, identity(evidence))

    bundles = {}
    for head, kind in kinds.items():
        if kind == "code_bundle":
            value = sources[head]["value"]
            key = (value["run_id"], value["artifact_id"])
            require(key not in bundles, "a05_bundle", "duplicate_identity")
            bundles[key] = head

    inline_refs = {}

    def references(head):
        row, kind = sources[head], kinds[head]
        value = row["value"]
        result = {tuple(r["path"]): aliases[r["sha256"]] for r in row["references"]}
        typed_object = kind in CHECKSUMS
        budget = row["kind"] == "execution_0_4" and value.get("record_type") == "budget"
        pause = row["kind"] == "execution_0_4" and value.get("record_type") == "pause"

        def walk(item, path=()):
            if type(item) is list:
                for i, child in enumerate(item):
                    walk(child, path + (i,))
            elif type(item) is dict:
                embedded = digest(item)
                if embedded in typed and embedded != head:
                    _same_owner(identity(value), identity(item))
                    inline_refs[head, path] = embedded
                    return
                if item.get("slot") == "code" and item.get("attempt_kind") == "code_agent" and "members" in item:
                    candidates = [h for (run, artifact), h in bundles.items() if artifact == item.get("artifact_id") and
                                  (identity(value).get("run_id") is None or run == identity(value)["run_id"])]
                    require(len(candidates) == 1, "a05_bundle", "pointer_source")
                    target = candidates[0]
                    require(item == sources[target]["value"].get("pointer"), "a05_bundle", "pointer_binding")
                    if head != target:
                        inline_refs[head, path] = target
                        return
                for key, child in item.items():
                    child_path = path + (key,)
                    if child_path in result or child is None or child_path == (checksums.get(head),):
                        continue
                    accepted = None
                    if typed_object or budget or pause or row["kind"] == "canonical_json":
                        accepted = COMMON.get(key)
                        if typed_object:
                            accepted = PROFILE_REFS.get(kind, {}).get(key, accepted)
                        elif row["kind"] == "canonical_json":
                            accepted = EVENT_REFS.get(key, accepted)
                        if budget and key == "evidence_digest":
                            accepted = {"external_final", "verification", "failure_evidence", "failure_identity", "interrupt_evidence"}
                        if budget and key == "input_digest" and value["event"] == "resource_reserved":
                            accepted = {"task", "verification", "material", "canonical_json"}
                    if (kind == "code_bundle" or typed_object) and key == "sha256" and "members" in path:
                        accepted = set(CHECKSUMS) | {"tool_audit", "material"}
                    if accepted is not None:
                        require(type(child) is str, "a05_reference", "scalar", "invalid_evidence")
                        result[child_path] = resolve(child, accepted, head, member=key == "sha256")
                    else:
                        walk(child, child_path)
        walk(value)
        if kind == "task":
            require(value.get("task_id") == value.get("attempt_id", "") + ":code_task" and
                    value.get("attempt_kind") == value.get("node_name") == "code_agent", "a05_task", "identity")
            require(all((k,) in result for k in ("execution_head", "artifact_head", "budget_envelope_digest")), "a05_task", "sources")
            decision = sources[result[("budget_envelope_digest",)]]["value"]
            require(decision["payload"]["decision"] == "allow" and decision["payload"]["target_kind"] == "code_agent" and
                    decision["event_id"] == value["budget_envelope_ref"]["event_id"], "a05_task", "budget_decision")
            require(value["budget_envelope_ref"] == {"path": "execution_history.jsonl", "event_id": decision["event_id"]} and
                    decision["event_index"] <= sources[result[("execution_head",)]]["value"]["event_index"],
                    "a05_task", "budget_reference")
        if kind == "manifest":
            require(("task_digest",) in result and value.get("workspace_id") is not None, "a05_manifest", "task")
        if kind == "core":
            require(all((k,) in result for k in ("task_digest", "workspace_manifest_digest", "reservation_digest")), "a05_core", "dependencies")
        if kind == "pause_binding":
            require(type(value.get("pause_id")) is str and value["pause_id"] and
                    all((k,) in result for k in ("task_digest", "workspace_manifest_digest", "operation_contract_digest", "reservation_digest")),
                    "a05_pause", "dependencies")
        if kind == "code_bundle":
            members = value.get("members")
            require(type(members) is list and bool(members), "a05_bundle", "members")
            paths = set()
            member_sources = {}
            for i, member in enumerate(members):
                target = result[("members", i, "sha256")]
                raw = canonical_bytes(sources[target]["value"]) if target in sources else material[target]["content"].encode()
                require(sha256(raw).hexdigest() == member["sha256"] and type(member["size_bytes"]) is int and
                        member["size_bytes"] == len(raw), "a05_bundle", "member_bytes")
                path = Path(member["canonical_path"])
                require(not path.is_absolute() and path.as_posix() == member["canonical_path"] and
                        ".." not in path.parts and path.parts[:2] == ("attempts", value["attempt_id"]) and path not in paths,
                        "a05_bundle", "member_namespace")
                paths.add(path)
                require(path.name in BUNDLE_MEMBERS and kinds[target] == BUNDLE_MEMBERS[path.name], "a05_bundle", "member_kind")
                member_sources[path.name] = target
            require(value.get("artifact_id") == value["attempt_id"] + ":code" and "code_agent_result.json" in member_sources,
                    "a05_bundle", "identity")
            code_result = sources[member_sources["code_agent_result.json"]]["value"]
            require(value["pointer"].get("status") == code_result.get("status") and
                    all(value["pointer"].get(k) == value.get(k) for k in ("artifact_id", "slot", "attempt_id", "members")),
                    "a05_bundle", "pointer_identity")
            origin = code_result.get("result_origin")
            require(origin in ("backend_delivery", "host_timeout"), "a05_bundle", "origin")
            required = {"code_agent_task.json", "code_agent_result.json", "workspace_manifest.json", "change_manifest.json", "verification_results.json"}
            if origin == "backend_delivery":
                required.update({"backend_dispatch_receipt.json", "workspace_seal.json", "tool_audit.jsonl"})
                if code_result.get("patch_digest") is not None:
                    required.add("changes.patch")
            else:
                required.add("interrupt_evidence.json")
                if code_result.get("dispatch_receipt_digest") is not None:
                    required.add("backend_dispatch_receipt.json")
                require(code_result.get("status") == "failed" and code_result.get("usable") is False and
                        code_result.get("workspace_seal_digest") is None and code_result.get("patch_digest") is None,
                        "a05_bundle", "timeout_shape")
            require(set(member_sources) == required, "a05_bundle", "member_set")
            links = {"task_digest": "code_agent_task.json", "workspace_manifest_digest": "workspace_manifest.json",
                     "change_manifest_digest": "change_manifest.json", "verification_results_digest": "verification_results.json",
                     "dispatch_receipt_digest": "backend_dispatch_receipt.json", "workspace_seal_digest": "workspace_seal.json",
                     "interrupt_evidence_digest": "interrupt_evidence.json", "tool_audit_digest": "tool_audit.jsonl", "patch_digest": "changes.patch"}
            for field, name in links.items():
                if code_result.get(field) is not None:
                    require(name in member_sources and aliases[code_result[field]] == member_sources[name], "a05_bundle", "result_member_binding")
        return result

    refs = {head: references(head) for head in sources}
    visiting, visited, projected = set(), set(), {}
    opaque, provider_bindings = {}, {}

    def project_source(head):
        if head in projected:
            visited.add(head)
            return projected[head]
        require(head not in visiting, "a05_trace", "cycle", "invalid_evidence")
        visiting.add(head)
        kind = kinds[head]
        row = sources.get(head) or material[head]
        value = row["value"]
        owner = identity(value) if head in sources else material[head]["owner"]

        def encode(item, path=()):
            if (head, path) in inline_refs:
                return ["bound_code_pointer", project_source(inline_refs[head, path])]
            if path in refs.get(head, {}):
                return ["digest_reference", project_source(refs[head][path])]
            if kind == "code_bundle" and len(path) >= 3 and path[-3] == "members" and path[-1] == "size_bytes":
                return ["validated_member_size", project_source(refs[head][(*path[:-1], "sha256")])]
            if path == (checksums.get(head),) or (row["kind"] in ("checkpoint_manifest", "historical_checkpoint_manifest_0_3") and path == ("checkpoint_head",)):
                return ["validated_self_digest"]
            if row["kind"] in ("execution_0_4", "historical_execution_0_3") and path in (("created_at",), ("committed_at",)):
                return ["validated_clock", item["source"]]
            if clock_path(kind, path):
                require(type(item) in (int, float) and item >= 0, "a05_clock", "number")
                return ["validated_clock", path[-1]]
            if len(path) == 1 and path[-1] in OPAQUE and kind in ("receipt", "external_result") and item is not None:
                text(item, "a05_opaque", "value")
                binding_key = tuple(owner.get(k) for k in IDENTITIES if k != "workspace_id")
                key = (path[-1], item)
                require(key not in opaque or opaque[key] == binding_key, "a05_opaque", "foreign_reuse")
                owner_key = (path[-1], binding_key)
                require(owner_key not in provider_bindings or provider_bindings[owner_key] == item, "a05_opaque", "conflicting_binding")
                opaque[key] = binding_key
                provider_bindings[owner_key] = item
                return ["bound_provider_identity", path[-1], list(binding_key)]
            if type(item) is dict:
                return ["object", [[k, encode(item[k], path + (k,))] for k in sorted(item)]]
            if type(item) is list:
                return ["array", [encode(v, path + (i,)) for i, v in enumerate(item)]]
            if type(item) is str:
                for run_identity, root in roots.items():
                    if path and path[-1] in RUN_PATH_FIELDS and kind not in CHECKSUMS and (item == str(root) or item.startswith(str(root) + "/")):
                        physical = Path(item)
                        require(str(physical) == item and physical.resolve() == physical, "a05_path", "canonical")
                        return ["physical_path", list(run_identity), physical.relative_to(root).as_posix()]
                for root, (evidence, workspace_owner) in workspace_roots.items():
                    if item == str(root) or item.startswith(str(root) + "/"):
                        allowed_path = ((kind == "workspace_evidence" and path == ("workspace_path",)) or
                                        (kind == "verification" and len(path) == 3 and path[0] == "results" and path[-1] == "cwd") or
                                        (kind == "tool_audit" and len(path) == 2 and path[-1] == "cwd"))
                        require(allowed_path, "a05_path", "material_path")
                        _same_owner(owner, workspace_owner)
                        physical = Path(item)
                        require(str(physical) == item and physical.resolve() == physical, "a05_path", "canonical")
                        binding = ["self_workspace"] if head == evidence else project_source(evidence)
                        return ["workspace_path", workspace_owner, physical.relative_to(root).as_posix(), binding]
            return ["literal", item]

        content = ["material_sha256", head] if kind == "material" else encode(value)
        result = base.SEMANTIC_PREFIX + digest({"projection_version": "0.5", "source_kind": kind, "content": content})
        projected[head] = result
        visiting.remove(head)
        visited.add(head)
        return result

    result = []
    for event in events:
        value = {k: v for k, v in event.items() if k != "ephemeral"}
        for field, expected in base.EVENT_HEADS.items():
            if value[field] is not None:
                head = resolve(value[field], {expected, {"execution_0_4": "historical_execution_0_3", "checkpoint_manifest": "historical_checkpoint_manifest_0_3"}.get(expected, expected), "budget_decision", "budget_reservation"} if field == "execution_head" else {expected})
                _same_owner({"run_id": value["run_id"]}, identity(sources[head]["value"]))
                value[field] = project_source(head)
        for field, accepted in EVENT_REFS.items():
            if value[field] is not None:
                head = resolve(value[field], accepted)
                _same_owner({k: value.get({"producer_operation_id": "external_operation_id"}.get(k, k)) for k in IDENTITIES}, identity(sources[head]["value"]))
                value[field] = project_source(head)
        artifacts = []
        for artifact in value["artifacts"]:
            head = resolve(artifact["digest"], {"code_bundle", "canonical_json"})
            require(all(artifact[k] == sources[head]["value"].get(k) for k in ("artifact_id", "slot")), "a05_event", "artifact_binding")
            _same_owner({"run_id": value["run_id"]}, identity(sources[head]["value"]))
            artifacts.append(dict(artifact, digest=project_source(head)))
        value["artifacts"] = artifacts
        result.append(value)
    require(visited == set(sources) | set(material), "a05_trace", "orphan_sources", "invalid_evidence")
    return result
