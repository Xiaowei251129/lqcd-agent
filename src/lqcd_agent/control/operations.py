"""Guarded ControlOperation lookups over the generated protocol.

These checks validate control structure. Evidence is produced and verified by
trusted phase implementations, never supplied through a public client request.
"""
from dataclasses import asdict, dataclass

from .protocol import PROTOCOL, operation_variant
from .strict_json import ControlIntegrityError, canonical_bytes, closed, digest, digest_value, loads, require, text


CONTROL = PROTOCOL["state_machines"]["control_operation"]


class BootstrapIntegrityError(ControlIntegrityError):
    """A production bootstrap source check failed, not a stale writer fence."""


class TerminalIntegrityError(ControlIntegrityError):
    """A frozen terminal publication source no longer matches its authority."""


@dataclass(frozen=True)
class CloseRunRequest:
    run_locator: dict
    trigger_execution_head: str
    stop_reason: str | None = None


class ExternalControl:
    """Control-side CAS over B03-owned rows in the shared coordinator domain.

    This consumer does not allocate producers, dispatch backends or manufacture
    stop evidence. The backend adapter remains responsible for those actions.
    """

    def __init__(self, coordinator):
        self.coordinator = coordinator

    def read(self, db, external_id):
        text(external_id)
        row = db.execute("SELECT revision,value FROM external_operations WHERE external_operation_id=?", (external_id,)).fetchone()
        require(row is not None, "Unknown ExternalOperation")
        value = loads(row["value"])
        machine = PROTOCOL["state_machines"]["external_operation"]
        require(value["producer_operation_id"] == external_id and value["phase_revision"] == row["revision"],
                "ExternalOperation identity or revision mismatch")
        require(value["operation_phase"] in machine["phases"] and value["operation_status"] in machine["statuses"] and
                (value["resolution_owner"] is None or value["resolution_owner"] in machine["resolution_owner_values"]), "Unknown ExternalOperation state")
        require(value["operation_status"] in machine["phase_statuses"][value["operation_phase"]], "External phase/status mismatch")
        closed(value["run_locator"], ("case_id", "run_id"))
        from .strict_json import number
        number(value["lease_epoch"], integer=True, minimum=1)
        number(value["phase_revision"], integer=True, minimum=1)
        if external_id.startswith("external_"):
            active = value.get("prestart", {}).get("active_time")
            require(active is not None and active["setup_record"]["payload"]["producer_operation_id"] == external_id and
                    digest(active["setup_record"]) == active["setup_record_digest"],
                    "Canonical producer lost its frozen active-time intent")
        return value

    def attached(self, db, locator):
        values = [self.read(db, row[0]) for row in db.execute("SELECT external_operation_id FROM external_operations")]
        return [value for value in values if value["run_locator"] == locator and not self.detached(db, value)]

    def detached(self, db, value):
        if value.get("active_binding_status") != "released":
            require(value.get("close_disposition") is None and value.get("consumption_release") is None, "Release proof without released binding")
            return False
        from .coordinator import read_regular
        from .execution import parse_ledger
        require(value.get("active_binding_generation") == 1, "Unknown external binding generation")
        self.final_evidence(db, value["producer_operation_id"])
        if value.get("consumption_release") is not None:
            proof = value["consumption_release"]
            require(value.get("close_disposition") is None, "Conflicting external release dispositions")
            owner = self.coordinator.get(proof["consumption_operation_id"], db=db)
            history = self.coordinator.history(owner["operation_id"])
            require(any(row["phase"] == "external_consumption_released" and row["evidence"]["external_consumption_release_proof"] == proof
                        for row in history), "External release lacks a committed owner phase")
            locator = value["run_locator"]
            root = self.coordinator.root / locator["case_id"] / locator["run_id"]
            records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
            terminal = next((r for r in records if digest(r) == proof["terminal_code_attempt_head"]), None)
            require(terminal is not None, "Released Code Attempt disappeared")
            release_rows = records[:terminal["event_index"]]
            artifact_rows = [loads(line) for line in read_regular(root / "artifact_history.jsonl").splitlines()]
            require(any(digest(r) == proof["canonical_code_artifact_head"] for r in artifact_rows), "Released Code artifact disappeared")
            expected = self.consumption_proof(owner, value, release_rows, None, phase_revision=proof["phase_revision"],
                                              artifact_head=proof["canonical_code_artifact_head"], epoch=proof["consumption_epoch"])
            require(proof == expected, "External release proof changed")
            return True
        proof = value.get("close_disposition")
        require(proof is not None and value.get("consumption_release") is None, "Missing typed external detachment proof")
        require(proof["external_final_digest"] == value["terminal_evidence_digest"] and proof["binding_generation"] == 1,
                "Detached external proof binding mismatch")
        owner = self.coordinator.get(proof["operation_id"], db=db)
        if proof.get("disposition_kind") == "consumption_failure":
            require(owner["operation_type"] == "resume_run" and owner["request"]["input_kind"] == "external_result" and
                    owner["request"]["run_locator"] == value["run_locator"] and value["resolution_owner"] == "normal",
                    "Wrong consumption failure release owner")
            require(any(row["phase"] == "consumption_failure_disposition_committed" and
                        row["evidence"]["active_binding_failure_release_proof"] == proof for row in self.coordinator.history(owner["operation_id"])),
                    "Failure detachment lacks its exact committed phase")
            locator = value["run_locator"]
            root = self.coordinator.root / locator["case_id"] / locator["run_id"]
            records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
            by_head = {digest(r): r for r in records}
            pause, attempt = (by_head.get(proof[k]) for k in ("pause_disposition_head", "target_disposition_head"))
            require(pause is not None and pause["record_type"] == "pause" and pause["pause_id"] == value["pause_id"] and
                    pause["status"] in ("consumed", "interrupted") and pause["operation_id"] == owner["operation_id"] and
                    attempt is not None and attempt["record_type"] == "attempt" and attempt["attempt_id"] == value["attempt_id"] and
                    attempt["event"] in ("finished", "abandoned"), "Failure release lost its exact terminal dispositions")
            settlements = [by_head.get(head) for head in proof["settlement_heads"]]
            require(all(r is not None and r["record_type"] == "budget" and r["event"] == "resource_settled" for r in settlements) and
                    sum(r["payload"]["resource_operation_id"] == value["reservation_id"] for r in settlements) == 1,
                    "Failure release lacks original resource settlement")
            return True
        require(owner["operation_type"] in ("cancel_pause", "close_run") and owner["request"]["run_locator"] == value["run_locator"], "Detached external owner mismatch")
        if owner["operation_type"] == "close_run":
            require(value["resolution_owner"] == "normal" and any(r["phase"] == "close_source_disposition_committed" and
                    r["evidence"]["pause_target_disposition_and_detachment_or_not_applicable"]["external"] == proof
                    for r in self.coordinator.history(owner["operation_id"])), "Close release lacks its exact committed phase")
        locator = value["run_locator"]
        records = parse_ledger(read_regular(self.coordinator.root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl")).values
        by_head = {digest(record): record for record in records}
        settlement, pause, target = (by_head.get(proof[field]) for field in ("settlement_head", "pause_disposition_head", "target_disposition_head"))
        require(settlement is not None and settlement["record_type"] == "budget" and settlement["event"] == "resource_settled" and
                settlement["payload"]["resource_operation_id"] == value["reservation_id"] and settlement["payload"]["operation_id"] == owner["operation_id"] and
                pause is not None and pause["record_type"] == "pause" and pause["status"] == ("interrupted" if owner["operation_type"] == "close_run" else "cancelled") and pause["operation_id"] == owner["operation_id"] and
                pause["pause_id"] == value["pause_id"] and target is not None and target["record_type"] == "attempt" and target["status"] == "abandoned" and
                target["attempt_id"] == value["attempt_id"], "External detachment lacks exact terminal dispositions")
        return True

    def consumption_proof(self, operation, value, records, index, *, phase_revision, artifact_head=None, epoch=None):
        """Freeze control bindings only after the domain port registered its result."""
        require(operation["request"]["run_locator"] == value["run_locator"], "Wrong external consumption Run")
        if operation["operation_type"] == "resume_run":
            require(operation["operation_variant"] == "continue_execution" and operation["request"]["input_kind"] == "external_result", "Wrong consumption owner")
            frozen = operation["reservation"]["target_prestart_closure"]["external"]["value"]
            resolution = "normal"
        else:
            require(operation["operation_type"] == "resolve_external_interrupt" and operation["operation_variant"] == "recoverable_timeout" and
                    value["resolution_owner_operation_id"] == operation["operation_id"], "Wrong interrupt consumption owner")
            phase = next((r for r in self.coordinator.history(operation["operation_id"]) if r["phase"] == "canonical_failed_delivery_committed"), None)
            require(phase is not None, "Missing canonical timeout delivery")
            frozen = phase["evidence"]["safe_stop_final_evidence"]["value"]
            resolution = "interrupt"
        require(value["resolution_owner"] == resolution and value["proof_kind"] == "safe_stop" and
                value["terminal_evidence_digest"] == frozen["terminal_evidence_digest"] and
                value["producer_operation_id"] == frozen["producer_operation_id"] and value["active_binding_generation"] == frozen["active_binding_generation"],
                "External consumption final identity changed")
        settlement = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled" and
                      r["payload"]["resource_operation_id"] == value["reservation_id"]]
        pauses = [r for r in records if r["record_type"] == "pause" and r["pause_id"] == value["pause_id"]]
        attempts = [r for r in records if r["record_type"] == "attempt" and r["attempt_id"] == value["attempt_id"]]
        require(len(settlement) == 1 and settlement[0]["payload"]["operation_id"] == operation["operation_id"] and
                settlement[0]["payload"]["evidence_digest"] == value["terminal_evidence_digest"] and
                pauses[-1]["status"] == "consumed" and pauses[-1]["operation_id"] == operation["operation_id"] and
                attempts[-1]["event"] == "finished" and attempts[-1]["attempt_kind"] == "code_agent" and
                settlement[0]["event_index"] < pauses[-1]["event_index"] < attempts[-1]["event_index"], "Incomplete external consumption closure")
        if index is not None:
            code = index["current"]["code"]
            require(code is not None and code["attempt_id"] == value["attempt_id"] and
                    attempts[-1]["output_references"]["current_artifact_ids"].get("code") == code["artifact_id"] and
                    attempts[-1]["artifact_head"] == index["artifact_head"], "Missing registered Code result")
            artifact_head = index["artifact_head"]
        digest_value(artifact_head)
        return {"release_kind": "external_consumed", "run_id": value["run_locator"]["run_id"], "external_operation_id": value["producer_operation_id"],
                "external_final_digest": value["terminal_evidence_digest"], "external_resolution_owner": value["resolution_owner"],
                "consumption_operation_id": operation["operation_id"], "consumption_epoch": operation["lease_epoch"] if epoch is None else epoch,
                "phase_revision": phase_revision, "active_binding_generation": value["active_binding_generation"],
                "resource_settlement_digest": digest(settlement[0]), "pause_consumed_head": digest(pauses[-1]),
                "terminal_code_attempt_head": digest(attempts[-1]), "canonical_code_artifact_head": artifact_head}

    def release_consumption(self, db, operation, proof):
        from .coordinator import read_regular
        from .execution import parse_ledger
        value, _ = self.final_evidence(db, proof["external_operation_id"])
        locator = value["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (digest(locator),)).fetchone() is None,
                "Terminal owner blocks external consumption release")
        require(value["active_binding_status"] == "active" and value["consumption_release"] is None and value["close_disposition"] is None,
                "External binding release CAS lost")
        expected = self.consumption_proof(operation, value, parse_ledger(read_regular(root / "execution_history.jsonl")).values,
                                          loads(read_regular(root / "artifact_index.json")), phase_revision=operation["phase_revision"] + 1)
        require(proof == expected, "External consumption proof does not match current heads")
        value.update(active_binding_status="released", consumption_release=proof)
        db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?", (canonical_bytes(value), value["producer_operation_id"]))

    def preparation(self, db, locator, target, records):
        values = self.attached(db, locator)
        require(len(values) == 1, "External Pause requires one exact active binding")
        value = values[0]
        require(value["attempt_id"] == target["attempt_id"] and value["cycle_id"] == target["cycle_id"] and
                value["operation_phase"] == "workspace_materialized" and value["operation_status"] == "reserved" and
                value["resolution_owner"] is None and value["pause_id"] is None and value["pause_binding_digest"] is None,
                "External dependency is not an unbound materialized producer")
        require(self.coordinator._time().monotonic_seconds < value["worker_lease_expires_at"], "External preparation lease expired")
        reservations = [r for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                        r["payload"]["resource_operation_id"] == value["reservation_id"]]
        require(len(reservations) == 1 and digest(reservations[0]) == value["reservation_digest"], "External reservation is not committed")
        payload = reservations[0]["payload"]
        require(payload["resource_kind"] == "code_backend_operation" and payload["producer_operation_id"] == value["producer_operation_id"] and
                payload["attempt_id"] == target["attempt_id"] and payload["workspace_id"] == value["workspace_id"] and
                payload["task_digest"] == value["task_digest"] and payload["workspace_manifest_digest"] == value["workspace_manifest_digest"],
                "External dependency cross-wired with reservation")
        active = value.get("prestart", {}).get("active_time")
        if active is not None:
            setup = [r for r in records if r["record_type"] == "budget" and r["event"] == "active_interval_reserved" and
                     r["payload"]["stage"] == "host_setup" and r["payload"]["producer_operation_id"] == value["producer_operation_id"]]
            require(active["published"] and len(setup) == 1 and setup[0] == active["setup_record"] and
                    digest(setup[0]) == active["setup_record_digest"], "External setup reservation is not committed")
        digest_value(value["operation_contract_digest"])
        return {"producer_operation_id": value["producer_operation_id"], "lease_epoch": value["lease_epoch"],
                "phase_revision": value["phase_revision"], "reservation_digest": value["reservation_digest"],
                "operation_contract_digest": value["operation_contract_digest"]}

    def bind_pause(self, db, dependency, prepared):
        value = self.read(db, dependency["producer_operation_id"])
        binding = {"pause_id": prepared["pause_id"], "prepared_execution_head": digest(prepared),
                   "reservation_digest": dependency["reservation_digest"]}
        if value["pause_id"] is not None:
            require(value["pause_id"] == prepared["pause_id"] and value["pause_binding_digest"] == digest(binding), "External Pause binding conflict")
            return binding
        require(value["operation_phase"] == "workspace_materialized" and value["resolution_owner"] is None and
                value["lease_epoch"] == dependency["lease_epoch"] and value["phase_revision"] == dependency["phase_revision"] and
                value["operation_contract_digest"] == dependency["operation_contract_digest"] and
                value["reservation_digest"] == dependency["reservation_digest"], "External binding CAS lost")
        require(self.coordinator._time().monotonic_seconds < value["worker_lease_expires_at"], "External binding lease expired")
        from .coordinator import boundary
        boundary(self.coordinator.observer, "external.pause_binding", "before", binding)
        prior = value["phase_revision"]
        value.update(operation_phase="pause_bound", phase_revision=prior + 1, pause_id=prepared["pause_id"], pause_binding_digest=digest(binding),
                     active_binding_generation=1, active_binding_status="active", consumption_release=None, close_disposition=None)
        require(db.execute("UPDATE external_operations SET revision=?,value=? WHERE external_operation_id=? AND revision=?",
                           (prior + 1, canonical_bytes(value), value["producer_operation_id"], prior)).rowcount == 1, "External binding CAS lost")
        boundary(self.coordinator.observer, "external.pause_binding", "after", binding)
        return binding

    def final_evidence(self, db, external_id):
        """Verify immutable source bytes and classify all frozen proof dimensions."""
        try:
            return self._final_evidence(db, external_id)
        except (KeyError, TypeError, ValueError, IndexError, OSError) as error:
            raise ControlIntegrityError(str(error)) from error

    def _final_evidence(self, db, external_id):
        from hashlib import sha256
        from .coordinator import read_regular
        value = self.read(db, external_id)
        require(value["operation_phase"] == "external_final_evidence_committed", "External result is not terminal evidence")
        locator = value["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        path = root / value["terminal_evidence_reference"]
        require(path == path.resolve() and path.is_relative_to(root), "External final evidence escaped Run")
        raw = read_regular(path)
        require(sha256(raw).hexdigest() == value["terminal_evidence_digest"], "External final evidence bytes changed")
        proof = loads(raw)
        require(canonical_bytes(proof) == raw, "Noncanonical external final evidence")
        for field in ("producer_operation_id", "run_locator", "attempt_id", "cycle_id", "lease_epoch", "resolution_owner"):
            require(proof[field] == value[field], "External final evidence identity mismatch")
        classifier = PROTOCOL["state_machines"]["external_operation"]["final_proof_classification"]
        dimensions = proof["stop_proof"]
        require(type(dimensions) is dict and set(dimensions) <= set(classifier["dimensions"]), "Unknown external stop dimension")
        termination = dimensions.get("termination_or_not_dispatched")
        if termination == {"tag": "not_dispatched"}:
            require(value.get("dispatch_receipt_reference") is None and value.get("dispatch_receipt_digest") is None,
                    "Not-dispatched proof conflicts with dispatch receipt")
        safe = (termination == "confirmed" or termination == {"tag": "not_dispatched"}) and all(
            dimensions.get(field) is True for field in classifier["dimensions"] if field != "termination_or_not_dispatched")
        kind = "safe_stop" if safe else "unavailable"
        require(value["proof_kind"] == proof["proof_kind"] == kind, "External proof classifier mismatch")
        require(proof["classification_timing"] == classifier["resolution_timing"][value["resolution_owner"]], "External proof timing mismatch")
        require(value["resolution_owner"] != "normal" or kind == "safe_stop", "Normal unavailable evidence is forbidden")
        if value["resolution_owner"] == "normal":
            for field in ("dispatch_receipt", "result"):
                reference = value[field + "_reference"]
                digest_value(value[field + "_digest"])
                member = root / reference
                require(member == member.resolve() and member.is_relative_to(root), "External normal evidence escaped Run")
                require(sha256(read_regular(member)).hexdigest() == value[field + "_digest"], "External normal evidence bytes changed")
                require(proof[field + "_digest"] == value[field + "_digest"], "External final reference binding mismatch")
        if kind == "unavailable":
            require(value["operation_status"] == "recovery_required" and proof.get("quarantine_reference") and
                    proof.get("missing_proof_dimensions"), "Unavailable external evidence lacks quarantine")
        require(any(outcome["resolution_kind"] == value["resolution_owner"] and outcome["proof_kind"] == kind and
                    outcome["interrupt_disposition"] == proof["interrupt_disposition"] and value["operation_status"] in outcome["statuses"]
                    for outcome in PROTOCOL["state_machines"]["external_operation"]["terminal_outcomes"]), "Illegal external terminal tuple")
        return value, proof


class TerminalOperations:
    """Same-coordinator terminal ownership and deterministic bootstrap failure tails."""

    def __init__(self, coordinator, worker_id, lease_seconds):
        self.coordinator = coordinator
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    def closure(self, locator, *, db=None):
        row = (db or self.coordinator.connection).execute(
            "SELECT value FROM run_terminal_closure WHERE run_key=?", (digest(locator),)).fetchone()
        return None if row is None else loads(row[0])

    def close(self, request, actor):
        """Derive the terminal contract from committed authority, not a requested status."""
        from .coordinator import component, read_regular
        from .execution import parse_ledger
        from .integrity import validate_control_root
        from .pause import PauseOperations

        require(type(request) is CloseRunRequest, "Expected trusted CloseRunRequest")
        actor.authorize("control.internal")
        closed(request.run_locator, ("case_id", "run_id"))
        for value in request.run_locator.values():
            component(value)
        digest_value(request.trigger_execution_head)
        require(request.stop_reason in (None, "terminal_operator_stop"), "Unsupported trusted stop reason")
        coordinator, locator = self.coordinator, request.run_locator
        key = digest(locator)
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        with coordinator.transaction() as db:
            existing = self.closure(locator, db=db)
            prior = []
            if existing is None:
                for row in db.execute("SELECT operation_id FROM control_operations WHERE operation_type='close_run'"):
                    candidate = coordinator.get(row[0], db=db)
                    source_request = candidate["request"]
                    trigger = source_request["trigger"]
                    if source_request["run_locator"] == locator and trigger.get("execution_head") == request.trigger_execution_head and (
                            request.stop_reason is None or trigger["kind"] == request.stop_reason):
                        prior.append(candidate)
                require(len(prior) <= 1, "Conflicting reserved terminal triggers")
            if existing is not None:
                trigger = existing["terminal_trigger_reference"]
                require(trigger.get("execution_head") == request.trigger_execution_head and
                        (request.stop_reason is None or trigger["kind"] == request.stop_reason),
                        "Competing terminal trigger")
                operation = coordinator.get(existing["terminal_closure_owner_operation_id"], db=db)
                require(operation["operation_type"] == "close_run", "Terminal source belongs to an embedded owner")
            elif prior:
                # A durable reservation precedes the terminal ownership transaction.
                # Its retry must reach the original fenced failure handler even if
                # the source can no longer be used to admit a new operation.
                operation = prior[0]
            else:
                row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (key,)).fetchone()
                require(row is not None, "Unknown Run")
                control = loads(row["value"])
                state = validate_control_root(coordinator, db, locator, control).value
                require(state["run_status"] in ("running", "paused") and state.get("pending_pause") is None,
                        "Close requires an unowned stable source")
                records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
                trigger_record = records[-1]
                require(digest(trigger_record) == request.trigger_execution_head, "Terminal trigger is not the exact latest head")
                index = loads(read_regular(root / "artifact_index.json"))
                if request.stop_reason is not None:
                    kind, disposition = request.stop_reason, "halted"
                elif trigger_record["record_type"] == "transition" and trigger_record["target_attempt_id"] is None:
                    source_attempt = next(r for r in reversed(records) if r["record_type"] == "attempt")
                    terminal = index["current"]["terminal"]
                    require(trigger_record["source_node"] == "memory_report" and source_attempt["event"] == "finished" and
                            source_attempt["status"] == "succeeded" and terminal is not None and
                            terminal["attempt_id"] == source_attempt["attempt_id"], "END lacks completed terminal artifacts")
                    kind, disposition = "normal_end", "completed"
                elif trigger_record["record_type"] == "attempt" and trigger_record["event"] == "finished":
                    require(trigger_record["status"] == "failed" and trigger_record["error"] is not None,
                            "Runtime failure lacks canonical Attempt evidence")
                    kind, disposition = "non_pause_runtime_failure", "failed"
                else:
                    require(trigger_record["record_type"] == "budget" and trigger_record["event"] == "decision_recorded" and
                            trigger_record["payload"]["decision"] == "halt", "No canonical terminal trigger")
                    kind, disposition = "internal_terminal_decision", "halted"
                attached = ExternalControl(coordinator).attached(db, locator)
                external = None
                opened = next((r for r in reversed(records) if r["record_type"] == "pause"), None)
                if opened is not None and opened["status"] != "opened":
                    opened = None
                if attached:
                    require(request.stop_reason is not None and len(attached) == 1 and opened is not None and
                            opened["reason"] == "external_result", "Close requires one unconsumed normal final")
                    value, final = ExternalControl(coordinator).final_evidence(db, attached[0]["producer_operation_id"])
                    require(value["resolution_owner"] == "normal" and value["proof_kind"] == "safe_stop" and
                            value["pause_id"] == opened["pause_id"] and value["attempt_id"] == opened["target_attempt_id"],
                            "Close cannot stop or rewrite an external producer")
                    target = next(r for r in reversed(records) if r["record_type"] == "attempt" and r["attempt_id"] == value["attempt_id"])
                    require(target["status"] == "scheduled", "Close target is already consumed")
                    reserved = next(r for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                                    r["payload"]["resource_operation_id"] == value["reservation_id"])
                    violation = final.get("proven_policy_violation") is True or final.get("resource_actual") is not None and any(
                        final["resource_actual"][k] > v for k, v in reserved["payload"]["maximum_charge"].items())
                    disposition = "failed" if violation else "halted"
                    external = {"value": value, "final": final, "reservation": reserved}
                    precondition = {"tag": "normal_safe_stop_attached_opened_pause", "external_operation_id": value["producer_operation_id"],
                        "external_final_evidence_digest": value["terminal_evidence_digest"], "external_phase_revision": value["phase_revision"],
                        "external_lease_epoch": value["lease_epoch"], "resolution_owner": "normal", "pause_id": opened["pause_id"],
                        "opened_execution_head": digest(opened), "scheduled_target_attempt": target,
                        "resource_reservation_snapshot": reserved, "trusted_integrity_classification": "proven_violation" if violation else "clear",
                        "precomputed_settlement_and_pause_target_disposition": {"actual": final.get("resource_actual"), "pause_status": "interrupted", "target_status": "abandoned"}}
                else:
                    precondition = PauseOperations(coordinator, self.worker_id, self.lease_seconds)._external_absence(db, locator)
                    prior_external = [ExternalControl(coordinator).read(db, r[0]) for r in db.execute("SELECT external_operation_id FROM external_operations")]
                    detached = [v for v in prior_external if v["run_locator"] == locator]
                    precondition.update(tag="safely_terminal_and_detached" if detached else "absent", detached=detached)
                if opened is not None:
                    require(request.stop_reason is not None, "Paused closure requires a trusted stop trigger")
                    ownership = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, opened["pause_id"])).fetchone()
                    require(ownership is not None and loads(ownership[0])["status"] == "opened" and loads(ownership[0])["owner"] is None,
                            "Close source Pause already has an owner")
                reservations = {r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved"}
                settled = {r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"}
                require(reservations - settled == ({external["value"]["reservation_id"]} if external else set()),
                        "Terminal source has unrelated unsettled resources")
                heads = {name: state[name] for name in ("execution_head", "artifact_head", "checkpoint_head")}
                heads["policy_digest"] = state["budget"]["policy_digest"]
                trigger = {"kind": kind, "execution_head": request.trigger_execution_head,
                           "run_locator": locator, "record": trigger_record}
                source = {"tag": "appendable", "last_trusted_heads": heads, "records": records,
                          "previous_index": canonical_bytes(index).decode(), "artifact_index": index,
                          "artifact_history_present": True, "artifact_history": read_regular(root / "artifact_history.jsonl").decode(),
                          "policy": loads(read_regular(root / "budget_policy.json")), "source_control_revision": row["revision"],
                          "opened": opened, "external": external, "state": state}
                canonical = {"run_locator": locator, "trigger": trigger, "trigger_digest": digest(trigger),
                             "disposition": disposition, "source": source, "policy_digest": heads["policy_digest"]}

                def reserve(operation_id, stamp):
                    return {"run_terminal_closure_key": key, "terminal_trigger_identity": trigger,
                            "requested_terminal_disposition": disposition, "external_operation_precondition": precondition["tag"],
                            "external_operation_precondition_proof_digest": digest(precondition),
                            "terminal_disposition_contract_digest": digest({"trigger": digest(trigger), "disposition": disposition}),
                            "close_source_snapshot": {"precondition": precondition, "source": source}}

                operation = coordinator.reserve_in_transaction(
                    db, "close_run", "not_applicable", "internal_terminal", digest(canonical), canonical,
                    self.worker_id, reserve, lease_seconds=self.lease_seconds,
                    build_snapshot=lambda op: self._close_snapshot(op, source))
        return self.continue_close(operation["operation_id"])

    def fail_bootstrap(self, operation, error):
        """Freeze the failure and its dependent close reservation in one transaction."""
        from .coordinator import MaterializationSnapshotError, read_regular

        coordinator = self.coordinator
        operation_id = operation["operation_id"]
        with coordinator.transaction() as db:
            operation = coordinator.failed_operation(db, operation, self.worker_id, error)
            if isinstance(error, MaterializationSnapshotError):
                require(error.operation_id == operation_id, "Foreign materialization failure")
                if error.missing:
                    return coordinator.interrupt(db, operation, "recovery_required", {
                        "kind": "missing_materialization_snapshot", "source_operation_id": operation_id,
                        "source_phase_revision": operation["phase_revision"], "lease_epoch": operation["lease_epoch"]})
            try:
                snapshot = coordinator.snapshot(operation_id, db=db)
            except MaterializationSnapshotError:
                snapshot = None
            reserved = operation["reservation"]
            locator = reserved.get("reserved_run_locator", reserved.get("reserved_child_run_locator"))
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            # Observed bytes describe the violation, never an authoritative head.
            observed = {}
            from hashlib import sha256
            for name in ("execution_history.jsonl", "artifact_history.jsonl", "artifact_index.json", "budget_policy.json"):
                path = root / name
                if path.is_file() and not path.is_symlink() and root == root.resolve():
                    observed[name] = sha256(read_regular(path)).hexdigest()
                else:
                    observed[name] = None
            trigger = {"kind": "non_pause_runtime_failure", "source_operation_id": operation_id,
                       "source_phase_revision": operation["phase_revision"], "run_locator": locator,
                       "violation": str(error), "observed_digests": observed}
            if snapshot is None:
                trusted = db.execute("SELECT value FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone()
                state = loads(trusted[0])["projection"] if trusted is not None else None
                source = {"tag": "unavailable_by_construction", "last_trusted_heads": {
                    name: state.get(name) if state is not None else None for name in ("execution_head", "artifact_head", "checkpoint_head")}}
                source["last_trusted_heads"]["policy_digest"] = reserved.get("budget_policy_digest", reserved.get("child_policy_digest"))
            else:
                source = self._bootstrap_source(root, operation, snapshot)
            proof = {"kind": "bootstrap_integrity_failure", "trigger": trigger,
                     "trigger_digest": digest(trigger), "source": source}
            request = {"run_locator": locator, "trigger": trigger, "trigger_digest": digest(trigger),
                       "disposition": "failed", "source": source,
                       "policy_digest": reserved.get("budget_policy_digest", reserved.get("child_policy_digest"))}
            precondition = {"tag": "absent", "source_operation_id": operation_id,
                            "bootstrap_never_activated": True}
            require(self.closure(locator, db=db) is None, "Bootstrap already has terminal ownership")

            def reserve(close_id, stamp):
                return {"run_terminal_closure_key": digest(locator), "terminal_trigger_identity": trigger,
                        "requested_terminal_disposition": "failed", "external_operation_precondition": "absent",
                        "external_operation_precondition_proof_digest": digest(precondition),
                        "terminal_disposition_contract_digest": digest({"trigger": digest(trigger), "disposition": "failed"}),
                        "close_source_snapshot": {"precondition": precondition, "source": source}}

            close = coordinator.reserve_in_transaction(
                db, "close_run", "not_applicable", "internal_terminal", digest(request), request,
                self.worker_id, reserve, lease_seconds=self.lease_seconds,
                build_snapshot=lambda op: self._close_snapshot(op, source))
            proof["close_operation_id"] = close["operation_id"]
            if db.execute("SELECT 1 FROM run_controls WHERE run_key=?", (digest(locator),)).fetchone() is None:
                db.execute("INSERT INTO run_controls VALUES (?,?,?)",
                           (digest(locator), 1, canonical_bytes({"locator": locator, "projection": None, "manifest": None})))
            coordinator.interrupt(db, operation, "failed", proof)
            coordinator.fence(db, close["operation_id"], self.worker_id, close["lease_epoch"], close["phase_revision"])
        return self.continue_close(close["operation_id"])

    def fail_advance(self, operation, error):
        """Quarantine an owned advance and close only its validated control prefix."""
        from .coordinator import read_regular
        from .integrity import validate_advanced_run_root
        from .pause import PauseOperations

        coordinator = self.coordinator
        operation_id = operation["operation_id"]
        with coordinator.transaction() as db:
            operation = coordinator.failed_operation(db, operation, self.worker_id, error)
            snapshot = coordinator.snapshot(operation_id, db=db)
            locator = snapshot["run_locator"]
            key = digest(locator)
            row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (key,)).fetchone()
            control = loads(row["value"])
            proof = {"kind": "advance_integrity_failure", "source_phase_revision": operation["phase_revision"], "violation": str(error)}
            if control.get("advance_owner") != operation_id or self.closure(locator, db=db) is not None:
                return coordinator.interrupt(db, operation, "failed", proof)
            heads = {key: control["projection"][key] for key in ("execution_head", "artifact_head", "checkpoint_head")}
            heads["policy_digest"] = snapshot["policy"]["policy_digest"]
            source = {"tag": "unavailable_by_construction", "last_trusted_heads": heads}
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            precondition = {"tag": "absent", "source_operation_id": operation_id, "advance_never_activated": True}
            try:
                require(read_regular(root / "execution_history.jsonl") ==
                        b"".join(canonical_bytes(r) + b"\n" for r in snapshot["records"]), "Advance source is not its frozen completed Transition")
                state = validate_advanced_run_root(root, manifest=snapshot["manifest"], projection=snapshot["projection"]).value
                require(state["run_status"] == "running" and state.get("active_pause") is None and state.get("pending_pause") is None,
                        "Advance has an unresolved Pause")
                precondition = {"tag": "absent", **PauseOperations(coordinator, self.worker_id, self.lease_seconds)._external_absence(db, locator)}
                detached = [ExternalControl(coordinator).read(db, r[0]) for r in db.execute("SELECT external_operation_id FROM external_operations")]
                detached = [value for value in detached if value["run_locator"] == locator]
                if detached:
                    precondition.update(tag="safely_terminal_and_detached", detached=detached)
                reservations = {r["payload"]["resource_operation_id"] for r in snapshot["records"] if r["record_type"] == "budget" and r["event"] == "resource_reserved"}
                settled = {r["payload"]["resource_operation_id"] for r in snapshot["records"] if r["record_type"] == "budget" and r["event"] == "resource_settled"}
                require(reservations == settled, "Advance has unsettled resources")
                require(not any(loads(r[0]).get("started_intent") is not None for r in db.execute(
                    "SELECT value FROM invocation_capabilities WHERE capability_id=?", ("capability_" + operation_id,))), "Advance target start is uncertain")
                index = loads(read_regular(root / "artifact_index.json"))
                source = {"tag": "appendable", "last_trusted_heads": {**heads, **{key: state[key] for key in heads if key != "policy_digest"}}, "records": snapshot["records"],
                          "previous_index": canonical_bytes(index).decode(), "artifact_index": index,
                          "artifact_history_present": True, "artifact_history": read_regular(root / "artifact_history.jsonl").decode(),
                          "policy": snapshot["policy"], "source_control_revision": row["revision"],
                          "preserve_scheduled_target": True, "state": state}
            except (ControlIntegrityError, OSError, ValueError):
                pass
            trigger = {"kind": "non_pause_runtime_failure", "source_operation_id": operation_id,
                       "source_phase_revision": operation["phase_revision"], "run_locator": locator, "cause": proof}
            request = {"run_locator": locator, "trigger": trigger, "trigger_digest": digest(trigger),
                       "disposition": "failed", "source": source, "policy_digest": snapshot["policy"]["policy_digest"]}

            def reserve(close_id, stamp):
                return {"run_terminal_closure_key": key, "terminal_trigger_identity": trigger,
                        "requested_terminal_disposition": "failed", "external_operation_precondition": precondition["tag"],
                        "external_operation_precondition_proof_digest": digest(precondition),
                        "terminal_disposition_contract_digest": digest({"trigger": digest(trigger), "disposition": "failed"}),
                        "close_source_snapshot": {"precondition": precondition, "source": source}}

            close = coordinator.reserve_in_transaction(db, "close_run", "not_applicable", "internal_terminal", digest(request), request,
                self.worker_id, reserve, lease_seconds=self.lease_seconds, build_snapshot=lambda op: self._close_snapshot(op, source))
            coordinator.interrupt(db, operation, "failed", {**proof, "close_operation_id": close["operation_id"]})
        self.continue_close(close["operation_id"])
        return coordinator.get(operation_id)

    @staticmethod
    def _bootstrap_source(root, operation, snapshot):
        from .checkpoints import verify_checkpoint
        from .coordinator import read_regular
        from .execution import parse_ledger
        from .integrity import validate_run_root

        reserved = operation["reservation"]
        child = operation["operation_type"] in ("replay_run", "fork_run")
        canonical_policy = reserved["canonical_child_policy_bytes"] if child else reserved["canonical_budget_policy_bytes"]
        last_trusted = {"execution_head": None, "artifact_head": None, "checkpoint_head": None,
                        "policy_digest": reserved["child_policy_digest"] if child else reserved["budget_policy_digest"]}
        phases = operation_variant(operation["operation_type"], "not_applicable")["phases"]
        phase_index = phases.index(operation["phase"])
        prefix = "child_" if child else ""
        count = {prefix + "run_ledger_started": 1, prefix + "bootstrap_records_complete": 7 if child else 6,
                 prefix + "running_lifecycle_recorded": 8 if child else 7}
        if child:
            count["child_lineage_recorded"] = 2
        count = dict(sorted(count.items(), key=lambda item: phases.index(item[0])))
        for phase, number in count.items():
            if phase_index >= phases.index(phase):
                last_trusted["execution_head"] = digest(snapshot["records"][number - 1])
        if phase_index >= phases.index(prefix + "checkpoint_committed"):
            last_trusted["checkpoint_head"] = snapshot["manifest"]["checkpoint_head"]
        try:
            require(root == root.resolve(), "Escaped bootstrap root")
            require(read_regular(root / "budget_policy.json") == canonical_policy.encode(), "Untrusted policy")
            ledger = read_regular(root / "execution_history.jsonl")
            parsed = parse_ledger(ledger)
            actual = parsed.values
            require(actual == snapshot["records"][:len(actual)] and 1 <= len(actual) <= len(snapshot["records"]),
                    "No exact validated bootstrap prefix")
            artifact_path = root / "artifact_history.jsonl"
            artifact_bytes = read_regular(artifact_path) if artifact_path.exists() else None
            require(artifact_bytes == b"" or (artifact_bytes is None and len(actual) < (7 if child else 6) and
                    phase_index < phases.index(prefix + "bootstrap_records_complete")), "Foreign or missing bootstrap artifacts")
            inputs = snapshot["child"]["root_inputs"] if child else operation["request"]["root_inputs"]
            for name, expected in inputs.items():
                require(read_regular(root / (name + ".json")) == canonical_bytes(expected), "Untrusted root input")
            index = root / "artifact_index.json"
            previous_index = read_regular(index) if index.exists() else None
            require(previous_index is None or previous_index == canonical_bytes(snapshot["artifact_index"]),
                    "Untrusted artifact projection")
            if phase_index >= phases.index(prefix + "checkpoint_committed"):
                verify_checkpoint(root, snapshot["manifest"])
                validate_run_root(root, manifest=snapshot["manifest"], projection=snapshot["projection"])
            return {"tag": "appendable", "last_trusted_heads": last_trusted,
                    "records": parsed.values, "previous_index": previous_index.decode() if previous_index is not None else None,
                    "artifact_history_present": artifact_bytes is not None,
                    "policy": loads(canonical_policy),
                    "artifact_index": {**snapshot["artifact_index"], "execution_head": digest(actual[-1])}}
        except (ControlIntegrityError, OSError, ValueError):
            return {"tag": "unavailable_by_construction", "last_trusted_heads": last_trusted}

    @staticmethod
    def _close_snapshot(operation, source):
        from .checkpoints import checkpoint_payload
        from .clock import Timestamp
        from .execution import replay
        from .projections import attach_checkpoint, bounded_projection, checkpoint_manifest
        from .records import FIELDS, build_record

        if source["tag"] == "unavailable_by_construction":
            return {"source": source}
        records = list(source["records"])
        stamp = Timestamp(**operation["created_at"])
        locator = operation["request"]["run_locator"]

        def append(kind, event, **fields):
            records.append(build_record(kind, event, **locator, event_index=len(records) + 1,
                                        previous_execution_head=digest(records[-1]), artifact_head=source["artifact_index"]["artifact_head"],
                                        artifact_event_index=source["artifact_index"]["revision"], timestamp=stamp, **fields).value)

        external, opened = source.get("external"), source.get("opened")
        settlement = {"tag": "not_applicable"}
        if external is not None:
            value, final, reserved = (external[k] for k in ("value", "final", "reservation"))
            budget_index = max(r["budget_event_index"] for r in records if r["record_type"] == "budget") + 1
            append("budget", "resource_settled", budget_event_id=f"budget_event_{budget_index:06d}", budget_event_index=budget_index,
                   policy_version=reserved["policy_version"], policy_digest=reserved["policy_digest"], payload={
                       "resource_operation_id": value["reservation_id"], "actual": final.get("resource_actual"),
                       "tokens": {"state": "unknown", "value": None}, "cost": {"state": "unknown", "value": None},
                       "evidence_digest": value["terminal_evidence_digest"], "operation_id": operation["operation_id"],
                       "lease_epoch": operation["lease_epoch"], "phase_revision": 3})
            settlement = records[-1]
        resource_records = list(records)
        pause_disposition = {"tag": "not_applicable"}
        if opened is not None:
            from .pause import IDENTITY_FIELDS
            append("pause", "pause_interrupted", **{key: opened[key] for key in IDENTITY_FIELDS}, status="interrupted",
                   state_digest=digest(source["state"]), operation_id=operation["operation_id"], lease_epoch=operation["lease_epoch"],
                   phase_revision=4, proof={"opened": {"execution_head": digest(opened)}, "terminal_trigger": operation["request"]["trigger_digest"]})
            pause_disposition = records[-1]
        target = next((row for row in reversed(records) if row["record_type"] == "attempt"), None)
        disposition = {"tag": "not_applicable"}
        if target is not None and target["status"] == "scheduled" and not source.get("preserve_scheduled_target", False):
            fields = {key: target[key] for key in FIELDS["attempt"]}
            fields["status"] = "abandoned"
            append("attempt", "abandoned", **fields)
            disposition = records[-1]
        disposition_records = list(records)
        from_status = replay(source["records"]).projection.value["run_status"]
        append("run_lifecycle", "transitioned", from_status=from_status, to_status=operation["request"]["disposition"],
               reason_code=operation["request"]["trigger"]["kind"], operation_id=operation["operation_id"],
               attempt_id=None, pause_id=opened["pause_id"] if opened else None, budget_event_id=settlement.get("budget_event_id"))
        execution = replay(records)
        index = {**source["artifact_index"], "execution_head": execution.projection.value["execution_head"]}
        core = bounded_projection(execution, artifact_index=index, artifact_head=index["artifact_head"], artifact_event_index=index["revision"])
        checkpoint_id = operation["operation_id"] + "_terminal"
        checkpoint = checkpoint_payload(checkpoint_id, core, stamp, operation_id=operation["operation_id"])
        manifest = checkpoint_manifest(execution, artifact_head=index["artifact_head"], artifact_event_index=index["revision"], checkpoint_id=checkpoint_id,
                                       checkpoint_digest=digest(checkpoint), state_digest=core.digest).value
        release = {"tag": "not_applicable"}
        if external is not None:
            release = {"operation_id": operation["operation_id"], "binding_generation": external["value"]["active_binding_generation"],
                       "external_final_digest": external["value"]["terminal_evidence_digest"], "settlement_head": digest(settlement),
                       "pause_disposition_head": digest(pause_disposition), "target_disposition_head": digest(disposition)}
        return {"source": source, "resource_records": resource_records, "settlement": settlement, "pause_disposition": pause_disposition,
                "release": release, "disposition_records": disposition_records, "target_disposition": disposition, "records": records,
                "artifact_index": index, "manifest": manifest, "checkpoint": checkpoint,
                "projection": attach_checkpoint(core, execution, manifest).value}

    def continue_close(self, operation_id):
        from .checkpoints import persist_checkpoint, verify_checkpoint
        from .coordinator import MaterializationSnapshotError, exclusive_directory, publish_exact, replace_projection
        from .integrity import validate_run_root

        coordinator = self.coordinator
        operation = coordinator.get(operation_id)
        require(operation["operation_type"] == "close_run", "Expected close operation")
        if operation["status"] != "in_progress":
            return operation
        now = coordinator._time()
        if now.monotonic_seconds >= operation["lease_expires"]:
            operation = coordinator.acquire(operation_id, self.worker_id, lease_seconds=self.lease_seconds)
        elif operation["worker_owner_id"] != self.worker_id:
            return operation
        try:
            snapshot = coordinator.snapshot(operation_id)
        except MaterializationSnapshotError as error:
            return coordinator.quarantine_plan(operation, self.worker_id, error)
        source = snapshot["source"]
        disposition = operation["request"]["disposition"]
        locator = operation["request"]["run_locator"]
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        key = digest(locator)
        declaration = operation_variant("close_run", "not_applicable")
        ledger = lambda records: b"".join(canonical_bytes(row) + b"\n" for row in records)
        while operation["status"] == "in_progress":
            if operation["phase"] == "terminal_ownership_reserved" and source["tag"] == "unavailable_by_construction":
                with coordinator.transaction() as db:
                    operation = coordinator.interrupt(db, operation, "failed", {
                        "kind": "run_authority_unavailable", "trigger_digest": operation["request"]["trigger_digest"],
                        "last_trusted_heads": source["last_trusted_heads"]})
                break
            phase = next(target for old, target in declaration["success_edges"] if old == operation["phase"])
            plans = []
            if phase == "resource_disposition_committed" and source.get("external") is not None:
                plans = [(root / "execution_history.jsonl", ledger(snapshot["resource_records"]), ledger(source["records"]))]
            elif phase == "close_source_disposition_committed":
                plans = [(root / "execution_history.jsonl", ledger(snapshot["disposition_records"]), ledger(snapshot["resource_records"]))]
                if not source["artifact_history_present"]:
                    plans.append((root / "artifact_history.jsonl", b"", None))
            elif phase == "terminal_lifecycle_recorded":
                plans = [(root / "execution_history.jsonl", ledger(snapshot["records"]), ledger(snapshot["disposition_records"]))]
            elif phase == "terminal_checkpoint_committed":
                plans = [(root / "checkpoints" / (snapshot["manifest"]["checkpoint_id"] + ".json"),
                          canonical_bytes(snapshot["manifest"]), None)]
            def publish(db, current):
                if phase == "terminal_ownership_reserved":
                    require(self.closure(locator, db=db) is None, "Competing Run terminal owner")
                    if "source_control_revision" in source:
                        row = db.execute("SELECT revision FROM run_controls WHERE run_key=?", (key,)).fetchone()
                        require(row is not None and row[0] == source["source_control_revision"], "Terminal source revision changed")
                        self._verify_close_inputs(root, snapshot, current, phase)
                    self._close_ownership(db, current, snapshot, acquire=True)
                    value = {"terminal_closure_revision": 1, "terminal_closure_owner_operation_id": operation_id,
                             "terminal_trigger_reference": current["request"]["trigger"],
                             "terminal_trigger_digest": current["request"]["trigger_digest"],
                             "terminal_request_digest": current["request_digest"],
                             "terminal_disposition_contract": {"run_status": disposition},
                             "terminal_preclose_contract": source, "resolved_terminal_disposition": None,
                             "resolved_preclose_heads": None, "terminal_closure": "pending", "run_status": None}
                    db.execute("INSERT INTO run_terminal_closure VALUES (?,?,?)", (key, 1, canonical_bytes(value)))
                    db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (key,))
                    return {"deterministic_terminal_trigger": current["request"]["trigger"],
                            "empty_run_terminal_owner_cas": {"run_key": key, "revision": 1, "owner": operation_id},
                            "terminal_resolution_contracts": current["reservation"]["terminal_disposition_contract_digest"],
                            "close_source_snapshot": current["reservation"]["close_source_snapshot"],
                            "atomic_pause_run_owner_cas": {"run_owner": operation_id, "pause": source.get("opened") or {"tag": "not_applicable"}},
                            "normal_final_read_only_or_not_applicable": source.get("external") or {"tag": "not_applicable"}}
                closure = self.closure(locator, db=db)
                require(closure is not None and closure["terminal_closure_owner_operation_id"] == operation_id and
                        closure["terminal_closure"] == "pending", "Terminal owner fence failed")
                self._verify_close_inputs(root, snapshot, current, phase)
                self._close_ownership(db, current, snapshot, acquire=False)
                if phase == "terminal_checkpoint_committed":
                    exclusive_directory(root / "checkpoints")
                for path, _, _ in plans:
                    coordinator.materialize_publication(db, current, phase, path, name="close." + path.name)
                if phase == "resource_disposition_committed":
                    return {"resource_settlement_or_not_applicable": snapshot["settlement"]}
                if phase == "close_source_disposition_committed":
                    opened, external = source.get("opened"), source.get("external")
                    if opened is not None:
                        pause_row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, opened["pause_id"])).fetchone()
                        pause = loads(pause_row[0])
                        pause["status"] = "interrupted"
                        db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?",
                                   (canonical_bytes(pause), key, opened["pause_id"]))
                    if external is not None:
                        value = ExternalControl(coordinator).read(db, external["value"]["producer_operation_id"])
                        require(value["active_binding_status"] == "active" and value["close_disposition"] is None and value["consumption_release"] is None,
                                "Close detachment CAS lost")
                        value.update(active_binding_status="released", close_disposition=snapshot["release"])
                        db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?",
                                   (canonical_bytes(value), value["producer_operation_id"]))
                    return {"close_source_snapshot": current["reservation"]["close_source_snapshot"],
                            "same_close_owner": operation_id, "resource_settlement_or_not_applicable": snapshot["settlement"],
                            "pause_target_disposition_and_detachment_or_not_applicable": {
                                "target_disposition_record": snapshot["target_disposition"],
                                "pause": snapshot["pause_disposition"], "external": snapshot["release"]}}
                if phase == "terminal_eligibility_verified":
                    from .coordinator import read_regular
                    require(read_regular(root / "execution_history.jsonl") == ledger(snapshot["disposition_records"]),
                            "Terminal preclose execution head changed")
                    require(read_regular(root / "artifact_history.jsonl") == source.get("artifact_history", "").encode(), "Terminal preclose artifacts changed")
                    require(digest(loads(read_regular(root / "budget_policy.json"))) ==
                            digest(policy_for_source(source)), "Terminal policy changed")
                    require(closure["resolved_terminal_disposition"] is None, "Terminal disposition already resolved")
                    heads = {"execution_head": digest(snapshot["disposition_records"][-1]), "artifact_head": source["artifact_index"]["artifact_head"],
                             "checkpoint_head": source["last_trusted_heads"]["checkpoint_head"],
                             "policy_digest": current["request"]["policy_digest"]}
                    closure.update(resolved_terminal_disposition=disposition, resolved_preclose_heads=heads)
                    db.execute("UPDATE run_terminal_closure SET value=? WHERE run_key=?", (canonical_bytes(closure), key))
                    return {"final_terminal_evidence": current["request"]["trigger"], "exact_authority_heads": heads,
                            "single_assignment_resolution": {"run_status": disposition, "owner": operation_id}}
                if phase == "terminal_lifecycle_recorded":
                    require(closure["resolved_terminal_disposition"] == disposition, "Unresolved terminal lifecycle")
                    return {"terminal_owner": operation_id, "terminal_closure_revision": 1,
                            "resolved_terminal_disposition": disposition,
                            "terminal_disposition_contract_digest": current["reservation"]["terminal_disposition_contract_digest"],
                            "legal_terminal_lifecycle_edge": snapshot["records"][-1]}
                if phase == "terminal_checkpoint_committed":
                    previous = source["previous_index"]
                    if previous is None:
                        publish_exact(root / "artifact_index.json", canonical_bytes(snapshot["artifact_index"]), observer=coordinator.observer)
                    else:
                        replace_projection(root / "artifact_index.json", previous.encode(), canonical_bytes(snapshot["artifact_index"]),
                                           observer=coordinator.observer)
                    persist_checkpoint(coordinator, db, current, root, snapshot["checkpoint"],
                                       {"source": "input", "step": 0, "parents": {}, "operation_id": operation_id})
                    verify_checkpoint(root, snapshot["manifest"])
                    validate_run_root(root, manifest=snapshot["manifest"], projection=snapshot["projection"])
                    db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?",
                               (canonical_bytes({"locator": locator, "projection": snapshot["projection"], "manifest": snapshot["manifest"]}), key))
                    return {"terminal_lifecycle_resulting_head": snapshot["manifest"]["execution_head"],
                            "empty_active_pause_projection": {"pause_id": None, "checkpoint_head": snapshot["manifest"]["checkpoint_head"]}}
                require(phase == "result_committed", "Unknown close phase")
                verify_checkpoint(root, snapshot["manifest"])
                validate_run_root(root, manifest=snapshot["manifest"], projection=snapshot["projection"])
                closure.update(terminal_closure="committed", run_status=disposition)
                db.execute("UPDATE run_terminal_closure SET value=? WHERE run_key=?", (canonical_bytes(closure), key))
                return {"final_phase_revision": current["phase_revision"] + 1, "exact_public_or_internal_result": {
                    "run_locator": locator, "run_status": disposition, "terminal_closure": "committed",
                    "execution_head": snapshot["manifest"]["execution_head"], "artifact_head": snapshot["manifest"]["artifact_head"],
                    "checkpoint_head": snapshot["manifest"]["checkpoint_head"], "pause_id": None, "domain_status": None}}

            try:
                for path, content, previous in plans:
                    coordinator.freeze_publication(operation_id, self.worker_id, operation["lease_epoch"],
                                                   operation["phase_revision"], phase, path, content, previous=previous)
                operation = coordinator.step(operation_id, self.worker_id, operation["lease_epoch"],
                                             operation["phase_revision"], phase, publish)
            except (ControlIntegrityError, OSError, ValueError) as error:
                with coordinator.transaction() as db:
                    # Recheck this worker's original fence; a stale worker cannot
                    # terminalize a successor or change the winning Run owner.
                    coordinator.fence(db, operation_id, self.worker_id, operation["lease_epoch"], operation["phase_revision"])
                    operation = coordinator.interrupt(db, operation, "failed", {
                        "kind": "terminal_integrity_failure", "violation": str(error),
                        "trigger_digest": operation["request"]["trigger_digest"]})
        return operation

    def _close_ownership(self, db, operation, snapshot, *, acquire):
        source, owner = snapshot["source"], operation["operation_id"]
        locator = operation["request"]["run_locator"]
        opened, external = source.get("opened"), source.get("external")
        if external is not None:
            value, final = ExternalControl(self.coordinator).final_evidence(db, external["value"]["producer_operation_id"])
            expected = external["value"]
            require(final == external["final"] and all(value.get(k) == expected.get(k) for k in (
                "phase_revision", "lease_epoch", "resolution_owner", "resolution_owner_operation_id", "terminal_evidence_digest", "active_binding_generation")),
                "Normal final changed during close")
            released = operation["phase"] in ("close_source_disposition_committed", "terminal_eligibility_verified", "terminal_lifecycle_recorded", "terminal_checkpoint_committed")
            require(value["active_binding_status"] == ("released" if released else "active") and value["consumption_release"] is None and
                    value["close_disposition"] == (snapshot["release"] if released else None), "Close external binding changed")
        if opened is not None:
            key = digest(locator)
            row = db.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?", (key, opened["pause_id"])).fetchone()
            require(row is not None, "Missing close Pause ownership")
            pause = loads(row[0])
            require(pause["owner"] == (None if acquire else owner) and pause["opened_head"] == digest(opened), "Close Pause owner CAS lost")
            require(pause["status"] in (("opened",) if acquire else ("opened", "interrupted")), "Close Pause was consumed")
            if acquire:
                pause["owner"] = owner
                db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=? AND pause_id=?", (canonical_bytes(pause), key, opened["pause_id"]))

    @staticmethod
    def _verify_close_inputs(root, snapshot, operation, next_phase):
        """Accept only the current exact prefix or its precomputed immediate suffix."""
        from hashlib import sha256
        from .coordinator import read_regular

        try:
            require(root == root.resolve(), "Terminal root escaped")
            source = snapshot["source"]
            require(read_regular(root / "budget_policy.json") == canonical_bytes(policy_for_source(source)), "Terminal policy changed")
            artifact_path = root / "artifact_history.jsonl"
            artifact_bytes = read_regular(artifact_path) if artifact_path.exists() else None
            before_artifact_publication = operation["phase"] in ("terminal_ownership_reserved", "resource_disposition_committed")
            require(artifact_bytes == source.get("artifact_history", "").encode() or (not source["artifact_history_present"] and artifact_bytes is None and before_artifact_publication),
                    "Terminal artifacts changed")
            for field in ("root_goal_reference", "input_snapshot_reference"):
                reference = source["records"][0][field]
                require(sha256(read_regular(root / reference["reference"])).hexdigest() == reference["sha256"],
                        "Terminal root input changed")
            phases = operation_variant("close_run", "not_applicable")["phases"]
            current = phases.index(operation["phase"])
            candidates = [source["records"]]
            if current >= phases.index("resource_disposition_committed"):
                candidates = [snapshot["resource_records"]]
            if next_phase == "resource_disposition_committed":
                candidates.append(snapshot["resource_records"])
            if current >= phases.index("close_source_disposition_committed"):
                candidates = [snapshot["disposition_records"]]
            if current >= phases.index("terminal_lifecycle_recorded"):
                candidates = [snapshot["records"]]
            if next_phase == "close_source_disposition_committed":
                candidates.append(snapshot["disposition_records"])
            if next_phase == "terminal_lifecycle_recorded":
                candidates.append(snapshot["records"])
            require(read_regular(root / "execution_history.jsonl") in
                    [b"".join(canonical_bytes(row) + b"\n" for row in records) for records in candidates],
                    "Terminal execution prefix changed")
            path = root / "artifact_index.json"
            actual = read_regular(path) if path.exists() else None
            old = source["previous_index"]
            allowed = [old.encode() if old is not None else None]
            if next_phase == "terminal_checkpoint_committed":
                allowed.append(canonical_bytes(snapshot["artifact_index"]))
            elif current >= phases.index("terminal_checkpoint_committed"):
                allowed = [canonical_bytes(snapshot["artifact_index"])]
            require(actual in allowed, "Terminal artifact projection changed")
        except (ControlIntegrityError, OSError) as error:
            raise TerminalIntegrityError(str(error)) from error


