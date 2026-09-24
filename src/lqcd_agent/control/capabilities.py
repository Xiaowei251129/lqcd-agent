"""Immutable bootstrap authorization and independently fenced invocation starts.

This implements the start boundary, not product node completion or resource
admission. A started intent can never be taken over to reexecute a consumer.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256

from .checkpoints import verify_checkpoint
from .coordinator import boundary, publish_exact, read_regular, replace_projection
from .execution import append_record_bytes, parse_ledger
from .integrity import validate_advanced_run_root, validate_run_root
from .protocol import PROTOCOL, operation_variant
from .records import FIELDS, build_record
from .strict_json import canonical_bytes, digest, loads, number, require, text


CONTRACT = PROTOCOL["state_machines"]["control_operation"]["invocation_capability_contract"]


@dataclass(frozen=True)
class TargetOutcome:
    """A trusted target port's domain outcome, never a control or route decision."""

    status: str
    output_references: dict
    error: dict | None = None
    artifact: "ArtifactOutput | None" = None
    human_request_packet: str | None = None
    human_response_verdict: "HumanResponseVerdict | None" = None


@dataclass(frozen=True)
class HumanResponseVerdict:
    """Domain validation result; exact authorization is derived from frozen scope."""

    valid: bool
    error: str | None = None


@dataclass(frozen=True)
class ArtifactOutput:
    """Domain output proposal; membership and dependencies remain registry-verified."""

    slot: str
    member_paths: tuple
    state_paths: dict
    status: str


@dataclass(frozen=True)
class CodeConsumptionProof:
    """Trusted domain verification receipt; B02 checks binding, never Code semantics."""

    producer_operation_id: str
    external_final_digest: str
    target_attempt_id: str
    artifact_members_digest: str
    domain_status: str


class ArtifactEffectPort:
    """Live invocation-scoped canonical-file writer, not a reusable permission."""

    def __init__(self, leases, db, capability_id, worker, epoch):
        self.leases, self.db = leases, db
        self.capability_id, self.worker, self.epoch = capability_id, worker, epoch

    def write_member(self, relative, content):
        from pathlib import Path
        from .coordinator import exclusive_directory
        if self.db is None:
            with self.leases.coordinator.transaction() as db:
                return ArtifactEffectPort(self.leases, db, self.capability_id, self.worker, self.epoch).write_member(relative, content)
        require(type(content) is bytes, "Artifact output must be bytes")
        path = Path(relative)
        require(not path.is_absolute() and path.parts and all(item not in (".", "..") for item in path.parts), "Invalid artifact member path")
        self.leases._effect_authority(self.db, self.capability_id, self.worker, self.epoch)
        _, value, root, _ = self.leases._fence(self.db, self.capability_id, self.worker, self.epoch)
        attempt = root / "attempts" / value["authorization"]["identity"]["attempt_id"]
        destination = attempt / path
        require(destination == destination.resolve() and destination.is_relative_to(attempt), "Artifact member escaped Attempt")
        parent = root
        for part in destination.parent.relative_to(root).parts:
            parent = parent / part
            self.leases._fence(self.db, self.capability_id, self.worker, self.epoch)
            exclusive_directory(parent)
        self.leases._fence(self.db, self.capability_id, self.worker, self.epoch)
        publish_exact(destination, content, observer=self.leases.coordinator.observer, name="invocation.artifact_member")
        self.leases._fence(self.db, self.capability_id, self.worker, self.epoch)
        return destination

    def run_verification(self, *, spec_id, input_digest, config_digest, timeout_seconds, effect):
        from lqcd_agent.code_agent.verification_resources import run_verification
        return run_verification(self, spec_id=spec_id, input_digest=input_digest, config_digest=config_digest,
                                timeout_seconds=timeout_seconds, effect=effect)


def prepare_capability(coordinator, db, operation, run_root, manifest, projection, *, advanced=False):
    require(db is coordinator.connection and db.in_transaction, "Capability requires coordinator authority")
    coordinator.fence(db, operation["operation_id"], operation["worker_owner_id"],
                      operation["lease_epoch"], operation["phase_revision"])
    producer = operation["operation_type"] + "/" + operation["operation_variant"]
    allowed = {row["operation_variant"] for row in CONTRACT["prepared_then_activated"]["producer_cases"]}
    require(producer in allowed, "Unknown prepared capability producer")
    declaration = operation_variant(operation["operation_type"], operation["operation_variant"])
    require((operation["phase"], CONTRACT["prepared_then_activated"]["preparation_phase"]) in declaration["success_edges"],
            "Capability preparation precedes its generated boundary")
    if operation["operation_type"] == "advance_run":
        require(operation["reservation"]["transition_target_kind"] == "attempt", "END has no capability")
    verify_checkpoint(run_root, manifest)
    validator = validate_advanced_run_root if advanced else validate_run_root
    state = validator(run_root, manifest=manifest, projection=projection).value
    require(state["run_status"] == "running" and state["attempt_status"] == "scheduled", "Target is not scheduled")
    locator = {key: state[key] for key in ("case_id", "run_id")}
    run_key = digest(locator)
    require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (run_key,)).fetchone() is None,
            "Run already has terminal ownership")
    identity = {key: state[key] for key in ("case_id", "run_id", "attempt_id", "attempt_kind")}
    heads = {key: state[key] for key in ("execution_head", "artifact_head", "checkpoint_head")}
    scope_key = "advance_target_code_agent" if operation["operation_type"] == "advance_run" and state["attempt_kind"] == "code_agent" else "start_replay_fork_and_other_advance_targets"
    authorization = {"producer_operation_id": operation["operation_id"], "activation_result_revision": operation["phase_revision"] + 2,
                     "identity": identity, "heads": heads, "manifest": manifest, "projection": state,
                     "artifact_history_digest": sha256(read_regular(run_root / "artifact_history.jsonl")).hexdigest(),
                     "producing_epoch": operation["lease_epoch"], "terminal_closure_revision": 0,
                     "checkpoint_anchor_kind": "owned_transition" if advanced else "same_head",
                     "scope": CONTRACT["authorization_scopes"][scope_key]}
    if operation["operation_type"] == "advance_run":
        preparation = operation["reservation"]["target_preparation_snapshot"]
        if preparation["preparation_kind"] == "analysis_fresh":
            phase = coordinator.history(operation["operation_id"])[-1]
            require(phase["phase"] == "target_preparation_committed" and phase["evidence"]["target_preparation_snapshot"] == preparation,
                    "Analysis lacks exact committed preparation")
            authorization["target_preparation"] = preparation
            authorization["preparation_receipt"] = phase["evidence"]["spec_manifest_bytes_and_effective_tree_verified_or_not_applicable"]
    value = {"authorization": authorization, "authorization_digest": digest(authorization), "state": "unclaimed",
             "worker_id": None, "invocation_epoch": 0, "expires_at": None, "deadline": None,
             "started_intent": None, "updated_at": asdict(coordinator._time())}
    capability_id = "capability_" + operation["operation_id"]
    db.execute("INSERT INTO invocation_capabilities VALUES (?,?,?)", (capability_id, 1, canonical_bytes(value)))
    return {"attempt_identity": identity, "exact_heads": heads, "lease_epoch": operation["lease_epoch"],
            "terminal_closure_revision": 0, "producer_operation_id": operation["operation_id"],
            "activation_result_revision": authorization["activation_result_revision"], "inactive_until_operation_committed": True}


