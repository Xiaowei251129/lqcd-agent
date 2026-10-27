"""Initial producer authority in the existing project coordinator."""
from hashlib import sha256
import uuid

from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.coordinator import boundary, publish_exact, read_regular
from lqcd_agent.control.execution import append_record_bytes, parse_ledger
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.records import build_record
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads, number, require, text

from .backend import validate_receipt, validate_result_reference, validate_status
from .ingress import preflight_result
from .schemas import validate_manifest, validate_task
from .workspace import WorkspaceProvider, immutable_git_tree, seal_workspace, validate_tool_audit


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


class ExternalDispatch:
    """Fence one original Backend dispatch after the public Pause checkpoint."""

    def __init__(self, coordinator, producer_operation_id, worker_id, epoch, backend, containment, receipt_loader,
                 result_loader):
        self.coordinator = coordinator
        self.producer = producer_operation_id
        self.worker_id = worker_id
        self.epoch = epoch
        self.backend = backend
        self.containment = containment
        self.receipt_loader = receipt_loader
        self.result_loader = result_loader

    def _source(self, db):
        boundary(self.coordinator.observer, "external.backend_authority_lookup", "before")
        value = ExternalControl(self.coordinator).read(db, self.producer)
        boundary(self.coordinator.observer, "external.backend_authority_lookup", "after", value=value)
        now = self.coordinator._time().monotonic_seconds
        require(value["worker_owner_id"] == self.worker_id and value["lease_epoch"] == self.epoch and
                now < value["worker_lease_expires_at"] and now < value["hard_deadline"] and
                value["resolution_owner"] is None, "Backend worker lost its original authority")
        locator = value["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        control = db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()
        require(control is not None, "Missing Backend Run control")
        source = loads(control[0])
        state = validate_run_root(root, manifest=source["manifest"], projection=source["projection"]).value
        records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
        opened = [record for record in records if record["record_type"] == "pause" and
                  record["event"] == "pause_opened" and record["pause_id"] == value["pause_id"]]
        require(state["run_status"] == "paused" and state["attempt_status"] == "scheduled" and
                state["attempt_id"] == value["attempt_id"] and len(opened) == 1 and
                records[-1] == opened[0], "Backend dispatch requires the public Pause head")
        directory = root / "code_agent_control" / value["attempt_id"]
        require(directory == directory.resolve() and directory.is_relative_to(root),
                "Backend control directory escaped its Run")
        task = validate_task(read_regular(directory / "code_agent_task.json")).value
        manifest = validate_manifest(read_regular(directory / "workspace_manifest.json"), task).value
        require(task["task_digest"] == value["task_digest"] and
                manifest["manifest_digest"] == value["workspace_manifest_digest"] and
                task["producer_operation_id"] == self.producer and
                task["coding_backend_kind"] == value["backend_kind"] and
                task["backend_version"] == value["backend_version"], "Backend source changed")
        return value, root, directory, task, manifest

    def authorize(self):
        with self.coordinator.transaction() as db:
            value, _, _, _, _ = self._source(db)
            if value["operation_phase"] in ("dispatch_authorized", "dispatch_receipt_committed",
                                             "result_reference_committed"):
                return False
            require(value["operation_phase"] == "pause_bound" and value["operation_status"] == "reserved",
                    "Backend dispatch cannot advance from this phase")
            boundary(self.coordinator.observer, "external.dispatch_authorization", "before", value=value)
            prior = value["phase_revision"]
            value.update(operation_phase="dispatch_authorized", operation_status="active", phase_revision=prior + 1,
                         dispatch_started_at=self.coordinator._time().monotonic_seconds)
            require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                               (prior + 1, canonical_bytes(value), self.producer, prior)).rowcount == 1,
                    "Backend dispatch authorization CAS lost")
            boundary(self.coordinator.observer, "external.dispatch_authorization", "after", value=value)
            boundary(self.coordinator.observer, "external.dispatch_authorized", "before", value=value)
        boundary(self.coordinator.observer, "external.dispatch_authorized", "after", value=value)
        return True

    def dispatch(self):
        first = self.authorize()
        if first:
            with self.coordinator.transaction() as db:
                value, _, _, task, manifest = self._source(db)
                require(value["operation_phase"] == "dispatch_authorized", "Backend dispatch intent changed")
                boundary(self.coordinator.observer, "external.workspace_lease", "before", value=value)
                self.containment.start(self.producer, manifest["workspace_id"])
                boundary(self.coordinator.observer, "external.workspace_lease", "after", value=value)
                boundary(self.coordinator.observer, "external.backend_dispatch", "before", value=value)
                self.backend.dispatch(task, manifest, self.producer)
                boundary(self.coordinator.observer, "external.backend_dispatch", "after", value=value)
        return self.publish_receipt()

    def publish_receipt(self):
        status = validate_status(self.backend.lookup(self.producer)).value
        require(status["status"] != "unknown" and status["receipt_reference"] is not None,
                "Original Backend operation has no recoverable receipt")
        receipt = self.receipt_loader(status["receipt_reference"])
        with self.coordinator.transaction() as db:
            value, root, directory, task, manifest = self._source(db)
            require(status["producer_operation_id"] == self.producer and
                    status["backend_kind"] == task["coding_backend_kind"] and
                    status["backend_version"] == task["backend_version"], "Backend lookup identity changed")
            expected = validate_receipt(receipt, task, manifest).value
            require(status["receipt_digest"] == sha256(canonical_bytes(expected)).hexdigest(),
                    "Backend lookup receipt mismatch")
            reference = (directory / "backend_dispatch_receipt.json").relative_to(root).as_posix()
            if value["operation_phase"] in ("dispatch_receipt_committed", "result_reference_committed"):
                require(value["dispatch_receipt_reference"] == reference and
                        value["dispatch_receipt_digest"] == sha256(canonical_bytes(expected)).hexdigest() and
                        read_regular(root / reference) == canonical_bytes(expected), "Backend receipt replay changed")
                return expected
            require(value["operation_phase"] == "dispatch_authorized", "Backend receipt has no dispatch intent")
            from lqcd_agent.control.coordinator import publish_exact
            publish_exact(root / reference, canonical_bytes(expected),
                          observer=self.coordinator.observer, name="external.receipt")
            prior = value["phase_revision"]
            value.update(operation_phase="dispatch_receipt_committed", phase_revision=prior + 1,
                         dispatch_receipt_reference=reference,
                         dispatch_receipt_digest=sha256(canonical_bytes(expected)).hexdigest(),
                         last_observed_status=status["status"],
                         last_observed_at=self.coordinator._time().monotonic_seconds)
            boundary(self.coordinator.observer, "external.dispatch_receipt_committed", "before", value=value)
            require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                               (prior + 1, canonical_bytes(value), self.producer, prior)).rowcount == 1,
                    "Backend receipt CAS lost")
            boundary(self.coordinator.observer, "external.dispatch_receipt_committed", "after", value=value)
        return expected

    def publish_result_reference(self):
        boundary(self.coordinator.observer, "external.backend_completion", "before",
                 value={"producer_operation_id": self.producer})
        status = validate_status(self.backend.lookup(self.producer)).value
        require(status["status"] in ("completed", "failed"), "Backend has no immutable terminal result")
        boundary(self.coordinator.observer, "external.backend_completion", "after", value=status)
        reference = validate_result_reference(self.backend.fetch_result(self.producer)).value
        require(reference["producer_operation_id"] == self.producer, "Foreign Backend result reference")
        content = self.result_loader(reference)
        require(type(content) is bytes and len(content) == reference["size"] and
                sha256(content).hexdigest() == reference["digest"], "Backend result reference changed")
        with self.coordinator.transaction() as db:
            value, root, directory, task, _ = self._source(db)
            require(status["producer_operation_id"] == self.producer and
                    status["backend_kind"] == task["coding_backend_kind"] and
                    status["backend_version"] == task["backend_version"] and
                    status["receipt_digest"] == value["dispatch_receipt_digest"],
                    "Backend status lost the original receipt")
            target = (directory / "code_agent_external_result.json").relative_to(root).as_posix()
            if value["operation_phase"] == "result_reference_committed":
                require(value["result_reference"] == target and value["result_digest"] == reference["digest"] and
                        read_regular(root / target) == content, "Backend result replay changed")
                return reference
            require(value["operation_phase"] == "dispatch_receipt_committed", "Result lacks committed dispatch receipt")
            from lqcd_agent.control.coordinator import publish_exact
            publish_exact(root / target, content, observer=self.coordinator.observer,
                          name="external.immutable_result")
            prior = value["phase_revision"]
            value.update(operation_phase="result_reference_committed", phase_revision=prior + 1,
                         result_reference=target, result_digest=reference["digest"],
                         last_observed_status=status["status"],
                         last_observed_at=self.coordinator._time().monotonic_seconds)
            boundary(self.coordinator.observer, "external.result_reference_committed", "before", value=value)
            require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                               (prior + 1, canonical_bytes(value), self.producer, prior)).rowcount == 1,
                    "Backend result CAS lost")
            boundary(self.coordinator.observer, "external.result_reference_committed", "after", value=value)
        return reference


