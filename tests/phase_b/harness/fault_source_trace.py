"""Native four-stage evidence for explicit trace 0.12, without runtime authority."""
from base64 import b64decode, b64encode
from contextlib import closing, contextmanager
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path
import gzip
import lzma
import os
import sqlite3
import stat
import tempfile

from .strict_json import Invalid, canonical, keys, read, require, sha


STAGES = ("S0", "S1", "S2", "S3")
RECORD_FIELDS = {"schema_version", "binding", "case_id", "nodeid", "stage", "previous_stage_sha256",
    "collector_pid", "child_pid", "process_request_sha256", "process_receipt_sha256", "process_source_sha256",
    "producer", "snapshot", "observation"}
ANCHOR_FIELDS = {"schema_version", "binding", "case_id", "nodeid", "process_request_sha256",
                 "process_receipt_sha256", "process_source_sha256", "stage_heads"}
DECLARATION_FIELDS = {"schema_version", "case_id", "failpoint_id", "side", "outcome", "process_request",
    "process_receipt", "original_source", "before_snapshot", "fault_observation", "after_snapshot", "recovery_observation"}
RESOLVER = ContextVar("c26_verified_source_view", default=None)
CALL_FIELDS = {"entry", "request", "owner", "before_snapshot", "after_snapshot", "identities_before",
               "identities_after", "return", "exception"}
IDENTITY_SITES = ("lqcd_agent.control.interfaces", "lqcd_agent.control.coordinator",
                  "lqcd_agent.control.children", "lqcd_agent.code_agent.external_operation")


def save_evidence(directory, name, raw):
    """Compress new retained source bytes without changing their byte identity."""
    check(Path(name).name == name and name.endswith(".json"), "evidence_name")
    exclusive(directory / (name + ".gz"), gzip.compress(raw, compresslevel=6, mtime=0))
    return sha(raw)


def evidence_bytes(directory, name):
    check(Path(name).name == name and name.endswith(".json"), "evidence_name")
    path = directory / (name + ".gz")
    if not path.exists():
        path = directory / name
    check(path.resolve() == path and path.is_file() and not path.is_symlink(), "evidence_path")
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else raw


def check(value, field):
    require(value, "fault_source", field, "invalid_evidence")


def source_path(path):
    """Only the validated 0.12 projector can install a private read view."""
    path = Path(path)
    mapping = RESOLVER.get()
    if mapping is None:
        return path
    for logical, physical in mapping:
        if path == logical or path.is_relative_to(logical):
            return physical / path.relative_to(logical)
    # Views may call existing readers with an already resolved physical path.
    if any(path == physical or path.is_relative_to(physical) for _, physical in mapping):
        return path
    # Existing path validators inspect every ancestor for symlinks. Ancestor
    # directories are path metadata, never alternative file-content sources.
    if any(logical.is_relative_to(path) or physical.is_relative_to(path) for logical, physical in mapping):
        check(path.is_dir() and not path.is_symlink(), "source_ancestor")
        return path
    raise Invalid("fault_source", "outside_verified_source_view", "invalid_evidence")


def anchor_directory(binding, case_id):
    from .trace_proof import _binding, sha_value
    _binding({k: binding[k] for k in ("invocation_token", "digests")}, binding)
    sha_value(binding["invocation_token"], "native_capture_token")
    check(type(case_id) is str and bool(case_id), "case_id")
    path = Path("/private/tmp") / ("lqcd-agent-b00c26-capture-" + binding["invocation_token"]) / sha(case_id.encode())
    check(path.resolve() == path and not path.is_symlink() and not path.parent.is_symlink(), "anchor_path")
    return path


def exclusive(path, raw):
    check(path.resolve() == path and not path.is_symlink(), "exclusive_path")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def source_roots(raw, process=None):
    """Use complete authority, workspace and auxiliary trees, not chosen files."""
    roots = sorted({str(Path(row["path"]).parent.parent) for row in raw["proof"]["output_roots"]})
    for row in raw["proof"]["workspace_roots"]:
        if not any(Path(row["path"]).is_relative_to(Path(root)) for root in roots):
            roots.append(row["path"])
    if process is not None and "repository" in process:
        check(process["case_id"].startswith("artifact.bundle_before_analysis_transition."), "original_analysis_source")
        if process["repository"] not in roots:
            roots.append(process["repository"])
    check(roots and len(roots) == len(set(roots)), "source_roots")
    result = []
    for position, value in enumerate(sorted(roots)):
        path = Path(value)
        check(path.resolve() == path and path.is_dir() and not path.is_symlink() and
              path.parent == Path("/private/tmp") and path.name.startswith("lqcd-agent-"), "source_root_path")
        result.append({"id": str(position), "path": str(path)})
    return result


def passive_file(relative, request):
    # These original root-level collector outputs are bound separately. They
    # are not Run, journal, workspace or material files consumed by validators.
    return relative in {"process-source.json", "source-root.txt", "before-raw.json", "before-normalized.json",
        "after-raw.json", "after-normalized.json", "case-trace.json", "result.json", "race-results.json",
        "race-observations.json", Path(request["receipt_path"]).name}


def inventory(roots, request, *, contents=False):
    entries, blobs = [], {}
    for root in roots:
        path = Path(root["path"])
        for parent, directories, files in os.walk(path, followlinks=False):
            directories.sort()
            files.sort()
            for child in [*(Path(parent) / name for name in directories), *(Path(parent) / name for name in files)]:
                name = child.relative_to(path).as_posix()
                if passive_file(name, request):
                    continue
                info = child.lstat()
                check(not stat.S_ISLNK(info.st_mode), "source_symlink")
                entry = {"root": root["id"], "path": name, "mode": stat.S_IMODE(info.st_mode),
                         "type": "directory", "sha256": None, "size": None}
                if stat.S_ISREG(info.st_mode):
                    raw = child.read_bytes()
                    entry.update(type="file", sha256=sha(raw), size=len(raw))
                    if contents:
                        blobs[entry["sha256"]] = raw
                else:
                    check(stat.S_ISDIR(info.st_mode), "source_file_type")
                entries.append(entry)
        names = {entry["path"] for entry in entries if entry["root"] == root["id"]}
        for name in sorted(n for n in names if n.endswith(".sqlite")):
            for suffix in ("-wal", "-shm"):
                if name + suffix not in names:
                    entries.append({"root": root["id"], "path": name + suffix, "mode": None,
                                    "type": "absent", "sha256": None, "size": None})
    entries.sort(key=lambda entry: (entry["root"], entry["path"]))
    return entries, blobs


def check_manifest(manifest):
    from .trace_proof import sha_value
    keys(manifest, {"schema_version", "roots", "files"}, "fault_manifest")
    check(manifest["schema_version"] == "0.1" and type(manifest["roots"]) is list and
          type(manifest["files"]) is list, "manifest_schema")
    roots = {}
    for root in manifest["roots"]:
        keys(root, {"id", "path"}, "fault_root")
        check(root["id"] not in roots and type(root["path"]) is str, "root_identity")
        roots[root["id"]] = Path(root["path"])
    seen = set()
    for entry in manifest["files"]:
        keys(entry, {"root", "path", "mode", "type", "sha256", "size"}, "fault_file")
        key = entry["root"], entry["path"]
        check(entry["root"] in roots and key not in seen and type(entry["path"]) is str and
              Path(entry["path"]).as_posix() == entry["path"] and not Path(entry["path"]).is_absolute() and
              entry["path"] not in ("", ".") and ".." not in Path(entry["path"]).parts, "file_path")
        seen.add(key)
        check(entry["type"] in ("file", "directory", "absent"), "file_type")
        if entry["type"] == "file":
            sha_value(entry["sha256"], "fault_file")
            check(type(entry["size"]) is int and entry["size"] >= 0, "file_size")
        else:
            check(entry["sha256"] is None and entry["size"] is None, "nonfile_bytes")
        check(entry["mode"] is None if entry["type"] == "absent" else
              type(entry["mode"]) is int and 0 <= entry["mode"] <= 0o7777, "file_mode")
    check(manifest["files"] == sorted(manifest["files"], key=lambda x: (x["root"], x["path"])), "file_order")


def blob(directory, entry):
    path = directory / "blobs" / (entry["sha256"] + ".xz")
    if not path.exists():
        path = path.with_suffix(".gz")
    check(path.resolve() == path and path.is_file() and not path.is_symlink(), "blob_path")
    raw = (lzma.decompress if path.suffix == ".xz" else gzip.decompress)(path.read_bytes())
    check(sha(raw) == entry["sha256"] and len(raw) == entry["size"], "blob_bytes")
    return raw


@contextmanager
def private_view(directory, manifest, *, resolve=False):
    check_manifest(manifest)
    with tempfile.TemporaryDirectory(prefix="lqcd-agent-b00c26-read-", dir="/private/tmp") as temporary:
        destination = Path(temporary)
        mapping = [(Path(root["path"]), destination / root["id"]) for root in manifest["roots"]]
        for _, path in mapping:
            path.mkdir()
        for entry in manifest["files"]:
            path = destination / entry["root"] / entry["path"]
            if entry["type"] == "absent":
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if entry["type"] == "file":
                path.write_bytes(blob(directory, entry))
            else:
                path.mkdir(exist_ok=True)
            path.chmod(entry["mode"])
        check(RESOLVER.get() is None, "nested_source_view")
        token = RESOLVER.set(tuple(mapping)) if resolve else None
        try:
            yield destination
        finally:
            if token is not None:
                RESOLVER.reset(token)