def authorize_resume_capability(coordinator, db, operation, run_root, manifest, projection):
    """Activate only at the generated in-progress resume authorization boundary."""
    require(db is coordinator.connection and db.in_transaction, "Resume authorization requires coordinator authority")
    coordinator.fence(db, operation["operation_id"], operation["worker_owner_id"], operation["lease_epoch"], operation["phase_revision"])
    require(operation["operation_type"] + "/" + operation["operation_variant"] in CONTRACT["active_within_resume"]["operation_variants"] and
            operation["phase"] == "resume_checkpoint_committed", "Resume authorization precedes its generated boundary")
    verify_checkpoint(run_root, manifest)
    state = validate_run_root(run_root, manifest=manifest, projection=projection).value
    require(state["run_status"] == "running" and state["attempt_status"] == "scheduled" and state.get("active_pause") is None,
            "Resume target is not consumed, running and scheduled")
    locator = {key: state[key] for key in ("case_id", "run_id")}
    require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (digest(locator),)).fetchone() is None, "Run has terminal owner")
    pause = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?",
                       (digest(locator), operation["request"]["pause_id"])).fetchone()
    require(pause is not None and loads(pause[0])["owner"] == operation["operation_id"] and loads(pause[0])["status"] == "consumed",
            "Resume has no consumed Pause ownership")
    identity = {key: state[key] for key in ("case_id", "run_id", "attempt_id", "attempt_kind")}
    heads = {key: state[key] for key in ("execution_head", "artifact_head", "checkpoint_head")}
    authorization = {"producer_operation_id": operation["operation_id"], "activation_result_revision": operation["phase_revision"] + 1,
                     "activation_kind": "active_within_resume", "identity": identity, "heads": heads, "manifest": manifest, "projection": state,
                     "artifact_history_digest": sha256(read_regular(run_root / "artifact_history.jsonl")).hexdigest(),
                     "producing_epoch": operation["lease_epoch"], "terminal_closure_revision": 0, "checkpoint_anchor_kind": "same_head",
                     "scope": CONTRACT["authorization_scopes"]["resume_continue"]}
    if operation["request"]["input_kind"] == "external_result":
        authorization["external_consumption"] = operation["reservation"]["target_prestart_closure"]["external"]
    preparation = operation["reservation"]["target_prestart_closure"].get("preparation")
    if preparation is not None:
        authorization.update(preparation)
    value = {"authorization": authorization, "authorization_digest": digest(authorization), "state": "unclaimed", "worker_id": None,
             "invocation_epoch": 0, "expires_at": None, "deadline": None, "started_intent": None, "updated_at": asdict(coordinator._time())}
    db.execute("INSERT INTO invocation_capabilities VALUES (?,?,?)", ("capability_" + operation["operation_id"], 1, canonical_bytes(value)))
    return {"attempt_identity": identity, "exact_heads": heads, "lease_epoch": operation["lease_epoch"], "terminal_closure_revision": 0}


