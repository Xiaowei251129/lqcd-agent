"""Read-only 0.4 cross-head adapter over the existing A03 registry authority."""
from pathlib import Path

from lqcd_agent.artifacts import registry

from .budget import validate_policy
from .execution import parse_ledger
from .projections import attach_checkpoint, bounded_projection, validate_projection
from .strict_json import ControlIntegrityError, ValidatedValue, closed, digest, loads, number, require


def artifact_binding(record, *, previous_artifact_head, execution_head):
    """Pure encoding of an A03 event's 0.4 cross-head envelope, not publication."""
    require(type(record) is dict and not {"execution_head", "previous_artifact_head"}.intersection(record),
            "Artifact binding may be assigned only once")
    from .strict_json import digest_value
    digest_value(previous_artifact_head, nullable=True)
    digest_value(execution_head)
    return ValidatedValue.from_value({**record, "previous_artifact_head": previous_artifact_head,
                                     "execution_head": execution_head})


def _validate(root, *, manifest, projection, advanced=False, pending_index=None):
    root = Path(root).resolve(strict=True)
    require(root.is_dir(), "Explicit Run root is not a directory")
    paths = {name: root / name for name in ("execution_history.jsonl", "artifact_history.jsonl",
                                           "artifact_index.json", "budget_policy.json")}
    require(all(path.is_file() and path.resolve().parent == root for path in paths.values()),
            "Missing or escaped control artifact")
    original = {name: path.read_bytes() for name, path in paths.items()}
    execution = parse_ledger(original["execution_history.jsonl"])
    records = execution.values
    require(execution.projection.value["run_status"] != "initializing", "Bootstrap publication is incomplete")
    transition_ids = {record["transition_id"] for record in records if record["record_type"] == "transition"}
    for record in records:
        if record["record_type"] == "budget" and record["event"] == "grant_consumed":
            require(record["payload"]["transition_id"] in transition_ids, "Grant/Transition publication is incomplete")
    require(records[0]["canonical_output_root"] == str(root), "Run root identity mismatch")
    saved_policy = validate_policy(loads(original["budget_policy.json"]))
    require(saved_policy.value["policy_digest"] == records[0]["policy_digest"], "Policy file binding mismatch")
    raw_history = original["artifact_history.jsonl"]
    require(not raw_history or raw_history.endswith(b"\n"), "Partial artifact history line")
    history = [loads(line) for line in raw_history[:-1].split(b"\n")] if raw_history else []
    index = loads(original["artifact_index.json"])
    if pending_index is not None:
        require({k: v for k, v in index.items() if k != "execution_head"} ==
                {k: v for k, v in pending_index.items() if k != "execution_head"},
                "Pending Pause publication changed artifact authority")
        index = pending_index
    closed(index, ("schema_version", "run_id", "case_id", "revision", "last_event_id", "current",
                   "managed_projections", "execution_head", "artifact_head"))
    number(index["revision"], integer=True)
    execution_positions = {digest(record): position for position, record in enumerate(records, 1)}
    artifact_heads = [None]
    previous_execution_position = 0
    for position, record in enumerate(history, 1):
        require(record.get("event_index") == position and type(record["event_index"]) is int,
                "Artifact event index gap or wrong type")
        require(record.get("previous_artifact_head") == artifact_heads[-1] and "previous_artifact_head" in record,
                "Artifact hash chain mismatch")
        require(record.get("execution_head") in execution_positions, "Artifact references unknown execution head")
        execution_position = execution_positions[record["execution_head"]]
        require(execution_position >= previous_execution_position, "Artifact execution binding rollback")
        previous_execution_position = execution_position
        artifact_heads.append(digest(record))
    for position, record in enumerate(records, 1):
        revision = record["artifact_event_index"]
        require(revision < len(artifact_heads) and record["artifact_head"] == artifact_heads[revision],
                "Execution references missing or conflicting artifact head")
        if revision:
            require(execution_positions[history[revision - 1]["execution_head"]] < position,
                    "Artifact/execution publication cycle")
        if revision < len(history):
            require(execution_positions[history[revision]["execution_head"]] >= position,
                    "Execution record rolls back already-published artifact head")
    head = execution.projection.value["execution_head"]
    require(index["execution_head"] == head and index["artifact_head"] == artifact_heads[-1],
            "Artifact index cross-head mismatch")
    require(records[-1]["artifact_head"] == artifact_heads[-1] and records[-1]["artifact_event_index"] == len(history),
            "Incomplete execution/artifact publication closure")
    core = bounded_projection(execution, artifact_index=index, artifact_head=artifact_heads[-1], artifact_event_index=len(history))
    state = {**core.value, "output_dir": str(root), "execution_history_path": str(paths["execution_history.jsonl"]),
             "artifact_history_path": str(paths["artifact_history.jsonl"]), "artifact_index_path": str(paths["artifact_index.json"])}
    # The established bidirectional A03 checks retain every invalidation and
    # protected-snapshot rule, with no pending-publication exception enabled.
    if not any(record["record_type"] == "cycle" for record in records):
        # A failed pre-Cycle bootstrap has no A03 producer or artifact namespace.
        require(records[-1]["record_type"] == "run_lifecycle" and records[-1]["from_status"] == "initializing" and
                records[-1]["to_status"] == "failed" and
                all(record["record_type"] in ("run", "lineage", "budget") for record in records[:-1]),
                "Cycle-free Run is not a failed bootstrap")
        require(not history and index["schema_version"] == registry.ARTIFACT_SCHEMA_VERSION and
                index["run_id"] == records[0]["run_id"] and index["case_id"] == records[0]["case_id"] and
                index["revision"] == 0 and index["last_event_id"] is None and
                index["current"] == dict.fromkeys(registry.ARTIFACT_SLOTS) and index["managed_projections"] == {},
                "Failed pre-Cycle bootstrap has artifact state")
    else:
        registry.validate_state_artifacts(state)
    if advanced:
        from .checkpoints import verify_checkpoint
        from .execution import replay
        old = verify_checkpoint(root, manifest)
        count = manifest["execution_event_index"]
        require(type(count) is int and 1 <= count < len(records) and digest(records[count - 1]) == manifest["execution_head"],
                "Transition does not extend its immutable checkpoint anchor")
        anchored_execution = replay(records[:count])
        anchored_index = {"run_id": old["run_id"], "case_id": old["case_id"], "current": old["current_artifacts"]}
        anchored_core = bounded_projection(anchored_execution, artifact_index=anchored_index,
                                          artifact_head=old["artifact_head"], artifact_event_index=old["artifact_event_index"])
        require(anchored_core.value == old, "Checkpoint prefix state does not replay")
        attach_checkpoint(anchored_core, anchored_execution, manifest)
        require(core.value["run_status"] == "running" or pending_index is not None and
                core.value["run_status"] == "paused" and core.value.get("pending_pause") is not None,
                "Only an owned Transition or prepared Pause may extend a checkpoint anchor")
        expected = ValidatedValue.from_value({**core.value, "checkpoint_head": manifest["checkpoint_head"]})
    else:
        expected = attach_checkpoint(core, execution, manifest)
    if projection is not None:
        validate_projection(projection, expected)
    require(all(path.read_bytes() == original[name] for name, path in paths.items()), "Control inputs changed during validation")
    return expected


