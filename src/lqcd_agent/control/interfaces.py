"""B02 versioned control entry points under construction; not the legacy CLI.

The Host constructs ActorContext only after authentication. Request payloads
cannot supply authority, filesystem roots, identities or passing decisions.
The explicit 0.4 adapter is separate from the unchanged default legacy CLI.
"""
from dataclasses import asdict, dataclass
import uuid

from lqcd_agent.artifacts.registry import ARTIFACT_SLOTS

from .budget import policy
from .checkpoints import checkpoint_payload, persist_checkpoint, verify_checkpoint
from .clock import Timestamp
from .coordinator import component, exclusive_directory, read_regular
from .execution import replay
from .integrity import validate_run_root
from .operations import BootstrapIntegrityError, TerminalOperations, bootstrap_admission
from .projections import attach_checkpoint, bounded_projection, checkpoint_manifest
from .protocol import operation_variant
from .records import build_record
from .strict_json import ControlIntegrityError, canonical_bytes, closed, digest, digest_value, loads, require, text


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    actor_type: str
    scopes: tuple[str, ...]

    def authorize(self, scope):
        text(self.actor_id)
        text(self.actor_type)
        require(type(self.scopes) is tuple and all(type(item) is str and item for item in self.scopes) and
                self.scopes == tuple(sorted(set(self.scopes))) and scope in self.scopes,
                "Missing trusted actor scope")
        return {"actor_id": self.actor_id, "actor_type": self.actor_type, "scopes": list(self.scopes)}


@dataclass(frozen=True)
class StartRunRequest:
    case_id: str
    root_inputs: dict
    root_inputs_digest: str
    idempotency_key: str
    profile_id: str = "balanced_v1"

    def canonical(self, actor):
        require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
        identity = actor.authorize("start")
        component(self.case_id)
        text(self.idempotency_key)
        frozen_inputs = loads(canonical_bytes(self.root_inputs))
        closed(frozen_inputs, ("root_goal", "input_snapshot"))
        require(all(type(value) is dict and value for value in frozen_inputs.values()), "Missing immutable root inputs")
        digest_value(self.root_inputs_digest)
        require(digest(frozen_inputs) == self.root_inputs_digest, "Root inputs digest mismatch")
        selected = policy(self.profile_id)
        return {"case_id": self.case_id, "root_inputs": frozen_inputs, "root_inputs_digest": self.root_inputs_digest,
                "profile_id": self.profile_id, "policy_digest": selected.value["policy_digest"], "actor": identity}


