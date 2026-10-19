"""Read-only A04 0.3 fixtures through a trusted historical-format reader.

These archived source inputs are not a new 0.3 runtime or relabelled 0.4 Run.
They contain no A06 policy/budget/bootstrap records. Only child creation uses
production 0.4 writers; the historical validator has no mutation interface.
"""
from harness.temporary import mkdtemp
from hashlib import sha256
from pathlib import Path
import sqlite3

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from lqcd_agent.control.checkpoints import CanonicalCheckpointSerializer
from lqcd_agent.control.children import ForkRunRequest, HistoricalSourceRead, ReplayRunRequest
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads, require


class Archived03Reader:
    """Validate the original fixture format; never calls a 0.4 source builder."""

    def read_source(self, root, view):
        records = [loads(line) for line in (root / "execution_history.jsonl").read_bytes().splitlines()]
        created = records[0]
        require(created["status"] == "initializing" and created["creation_reason"] == "root", "Invalid original Run")
        inputs = {k: loads((root / created[k + "_reference"]["reference"]).read_bytes()) for k in ("root_goal", "input_snapshot")}
        evidence = {name: sha256((root / name).read_bytes()).hexdigest() for name in ("execution_history.jsonl", "root_goal.json", "input_snapshot.json")}
        state = None
        if view["creation_reason"] == "fork_of":
            prior = None
            for index, record in enumerate(records, 1):
                require(record["event_index"] == index and record["previous_execution_head"] == prior, "Historical execution chain conflict")
                prior = digest(record)
            state = view["source_control"]["projection"] if view["source_control"] is not None else None
            require(state is not None and state["run_status"] == "paused" and records[-1]["status"] == "opened" and
                    records[-2]["record_type"] == "run_lifecycle" and records[-2]["to_status"] == "paused", "Historical Pause closure conflict")
            require(state["execution_head"] == prior and state["artifact_head"] is None and not view["selected_artifact_ids"], "Historical head conflict")
            evidence["artifact_index.json"] = sha256((root / "artifact_index.json").read_bytes()).hexdigest()
        return HistoricalSourceRead(inputs, created["runtime_fingerprint"], state, (), evidence)


