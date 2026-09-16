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


def _validate(root, *, manifest, projection):
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
    registry.validate_state_artifacts(state)
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
