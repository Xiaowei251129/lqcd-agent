"""Durable, network-free backend evidence selected by trusted fixture IDs."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import sqlite3
import time

from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, require, text

from .backend import validate_receipt, validate_result_reference, validate_status
from .schemas import validate_manifest, validate_task


class FakeCodingBackend:
    """The fixture registry is Host-supplied and is never read from a task."""

    def __init__(self, root, *, operation_scenarios=None, fixtures=None, clock=None):
        self.root = Path(root)
        control = Path(__file__).resolve().parents[3]
        require(self.root.is_absolute() and self.root == self.root.resolve() and
                not self.root.is_relative_to(control) and not control.is_relative_to(self.root),
                "Fake backend root cannot be the control repository")
        self.root.mkdir(parents=True, exist_ok=True)
        require(not self.root.is_symlink() and self.root.is_dir(), "Fake backend root was replaced")
        self.database = self.root / "fake_backend.sqlite"
        require(not self.database.is_symlink(), "Fake backend database was replaced")
        self.operation_scenarios = dict(operation_scenarios or {})
        self.fixtures = dict(fixtures or {})
        self.clock = clock or time.time
        with self._db(write=True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS operations (operation_id TEXT PRIMARY KEY, task_digest TEXT NOT NULL, "
                       "manifest_digest TEXT NOT NULL, scenario_id TEXT NOT NULL, receipt BLOB NOT NULL, "
                       "status TEXT NOT NULL, result BLOB, cancel_reason TEXT)")

    @contextmanager
    def _db(self, *, write=False):
        require(not self.database.is_symlink(), "Fake backend database was replaced")
        db = sqlite3.connect(self.database, timeout=10)
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except Exception:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _receipt(task, manifest):
        value = {"schema_version": "0.1", "producer_operation_id": task["producer_operation_id"],
                 "task_id": task["task_id"], "task_digest": task["task_digest"],
                 "workspace_id": manifest["workspace_id"], "workspace_manifest_digest": manifest["manifest_digest"],
                 "backend_kind": task["coding_backend_kind"], "backend_version": task["backend_version"],
                 "provider_operation_reference": None, "provider_thread_reference": None,
                 "dispatch_status": "accepted"}
        value["receipt_digest"] = digest(value)
        return validate_receipt(value, task, manifest).value

    def dispatch(self, task_ref, workspace_manifest_ref, producer_operation_id):
        task = validate_task(task_ref).value
        manifest = validate_manifest(workspace_manifest_ref, task).value
        text(producer_operation_id)
        require(task["producer_operation_id"] == producer_operation_id and task["coding_backend_kind"] == "fake",
                "Fake dispatch has no canonical producer")
        scenario_id = self.operation_scenarios.get(producer_operation_id)
        require(type(scenario_id) is str and bool(scenario_id) and scenario_id in self.fixtures,
                "Only a trusted fixture may select a Fake outcome")
        fixture = self.fixtures[scenario_id]
        require(type(fixture) is dict and set(fixture) == {"status", "result"} and
                fixture["status"] in ("running", "completed", "failed"), "Invalid Fake fixture")
        result = fixture["result"]
        require(result is None if fixture["status"] == "running" else type(result) is bytes and bool(result),
                "Fake fixture lacks immutable result bytes")
        receipt = self._receipt(task, manifest)
        with self._db(write=True) as db:
            row = db.execute("SELECT task_digest,manifest_digest,scenario_id,receipt FROM operations WHERE operation_id=?",
                             (producer_operation_id,)).fetchone()
            if row is not None:
                require(row == (task["task_digest"], manifest["manifest_digest"], scenario_id, canonical_bytes(receipt)),
                        "Conflicting Fake dispatch")
                return receipt
            db.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?)",
                       (producer_operation_id, task["task_digest"], manifest["manifest_digest"], scenario_id,
                        canonical_bytes(receipt), fixture["status"], result, None))
        return receipt

    def lookup(self, producer_operation_id):
        text(producer_operation_id)
        with self._db() as db:
            row = db.execute("SELECT receipt,status FROM operations WHERE operation_id=?",
                             (producer_operation_id,)).fetchone()
        receipt = loads(row[0]) if row else None
        value = {"schema_version": "0.1", "producer_operation_id": producer_operation_id,
                 "backend_kind": "fake", "backend_version": receipt["backend_version"] if receipt else "0.1",
                 "status": row[1] if row else "unknown",
                 "receipt_reference": "fake-receipt:" + producer_operation_id if receipt else None,
                 "receipt_digest": sha256(row[0]).hexdigest() if receipt else None, "queried_at": self.clock()}
        return validate_status(value).value

    def read_receipt(self, reference):
        require(type(reference) is str and reference.startswith("fake-receipt:"), "Invalid Fake receipt reference")
        operation_id = reference.removeprefix("fake-receipt:")
        with self._db() as db:
            row = db.execute("SELECT receipt FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        require(row is not None, "Missing Fake receipt")
        return loads(row[0])

    def fetch_result(self, producer_operation_id):
        text(producer_operation_id)
        with self._db() as db:
            row = db.execute("SELECT status,result FROM operations WHERE operation_id=?",
                             (producer_operation_id,)).fetchone()
        require(row is not None and row[0] in ("completed", "failed") and type(row[1]) is bytes and bool(row[1]),
                "Fake result is not immutable and complete")
        content = row[1]
        value = {"schema_version": "0.1", "producer_operation_id": producer_operation_id,
                 "reference": "fake-result:" + producer_operation_id, "digest": sha256(content).hexdigest(),
                 "size": len(content)}
        return validate_result_reference(value).value

    def read_result(self, reference):
        value = validate_result_reference(reference).value
        require(value["reference"] == "fake-result:" + value["producer_operation_id"],
                "Fake result reference identity mismatch")
        with self._db() as db:
            row = db.execute("SELECT status,result FROM operations WHERE operation_id=?",
                             (value["producer_operation_id"],)).fetchone()
        require(row is not None and row[0] in ("completed", "failed") and type(row[1]) is bytes and
                len(row[1]) == value["size"] and sha256(row[1]).hexdigest() == value["digest"],
                "Fake result reference changed")
        return row[1]

    def cancel(self, producer_operation_id, typed_reason):
        text(producer_operation_id)
        text(typed_reason)
        with self._db(write=True) as db:
            row = db.execute("SELECT status,cancel_reason FROM operations WHERE operation_id=?",
                             (producer_operation_id,)).fetchone()
            if row is not None and row[0] in ("accepted", "running"):
                require(row[1] is None or row[1] == typed_reason, "Conflicting Fake cancellation")
                db.execute("UPDATE operations SET status='cancelled',cancel_reason=? WHERE operation_id=?",
                           (typed_reason, producer_operation_id))
            elif row is not None and row[0] == "cancelled":
                require(row[1] == typed_reason, "Conflicting Fake cancellation")
        return self.lookup(producer_operation_id)