def _bootstrap_snapshot(output_root, operation, *, child=None):
    """Build one immutable bootstrap closure inside the reservation transaction."""
    reserved = operation["reservation"]
    locator = reserved["reserved_run_locator"] if child is None else reserved["reserved_child_run_locator"]
    root = output_root / locator["case_id"] / locator["run_id"]
    selected = policy(reserved["budget_policy_profile"] if child is None else reserved["child_policy_profile"]).value
    stamp = Timestamp(**operation["created_at"])
    root_inputs = operation["request"]["root_inputs"] if child is None else child["root_inputs"]
    decision = bootstrap_admission(operation["operation_id"], digest(root_inputs), selected)
    records = []

    def append(kind, event, **fields):
        record = build_record(kind, event, **locator, event_index=len(records) + 1,
                              previous_execution_head=digest(records[-1]) if records else None,
                              artifact_head=None, artifact_event_index=0, timestamp=stamp, **fields).value
        records.append(record)
        return record

    append("run", "created", parent_run_id=None if child is None else child["source_run_identity"]["run_id"],
           creation_reason="root" if child is None else child["creation_reason"],
           root_goal_reference={"reference": "root_goal.json", "sha256": digest(root_inputs["root_goal"])},
           input_snapshot_reference={"reference": "input_snapshot.json", "sha256": digest(root_inputs["input_snapshot"])},
           canonical_output_root=str(root), checkpoint_thread_id=f"{locator['case_id']}:{locator['run_id']}",
           status="initializing", policy_version="0.1", policy_digest=selected["policy_digest"])
    if child is not None:
        append("lineage", "lineage_initialized", creation_reason=child["creation_reason"],
               parent_operation_id=operation["operation_id"], source_snapshot_proof=reserved["source_snapshot_proof"],
               lineage_snapshot_digest=digest(reserved["source_snapshot_proof"]),
               source_runtime_fingerprint=child["source_runtime_fingerprint"], target_runtime_fingerprint=child["target_runtime_fingerprint"])
    append("budget", "policy_initialized", budget_event_id="budget_event_000001", budget_event_index=1,
           policy_version="0.1", policy_digest=selected["policy_digest"],
           payload={"policy": selected, "policy_reference": "budget_policy.json"})
    append("budget", "decision_recorded", budget_event_id="budget_event_000002", budget_event_index=2,
           policy_version="0.1", policy_digest=selected["policy_digest"], payload=decision)
    append("cycle", "created", cycle_id="cycle_0001", cycle_index=1, parent_cycle_id=None,
           trigger_reason="initial", created_by_attempt_id=None, status="active")
    append("attempt", "scheduled", cycle_id="cycle_0001", cycle_index=1, attempt_id="attempt_000001", attempt_index=1,
           parent_attempt_id=None, attempt_kind="method_planner", node_name="method_planner", attempt_trigger="initial",
           inbound_transition_id="transition_000001", status="scheduled", input_references={"current_artifact_ids": {}},
           output_references={"current_artifact_ids": {}}, error=None)
    append("transition", "committed", transition_id="transition_000001", transition_index=1, source="START",
           source_node="START", source_cycle_id=None, source_attempt_id=None, route="method_planner",
           target_node="method_planner", target_cycle_id="cycle_0001", target_attempt_id="attempt_000001",
           target_attempt_kind="method_planner", human_request_id=None, human_response_id=None, trigger_reason="initial",
           reason="bootstrap_initial_route", fields={}, evidence_references={}, applied_state_update_keys=[],
           applied_state_updates_sha256=digest({}), status="committed", committed_at=asdict(stamp))
    append("run_lifecycle", "transitioned", from_status="initializing", to_status="running", reason_code="bootstrap_completed",
           operation_id=operation["operation_id"], attempt_id=None, pause_id=None, budget_event_id="budget_event_000002")
    execution = replay(records)
    artifact_index = {"schema_version": "0.1", **locator, "revision": 0, "last_event_id": None,
                      "current": dict.fromkeys(ARTIFACT_SLOTS), "managed_projections": {},
                      "execution_head": execution.projection.value["execution_head"], "artifact_head": None}
    core = bounded_projection(execution, artifact_index=artifact_index, artifact_head=None, artifact_event_index=0)
    checkpoint_id = operation["operation_id"] + "_bootstrap"
    checkpoint = checkpoint_payload(checkpoint_id, core, stamp, operation_id=operation["operation_id"])
    manifest = checkpoint_manifest(execution, artifact_head=None, artifact_event_index=0, checkpoint_id=checkpoint_id,
                                   checkpoint_digest=digest(checkpoint), state_digest=core.digest).value
    from .pause import runtime_fingerprint
    return {"records": records, "artifact_index": artifact_index, "checkpoint": checkpoint, "manifest": manifest,
            "runtime_fingerprint": runtime_fingerprint() if child is None else child["target_runtime_fingerprint"],
            "projection": attach_checkpoint(core, execution, manifest).value,
            "run_creation_binding": {"operation_id": operation["operation_id"], "request_digest": operation["request_digest"],
                                     "idempotency_key_digest": digest(operation["idempotency_key"]),
                                     "run_created_digest": digest(records[0]), "policy_reference": "budget_policy.json",
                                     "policy_digest": selected["policy_digest"]}}