def historical_source(coordinator):
    """Load immutable historical bytes and their original monotonic control state."""
    locator = {"case_id": "case", "run_id": "historical_03"}
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    root.mkdir(parents=True)
    inputs = {"root_goal": {"goal": "historical synthetic"}, "input_snapshot": {"data": "historical synthetic"}}
    references = {}
    for name, value in inputs.items():
        content = canonical_bytes(value)
        (root / (name + ".json")).write_bytes(content)
        references[name + "_reference"] = {"reference": name + ".json", "sha256": sha256(content).hexdigest()}
    fingerprint = {"control_protocol": digest("historical A04"), "application_build": digest("archived 0.3 application"),
        "graph_topology": digest("archived topology"), "state_schema": "0.3", "execution_schema": "0.3", "artifact_schema": "0.1",
        "langgraph": "archived", "checkpointer": "archived", "serializer": "archived"}
    records = []
    def append(kind, event, **fields):
        value = {"schema_version": "0.3", "record_type": kind, "event": event, **locator, "event_index": len(records) + 1,
                 "previous_execution_head": digest(records[-1]) if records else None, "artifact_head": None, "artifact_event_index": 0,
                 "created_at": {"source": "archived", "wall_seconds": 10, "monotonic_seconds": 0}, **fields}
        records.append(value)
        return value
    append("run", "created", parent_run_id=None, creation_reason="root", status="initializing", canonical_output_root=str(root),
           checkpoint_thread_id="case:historical_03", runtime_fingerprint=fingerprint, **references)
    append("cycle", "created", cycle_id="cycle_0001", cycle_index=1, parent_cycle_id=None, trigger_reason="initial", created_by_attempt_id=None, status="active")
    append("attempt", "scheduled", attempt_id="attempt_000001", attempt_index=1, cycle_id="cycle_0001", cycle_index=1,
           attempt_kind="method_planner", node_name="method_planner", status="scheduled", inbound_transition_id="transition_000001")
    append("transition", "committed", transition_id="transition_000001", transition_index=1, source="START", source_attempt_id=None,
           target_attempt_id="attempt_000001", target_node="method_planner", target_cycle_id="cycle_0001", status="committed")
    append("run_lifecycle", "transitioned", from_status="initializing", to_status="running", operation_id="original_start")
    append("attempt", "started", attempt_id="attempt_000001", status="running")
    append("attempt", "finished", attempt_id="attempt_000001", status="failed", error={"type": "HistoricalFailure", "message": "synthetic"})
    append("pause", "pause_prepared", pause_id="pause_000001", pause_index=1, status="prepared", reason="recovery_decision", runtime_fingerprint=fingerprint)
    append("run_lifecycle", "transitioned", from_status="running", to_status="paused", pause_id="pause_000001", operation_id="original_pause")
    opened = append("pause", "pause_opened", pause_id="pause_000001", pause_index=1, status="opened", reason="recovery_decision", runtime_fingerprint=fingerprint)
    (root / "execution_history.jsonl").write_bytes(b"".join(canonical_bytes(r) + b"\n" for r in records))
    (root / "artifact_history.jsonl").write_bytes(b"")
    index = {"schema_version": "0.1", **locator, "execution_head": digest(opened), "artifact_head": None, "revision": 0, "current": {}}
    (root / "artifact_index.json").write_bytes(canonical_bytes(index))
    state = {**locator, "checkpoint_thread_id": "case:historical_03", "run_status": "paused", "execution_head": digest(opened),
             "execution_event_index": len(records), "artifact_head": None, "artifact_event_index": 0,
             "active_pause": {"pause_id": "pause_000001", "status": "opened"}}
    checkpoint_id = "original_public_pause"
    payload = {"v": 4, "id": checkpoint_id, "ts": "1970-01-01T00:00:10+00:00", "channel_values": {"control": state},
               "channel_versions": {"control": 1}, "versions_seen": {}, "pending_sends": [], "updated_channels": ["control"],
               "lqcd_control_operation_id": "original_pause"}
    manifest = {**locator, "checkpoint_thread_id": state["checkpoint_thread_id"], "checkpoint_id": checkpoint_id,
                "checkpoint_digest": digest(payload), "state_digest": digest(state), "execution_head": digest(opened),
                "execution_event_index": len(records), "artifact_head": None, "artifact_event_index": 0}
    manifest["checkpoint_head"] = digest(manifest)
    (root / "checkpoints").mkdir()
    connection = sqlite3.connect(root / "checkpoints/graph_checkpoints.sqlite")
    with connection:
        saver = SqliteSaver(connection, serde=CanonicalCheckpointSerializer())
        saver.put({"configurable": {"thread_id": state["checkpoint_thread_id"], "checkpoint_ns": ""}}, payload,
                  {"source": "input", "step": 0, "parents": {}, "operation_id": "original_pause"}, payload["channel_versions"])
    connection.close()
    (root / "checkpoints/original_public_pause.json").write_bytes(canonical_bytes(manifest))
    with coordinator.transaction() as db:
        db.execute("INSERT INTO run_controls VALUES (?,?,?)", (digest(locator), 1, canonical_bytes({"locator": locator, "projection": None, "manifest": None})))
    with coordinator.transaction() as db:
        db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes({"locator": locator,
            "projection": {**state, "checkpoint_head": manifest["checkpoint_head"]}, "manifest": manifest}), digest(locator)))
        db.execute("INSERT INTO pause_ownership VALUES (?,?,?,?)", (digest(locator), "pause_000001", 1,
            canonical_bytes({"publication_owner": "original_pause", "status": "opened", "owner": None, "opened_head": digest(opened)})))
    return locator, inputs, digest(opened)


@pytest.fixture
def historical():
    output = Path(mkdtemp(prefix="lqcd-agent-b02-history-", dir="/private/tmp"))
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    plane = ControlPlane(coordinator, worker_id="child", source_adapter=Archived03Reader())
    actor = ActorContext("operator", "human", ("fork", "policy.select", "replay"))
    locator, inputs, head = historical_source(coordinator)
    try:
        yield coordinator, plane, actor, locator, inputs, head
    finally:
        coordinator.close()