def policy_for_source(source):
    """Read the validated policy initialization from a frozen source snapshot."""
    return source["policy"]


def checkpoint_snapshot(records, index, operation, label, timestamp):
    """Freeze a non-self-referential checkpoint and its exact public projection."""
    from .checkpoints import checkpoint_payload
    from .clock import Timestamp
    from .execution import replay
    from .projections import attach_checkpoint, bounded_projection, checkpoint_manifest

    execution = replay(records)
    index = {**index, "execution_head": execution.projection.value["execution_head"]}
    core = bounded_projection(execution, artifact_index=index, artifact_head=index["artifact_head"], artifact_event_index=index["revision"])
    checkpoint_id = operation["operation_id"] + "_" + label
    payload = checkpoint_payload(checkpoint_id, core, Timestamp(**records[-1]["created_at"]), operation_id=operation["operation_id"])
    manifest = checkpoint_manifest(execution, artifact_head=index["artifact_head"], artifact_event_index=index["revision"],
                                   checkpoint_id=checkpoint_id, checkpoint_digest=digest(payload), state_digest=core.digest).value
    return {"records": records, "artifact_index": index, "checkpoint": payload, "manifest": manifest,
            "projection": attach_checkpoint(core, execution, manifest).value}


class PublicationPlan:
    """Trusted phase builders freeze records and checkpoints before publication."""

    def __init__(self, operation, records, index):
        from .clock import Timestamp
        self.operation, self.records, self.index = operation, list(records), index
        self.timestamp = Timestamp(**operation.get("_materialization_time", operation["created_at"]))
        self.steps = []
        self.source = "operation_reserved"
        self.previous = self.ledger()

    def ledger(self):
        return b"".join(canonical_bytes(row) + b"\n" for row in self.records).decode()

    def append(self, kind, event, **fields):
        from .records import build_record
        root = self.records[0]
        row = build_record(kind, event, run_id=root["run_id"], case_id=root["case_id"], event_index=len(self.records) + 1,
                           previous_execution_head=digest(self.records[-1]), artifact_head=self.index["artifact_head"],
                           artifact_event_index=self.index["revision"], timestamp=self.timestamp, **fields).value
        row = retain_materialized_record(self.operation, row)
        self.records.append(row)
        return row

    def checkpoint(self, label):
        return checkpoint_snapshot(list(self.records), self.index, self.operation, label, self.timestamp)

    def step(self, target, evidence, *, checkpoint=None, branch=None):
        select_successor({**self.operation, "phase": self.source}, target, branch or {})
        validate_phase_evidence({**self.operation, "phase_revision": len(self.steps) + self.operation.get("_plan_start_revision", 1)}, target, evidence)
        content = self.ledger()
        publications = []
        if content != self.previous:
            publications.append({"path": "execution_history.jsonl", "previous": self.previous, "content": content, "replacement": False})
        if checkpoint is not None:
            publications.extend([
                {"path": "artifact_index.json", "previous": canonical_bytes(self.index).decode(),
                 "content": canonical_bytes(checkpoint["artifact_index"]).decode(), "replacement": True},
                {"path": "checkpoints/" + checkpoint["manifest"]["checkpoint_id"] + ".json", "previous": None,
                 "content": canonical_bytes(checkpoint["manifest"]).decode(), "replacement": False}])
            self.index = checkpoint["artifact_index"]
        self.steps.append({"source": self.source, "target": target, "evidence": evidence, "branch": branch or {},
                           "publications": publications, "checkpoint": checkpoint,
                           "expected_previous_ledger": self.previous, "expected_ledger": content})
        self.source, self.previous = target, content


