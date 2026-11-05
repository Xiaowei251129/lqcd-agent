"""A04 Pause record validation and replay, subordinate to the execution ledger."""
from dataclasses import asdict, dataclass
from .clock import Timestamp
from .protocol import PROTOCOL, operation_variant
from .strict_json import ControlIntegrityError, canonical_bytes, closed, digest, digest_value, loads, number, require, text


CONTRACT = PROTOCOL["state_machines"]["pause_lifecycle"]
FIELDS = ("pause_id", "pause_index", "cycle_id", "reason", "status", "requesting_attempt_id",
          "target_attempt_id", "input_contract", "authorization_scope", "runtime_fingerprint",
          "state_digest", "operation_id", "lease_epoch", "phase_revision", "proof")
IDENTITY_FIELDS = ("pause_id", "pause_index", "cycle_id", "reason", "requesting_attempt_id",
                   "target_attempt_id", "input_contract", "authorization_scope", "runtime_fingerprint")
REASONS = ("human_input", "external_result", "recovery_decision")
FINGERPRINT_FIELDS = ("control_protocol", "application_build", "graph_topology", "state_schema",
                      "execution_schema", "artifact_schema", "langgraph", "checkpointer", "serializer")


def runtime_fingerprint():
    """Capture actual Host runtime components only at the explicit control boundary."""
    from importlib.metadata import version
    from .protocol import PROTOCOL_SHA256

    from importlib.resources import files
    import json
    manifest = json.loads(files("lqcd_agent").joinpath("_build_manifest.json").read_text())
    value = {"control_protocol": PROTOCOL_SHA256, "application_build": manifest["application_build"],
             "graph_topology": manifest["graph_topology"], "state_schema": "0.4", "execution_schema": "0.4",
             "artifact_schema": "0.1", "langgraph": version("langgraph"),
             "checkpointer": "langgraph.checkpoint.sqlite:" + version("langgraph-checkpoint-sqlite"),
             "serializer": "lqcd_agent.control.checkpoints.CanonicalCheckpointSerializer:0.4"}
    validate_fingerprint(value)
    return value


@dataclass(frozen=True)
class PublishPauseRequest:
    """Internal Host proposal; Run heads, identities and deadline are derived."""

    run_locator: dict
    reason: str
    requesting_attempt_id: str
    target_attempt_id: str | None
    input_contract: dict
    authorization_scope: dict
    idempotency_key: str


@dataclass(frozen=True)
class ResumeRunRequest:
    run_locator: dict
    pause_id: str
    idempotency_key: str
    input_kind: str
    input_snapshot: dict
    input_digest: str


@dataclass(frozen=True)
class CancelPauseRequest:
    run_locator: dict
    pause_id: str
    idempotency_key: str
    reason: str


@dataclass(frozen=True)
class ResolveExternalInterruptRequest:
    run_locator: dict
    producer_operation_id: str
    reason: str
    trigger_reference: str
    trigger_digest: str


class PauseExpired(ControlIntegrityError):
    """Deadline rejection does not mutate the Pause or create an Attempt."""

    code = "pause_expired"


class PauseOwnershipConflict(ControlIntegrityError):
    """Another durable owner won; rejection must not change its outcome."""