class ExternalNormalFinal:
    """Commit a Host-validated normal winner from one immutable Backend result."""

    def __init__(self, dispatch, base_repository):
        self.dispatch = dispatch
        self.base_repository = base_repository

    def _interrupt_unavailable(self, value):
        from lqcd_agent.control.interfaces import ActorContext, ControlPlane
        from lqcd_agent.control.pause import ResolveExternalInterruptRequest
        dispatch = self.dispatch
        locator = value["run_locator"]
        root = dispatch.coordinator.root / locator["case_id"] / locator["run_id"]
        trigger = {"run_locator": locator, "producer_operation_id": dispatch.producer,
                   "reason": "normal_finalization_unavailable"}
        path = root / "code_agent_control" / value["attempt_id"] / "normal_unavailable_trigger.json"
        publish_exact(path, canonical_bytes(trigger))
        plane = ControlPlane(dispatch.coordinator, worker_id=dispatch.worker_id)
        plane.external_adapter = CodeExternalStop(dispatch.coordinator, dispatch.backend,
                                                  dispatch.containment, dispatch.receipt_loader)
        request = ResolveExternalInterruptRequest(locator, dispatch.producer, trigger["reason"],
            path.relative_to(root).as_posix(), sha256(canonical_bytes(trigger)).hexdigest())
        return plane.resolve_external_interrupt(request, actor=ActorContext("code_host", "host", ("control.internal",)))

    def commit(self, *, tool_audit, patch):
        dispatch = self.dispatch
        coordinator = dispatch.coordinator
        current = ExternalControl(coordinator).read(coordinator.connection, dispatch.producer)
        locator = current["run_locator"]
        handoff = (coordinator.root / locator["case_id"] / locator["run_id"] / "code_agent_control" /
                   current["attempt_id"] / "normal_unavailable_trigger.json")
        if current["resolution_owner"] is None and handoff.exists():
            return self._interrupt_unavailable(current)
        if current["resolution_owner"] == "interrupt" and current.get("cancel_reason") == "normal_finalization_unavailable":
            return self._interrupt_unavailable(current)
        with coordinator.transaction() as db:
            value = ExternalControl(coordinator).read(db, dispatch.producer)
            if value["operation_phase"] == "external_final_evidence_committed":
                verified, proof = ExternalControl(coordinator).final_evidence(db, dispatch.producer)
                require(verified["resolution_owner"] == "normal" and proof["proof_kind"] == "safe_stop",
                        "A different resolution already owns this Code operation")
                root = coordinator.root / value["run_locator"]["case_id"] / value["run_locator"]["run_id"]
                directory = root / "code_agent_control" / value["attempt_id"]
                require(not (directory / "changes.patch").is_symlink(),
                        "Normal final replay found a symlink patch")
                require(read_regular(directory / "tool_audit.jsonl") == tool_audit and
                        (patch is None and not (directory / "changes.patch").exists() or
                         type(patch) is bytes and read_regular(directory / "changes.patch") == patch),
                        "Normal final replay changed its sealed evidence")
                return verified
            source, root, directory, task, manifest = dispatch._source(db)
            require(source["operation_phase"] == "result_reference_committed" and
                    source["dispatch_started_at"] is not None, "Normal final lacks an original result")
            original_revision = source["phase_revision"]
            receipt = validate_receipt(read_regular(root / source["dispatch_receipt_reference"]), task, manifest).value
            raw = read_regular(root / source["result_reference"])
            require(sha256(raw).hexdigest() == source["result_digest"] and
                    sha256(canonical_bytes(receipt)).hexdigest() == source["dispatch_receipt_digest"],
                    "Original Backend evidence changed")
            witness = source["prestart"]["workspace"]

        status = validate_status(dispatch.backend.lookup(dispatch.producer)).value
        require(status["producer_operation_id"] == dispatch.producer and
                status["backend_kind"] == task["coding_backend_kind"] and
                status["backend_version"] == task["backend_version"] and
                status["status"] in ("completed", "failed") and
                status["receipt_digest"] == source["dispatch_receipt_digest"],
                "Backend did not preserve the terminal operation")
        dispatch.containment.revoke_writes(dispatch.producer)
        dispatch.containment.terminate(dispatch.producer)
        dispatch.containment.kill_all(dispatch.producer)
        dispatch.containment.drain(dispatch.producer)
        stop_proof = dispatch.containment.proof(dispatch.producer)
        if not (stop_proof["termination_or_not_dispatched"] == "confirmed" and
                all(observed is True for name, observed in stop_proof.items() if name != "termination_or_not_dispatched")):
            return self._interrupt_unavailable(source)
        audit = validate_tool_audit(tool_audit, task, manifest)
        require(len(audit) == dispatch.containment.observed_tool_count(dispatch.producer),
                "Tool audit omits a Host-observed invocation")
        provider = WorkspaceProvider(coordinator.root / "code_workspaces")
        base = immutable_git_tree(self.base_repository, task["base_revision"])
        now = coordinator._time().monotonic_seconds
        prior_seal = directory / "workspace_seal.json"
        finished_at = loads(read_regular(prior_seal))["sealed_at"] if prior_seal.exists() else now
        require(source["dispatch_started_at"] <= finished_at <= now, "Invalid backend stop interval")
        duration = finished_at - source["dispatch_started_at"]
        require(duration >= 0, "Backend active interval moved backward")
        sealed_at = finished_at
        boundary(coordinator.observer, "external.workspace_seal", "before", value=source)
        changes, seal = seal_workspace(provider, task, manifest, witness, base,
                                       backend_status=status["status"], stop_proof=stop_proof,
                                       tool_audit=tool_audit, sealed_at=sealed_at, fence=lambda: None)
        boundary(coordinator.observer, "external.workspace_seal", "after", value=source)
        validated = preflight_result(raw, task, manifest, receipt, seal, changes, tool_audit, patch,
                                     provider, witness, base).value
        actual = {"llm_calls": sum(item["resource_usage"]["llm_calls"] for item in audit),
                  "tool_calls": len(audit), "verification_commands": 0, "active_seconds": duration}
        require(validated["resource_usage"] == actual, "Backend usage lacks exact Host observation")

        with coordinator.transaction() as db:
            value, root, directory, current_task, current_manifest = dispatch._source(db)
            require(value["phase_revision"] == original_revision and
                    value["operation_phase"] == "result_reference_committed" and
                    current_task == task and current_manifest == manifest and
                    value["result_digest"] == sha256(raw).hexdigest(),
                    "Normal final lost the original revision or source")
            records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
            reservations = [record for record in records if record["record_type"] == "budget" and
                            record["event"] == "resource_reserved" and
                            record["payload"]["resource_operation_id"] == value["reservation_id"]]
            require(len(reservations) == 1 and digest(reservations[0]) == value["reservation_digest"] and
                    all(actual[name] <= maximum for name, maximum in
                        reservations[0]["payload"]["maximum_charge"].items()),
                    "Normal final exceeds its trusted aggregate reservation")
            for name, content in (("change_manifest.json", canonical_bytes(changes)),
                                  ("workspace_seal.json", canonical_bytes(seal)),
                                  ("tool_audit.jsonl", tool_audit)):
                publish_exact(directory / name, content)
            if patch is not None:
                publish_exact(directory / "changes.patch", patch)
            proof = {key: value[key] for key in ("producer_operation_id", "run_locator", "attempt_id", "cycle_id", "lease_epoch")}
            proof.update(resolution_owner="normal", stop_proof=stop_proof, proof_kind="safe_stop",
                         classification_timing="candidate_classified_in_normal_request_before_cas",
                         interrupt_disposition="not_applicable", proven_policy_violation=False,
                         resource_actual=actual, dispatch_receipt_digest=value["dispatch_receipt_digest"],
                         result_digest=value["result_digest"], workspace_seal_digest=seal["seal_digest"])
            final_path = directory / "external_final_evidence.json"
            boundary(coordinator.observer, "external.final_evidence", "before", value=value)
            publish_exact(final_path, canonical_bytes(proof))
            boundary(coordinator.observer, "external.final_evidence", "after", value=value)
            value.update(operation_phase="external_final_evidence_committed",
                         operation_status=status["status"], phase_revision=original_revision + 1,
                         resolution_owner="normal", workspace_seal_digest=seal["seal_digest"],
                         proof_kind="safe_stop", terminal_evidence_reference=final_path.relative_to(root).as_posix(),
                         terminal_evidence_digest=sha256(canonical_bytes(proof)).hexdigest(),
                         last_observed_status=status["status"], last_observed_at=now)
            boundary(coordinator.observer, "external.resolution_cas", "before", value=value)
            require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                               (original_revision + 1, canonical_bytes(value), dispatch.producer, original_revision)).rowcount == 1,
                    "Normal final CAS lost")
            boundary(coordinator.observer, "external.resolution_cas", "after", value=value)
            ExternalControl(coordinator).final_evidence(db, dispatch.producer)
            return value