def sql_value(value):
    return {"bytes": b64encode(value).decode()} if type(value) is bytes else value


def database_rows(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        schemas = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        result = {"schema": schemas, "tables": {}}
        for kind, name, _, _ in schemas:
            if kind != "table":
                continue
            quoted = '"' + name.replace('"', '""') + '"'
            columns = connection.execute("PRAGMA table_info(" + quoted + ")").fetchall()
            rows = [[sql_value(v) for v in row] for row in connection.execute("SELECT * FROM " + quoted)]
            result["tables"][name] = {"columns": columns, "rows": sorted(rows, key=canonical)}
        return read_value(result)


def read_value(value):
    from .strict_json import loads
    return loads(canonical(value))


def logical_state(directory, manifest):
    result = {}
    with private_view(directory, manifest) as view:
        for entry in manifest["files"]:
            key = entry["root"] + "/" + entry["path"]
            if entry["path"].endswith((".sqlite-wal", ".sqlite-shm")):
                continue
            if entry["type"] == "file" and entry["path"].endswith(".sqlite"):
                result[key] = {"mode": entry["mode"], "database": database_rows(view / entry["root"] / entry["path"])}
            else:
                result[key] = {k: v for k, v in entry.items() if k not in ("root", "path")}
    return result


def live_state(roots, request):
    entries, contents = inventory(roots, request, contents=True)
    check(inventory(roots, request)[0] == entries, "live_concurrent_change")
    indexed = {(row["root"], row["path"]): row for row in entries}
    result = {}
    with tempfile.TemporaryDirectory(prefix="lqcd-agent-b00c26-live-read-", dir="/private/tmp") as temporary:
        for row in entries:
            name = row["root"] + "/" + row["path"]
            if row["path"].endswith((".sqlite-wal", ".sqlite-shm")):
                continue
            if row["type"] == "file" and row["path"].endswith(".sqlite"):
                target = Path(temporary) / row["root"] / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                for suffix in ("", "-wal", "-shm"):
                    part = indexed.get((row["root"], row["path"] + suffix))
                    if part and part["type"] == "file":
                        Path(str(target) + suffix).write_bytes(contents[part["sha256"]])
                result[name] = {"mode": row["mode"], "database": database_rows(target)}
            else:
                result[name] = {key: value for key, value in row.items() if key not in ("root", "path")}
    return result


def capture_snapshot(directory, stage, roots, request):
    entries, contents = inventory(roots, request, contents=True)
    check(inventory(roots, request)[0] == entries, "concurrent_source_change")
    (directory / "blobs").mkdir(exist_ok=True)
    for head, raw in contents.items():
        destination = directory / "blobs" / (head + ".xz")
        if destination.exists():
            check(lzma.decompress(destination.read_bytes()) == raw, "existing_blob")
        else:
            exclusive(destination, lzma.compress(raw, preset=3))
    manifest = {"schema_version": "0.1", "roots": roots, "files": entries}
    content = canonical(manifest)
    exclusive(directory / (stage + "-manifest.json"), content)
    return {"stage": stage, "manifest_sha256": sha(content)}, manifest

def stage_manifest(directory, record):
    reference = record["snapshot"]
    keys(reference, {"stage", "manifest_sha256"}, "stage_snapshot")
    check(reference["stage"] == record["stage"], "snapshot_stage")
    path = directory / (record["stage"] + "-manifest.json")
    raw = path.read_bytes()
    check(sha(raw) == reference["manifest_sha256"], "manifest_bytes")
    manifest = read(path)
    check_manifest(manifest)
    for entry in manifest["files"]:
        if entry["type"] == "file":
            blob(directory, entry)
    return manifest


def checked_json(path):
    check(path.resolve() == path and path.is_file() and not path.is_symlink(), "captured_path")
    return read(path)


def identity_state(value, case_id):
    from hashlib import sha256
    import uuid
    from lqcd_agent.control.strict_json import canonical_bytes
    keys(value, {"namespace", "ordinals", "allocations"}, "host_fixture")
    check(value["namespace"] == "b00c27-parent-recovery:" + case_id and type(value["allocations"]) is list,
          "fixture_namespace")
    check(type(value["ordinals"]) is dict and all(type(number) is int for number in value["ordinals"].values()), "fixture_ordinal_types")
    ordinals = dict.fromkeys(IDENTITY_SITES, 0)
    seen = set()
    for row in value["allocations"]:
        keys(row, {"scenario_id", "allocation_site", "ordinal", "uuid"}, "host_allocation")
        site = row["allocation_site"]
        check(site in ordinals and row["scenario_id"] == value["namespace"], "fixture_site")
        ordinals[site] += 1
        check(type(row["ordinal"]) is int and row["ordinal"] == ordinals[site], "fixture_ordinal")
        preimage = {key: row[key] for key in ("scenario_id", "allocation_site", "ordinal")}
        expected = str(uuid.UUID(bytes=sha256(canonical_bytes(preimage)).digest()[:16], version=4))
        check(row["uuid"] == expected and expected not in seen, "fixture_uuid")
        seen.add(expected)
    check(value["ordinals"] == ordinals, "fixture_final_ordinals")
    return value["allocations"]


def capture_records(directory, binding, case_id):
    from .trace_proof import _binding
    anchor = checked_json(directory / "anchor.json")
    keys(anchor, ANCHOR_FIELDS, "fault_anchor")
    _binding(anchor["binding"], binding)
    node = "tests/phase_b/test_b04_runtime_cases.py::test_independent_case[" + case_id + "]"
    check(anchor["schema_version"] == "0.1" and anchor["case_id"] == case_id and anchor["nodeid"] == node and
          type(anchor["stage_heads"]) is list and len(anchor["stage_heads"]) == 4, "anchor_identity")
    if "selection" in binding:
        check(node in binding["selection"], "native_selection")
        hooks = [row for row in binding["hook_events"] if row["case_id"] == case_id and row["nodeid"] == node]
        check(len(hooks) == 1 and hooks[0]["hook_ref"] == "src/lqcd_agent/control/coordinator.py:boundary", "native_hook")
    records, manifests, previous, allocated = [], [], None, []
    for index, stage in enumerate(STAGES):
        path = directory / (stage + ".json")
        record = checked_json(path)
        keys(record, RECORD_FIELDS, "fault_stage")
        check(sha(path.read_bytes()) == anchor["stage_heads"][index] and record["previous_stage_sha256"] == previous and
              record["stage"] == stage, "stage_chain")
        check(all(record[key] == anchor[key] for key in ("schema_version", "binding", "case_id", "nodeid",
              "process_request_sha256", "process_receipt_sha256", "process_source_sha256")), "stage_binding")
        check(all(type(record[key]) is int and record[key] > 0 for key in ("collector_pid", "child_pid")) and
              record["collector_pid"] != record["child_pid"], "stage_processes")
        if records:
            check(all(record[key] == records[0][key] for key in ("producer", "collector_pid", "child_pid")), "stage_producer")
        fields = {"host_identities"} | ({"raw_sha256", "validated_version"} if stage == "S0" else
                 {"source", "injector_pid"} if stage == "S1" else {"source", "calls", "contenders"} if stage == "S2" else {"source", "calls"})
        keys(record["observation"], fields, "stage_observation")
        if stage == "S0":
            check(record["observation"]["validated_version"] == "0.11", "S0_validated_version")
        elif stage == "S1":
            check(record["observation"]["injector_pid"] == record["collector_pid"], "original_injector")
        current = identity_state(record["observation"]["host_identities"], case_id)
        check(current[:len(allocated)] == allocated and (not current if stage in ("S0", "S1") else True), "fixture_stage_order")
        allocated = current
        records.append(record)
        manifests.append(stage_manifest(directory, record))
        previous = anchor["stage_heads"][index]
    check(all(manifest["roots"] == manifests[0]["roots"] for manifest in manifests), "stage_root_set")
    return anchor, records, manifests


def declaration(directory, records, manifests, fault):
    request = read_value_bytes(evidence_bytes(directory, "request.json"))
    receipt = read_value_bytes(evidence_bytes(directory, "receipt.json"))
    boundary, side, outcome = request["case_id"].rsplit(".", 2)
    first = records[2]["observation"]["calls"]
    repeated = records[3]["observation"]["calls"]
    check(repeated[:len(first)] == first, "call_prefix")
    return {"schema_version": "0.1", "case_id": request["case_id"], "failpoint_id": boundary,
        "side": side, "outcome": outcome, "process_request": request, "process_receipt": receipt,
        "original_source": {"anchor": str(directory / "anchor.json"), "roots": manifests[0]["roots"],
            "raw_sha256": records[0]["observation"]["raw_sha256"],
            "original_raw_sha256": sha(evidence_bytes(directory, "original-before-raw.json")),
            "process_source_sha256": records[0]["process_source_sha256"]},
        "before_snapshot": records[0]["snapshot"], "fault_observation": fault, "after_snapshot": records[1]["snapshot"],
        "recovery_observation": {"after_recovery": records[2]["snapshot"], "after_repeat": records[3]["snapshot"],
            "first_call": first[0] if first else None, "repeat_calls": repeated[len(first):],
            "contenders": records[2]["observation"]["contenders"]}}


def row_values(table):
    from base64 import b64decode
    columns = [column[1] for column in table["columns"]]
    return [{key: b64decode(value["bytes"], validate=True) if type(value) is dict else value
             for key, value in zip(columns, row)} for row in table["rows"]]


def manifest_file(directory, manifest, key):
    root, relative = key.split("/", 1)
    entry, = [entry for entry in manifest["files"] if (entry["root"], entry["path"]) == (root, relative)]
    check(entry["type"] == "file", "required_file")
    return blob(directory, entry)


def owner_location(records, manifests):
    producer = records[0]["producer"]
    locator = producer["value"]["request"]["run_locator"] if producer["kind"] == "control" else {
        key: producer["value"]["authorization"]["identity"][key] for key in ("case_id", "run_id")}
    roots = manifests[0]["roots"]
    candidates = [root for root in roots if any(entry["root"] == root["id"] and
        entry["path"] == locator["case_id"] + "/" + locator["run_id"] + "/execution_history.jsonl"
        for entry in manifests[0]["files"])]
    check(len(candidates) == 1, "owner_run_root")
    root = candidates[0]
    return producer, locator, root["id"], root["id"] + "/" + locator["case_id"] + "/" + locator["run_id"]


def fault_difference(directory, records, manifests, states, spec):
    from .strict_json import sha
    producer, _, root, run = owner_location(records, manifests)
    before, after = deepcopy(states[0]), states[1]
    outcome = spec["outcome"]
    targets = []
    if outcome in ("committed_result_replay", "materializable_publication_prefix"):
        kind = "none"
    elif outcome == "non_materializable_domain_gap":
        kind = "row_delete"
        database = root + "/.lqcd/control_operations.sqlite"
        table, primary, identity = ("control_snapshots", "operation_id", producer["value"]["operation_id"]) if producer["kind"] == "control" else (
            "invocation_capabilities", "capability_id", producer["capability_id"])
        data = before[database]["database"]["tables"][table]
        column = [row[1] for row in data["columns"]].index(primary)
        removed, = [row for row in data["rows"] if row[column] == identity]
        data["rows"].remove(removed)
        targets.append({"database": database, "table": table, "primary_key": {primary: identity},
                        "before": removed, "after": {"tag": "absent"}})
    else:
        check(outcome == "integrity_conflict", "fault_outcome")
        kind = "file_corruption"
        if producer["kind"] == "control":
            target = run + "/execution_history.jsonl"
            prior = manifest_file(directory, manifests[0], target)
            damaged = prior + b"{"
        else:
            completion = producer["value"].get("completion_intent")
            relative = completion["artifact_publication"]["projections"][0]["canonical_path"] if completion else "artifact_index.json"
            target = run + "/" + relative
            prior = manifest_file(directory, manifests[0], target)
            damaged = b"changed" if completion else b"{"
        actual = manifest_file(directory, manifests[1], target)
        check(actual == damaged, "original_fault_bytes")
        before[target].update(sha256=sha(damaged), size=len(damaged))
        targets.append({"path": target, "before": {"sha256": sha(prior), "size": len(prior)},
                        "after": {"sha256": sha(damaged), "size": len(damaged)}})
    check(before == after, "exact_fault_difference")
    return {"kind": kind, "targets": targets,
            "before_snapshot_sha256": records[0]["snapshot"]["manifest_sha256"],
            "after_snapshot_sha256": records[1]["snapshot"]["manifest_sha256"],
            "injector_pid": records[1]["collector_pid"]}


@contextmanager
def original_coordinator(directory, manifest, root):
    from lqcd_agent.control.coordinator import Coordinator
    with private_view(directory, manifest) as temporary:
        connection = sqlite3.connect((temporary / root / ".lqcd/control_operations.sqlite").as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        coordinator = object.__new__(Coordinator)
        coordinator.root, coordinator.connection, coordinator.observer = temporary / root, connection, None
        try:
            yield coordinator
        finally:
            connection.close()


def compare_schema(before, after):
    check(before["schema"] == after["schema"] and before["tables"].keys() == after["tables"].keys(), "database_schema")
    for table in before["tables"]:
        check(before["tables"][table]["columns"] == after["tables"][table]["columns"], "database_columns")


def prefix_additions(directory, before_manifest, after_manifest, before, after):
    """Accept only complete C22 snapshots derived from the actual journal row."""
    from lqcd_agent.control.strict_json import loads as original_loads
    allowed = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) == after.get(key) or "/trace_prefix_evidence/" not in key:
            continue
        check(key not in before and after[key]["type"] == "file", "prefix_append_only")
        raw = manifest_file(directory, after_manifest, key)
        value = original_loads(raw)
        keys(value, {"schema_version", "capability_id", "journal_revision", "binding", "journal", "publication"}, "prefix_snapshot")
        check(value["schema_version"] == "0.1" and key.rsplit("/", 1)[1] == sha(raw) + ".json", "prefix_snapshot_name")
        database = after[key.split("/", 1)[0] + "/.lqcd/control_operations.sqlite"]["database"]
        row, = [row for row in row_values(database["tables"]["invocation_capabilities"])
                if row["capability_id"] == value["capability_id"]]
        keys(value["journal"], {"schema_version", "profile", "content", "sha256"}, "prefix_journal")
        check(value["journal_revision"] == row["revision"] and
              value["journal"]["profile"] == "invocation_publication_journal" and
              value["journal"]["content"].encode() == row["value"] and
              value["journal"]["sha256"] == sha(row["value"]), "prefix_actual_row")
        # The original 0.11 source validator checks publication bytes and owner.
        matching = []
        for stage in STAGES:
            name = "before-raw.json" if stage == "S0" else stage + "-raw.json"
            if not (directory / (name + ".gz")).exists() and not (directory / name).exists():
                continue
            source = read_value_bytes(evidence_bytes(directory, name))
            matching.extend((source["proof"]["binding"], declaration) for declaration in
                source["proof"]["ordinary_publication_prefixes"] if declaration["snapshot_sha256"] == sha(raw))
        check(matching and all(value["binding"] == binding and
              all(declaration[field] == value[field] for field in ("capability_id", "journal_revision", "journal", "publication"))
              for binding, declaration in matching),
              "prefix_source_binding")
        allowed.append(key)
    return allowed


def read_value_bytes(raw):
    from .strict_json import loads
    return loads(raw)


def verify_repeat(directory, records, manifests):
    """Keep every row; classify only the two approved same-payload CAS saves."""
    before, after = [logical_state(directory, manifest) for manifest in manifests[2:]]
    adjusted = deepcopy(before)
    producer, _, root, _ = owner_location(records, manifests)
    database = root + "/.lqcd/control_operations.sqlite"
    compare_schema(before[database]["database"], after[database]["database"])
    first_calls = records[2]["observation"]["calls"]
    all_calls = records[3]["observation"]["calls"]
    check(all_calls[:len(first_calls)] == first_calls and len(all_calls) > len(first_calls), "repeat_calls")
    repeat_calls = all_calls[len(first_calls):]
    saves = [call for call in repeat_calls if call["entry"] in
             ("ArtifactEffectPort.publish_budget", "InvocationLeases.publish_started") and call["exception"] is None]
    changes = []
    a = adjusted[database]["database"]["tables"]["invocation_capabilities"]
    b = after[database]["database"]["tables"]["invocation_capabilities"]
    old = {row["capability_id"]: row for row in row_values(a)}
    new = {row["capability_id"]: row for row in row_values(b)}
    check(old.keys() == new.keys(), "repeat_capability_set")
    for key in old:
        if old[key] == new[key]:
            continue
        check(producer["kind"] == "invocation" and key == producer["capability_id"] and saves and
              {field for field in old[key] if old[key][field] != new[key][field]} == {"revision"} and
              new[key]["revision"] == old[key]["revision"] + len(saves), "repeat_original_cas")
        changes.append({"capability_id": key, "before_revision": old[key]["revision"],
                        "after_revision": new[key]["revision"], "successful_saves": len(saves)})
    check(bool(changes) == bool(saves), "repeat_save_accounting")
    a["rows"] = deepcopy(b["rows"])
    prefixes = prefix_additions(directory, manifests[2], manifests[3], before, after)
    for key in prefixes:
        adjusted[key] = after[key]
    check(adjusted == after, "repeat_business_state")
    return {"cas": changes, "derived_prefix_count": len(prefixes), "new_business_effects": False}

def analysis_preparation_files(directory, manifest, root, run, preparation):
    """Verify the original frozen Analysis tree without materializing or running it."""
    from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
    from lqcd_agent.code_agent.workspace import immutable_git_tree, tree_digest, validate_changes, canonical_patch
    from lqcd_agent.code_agent.analysis_handoff import AnalysisHandoff
    from lqcd_agent.control.operations import PreparationVerification
    spec = loads(preparation["canonical_spec_bytes"])
    workspace = loads(preparation["canonical_workspace_manifest_bytes"])
    logical_root = Path(next(row["path"] for row in manifest["roots"] if row["id"] == root))
    adapter = object.__new__(AnalysisHandoff)
    adapter.provider = type("ReadOnlyWorkspace", (), {"root": logical_root / "analysis_workspaces"})()
    adapter.allowed_command, adapter.expected_outputs = spec["allowed_command"], spec["expected_outputs"]
    adapter._frozen(preparation)
    namespace = run + "/attempts/" + spec["target_attempt_identity"]["attempt_id"] + "/control/"
    permitted = {namespace + "analysis_execution_spec.json": canonical_bytes(spec),
                 namespace + "analysis_workspace_manifest.json": canonical_bytes(workspace),
                 namespace + "domain_preparation.json": canonical_bytes(PreparationVerification(digest(preparation),
                     preparation["workspace_manifest_digest"], preparation["expected_effective_tree_digest"]).__dict__)}
    prefix = root + "/analysis_workspaces/" + workspace["workspace_id"] + "/"
    final = {}
    for entry in manifest["files"]:
        key = entry["root"] + "/" + entry["path"]
        if key.startswith(prefix) and entry["type"] == "file":
            check(not entry["mode"] & 0o111, "analysis_file_mode")
            final[key[len(prefix):]] = blob(directory, entry)
            permitted[key] = final[key[len(prefix):]]
    check(tree_digest(final) == spec["expected_effective_tree_digest"], "analysis_effective_tree")
    source_prefix = run + "/attempts/" + spec["source_code_attempt_id"] + "/"
    members = {name: manifest_file(directory, manifest, source_prefix + name) for name in spec["source_member_digests"]}
    check({name: sha(raw) for name, raw in members.items()} == spec["source_member_digests"], "analysis_code_members")
    process = read_value_bytes(evidence_bytes(directory, "process-source.json"))
    repository = Path(process["repository"])
    repositories = [row for row in manifest["roots"] if repository == Path(row["path"])]
    check(len(repositories) == 1, "analysis_base_root")
    with private_view(directory, manifest) as view:
        base = immutable_git_tree(view / repositories[0]["id"], spec["base_revision"])
    changes = validate_changes(loads(members["code_agent_task.json"]), base, final)
    check(changes == loads(members["change_manifest.json"])["changes"] and
          canonical_patch(base, final, changes) == members["changes.patch"], "analysis_verified_change")
    owner_path = root + "/analysis_workspaces/.workspace_owners/" + workspace["workspace_id"] + ".json"
    owner_bytes = manifest_file(directory, manifest, owner_path)
    owner = loads(owner_bytes)
    info = (logical_root / "analysis_workspaces" / workspace["workspace_id"]).stat()
    expected = {key: workspace[key] for key in ("workspace_id", "manifest_digest", "managed_root_identity", "base_tree_digest")}
    check(owner == {**expected, "device": info.st_dev, "inode": info.st_ino}, "analysis_workspace_identity")
    permitted[owner_path] = owner_bytes
    return permitted


def recovery_difference(directory, records, manifests, states, spec):
    from base64 import b64decode
    from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
    from lqcd_agent.control.capabilities import invocation_prefix
    from lqcd_agent.control.interfaces import ControlPlane
    from lqcd_agent.control.operations import select_successor, validate_phase_evidence, validate_reservation
    from lqcd_agent.control.pause import PauseOperations
    producer, locator, root, run = owner_location(records, manifests)
    before, after = states[1], states[2]
    database = root + "/.lqcd/control_operations.sqlite"
    a, b = before[database]["database"], after[database]["database"]
    check(before[database]["mode"] == after[database]["mode"], "recovery_database_mode")
    compare_schema(a, b)
    tables_a, tables_b = a["tables"], b["tables"]
    owners = set()
    authority = {"operation_id": producer["value"]["operation_id"]} if producer["kind"] == "control" else {
        "capability_id": producer["capability_id"], "operation_id": producer["value"]["authorization"]["producer_operation_id"]}
    allowed_files, allowed_checkpoints, allowed_removals = {}, {}, {}
    allowed_controls, control_saves = [], 0
    semantics = {"owner": authority, "writes": [], "operation_results": []}
    def permit(path, raw):
        check(type(raw) is bytes, "frozen_file_bytes")
        allowed_files.setdefault(path, []).append(raw)
    def invocation_intents(value):
        if value.get("started_intent") is not None:
            intent = value["started_intent"]
            permit(run + "/execution_history.jsonl", intent["content"].encode())
            permit(run + "/artifact_index.json", intent["index"].encode())
        for intent in value.get("budget_intents", []):
            permit(run + "/execution_history.jsonl", intent["content"].encode())
            permit(run + "/artifact_index.json", intent["index"].encode())
        intent = value.get("completion_intent")
        if intent is not None:
            permit(run + "/execution_history.jsonl", intent["content"].encode())
            permit(run + "/artifact_index.json", intent["index"].encode())
            manifest = intent["manifest"]
            permit(run + "/checkpoints/" + manifest["checkpoint_id"] + ".json", canonical_bytes(manifest))
            allowed_checkpoints[manifest["checkpoint_id"]] = intent["checkpoint"]
            publication = intent["artifact_publication"]
            if publication is not None:
                permit(run + "/artifact_history.jsonl", publication["content"].encode())
                for member in publication["projections"]:
                    content = b64decode(member["content_base64"], validate=True)
                    for key in ("canonical_path", "projection_path"):
                        permit(run + "/" + member[key], content)
    calls = records[2]["observation"]["calls"]
    contenders = records[2]["observation"]["contenders"]
    if producer["kind"] == "invocation":
        invocation_intents(producer["value"])
        check(len(calls) == 1 and not contenders, "invocation_first_call")
        first = calls[0]
        failed = spec["outcome"] in ("integrity_conflict", "non_materializable_domain_gap")
        check((first["exception"] is not None) == failed and (first["return"] is None if failed else True), "invocation_result")
        if failed:
            check(first["exception"]["type"] == "ControlIntegrityError", "invocation_rejection")
        for table in tables_a:
            if table not in ("invocation_capabilities", "run_controls"):
                check(tables_a[table] == tables_b[table], "invocation_foreign_table")
        old_caps, new_caps = row_values(tables_a["invocation_capabilities"]), row_values(tables_b["invocation_capabilities"])
        foreign = lambda rows: [row for row in rows if row["capability_id"] != producer["capability_id"]]
        check(foreign(old_caps) == foreign(new_caps), "foreign_invocation")
        own_before = [row for row in old_caps if row["capability_id"] == producer["capability_id"]]
        own_after = [row for row in new_caps if row["capability_id"] == producer["capability_id"]]
        check(len(own_before) == len(own_after), "deleted_authority_restored")
        if own_after:
            old, new = loads(own_before[0]["value"]), loads(own_after[0]["value"])
            for key in old:
                if key not in ("budget_intents", "completion_intent", "started_intent", "state"):
                    check(old[key] == new[key], "invocation_owner_changed")
            def frozen(value):
                if type(value) is dict:
                    return {key: frozen(child) for key, child in value.items() if key != "published"}
                return [frozen(child) for child in value] if type(value) is list else value
            for key in ("budget_intents", "completion_intent", "started_intent"):
                check(frozen(old.get(key)) == frozen(new.get(key)), "invocation_frozen_intent")
            check(new["state"] == old["state"] or old["state"] == "started" and new["state"] == "finished" and not failed,
                  "invocation_state")
            check(own_after[0]["revision"] == own_before[0]["revision"] + int(not failed), "invocation_publication_cas")
            if not failed and new.get("completion_intent") is not None:
                intent = new["completion_intent"]
                if not intent.get("checkpoint_deferred_until_release", False):
                    control_saves += 1
                    allowed_controls.append({"locator": locator, "projection": intent["projection"], "manifest": intent["manifest"]})
        semantics.update(result="rejected_original_authority" if failed else "original_publication_completed")
    else:
        original = producer["value"]
        owners.add(original["operation_id"])
        with original_coordinator(directory, manifests[2], root) as coordinator:
            actual = coordinator.get(original["operation_id"])
            plane = ControlPlane(coordinator, worker_id=actual["worker_owner_id"])
            result = plane.query_operation(original["operation_id"])
            if contenders:
                check(spec["failpoint_id"] == "budget.grant_owner_race" and len(contenders) == 2, "original_contenders")
                terminal = [row["result"] for row in contenders if "result" in row and row["result"]["operation_status"] != "in_progress"]
                check(terminal and all(value == result for value in terminal), "contender_terminal")
                for row in contenders:
                    check(set(row) in ({"result", "call"}, {"rejected", "call"}), "contender_shape")
                    call = row["call"]
                    keys(call, {"binding", "case_id", "entry", "request", "actor", "worker_id", "process_id",
                                "return", "exception"}, "contender_call")
                    check(call["binding"] == records[0]["binding"] and call["case_id"] == records[0]["case_id"] and
                          call["entry"] == "ControlPlane.advance_run" and call["request"] == {
                              "run_locator": locator, "source_attempt_id": original["request"]["source_attempt_id"],
                              "idempotency_key": original["idempotency_key"]} and call["actor"] == {
                              "actor_id": "operator", "actor_type": "human", "scopes": ["control.internal", "resume", "start"]} and
                          call["worker_id"] == "b04-grant-racer-" + str(contenders.index(row)) and
                          type(call["process_id"]) is int and call["process_id"] > 0 and
                          call["process_id"] not in (records[0]["child_pid"], records[0]["collector_pid"]), "original_contender_call")
                    check(call["return"] == row.get("result") and call["exception"] == (None if "result" in row else {
                          "type": "ControlIntegrityError", "message": row["rejected"]}), "contender_actual_result")
                    if "result" in row and row["result"]["operation_status"] == "in_progress":
                        value = row["result"]
                        check(value["operation_id"] == result["operation_id"] and value["result"] is None and value["error"] is None and
                              value["publication_status"] == "materialization_pending" and value["run_status"] is None and
                              value["lease_epoch"] == result["lease_epoch"] and value["phase_revision"] <= result["phase_revision"], "contender_prefix")
                check(len({row["call"]["process_id"] for row in contenders}) == 2 and actual["worker_owner_id"] in
                      {row["call"]["worker_id"] for row in contenders if row.get("result", {}).get("operation_status") in
                       ("committed", "failed", "recovery_required")},
                      "single_race_owner")
            else:
                check(len(calls) == 1 and calls[0]["return"] == result and calls[0]["exception"] is None, "control_actual_return")
            expected_status = ("committed",) if spec["outcome"] in ("committed_result_replay", "materializable_publication_prefix") else ("failed", "recovery_required")
            check(result["operation_status"] in expected_status and (result["run_status"] is None if result["operation_status"] != "committed" else True), "control_recovery_status")
            if original["operation_type"] == "resume_run":
                child = PauseOperations(coordinator, actual["worker_owner_id"], 30)._invalid_human_followup(actual)
                if child is not None:
                    owners.add(child["operation"]["operation_id"])
            if original["operation_type"] == "advance_run" and actual["error"] is not None and "close_operation_id" in actual["error"]:
                cause = {"kind": "advance_integrity_failure", "source_phase_revision": original["phase_revision"],
                         "violation": "Advance prefix conflict"}
                close = coordinator.get(actual["error"]["close_operation_id"])
                check(actual["error"] == {**cause, "close_operation_id": close["operation_id"]} and
                      actual["status"] == "failed" and actual["phase_revision"] == original["phase_revision"] and
                      spec["outcome"] == "integrity_conflict", "original_advance_failure")
                prior_control, = [row for row in row_values(tables_a["run_controls"]) if row["run_key"] == digest(locator)]
                control = loads(prior_control["value"])
                check(control.get("advance_owner") == original["operation_id"], "original_advance_owner")
                frozen = coordinator.snapshot(original["operation_id"])
                heads = {key: control["projection"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}
                heads["policy_digest"] = frozen["policy"]["policy_digest"]
                source = {"tag": "unavailable_by_construction", "last_trusted_heads": heads}
                precondition = {"tag": "absent", "source_operation_id": original["operation_id"], "advance_never_activated": True}
                trigger = {"kind": "non_pause_runtime_failure", "source_operation_id": original["operation_id"],
                           "source_phase_revision": original["phase_revision"], "run_locator": locator, "cause": cause}
                request = {"run_locator": locator, "trigger": trigger, "trigger_digest": digest(trigger),
                           "disposition": "failed", "source": source, "policy_digest": heads["policy_digest"]}
                reservation = {"run_terminal_closure_key": digest(locator), "terminal_trigger_identity": trigger,
                    "requested_terminal_disposition": "failed", "external_operation_precondition": "absent",
                    "external_operation_precondition_proof_digest": digest(precondition),
                    "terminal_disposition_contract_digest": digest({"trigger": digest(trigger), "disposition": "failed"}),
                    "close_source_snapshot": {"precondition": precondition, "source": source}}
                error = {"kind": "run_authority_unavailable", "trigger_digest": digest(trigger), "last_trusted_heads": heads}
                check(close["operation_type"] == "close_run" and close["operation_variant"] == "not_applicable" and
                      close["idempotency_scope"] == "internal_terminal" and close["idempotency_key"] == digest(request) and
                      close["request"] == request and close["reservation"] == reservation and
                      coordinator.snapshot(close["operation_id"]) == {"source": source} and
                      close["worker_owner_id"] == actual["worker_owner_id"] and close["lease_epoch"] == 1 and
                      close["phase"] == "terminal_ownership_reserved" and close["phase_revision"] == 2 and
                      close["status"] == "failed" and close["error"] == error, "original_advance_close")
                check(not any(row["operation_id"] == close["operation_id"] for row in row_values(tables_a["control_operations"])) and
                      not any(row["operation_id"] == close["operation_id"] for row in row_values(tables_b["control_publications"])),
                      "unavailable_close_has_no_publication")
                expected_closure = {"terminal_closure_revision": 1, "terminal_closure_owner_operation_id": close["operation_id"],
                    "terminal_trigger_reference": trigger, "terminal_trigger_digest": digest(trigger),
                    "terminal_request_digest": close["request_digest"], "terminal_disposition_contract": {"run_status": "failed"},
                    "terminal_preclose_contract": source, "resolved_terminal_disposition": None, "resolved_preclose_heads": None,
                    "terminal_closure": "unavailable", "run_status": None, "unavailable_proof": error}
                check(not any(row["run_key"] == digest(locator) for row in row_values(tables_a["run_terminal_closure"])) and
                      [row for row in row_values(tables_b["run_terminal_closure"]) if row["run_key"] == digest(locator)] ==
                      [{"run_key": digest(locator), "revision": 1, "value": canonical_bytes(expected_closure)}],
                      "original_unavailable_closure")
                owners.add(close["operation_id"])
            old_operations = {row["operation_id"]: row for row in row_values(tables_a["control_operations"])}
            new_operations = {row["operation_id"]: row for row in row_values(tables_b["control_operations"])}
            check(old_operations.keys() <= new_operations.keys(), "removed_control_owner")
            check({key for key in new_operations if old_operations.get(key) != new_operations[key]} <= owners, "foreign_control_owner")
            for identity in sorted(owners):
                operation = coordinator.get(identity)
                check(operation["request"]["run_locator"] == locator, "recovery_operation_run")
                validate_reservation(operation["operation_type"], operation["operation_variant"], operation["reservation"])
                history = coordinator.history(identity)
                prior_rows = [row for row in row_values(tables_a["control_phases"]) if row["operation_id"] == identity]
                previous_revision = max((row["revision"] for row in prior_rows), default=0)
                new_phases = {row["phase"] for row in history if row["revision"] > previous_revision}
                saving_phases = {"advance_run": {"budget_decision_committed", "result_committed"},
                    "publish_pause": {"public_paused_checkpoint_committed"},
                    "close_run": {"terminal_ownership_reserved", "terminal_checkpoint_committed"}}.get(operation["operation_type"], set())
                control_saves += len(new_phases & saving_phases)
                for prior in prior_rows:
                    matching, = [row for row in history if row["revision"] == prior["revision"]]
                    check(all(matching[key] == loads(prior[key]) if key in ("evidence", "branch") else matching[key] == prior[key]
                              for key in ("revision", "phase", "lease_epoch", "evidence", "branch")), "changed_phase_prefix")
                for previous, current in zip(history, history[1:]):
                    state = {**operation, "phase": previous["phase"], "phase_revision": previous["revision"]}
                    check(current["revision"] == previous["revision"] + 1, "phase_revision_sequence")
                    select_successor(state, current["phase"], current["branch"])
                    validate_phase_evidence(state, current["phase"], current["evidence"])
                check(history[-1]["revision"] == operation["phase_revision"] and history[-1]["phase"] == operation["phase"], "current_phase")
                if identity in old_operations:
                    immutable = ("operation_id", "idempotency_scope", "idempotency_key", "request_digest", "operation_type", "operation_variant", "request", "reservation", "created_at")
                    check(all(old_operations[identity][key] == new_operations[identity][key] for key in immutable), "changed_original_contract")
                    check([row for row in row_values(tables_a["control_snapshots"]) if row["operation_id"] == identity] ==
                          [row for row in row_values(tables_b["control_snapshots"]) if row["operation_id"] == identity],
                          "original_frozen_snapshot")
                semantics["operation_results"].append({key: operation[key] for key in
                    ("operation_id", "operation_type", "phase", "phase_revision", "lease_epoch", "status")})
                snapshots = [loads(row["value"]) for row in row_values(tables_b["control_snapshots"])
                             if row["operation_id"] == identity]
                if not snapshots:
                    continue
                snapshot, = snapshots
                control = snapshot.get("public", snapshot)
                if "projection" in control and "manifest" in control:
                    candidate = {"locator": locator, "projection": control["projection"], "manifest": control["manifest"]}
                    if operation["operation_type"] == "advance_run":
                        candidate.update(checkpoint_anchor_kind="owned_transition", transition_owner=identity)
                    allowed_controls.append(candidate)
                for step in snapshot.get("steps", []):
                    checkpoint = step.get("checkpoint")
                    if checkpoint is not None:
                        allowed_checkpoints[checkpoint["manifest"]["checkpoint_id"]] = checkpoint["checkpoint"]
                if operation["operation_type"] == "close_run":
                    if snapshot["source"]["tag"] != "unavailable_by_construction":
                        permit(run + "/artifact_index.json", canonical_bytes(snapshot["artifact_index"]))
                        manifest = snapshot["manifest"]
                        permit(run + "/checkpoints/" + manifest["checkpoint_id"] + ".json", canonical_bytes(manifest))
                        allowed_checkpoints[manifest["checkpoint_id"]] = snapshot["checkpoint"]
                if operation["operation_type"] == "advance_run":
                    if any(row["phase"] == "target_artifacts_invalidated" for row in history):
                        for removal in snapshot["removals"]:
                            path = run + "/" + removal["path"]
                            check(snapshot["original_index"]["managed_projections"][removal["path"]] ==
                                  removal["artifact_id"], "original_projection_owner")
                            allowed_removals[path] = removal["sha256"]
                    preparation = snapshot["reservation"]["target_preparation_snapshot"]
                    if preparation["preparation_kind"] == "analysis_fresh" and any(
                            row["phase"] == "target_preparation_committed" for row in history):
                        for path, content in analysis_preparation_files(directory, manifests[2], root, run,
                                                                       preparation).items():
                            permit(path, content)
            for row in row_values(tables_b["control_publications"]):
                if row["operation_id"] not in owners:
                    continue
                check(sha(row["content"]) == row["content_digest"], "publication_digest")
                logical = Path(row["path"])
                original_root = Path(next(value["path"] for value in manifests[2]["roots"] if value["id"] == root))
                check(logical.is_relative_to(original_root / locator["case_id"] / locator["run_id"]), "publication_run")
                permit(root + "/" + logical.relative_to(original_root).as_posix(), row["content"])
            for row in row_values(tables_b["invocation_capabilities"]):
                value = loads(row["value"])
                if value["authorization"]["producer_operation_id"] in owners:
                    check(all(value["authorization"]["identity"][key] == locator[key] for key in locator), "recovered_capability_run")
                    invocation_intents(value)
                    prior = [old for old in row_values(tables_a["invocation_capabilities"]) if old["capability_id"] == row["capability_id"]]
                    if prior and loads(prior[0]["value"])["state"] != "finished" and value["state"] == "finished":
                        intent = value["completion_intent"]
                        if not intent.get("checkpoint_deferred_until_release", False):
                            control_saves += 1
                            allowed_controls.append({"locator": locator, "projection": intent["projection"], "manifest": intent["manifest"]})
            def foreign_capabilities(table):
                return [row for row in row_values(table) if loads(row["value"])["authorization"]["producer_operation_id"] not in owners]
            check(foreign_capabilities(tables_a["invocation_capabilities"]) == foreign_capabilities(tables_b["invocation_capabilities"]),
                  "foreign_recovery_capability")
            for table in tables_a:
                if table in ("control_operations", "control_phases", "control_publications", "control_snapshots"):
                    rows_a, rows_b = row_values(tables_a[table]), row_values(tables_b[table])
                    check([row for row in rows_a if row["operation_id"] not in owners] ==
                          [row for row in rows_b if row["operation_id"] not in owners], "foreign_control_rows")
                elif table not in ("invocation_capabilities", "run_controls", "pause_ownership", "run_terminal_closure"):
                    check(tables_a[table] == tables_b[table], "foreign_recovery_table")
            semantics["result"] = {key: result[key] for key in ("operation_status", "operation_phase", "phase_revision", "lease_epoch", "run_status", "domain_status", "terminal_closure")}
    run_key = digest(locator)
    for table in ("run_controls", "pause_ownership", "run_terminal_closure"):
        rows_a, rows_b = row_values(tables_a[table]), row_values(tables_b[table])
        check([row for row in rows_a if row["run_key"] != run_key] ==
              [row for row in rows_b if row["run_key"] != run_key], "foreign_run_rows")
    control_before, = [row for row in row_values(tables_a["run_controls"]) if row["run_key"] == run_key]
    control_after, = [row for row in row_values(tables_b["run_controls"]) if row["run_key"] == run_key]
    check(control_after["revision"] == control_before["revision"] + control_saves, "original_run_control_cas")
    check(control_after["value"] == control_before["value"] or loads(control_after["value"]) in allowed_controls,
          "original_run_control_value")
    prefixes = prefix_additions(directory, manifests[1], manifests[2], before, after)
    for key in prefixes:
        permit(key, manifest_file(directory, manifests[2], key))
    consumed_index_temporary = set()
    for content in allowed_files.get(run + "/artifact_index.json", []):
        temporary = run + "/.artifact_index_" + sha(content) + ".tmp"
        if temporary in before and temporary not in after:
            check(before[temporary]["type"] == "file" and before[temporary]["sha256"] == sha(content) and
                  manifest_file(directory, manifests[1], temporary) == content and
                  manifest_file(directory, manifests[2], run + "/artifact_index.json") == content and
                  before[temporary]["mode"] == after[run + "/artifact_index.json"]["mode"],
                  "original_atomic_index_consumption")
            allowed_removals[temporary] = sha(content)
            consumed_index_temporary.add(temporary)
    # Every changed domain file must equal bytes frozen by the original owner.
    for key in sorted(set(before) | set(after)):
        if before.get(key) == after.get(key) or key == database:
            continue
        value = after.get(key)
        if value is not None and key in before:
            check(value["mode"] == before[key]["mode"], "recovery_file_mode")
        if value is None:
            check(key in allowed_removals and before[key]["type"] == "file" and
                  before[key]["sha256"] == allowed_removals[key], "recovery_removed_file")
        elif "database" in value:
            check(key == run + "/checkpoints/graph_checkpoints.sqlite", "foreign_recovery_database")
            compare_schema(before[key]["database"], value["database"])
            for table in before[key]["database"]["tables"]:
                old_rows = row_values(before[key]["database"]["tables"][table])
                new_rows = row_values(value["database"]["tables"][table])
                check(all(row in new_rows for row in old_rows), "checkpoint_prefix")
                for row in new_rows:
                    if row in old_rows:
                        continue
                    check(table == "checkpoints" and row["checkpoint_id"] in allowed_checkpoints,
                          "original_checkpoint_identity")
                    payload = allowed_checkpoints[row["checkpoint_id"]]
                    check(row["type"] == "json" and row["checkpoint_ns"] == "" and
                          row["parent_checkpoint_id"] is None and row["checkpoint"] == canonical_bytes(payload) and
                          row["thread_id"] == payload["channel_values"]["control"]["checkpoint_thread_id"] and
                          loads(row["metadata"], canonical=False) == {"source": "input", "step": 0, "parents": {},
                              "operation_id": payload["lqcd_control_operation_id"]}, "original_checkpoint_bytes")
        elif value["type"] == "directory":
            check(before.get(key) is None and any(path.startswith(key + "/") for path in allowed_files), "recovery_directory")
        else:
            check(key in allowed_files and manifest_file(directory, manifests[2], key) in allowed_files[key], "unfrozen_recovery_file")
        if key in consumed_index_temporary:
            semantics["writes"].append({"kind": "atomic_artifact_index_consumption", "target": "artifact_index.json"})
        elif key in prefixes:
            prefix = loads(manifest_file(directory, manifests[2], key))
            semantics["writes"].append({"kind": "derived_publication_prefix", "capability_id": prefix["capability_id"],
                                       "journal_revision": prefix["journal_revision"]})
        else:
            semantics["writes"].append(key[len(root) + 1:])
    return semantics


def validate_calls(directory, records, manifests, states):
    from lqcd_agent.control.strict_json import loads
    producer, locator, root, _ = owner_location(records, manifests)
    case_id = records[0]['case_id']
    calls = records[3]['observation']['calls']
    check(type(calls) is list and calls, 'actual_calls')
    race = case_id.startswith('budget.grant_owner_race.')
    first_count = len(records[2]['observation']['calls'])
    check(first_count == (0 if race else 1) and calls[:first_count] == records[2]['observation']['calls'], 'first_call_count')
    expected_count = 4 if producer['kind'] == 'invocation' and not producer['value'].get('completion_intent') else 2
    check(len(calls) == expected_count - int(race), 'original_call_count')
    current = records[1]['observation']['host_identities']
    previous_manifest, previous_state = (manifests[2], states[2]) if race else (manifests[1], states[1])
    def passive_gap(old_manifest, new_manifest, old, new):
        allowed = prefix_additions(directory, old_manifest, new_manifest, old, new)
        adjusted = deepcopy(old)
        adjusted.update({key: new[key] for key in allowed})
        for key in allowed:
            parent = key.rsplit('/', 1)[0]
            if parent not in old:
                check(parent == key.split('/', 1)[0] + '/trace_prefix_evidence' and
                      new.get(parent, {}).get('type') == 'directory', 'prefix_directory')
                adjusted[parent] = new[parent]
        check(adjusted == new, 'call_snapshot_continuity')
    results = []
    for index, call in enumerate(calls):
        keys(call, CALL_FIELDS, 'fault_call')
        check(type(call['request']) is dict, 'call_request')
        keys(call['owner'], {'worker_id', 'capability_id', 'invocation_epoch'}, 'call_owner')
        check(call['identities_before'] == current, 'call_fixture_continuity')
        before_ids = identity_state(call['identities_before'], case_id)
        after_ids = identity_state(call['identities_after'], case_id)
        check(after_ids[:len(before_ids)] == before_ids, 'call_fixture_prefix')
        current = call['identities_after']
        snapshots, call_manifests = [], []
        for side in ('before', 'after'):
            reference = call[side + '_snapshot']
            keys(reference, {'stage', 'manifest_sha256'}, 'call_snapshot')
            name = 'call-' + str(index) + '-' + side
            check(reference['stage'] == name, 'call_snapshot_identity')
            manifest = stage_manifest(directory, {'stage': name, 'snapshot': reference})
            check(manifest['roots'] == manifests[0]['roots'], 'call_root_set')
            snapshots.append(logical_state(directory, manifest))
            call_manifests.append(manifest)
        passive_gap(previous_manifest, call_manifests[0], previous_state, snapshots[0])
        if index == first_count:
            passive_gap(manifests[2], call_manifests[0], states[2], snapshots[0])
        error = call['exception']
        if error is not None:
            keys(error, {'type', 'message'}, 'actual_exception')
            check(call['return'] is None and error['type'] == 'ControlIntegrityError' and
                  type(error['message']) is str, 'actual_rejection')
        entry, request = call['entry'], call['request']
        if producer['kind'] == 'invocation':
            value = producer['value']
            worker, epoch = value['worker_id'], value['invocation_epoch']
            if entry == 'CanonicalProductRuntime.run':
                check(index >= 2 and error is not None and request['locator'] == locator and
                      call['owner']['worker_id'] == worker, 'original_reentry')
            else:
                boundary = case_id.rsplit('.', 2)[0]
                expected = ('InvocationLeases.publish_completion' if value.get('completion_intent') else
                    'InvocationLeases.publish_started' if boundary == 'artifact.transition_before_target_started'
                    else 'ArtifactEffectPort.publish_budget')
                check(entry == expected and call['owner'] == {'worker_id': worker, 'capability_id': producer['capability_id'],
                      'invocation_epoch': epoch}, 'invocation_call_owner')
                check(request == ({} if entry == 'ArtifactEffectPort.publish_budget' else
                      {'capability_id': producer['capability_id'], 'worker_id': worker, 'epoch': epoch}), 'invocation_call_request')
                if error is None:
                    table = snapshots[1][root + '/.lqcd/control_operations.sqlite']['database']['tables']['invocation_capabilities']
                    row, = [r for r in row_values(table) if r['capability_id'] == producer['capability_id']]
                    after = loads(row['value'])
                    returned = None if entry == 'ArtifactEffectPort.publish_budget' else (
                        after['completion_intent']['projection'] if entry == 'InvocationLeases.publish_completion' else after)
                    check(call['return'] == returned, 'actual_invocation_return')
        else:
            operation = producer['value']
            expected = 'ControlPlane.resume_run' if operation['operation_type'] == 'resume_run' else 'ControlPlane.advance_run'
            check(entry == expected and call['owner'] == {'worker_id': 'product-host', 'capability_id': None,
                  'invocation_epoch': None}, 'control_call_owner')
            keys(request, {'request', 'actor'}, 'control_call')
            check(request['actor'] == {'actor_id': 'operator', 'actor_type': 'human',
                  'scopes': ['control.internal', 'resume', 'start']}, 'control_call_actor')
            original = read_value_bytes(evidence_bytes(directory, 'process-source.json'))
            expected_request = original.get('resume_request', {'run_locator': locator,
                'source_attempt_id': operation['request']['source_attempt_id'], 'idempotency_key': operation['idempotency_key']}) if expected.endswith('advance_run') else original['resume_request']
            check(request['request'] == expected_request and error is None, 'control_call_request')
            manifest = checked_json(directory / (call['after_snapshot']['stage'] + '-manifest.json'))
            with original_coordinator(directory, manifest, root) as coordinator:
                from lqcd_agent.control.interfaces import ControlPlane
                check(call['return'] == ControlPlane(coordinator, worker_id='product-host').query_operation(operation['operation_id']),
                      'actual_control_return')
        results.append({'entry': entry, 'owner': call['owner'], 'exception_type': None if error is None else error['type'],
                        'has_return_value': call['return'] is not None})
        if index >= first_count:
            adjusted = deepcopy(snapshots[0])
            if error is None and entry in ('ArtifactEffectPort.publish_budget', 'InvocationLeases.publish_started'):
                table = adjusted[root + '/.lqcd/control_operations.sqlite']['database']['tables']['invocation_capabilities']
                columns = [row[1] for row in table['columns']]
                own, = [row for row in table['rows'] if row[columns.index('capability_id')] == producer['capability_id']]
                own[columns.index('revision')] += 1
            check(adjusted == snapshots[1], 'repeat_call_exact_effect')
        previous_manifest, previous_state = call_manifests[1], snapshots[1]
        if index + 1 == first_count:
            passive_gap(previous_manifest, manifests[2], previous_state, states[2])
            previous_manifest, previous_state = manifests[2], states[2]
    passive_gap(previous_manifest, manifests[3], previous_state, states[3])
    check(current == records[3]['observation']['host_identities'], 'final_fixture_state')
    return results


def validate_stage_sources(directory, records, manifests, binding, states):
    from .trace import normalize
    normalized, facts, validated = [], [], []
    for index, stage in enumerate(STAGES):
        observation = records[index]['observation']
        name = 'before-raw.json' if stage == 'S0' else stage + '-raw.json'
        reference = observation if stage == 'S0' else observation['source']
        if stage != 'S0':
            keys(reference, {'raw_sha256', 'rejection'}, 'stage_source')
        if reference['raw_sha256'] is not None:
            raw = evidence_bytes(directory, name)
            check(sha(raw) == reference['raw_sha256'], 'stage_raw_bytes')
            source = read_value_bytes(raw)
            check(source['schema_version'] == '0.11' and source['proof']['schema_version'] == '0.8', 'stage_raw_version')
            equivalent = [result for prior_raw, prior_state, result in validated if prior_raw == raw and prior_state == states[index]]
            if equivalent:
                result = equivalent[0]
            else:
                with private_view(directory, manifests[index], resolve=True):
                    result = normalize(source, binding=binding)
                validated.append((raw, states[index], result))
            normalized.append(result)
            facts.append({'stage': stage, 'valid': True, 'rejection': None})
        else:
            check(stage != 'S0' and reference['rejection'] is not None, 'required_S0_source')
            from lqcd_agent.control.execution import parse_ledger
            from lqcd_agent.control.strict_json import ControlIntegrityError, loads
            producer, _, _, run = owner_location(records, manifests)
            if producer['kind'] == 'control' and records[0]['case_id'].endswith('.integrity_conflict'):
                try:
                    parse_ledger(manifest_file(directory, manifests[index], run + '/execution_history.jsonl'))
                except ControlIntegrityError as error:
                    rejection = {'validator': 'lqcd_agent.control.execution.parse_ledger',
                                 'type': type(error).__name__, 'message': str(error)}
                    normalized.append(None)
                    facts.append({'stage': stage, 'valid': False, 'rejection': rejection})
                    continue
            if (producer['kind'] == 'invocation' and not producer['value'].get('completion_intent') and
                    records[0]['case_id'].endswith('.integrity_conflict')):
                try:
                    loads(manifest_file(directory, manifests[index], run + '/artifact_index.json'))
                except ControlIntegrityError as error:
                    rejection = {'validator': 'lqcd_agent.control.strict_json.loads',
                                 'type': type(error).__name__, 'message': str(error)}
                    normalized.append(None)
                    facts.append({'stage': stage, 'valid': False, 'rejection': rejection})
                    continue
            fallback = directory / (stage + '-rejected-raw.json.gz')
            raw = evidence_bytes(directory, stage + '-rejected-raw.json' if fallback.exists() else 'before-raw.json')
            try:
                with private_view(directory, manifests[index], resolve=True):
                    normalize(read_value_bytes(raw), binding=binding)
            except Invalid as error:
                rejection = error.error
            else:
                raise Invalid('fault_source', 'missing_original_rejection', 'invalid_evidence')
            normalized.append(None)
            facts.append({'stage': stage, 'valid': False, 'rejection': rejection})
    return normalized, facts


def source_bundle(directory, binding, case_id):
    from .inventory import case_specs
    from lqcd_agent.control.protocol import PROTOCOL
    from .trace_proof import _binding
    check(directory == anchor_directory(binding, case_id), 'fixed_native_anchor')
    anchor, records, manifests = capture_records(directory, binding, case_id)
    specs = case_specs(PROTOCOL)
    check(case_id in specs, 'original_case')
    spec = specs[case_id]
    check(spec['failpoint_id'] in {
        'budget.resource_settled', 'budget.resource_reserved', 'budget.decision_before_resource',
        'artifact.transition_before_target_started', 'artifact.projection_publication', 'artifact.history_publication',
        'artifact.index_publication', 'artifact.bounded_state_sync', 'budget.decision_before_transition',
        'budget.grant_consumed', 'budget.grant_target_allocation', 'budget.grant_invalidation', 'budget.grant_transition',
        'budget.grant_owner_race', 'budget.terminal_reserve', 'artifact.bundle_before_analysis_transition',
        'budget.invalid_response_allow', 'budget.invalid_response_halt'}, 'original_boundary')
    request_raw, receipt_raw, process_raw = [evidence_bytes(directory, name) for name in
        ('request.json', 'receipt.json', 'process-source.json')]
    check(all(sha(raw) == anchor[key] for raw, key in zip((request_raw, receipt_raw, process_raw),
        ('process_request_sha256', 'process_receipt_sha256', 'process_source_sha256'))), 'process_original_bytes')
    request, receipt, process = [read_value_bytes(raw) for raw in (request_raw, receipt_raw, process_raw)]
    keys(request, {'schema_version', 'invocation_token', 'digests', 'project_root', 'nodeid', 'case_id',
        'process_token', 'hook_ref', 'receipt_path'}, 'original_request')
    keys(receipt, {'request', 'process_id', 'hook_ref'}, 'original_receipt')
    from .contracts import ROOT
    from .trace_proof import sha_value
    sha_value(request['process_token'], 'original_process_nonce')
    check(Path(request['receipt_path']).name == request['process_token'] + '.json', 'original_receipt_name')
    check(request['schema_version'] == '0.1' and request['project_root'] == str(ROOT) and request['nodeid'] == anchor['nodeid'] and
          request['case_id'] == case_id and request['hook_ref'] == 'src/lqcd_agent/control/coordinator.py:boundary' and
          receipt == {'request': request, 'process_id': process['process_id'], 'hook_ref': request['hook_ref']} and
          process['process_id'] == records[0]['child_pid'] and process['case_id'] == case_id, 'process_origin')
    _binding({key: request[key] for key in ('invocation_token', 'digests')}, binding)
    _binding(process['binding'], binding)
    check(checked_json(Path(request['receipt_path'])) == receipt and
          sha(Path(request['receipt_path']).read_bytes()) == anchor['process_receipt_sha256'], 'live_receipt')
    source = read_value_bytes(evidence_bytes(directory, 'before-raw.json'))
    check(source_roots(source, process) == manifests[0]['roots'], 'complete_source_roots')
    original = evidence_bytes(directory, 'original-before-raw.json')
    check((Path(request['receipt_path']).parent / 'before-raw.json').read_bytes() == original, 'original_before_bytes')
    old = read_value_bytes(original)
    upgraded = deepcopy(old)
    upgraded['schema_version'] = '0.11'
    upgraded['proof'].update(schema_version='0.8', unconsumed_code_sources=[])
    check(source == upgraded, 'original_S0_upgrade')
    states = [logical_state(directory, manifest) for manifest in manifests]
    producer, locator, root, _ = owner_location(records, manifests)
    check(manifest_file(directory, manifests[0], root + '/.lqcd/control_operations.sqlite'), 'S0_database')
    from lqcd_agent.control.strict_json import loads
    tables = states[0][root + '/.lqcd/control_operations.sqlite']['database']['tables']
    with original_coordinator(directory, manifests[0], root) as coordinator:
        if producer['kind'] == 'control':
            keys(producer, {'kind', 'value'}, 'original_control')
            check(coordinator.get(process['operation_id']) == producer['value'], 'original_control_preimage')
        else:
            keys(producer, {'kind', 'capability_id', 'revision', 'value', 'operation'}, 'original_invocation')
            row, = [row for row in row_values(tables['invocation_capabilities']) if row['capability_id'] == producer['capability_id']]
            check(row['revision'] == producer['revision'] and loads(row['value']) == producer['value'] and
                  coordinator.get(producer['value']['authorization']['producer_operation_id']) == producer['operation'] and
                  process['locator'] == locator, 'original_invocation_preimage')
    check((Path(next(row['path'] for row in manifests[0]['roots'] if row['id'] == root)) /
           'process-source.json').read_bytes() == process_raw, 'live_process_source')
    registered = {(row['value'].get('case_id'), row['value'].get('run_id'), row['value'].get('attempt_id'))
        for row in source['proof']['objects'] if row['value'].get('event') == 'registered' and row['value'].get('slot') == 'code'}
    for row in row_values(tables['external_operations']):
        value = loads(row['value'])
        identity = value['run_locator']['case_id'], value['run_locator']['run_id'], value['attempt_id']
        check(value['terminal_evidence_digest'] is None or value['consumption_release'] is not None or identity in registered,
              'original_empty_unconsumed')
    check(live_state(manifests[-1]['roots'], request) == states[-1], 'S3_live_durable')
    fault = fault_difference(directory, records, manifests, states, spec)
    stages, stage_facts = validate_stage_sources(directory, records, manifests, binding, states)
    calls = validate_calls(directory, records, manifests, states)
    recovery = recovery_difference(directory, records, manifests, states, spec)
    repeated = verify_repeat(directory, records, manifests)
    producer, _, root, _ = owner_location(records, manifests)
    before_operations = row_values(states[0][root + '/.lqcd/control_operations.sqlite']['database']['tables']['control_operations'])
    after_operations = row_values(states[3][root + '/.lqcd/control_operations.sqlite']['database']['tables']['control_operations'])
    original_ids = {row['operation_id'] for row in before_operations}
    new_ids = {row['operation_id'] for row in after_operations} - original_ids
    allocations = records[3]['observation']['host_identities']['allocations']
    check(new_ids == {'control_' + row['uuid'].replace('-', '') for row in allocations
          if row['allocation_site'] == 'lqcd_agent.control.coordinator'}, 'actual_host_allocations')
    return {'source': source, 'declaration': declaration(directory, records, manifests, fault),
            'stages': stages, 'stage_facts': stage_facts, 'calls': calls, 'recovery': recovery, 'repeat': repeated,
            'spec': spec, 'allocations': allocations}


def project(events, proof, binding):
    from .unconsumed_code_final_trace import FIELDS
    from .trace_proof import _binding
    from .trace import event
    from .strict_json import digest
    try:
        keys(proof, FIELDS | {'fault_sources'}, 'fault_proof')
        check(proof['schema_version'] == '0.9' and type(proof['fault_sources']) is list and len(proof['fault_sources']) == 1,
              'fault_proof_version')
        _binding(proof['binding'], binding)
        declaration_value = proof['fault_sources'][0]
        keys(declaration_value, DECLARATION_FIELDS, 'fault_declaration')
        case_id = declaration_value['case_id']
        directory = anchor_directory(binding, case_id)
        _, records, manifests = capture_records(directory, binding, case_id)
        from .inventory import case_specs
        from lqcd_agent.control.protocol import PROTOCOL
        check(case_id in case_specs(PROTOCOL), 'original_case')
        states = [logical_state(directory, manifest) for manifest in manifests[:2]]
        original_fault = fault_difference(directory, records, manifests, states, case_specs(PROTOCOL)[case_id])
        check(declaration_value == declaration(directory, records, manifests, original_fault), 'original_capture_declaration')
        source = read_value_bytes(evidence_bytes(directory, 'before-raw.json'))
        base = {key: deepcopy(value) for key, value in proof.items() if key != 'fault_sources'}
        base['schema_version'] = '0.8'
        check(base == source['proof'] and events ==
              [{key: value for key, value in row.items() if key != 'ephemeral'} for row in source['events']], 'original_capture_trace')
        bundle = source_bundle(directory, binding, case_id)
        result = list(bundle['stages'][0]['events'])
        for stage, normalized, fact in zip(STAGES, bundle['stages'], bundle['stage_facts']):
            result.append(event('fault_source_stage', target=case_id, stage=stage,
                outcome='valid_original_source' if normalized is not None else 'original_source_rejected',
                result_digest='semantic_sha256:' + digest(normalized if normalized is not None else fact)))
        result.append(event('fault_source_recovery', target=case_id, outcome=declaration_value['outcome'],
            guard=declaration_value['fault_observation']['kind'], invariants=sorted(bundle['spec']['invariants']),
            result_digest='semantic_sha256:' + digest({'calls': bundle['calls'], 'recovery': bundle['recovery'],
                                                     'repeat': bundle['repeat'], 'allocations': bundle['allocations']})))
        for target in declaration_value['fault_observation']['targets']:
            semantic = {key: value for key, value in target.items() if key not in ('before', 'after')}
            semantic['before'] = digest(bundle['stages'][0])
            if declaration_value['fault_observation']['kind'] == 'file_corruption' and target['path'].endswith('/execution_history.jsonl'):
                # The independently checked original action appends exactly one
                # byte to the verified ledger; its physical roots stay in proof.
                semantic['after'] = {'kind': 'append_to_verified_before', 'suffix_sha256': sha(b'{'), 'suffix_size': 1}
            else:
                semantic['after'] = target['after']
            result.append(event('fault_source_injection', target=case_id, guard=declaration_value['fault_observation']['kind'],
                                result_digest='semantic_sha256:' + digest(semantic)))
        return result
    except Invalid:
        raise
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, StopIteration, RecursionError) as error:
        raise Invalid('fault_source', 'provenance', 'invalid_evidence') from error