def authorize_interrupt_capability(coordinator, db, operation, root, checkpoint, delivery_digest):
    """Authorize only materialization of the same winner's frozen timeout result."""
    coordinator.fence(db, operation["operation_id"], operation["worker_owner_id"], operation["lease_epoch"], operation["phase_revision"])
    require(operation["operation_type"] == "resolve_external_interrupt" and operation["operation_variant"] == "recoverable_timeout" and
            operation["phase"] == "resume_checkpoint_committed", "Invalid interrupt activation source")
    verify_checkpoint(root, checkpoint["manifest"])
    state = validate_run_root(root, manifest=checkpoint["manifest"], projection=checkpoint["projection"]).value
    require(state["run_status"] == "running" and state["attempt_kind"] == "code_agent" and state["attempt_status"] == "scheduled" and
            state.get("active_pause") is None, "Interrupt target is not consumed and scheduled")
    identity = {k: state[k] for k in ("case_id", "run_id", "attempt_id", "attempt_kind")}
    locator = {k: state[k] for k in ("case_id", "run_id")}
    pause_id = operation["reservation"]["pause_snapshot"]["pause_id"]
    pause = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (digest(locator), pause_id)).fetchone()
    require(pause is not None and loads(pause[0])["owner"] == operation["operation_id"] and loads(pause[0])["status"] == "consumed" and
            db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (digest(locator),)).fetchone() is None, "Interrupt lost consumption ownership")
    authorization = {"producer_operation_id": operation["operation_id"], "activation_result_revision": operation["phase_revision"] + 1,
        "activation_kind": "active_interrupt_result_consumption", "canonical_failed_delivery_digest": delivery_digest,
        "identity": identity, "heads": {k: state[k] for k in ("execution_head", "artifact_head", "checkpoint_head")},
        "manifest": checkpoint["manifest"], "projection": state,
        "artifact_history_digest": sha256(read_regular(root / "artifact_history.jsonl")).hexdigest(),
        "producing_epoch": operation["lease_epoch"], "terminal_closure_revision": 0, "checkpoint_anchor_kind": "same_head",
        "scope": CONTRACT["authorization_scopes"]["recoverable_interrupt"]}
    value = {"authorization": authorization, "authorization_digest": digest(authorization), "state": "unclaimed", "worker_id": None,
        "invocation_epoch": 0, "expires_at": None, "deadline": None, "started_intent": None, "updated_at": asdict(coordinator._time())}
    capability_id = "capability_" + operation["operation_id"]
    db.execute("INSERT INTO invocation_capabilities VALUES (?,?,?)", (capability_id, 1, canonical_bytes(value)))
    return {"capability_id": capability_id, "authorization_digest": digest(authorization), "lease_state": "unclaimed"}


