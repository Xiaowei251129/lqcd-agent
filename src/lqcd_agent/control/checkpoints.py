"""Per-Run LangGraph persistence, subordinate to a held coordinator fence."""
from lqcd_agent.control.storage import execution_scratch_root
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from langgraph.checkpoint.base import LATEST_VERSION
from langgraph.checkpoint.sqlite import SqliteSaver

from .coordinator import boundary, exclusive_directory, read_regular, sync_directory
from .strict_json import canonical_bytes, digest, loads, require


class CanonicalCheckpointSerializer:
    """Only JSON values are allowed; checkpoint reads never import user types."""

    def dumps_typed(self, value):
        return "json", canonical_bytes(value)

    def loads_typed(self, value):
        kind, data = value
        require(kind == "json", "Unsupported checkpoint serializer")
        return loads(data)


def checkpoint_payload(checkpoint_id, projection, timestamp, *, operation_id):
    """Freeze checkpoint identity, timestamp and state before any publication."""
    return {"v": LATEST_VERSION, "id": checkpoint_id,
            "ts": datetime.fromtimestamp(timestamp.wall_seconds, timezone.utc).isoformat(),
            "channel_values": {"control": projection.value},
            "channel_versions": {"control": 1}, "versions_seen": {}, "pending_sends": [],
            "updated_channels": ["control"], "lqcd_control_operation_id": operation_id}


def persist_checkpoint(coordinator, db, operation, run_root, payload, metadata):
    """Create or verify an exact checkpoint, never replace an existing snapshot."""
    require(db is coordinator.connection and db.in_transaction, "Checkpoint requires coordinator writer authority")
    coordinator.fence(db, operation["operation_id"], operation["worker_owner_id"],
                      operation["lease_epoch"], operation["phase_revision"])
    return _persist_checkpoint(coordinator, operation, run_root, payload, metadata)


def persist_invocation_checkpoint(coordinator, db, capability_id, worker_id, epoch, run_root, payload, metadata, *, preparation_adapter=None):
    """Publish an owned completion checkpoint under the independent invocation lease."""
    from .capabilities import InvocationLeases
    require(db is coordinator.connection and db.in_transaction, "Checkpoint requires coordinator writer authority")
    leases = InvocationLeases(coordinator, preparation_adapter=preparation_adapter)
    _, value, root, _ = leases._fence(db, capability_id, worker_id, epoch)
    require(root == run_root and value["state"] == "started" and value.get("completion_intent") is not None,
            "Missing owned invocation completion")
    producer = coordinator.get(value["authorization"]["producer_operation_id"], db=db)
    result = _persist_checkpoint(coordinator, producer, run_root, payload, metadata)
    leases._fence(db, capability_id, worker_id, epoch)
    return result


def _persist_checkpoint(coordinator, operation, run_root, payload, metadata):
    """Write only after one of the two explicit coordinator authority checks."""
    root = Path(run_root)
    require(root == root.resolve() and root.is_relative_to(coordinator.root) and root != coordinator.root,
            "Checkpoint escaped managed Run")
    folder = root / "checkpoints"
    exclusive_directory(folder)
    path = folder / "graph_checkpoints.sqlite"
    require(not path.is_symlink(), "Checkpoint path is a symlink")
    if path.exists():
        read_regular(path)
    state = payload["channel_values"]["control"]
    require(root.name == state["run_id"] and root.parent.name == state["case_id"], "Checkpoint Run binding mismatch")
    connection = sqlite3.connect(path)
    try:
        require(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal",
                "Checkpoint WAL unavailable")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        require(connection.execute("PRAGMA synchronous").fetchone()[0] == 2 and
                connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1, "Checkpoint durability profile unavailable")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(tables <= {"checkpoints", "writes"} and not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') OR "
            "(type='index' AND name NOT LIKE 'sqlite_autoindex_%')").fetchone(), "Unknown checkpoint schema object")
        saver = SqliteSaver(connection, serde=CanonicalCheckpointSerializer())
        saver.setup()
        require(not connection.execute("SELECT 1 FROM checkpoints WHERE thread_id != ? OR checkpoint_ns != ''",
                                       (state["checkpoint_thread_id"],)).fetchone(), "Foreign checkpoint owner")
        config = {"configurable": {"thread_id": state["checkpoint_thread_id"], "checkpoint_ns": "",
                                   "checkpoint_id": payload["id"]}}
        previous = saver.get_tuple(config)
        boundary(coordinator.observer, "checkpoint.sqlite_commit", "before", operation)
        if previous is None:
            write_config = {"configurable": {"thread_id": state["checkpoint_thread_id"], "checkpoint_ns": ""}}
            saver.put(write_config, payload, metadata, payload["channel_versions"])
        current = saver.get_tuple(config)
        require(current is not None and canonical_bytes(current.checkpoint) == canonical_bytes(payload) and
                canonical_bytes(current.metadata) == canonical_bytes(metadata) and not current.pending_writes and
                current.parent_config is None, "Checkpoint bytes or binding conflict")
        boundary(coordinator.observer, "checkpoint.sqlite_commit", "after", operation)
    finally:
        connection.close()
    sync_directory(folder)
    boundary(coordinator.observer, "checkpoint.directory_sync", "after", operation)
    return digest(payload)