class PauseOperations:
    def __init__(self, coordinator, worker_id, lease_seconds, target_adapter=None, decision_adapter=None, external_adapter=None, preparation_adapter=None):
        self.coordinator, self.worker_id, self.lease_seconds = coordinator, worker_id, lease_seconds
        self.target_adapter = target_adapter
        self.decision_adapter = decision_adapter
        self.external_adapter = external_adapter
        self.preparation_adapter = preparation_adapter

    def cancel(self, request, actor):
        from .checkpoints import verify_checkpoint
        from .coordinator import component, read_regular
        from .execution import parse_ledger
        from .integrity import validate_run_root
        from .operations import continue_publication_plan

        require(type(request) is CancelPauseRequest, "Expected typed CancelPauseRequest")
        identity = actor.authorize("cancel")
        closed(request.run_locator, ("case_id", "run_id"))
        for value in request.run_locator.values():
            component(value)
        text(request.pause_id)
        text(request.idempotency_key)
        require(request.reason == "operator_cancel", "Cancel cannot replace an internal timeout or integrity trigger")
        canonical = {**asdict(request), "actor": identity}
        canonical.pop("idempotency_key")
        coordinator = self.coordinator
        key = digest(request.run_locator)
        root = coordinator.root / request.run_locator["case_id"] / request.run_locator["run_id"]
        from .operations import ExternalControl
        old = coordinator.lookup_key("public_control", request.idempotency_key)
        winners = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM external_operations")]
        existing_winner = any(value["run_locator"] == request.run_locator and value.get("pause_id") == request.pause_id and
                              value["resolution_owner"] in ("cancel", "interrupt") for value in winners)
        if old is not None and old["reservation"].get("external_operation_identity", {}).get("producer_operation_id") or existing_winner or ExternalControl(coordinator).attached(coordinator.connection, request.run_locator):
            return ExternalCancellation(self).cancel(request, canonical)
        with coordinator.transaction() as db:
            operation = coordinator.lookup_key("public_control", request.idempotency_key, db=db)
            if operation is not None:
                require(operation["request_digest"] == digest({"operation_type": "cancel_pause", "operation_variant": "not_applicable", "request": canonical}),
                        "Same-key request conflict")
            else:
                row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (key,)).fetchone()
                require(row is not None, "Unknown Run")
                control = loads(row["value"])
                require(control["projection"] is not None, "Run has no stable checkpoint")
                verify_checkpoint(root, control["manifest"])
                state = validate_run_root(root, manifest=control["manifest"], projection=control["projection"]).value
                opened = state.get("active_pause")
                require(state["run_status"] == "paused" and opened is not None and opened["status"] == "opened" and
                        opened["pause_id"] == request.pause_id, "Cancel requires the latest public opened Pause")
                records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
                opened = records[-1]
                require(opened["record_type"] == "pause" and opened["status"] == "opened", "Cancel source head mismatch")
                owner = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, request.pause_id)).fetchone()
                require(owner is not None and loads(owner[0])["owner"] is None and
                        db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone() is None, "Pause/Run already owned")
                absence = self._external_absence(db, request.run_locator)
                reserved = {r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved"}
                settled = {r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"}
                require(reserved == settled, "Cancel requires resource disposition")
                terminal_contract = digest({"run_locator": request.run_locator, "pause_id": request.pause_id,
                                            "opened_head": digest(opened), "reason": request.reason, "run_status": "halted"})

                def reserve(operation_id, stamp):
                    return {"exact_pause_and_opened_head": {"pause_id": request.pause_id, "execution_head": digest(opened)},
                            "external_operation_identity": {"tag": "null"}, "typed_cancel_reason": request.reason,
                            "precomputed_pause_cancel_or_quarantine_event": {"event_index": len(records) + 1, "event": "pause_cancelled"},
                            "terminal_disposition_contract_digest": terminal_contract}

                operation = coordinator.reserve_in_transaction(
                    db, "cancel_pause", "not_applicable", "public_control", request.idempotency_key, canonical,
                    self.worker_id, reserve, lease_seconds=self.lease_seconds,
                    build_snapshot=lambda op: self._cancel_snapshot(op, records, loads(read_regular(root / "artifact_index.json")), state, row["revision"], absence))
        try:
            return continue_publication_plan(coordinator, operation, self.worker_id, self.lease_seconds, self._resume_phase, rebuild=self._rebuild)
        except (ControlIntegrityError, OSError) as error:
            return self._fail(operation, error)

    def _fail(self, operation, error):
        from .coordinator import MaterializationSnapshotError

        with self.coordinator.transaction() as db:
            current = self.coordinator.failed_operation(db, operation, self.worker_id, error)
            missing = isinstance(error, MaterializationSnapshotError) and error.missing
            return self.coordinator.interrupt(db, current, "recovery_required" if missing else "failed", {
                "kind": "missing_materialization_snapshot" if missing else "pause_control_integrity_failure",
                "source_operation_id": current["operation_id"], "source_phase_revision": current["phase_revision"],
                "lease_epoch": current["lease_epoch"], "cause_type": type(error).__name__, "message": str(error)})

    def _external_absence(self, db, locator):
        from .operations import ExternalControl
        require(not ExternalControl(self.coordinator).attached(db, locator), "External Pause requires the external resolution adapter")
        return {"run_locator": locator, "external_operation_id": None, "authority": "coordinator_sqlite"}

    def _cancel_snapshot(self, operation, records, index, state, source_revision, absence):
        from .operations import PublicationPlan
        from .records import FIELDS as RECORD_FIELDS

        plan = PublicationPlan(operation, records, index)
        opened = records[-1]
        owner, locator = operation["operation_id"], operation["request"]["run_locator"]
        proof = {"proof_variant": "no_external_operation", "typed_null_external_identity": {"tag": "null"},
                 "external_absence_proof": absence, "not_dispatched": {"external_operation_id": None}}
        plan.step("cancel_arbitrated", {"exact_pause_identity_and_opened_head": operation["reservation"]["exact_pause_and_opened_head"],
                                        "outcome_conditioned_pause_run_owner_guard": {"owner": owner, "run_key": digest(locator)},
                                        "external_operation_identity_or_typed_null": {"tag": "null"},
                                        "external_revision_epoch_resolution_owner_and_owner_operation_id": {"tag": "not_applicable"},
                                        "arbitration_outcome": "no_external_operation",
                                        "winner_revision_and_proof_or_intent_digest_or_not_dispatched_digest": digest(absence)})
        cancelled = plan.append("pause", "pause_cancelled", **{key: opened[key] for key in IDENTITY_FIELDS}, status="cancelled",
                                state_digest=digest(state), operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=3,
                                proof={"opened": {"execution_head": digest(opened)}, "cancel": proof,
                                       "actor": operation["request"]["actor"], "request_digest": operation["request_digest"]})
        plan.step("pause_cancelled_recorded", {"pause_cancel_proof": proof},
                  branch={"arbitration_outcome": "no_external_operation", "external_final_proof_kind": "not_applicable"})
        target = next((r for r in reversed(records) if r["record_type"] == "attempt" and r["attempt_id"] == opened["target_attempt_id"]), None)
        disposition = {"tag": "not_applicable"}
        if target is not None:
            require(target["status"] == "scheduled", "Cancel target already started")
            fields = {key: target[key] for key in RECORD_FIELDS["attempt"]}
            fields["status"] = "abandoned"
            disposition = plan.append("attempt", "abandoned", **fields)
        plan.step("target_disposition_committed", {"target_abandoned_or_not_applicable": disposition})
        plan.step("resource_disposition_committed", {"resource_settlement_or_not_applicable": {"tag": "not_applicable"}})
        heads = {"execution_head": digest(plan.records[-1]), "artifact_head": index["artifact_head"], "checkpoint_head": state["checkpoint_head"]}
        plan.step("terminal_eligibility_verified", {"final_terminal_evidence": {"cancelled_head": digest(cancelled), "cancel_proof": proof},
                                                   "exact_authority_heads": heads, "single_assignment_resolution": "halted"})
        terminal = plan.append("run_lifecycle", "transitioned", from_status="paused", to_status="halted", reason_code="operator_cancel",
                               operation_id=owner, pause_id=opened["pause_id"], attempt_id=None, budget_event_id=None)
        plan.step("terminal_lifecycle_recorded", {"terminal_owner": owner, "terminal_closure_revision": 1,
                                                  "resolved_terminal_disposition": "halted",
                                                  "terminal_disposition_contract_digest": operation["reservation"]["terminal_disposition_contract_digest"],
                                                  "legal_terminal_lifecycle_edge": terminal})
        checkpoint = plan.checkpoint("cancelled")
        plan.step("terminal_checkpoint_committed", {"terminal_lifecycle_resulting_head": digest(terminal), "empty_active_pause_projection": {"pause_id": None}},
                  checkpoint=checkpoint)
        result = {"run_locator": locator, "run_status": "halted", "domain_status": None, "pause_id": None, "terminal_closure": "committed",
                  **{key: checkpoint["manifest"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}}
        plan.step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": len(plan.steps) + 2})
        return {"run_locator": locator, "steps": plan.steps, "opened": opened, "source_control_revision": source_revision,
                "source": {"records": records, "index": index, "state": state},
                "checkpoint": checkpoint, "external_absence": absence,
                "original_policy": next(r["payload"]["policy"] for r in records if r["record_type"] == "budget" and r["event"] == "policy_initialized")}

    def resume(self, request, actor):
        from .checkpoints import verify_source_checkpoint
        from .coordinator import component, read_regular
        from .execution import parse_ledger
        from .integrity import validate_run_root
        from .operations import continue_publication_plan

        require(type(request) is ResumeRunRequest, "Expected typed ResumeRunRequest")
        identity = actor.authorize("resume")
        closed(request.run_locator, ("case_id", "run_id"))
        for item in request.run_locator.values():
            component(item)
        text(request.pause_id)
        text(request.idempotency_key)
        digest_value(request.input_digest)
        require(digest(request.input_snapshot) == request.input_digest, "Resume input digest mismatch")
        require(request.input_kind in ("recovery_decision", "human_response", "external_result"), "Unknown reason-specific resume input")
        human = request.input_kind == "human_response"
        external_result = request.input_kind == "external_result"
        if human:
            closed(request.input_snapshot, ("case_id", "run_id", "cycle_id", "human_request_id", "decision", "conditions", "reason", "decided_by"))
            require(all(request.input_snapshot[key] == value for key, value in request.run_locator.items()), "Human response Run mismatch")
            action = "validate_human_response"
        elif external_result:
            closed(request.input_snapshot, ("producer_operation_id", "external_final_digest"))
            text(request.input_snapshot["producer_operation_id"])
            digest_value(request.input_snapshot["external_final_digest"])
            action = "consume_external_result"
        else:
            closed(request.input_snapshot, ("action",))
            action = request.input_snapshot["action"]
            require(action in ("continue_existing_target", "abandon_and_halt"), "Unknown RecoveryDecision")
        variant = "abandon_and_halt" if action == "abandon_and_halt" else "continue_execution"
        canonical = {**asdict(request), "actor": identity}
        canonical.pop("idempotency_key")
        coordinator = self.coordinator
        key = digest(request.run_locator)
        root = coordinator.root / request.run_locator["case_id"] / request.run_locator["run_id"]
        with coordinator.transaction() as db:
            old = coordinator.lookup_key("public_control", request.idempotency_key, db=db)
            if old is not None:
                expected = digest({"operation_type": "resume_run", "operation_variant": variant, "request": canonical})
                require(old["request_digest"] == expected, "Same-key request conflict")
                operation = old
            else:
                row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (key,)).fetchone()
                require(row is not None, "Unknown Run")
                control = loads(row["value"])
                require(control["projection"] is not None, "Run has no stable checkpoint")
                require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone() is None, "Run already has terminal owner")
                verify_source_checkpoint(coordinator, db, root, control["manifest"])
                state = validate_run_root(root, manifest=control["manifest"], projection=control["projection"]).value
                active = state.get("active_pause")
                require(state["run_status"] == "paused" and active is not None and active["status"] == "opened" and
                        active["pause_id"] == request.pause_id, "Run has no matching stable opened Pause")
                records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
                opened = records[-1]
                require(opened["record_type"] == "pause" and opened["status"] == "opened" and opened["reason"] == ("human_input" if human else request.input_kind),
                        "Resume reason or opened head mismatch")
                require(opened["runtime_fingerprint"] == runtime_fingerprint(), "Unsupported runtime fingerprint")
                scope = opened["authorization_scope"]
                require(identity["actor_type"] == scope["actor_type"] and set(scope["scopes"]) <= set(identity["scopes"]), "Pause actor/scope mismatch")
                if not human and not external_result:
                    require(action in opened["input_contract"]["actions"], "RecoveryDecision not allowed by Pause")
                self._check_deadline(opened)
                owner = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, request.pause_id)).fetchone()
                require(owner is not None and loads(owner[0])["owner"] is None and loads(owner[0])["status"] == "opened",
                        "Pause already claimed or cancelled")
                target = next((r for r in reversed(records) if r["record_type"] == "attempt" and r["attempt_id"] == opened["target_attempt_id"]), None)
                external = {"tag": "not_applicable"}
                preparation = None
                if external_result:
                    from .operations import ExternalControl
                    external_control = ExternalControl(coordinator)
                    values = external_control.attached(db, request.run_locator)
                    require(len(values) == 1 and values[0]["producer_operation_id"] == request.input_snapshot["producer_operation_id"] ==
                            opened["input_contract"]["producer_operation_id"], "Resume external producer mismatch")
                    value, final = external_control.final_evidence(db, values[0]["producer_operation_id"])
                    require(value["resolution_owner"] == "normal" and value["proof_kind"] == "safe_stop" and
                            not final.get("proven_policy_violation") and value["terminal_evidence_digest"] == request.input_snapshot["external_final_digest"] and
                            value["pause_id"] == request.pause_id and value["active_binding_status"] == "active", "External result is not a consumable normal final")
                    require(target is not None and target["attempt_kind"] == "code_agent" and target["status"] == "scheduled" and
                            target["attempt_id"] == value["attempt_id"] and self.target_adapter is not None and self.external_adapter is not None,
                            "External resume lacks its scheduled Code target or trusted domain ports")
                    inbound = [r for r in records if r["record_type"] == "transition" and r["target_attempt_id"] == target["attempt_id"]]
                    require(len(inbound) == 1 and inbound[0]["transition_id"] == target["inbound_transition_id"], "External target inbound mismatch")
                    reserved = next((r for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                                     r["payload"]["resource_operation_id"] == value["reservation_id"]), None)
                    require(reserved is not None and digest(reserved) == value["reservation_digest"] and
                            final.get("resource_actual") is not None and all(final["resource_actual"][k] <= v for k, v in reserved["payload"]["maximum_charge"].items()),
                            "Normal external consumption lacks safe exact resource settlement")
                    external = {"tag": "normal_final", "value": value, "final": final, "reservation": reserved}
                    if hasattr(self.target_adapter, "preflight_delivery"):
                        self.target_adapter.preflight_delivery(external)
                if human:
                    require(opened["target_attempt_id"] is None and self.target_adapter is not None, "Human resume needs null target and a trusted validator")
                    require(self.decision_adapter is not None, "Human resume needs a trusted repause decision adapter")
                    require(request.input_snapshot["cycle_id"] == state["cycle_id"] and
                            request.input_snapshot["human_request_id"] == state["active_human_request_id"] == opened["input_contract"]["human_request_id"] and
                            state["human_request_status"] == "open", "Human response request mismatch")
                    selected = next(r["payload"]["policy"] for r in records if r["record_type"] == "budget" and r["event"] == "policy_initialized")
                    gate_inbound = next(r for r in records if r["record_type"] == "transition" and
                                        r["target_attempt_id"] == state["attempt_id"])
                    sequence = gate_inbound["fields"].get("stop_sequence_id")
                    if sequence is not None:
                        require(gate_inbound["target_attempt_kind"] == "human_gate" and
                                any(r["record_type"] == "transition" and r["trigger_reason"] == "budget_stop" and
                                    r["fields"].get("stop_sequence_id") == sequence and
                                    sequence == digest({"run_id": state["run_id"], "source_attempt_id": r["source_attempt_id"],
                                                        "reason": "budget_stop"}) for r in records), "Unproven Human terminal sequence")
                    for dimension, reserve_key in (("control_attempts_per_run", "control_attempts"), ("transitions_per_run", "transitions")):
                        needed = (3 if reserve_key == "control_attempts" else 4) if sequence is not None else 1 + selected["terminal_reserve"][reserve_key]
                        require(state["budget"]["dimensions"][dimension]["remaining"] >= needed,
                                "Human validation lacks reserved terminal capacity")
                    target = {**request.run_locator, "attempt_id": f"attempt_{state['attempt_index'] + 1:06d}", "attempt_kind": "human_gate",
                              "inbound_transition_id": f"transition_{state['transition_index'] + 1:06d}"}
                    inbound = [{"tag": "human_response_control", "human_request_id": state["active_human_request_id"]}]
                    self._external_absence(db, request.run_locator)
                if action == "continue_existing_target":
                    contract = PROTOCOL["state_machines"]["control_operation"]["recovery_target_authorization_contract"]
                    require(target is not None and target["attempt_kind"] in contract["continue_existing_target"]["allowed_target_kinds"],
                            "Recovery target cannot continue")
                    require(target["status"] == "scheduled", "Recovery target already started")
                    require(self.target_adapter is not None, "Recovery continuation requires a Host-owned target adapter")
                    inbound = [r for r in records if r["record_type"] == "transition" and r["target_attempt_id"] == target["attempt_id"]]
                    require(len(inbound) == 1 and inbound[0]["transition_id"] == target["inbound_transition_id"], "Recovery lacks unique committed inbound Transition")
                    require(sum(r["record_type"] == "attempt" and r["attempt_id"] == target["attempt_id"] for r in records) == 1,
                            "Recovery target was already started or disposed")
                    self._external_absence(db, request.run_locator)
                    target_capabilities = []
                    for capability in db.execute("SELECT capability_id,value FROM invocation_capabilities"):
                        value = loads(capability["value"])
                        bound = value["authorization"]["identity"]
                        if all(bound[key] == request.run_locator[key] for key in request.run_locator) and bound["attempt_id"] == target["attempt_id"]:
                            require(value["started_intent"] is None and value["state"] in ("unclaimed", "leased_not_started"), "Recovery target has execution intent")
                            target_capabilities.append((capability["capability_id"], value))
                    require(not any(r["record_type"] == "budget" and r["event"] == "resource_reserved" and r["payload"]["attempt_id"] == target["attempt_id"] for r in records),
                            "Recovery target already has resource effects")
                    if target["attempt_kind"] == "analysis_engineer" and state["current_artifacts"]["code"] is not None:
                        from .capabilities import InvocationLeases
                        require(len(target_capabilities) == 1 and "target_preparation" in target_capabilities[0][1]["authorization"],
                                "Analysis recovery requires its original fresh preparation proof")
                        original_id, original = target_capabilities[0]
                        InvocationLeases(coordinator, preparation_adapter=self.preparation_adapter)._activation(db, original_id, original)
                        preparation = {k: original["authorization"][k] for k in ("target_preparation", "preparation_receipt")}
                reservations = {r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved"}
                settled = {r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"}
                expected_pending = {external["value"]["reservation_id"]} if external_result else set()
                require(reservations - settled == expected_pending and settled <= reservations, "Resume has unexpected unsettled resources")
                terminal_contract = digest({"run_locator": request.run_locator, "pause_id": request.pause_id,
                                            "opened_head": digest(opened), "input_digest": request.input_digest, "run_status": "halted"})

                def reserve(operation_id, stamp):
                    if variant == "continue_execution":
                        return {"exact_pause_and_opened_head": {"pause_id": request.pause_id, "execution_head": digest(opened)},
                                "precomputed_next_event_identity_digest": digest({"event_index": len(records) + 1, "pause_id": request.pause_id, "operation_id": operation_id}),
                                "target_prestart_closure": {"target": target, "inbound_transition": inbound[0], "external": external, "preparation": preparation}}
                    return {"exact_pause_and_opened_head": {"pause_id": request.pause_id, "execution_head": digest(opened)},
                            "run_terminal_closure_key": key,
                            "precomputed_abandon_evidence": {"target": target, "input_digest": request.input_digest},
                            "terminal_disposition_contract_digest": terminal_contract}

                operation = coordinator.reserve_in_transaction(
                    db, "resume_run", variant, "public_control", request.idempotency_key, canonical, self.worker_id,
                    reserve, lease_seconds=self.lease_seconds,
                    build_snapshot=lambda op: (self._continue_snapshot if variant == "continue_execution" else self._abandon_snapshot)(
                        op, records, loads(read_regular(root / "artifact_index.json")), state, row["revision"]))
        try:
            if variant == "continue_execution":
                return self._continue_recovery(operation)
            return continue_publication_plan(coordinator, operation, self.worker_id, self.lease_seconds, self._resume_phase, rebuild=self._rebuild)
        except (PauseExpired, PauseOwnershipConflict) as error:
            with coordinator.transaction() as db:
                current = coordinator.failed_operation(db, operation, self.worker_id, error)
                return coordinator.interrupt(db, current, "failed", {
                    "kind": "pause_expired" if isinstance(error, PauseExpired) else "pause_ownership_conflict", "pause_id": request.pause_id})
        except (ControlIntegrityError, OSError) as error:
            with coordinator.transaction() as db:
                current = coordinator.failed_operation(db, operation, self.worker_id, error)
            failure = ConsumptionFailure(self)
            if external_result and current["status"] == "in_progress" and current["phase"] in failure.contract["entry_phases"]:
                return failure.start(current, error)
            return self._fail(current, error)

    def _continue_snapshot(self, operation, records, index, state, source_revision, completion=None, followup=None):
        from copy import deepcopy
        from .operations import PublicationPlan

        plan = PublicationPlan(operation, records, deepcopy(index))
        opened = records[-1]
        owner, request = operation["operation_id"], operation["request"]
        target = operation["reservation"]["target_prestart_closure"]["target"]
        proof = {"opened": {"execution_head": digest(opened)}, "input_snapshot": request["input_snapshot"],
                 "input_digest": request["input_digest"], "actor": request["actor"], "request_digest": operation["request_digest"],
                 "idempotency_key": operation["idempotency_key"]}

        def step(phase, evidence, **kwargs):
            branch = {"consumption_outcome_at_" + plan.source: "continue"} if plan.source in (
                "pause_ownership_reserved", "pause_claimed_recorded", "prestart_records_committed", "pause_consumed_recorded",
                "running_lifecycle_recorded", "resume_checkpoint_committed", "invocation_authorized") else None
            plan.step(phase, evidence, branch=branch, **kwargs)

        step("resume_disposition_committed", {"frozen_resume_variant": "continue_execution", "exact_opened_pause": opened,
                                              "reason_target_scope_preflight_proof": operation["reservation"]["target_prestart_closure"]})
        step("pause_ownership_reserved", {"exact_pause_cas": {"pause_id": opened["pause_id"], "owner": owner}, "opened_execution_head": digest(opened)})
        identity = {key: opened[key] for key in IDENTITY_FIELDS}
        claimed = plan.append("pause", "pause_claimed", **identity, status="claimed", state_digest=digest(state),
                              operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=4, proof=proof)
        step("pause_claimed_recorded", {"pause_owner_operation": owner, "producing_lease_epoch": claimed["lease_epoch"]})
        human_publications = []
        if request["input_kind"] == "human_response":
            human_publications = self._human_prestart(plan, state, opened, target)
        settlement = {"tag": "not_applicable"}
        external = operation["reservation"]["target_prestart_closure"]["external"]
        if request["input_kind"] == "external_result":
            reserved = external["reservation"]
            position = state["budget"]["budget_event_index"] + 1
            settlement = plan.append("budget", "resource_settled", budget_event_id=f"budget_event_{position:06d}", budget_event_index=position,
                policy_version=reserved["policy_version"], policy_digest=reserved["policy_digest"], payload={
                    "resource_operation_id": reserved["payload"]["resource_operation_id"], "actual": external["final"]["resource_actual"],
                    "tokens": {"state": "unknown", "value": None}, "cost": {"state": "unknown", "value": None},
                    "evidence_digest": external["value"]["terminal_evidence_digest"], "operation_id": owner,
                    "lease_epoch": operation["lease_epoch"], "phase_revision": 5})
        step("prestart_records_committed", {"reason_specific_target_closure": operation["reservation"]["target_prestart_closure"],
                                            "invalidation_closure": {"kind": "existing_committed_transition", "transition_id": target["inbound_transition_id"]},
                                            "grant_or_settlement_closure": settlement})
        plan.steps[-1]["publications"] = human_publications + plan.steps[-1]["publications"]
        consumed = plan.append("pause", "pause_consumed", **identity, status="consumed", state_digest=digest(state),
                               operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=6,
                               proof={**proof, "claimed": {"execution_head": digest(claimed)}})
        step("pause_consumed_recorded", {"pause_claim_head": digest(claimed), "single_use_authorization": request["input_digest"]})
        lifecycle = plan.append("run_lifecycle", "transitioned", from_status="paused", to_status="running", reason_code=request["input_kind"],
                                operation_id=owner, pause_id=opened["pause_id"], attempt_id=target["attempt_id"], budget_event_id=None)
        step("running_lifecycle_recorded", {"legal_run_lifecycle_edge": lifecycle, "exact_pre_head": digest(consumed)})
        checkpoint = plan.checkpoint("resumed")
        step("resume_checkpoint_committed", {"consumed_pause_head": digest(consumed), "running_lifecycle_head": digest(lifecycle)}, checkpoint=checkpoint)
        heads = {key: checkpoint["manifest"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}
        step("invocation_authorized", {"attempt_identity": {key: target[key] for key in ("run_id", "case_id", "attempt_id", "attempt_kind")},
                                      "exact_heads": heads, "lease_epoch": operation["lease_epoch"], "terminal_closure_revision": 0})
        if completion is not None:
            from .execution import parse_ledger
            plan.records = parse_ledger(completion["content"].encode()).values
            plan.previous = completion["content"]
            plan.index = loads(completion["index"])
            release = {"release_kind": "not_applicable", "not_applicable_reason": request["input_kind"] + "_has_no_external_operation"}
            if request["input_kind"] == "external_result":
                from .operations import ExternalControl
                release = ExternalControl(self.coordinator).consumption_proof(operation, external["value"], plan.records, plan.index,
                                                                             phase_revision=len(plan.steps) + 2)
            step("external_consumption_released", {"external_consumption_release_proof": release,
                "same_consumption_owner_current_epoch": {"operation_id": owner, "lease_epoch": operation["lease_epoch"]}})
            stable = completion
            if request["input_kind"] == "external_result":
                stable = plan.checkpoint("external_consumed")
            if followup is not None and followup["operation"]["status"] == "committed":
                stable = followup["snapshot"]
                plan.records = stable["records"]
                plan.previous = b"".join(canonical_bytes(r) + b"\n" for r in plan.records).decode()
                plan.index = stable["artifact_index"]
            step("stable_boundary_committed", {"committed_pause_or_close_or_running_checkpoint": stable["manifest"]},
                 **({"checkpoint": stable} if request["input_kind"] == "external_result" else {}))
            result = {"run_locator": request["run_locator"], "run_status": stable["projection"]["run_status"],
                      "domain_status": completion["projection"]["attempt_status"],
                      "pause_id": stable["projection"].get("active_pause", {}).get("pause_id") if stable["projection"].get("active_pause") else None,
                      "terminal_closure": "committed" if stable["projection"]["run_status"] == "halted" else "not_applicable",
                      **{key: stable["manifest"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}}
            step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": len(plan.steps) + 2})
        return {"run_locator": request["run_locator"], "steps": plan.steps, "opened": opened, "source_control_revision": source_revision,
                "source": {"records": records, "index": index, "state": state}, "checkpoint": checkpoint, "completion": completion, "followup": followup,
                "stable": stable if completion is not None else None,
                "original_policy": next(r["payload"]["policy"] for r in records if r["record_type"] == "budget" and r["event"] == "policy_initialized")}

    def _human_prestart(self, plan, state, opened, target):
        from datetime import datetime, timezone
        from hashlib import sha256
        from .coordinator import read_regular
        from .integrity import artifact_binding

        request = plan.operation["request"]
        locator = request["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        response_index = state["human_response_index"] + 1
        response_id = f"human_response_{response_index:06d}"
        relative = f"human_responses/{response_id}/payload.json"
        payload = canonical_bytes(request["input_snapshot"])
        previous_index = canonical_bytes(plan.index).decode()
        member = {"logical_name": "payload.json", "canonical_path": relative, "projection_path": None,
                  "sha256": sha256(payload).hexdigest(), "size_bytes": len(payload), "media_type": "application/json"}
        position = plan.index["revision"] + 1
        artifact = {"schema_version": "0.1", "event_id": f"artifact_event_{position:06d}", "event_index": position,
                    "event": "protected_snapshot_registered", **locator, "cycle_id": state["cycle_id"], "attempt_id": state["attempt_id"],
                    "transition_id": None, "human_request_id": state["active_human_request_id"], "human_response_id": response_id,
                    "slot": None, "artifact_id": response_id + ":payload", "reason_code": "human_response_submitted",
                    "created_at": datetime.fromtimestamp(plan.timestamp.wall_seconds, timezone.utc).isoformat(),
                    "protected_kind": "human_response", "members": [member], "dependencies": []}
        # A frozen prior-epoch artifact publication is immutable on restart.
        original = read_regular(root / "artifact_history.jsonl")
        require(not original or original.endswith(b"\n"), "Partial Human response artifact history")
        prefix_length = state["artifact_event_index"]
        source_lines = original.splitlines(keepends=True)
        source = b"".join(source_lines[:prefix_length])
        bound = artifact_binding(artifact, previous_artifact_head=plan.index["artifact_head"], execution_head=digest(plan.records[-1]))
        if len(source_lines) > prefix_length:
            existing = loads(source_lines[prefix_length][:-1])
            require({k: v for k, v in existing.items() if k != "created_at"} ==
                    {k: v for k, v in bound.value.items() if k != "created_at"}, "Human response artifact publication conflict")
            artifact = existing
        else:
            artifact = bound.value
        plan.index.update(revision=position, last_event_id=artifact["event_id"], artifact_head=digest(artifact))
        plan.append("human_response", "submitted", cycle_id=state["cycle_id"], human_request_id=state["active_human_request_id"],
                    human_response_id=response_id, response_index=response_index, payload_reference=str(root / relative),
                    payload_sha256=member["sha256"], submitted_payload_reference="inline:resume_run", payload_snapshot=request["input_snapshot"],
                    validator_attempt_id=None, consumer_attempt_id=None, authorized_target_attempt_id=None, decision=None,
                    authorized_route=None, authorized_transition_route=None, authorized_transition_target=None, status="submitted")
        refs = {"current_artifact_ids": {slot: pointer["artifact_id"] for slot, pointer in plan.index["current"].items() if pointer is not None}}
        plan.append("attempt", "scheduled", cycle_id=state["cycle_id"], cycle_index=state["cycle_index"],
                    attempt_id=target["attempt_id"], attempt_index=state["attempt_index"] + 1, parent_attempt_id=state["attempt_id"],
                    attempt_kind="human_gate", node_name="human_approval_gate", attempt_trigger="human_response",
                    inbound_transition_id=target["inbound_transition_id"], status="scheduled", input_references=refs,
                    output_references={"current_artifact_ids": {}}, error=None)
        plan.append("transition", "committed", transition_id=target["inbound_transition_id"], transition_index=state["transition_index"] + 1,
                    source="HUMAN_RESPONSE", source_node="HUMAN_RESPONSE", source_cycle_id=state["cycle_id"], source_attempt_id=None,
                    route="human_approval_gate", target_node="human_approval_gate", target_cycle_id=state["cycle_id"], target_attempt_id=target["attempt_id"],
                    target_attempt_kind="human_gate", human_request_id=state["active_human_request_id"], human_response_id=response_id,
                    trigger_reason="human_response", reason="identity_bound_human_response", fields={"pause_id": opened["pause_id"],
                        **next(({"stop_sequence_id": r["fields"]["stop_sequence_id"]} for r in plan.records
                                if r["record_type"] == "transition" and r["target_attempt_id"] == state["attempt_id"] and
                                r["fields"].get("stop_sequence_id") is not None), {})},
                    evidence_references={}, applied_state_update_keys=[], applied_state_updates_sha256=digest({}),
                    status="committed", committed_at=asdict(plan.timestamp))
        plan.index["execution_head"] = digest(plan.records[-1])
        return [{"path": relative, "content": payload.decode(), "previous": None, "replacement": False},
                {"path": "artifact_history.jsonl", "content": (source + canonical_bytes(artifact) + b"\n").decode(),
                 "previous": source.decode(), "replacement": False},
                {"path": "artifact_index.json", "content": canonical_bytes(plan.index).decode(),
                 "previous": previous_index, "replacement": True}]

    def _continue_recovery(self, operation):
        from .capabilities import InvocationLeases
        from .operations import continue_publication_plan

        coordinator = self.coordinator
        failure = ConsumptionFailure(self)
        if failure.intent(operation) is not None:
            if operation["status"] != "in_progress":
                return operation
            if coordinator._time().monotonic_seconds >= operation["lease_expires"]:
                operation = coordinator.acquire(operation["operation_id"], self.worker_id, lease_seconds=self.lease_seconds)
            elif operation["worker_owner_id"] != self.worker_id:
                return operation
            return failure.continue_failure(operation)
        operation = continue_publication_plan(coordinator, operation, self.worker_id, self.lease_seconds,
                                              self._continue_phase, rebuild=self._rebuild, stop_after=("invocation_authorized", "external_consumption_released"))
        if operation["status"] != "in_progress" or operation["worker_owner_id"] != self.worker_id:
            return operation
        if operation["phase"] == "invocation_authorized":
            leases = InvocationLeases(coordinator, decision_adapter=self.decision_adapter, external_adapter=self.external_adapter,
                                      preparation_adapter=self.preparation_adapter)
            capability = "capability_" + operation["operation_id"]
            _, value = leases.get(capability)
            if value["state"] in ("unclaimed", "leased_not_started"):
                if value["worker_id"] != self.worker_id or value["expires_at"] is None or coordinator._time().monotonic_seconds >= value["expires_at"]:
                    if value["expires_at"] is not None and coordinator._time().monotonic_seconds < value["expires_at"]:
                        return operation
                    value = leases.acquire(capability, self.worker_id, expected_epoch=value["invocation_epoch"], lease_seconds=self.lease_seconds)
                try:
                    leases.invoke(capability, self.worker_id, value["invocation_epoch"], self.target_adapter)
                except Exception as error:
                    _, durable = leases.get(capability)
                    if durable["state"] != "finished":
                        if operation["request"]["input_kind"] == "human_response" and durable.get("completion_intent") is not None:
                            leases.verify_human_completion_prefix(capability, operation["operation_id"], self.worker_id, operation["lease_epoch"])
                            return operation
                        if operation["request"]["input_kind"] == "external_result":
                            return failure.start(operation, error)
                        with coordinator.transaction() as db:
                            return coordinator.interrupt(db, operation, "recovery_required", {
                                "kind": "uncertain_resume_consumer", "capability_id": capability,
                                "authorization_digest": durable["authorization_digest"], "cause_type": type(error).__name__})
            elif value["state"] != "finished":
                if value.get("completion_intent") is not None:
                    with coordinator.failure_context(operation):
                        leases.recover_completion(capability, operation["operation_id"], self.worker_id, operation["lease_epoch"])
                else:
                    if operation["request"]["input_kind"] == "external_result":
                        return failure.start(operation, ControlIntegrityError("Uncertain consumer started intent cannot be redispatched"))
                    with coordinator.transaction() as db:
                        return coordinator.interrupt(db, operation, "recovery_required", {"kind": "uncertain_resume_consumer", "capability_id": capability,
                                                                                          "authorization_digest": value["authorization_digest"]})
        operation = continue_publication_plan(coordinator, operation, self.worker_id, self.lease_seconds,
                                              self._continue_phase, rebuild=self._rebuild, stop_after=("external_consumption_released",))
        if operation["status"] != "in_progress" or operation["worker_owner_id"] != self.worker_id:
            return operation
        followup = self._invalid_human_followup(operation, execute=True)
        if followup is not None and followup["operation"]["status"] != "committed":
            child = followup["operation"]
            if child["status"] in ("failed", "recovery_required"):
                with coordinator.transaction() as db:
                    return coordinator.interrupt(db, operation, child["status"], {
                        "kind": "human_followup_unavailable", "followup_operation_id": child["operation_id"],
                        "followup_status": child["status"], "followup_error": child["error"]})
            return operation
        return continue_publication_plan(coordinator, operation, self.worker_id, self.lease_seconds, self._continue_phase, rebuild=self._rebuild)

    def _invalid_human_followup(self, operation, *, execute=False):
        from .capabilities import InvocationLeases
        from .operations import CloseRunRequest, TerminalOperations
        from .interfaces import ActorContext

        if operation["request"]["input_kind"] != "human_response":
            return None
        row = self.coordinator.connection.execute("SELECT 1 FROM invocation_capabilities WHERE capability_id=?",
                                                  ("capability_" + operation["operation_id"],)).fetchone()
        if row is None:
            return None
        completion = InvocationLeases(self.coordinator).get("capability_" + operation["operation_id"])[1].get("completion_intent")
        if completion is None or completion.get("invalid_response_decision") is None:
            return None
        decision = completion["invalid_response_decision"]["record"]
        locator = operation["request"]["run_locator"]
        key = digest({"source_resume_operation": operation["operation_id"], "decision_head": digest(decision)})
        if decision["payload"]["decision"] == "allow":
            child = self.coordinator.lookup_key("internal_pause", key)
            if execute and (child is None or child["status"] == "in_progress"):
                source = self.coordinator.snapshot(operation["operation_id"])
                state = completion["projection"]
                child = self.publish(PublishPauseRequest(locator, "human_input", state["attempt_id"], None,
                    {"kind": "human_response", "human_request_id": state["active_human_request_id"]},
                    source["opened"]["authorization_scope"], key))
        else:
            terminals = TerminalOperations(self.coordinator, self.worker_id, self.lease_seconds)
            closure = terminals.closure(locator)
            child = self.coordinator.get(closure["terminal_closure_owner_operation_id"]) if closure is not None else None
            if execute and (child is None or child["status"] == "in_progress"):
                child = terminals.close(CloseRunRequest(locator, digest(decision)), ActorContext("trusted_control", "system", ("control.internal",)))
        if child is None:
            return None
        if child["status"] in ("failed", "recovery_required"):
            return {"operation": child, "snapshot": None}
        from .coordinator import MaterializationSnapshotError, read_regular
        try:
            snapshot = self.coordinator.snapshot(child["operation_id"])
        except MaterializationSnapshotError:
            if child["status"] != "committed":
                raise
            from .checkpoints import verify_checkpoint
            from .execution import parse_ledger
            from .integrity import validate_run_root
            control = loads(self.coordinator.connection.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()[0])
            root = self.coordinator.root / locator["case_id"] / locator["run_id"]
            require(all(control["manifest"][key] == child["result"][key] for key in
                        ("execution_head", "artifact_head", "checkpoint_head")), "Followup committed heads changed")
            verify_checkpoint(root, control["manifest"])
            validate_run_root(root, manifest=control["manifest"], projection=control["projection"])
            stable = {**control, "records": parse_ledger(read_regular(root / "execution_history.jsonl")).values,
                      "artifact_index": loads(read_regular(root / "artifact_index.json"))}
            return {"operation": child, "snapshot": stable}
        return {"operation": child, "snapshot": snapshot["public"] if child["operation_type"] == "publish_pause" else snapshot}

    def _continue_phase(self, db, operation, step, snapshot, *, before):
        from .capabilities import authorize_resume_capability
        from .checkpoints import verify_checkpoint
        from .coordinator import read_regular
        from .integrity import validate_run_root

        locator, opened = snapshot["run_locator"], snapshot["opened"]
        key = digest(locator)
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, opened["pause_id"])).fetchone()
        require(row is not None, "Missing Pause publication owner")
        owner = loads(row[0])
        if before:
            if step["target"] in ("resume_disposition_committed", "pause_ownership_reserved") and owner["owner"] is not None:
                raise PauseOwnershipConflict("A competing operation already claimed the Pause")
            terminal = db.execute("SELECT value FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone()
            followup = snapshot.get("followup")
            own_tail = (followup is not None and step["target"] in ("stable_boundary_committed", "result_committed") and
                        terminal is not None and loads(terminal[0])["terminal_closure_owner_operation_id"] == followup["operation"]["operation_id"])
            require(terminal is None or own_tail, "Resume is fenced by terminal owner")
            require(read_regular(root / "execution_history.jsonl").decode() in (step["expected_previous_ledger"], step["expected_ledger"]), "Resume continuation prefix conflict")
            require(read_regular(root / "budget_policy.json") == canonical_bytes(snapshot["original_policy"]), "Resume policy changed")
            if operation["request"]["input_kind"] == "external_result":
                from .operations import ExternalControl
                frozen = operation["reservation"]["target_prestart_closure"]["external"]["value"]
                value, _ = ExternalControl(self.coordinator).final_evidence(db, frozen["producer_operation_id"])
                require(value["terminal_evidence_digest"] == frozen["terminal_evidence_digest"] and value["resolution_owner"] == "normal" and
                        value["active_binding_generation"] == frozen["active_binding_generation"], "External result binding changed")
                if step["target"] not in ("stable_boundary_committed", "result_committed"):
                    require(value["active_binding_status"] == "active" and value["consumption_release"] is None, "External consumption already released")
            if step["target"] in ("resume_disposition_committed", "pause_ownership_reserved"):
                self._check_deadline(opened)
                require(owner["owner"] is None and owner["status"] == "opened" and owner["opened_head"] == digest(opened), "Pause already owned")
            else:
                require(owner["owner"] == operation["operation_id"], "Resume claim owner changed")
            if step["target"] == "pause_ownership_reserved":
                require(db.execute("SELECT revision FROM run_controls WHERE run_key=?", (key,)).fetchone()[0] == snapshot["source_control_revision"], "Resume source revision changed")
                owner["owner"] = operation["operation_id"]
                db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?", (canonical_bytes(owner), key, opened["pause_id"]))
                db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (key,))
            if step["target"] == "prestart_records_committed" and operation["request"]["input_kind"] == "human_response":
                from .coordinator import exclusive_directory
                exclusive_directory(root / "human_responses")
                response_index = snapshot["source"]["state"]["human_response_index"] + 1
                exclusive_directory(root / "human_responses" / f"human_response_{response_index:06d}")
            return
        if step["target"] in ("pause_claimed_recorded", "pause_consumed_recorded"):
            owner["status"] = "claimed" if step["target"] == "pause_claimed_recorded" else "consumed"
            db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?", (canonical_bytes(owner), key, opened["pause_id"]))
        elif step["target"] == "resume_checkpoint_committed":
            checkpoint = snapshot["checkpoint"]
            verify_checkpoint(root, checkpoint["manifest"])
            validate_run_root(root, manifest=checkpoint["manifest"], projection=checkpoint["projection"])
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes({"locator": locator, "manifest": checkpoint["manifest"], "projection": checkpoint["projection"]}), key))
        elif step["target"] == "invocation_authorized":
            checkpoint = snapshot["checkpoint"]
            return authorize_resume_capability(self.coordinator, db, operation, root, checkpoint["manifest"], checkpoint["projection"])
        elif step["target"] in ("external_consumption_released", "stable_boundary_committed", "result_committed"):
            require(snapshot["completion"] is not None and snapshot["completion"]["published"], "Consumer completion is not durable")
            stable = snapshot["completion"]
            if operation["request"]["input_kind"] == "external_result":
                from .operations import ExternalControl
                if step["target"] == "external_consumption_released":
                    ExternalControl(self.coordinator).release_consumption(db, operation, step["evidence"]["external_consumption_release_proof"])
                    validate_run_root(root, manifest=stable["manifest"], projection=stable["projection"])
                    return
                stable = snapshot["stable"]
                if step["target"] == "stable_boundary_committed":
                    db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes({
                        "locator": locator, "manifest": stable["manifest"], "projection": stable["projection"]}), key))
            if step["target"] != "external_consumption_released" and stable.get("invalid_response_decision") is not None:
                require(snapshot["followup"] is not None and snapshot["followup"]["operation"]["status"] == "committed", "Invalid response has no durable next boundary")
                stable = snapshot["followup"]["snapshot"]
            verify_checkpoint(root, stable["manifest"])
            validate_run_root(root, manifest=stable["manifest"], projection=stable["projection"])

    def _check_deadline(self, opened):
        now = self.coordinator._time()
        before = opened["proof"]["opened_at"]
        require(now.source == before["source"] and now.wall_seconds >= before["wall_seconds"] and
                now.monotonic_seconds >= before["monotonic_seconds"], "Pause clock regression")
        if now.wall_seconds >= opened["proof"]["deadline"]:
            raise PauseExpired("Pause deadline elapsed")

    def _abandon_snapshot(self, operation, records, index, state, source_revision):
        from .operations import PublicationPlan
        from .records import FIELDS as RECORD_FIELDS

        plan = PublicationPlan(operation, records, index)
        opened = records[-1]
        request = operation["request"]
        owner = operation["operation_id"]
        locator = request["run_locator"]
        proof = {"opened": {"execution_head": digest(opened)}, "input_snapshot": request["input_snapshot"],
                 "input_digest": request["input_digest"], "actor": request["actor"],
                 "request_digest": operation["request_digest"], "idempotency_key": operation["idempotency_key"]}
        identity = {key: opened[key] for key in IDENTITY_FIELDS}
        plan.step("resume_disposition_committed", {"frozen_resume_variant": "abandon_and_halt", "exact_opened_pause": opened,
                                                   "reason_target_scope_preflight_proof": proof})
        plan.step("pause_and_terminal_ownership_reserved", {"exact_pause_cas": {"pause_id": opened["pause_id"], "owner": owner},
                                                            "empty_run_terminal_owner_cas": {"run_key": digest(locator), "owner": owner},
                                                            "terminal_resolution_contracts": operation["reservation"]["terminal_disposition_contract_digest"]})
        claimed = plan.append("pause", "pause_claimed", **identity, status="claimed", state_digest=digest(state),
                              operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=4, proof=proof)
        plan.step("pause_claimed_recorded", {"pause_owner_operation": owner, "producing_lease_epoch": claimed["lease_epoch"]})
        consumed = plan.append("pause", "pause_consumed", **identity, status="consumed", state_digest=digest(state),
                               operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=5,
                               proof={**proof, "claimed": {"execution_head": digest(claimed)}})
        plan.step("pause_consumed_recorded", {"pause_claim_head": digest(claimed), "single_use_authorization": request["input_digest"]})
        target = operation["reservation"]["precomputed_abandon_evidence"]["target"]
        disposition = {"tag": "not_applicable"}
        if target is not None:
            require(target["status"] == "scheduled", "Abandon target is not scheduled")
            fields = {key: target[key] for key in RECORD_FIELDS["attempt"]}
            fields["status"] = "abandoned"
            disposition = plan.append("attempt", "abandoned", **fields)
        plan.step("target_disposition_committed", {"target_abandoned_or_not_applicable": disposition})
        plan.step("resource_disposition_committed", {"resource_settlement_or_not_applicable": {"tag": "not_applicable"}})
        heads = {"execution_head": digest(plan.records[-1]), "artifact_head": index["artifact_head"], "checkpoint_head": state["checkpoint_head"]}
        plan.step("terminal_eligibility_verified", {"final_terminal_evidence": {"pause_consumed": digest(consumed), "input_digest": request["input_digest"]},
                                                   "exact_authority_heads": heads, "single_assignment_resolution": "halted"})
        terminal = plan.append("run_lifecycle", "transitioned", from_status="paused", to_status="halted", reason_code="abandon_and_halt",
                               operation_id=owner, pause_id=opened["pause_id"], attempt_id=None, budget_event_id=None)
        plan.step("terminal_lifecycle_recorded", {"terminal_owner": owner, "terminal_closure_revision": 1,
                                                  "resolved_terminal_disposition": "halted",
                                                  "terminal_disposition_contract_digest": operation["reservation"]["terminal_disposition_contract_digest"],
                                                  "legal_terminal_lifecycle_edge": terminal})
        checkpoint = plan.checkpoint("abandoned")
        plan.step("terminal_checkpoint_committed", {"terminal_lifecycle_resulting_head": digest(terminal), "empty_active_pause_projection": {"pause_id": None}},
                  checkpoint=checkpoint)
        result = {"run_locator": locator, "run_status": "halted", "domain_status": None, "pause_id": None, "terminal_closure": "committed",
                  **{key: checkpoint["manifest"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}}
        plan.step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": len(plan.steps) + 2})
        return {"run_locator": locator, "steps": plan.steps, "opened": opened, "source_control_revision": source_revision,
                "source": {"records": records, "index": index, "state": state},
                "checkpoint": checkpoint, "original_policy": next(r["payload"]["policy"] for r in records if r["record_type"] == "budget" and r["event"] == "policy_initialized")}

    def _rebuild(self, operation, snapshot):
        source = snapshot["source"]
        args = (operation, source["records"], source["index"], source["state"])
        if operation["operation_type"] == "publish_pause":
            return self._publication_snapshot(*args)
        if operation["operation_type"] == "cancel_pause":
            return self._cancel_snapshot(*args, snapshot["source_control_revision"], snapshot["external_absence"])
        if operation["operation_variant"] == "continue_execution":
            from .capabilities import InvocationLeases
            if operation["phase"] in ("operation_reserved", "resume_disposition_committed"):
                owner = self.coordinator.connection.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?",
                    (digest(operation["request"]["run_locator"]), operation["request"]["pause_id"])).fetchone()
                if owner is not None and loads(owner[0])["owner"] not in (None, operation["operation_id"]):
                    raise PauseOwnershipConflict("A competing operation already claimed the Pause")
            row = self.coordinator.connection.execute("SELECT 1 FROM invocation_capabilities WHERE capability_id=?", ("capability_" + operation["operation_id"],)).fetchone()
            completion = InvocationLeases(self.coordinator).get("capability_" + operation["operation_id"])[1].get("completion_intent") if row else None
            return self._continue_snapshot(*args, snapshot["source_control_revision"], completion=completion,
                                           followup=self._invalid_human_followup(operation))
        return self._abandon_snapshot(*args, snapshot["source_control_revision"])

    def _resume_phase(self, db, operation, step, snapshot, *, before):
        from .checkpoints import verify_checkpoint
        from .coordinator import read_regular
        from .integrity import validate_run_root
        from .operations import TerminalOperations

        coordinator = self.coordinator
        locator, opened = snapshot["run_locator"], snapshot["opened"]
        key, pause_id = digest(locator), opened["pause_id"]
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, pause_id)).fetchone()
        require(row is not None, "Missing Pause publication ownership")
        pause_owner = loads(row[0])
        terminal = TerminalOperations(coordinator, self.worker_id, self.lease_seconds).closure(locator, db=db)
        if before:
            require(read_regular(root / "execution_history.jsonl").decode() in (step["expected_previous_ledger"], step["expected_ledger"]),
                    "Resume publication prefix conflict")
            require(read_regular(root / "budget_policy.json") == canonical_bytes(snapshot["original_policy"]), "Resume policy changed")
            if step["target"] in ("resume_disposition_committed", "pause_and_terminal_ownership_reserved", "cancel_arbitrated"):
                if operation["operation_type"] == "resume_run":
                    self._check_deadline(opened)
                else:
                    require(self._external_absence(db, locator) == snapshot["external_absence"], "External absence changed")
                require(pause_owner["owner"] is None and terminal is None and pause_owner["status"] == "opened" and
                        pause_owner["opened_head"] == digest(opened), "Pause/Run ownership conflict")
            else:
                require(pause_owner["owner"] == operation["operation_id"] and terminal is not None and
                        terminal["terminal_closure_owner_operation_id"] == operation["operation_id"] and terminal["terminal_closure"] == "pending",
                        "Resume owner fence failed")
            if step["target"] in ("pause_and_terminal_ownership_reserved", "cancel_arbitrated"):
                require(db.execute("SELECT revision FROM run_controls WHERE run_key=?", (key,)).fetchone()[0] == snapshot["source_control_revision"],
                        "Resume source control revision changed")
                pause_owner["owner"] = operation["operation_id"]
                db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?",
                           (canonical_bytes(pause_owner), key, pause_id))
                terminal = {"terminal_closure_revision": 1, "terminal_closure_owner_operation_id": operation["operation_id"],
                            "terminal_trigger_reference": operation["request"], "terminal_trigger_digest": operation["request_digest"],
                            "terminal_request_digest": operation["request_digest"], "terminal_disposition_contract": {"run_status": "halted"},
                            "terminal_preclose_contract": operation["reservation"].get("precomputed_abandon_evidence", snapshot.get("external_absence")),
                            "resolved_terminal_disposition": None, "resolved_preclose_heads": None,
                            "terminal_closure": "pending", "run_status": None}
                db.execute("INSERT INTO run_terminal_closure VALUES (?,?,?)", (key, 1, canonical_bytes(terminal)))
                db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (key,))
            return
        if step["target"] in ("pause_claimed_recorded", "pause_consumed_recorded", "pause_cancelled_recorded"):
            pause_owner["status"] = {"pause_claimed_recorded": "claimed", "pause_consumed_recorded": "consumed", "pause_cancelled_recorded": "cancelled"}[step["target"]]
            db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?",
                       (canonical_bytes(pause_owner), key, pause_id))
        elif step["target"] == "terminal_eligibility_verified":
            require(terminal["resolved_terminal_disposition"] is None, "Terminal disposition already resolved")
            terminal.update(resolved_terminal_disposition="halted", resolved_preclose_heads=step["evidence"]["exact_authority_heads"])
            db.execute("UPDATE run_terminal_closure SET value=? WHERE run_key=?", (canonical_bytes(terminal), key))
        elif step["target"] == "terminal_checkpoint_committed":
            checkpoint = snapshot["checkpoint"]
            verify_checkpoint(root, checkpoint["manifest"])
            validate_run_root(root, manifest=checkpoint["manifest"], projection=checkpoint["projection"])
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?",
                       (canonical_bytes({"locator": locator, "projection": checkpoint["projection"], "manifest": checkpoint["manifest"]}), key))
        elif step["target"] == "result_committed":
            terminal.update(terminal_closure="committed", run_status="halted")
            db.execute("UPDATE run_terminal_closure SET value=? WHERE run_key=?", (canonical_bytes(terminal), key))

    def publish(self, request):
        from .coordinator import component
        from .operations import continue_publication_plan

        require(type(request) is PublishPauseRequest, "Expected internal typed Pause proposal")
        closed(request.run_locator, ("case_id", "run_id"))
        for name in request.run_locator.values():
            component(name)
        require(request.reason in REASONS, "Unknown Pause reason")
        text(request.idempotency_key)
        coordinator = self.coordinator
        proposal = asdict(request)
        proposal.pop("idempotency_key")
        old = coordinator.lookup_key("internal_pause", request.idempotency_key)
        if old is not None:
            require(all(old["request"][key] == value for key, value in proposal.items()), "Same-key request conflict")
            operation = old
        else:
            fingerprint = runtime_fingerprint()
            operation = self._reserve_publication(request, proposal, fingerprint)
        try:
            return continue_publication_plan(coordinator, operation, self.worker_id, self.lease_seconds, self._publish_phase, rebuild=self._rebuild)
        except (ControlIntegrityError, OSError) as error:
            return self._fail(operation, error)

    def _reserve_publication(self, request, proposal, fingerprint):
        from .checkpoints import verify_checkpoint
        from .coordinator import read_regular
        from .execution import parse_ledger
        from .integrity import validate_control_root

        coordinator = self.coordinator
        key = digest(request.run_locator)
        root = coordinator.root / request.run_locator["case_id"] / request.run_locator["run_id"]
        with coordinator.transaction() as db:
            old = coordinator.lookup_key("internal_pause", request.idempotency_key, db=db)
            if old is not None:
                require(all(old["request"][key] == value for key, value in proposal.items()), "Same-key request conflict")
                return old
            row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (key,)).fetchone()
            require(row is not None, "Unknown Run")
            control = loads(row["value"])
            require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone() is None, "Run has terminal ownership")
            require(control["projection"] is not None, "Run has no stable checkpoint")
            verify_checkpoint(root, control["manifest"])
            state = validate_control_root(coordinator, db, request.run_locator, control).value
            require(state["run_status"] == "running" and state.get("pending_pause") is None and state.get("active_pause") is None,
                    "Run is not at a publishable Pause boundary")
            records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
            attempts = {r["attempt_id"]: r for r in records if r["record_type"] == "attempt"}
            requester = attempts.get(request.requesting_attempt_id)
            require(requester is not None and (requester["event"] == "finished" or
                    request.reason == "external_result" and requester["status"] == "scheduled" and requester["attempt_kind"] == "code_agent"),
                    "Requesting Attempt lacks a pausable outcome")
            if request.reason == "recovery_decision":
                require(requester["status"] == "failed" and requester["error"] is not None, "Recovery Pause has no canonical failure identity")
            elif request.reason == "human_input":
                require(requester["attempt_kind"] == "human_gate" and state["human_request_status"] == "open" and
                        request.target_attempt_id is None, "Human Pause needs a finished Gate and open request")
                require(request.input_contract == {"kind": "human_response", "human_request_id": state["active_human_request_id"]},
                        "Human Pause input contract is not the exact open request")
            if request.target_attempt_id is not None:
                target = attempts.get(request.target_attempt_id)
                require(request.reason in ("recovery_decision", "external_result") and target is not None and target["status"] == "scheduled",
                        "Pause target is not an existing scheduled target")
            external_dependency = None
            if request.reason == "external_result":
                from .operations import ExternalControl
                require(request.target_attempt_id == requester["attempt_id"] and target["attempt_kind"] == "code_agent",
                        "External pause must bind its original scheduled Research Worker attempt")
                external_dependency = ExternalControl(coordinator).preparation(db, request.run_locator, target, records)
                require(request.input_contract == {"kind": "external_result", "producer_operation_id": external_dependency["producer_operation_id"]},
                        "External Pause input contract mismatch")
            canonical = {**proposal, "source_heads": {field: state[field] for field in ("execution_head", "artifact_head", "checkpoint_head")},
                         "runtime_fingerprint": fingerprint, "source_control_revision": row["revision"],
                         "requesting_outcome": {"attempt_id": requester["attempt_id"], "execution_head": digest(requester), "error": requester["error"]}}
            if external_dependency is not None:
                canonical["external_dependency"] = external_dependency

            def reserve(operation_id, stamp):
                return {"source_execution_artifact_checkpoint_heads": canonical["source_heads"], "typed_pause_reason": request.reason,
                        "requesting_and_target_identity": {"requesting_attempt_id": request.requesting_attempt_id,
                                                          "target_attempt_id": request.target_attempt_id},
                        "deterministic_pause_identity_inputs": {"run_locator": request.run_locator,
                                                               "pause_index": state.get("pause_index", 0) + 1,
                                                               "source_execution_head": state["execution_head"]}}

            operation = coordinator.reserve_in_transaction(
                db, "publish_pause", "not_applicable", "internal_pause", request.idempotency_key, canonical,
                self.worker_id, reserve, lease_seconds=self.lease_seconds,
                build_snapshot=lambda op: self._publication_snapshot(op, records, loads(read_regular(root / "artifact_index.json")), state))
        return operation

    def _publication_snapshot(self, operation, records, index, state):
        from .operations import checkpoint_snapshot, retain_materialized_record
        from .protocol import operation_variant
        from .records import build_record

        original = {"records": records, "index": index, "state": state}
        request = operation["request"]
        records = list(records)
        locator = request["run_locator"]
        stamp = Timestamp(**operation.get("_materialization_time", operation["created_at"]))
        pause_index = state.get("pause_index", 0) + 1
        identity = {"pause_id": f"pause_{pause_index:06d}", "pause_index": pause_index, "cycle_id": state["cycle_id"],
                    "reason": request["reason"], "requesting_attempt_id": request["requesting_attempt_id"],
                    "target_attempt_id": request["target_attempt_id"], "input_contract": request["input_contract"],
                    "authorization_scope": request["authorization_scope"], "runtime_fingerprint": request["runtime_fingerprint"]}
        steps = []
        source = "operation_reserved"
        prior_index = index
        previous = b"".join(canonical_bytes(row) + b"\n" for row in records).decode()

        def append(kind, event, **fields):
            candidate = build_record(kind, event, **locator, event_index=len(records) + 1,
                                     previous_execution_head=digest(records[-1]), artifact_head=index["artifact_head"],
                                     artifact_event_index=index["revision"], timestamp=stamp, **fields).value
            records.append(retain_materialized_record(operation, candidate))

        def step(target, evidence, checkpoint=None):
            nonlocal source, previous, prior_index
            publications = []
            content = b"".join(canonical_bytes(row) + b"\n" for row in records).decode()
            if content != previous:
                publications.append({"path": "execution_history.jsonl", "previous": previous, "content": content, "replacement": False})
            if checkpoint is not None:
                publications.extend([
                    {"path": "artifact_index.json", "previous": canonical_bytes(prior_index).decode(),
                     "content": canonical_bytes(checkpoint["artifact_index"]).decode(), "replacement": True},
                    {"path": "checkpoints/" + checkpoint["manifest"]["checkpoint_id"] + ".json", "previous": None,
                     "content": canonical_bytes(checkpoint["manifest"]).decode(), "replacement": False}])
                prior_index = checkpoint["artifact_index"]
            steps.append({"source": source, "target": target, "evidence": evidence, "branch": {}, "publications": publications,
                          "checkpoint": checkpoint, "expected_previous_ledger": previous, "expected_ledger": content})
            source, previous = target, content

        preparation = {"source_heads": request["source_heads"], "dependency": request.get("external_dependency", {"tag": "not_applicable", "reason": request["reason"]}),
                       "allowed_target_action": {"kind": "external_result" if request["reason"] == "external_result" else "human_gate" if request["reason"] == "human_input" else
                                                  "continue_existing_target" if request["target_attempt_id"] else "abandon_and_halt",
                                                 "requesting_outcome": request["requesting_outcome"]}}
        append("pause", "pause_prepared", **identity, status="prepared", state_digest=digest(state),
               operation_id=operation["operation_id"], lease_epoch=operation["lease_epoch"], phase_revision=2, proof=preparation)
        prepared = records[-1]
        step("pause_prepared_recorded", {"deterministic_pause_identity": identity["pause_id"], "source_heads": request["source_heads"],
                                         "typed_pause_reason": request["reason"]})
        step("pause_dependencies_bound", {"pause_prepared_digest": digest(prepared), "reason_specific_dependency_binding": preparation["dependency"]})
        pending = checkpoint_snapshot(list(records), index, operation, "prepared", stamp)
        step("prepared_checkpoint_committed", {"prepared_pause_projection": pending["projection"]["pending_pause"],
                                                "prepared_execution_head": digest(prepared)}, pending)
        decision = next(row for row in reversed(records) if row["record_type"] == "budget" and row["event"] == "decision_recorded")
        require(decision["payload"]["decision"] == "allow", "Pause lacks an applicable admission")
        append("run_lifecycle", "transitioned", from_status="running", to_status="paused", reason_code=request["reason"],
               operation_id=operation["operation_id"], attempt_id=request["requesting_attempt_id"], pause_id=identity["pause_id"],
               budget_event_id=decision["budget_event_id"])
        paused = records[-1]
        step("paused_lifecycle_recorded", {"running_to_paused_edge": paused, "prepared_checkpoint_digest": pending["manifest"]["checkpoint_digest"]})
        selected = next(row["payload"]["policy"] for row in records if row["record_type"] == "budget" and row["event"] == "policy_initialized")
        materialized = operation.get("_materialized_records", ())
        if len(materialized) > len(records):
            stamp = Timestamp(**materialized[len(records)]["created_at"])
        active_time = None
        initial = None
        if request["reason"] == "external_result":
            producer = request["external_dependency"]["producer_operation_id"]
            setup = [row for row in original["records"] if row["record_type"] == "budget" and
                     row["event"] == "active_interval_reserved" and row["payload"]["stage"] == "host_setup" and
                     row["payload"]["producer_operation_id"] == producer]
            require(len(setup) <= 1, "External Pause has duplicate setup intervals")
            initial = setup[0]["payload"] if setup else None
        if initial is not None:
            actual = (stamp.monotonic_seconds - initial["start_at"]["monotonic_seconds"]
                      if getattr(self.coordinator.clock, "epoch_id", None) == initial["clock_epoch_id"] and
                      stamp.source == initial["start_at"]["source"] and
                      stamp.wall_seconds >= initial["start_at"]["wall_seconds"] and
                      stamp.monotonic_seconds >= initial["start_at"]["monotonic_seconds"] else None)
            require(actual is None or actual <= initial["maximum_seconds"],
                    f"Setup active window exceeded: observed={actual}, maximum={initial['maximum_seconds']}")
            evidence = {"producer_operation_id": producer, "pause_id": identity["pause_id"],
                        "paused_lifecycle_head": digest(paused)}
            payload = {key: initial[key] for key in ("schema_version", "interval_id", "stage", "attempt_id",
                                                     "producer_operation_id", "owner_operation_id", "clock_epoch_id")}
            payload.update(settlement_operation_id=operation["operation_id"], lease_epoch=operation["lease_epoch"],
                           phase_revision=6, end_at=asdict(stamp) if actual is not None else None,
                           actual_seconds=actual, disposition="actual" if actual is not None else "conservative_maximum",
                           evidence_digest=digest(evidence))
            policy = next(row["payload"]["policy"] for row in records if row["record_type"] == "budget" and row["event"] == "policy_initialized")
            ordinal = 1 + sum(row["record_type"] == "budget" for row in records)
            append("budget", "active_interval_settled", budget_event_id=f"budget_event_{ordinal:06d}",
                   budget_event_index=ordinal, policy_version="0.1", policy_digest=policy["policy_digest"], payload=payload)
            active_time = {"interval_id": initial["interval_id"], "settlement_execution_head": digest(records[-1])}
        proof = {"prepared": {"execution_head": digest(prepared)}, "prepared_checkpoint": pending["manifest"],
                 "paused_lifecycle": {"execution_head": digest(paused)}, "opened_at": asdict(stamp),
                 "deadline": stamp.wall_seconds + selected["pause_deadline_seconds"]}
        if active_time is not None:
            proof["active_time"] = active_time
        append("pause", "pause_opened", **identity, status="opened", state_digest=pending["manifest"]["state_digest"],
               operation_id=operation["operation_id"], lease_epoch=operation["lease_epoch"], phase_revision=6, proof=proof)
        opened = records[-1]
        step("pause_opened_recorded", {"prepared_head": digest(prepared), "prepared_checkpoint_digest": pending["manifest"]["checkpoint_digest"],
                                       "paused_lifecycle_head": digest(paused)})
        public = checkpoint_snapshot(list(records), index, operation, "paused", stamp)
        step("public_paused_checkpoint_committed", {"pause_opened_resulting_head": digest(opened),
                                                     "active_pause_projection": public["projection"]["active_pause"]}, public)
        result = {"run_locator": locator, "run_status": "paused", "domain_status": None, "terminal_closure": "not_applicable",
                  "pause_id": identity["pause_id"], **{key: public["manifest"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}}
        step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": len(steps) + 2})
        require([item["target"] for item in steps] == list(operation_variant("publish_pause", "not_applicable")["phases"])[1:],
                "Pause publication plan disagrees with generated phases")
        return {"run_locator": locator, "steps": steps, "pause": identity, "prepared": prepared, "opened": opened, "public": public, "source": original}

    def _publish_phase(self, db, operation, step, snapshot, *, before):
        from .checkpoints import verify_checkpoint
        from .coordinator import read_regular
        from .integrity import validate_run_root

        coordinator = self.coordinator
        locator = snapshot["run_locator"]
        key = digest(locator)
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        pause_id = snapshot["pause"]["pause_id"]
        owner = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, pause_id)).fetchone()
        if before:
            require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone() is None, "Run is closing")
            require(read_regular(root / "execution_history.jsonl").decode() in (step["expected_previous_ledger"], step["expected_ledger"]),
                    "Pause publication prefix conflict")
            if step["target"] == "pause_prepared_recorded":
                require(owner is None, "Competing Pause publisher")
                revision = db.execute("SELECT revision FROM run_controls WHERE run_key=?", (key,)).fetchone()[0]
                require(revision == operation["request"]["source_control_revision"], "Pause source revision changed")
                db.execute("INSERT INTO pause_ownership VALUES (?,?,?,?)", (key, pause_id, 1, canonical_bytes({
                    "publication_owner": operation["operation_id"], "owner": None, "status": "prepared", "opened_head": None})))
            else:
                require(owner is not None and loads(owner[0])["publication_owner"] == operation["operation_id"] and
                        loads(owner[0])["owner"] is None and loads(owner[0])["status"] in ("prepared", "opened"),
                        "Wrong or revoked Pause publisher")
            if step["target"] == "pause_dependencies_bound" and snapshot["pause"]["reason"] == "external_result":
                from .operations import ExternalControl
                ExternalControl(coordinator).bind_pause(db, operation["request"]["external_dependency"], snapshot["prepared"])
            return
        if step["target"] == "pause_opened_recorded":
            value = loads(owner[0])
            value.update(status="opened", opened_head=digest(snapshot["opened"]))
            db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?",
                       (canonical_bytes(value), key, pause_id))
        if step["target"] == "public_paused_checkpoint_committed":
            public = snapshot["public"]
            verify_checkpoint(root, public["manifest"])
            validate_run_root(root, manifest=public["manifest"], projection=public["projection"])
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?",
                       (canonical_bytes({"locator": locator, "projection": public["projection"], "manifest": public["manifest"]}), key))


