"""Initial producer authority in the existing project coordinator."""
from hashlib import sha256
import uuid

from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.coordinator import boundary, read_regular
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import canonical_bytes, digest, number, require, text


class ExternalProducer:
    """A trusted Host entry point; callers cannot supply a producer identity."""

    def __init__(self, coordinator):
        self.coordinator = coordinator

    def lookup(self, producer_operation_id):
        """Read the original producer without renewing leases or creating work."""
        return ExternalControl(self.coordinator).read(self.coordinator.connection, producer_operation_id)

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
            now = coordinator._time().monotonic_seconds
            require(hard_deadline > now, "Producer deadline already expired")
            producer = "external_" + uuid.uuid4().hex
            workspace = "workspace_" + producer
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
