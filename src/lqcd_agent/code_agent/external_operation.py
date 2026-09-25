"""Initial producer authority in the existing project coordinator."""
from hashlib import sha256
import uuid

from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.coordinator import boundary, read_regular
from lqcd_agent.control.execution import append_record_bytes, parse_ledger
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.records import build_record
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, number, require, text


class ExternalProducer:
    """A trusted Host entry point; callers cannot supply a producer identity."""

    def __init__(self, coordinator):
        self.coordinator = coordinator

    def lookup(self, producer_operation_id):
        """Read the original producer without renewing leases or creating work."""
        return ExternalControl(self.coordinator).read(self.coordinator.connection, producer_operation_id)

    def recover_setup(self, producer_operation_id, *, worker_id, lease_seconds):
        """Fence exact setup publication after the original effect window expires."""
        text(worker_id)
        number(lease_seconds)
        require(lease_seconds > 0, "Invalid setup recovery lease")
        with self.coordinator.transaction() as db:
            value = ExternalControl(self.coordinator).read(db, producer_operation_id)
            active = value.get("prestart", {}).get("active_time")
            require(active is not None and not active["published"] and
                    value["operation_phase"] == "external_operation_reserved" and value["resolution_owner"] is None,
                    "Setup recovery has no unpublished original suffix")
            require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?",
                               (digest(value["run_locator"]),)).fetchone() is None,
                    "Setup recovery lost terminal ownership")
            now = self.coordinator._time().monotonic_seconds
            deadline = active["setup_record"]["payload"]["deadline_monotonic_seconds"]
            if active.get("recovery_only") is True and now < active["recovery_expires_at"]:
                return value
            if now >= min(value["worker_lease_expires_at"], value["hard_deadline"], deadline):
                prior = value["phase_revision"]
                value["lease_epoch"] += 1
                value["worker_owner_id"] = worker_id
                value["worker_lease_expires_at"] = now + lease_seconds
                value["phase_revision"] = prior + 1
                active.update(recovery_only=True, recovery_epoch=value["lease_epoch"],
                              recovery_expires_at=now + lease_seconds)
                require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                                   (value["phase_revision"], canonical_bytes(value), producer_operation_id, prior)).rowcount == 1,
                        "Setup recovery CAS lost")
            return value

    def reserve(self, capability_id, *, backend_kind, backend_version, hard_deadline, worker_id, lease_seconds):
        for value in (backend_kind, backend_version, worker_id):
            text(value)
        number(hard_deadline)
        number(lease_seconds)
        require(lease_seconds > 0, "External worker lease must be positive")
        coordinator = self.coordinator
        leases = InvocationLeases(coordinator)
        with coordinator.transaction(commit_boundary="external.external_operation_reserved") as db:
            _, capability = leases.get(capability_id, db=db)
            authorization = capability["authorization"]
            identity = authorization["identity"]
            require(authorization["scope"] == "external_prestart_only" and identity["attempt_kind"] == "code_agent",
                    "Producer requires a canonical Code prestart target")
            parent = coordinator.get(authorization["producer_operation_id"], db=db)
            require(parent["operation_type"] == "advance_run" and parent["status"] == "committed" and
                    parent["phase"] == "result_committed" and
                    parent["phase_revision"] == authorization["activation_result_revision"] and
                    parent["result"]["capability_id"] == capability_id and
                    all(parent["result"].get(key) == value for key, value in authorization["heads"].items()),
                    "Producer target lacks its exact committed parent")
            locator = {key: identity[key] for key in ("case_id", "run_id")}
            external = ExternalControl(coordinator)
            existing = [external.read(db, row[0]) for row in db.execute("SELECT external_operation_id FROM external_operations")]
            same_target = [row for row in existing if row["run_locator"] == locator and row["attempt_id"] == identity["attempt_id"]]
            require(len(same_target) <= 1, "Multiple producers own one Code target")
            if same_target:
                saved = same_target[0]
                require(saved["parent_control_operation_id"] == parent["operation_id"] and
                        saved["cycle_id"] == authorization["projection"]["cycle_id"] and
                        (saved["backend_kind"], saved["backend_version"], saved["hard_deadline"]) ==
                        (backend_kind, backend_version, hard_deadline), "Conflicting producer reservation")
                return saved
            require(not external.attached(db, locator), "Run already has an attached producer")
            require(capability["state"] == "unclaimed" and capability["started_intent"] is None,
                    "Producer target has already been claimed")
            require(authorization["terminal_closure_revision"] == 0 and
                    db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (digest(locator),)).fetchone() is None,
                    "Terminal ownership revoked producer admission")
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            require(root == root.resolve() and root.is_relative_to(coordinator.root), "Producer Run path changed")
            state = leases._validate_anchor(root, authorization).value
            require(state["run_status"] == "running" and state["attempt_status"] == "scheduled" and
                    state["attempt_kind"] == "code_agent" and
                    all(state[key] == value for key, value in identity.items()), "Producer target is not scheduled")
            require(sha256(read_regular(root / "artifact_history.jsonl")).hexdigest() == authorization["artifact_history_digest"],
                    "Producer artifact authorization changed")
            clock_stamp = coordinator._time()
            now = clock_stamp.monotonic_seconds
            require(hard_deadline > now, "Producer deadline already expired")
            clock_epoch = getattr(coordinator.clock, "epoch_id", None)
            text(clock_epoch)
            execution = parse_ledger(read_regular(root / "execution_history.jsonl"))
            index = loads(read_regular(root / "artifact_index.json"))
            control_row = db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()
            require(control_row is not None and execution.projection.value["execution_head"] == authorization["heads"]["execution_head"],
                    "Producer source head changed")
            dimensions = execution.projection.value["budget"]["dimensions"]
            run_remaining = dimensions["active_seconds_per_run"]["remaining"]
            attempt_remaining = dimensions["active_seconds_per_attempt"]["remaining"]
            deadline_remaining = hard_deadline - now
            backend_maximum = min(deadline_remaining / 2, attempt_remaining / 2)
            setup_maximum = min(deadline_remaining - backend_maximum, run_remaining / 3)
            attempt_maximum = min(attempt_remaining - backend_maximum, run_remaining - setup_maximum - backend_maximum)
            require(min(setup_maximum, backend_maximum, attempt_maximum) > 0 and
                    setup_maximum + backend_maximum <= deadline_remaining,
                    "Producer lacks a complete active-time envelope")
            producer = "external_" + uuid.uuid4().hex
            workspace = "workspace_" + producer
            event_index = execution.projection.value["budget"]["budget_event_index"] + 1
            interval_id = producer + ":host_setup"
            setup_record = build_record("budget", "active_interval_reserved", **locator,
                event_index=len(execution.values) + 1, previous_execution_head=execution.projection.value["execution_head"],
                artifact_head=index["artifact_head"], artifact_event_index=index["revision"], timestamp=clock_stamp,
                budget_event_id=f"budget_event_{event_index:06d}", budget_event_index=event_index,
                policy_version="0.1", policy_digest=execution.projection.value["budget"]["policy_digest"],
                payload={"schema_version": "active_time_0.1", "interval_id": interval_id, "stage": "host_setup",
                         "attempt_id": identity["attempt_id"], "producer_operation_id": producer,
                         "owner_operation_id": producer, "clock_epoch_id": clock_epoch,
                         "start_at": {"source": clock_stamp.source, "wall_seconds": clock_stamp.wall_seconds,
                                      "monotonic_seconds": clock_stamp.monotonic_seconds},
                         "maximum_seconds": setup_maximum, "run_remaining_before": run_remaining,
                         "attempt_remaining_before": None, "deadline_monotonic_seconds": now + setup_maximum}).value
            previous_ledger = read_regular(root / "execution_history.jsonl")
            setup_content = append_record_bytes(previous_ledger, setup_record)
            stub = {
                "schema_version": "0.1", "producer_operation_id": producer,
                "parent_control_operation_id": parent["operation_id"], "run_locator": locator,
                "cycle_id": state["cycle_id"], "attempt_id": identity["attempt_id"], "workspace_id": workspace,
                "managed_workspace_locator_digest": digest({"run_locator": locator, "workspace_id": workspace}),
                "backend_kind": backend_kind, "backend_version": backend_version, "hard_deadline": hard_deadline,
                "worker_owner_id": worker_id, "worker_lease_expires_at": min(now + lease_seconds, hard_deadline),
                "lease_epoch": 1, "operation_phase": "external_operation_reserved", "operation_status": "reserved",
                "phase_revision": 1,
            }
            stub["prestart"] = {"active_time": {"published": False, "setup_record": setup_record,
                "setup_record_digest": digest(setup_record), "previous_ledger": previous_ledger.decode(),
                "setup_content": setup_content.decode(), "source_control": loads(control_row[0]),
                "source_index": index, "setup_index": {**index, "execution_head": digest(setup_record)},
                "backend_maximum_seconds": backend_maximum, "attempt_maximum_seconds": attempt_maximum,
                "attempt_interval_id": producer + ":attempt_active"}}
            stub.update({key: None for key in (
                "task_digest", "workspace_manifest_digest", "reservation_id", "reservation_digest",
                "operation_contract_digest", "pause_id", "pause_binding_digest", "resolution_owner",
                "cancel_intent", "cancel_reason", "dispatch_receipt_reference", "dispatch_receipt_digest",
                "provider_operation_reference", "result_reference", "result_digest", "workspace_seal_digest",
                "last_observed_status", "last_observed_at", "terminal_evidence_reference", "terminal_evidence_digest",
                "proof_kind", "quarantine_reference", "missing_proof_dimensions")})
            boundary(coordinator.observer, "external.stub", "before", value=stub)
            db.execute("INSERT INTO external_operations VALUES (?,?,?)", (producer, 1, canonical_bytes(stub)))
            boundary(coordinator.observer, "external.stub", "after", value=stub)
        return stub
