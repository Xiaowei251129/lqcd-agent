"""Explicit trace 0.6 / proof 0.3 ordinary provenance, without authority."""
from hashlib import sha256
from pathlib import Path
import sqlite3

from lqcd_agent.agents.decision_coordinator import validate_product_diagnostic
from lqcd_agent.artifacts.registry import SLOT_BY_ATTEMPT_KIND, STATE_FIELDS_BY_SLOT
from lqcd_agent.control.budget import validate_budget_payload, validate_policy, validate_fingerprint
from lqcd_agent.control.execution import replay
from lqcd_agent.control.projections import bounded_projection
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from lqcd_agent.graph.state import PRODUCT_CONTEXT_SLOTS, validate_remediation_packet

from . import a05_trace
from .fault_source_trace import source_path
from .strict_json import Invalid, keys, require


MEMBERS = {
    "method_planner": {"method_plan.json", "method_planner_diagnostic.json"},
    "analysis_engineer": {"run_result.json", "analysis_outputs/result.json", "analysis_engineer_diagnostic.json"},
    "scientific_reviewer": {"scientific_review_report.json", "scientific_reviewer_diagnostic.json"},
    "decision_coordinator": {"decision_log.json", "decision_coordinator_diagnostic.json"},
    "human_gate": {"approval_packet/request.json"},
    "memory_report": {"memory_update.json", "final_report.md"},
}
AUTHORIZATION = {
    "producer_operation_id", "activation_result_revision", "identity", "heads", "manifest", "projection",
    "artifact_history_digest", "producing_epoch", "terminal_closure_revision", "checkpoint_anchor_kind", "scope",
}
PRODUCER = {
    "operation_id", "idempotency_scope", "idempotency_key", "request_digest", "operation_type", "operation_variant",
    "status", "phase", "phase_revision", "worker_owner_id", "lease_epoch", "lease_expires", "request", "reservation",
    "result", "error", "created_at", "updated_at",
}
CALL = {
    "schema_version", "profile", "reservation_head", "capability_id", "authorization", "producer",
    "input", "config", "outcome", "exception",
}


def check(condition, field):
    require(condition, "ordinary_trace", field, "invalid_evidence")


def project(events, proof, binding):
    try:
        fields = {"schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources",
                  "workspace_roots", "ordinary_calls", "ordinary_members"}
        keys(proof, fields, "ordinary_proof")
        check(proof["schema_version"] == "0.3", "proof_version")
        extension = OrdinaryProjection(proof)
        base = {key: value for key, value in proof.items() if key not in ("ordinary_calls", "ordinary_members")}
        base["schema_version"] = "0.2"
        return a05_trace._project(events, base, binding, ordinary=extension)
    except Invalid:
        raise
    except (KeyError, TypeError, ValueError, OSError, RecursionError, StopIteration) as error:
        raise Invalid("ordinary_trace", "provenance", "invalid_evidence") from error


