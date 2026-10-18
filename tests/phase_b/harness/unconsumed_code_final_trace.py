"""Trace 0.11 binds unconsumed Code evidence to its original control storage."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3

from lqcd_agent.code_agent.backend import validate_receipt
from lqcd_agent.code_agent.ingress import validate_change_manifest, validate_workspace_seal
from lqcd_agent.code_agent.schemas import validate_manifest, validate_task
from lqcd_agent.code_agent.workspace import validate_tool_audit
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from . import a05_trace
from .ordinary_publication_prefix_trace import BASE_FIELDS, PROOF_FIELDS, PublicationPrefixProjection
from .ordinary_trace import check
from .fault_source_trace import source_path
from .strict_json import Invalid, keys


FIELDS = PROOF_FIELDS | {"unconsumed_code_sources"}
DECLARATION_FIELDS = {"schema_version", "producer_operation_id", "producer_snapshot", "task_head", "manifest_head",
    "core_head", "receipt_head", "external_result_head", "seal_head", "change_manifest_head", "tool_audit_head",
    "patch_head", "final_head", "reservation_head", "resolution_owner", "resolution_operation_id",
    "terminal_operation_id", "pause_snapshot", "publication_stage"}
MEMBERS = {"receipt": ("receipt_head", "backend_dispatch_receipt.json"),
    "external_result": ("external_result_head", "code_agent_external_result.json"),
    "seal": ("seal_head", "workspace_seal.json"), "change_manifest": ("change_manifest_head", "change_manifest.json"),
    "canonical_tool_audit": ("tool_audit_head", "tool_audit.jsonl"), "material": ("patch_head", "changes.patch")}


def original_file(root, reference):
    path = root / reference
    check(path.resolve() == path and path.is_relative_to(root) and not source_path(path).is_symlink(), "unconsumed_path")
    return read_regular(source_path(path))


def read_consumption_failure(coordinator, producer):
    """Verify the original Resume failure journals without recovering an effect."""
    from lqcd_agent.code_agent.verification_resources import owned_prefix
    from lqcd_agent.control.execution import parse_ledger
    locator = producer["run_locator"]
    row = coordinator.connection.execute("SELECT value FROM run_terminal_closure WHERE run_key=?", (digest(locator),)).fetchone()
    if row is None:
        return None
    closure = loads(row[0])
    operation = coordinator.get(closure["terminal_closure_owner_operation_id"])
    history = coordinator.history(operation["operation_id"])
    entries = [r for r in history if r["phase"] == "consumption_failure_ownership_reserved"]
    if not entries:
        return None
    if operation["reservation"]["target_prestart_closure"]["external"]["value"]["producer_operation_id"] != producer["producer_operation_id"]:
        return None
    check(len(entries) == 1 and producer["resolution_owner"] == "normal" and producer["proof_kind"] == "safe_stop" and
          operation["operation_type"] == "resume_run" and operation["request"]["run_locator"] == locator and
          operation["request"]["pause_id"] == producer["pause_id"] and operation["request"]["input_kind"] == "external_result",
          "consumption_failure_owner")
    reserved = entries[0]
    frozen = reserved["evidence"]["frozen_failure_snapshot_and_disposition_contract"]
    failure = frozen["failure"]
    owner = operation["operation_id"]
    check(frozen["run_locator"] == locator and reserved["revision"] == failure["source_phase_revision"] + 1 and
          reserved["lease_epoch"] == failure["source_resume_owner_epoch"] and
          any(r["revision"] == failure["source_phase_revision"] and r["phase"] == frozen["source_phase"] and
              r["lease_epoch"] == failure["source_resume_owner_epoch"] for r in history), "consumption_failure_revision")
    check(failure["terminal_disposition_contract_digest"] == digest({k: v for k, v in failure.items()
          if k != "terminal_disposition_contract_digest"}) and closure["terminal_disposition_contract"] == failure and
          closure["terminal_trigger_digest"] == failure["failure_id_digest"] and
          closure["terminal_trigger_reference"] == {"failure_id_digest": failure["failure_id_digest"]} and
          closure["terminal_request_digest"] == operation["request_digest"], "consumption_failure_contract")
    original = operation["reservation"]["target_prestart_closure"]["external"]
    check(original["value"]["producer_operation_id"] == producer["producer_operation_id"] and
          original["value"]["prestart"] == producer["prestart"] and
          original["value"]["terminal_evidence_digest"] == failure["original_normal_final_digest"] == producer["terminal_evidence_digest"] and
          failure["active_binding_generation"] == producer["active_binding_generation"], "consumption_failure_original_final")
    cap_id = "capability_" + owner
    cap_row = coordinator.connection.execute("SELECT value FROM invocation_capabilities WHERE capability_id=?", (cap_id,)).fetchone()
    capability = loads(cap_row[0]) if cap_row else None
    started = failure["attempt_identity_status_and_started_intent"]["started_intent"]
    if capability is not None:
        check(capability["authorization"]["producer_operation_id"] == owner and capability["state"] == "uncertain" and
              capability["started_intent"] == started and capability["invocation_epoch"] ==
              reserved["evidence"]["invocation_epoch_revoked_before_further_effects"]["epoch"] and
              capability["authorization"]["external_consumption"] == original and
              all(capability["authorization"]["identity"][k] == v for k, v in locator.items()) and
              capability["authorization"]["identity"]["attempt_id"] == producer["attempt_id"], "consumption_failure_capability")
        if capability.get("verification_intents"):
            owned_prefix(capability)
    else:
        check(started is None, "consumption_failure_missing_capability")
    pause = failure["pause_identity_status_and_claim_owner"]
    check(pause["pause_id"] == producer["pause_id"] and pause["owner"] == owner, "consumption_failure_claim")
    pause_row = coordinator.connection.execute("SELECT value FROM pause_ownership WHERE run_key=? AND pause_id=?",
                                             (digest(locator), producer["pause_id"])).fetchone()
    check(pause_row is not None and loads(pause_row[0])["owner"] == owner, "consumption_failure_pause_owner")
    stops = [r for r in history if r["phase"] == "consumption_failure_stop_verified"]
    check(len(stops) == 1 and stops[0]["revision"] == reserved["revision"] + 1 and
          stops[0]["lease_epoch"] == reserved["lease_epoch"], "consumption_failure_stop_phase")
    stop = stops[0]["evidence"]
    check(stop["same_failure_owner"] == owner and
          stop["original_external_normal_final_digest_unchanged"]["expected_digest"] == failure["original_normal_final_digest"],
          "consumption_failure_stop_binding")
    witness = stop["consumer_verifier_containment_stop_and_write_fence_proof"]
    safe = witness["proof"]["termination_or_not_dispatched"] in ("confirmed", {"tag": "not_dispatched"}) and all(
        witness["proof"][k] is True for k in ("write_lease_revocation", "verify_empty", "bounded_drain", "post_stop_stability"))
    check(witness["classification"] == ("safe_stop" if safe else "unavailable"), "consumption_failure_stop_class")
    authority = stop["run_authority_integrity_proof_or_unavailable"]
    check(authority["classification"] in ("appendable", "unavailable") and
          (authority["source"] is None) == (authority["classification"] == "unavailable"), "consumption_failure_authority")
    closed_safely = safe and authority["classification"] == "appendable"
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    records = parse_ledger(original_file(root, "execution_history.jsonl")).values
    settlements = [r for r in records if r.get("event") == "resource_settled" and
                   r["payload"]["evidence_digest"] == failure["failure_id_digest"]]
    active = [r for r in records if r.get("event") == "active_interval_settled" and r["payload"]["settlement_operation_id"] == owner]
    if closed_safely:
        check(operation["status"] == closure["terminal_closure"] == "committed" and
              operation["result"]["run_status"] == closure["run_status"] == "failed" and
              producer["active_binding_status"] == "released", "consumption_failure_failed_closure")
        disposition, = [r["evidence"] for r in history if r["phase"] == "consumption_failure_disposition_committed"]
        check(disposition["exact_pending_resource_settlements"] == settlements and
              disposition["active_binding_failure_release_proof"] == producer["close_disposition"] and
              producer["close_disposition"]["operation_id"] == owner and
              producer["close_disposition"]["failure_id_digest"] == failure["failure_id_digest"], "consumption_failure_release")
        pending = failure["pending_resource_operation_ids_and_settlement_snapshots"]["pending"]
        check({r["payload"]["resource_operation_id"] for r in settlements} == {r["payload"]["resource_operation_id"] for r in pending}
              and len(settlements) == len(pending), "consumption_failure_settlement_set")
        for settled in settlements:
            payload = settled["payload"]
            reservation, = [r for r in pending if r["payload"]["resource_operation_id"] == payload["resource_operation_id"]]
            actual = original["final"]["resource_actual"] if payload["resource_operation_id"] == producer["reservation_id"] else (
                stop["all_pending_resource_usage_or_conservative_charge"].get(payload["resource_operation_id"]))
            check(payload["operation_id"] == owner and payload["actual"] == actual and
                  payload["lease_epoch"] == reserved["lease_epoch"] and payload["phase_revision"] == failure["source_phase_revision"] + 4 and
                  payload["tokens"] == payload["cost"] == {"state": "unknown", "value": None} and reservation in records and
                  sum(r.get("event") == "resource_settled" and r["payload"]["resource_operation_id"] == payload["resource_operation_id"]
                      for r in records) == 1, "consumption_failure_settlement")
        for settled in active:
            payload = settled["payload"]
            interval, = [r["payload"] for r in records if r.get("event") == "active_interval_reserved" and
                         r["payload"]["interval_id"] == payload["interval_id"]]
            check(all(payload[k] == interval[k] for k in ("schema_version", "interval_id", "stage", "attempt_id",
                  "producer_operation_id", "owner_operation_id", "clock_epoch_id")) and
                  payload["owner_operation_id"] == owner and payload["producer_operation_id"] == producer["producer_operation_id"] and
                  payload["evidence_digest"] == failure["failure_id_digest"] and payload["phase_revision"] == failure["source_phase_revision"] + 4 and
                  payload["lease_epoch"] == reserved["lease_epoch"], "consumption_failure_interval_owner")
            check(sum(r.get("event") == "active_interval_settled" and r["payload"]["interval_id"] == payload["interval_id"]
                      for r in records) == 1, "consumption_failure_interval_unique")
            following = records[settled["event_index"]]
            check(following["record_type"] == "attempt" and following["event"] == "finished" and following["status"] == "failed" and
                  following["attempt_id"] == producer["attempt_id"] and following["artifact_head"] == settled["artifact_head"] and
                  following["error"] == {"type": "ConsumptionIntegrityFailure", "message": failure["failure_id_digest"]},
                  "consumption_failure_interval_disposition")
            if payload["disposition"] == "actual":
                check(payload["end_at"] == witness["trusted_stop_at"] and payload["actual_seconds"] ==
                      payload["end_at"]["monotonic_seconds"] - interval["start_at"]["monotonic_seconds"] and
                      0 <= payload["actual_seconds"] <= interval["maximum_seconds"], "consumption_failure_interval_duration")
            else:
                check(payload["disposition"] == "conservative_maximum" and payload["end_at"] is None and
                      payload["actual_seconds"] is None, "consumption_failure_interval_maximum")
    else:
        check(operation["status"] == "recovery_required" and closure["terminal_closure"] == "unavailable" and
              closure["run_status"] is None and producer["active_binding_status"] == "quarantined" and
              producer["close_disposition"] is None and not settlements and not active, "consumption_failure_unavailable")
        check(records == frozen["source"]["records"] or authority["classification"] == "unavailable",
              "consumption_failure_unavailable_ledger")
    return {"owner": owner, "source_phase": frozen["source_phase"], "failure": failure,
        "consumer_stop": witness, "authority": authority["classification"], "closure": closure["terminal_closure"],
        "active_settlements": active, "resource_settlements": settlements,
        "verification_reservations": [r["record"] for r in capability.get("verification_intents", [])
            if r["record"]["event"] == "resource_reserved"] if capability else []}


def read_backend_claim(root, producer, result, binding):
    """Check original Fake claim preimages without promoting them to Host evidence."""
    raw = original_file(root, Path("trace_backend_claims") / (producer["producer_operation_id"] + ".json"))
    value = loads(raw)
    keys(value, {"schema_version", "profile", "binding", "producer_operation_id", "task", "manifest", "receipt",
                 "result", "change_manifest", "seal", "tool_audit", "patch"}, "unaccepted_claim")
    check(raw == canonical_bytes(value) and value["schema_version"] == "0.1" and value["profile"] == "unaccepted_backend_claim" and
          value["binding"] == binding and value["producer_operation_id"] == producer["producer_operation_id"] and
          value["task"] == producer["prestart"]["task"] and value["manifest"] == producer["prestart"]["manifest"] and
          canonical_bytes(value["result"]) == result and sha256(result).hexdigest() == producer["result_digest"], "unaccepted_claim_binding")
    task, manifest = value["task"], value["manifest"]
    check(task["coding_backend_kind"] == "fake" and type(value["tool_audit"]) is str and
          (value["patch"] is None or type(value["patch"]) is str), "unaccepted_claim_types")
    receipt = validate_receipt(value["receipt"], task, manifest).value
    audit = value["tool_audit"].encode()
    validate_tool_audit(audit, task, manifest)
    changes = validate_change_manifest(value["change_manifest"], task, manifest).value
    seal = validate_workspace_seal(value["seal"], task, manifest, changes, audit).value
    from lqcd_agent.code_agent.ingress import RESULT_FIELDS
    result_value = value["result"]
    keys(result_value, set(RESULT_FIELDS), "unaccepted_result")
    check(result_value["result_digest"] == digest({k: v for k, v in result_value.items() if k != "result_digest"}) and
          all(result_value[k] == task[k] for k in ("case_id", "run_id", "cycle_id", "attempt_id", "producer_operation_id", "task_id", "task_digest")) and
          result_value["workspace_id"] == manifest["workspace_id"] and result_value["workspace_manifest_digest"] == manifest["manifest_digest"] and
          result_value["dispatch_receipt_digest"] == digest(receipt) and
          result_value["workspace_seal_digest"] == seal["seal_digest"] and result_value["change_manifest_digest"] == changes["change_manifest_digest"] and
          result_value["tool_audit_digest"] == sha256(audit).hexdigest() and result_value["patch_digest"] ==
          (sha256(value["patch"].encode()).hexdigest() if value["patch"] is not None else None), "unaccepted_claim_references")
    database = root / "fake_backend/fake_backend.sqlite"
    check(database.resolve() == database and not source_path(database).is_symlink(), "unaccepted_backend_database")
    with closing(sqlite3.connect(source_path(database).as_uri() + "?mode=ro", uri=True)) as connection:
        row = connection.execute("SELECT task_digest,manifest_digest,receipt,result FROM operations WHERE operation_id=?",
                                 (producer["producer_operation_id"],)).fetchone()
    check(row == (task["task_digest"], manifest["manifest_digest"], canonical_bytes(receipt), result), "unaccepted_immutable_backend")
    return raw, value


def read_source(coordinator, producer):
    """Read original bytes and journal state without claiming or publishing anything."""
    external = ExternalControl(coordinator)
    actual, final = external.final_evidence(coordinator.connection, producer["producer_operation_id"])
    check(actual == producer and actual["consumption_release"] is None, "unconsumed_original_producer")
    locator = actual["run_locator"]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    from lqcd_agent.control.execution import parse_ledger
    records = parse_ledger(original_file(root, "execution_history.jsonl")).values
    history = [loads(line) for line in original_file(root, "artifact_history.jsonl").splitlines()]
    check(not any(row["event"] == "registered" and row["slot"] == "code" and row["attempt_id"] == actual["attempt_id"]
                  for row in history), "unconsumed_domain_registration")
    task = validate_task(actual["prestart"]["task"]).value
    manifest = validate_manifest(actual["prestart"]["manifest"], task).value
    directory = Path("code_agent_control") / actual["attempt_id"]
    for name, value in (("code_agent_task.json", task), ("workspace_manifest.json", manifest)):
        check(original_file(root, directory / name) == canonical_bytes(value), "unconsumed_prestart_bytes")
    check(all(actual[key] == task[key] for key in ("producer_operation_id", "attempt_id", "cycle_id", "task_digest")) and
          actual["workspace_id"] == manifest["workspace_id"] and actual["workspace_manifest_digest"] == manifest["manifest_digest"] and
          actual["run_locator"] == {key: task[key] for key in ("case_id", "run_id")}, "unconsumed_owner")
    members = {}
    for kind, (_, name) in MEMBERS.items():
        path = root / directory / name
        if source_path(path).exists() or source_path(path).is_symlink():
            members[kind] = original_file(root, directory / name)
    receipt = members.get("receipt")
    check((receipt is None) == (actual["dispatch_receipt_digest"] is None), "unconsumed_receipt_presence")
    if receipt is not None:
        validate_receipt(receipt, task, manifest)
        check(actual["dispatch_receipt_reference"] == (directory / MEMBERS["receipt"][1]).as_posix() and
              sha256(receipt).hexdigest() == actual["dispatch_receipt_digest"], "unconsumed_original_receipt")
    # A non-normal final can retain an unaccepted backend result. Its absent seal is not a successful publication.
    result = members.get("external_result")
    check((result is None) == (actual["result_digest"] is None), "unconsumed_result_presence")
    if result is not None:
        check(sha256(result).hexdigest() == actual["result_digest"] and
              actual["result_reference"] == (directory / MEMBERS["external_result"][1]).as_posix(), "unconsumed_original_result")
    if actual["resolution_owner"] == "normal":
        check(all(kind in members for kind in ("receipt", "external_result", "seal", "change_manifest", "canonical_tool_audit")),
              "unconsumed_normal_closure")
        changes = validate_change_manifest(members["change_manifest"], task, manifest).value
        audit = validate_tool_audit(members["canonical_tool_audit"], task, manifest)
        seal = validate_workspace_seal(members["seal"], task, manifest, changes, members["canonical_tool_audit"]).value
        value = loads(result)
        check(result == canonical_bytes(value) and value["result_digest"] == digest({k: v for k, v in value.items() if k != "result_digest"}),
              "unconsumed_result_checksum")
        check(all(value[k] == task[k] for k in ("case_id", "run_id", "cycle_id", "attempt_id", "producer_operation_id", "task_id", "task_digest")) and
              value["workspace_id"] == manifest["workspace_id"] and value["workspace_manifest_digest"] == manifest["manifest_digest"] and
              value["dispatch_receipt_digest"] == actual["dispatch_receipt_digest"] and value["workspace_seal_digest"] == seal["seal_digest"] and
              value["change_manifest_digest"] == changes["change_manifest_digest"] and value["tool_audit_digest"] == seal["tool_audit_digest"] and
              value["patch_digest"] == (sha256(members["material"]).hexdigest() if "material" in members else None) and
              bool(changes["changes"]) == ("material" in members), "unconsumed_result_references")
        commands = {spec["spec_id"]: spec for spec in task["tool_policy"]}
        check(all(row["argv_digest"] == digest(commands[row["tool_id"]]["argv"]) and row["cwd"] == commands[row["tool_id"]]["cwd"] for row in audit),
              "unconsumed_audit_command")
        check(seal["seal_digest"] == actual["workspace_seal_digest"] == final["workspace_seal_digest"] and
              seal["stop_proof_digest"] == digest(final["stop_proof"]) and value["resource_usage"] == final["resource_actual"] and
              final["resource_actual"]["tool_calls"] == len(audit) and
              final["resource_actual"]["llm_calls"] == sum(row["resource_usage"]["llm_calls"] for row in audit), "unconsumed_observed_usage")
    else:
        check(not any(kind in members for kind in ("seal", "change_manifest", "canonical_tool_audit", "material")),
              "unconsumed_unaccepted_material")
    reservations = [row for row in records if row.get("event") == "resource_reserved" and
                    row["payload"]["resource_operation_id"] == actual["reservation_id"]]
    check(len(reservations) == 1 and digest(reservations[0]) == actual["reservation_digest"], "unconsumed_reservation")
    settlements = [row for row in records if row.get("event") == "resource_settled" and
                   row["payload"]["resource_operation_id"] == actual["reservation_id"]]
    check(len(settlements) <= 1, "unconsumed_unique_settlement")
    pauses = [row for row in records if row["record_type"] == "pause" and row["pause_id"] == actual["pause_id"]]
    check(pauses and pauses[0]["target_attempt_id"] == actual["attempt_id"], "unconsumed_pause")
    closure_row = coordinator.connection.execute("SELECT value FROM run_terminal_closure WHERE run_key=?", (digest(locator),)).fetchone()
    closure = loads(closure_row[0]) if closure_row else None
    terminal = closure["terminal_closure_owner_operation_id"] if closure else None
    detached = external.detached(coordinator.connection, actual)
    failure = read_consumption_failure(coordinator, actual)
    if terminal is not None:
        owner = coordinator.get(terminal)
        unavailable = actual["proof_kind"] == "unavailable" or failure is not None and failure["closure"] == "unavailable"
        check(owner["status"] == ("recovery_required" if unavailable else "committed") and
              owner["request"]["run_locator"] == locator and
              (bool(settlements) and settlements[0]["payload"]["operation_id"] == terminal or
               failure is not None and failure["closure"] == "unavailable" and not settlements), "unconsumed_terminal_owner")
    if failure is not None and failure["closure"] == "unavailable":
        stage = "unavailable_without_consumption"
        check(not detached, "unconsumed_consumer_unavailable")
    elif actual["proof_kind"] == "unavailable":
        stage = "unavailable_without_consumption"
        check(actual["operation_status"] == "recovery_required" and not detached, "unconsumed_unavailable")
    elif detached or terminal is not None:
        stage = "closed_without_consumption"
    else:
        stage = "normal_final_unconsumed"
        check(actual["resolution_owner"] == "normal" and not settlements and pauses[-1]["status"] == "opened", "unconsumed_pending")
    declaration = {"schema_version": "0.1", "producer_operation_id": actual["producer_operation_id"], "producer_snapshot": actual,
        **{kind + "_head": digest(actual["prestart"][kind]) for kind in ("task", "manifest", "core")},
        **{field: sha256(members[kind]).hexdigest() if kind in members else None for kind, (field, _) in MEMBERS.items()},
        "final_head": actual["terminal_evidence_digest"], "reservation_head": actual["reservation_digest"],
        "resolution_owner": actual["resolution_owner"], "resolution_operation_id": actual.get("resolution_owner_operation_id"),
        "terminal_operation_id": terminal, "pause_snapshot": pauses, "publication_stage": stage}
    return declaration, members


def project(events, proof, binding):
    try:
        keys(proof, FIELDS, "unconsumed_proof")
        check(proof["schema_version"] == "0.8" and type(proof["unconsumed_code_sources"]) is list, "unconsumed_version")
        projection = UnconsumedCodeProjection(proof)
        base = {key: value for key, value in proof.items() if key in BASE_FIELDS}
        base["schema_version"] = "0.2"
        # Only material declarations with an independently verified unconsumed owner leave the registered path.
        identities = {row["producer_operation_id"] for row in proof["unconsumed_code_sources"]}
        base["material_sources"] = [row for row in proof["material_sources"] if row["owner"]["producer_operation_id"] not in identities]
        return a05_trace._project(events, base, binding, ordinary=projection)
    except Invalid:
        raise
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, RecursionError, StopIteration) as error:
        raise Invalid("unconsumed_code_final", "provenance", "invalid_evidence") from error


class UnconsumedCodeProjection(PublicationPrefixProjection):
    def __init__(self, proof):
        super().__init__(proof)
        self.unconsumed, self.unconsumed_material, self.unaccepted_results = {}, {}, {}
        self.failure_intervals = set()
        self.backend_seals = set()
        self.failure_owners = set()

    def validate(self, sources, executions, roots, events):
        self.base_sources, self.executions, self.roots = sources, executions, roots
        declarations = self.proof["unconsumed_code_sources"]
        seen, materials = set(), set()
        for declaration in declarations:
            keys(declaration, DECLARATION_FIELDS, "unconsumed_source")
            identity = declaration["producer_operation_id"]
            check(identity not in seen, "unconsumed_duplicate")
            seen.add(identity)
            task = sources[declaration["task_head"]]["value"]
            run = task["case_id"], task["run_id"]
            producer = self.producer(run, task)
            check(producer["producer_operation_id"] == identity, "unconsumed_task_owner")
            with closing(sqlite3.connect(source_path(self.database(run)).as_uri() + "?mode=ro", uri=True)) as connection:
                connection.row_factory = sqlite3.Row
                coordinator = object.__new__(Coordinator)
                coordinator.root, coordinator.connection = source_path(roots[run].parent.parent), connection
                expected, members = read_source(coordinator, producer)
                failure = read_consumption_failure(coordinator, producer)
                terminal = coordinator.get(expected["terminal_operation_id"]) if expected["terminal_operation_id"] else None
                parent = coordinator.get(producer["parent_control_operation_id"])
                check(parent["status"] == "committed" and parent["operation_type"] == "advance_run" and
                      parent["request"]["run_locator"] == producer["run_locator"], "unconsumed_parent_owner")
            check(declaration == expected, "unconsumed_original_snapshot")
            owner = {key: task[key] for key in ("case_id", "run_id", "attempt_id", "producer_operation_id")}
            owner["workspace_id"] = producer["workspace_id"]
            if failure is not None:
                self.bind_failure(failure, owner, events)
            for kind, raw in members.items():
                field = MEMBERS[kind][0]
                head = declaration[field]
                unaccepted = kind == "external_result" and producer["resolution_owner"] != "normal"
                if kind in ("material", "canonical_tool_audit") or unaccepted:
                    material_kind = "material" if unaccepted else kind
                    key = material_kind, head, tuple(owner[k] for k in a05_trace.IDENTITIES)
                    matches = [row for row in self.proof["material_sources"] if row.get("kind") == material_kind and
                               row.get("sha256") == head and row.get("owner") == owner]
                    check(len(matches) == 1, "unconsumed_material_declaration")
                    keys(matches[0], {"kind", "sha256", "content", "owner"}, "unconsumed_material")
                    check(matches[0]["content"].encode() == raw, "unconsumed_material_bytes")
                    materials.add(key)
                    if unaccepted:
                        claim_raw, claim = read_backend_claim(roots[run].parent.parent, producer, raw, self.proof["binding"])
                        claim_head = sha256(claim_raw).hexdigest()
                        claim_rows = [r for r in self.proof["material_sources"] if r["kind"] == "material" and
                                      r["sha256"] == claim_head and r["owner"] == owner]
                        check(len(claim_rows) == 1 and claim_rows[0]["content"].encode() == claim_raw, "unaccepted_claim_declaration")
                        materials.add(("material", claim_head, tuple(owner[k] for k in a05_trace.IDENTITIES)))
                        wrapper_head = self.bind_backend_claim(claim, head, declaration, owner)
                        self.unaccepted_results[head] = wrapper_head
                        continue
                    value = [loads(line) for line in raw.splitlines()] if kind == "canonical_tool_audit" else None
                    wrapper = {"kind": kind, "owner": owner, "sha256": head, "value": value}
                    wrapper_head = self.internal_source(wrapper, owner)
                    self.unconsumed_material[wrapper_head] = wrapper
                    for typed_kind in ("seal", "external_result"):
                        source_head = declaration[MEMBERS[typed_kind][0]]
                        if source_head is not None:
                            self.reference(source_head, ("tool_audit_digest" if kind == "canonical_tool_audit" else "patch_digest",), wrapper_head)
                else:
                    check(head in sources and sources[head]["value"] == loads(raw) and raw == canonical_bytes(loads(raw)) and
                          {"kind": kind, "source_sha256": head} in self.proof["typed_sources"], "unconsumed_typed_bytes")
                    self.bind_source_owner(head, owner)
            if terminal is not None and terminal["operation_type"] == "close_run":
                trigger = terminal["request"]["trigger"]
                trigger_head = self.internal_source(trigger, owner)
                check(digest(trigger) == terminal["request"]["trigger_digest"] and
                      trigger["record"] == sources[trigger["execution_head"]]["value"], "unconsumed_terminal_trigger")
                self.reference(trigger_head, ("record",), trigger["execution_head"])
                self.reference(trigger_head, ("execution_head",), trigger["execution_head"])
                for row in executions[run]:
                    if row.get("operation_id") == terminal["operation_id"] and "terminal_trigger" in row.get("proof", {}):
                        check(row["proof"]["terminal_trigger"] == trigger_head, "unconsumed_trigger_binding")
                        self.reference(digest(row), ("proof", "terminal_trigger"), trigger_head)
            self.unconsumed[declaration["final_head"]] = declaration
            matching = [item for item in events if item["event"] == "unconsumed_code_final" and item["external_operation_id"] == identity]
            check(len(matching) == 1 and matching[0]["result_digest"] == declaration["final_head"] and
                  matching[0]["guard"] == declaration["publication_stage"] and matching[0]["owner"] == declaration["resolution_owner"] and
                  matching[0]["operation_id"] == declaration["terminal_operation_id"] and matching[0]["lease_epoch"] == producer["lease_epoch"] and
                  matching[0]["run_id"] == run[1] and matching[0]["attempt_id"] == task["attempt_id"], "unconsumed_event")
        actual_materials = {(row["kind"], row["sha256"], tuple(row["owner"][k] for k in a05_trace.IDENTITIES))
                            for row in self.proof["material_sources"] if row["owner"]["producer_operation_id"] in seen}
        check(actual_materials == materials and sum(row["owner"]["producer_operation_id"] in seen for row in self.proof["material_sources"]) == len(materials),
              "unconsumed_material_set")
        required = set()
        for run in roots:
            with closing(sqlite3.connect(source_path(self.database(run)).as_uri() + "?mode=ro", uri=True)) as connection:
                for row in connection.execute("SELECT value FROM external_operations"):
                    p = loads(row[0])
                    if p["run_locator"] != dict(zip(("case_id", "run_id"), run)) or p["terminal_evidence_digest"] is None:
                        continue
                    registered = any(r["value"].get("event") == "registered" and
                        r["value"].get("slot") == "code" and r["value"].get("attempt_id") == p["attempt_id"] and
                        r["value"].get("run_id") == run[1] for r in sources.values())
                    if p["consumption_release"] is None and not registered:
                        required.add(p["producer_operation_id"])
        check(required == seen and sum(item["event"] == "unconsumed_code_final" for item in events) == len(seen), "unconsumed_source_set")
        check(sum(item["event"] == "consumption_failure_source" for item in events) == len(self.failure_owners) and
              sum("durable_consumption_failure" in row["value"] for row in sources.values()) == len(self.failure_owners),
              "consumption_failure_source_set")
        super().validate(sources, executions, roots, events)

    def active_interval_source(self, value):
        return digest(value) in self.failure_intervals

    def bind_backend_claim(self, claim, raw_head, declaration, owner):
        heads = {}
        for kind in ("result", "seal", "change_manifest"):
            heads[kind] = self.internal_source({"unaccepted_backend_kind": kind, "value": claim[kind]}, owner)
        heads["audit"] = self.internal_source({"unaccepted_backend_kind": "audit", "value":
            [loads(line) for line in claim["tool_audit"].splitlines()]}, owner)
        if claim["patch"] is not None:
            heads["patch"] = self.internal_source({"unaccepted_patch_bytes": sha256(claim["patch"].encode()).hexdigest()}, owner)
        for kind, checksum in (("result", "result_digest"), ("seal", "seal_digest"), ("change_manifest", "change_manifest_digest")):
            self.sizes[heads[kind], ("value", checksum)] = ("self", None)
        references = {"task_digest": declaration["task_head"], "workspace_manifest_digest": declaration["manifest_head"],
            "dispatch_receipt_digest": declaration["receipt_head"], "workspace_seal_digest": heads["seal"],
            "change_manifest_digest": heads["change_manifest"], "tool_audit_digest": heads["audit"], "patch_digest": heads.get("patch")}
        for kind in ("result", "seal"):
            for key, target in references.items():
                if key in claim[kind] and claim[kind][key] is not None:
                    check(target is not None, "unaccepted_claim_material")
                    self.reference(heads[kind], ("value", key), target)
        self.backend_seals.add(heads["seal"])
        self.unconsumed_material[heads["audit"]] = {"kind": "canonical_tool_audit"}
        return heads["result"]

    def bind_failure(self, failure, owner, events):
        check(failure["owner"] not in self.failure_owners, "consumption_failure_duplicate_owner")
        self.failure_owners.add(failure["owner"])
        wrapper = {"durable_consumption_failure": failure}
        head = digest(wrapper)
        check(head in self.base_sources and self.base_sources[head]["value"] == wrapper, "consumption_failure_source")
        self.bind_source_owner(head, owner)
        matching = [e for e in events if e["event"] == "consumption_failure_source" and e["operation_id"] == failure["owner"]]
        check(len(matching) == 1 and matching[0]["result_digest"] == head and matching[0]["owner"] == failure["owner"] and
              matching[0]["guard"] == failure["closure"] and matching[0]["run_id"] == owner["run_id"] and
              matching[0]["attempt_id"] == owner["attempt_id"], "consumption_failure_event")
        identity = failure["failure"]["failure_id_digest"]
        opaque = self.internal_source({"bound_failure_identity": identity, "resume_owner": failure["owner"]}, owner)
        references = {"failure_id_digest": opaque, "trusted_rejection_digest": opaque}
        self.sizes[head, ("durable_consumption_failure", "failure", "terminal_disposition_contract_digest")] = ("self", None)
        started = failure["failure"]["attempt_identity_status_and_started_intent"]["started_intent"]
        if started is not None:
            from lqcd_agent.control.execution import parse_ledger
            prefix = ("durable_consumption_failure", "failure", "attempt_identity_status_and_started_intent", "started_intent")
            records = self.executions[owner["case_id"], owner["run_id"]]
            for key in ("previous", "content"):
                parsed = parse_ledger(started[key].encode()).values
                check(parsed == records[:len(parsed)] and started[key].encode() ==
                      b"".join(canonical_bytes(row) + b"\n" for row in parsed), "consumption_failure_started_prefix")
                self.reference(head, prefix + (key,), digest(parsed[-1]))
            for key in ("previous_index", "index"):
                index = loads(started[key])
                check(canonical_bytes(index).decode() == started[key] and index["case_id"] == owner["case_id"] and
                      index["run_id"] == owner["run_id"], "consumption_failure_started_index")
                index_head = self.internal_source(index, owner)
                for field in ("execution_head", "artifact_head"):
                    check(index[field] in self.base_sources, "consumption_failure_index_head")
                    self.reference(index_head, (field,), index[field])
                for slot, pointer in index["current"].items():
                    if pointer is not None:
                        matching = [h for h, row in self.base_sources.items() if row["value"].get("event") == "registered" and
                            row["value"].get("pointer") == pointer and row["value"].get("run_id") == owner["run_id"] and
                            row["value"].get("case_id") == owner["case_id"] and row["value"].get("slot") == slot]
                        check(len(matching) == 1, "consumption_failure_index_registration")
                        self.reference(index_head, ("current", slot), matching[0])
                self.reference(head, prefix + (key,), index_head)
        for row in failure["active_settlements"]:
            source_head = digest(row)
            check(source_head in self.base_sources and self.base_sources[source_head]["value"] == row, "consumption_failure_active_source")
            self.failure_intervals.add(source_head)
            self.reference(source_head, ("payload", "evidence_digest"), opaque)
        for row in failure["resource_settlements"]:
            self.reference(digest(row), ("payload", "evidence_digest"), opaque)
        for row in failure["verification_reservations"]:
            for key in ("input_digest", "config_digest"):
                bound = self.internal_source({"original_verification_reservation": row["payload"]["resource_operation_id"],
                    "resume_owner": failure["owner"], "field": key, "opaque_digest": row["payload"][key]}, owner)
                self.reference(digest(row), ("payload", key), bound)
        for source_head, source in list(self.base_sources.items()) + [(head, {"value": wrapper})]:
            value = source["value"]
            if source_head != head and (value.get("case_id"), value.get("run_id")) != (owner["case_id"], owner["run_id"]):
                continue
            def walk(item, path=()):
                if type(item) is dict:
                    embedded = digest(item)
                    if source_head == head and path and embedded in self.base_sources and embedded != source_head:
                        self.reference(source_head, path, embedded)
                        return
                    for key, child in item.items():
                        target = references.get(key) if child == identity else None
                        if target is not None:
                            self.reference(source_head, path + (key,), target)
                        elif key == "message" and item.get("type") == "ConsumptionIntegrityFailure" and child == identity:
                            self.reference(source_head, path + (key,), opaque)
                        elif source_head == head and type(child) is str and key in ("execution_head", "artifact_head", "checkpoint_head",
                                "original_normal_final_digest", "previous_execution_head", "opened_head") and child in self.base_sources:
                            self.reference(source_head, path + (key,), child)
                        else:
                            walk(child, path + (key,))
                elif type(item) is list:
                    for i, child in enumerate(item):
                        walk(child, path + (i,))
            walk(value)

    def encode(self, head, path, project_source):
        if head in self.backend_seals and path == ("value", "sealed_at"):
            return ["validated_clock", "sealed_at"]
        if head in self.unconsumed_material:
            wrapper = self.unconsumed_material[head]
            if not path and wrapper["kind"] in ("material", "unaccepted_external_result"):
                return [wrapper["kind"], wrapper["owner"], wrapper["sha256"]]
            if path == ("sha256",):
                return ["validated_audit_bytes"]
            if len(path) == 3 and path[0] == "value" and path[-1] in ("start_at", "end_at"):
                return ["validated_clock", path[-1]]
        return super().encode(head, path, project_source)

    def finish_content(self, head, content, project_source):
        content = super().finish_content(head, content, project_source)
        if head not in self.unconsumed:
            return content
        declaration = self.unconsumed[head]
        producer = declaration["producer_snapshot"]
        identity = {k: producer[k] for k in ("producer_operation_id", "phase_revision", "lease_epoch", "operation_phase", "operation_status",
                    "active_binding_status", "active_binding_generation", "resolution_owner", "worker_owner_id")}
        identity.update({k: declaration[k] for k in ("publication_stage", "resolution_operation_id", "terminal_operation_id")})
        references = [[field, project_source(self.unaccepted_results.get(declaration[field], declaration[field]))] for field in ("task_head", "manifest_head", "core_head", "receipt_head",
                      "external_result_head", "seal_head", "change_manifest_head", "reservation_head") if declaration[field] is not None]
        return ["unconsumed_code_provenance", content, identity, references]