def retain_materialized_record(operation, candidate):
    """Preserve exact old producers; only unpublished records use a new epoch/time."""
    records = operation.get("_materialized_records", ())
    index = candidate["event_index"] - 1
    if index >= len(records):
        return candidate
    existing = records[index]
    mutable_producer = {"lease_epoch", "created_at"}
    if candidate["record_type"] == "transition":
        require(existing["committed_at"] == existing["created_at"], "Materialized Transition timestamp mismatch")
        mutable_producer.add("committed_at")
    if candidate["record_type"] == "budget" and candidate["event"] in ("resource_settled", "active_interval_settled"):
        require(existing["payload"]["lease_epoch"] <= operation["lease_epoch"], "Future settlement producer epoch")
        candidate = {**candidate, "payload": {**candidate["payload"], "lease_epoch": existing["payload"]["lease_epoch"]}}
    require({key: value for key, value in existing.items() if key not in mutable_producer} ==
            {key: value for key, value in candidate.items() if key not in mutable_producer},
            "Materialized record conflicts with frozen control inputs")
    require(existing.get("lease_epoch", operation["lease_epoch"]) <= operation["lease_epoch"], "Future producer epoch")
    return existing


def continue_publication_plan(coordinator, operation, worker, lease_seconds, commit_phase, *, rebuild=None, stop_after=(), plan_snapshot=None):
    """Materialize a trusted handler's frozen plan through the generated graph."""
    from .checkpoints import persist_checkpoint
    from .coordinator import MaterializationSnapshotError, exclusive_directory

    if operation["status"] != "in_progress":
        return operation
    if coordinator._time().monotonic_seconds >= operation["lease_expires"]:
        operation = coordinator.acquire(operation["operation_id"], worker, lease_seconds=lease_seconds)
    elif operation["worker_owner_id"] != worker:
        return operation
    try:
        with coordinator.failure_context(operation):
            snapshot = coordinator.snapshot(operation["operation_id"]) if plan_snapshot is None else plan_snapshot
    except MaterializationSnapshotError as error:
        if operation["operation_type"] == "resume_run" and operation["request"].get("input_kind") == "external_result":
            raise
        return coordinator.quarantine_plan(operation, worker, error)
    locator = snapshot["run_locator"]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    while operation["status"] == "in_progress":
        with coordinator.failure_context(operation):
            if operation["phase"] in stop_after:
                return operation
            if rebuild is not None:
                from dataclasses import asdict
                from .coordinator import read_regular
                from .execution import parse_ledger
                has_publications = snapshot.get("steps") is None or any(step["publications"] for step in snapshot["steps"])
                materialized = parse_ledger(read_regular(root / "execution_history.jsonl")).values if has_publications else []
                snapshot = rebuild({**operation, "_materialized_records": materialized,
                                    "_materialization_time": asdict(coordinator._time())}, snapshot)
            steps = snapshot["steps"]
            position = next((i for i, item in enumerate(steps) if item["source"] == operation["phase"]), None)
            require(position is not None, "Frozen plan lacks current generated successor")
            step = steps[position]
            for item in step["publications"]:
                coordinator.freeze_publication(operation["operation_id"], worker, operation["lease_epoch"],
                                               operation["phase_revision"], step["target"], root / item["path"],
                                               item["content"].encode(), previous=None if item["previous"] is None else item["previous"].encode(),
                                               replacement=item["replacement"])

            def publish(db, current):
                commit_phase(db, current, step, snapshot, before=True)
                for item in step["publications"]:
                    path = root / item["path"]
                    if item["path"].startswith("checkpoints/"):
                        exclusive_directory(root / "checkpoints")
                    coordinator.materialize_publication(db, current, step["target"], path,
                                                        name=current["operation_type"] + "." + item["path"],
                                                        replacement=item["replacement"])
                checkpoint = step["checkpoint"]
                if checkpoint is not None:
                    persist_checkpoint(coordinator, db, current, root, checkpoint["checkpoint"],
                                       {"source": "input", "step": 0, "parents": {}, "operation_id": current["operation_id"]})
                actual_evidence = commit_phase(db, current, step, snapshot, before=False)
                return step["evidence"] if actual_evidence is None else actual_evidence

            operation = coordinator.step(operation["operation_id"], worker, operation["lease_epoch"], operation["phase_revision"],
                                         step["target"], publish, branch_values=step["branch"])
    return operation