def validate_run_root(root, *, manifest, projection=None):
    """Validate an explicit 0.4 root, without scanning, repairing or migrating."""
    try:
        return _validate(root, manifest=manifest, projection=projection)
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        raise ControlIntegrityError(str(error)) from error


def validate_advanced_run_root(root, *, manifest, projection):
    """Read-only exact current heads with a verified older checkpoint anchor.

    This does not create a checkpoint or grant authority. Control callers must
    additionally prove the exact suffix belongs to their coordinator operation.
    """
    try:
        require(projection is not None, "Advanced root needs its exact owned projection")
        return _validate(root, manifest=manifest, projection=projection, advanced=True)
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        raise ControlIntegrityError(str(error)) from error


def validate_control_root(coordinator, db, locator, control):
    """Validate a coordinator-owned stable checkpoint or committed Transition suffix."""
    from .coordinator import read_regular
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    if control.get("checkpoint_anchor_kind") not in ("owned_transition", "external_prestart"):
        return validate_run_root(root, manifest=control["manifest"], projection=control["projection"])
    operation = coordinator.get(control["transition_owner"], db=db)
    require(operation["operation_type"] == "advance_run" and operation["status"] == "committed", "Uncommitted Transition anchor")
    snapshot = coordinator.snapshot(operation["operation_id"], db=db)
    records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
    expected_records = snapshot["records"]
    if control["checkpoint_anchor_kind"] == "external_prestart":
        from .operations import ExternalControl
        external = ExternalControl(coordinator).read(db, control["external_owner"])
        require(external["run_locator"] == locator and external["parent_control_operation_id"] == operation["operation_id"] and
                len(records) == len(expected_records) + 1 and records[:-1] == expected_records, "External source prefix changed")
        reservation = records[-1]
        require(reservation["record_type"] == "budget" and reservation["event"] == "resource_reserved" and
                digest(reservation) == external["reservation_digest"] and reservation["payload"]["producer_operation_id"] == external["producer_operation_id"] and
                reservation["payload"]["attempt_id"] == external["attempt_id"] == snapshot["projection"]["attempt_id"], "External reservation source mismatch")
        require(snapshot["manifest"] == control["manifest"], "External preparation replaced checkpoint")
        return validate_advanced_run_root(root, manifest=control["manifest"], projection=control["projection"])
    require(snapshot["run_locator"] == locator and snapshot["projection"] == control["projection"] and
            snapshot["manifest"] == control["manifest"] and records == expected_records,
            "Current head is not the committed advance's exact owned suffix")
    return validate_advanced_run_root(root, manifest=control["manifest"], projection=control["projection"])