@pytest.mark.parametrize("fork", [False, True])
def test_historical_source_creates_fresh_child_without_source_mutation(historical, fork):
    coordinator, plane, actor, locator, inputs, head = historical
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    source_control = tuple(coordinator.connection.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone())
    request = ForkRunRequest(locator, "historical-child", head) if fork else ReplayRunRequest(locator, "historical-child", digest(inputs))
    create = plane.fork_run if fork else plane.replay_run
    result = create(request, actor=actor)
    assert result["operation_status"] == "committed" and result["run_status"] == "running", result
    assert create(request, actor=actor) == result
    child = result["result"]["run_locator"]
    records = parse_ledger((coordinator.root / child["case_id"] / child["run_id"] / "execution_history.jsonl").read_bytes()).values
    assert records[1]["source_snapshot_proof"]["source_schema"] == "0.3"
    assert records[1]["source_runtime_fingerprint"]["execution_schema"] == "0.3"
    assert records[1]["target_runtime_fingerprint"]["execution_schema"] == "0.4"
    assert records[2]["payload"]["policy"]["profile_id"] == "balanced_v1"
    assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert tuple(coordinator.connection.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()) == source_control


@pytest.mark.parametrize("fault", ["policy", "input", "fingerprint", "reader_absent", "revision_absent", "claimed", "stale_head", "checkpoint", "foreign"])
def test_historical_invalid_source_rejects_before_child_reservation(historical, fault):
    from dataclasses import replace
    coordinator, plane, actor, locator, inputs, head = historical
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    fork = fault in ("revision_absent", "claimed", "stale_head", "checkpoint")
    if fault == "policy":
        (root / "budget_policy.json").write_bytes(b"{}")
    elif fault == "input":
        (root / "root_goal.json").write_bytes(b'{"goal":"changed"}')
    elif fault == "fingerprint":
        class WrongFingerprint(Archived03Reader):
            def read_source(self, source_root, view):
                read = super().read_source(source_root, view)
                return replace(read, runtime_fingerprint={**read.runtime_fingerprint, "application_build": digest("new build")})
        plane.source_adapter = WrongFingerprint()
    elif fault == "reader_absent":
        plane.source_adapter = None
    elif fault == "revision_absent":
        with coordinator.transaction() as db:
            db.execute("DELETE FROM pause_ownership WHERE run_key=?", (digest(locator),))
            db.execute("DELETE FROM run_controls WHERE run_key=?", (digest(locator),))
    elif fault == "claimed":
        with coordinator.transaction() as db:
            row = db.execute("SELECT value FROM pause_ownership WHERE run_key=?", (digest(locator),)).fetchone()
            pause = loads(row[0])
            pause["owner"] = "original_resume"
            db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes(pause), digest(locator)))
            db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (digest(locator),))
    elif fault == "stale_head":
        head = digest("old checkpoint")
    elif fault == "checkpoint":
        with coordinator.transaction() as db:
            row = db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()
            value = loads(row[0])
            value["manifest"]["checkpoint_digest"] = digest("changed checkpoint")
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes(value), digest(locator)))
    elif fault == "foreign":
        path = root / "execution_history.jsonl"
        rows = [loads(line) for line in path.read_bytes().splitlines()]
        rows[0]["run_id"] = "foreign"
        path.write_bytes(b"".join(canonical_bytes(r) + b"\n" for r in rows))
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    request = ForkRunRequest(locator, "rejected-child", head) if fork else ReplayRunRequest(locator, "rejected-child", digest(inputs))
    with pytest.raises(ControlIntegrityError):
        (plane.fork_run if fork else plane.replay_run)(request, actor=actor)
    assert coordinator.lookup_key("public_control", "rejected-child") is None
    assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("fork_first", [False, True])