def phase_contract(operation_type, variant, phase):
    declaration = operation_variant(operation_type, variant)
    require(phase in declaration["phases"], "Phase belongs to another operation variant")
    return CONTROL["phase_contracts"][phase]


def reservation_fields(operation_type, variant):
    phase_contract(operation_type, variant, "operation_reserved")
    overlay = next(row for row in CONTROL["phase_contract_overlays"]
                   if (row["operation_type"], row["operation_variant"]) == (operation_type, variant))
    return tuple(row["field"] for row in overlay["required_evidence_additions"])


def validate_reservation(operation_type, variant, value):
    closed(value, reservation_fields(operation_type, variant))
    require(all(item is not None for item in value.values()), "Null reservation overlay")


def branch_contract(operation):
    return next((row for row in PROTOCOL["branch_contracts"]
                 if row["machine"] == "control_operation" and
                 (row["operation_type"], row["operation_variant"], row["source_phase"]) ==
                 (operation["operation_type"], operation["operation_variant"], operation["phase"])), None)


def select_successor(operation, target, branch_values):
    declaration = operation_variant(operation["operation_type"], operation["operation_variant"])
    require((operation["phase"], target) in declaration["success_edges"], "Skipped or cross-variant phase")
    branch = branch_contract(operation)
    if branch is None:
        require(not branch_values, "Discriminants on an unguarded edge")
        return True
    fields = [row["field"] for row in branch["discriminants"]]
    closed(branch_values, fields)
    require(any(branch_values == dict(row) for row in branch["valid_combinations"]), "Invalid branch tuple")
    for discriminant in branch["discriminants"]:
        if discriminant["binding"] == "immutable_at_operation_reservation":
            field = discriminant["field"]
            require(branch_values[field] == operation["reservation"][field], "Reservation branch changed")
    matches = [row["target"] for row in branch["cases"]
               if all(branch_values[field] in allowed for field, allowed in row["when"].items())]
    require(matches == [target], "Successor does not match the exact frozen branch tuple")
    return True