def validate_prepared_pause_root(coordinator, db, locator, control, pause):
    """Read an exact frozen publication prefix without promoting it to opened."""
    from hashlib import sha256
    from .coordinator import read_regular
    from .strict_json import canonical_bytes

    root = coordinator.root / locator["case_id"] / locator["run_id"]
    row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?",
                     (digest(locator), pause["pause_id"])).fetchone()
    publisher = coordinator.get(pause["operation_id"], db=db)
    require(row is not None or publisher["phase"] == "operation_reserved", "Prepared Pause lost publication ownership")
    ownership = loads(row[0]) if row is not None else {"owner": None, "status": "prepared", "publication_owner": publisher["operation_id"]}
    require(ownership["owner"] is None and ownership["status"] == "prepared" and
            ownership["publication_owner"] == publisher["operation_id"] and publisher["operation_type"] == "publish_pause" and publisher["status"] == "in_progress" and
            publisher["request"]["run_locator"] == locator and pause["operation_id"] == publisher["operation_id"],
            "Prepared Pause publisher or ownership mismatch")
    snapshot = coordinator.snapshot(publisher["operation_id"], db=db)
    raw = read_regular(root / "execution_history.jsonl")
    publications = db.execute("SELECT content,content_digest FROM control_publications WHERE operation_id=? AND path=?",
                              (publisher["operation_id"], str(root / "execution_history.jsonl"))).fetchall()
    require(any(item["content"] == raw and sha256(raw).hexdigest() == item["content_digest"] for item in publications),
            "Prepared Pause is not an exact frozen publication")
    records = parse_ledger(raw).values
    source = snapshot["source"]["records"]
    require(records[:len(source)] == source and len(source) < len(records) <= len(source) + 2 and
            records[len(source)] == pause and pause["status"] == "prepared", "Unexpected prepared publication suffix")
    if len(records) == len(source) + 2:
        life = records[-1]
        require(life["record_type"] == "run_lifecycle" and life["operation_id"] == publisher["operation_id"] and
                life["pause_id"] == pause["pause_id"] and life["from_status"] == "running" and life["to_status"] == "paused",
                "Foreign lifecycle after prepared Pause")
    index = loads(read_regular(root / "artifact_index.json"))
    allowed_indexes = [snapshot["source"]["index"], {**snapshot["source"]["index"], "execution_head": digest(pause)}]
    require(index in allowed_indexes, "Prepared Pause index escaped publication closure")
    require(control["manifest"]["checkpoint_head"] == publisher["request"]["source_heads"]["checkpoint_head"],
            "Prepared Pause checkpoint anchor changed")
    require(read_regular(root / "budget_policy.json") == canonical_bytes(next(
        r["payload"]["policy"] for r in source if r["record_type"] == "budget" and r["event"] == "policy_initialized")),
        "Prepared Pause policy changed")
    return _validate(root, manifest=control["manifest"], projection=None, advanced=True,
                     pending_index={**index, "execution_head": digest(records[-1])})


