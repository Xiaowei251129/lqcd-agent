"""Explicit 0.9 Task evidence and authorization origins; no execution authority."""
from contextlib import closing
from hashlib import sha256
import sqlite3

from lqcd_agent.code_agent.artifacts import validate_code_result
from lqcd_agent.code_agent.ingress import validate_change_manifest
from lqcd_agent.code_agent.schemas import task_context, validate_task, validate_manifest
from lqcd_agent.code_agent.verification import build_verification_results
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from . import a05_trace
from .ordinary_trace import check
from .product_failure_trace import ProductProjection, PROOF_FIELDS
from .fault_source_trace import source_path
from .strict_json import Invalid, keys


FIELDS = PROOF_FIELDS | {"code_evidence_sources", "code_task_authorizations"}
EVIDENCE_FIELDS = {"schema_version", "consumer_task_head", "evidence_index", "consumer_transition_head",
    "source_registration_head", "source_task_head", "source_result_head", "source_manifest_head", "source_change_head",
    "source_verification_head", "source_final_evidence_head", "source_producer_operation_id"}
AUTH_FIELDS = {"schema_version", "consumer_task_head", "human_request_head", "response_submitted_head",
    "response_validated_head", "response_consumed_head", "snapshot_registration_head", "resume_operation_id",
    "parent_transition_head", "consumer_transition_head"}
CODE_MEMBERS = ("code_agent_task.json", "code_agent_result.json", "workspace_manifest.json",
                "change_manifest.json", "verification_results.json")


def project(events, proof, binding):
    try:
        keys(proof, FIELDS, "prior_code_proof")
        check(proof["schema_version"] == "0.6", "prior_code_proof_version")
        base = {k: v for k, v in proof.items() if k in {
            "schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources", "workspace_roots"}}
        base["schema_version"] = "0.2"
        return a05_trace._project(events, base, binding, ordinary=PriorCodeProjection(proof))
    except Invalid:
        raise
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, RecursionError, StopIteration) as error:
        raise Invalid("prior_code_trace", "provenance", "invalid_evidence") from error