def validate_phase_evidence(operation, target, evidence):
    contract = phase_contract(operation["operation_type"], operation["operation_variant"], target)
    closed(evidence, contract["required_evidence"])
    require(all(item is not None for item in evidence.values()), "Missing phase evidence")
    if "final_phase_revision" in evidence:
        require(type(evidence["final_phase_revision"]) is int and
                evidence["final_phase_revision"] == operation["phase_revision"] + 1,
                "Result is bound to another revision")


def bootstrap_admission(operation_id, root_inputs_digest, selected_policy):
    """Compute the initial route and full terminal reserve from trusted policy.

    A02C01 owns this one-time admission; callers cannot provide a decision,
    counters, available capacity, or a replacement policy body.
    """
    from .budget import validate_budget_payload, validate_policy
    text(operation_id)
    digest_value(root_inputs_digest)
    selected = validate_policy(selected_policy).value
    reserve = selected["terminal_reserve"]
    needed = {"cycles_per_run": 1, "work_attempts_per_run": 1,
              "control_attempts_per_run": reserve["control_attempts"],
              "transitions_per_run": 1 + reserve["transitions"]}
    dimensions = {key: {"used": 0, "remaining": limit, "projected_after": needed.get(key, 0)}
                  for key, limit in selected["limits"].items()}
    require(all(row["projected_after"] <= row["remaining"] for row in dimensions.values()),
            "Bootstrap cannot retain the full terminal reserve")
    proposal = {"operation_id": operation_id, "root_inputs_digest": root_inputs_digest,
                "policy_digest": selected["policy_digest"], "proposed_action": "bootstrap_initial_route"}
    body = {"schema_version": "0.1", "proposal_id": digest(proposal),
            "proposed_action": "bootstrap_initial_route", "target_kind": "method_planner", "risk": "low",
            "fingerprint_digest": None, "occurrence": 0, "dimensions": dimensions, "budget_grant_id": None,
            "decision": "allow", "reason_code": "bootstrap_capacity_and_terminal_reserve", "next_control_action": "bootstrap"}
    result = {**body, "decision_digest": digest(body)}
    validate_budget_payload("decision_recorded", result)
    return result