def validate_owned_resume_prefix(coordinator, db, operation):
    """Validate a frozen resume prefix for failure disposition, never execution."""
    from .checkpoints import verify_checkpoint
    from .clock import Timestamp
    from .coordinator import read_regular
    from .operations import checkpoint_snapshot
    from .strict_json import canonical_bytes

    locator = operation["request"]["run_locator"]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    snapshot = coordinator.snapshot(operation["operation_id"], db=db)
    control = loads(db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()[0])
    verify_checkpoint(root, control["manifest"])
    source = snapshot["source"]
    prefix = b"".join(canonical_bytes(r) + b"\n" for r in source["records"])
    ledgers, indexes = [prefix], [canonical_bytes(source["index"])]
    for row in db.execute("SELECT path,content,content_digest FROM control_publications WHERE operation_id=?", (operation["operation_id"],)):
        from hashlib import sha256
        require(sha256(row["content"]).hexdigest() == row["content_digest"], "Corrupt resume publication authority")
        if row["path"] == str(root / "execution_history.jsonl"):
            ledgers.append(row["content"])
        if row["path"] == str(root / "artifact_index.json"):
            indexes.append(row["content"])
    capability = db.execute("SELECT value FROM invocation_capabilities WHERE capability_id=?", ("capability_" + operation["operation_id"],)).fetchone()
    if capability is not None:
        value = loads(capability[0])
        require(value["authorization"]["producer_operation_id"] == operation["operation_id"] and
                value["authorization_digest"] == digest(value["authorization"]), "Corrupt resume capability authority")
        if value.get("verification_intents"):
            from lqcd_agent.code_agent.verification_resources import owned_prefix
            owned_prefix(value, published=False)
            for intent in value["verification_intents"]:
                ledgers.append(intent["content"].encode())
                indexes.append(intent["index"].encode())
        for name in ("started_intent", "completion_intent"):
            intent = value.get(name)
            if intent is not None:
                ledgers.append(intent["content"].encode())
                indexes.append(intent["index"].encode())
    raw, raw_index = read_regular(root / "execution_history.jsonl"), read_regular(root / "artifact_index.json")
    require(raw.startswith(prefix) and any(candidate.startswith(raw) for candidate in ledgers) and raw_index in indexes,
            "Resume prefix is outside its frozen publications")
    records, index = parse_ledger(raw).values, loads(raw_index)
    require(read_regular(root / "budget_policy.json") == canonical_bytes(snapshot["original_policy"]), "Resume policy changed")
    virtual = checkpoint_snapshot(records, index, operation, "failure_validation", Timestamp(**records[-1]["created_at"]))
    state = _validate(root, manifest=virtual["manifest"], projection=None, pending_index=virtual["artifact_index"]).value
    state = {**state, "checkpoint_head": control["manifest"]["checkpoint_head"]}
    require(state["run_status"] in ("running", "paused"), "Failure source is not an active Run")
    return {"records": records, "index": index, "state": state, "manifest": control["manifest"],
            "artifact_history": read_regular(root / "artifact_history.jsonl").decode(), "policy": snapshot["original_policy"]}