class ExternalCancellation:
    """B02 cancellation owns arbitration; a trusted B03 port owns physical stop."""

    def __init__(self, pause_operations):
        self.pause = pause_operations
        self.coordinator = pause_operations.coordinator
        self.worker = pause_operations.worker_id
        self.lease_seconds = pause_operations.lease_seconds

    def cancel(self, request, canonical):
        from .coordinator import read_regular
        from .execution import parse_ledger
        from .integrity import validate_run_root
        from .operations import ExternalControl

        coordinator, locator = self.coordinator, request.run_locator
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        external_control = ExternalControl(coordinator)
        with coordinator.transaction() as db:
            operation = coordinator.lookup_key("public_control", request.idempotency_key, db=db)
            if operation is not None:
                require(operation["request_digest"] == digest({"operation_type": "cancel_pause", "operation_variant": "not_applicable", "request": canonical}),
                        "Same-key request conflict")
            else:
                row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()
                require(row is not None, "Unknown Run")
                control = loads(row["value"])
                records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
                opened = next((r for r in records if r["record_type"] == "pause" and r["status"] == "opened" and r["pause_id"] == request.pause_id), None)
                require(opened is not None and opened["reason"] == "external_result" and
                        next(r for r in reversed(records) if r["record_type"] == "pause")["pause_id"] == request.pause_id,
                        "Cancel requires the latest external public Pause")
                values = [external_control.read(db, row[0]) for row in db.execute("SELECT external_operation_id FROM external_operations")]
                values = [v for v in values if v["run_locator"] == locator and v.get("pause_id") == request.pause_id]
                require(len(values) == 1 and values[0]["pause_id"] == opened["pause_id"] and
                        values[0]["attempt_id"] == opened["target_attempt_id"], "External cancellation binding mismatch")
                external = values[0]
                if external["resolution_owner"] in ("cancel", "interrupt"):
                    winner = self._winner(db, external, opened)
                    source = coordinator.snapshot(winner["operation_id"], db=db)["source"]
                    require(opened in source["records"] and source["state"]["run_status"] == "paused", "Winner has no original public Pause source")
                    state = source["state"]
                else:
                    state = validate_run_root(root, manifest=control["manifest"], projection=control["projection"]).value
                    require(state["run_status"] == "paused" and records[-1] == opened, "Cancel requires the latest external opened Pause")
                require(external["resolution_owner"] is not None or self.pause.external_adapter is not None,
                        "Cancellation requires a trusted external stop adapter")
                index = loads(read_regular(root / "artifact_index.json"))
                snapshot = {"run_locator": locator, "opened": opened, "source_control_revision": row["revision"],
                            "source": {"records": records, "index": index, "state": state}, "external_id": external["producer_operation_id"]}

                def reserve(operation_id, stamp):
                    return {"exact_pause_and_opened_head": {"pause_id": request.pause_id, "execution_head": digest(opened)},
                            "external_operation_identity": {"producer_operation_id": external["producer_operation_id"]},
                            "typed_cancel_reason": request.reason,
                            "precomputed_pause_cancel_or_quarantine_event": {"event_index": len(records) + 1, "pause_id": request.pause_id},
                            "terminal_disposition_contract_digest": digest({"opened_head": digest(opened), "external_id": external["producer_operation_id"],
                                                                          "reason": request.reason})}

                operation = coordinator.reserve_in_transaction(db, "cancel_pause", "not_applicable", "public_control", request.idempotency_key,
                                                               canonical, self.worker, reserve, lease_seconds=self.lease_seconds, build_snapshot=lambda op: snapshot)
        if operation["status"] != "in_progress":
            return operation
        if coordinator._time().monotonic_seconds >= operation["lease_expires"]:
            operation = coordinator.acquire(operation["operation_id"], self.worker, lease_seconds=self.lease_seconds)
        elif operation["worker_owner_id"] != self.worker:
            return operation
        return self._continue(operation, "cancel_arbitrated")

    def _winner(self, db, external, opened):
        from .operations import TerminalOperations
        locator = external["run_locator"]
        winner = self.coordinator.get(external["resolution_owner_operation_id"], db=db)
        require(winner["operation_type"] == ("cancel_pause" if external["resolution_owner"] == "cancel" else "resolve_external_interrupt") and
                winner["request"]["run_locator"] == locator, "External winner operation mismatch")
        reservation = winner["reservation"]
        bound = reservation["external_operation_identity"]["producer_operation_id"] if winner["operation_type"] == "cancel_pause" else reservation["exact_external_operation_resolution_tuple"]["external_operation_id"]
        require(bound == external["producer_operation_id"], "Winner owns another external operation")
        row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (digest(locator), opened["pause_id"])).fetchone()
        require(row is not None, "Winner has no public Pause authority")
        pause = loads(row[0])
        require(pause["owner"] == winner["operation_id"] and pause["opened_head"] == digest(opened), "Winner Pause owner/head mismatch")
        public = next((r for r in self.coordinator.history(pause["publication_owner"]) if r["phase"] == "public_paused_checkpoint_committed"), None)
        require(public is not None and public["evidence"]["pause_opened_resulting_head"] == digest(opened), "Winner source was never a public opened Pause")
        terminal = TerminalOperations(self.coordinator, self.worker, self.lease_seconds).closure(locator, db=db)
        require(terminal is None or terminal["terminal_closure_owner_operation_id"] == winner["operation_id"], "Winner Run owner mismatch")
        return winner

    def _continue(self, operation, first_phase):
        from .operations import ExternalControl, TerminalOperations, continue_publication_plan
        from .coordinator import MaterializationSnapshotError
        coordinator = self.coordinator
        try:
            if operation["phase"] == "operation_reserved":
                operation = coordinator.step(operation["operation_id"], self.worker, operation["lease_epoch"], operation["phase_revision"], first_phase, self._arbitrate)
            snapshot = coordinator.snapshot(operation["operation_id"])
            value = ExternalControl(coordinator).read(coordinator.connection, snapshot["external_id"])
            if value.get("resolution_owner_operation_id") == operation["operation_id"] and value["operation_phase"] != "external_final_evidence_committed":
                require(self.pause.external_adapter is not None, "Missing external stop continuation adapter")
                self.pause.external_adapter.stop(coordinator, snapshot["external_id"], operation["operation_id"])
            return continue_publication_plan(coordinator, operation, self.worker, self.lease_seconds, self._phase, rebuild=self._plan)
        except (ControlIntegrityError, OSError, ValueError) as error:
            if isinstance(error, MaterializationSnapshotError):
                return coordinator.quarantine_plan(operation, self.worker, error)
            with coordinator.transaction() as db:
                current = coordinator.failed_operation(db, operation, self.worker, error)
                snapshot = coordinator.snapshot(current["operation_id"], db=db)
                closure = TerminalOperations(coordinator, self.worker, self.lease_seconds).closure(snapshot["run_locator"], db=db)
                if closure is None and current["operation_type"] == "resolve_external_interrupt" and current["operation_variant"] == "recoverable_timeout":
                    value = ExternalControl(coordinator).read(db, snapshot["external_id"])
                    if value.get("resolution_owner_operation_id") == current["operation_id"]:
                        locator = snapshot["run_locator"]
                        pause = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (digest(locator), snapshot["opened"]["pause_id"])).fetchone()
                        require(pause is not None and loads(pause[0])["owner"] == current["operation_id"], "Timeout fallback lost Pause ownership")
                        closure = {"terminal_closure_revision": 1, "terminal_closure_owner_operation_id": current["operation_id"],
                                   "terminal_trigger_reference": current["request"], "terminal_trigger_digest": current["request_digest"],
                                   "terminal_request_digest": current["request_digest"], "terminal_disposition_contract": {"variant": "recoverable_timeout"},
                                   "terminal_preclose_contract": current["reservation"], "resolved_terminal_disposition": None, "resolved_preclose_heads": None,
                                   "terminal_closure": "pending", "run_status": None}
                        db.execute("INSERT INTO run_terminal_closure VALUES (?,?,?)", (digest(locator), 1, canonical_bytes(closure)))
                        db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (digest(locator),))
                owned = closure is not None and closure["terminal_closure_owner_operation_id"] == current["operation_id"]
                return coordinator.interrupt(db, current, "recovery_required" if owned else "failed", {
                    "kind": "external_control_closure_unavailable" if owned else "external_arbitration_rejected",
                    "external_operation_id": snapshot["external_id"], "phase": current["phase"], "lease_epoch": current["lease_epoch"],
                    "source_execution_head": snapshot["source"]["state"]["execution_head"], "cause_type": type(error).__name__, "message": str(error)})

    def _arbitrate(self, db, operation):
        from .coordinator import read_regular
        from .operations import ExternalControl, TerminalOperations
        coordinator = self.coordinator
        snapshot = coordinator.snapshot(operation["operation_id"], db=db)
        locator, opened = snapshot["run_locator"], snapshot["opened"]
        key = digest(locator)
        external_control = ExternalControl(coordinator)
        value = external_control.read(db, snapshot["external_id"])
        resolution = value["resolution_owner"]
        winner_summary = None
        if resolution in ("cancel", "interrupt"):
            winner = self._winner(db, value, opened)
            winner_summary = {k: winner[k] for k in ("operation_id", "phase_revision", "lease_epoch", "status", "phase")}
            outcome = "preexisting_" + resolution + "_resolution"
        else:
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            require(read_regular(root / "execution_history.jsonl") == b"".join(canonical_bytes(r) + b"\n" for r in snapshot["source"]["records"]),
                    "External cancellation source changed")
            owner_row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, opened["pause_id"])).fetchone()
            require(owner_row is not None, "Missing external Pause authority")
            owner = loads(owner_row[0])
            require(owner["owner"] is None and owner["status"] == "opened" and owner["opened_head"] == digest(opened) and
                    TerminalOperations(coordinator, self.worker, self.lease_seconds).closure(locator, db=db) is None, "Pause/Run arbitration lost")
            require(db.execute("SELECT revision FROM run_controls WHERE run_key=?", (key,)).fetchone()[0] == snapshot["source_control_revision"],
                    "Cancel source revision changed")
            if resolution == "normal":
                external_control.final_evidence(db, value["producer_operation_id"])
                outcome = "normal_terminal_won"
            else:
                machine = PROTOCOL["state_machines"]["external_operation"]
                require(value["operation_phase"] in machine["cancellable_work_phases"], "External phase is not cancellable")
                prior = value["phase_revision"]
                value.update(resolution_owner="cancel", resolution_owner_operation_id=operation["operation_id"],
                             cancel_intent=True, cancel_reason=operation["request"]["reason"], operation_phase="cancel_intent_committed",
                             operation_status="stop_requested", phase_revision=prior + 1)
                require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                                   (prior + 1, canonical_bytes(value), value["producer_operation_id"], prior)).rowcount == 1, "External resolution CAS lost")
                outcome = "cancel_won"
            owner["owner"] = operation["operation_id"]
            db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?", (canonical_bytes(owner), key, opened["pause_id"]))
            terminal = {"terminal_closure_revision": 1, "terminal_closure_owner_operation_id": operation["operation_id"],
                        "terminal_trigger_reference": operation["request"], "terminal_trigger_digest": operation["request_digest"],
                        "terminal_request_digest": operation["request_digest"], "terminal_disposition_contract": {"reason": "operator_cancel"},
                        "terminal_preclose_contract": operation["reservation"], "resolved_terminal_disposition": None, "resolved_preclose_heads": None,
                        "terminal_closure": "pending", "run_status": None}
            db.execute("INSERT INTO run_terminal_closure VALUES (?,?,?)", (key, 1, canonical_bytes(terminal)))
            db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (key,))
        return {"exact_pause_identity_and_opened_head": operation["reservation"]["exact_pause_and_opened_head"],
                "outcome_conditioned_pause_run_owner_guard": {"acquired": not outcome.startswith("preexisting_"), "operation_id": operation["operation_id"], "winner": winner_summary},
                "external_operation_identity_or_typed_null": {"producer_operation_id": value["producer_operation_id"]},
                "external_revision_epoch_resolution_owner_and_owner_operation_id": {"phase_revision": value["phase_revision"], "lease_epoch": value["lease_epoch"],
                                                                                  "resolution_owner": value["resolution_owner"], "owner_operation_id": value.get("resolution_owner_operation_id")},
                "arbitration_outcome": outcome,
                "winner_revision_and_proof_or_intent_digest_or_not_dispatched_digest": digest(value)}

    def _plan(self, operation, snapshot):
        from copy import deepcopy
        from .operations import ExternalControl, PublicationPlan
        from .records import FIELDS as RECORD_FIELDS
        coordinator = self.coordinator
        source, opened, locator = snapshot["source"], snapshot["opened"], snapshot["run_locator"]
        owner = operation["operation_id"]
        plan = PublicationPlan(operation, source["records"], deepcopy(source["index"]))
        arbitration = next(row["evidence"] for row in coordinator.history(owner) if row["phase"] == "cancel_arbitrated")
        plan.step("cancel_arbitrated", arbitration)
        outcome = arbitration["arbitration_outcome"]
        value = ExternalControl(coordinator).read(coordinator.connection, snapshot["external_id"])
        if outcome.startswith("preexisting_"):
            winner = arbitration["outcome_conditioned_pause_run_owner_guard"]["winner"]
            plan.step("resolution_winner_observed", {"preexisting_cancel_or_interrupt_resolution_owner": value["resolution_owner"],
                      "winner_operation_identity": winner["operation_id"], "winner_phase_revision_and_lease_epoch": {"phase_revision": winner["phase_revision"], "lease_epoch": winner["lease_epoch"]},
                      "winner_domain_owner_coherence": arbitration, "no_cancel_pause_or_run_ownership": owner},
                      branch={"arbitration_outcome": outcome, "external_final_proof_kind": "not_applicable"})
            result = {"run_locator": locator, "winner_operation_id": winner["operation_id"], "domain_status": None,
                      "winner_operation_status": winner["status"], "winner_phase": winner["phase"],
                      "pause_id": opened["pause_id"], "run_status": None, "terminal_closure": "not_applicable"}
            plan.step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": 4})
            return {**snapshot, "steps": plan.steps, "observer_only": True}
        value, final = ExternalControl(coordinator).final_evidence(coordinator.connection, snapshot["external_id"])
        safe = value["proof_kind"] == "safe_stop"
        branch = {"arbitration_outcome": outcome, "external_final_proof_kind": value["proof_kind"]}
        final_digest = value["terminal_evidence_digest"]
        if safe:
            plan.step("external_terminal_closure_verified", {"external_final_evidence_digest": final_digest, "safe_stop_proof_kind": "safe_stop",
                      "resolution_owner_and_revision": {"resolution_owner": value["resolution_owner"], "phase_revision": value["phase_revision"]}}, branch=branch)
            proof = {"proof_variant": "external_safe_stop", "external_final_digest": final_digest, "resolution_revision": value["phase_revision"], **final["stop_proof"]}
            cancelled = plan.append("pause", "pause_cancelled", **{key: opened[key] for key in IDENTITY_FIELDS}, status="cancelled",
                                    state_digest=digest(source["state"]), operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=4,
                                    proof={"opened": {"execution_head": digest(opened)}, "cancel": proof})
            plan.step("pause_cancelled_recorded", {"pause_cancel_proof": proof})
            target = next(r for r in reversed(source["records"]) if r["record_type"] == "attempt" and r["attempt_id"] == opened["target_attempt_id"])
            require(target["status"] == "scheduled", "External cancel target already started")
            abandoned = plan.append("attempt", "abandoned", **{**{key: target[key] for key in RECORD_FIELDS["attempt"]}, "status": "abandoned"})
            plan.step("target_disposition_committed", {"target_abandoned_or_not_applicable": abandoned})
        else:
            plan.step("external_unavailable_verified", {"external_final_evidence_digest": final_digest, "unavailable_proof_kind": "unavailable",
                      "quarantine_evidence": final["quarantine_reference"], "missing_proof_dimensions": final["missing_proof_dimensions"]}, branch=branch)
        reservation = next(r for r in source["records"] if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                           r["payload"]["resource_operation_id"] == value["reservation_id"])
        actual = final.get("resource_actual")
        if not safe and actual is not None:
            actual = {field: max(amount, actual[field]) for field, amount in reservation["payload"]["maximum_charge"].items()}
        violation = final.get("proven_policy_violation") is True or actual is not None and any(
            actual[field] > reservation["payload"]["maximum_charge"][field] for field in reservation["payload"]["maximum_charge"])
        budget_index = max(r["budget_event_index"] for r in plan.records if r["record_type"] == "budget") + 1
        settlement = plan.append("budget", "resource_settled", budget_event_id=f"budget_event_{budget_index:06d}", budget_event_index=budget_index,
                                 policy_version=reservation["policy_version"], policy_digest=reservation["policy_digest"],
                                 payload={"resource_operation_id": value["reservation_id"], "actual": actual, "tokens": {"state": "unknown", "value": None},
                                          "cost": {"state": "unknown", "value": None}, "evidence_digest": final_digest,
                                          "operation_id": owner, "lease_epoch": operation["lease_epoch"], "phase_revision": len(plan.steps) + 2})
        if not safe:
            plan.step("unavailable_resource_disposition_committed", {"unavailable_final_evidence": final_digest, "resource_settlement_or_not_applicable": settlement,
                      "conservative_charge_including_observed_overage": actual or reservation["payload"]["maximum_charge"], "same_cancel_owner": owner})
            quarantined = plan.append("pause", "pause_quarantined", **{key: opened[key] for key in IDENTITY_FIELDS}, status="quarantined",
                                      state_digest=digest(source["state"]), operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=len(plan.steps) + 2,
                                      proof={"opened": {"execution_head": digest(opened)}, "external_final_digest": final_digest, "quarantine": final["quarantine_reference"]})
            plan.step("pause_quarantined_recorded", {"external_unavailable_final_proof": final_digest, "pause_cancel_owner": owner, "quarantine_event_identity": digest(quarantined)})
            unavailable = {"pause_disposition": "cancel_opened_quarantined", "pause_quarantined_head": digest(quarantined), "external_unavailable_final_digest": final_digest}
            plan.step("terminal_closure_unavailable_recorded", {"run_terminal_closure_owner": owner, "terminal_closure_unavailable_proof": unavailable,
                      "unavailable_tombstone": {"operation_id": owner, "proof": unavailable}})
            return {**snapshot, "steps": plan.steps, "observer_only": False, "final_digest": final_digest, "disposition": None}
        plan.step("resource_disposition_committed", {"resource_settlement_or_not_applicable": settlement})
        disposition = "failed" if violation else "halted"
        heads = {"execution_head": digest(plan.records[-1]), "artifact_head": plan.index["artifact_head"], "checkpoint_head": source["state"]["checkpoint_head"]}
        plan.step("terminal_eligibility_verified", {"final_terminal_evidence": {"pause_cancelled_head": digest(cancelled), "external_final_digest": final_digest},
                  "exact_authority_heads": heads, "single_assignment_resolution": disposition})
        terminal = plan.append("run_lifecycle", "transitioned", from_status="paused", to_status=disposition, reason_code="operator_cancel",
                               operation_id=owner, pause_id=opened["pause_id"], attempt_id=None, budget_event_id=settlement["budget_event_id"])
        plan.step("terminal_lifecycle_recorded", {"terminal_owner": owner, "terminal_closure_revision": 1, "resolved_terminal_disposition": disposition,
                  "terminal_disposition_contract_digest": operation["reservation"]["terminal_disposition_contract_digest"], "legal_terminal_lifecycle_edge": terminal})
        checkpoint = plan.checkpoint("cancelled")
        plan.step("terminal_checkpoint_committed", {"terminal_lifecycle_resulting_head": digest(terminal), "empty_active_pause_projection": {"pause_id": None}}, checkpoint=checkpoint)
        result = {"run_locator": locator, "run_status": disposition, "domain_status": None, "pause_id": None, "terminal_closure": "committed",
                  **{key: checkpoint["manifest"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}}
        plan.step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": len(plan.steps) + 2})
        return {**snapshot, "steps": plan.steps, "checkpoint": checkpoint, "observer_only": False, "final_digest": final_digest, "disposition": disposition,
                "close_disposition": {"operation_id": owner, "binding_generation": value["active_binding_generation"], "external_final_digest": final_digest,
                                      "settlement_head": digest(settlement), "pause_disposition_head": digest(cancelled), "target_disposition_head": digest(abandoned)}}

    def _phase(self, db, operation, step, snapshot, *, before):
        from .coordinator import read_regular
        from .checkpoints import verify_checkpoint
        from .integrity import validate_run_root
        from .operations import ExternalControl, TerminalOperations
        locator, owner = snapshot["run_locator"], operation["operation_id"]
        key, pause_id = digest(locator), snapshot["opened"]["pause_id"] if snapshot["opened"] is not None else None
        terminal = TerminalOperations(self.coordinator, self.worker, self.lease_seconds).closure(locator, db=db)
        row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, pause_id)).fetchone()
        pause = loads(row[0]) if row is not None else None
        if snapshot["observer_only"]:
            value = ExternalControl(self.coordinator).read(db, snapshot["external_id"])
            winner = self._winner(db, value, snapshot["opened"])
            require(winner["operation_id"] != owner, "Observer is the resolution winner")
            require(pause["owner"] != owner and (terminal is None or terminal["terminal_closure_owner_operation_id"] != owner), "Observer acquired domain ownership")
            return
        require((pause is None or pause["owner"] == owner) and terminal is not None and terminal["terminal_closure_owner_operation_id"] == owner and
                terminal["terminal_closure"] == "pending", "External cancellation owner fence lost")
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        if before:
            require(read_regular(root / "execution_history.jsonl").decode() in (step["expected_previous_ledger"], step["expected_ledger"]), "External cancel prefix conflict")
            value, proof = ExternalControl(self.coordinator).final_evidence(db, snapshot["external_id"])
            require(value["terminal_evidence_digest"] == snapshot["final_digest"], "External cancel final changed")
            return
        phase = step["target"]
        if phase in ("pause_cancelled_recorded", "pause_quarantined_recorded", "interrupt_safe_pause_disposition_committed", "interrupt_unavailable_pause_disposition_committed"):
            if pause is not None:
                pause["status"] = snapshot["pause_status"] if phase.startswith("interrupt_") else "cancelled" if phase == "pause_cancelled_recorded" else "quarantined"
                db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?", (canonical_bytes(pause), key, pause_id))
        elif phase == "resource_disposition_committed" and operation["operation_type"] == "cancel_pause":
            value = ExternalControl(self.coordinator).read(db, snapshot["external_id"])
            proof = snapshot["close_disposition"]
            require(value["active_binding_generation"] == proof["binding_generation"] and value["active_binding_status"] == "active" and
                    value["close_disposition"] is None and value["consumption_release"] is None, "External close disposition CAS lost")
            value.update(active_binding_status="released", close_disposition=proof)
            db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?", (canonical_bytes(value), snapshot["external_id"]))
        elif phase == "terminal_eligibility_verified":
            terminal.update(resolved_terminal_disposition=snapshot["disposition"], resolved_preclose_heads=step["evidence"]["exact_authority_heads"])
            db.execute("UPDATE run_terminal_closure SET value=? WHERE run_key=?", (canonical_bytes(terminal), key))
        elif phase == "terminal_checkpoint_committed":
            checkpoint = snapshot["checkpoint"]
            verify_checkpoint(root, checkpoint["manifest"])
            validate_run_root(root, manifest=checkpoint["manifest"], projection=checkpoint["projection"])
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes({"locator": locator,
                       "projection": checkpoint["projection"], "manifest": checkpoint["manifest"]}), key))
        elif phase in ("result_committed", "terminal_closure_unavailable_recorded"):
            terminal.update(terminal_closure="committed" if phase == "result_committed" else "unavailable", run_status=snapshot["disposition"])
            if phase == "terminal_closure_unavailable_recorded":
                terminal["unavailable_proof"] = step["evidence"]["terminal_closure_unavailable_proof"]
            db.execute("UPDATE run_terminal_closure SET value=? WHERE run_key=?", (canonical_bytes(terminal), key))


