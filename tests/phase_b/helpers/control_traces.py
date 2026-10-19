"""Capture actual B02 boundaries and their complete raw authority references."""
from harness.temporary import mkdtemp
from itertools import count
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
import uuid
from hashlib import sha256

from harness.a05_trace import BUNDLE_MEMBERS, material_source, typed_source
from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.pause import PublishPauseRequest, ResumeRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.code_agent.schemas import task_context

from harness.trace import event
from harness.trace_proof import source_object
from helpers.trace_sources import current_binding


class ControlTrace:
    def __init__(self, output, *, version="0.2", ordinary_sources=None):
        self.output, self.events, self.observed_records = output, [], set()
        self.version = version
        self.ordinary_sources = ordinary_sources

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
                    owner="historical_source" if self.version in ("0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "0.10", "0.11") and record["schema_version"] == "0.3" else "production_control",
                    ephemeral={"output_root": str(path.parent)}))
        if name.startswith("control."):
            self.events.append(event(name, operation_id=value["operation_id"], phase=value["phase"],
                phase_revision=value["phase_revision"], lease_epoch=value["lease_epoch"], status=value["status"],
                owner=value["worker_owner_id"], result_digest=digest(value["result"]) if value["result"] is not None else None,
                outcome="committed_phase"))

    def finish(self, coordinator):
        if self.version in ("0.6", "0.7", "0.8", "0.9", "0.10", "0.11"):
            self.observer("invocation.attempt_source_prefix", "after", {})
        events = self.events
        if self.version in ("0.8", "0.9", "0.10", "0.11"):
            # An after callback runs before its enclosing transaction commits.
            # Keep all observations, but attest only durable journal phases.
            phases, latest = {}, {}
            for position, observed in enumerate(self.events):
                if not observed["event"].startswith("control."):
                    continue
                identity = observed["operation_id"]
                if identity not in phases:
                    phases[identity] = {row["revision"]: row for row in coordinator.history(identity)}
                durable = phases[identity].get(observed["phase_revision"])
                if durable is None:
                    assert observed["phase_revision"] > coordinator.get(identity)["phase_revision"]
                    continue
                assert durable["phase"] == observed["phase"] and durable["lease_epoch"] == observed["lease_epoch"]
                if observed["result_digest"] is not None:
                    assert digest(durable["evidence"]["exact_public_or_internal_result"]) == observed["result_digest"]
                key = identity, observed["phase_revision"], observed["lease_epoch"]
                if key in latest:
                    assert self.events[latest[key]] == observed
                latest[key] = position
            retained = set(latest.values())
            events = [observed for position, observed in enumerate(self.events)
                      if not observed["event"].startswith("control.") or position in retained]
        candidates, sources = {}, {}
        source_version = "0.4" if self.version in ("0.5", "0.6", "0.7", "0.8", "0.9", "0.10", "0.11") else self.version
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
        if self.version in ("0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "0.10", "0.11"):
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
            historical = self.version in ("0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "0.10", "0.11") and records[0]["schema_version"] == "0.3"
            for record in records:
                item = source_object("historical_execution_0_3" if historical else "execution_0_4", record, version=source_version)
                sources[item["sha256"]] = item
                if self.version in ("0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "0.10", "0.11") and record["record_type"] == "lineage":
                    proof = record["source_snapshot_proof"]
                    collect(proof)
                    if proof["source_snapshot_kind"] == "fork_head":
                        collect({"source_run_identity": proof["source_run_identity"],
                                 "revision": proof["source_control_revision"], "heads": proof["source_latest_heads"]})
            for manifest_path in root.glob("checkpoints/*.json"):
                manifest = loads(manifest_path.read_bytes())
                item = source_object("historical_checkpoint_manifest_0_3" if historical else "checkpoint_manifest", manifest, version=source_version)
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
        failure_sources = []
        if self.version == "0.11":
            from harness.unconsumed_code_final_trace import read_consumption_failure
            for row in coordinator.connection.execute("SELECT value FROM external_operations"):
                failure = read_consumption_failure(coordinator, loads(row[0]))
                if failure is not None:
                    wrapper = {"durable_consumption_failure": failure}
                    collect(wrapper)
                    failure_sources.append(digest(wrapper))
        used = {}
        def use(head):
            if head in used:
                return
            row = sources.get(head)
            if row is None:
                assert head in candidates, ("Missing raw preimage", head)
                row = source_object("canonical_json", candidates[head], version=source_version)
            used[head] = row
            for ref in row["references"]:
                use(ref["sha256"])
        for head in failure_sources:
            use(head)
        for observed in events:
            for field in ("execution_head", "artifact_head", "checkpoint_head", "result_digest"):
                if observed[field] is not None:
                    use(observed[field])
        proof = {"schema_version": "0.1", "binding": current_binding(), "objects": list(used.values()), "output_roots": roots}
        if self.version in ("0.5", "0.6", "0.7", "0.8", "0.9", "0.10", "0.11"):
            proof.update(schema_version="0.2", typed_sources=[], material_sources=[], workspace_roots=[])
            executions = {}
            for row in used.values():
                if row["kind"] == "execution_0_4":
                    value = row["value"]
                    executions.setdefault((value["case_id"], value["run_id"]), {})[value["event_index"]] = value
            for run in executions.values():
                for position, value in list(run.items()):
                    if value["record_type"] != "budget" or value["event"] != "active_interval_settled":
                        continue
                    payload = value["payload"]
                    if self.version == "0.11" and payload["stage"] == "attempt_active":
                        from harness.unconsumed_code_final_trace import read_consumption_failure
                        row = coordinator.connection.execute("SELECT value FROM external_operations WHERE external_operation_id=?",
                                                             (payload["producer_operation_id"],)).fetchone()
                        failure = read_consumption_failure(coordinator, loads(row[0])) if row else None
                        if failure is not None and value in failure["active_settlements"]:
                            continue
                    if payload["stage"] == "host_setup":
                        previous = run[position - 1]
                        evidence = {"producer_operation_id": payload["producer_operation_id"],
                                    "pause_id": previous["pause_id"], "paused_lifecycle_head": digest(previous)}
                    else:
                        following = run[position + 1]
                        evidence = {"status": following["status"], "artifact_head": value["artifact_head"]}
                        if digest(evidence) != payload["evidence_digest"]:
                            matches = [candidate for candidate in candidates.values() if
                                       set(candidate) == {"artifact_status", "member_contents", "result_semantics", "state_members"} and
                                       digest({"delivery_digest": digest(candidate),
                                               "artifact_head": value["artifact_head"]}) == payload["evidence_digest"]]
                            assert len(matches) == 1
                            delivery = matches[0]
                            item = source_object("canonical_json", delivery, version="0.4")
                            if item["sha256"] not in used:
                                used[item["sha256"]] = item
                                proof["objects"].append(item)
                            proof["typed_sources"].append(typed_source("delivery", delivery))
                            evidence = {"delivery_digest": digest(delivery), "artifact_head": value["artifact_head"]}
                    assert digest(evidence) == payload["evidence_digest"]
                    item = source_object("canonical_json", evidence, version="0.4")
                    if item["sha256"] not in used:
                        used[item["sha256"]] = item
                        proof["objects"].append(item)
            for row in list(used.values()):
                value = row["value"]
                if not (value.get("slot") == "code" and value.get("event") == "registered"):
                    continue
                root = next(Path(item["path"]) for item in roots if
                            (item["case_id"], item["run_id"]) == (value["case_id"], value["run_id"]))
                task = loads((root / "attempts" / value["attempt_id"] / "code_agent_task.json").read_bytes())
                manifest = loads((root / "attempts" / value["attempt_id"] / "workspace_manifest.json").read_bytes())
                owner = {key: task[key] for key in ("case_id", "run_id", "attempt_id", "producer_operation_id")}
                owner["workspace_id"] = manifest["workspace_id"]

                def add_json(kind, raw):
                    parsed = loads(raw)
                    item = source_object("canonical_json", parsed, version="0.4")
                    assert raw == canonical_bytes(parsed) and item["sha256"] == sha256(raw).hexdigest()
                    if item["sha256"] not in used:
                        used[item["sha256"]] = item
                        proof["objects"].append(item)
                    declaration = typed_source(kind, parsed)
                    if declaration not in proof["typed_sources"]:
                        proof["typed_sources"].append(declaration)

                for member in value["members"]:
                    path = root / member["canonical_path"]
                    assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root)
                    raw = path.read_bytes()
                    assert sha256(raw).hexdigest() == member["sha256"] and len(raw) == member["size_bytes"]
                    kind = BUNDLE_MEMBERS[path.name]
                    if kind in ("material", "tool_audit"):
                        if self.version in ("0.8", "0.9", "0.10", "0.11") and kind == "tool_audit":
                            proof["material_sources"].append({"kind": "canonical_tool_audit", "sha256": sha256(raw).hexdigest(),
                                                              "content": raw.decode("utf-8"), "owner": dict(owner)})
                        else:
                            proof["material_sources"].append(material_source(kind, raw, owner))
                    else:
                        add_json(kind, raw)
                add_json("code_context", canonical_bytes(task_context(task)))
                if self.version in ("0.6", "0.7", "0.8", "0.9", "0.10", "0.11"):
                    from lqcd_agent.code_agent.workspace import scan_tree
                    verification_path = root / "attempts" / value["attempt_id"] / "verification_results.json"
                    verification = loads(verification_path.read_bytes())
                    commands = {spec["spec_id"]: spec for spec in task["verification_specs"]}
                    run_records = executions[value["case_id"], value["run_id"]].values()
                    reserved_commands = [record for record in run_records if record.get("event") == "resource_reserved" and
                                         record["payload"]["resource_kind"] == "verification_command" and
                                         record["payload"]["attempt_id"] == value["attempt_id"]]
                    if reserved_commands:
                        tree = scan_tree(coordinator.root / "verification_workspaces" / (value["attempt_id"] + "_verification"))
                        tree_preimage = {name: sha256(raw).hexdigest() for name, raw in sorted(tree.items())}
                        item = source_object("canonical_json", tree_preimage, version="0.4")
                        if item["sha256"] not in used:
                            used[item["sha256"]] = item
                            proof["objects"].append(item)
                        for reservation in reserved_commands:
                            assert reservation["payload"]["input_digest"] == digest(tree_preimage)
                            name = reservation["payload"]["resource_operation_id"].rsplit(":", 1)[1]
                            spec = commands[name]
                            assert reservation["payload"]["config_digest"] == digest(spec)
                            item = source_object("canonical_json", spec, version="0.4")
                            if item["sha256"] not in used:
                                used[item["sha256"]] = item
                                proof["objects"].append(item)
                            result = next(result for result in verification["spec_results"] if result["spec_id"] == name)
                            add_json("verification", canonical_bytes(result))
                for candidate in candidates.values():
                    if (candidate.get("schema_version") == "0.1" and
                            candidate.get("operation_contract_digest") == digest({
                                key: item for key, item in candidate.items() if key != "operation_contract_digest"}) and
                            candidate.get("task_digest") == task["task_digest"] and
                            candidate.get("workspace_manifest_digest") == manifest["manifest_digest"] and
                            "reservation_digest" in candidate):
                        add_json("core", canonical_bytes(candidate))
                upstream = root / "code_agent_control" / value["attempt_id"]
                for kind, name in (("external_result", "code_agent_external_result.json"),
                                   ("external_final", "external_final_evidence.json")):
                    path = upstream / name
                    if path.is_file():
                        add_json(kind, path.read_bytes())
                for (raw,) in coordinator.connection.execute("SELECT value FROM external_operations"):
                    operation = loads(raw)
                    if (operation["attempt_id"] == value["attempt_id"] and
                            operation["run_locator"] == {"case_id": value["case_id"], "run_id": value["run_id"]} and
                            operation["terminal_evidence_reference"] is not None):
                        path = root / operation["terminal_evidence_reference"]
                        assert path == path.resolve() and path.is_relative_to(root) and not path.is_symlink()
                        content = path.read_bytes()
                        assert sha256(content).hexdigest() == operation["terminal_evidence_digest"]
                        add_json("external_final", content)
        if self.version in ("0.9", "0.10", "0.11"):
            registered_tasks = {row["source_sha256"] for row in proof["typed_sources"] if row["kind"] == "task"}
            for (stored,) in coordinator.connection.execute("SELECT value FROM external_operations"):
                producer = loads(stored)
                prestart = producer.get("prestart", {})
                if "task" not in prestart or digest(prestart["task"]) in registered_tasks:
                    continue
                def prepared_source(kind, value):
                    item = source_object("canonical_json", value, version="0.4")
                    if item["sha256"] not in used:
                        used[item["sha256"]] = item
                        proof["objects"].append(item)
                    declaration = typed_source(kind, value)
                    if declaration not in proof["typed_sources"]:
                        proof["typed_sources"].append(declaration)
                for kind in ("task", "manifest", "core"):
                    if kind in prestart:
                        prepared_source(kind, prestart[kind])
                prepared_source("code_context", task_context(prestart["task"]))
                if producer["terminal_evidence_reference"] is not None:
                    root = coordinator.root / producer["run_locator"]["case_id"] / producer["run_locator"]["run_id"]
                    raw = (root / producer["terminal_evidence_reference"]).read_bytes()
                    assert sha256(raw).hexdigest() == producer["terminal_evidence_digest"]
                    prepared_source("external_final", loads(raw))
        trace = {"schema_version": self.version, "representation": "raw_with_proof", "events": events,
                 "proof": proof}
        if self.version in ("0.6", "0.7", "0.8", "0.9", "0.10", "0.11"):
            assert self.ordinary_sources is not None
            self.ordinary_sources.finish(trace)
        return trace


def fresh_recovery_trace():
    output = Path(mkdtemp(prefix="lqcd-agent-b02-trace-", dir="/private/tmp"))
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
    identities = count(4)
    with patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=next(identities))):
        fixture = normal_external.__wrapped__()
        coordinator, plane, actor, _, request, adapter = next(fixture)
        try:
            captured = ControlTrace(coordinator.root, version="0.5")
            coordinator.observer = captured.observer
            result = plane.resume_run(request, actor=actor)
            assert result["operation_status"] == "committed" and result["domain_status"] == "succeeded"
            assert adapter.calls == 1 and plane.resume_run(request, actor=actor) == result and adapter.calls == 1
            return captured.finish(coordinator)
        finally:
            fixture.close()
