"""Capture actual B02 boundaries and their complete raw authority references."""
from itertools import count
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
import uuid

from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.pause import PublishPauseRequest, ResumeRunRequest
from lqcd_agent.control.strict_json import digest, loads

from harness.trace import event
from harness.trace_proof import source_object
from helpers.trace_sources import current_binding


class ControlTrace:
    def __init__(self, output, *, version="0.2"):
        self.output, self.events, self.observed_records = output, [], set()
        self.version = version

    def observer(self, name, side, value):
        if side != "after":
            return
        selected = name.startswith("control.") or name.startswith("invocation.attempt_")
        if not selected:
            return
        for path in sorted(self.output.glob("*/*/execution_history.jsonl")):
            records = [loads(line) for line in path.read_bytes().splitlines()]
            run_status = "initializing"
            for record in records:
                if record["record_type"] == "run_lifecycle":
                    run_status = record["to_status"]
                head = digest(record)
                if head in self.observed_records:
                    continue
                self.observed_records.add(head)
                self.events.append(event(record["record_type"] + ":" + record["event"], run_id=record["run_id"],
                    cycle_id=record.get("cycle_id"), attempt_id=record.get("attempt_id"), transition_id=record.get("transition_id"),
                    operation_id=record.get("operation_id"), pause_id=record.get("pause_id"), physical_node=record.get("node_name"),
                    attempt_kind=record.get("attempt_kind"), index=record["event_index"], execution_head=head,
                    artifact_head=record["artifact_head"], run_status=run_status, outcome="durable_record",
                    owner="historical_source" if self.version in ("0.3", "0.4") and record["schema_version"] == "0.3" else "production_control",
                    ephemeral={"output_root": str(path.parent)}))
        if name.startswith("control."):
            self.events.append(event(name, operation_id=value["operation_id"], phase=value["phase"],
                phase_revision=value["phase_revision"], lease_epoch=value["lease_epoch"], status=value["status"],
                owner=value["worker_owner_id"], result_digest=digest(value["result"]) if value["result"] is not None else None,
                outcome="committed_phase"))

    def finish(self, coordinator):
        candidates, sources = {}, {}
        def collect(value):
            if type(value) is dict:
                candidates[digest(value)] = value
                for child in value.values():
                    collect(child)
            elif type(value) is list:
                for child in value:
                    collect(child)
        for table, column in (("control_snapshots", "value"), ("control_phases", "evidence"),
                              ("invocation_capabilities", "value"), ("control_operations", "result"),
                              ("control_operations", "reservation")):
            for row in coordinator.connection.execute(f"SELECT {column} FROM {table}"):
                if row[0] is not None:
                    collect(loads(row[0]))
        if self.version in ("0.3", "0.4"):
            for row in coordinator.connection.execute("SELECT operation_type,operation_variant,request FROM control_operations"):
                collect({"operation_type": row[0], "operation_variant": row[1], "request": loads(row[2])})
        roots = []
        for path in sorted(self.output.glob("*/*/execution_history.jsonl")):
            records = [loads(line) for line in path.read_bytes().splitlines()]
            root = path.parent
            roots.append({"case_id": records[0]["case_id"], "run_id": records[0]["run_id"], "path": str(root)})
            artifact_history = root / "artifact_history.jsonl"
            if artifact_history.exists():
                for line in artifact_history.read_bytes().splitlines():
                    collect(loads(line))
            historical = self.version in ("0.3", "0.4") and records[0]["schema_version"] == "0.3"
            for record in records:
                item = source_object("historical_execution_0_3" if historical else "execution_0_4", record, version=self.version)
                sources[item["sha256"]] = item
                if self.version in ("0.3", "0.4") and record["record_type"] == "lineage":
                    proof = record["source_snapshot_proof"]
                    collect(proof)
                    if proof["source_snapshot_kind"] == "fork_head":
                        collect({"source_run_identity": proof["source_run_identity"],
                                 "revision": proof["source_control_revision"], "heads": proof["source_latest_heads"]})
            for manifest_path in root.glob("checkpoints/*.json"):
                manifest = loads(manifest_path.read_bytes())
                item = source_object("historical_checkpoint_manifest_0_3" if historical else "checkpoint_manifest", manifest, version=self.version)
                sources[item["sha256"]] = item
            # Read a private copy of the complete durability unit. Opening the
            # original database, even read-only, can create or alter its SHM.
            with coordinator.transaction(), tempfile.TemporaryDirectory(prefix="lqcd-agent-trace-db-", dir="/private/tmp") as directory:
                database = root / "checkpoints/graph_checkpoints.sqlite"
                for suffix in ("", "-wal", "-shm"):
                    path = Path(str(database) + suffix)
                    if path.exists():
                        (Path(directory) / path.name).write_bytes(path.read_bytes())
                connection = sqlite3.connect((Path(directory) / database.name).as_uri() + "?mode=ro", uri=True)
                try:
                    for row in connection.execute("SELECT checkpoint FROM checkpoints"):
                        collect(loads(row[0]))
                finally:
                    connection.close()
        used = {}
        def use(head):
            if head in used:
                return
            row = sources.get(head)
            if row is None:
                assert head in candidates, ("Missing raw preimage", head)
                row = source_object("canonical_json", candidates[head], version=self.version)
            used[head] = row
            for ref in row["references"]:
                use(ref["sha256"])
        for observed in self.events:
            for field in ("execution_head", "artifact_head", "checkpoint_head", "result_digest"):
                if observed[field] is not None:
                    use(observed[field])
        return {"schema_version": self.version, "representation": "raw_with_proof", "events": self.events,
            "proof": {"schema_version": "0.1", "binding": current_binding(), "objects": list(used.values()), "output_roots": roots}}