class ExternalInterrupt(ExternalCancellation):
    """Typed internal interrupt arbitration shares the existing terminal domain."""

    def interrupt(self, request, actor):
        from hashlib import sha256
        from .coordinator import component, read_regular
        from .execution import parse_ledger
        from .integrity import validate_control_root
        from .operations import ExternalControl

        require(type(request) is ResolveExternalInterruptRequest, "Expected typed external interrupt request")
        identity = actor.authorize("control.internal")
        closed(request.run_locator, ("case_id", "run_id"))
        for value in request.run_locator.values():
            component(value)
        text(request.producer_operation_id)
        digest_value(request.trigger_digest)
        classes = PROTOCOL["stop_route_contract"]["trigger_classes"]
        classification = next((row["trigger_class"] for row in classes if request.reason in row["triggers"]), None)
        variants = {"recoverable_external_timeout": "recoverable_timeout", "terminal_system_stop": "controlled_halt", "external_integrity_stop": "integrity_failure"}
        require(classification in variants, "Trigger does not select an external interrupt")
        variant = variants[classification]
        canonical = {**asdict(request), "actor": identity}
        key = digest({"external_id": request.producer_operation_id, "reason": request.reason, "trigger_digest": request.trigger_digest})
        coordinator, locator = self.coordinator, request.run_locator
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        with coordinator.transaction() as db:
            pending_owner = coordinator.lookup_key("internal_interrupt", key, db=db)
            if pending_owner is None:
                trigger_path = root / request.trigger_reference
                require(trigger_path == trigger_path.resolve() and trigger_path.is_relative_to(root), "Interrupt trigger escaped Run")
                raw = read_regular(trigger_path)
                require(sha256(raw).hexdigest() == request.trigger_digest, "Interrupt trigger bytes changed")
                trigger = loads(raw)
                require(trigger["reason"] == request.reason and trigger["producer_operation_id"] == request.producer_operation_id and
                        trigger["run_locator"] == locator, "Interrupt trigger identity mismatch")
            producer = ExternalControl(coordinator).read(db, request.producer_operation_id)
            active = producer.get("prestart", {}).get("active_time")
            needs_setup = pending_owner is None and active is not None and not active["published"]
        if needs_setup:
            from lqcd_agent.code_agent.external_operation import ExternalProducer
            from lqcd_agent.code_agent.prestart import CodePrestart
            producer = ExternalProducer(coordinator).recover_setup(request.producer_operation_id,
                worker_id=self.worker, lease_seconds=self.lease_seconds)
            CodePrestart(coordinator, request.producer_operation_id,
                         producer["worker_owner_id"], producer["lease_epoch"]).publish_setup()
        with coordinator.transaction() as db:
            operation = coordinator.lookup_key("internal_interrupt", key, db=db)
            if operation is not None:
                require(operation["request_digest"] == digest({"operation_type": "resolve_external_interrupt", "operation_variant": variant, "request": canonical}), "Interrupt request conflict")
            else:
                trigger_path = root / request.trigger_reference
                require(trigger_path == trigger_path.resolve() and trigger_path.is_relative_to(root), "Interrupt trigger escaped Run")
                raw = read_regular(trigger_path)
                require(sha256(raw).hexdigest() == request.trigger_digest, "Interrupt trigger bytes changed")
                trigger = loads(raw)
                require(trigger["reason"] == request.reason and trigger["producer_operation_id"] == request.producer_operation_id and
                        trigger["run_locator"] == locator, "Interrupt trigger identity mismatch")
                external = ExternalControl(coordinator).read(db, request.producer_operation_id)
                require(external["run_locator"] == locator, "Interrupt belongs to another Run")
                require(external["resolution_owner"] is None and external["operation_phase"] in PROTOCOL["state_machines"]["external_operation"]["interruptible_work_phases"],
                        "External interrupt resolution already owned or phase not interruptible")
                row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()
                require(row is not None, "Unknown interrupt Run")
                control = loads(row["value"])
                records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
                latest_pause = next((r for r in reversed(records) if r["record_type"] == "pause"), None)
                pause = latest_pause if latest_pause is not None and latest_pause["status"] in ("prepared", "opened", "claimed") else None
                require(pause is None or pause["status"] in ("prepared", "opened") and pause["reason"] == "external_result" and
                        pause["target_attempt_id"] == external["attempt_id"] and
                        (external["pause_id"] == pause["pause_id"] or pause["status"] == "prepared" and external["pause_id"] is None),
                        "Interrupt source requires an unclaimed external Pause boundary")
                if pause is not None and pause["status"] == "prepared":
                    from .integrity import validate_prepared_pause_root
                    state = validate_prepared_pause_root(coordinator, db, locator, control, pause).value
                    pause_snapshot = {"pause_snapshot": "prepared", "pause_id": pause["pause_id"], "pause_prepared_head": digest(pause)}
                else:
                    state = validate_control_root(coordinator, db, locator, control).value
                    pause_snapshot = {"pause_snapshot": "absent", "pause_absence_proof": {"execution_head": state["execution_head"]}} if pause is None else {
                        "pause_snapshot": "opened", "pause_id": pause["pause_id"], "pause_opened_head": digest(pause), "public_paused_checkpoint": control["manifest"]}
                require(state["run_status"] in ("running", "paused"), "Interrupt source is terminal")
                if variant == "recoverable_timeout":
                    require(pause is not None and pause["status"] == "opened" and external["operation_phase"] in ("dispatch_authorized", "dispatch_receipt_committed"), "Timeout is not a dispatched opened external Pause")
                resolution = {"external_operation_id": external["producer_operation_id"], "external_phase": external["operation_phase"],
                              "external_phase_revision": external["phase_revision"], "external_lease_epoch": external["lease_epoch"]}
                reservation = next((r for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                                    r["payload"]["producer_operation_id"] == external["producer_operation_id"]), None)
                if reservation is None:
                    require(external.get("reservation_id") is None and external.get("reservation_digest") is None and
                            external["operation_phase"] in ("external_operation_reserved", "task_committed", "workspace_manifest_committed"), "Missing committed external reservation")
                    resource = {"reservation_state": "absent_before_reservation", **resolution, "reservation_fields_are_null": True,
                                "no_budget_event_proof": {"execution_head": state["execution_head"], "producer_operation_id": external["producer_operation_id"]}}
                else:
                    require(digest(reservation) == external["reservation_digest"] and reservation["payload"]["resource_operation_id"] == external["reservation_id"], "Interrupt reservation mismatch")
                    binding = {"external_operation_id": external["producer_operation_id"], "reservation_id": external["reservation_id"], "reservation_digest": external["reservation_digest"]}
                    resource = {"reservation_state": "present", **resolution, **binding, "reservation_status": "reserved", "reservation_binding_digest": digest(binding)}
                heads = {field: state[field] for field in ("execution_head", "artifact_head", "checkpoint_head")}
                snapshot = {"run_locator": locator, "opened": pause, "source_control_revision": row["revision"], "external_id": external["producer_operation_id"],
                            "source": {"records": records, "index": loads(read_regular(root / "artifact_index.json")), "state": state}}

                def reserve(operation_id, stamp):
                    return {"exact_external_operation_resolution_tuple": resolution, "typed_interrupt_reason": request.reason, "exact_run_heads": heads,
                            "pause_snapshot": pause_snapshot, "deterministic_delivery_or_closure_identity": digest({"operation_id": operation_id, "external_id": external["producer_operation_id"]}),
                            "resource_reservation_snapshot": resource, "terminal_disposition_contract_digest": digest({"variant": variant, "trigger": trigger, "heads": heads})}

                require(self.pause.external_adapter is not None, "Interrupt requires a trusted external stop adapter")
                operation = coordinator.reserve_in_transaction(db, "resolve_external_interrupt", variant, "internal_interrupt", key, canonical, self.worker,
                                                               reserve, lease_seconds=self.lease_seconds, build_snapshot=lambda op: snapshot)
        if operation["status"] != "in_progress":
            return operation
        if coordinator._time().monotonic_seconds >= operation["lease_expires"]:
            operation = coordinator.acquire(operation["operation_id"], self.worker, lease_seconds=self.lease_seconds)
        elif operation["worker_owner_id"] != self.worker:
            return operation
        phase = "interrupt_and_pause_ownership_reserved" if variant == "recoverable_timeout" else "interrupt_and_terminal_ownership_reserved"
        return self._continue(operation, phase)

    def _arbitrate(self, db, operation):
        from .coordinator import read_regular
        from .operations import ExternalControl, TerminalOperations
        snapshot = self.coordinator.snapshot(operation["operation_id"], db=db)
        locator, pause = snapshot["run_locator"], snapshot["opened"]
        key, owner = digest(locator), operation["operation_id"]
        require(TerminalOperations(self.coordinator, self.worker, self.lease_seconds).closure(locator, db=db) is None, "Interrupt Run already owned")
        require(db.execute("SELECT revision FROM run_controls WHERE run_key=?", (key,)).fetchone()[0] == snapshot["source_control_revision"], "Interrupt source revision changed")
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        require(read_regular(root / "execution_history.jsonl") == b"".join(canonical_bytes(r) + b"\n" for r in snapshot["source"]["records"]), "Interrupt source bytes changed")
        if pause is not None:
            row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, pause["pause_id"])).fetchone()
            if row is None and pause["status"] == "prepared":
                from .integrity import validate_prepared_pause_root
                control = loads(db.execute("SELECT value FROM run_controls WHERE run_key=?", (key,)).fetchone()[0])
                validate_prepared_pause_root(self.coordinator, db, locator, control, pause)
                db.execute("INSERT INTO pause_ownership VALUES (?,?,?,?)", (key, pause["pause_id"], 1, canonical_bytes({
                    "publication_owner": pause["operation_id"], "owner": None, "status": "prepared", "opened_head": None})))
                row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, pause["pause_id"])).fetchone()
            require(row is not None, "Missing interrupt Pause owner")
            pause_owner = loads(row[0])
            require(pause_owner["owner"] is None and pause_owner["status"] == pause["status"], "Interrupt Pause claim lost")
            pause_owner["owner"] = owner
            db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?", (canonical_bytes(pause_owner), key, pause["pause_id"]))
        value = ExternalControl(self.coordinator).read(db, snapshot["external_id"])
        expected = operation["reservation"]["exact_external_operation_resolution_tuple"]
        require(value["resolution_owner"] is None and value["lease_epoch"] == expected["external_lease_epoch"] and
                value["phase_revision"] == expected["external_phase_revision"] and value["operation_phase"] == expected["external_phase"], "Interrupt External CAS lost")
        value.update(resolution_owner="interrupt", resolution_owner_operation_id=owner, interrupt_disposition=operation["operation_variant"],
                     operation_phase="interrupt_stop_intent_committed", operation_status="stop_requested", phase_revision=value["phase_revision"] + 1,
                     cancel_intent=True, cancel_reason=operation["request"]["reason"])
        db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=?", (value["phase_revision"], canonical_bytes(value), snapshot["external_id"]))
        db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (key,))
        if operation["operation_variant"] == "recoverable_timeout":
            return {"recoverable_timeout_disposition": "recoverable_timeout", "exact_external_resolution_tuple": expected,
                    "exact_opened_external_result_pause": operation["reservation"]["pause_snapshot"],
                    "empty_pause_owner_cas": owner, "interrupt_intent_digest": digest(value)}
        terminal = {"terminal_closure_revision": 1, "terminal_closure_owner_operation_id": owner, "terminal_trigger_reference": operation["request"],
                    "terminal_trigger_digest": operation["request_digest"], "terminal_request_digest": operation["request_digest"],
                    "terminal_disposition_contract": {"variant": operation["operation_variant"]}, "terminal_preclose_contract": operation["reservation"],
                    "resolved_terminal_disposition": None, "resolved_preclose_heads": None, "terminal_closure": "pending", "run_status": None}
        db.execute("INSERT INTO run_terminal_closure VALUES (?,?,?)", (key, 1, canonical_bytes(terminal)))
        return {"terminal_interrupt_disposition": operation["operation_variant"], "exact_external_resolution_tuple": expected,
                "exact_run_heads": operation["reservation"]["exact_run_heads"], "pause_snapshot": operation["reservation"]["pause_snapshot"],
                "empty_run_terminal_owner_cas": owner, "applicable_empty_pause_or_publication_owner_cas": {"owner": owner, "pause_id": pause["pause_id"] if pause else None},
                "interrupt_intent_digest": digest(value)}

    def _plan(self, operation, snapshot):
        from copy import deepcopy
        from .operations import ExternalControl, PublicationPlan
        from .records import FIELDS as RECORD_FIELDS
        source, pause = snapshot["source"], snapshot["opened"]
        owner, variant = operation["operation_id"], operation["operation_variant"]
        value, final = ExternalControl(self.coordinator).final_evidence(self.coordinator.connection, snapshot["external_id"])
        require(value["resolution_owner"] == "interrupt" and value["resolution_owner_operation_id"] == owner and final["interrupt_disposition"] == variant,
                "Interrupt final belongs to another owner")
        final_digest, safe = value["terminal_evidence_digest"], value["proof_kind"] == "safe_stop"
        plan = PublicationPlan(operation, source["records"], deepcopy(source["index"]))
        arbitration = self.coordinator.history(owner)[1]
        plan.step(arbitration["phase"], arbitration["evidence"])
        plan.step("external_final_evidence_verified", {"interrupt_external_final_evidence_digest": final_digest,
                  "interrupt_resolution_owner_and_revision": {"owner": owner, "revision": value["phase_revision"]}, "proof_kind": value["proof_kind"],
                  "trusted_usage_and_integrity_evidence": final})
        active = value.get("prestart", {}).get("active_time")
        if active is not None:
            initial = active["setup_record"]["payload"]
            require(active["published"] and active["setup_record"] in source["records"],
                    "Interrupt lacks the canonical setup reservation")
            already_settled = any(row["record_type"] == "budget" and row["event"] == "active_interval_settled" and
                                  row["payload"]["interval_id"] == initial["interval_id"] for row in source["records"])
            if not already_settled:
                stamp = plan.timestamp
                same_clock = (self.coordinator.clock.epoch_id == initial["clock_epoch_id"] and
                              stamp.source == initial["start_at"]["source"] and
                              stamp.wall_seconds >= initial["start_at"]["wall_seconds"] and
                              stamp.monotonic_seconds >= initial["start_at"]["monotonic_seconds"])
                duration = stamp.monotonic_seconds - initial["start_at"]["monotonic_seconds"] if same_clock else None
                require(duration is None or duration <= initial["maximum_seconds"],
                        f"Interrupt setup interval exceeded: observed={duration}, maximum={initial['maximum_seconds']}")
                budget_index = max(r["budget_event_index"] for r in plan.records if r["record_type"] == "budget") + 1
                plan.append("budget", "active_interval_settled", budget_event_id=f"budget_event_{budget_index:06d}",
                            budget_event_index=budget_index, policy_version="0.1",
                            policy_digest=active["setup_record"]["policy_digest"], payload={
                                **{key: initial[key] for key in ("schema_version", "interval_id", "stage", "attempt_id",
                                                               "producer_operation_id", "owner_operation_id", "clock_epoch_id")},
                                "settlement_operation_id": owner, "lease_epoch": operation["lease_epoch"],
                                "phase_revision": 4, "end_at": asdict(stamp) if duration is not None else None,
                                "actual_seconds": duration,
                                "disposition": "actual" if duration is not None else "conservative_maximum",
                                "evidence_digest": final_digest})
        resource = operation["reservation"]["resource_reservation_snapshot"]
        settlement = {"tag": "not_applicable", "reservation_absence": resource}
        violation = final.get("proven_policy_violation") is True
        if resource["reservation_state"] == "present":
            reserved = next(r for r in source["records"] if digest(r) == resource["reservation_digest"])
            actual = final.get("resource_actual")
            violation = violation or actual is not None and any(actual[k] > v for k, v in reserved["payload"]["maximum_charge"].items())
            if not safe and actual is not None:
                actual = {k: max(v, actual[k]) for k, v in reserved["payload"]["maximum_charge"].items()}
            budget_index = max(r["budget_event_index"] for r in plan.records if r["record_type"] == "budget") + 1
            settlement = plan.append("budget", "resource_settled", budget_event_id=f"budget_event_{budget_index:06d}", budget_event_index=budget_index,
                                     policy_version=reserved["policy_version"], policy_digest=reserved["policy_digest"], payload={"resource_operation_id": resource["reservation_id"],
                                     "actual": actual, "tokens": {"state": "unknown", "value": None}, "cost": {"state": "unknown", "value": None},
                                     "evidence_digest": final_digest, "operation_id": owner, "lease_epoch": operation["lease_epoch"], "phase_revision": 4})
        plan.step("resource_disposition_committed", {"resource_settlement_or_not_applicable": settlement})
        outcome = "unavailable_closure" if not safe else "failed_closure" if violation or variant == "integrity_failure" else "recoverable_delivery" if variant == "recoverable_timeout" else "halted_closure"
        plan.step("resolved_interrupt_outcome_committed", {"interrupt_trigger_variant": variant, "external_final_proof_kind": value["proof_kind"],
                  "resource_settlement": settlement, "integrity_classification": "proven_violation" if violation else "clear", "resolved_interrupt_outcome": outcome,
                  "outcome_precedence": list(PROTOCOL["state_machines"]["control_operation"]["interrupt_outcome_resolution"]["precedence"])})
        if outcome == "recoverable_delivery":
            return InterruptedDelivery(self).extend(operation, snapshot, plan, value, final)
        plan.step("interrupt_terminal_ownership_reserved", {"resolved_interrupt_outcome": outcome, "same_interrupt_winner_operation": owner,
                  "existing_or_empty_run_terminal_owner_cas": owner, "terminal_closure_identity": operation["reservation"]["deterministic_delivery_or_closure_identity"]},
                  branch={"resolved_interrupt_outcome": outcome} if variant == "recoverable_timeout" else None)
        pause_snapshot = operation["reservation"]["pause_snapshot"]
        pause_status, event = None, None
        if pause is None:
            disposition_proof = {"pause_disposition": "absent_not_applicable", "pause_snapshot_absent": pause_snapshot, "no_pause_event": True}
        else:
            pause_status = ("aborted" if pause["status"] == "prepared" else "interrupted") if safe else "quarantined"
            event = plan.append("pause", "pause_" + pause_status, **{key: pause[key] for key in IDENTITY_FIELDS}, status=pause_status,
                                state_digest=digest(source["state"]), operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=7,
                                proof={pause["status"]: {"execution_head": digest(pause)}, "external_final_digest": final_digest, "interrupt": operation["request"]["reason"]})
            disposition_proof = {"pause_disposition": pause["status"] + "_" + pause_status,
                                 "pause_snapshot_" + pause["status"]: pause_snapshot, "pause_" + pause_status + "_event_digest": digest(event)}
        target = next(r for r in reversed(source["records"]) if r["record_type"] == "attempt" and r["attempt_id"] == value["attempt_id"])
        if safe:
            require(target["status"] == "scheduled", "Pre-start external interrupt cannot dispose a started consumer")
            plan.append("attempt", "abandoned", **{**{key: target[key] for key in RECORD_FIELDS["attempt"]}, "status": "abandoned"})
        name = "interrupt_safe_pause_disposition_committed" if safe else "interrupt_unavailable_pause_disposition_committed"
        plan.step(name, {"interrupt_safe_pause_disposition_proof" if safe else "interrupt_unavailable_pause_disposition_proof": disposition_proof}, branch={"resolved_interrupt_outcome": outcome})
        disposition = None if not safe else "failed" if outcome == "failed_closure" else "halted"
        if not safe:
            unavailable = {"pause_disposition": "terminal_absent_not_applicable" if pause is None else "terminal_" + pause["status"] + "_quarantined",
                           "pause_disposition_proof_digest": digest(disposition_proof), "external_unavailable_final_digest": final_digest}
            unavailable.update({"pause_not_applicable": disposition_proof} if pause is None else {"pause_quarantined_head": digest(event)})
            plan.step("terminal_closure_unavailable_recorded", {"run_terminal_closure_owner": owner, "terminal_closure_unavailable_proof": unavailable,
                      "unavailable_tombstone": {"operation_id": owner, "proof": unavailable}})
            return {**snapshot, "steps": plan.steps, "observer_only": False, "final_digest": final_digest, "disposition": None, "pause_status": pause_status}
        heads = {"execution_head": digest(plan.records[-1]), "artifact_head": plan.index["artifact_head"], "checkpoint_head": source["state"]["checkpoint_head"]}
        plan.step("terminal_eligibility_verified", {"final_terminal_evidence": {"external_final_digest": final_digest, "pause_disposition": disposition_proof},
                  "exact_authority_heads": heads, "single_assignment_resolution": disposition})
        terminal = plan.append("run_lifecycle", "transitioned", from_status=source["state"]["run_status"], to_status=disposition, reason_code=operation["request"]["reason"],
                               operation_id=owner, pause_id=pause["pause_id"] if pause else None, attempt_id=None, budget_event_id=settlement.get("budget_event_id"))
        plan.step("terminal_lifecycle_recorded", {"terminal_owner": owner, "terminal_closure_revision": 1, "resolved_terminal_disposition": disposition,
                  "terminal_disposition_contract_digest": operation["reservation"]["terminal_disposition_contract_digest"], "legal_terminal_lifecycle_edge": terminal})
        checkpoint = plan.checkpoint("interrupted")
        plan.step("terminal_checkpoint_committed", {"terminal_lifecycle_resulting_head": digest(terminal), "empty_active_pause_projection": {"pause_id": None}}, checkpoint=checkpoint)
        result = {"run_locator": snapshot["run_locator"], "run_status": disposition, "domain_status": None, "pause_id": None, "terminal_closure": "committed",
                  **{key: checkpoint["manifest"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}}
        plan.step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": len(plan.steps) + 2})
        return {**snapshot, "steps": plan.steps, "checkpoint": checkpoint, "observer_only": False, "final_digest": final_digest,
                "disposition": disposition, "pause_status": pause_status}

    def _phase(self, db, operation, step, snapshot, *, before):
        if snapshot.get("recoverable_delivery"):
            return InterruptedDelivery(self).phase(db, operation, step, snapshot, before=before)
        if operation["operation_variant"] != "recoverable_timeout" or step["target"] not in (
                "external_final_evidence_verified", "resource_disposition_committed", "resolved_interrupt_outcome_committed", "interrupt_terminal_ownership_reserved"):
            return super()._phase(db, operation, step, snapshot, before=before)
        from .coordinator import read_regular
        from .operations import ExternalControl, TerminalOperations
        locator, owner = snapshot["run_locator"], operation["operation_id"]
        key, pause_id = digest(locator), snapshot["opened"]["pause_id"]
        row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, pause_id)).fetchone()
        require(row is not None and loads(row[0])["owner"] == owner, "Timeout lost Pause ownership")
        if before:
            terminal = TerminalOperations(self.coordinator, self.worker, self.lease_seconds).closure(locator, db=db)
            require(terminal is None, "Timeout terminal ownership conflict")
            root = self.coordinator.root / locator["case_id"] / locator["run_id"]
            require(read_regular(root / "execution_history.jsonl").decode() in (step["expected_previous_ledger"], step["expected_ledger"]), "Timeout publication prefix conflict")
            value, _ = ExternalControl(self.coordinator).final_evidence(db, snapshot["external_id"])
            require(value["terminal_evidence_digest"] == snapshot["final_digest"], "Timeout final evidence changed")
            if step["target"] == "interrupt_terminal_ownership_reserved":
                terminal = {"terminal_closure_revision": 1, "terminal_closure_owner_operation_id": owner, "terminal_trigger_reference": operation["request"],
                            "terminal_trigger_digest": operation["request_digest"], "terminal_request_digest": operation["request_digest"],
                            "terminal_disposition_contract": {"variant": operation["operation_variant"]}, "terminal_preclose_contract": operation["reservation"],
                            "resolved_terminal_disposition": None, "resolved_preclose_heads": None, "terminal_closure": "pending", "run_status": None}
                db.execute("INSERT INTO run_terminal_closure VALUES (?,?,?)", (key, 1, canonical_bytes(terminal)))
                db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (key,))