def test_historical_fork_snapshot_and_claim_serialize_in_two_processes(historical, fork_first):
    from dataclasses import asdict
    import multiprocessing
    from helpers.process_client import historical_child_client, historical_claim_client
    coordinator, plane, actor, locator, inputs, head = historical
    context = multiprocessing.get_context("spawn")
    request = ForkRunRequest(locator, "competing-fork", head)
    original_revision = coordinator.connection.execute("SELECT revision FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()[0]
    parent, child = context.Pipe()
    worker = context.Process(target=historical_child_client, args=(child, str(coordinator.root), asdict(request), True), kwargs={"hold_snapshot": fork_first})
    def claim():
        receiver, sender = context.Pipe()
        process = context.Process(target=historical_claim_client, args=(sender, str(coordinator.root), locator))
        try:
            process.start()
            sender.close()
            assert receiver.poll(10) and receiver.recv() == "claimed"
            process.join(10)
            assert process.exitcode == 0
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            receiver.close()
    try:
        if not fork_first:
            claim()
        worker.start()
        child.close()
        if fork_first:
            assert parent.poll(10)
            status, frozen = parent.recv()
            assert status == "snapshot_frozen" and frozen["source_control_revision"] == original_revision
            claim()
            parent.send("continue")
        assert parent.poll(10)
        status, result = parent.recv()
        worker.join(10)
        assert worker.exitcode == 0
        if fork_first:
            assert status == "result" and result["operation_status"] == "committed", result
            assert coordinator.get(result["operation_id"])["reservation"]["source_snapshot_proof"] == frozen
        else:
            assert status == "rejected" and coordinator.lookup_key("public_control", "competing-fork") is None
        assert coordinator.connection.execute("SELECT revision FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()[0] == original_revision + 1
    finally:
        if worker.is_alive():
            worker.kill()
            worker.join()
        parent.close()


def test_historical_fork_reads_live_wal_without_changing_source_files(historical):
    coordinator, plane, actor, locator, inputs, head = historical
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    database = root / "checkpoints/graph_checkpoints.sqlite"
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        connection.execute("PRAGMA wal_autocheckpoint=0")
        payload = loads(connection.execute("SELECT checkpoint FROM checkpoints").fetchone()[0])
        payload["ts"] = "1970-01-01T00:00:11+00:00"
        connection.execute("UPDATE checkpoints SET checkpoint=?", (canonical_bytes(payload),))
        connection.commit()
        with coordinator.transaction() as db:
            value = loads(db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()[0])
            manifest = value["manifest"]
            manifest["checkpoint_digest"] = digest(payload)
            manifest.pop("checkpoint_head")
            manifest["checkpoint_head"] = digest(manifest)
            value["projection"]["checkpoint_head"] = manifest["checkpoint_head"]
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes(value), digest(locator)))
            (root / "checkpoints/original_public_pause.json").write_bytes(canonical_bytes(manifest))
        main_only = sqlite3.connect(database.as_uri() + "?immutable=1", uri=True)
        try:
            assert digest(loads(main_only.execute("SELECT checkpoint FROM checkpoints").fetchone()[0])) != digest(payload)
        finally:
            main_only.close()
        assert Path(str(database) + "-wal").stat().st_size > 0
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        result = plane.fork_run(ForkRunRequest(locator, "wal-child", head), actor=actor)
        assert result["operation_status"] == "committed", result
        assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    finally:
        connection.close()


@pytest.mark.parametrize("encoding", ["execution_0_4", "canonical_json", "omitted"])
def test_historical_fork_exposes_missing_trace_source_kind(historical, encoding):
    """Diagnostic only: runtime success is not passing B02 trace acceptance."""
    from harness.strict_json import Invalid
    from harness.trace import event, normalize
    from helpers.control_traces import ControlTrace
    from helpers.trace_sources import current_binding
    from harness.trace_proof import source_object
    coordinator, plane, actor, locator, inputs, head = historical
    result = plane.fork_run(ForkRunRequest(locator, "trace-gap-child", head), actor=actor)
    assert result["operation_status"] == "committed"
    capture = ControlTrace(coordinator.root)
    capture.events.append(event("fork_child_checkpoint", run_id=result["result"]["run_locator"]["run_id"],
        execution_head=result["result"]["execution_head"], checkpoint_head=result["result"]["checkpoint_head"],
        operation_id=result["operation_id"], outcome="committed"))
    trace = capture.finish(coordinator)
    historical_objects = [row for row in trace["proof"]["objects"] if row["kind"] == "execution_0_4" and row["value"].get("schema_version") == "0.3"]
    assert historical_objects
    if encoding != "execution_0_4":
        trace["proof"]["objects"] = [row for row in trace["proof"]["objects"] if row not in historical_objects]
        if encoding == "canonical_json":
            trace["proof"]["objects"].extend(source_object("canonical_json", row["value"]) for row in historical_objects)
    with pytest.raises(Invalid) as rejected:
        normalize(trace, binding=current_binding())
    # The historical execution head is real; relabelling it cannot satisfy 0.4 replay.
    assert rejected.value.error["category"] == "invalid_evidence"
    assert rejected.value.error["field_path"] == {"execution_0_4": "source_validation", "canonical_json": "reference_kind", "omitted": "missing_reference"}[encoding]
    (coordinator.root / "historical-trace-gap.json").write_bytes(canonical_bytes({
        "runtime_status": result["operation_status"], "validation_error": rejected.value.error,
        "source_schema": "0.3", "trace_schema": "0.2", "attempted_encoding": encoding,
        "cause": str(rejected.value.__cause__), "trace": trace}))
