"""Fresh original-format 0.3 sources and actual 0.4 Fork trace capture."""
from contextlib import contextmanager
from itertools import count
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
import uuid

from lqcd_agent.control.children import ForkRunRequest
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads

from harness.trace import event
from helpers.control_traces import ControlTrace
from test_historical_source_control import Archived03Reader, historical_source


def files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def fresh_historical_trace():
    with historical_trace() as (trace, _):
        return trace


@contextmanager
def historical_trace(*, wal=False, archive_offset=0, revision_offset=0, material=None):
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-historical-trace-", dir="/private/tmp"))
    identities = count(1)
    with patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=next(identities))):
        coordinator = Coordinator(output, clock=FakeClock(100, 0))
        connection = None
        try:
            locator, _, _ = historical_source(coordinator)
            root = output / locator["case_id"] / locator["run_id"]
            # Configure the synthetic archive before it becomes a Fork source.
            records = [loads(line) for line in (root / "execution_history.jsonl").read_bytes().splitlines()]
            if material is not None:
                from hashlib import sha256
                content = canonical_bytes({"goal": material})
                (root / "root_goal.json").write_bytes(content)
                records[0]["root_goal_reference"]["sha256"] = sha256(content).hexdigest()
            for index, record in enumerate(records):
                record["created_at"]["wall_seconds"] += archive_offset
                record["created_at"]["monotonic_seconds"] += archive_offset
                record["previous_execution_head"] = digest(records[index - 1]) if index else None
            head = digest(records[-1])
            (root / "execution_history.jsonl").write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in records))
            index = loads((root / "artifact_index.json").read_bytes())
            index["execution_head"] = head
            (root / "artifact_index.json").write_bytes(canonical_bytes(index))
            connection = sqlite3.connect(root / "checkpoints/graph_checkpoints.sqlite")
            if wal:
                assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
                connection.execute("PRAGMA wal_autocheckpoint=0")
            payload = loads(connection.execute("SELECT checkpoint FROM checkpoints").fetchone()[0])
            payload["channel_values"]["control"]["execution_head"] = head
            if wal:
                payload["ts"] = "1970-01-01T00:00:11+00:00"
            connection.execute("UPDATE checkpoints SET checkpoint=?", (canonical_bytes(payload),))
            connection.commit()
            with coordinator.transaction() as db:
                value = loads(db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()[0])
                manifest = value["manifest"]
                manifest.update(execution_head=head, checkpoint_digest=digest(payload), state_digest=digest(payload["channel_values"]["control"]))
                manifest.pop("checkpoint_head")
                manifest["checkpoint_head"] = digest(manifest)
                value["projection"].update(execution_head=head, checkpoint_head=manifest["checkpoint_head"])
                db.execute("UPDATE run_controls SET revision=revision+?,value=? WHERE run_key=?", (revision_offset, canonical_bytes(value), digest(locator)))
                pause = loads(db.execute("SELECT value FROM pause_ownership WHERE run_key=?", (digest(locator),)).fetchone()[0])
                pause["opened_head"] = head
                db.execute("UPDATE pause_ownership SET value=? WHERE run_key=?", (canonical_bytes(pause), digest(locator)))
                (root / "checkpoints/original_public_pause.json").write_bytes(canonical_bytes(manifest))
            if not wal:
                connection.close()
                connection = None
            else:
                assert Path(str(root / "checkpoints/graph_checkpoints.sqlite") + "-wal").stat().st_size > 0
            before = files(root)
            capture = ControlTrace(output, version="0.3")
            coordinator.observer = capture.observer
            actor = ActorContext("operator", "human", ("fork", "policy.select"))
            plane = ControlPlane(coordinator, worker_id="trace-worker", source_adapter=Archived03Reader())
            result = plane.fork_run(ForkRunRequest(locator, "historical-trace-child", head), actor=actor)
            assert result["operation_status"] == "committed", result
            capture.events.append(event("fork_child_checkpoint", run_id=result["result"]["run_locator"]["run_id"],
                execution_head=result["result"]["execution_head"], checkpoint_head=result["result"]["checkpoint_head"],
                operation_id=result["operation_id"], outcome="committed"))
            trace = capture.finish(coordinator)
            assert files(root) == before
            yield trace, root
        finally:
            if connection is not None:
                connection.close()
            coordinator.close()