def validate_fingerprint(value):
    """Validate a recorded fingerprint without reading the current Host environment."""
    closed(value, FINGERPRINT_FIELDS)
    for field in ("control_protocol", "application_build", "graph_topology"):
        digest_value(value[field])
    for field in ("state_schema", "execution_schema", "artifact_schema", "langgraph", "checkpointer", "serializer"):
        text(value[field])
    require(value["execution_schema"] == PROTOCOL["schema_version"], "Unsupported fingerprint execution schema")


def validate_pause_record(record):
    """Validate a closed Pause event; cross-event guards are checked by replay."""
    number(record["pause_index"], integer=True, minimum=1)
    require(record["pause_id"] == f"pause_{record['pause_index']:06d}", "Non-canonical Pause identity")
    require(record["status"] in CONTRACT["states"] and record["event"] == "pause_" + record["status"],
            "Unknown Pause lifecycle event")
    require(record["reason"] in REASONS, "Unknown Pause reason")
    for field in ("cycle_id", "requesting_attempt_id", "operation_id"):
        text(record[field])
    text(record["target_attempt_id"], nullable=True)
    if record["reason"] == "human_input":
        require(record["target_attempt_id"] is None, "Human Pause cannot preallocate a validator")
    if record["reason"] == "external_result":
        text(record["target_attempt_id"])
    for field in ("input_contract", "authorization_scope", "proof"):
        require(type(record[field]) is dict and bool(record[field]), "Missing typed Pause binding")
    validate_fingerprint(record["runtime_fingerprint"])
    require(record["runtime_fingerprint"]["execution_schema"] == record["schema_version"], "Pause schema fingerprint mismatch")
    digest_value(record["state_digest"])
    number(record["lease_epoch"], integer=True, minimum=1)
    number(record["phase_revision"], integer=True, minimum=1)
    proof = record["proof"]
    if record["status"] == "prepared":
        closed(proof, ("source_heads", "dependency", "allowed_target_action"))
        closed(proof["source_heads"], ("execution_head", "artifact_head", "checkpoint_head"))
        require(proof["source_heads"]["execution_head"] == record["previous_execution_head"] and
                proof["source_heads"]["artifact_head"] == record["artifact_head"], "Pause preparation head mismatch")
        digest_value(proof["source_heads"]["checkpoint_head"])
        require(type(proof["dependency"]) is dict and type(proof["allowed_target_action"]) is dict,
                "Missing Pause dependency or target contract")
    elif record["status"] == "opened":
        closed(proof, ("prepared", "prepared_checkpoint", "paused_lifecycle", "opened_at", "deadline") +
               (("active_time",) if "active_time" in proof else ()))
        for field in ("prepared", "paused_lifecycle"):
            closed(proof[field], ("execution_head",))
            digest_value(proof[field]["execution_head"])
        if "active_time" in proof:
            closed(proof["active_time"], ("interval_id", "settlement_execution_head"))
            text(proof["active_time"]["interval_id"])
            digest_value(proof["active_time"]["settlement_execution_head"])
            require(proof["active_time"]["settlement_execution_head"] == record["previous_execution_head"],
                    "Pause opened settlement head mismatch")
        else:
            require(proof["paused_lifecycle"]["execution_head"] == record["previous_execution_head"],
                    "Pause opened pre-head mismatch")
        require(type(proof["prepared_checkpoint"]) is dict, "Missing prepared checkpoint")
        closed(proof["opened_at"], ("source", "wall_seconds", "monotonic_seconds"))
        Timestamp(**proof["opened_at"])
        require(proof["opened_at"] == record["created_at"], "Pause opened clock binding mismatch")
        number(proof["deadline"])
        require(proof["deadline"] >= proof["opened_at"]["wall_seconds"], "Pause deadline predates open")
    else:
        require("opened" in proof or record["status"] in ("aborted", "quarantined"), "Missing Pause opened binding")
        if "opened" in proof:
            closed(proof["opened"], ("execution_head",))
            digest_value(proof["opened"]["execution_head"])