class InvocationLeases:
    def __init__(self, coordinator, *, decision_adapter=None, external_adapter=None, preparation_adapter=None):
        self.coordinator = coordinator
        self.decision_adapter = decision_adapter
        self.external_adapter = external_adapter
        self.preparation_adapter = preparation_adapter

    def get(self, capability_id, *, db=None):
        text(capability_id)
        row = (db or self.coordinator.connection).execute("SELECT revision,value FROM invocation_capabilities WHERE capability_id=?",
                                                         (capability_id,)).fetchone()
        require(row is not None, "Unknown invocation capability")
        value = loads(row["value"])
        require(digest(value["authorization"]) == value["authorization_digest"], "Invocation authorization changed")
        require(value["state"] in CONTRACT["execution_lease"]["states"], "Unknown invocation state")
        return row["revision"], value

    def _save(self, db, capability_id, revision, value):
        changed = db.execute("UPDATE invocation_capabilities SET revision=?,value=? WHERE capability_id=? AND revision=?",
                             (revision + 1, canonical_bytes(value), capability_id, revision))
        require(changed.rowcount == 1, "Invocation revision conflict")

    @staticmethod
    def _validate_anchor(root, authorization):
        kind = authorization["checkpoint_anchor_kind"]
        require(kind in ("same_head", "owned_transition"), "Unknown checkpoint authorization anchor")
        validator = validate_advanced_run_root if kind == "owned_transition" else validate_run_root
        return validator(root, manifest=authorization["manifest"], projection=authorization["projection"])

    def _activation(self, db, capability_id, value):
        authorization = value["authorization"]
        producer = self.coordinator.get(authorization["producer_operation_id"], db=db)
        interrupt = authorization.get("activation_kind") == "active_interrupt_result_consumption"
        if interrupt:
            contract = CONTRACT["active_interrupt_result_consumption"]
            require(producer["operation_type"] + "/" + producer["operation_variant"] == contract["operation_variant"] and
                    producer["status"] == "in_progress" and producer["phase"] == contract["activation_phase"] and
                    producer["phase_revision"] == authorization["activation_result_revision"], "Interrupt authorization is not active")
            self.coordinator.fence(db, producer["operation_id"], producer["worker_owner_id"], producer["lease_epoch"], producer["phase_revision"])
            phase = self.coordinator.history(producer["operation_id"])[-1]
            require(phase["evidence"]["canonical_failed_delivery_digest"] == authorization["canonical_failed_delivery_digest"] and
                    phase["evidence"]["same_interrupt_winner"] == producer["operation_id"], "Interrupt delivery authorization changed")
        elif authorization.get("activation_kind") == "active_within_resume":
            require(producer["operation_type"] + "/" + producer["operation_variant"] in CONTRACT["active_within_resume"]["operation_variants"] and
                    producer["status"] == "in_progress" and producer["phase"] == CONTRACT["active_within_resume"]["activation_phase"] and
                    producer["phase_revision"] == authorization["activation_result_revision"], "Resume authorization is not active")
            phase = self.coordinator.history(producer["operation_id"])[-1]
            require(phase["evidence"]["attempt_identity"] == authorization["identity"] and phase["evidence"]["exact_heads"] == authorization["heads"],
                    "Resume authorization differs from its committed phase")
        else:
            require(producer["status"] == "committed" and
                    producer["phase"] == CONTRACT["prepared_then_activated"]["activation_phase"] and
                    producer["phase_revision"] == authorization["activation_result_revision"] and
                    producer["result"]["capability_id"] == capability_id, "Capability has not been activated by its producer")
            require(all(producer["result"].get(key) == value for key, value in authorization["heads"].items()),
                    "Producer result differs from authorization heads")
        require(authorization["scope"] == (CONTRACT["authorization_scopes"]["recoverable_interrupt"] if interrupt else "attempt_execution"),
                "Capability scope cannot claim an Attempt lease")
        locator = {key: authorization["identity"][key] for key in ("case_id", "run_id")}
        require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (digest(locator),)).fetchone() is None and
                authorization["terminal_closure_revision"] == 0, "Terminal ownership revoked invocation authorization")
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        require(root == root.resolve(), "Invocation Run path changed")
        records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
        for name in ("root_goal_reference", "input_snapshot_reference"):
            reference = records[0][name]
            path = root / reference["reference"]
            require(path == path.resolve() and path.is_relative_to(root), "Invocation input reference escaped Run")
            require(sha256(read_regular(path)).hexdigest() == reference["sha256"], "Invocation root input digest mismatch")
        preparation = authorization.get("target_preparation")
        if preparation is not None:
            from .operations import verify_preparation_receipt
            require(self.preparation_adapter is not None and hasattr(self.preparation_adapter, "verify_preparation"),
                    "Analysis invocation lacks its original workspace verification port")
            namespace = root / "attempts" / authorization["identity"]["attempt_id"] / "control"
            for name, field in (("analysis_execution_spec.json", "canonical_spec_bytes"), ("analysis_workspace_manifest.json", "canonical_workspace_manifest_bytes")):
                require(read_regular(namespace / name) == preparation[field].encode(), "Analysis preparation bytes changed")
            receipt = self.preparation_adapter.verify_preparation(loads(canonical_bytes(preparation)))
            require(verify_preparation_receipt(preparation, receipt) == authorization["preparation_receipt"], "Analysis workspace receipt changed")
        return root

    def _now(self, value):
        now = self.coordinator._time()
        old = value["updated_at"]
        require(now.source == old["source"] and now.wall_seconds >= old["wall_seconds"] and
                now.monotonic_seconds >= old["monotonic_seconds"], "Invocation clock regression")
        return now

    def acquire(self, capability_id, worker_id, *, expected_epoch, lease_seconds):
        text(worker_id)
        number(expected_epoch, integer=True)
        number(lease_seconds, minimum=1)
        with self.coordinator.transaction() as db:
            revision, value = self.get(capability_id, db=db)
            from .coordinator import boundary
            boundary(self.coordinator.observer, "invocation.activation_check", "before")
            try:
                root = self._activation(db, capability_id, value)
            finally:
                boundary(self.coordinator.observer, "invocation.activation_check", "after")
            now = self._now(value)
            require(value["invocation_epoch"] == expected_epoch, "Stale invocation epoch")
            require(value["state"] in ("unclaimed", "leased_not_started") and value["started_intent"] is None,
                    "Started or uncertain invocation cannot be acquired again")
            require(value["expires_at"] is None or now.monotonic_seconds >= value["expires_at"], "Invocation is already leased")
            authorization = value["authorization"]
            if authorization.get("activation_kind") == "active_interrupt_result_consumption":
                require(self.coordinator.get(authorization["producer_operation_id"], db=db)["worker_owner_id"] == worker_id,
                        "Timeout lease requires the current interrupt worker")
            verify_checkpoint(root, authorization["manifest"])
            state = self._validate_anchor(root, authorization).value
            require(state["attempt_id"] == authorization["identity"]["attempt_id"] and state["attempt_status"] == "scheduled",
                    "Invocation target is no longer scheduled")
            remaining = state["budget"]["dimensions"]
            duration = min(remaining["active_seconds_per_attempt"]["remaining"], remaining["active_seconds_per_run"]["remaining"])
            deadline = value["deadline"] if value["deadline"] is not None else now.monotonic_seconds + duration
            now = self._now(value)
            require(now.monotonic_seconds < deadline, "Invocation budget deadline elapsed")
            value.update(state="leased_not_started", worker_id=worker_id, invocation_epoch=expected_epoch + 1,
                         expires_at=min(now.monotonic_seconds + lease_seconds, deadline), deadline=deadline,
                         updated_at=asdict(now))
            if "external_consumption" in authorization:
                producer = self.coordinator.get(authorization["producer_operation_id"], db=db)
                self.coordinator.fence(db, producer["operation_id"], producer["worker_owner_id"],
                                       producer["lease_epoch"], authorization["activation_result_revision"])
                value["consumer_resume_epoch"] = producer["lease_epoch"]
            self._save(db, capability_id, revision, value)
            return value

    def _fence(self, db, capability_id, worker_id, epoch):
        revision, value = self.get(capability_id, db=db)
        root = self._activation(db, capability_id, value)
        now = self._now(value)
        if value["authorization"].get("activation_kind") == "active_interrupt_result_consumption":
            require(self.coordinator.get(value["authorization"]["producer_operation_id"], db=db)["worker_owner_id"] == worker_id,
                    "Old interrupt worker cannot start the timeout target")
        require(value["worker_id"] == worker_id and value["invocation_epoch"] == epoch and
                value["expires_at"] is not None and now.monotonic_seconds < value["expires_at"] and
                value["deadline"] is not None and now.monotonic_seconds < value["deadline"],
                "Stale or expired invocation lease")
        require(value["state"] in ("leased_not_started", "started"), "Invocation cannot execute")
        if "external_consumption" in value["authorization"]:
            producer = self.coordinator.get(value["authorization"]["producer_operation_id"], db=db)
            self.coordinator.fence(db, producer["operation_id"], producer["worker_owner_id"],
                                   value["consumer_resume_epoch"], value["authorization"]["activation_result_revision"])
        return revision, value, root, now

    def start_intent(self, capability_id, worker_id, epoch):
        """Persist the irreversible start CAS before writing the A02 started record."""
        with self.coordinator.transaction() as db:
            revision, value, root, now = self._fence(db, capability_id, worker_id, epoch)
            require(value["state"] == "leased_not_started" and value["started_intent"] is None, "Start intent already exists")
            authorization = value["authorization"]
            verify_checkpoint(root, authorization["manifest"])
            self._validate_anchor(root, authorization)
            old_bytes = read_regular(root / "execution_history.jsonl")
            execution = parse_ledger(old_bytes)
            old_index = read_regular(root / "artifact_index.json")
            revision, value, _, now = self._fence(db, capability_id, worker_id, epoch)
            require(value["state"] == "leased_not_started" and value["started_intent"] is None, "Start intent already exists")
            scheduled = next(row for row in execution.values if row["record_type"] == "attempt" and
                             row["attempt_id"] == authorization["identity"]["attempt_id"])
            fields = {key: scheduled[key] for key in FIELDS["attempt"]}
            fields["status"] = "running"
            state = execution.projection.value
            started = build_record("attempt", "started", run_id=state["run_id"], case_id=state["case_id"],
                                   event_index=len(execution.records) + 1, previous_execution_head=state["execution_head"],
                                   artifact_head=authorization["heads"]["artifact_head"],
                                   artifact_event_index=authorization["projection"]["artifact_event_index"],
                                   timestamp=now, **fields)
            new_bytes = append_record_bytes(old_bytes, started.value)
            new_index = canonical_bytes({**loads(old_index), "execution_head": started.digest})
            revision, value, _, now = self._fence(db, capability_id, worker_id, epoch)
            require(value["state"] == "leased_not_started" and value["started_intent"] is None, "Start intent already exists")
            value.update(state="started", started_intent={"record": started.value, "previous": old_bytes.decode(),
                                                          "content": new_bytes.decode(), "published": False,
                                                          "previous_index": old_index.decode(), "index": new_index.decode()},
                         updated_at=asdict(now))
            self._save(db, capability_id, revision, value)
            boundary(self.coordinator.observer, "invocation.started_intent", "before", value)
        boundary(self.coordinator.observer, "invocation.started_intent", "after", value)
        return value

    def publish_started(self, capability_id, worker_id, epoch):
        """Materialize the frozen started record; this never executes a target."""
        with self.coordinator.transaction() as db:
            revision, value, root, now = self._fence(db, capability_id, worker_id, epoch)
            intent = value["started_intent"]
            require(value["state"] == "started" and intent is not None, "Missing durable started intent")
            publish_exact(root / "execution_history.jsonl", intent["content"].encode(), previous=intent["previous"].encode(),
                          observer=self.coordinator.observer, name="invocation.attempt_started")
            replace_projection(root / "artifact_index.json", intent["previous_index"].encode(), intent["index"].encode(),
                               observer=self.coordinator.observer)
            self._fence(db, capability_id, worker_id, epoch)
            intent["published"] = True
            value["updated_at"] = asdict(now)
            self._save(db, capability_id, revision, value)
            return value

    def require_effect_authority(self, capability_id, worker_id, epoch):
        """Check the live owned started prefix, without renewing or invoking it.

        Product wrappers must use a fenced effect port when they are connected;
        this read-only check alone is not a dispatch API or a reusable permit.
        """
        with self.coordinator.transaction() as db:
            return self._effect_authority(db, capability_id, worker_id, epoch)

    def _effect_authority(self, db, capability_id, worker_id, epoch):
        """Check the owned prefix at the immediate trusted effect boundary."""
        require(self.get(capability_id, db=db)[1]["authorization"]["scope"] == "attempt_execution",
                "Deterministic timeout capability cannot invoke a consumer")
        require(db is self.coordinator.connection and db.in_transaction, "Effect requires coordinator authority")
        _, value, root, _ = self._fence(db, capability_id, worker_id, epoch)
        require(value.get("completion_intent") is None, "Target already completed or awaiting completion publication")
        intent = value["started_intent"]
        require(value["state"] == "started" and intent is not None and intent["published"],
                "Effect precedes durable Attempt started")
        from lqcd_agent.code_agent.verification_resources import owned_prefix
        intent = owned_prefix(value)
        require(read_regular(root / "execution_history.jsonl") == intent["content"].encode(), "Foreign invocation head progression")
        require(read_regular(root / "artifact_index.json") == intent["index"].encode(), "Foreign artifact projection")
        authorization = value["authorization"]
        require(sha256(read_regular(root / "artifact_history.jsonl")).hexdigest() == authorization["artifact_history_digest"],
                "Foreign artifact head progression")
        if "external_consumption" in authorization:
            from .operations import ExternalControl
            frozen = authorization["external_consumption"]["value"]
            external, _ = ExternalControl(self.coordinator).final_evidence(db, frozen["producer_operation_id"])
            require(external["terminal_evidence_digest"] == frozen["terminal_evidence_digest"] and external["resolution_owner"] == "normal" and
                    external["active_binding_status"] == "active" and external["active_binding_generation"] == frozen["active_binding_generation"] and
                    external["consumption_release"] is None, "External consumer lost its immutable normal final")
        from .budget import validate_policy
        selected = validate_policy(loads(read_regular(root / "budget_policy.json"))).value
        require(selected["policy_digest"] == authorization["projection"]["budget"]["policy_digest"], "Invocation policy changed")
        verify_checkpoint(root, authorization["manifest"])
        self._fence(db, capability_id, worker_id, epoch)
        return value["authorization_digest"]

    def invoke(self, capability_id, worker_id, epoch, target_port):
        """Invoke one Host-owned target port; restart never redispatches a started intent."""
        from .checkpoints import checkpoint_payload
        from .execution import replay
        from .projections import attach_checkpoint, bounded_projection, checkpoint_manifest

        self.start_intent(capability_id, worker_id, epoch)
        self.publish_started(capability_id, worker_id, epoch)
        target_error = None
        with self.coordinator.transaction() as db:
            self._effect_authority(db, capability_id, worker_id, epoch)
            _, current, _, _ = self._fence(db, capability_id, worker_id, epoch)
            external = current["authorization"].get("external_consumption")
        if external is not None:
            require(hasattr(target_port, "consume_external"), "Code consumer requires a trusted materialization-only port")
            outcome = target_port.consume_external(dict(current["authorization"]["identity"]),
                loads(canonical_bytes(external)), ArtifactEffectPort(self, None, capability_id, worker_id, epoch))
        with self.coordinator.transaction() as db:
            self._effect_authority(db, capability_id, worker_id, epoch)
            revision, value, root, _ = self._fence(db, capability_id, worker_id, epoch)
            authorization = value["authorization"]
            try:
                if external is None:
                    if hasattr(target_port, "invoke_with_artifacts"):
                        outcome = target_port.invoke_with_artifacts(dict(authorization["identity"]),
                            ArtifactEffectPort(self, db, capability_id, worker_id, epoch))
                    else:
                        outcome = target_port.invoke(dict(authorization["identity"]))
            except Exception as error:
                target_error = error
                outcome = TargetOutcome("failed", {"current_artifact_ids": {}},
                                        {"type": type(error).__name__, "message": str(error) or type(error).__name__})
            require(type(outcome) is TargetOutcome, "Target port returned an untyped outcome")
            require(outcome.status in ("succeeded", "failed", "pending"), "Invalid target disposition")
            self._effect_authority(db, capability_id, worker_id, epoch)
            _, _, _, now = self._fence(db, capability_id, worker_id, epoch)
            from lqcd_agent.code_agent.verification_resources import owned_prefix
            prefix = owned_prefix(value)
            previous = prefix["content"].encode()
            execution = parse_ledger(previous)
            started = value["started_intent"]["record"]
            index = loads(prefix["index"])
            resources = {r["payload"]["resource_operation_id"] for r in execution.values
                         if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                         r["payload"]["attempt_id"] == started["attempt_id"]}
            settled = {r["payload"]["resource_operation_id"] for r in execution.values
                       if r["record_type"] == "budget" and r["event"] == "resource_settled"}
            require(resources <= settled, "Invocation cannot finish with unsettled resources")
            artifact_publication = None
            if outcome.artifact is not None:
                code_proof = None
                if authorization["identity"]["attempt_kind"] == "code_agent":
                    require("external_consumption" in authorization and self.external_adapter is not None and
                            hasattr(self.external_adapter, "verify_consumption"), "Missing trusted Code verification port")
                    code_proof = self.external_adapter.verify_consumption(dict(authorization["identity"]),
                        loads(canonical_bytes(authorization["external_consumption"])), outcome)
                    require(type(code_proof) is CodeConsumptionProof and outcome.artifact.slot == "code", "Untyped Code verification receipt")
                    members = [{"path": str(path.relative_to(root)), "sha256": sha256(read_regular(path)).hexdigest()}
                               for path in outcome.artifact.member_paths]
                    frozen = authorization["external_consumption"]["value"]
                    require(code_proof == CodeConsumptionProof(frozen["producer_operation_id"], frozen["terminal_evidence_digest"],
                            authorization["identity"]["attempt_id"], digest(members), outcome.status), "Code verification receipt binding mismatch")
                    self._effect_authority(db, capability_id, worker_id, epoch)
                index, artifact_publication = self._artifact_plan(root, execution, index, outcome.artifact, now, code_proof=code_proof)
            require("external_consumption" not in authorization or outcome.artifact is not None, "External consumption returned no registered result")
            execution = self._human_completion(root, execution, index, outcome, now)
            fields = {key: started[key] for key in FIELDS["attempt"]}
            fields.update(status=outcome.status, output_references=outcome.output_references, error=outcome.error)
            if outcome.artifact is not None:
                expected = {slot: pointer["artifact_id"] for slot, pointer in index["current"].items() if pointer is not None}
                require(outcome.output_references == {"current_artifact_ids": expected}, "Target output references disagree with verified registry")
            finished = build_record("attempt", "finished", **{key: started[key] for key in ("case_id", "run_id")},
                                    event_index=len(execution.records) + 1, previous_execution_head=execution.projection.value["execution_head"],
                                    artifact_head=index["artifact_head"], artifact_event_index=index["revision"],
                                    timestamp=now, **fields).value
            execution = replay([*execution.values, finished])
            invalid_decision = None
            if outcome.human_response_verdict is not None and execution.projection.value["human_response_status"] == "invalid":
                from .operations import invalid_response_admission
                payload, binding = invalid_response_admission(execution, self.decision_adapter)
                budget = execution.projection.value["budget"]
                position = budget["budget_event_index"] + 1
                decision = build_record("budget", "decision_recorded", **{key: started[key] for key in ("case_id", "run_id")},
                    event_index=len(execution.records) + 1, previous_execution_head=digest(finished), artifact_head=index["artifact_head"],
                    artifact_event_index=index["revision"], timestamp=now, budget_event_id=f"budget_event_{position:06d}",
                    budget_event_index=position, policy_version="0.1", policy_digest=budget["policy_digest"], payload=payload).value
                execution = replay([*execution.values, decision])
                invalid_decision = {"record": decision, "binding": {**binding, "decision_resulting_execution_head": digest(decision)}}
            index = {**index, "execution_head": execution.projection.value["execution_head"]}
            core = bounded_projection(execution, artifact_index=index, artifact_head=finished["artifact_head"],
                                      artifact_event_index=finished["artifact_event_index"])
            checkpoint_id = capability_id + "_finished"
            payload = checkpoint_payload(checkpoint_id, core, now, operation_id=authorization["producer_operation_id"])
            manifest = checkpoint_manifest(execution, artifact_head=finished["artifact_head"],
                                           artifact_event_index=finished["artifact_event_index"], checkpoint_id=checkpoint_id,
                                           checkpoint_digest=digest(payload), state_digest=core.digest).value
            value["completion_intent"] = {"content": (b"\n".join(execution.records) + b"\n").decode(),
                                          "index": canonical_bytes(index).decode(), "checkpoint": payload,
                                          "manifest": manifest, "projection": attach_checkpoint(core, execution, manifest).value,
                                          "artifact_publication": artifact_publication, "invalid_response_decision": invalid_decision, "published": False}
            value["completion_intent"]["checkpoint_deferred_until_release"] = "external_consumption" in authorization
            revision, _, _, now = self._fence(db, capability_id, worker_id, epoch)
            value["updated_at"] = asdict(now)
            self._save(db, capability_id, revision, value)
            boundary(self.coordinator.observer, "invocation.completion_intent", "before", value)
        boundary(self.coordinator.observer, "invocation.completion_intent", "after", value)
        result = self.publish_completion(capability_id, worker_id, epoch)
        if target_error is not None:
            raise target_error
        return result

    @staticmethod
    def _human_completion(root, execution, index, outcome, now):
        from .execution import replay
        rows = list(execution.values)
        state = execution.projection.value
        if outcome.human_request_packet is None and outcome.human_response_verdict is None:
            return execution
        require(state["attempt_kind"] == "human_gate", "Only Human Gate may publish Human control results")
        request = next((r for r in reversed(rows) if r["record_type"] == "human_request"), None)
        require(request is not None and request["status"] == "open", "No open Human Request")

        def append(kind, event, fields):
            rows.append(build_record(kind, event, case_id=state["case_id"], run_id=state["run_id"],
                event_index=len(rows) + 1, previous_execution_head=digest(rows[-1]),
                artifact_head=index["artifact_head"], artifact_event_index=index["revision"], timestamp=now, **fields).value)

        if outcome.human_request_packet is not None:
            from pathlib import Path
            path = Path(outcome.human_request_packet)
            attempt_root = root / "attempts" / state["attempt_id"]
            require(path == path.resolve() and path.is_relative_to(attempt_root), "Human packet escaped producing Attempt")
            read_regular(path)
            require(request["event"] == "created", "Human Request packet already published")
            append("human_request", "packet_written", {**{key: request[key] for key in FIELDS["human_request"]}, "packet_reference": str(path)})
        if outcome.human_response_verdict is not None:
            verdict = outcome.human_response_verdict
            require(type(verdict) is HumanResponseVerdict and type(verdict.valid) is bool, "Untyped Human validation verdict")
            submitted = next((r for r in reversed(rows) if r["record_type"] == "human_response"), None)
            require(submitted is not None and submitted["status"] == "submitted" and
                    submitted["human_request_id"] == request["human_request_id"], "No current submitted response")
            scope = request["authorization_scope"]
            choice = submitted["payload_snapshot"].get("decision")
            target = scope.get("decision_transition_targets", {}).get(choice)
            route = scope.get("decision_transition_routes", {}).get(choice)
            valid = verdict.valid and choice in scope.get("allowed_decisions", []) and target in scope.get("allowed_target_nodes", []) and isinstance(route, str)
            error = None if valid else verdict.error or "Response exceeds the exact frozen authorization scope"
            fields = {key: submitted[key] for key in FIELDS["human_response"]}
            fields.update(status="validated" if valid else "invalid", validator_attempt_id=state["attempt_id"], error=error,
                          decision=choice if valid else None, authorized_route=target if valid else None,
                          authorized_transition_route=route if valid else None, authorized_transition_target=target if valid else None)
            append("human_response", fields["status"], fields)
        return replay(rows)

    @staticmethod
    def _artifact_plan(root, execution, index, output, now, *, code_proof=None):
        from base64 import b64encode
        from datetime import datetime, timezone
        from lqcd_agent.artifacts import registry
        from .integrity import artifact_binding
        from .projections import bounded_projection

        require(type(output) is ArtifactOutput, "Untyped artifact output")
        require(execution.projection.value["attempt_kind"] != "code_agent" or type(code_proof) is CodeConsumptionProof,
                "Code Agent requires its verified B03 bundle adapter")
        state = bounded_projection(execution, artifact_index=index, artifact_head=index["artifact_head"], artifact_event_index=index["revision"]).value
        state.update(output_dir=str(root), execution_history_path=str(root / "execution_history.jsonl"),
                     artifact_history_path=str(root / "artifact_history.jsonl"), artifact_index_path=str(root / "artifact_index.json"))
        created_at = datetime.fromtimestamp(now.wall_seconds, timezone.utc).isoformat()
        updated, events = registry.preflight_control_registration(state, slot=output.slot, member_paths=output.member_paths,
            state_paths=output.state_paths, status=output.status, created_at=created_at)
        previous = read_regular(root / "artifact_history.jsonl")
        content = previous
        head = index["artifact_head"]
        for event in events:
            bound = artifact_binding(event, previous_artifact_head=head, execution_head=state["execution_head"])
            content += bound.canonical + b"\n"
            head = bound.digest
        updated["artifact_head"] = head
        projections = []
        for member in updated["current"][output.slot]["members"]:
            raw = read_regular(root / member["canonical_path"])
            require(sha256(raw).hexdigest() == member["sha256"], "Artifact member changed during preflight")
            projections.append({"canonical_path": member["canonical_path"], "projection_path": member["projection_path"],
                                "sha256": member["sha256"], "content_base64": b64encode(raw).decode()})
        return updated, {"previous": previous.decode(), "content": content.decode(), "projections": projections}

    def _publish_artifact_plan(self, root, intent, fence):
        from base64 import b64decode
        from .coordinator import exclusive_directory

        plan = intent.get("artifact_publication")
        if plan is None:
            return
        for member in plan["projections"]:
            raw = read_regular(root / member["canonical_path"])
            require(sha256(raw).hexdigest() == member["sha256"], "Frozen artifact member changed")
            destination = root / member["projection_path"]
            require(destination == destination.resolve() and destination.is_relative_to(root), "Artifact projection escaped Run")
            parent = root
            for part in destination.parent.relative_to(root).parts:
                parent = parent / part
                fence()
                exclusive_directory(parent)
            fence()
            publish_exact(destination, b64decode(member["content_base64"], validate=True), observer=self.coordinator.observer,
                          name="invocation.artifact_projection")
        fence()
        publish_exact(root / "artifact_history.jsonl", plan["content"].encode(), previous=plan["previous"].encode(),
                      observer=self.coordinator.observer, name="invocation.artifact_registration")

    def publish_completion(self, capability_id, worker_id, epoch):
        """Publish the original live invocation's exact completion without invoking it."""
        from .checkpoints import persist_invocation_checkpoint

        with self.coordinator.transaction() as db:
            _, completed = self.get(capability_id, db=db)
            if completed["state"] == "finished":
                return completed["completion_intent"]["projection"]
            _, value, root, _ = self._fence(db, capability_id, worker_id, epoch)
            revision, value = self.get(capability_id, db=db)
            intent = value.get("completion_intent")
            require(intent is not None, "Missing frozen invocation completion")
            authorization = value["authorization"]
            self._publish_artifact_plan(root, intent, lambda: self._fence(db, capability_id, worker_id, epoch))
            from lqcd_agent.code_agent.verification_resources import owned_prefix
            prefix = owned_prefix(value)
            publish_exact(root / "execution_history.jsonl", intent["content"].encode(), previous=prefix["content"].encode(),
                          observer=self.coordinator.observer, name="invocation.attempt_finished")
            replace_projection(root / "artifact_index.json", prefix["index"].encode(), intent["index"].encode(),
                               observer=self.coordinator.observer)
            deferred = intent.get("checkpoint_deferred_until_release", False)
            if not deferred:
                persist_invocation_checkpoint(self.coordinator, db, capability_id, worker_id, epoch, root, intent["checkpoint"],
                                              {"source": "input", "step": 0, "parents": {}, "operation_id": authorization["producer_operation_id"]},
                                              preparation_adapter=self.preparation_adapter)
                publish_exact(root / "checkpoints" / (intent["manifest"]["checkpoint_id"] + ".json"), canonical_bytes(intent["manifest"]),
                              observer=self.coordinator.observer)
                verify_checkpoint(root, intent["manifest"])
            validate_run_root(root, manifest=intent["manifest"], projection=intent["projection"])
            _, _, _, now = self._fence(db, capability_id, worker_id, epoch)
            intent["published"] = True
            value["state"] = "finished"
            value["updated_at"] = asdict(now)
            self._save(db, capability_id, revision, value)
            locator = {key: authorization["identity"][key] for key in ("case_id", "run_id")}
            if not deferred:
                self.coordinator.connection.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?",
                                                (canonical_bytes({"locator": locator, "projection": intent["projection"],
                                                                  "manifest": intent["manifest"]}), digest(locator)))
            return intent["projection"]

    def renew(self, capability_id, worker_id, epoch, *, lease_seconds):
        """Only a live owner may extend its lease, never its original deadline."""
        number(lease_seconds, minimum=1)
        with self.coordinator.transaction() as db:
            revision, value, root, now = self._fence(db, capability_id, worker_id, epoch)
            intent = value["started_intent"]
            if intent is None:
                authorization = value["authorization"]
                verify_checkpoint(root, authorization["manifest"])
                self._validate_anchor(root, authorization)
            else:
                from lqcd_agent.code_agent.verification_resources import owned_prefix
                intent = owned_prefix(value)
                actual = read_regular(root / "execution_history.jsonl")
                require(actual in (intent["previous"].encode(), intent["content"].encode()), "Foreign owned head progression")
            revision, value, _, now = self._fence(db, capability_id, worker_id, epoch)
            value.update(expires_at=min(now.monotonic_seconds + lease_seconds, value["deadline"]), updated_at=asdict(now))
            self._save(db, capability_id, revision, value)
            return value

    def recover_completion(self, capability_id, operation_id, worker_id, epoch):
        """A current resume owner may finish exact bytes, never reclaim execution."""
        from .checkpoints import persist_checkpoint

        with self.coordinator.transaction() as db:
            operation = self.coordinator.get(operation_id, db=db)
            self.coordinator.fence(db, operation_id, worker_id, epoch, operation["phase_revision"])
            require(operation["operation_type"] == "resume_run" and operation["operation_variant"] == "continue_execution" and
                    operation["phase"] == "invocation_authorized", "Wrong completion materialization owner")
            revision, value = self.get(capability_id, db=db)
            require(value["authorization"]["producer_operation_id"] == operation_id, "Foreign invocation completion")
            root = self._activation(db, capability_id, value)
            intent = value.get("completion_intent")
            require(intent is not None and value["state"] in ("started", "finished"), "No exact completion to materialize")
            if value["state"] == "finished":
                return intent["projection"]
            self._publish_artifact_plan(root, intent, lambda: self.coordinator.fence(db, operation_id, worker_id, epoch, operation["phase_revision"]))
            from lqcd_agent.code_agent.verification_resources import owned_prefix
            prefix = owned_prefix(value)
            publish_exact(root / "execution_history.jsonl", intent["content"].encode(), previous=prefix["content"].encode(),
                          observer=self.coordinator.observer, name="invocation.attempt_finished")
            replace_projection(root / "artifact_index.json", prefix["index"].encode(), intent["index"].encode(), observer=self.coordinator.observer)
            deferred = intent.get("checkpoint_deferred_until_release", False)
            if not deferred:
                persist_checkpoint(self.coordinator, db, operation, root, intent["checkpoint"],
                                   {"source": "input", "step": 0, "parents": {}, "operation_id": operation_id})
                publish_exact(root / "checkpoints" / (intent["manifest"]["checkpoint_id"] + ".json"), canonical_bytes(intent["manifest"]),
                              observer=self.coordinator.observer)
                verify_checkpoint(root, intent["manifest"])
            validate_run_root(root, manifest=intent["manifest"], projection=intent["projection"])
            self.coordinator.fence(db, operation_id, worker_id, epoch, operation["phase_revision"])
            value.update(state="finished", updated_at=asdict(self.coordinator._time()))
            intent["published"] = True
            self._save(db, capability_id, revision, value)
            locator = {key: value["authorization"]["identity"][key] for key in ("case_id", "run_id")}
            if not deferred:
                db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (
                canonical_bytes({"locator": locator, "projection": intent["projection"], "manifest": intent["manifest"]}), digest(locator)))
            return intent["projection"]
