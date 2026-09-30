"""Durable deterministic containment evidence for the Phase B Fake backend."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from lqcd_agent.control.strict_json import require, text


class DeterministicContainment:
    """Model dedicated workers without claiming operating-system containment."""

    def __init__(self, root, *, fault_by_operation=None):
        self.root = Path(root)
        control = Path(__file__).resolve().parents[3]
        require(self.root.is_absolute() and self.root == self.root.resolve() and
                not self.root.is_relative_to(control) and not control.is_relative_to(self.root),
                "Containment evidence cannot live in the control repository")
        self.root.mkdir(parents=True, exist_ok=True)
        require(self.root.is_dir() and not self.root.is_symlink(), "Containment root was replaced")
        self.database = self.root / "containment.sqlite"
        self.faults = dict(fault_by_operation or {})
        with self._db(write=True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS operations (operation_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, "
                       "phase TEXT NOT NULL, write_lease INTEGER NOT NULL, descendants INTEGER NOT NULL, "
                       "reader_open INTEGER NOT NULL, tool_index INTEGER NOT NULL, stop_tool_index INTEGER, "
                       "kill_fault INTEGER NOT NULL, drain_fault INTEGER NOT NULL, stability_fault INTEGER NOT NULL)")

    @contextmanager
    def _db(self, *, write=False):
        require(not self.database.is_symlink(), "Containment database was replaced")
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

    def start(self, operation_id, workspace_id):
        text(operation_id)
        text(workspace_id)
        faults = self.faults.get(operation_id, {})
        require(type(faults) is dict and set(faults) <= {"kill_all", "bounded_drain", "post_stop_stability"} and
                all(type(value) is bool for value in faults.values()), "Invalid deterministic containment fault")
        with self._db(write=True) as db:
            row = db.execute("SELECT workspace_id,phase FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is not None:
                require(row == (workspace_id, "running"), "Containment operation cannot be restarted")
                return
            db.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (operation_id, workspace_id, "running", 1, 1, 1, 0, None,
                        int(faults.get("kill_all") is False), int(faults.get("bounded_drain") is False),
                        int(faults.get("post_stop_stability") is False)))

    def record_tool(self, operation_id):
        with self._db(write=True) as db:
            row = db.execute("SELECT phase,write_lease FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            require(row == ("running", 1), "Stopped worker cannot perform a tool effect")
            db.execute("UPDATE operations SET tool_index=tool_index+1 WHERE operation_id=?", (operation_id,))

    def revoke_writes(self, operation_id):
        with self._db(write=True) as db:
            row = db.execute("SELECT phase,write_lease,tool_index FROM operations WHERE operation_id=?",
                             (operation_id,)).fetchone()
            require(row is not None, "Unknown containment worker")
            if row[0] in ("stopping", "terminating"):
                require(row[1] == 0, "Write lease returned after revocation")
                return
            require(row[0] == "running" and row[1] == 1, "Invalid write lease transition")
            db.execute("UPDATE operations SET phase='stopping',write_lease=0,stop_tool_index=? WHERE operation_id=?",
                       (row[2], operation_id))

    def terminate(self, operation_id):
        with self._db(write=True) as db:
            row = db.execute("SELECT phase FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            require(row is not None and row[0] in ("stopping", "terminating"),
                    "Termination requires revoked writes")
            db.execute("UPDATE operations SET phase='terminating' WHERE operation_id=?", (operation_id,))

    def kill_all(self, operation_id):
        with self._db(write=True) as db:
            row = db.execute("SELECT phase,kill_fault FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            require(row is not None and row[0] == "terminating", "Kill-all requires termination intent")
            if not row[1]:
                db.execute("UPDATE operations SET descendants=0 WHERE operation_id=?", (operation_id,))

    def drain(self, operation_id):
        with self._db(write=True) as db:
            row = db.execute("SELECT phase,drain_fault FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            require(row is not None and row[0] == "terminating", "Drain requires termination intent")
            if not row[1]:
                db.execute("UPDATE operations SET reader_open=0 WHERE operation_id=?", (operation_id,))

    def proof(self, operation_id):
        with self._db() as db:
            row = db.execute("SELECT phase,write_lease,descendants,reader_open,tool_index,stop_tool_index,"
                             "stability_fault FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        require(row is not None, "Unknown containment worker")
        phase, writes, descendants, reader, tools, stopped_at, stability_fault = row
        return {"termination_or_not_dispatched": "confirmed" if phase == "terminating" and descendants == 0 else "unknown",
                "write_lease_revocation": writes == 0,
                "verify_empty": descendants == 0,
                "bounded_drain": reader == 0,
                "post_stop_stability": stopped_at is not None and tools == stopped_at and not stability_fault}

    def observed_tool_count(self, operation_id):
        with self._db() as db:
            row = db.execute("SELECT tool_index FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        require(row is not None, "Unknown containment worker")
        return row[0]

    def never_started(self, operation_id):
        """A missing start witness proves dispatch was not reached by this Host."""
        with self._db() as db:
            return db.execute("SELECT 1 FROM operations WHERE operation_id=?", (operation_id,)).fetchone() is None