@dataclass(frozen=True)
class RepauseAdmission:
    capacity: str
    decision: dict


def invalid_response_admission(execution, adapter):
    """Bind a trusted domain decision; B02 does not select the capacity policy."""
    from .budget import validate_budget_payload
    state, records = execution.projection.value, execution.values
    selected = next(r["payload"]["policy"] for r in records if r["record_type"] == "budget" and r["event"] == "policy_initialized")
    pause = next(r for r in reversed(records) if r["record_type"] == "pause")
    response = next(r for r in reversed(records) if r["record_type"] == "human_response")
    validator = records[-1]
    require(pause["status"] == "consumed" and response["status"] == "invalid" and validator["record_type"] == "attempt" and
            validator["event"] == "finished" and response["validator_attempt_id"] == validator["attempt_id"], "Invalid response lacks finished consumption closure")
    source = {"consumed_old_pause": digest(pause), "finished_validator_attempt": digest(validator),
              "open_human_request": state["active_human_request_id"], "derived_next_pause_identity": f"pause_{state['pause_index'] + 1:06d}"}
    require(adapter is not None, "Missing trusted repause decision adapter")
    admitted = adapter.repause({"binding": source, "policy": selected, "budget": state["budget"]})
    require(type(admitted) is RepauseAdmission, "Untyped repause admission")
    matches = [row for row in PROTOCOL["budget_decision_contract"]["invalid_response_cases"] if row["capacity"] == admitted.capacity]
    require(len(matches) == 1, "Unknown repause capacity classification")
    decision = admitted.decision
    validate_budget_payload("decision_recorded", decision)
    dimensions = decision["dimensions"]
    require(set(dimensions) == set(state["budget"]["dimensions"]) and all(
        row["used"] == state["budget"]["dimensions"][name]["used"] and row["remaining"] == state["budget"]["dimensions"][name]["remaining"]
        for name, row in dimensions.items()), "Repause decision has foreign budget inputs")
    case = matches[0]
    binding = {**source, "terminal_tail_capacity": dimensions}
    require(decision["proposal_id"] == digest(binding) and decision["proposed_action"] == "repause" and
            decision["decision"] == case["decision"] and decision["next_control_action"] == case["next_control_action"] and
            decision["target_kind"] == "human_gate" and decision["budget_grant_id"] is None, "Repause decision binding mismatch")
    return decision, binding


@dataclass(frozen=True)
class AdvanceRunRequest:
    run_locator: dict
    source_attempt_id: str
    idempotency_key: str


@dataclass(frozen=True)
class RouteAdmission:
    """Trusted domain adapter output, never accepted from a public request."""

    target_node: str | None
    route: str
    trigger_reason: str
    reason: str
    budget_decision: dict
    target_preparation: dict
    human_request: dict | None = None


def route_grant_consumption(records, state, admitted):
    """Bind an already-issued B04 grant; control never issues or extends one."""
    from lqcd_agent.graph.state import canonical_attempt_kind, stable_attempt_id, stable_transition_id
    from .budget import validate_budget_payload

    decision = admitted.budget_decision
    if decision["budget_grant_id"] is None:
        return None
    grant = state["budget"]["active_grant"]
    require(grant is not None and grant["budget_grant_id"] == decision["budget_grant_id"], "Missing active route grant")
    validate_budget_payload("grant_issued", grant)
    require(sum(r["record_type"] == "budget" and r["event"] == "grant_issued" and r["payload"] == grant for r in records) == 1 and
            not any(r["record_type"] == "budget" and r["event"] == "grant_consumed" and
                    r["payload"]["budget_grant_id"] == grant["budget_grant_id"] for r in records), "Grant is not uniquely issued and unconsumed")
    require(admitted.target_node is not None and grant["target_node"] == admitted.target_node and
            grant["target_attempt_kind"] == canonical_attempt_kind(admitted.target_node) == decision["target_kind"] and
            grant["target_attempt_id"] == stable_attempt_id(state["attempt_index"] + 1) and
            grant["transition_id"] == stable_transition_id(state["transition_index"] + 1) and
            grant["cycle_id"] == state["cycle_id"] and grant["fingerprint_digest"] == decision["fingerprint_digest"] and
            grant["occurrence"] == decision["occurrence"], "Grant does not authorize this exact route opportunity")
    return {"budget_grant_id": grant["budget_grant_id"], "transition_id": grant["transition_id"],
            "target_attempt_id": grant["target_attempt_id"], "grant_digest": digest(grant)}


@dataclass(frozen=True)
class PreparationVerification:
    """A Host domain receipt; control checks binding, never materializes code."""

    snapshot_digest: str
    workspace_manifest_digest: str
    effective_tree_digest: str