def replay_pauses(records):
    """Derive pending/active Pause projections and verify cross-event identity."""
    pauses = {}
    run_status = "initializing"
    current = None
    by_head = {}
    attempts = {}
    transitions = {}
    for record in records:
        kind = record["record_type"]
        if kind == "attempt":
            attempts[record["attempt_id"]] = record
        elif kind == "transition":
            transitions[record["transition_id"]] = record
        elif kind == "run_lifecycle":
            if current is not None and record["to_status"] == "paused":
                require(current["status"] == "prepared" and current["pause_id"] == record["pause_id"],
                        "Paused lifecycle does not bind the prepared Pause")
            if current is not None and record["from_status"] == "paused" and record["to_status"] == "running":
                require(current["status"] == "consumed" and current["pause_id"] == record["pause_id"],
                        "Running lifecycle precedes Pause consumption")
            run_status = record["to_status"]
        elif kind == "pause":
            validate_pause_record(record)
            identity, status = record["pause_id"], record["status"]
            if status == "prepared":
                require(run_status == "running" and (current is None or current["status"] in CONTRACT["terminal_states"]),
                        "Pause preparation outside a safe running boundary")
                require(identity not in pauses and record["pause_index"] == len(pauses) + 1, "Pause allocation gap or reuse")
                require(record["requesting_attempt_id"] in attempts, "Unknown requesting Attempt")
                target = record["target_attempt_id"]
                if target is not None:
                    require(target in attempts and attempts[target]["status"] == "scheduled", "Pause target already started or absent")
                    inbound = transitions.get(attempts[target]["inbound_transition_id"])
                    require(inbound is not None and inbound["target_attempt_id"] == target, "Pause lacks committed target Transition")
                pauses[identity] = []
            else:
                require(current is not None and identity == current["pause_id"], "Pause is not latest")
                require((current["status"], status) in CONTRACT["allowed_edges"], "Forbidden Pause lifecycle edge")
                require(all(record[field] == current[field] for field in IDENTITY_FIELDS), "Pause immutable identity changed")
                if status == "opened":
                    proof = record["proof"]
                    require(run_status == "paused", "Pause opened before paused lifecycle")
                    require(proof["prepared"]["execution_head"] == digest(pauses[identity][0]), "Foreign prepared head")
                    life = by_head.get(record["previous_execution_head"])
                    if "active_time" in proof:
                        settled = life
                        require(settled is not None and settled["record_type"] == "budget" and
                                settled["event"] == "active_interval_settled" and
                                settled["payload"]["interval_id"] == proof["active_time"]["interval_id"] and
                                settled["payload"]["stage"] == "host_setup" and
                                settled["payload"]["settlement_operation_id"] == record["operation_id"],
                                "Pause opened lacks exact setup settlement")
                        life = by_head.get(settled["previous_execution_head"])
                    require(life is not None and life["record_type"] == "run_lifecycle" and
                            life["from_status"] == "running" and life["to_status"] == "paused" and
                            life["pause_id"] == identity, "Pause opened lacks exact lifecycle closure")
                    checkpoint = proof["prepared_checkpoint"]
                    require(checkpoint.get("execution_head") == digest(pauses[identity][0]) and
                            checkpoint.get("run_id") == record["run_id"] and checkpoint.get("case_id") == record["case_id"],
                            "Prepared checkpoint belongs to another Pause")
                if "opened" in record["proof"]:
                    opened = next((row for row in pauses[identity] if row["status"] == "opened"), None)
                    require(opened is not None and record["proof"]["opened"]["execution_head"] == digest(opened), "Foreign opened Pause")
                if status in ("claimed", "consumed", "cancelled"):
                    require(run_status == "paused", "Pause consumed outside paused lifecycle")
                if status == "consumed":
                    require(record["operation_id"] == current["operation_id"], "Pause claim owner changed")
            pauses[identity].append(record)
            current = record
        by_head[digest(record)] = record
    if not pauses:
        return {}
    value = {field: current[field] for field in IDENTITY_FIELDS + ("status",)}
    value["execution_head"] = digest(current)
    return {"pause_index": len(pauses), "pending_pause": value if current["status"] == "prepared" else None,
            "active_pause": value if current["status"] in ("opened", "claimed") else None}


@dataclass(frozen=True)
class ConsumerStopObservation:
    """Trusted consumer containment observation, separate from Backend finality."""

    stop_proof: dict
    resource_actual: dict


