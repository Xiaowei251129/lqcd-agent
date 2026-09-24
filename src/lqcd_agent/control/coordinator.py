"""B02 work-in-progress SQLite coordinator primitives, not a public control API.

The operation journal owns reservations, leases and results, not Run history.
Only trusted control implementations may use this module. The macOS reference
preflight and bootstrap primitives exist; complete operation handlers and B02
runtime acceptance are not yet delivered.
"""
from contextlib import contextmanager
from dataclasses import asdict
import ctypes
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import uuid

from .clock import HostClock
from .protocol import PROTOCOL_SHA256, operation_variant
from .strict_json import ControlIntegrityError, canonical_bytes, digest, loads, number, require, text


class MaterializationSnapshotError(ControlIntegrityError):
    """A missing or corrupt frozen plan, distinct from a rejected worker fence."""

    def __init__(self, operation_id, *, missing):
        self.operation_id, self.missing = operation_id, missing
        super().__init__("Missing operation materialization snapshot" if missing else "Operation materialization snapshot changed")


SCHEMA_VERSION = 2
TABLES = {
    "control_metadata": "key TEXT PRIMARY KEY, value TEXT NOT NULL",
    "control_operations": (
        "operation_id TEXT PRIMARY KEY, idempotency_scope TEXT NOT NULL, idempotency_key TEXT NOT NULL, "
        "request_digest TEXT NOT NULL, operation_type TEXT NOT NULL, operation_variant TEXT NOT NULL, "
        "status TEXT NOT NULL, phase TEXT NOT NULL, phase_revision INTEGER NOT NULL, "
        "worker_owner_id TEXT NOT NULL, lease_epoch INTEGER NOT NULL, lease_expires REAL NOT NULL, "
        "request BLOB NOT NULL, reservation BLOB NOT NULL, result BLOB, error BLOB, "
        "created_at BLOB NOT NULL, updated_at BLOB NOT NULL, "
        "UNIQUE(idempotency_scope, idempotency_key)"
    ),
    "control_phases": (
        "operation_id TEXT NOT NULL REFERENCES control_operations(operation_id), revision INTEGER NOT NULL, "
        "phase TEXT NOT NULL, lease_epoch INTEGER NOT NULL, evidence BLOB NOT NULL, branch BLOB NOT NULL, "
        "PRIMARY KEY(operation_id, revision)"
    ),
    "control_publications": (
        "operation_id TEXT NOT NULL REFERENCES control_operations(operation_id), phase TEXT NOT NULL, "
        "path TEXT NOT NULL, previous BLOB, content BLOB NOT NULL, content_digest TEXT NOT NULL, "
        "producing_epoch INTEGER NOT NULL, producing_revision INTEGER NOT NULL, "
        "PRIMARY KEY(operation_id, phase, path, producing_epoch)"
    ),
    "control_snapshots": (
        "operation_id TEXT PRIMARY KEY REFERENCES control_operations(operation_id), "
        "value BLOB NOT NULL, value_digest TEXT NOT NULL"
    ),
    "run_controls": "run_key TEXT PRIMARY KEY, revision INTEGER NOT NULL, value BLOB NOT NULL",
    "pause_ownership": (
        "run_key TEXT NOT NULL REFERENCES run_controls(run_key), pause_id TEXT NOT NULL, "
        "revision INTEGER NOT NULL, value BLOB NOT NULL, PRIMARY KEY(run_key, pause_id)"
    ),
    "run_terminal_closure": (
        "run_key TEXT PRIMARY KEY REFERENCES run_controls(run_key), revision INTEGER NOT NULL, value BLOB NOT NULL"
    ),
    "external_operations": (
        "external_operation_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, value BLOB NOT NULL"
    ),
    "invocation_capabilities": (
        "capability_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, value BLOB NOT NULL"
    ),
}


def boundary(observer, name, side, value=None):
    """Expose a real production boundary without taking authority from an observer."""
    if observer is not None:
        for hook in getattr(observer, "production_hooks", {}).get((name, side), ()):
            hook()
        observer(name, side, value)