def validate_target_preparation(value, locator, target_kind, attempt_id, transition_id, code):
    union = next(row for row in PROTOCOL["evidence_unions"] if row["union_id"] == "TargetPreparationSnapshot")
    require(type(value) is dict, "Missing target preparation")
    variant = next((v for v in union["variants"] if v["tag"] == value.get("preparation_kind")), None)
    require(variant is not None, "Unknown preparation kind")
    closed(value, (union["tag_field"], *variant["required_fields"]))
    required = target_kind == "analysis_engineer" and code is not None
    require((value["preparation_kind"] == "analysis_fresh") == required, "Analysis preparation does not match selected Code")
    if not required:
        text(value["not_applicable_reason"])
        return
    require(value["target_attempt_identity"] == {**locator, "attempt_id": attempt_id, "attempt_kind": target_kind} and
            value["inbound_transition_identity"] == transition_id and
            value["analysis_execution_spec_id"] == attempt_id + ":analysis_execution_spec", "Preparation target identity mismatch")
    text(value["fresh_workspace_identity"])
    for key in ("spec_digest", "workspace_manifest_digest", "verified_change_digest", "expected_effective_tree_digest", "runtime_policy_digest"):
        digest_value(value[key])
    for key, expected in (("canonical_spec_bytes", "spec_digest"), ("canonical_workspace_manifest_bytes", "workspace_manifest_digest")):
        text(value[key])
        require(type(loads(value[key])) is dict and digest(loads(value[key])) == value[expected], "Preparation bytes differ from frozen digest")
    require(value["source_code_bundle_id_digest"] == {"artifact_id": code["artifact_id"], "digest": digest(code)},
            "Preparation selected Code binding mismatch")
    require(type(value["base_revision_tree"]) is dict and bool(value["base_revision_tree"]), "Missing frozen base binding")


def verify_preparation_receipt(value, receipt):
    require(type(receipt) is PreparationVerification and receipt.snapshot_digest == digest(value) and
            receipt.workspace_manifest_digest == value["workspace_manifest_digest"] and
            receipt.effective_tree_digest == value["expected_effective_tree_digest"], "Fresh preparation verification failed")
    return asdict(receipt)


class PreparationPort:
    """A current-operation fence for a trusted deterministic workspace adapter."""

    def __init__(self, coordinator, db, operation):
        self.coordinator, self.db, self.operation = coordinator, db, operation

    def fence(self):
        operation = self.operation
        self.coordinator.fence(self.db, operation["operation_id"], operation["worker_owner_id"],
                               operation["lease_epoch"], operation["phase_revision"])
        require(self.db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (digest(operation["request"]["run_locator"]),)).fetchone() is None,
                "Terminal ownership revoked preparation")