def verify_checkpoint(run_root, manifest):
    """Read an exact persisted checkpoint without setup, writes, or lease changes."""
    path = Path(run_root) / "checkpoints/graph_checkpoints.sqlite"
    require(path.is_file() and not path.is_symlink(), "Missing durable checkpoint")
    read_regular(path)
    control = Path(run_root).parent.parent / ".lqcd"
    if control.exists() or control.is_symlink():
        from .storage import require_host_binding
        require_host_binding(control)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        raw_metadata = connection.execute("SELECT metadata FROM checkpoints WHERE thread_id=? AND checkpoint_ns='' AND checkpoint_id=?",
                                          (manifest["checkpoint_thread_id"], manifest["checkpoint_id"])).fetchone()
        require(raw_metadata is not None, "Missing exact checkpoint")
        # SqliteSaver owns metadata whitespace, but duplicate keys remain invalid.
        metadata = loads(raw_metadata[0], canonical=False)
        saver = SqliteSaver(connection, serde=CanonicalCheckpointSerializer())
        saver.is_setup = True
        current = saver.get_tuple({"configurable": {"thread_id": manifest["checkpoint_thread_id"],
                                                    "checkpoint_ns": "", "checkpoint_id": manifest["checkpoint_id"]}})
        require(current is not None and not current.pending_writes and
                digest(current.checkpoint) == manifest["checkpoint_digest"], "Checkpoint digest mismatch")
        require(metadata == {"source": "input", "step": 0, "parents": {},
                             "operation_id": current.checkpoint["lqcd_control_operation_id"]},
                "Checkpoint producer metadata mismatch")
        state = current.checkpoint["channel_values"]["control"]
        require(digest(state) == manifest["state_digest"] and
                state["execution_head"] == manifest["execution_head"] and
                state["artifact_head"] == manifest["artifact_head"], "Checkpoint authority heads mismatch")
        return state
    finally:
        connection.close()


def verify_source_checkpoint(coordinator, db, run_root, manifest):
    """Read a stable checkpoint durability unit without touching source sidecars.

    SQLite mode=ro can create or update SHM; immutable=1 ignores live WAL.
    All checkpoint writers share the held coordinator transaction. Copy the
    complete stable unit for read-only verification, then recheck source bytes.
    This temporary reader copy is never a coordinator or mutation authority.
    """
    import tempfile
    require(db is coordinator.connection and db.in_transaction, "Source checkpoint requires the coordinator snapshot lock")
    root = Path(run_root)
    require(root == root.resolve() and root.is_relative_to(coordinator.root), "Source checkpoint escaped Run")
    directory = root / "checkpoints"
    names = ("graph_checkpoints.sqlite", "graph_checkpoints.sqlite-wal", "graph_checkpoints.sqlite-shm")
    frozen = {name: read_regular(directory / name) if (directory / name).exists() else None for name in names}
    require(frozen[names[0]] is not None, "Missing source checkpoint database")
    with tempfile.TemporaryDirectory(prefix="lqcd-agent-checkpoint-read-", dir=execution_scratch_root()) as temporary:
        copy_root = Path(temporary)
        (copy_root / "checkpoints").mkdir()
        for name, content in frozen.items():
            if content is not None:
                (copy_root / "checkpoints" / name).write_bytes(content)
        result = verify_checkpoint(copy_root, manifest)
        current = {name: read_regular(directory / name) if (directory / name).exists() else None for name in names}
        require(current == frozen, "Source checkpoint changed during its snapshot")
        return result