class ConsumptionFailure:
    """The original resume owner closes a claimed normal-result consumption."""

    def __init__(self, pause):
        self.pause = pause
        self.coordinator = pause.coordinator
        self.worker, self.lease_seconds = pause.worker_id, pause.lease_seconds
        self.contract = PROTOCOL["state_machines"]["control_operation"]["consumption_failure_contract"]

    def intent(self, operation):
        return next((row["evidence"]["frozen_failure_snapshot_and_disposition_contract"] for row in
                     self.coordinator.history(operation["operation_id"]) if row["phase"] == "consumption_failure_ownership_reserved"), None)

    def start(self, operation, error):
        from .capabilities import InvocationLeases
        from .integrity import validate_owned_resume_prefix

        coordinator = self.coordinator
        with coordinator.transaction() as db:
            operation = coordinator.failed_operation(db, operation, self.worker, error)
        if self.intent(operation) is not None:
            return self.continue_failure(operation)
        require(operation["phase"] in self.contract["entry_phases"] and operation["request"]["input_kind"] == "external_result",
                "Failure does not own a claimed external consumption boundary")
        source_phase = operation["phase"]

        def reserve(db, current):
            locator = current["request"]["run_locator"]
            key, owner = digest(locator), current["operation_id"]
            pause_row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, current["request"]["pause_id"])).fetchone()
            require(pause_row is not None and loads(pause_row[0])["owner"] == owner, "Failure has no original Pause claim")
            require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone() is None, "Failure lost Run terminal CAS")
            try:
                from lqcd_agent.code_agent.verification_resources import recover_publications
                recover_publications(coordinator, db, current)
                source = validate_owned_resume_prefix(coordinator, db, current)
            except (ControlIntegrityError, OSError, ValueError, KeyError):
                source = None
            trusted = source if source is not None else self._last_trusted_source(db, current, loads(pause_row[0]))
            records = trusted["records"]
            target = current["reservation"]["target_prestart_closure"]["target"]
            attempt = next(r for r in reversed(records) if r["record_type"] == "attempt" and r["attempt_id"] == target["attempt_id"])
            cap_id = "capability_" + owner
            row = db.execute("SELECT revision,value FROM invocation_capabilities WHERE capability_id=?", (cap_id,)).fetchone()
            capability = loads(row["value"]) if row is not None else None
            if capability is not None:
                require(capability["authorization"]["producer_operation_id"] == owner, "Foreign failure capability")
                capability.update(state="uncertain", invocation_epoch=capability["invocation_epoch"] + 1,
                                  expires_at=coordinator._time().monotonic_seconds, updated_at=asdict(coordinator._time()))
                InvocationLeases(coordinator)._save(db, cap_id, row["revision"], capability)
            external = current["reservation"]["target_prestart_closure"]["external"]
            failure_id = digest({"owner": owner, "source_phase": source_phase, "source_revision": current["phase_revision"],
                                 "epoch": current["lease_epoch"], "cause_type": type(error).__name__, "cause": str(error)})
            settled = {r["payload"]["resource_operation_id"]: r for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"}
            pending = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved" and r["payload"]["resource_operation_id"] not in settled]
            artifact = {"tag": "registration_forbidden", "artifact_head": None, "trusted_rejection_digest": failure_id}
            code = trusted["index"]["current"]["code"]
            if code is not None and code["attempt_id"] == target["attempt_id"]:
                artifact = {"tag": "already_registered_audit_only", "artifact_head": trusted["index"]["artifact_head"], "artifact_id": code["artifact_id"]}
            failure = {"failure_id_digest": failure_id, "source_phase_revision": current["phase_revision"], "source_resume_owner_epoch": current["lease_epoch"],
                       "pause_identity_status_and_claim_owner": {"pause_id": current["request"]["pause_id"], **loads(pause_row[0])},
                       "attempt_identity_status_and_started_intent": {"attempt": attempt, "started_intent": capability.get("started_intent") if capability else None},
                       "original_normal_final_digest": external["value"]["terminal_evidence_digest"],
                       "last_trusted_execution_artifact_checkpoint_heads": {k: trusted["state"][k] for k in ("execution_head", "artifact_head", "checkpoint_head")},
                       "pending_resource_operation_ids_and_settlement_snapshots": {"pending": pending, "settled": settled},
                       "artifact_registration_forbidden_or_exact_existing_audit_snapshot": artifact,
                       "active_binding_generation": external["value"]["active_binding_generation"]}
            failure["terminal_disposition_contract_digest"] = digest(failure)
            closed(failure, self.contract["snapshot_fields"])
            frozen = {"failure": failure, "source_phase": source_phase, "run_locator": locator, "source": trusted,
                      "stop_intent": {"failure_id_digest": failure_id, "consumer_capability_id": cap_id,
                                      "pending_resource_ids": [r["payload"]["resource_operation_id"] for r in pending]}}
            closure = {"terminal_closure_revision": 1, "terminal_closure_owner_operation_id": owner,
                       "terminal_trigger_reference": {"failure_id_digest": failure_id}, "terminal_trigger_digest": failure_id,
                       "terminal_request_digest": current["request_digest"], "terminal_disposition_contract": failure,
                       "terminal_preclose_contract": frozen["stop_intent"], "resolved_terminal_disposition": None,
                       "resolved_preclose_heads": None, "terminal_closure": "pending", "run_status": None}
            db.execute("INSERT INTO run_terminal_closure VALUES (?,?,?)", (key, 1, canonical_bytes(closure)))
            db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (key,))
            return {"same_in_progress_external_result_resume_and_pause_claim_owner": owner,
                    "exact_source_phase_revision_and_current_epoch": {"phase_revision": current["phase_revision"], "epoch": current["lease_epoch"]},
                    "trusted_failure_intent_and_last_trusted_heads": failure["last_trusted_execution_artifact_checkpoint_heads"],
                    "empty_run_terminal_owner_cas": owner, "frozen_failure_snapshot_and_disposition_contract": frozen,
                    "invocation_epoch_revoked_before_further_effects": {"capability_id": cap_id, "epoch": capability["invocation_epoch"] if capability else None},
                    "precomputed_consumer_stop_intent_bound_to_original_resource_ids": frozen["stop_intent"]}

        operation = coordinator.step(operation["operation_id"], self.worker, operation["lease_epoch"], operation["phase_revision"],
                                     "consumption_failure_ownership_reserved", reserve,
                                     branch_values={"consumption_outcome_at_" + source_phase: "consumption_failure"})
        return self.continue_failure(operation)

    def _last_trusted_source(self, db, operation, pause):
        """Retain historical authority without treating it as an appendable prefix."""
        from .coordinator import MaterializationSnapshotError
        from .capabilities import InvocationLeases
        from .execution import parse_ledger
        from .projections import bounded_projection
        from lqcd_agent.code_agent.verification_resources import owned_prefix

        capability = "capability_" + operation["operation_id"]
        row = db.execute("SELECT 1 FROM invocation_capabilities WHERE capability_id=?", (capability,)).fetchone()
        if row is not None:
            _, value = InvocationLeases(self.coordinator).get(capability, db=db)
            if value.get("verification_intents"):
                authorization = value["authorization"]
                require(authorization["producer_operation_id"] == operation["operation_id"] and
                        all(authorization["identity"][k] == v for k, v in operation["request"]["run_locator"].items()),
                        "Foreign historical verification journal")
                prefix = owned_prefix(value, published=False)
                execution, index = parse_ledger(prefix["content"].encode()), loads(prefix["index"])
                state = bounded_projection(execution, artifact_index=index, artifact_head=index["artifact_head"],
                                           artifact_event_index=index["revision"]).value
                state["checkpoint_head"] = authorization["heads"]["checkpoint_head"]
                return {"records": execution.values, "index": index, "state": state}

        try:
            return self.coordinator.snapshot(operation["operation_id"], db=db)["source"]
        except MaterializationSnapshotError:
            publisher = self.coordinator.get(pause["publication_owner"], db=db)
            require(publisher["operation_type"] == "publish_pause" and publisher["status"] == "committed" and
                    publisher["result"]["run_locator"] == operation["request"]["run_locator"] and
                    publisher["result"]["pause_id"] == operation["request"]["pause_id"], "Foreign last trusted Pause publisher")
            stable = self.coordinator.snapshot(publisher["operation_id"], db=db)["public"]
            require(all(stable["manifest"][key] == publisher["result"][key] for key in
                        ("execution_head", "artifact_head", "checkpoint_head")) and
                    digest(stable["records"][-1]) == pause["opened_head"] ==
                    operation["reservation"]["exact_pause_and_opened_head"]["execution_head"], "Last trusted Pause heads changed")
            return {"records": stable["records"], "index": stable["artifact_index"], "state": stable["projection"]}

    def continue_failure(self, operation):
        from .operations import ExternalControl, continue_publication_plan
        from .integrity import validate_owned_resume_prefix
        from .coordinator import read_regular
        from .execution import parse_ledger

        coordinator = self.coordinator
        frozen = self.intent(operation)
        require(frozen is not None, "Missing durable consumption failure intent")
        try:
            if operation["phase"] == "consumption_failure_ownership_reserved":
                failure = frozen["failure"]
                started = failure["attempt_identity_status_and_started_intent"]["started_intent"]
                if started is None:
                    observation = ConsumerStopObservation({"termination_or_not_dispatched": {"tag": "not_dispatched"},
                        "write_lease_revocation": True, "verify_empty": True, "bounded_drain": True, "post_stop_stability": True}, {})
                elif self.pause.external_adapter is not None and hasattr(self.pause.external_adapter, "stop_consumption"):
                    with coordinator.transaction() as db:
                        coordinator.fence(db, operation["operation_id"], self.worker, operation["lease_epoch"], operation["phase_revision"])
                    intent = {**loads(canonical_bytes(frozen["stop_intent"])), "control_operation_id": operation["operation_id"],
                              "control_worker_id": self.worker, "control_lease_epoch": operation["lease_epoch"],
                              "control_phase_revision": operation["phase_revision"]}
                    observation = self.pause.external_adapter.stop_consumption(coordinator, intent)
                else:
                    observation = ConsumerStopObservation({"termination_or_not_dispatched": "unknown", "write_lease_revocation": True,
                        "verify_empty": False, "bounded_drain": False, "post_stop_stability": False}, {})
                require(type(observation) is ConsumerStopObservation, "Untyped consumer containment observation")
                proof = observation.stop_proof
                closed(proof, ("termination_or_not_dispatched", "write_lease_revocation", "verify_empty", "bounded_drain", "post_stop_stability"))
                safe = proof["termination_or_not_dispatched"] in ("confirmed", {"tag": "not_dispatched"}) and all(
                    proof[k] is True for k in ("write_lease_revocation", "verify_empty", "bounded_drain", "post_stop_stability"))

                def stop_verified(db, current):
                    value = current["reservation"]["target_prestart_closure"]["external"]["value"]
                    try:
                        observed, _ = ExternalControl(coordinator).final_evidence(db, value["producer_operation_id"])
                        require(observed["terminal_evidence_digest"] == failure["original_normal_final_digest"] and observed["resolution_owner"] == "normal", "Original normal final changed")
                        source = validate_owned_resume_prefix(coordinator, db, current)
                        authority = {"classification": "appendable", "source": source}
                    except (ControlIntegrityError, OSError, ValueError, KeyError):
                        authority = {"classification": "unavailable", "source": None}
                    return {"same_failure_owner": current["operation_id"],
                            "original_external_normal_final_digest_unchanged": {"expected_digest": failure["original_normal_final_digest"], "verified": authority["classification"] == "appendable"},
                            "consumer_verifier_containment_stop_and_write_fence_proof": {"classification": "safe_stop" if safe else "unavailable",
                                "proof": proof, "trusted_stop_at": asdict(coordinator._time())},
                            "all_pending_resource_usage_or_conservative_charge": observation.resource_actual,
                            "run_authority_integrity_proof_or_unavailable": authority}

                operation = coordinator.step(operation["operation_id"], self.worker, operation["lease_epoch"], operation["phase_revision"],
                                             "consumption_failure_stop_verified", stop_verified)
            locator = frozen["run_locator"]
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            stop = next(row["evidence"] for row in coordinator.history(operation["operation_id"])
                        if row["phase"] == "consumption_failure_stop_verified")
            appendable = stop["run_authority_integrity_proof_or_unavailable"]["classification"] == "appendable"
            safe = stop["consumer_verifier_containment_stop_and_write_fence_proof"]["classification"] == "safe_stop"
            materialized = parse_ledger(read_regular(root / "execution_history.jsonl")).values if appendable and safe else []
            snapshot = self._plan({**operation, "_materialized_records": materialized}, None)
            return continue_publication_plan(coordinator, operation, self.worker, self.lease_seconds, self._phase,
                                             rebuild=self._plan, plan_snapshot=snapshot)
        except (ControlIntegrityError, OSError) as error:
            with coordinator.transaction() as db:
                current = coordinator.failed_operation(db, operation, self.worker, error)
                return coordinator.interrupt(db, current, "recovery_required", {"kind": "consumption_failure_closure_unavailable",
                    "failure_id_digest": frozen["failure"]["failure_id_digest"], "cause_type": type(error).__name__, "message": str(error)})

    def _plan(self, operation, unused):
        from copy import deepcopy
        from .operations import PublicationPlan
        from .records import FIELDS as RECORD_FIELDS

        frozen = self.intent(operation)
        stop = next(row["evidence"] for row in self.coordinator.history(operation["operation_id"]) if row["phase"] == "consumption_failure_stop_verified")
        failure, owner = frozen["failure"], operation["operation_id"]
        authority = stop["run_authority_integrity_proof_or_unavailable"]
        outcome = "failed_closure" if authority["classification"] == "appendable" and stop["consumer_verifier_containment_stop_and_write_fence_proof"]["classification"] == "safe_stop" else "unavailable_closure"
        source = authority["source"] or frozen["source"]
        materialized = operation.get("_materialized_records", ())
        prior_active_close = next((row for row in materialized if row["record_type"] == "budget" and
            row["event"] == "active_interval_settled" and row["payload"]["stage"] == "attempt_active" and
            row["payload"]["settlement_operation_id"] == owner), None)
        operation = {**operation, "_plan_start_revision": failure["source_phase_revision"] + 2}
        if prior_active_close is not None:
            operation["_materialization_time"] = prior_active_close["created_at"]
        else:
            operation["_materialization_time"] = stop["consumer_verifier_containment_stop_and_write_fence_proof"]["trusted_stop_at"]
        plan = PublicationPlan(operation, source["records"], deepcopy(source["index"]))
        plan.source = "consumption_failure_stop_verified"
        plan.step("consumption_failure_classified", {"consumer_failure_stop_proof": stop["consumer_verifier_containment_stop_and_write_fence_proof"],
                  "run_authority_classification": authority["classification"], "consumption_failure_outcome": outcome})
        snapshot = {"run_locator": frozen["run_locator"], "failure": failure, "source": source, "steps": plan.steps,
                    "disposition": "failed" if outcome == "failed_closure" else None}
        if outcome == "unavailable_closure":
            plan.step("consumption_failure_unavailable_recorded", {"same_failure_run_owner": owner,
                      "consumer_stop_or_run_authority_unavailable": stop, "immutable_failure_tombstone_with_conservative_resource_charges": failure,
                      "active_binding_quarantined_not_safely_detached": {"generation": failure["active_binding_generation"]},
                      "no_fabricated_run_lifecycle_or_code_artifact": True}, branch={"consumption_failure_outcome": outcome})
            return snapshot
        locator = frozen["run_locator"]
        external = operation["reservation"]["target_prestart_closure"]["external"]
        settlements = []
        settled = {r["payload"]["resource_operation_id"] for r in plan.records if r["record_type"] == "budget" and r["event"] == "resource_settled"}
        for reserved in [r for r in plan.records if r["record_type"] == "budget" and r["event"] == "resource_reserved"]:
            rid = reserved["payload"]["resource_operation_id"]
            if rid in settled:
                continue
            actual = external["final"]["resource_actual"] if rid == external["value"]["reservation_id"] else stop["all_pending_resource_usage_or_conservative_charge"].get(rid)
            position = max(r["budget_event_index"] for r in plan.records if r["record_type"] == "budget") + 1
            settlements.append(plan.append("budget", "resource_settled", budget_event_id=f"budget_event_{position:06d}", budget_event_index=position,
                policy_version=reserved["policy_version"], policy_digest=reserved["policy_digest"], payload={"resource_operation_id": rid, "actual": actual,
                    "tokens": {"state": "unknown", "value": None}, "cost": {"state": "unknown", "value": None}, "evidence_digest": failure["failure_id_digest"],
                    "operation_id": owner, "lease_epoch": operation["lease_epoch"], "phase_revision": failure["source_phase_revision"] + 4}))
        pause = next(r for r in reversed(plan.records) if r["record_type"] == "pause")
        if pause["status"] in ("opened", "claimed"):
            opened = next(r for r in plan.records if r["record_type"] == "pause" and r["pause_id"] == pause["pause_id"] and r["status"] == "opened")
            pause = plan.append("pause", "pause_interrupted", **{k: pause[k] for k in IDENTITY_FIELDS}, status="interrupted",
                state_digest=digest(source["state"]), operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=failure["source_phase_revision"] + 4,
                proof={"opened": {"execution_head": digest(opened)}, "failure_id_digest": failure["failure_id_digest"]})
        attempt = next(r for r in reversed(plan.records) if r["record_type"] == "attempt" and r["attempt_id"] == external["value"]["attempt_id"])
        active = next((r["payload"] for r in plan.records if r["record_type"] == "budget" and
                       r["event"] == "active_interval_reserved" and r["payload"]["stage"] == "attempt_active" and
                       r["payload"]["attempt_id"] == attempt["attempt_id"]), None)
        active_closed = active is not None and any(r["record_type"] == "budget" and
            r["event"] == "active_interval_settled" and r["payload"]["interval_id"] == active["interval_id"]
            for r in plan.records)
        if active_closed:
            require(attempt["status"] in ("succeeded", "failed", "pending"),
                    "Closed Code interval has an open Attempt")
        elif active is not None:
            require(attempt["status"] == "running", "Failure active interval is not an open Attempt")
            stamp = plan.timestamp
            same_clock = (self.coordinator.clock.epoch_id == active["clock_epoch_id"] and
                          stamp.source == active["start_at"]["source"] and
                          stamp.wall_seconds >= active["start_at"]["wall_seconds"] and
                          stamp.monotonic_seconds >= active["start_at"]["monotonic_seconds"])
            verification_uncertain = any(r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                r["payload"]["resource_kind"] == "verification_command" and r["payload"]["attempt_id"] == attempt["attempt_id"] and
                (r["payload"]["resource_operation_id"] not in settled or
                 next((s["payload"]["actual"] for s in plan.records if s["record_type"] == "budget" and
                       s["event"] == "resource_settled" and s["payload"]["resource_operation_id"] == r["payload"]["resource_operation_id"]), None) is None)
                for r in plan.records)
            duration = (prior_active_close["payload"]["actual_seconds"] if prior_active_close is not None else
                        stamp.monotonic_seconds - active["start_at"]["monotonic_seconds"] if same_clock and not verification_uncertain else None)
            require(duration is None or duration <= active["maximum_seconds"],
                    f"Failure active interval exceeded: observed={duration}, maximum={active['maximum_seconds']}")
            position = max(r["budget_event_index"] for r in plan.records if r["record_type"] == "budget") + 1
            plan.append("budget", "active_interval_settled", budget_event_id=f"budget_event_{position:06d}",
                        budget_event_index=position, policy_version="0.1",
                        policy_digest=source["state"]["budget"]["policy_digest"], payload={
                            **{key: active[key] for key in ("schema_version", "interval_id", "stage", "attempt_id",
                                                       "producer_operation_id", "owner_operation_id", "clock_epoch_id")},
                            "settlement_operation_id": owner, "lease_epoch": operation["lease_epoch"],
                            "phase_revision": failure["source_phase_revision"] + 4,
                            "end_at": asdict(stamp) if duration is not None else None, "actual_seconds": duration,
                            "disposition": "actual" if duration is not None else "conservative_maximum",
                            "evidence_digest": failure["failure_id_digest"]})
        if attempt["status"] in ("scheduled", "running"):
            fields = {k: attempt[k] for k in RECORD_FIELDS["attempt"]}
            fields.update(status="abandoned" if attempt["status"] == "scheduled" else "failed",
                          error=None if attempt["status"] == "scheduled" else {"type": "ConsumptionIntegrityFailure", "message": failure["failure_id_digest"]})
            attempt = plan.append("attempt", "abandoned" if attempt["status"] == "scheduled" else "finished", **fields)
        release = {"disposition_kind": "consumption_failure", "operation_id": owner, "failure_id_digest": failure["failure_id_digest"],
                   "binding_generation": failure["active_binding_generation"], "external_final_digest": failure["original_normal_final_digest"],
                   "artifact_disposition": failure["artifact_registration_forbidden_or_exact_existing_audit_snapshot"],
                   "pause_disposition_head": digest(pause), "target_disposition_head": digest(attempt),
                   "settlement_heads": [digest(r) for r in plan.records if r["record_type"] == "budget" and r["event"] == "resource_settled"]}
        heads = {"execution_head": digest(plan.records[-1]), "artifact_head": plan.index["artifact_head"], "checkpoint_head": source["state"]["checkpoint_head"]}
        plan.step("consumption_failure_disposition_committed", {"same_failure_run_and_pause_owner": owner,
                  "safe_consumer_stop_and_intact_run_authority": {"stop": stop["consumer_verifier_containment_stop_and_write_fence_proof"], "authority": authority["classification"]},
                  "frozen_attempt_disposition_and_artifact_absence_or_existing_audit_snapshot": {"attempt": attempt, "artifact": release["artifact_disposition"]},
                  "exact_pending_resource_settlements": settlements, "pause_finality_preserving_disposition": pause,
                  "active_binding_failure_release_proof": release, "failed_disposition_contract_and_exact_preclose_heads": heads},
                  branch={"consumption_failure_outcome": outcome})
        plan.step("terminal_eligibility_verified", {"final_terminal_evidence": release, "exact_authority_heads": heads, "single_assignment_resolution": "failed"})
        terminal = plan.append("run_lifecycle", "transitioned", from_status=source["state"]["run_status"], to_status="failed", reason_code="external_consumption_integrity_failure",
                               operation_id=owner, pause_id=pause["pause_id"], attempt_id=None, budget_event_id=settlements[-1]["budget_event_id"] if settlements else None)
        plan.step("terminal_lifecycle_recorded", {"terminal_owner": owner, "terminal_closure_revision": 1, "resolved_terminal_disposition": "failed",
                  "terminal_disposition_contract_digest": failure["terminal_disposition_contract_digest"], "legal_terminal_lifecycle_edge": terminal})
        checkpoint = plan.checkpoint("consumption_failed")
        plan.step("terminal_checkpoint_committed", {"terminal_lifecycle_resulting_head": digest(terminal), "empty_active_pause_projection": {"pause_id": None}}, checkpoint=checkpoint)
        result = {"run_locator": locator, "run_status": "failed", "domain_status": "failed", "pause_id": None, "terminal_closure": "committed",
                  **{k: checkpoint["manifest"][k] for k in ("execution_head", "artifact_head", "checkpoint_head")}}
        plan.step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": failure["source_phase_revision"] + 3 + len(plan.steps)})
        snapshot.update(checkpoint=checkpoint, release=release, pause_status=pause["status"])
        return snapshot

    def _phase(self, db, operation, step, snapshot, *, before):
        from .coordinator import read_regular
        from .checkpoints import verify_checkpoint
        from .integrity import validate_run_root
        from .operations import ExternalControl

        owner, locator = operation["operation_id"], snapshot["run_locator"]
        key = digest(locator)
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        terminal = loads(db.execute("SELECT value FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone()[0])
        require(terminal["terminal_closure_owner_operation_id"] == owner and terminal["terminal_closure"] == "pending", "Consumption failure owner changed")
        if before:
            if snapshot["disposition"] is not None:
                require(read_regular(root / "execution_history.jsonl").decode() in (step["expected_previous_ledger"], step["expected_ledger"]) and
                        read_regular(root / "artifact_history.jsonl").decode() == snapshot["source"]["artifact_history"] and
                        read_regular(root / "budget_policy.json") == canonical_bytes(snapshot["source"]["policy"]), "Failure publication authority changed")
                value, _ = ExternalControl(self.coordinator).final_evidence(db,
                    operation["reservation"]["target_prestart_closure"]["external"]["value"]["producer_operation_id"])
                require(value["terminal_evidence_digest"] == snapshot["failure"]["original_normal_final_digest"] and value["resolution_owner"] == "normal",
                        "Failure continuation lost original normal final")
            return
        phase = step["target"]
        external_id = operation["reservation"]["target_prestart_closure"]["external"]["value"]["producer_operation_id"]
        if phase in ("consumption_failure_disposition_committed", "consumption_failure_unavailable_recorded"):
            value = ExternalControl(self.coordinator).read(db, external_id)
            require(value["resolution_owner"] == "normal" and value["active_binding_generation"] == snapshot["failure"]["active_binding_generation"] and
                    value["consumption_release"] is None and value["close_disposition"] is None, "Failure binding CAS lost")
            if phase == "consumption_failure_disposition_committed":
                value.update(active_binding_status="released", close_disposition=snapshot["release"])
                pause_row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, operation["request"]["pause_id"])).fetchone()
                pause = loads(pause_row[0])
                require(pause["owner"] == owner, "Failure lost original Pause claim")
                pause["status"] = snapshot["pause_status"]
                db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?", (canonical_bytes(pause), key, operation["request"]["pause_id"]))
            else:
                value["active_binding_status"] = "quarantined"
                terminal.update(terminal_closure="unavailable", run_status=None, unavailable_proof=step["evidence"])
            db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?", (canonical_bytes(value), external_id))
        elif phase == "terminal_eligibility_verified":
            terminal.update(resolved_terminal_disposition="failed", resolved_preclose_heads=step["evidence"]["exact_authority_heads"])
        elif phase == "terminal_checkpoint_committed":
            stable = snapshot["checkpoint"]
            verify_checkpoint(root, stable["manifest"])
            validate_run_root(root, manifest=stable["manifest"], projection=stable["projection"])
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes({"locator": locator,
                       "projection": stable["projection"], "manifest": stable["manifest"]}), key))
        elif phase == "result_committed":
            terminal.update(terminal_closure="committed", run_status="failed")
        db.execute("UPDATE run_terminal_closure SET value=? WHERE run_key=?", (canonical_bytes(terminal), key))