def component(value):
    text(value)
    require(value not in (".", "..") and not any(c in value for c in ("/", "\\", "\0")),
            "Invalid managed path component")
    require(not value.startswith("."), "Reserved managed path component")
    return value


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def local_filesystem(path):
    """Verify the local mount of the macOS reference durability profile.

    The ABI and MNT_LOCAL flag are defined by Darwin sys/mount.h. Unknown
    platforms fail closed; successful SQLite pragmas alone do not prove a
    local filesystem or a supported durability profile.
    """
    require(sys.platform == "darwin", "Unverified platform durability profile")

    class StatFS(ctypes.Structure):
        _fields_ = [
            ("block_size", ctypes.c_uint32), ("io_size", ctypes.c_int32),
            ("blocks", ctypes.c_uint64), ("free_blocks", ctypes.c_uint64),
            ("available_blocks", ctypes.c_uint64), ("files", ctypes.c_uint64),
            ("free_files", ctypes.c_uint64), ("fsid", ctypes.c_int32 * 2),
            ("owner", ctypes.c_uint32), ("type", ctypes.c_uint32),
            ("flags", ctypes.c_uint32), ("subtype", ctypes.c_uint32),
            ("type_name", ctypes.c_char * 16), ("mount_point", ctypes.c_char * 1024),
            ("mount_source", ctypes.c_char * 1024), ("extended_flags", ctypes.c_uint32),
            ("reserved", ctypes.c_uint32 * 7),
        ]

    library = ctypes.CDLL(None, use_errno=True)
    inspect = library.statfs64
    inspect.argtypes, inspect.restype = [ctypes.c_char_p, ctypes.POINTER(StatFS)], ctypes.c_int
    info = StatFS()
    if inspect(os.fsencode(path), ctypes.byref(info)) != 0:
        raise OSError(ctypes.get_errno(), "Cannot verify control filesystem")
    require(info.flags & 0x00001000 and not info.flags & 0x00000001,
            "Control requires a writable local filesystem")
    return info.type_name.decode("ascii")


def durability_preflight(control, observer=None):
    """Exercise file sync, directory sync and same-directory atomic replacement."""
    filesystem = local_filesystem(control)
    with tempfile.TemporaryDirectory(prefix="durability-", dir=control) as scratch:
        directory = Path(scratch)
        old, new = directory / "old", directory / "new"
        publish_exact(old, b"old", observer=observer, name="preflight.old")
        publish_exact(new, b"new", observer=observer, name="preflight.new")
        with old.open("rb") as opened:
            boundary(observer, "preflight.atomic_replace", "before")
            os.replace(new, old)
            sync_directory(directory)
            require(opened.read() == b"old" and read_regular(old) == b"new" and not new.exists(),
                    "Atomic replacement preflight failed")
            boundary(observer, "preflight.atomic_replace", "after")
    sync_directory(control)
    return filesystem


def exclusive_directory(path, *, observer=None, name="directory"):
    path = Path(path)
    boundary(observer, name + ".root_exclusive_create", "before")
    try:
        path.mkdir()
    except FileExistsError:
        require(path.is_dir() and not path.is_symlink(), "Managed directory is not a directory")
    boundary(observer, name + ".root_exclusive_create", "after")
    boundary(observer, name + ".parent_directory_sync", "before")
    sync_directory(path.parent)
    boundary(observer, name + ".parent_directory_sync", "after")