class CodeExternalStop:
    """Turn the B02 resolution winner into Host-observed stop evidence."""

    def __init__(self, coordinator, backend, containment, receipt_loader):
        self.coordinator = coordinator
        self.backend = backend
        self.containment = containment
        self.receipt_loader = receipt_loader

    def _maximum(self, value):
        locator = value["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
        rows = [row for row in records if row["record_type"] == "budget" and
                row["event"] == "resource_reserved" and
                row["payload"]["resource_operation_id"] == value["reservation_id"]]
        require(len(rows) == 1 and digest(rows[0]) == value["reservation_digest"],
                "External stop lost its aggregate reservation")
        return rows[0]["payload"]["maximum_charge"]

    def _observe_stop(self, value):
        coordinator = self.coordinator
        external_id = value["producer_operation_id"]
        missing = []
        status = None
        try:
            status = validate_status(self.backend.lookup(external_id)).value
            require(status["producer_operation_id"] == external_id and
                    status["backend_kind"] == value["backend_kind"] and
                    status["backend_version"] == value["backend_version"],
                    "Backend stop lookup changed identity")
            if value.get("dispatch_started_at") is not None:
                locator = value["run_locator"]
                root = coordinator.root / locator["case_id"] / locator["run_id"]
                directory = root / "code_agent_control" / value["attempt_id"]
                task = validate_task(read_regular(directory / "code_agent_task.json")).value
                manifest = validate_manifest(read_regular(directory / "workspace_manifest.json"), task).value
                require(task["task_digest"] == value["task_digest"] and
                        task["producer_operation_id"] == external_id and
                        manifest["manifest_digest"] == value["workspace_manifest_digest"],
                        "Backend stop source changed")
            if status["status"] != "unknown":
                require(value.get("dispatch_started_at") is not None,
                        "Backend stop has no dispatch authority")
                receipt = validate_receipt(self.receipt_loader(status["receipt_reference"]), task, manifest).value
                require(status["receipt_digest"] == sha256(canonical_bytes(receipt)).hexdigest(),
                        "Backend stop receipt changed")
            if value["dispatch_receipt_digest"] is not None:
                require(status["receipt_digest"] == value["dispatch_receipt_digest"],
                        "Backend stop lookup lost the original receipt")
        except (ControlIntegrityError, OSError, ValueError):
            missing.append("backend_lookup")
        never_started = self.containment.never_started(external_id)
        if (never_started and status is not None and status["status"] == "unknown" and
                value["dispatch_receipt_reference"] is None):
            dimensions = {"termination_or_not_dispatched": {"tag": "not_dispatched"},
                          "write_lease_revocation": True, "verify_empty": True,
                          "bounded_drain": True, "post_stop_stability": True}
            actual = {name: 0 for name in ("llm_calls", "tool_calls", "verification_commands", "active_seconds")}
        else:
            try:
                boundary(coordinator.observer, "external.backend_cancel", "before", value=value)
                cancelled = validate_status(self.backend.cancel(external_id, value["cancel_reason"])).value
                boundary(coordinator.observer, "external.backend_cancel", "after", value=cancelled)
                require(cancelled["producer_operation_id"] == external_id and
                        cancelled["backend_kind"] == value["backend_kind"] and
                        cancelled["backend_version"] == value["backend_version"],
                        "Backend cancellation changed identity")
            except (ControlIntegrityError, OSError, ValueError):
                missing.append("backend_cancel")
            if never_started:
                dimensions = {"termination_or_not_dispatched": "unknown",
                              "write_lease_revocation": False, "verify_empty": False,
                              "bounded_drain": False, "post_stop_stability": False}
            else:
                try:
                    boundary(coordinator.observer, "external.write_lease_revocation", "before", value=value)
                    self.containment.revoke_writes(external_id)
                    boundary(coordinator.observer, "external.write_lease_revocation", "after", value=value)
                    self.containment.terminate(external_id)
                    boundary(coordinator.observer, "external.containment_kill_all", "before", value=value)
                    self.containment.kill_all(external_id)
                    boundary(coordinator.observer, "external.containment_kill_all", "after", value=value)
                    boundary(coordinator.observer, "external.bounded_drain", "before", value=value)
                    self.containment.drain(external_id)
                    boundary(coordinator.observer, "external.bounded_drain", "after", value=value)
                    boundary(coordinator.observer, "external.verify_empty", "before", value=value)
                    boundary(coordinator.observer, "external.post_stop_stability", "before", value=value)
                    dimensions = self.containment.proof(external_id)
                    boundary(coordinator.observer, "external.post_stop_stability", "after", value=dimensions)
                    boundary(coordinator.observer, "external.verify_empty", "after", value=dimensions)
                except (ControlIntegrityError, OSError, ValueError):
                    dimensions = {"termination_or_not_dispatched": "unknown",
                                  "write_lease_revocation": False, "verify_empty": False,
                                  "bounded_drain": False, "post_stop_stability": False}
                missing.extend(name for name, observed in dimensions.items() if
                               observed not in (True, "confirmed"))
            actual = self._maximum(value)
        if missing and dimensions["termination_or_not_dispatched"] in ("confirmed", {"tag": "not_dispatched"}):
            dimensions["termination_or_not_dispatched"] = "unknown"
            missing.append("termination_or_not_dispatched")
        safe = (not missing and dimensions["termination_or_not_dispatched"] in
            ("confirmed", {"tag": "not_dispatched"}) and all(dimensions[name] is True for name in
            ("write_lease_revocation", "verify_empty", "bounded_drain", "post_stop_stability")))
        if not safe and not missing:
            missing.append("termination_or_not_dispatched")
        locator = value["run_locator"]
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        directory = root / "code_agent_control" / value["attempt_id"]
        if not directory.is_dir():
            directory = root
        proof = {key: value[key] for key in ("producer_operation_id", "run_locator", "attempt_id", "cycle_id",
                                           "lease_epoch", "resolution_owner")}
        proof.update(stop_proof=dimensions, proof_kind="safe_stop" if safe else "unavailable",
                     classification_timing=PROTOCOL["state_machines"]["external_operation"]["final_proof_classification"]
                     ["resolution_timing"][value["resolution_owner"]],
                     interrupt_disposition=value.get("interrupt_disposition", "not_applicable"),
                     proven_policy_violation=False, resource_actual=actual)
        if not safe:
            quarantine = directory / "external_stop_unavailable.json"
            proof.update(quarantine_reference=quarantine.relative_to(root).as_posix(),
                         missing_proof_dimensions=sorted(set(missing)))
        return proof

    def stop(self, coordinator, external_id, owner):
        require(coordinator is self.coordinator, "Foreign stop coordinator")
        with coordinator.transaction() as db:
            value = ExternalControl(coordinator).read(db, external_id)
            if value["operation_phase"] == "external_final_evidence_committed":
                require(value["resolution_owner_operation_id"] == owner, "Foreign final stop owner")
                return ExternalControl(coordinator).final_evidence(db, external_id)[0]
            intent = "cancel_intent_committed" if value["resolution_owner"] == "cancel" else "interrupt_stop_intent_committed"
            require(value["resolution_owner_operation_id"] == owner and
                    value["resolution_owner"] in ("cancel", "interrupt") and
                    value["operation_phase"] in (intent, "termination_evidence_committed") and
                    value["operation_status"] == "stop_requested", "Missing B02 stop intent")
        locator = value["run_locator"]
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        directory = root / "code_agent_control" / value["attempt_id"]
        if not directory.is_dir():
            directory = root
        if value["operation_phase"] == intent:
            proof = self._observe_stop(value)
            termination = directory / "termination_evidence.json"
            raw = canonical_bytes(proof)
            if termination.exists() and read_regular(termination) != raw:
                candidate_raw = read_regular(termination)
                candidate = loads(candidate_raw)
                fields = set(proof) - {"quarantine_reference", "missing_proof_dimensions"}
                require(proof["proof_kind"] == "unavailable" and type(candidate) is dict and
                        type(candidate.get("stop_proof")) is dict and canonical_bytes(candidate) == candidate_raw and
                        set(candidate) == fields and candidate.get("proof_kind") == "safe_stop" and
                        all(candidate.get(key) == proof[key] for key in fields - {"proof_kind", "stop_proof"}) and
                        candidate.get("stop_proof", {}).get("termination_or_not_dispatched") in
                        ("confirmed", {"tag": "not_dispatched"}) and
                        all(candidate.get("stop_proof", {}).get(key) is True for key in
                            ("write_lease_revocation", "verify_empty", "bounded_drain", "post_stop_stability")),
                        "Conflicting termination candidate")
                termination = directory / "termination_evidence_unavailable.json"
            with coordinator.transaction() as db:
                current = ExternalControl(coordinator).read(db, external_id)
                require(current == value, "External termination observation lost its owner")
                if proof["proof_kind"] == "unavailable":
                    quarantine = root / proof["quarantine_reference"]
                    publish_exact(quarantine, canonical_bytes({"owner": owner,
                        "missing_proof_dimensions": proof["missing_proof_dimensions"]}))
                boundary(coordinator.observer, "external.termination_evidence_committed", "before", value=current)
                boundary(coordinator.observer, "external.termination_evidence", "before", value=current)
                publish_exact(termination, raw)
                boundary(coordinator.observer, "external.termination_evidence", "after", value=current)
                revision = current["phase_revision"]
                current.update(operation_phase="termination_evidence_committed", phase_revision=revision + 1,
                    termination_evidence_reference=termination.relative_to(root).as_posix(),
                    termination_evidence_digest=sha256(raw).hexdigest())
                require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                    (revision + 1, canonical_bytes(current), external_id, revision)).rowcount == 1,
                    "External termination observation CAS lost")
                boundary(coordinator.observer, "external.termination_evidence_committed", "after", value=current)
                value = current
        termination = root / value["termination_evidence_reference"]
        require(termination == termination.resolve() and termination.is_relative_to(root),
                "Termination evidence escaped its Run")
        raw = read_regular(termination)
        require(sha256(raw).hexdigest() == value["termination_evidence_digest"],
                "Frozen termination evidence changed")
        proof = loads(raw)
        require(raw == canonical_bytes(proof) and
                all(proof[key] == value[key] for key in ("producer_operation_id", "run_locator", "attempt_id",
                    "cycle_id", "lease_epoch", "resolution_owner")),
                "Termination observation lost its identity")
        safe = proof["proof_kind"] == "safe_stop"
        with coordinator.transaction() as db:
            current = ExternalControl(coordinator).read(db, external_id)
            require(current == value and current["operation_phase"] == "termination_evidence_committed",
                    "External final lost its frozen termination CAS")
            final = directory / "external_final_evidence.json"
            if final.exists() and read_regular(final) != raw:
                candidate = loads(read_regular(final))
                require(candidate.get("resolution_owner") == "normal" and
                        all(candidate.get(key) == current[key] for key in
                            ("producer_operation_id", "run_locator", "attempt_id", "cycle_id",
                             "dispatch_receipt_digest", "result_digest")),
                        "Conflicting external final candidate")
                final = directory / ("external_final_evidence_" + owner + ".json")
            boundary(coordinator.observer, "external.external_final_evidence_committed", "before", value=current)
            publish_exact(final, raw)
            revision = current["phase_revision"]
            current.update(operation_phase="external_final_evidence_committed",
                           operation_status=("cancelled" if current["resolution_owner"] == "cancel" else "interrupted")
                           if safe else "recovery_required", phase_revision=revision + 1,
                           proof_kind=proof["proof_kind"], terminal_evidence_reference=final.relative_to(root).as_posix(),
                           terminal_evidence_digest=sha256(raw).hexdigest())
            require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                               (revision + 1, canonical_bytes(current), external_id, revision)).rowcount == 1,
                    "External stop CAS lost")
            boundary(coordinator.observer, "external.external_final_evidence_committed", "after", value=current)
            return ExternalControl(coordinator).final_evidence(db, external_id)[0]

    def prepare_timeout_delivery(self, view):
        from lqcd_agent.control.pause import TimeoutDelivery
        from .artifacts import timeout_bundle
        value, final = view["external"], view["final"]
        require(value["resolution_owner"] == "interrupt" and value["proof_kind"] == "safe_stop",
                "Timeout delivery has no trusted interrupt winner")
        locator = value["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        directory = root / "code_agent_control" / value["attempt_id"]
        task = validate_task(read_regular(directory / "code_agent_task.json")).value
        manifest = validate_manifest(read_regular(directory / "workspace_manifest.json"), task).value
        receipt = (read_regular(root / value["dispatch_receipt_reference"]) if
                   value["dispatch_receipt_reference"] is not None else None)
        members, result = timeout_bundle(task, manifest, value, final,
            dispatch_phase=view["original_dispatch"]["external_phase"], receipt=receipt)
        return TimeoutDelivery({name: content.decode() for name, content in members.items()},
            {"code_change_summary_path": None, "tests_status_path": None,
             "code_agent_task_path": "code_agent_task.json", "code_agent_result_path": "code_agent_result.json",
             "code_change_manifest_path": "change_manifest.json",
             "code_verification_results_path": "verification_results.json"}, result["status"],
            dict(PROTOCOL["state_machines"]["control_operation"]["recoverable_code_consumption_contract"]["result"]))


class CodeWatchdog:
    """Fence an expired monitor and resolve the original operation only."""

    def __init__(self, coordinator, backend, containment, receipt_loader, *, worker_id="code_watchdog"):
        self.coordinator = coordinator
        self.backend = backend
        self.containment = containment
        self.receipt_loader = receipt_loader
        self.worker_id = worker_id

    def inspect(self, producer_operation_id):
        value = ExternalControl(self.coordinator).read(self.coordinator.connection, producer_operation_id)
        if value["operation_phase"] == "external_final_evidence_committed" or value["resolution_owner"] is not None:
            return None
        now = self.coordinator._time().monotonic_seconds
        active = value.get("prestart", {}).get("active_time")
        setup_deadline = active["setup_record"]["payload"]["deadline_monotonic_seconds"] if active else value["hard_deadline"]
        dispatch_at = value.get("dispatch_started_at")
        maximum = self._maximum(value) if value.get("reservation_id") is not None else None
        backend_deadline = dispatch_at + maximum["active_seconds"] if dispatch_at is not None and maximum is not None else None
        reason = None
        if maximum is not None and not self.containment.never_started(producer_operation_id):
            try:
                tools = self.containment.observed_tool_count(producer_operation_id)
            except ControlIntegrityError:
                tools = None
            if tools is not None and tools >= maximum["tool_calls"]:
                reason = "aggregate_hard_limit"
        if reason is None and backend_deadline is not None and now >= backend_deadline:
            reason = "operation_timeout"
        if reason is None and now >= value["hard_deadline"]:
            reason = "policy_stop"
        if reason is None and dispatch_at is None and now >= setup_deadline:
            reason = "policy_stop"
        return reason

    def _maximum(self, value):
        return CodeExternalStop(self.coordinator, self.backend, self.containment,
                                self.receipt_loader)._maximum(value)

    def enforce(self, producer_operation_id):
        from lqcd_agent.control.interfaces import ActorContext, ControlPlane
        from lqcd_agent.control.pause import ResolveExternalInterruptRequest
        coordinator = self.coordinator
        plane = ControlPlane(coordinator, worker_id=self.worker_id)
        plane.external_adapter = CodeExternalStop(coordinator, self.backend, self.containment, self.receipt_loader)
        actor = ActorContext("code_watchdog", "host", ("control.internal",))
        for row in coordinator.connection.execute(
                "SELECT operation_id FROM control_operations WHERE operation_type='resolve_external_interrupt'"):
            existing = coordinator.get(row[0])
            request = existing["request"]
            if (request["producer_operation_id"] == producer_operation_id and
                    request["actor"] == actor.authorize("control.internal")):
                return plane.resolve_external_interrupt(ResolveExternalInterruptRequest(**{
                    key: request[key] for key in ("run_locator", "producer_operation_id", "reason",
                                             "trigger_reference", "trigger_digest")}), actor=actor)
        reason = self.inspect(producer_operation_id)
        if reason is None:
            return None
        with coordinator.transaction() as db:
            value = ExternalControl(coordinator).read(db, producer_operation_id)
            require(value["resolution_owner"] is None, "Watchdog lost empty resolution owner")
            if value["worker_owner_id"] != self.worker_id or coordinator._time().monotonic_seconds >= value["worker_lease_expires_at"]:
                boundary(coordinator.observer, "external.watchdog_takeover", "before", value=value)
                revision = value["phase_revision"]
                value.update(lease_epoch=value["lease_epoch"] + 1,
                             worker_owner_id=self.worker_id,
                             worker_lease_expires_at=coordinator._time().monotonic_seconds + 10,
                             phase_revision=revision + 1)
                require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                    (revision + 1, canonical_bytes(value), producer_operation_id, revision)).rowcount == 1,
                    "Watchdog monitor takeover CAS lost")
                boundary(coordinator.observer, "external.watchdog_takeover", "after", value=value)
        if (value.get("prestart", {}).get("aggregate") is not None and
                value["reservation_digest"] is None):
            from .prestart import CodePrestart
            CodePrestart(coordinator, producer_operation_id, self.worker_id,
                         value["lease_epoch"]).recover_frozen_aggregate()
        locator = value["run_locator"]
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        trigger = {"run_locator": locator, "producer_operation_id": producer_operation_id, "reason": reason}
        path = root / ("watchdog_" + producer_operation_id + "_trigger.json")
        with coordinator.transaction():
            publish_exact(path, canonical_bytes(trigger))
        request = ResolveExternalInterruptRequest(locator, producer_operation_id, reason,
            path.relative_to(root).as_posix(), sha256(canonical_bytes(trigger)).hexdigest())
        return plane.resolve_external_interrupt(request, actor=actor)