@dataclass(frozen=True)
class TimeoutDelivery:
    """Frozen domain bytes supplied by the Host; no Backend or verifier execution."""

    member_contents: dict
    state_members: dict
    artifact_status: str
    result_semantics: dict


class InterruptedDelivery:
    """Materialize a safe timeout under the original interrupt owner only."""

    def __init__(self, interrupt):
        self.interrupt = interrupt
        self.coordinator, self.worker = interrupt.coordinator, interrupt.worker

    def extend(self, operation, snapshot, plan, value, final):
        from hashlib import sha256
        from pathlib import Path
        from .capabilities import InvocationLeases
        from .coordinator import read_regular
        from .operations import ExternalControl

        owner, opened = operation["operation_id"], snapshot["opened"]
        locator = snapshot["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        early = ("operation_reserved", "interrupt_and_pause_ownership_reserved", "external_final_evidence_verified", "resource_disposition_committed")
        result = {**snapshot, "recoverable_delivery": True, "observer_only": False, "final_digest": value["terminal_evidence_digest"]}
        if operation["phase"] in early:
            return {**result, "steps": plan.steps}
        path = root / (owner + "_timeout_delivery.json")
        cached = self.coordinator.connection.execute("SELECT content,content_digest FROM control_publications WHERE operation_id=? AND phase=? AND path=? ORDER BY producing_epoch DESC LIMIT 1",
            (owner, "canonical_failed_delivery_committed", str(path))).fetchone()
        if cached is not None:
            require(sha256(cached["content"]).hexdigest() == cached["content_digest"], "Frozen timeout bytes changed")
            delivery = loads(cached["content"])
        else:
            adapter = self.interrupt.pause.external_adapter
            require(hasattr(adapter, "prepare_timeout_delivery"), "Missing trusted timeout delivery port")
            proposed = adapter.prepare_timeout_delivery(loads(canonical_bytes({"run_locator": locator, "external": value, "final": final,
                "original_dispatch": operation["reservation"]["exact_external_operation_resolution_tuple"], "target_attempt_id": value["attempt_id"]})))
            require(type(proposed) is TimeoutDelivery, "Untyped timeout delivery")
            delivery = asdict(proposed)
        require(delivery["result_semantics"] == PROTOCOL["state_machines"]["control_operation"]["recoverable_code_consumption_contract"]["result"],
                "Timeout delivery changed its failure semantics")
        from lqcd_agent.artifacts.contracts import CODE_MEMBER_BY_STATE_FIELD
        from lqcd_agent.code_agent.artifacts import timeout_bundle
        from lqcd_agent.code_agent.schemas import validate_manifest, validate_task
        require(type(delivery["member_contents"]) is dict and
                set(delivery["state_members"]) == set(CODE_MEMBER_BY_STATE_FIELD), "Incomplete timeout domain members")
        for name, content in delivery["member_contents"].items():
            relative = Path(name)
            require(not relative.is_absolute() and relative.parts and all(p not in (".", "..") for p in relative.parts) and
                    relative.as_posix() == name and type(content) is str, "Invalid frozen timeout member")
        require(set(delivery["state_members"].values()) <=
                set(delivery["member_contents"]), "Timeout state member is absent")
        directory = root / "code_agent_control" / value["attempt_id"]
        task = validate_task(read_regular(directory / "code_agent_task.json")).value
        manifest = validate_manifest(read_regular(directory / "workspace_manifest.json"), task).value
        receipt = None
        if value["dispatch_receipt_reference"] is not None:
            receipt = read_regular(root / value["dispatch_receipt_reference"])
        expected_members, expected_result = timeout_bundle(task, manifest, value, final,
            dispatch_phase=operation["reservation"]["exact_external_operation_resolution_tuple"]["external_phase"],
            receipt=receipt)
        require(delivery["member_contents"] == {name: raw.decode() for name, raw in expected_members.items()} and
                delivery["artifact_status"] == expected_result["status"] and
                delivery["state_members"] == CODE_MEMBER_BY_STATE_FIELD,
                "Timeout delivery differs from its original canonical evidence")
        text(delivery["artifact_status"])
        delivery_digest = digest(delivery)
        evidence = {"safe_stop_final_evidence": {"value": value, "final": final}, "canonical_failed_code_agent_delivery": delivery,
            "exact_opened_external_result_pause": opened, "precomputed_failed_result_bytes_digest_and_attempt_completion": delivery_digest,
            "trusted_safe_timeout_classification": delivery["result_semantics"]}
        plan.step("canonical_failed_delivery_committed", evidence, branch={"resolved_interrupt_outcome": "recoverable_delivery"})
        plan.steps[-1]["publications"].append({"path": path.name, "content": canonical_bytes(delivery).decode(), "previous": None, "replacement": False})
        identity = {k: opened[k] for k in IDENTITY_FIELDS}
        proof = {"opened": {"execution_head": digest(opened)}, "external_final_digest": value["terminal_evidence_digest"], "delivery_digest": delivery_digest}
        claimed = plan.append("pause", "pause_claimed", **identity, status="claimed", state_digest=digest(snapshot["source"]["state"]),
            operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=len(plan.steps) + 2, proof=proof)
        plan.step("pause_claimed_recorded", {"pause_owner_operation": owner, "producing_lease_epoch": claimed["lease_epoch"]})
        consumed = plan.append("pause", "pause_consumed", **identity, status="consumed", state_digest=digest(snapshot["source"]["state"]),
            operation_id=owner, lease_epoch=operation["lease_epoch"], phase_revision=len(plan.steps) + 2, proof={**proof, "claimed": {"execution_head": digest(claimed)}})
        plan.step("pause_consumed_recorded", {"pause_claim_head": digest(claimed), "single_use_authorization": delivery_digest})
        lifecycle = plan.append("run_lifecycle", "transitioned", from_status="paused", to_status="running", reason_code="operation_timeout",
            operation_id=owner, pause_id=opened["pause_id"], attempt_id=value["attempt_id"], budget_event_id=None)
        plan.step("running_lifecycle_recorded", {"legal_run_lifecycle_edge": lifecycle, "exact_pre_head": digest(consumed)})
        checkpoint = plan.checkpoint("timeout_resumed")
        plan.step("resume_checkpoint_committed", {"consumed_pause_head": digest(consumed), "running_lifecycle_head": digest(lifecycle)}, checkpoint=checkpoint)
        plan.step("interrupted_code_invocation_authorized", {"same_interrupt_winner": owner, "resolved_outcome_recoverable_delivery": True,
            "scheduled_code_attempt": value["attempt_id"], "running_checkpoint_head": checkpoint["manifest"]["checkpoint_head"],
            "canonical_failed_delivery_digest": delivery_digest, "invocation_authorization_and_lease": {"capability_id": "capability_" + owner}})
        result.update(delivery=delivery, delivery_digest=delivery_digest, resumed_checkpoint=checkpoint)
        authorization_phases = operation_variant("resolve_external_interrupt", "recoverable_timeout")["phases"]
        if authorization_phases.index(operation["phase"]) < authorization_phases.index("interrupted_code_invocation_authorized"):
            return {**result, "steps": plan.steps}
        leases, capability_id = InvocationLeases(self.coordinator), "capability_" + owner
        _, capability = leases.get(capability_id)
        if capability["started_intent"] is None:
            require(operation["phase"] == "interrupted_code_invocation_authorized", "Missing original timeout start intent")
            if capability["worker_id"] != self.worker or capability["expires_at"] is None or self.coordinator._time().monotonic_seconds >= capability["expires_at"]:
                capability = leases.acquire(capability_id, self.worker, expected_epoch=capability["invocation_epoch"], lease_seconds=self.interrupt.lease_seconds)
            capability = leases.start_intent(capability_id, self.worker, capability["invocation_epoch"])
        intent = capability["started_intent"]
        require(intent["previous"] == plan.ledger() and capability["authorization"]["canonical_failed_delivery_digest"] == delivery_digest,
                "Timeout start intent differs from its frozen source")
        old_index = canonical_bytes(plan.index).decode()
        if intent.get("interval_record") is not None:
            plan.records.append(intent["interval_record"])
        plan.records.append(intent["record"])
        plan.step("interrupted_code_attempt_started", {"same_interrupt_winner": owner, "exact_code_target_authorization": capability["authorization_digest"],
            "invocation_started_intent": intent, "exact_a02_started_record": intent["record"]})
        plan.index = loads(intent["index"])
        plan.steps[-1]["publications"].append({"path": "artifact_index.json", "previous": old_index, "content": intent["index"], "replacement": True})
        if operation["phase"] == "interrupted_code_invocation_authorized":
            return {**result, "steps": plan.steps}
        completion = capability.get("timeout_completion")
        if completion is None:
            completion = self.freeze_completion(operation, root, delivery, value, plan, capability)
        from base64 import b64decode
        registered = completion["registered_index"]
        plan.step("interrupted_code_result_registered", {"same_interrupt_winner": owner, "a02_started_head": digest(intent["record"]),
            "precomputed_failed_result_bytes_digest_and_attempt_completion": delivery_digest,
            "validated_failed_code_artifact_registration": registered["current"]["code"]})
        publication = completion["artifact_publication"]
        for member in publication["projections"]:
            plan.steps[-1]["publications"].append({"path": member["projection_path"], "content": b64decode(member["content_base64"], validate=True).decode(),
                "previous": None, "replacement": False})
        plan.steps[-1]["publications"].extend([
            {"path": "artifact_history.jsonl", "previous": publication["previous"], "content": publication["content"], "replacement": False},
            {"path": "artifact_index.json", "previous": canonical_bytes(plan.index).decode(), "content": canonical_bytes(registered).decode(), "replacement": True}])
        plan.index = registered
        if completion.get("interval_settlement") is not None:
            plan.records.append(completion["interval_settlement"])
        plan.records.append(completion["finished_record"])
        plan.step("interrupted_code_attempt_finished", {"same_interrupt_winner": owner, "failed_code_artifact_head": registered["artifact_head"],
            "exact_code_attempt_failed_record": completion["finished_record"], "no_outbound_transition": True})
        finished_index = {**registered, "execution_head": digest(completion["finished_record"])}
        plan.steps[-1]["publications"].append({"path": "artifact_index.json", "previous": canonical_bytes(registered).decode(),
            "content": canonical_bytes(finished_index).decode(), "replacement": True})
        plan.index = finished_index
        release = value["consumption_release"] or ExternalControl(self.coordinator).consumption_proof(operation, value, plan.records, plan.index,
            phase_revision=len(plan.steps) + 2)
        plan.step("external_consumption_released", {"external_consumption_release_proof": release,
            "same_consumption_owner_current_epoch": {"operation_id": owner, "lease_epoch": operation["lease_epoch"]}})
        final_checkpoint = plan.checkpoint("timeout_consumed")
        plan.step("interrupted_code_checkpoint_committed", {"failed_code_attempt_head": digest(completion["finished_record"]),
            "failed_code_artifact_head": registered["artifact_head"], "running_lifecycle_head": digest(lifecycle), "consumed_pause_head": digest(consumed)}, checkpoint=final_checkpoint)
        public = {"run_locator": locator, "run_status": "running", "domain_status": "failed", "pause_id": None, "terminal_closure": "not_applicable",
            **{k: final_checkpoint["manifest"][k] for k in ("execution_head", "artifact_head", "checkpoint_head")}}
        plan.step("result_committed", {"exact_public_or_internal_result": public, "final_phase_revision": len(plan.steps) + 2})
        return {**result, "steps": plan.steps, "final_checkpoint": final_checkpoint, "completion": completion}

    def freeze_completion(self, operation, root, delivery, external, plan, capability):
        from hashlib import sha256
        from .capabilities import ArtifactOutput, CodeConsumptionProof, InvocationLeases
        from .coordinator import exclusive_directory, read_regular
        from .execution import replay
        from .records import FIELDS, build_record
        owner = operation["operation_id"]
        require(operation["phase"] == "interrupted_code_attempt_started", "Timeout completion cannot be evaluated twice")
        namespace = root / "attempts" / external["attempt_id"]
        for name, content in delivery["member_contents"].items():
            self.coordinator.freeze_publication(owner, self.worker, operation["lease_epoch"], operation["phase_revision"],
                "interrupted_code_result_registered", namespace / name, content.encode())
        with self.coordinator.transaction() as db:
            self.coordinator.fence(db, owner, self.worker, operation["lease_epoch"], operation["phase_revision"])
            for name in delivery["member_contents"]:
                path = namespace / name
                parent = root
                for part in path.parent.relative_to(root).parts:
                    parent = parent / part
                    exclusive_directory(parent)
                self.coordinator.materialize_publication(db, operation, "interrupted_code_result_registered", path, name="interrupt.timeout_member")
            output = ArtifactOutput("code", tuple(namespace / name for name in delivery["member_contents"]),
                {k: str(namespace / name) for k, name in delivery["state_members"].items()},
                delivery["artifact_status"])
            members = [{"path": str(path.relative_to(root)), "sha256": sha256(read_regular(path)).hexdigest()} for path in output.member_paths]
            proof = CodeConsumptionProof(external["producer_operation_id"], external["terminal_evidence_digest"], external["attempt_id"], digest(members), "failed")
            now = self.coordinator._time()
            index, publication = InvocationLeases._artifact_plan(root, replay(plan.records), plan.index, output, now, code_proof=proof)
            target = plan.records[-1]
            refs = {slot: pointer["artifact_id"] for slot, pointer in index["current"].items() if pointer is not None}
            fields = {k: target[k] for k in FIELDS["attempt"]}
            fields.update(status="failed", output_references={"current_artifact_ids": refs}, error={"type": "OperationTimeout", "message": "Trusted safe timeout"})
            settlement = None
            parent = capability["started_intent"].get("interval_record")
            if parent is not None:
                interval = parent["payload"]
                same_clock = (self.coordinator.clock.epoch_id == interval["clock_epoch_id"] and
                              now.source == interval["start_at"]["source"] and
                              now.wall_seconds >= interval["start_at"]["wall_seconds"] and
                              now.monotonic_seconds >= interval["start_at"]["monotonic_seconds"])
                duration = now.monotonic_seconds - interval["start_at"]["monotonic_seconds"] if same_clock else None
                require(duration is None or duration <= interval["maximum_seconds"],
                        f"Timeout active interval exceeded: observed={duration}, maximum={interval['maximum_seconds']}")
                budget = replay(plan.records).projection.value["budget"]
                position = budget["budget_event_index"] + 1
                settlement = build_record("budget", "active_interval_settled", **operation["request"]["run_locator"],
                    event_index=len(plan.records) + 1, previous_execution_head=digest(target),
                    artifact_head=index["artifact_head"], artifact_event_index=index["revision"], timestamp=now,
                    budget_event_id=f"budget_event_{position:06d}", budget_event_index=position,
                    policy_version="0.1", policy_digest=budget["policy_digest"], payload={
                        **{key: interval[key] for key in ("schema_version", "interval_id", "stage", "attempt_id",
                                                       "producer_operation_id", "owner_operation_id", "clock_epoch_id")},
                        "settlement_operation_id": owner, "lease_epoch": operation["lease_epoch"],
                        "phase_revision": operation["phase_revision"],
                        "end_at": asdict(now) if duration is not None else None, "actual_seconds": duration,
                        "disposition": "actual" if duration is not None else "conservative_maximum",
                        "evidence_digest": digest({"delivery_digest": digest(delivery), "artifact_head": index["artifact_head"]})}).value
            finished = build_record("attempt", "finished", **operation["request"]["run_locator"], event_index=len(plan.records) + 1 + (settlement is not None),
                previous_execution_head=digest(settlement) if settlement is not None else digest(target),
                artifact_head=index["artifact_head"], artifact_event_index=index["revision"], timestamp=now, **fields).value
            completion = {"registered_index": index, "artifact_publication": publication,
                          "interval_settlement": settlement, "finished_record": finished}
            leases = InvocationLeases(self.coordinator)
            revision, value = leases.get("capability_" + owner, db=db)
            require(value["started_intent"] == capability["started_intent"] and value.get("timeout_completion") is None, "Timeout completion already frozen")
            value["timeout_completion"] = completion
            self.coordinator.fence(db, owner, self.worker, operation["lease_epoch"], operation["phase_revision"])
            leases._save(db, "capability_" + owner, revision, value)
        return completion

    def phase(self, db, operation, step, snapshot, *, before):
        from .capabilities import InvocationLeases, authorize_interrupt_capability
        from .checkpoints import verify_checkpoint
        from .coordinator import exclusive_directory, read_regular
        from .integrity import validate_run_root
        from .operations import ExternalControl
        locator, owner = snapshot["run_locator"], operation["operation_id"]
        root, key = self.coordinator.root / locator["case_id"] / locator["run_id"], digest(locator)
        pause_id = snapshot["opened"]["pause_id"]
        row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, pause_id)).fetchone()
        require(row is not None and loads(row[0])["owner"] == owner and
                db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone() is None, "Timeout consumption owner changed")
        value, _ = ExternalControl(self.coordinator).final_evidence(db, snapshot["external_id"])
        require(value["resolution_owner"] == "interrupt" and value["resolution_owner_operation_id"] == owner and
                value["terminal_evidence_digest"] == snapshot["final_digest"], "Timeout final changed")
        if before:
            require(read_regular(root / "execution_history.jsonl").decode() in (step["expected_previous_ledger"], step["expected_ledger"]), "Timeout materialization prefix changed")
            if snapshot.get("completion") is not None:
                from hashlib import sha256
                for member in snapshot["completion"]["artifact_publication"]["projections"]:
                    require(sha256(read_regular(root / member["canonical_path"])).hexdigest() == member["sha256"], "Timeout member changed after freezing")
            if step["target"] == "external_consumption_released":
                final_checkpoint = snapshot["final_checkpoint"]
                validate_run_root(root, manifest=final_checkpoint["manifest"], projection=final_checkpoint["projection"])
            if step["target"] == "interrupted_code_result_registered":
                for item in step["publications"]:
                    parent = root
                    for part in (root / item["path"]).parent.relative_to(root).parts:
                        parent = parent / part
                        exclusive_directory(parent)
            return
        phase = step["target"]
        if phase in ("pause_claimed_recorded", "pause_consumed_recorded"):
            pause = loads(row[0])
            pause["status"] = "claimed" if phase == "pause_claimed_recorded" else "consumed"
            db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?", (canonical_bytes(pause), key, pause_id))
        elif phase in ("resume_checkpoint_committed", "interrupted_code_checkpoint_committed"):
            checkpoint = snapshot["resumed_checkpoint"] if phase == "resume_checkpoint_committed" else snapshot["final_checkpoint"]
            verify_checkpoint(root, checkpoint["manifest"])
            validate_run_root(root, manifest=checkpoint["manifest"], projection=checkpoint["projection"])
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes({"locator": locator,
                "manifest": checkpoint["manifest"], "projection": checkpoint["projection"]}), key))
        elif phase == "interrupted_code_invocation_authorized":
            authority = authorize_interrupt_capability(self.coordinator, db, operation, root, snapshot["resumed_checkpoint"], snapshot["delivery_digest"])
            return {**step["evidence"], "invocation_authorization_and_lease": authority}
        elif phase in ("interrupted_code_attempt_started", "interrupted_code_attempt_finished"):
            leases = InvocationLeases(self.coordinator)
            revision, capability = leases.get("capability_" + owner, db=db)
            capability["started_intent"]["published"] = True
            if phase == "interrupted_code_attempt_finished":
                capability["state"] = "finished"
            leases._save(db, "capability_" + owner, revision, capability)
        elif phase == "external_consumption_released":
            ExternalControl(self.coordinator).release_consumption(db, operation, step["evidence"]["external_consumption_release_proof"])