class PriorCodeProjection(ProductProjection):
    def __init__(self, proof):
        super().__init__(proof)
        self.code_leaves = {}
        self.wire_context_heads = set()

    def value(self, head):
        return (self.sources.get(head) or self.base_sources[head])["value"]

    def database(self, run):
        return self.roots[run].parent.parent / ".lqcd/control_operations.sqlite"

    def operation(self, run, identity):
        with closing(sqlite3.connect(source_path(self.database(run)).as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM control_operations WHERE operation_id=?", (identity,)).fetchone()
        check(row is not None and row["status"] == "committed", "task_original_operation")
        return dict(row)

    def producer(self, run, task):
        with closing(sqlite3.connect(source_path(self.database(run)).as_uri() + "?mode=ro", uri=True)) as connection:
            row = connection.execute("SELECT revision,value FROM external_operations WHERE external_operation_id=?",
                                     (task["producer_operation_id"],)).fetchone()
        check(row is not None, "task_original_producer")
        value = loads(row[1])
        check(value["phase_revision"] == row[0] and value["producer_operation_id"] == task["producer_operation_id"] and
              value["task_digest"] == task["task_digest"] and value["attempt_id"] == task["attempt_id"] and
              value["cycle_id"] == task["cycle_id"] and value["run_locator"] == dict(zip(("case_id", "run_id"), run)) and
              value["parent_control_operation_id"] == task["external_producer_contract"]["parent_control_operation_id"] and
              value["prestart"]["task"] == task, "task_producer_owner")
        return value

    def parent(self, run, task, transition):
        identity = task["external_producer_contract"]["parent_control_operation_id"]
        operation = self.operation(run, identity)
        with closing(sqlite3.connect(source_path(self.database(run)).as_uri() + "?mode=ro", uri=True)) as connection:
            row = connection.execute("SELECT value,value_digest FROM control_snapshots WHERE operation_id=?", (identity,)).fetchone()
        check(row is not None, "task_parent_snapshot")
        snapshot = loads(row[0])
        check(digest(snapshot) == row[1] and operation["operation_type"] == "advance_run" and snapshot["records"][-1] == transition and
              transition["source_attempt_id"] == task["source_attempt_id"] and transition["target_attempt_id"] == task["attempt_id"] and
              transition["transition_id"] == task["transition_id"], "task_parent_transition")
        registration, = [r for _, r in self.registered.values() if (r["case_id"], r["run_id"]) == run and
                         r["attempt_id"] == task["source_attempt_id"] and r["slot"] == "decision"]
        member, = [m for m in registration["members"] if m["logical_name"] == "decision_log.json"]
        packet = self.value(member["sha256"])["remediation"]
        check(task["task_origin"] == "coordinator_code_fix" and packet["target_node"] == "code_agent" and
              packet["parent_attempt_id"] == task["source_attempt_id"] and
              packet["budget_policy_digest"] == task["budget_policy_digest"], "task_original_packet")
        return snapshot, packet

    def code_bundle(self, registration):
        members = {m["logical_name"]: m for m in registration["members"]}
        values = {}
        for name in CODE_MEMBERS:
            member = members[name]
            value = self.value(member["sha256"])
            raw = canonical_bytes(value)
            check(sha256(raw).hexdigest() == member["sha256"] and len(raw) == member["size_bytes"], "prior_code_member_bytes")
            values[name] = value
        task = validate_task(values[CODE_MEMBERS[0]]).value
        result = validate_code_result(values[CODE_MEMBERS[1]], task).value
        manifest = validate_manifest(values[CODE_MEMBERS[2]], task).value
        changes = validate_change_manifest(values[CODE_MEMBERS[3]], task, manifest).value
        verification = values[CODE_MEMBERS[4]]
        check(verification == build_verification_results(task, verification["spec_results"]) and
              all(registration[k] == task[k] for k in ("case_id", "run_id", "cycle_id", "attempt_id")) and
              registration["status"] == result["status"], "prior_code_bundle_owner")
        science = {"base_revision": task["base_revision"], "base_tree_digest": task["base_tree_digest"],
                   "final_tree_digest": changes["final_tree_digest"], "changes": changes["changes"], "patch_digest": result["patch_digest"]}
        return members, task, result, manifest, science

    def final_origin(self, run, registration, task, manifest):
        producer = self.producer(run, task)
        release = producer["consumption_release"]
        check(producer["operation_phase"] == "external_final_evidence_committed" and producer["proof_kind"] == "safe_stop" and
              producer["active_binding_status"] == "released" and release is not None and
              producer["workspace_manifest_digest"] == manifest["manifest_digest"] and producer["workspace_id"] == manifest["workspace_id"],
              "prior_code_safe_consumption")
        head = producer["terminal_evidence_digest"]
        raw = (source_path(self.roots[run] / producer["terminal_evidence_reference"])).read_bytes()
        check(sha256(raw).hexdigest() == head and loads(raw) == self.value(head), "prior_code_original_final")
        final = self.value(head)
        check(final["proof_kind"] == "safe_stop" and final["resolution_owner"] == producer["resolution_owner"] and
              all(final[k] == producer[k] for k in ("producer_operation_id", "run_locator", "attempt_id", "cycle_id", "lease_epoch")),
              "prior_code_final_owner")
        owner = self.operation(run, release["consumption_operation_id"])
        rows = self.executions[run]
        finished, = [r for r in rows if digest(r) == release["terminal_code_attempt_head"]]
        settled, = [r for r in rows if digest(r) == release["resource_settlement_digest"]]
        pause, = [r for r in rows if digest(r) == release["pause_consumed_head"]]
        check(finished["record_type"] == "attempt" and finished["event"] == "finished" and finished["attempt_id"] == task["attempt_id"] and
              finished["output_references"]["current_artifact_ids"]["code"] == registration["artifact_id"] and
              finished["artifact_head"] == release["canonical_code_artifact_head"] and
              settled["event"] == "resource_settled" and settled["payload"]["evidence_digest"] == head and
              settled["payload"]["resource_operation_id"] == producer["reservation_id"] and
              settled["payload"]["operation_id"] == owner["operation_id"] and
              pause["event"] == "pause_consumed" and pause["operation_id"] == owner["operation_id"] and
              settled["event_index"] < pause["event_index"] < finished["event_index"], "prior_code_consumption_records")
        with closing(sqlite3.connect(source_path(self.database(run)).as_uri() + "?mode=ro", uri=True)) as connection:
            phases = [loads(r[0]) for r in connection.execute("SELECT evidence FROM control_phases WHERE operation_id=?",
                                                            (owner["operation_id"],))]
        check(any(p.get("external_consumption_release_proof") == release for p in phases), "prior_code_release_journal")
        return head, finished

    def failure_and_grant_sources(self, sources, executions):
        for name in ("code_evidence_sources", "code_task_authorizations"):
            check(type(self.proof[name]) is list, "task_source_array")
        declarations = {}
        for declaration in self.proof["code_evidence_sources"]:
            keys(declaration, EVIDENCE_FIELDS, "code_evidence_source")
            key = declaration["consumer_task_head"], declaration["evidence_index"]
            check(declaration["schema_version"] == "0.1" and type(key[1]) is int and key[1] >= 0 and key not in declarations,
                  "code_evidence_duplicate")
            declarations[key] = declaration
        authorizations = {}
        for declaration in self.proof["code_task_authorizations"]:
            keys(declaration, AUTH_FIELDS, "code_task_authorization")
            key = declaration["consumer_task_head"]
            check(declaration["schema_version"] == "0.1" and key not in authorizations, "code_authorization_duplicate")
            authorizations[key] = declaration
        seen, authorized = set(), set()
        for typed in self.proof["typed_sources"]:
            if typed["kind"] != "task":
                continue
            task_head = typed["source_sha256"]
            task = validate_task(self.value(task_head)).value
            run = task["case_id"], task["run_id"]
            transition, = [r for r in executions[run] if r.get("record_type") == "transition" and r["transition_id"] == task["transition_id"]]
            producer = self.producer(run, task)
            manifest = validate_manifest(producer["prestart"]["manifest"], task).value
            owner = {k: task[k] for k in ("case_id", "run_id", "attempt_id", "producer_operation_id")}
            owner["workspace_id"] = manifest["workspace_id"]
            for kind, value in (("task", task), ("manifest", manifest), ("core", producer["prestart"]["core"])):
                head = digest(value)
                check(any(r == {"kind": kind, "source_sha256": head} for r in self.proof["typed_sources"]), "task_prestart_source")
                self.bind_source_owner(head, owner)
            if producer["terminal_evidence_digest"] is not None:
                final_head = producer["terminal_evidence_digest"]
                final = self.value(final_head)
                final_raw = (source_path(self.roots[run] / producer["terminal_evidence_reference"])).read_bytes()
                check(sha256(final_raw).hexdigest() == final_head and loads(final_raw) == final and
                      all(final[k] == producer[k] for k in ("producer_operation_id", "run_locator", "attempt_id", "cycle_id", "lease_epoch")),
                      "task_original_final_dependency")
                self.bind_source_owner(final_head, owner)
            if task["human_authorization_ref"] is not None:
                check(task_head in authorizations, "code_authorization_missing")
                self.authorization(run, task, task_head, transition, authorizations[task_head])
                authorized.add(task_head)
            for i, evidence in enumerate(task["evidence"]):
                _, prior = self.registered[(*run, evidence["artifact_id"])]
                if prior["slot"] != "code":
                    continue
                key = task_head, i
                check(key in declarations, "code_evidence_missing")
                snapshot, packet = self.parent(run, task, transition)
                prior_members, prior_task, _, prior_manifest, science = self.code_bundle(prior)
                check(prior["event_index"] <= transition["artifact_event_index"] and
                      snapshot["original_index"]["current"]["code"] == prior["pointer"] and
                      evidence == {"artifact_id": prior["artifact_id"], "path": prior_members[CODE_MEMBERS[1]]["canonical_path"],
                                   "sha256": prior_members[CODE_MEMBERS[1]]["sha256"]} and
                      {"artifact_id": evidence["artifact_id"], "member": evidence["path"], "sha256": evidence["sha256"]}
                      in packet["evidence"], "code_evidence_packet_owner")
                final_head, finished = self.final_origin(run, prior, prior_task, prior_manifest)
                check(finished["event_index"] < transition["event_index"], "code_evidence_future")
                expected = {"schema_version": "0.1", "consumer_task_head": task_head, "evidence_index": i,
                    "consumer_transition_head": digest(transition), "source_registration_head": digest(prior),
                    "source_producer_operation_id": prior_task["producer_operation_id"], "source_final_evidence_head": final_head,
                    **{field: prior_members[name]["sha256"] for field, name in zip(
                        ("source_task_head", "source_result_head", "source_manifest_head", "source_change_head", "source_verification_head"), CODE_MEMBERS)}}
                check(declarations[key] == expected, "code_evidence_declaration")
                inputs = [{"kind": "member", "head": prior_members[name]["sha256"], "registration_head": digest(prior),
                           "member": name, "path": []} for name in CODE_MEMBERS]
                inputs.append({"kind": "typed_source", "head": final_head, "registration_head": None, "member": None, "path": []})
                self.code_leaves[key] = science, inputs
                self.reference(task_head, ("evidence", i, "sha256"), expected["source_result_head"])
                wire_context = task_context(task)
                wire_head = digest(wire_context)
                check(self.value(wire_head) == wire_context and any(r == {"kind": "code_context", "source_sha256": wire_head}
                      for r in self.proof["typed_sources"]), "code_evidence_wire_context")
                position = wire_context["evidence_digests"].index(evidence["sha256"])
                self.reference(wire_head, ("evidence_digests", position), expected["source_result_head"])
                self.wire_context_heads.add(wire_head)
                seen.add(key)
        check(seen == set(declarations) and authorized == set(authorizations), "task_source_set_equal")
        super().failure_and_grant_sources(sources, executions)

    def task_evidence_science(self, task, evidence, registration, member):
        if registration["slot"] != "code":
            return super().task_evidence_science(task, evidence, registration, member)
        key = digest(task), task["evidence"].index(evidence)
        check(key in self.code_leaves and member["logical_name"] == "code_agent_result.json" and
              member["sha256"] == evidence["sha256"], "code_evidence_scientific_origin")
        return self.code_leaves[key]

    def encode(self, head, path, project_source):
        if head in self.wire_context_heads and path == ("evidence_digests",):
            rows = []
            for i, value in enumerate(self.value(head)["evidence_digests"]):
                target = self.refs_at.get((head, (*path, i)))
                rows.append(["digest_reference", project_source(target)] if target is not None else ["literal", value])
            return ["array", sorted(rows, key=canonical_bytes)]
        return super().encode(head, path, project_source)

    def authorization(self, run, task, task_head, transition, declaration):
        _, packet = self.parent(run, task, transition)
        ref = task["human_authorization_ref"]
        rows = self.executions[run]
        request, = [r for r in rows if r.get("record_type") == "human_request" and r["event"] == "created" and
                    r["human_request_id"] == packet["human_authorization"]["human_request_id"]]
        response = {r["event"]: r for r in rows if r.get("record_type") == "human_response" and
                    r["human_response_id"] == ref["single_use_id"]}
        submitted, validated, consumed = (response[k] for k in ("submitted", "validated", "consumed"))
        check(all(r["human_request_id"] == request["human_request_id"] and r["human_response_id"] == ref["artifact_id"] for r in response.values()) and
              consumed["authorized_target_attempt_id"] == task["source_attempt_id"] and validated["status"] == "validated" and
              consumed["decision"] == validated["decision"] == ref["action"] and ref["action"] in request["authorization_scope"]["allowed_decisions"] and
              request["authorization_scope"]["work_target"] == "code_agent" and
              submitted["event_index"] < validated["event_index"] < consumed["event_index"] < transition["event_index"], "code_authorization_stage")
        snapshot_head, snapshot, path = self.human_snapshots[(*run, ref["single_use_id"])]
        registration, = [r["value"] for r in self.base_sources.values() if r["value"].get("event") == "protected_snapshot_registered" and
                         r["value"].get("protected_kind") == "human_response" and
                         (r["value"]["case_id"], r["value"]["run_id"]) == run and
                         r["value"].get("human_response_id") == ref["single_use_id"]]
        check(ref["path"] == registration["members"][0]["canonical_path"] and path == consumed["payload_reference"] and
              ref["sha256"] == snapshot_head == consumed["payload_sha256"] and
              ref["scope_digest"] == digest(request["authorization_scope"]) and
              packet["human_authorization"] == {"human_request_id": request["human_request_id"], "human_response_id": ref["single_use_id"],
                  "response_digest": snapshot_head, "target_node": "code_agent"}, "code_authorization_snapshot")
        parent_transition, = [r for r in rows if r.get("record_type") == "transition" and
                              r["target_attempt_id"] == task["source_attempt_id"]]
        pause, = [r for r in rows if r.get("record_type") == "pause" and r["event"] == "pause_consumed" and
                  r["proof"].get("input_digest") == consumed["payload_sha256"]]
        validator, = [r for r in rows if r.get("record_type") == "attempt" and r["event"] == "started" and
                      r["attempt_id"] == consumed["consumer_attempt_id"]]
        resume = self.operation(run, pause["operation_id"])
        request_value = loads(resume["request"])
        actor = request_value["actor"]
        check(resume["operation_type"] == "resume_run" and resume["request_digest"] == pause["proof"]["request_digest"] and
              request_value["input_snapshot"] == snapshot and request_value["input_digest"] == snapshot_head and
              actor == pause["proof"]["actor"] and snapshot["decided_by"] == actor["actor_id"] and
              actor["actor_type"] == pause["authorization_scope"]["actor_type"] and
              set(pause["authorization_scope"]["scopes"]) <= set(actor["scopes"]) and
              validator["attempt_kind"] == "human_gate" and parent_transition["source_node"] == validator["node_name"] and
              parent_transition["source_attempt_id"] == consumed["consumer_attempt_id"],
              "code_authorization_actor")
        expected = {"schema_version": "0.1", "consumer_task_head": task_head, "human_request_head": digest(request),
            "response_submitted_head": digest(submitted), "response_validated_head": digest(validated), "response_consumed_head": digest(consumed),
            "snapshot_registration_head": digest(registration), "resume_operation_id": resume["operation_id"],
            "parent_transition_head": digest(parent_transition), "consumer_transition_head": digest(transition)}
        check(declaration == expected, "code_authorization_declaration")
        scope_head = self.internal_source(request["authorization_scope"], dict(zip(("case_id", "run_id"), run)))
        diagnostic, = self.request_diagnostic_sources(run, request["requesting_attempt_id"])
        check(diagnostic[0] == request["authorization_scope"]["diagnostic_digest"], "code_authorization_diagnostic")
        self.reference(scope_head, ("diagnostic_digest",), diagnostic[0])
        self.reference(task_head, ("human_authorization_ref", "scope_digest"), scope_head)
        self.reference(task_head, ("human_authorization_ref", "sha256"), snapshot_head)