class ControlPlane:
    """Explicit versioned Host adapter; construction never executes a target."""

    def __init__(self, coordinator, *, worker_id, lease_seconds=30, route_adapter=None, resume_target_adapter=None, resume_decision_adapter=None, external_adapter=None, preparation_adapter=None, source_adapter=None):
        text(worker_id)
        self.coordinator = coordinator
        self.worker_id, self.lease_seconds = worker_id, lease_seconds
        self.route_adapter = route_adapter
        self.resume_target_adapter = resume_target_adapter
        self.resume_decision_adapter = resume_decision_adapter
        self.external_adapter = external_adapter
        self.preparation_adapter = preparation_adapter
        self.source_adapter = source_adapter

    def start_run(self, request, *, actor):
        require(type(request) is StartRunRequest, "Expected typed StartRunRequest")
        canonical = request.canonical(actor)
        selected = policy(request.profile_id)

        def reserve(operation_id, stamp):
            locator = {"case_id": request.case_id, "run_id": "run_" + uuid.uuid4().hex}
            return {"target_run_identity": locator, "reserved_run_locator": locator,
                    "canonical_budget_policy_bytes": selected.canonical.decode(),
                    "budget_policy_digest": selected.value["policy_digest"], "budget_policy_profile": request.profile_id,
                    "budget_policy_version": "0.1", "budget_policy_selection_authority": "authenticated_host_profile_selection",
                    "initial_invocation_capability_inputs": {"attempt_id": "attempt_000001", "target_kind": "method_planner"}}

        operation = self.coordinator.reserve("start_run", "not_applicable", "public_control", request.idempotency_key,
                                              canonical, self.worker_id, reserve, lease_seconds=self.lease_seconds,
                                              build_snapshot=lambda op: _bootstrap_snapshot(self.coordinator.root, op))
        if operation["status"] != "in_progress":
            if operation["error"] is not None and "close_operation_id" in operation["error"]:
                TerminalOperations(self.coordinator, self.worker_id, self.lease_seconds).continue_close(operation["error"]["close_operation_id"])
            return self.query_operation(operation["operation_id"])
        if operation["worker_owner_id"] != self.worker_id or self.coordinator._time().monotonic_seconds >= operation["lease_expires"]:
            if self.coordinator._time().monotonic_seconds < operation["lease_expires"]:
                return self.query_operation(operation["operation_id"])
            operation = self.coordinator.acquire(operation["operation_id"], self.worker_id, lease_seconds=self.lease_seconds)
        try:
            self._materialize_start(operation)
        except (ControlIntegrityError, OSError) as error:
            TerminalOperations(self.coordinator, self.worker_id, self.lease_seconds).fail_bootstrap(operation, error)
        return self.query_operation(operation["operation_id"])

    def query_operation(self, operation_id):
        operation = self.coordinator.get(operation_id)
        locator = operation["reservation"].get("reserved_run_locator", operation["reservation"].get("reserved_child_run_locator", operation["request"].get("run_locator")))
        closure = TerminalOperations(self.coordinator, self.worker_id, self.lease_seconds).closure(locator) if locator else None
        result = operation["result"] or {}
        return {"operation_id": operation_id, "operation_status": operation["status"], "operation_phase": operation["phase"],
                "phase_revision": operation["phase_revision"], "lease_epoch": operation["lease_epoch"],
                "result": operation["result"], "error": operation["error"],
                "terminal_closure": closure["terminal_closure"] if closure else result.get("terminal_closure", "not_applicable"),
                "run_status": closure["run_status"] if closure else result.get("run_status"),
                "domain_status": result.get("domain_status"),
                "publication_status": "materialization_pending" if operation["status"] == "in_progress" else "terminal"}

    def publish_pause(self, request, *, actor):
        """Trusted-only internal Pause publication, never an Agent entry point."""
        from .pause import PauseOperations
        require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
        actor.authorize("control.internal")
        operation = PauseOperations(self.coordinator, self.worker_id, self.lease_seconds).publish(request)
        return self.query_operation(operation["operation_id"])

    def resume_run(self, request, *, actor):
        from .pause import PauseOperations
        from .coordinator import boundary
        boundary(self.coordinator.observer, "resume.request", "before")
        try:
            require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
            operation = PauseOperations(self.coordinator, self.worker_id, self.lease_seconds, self.resume_target_adapter,
                                        self.resume_decision_adapter, self.external_adapter, self.preparation_adapter).resume(request, actor)
            return self.query_operation(operation["operation_id"])
        finally:
            boundary(self.coordinator.observer, "resume.request", "after")

    def replay_run(self, request, *, actor):
        from .children import ChildOperations
        require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
        operation = ChildOperations(self.coordinator, self.worker_id, self.lease_seconds, self.source_adapter).create(request, actor)
        return self.query_operation(operation["operation_id"])

    def fork_run(self, request, *, actor):
        from .children import ChildOperations
        require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
        operation = ChildOperations(self.coordinator, self.worker_id, self.lease_seconds, self.source_adapter).create(request, actor)
        return self.query_operation(operation["operation_id"])

    def cancel_pause(self, request, *, actor):
        from .pause import PauseOperations
        require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
        operation = PauseOperations(self.coordinator, self.worker_id, self.lease_seconds, external_adapter=self.external_adapter).cancel(request, actor)
        return self.query_operation(operation["operation_id"])

    def resolve_external_interrupt(self, request, *, actor):
        from .pause import ExternalInterrupt, PauseOperations
        require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
        operation = ExternalInterrupt(PauseOperations(self.coordinator, self.worker_id, self.lease_seconds,
                                      self.resume_target_adapter, self.resume_decision_adapter, self.external_adapter)).interrupt(request, actor)
        return self.query_operation(operation["operation_id"])

    def advance_run(self, request, *, actor):
        from .operations import AdvanceOperations
        require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
        operation = AdvanceOperations(self.coordinator, self.worker_id, self.lease_seconds, self.route_adapter).advance(request, actor)
        return self.query_operation(operation["operation_id"])

    def close_run(self, request, *, actor):
        require(type(actor) is ActorContext, "Missing Host-authenticated ActorContext")
        operation = TerminalOperations(self.coordinator, self.worker_id, self.lease_seconds).close(request, actor)
        return self.query_operation(operation["operation_id"])

    def _materialize_start(self, operation):
        from .capabilities import prepare_capability

        coordinator = self.coordinator
        with coordinator.failure_context(operation):
            snapshot = coordinator.snapshot(operation["operation_id"])
        locator = operation["reservation"]["reserved_run_locator"]
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        records = snapshot["records"]
        manifest = snapshot["manifest"]
        ledger = lambda count: b"".join(canonical_bytes(row) + b"\n" for row in records[:count])
        plans = {
            "run_root_created": [("root_goal.json", canonical_bytes(operation["request"]["root_inputs"]["root_goal"]), None),
                                 ("input_snapshot.json", canonical_bytes(operation["request"]["root_inputs"]["input_snapshot"]), None)],
            "policy_published": [("budget_policy.json", operation["reservation"]["canonical_budget_policy_bytes"].encode(), None)],
            "run_ledger_started": [("execution_history.jsonl", ledger(1), b"")],
            "bootstrap_records_complete": [("execution_history.jsonl", ledger(6), ledger(1)), ("artifact_history.jsonl", b"", None)],
            "running_lifecycle_recorded": [("execution_history.jsonl", ledger(7), ledger(6))],
            "checkpoint_committed": [("artifact_index.json", canonical_bytes(snapshot["artifact_index"]), None),
                                     ("checkpoints/" + manifest["checkpoint_id"] + ".json", canonical_bytes(manifest), None)],
        }
        declaration = operation_variant("start_run", "not_applicable")
        while operation["status"] == "in_progress":
            with coordinator.failure_context(operation):
                successors = [target for source, target in declaration["success_edges"] if source == operation["phase"]]
                require(len(successors) == 1, "Bootstrap must consume a generated linear successor")
                phase = successors[0]
                for path, content, previous in plans.get(phase, []):
                    coordinator.freeze_publication(operation["operation_id"], self.worker_id, operation["lease_epoch"],
                                                   operation["phase_revision"], phase, root / path, content, previous=previous)

                def publish(db, current):
                    try:
                        self._verify_start_prefix(root, plans, declaration, current, phase)
                        if declaration["phases"].index(current["phase"]) >= declaration["phases"].index("checkpoint_committed"):
                            verify_checkpoint(root, manifest)
                            validate_run_root(root, manifest=manifest, projection=snapshot["projection"])
                    except (ControlIntegrityError, OSError) as error:
                        raise BootstrapIntegrityError(str(error)) from error
                    if phase == "run_root_created":
                        exclusive_directory(root.parent)
                        exclusive_directory(root, observer=coordinator.observer, name="bootstrap")
                    if phase == "checkpoint_committed":
                        metadata = {"source": "input", "step": 0, "parents": {}, "operation_id": current["operation_id"]}
                        persist_checkpoint(coordinator, db, current, root, snapshot["checkpoint"], metadata)
                    for path, _, _ in plans.get(phase, []):
                        coordinator.materialize_publication(db, current, phase, root / path, name="bootstrap." + path)
                    if phase == "run_root_created":
                        return {"reserved_run_locator": locator, "current_lease_epoch": current["lease_epoch"]}
                    if phase == "policy_published":
                        return {"canonical_policy_bytes": current["reservation"]["canonical_budget_policy_bytes"],
                                "policy_digest": current["reservation"]["budget_policy_digest"]}
                    if phase == "run_ledger_started":
                        return {"run_created_initializing_record": snapshot["run_creation_binding"]}
                    if phase == "bootstrap_records_complete":
                        return {"policy_initialized": records[1], "bootstrap_allow_decision": records[2],
                                "initial_identity_closure": {"cycle": records[3], "attempt": records[4],
                                                             "invalidation": {"kind": "empty_new_run", "current": {}}},
                                "start_transition": records[5]}
                    if phase == "running_lifecycle_recorded":
                        return {"legal_run_lifecycle_edge": records[6], "exact_pre_head": digest(records[5])}
                    if phase == "checkpoint_committed":
                        verify_checkpoint(root, manifest)
                        state = validate_run_root(root, manifest=manifest, projection=snapshot["projection"])
                        db.execute("INSERT INTO run_controls VALUES (?,?,?)",
                                   (digest(locator), 1, canonical_bytes({"locator": locator, "projection": state.value, "manifest": manifest})))
                        return {"resulting_execution_head": manifest["execution_head"], "policy_digest": current["reservation"]["budget_policy_digest"]}
                    if phase == "invocation_capability_prepared":
                        return prepare_capability(coordinator, db, current, root, manifest, snapshot["projection"])
                    require(phase == "result_committed", "Missing generated bootstrap phase handler")
                    verify_checkpoint(root, manifest)
                    validate_run_root(root, manifest=manifest, projection=snapshot["projection"])
                    result = {"run_locator": locator, "run_status": "running", "terminal_closure": "not_applicable",
                              "execution_head": manifest["execution_head"], "artifact_head": None,
                              "checkpoint_head": manifest["checkpoint_head"], "pause_id": None,
                              "capability_id": "capability_" + current["operation_id"], "request_digest": current["request_digest"]}
                    return {"exact_public_or_internal_result": result, "final_phase_revision": current["phase_revision"] + 1}

                operation = coordinator.step(operation["operation_id"], self.worker_id, operation["lease_epoch"],
                                             operation["phase_revision"], phase, publish)

    @staticmethod
    def _verify_start_prefix(root, plans, declaration, operation, next_phase):
        """Reject phase-ahead, conflicting and unknown bytes before any append."""
        require(root == root.resolve(), "Run root is not canonical")
        completed = declaration["phases"].index(operation["phase"])
        expected = {}
        for phase in declaration["phases"][:completed + 1]:
            for path, content, previous in plans.get(phase, []):
                expected[path] = (content, content)
        required = set(expected)
        for path, content, previous in plans.get(next_phase, []):
            expected[path] = (previous, content)
        checkpoint_phase = "checkpoint_committed" if "checkpoint_committed" in declaration["phases"] else "child_checkpoint_committed"
        checkpoint_allowed = completed >= declaration["phases"].index(checkpoint_phase) or next_phase == checkpoint_phase
        physical = {"checkpoints/graph_checkpoints.sqlite", "checkpoints/graph_checkpoints.sqlite-wal",
                    "checkpoints/graph_checkpoints.sqlite-shm"} if checkpoint_allowed else set()
        if root.exists():
            for path in root.rglob("*"):
                require(not path.is_symlink(), "Symlink in managed bootstrap prefix")
                relative = path.relative_to(root).as_posix()
                if path.is_dir():
                    require(relative == "checkpoints" and checkpoint_allowed, "Unknown bootstrap directory")
                    continue
                require(relative in expected or relative in physical, "Unknown or phase-ahead bootstrap file")
                if relative in expected:
                    previous, content = expected[relative]
                    actual = read_regular(path)
                    require(actual == content or (previous is not None and actual.startswith(previous) and
                                                  content.startswith(actual) and (not actual or actual.endswith(b"\n"))),
                            "Conflicting or partial bootstrap publication")
        for relative, (previous, _) in expected.items():
            if relative in required or previous:
                require((root / relative).is_file(), "Phase is ahead of missing bootstrap bytes")