def read_regular(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Control file is not a unique regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def publish_exact(path, data, *, previous=None, observer=None, name="file"):
    """Materialize an exact immutable file or an exact append-only ledger suffix.

    The caller holds the coordinator write transaction and current operation
    fence. An existing partial or conflicting record is never repaired.
    """
    path = Path(path)
    require(type(data) is bytes, "Publication requires frozen bytes")
    if previous is not None:
        require(type(previous) is bytes and data.startswith(previous), "Publication is not an append")
        require(not previous or previous.endswith(b"\n"), "Incomplete previous ledger")
        require(data.endswith(b"\n"), "Incomplete proposed ledger")
    boundary(observer, name, "before")
    if path.exists() or path.is_symlink():
        actual = read_regular(path)
        if actual == data:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            sync_directory(path.parent)
            boundary(observer, name, "after")
            return
        require(previous is not None and actual == previous, "Conflicting publication bytes")
        flags, suffix = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, data[len(previous):]
    else:
        require(previous in (None, b""), "Missing prior ledger")
        flags, suffix = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, data
    descriptor = os.open(path, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Control file is not a unique regular file")
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(suffix)
            stream.flush()
            boundary(observer, name + ".file_sync", "before")
            os.fsync(descriptor)
        boundary(observer, name + ".file_sync", "after")
    finally:
        os.close(descriptor)
    boundary(observer, name + ".directory_sync", "before")
    sync_directory(path.parent)
    boundary(observer, name + ".directory_sync", "after")
    boundary(observer, name, "after")


def replace_projection(path, previous, content, *, observer=None):
    """Atomically update a derived projection from an exact, journaled old value.

    Ledger and immutable artifacts must use publish_exact, never this function.
    The caller holds the coordinator fence across validation and replacement.
    """
    from hashlib import sha256
    path = Path(path)
    require(path.name == "artifact_index.json", "Only the derived artifact index may be replaced")
    actual = read_regular(path)
    require(actual in (previous, content), "Artifact projection changed outside its owner")
    if actual == content:
        publish_exact(path, content, observer=observer, name="invocation.artifact_index")
        return
    temporary = path.with_name(".artifact_index_" + sha256(content).hexdigest() + ".tmp")
    publish_exact(temporary, content, observer=observer, name="invocation.artifact_index_temporary")
    boundary(observer, "invocation.artifact_index_replace", "before")
    os.replace(temporary, path)
    sync_directory(path.parent)
    boundary(observer, "invocation.artifact_index_replace", "after")


class Coordinator:
    """One connection per independent client; SQLite is the only writer lock."""

    def __init__(self, output_root, *, clock=None, observer=None):
        root = Path(output_root)
        require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "Missing trusted output root")
        require(root == root.resolve(), "Output root must be canonical and symlink-free")
        self.root, self.clock, self.observer = root, clock or HostClock(), observer
        control = root / ".lqcd"
        exclusive_directory(control)
        self.filesystem = durability_preflight(control, observer)
        self.path = control / "control_operations.sqlite"
        require(not self.path.is_symlink(), "Coordinator path is a symlink")
        existing = self.path.exists()
        if existing:
            read_regular(self.path)
        self.connection = sqlite3.connect(self.path, isolation_level=None, timeout=1.0)
        self.connection.row_factory = sqlite3.Row
        try:
            mode = self.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            require(mode.lower() == "wal", "SQLite WAL is unavailable")
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("PRAGMA foreign_keys=ON")
            self.connection.execute("PRAGMA busy_timeout=1000")
            require(self.connection.execute("PRAGMA synchronous").fetchone()[0] == 2 and
                    self.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1,
                    "SQLite FULL/foreign-key profile is unavailable")
            with self.transaction() as db:
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                require(not db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') OR "
                                       "(type='index' AND name NOT LIKE 'sqlite_autoindex_%')").fetchone(),
                        "Unknown coordinator schema object")
                if not existing and not tables:
                    for name, definition in TABLES.items():
                        db.execute(f"CREATE TABLE {name} ({definition})")
                    db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    db.execute("INSERT INTO control_metadata VALUES (?,?)", ("protocol_digest", PROTOCOL_SHA256))
                    db.execute("INSERT INTO control_metadata VALUES (?,?)", ("output_root", str(root)))
                else:
                    require(tables == set(TABLES), "Unknown or incomplete coordinator schema")
                require(db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION,
                        "Unsupported coordinator version")
                for name, definition in TABLES.items():
                    actual = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0]
                    require(actual == f"CREATE TABLE {name} ({definition})", "Coordinator table contract changed")
                metadata = dict(db.execute("SELECT key,value FROM control_metadata"))
                require(metadata == {"protocol_digest": PROTOCOL_SHA256, "output_root": str(root)},
                        "Coordinator authority binding changed")
            sync_directory(control)
            self._locking_preflight()
        except BaseException:
            self.connection.close()
            raise

    def close(self):
        self.connection.close()

    def _locking_preflight(self):
        competing = sqlite3.connect(self.path, isolation_level=None, timeout=0)
        try:
            with self.transaction():
                try:
                    competing.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as error:
                    require(error.sqlite_errorcode == sqlite3.SQLITE_BUSY, "SQLite locking preflight failed")
                else:
                    competing.rollback()
                    require(False, "Filesystem did not enforce SQLite single-writer locking")
        finally:
            competing.close()

    @contextmanager
    def transaction(self, *, commit_boundary=None):
        require(not self.connection.in_transaction, "Nested coordinator transaction")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
            boundary(self.observer, "coordinator.database_commit", "before")
            if commit_boundary is not None:
                boundary(self.observer, commit_boundary, "before")
            self.connection.commit()
            if commit_boundary is not None:
                boundary(self.observer, commit_boundary, "after")
            boundary(self.observer, "coordinator.database_commit", "after")
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _time(self):
        value = self.clock.now()
        number(value.wall_seconds)
        number(value.monotonic_seconds)
        return value

    @contextmanager
    def failure_context(self, operation):
        """Keep the failed boundary's fence across unwinding and lease replacement."""
        try:
            yield
        except (ControlIntegrityError, OSError, ValueError) as error:
            if not hasattr(error, "control_failure_context"):
                error.control_failure_context = {key: operation[key] for key in
                    ("operation_id", "worker_owner_id", "lease_epoch", "phase_revision")}
            raise

    def failed_operation(self, db, operation, worker, error):
        context = getattr(error, "control_failure_context", operation)
        require(context["operation_id"] == operation["operation_id"] and context["worker_owner_id"] == worker,
                "Foreign failed operation context")
        return self.fence(db, context["operation_id"], worker, context["lease_epoch"], context["phase_revision"])

    def get(self, operation_id, *, db=None):
        text(operation_id)
        row = (db or self.connection).execute(
            "SELECT * FROM control_operations WHERE operation_id=?", (operation_id,)).fetchone()
        require(row is not None, "Unknown control operation")
        result = dict(row)
        for key in ("request", "reservation", "result", "error", "created_at", "updated_at"):
            result[key] = loads(result[key]) if result[key] is not None else None
        return result

    def lookup_key(self, scope, key, *, db=None):
        boundary(self.observer, "coordinator.key_lookup", "before")
        row = (db or self.connection).execute(
            "SELECT operation_id FROM control_operations WHERE idempotency_scope=? AND idempotency_key=?",
            (scope, key)).fetchone()
        operation = self.get(row[0], db=db) if row else None
        boundary(self.observer, "coordinator.key_lookup", "after", operation)
        return operation

    def reserve(self, operation_type, variant, scope, key, request, worker, build_reservation, *, lease_seconds,
                build_snapshot=None):
        """Reserve before any Run bytes; the builder is a trusted, pure control function."""
        with self.transaction() as db:
            return self.reserve_in_transaction(db, operation_type, variant, scope, key, request, worker,
                                               build_reservation, lease_seconds=lease_seconds,
                                               build_snapshot=build_snapshot)

    def reserve_in_transaction(self, db, operation_type, variant, scope, key, request, worker,
                               build_reservation, *, lease_seconds, build_snapshot=None):
        """Join the held authority transaction, including dependent closure reservations."""
        require(db is self.connection and db.in_transaction, "Reservation requires coordinator authority")
        declaration = operation_variant(operation_type, variant)
        from .operations import validate_reservation
        for value in (scope, key, worker):
            text(value)
        number(lease_seconds, minimum=1)
        request_bytes = canonical_bytes(request)
        request = loads(request_bytes)
        request_digest = digest({"operation_type": operation_type, "operation_variant": variant, "request": request})
        old = self.lookup_key(scope, key, db=db)
        if old:
            require(old["request_digest"] == request_digest, "Same-key request conflict")
            return old
        name = f"control.{operation_type}.{variant}.{declaration['initial_phase']}"
        boundary(self.observer, name, "before")
        stamp = self._time()
        operation_id = "control_" + uuid.uuid4().hex
        reservation = build_reservation(operation_id, stamp)
        validate_reservation(operation_type, variant, reservation)
        raw_stamp = canonical_bytes(asdict(stamp))
        db.execute("INSERT INTO control_operations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (operation_id, scope, key, request_digest, operation_type, variant, "in_progress",
                    declaration["initial_phase"], 1, worker, 1, stamp.monotonic_seconds + lease_seconds,
                    request_bytes, canonical_bytes(reservation), None, None, raw_stamp, raw_stamp))
        db.execute("INSERT INTO control_phases VALUES (?,?,?,?,?,?)",
                   (operation_id, 1, declaration["initial_phase"], 1, canonical_bytes(reservation), b"{}"))
        if build_snapshot is not None:
            snapshot = build_snapshot(self.get(operation_id, db=db))
            db.execute("INSERT INTO control_snapshots VALUES (?,?,?)",
                       (operation_id, canonical_bytes(snapshot), digest(snapshot)))
        boundary(self.observer, name, "after", self.get(operation_id, db=db))
        return self.get(operation_id, db=db)

    def interrupt(self, db, operation, status, error):
        """Freeze a nonterminal phase and atomically quarantine any owned closure."""
        from .operations import CONTROL
        require(db is self.connection and db.in_transaction, "Interrupt requires coordinator authority")
        require(status in CONTROL["interrupt_terminal_statuses"], "Unknown interrupt outcome")
        current = self.fence(db, operation["operation_id"], operation["worker_owner_id"],
                             operation["lease_epoch"], operation["phase_revision"])
        require(type(error) is dict and bool(error), "Missing interrupt proof")
        for row in db.execute("SELECT run_key,revision,value FROM run_terminal_closure").fetchall():
            value = loads(row["value"])
            if value["terminal_closure_owner_operation_id"] == current["operation_id"]:
                require(value["terminal_closure"] == "pending", "Cannot interrupt a finished closure")
                if current["operation_type"] == "resume_run" and current["request"].get("input_kind") == "external_result":
                    reserved = current["reservation"]["target_prestart_closure"]["external"]["value"]
                    external = db.execute("SELECT value FROM external_operations WHERE external_operation_id=?",
                                          (reserved["producer_operation_id"],)).fetchone()
                    require(external is not None, "Failure closure lost its external binding")
                    binding = loads(external[0])
                    require(binding["resolution_owner"] == "normal" and
                            binding["active_binding_generation"] == reserved["active_binding_generation"], "Failure closure binding changed")
                    if binding["active_binding_status"] == "active":
                        binding["active_binding_status"] = "quarantined"
                        db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?",
                                   (canonical_bytes(binding), reserved["producer_operation_id"]))
                value.update(terminal_closure="unavailable", run_status=None, unavailable_proof=error)
                db.execute("UPDATE run_terminal_closure SET value=? WHERE run_key=? AND revision=?",
                           (canonical_bytes(value), row["run_key"], row["revision"]))
        db.execute("UPDATE control_operations SET status=?,error=?,updated_at=? WHERE operation_id=?",
                   (status, canonical_bytes(error), canonical_bytes(asdict(self._time())), current["operation_id"]))
        return self.get(current["operation_id"], db=db)

    def snapshot(self, operation_id, *, db=None):
        row = (db or self.connection).execute("SELECT value,value_digest FROM control_snapshots WHERE operation_id=?",
                                             (operation_id,)).fetchone()
        if row is None:
            raise MaterializationSnapshotError(operation_id, missing=True)
        try:
            value = loads(row[0])
            require(type(value) is dict and digest(value) == row[1], "Operation materialization snapshot changed")
        except ControlIntegrityError as error:
            raise MaterializationSnapshotError(operation_id, missing=False) from error
        return value

    def quarantine_plan(self, operation, worker, error):
        """Freeze an owned lost plan without regenerating domain authority."""
        require(isinstance(error, MaterializationSnapshotError) and error.operation_id == operation["operation_id"],
                "Foreign materialization failure")
        external = (operation["operation_type"] == "resolve_external_interrupt" or
                    operation["operation_type"] == "resume_run" and operation["request"].get("input_kind") == "external_result" or
                    operation["operation_type"] == "cancel_pause" and
                    operation["reservation"]["external_operation_identity"].get("tag") != "null")
        with self.transaction() as db:
            self.fence(db, operation["operation_id"], worker, operation["lease_epoch"], operation["phase_revision"])
            return self.interrupt(db, operation, "recovery_required" if error.missing or external else "failed", {
                "kind": "missing_materialization_snapshot" if error.missing else "corrupt_materialization_snapshot",
                "source_operation_id": operation["operation_id"], "source_phase_revision": operation["phase_revision"],
                "lease_epoch": operation["lease_epoch"]})

    def fence(self, db, operation_id, worker, epoch, revision):
        boundary(self.observer, "coordinator.operation_fence", "before")
        try:
            operation = self.get(operation_id, db=db)
            require(operation["status"] == "in_progress" and operation["worker_owner_id"] == worker and
                    operation["lease_epoch"] == epoch and operation["phase_revision"] == revision,
                    "Stale or terminal operation fence")
            now = self._time()
            prior = operation["updated_at"]
            require(now.source == prior["source"] and now.wall_seconds >= prior["wall_seconds"] and
                    now.monotonic_seconds >= prior["monotonic_seconds"], "Coordinator clock regression")
            require(now.monotonic_seconds < operation["lease_expires"], "Operation lease expired")
            return operation
        finally:
            boundary(self.observer, "coordinator.operation_fence", "after")

    def acquire(self, operation_id, worker, *, lease_seconds):
        text(worker)
        number(lease_seconds, minimum=1)
        with self.transaction() as db:
            old = self.get(operation_id, db=db)
            require(old["status"] == "in_progress", "Cannot lease terminal operation")
            stamp = self._time()
            require(stamp.source == old["updated_at"]["source"] and
                    stamp.wall_seconds >= old["updated_at"]["wall_seconds"] and
                    stamp.monotonic_seconds >= old["updated_at"]["monotonic_seconds"], "Lease clock regression")
            require(stamp.monotonic_seconds >= old["lease_expires"], "Operation already leased")
            boundary(self.observer, "coordinator.lease_takeover", "before", old)
            db.execute("UPDATE control_operations SET worker_owner_id=?, lease_epoch=lease_epoch+1, "
                       "lease_expires=?, updated_at=? WHERE operation_id=?",
                       (worker, stamp.monotonic_seconds + lease_seconds, canonical_bytes(asdict(stamp)), operation_id))
            boundary(self.observer, "coordinator.lease_takeover", "after", self.get(operation_id, db=db))
            return self.get(operation_id, db=db)

    def renew(self, operation_id, worker, epoch, revision, *, lease_seconds):
        """Renew a live worker fence without acquiring or advancing a phase."""
        number(lease_seconds, minimum=1)
        with self.transaction() as db:
            self.fence(db, operation_id, worker, epoch, revision)
            stamp = self._time()
            db.execute("UPDATE control_operations SET lease_expires=?,updated_at=? WHERE operation_id=?",
                       (stamp.monotonic_seconds + lease_seconds, canonical_bytes(asdict(stamp)), operation_id))
            return self.get(operation_id, db=db)

    def freeze_publication(self, operation_id, worker, epoch, revision, phase, path, content, *, previous=None,
                           replacement=False):
        """Commit deterministic bytes before their first filesystem effect.

        This internal API is not a request or admission port. Only a trusted
        phase handler may produce the bytes and the exact managed destination.
        """
        from .operations import phase_contract
        path = Path(path)
        require(path.is_absolute() and path == path.resolve() and path.is_relative_to(self.root) and
                not path.is_relative_to(self.path.parent), "Publication escaped managed Run storage")
        require(type(content) is bytes and (previous is None or type(previous) is bytes),
                "Publication plan requires exact bytes")
        if replacement:
            require(previous is not None, "Projection replacement needs an exact previous object")
            require(type(loads(previous)) is dict and type(loads(content)) is dict, "Projection must be canonical JSON")
        elif previous is not None:
            require(content.startswith(previous) and (not previous or previous.endswith(b"\n")) and
                    content.endswith(b"\n"), "Publication plan is not a complete ledger append")
        with self.transaction() as db:
            operation = self.fence(db, operation_id, worker, epoch, revision)
            phase_contract(operation["operation_type"], operation["operation_variant"], phase)
            declaration = operation_variant(operation["operation_type"], operation["operation_variant"])
            require((operation["phase"], phase) in declaration["success_edges"],
                    "Publication is not for the immediate next phase")
            key = (operation_id, phase, str(path))
            old = db.execute("SELECT previous,content,producing_epoch FROM control_publications WHERE operation_id=? AND phase=? AND path=? "
                             "ORDER BY producing_epoch DESC LIMIT 1",
                             key).fetchone()
            if old is not None:
                if (old[0], old[1]) == (previous, content):
                    return
                require(old["producing_epoch"] < epoch, "Frozen publication bytes changed")
                actual = read_regular(path) if path.exists() else None
                if replacement:
                    require(actual in (previous, content), "Takeover cannot replace a materialized projection")
                elif previous is None:
                    require(actual is None or actual == content, "Takeover cannot replace a materialized object")
                else:
                    require(old["previous"] == previous and actual is not None and actual.startswith(previous) and
                            content.startswith(actual) and (not actual or actual.endswith(b"\n")),
                            "Takeover cannot replace materialized ledger bytes")
            if old is None or (old[0], old[1]) != (previous, content):
                from hashlib import sha256
                db.execute("INSERT INTO control_publications VALUES (?,?,?,?,?,?,?,?)",
                           (*key, previous, content, sha256(content).hexdigest(), epoch, revision + 1))

    def materialize_publication(self, db, operation, phase, path, *, name, replacement=False):
        """Publish only journaled bytes while the same phase's writer fence is held."""
        from hashlib import sha256
        require(db is self.connection and db.in_transaction, "Publication requires coordinator transaction")
        self.fence(db, operation["operation_id"], operation["worker_owner_id"],
                   operation["lease_epoch"], operation["phase_revision"])
        declaration = operation_variant(operation["operation_type"], operation["operation_variant"])
        require((operation["phase"], phase) in declaration["success_edges"],
                "Publication is not for the immediate next phase")
        path = Path(path)
        require(path == path.resolve() and path.is_relative_to(self.root) and
                not path.is_relative_to(self.path.parent), "Publication path binding changed")
        row = db.execute("SELECT previous,content,content_digest FROM control_publications "
                         "WHERE operation_id=? AND phase=? AND path=? ORDER BY producing_epoch DESC LIMIT 1",
                         (operation["operation_id"], phase, str(path))).fetchone()
        require(row is not None and sha256(row["content"]).hexdigest() == row["content_digest"],
                "Missing or corrupt frozen publication")
        previous, content = row["previous"], row["content"]
        if replacement:
            require(previous is not None, "Projection replacement lacks its previous object")
            replace_projection(path, previous, content, observer=self.observer)
        elif previous is None:
            publish_exact(path, content, observer=self.observer, name=name)
        else:
            actual = read_regular(path) if path.exists() else b""
            require(actual.startswith(previous) and content.startswith(actual) and
                    (not actual or actual.endswith(b"\n")), "Conflicting or partial publication prefix")
            if actual == content:
                publish_exact(path, content, previous=actual, observer=self.observer, name=name)
            for line in content[len(actual):].splitlines(keepends=True):
                next_bytes = actual + line
                publish_exact(path, next_bytes, previous=actual, observer=self.observer, name=name)
                actual = next_bytes
        return row["content_digest"]

    def step(self, operation_id, worker, epoch, revision, target, publish, *, branch_values=None):
        """Hold the writer fence across one exact publication and its phase CAS."""
        from .operations import select_successor, validate_phase_evidence
        context = {"operation_id": operation_id, "worker_owner_id": worker, "lease_epoch": epoch, "phase_revision": revision}
        with self.failure_context(context), self.transaction() as db:
            operation = self.fence(db, operation_id, worker, epoch, revision)
            name = f"control.{operation['operation_type']}.{operation['operation_variant']}.{target}"
            boundary(self.observer, name, "before", operation)
            branch_values = {} if branch_values is None else branch_values
            require(select_successor(operation, target, branch_values), "Invalid or unguarded operation edge")
            evidence = publish(db, operation)
            validate_phase_evidence(operation, target, evidence)
            self.fence(db, operation_id, worker, epoch, revision)
            declaration = operation_variant(operation["operation_type"], operation["operation_variant"])
            terminal = next((v for v in declaration["terminal_outcomes"] if v["phase"] == target), None)
            status = terminal["status"] if terminal else "in_progress"
            result = evidence.get("exact_public_or_internal_result") if target == "result_committed" else None
            now = canonical_bytes(asdict(self._time()))
            db.execute("INSERT INTO control_phases VALUES (?,?,?,?,?,?)",
                       (operation_id, revision + 1, target, epoch, canonical_bytes(evidence), canonical_bytes(branch_values)))
            db.execute("UPDATE control_operations SET status=?,phase=?,phase_revision=?,result=?,updated_at=? "
                       "WHERE operation_id=?",
                       (status, target, revision + 1, canonical_bytes(result) if result is not None else None,
                        now, operation_id))
            boundary(self.observer, name, "after", self.get(operation_id, db=db))
            return self.get(operation_id, db=db)

    def history(self, operation_id):
        self.get(operation_id)
        return [{**dict(row), "evidence": loads(row["evidence"]), "branch": loads(row["branch"])} for row in self.connection.execute(
            "SELECT revision,phase,lease_epoch,evidence,branch FROM control_phases WHERE operation_id=? ORDER BY revision",
            (operation_id,))]

    def backup(self, destination):
        """Use SQLite's coherent snapshot API; raw database copying is not supported."""
        destination = Path(destination)
        require(destination.is_absolute() and not destination.exists() and not destination.is_symlink(),
                "Backup destination must be new")
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        target = sqlite3.connect(destination)
        try:
            self.connection.backup(target)
            require(target.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "Invalid coordinator backup")
        finally:
            target.close()
        descriptor = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        sync_directory(destination.parent)