class OrdinaryProjection:
    def __init__(self, proof):
        self.proof = proof
        self.sources, self.owners, self.refs, self.refs_at, self.sizes = {}, {}, {}, {}, {}
        self.registered, self.members, self.member_values, self.observations = {}, {}, {}, {}
        self.member_bindings = []
        self.human_snapshots = {}

    def bind_source_owner(self, head, owner):
        """Keep each verified origin separately in the explicit product version."""
        bindings = self.owner_bindings.setdefault(head, [])
        if owner not in bindings:
            bindings.append(dict(owner))
        self.owners[head] = {key: value for key, value in bindings[0].items()
                             if all(binding.get(key) == value for binding in bindings)}

    def add(self, declaration, owner, *, report=False):
        keys(declaration, {"schema_version", "profile", "sha256", "content"}, "ordinary_source")
        check(declaration["schema_version"] == "0.1" and (declaration["profile"] in
              ("input", "config", "outcome", "member", "report", "reservation_payload", "analysis_spec", "analysis_manifest",
               "fingerprint", "causal_context", "grant") or
              getattr(self, "maximum_sources", False) and declaration["profile"] in
              ("maximum_evidence", "maximum_observation")), "source_profile")
        check(type(declaration["content"]) is str, "source_content")
        raw = declaration["content"].encode()
        check(sha256(raw).hexdigest() == declaration["sha256"], "source_bytes")
        value = declaration["content"] if report else loads(raw)
        head = declaration["sha256"]
        if head in self.base_sources:
            original = self.base_sources[head]
            check(original["value"] == value, "source_collision")
            human_request = declaration["profile"] == "member" and original["kind"] == "execution_0_4" and value.get("record_type") == "human_request"
            typed_context = declaration["profile"] == "causal_context" and original["kind"] == "canonical_json" and any(
                row["source_sha256"] == head and row["kind"] in ("code_context", "analysis_context") for row in self.proof["typed_sources"])
            check(human_request or typed_context, "cross_profile_alias")
            return head, value
        row = {"kind": "ordinary", "sha256": head, "value": value, "references": []}
        check(head not in self.sources or self.sources[head] == row, "source_collision")
        self.sources[head] = row
        run_owner = {k: owner[k] for k in ("case_id", "run_id")}
        if getattr(self, "product_sources", False):
            self.bind_source_owner(head, owner)
        else:
            check(head not in self.owners or self.owners[head] == run_owner, "foreign_source")
            self.owners[head] = run_owner
        self.refs.setdefault(head, {})
        return head, value

    def reference(self, head, path, target):
        if head in self.sources:
            self.refs[head][path] = target
        else:
            self.refs_at[head, path] = target

    def validate(self, sources, executions, roots, events):
        self.base_sources, self.executions, self.roots = sources, executions, roots
        check(type(self.proof["ordinary_calls"]) is list and type(self.proof["ordinary_members"]) is list, "arrays")
        for head, row in sources.items():
            value = row["value"]
            if row["kind"] == "canonical_json" and value.get("event") == "registered":
                pointer = value["pointer"]
                key = (value["case_id"], value["run_id"], value["artifact_id"])
                check(key not in self.registered, "duplicate_registration")
                check(pointer["attempt_kind"] in MEMBERS or pointer["attempt_kind"] == "code_agent", "member_role")
                check(all(pointer[k] == value[k] for k in ("artifact_id", "slot", "attempt_id", "members", "status")), "pointer")
                check(pointer["slot"] == SLOT_BY_ATTEMPT_KIND[pointer["attempt_kind"]], "slot")
                run = (value["case_id"], value["run_id"])
                scheduled = [r for r in executions[run] if r["record_type"] == "attempt" and
                             r["event"] == "scheduled" and r["attempt_id"] == value["attempt_id"]]
                check(len(scheduled) == 1 and scheduled[0]["attempt_kind"] == pointer["attempt_kind"], "producing_attempt")
                self.registered[key] = (head, value)
                for member in value["members"]:
                    self.members[(*run, value["artifact_id"], member["canonical_path"])] = member
        declared = set()
        for declaration in self.proof["ordinary_members"]:
            keys(declaration, {"schema_version", "registration_head", "member", "sha256", "content"}, "ordinary_member")
            check(declaration["schema_version"] == "0.1" and type(declaration["content"]) is str, "member_version")
            registration = sources[declaration["registration_head"]]["value"]
            if registration.get("event") == "protected_snapshot_registered":
                self.human_snapshot(declaration, registration)
                declared.add((declaration["registration_head"], declaration["member"]))
                continue
            pointer = registration["pointer"]
            node, name = pointer["attempt_kind"], declaration["member"]
            check(node in MEMBERS and name in MEMBERS[node], "member_allowlist")
            selected = [m for m in registration["members"] if m["logical_name"] == name]
            check(len(selected) == 1, "member_registration")
            member = selected[0]
            identity = {k: registration[k] for k in ("case_id", "run_id", "attempt_id")}
            key = (declaration["registration_head"], name)
            check(key not in declared, "duplicate_member")
            declared.add(key)
            raw = declaration["content"].encode()
            check(declaration["sha256"] == member["sha256"] == sha256(raw).hexdigest() and
                  type(member["size_bytes"]) is int and len(raw) == member["size_bytes"], "member_bytes")
            check(member["canonical_path"] == "attempts/" + identity["attempt_id"] + "/" + name and
                  member["projection_path"] == name, "member_namespace")
            head, value = self.add({"schema_version": "0.1", "profile": "report" if name.endswith(".md") else "member",
                "sha256": declaration["sha256"], "content": declaration["content"]}, identity, report=name.endswith(".md"))
            if name.endswith("_diagnostic.json"):
                validate_product_diagnostic(value)
            elif name == "approval_packet/request.json":
                check(value in executions[identity["case_id"], identity["run_id"]] and
                      value["record_type"] == "human_request", "human_request")
            elif name != "analysis_outputs/result.json" and name.endswith(".json"):
                check(type(value) is dict and value.get("schema_version") == "0.1" and value.get("producer") == node and
                      value.get("attempt_kind") == node and all(value.get(k) == v for k, v in identity.items()), "host_identity")
            self.member_values[head] = (identity, node, name, value)
            self.member_bindings.append((identity, node, name, value))
        required = {(head, member["logical_name"]) for head, registration in self.registered.values()
                    if registration["pointer"]["attempt_kind"] != "code_agent" for member in registration["members"]}
        required.update((head, member["logical_name"]) for head, row in sources.items()
                        if row["value"].get("event") == "protected_snapshot_registered" and
                        row["value"].get("protected_kind") == "human_response" for member in row["value"]["members"])
        check(declared == required, "member_source_gap")
        reservations, settlements = {}, {}
        for records in executions.values():
            for record in records:
                if record["record_type"] != "budget":
                    continue
                payload = record["payload"]
                if record["event"] == "resource_reserved" and payload["resource_kind"] in ("llm_call", "tool_call"):
                    check(digest(record) not in reservations, "duplicate_reservation")
                    reservations[digest(record)] = record
                elif record["event"] == "resource_settled":
                    key = (record["case_id"], record["run_id"], payload["resource_operation_id"])
                    check(key not in settlements, "duplicate_settlement")
                    settlements[key] = record
        seen = set()
        for call in self.proof["ordinary_calls"]:
            keys(call, CALL, "ordinary_call")
            check(call["schema_version"] == "0.1" and call["profile"] in ("primitive", "scoped_llm", "analysis_tool"), "call_profile")
            head = call["reservation_head"]
            check(head in reservations and head not in seen, "call_reservation")
            seen.add(head)
            record = reservations[head]
            payload = record["payload"]
            run = (record["case_id"], record["run_id"])
            auth = call["authorization"]
            check(set(auth) in (AUTHORIZATION, AUTHORIZATION | {"target_preparation", "preparation_receipt"}), "authorization_fields")
            database = roots[run].parent.parent / ".lqcd/control_operations.sqlite"
            check(source_path(database).is_file() and not source_path(database).is_symlink(), "capability_database")
            try:
                connection = sqlite3.connect(source_path(database).as_uri() + "?mode=ro", uri=True)
                connection.row_factory = sqlite3.Row
                try:
                    stored = connection.execute("SELECT value FROM invocation_capabilities WHERE capability_id=?",
                                                (call["capability_id"],)).fetchone()
                    check(stored is not None, "original_capability")
                    capability = loads(stored[0])
                    check(capability["authorization"] == auth and capability["authorization_digest"] == digest(auth), "original_authorization")
                    stored_producer = connection.execute("SELECT * FROM control_operations WHERE operation_id=?",
                                                         (auth["producer_operation_id"],)).fetchone()
                    check(stored_producer is not None, "original_producer")
                    original_producer = dict(stored_producer)
                    for field in ("request", "reservation", "result", "error", "created_at", "updated_at"):
                        original_producer[field] = None if original_producer[field] is None else loads(original_producer[field])
                    check(canonical_bytes(original_producer) == canonical_bytes(call["producer"]) and
                          original_producer["status"] == "committed", "original_producer_snapshot")
                finally:
                    connection.close()
            except sqlite3.Error as error:
                raise Invalid("ordinary_trace", "capability_database", "invalid_evidence") from error
            owner = {**dict(zip(("case_id", "run_id"), run)), "attempt_id": payload["attempt_id"]}
            check(set(auth["identity"]) == {"case_id", "run_id", "attempt_id", "attempt_kind"} and
                  all(auth["identity"][k] == v for k, v in owner.items()) and auth["scope"] == "attempt_execution" and
                  auth["terminal_closure_revision"] == 0, "authorization_owner")
            producer = call["producer"]
            keys(producer, PRODUCER, "ordinary_producer")
            check(producer["operation_id"] == auth["producer_operation_id"] and
                  call["capability_id"] == "capability_" + producer["operation_id"] and
                  payload["resource_operation_id"].startswith(call["capability_id"] + ":") and
                  producer["lease_epoch"] == auth["producing_epoch"] and
                  producer["phase_revision"] == auth["activation_result_revision"], "producer_owner")
            matching = [e for e in events if e["operation_id"] == producer["operation_id"] and
                        e["phase_revision"] == producer["phase_revision"] and e["lease_epoch"] == producer["lease_epoch"]]
            check(len(matching) == 1 and matching[0]["result_digest"] == digest(producer["result"]) and
                  producer["result"]["capability_id"] == call["capability_id"], "producer_phase")
            check(matching[0]["owner"] == producer["worker_owner_id"] and matching[0]["status"] == producer["status"] and
                  matching[0]["phase"] == producer["phase"] and matching[0]["event"] ==
                  "control." + producer["operation_type"] + "." + producer["operation_variant"] + "." + producer["phase"], "producer_control_owner")
            check(auth["manifest"] == sources[auth["heads"]["checkpoint_head"]]["value"], "authorization_head")
            records = executions[run]
            projection = auth["projection"]
            check(auth["heads"] == {k: projection[k] for k in ("execution_head", "artifact_head", "checkpoint_head")}, "authorization_heads")
            prefix = records[:projection["execution_event_index"]]
            anchored = replay(prefix)
            check(digest(prefix[-1]) == auth["heads"]["execution_head"], "authorization_prefix")
            index = {"case_id": run[0], "run_id": run[1], "current": projection["current_artifacts"]}
            expected = bounded_projection(anchored, artifact_index=index, artifact_head=projection["artifact_head"],
                                          artifact_event_index=projection["artifact_event_index"]).value
            check(projection == {**expected, "checkpoint_head": auth["manifest"]["checkpoint_head"]} and
                  all(projection[k] == v for k, v in auth["identity"].items()), "authorization_projection")
            if auth["checkpoint_anchor_kind"] == "same_head":
                check({**sources[auth["manifest"]["state_digest"]]["value"],
                       "checkpoint_head": auth["manifest"]["checkpoint_head"]} == projection, "checkpoint_anchor")
            else:
                check(auth["checkpoint_anchor_kind"] == "owned_transition" and
                      auth["manifest"]["execution_event_index"] < projection["execution_event_index"], "checkpoint_anchor")
            check(record["event_index"] > auth["manifest"]["execution_event_index"], "reservation_order")
            started = [r for r in records[:record["event_index"]] if r["record_type"] == "attempt" and
                       r["event"] == "started" and r["attempt_id"] == owner["attempt_id"]]
            check(len(started) == 1, "started_invocation")
            before = replay(records[:record["event_index"] - 2]).projection.value
            selected_policy = validate_policy(loads((source_path(roots[run] / "budget_policy.json")).read_bytes())).value
            maximum = {"llm_calls": int(payload["resource_kind"] == "llm_call"),
                       "tool_calls": int(payload["resource_kind"] == "tool_call"),
                       "verification_commands": 0, "active_seconds": payload["timeout_seconds"]}
            limits, remaining = {}, {}
            for dimension in maximum:
                names = (dimension + "_per_attempt", dimension + "_per_run")
                limits[dimension] = 0 if dimension == "verification_commands" else min(selected_policy["limits"][key] for key in names)
                remaining[dimension] = 0 if dimension == "verification_commands" else min(before["budget"]["dimensions"][key]["remaining"] for key in names)
            check(record["policy_digest"] == selected_policy["policy_digest"] and payload["maximum_charge"] == maximum and
                  payload["applicable_limits"] == limits and payload["remaining_before"] == remaining and
                  all(payload[key] is None for key in ("task_digest", "producer_operation_id", "workspace_id")), "reservation_budget")
            input_head, input_value = self.add(call["input"], owner)
            config_head, config_value = self.add(call["config"], owner)
            check(call["input"]["profile"] == "input" and call["config"]["profile"] == "config" and
                  input_head == payload["input_digest"] and config_head == payload["config_digest"], "request_digest")
            self.reference(head, ("payload", "input_digest"), input_head)
            self.reference(head, ("payload", "config_digest"), config_head)
            if call["profile"] == "scoped_llm":
                check(payload["resource_kind"] == "llm_call" and config_value ==
                      {"node": auth["identity"]["attempt_kind"], "structured_output": True}, "llm_config")
                self.context(input_head, input_value, auth, record)
            elif call["profile"] == "analysis_tool":
                check(payload["resource_kind"] == "tool_call", "analysis_resource_kind")
                self.analysis_tool(input_head, input_value, config_value, auth)
            else:
                check(type(input_value) in (str, int, float, bool, type(None)) and
                      type(config_value) in (str, int, float, bool, type(None)), "primitive_scalar")
            settlement = settlements.get((*run, payload["resource_operation_id"]))
            if getattr(self, "maximum_sources", False) and settlement is not None and settlement["payload"]["actual"] is None:
                self.maximum_settlement(call, record, settlement, producer, owner)
            else:
                if call["exception"] is not None:
                    keys(call["exception"], {"type", "message"}, "ordinary_exception")
                    check(type(call["exception"]["type"]) is str and bool(call["exception"]["type"]) and
                          type(call["exception"]["message"]) is str, "exception_fields")
                    check(call["outcome"] is None and settlement is None, "exception_settlement")
                    self.observations[head] = ("exception", call["exception"])
                if settlement is not None:
                    check(call["outcome"] is not None and call["exception"] is None, "settled_source_gap")
                    result_head, result = self.add(call["outcome"], owner)
                    check(call["outcome"]["profile"] == "outcome" and result_head == settlement["payload"]["evidence_digest"], "outcome_digest")
                    check(all(settlement["payload"][key] == producer[key] for key in ("operation_id", "lease_epoch", "phase_revision")) and
                          settlement["event_index"] > record["event_index"], "settlement_publisher")
                    self.reference(digest(settlement), ("payload", "evidence_digest"), result_head)
                    if call["profile"] == "scoped_llm":
                        keys(result, {"diagnostic", "content"}, "ordinary_llm_result")
                        check(result["diagnostic"]["fingerprint"] is None and type(result["content"]) is dict, "agent_outcome")
                        self.agent_result(owner, auth["identity"]["attempt_kind"], result)
                        self.evidence(result_head, result["diagnostic"]["evidence"], ("diagnostic", "evidence"), run)
                else:
                    state = replay(records).projection.value
                    check(state["run_status"] == "running" and state["attempt_status"] == "running", "unsettled_prefix")
                    if call["outcome"] is not None:
                        # A return can precede a clock/overrun rejection; it is no settlement.
                        result_head, _ = self.add(call["outcome"], owner)
                        self.observations[head] = ("unsettled_return", result_head)
            previous = records[record["event_index"] - 2]
            check(previous["event"] == "decision_recorded" and previous["payload"]["proposal_id"] == digest(payload), "reservation_decision")
            payload_head, _ = self.add({"schema_version": "0.1", "profile": "reservation_payload",
                "sha256": digest(payload), "content": canonical_bytes(payload).decode()}, owner)
            self.reference(payload_head, ("input_digest",), input_head)
            self.reference(payload_head, ("config_digest",), config_head)
            self.reference(digest(previous), ("payload", "proposal_id"), payload_head)
        check(seen == set(reservations), "request_source_gap")
        self.verification_members(sources, executions)
        for head, (_, _, _, value) in self.member_values.items():
            if type(value) is dict:
                self.member_references(head, value)
        for head, row in sources.items():
            value = row["value"]
            if row["kind"] == "canonical_json" and value.get("event") == "registered":
                self.structural(head, value)
            elif value.get("schema_version") == "0.4" and "current_artifacts" in value:
                self.structural(head, value["current_artifacts"], ("current_artifacts",))
            elif type(value.get("channel_values")) is dict and type(value["channel_values"].get("control")) is dict:
                state = value["channel_values"]["control"]
                if state.get("schema_version") == "0.4":
                    self.structural(head, state["current_artifacts"], ("channel_values", "control", "current_artifacts"))
        for head, row in sources.items():
            value = row["value"]
            if row["kind"] == "execution_0_4" and value.get("record_type") == "budget" and value["event"] == "decision_recorded":
                payload = value["payload"]
                validate_budget_payload("decision_recorded", payload)
                check(payload["decision_digest"] == digest({k: v for k, v in payload.items() if k != "decision_digest"}), "decision_checksum")
                self.sizes[head, ("payload", "decision_digest")] = ("self", None)
        self.stop_sequences(sources)
        self.failure_and_grant_sources(sources, executions)

    def evidence(self, head, values, prefix, run):
        check(type(values) is list, "evidence")
        for i, reference in enumerate(values):
            keys(reference, {"artifact_id", "member", "sha256"}, "ordinary_evidence")
            member = self.members.get((*run, reference["artifact_id"], reference["member"]))
            check(member is not None and member["sha256"] == reference["sha256"], "foreign_evidence")
            self.reference(head, (*prefix, i, "sha256"), member["sha256"])

    def human_snapshot(self, declaration, registration):
        from .strict_json import loads as strict_parse
        check(registration["protected_kind"] == "human_response" and declaration["member"] == "payload.json" and
              len(registration["members"]) == 1, "human_member")
        member = registration["members"][0]
        run = registration["case_id"], registration["run_id"]
        response_id = registration["artifact_id"].removesuffix(":payload")
        raw = declaration["content"].encode()
        check(member["canonical_path"] == "human_responses/" + response_id + "/payload.json" and
              member["sha256"] == declaration["sha256"] == sha256(raw).hexdigest() and
              member["size_bytes"] == len(raw), "human_bytes")
        responses = [r for r in self.executions[run] if r.get("record_type") == "human_response" and
                     r["human_response_id"] == response_id]
        check(bool(responses) and all(r["payload_reference"] == member["canonical_path"] and
              r["payload_sha256"] == member["sha256"] for r in responses), "human_owner")
        submitted = next(r for r in responses if r["event"] == "submitted")
        payload = strict_parse(raw)
        check(payload == submitted["payload_snapshot"] and (*run, response_id) not in self.human_snapshots, "human_snapshot")
        head, _ = self.add({"schema_version": "0.1", "profile": "report", "sha256": declaration["sha256"],
                           "content": declaration["content"]}, dict(zip(("case_id", "run_id"), run)), report=True)
        self.human_snapshots[(*run, response_id)] = (head, payload, member["canonical_path"])
        self.reference(declaration["registration_head"], ("members", 0, "sha256"), head)
        self.sizes[declaration["registration_head"], ("members", 0, "size_bytes")] = ("size", head)
        for response in responses:
            self.reference(digest(response), ("payload_sha256",), head)

    def failure_and_grant_sources(self, sources, executions):
        failures, grants = {}, {}
        for run, records in executions.items():
            for record in records:
                if record.get("record_type") != "budget":
                    continue
                payload = record["payload"]
                validate_budget_payload(record["event"], payload)
                owner = dict(zip(("case_id", "run_id"), run))
                if record["event"] == "failure_observed":
                    fp = validate_fingerprint(payload["fingerprint"]).value
                    fp_head, _ = self.add({"schema_version": "0.1", "profile": "fingerprint", "sha256": digest(fp),
                                          "content": canonical_bytes(fp).decode()}, owner)
                    cause_head, _ = self.add({"schema_version": "0.1", "profile": "causal_context", "sha256": digest(fp["context"]),
                                             "content": canonical_bytes(fp["context"]).decode()}, owner)
                    self.reference(fp_head, ("causal_context_digest",), cause_head)
                    self.reference(fp_head, ("context",), cause_head)
                    for field in ("code_task_context_digest", "analysis_execution_context_digest"):
                        raw = fp["context"][field]
                        if raw is not None:
                            kind = "code_context" if field == "code_task_context_digest" else "analysis_context"
                            check(raw in sources and any(d == {"kind": kind, "source_sha256": raw}
                                  for d in self.proof["typed_sources"]), "fingerprint_context")
                            self.reference(cause_head, (field,), raw)
                    for field, member_name in (("plan_digest", "method_plan.json"), ("code_digest", "code_agent_result.json")):
                        raw = fp["context"][field]
                        if raw is None:
                            continue
                        candidates = []
                        for key, (_, registration) in self.registered.items():
                            if key[:2] != run or registration["event_index"] > record["artifact_event_index"]:
                                continue
                            for member in registration["members"]:
                                if member["logical_name"] != member_name:
                                    continue
                                value = (sources.get(member["sha256"]) or self.sources[member["sha256"]])["value"]
                                if raw == member["sha256"] or field == "code_digest" and raw == value["result_digest"]:
                                    candidates.append(member["sha256"])
                        check(len(candidates) == 1, "failure_member_source")
                        self.reference(cause_head, (field,), candidates[0])
                    self.sizes[fp_head, ("fingerprint_digest",)] = ("self", None)
                    self.reference(digest(record), ("payload", "fingerprint"), fp_head)
                    failures[(*run, fp["fingerprint_digest"])] = (fp_head, payload["occurrence"])
                elif record["event"] == "grant_issued":
                    fp_head, occurrence = failures[(*run, payload["fingerprint_digest"])]
                    snapshot_head, snapshot, reference = self.human_snapshots[(*run, payload["human_response_id"])]
                    check(snapshot_head == payload["response_digest"] and reference == payload["response_reference"] and
                          snapshot["decision"] == "approve_budget_window" and payload["occurrence"] == occurrence, "grant_source")
                    request = next(r for r in records[:record["event_index"]] if r.get("record_type") == "human_request" and
                                   r["event"] == "created" and r["human_request_id"] == payload["human_request_id"])
                    scope = request["authorization_scope"]
                    check("approve_budget_window" in scope["allowed_decisions"] and payload["target_node"] == payload["target_attempt_kind"] and
                          scope.get("work_target", payload["target_node"]) == payload["target_node"], "grant_scope")
                    grant_head, _ = self.add({"schema_version": "0.1", "profile": "grant", "sha256": digest(payload),
                                             "content": canonical_bytes(payload).decode()}, owner)
                    self.reference(grant_head, ("response_digest",), snapshot_head)
                    self.reference(grant_head, ("fingerprint_digest",), fp_head)
                    self.reference(digest(record), ("payload",), grant_head)
                    grants[(*run, payload["budget_grant_id"])] = (grant_head, payload, False)
                elif record["event"] == "grant_consumed":
                    key = (*run, payload["budget_grant_id"])
                    grant_head, issued, consumed = grants[key]
                    check(not consumed and payload["grant_digest"] == grant_head and all(payload[k] == issued[k] for k in
                          ("target_attempt_id", "transition_id")), "grant_single_use")
                    self.reference(digest(record), ("payload", "grant_digest"), grant_head)
                    grants[key] = (grant_head, issued, True)
        for head, row in sources.items():
            value = row["value"]
            run_identity = a05_trace.identity(value)
            run = (run_identity.get("case_id"), run_identity.get("run_id"))
            if value.get("record_type") == "budget" and value.get("event") == "decision_recorded" and value["payload"]["fingerprint_digest"] is not None:
                check((*run, value["payload"]["fingerprint_digest"]) in failures, "decision_failure_source")
                self.reference(head, ("payload", "fingerprint_digest"), failures[(*run, value["payload"]["fingerprint_digest"])][0])
            if value.get("record_type") == "human_request" and value.get("event") == "created" and "diagnostic_digest" in value["authorization_scope"]:
                candidates = self.request_diagnostic_sources(run, value["requesting_attempt_id"])
                check(len(candidates) == 1 and candidates[0][0] == value["authorization_scope"]["diagnostic_digest"], "human_diagnostic_source")
                self.reference(head, ("authorization_scope", "diagnostic_digest"), candidates[0][0])

    def request_diagnostic_sources(self, run, attempt_id):
        return [(head, identity) for head, (identity, _, name, _) in self.member_values.items() if
                name == "decision_coordinator_diagnostic.json" and identity.get("attempt_id") == attempt_id and
                (identity["case_id"], identity["run_id"]) == run]

    def agent_result(self, owner, node, result):
        diagnostics = [v for identity, role, name, v in self.member_bindings if
                       identity == owner and role == node and name == node + "_diagnostic.json"]
        check(len(diagnostics) == 1, "agent_registered_diagnostic")
        actual = result["diagnostic"]
        final = diagnostics[0]
        validate_product_diagnostic(final)
        expected = {**actual, "evidence": final["evidence"]} if actual.get("evidence") == [] else actual
        check(final == expected, "agent_diagnostic_binding")
        main_name = {"method_planner": "method_plan.json", "analysis_engineer": "run_result.json",
                     "scientific_reviewer": "scientific_review_report.json"}[node]
        main = next(v for identity, role, name, v in self.member_bindings if identity == owner and name == main_name)
        check(all(key in main and main[key] == value for key, value in result["content"].items()), "agent_content_binding")

    def context(self, head, value, auth, record):
        keys(value, {"identity", "direct_parent_attempt_id", "root_goal", "current_evidence", "remediation",
                     "relevant_history", "budget_summary"}, "ordinary_context")
        run = (record["case_id"], record["run_id"])
        records = self.executions[run]
        state = replay(records[:record["event_index"] - 2]).projection.value
        identity = {**auth["identity"], "cycle_id": state["cycle_id"]}
        check(value["identity"] == identity, "context_identity")
        scheduled = next(r for r in records if r["record_type"] == "attempt" and r["event"] == "scheduled" and
                         r["attempt_id"] == identity["attempt_id"])
        check(value["direct_parent_attempt_id"] == scheduled["parent_attempt_id"], "context_parent")
        root_goal = loads((source_path(self.roots[run] / "root_goal.json")).read_bytes())
        check(value["root_goal"] == root_goal and value["budget_summary"] ==
              {"policy_digest": state["budget"]["policy_digest"], "dimensions": state["budget"]["dimensions"]}, "context_material")
        self.evidence(head, value["current_evidence"], ("current_evidence",), run)
        pointers = {artifact: registration["pointer"] for (case, run_id, artifact), (_, registration) in self.registered.items()
                    if (case, run_id) == run and registration["event_index"] <= record["artifact_event_index"]}
        slots = PRODUCT_CONTEXT_SLOTS[identity["attempt_kind"]]
        history = sorted((row["value"] for row in self.base_sources.values() if row["kind"] == "canonical_json" and
                          row["value"].get("event") in ("registered", "current_set", "current_cleared") and
                          (row["value"].get("case_id"), row["value"].get("run_id")) == run and
                          row["value"]["event_index"] <= record["artifact_event_index"]), key=lambda row: row["event_index"])
        selected = {}
        for entry in history:
            if entry["event"] == "current_set":
                selected[entry["slot"]] = pointers[entry["artifact_id"]]
            elif entry["event"] == "current_cleared":
                selected.pop(entry["slot"], None)
        for slot, artifact_id in scheduled["input_references"]["current_artifact_ids"].items():
            check(artifact_id in pointers, "scheduled_input")
            selected.setdefault(slot, pointers[artifact_id])
        expected_evidence = [{"artifact_id": selected[slot]["artifact_id"], "member": member["canonical_path"], "sha256": member["sha256"]}
                             for slot in slots if slot in selected for member in selected[slot]["members"]]
        if value["remediation"] is not None:
            validate_remediation_packet(value["remediation"], identity=identity, parent_attempt_id=scheduled["parent_attempt_id"],
                                        registered=pointers, policy_digest=state["budget"]["policy_digest"])
            decision = pointers.get(scheduled["parent_attempt_id"] + ":decision")
            check(decision is not None, "packet_parent")
            member = next(m for m in decision["members"] if m["logical_name"] == "decision_log.json")
            check(self.member_values[member["sha256"]][3]["remediation"] == value["remediation"], "packet_source")
            self.evidence(head, value["remediation"]["evidence"], ("remediation", "evidence"), run)
            expected_evidence.extend(reference for reference in value["remediation"]["evidence"] if reference not in expected_evidence)
        check(value["current_evidence"] == expected_evidence, "selected_evidence")
        expected_history = [{k: pointers[entry["artifact_id"]][k] for k in ("artifact_id", "attempt_id", "slot", "status")}
                            for entry in history if entry["event"] == "registered" and entry["slot"] in slots and
                            (entry["attempt_id"] == scheduled["parent_attempt_id"] or value["remediation"] is not None and
                             entry["artifact_id"] in {reference["artifact_id"] for reference in value["remediation"]["evidence"]})][-4:]
        check(value["relevant_history"] == expected_history, "context_history")

    def member_references(self, head, value):
        identity, node, name, _ = self.member_values[head]
        run = identity["case_id"], identity["run_id"]
        if "evidence" in value and (name.endswith("_diagnostic.json") or name in ("decision_log.json", "memory_update.json")):
            self.evidence(head, value["evidence"], ("evidence",), run)
        if node == "decision_coordinator" and name == "decision_log.json" and value.get("remediation") is not None:
            packet = value["remediation"]
            keys(packet, {"target_node", "problem", "evidence", "constraints", "success_criteria", "parent_attempt_id",
                          "budget_policy_digest", "human_authorization"}, "ordinary_packet")
            check(packet["parent_attempt_id"] == identity["attempt_id"] and packet["target_node"] in PRODUCT_CONTEXT_SLOTS and
                  packet["budget_policy_digest"] == validate_policy(loads((source_path(self.roots[run] / "budget_policy.json")).read_bytes())).value["policy_digest"], "packet_owner")
            self.evidence(head, packet["evidence"], ("remediation", "evidence"), run)
            if packet["human_authorization"] is not None:
                self.human_authorization(head, packet["human_authorization"], identity,
                                         ("remediation", "human_authorization"), packet["target_node"])
        if value.get("human_authorization") is not None:
            self.human_authorization(head, value["human_authorization"], identity, ("human_authorization",))

    def human_authorization(self, head, authorization, identity, prefix, target=None):
        keys(authorization, {"human_request_id", "human_response_id", "response_digest", "target_node"}, "ordinary_human")
        run = identity["case_id"], identity["run_id"]
        responses = [r for r in self.executions[run] if r["record_type"] == "human_response" and r["event"] == "consumed" and
                     r["human_response_id"] == authorization["human_response_id"] and r["human_request_id"] == authorization["human_request_id"]]
        check(len(responses) == 1 and responses[0]["payload_sha256"] == authorization["response_digest"] and
              responses[0]["authorized_target_attempt_id"] == identity["attempt_id"], "human_snapshot")
        request = next(r for r in self.executions[run] if r["record_type"] == "human_request" and r["event"] == "created" and
                       r["human_request_id"] == authorization["human_request_id"])
        scope = request["authorization_scope"]
        expected_target = "memory_report" if responses[0]["decision"] == "reject_or_hold" or scope.get("work_target") is None else scope["work_target"]
        snapshot_head, _, reference = self.human_snapshots[(*run, authorization["human_response_id"])]
        check(authorization["target_node"] == expected_target and (target is None or target == expected_target) and
              snapshot_head == authorization["response_digest"] and reference == responses[0]["payload_reference"], "human_scope")
        self.reference(head, (*prefix, "response_digest"), snapshot_head)

    def structural(self, head, value, prefix=()):
        if type(value) is list:
            for i, child in enumerate(value):
                self.structural(head, child, prefix + (i,))
        elif type(value) is dict:
            if value.get("slot") in SLOT_BY_ATTEMPT_KIND.values() and "members" in value and "attempt_id" in value and (
                    "attempt_kind" in value or value.get("event") == "registered"):
                matches = [(key, row) for key, row in self.registered.items() if key[2] == value.get("artifact_id") and
                           (value == row[1]["pointer"] or not prefix and head == row[0])]
                check(len(matches) == 1, "registered_pointer")
                run, (_, registration) = matches[0][0][:2], matches[0][1]
                if registration["pointer"]["attempt_kind"] != "code_agent":
                    for i, member in enumerate(value["members"]):
                        self.reference(head, (*prefix, "members", i, "sha256"), member["sha256"])
                        self.sizes[head, (*prefix, "members", i, "size_bytes")] = ("size", member["sha256"])
                paths = value.get("state_paths", {})
                for field, physical in paths.items():
                    if physical is None:
                        continue
                    check(field in STATE_FIELDS_BY_SLOT[value["slot"]] or value["slot"] == "code", "state_path_field")
                    path = Path(physical)
                    check(path.resolve() == path and path.is_relative_to(self.roots[run]) and
                          any(path == self.roots[run] / m["canonical_path"] or
                              field.endswith("_dir") and path == (self.roots[run] / m["canonical_path"]).parent for m in value["members"]), "state_path_binding")
            children = {"pointer": value["pointer"]} if value.get("event") == "registered" else value
            for key, child in children.items():
                self.structural(head, child, prefix + (key,))

    def analysis_tool(self, head, value, config, auth):
        from lqcd_agent.code_agent.analysis_handoff import SPEC_FIELDS, MANIFEST_FIELDS
        check(auth.get("target_preparation") == value and value["preparation_kind"] == "analysis_fresh" and
              digest(config) == value["runtime_policy_digest"], "analysis_preparation")
        spec = loads(value["canonical_spec_bytes"])
        manifest = loads(value["canonical_workspace_manifest_bytes"])
        keys(spec, SPEC_FIELDS, "ordinary_analysis_spec")
        keys(manifest, MANIFEST_FIELDS, "ordinary_analysis_manifest")
        owner = auth["identity"]
        run = owner["case_id"], owner["run_id"]
        check(spec["schema_version"] == manifest["schema_version"] == "0.1" and
              spec["target_attempt_identity"] == manifest["target_attempt_identity"] == owner and
              spec["spec_digest"] == digest({k: v for k, v in spec.items() if k != "spec_digest"}) and
              manifest["manifest_digest"] == digest({k: v for k, v in manifest.items() if k != "manifest_digest"}) and
              digest(spec) == value["spec_digest"] and digest(manifest) == value["workspace_manifest_digest"] and
              spec["workspace_manifest_digest"] == manifest["manifest_digest"] and
              spec["fresh_workspace_identity"] == manifest["workspace_id"] == value["fresh_workspace_identity"] and
              spec["inbound_transition_identity"] == manifest["inbound_transition_identity"] == value["inbound_transition_identity"], "analysis_checksums")
        bundle = spec["source_code_bundle_id_digest"]
        registration_head, registration = self.registered[(*run, bundle["artifact_id"])]
        pointer = registration["pointer"]
        check(pointer["attempt_kind"] == "code_agent" and pointer["status"] == "success" and
              digest(pointer) == bundle["digest"] and manifest["source_code_bundle_id_digest"] == value["source_code_bundle_id_digest"] == bundle and
              spec["source_code_attempt_id"] == pointer["attempt_id"] and spec["source_member_digests"] ==
              {m["logical_name"]: m["sha256"] for m in pointer["members"]}, "analysis_code_source")
        task = self.base_sources[spec["source_member_digests"]["code_agent_task.json"]]["value"]
        check(spec["producing_task_digest"] == task["task_digest"] and spec["base_revision"] == task["base_revision"] and
              spec["base_tree_digest"] == manifest["base_tree_digest"] == task["base_tree_digest"], "analysis_task")
        check(spec["allowed_command"] == config["command"] and spec["environment_policy"] == config["environment"] and
              spec["expected_outputs"] == config["outputs"] and spec["analysis_runtime_fingerprint"] == digest(config["runtime"]), "analysis_config")
        managed_root = self.roots[run].parent.parent / "analysis_workspaces"
        check(managed_root.resolve() == managed_root and managed_root.is_dir() and
              manifest["managed_root_identity"] == digest(str(managed_root)), "analysis_root")
        spec_head, _ = self.add({"schema_version": "0.1", "profile": "analysis_spec", "sha256": digest(spec),
                                 "content": value["canonical_spec_bytes"]}, owner)
        manifest_head, _ = self.add({"schema_version": "0.1", "profile": "analysis_manifest", "sha256": digest(manifest),
                                     "content": value["canonical_workspace_manifest_bytes"]}, owner)
        for path in ("canonical_spec_bytes", "spec_digest"):
            self.reference(head, (path,), spec_head)
        for path in ("canonical_workspace_manifest_bytes", "workspace_manifest_digest"):
            self.reference(head, (path,), manifest_head)
        for source in (head, spec_head, manifest_head):
            self.reference(source, ("source_code_bundle_id_digest", "digest"), registration_head)
        for name, raw_head in spec["source_member_digests"].items():
            self.reference(spec_head, ("source_member_digests", name), raw_head)
        self.reference(spec_head, ("producing_task_digest",), spec["source_member_digests"]["code_agent_task.json"])
        self.reference(spec_head, ("change_manifest_digest",), spec["source_member_digests"]["change_manifest.json"])
        self.reference(head, ("verified_change_digest",), spec["source_member_digests"]["change_manifest.json"])
        self.reference(spec_head, ("patch_digest",), spec["source_member_digests"]["changes.patch"])
        self.reference(spec_head, ("workspace_manifest_digest",), manifest_head)
        for slot, selected in spec["selected_input_artifacts"].items():
            selected_head, selected_registration = self.registered[(*run, selected["artifact_id"])]
            check(selected_registration["slot"] == slot and selected["digest"] == digest(selected_registration["pointer"]), "analysis_selected_input")
            self.reference(spec_head, ("selected_input_artifacts", slot, "digest"), selected_head)
        self.sizes[spec_head, ("spec_digest",)] = ("self", None)
        self.sizes[manifest_head, ("manifest_digest",)] = ("self", None)
        self.sizes[manifest_head, ("managed_root_identity",)] = ("analysis_root", run)

    def verification_members(self, sources, executions):
        for (case_id, run_id, _), (_, registration) in self.registered.items():
            if registration["pointer"]["attempt_kind"] != "code_agent":
                continue
            by_name = {member["logical_name"]: member["sha256"] for member in registration["members"]}
            task = sources[by_name["code_agent_task.json"]]["value"]
            manifest = sources[by_name["workspace_manifest.json"]]["value"]
            verification = sources[by_name["verification_results.json"]]["value"]
            changes = sources[by_name["change_manifest.json"]]["value"]
            owner = {**{k: task[k] for k in ("case_id", "run_id", "attempt_id", "producer_operation_id")},
                     "workspace_id": manifest["workspace_id"]}
            records = executions[case_id, run_id]
            for reserved in records:
                payload = reserved.get("payload", {})
                if reserved.get("event") != "resource_reserved" or payload["resource_kind"] != "verification_command" or payload["attempt_id"] != task["attempt_id"]:
                    continue
                name = payload["resource_operation_id"].rsplit(":", 1)[1]
                spec = next(spec for spec in task["verification_specs"] if spec["spec_id"] == name)
                result = next(result for result in verification["spec_results"] if result["spec_id"] == name)
                result_head = digest(result)
                check(payload["input_digest"] == changes["final_tree_digest"] and
                      payload["config_digest"] == digest(spec) and
                      sources[payload["config_digest"]]["value"] == spec and sources[result_head]["value"] == result and
                      all(payload[k] == owner[k] for k in ("attempt_id", "producer_operation_id", "workspace_id")), "verification_member_binding")
                settlement = next(r for r in records if r.get("event") == "resource_settled" and
                                  r["payload"]["resource_operation_id"] == payload["resource_operation_id"])
                check(settlement["payload"]["evidence_digest"] == result_head, "verification_result_binding")
                if getattr(self, "product_sources", False):
                    self.bind_source_owner(result_head, owner)
                    self.bind_source_owner(digest(spec), owner)
                else:
                    self.owners[result_head] = owner
                self.reference(digest(reserved), ("payload", "config_digest"), digest(spec))

    def stop_sequences(self, sources):
        for head, row in sources.items():
            value = row["value"]
            if value.get("record_type") != "transition" or value.get("event") != "committed":
                continue
            sequence = value.get("fields", {}).get("stop_sequence_id")
            if sequence is None:
                continue
            diagnostic = [v for identity, node, name, v in self.member_bindings if
                          (identity["case_id"], identity["run_id"], identity["attempt_id"]) ==
                          (value["case_id"], value["run_id"], value["source_attempt_id"]) and name.endswith("_diagnostic.json")]
            if value["trigger_reason"] == "budget_stop":
                reason = "budget_stop"
            elif diagnostic:
                reason = diagnostic[0]["category"]
            else:
                # Continuation carries the originally committed terminal sequence.
                prior = [r for r in self.executions[value["case_id"], value["run_id"]][:value["event_index"] - 1]
                         if r.get("record_type") == "transition" and r.get("fields", {}).get("stop_sequence_id") == sequence]
                check(bool(prior), "stop_source")
                continue
            check(sequence == digest({"run_id": value["run_id"], "source_attempt_id": value["source_attempt_id"], "reason": reason}), "stop_sequence")

    def encode(self, head, path, project_source):
        if (head, path) in self.refs_at:
            return ["digest_reference", project_source(self.refs_at[head, path])]
        if (head, path) in self.sizes:
            kind, target = self.sizes[head, path]
            if kind == "analysis_root":
                return ["validated_analysis_root", list(target), "analysis_workspaces"]
            return ["validated_self_digest"] if kind == "self" else ["validated_member_size", project_source(target)]
        return None

    def finish_content(self, head, content, project_source):
        observation = self.observations.get(head)
        if observation is None:
            return content
        kind, value = observation
        return ["unsettled_observation", content, kind, project_source(value) if kind == "unsettled_return" else value]