class AdvanceOperations:
    """Own control publication while the Host domain port owns route selection."""

    def __init__(self, coordinator, worker, lease_seconds, route_adapter):
        self.coordinator, self.worker, self.lease_seconds = coordinator, worker, lease_seconds
        self.route_adapter = route_adapter

    def advance(self, request, actor):
        from .coordinator import component, read_regular
        from .execution import parse_ledger
        from .integrity import validate_run_root
        from .checkpoints import verify_checkpoint

        require(type(request) is AdvanceRunRequest, "Expected trusted AdvanceRunRequest")
        identity = actor.authorize("control.internal")
        closed(request.run_locator, ("case_id", "run_id"))
        for item in request.run_locator.values():
            component(item)
        text(request.source_attempt_id)
        text(request.idempotency_key)
        canonical = {**asdict(request), "actor": identity}
        canonical.pop("idempotency_key")
        coordinator, locator = self.coordinator, request.run_locator
        key = digest(locator)
        root = coordinator.root / locator["case_id"] / locator["run_id"]
        with coordinator.transaction() as db:
            operation = coordinator.lookup_key("internal_advance", request.idempotency_key, db=db)
            if operation is not None:
                require(operation["request_digest"] == digest({"operation_type": "advance_run", "operation_variant": "not_applicable", "request": canonical}),
                        "Same-key request conflict")
            else:
                require(self.route_adapter is not None, "Missing Host-owned route/admission adapter")
                row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (key,)).fetchone()
                require(row is not None, "Unknown Run")
                control = loads(row["value"])
                require(control["projection"] is not None, "Run checkpoint unavailable")
                require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone() is None, "Run has terminal owner")
                verify_checkpoint(root, control["manifest"])
                state = validate_run_root(root, manifest=control["manifest"], projection=control["projection"]).value
                require(state["run_status"] == "running" and state.get("active_pause") is None and state.get("pending_pause") is None,
                        "Advance requires a stable running source")
                records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
                source = next((r for r in reversed(records) if r["record_type"] == "attempt"), None)
                require(source is not None and source["attempt_id"] == request.source_attempt_id and source["event"] == "finished",
                        "Advance source Attempt is not the latest finished Attempt")
                require(not any(r["record_type"] == "transition" and r["source_attempt_id"] == source["attempt_id"] for r in records),
                        "Source Attempt already has an outbound Transition")
                require(not ExternalControl(coordinator).attached(db, locator), "Advance needs verified external detachment")
                view = loads(canonical_bytes({"run_locator": locator, "source": source, "state": state,
                                             "next_attempt_index": state["attempt_index"] + 1,
                                             "next_transition_index": state["transition_index"] + 1,
                                             "selected_code": loads(read_regular(root / "artifact_index.json"))["current"]["code"]}))
                admitted = self.route_adapter.admit(view)
                require(type(admitted) is RouteAdmission, "Domain adapter returned an untyped route admission")
                index = loads(read_regular(root / "artifact_index.json"))
                history = read_regular(root / "artifact_history.jsonl")
                built = {}

                def reserve(operation_id, stamp):
                    op = {"operation_id": operation_id, "operation_type": "advance_run", "operation_variant": "not_applicable",
                          "created_at": asdict(stamp), "lease_epoch": 1, "phase_revision": 1, "request": canonical}
                    built.update(self._snapshot(op, records, index, history, control["manifest"], state, row["revision"], admitted))
                    return built["reservation"]

                operation = coordinator.reserve_in_transaction(db, "advance_run", "not_applicable", "internal_advance",
                                                               request.idempotency_key, canonical, self.worker, reserve,
                                                               lease_seconds=self.lease_seconds, build_snapshot=lambda op: built)
        if operation["status"] != "in_progress":
            if operation["error"] is not None and "close_operation_id" in operation["error"]:
                TerminalOperations(coordinator, self.worker, self.lease_seconds).continue_close(operation["error"]["close_operation_id"])
            return operation
        try:
            return continue_publication_plan(coordinator, operation, self.worker, self.lease_seconds, self._phase)
        except (ControlIntegrityError, OSError, ValueError) as error:
            return TerminalOperations(coordinator, self.worker, self.lease_seconds).fail_advance(operation, error)

    def _snapshot(self, operation, records, index, history, manifest, state, source_revision, admitted):
        from copy import deepcopy
        from datetime import datetime, timezone
        from lqcd_agent.artifacts import registry
        from lqcd_agent.graph.state import canonical_attempt_kind, stable_attempt_id, stable_cycle_id, stable_transition_id
        from .budget import WORK_KINDS, validate_budget_payload
        from .execution import replay
        from .integrity import artifact_binding
        from .projections import bounded_projection
        from .records import build_record

        locator = operation["request"]["run_locator"]
        source = next(r for r in reversed(records) if r["record_type"] == "attempt")
        response = None
        if source["attempt_kind"] == "human_gate":
            response = next((r for r in reversed(records) if r["record_type"] == "human_response"), None)
            require(response is not None and response["status"] == "validated" and
                    response["validator_attempt_id"] == source["attempt_id"] and
                    response["authorized_transition_route"] == admitted.route and
                    response["authorized_transition_target"] == admitted.target_node,
                    "Human response does not authorize this exact Transition")
        target_kind = canonical_attempt_kind(admitted.target_node) if admitted.target_node is not None else None
        branch = "attempt" if target_kind is not None else "end"
        if target_kind == "human_gate":
            require(source["attempt_kind"] == "decision_coordinator" and admitted.human_request is not None,
                    "Human Gate entry requires an exact Coordinator request")
            closed(admitted.human_request, ("request_kind", "authorization_scope"))
        else:
            require(admitted.human_request is None, "Foreign Human Request route prerequisites")
        require((branch == "end") == (admitted.route in ("end", "__end__")), "Partial terminal route")
        if branch == "end":
            require(source["attempt_kind"] == "memory_report", "Only Memory Report may propose END")
        for value in (admitted.route, admitted.trigger_reason, admitted.reason):
            text(value)
        validate_budget_payload("decision_recorded", admitted.budget_decision)
        decision = admitted.budget_decision
        require(decision["decision"] == "allow" and decision["proposed_action"] == "route" and decision["target_kind"] == target_kind,
                "Route has no matching trusted allow decision")
        grant = route_grant_consumption(records, state, admitted)
        selected = policy_for_source({"policy": next(r["payload"]["policy"] for r in records if r["record_type"] == "budget" and r["event"] == "policy_initialized")})
        require(set(decision["dimensions"]) == set(state["budget"]["dimensions"]), "Incomplete decision dimensions")
        new_cycle = target_kind == "method_planner"
        if new_cycle:
            require(source["attempt_kind"] == "decision_coordinator" and admitted.trigger_reason == "replan", "Invalid replan Cycle producer")
        charges = {"cycles_per_run": int(new_cycle), "work_attempts_per_run": int(target_kind in WORK_KINDS),
                   "control_attempts_per_run": int(target_kind is not None and target_kind not in WORK_KINDS), "transitions_per_run": 1}
        for name, amounts in decision["dimensions"].items():
            before = state["budget"]["dimensions"][name]
            ceiling = selected["limits"][name]
            if grant is not None and name == state["budget"]["active_grant"]["route_dimension"]:
                ceiling = max(ceiling, before["used"] + 1)
            require(amounts["used"] == before["used"] and amounts["remaining"] == before["remaining"] and
                    amounts["projected_after"] >= before["used"] + charges.get(name, 0) and
                    amounts["projected_after"] <= ceiling, "Route decision disagrees with replayed capacity")
        preparation = admitted.target_preparation
        validate_target_preparation(preparation, locator, target_kind, stable_attempt_id(state["attempt_index"] + 1),
                                    stable_transition_id(state["transition_index"] + 1), index["current"]["code"])
        if preparation["preparation_kind"] == "analysis_fresh":
            require(self.route_adapter is not None and hasattr(self.route_adapter, "verify_preparation_source") and
                    hasattr(self.route_adapter, "materialize_preparation") and hasattr(self.route_adapter, "verify_preparation"),
                    "Missing Host fresh preparation port")
            verify_preparation_receipt(preparation, self.route_adapter.verify_preparation_source(loads(canonical_bytes(preparation))))
        operation = {**operation, "reservation": {"transition_target_kind": branch}}
        plan = PublicationPlan(operation, records, deepcopy(index))
        policy_digest = selected["policy_digest"]
        event_index = state["budget"]["budget_event_index"] + 1
        budget_record = plan.append("budget", "decision_recorded", budget_event_id=f"budget_event_{event_index:06d}",
                                    budget_event_index=event_index, policy_version="0.1", policy_digest=policy_digest, payload=decision)
        grant_record = {"tag": "not_applicable"}
        if grant is not None:
            event_index += 1
            grant_record = plan.append("budget", "grant_consumed", budget_event_id=f"budget_event_{event_index:06d}",
                                      budget_event_index=event_index, policy_version="0.1", policy_digest=policy_digest, payload=grant)
        heads = {key: state[key] for key in ("execution_head", "artifact_head", "checkpoint_head")}
        plan.step("budget_decision_committed", {"frozen_budget_decision": budget_record, "grant_consumed_or_not_applicable": grant_record, "exact_source_heads": heads})
        attempt_id = stable_attempt_id(state["attempt_index"] + 1) if branch == "attempt" else None
        transition_id = stable_transition_id(state["transition_index"] + 1)
        cycle_index = state["cycle_index"] + int(new_cycle)
        cycle_id = stable_cycle_id(cycle_index)
        slots = registry._slots_for_target(target_kind, new_human_request=admitted.human_request is not None) if target_kind is not None else ()
        invalidation = [{"slot": slot, "artifact_id": index["current"][slot]["artifact_id"]} for slot in slots if index["current"][slot] is not None]
        plan.step("transition_target_classified", {"transition_target_kind": branch,
                                                  "precomputed_transition_identity_and_digest": {"transition_id": transition_id}})
        target = {"tag": "null"}
        human_request = {"tag": "not_applicable"}
        removals, artifact_records = [], []
        if branch == "attempt":
            if new_cycle:
                plan.append("cycle", "created", cycle_id=cycle_id, cycle_index=cycle_index, parent_cycle_id=state["cycle_id"],
                            trigger_reason="replan", created_by_attempt_id=source["attempt_id"], status="active")
            if admitted.human_request is not None:
                from lqcd_agent.graph.state import stable_human_request_id
                request_index = state["human_request_index"] + 1
                human_request = plan.append("human_request", "created", cycle_id=cycle_id,
                    human_request_id=stable_human_request_id(request_index), request_index=request_index,
                    requesting_attempt_id=source["attempt_id"], packet_reference=None, status="open", **admitted.human_request)
            plan.step("route_prerequisites_committed", {"human_request_created_or_not_applicable": human_request,
                                                       "exact_route_prerequisites": {"source_attempt_id": source["attempt_id"]}},
                      branch={"transition_target_kind": "attempt"})
            target = plan.append("attempt", "scheduled", cycle_id=cycle_id, cycle_index=cycle_index,
                                 attempt_id=attempt_id, attempt_index=state["attempt_index"] + 1, parent_attempt_id=source["attempt_id"],
                                 attempt_kind=target_kind, node_name=admitted.target_node, attempt_trigger=admitted.trigger_reason,
                                 inbound_transition_id=transition_id, status="scheduled", input_references={"current_artifact_ids": {}},
                                 output_references={"current_artifact_ids": {}}, error=None)
            plan.step("target_attempt_scheduled", {"precomputed_target_attempt_identity": attempt_id, "scheduled_target_record": target})
            for item in invalidation:
                slot = item["slot"]
                pointer = plan.index["current"][slot]
                for member in pointer["members"]:
                    path = member["projection_path"]
                    if plan.index["managed_projections"].get(path) == pointer["artifact_id"]:
                        removals.append({"path": path, "artifact_id": pointer["artifact_id"], "sha256": member["sha256"]})
                        del plan.index["managed_projections"][path]
                number = plan.index["revision"] + 1
                row = {"schema_version": registry.ARTIFACT_SCHEMA_VERSION, "event_id": f"artifact_event_{number:06d}", "event_index": number,
                       "event": "current_cleared", **locator, "cycle_id": cycle_id, "attempt_id": attempt_id, "transition_id": transition_id,
                       "human_request_id": state["active_human_request_id"], "human_response_id": state["active_human_response_id"],
                       "slot": slot, "artifact_id": pointer["artifact_id"], "reason_code": "target_" + target_kind,
                       "created_at": datetime.fromtimestamp(plan.timestamp.wall_seconds, timezone.utc).isoformat(),
                       "target_attempt_id": attempt_id, "prior_artifact_id": pointer["artifact_id"]}
                row = artifact_binding(row, previous_artifact_head=plan.index["artifact_head"], execution_head=digest(target)).value
                artifact_records.append(row)
                plan.index.update(revision=number, last_event_id=row["event_id"], artifact_head=digest(row))
                plan.index["current"][slot] = None
            plan.step("target_artifacts_invalidated", {"required_invalidation_set": invalidation, "invalidation_set_digest": digest(invalidation), "scheduled_target_identity": attempt_id})
            if artifact_records:
                plan.steps[-1]["publications"].append({"path": "artifact_history.jsonl", "previous": history.decode(),
                                                     "content": (history + b"".join(canonical_bytes(r) + b"\n" for r in artifact_records)).decode(), "replacement": False})
        transition = plan.append("transition", "committed", transition_id=transition_id, transition_index=state["transition_index"] + 1,
                                 source=source["node_name"], source_node=source["node_name"], source_cycle_id=source["cycle_id"], source_attempt_id=source["attempt_id"],
                                 route=admitted.route, target_node=admitted.target_node, target_cycle_id=cycle_id if branch == "attempt" else None,
                                 target_attempt_id=attempt_id, target_attempt_kind=target_kind,
                                 human_request_id=response["human_request_id"] if response is not None else human_request.get("human_request_id"),
                                 human_response_id=response["human_response_id"] if response is not None else None,
                                 trigger_reason=admitted.trigger_reason, reason=admitted.reason, fields={}, evidence_references={},
                                 applied_state_update_keys=[], applied_state_updates_sha256=digest({}), status="committed", committed_at=asdict(plan.timestamp))
        if response is not None:
            from .records import FIELDS
            consumed = {key: response[key] for key in FIELDS["human_response"]}
            consumed.update(status="consumed", consumer_attempt_id=source["attempt_id"], authorized_target_attempt_id=attempt_id)
            plan.append("human_response", "consumed", **consumed)
            request = next(r for r in reversed(records) if r["record_type"] == "human_request")
            plan.append("human_request", "satisfied", **{**{key: request[key] for key in FIELDS["human_request"]}, "status": "satisfied"})
        if branch == "attempt":
            evidence = {"canonical_transition_bytes": canonical_bytes(transition).decode(), "transition_digest": digest(transition), "scheduled_target_identity": attempt_id}
            plan.step("transition_committed", evidence)
        else:
            evidence = {"canonical_terminal_transition_bytes": canonical_bytes(transition).decode(), "transition_digest": digest(transition), "typed_null_target": {"tag": "null"}}
            plan.step("terminal_transition_committed", evidence, branch={"transition_target_kind": "end"})
        plan.index["execution_head"] = digest(plan.records[-1])
        plan.steps[-1]["publications"].append({"path": "artifact_index.json", "previous": canonical_bytes(index).decode(),
                                             "content": canonical_bytes(plan.index).decode(), "replacement": True})
        execution = replay(plan.records)
        projection = {**bounded_projection(execution, artifact_index=plan.index, artifact_head=plan.index["artifact_head"],
                                           artifact_event_index=plan.index["revision"]).value, "checkpoint_head": manifest["checkpoint_head"]}
        final_heads = {key: projection[key] for key in heads}
        plan.step("transition_heads_verified", {"expected_post_transition_heads": final_heads, "exact_materialized_heads": final_heads, "transition_target_kind": branch})
        if branch == "attempt":
            plan.step("target_preparation_committed", {"target_preparation_snapshot": preparation,
                                                       "exact_committed_transition_and_scheduled_target": {"transition": transition_id, "target": attempt_id},
                                                       "current_advance_epoch_and_terminal_revision": {"lease_epoch": operation["lease_epoch"], "terminal_revision": 0},
                                                       "spec_manifest_bytes_and_effective_tree_verified_or_not_applicable": preparation,
                                                       "unchanged_execution_artifact_heads": final_heads}, branch={"transition_target_kind": "attempt"})
            if preparation["preparation_kind"] == "analysis_fresh":
                namespace = "attempts/" + attempt_id + "/control/"
                for name, field in (("analysis_execution_spec.json", "canonical_spec_bytes"), ("analysis_workspace_manifest.json", "canonical_workspace_manifest_bytes")):
                    plan.steps[-1]["publications"].append({"path": namespace + name, "content": preparation[field], "previous": None, "replacement": False})
            plan.step("invocation_capability_prepared", {"attempt_identity": {**locator, "attempt_id": attempt_id, "attempt_kind": target_kind},
                                                         "exact_heads": final_heads, "lease_epoch": operation["lease_epoch"], "terminal_closure_revision": 0,
                                                         "producer_operation_id": operation["operation_id"], "activation_result_revision": len(plan.steps) + 3,
                                                         "inactive_until_operation_committed": True})
        result = {"run_locator": locator, "run_status": "running", "domain_status": None, "pause_id": None, "terminal_closure": "not_applicable",
                  **final_heads, "transition_id": transition_id, "capability_id": "capability_" + operation["operation_id"] if branch == "attempt" else None}
        plan.step("result_committed", {"exact_public_or_internal_result": result, "final_phase_revision": len(plan.steps) + 2},
                  branch={"transition_target_kind": "end"} if branch == "end" else None)
        reservation = {"source_run_attempt_and_heads": {**locator, "source_attempt_id": source["attempt_id"], **heads}, "proposed_route": admitted.route,
                       "canonical_budget_decision_bytes": canonical_bytes(decision).decode(), "budget_decision_digest": decision["decision_digest"],
                       "grant_consumption_or_not_applicable": grant_record, "transition_target_kind": branch,
                       "target_attempt_identity_or_typed_null": {**locator, "attempt_id": attempt_id} if branch == "attempt" else {"tag": "null"},
                       "human_request_or_not_applicable": human_request, "required_invalidation_set": invalidation,
                       "invalidation_set_digest": digest(invalidation), "transition_identity": transition_id,
                       "canonical_transition_bytes": canonical_bytes(transition).decode(), "transition_digest": digest(transition),
                       "expected_post_transition_heads": final_heads, "terminal_closure_revision": 0, "target_preparation_snapshot": preparation}
        # Branch guards consume the exact overlay, which is frozen by the same reservation transaction.
        for step in plan.steps:
            if step["target"] == "transition_target_classified":
                step["evidence"]["precomputed_transition_identity_and_digest"]["transition_digest"] = digest(transition)
            select_successor({**operation, "reservation": reservation, "phase": step["source"]}, step["target"], step["branch"])
        return {"run_locator": locator, "steps": plan.steps, "reservation": reservation, "source_control_revision": source_revision,
                "source_records": records, "records": plan.records, "artifact_index": plan.index, "original_index": index,
                "original_artifact_history": history.decode(), "artifact_records": artifact_records, "removals": removals,
                "projection": projection, "manifest": manifest, "policy": selected}

    def _phase(self, db, operation, step, snapshot, *, before):
        from hashlib import sha256
        from .capabilities import prepare_capability
        from .coordinator import read_regular, sync_directory
        from .integrity import validate_advanced_run_root

        locator = snapshot["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        key = digest(locator)
        if before:
            require(db.execute("SELECT 1 FROM run_terminal_closure WHERE run_key=?", (key,)).fetchone() is None, "Run terminal owner revoked advance")
            require(read_regular(root / "execution_history.jsonl").decode() in (step["expected_previous_ledger"], step["expected_ledger"]), "Advance prefix conflict")
            require(read_regular(root / "budget_policy.json") == canonical_bytes(snapshot["policy"]), "Advance policy changed")
            row = db.execute("SELECT revision,value FROM run_controls WHERE run_key=?", (key,)).fetchone()
            control = loads(row["value"])
            if step["target"] == "budget_decision_committed":
                require(row["revision"] == snapshot["source_control_revision"] and control.get("advance_owner") is None, "Competing advance source")
                control["advance_owner"] = operation["operation_id"]
                db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes(control), key))
            else:
                require(control.get("advance_owner") == operation["operation_id"], "Wrong advance owner")
            if step["target"] == "target_preparation_committed" and operation["reservation"]["target_preparation_snapshot"]["preparation_kind"] == "analysis_fresh":
                from .coordinator import exclusive_directory
                parent = root
                for name in ("attempts", operation["reservation"]["target_attempt_identity_or_typed_null"]["attempt_id"], "control"):
                    parent = parent / name
                    PreparationPort(self.coordinator, db, operation).fence()
                    exclusive_directory(parent)
            if step["target"] == "target_artifacts_invalidated":
                for item in snapshot["removals"]:
                    path = root / item["path"]
                    require(path == path.resolve() and path.is_relative_to(root), "Projection removal escaped Run")
                    if path.exists():
                        require(sha256(read_regular(path)).hexdigest() == item["sha256"], "Projection bytes changed before invalidation")
                        self.coordinator.fence(db, operation["operation_id"], self.worker, operation["lease_epoch"], operation["phase_revision"])
                        path.unlink()
                        sync_directory(path.parent)
            return
        if step["target"] in ("transition_heads_verified", "target_preparation_committed", "invocation_capability_prepared", "result_committed"):
            validate_advanced_run_root(root, manifest=snapshot["manifest"], projection=snapshot["projection"])
        if step["target"] == "target_preparation_committed":
            preparation = operation["reservation"]["target_preparation_snapshot"]
            evidence = step["evidence"]
            if preparation["preparation_kind"] == "analysis_fresh":
                require(self.route_adapter is not None and hasattr(self.route_adapter, "materialize_preparation"), "Missing original preparation port")
                port = PreparationPort(self.coordinator, db, operation)
                port.fence()
                receipt = self.route_adapter.materialize_preparation(loads(canonical_bytes(preparation)), port)
                port.fence()
                verified = verify_preparation_receipt(preparation, receipt)
                verify_preparation_receipt(preparation, self.route_adapter.verify_preparation(loads(canonical_bytes(preparation))))
                validate_advanced_run_root(root, manifest=snapshot["manifest"], projection=snapshot["projection"])
                evidence = {**evidence, "spec_manifest_bytes_and_effective_tree_verified_or_not_applicable": verified}
            return {**evidence, "current_advance_epoch_and_terminal_revision": {"lease_epoch": operation["lease_epoch"], "terminal_revision": 0}}
        if step["target"] == "invocation_capability_prepared":
            return prepare_capability(self.coordinator, db, operation, root, snapshot["manifest"], snapshot["projection"], advanced=True)
        if step["target"] == "result_committed":
            db.execute("UPDATE run_controls SET revision=revision+1,value=? WHERE run_key=?",
                       (canonical_bytes({"locator": locator, "projection": snapshot["projection"], "manifest": snapshot["manifest"],
                                         "checkpoint_anchor_kind": "owned_transition", "transition_owner": operation["operation_id"]}), key))
