"""Trace 0.5 provenance for A05 objects; never runtime authorization.

Profiles are project-owned derivation rules, not replacement wire validators.
Every raw object is checked before a logical checksum or byte hash is used as
an alias. Unlisted fields remain material, including arbitrary hex strings.
"""
from pathlib import Path
from hashlib import sha256
from contextlib import closing
import sqlite3

from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.artifacts.registry import STATE_FIELDS_BY_SLOT

from .fault_source_trace import source_path
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
    "external_result_digest": {"external_result"},
    "paused_lifecycle_head": {"execution_0_4"},
    "delivery_digest": {"delivery"},
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
CANONICAL_CODE_PATHS = {
    "code_agent_task_path": "code_agent_task.json",
    "code_agent_result_path": "code_agent_result.json",
    "code_change_manifest_path": "change_manifest.json",
    "code_verification_results_path": "verification_results.json",
}
CODE_PATH_KEYS = {"code_change_summary_path", "tests_status_path", *CANONICAL_CODE_PATHS}
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


def _project(events, proof, binding, *, ordinary=None):
    keys(proof, {"schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources", "workspace_roots"}, "a05_proof")
    require(proof["schema_version"] == "0.2", "a05_proof", "schema_version")
    base._binding(proof["binding"], binding)
    sources, executions = base._sources(proof, version="0.4")
    roots = base._roots(proof, executions)
    base._checkpoint_sources(sources, executions)
    base._historical_source_files(sources, executions, roots)
    require(all(type(proof[k]) is list for k in ("typed_sources", "material_sources", "workspace_roots")), "a05_proof", "arrays")
    if ordinary is not None:
        ordinary.validate(sources, executions, roots, events)
    kinds = {head: source_kind(row) for head, row in sources.items()}
    aliases = {head: head for head in sources}
    declared_kinds = {row["source_sha256"]: row["kind"] for row in proof["typed_sources"] if
                      type(row) is dict and "source_sha256" in row and "kind" in row}
    product = ordinary is not None and getattr(ordinary, "product_sources", False)
    member_bindings, code_owners = {}, {}
    member_owners, producer_owners = {}, {}
    for row in sources.values():
        if source_kind(row) != "code_bundle":
            continue
        bundle = row["value"]
        by_name = {Path(member["canonical_path"]).name: member["sha256"] for member in bundle["members"]}
        require("code_agent_task.json" in by_name and "workspace_manifest.json" in by_name,
                "a05_bundle", "owner_members")
        task_head, manifest_head = by_name["code_agent_task.json"], by_name["workspace_manifest.json"]
        require(task_head in sources and manifest_head in sources, "a05_bundle", "owner_sources")
        task_owner = identity(sources[task_head]["value"])
        manifest_owner = identity(sources[manifest_head]["value"])
        require(all(task_owner.get(k) == manifest_owner.get(k) for k in
                    ("case_id", "run_id", "attempt_id", "producer_operation_id")) and
                all(bundle.get(k) == task_owner.get(k) for k in ("case_id", "run_id", "attempt_id")),
                "a05_bundle", "owner_identity")
        owner = {**task_owner, "workspace_id": manifest_owner["workspace_id"]}
        if product:
            owner_key = tuple(owner[k] for k in IDENTITIES)
            require(owner_key not in code_owners, "a05_bundle", "duplicate_owner")
            code_owners[owner_key] = (bundle, sources[task_head]["value"], sources[manifest_head]["value"])
        producer = owner["producer_operation_id"]
        require(producer not in producer_owners or producer_owners[producer] == owner,
                "a05_bundle", "producer_owner_conflict")
        producer_owners[producer] = owner
        for member in bundle["members"]:
            member_head = member["sha256"]
            if product:
                owners = member_bindings.setdefault(member_head, [])
                require(owner not in owners, "a05_bundle", "duplicate_member_owner")
                owners.append(owner)
                member_owners[member_head] = {k: v for k, v in owners[0].items()
                                              if all(candidate.get(k) == v for candidate in owners)}
            else:
                require(member_head not in member_owners or member_owners[member_head] == owner,
                        "a05_bundle", "member_owner_conflict")
                member_owners[member_head] = owner

    def source_identity(head):
        if ordinary is not None and head in ordinary.owners:
            return ordinary.owners[head]
        actual = identity(sources[head]["value"])
        if product:
            control = sources[head]["value"].get("channel_values", {}).get("control")
            if type(control) is dict and control.get("schema_version") == "0.4":
                nested = identity(control)
                require((nested.get("case_id"), nested.get("run_id")) in roots, "a05_source", "checkpoint_owner")
                _same_owner(actual, nested)
                actual.update(nested)
        inherited = member_owners.get(head)
        if inherited is None and declared_kinds.get(head) == "external_final":
            final = sources[head]["value"]
            result_head = final.get("result_digest")
            if result_head in sources and declared_kinds.get(result_head) == "external_result":
                inherited = identity(sources[result_head]["value"])
            elif result_head is None:
                inherited = producer_owners.get(final.get("producer_operation_id"))
        if inherited is None and declared_kinds.get(head) == "delivery" and "member_contents" in sources[head]["value"]:
            contents = sources[head]["value"]["member_contents"]
            task = loads(contents["code_agent_task.json"])
            manifest = loads(contents["workspace_manifest.json"])
            inherited = {**identity(task), "workspace_id": manifest["workspace_id"]}
        if inherited is None:
            return actual
        _same_owner(actual, inherited)
        return {**inherited, **actual}

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
            owner = source_identity(head)
            owners = (ordinary.owner_bindings.get(head) or member_bindings.get(head) or [owner]) if product else [owner]
            for candidate in owners:
                require(all(type(candidate.get(k)) is str and candidate[k] for k in ("case_id", "run_id", "attempt_id")), "a05_source", "identity")
                require((candidate["case_id"], candidate["run_id"]) in roots, "a05_source", "run")
                require(all(type(candidate.get(k)) is str and candidate[k] for k in
                            (("producer_operation_id",) if kind == "task" else ("producer_operation_id", "workspace_id"))) or
                        kind == "analysis_spec", "a05_source", "producer_workspace")
        checksum = CHECKSUMS[kind]
        if kind in ("change_manifest", "verification", "interrupt_evidence"):
            optional = {"change_manifest": "change_manifest_digest",
                        "verification": "verification_results_digest",
                        "interrupt_evidence": "interrupt_evidence_digest"}[kind]
            if optional in value:
                checksum = optional
        if checksum is not None:
            require(value.get("schema_version") == "0.1", "a05_source", "schema_version")
            logical = value[checksum]
            base.sha_value(logical, "a05_checksum")
            require(logical == digest({k: v for k, v in value.items() if k != checksum}), "a05_source", "checksum", "invalid_evidence")
            require(logical not in aliases or aliases[logical] == head, "a05_source", "ambiguous_alias")
            aliases[logical], checksums[head] = head, checksum
            key = (kind, *(source_identity(head).get(k) for k in IDENTITIES))
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
    if ordinary is not None:
        for head, row in ordinary.sources.items():
            require(head not in sources, "ordinary_source", "duplicate_base_source", "invalid_evidence")
            sources[head] = row
            aliases[head], kinds[head] = head, "ordinary"
    material, material_bindings, declared_materials = {}, {}, set()
    for row in proof["material_sources"]:
        keys(row, {"kind", "sha256", "content", "owner"}, "a05_material")
        require(row["kind"] in (("material", "tool_audit", "canonical_tool_audit") if product else
                                ("material", "tool_audit")) and type(row["content"]) is str, "a05_material", "encoding")
        raw, head = row["content"].encode(), row["sha256"]
        require(sha256(raw).hexdigest() == head and (head not in aliases or product and head in material),
                "a05_material", "raw_bytes", "invalid_evidence")
        _owner(row["owner"])
        require((row["owner"]["case_id"], row["owner"]["run_id"]) in roots, "a05_material", "run")
        if product:
            owner_key = tuple(row["owner"][k] for k in IDENTITIES)
            key = row["kind"], head, owner_key
            require(key not in declared_materials and owner_key in code_owners, "a05_material", "owner_binding")
            declared_materials.add(key)
            bundle, task, manifest = code_owners[owner_key]
            name = "tool_audit.jsonl" if row["kind"] in ("tool_audit", "canonical_tool_audit") else "changes.patch"
            members = [m for m in bundle["members"] if Path(m["canonical_path"]).name == name]
            require(len(members) == 1 and members[0]["sha256"] == head and members[0]["size_bytes"] == len(raw),
                    "a05_material", "registered_bytes", "invalid_evidence")
            physical = roots[row["owner"]["case_id"], row["owner"]["run_id"]] / members[0]["canonical_path"]
            require(source_path(physical).is_file() and not source_path(physical).is_symlink() and physical.resolve() == physical and
                    source_path(physical).read_bytes() == raw, "a05_material", "original_bytes", "invalid_evidence")
            material_bindings.setdefault(head, []).append(dict(row["owner"]))
        value = None
        if row["kind"] in ("tool_audit", "canonical_tool_audit"):
            value = [loads(line) for line in raw.splitlines()]
            require(raw == b"".join(canonical_bytes(v) + b"\n" for v in value), "a05_material", "canonical_jsonl")
            if row["kind"] == "canonical_tool_audit":
                from lqcd_agent.code_agent.schemas import validate_task, validate_manifest
                from lqcd_agent.code_agent.workspace import validate_tool_audit
                task = validate_task(task).value
                manifest = validate_manifest(manifest, task).value
                validate_tool_audit(raw, task, manifest)
                commands = {spec["spec_id"]: spec for spec in task["tool_policy"]}
                require(all(entry["argv_digest"] == digest(commands[entry["tool_id"]]["argv"]) and
                            entry["cwd"] == commands[entry["tool_id"]]["cwd"] for entry in value),
                        "a05_material", "audit_command", "invalid_evidence")
                root = roots[row["owner"]["case_id"], row["owner"]["run_id"]]
                database = root.parent.parent / ".lqcd/control_operations.sqlite"
                require(source_path(database).is_file() and not source_path(database).is_symlink(), "a05_material", "producer_database")
                with closing(sqlite3.connect(source_path(database).as_uri() + "?mode=ro", uri=True)) as connection:
                    stored = connection.execute("SELECT revision,value FROM external_operations WHERE external_operation_id=?",
                                                (row["owner"]["producer_operation_id"],)).fetchone()
                require(stored is not None, "a05_material", "original_producer", "invalid_evidence")
                producer = loads(stored[1])
                require(producer["phase_revision"] == stored[0] and producer["producer_operation_id"] == task["producer_operation_id"] and
                        producer["attempt_id"] == task["attempt_id"] and producer["workspace_id"] == manifest["workspace_id"] and
                        producer["run_locator"] == {k: task[k] for k in ("case_id", "run_id")} and
                        producer["task_digest"] == task["task_digest"] and producer["workspace_manifest_digest"] == manifest["manifest_digest"] and
                        producer["resolution_owner"] == "normal" and producer["proof_kind"] == "safe_stop",
                        "a05_material", "producer_owner", "invalid_evidence")
                final_path = root / producer["terminal_evidence_reference"]
                require(source_path(final_path).is_file() and not source_path(final_path).is_symlink() and final_path.resolve() == final_path and
                        final_path.is_relative_to(root), "a05_material", "final_path")
                final_raw = source_path(final_path).read_bytes()
                require(sha256(final_raw).hexdigest() == producer["terminal_evidence_digest"] and
                        producer["terminal_evidence_digest"] in sources and
                        sources[producer["terminal_evidence_digest"]]["value"] == loads(final_raw),
                        "a05_material", "original_final", "invalid_evidence")
                final = loads(final_raw)
                require(all(final[k] == producer[k] for k in ("producer_operation_id", "run_locator", "attempt_id", "cycle_id", "lease_epoch")) and
                        final["stop_proof"]["termination_or_not_dispatched"] == "confirmed" and
                        all(v is True for k, v in final["stop_proof"].items() if k != "termination_or_not_dispatched") and
                        final["resource_actual"]["tool_calls"] == len(value) and
                        final["resource_actual"]["llm_calls"] == sum(entry["resource_usage"]["llm_calls"] for entry in value),
                        "a05_material", "original_effect", "invalid_evidence")
                seal_member, = [m for m in bundle["members"] if Path(m["canonical_path"]).name == "workspace_seal.json"]
                seal = sources[seal_member["sha256"]]["value"]
                require(seal["tool_audit_digest"] == head and seal["seal_digest"] == producer["workspace_seal_digest"] == final["workspace_seal_digest"] and
                        seal["stop_proof_digest"] == digest(final["stop_proof"]), "a05_material", "original_seal", "invalid_evidence")
            else:
                for i, entry in enumerate(value, 1):
                    require(entry["tool_event_index"] == i, "a05_material", "audit_order")
                    _same_owner(row["owner"], identity(entry))
                    require(all(identity(entry).get(k) == row["owner"][k] for k in IDENTITIES), "a05_material", "audit_owner")
                    require(type(entry.get("started_at")) in (int, float) and type(entry.get("finished_at")) in (int, float) and
                            0 <= entry["started_at"] <= entry["finished_at"], "a05_clock", "audit_order")
        if head in material:
            require(material[head]["kind"] == row["kind"] and material[head]["content"] == row["content"],
                    "a05_material", "content_collision", "invalid_evidence")
        else:
            material[head] = {**row, "value": value}
        aliases[head], kinds[head] = head, row["kind"]

    if product:
        required_materials = {(m["sha256"], owner) for owner, (bundle, _, _) in code_owners.items()
                              for m in bundle["members"] if Path(m["canonical_path"]).name in ("tool_audit.jsonl", "changes.patch")}
        require({(head, owner) for _, head, owner in declared_materials} == required_materials,
                "a05_material", "material_source_gap", "invalid_evidence")

    def reference_owner(head, origin, *, analysis=False):
        candidates = (material_bindings.get(head) or member_bindings.get(head) or
                      (ordinary.owner_bindings.get(head) if product else None))
        if not candidates:
            return source_identity(head) if head in sources else material[head]["owner"]
        matching = [candidate for candidate in candidates if all(origin.get(k) is None or candidate.get(k) is None or
                    origin[k] == candidate[k] for k in IDENTITIES if not analysis or k not in ("attempt_id", "workspace_id"))]
        require(bool(matching), "a05_reference", "source_owner", "invalid_evidence")
        return {k: v for k, v in matching[0].items() if all(candidate.get(k) == v for candidate in matching)}

    def resolve(raw, accepted, origin=None, *, member=False, field=None):
        base.sha_value(raw, "a05_reference")
        require(raw in aliases, "a05_reference", "missing_source", "invalid_evidence")
        head = aliases[raw]
        require(kinds[head] in accepted or product and kinds[head] == "canonical_tool_audit" and "tool_audit" in accepted,
                "a05_reference", "kind", "invalid_evidence")
        if head in checksums:
            production_receipt = kinds[head] == "receipt" and "dispatch_status" in sources[head]["value"]
            production_final_result = (origin is not None and kinds[origin] == "external_final" and
                                       field == "result_digest" and
                                       "schema_version" not in sources[origin]["value"])
            expected = head if member or production_receipt or production_final_result else sources[head]["value"][checksums[head]]
            require(raw == expected, "a05_reference", "algorithm", "invalid_evidence")
        target = source_identity(head) if head in sources else material[head]["owner"]
        if origin is not None:
            left = source_identity(origin)
            if product:
                target = reference_owner(head, left, analysis=kinds[origin] == "analysis_spec")
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
        workspace_roots[path] = (head, source_identity(head))

    bundles = {}
    for head, kind in kinds.items():
        if kind == "code_bundle":
            value = sources[head]["value"]
            key = (value["run_id"], value["artifact_id"])
            require(key not in bundles, "a05_bundle", "duplicate_identity")
            bundles[key] = head

    inline_refs = {}
    canonical_paths = {}

    def code_path(head, path, field, pointer, source, run_identity=None):
        owner = source_identity(head)
        run = run_identity or (owner.get("case_id"), owner.get("run_id"))
        require(run in roots and pointer["attempt_kind"] == "code_agent", "a05_path", "code_owner")
        member = next((entry for entry in pointer["members"] if
                       entry["canonical_path"] == "attempts/" + pointer["attempt_id"] + "/" + CANONICAL_CODE_PATHS[field]), None)
        physical = Path(pointer["state_paths"][field])
        require(member is not None and pointer["state_paths"][field] ==
                str(roots[run] / member["canonical_path"]) and
                physical.is_absolute() and physical.resolve() == physical,
                "a05_path", "registered_code_member")
        canonical_paths[head, path] = (run, pointer["attempt_id"], field, source)

    def projection_paths(head, state, prefix):
        require(state.get("schema_version") == "0.4" and
                set(CODE_PATH_KEYS) <= set(state), "a05_path", "state_shape")
        pointer = state.get("current_artifacts", {}).get("code")
        if pointer is None:
            require(all(state[field] is None for field in CODE_PATH_KEYS) and
                    state.get("code_agent_status") is None and state.get("code_agent_usable") is None,
                    "a05_path", "empty_code_state")
            return
        owner = identity(state)
        target = bundles.get((owner.get("run_id"), pointer.get("artifact_id")))
        require(target is not None and pointer == sources[target]["value"]["pointer"] and
                all(state[field] == pointer["state_paths"][field] for field in CODE_PATH_KEYS),
                "a05_path", "state_pointer_binding")
        code_bundle = sources[target]["value"]
        code_member = next(entry for entry in code_bundle["members"] if
                           entry["canonical_path"].endswith("/code_agent_result.json"))
        result_head = aliases[code_member["sha256"]]
        code_result = sources[result_head]["value"]
        require(state.get("code_agent_status") == code_result["status"] and
                state.get("code_agent_usable") is code_result["usable"],
                "a05_path", "state_result_binding")
        for field in CANONICAL_CODE_PATHS:
            code_path(head, prefix + (field,), field, pointer, target,
                      (owner["case_id"], owner["run_id"]))

    def references(head):
        if ordinary is not None and head in ordinary.sources:
            return ordinary.refs.get(head, {})
        row, kind = sources[head], kinds[head]
        value = row["value"]
        result = {tuple(r["path"]): aliases[r["sha256"]] for r in row["references"]}
        typed_object = kind in CHECKSUMS
        budget = row["kind"] == "execution_0_4" and value.get("record_type") == "budget"
        pause = row["kind"] == "execution_0_4" and value.get("record_type") == "pause"
        if pause and value.get("event") in ("pause_claimed", "pause_consumed") and "input_snapshot" in value.get("proof", {}):
            require(value["proof"].get("input_digest") == digest(value["proof"]["input_snapshot"]),
                    "a05_pause", "input_snapshot_digest", "invalid_evidence")
        if (row["kind"] == "canonical_json" and value.get("operation_type") == "resume_run" and
                "input_digest" in value["request"]):
            request = value["request"]
            require(request.get("input_digest") == digest(request["input_snapshot"]),
                    "a05_request", "input_snapshot_digest", "invalid_evidence")
        active_extension = (getattr(ordinary, "active_interval_source", None)
                            if budget and value.get("event") == "active_interval_settled" else None)
        if budget and value.get("event") == "active_interval_settled" and not (active_extension and active_extension(value)):
            payload = value["payload"]
            run = value["case_id"], value["run_id"]
            records = executions[run]
            previous = records[value["event_index"] - 2]
            if payload["stage"] == "host_setup":
                require(previous["record_type"] == "run_lifecycle" and
                        previous["event"] == "transitioned" and previous["to_status"] == "paused" and
                        digest(previous) == value["previous_execution_head"],
                        "a05_active_time", "setup_stop")
                evidence = {"producer_operation_id": payload["producer_operation_id"],
                            "pause_id": previous["pause_id"], "paused_lifecycle_head": digest(previous)}
            else:
                require(payload["stage"] == "attempt_active" and
                        len(records) > value["event_index"], "a05_active_time", "attempt_stage")
                following = records[value["event_index"]]
                require(following["record_type"] == "attempt" and following["event"] == "finished" and
                        following["attempt_id"] == payload["attempt_id"] and
                        following["artifact_head"] == value["artifact_head"],
                        "a05_active_time", "attempt_stop")
                evidence = {"status": following["status"], "artifact_head": value["artifact_head"]}
                if digest(evidence) != payload["evidence_digest"]:
                    delivery = [head for head, kind in declared_kinds.items() if kind == "delivery" and
                                digest({"delivery_digest": head, "artifact_head": value["artifact_head"]}) ==
                                payload["evidence_digest"]]
                    require(len(delivery) == 1, "a05_active_time", "delivery_source")
                    evidence = {"delivery_digest": delivery[0], "artifact_head": value["artifact_head"]}
            require(digest(evidence) == payload["evidence_digest"] and
                    payload["evidence_digest"] in sources and
                    sources[payload["evidence_digest"]]["value"] == evidence,
                    "a05_active_time", "evidence_source", "invalid_evidence")

        def walk(item, path=()):
            if ordinary is not None and (head, path) in ordinary.refs_at:
                result[path] = ordinary.refs_at[head, path]
                return
            if type(item) is list:
                for i, child in enumerate(item):
                    walk(child, path + (i,))
            elif type(item) is dict:
                embedded = digest(item)
                if embedded in typed and embedded != head:
                    _same_owner(source_identity(head), source_identity(embedded))
                    inline_refs[head, path] = embedded
                    return
                if item.get("slot") == "code" and item.get("attempt_kind") == "code_agent" and "members" in item:
                    candidates = [h for (run, artifact), h in bundles.items() if artifact == item.get("artifact_id") and
                                  (source_identity(head).get("run_id") is None or run == source_identity(head)["run_id"])]
                    require(len(candidates) == 1, "a05_bundle", "pointer_source")
                    target = candidates[0]
                    require(item == sources[target]["value"].get("pointer"), "a05_bundle", "pointer_binding")
                    if head != target:
                        inline_refs[head, path] = target
                        return
                for key, child in item.items():
                    child_path = path + (key,)
                    if ordinary is not None and (head, child_path) in ordinary.refs_at:
                        result[child_path] = ordinary.refs_at[head, child_path]
                        continue
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
                            accepted = ({"canonical_json"} if value["event"] == "active_interval_settled" else
                                        {"external_final", "verification", "failure_evidence", "failure_identity", "interrupt_evidence"})
                        if budget and key == "input_digest" and value["event"] == "resource_reserved":
                            accepted = {"task", "verification", "material", "canonical_json"}
                    if (kind == "code_bundle" or typed_object) and key == "sha256" and "members" in path:
                        accepted = set(CHECKSUMS) | {"tool_audit", "material"}
                    if (pause and value.get("event") == "pause_opened" and
                            child_path == ("proof", "active_time", "settlement_execution_head")):
                        accepted = {"execution_0_4"}
                        require(child == value["previous_execution_head"] and
                                sources[child]["value"].get("event") == "active_interval_settled" and
                                sources[child]["value"]["payload"]["stage"] == "host_setup",
                                "a05_active_time", "pause_settlement", "invalid_evidence")
                    if accepted is not None:
                        require(type(child) is str, "a05_reference", "scalar", "invalid_evidence")
                        result[child_path] = resolve(child, accepted, head, member=key == "sha256", field=key)
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
                expected_kind = BUNDLE_MEMBERS.get(path.name)
                require(expected_kind is not None and (kinds[target] == expected_kind or
                        product and expected_kind == "tool_audit" and kinds[target] == "canonical_tool_audit"), "a05_bundle", "member_kind")
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
            pointer_paths = value["pointer"].get("state_paths")
            require(type(pointer_paths) is dict and set(pointer_paths) == CODE_PATH_KEYS and
                    pointer_paths["code_change_summary_path"] is None and
                    pointer_paths["tests_status_path"] is None,
                    "a05_path", "pointer_shape")
            for field, name in CANONICAL_CODE_PATHS.items():
                require(name in member_sources, "a05_path", "member_set")
                code_path(head, ("pointer", "state_paths", field), field, value["pointer"], member_sources[name])
            links = {"task_digest": "code_agent_task.json", "workspace_manifest_digest": "workspace_manifest.json",
                     "change_manifest_digest": "change_manifest.json", "verification_results_digest": "verification_results.json",
                     "dispatch_receipt_digest": "backend_dispatch_receipt.json", "workspace_seal_digest": "workspace_seal.json",
                     "interrupt_evidence_digest": "interrupt_evidence.json", "tool_audit_digest": "tool_audit.jsonl", "patch_digest": "changes.patch"}
            for field, name in links.items():
                if code_result.get(field) is not None:
                    require(name in member_sources and aliases[code_result[field]] == member_sources[name], "a05_bundle", "result_member_binding")
        if kind == "delivery" and "member_contents" in value:
            owner = source_identity(head)
            bundle_head = bundles.get((owner["run_id"], owner["attempt_id"] + ":code"))
            require(bundle_head is not None, "a05_delivery", "bundle")
            bundle = sources[bundle_head]["value"]
            members = {Path(item["canonical_path"]).name: item for item in bundle["members"]}
            require(set(value["member_contents"]) == set(members) and
                    value["artifact_status"] == bundle["pointer"]["status"],
                    "a05_delivery", "member_set")
            for name, content in value["member_contents"].items():
                require(type(content) is str and sha256(content.encode()).hexdigest() == members[name]["sha256"],
                        "a05_delivery", "member_bytes")
                if name.endswith(".json"):
                    target = aliases[members[name]["sha256"]]
                    require(content.encode() == canonical_bytes(sources[target]["value"]),
                            "a05_delivery", "canonical_member")
                    result[("member_contents", name)] = target
            require(value["state_members"] == {field: None if path is None else Path(path).name
                    for field, path in bundle["pointer"]["state_paths"].items()},
                    "a05_delivery", "state_paths")
        if (row["kind"] == "canonical_json" and value.get("schema_version") == "0.4" and
                "current_artifacts" in value):
            projection_paths(head, value, ())
        if (row["kind"] == "canonical_json" and type(value.get("channel_values")) is dict and
                type(value["channel_values"].get("control")) is dict and
                value["channel_values"]["control"].get("schema_version") == "0.4"):
            projection_paths(head, value["channel_values"]["control"], ("channel_values", "control"))
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
        owner = source_identity(head) if head in sources else material[head]["owner"]

        def encode(item, path=()):
            if ordinary is not None:
                derived = ordinary.encode(head, path, project_source)
                if derived is not None:
                    return derived
            if (head, path) in inline_refs:
                return ["bound_code_pointer", project_source(inline_refs[head, path])]
            if path in refs.get(head, {}):
                return ["digest_reference", project_source(refs[head][path])]
            if (head, path) in canonical_paths:
                run, attempt, field, source = canonical_paths[head, path]
                return ["canonical_code_path", list(run), attempt, field, project_source(source)]
            if kind == "code_bundle" and len(path) >= 3 and path[-3] == "members" and path[-1] == "size_bytes":
                return ["validated_member_size", project_source(refs[head][(*path[:-1], "sha256")])]
            if path == (checksums.get(head),) or (row["kind"] in ("checkpoint_manifest", "historical_checkpoint_manifest_0_3") and path == ("checkpoint_head",)):
                return ["validated_self_digest"]
            if (kind == "execution_0_4" and value.get("record_type") == "pause" and
                    value.get("event") in ("pause_claimed", "pause_consumed") and path == ("proof", "input_digest")):
                return ["validated_input_snapshot_digest"]
            if (row["kind"] == "canonical_json" and value.get("operation_type") == "resume_run" and
                    path == ("request", "input_digest")):
                return ["validated_input_snapshot_digest"]
            if row["kind"] in ("execution_0_4", "historical_execution_0_3") and path in (("created_at",), ("committed_at",)):
                return ["validated_clock", item["source"]]
            if clock_path(kind, path):
                require(type(item) in (int, float) and item >= 0, "a05_clock", "number")
                return ["validated_clock", path[-1]]
            if kind == "canonical_tool_audit" and len(path) == 2 and path[-1] in ("start_at", "end_at"):
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
                    if (path and path[-1] in RUN_PATH_FIELDS and kind not in CHECKSUMS and
                            not (ordinary is not None and head in ordinary.sources) and
                            (item == str(root) or item.startswith(str(root) + "/"))):
                        physical = Path(item)
                        require(str(physical) == item and physical.resolve() == physical, "a05_path", "canonical")
                        return ["physical_path", list(run_identity), physical.relative_to(root).as_posix()]
                for root, (evidence, workspace_owner) in workspace_roots.items():
                    if ordinary is not None and head in ordinary.sources:
                        continue
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
        if ordinary is not None:
            content = ordinary.finish_content(head, content, project_source)
        result = base.SEMANTIC_PREFIX + digest({"projection_version": "0.6" if ordinary is not None else "0.5", "source_kind": kind, "content": content})
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
                _same_owner({"run_id": value["run_id"]}, source_identity(head))
                value[field] = project_source(head)
        for field, accepted in EVENT_REFS.items():
            if value[field] is not None:
                head = resolve(value[field], accepted)
                _same_owner({k: value.get({"producer_operation_id": "external_operation_id"}.get(k, k)) for k in IDENTITIES}, source_identity(head))
                value[field] = project_source(head)
        artifacts = []
        for artifact in value["artifacts"]:
            head = resolve(artifact["digest"], {"code_bundle", "canonical_json"})
            require(all(artifact[k] == sources[head]["value"].get(k) for k in ("artifact_id", "slot")), "a05_event", "artifact_binding")
            _same_owner({"run_id": value["run_id"]}, source_identity(head))
            artifacts.append(dict(artifact, digest=project_source(head)))
        value["artifacts"] = artifacts
        result.append(value)
    require(visited == set(sources) | set(material), "a05_trace", "orphan_sources", "invalid_evidence")
    return result