def fresh_recovery_trace():
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-trace-", dir="/private/tmp"))
    captured = ControlTrace(output)
    identities = count(1)
    with patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=next(identities))):
        coordinator = Coordinator(output, clock=FakeClock(100, 0), observer=captured.observer)
        try:
            actor = ActorContext("operator", "human", ("control.internal", "resume", "start"))
            plane = ControlPlane(coordinator, worker_id="trace-worker")
            inputs = {"root_goal": {"goal": "synthetic"}, "input_snapshot": {"data": "synthetic"}}
            started = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "trace-start", "phase_b_test"), actor=actor)
            class Target:
                def invoke(self, identity):
                    return TargetOutcome("failed", {"current_artifact_ids": {}}, {"type": "SyntheticRecovery", "message": "external/domain adapter"})
            leases = InvocationLeases(coordinator)
            capability = started["result"]["capability_id"]
            leases.acquire(capability, "trace-consumer", expected_epoch=0, lease_seconds=20)
            leases.invoke(capability, "trace-consumer", 1, Target())
            locator = started["result"]["run_locator"]
            paused = plane.publish_pause(PublishPauseRequest(locator, "recovery_decision", "attempt_000001", None,
                {"kind": "recovery_decision", "actions": ["abandon_and_halt"]}, {"actor_type": "human", "scopes": ["resume"]}, "trace-pause"), actor=actor)
            payload = {"action": "abandon_and_halt"}
            closed = plane.resume_run(ResumeRunRequest(locator, paused["result"]["pause_id"], "trace-resume", "recovery_decision", payload, digest(payload)), actor=actor)
            assert closed["operation_status"] == "committed" and closed["run_status"] == "halted"
            return captured.finish(coordinator)
        finally:
            coordinator.close()


def fresh_external_trace():
    """Capture real control consumption using only the declared domain adapter."""
    from test_external_consumption_control import normal_external
    identities = count(1)
    with patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=next(identities))):
        fixture = normal_external.__wrapped__()
        coordinator, plane, actor, _, request, adapter = next(fixture)
        try:
            captured = ControlTrace(coordinator.root, version="0.4")
            coordinator.observer = captured.observer
            result = plane.resume_run(request, actor=actor)
            assert result["operation_status"] == "committed" and result["domain_status"] == "succeeded"
            assert adapter.calls == 1 and plane.resume_run(request, actor=actor) == result and adapter.calls == 1
            return captured.finish(coordinator)
        finally:
            fixture.close()
