"""Explicit 0.7 provenance; neither maximum nor a locator grants authority."""
from hashlib import sha256
from base64 import b64decode
from contextlib import closing
from math import isfinite
import stat
import sqlite3

from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from .ordinary_trace import AUTHORIZATION, OrdinaryProjection, check
from .fault_source_trace import source_path
from .strict_json import Invalid, keys
from . import a05_trace


DECLARATION = {"schema_version", "reservation_head", "settlement_head", "capability_id", "reason_code", "evidence", "observation"}
OBSERVATION = {"schema_version", "resource_operation_id", "call_disposition", "clock_read_state", "clock_epoch_before",
               "clock_epoch_after", "start_at", "end_at", "hard_usage", "host_error"}


def project(events, proof, binding):
    try:
        keys(proof, {"schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources",
                     "workspace_roots", "ordinary_calls", "ordinary_members", "ordinary_maximum_settlements"}, "maximum_proof")
        check(proof["schema_version"] == "0.4", "maximum_proof_version")
        extension = MaximumProjection(proof)
        base = {k: v for k, v in proof.items() if k not in ("ordinary_calls", "ordinary_members", "ordinary_maximum_settlements")}
        base["schema_version"] = "0.2"
        return a05_trace._project(events, base, binding, ordinary=extension)
    except Invalid:
        raise
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, RecursionError, StopIteration) as error:
        raise Invalid("ordinary_trace", "maximum_provenance", "invalid_evidence") from error


class MaximumProjection(OrdinaryProjection):
    maximum_sources = True

    def request_diagnostic_sources(self, run, attempt_id):
        return [(member["sha256"], {"case_id": run[0], "run_id": run[1], "attempt_id": attempt_id})
                for _, registration in self.registered.values()
                if (registration["case_id"], registration["run_id"], registration["attempt_id"]) == (*run, attempt_id)
                for member in registration["members"] if member["logical_name"] == "decision_coordinator_diagnostic.json"]

    def stop_sequences(self, sources):
        for run, records in self.executions.items():
            previous, sequence = None, None
            for record in records:
                if record.get("record_type") != "transition" or not record.get("fields", {}).get("stop_sequence_id"):
                    continue
                current = record["fields"]["stop_sequence_id"]
                if sequence is None:
                    check(record["trigger_reason"] == "budget_stop" and current == digest({"run_id": run[1],
                        "source_attempt_id": record["source_attempt_id"], "reason": "budget_stop"}), "stop_sequence")
                    sequence = current
                else:
                    check(current == sequence, "stop_sequence")
                    if record["source"] == "HUMAN_RESPONSE":
                        check(previous["target_attempt_kind"] == "human_gate" and record["target_attempt_kind"] == "human_gate" and
                              record["human_request_id"] == previous["human_request_id"], "stop_source")
                    else:
                        check(record["source_attempt_id"] == previous["target_attempt_id"], "stop_source")
                check(record["target_attempt_kind"] in ("decision_coordinator", "human_gate", "memory_report", None), "stop_work")
                previous = record

    def __init__(self, proof):
        super().__init__(proof)
        self.maximums, self.used_maximums, self.locators = {}, set(), {}
        self.packets, self.packet_locators = {}, {}

    def validate(self, sources, executions, roots, events):
        self.events = events
        declarations = self.proof["ordinary_maximum_settlements"]
        check(type(declarations) is list, "maximum_array")
        for item in declarations:
            keys(item, DECLARATION, "maximum_declaration")
            check(item["schema_version"] == "0.1" and item["reservation_head"] not in self.maximums, "maximum_duplicate")
            self.maximums[item["reservation_head"]] = item
        super().validate(sources, executions, roots, events)
        check(self.used_maximums == set(self.maximums), "maximum_source_set")
        self.request_packets()
        for head, row in {**sources, **self.sources}.items():
            self.locator_fields(head, row["value"])

    def maximum_settlement(self, call, reservation, settlement, producer, owner):
        head = digest(reservation)
        check(head in self.maximums, "maximum_source_gap")
        item = self.maximums[head]
        check(item["settlement_head"] == digest(settlement) and item["capability_id"] == call["capability_id"] and
              all(settlement["payload"][k] == producer[k] for k in ("operation_id", "lease_epoch", "phase_revision")) and
              settlement["event_index"] > reservation["event_index"], "maximum_owner")
        for key, profile in (("evidence", "maximum_evidence"), ("observation", "maximum_observation")):
            check(item[key]["profile"] == profile, "maximum_profile")
        evidence_head, evidence = self.add(item["evidence"], owner)
        observation_head, observation = self.add(item["observation"], owner)
        check(canonical_bytes(evidence).decode() == item["evidence"]["content"] and
              canonical_bytes(observation).decode() == item["observation"]["content"] and
              evidence_head == settlement["payload"]["evidence_digest"], "maximum_evidence_digest")
        keys(observation, OBSERVATION, "maximum_observation")
        check(observation["schema_version"] == "0.1" and observation["resource_operation_id"] == reservation["payload"]["resource_operation_id"], "maximum_resource")
        for error in (call["exception"], observation["host_error"]):
            if error is not None:
                keys(error, {"type", "message"}, "maximum_error")
                check(type(error["type"]) is str and bool(error["type"]) and type(error["message"]) is str, "maximum_error_fields")
        for field in ("clock_epoch_before", "clock_epoch_after"):
            check(observation[field] is None or type(observation[field]) is str and bool(observation[field]), "maximum_epoch")
        start, end = observation["start_at"], observation["end_at"]
        for stamp in (start, end):
            if stamp is not None:
                keys(stamp, {"source", "wall_seconds", "monotonic_seconds"}, "maximum_timestamp")
                check(type(stamp["source"]) is str and bool(stamp["source"]) and all(type(stamp[k]) in (int, float) and
                      isfinite(stamp[k]) and stamp[k] >= 0 for k in ("wall_seconds", "monotonic_seconds")), "maximum_timestamp_values")
        state = observation["clock_read_state"]
        raised = call["exception"] is not None
        check(observation["call_disposition"] == ("raised" if raised else "returned") and start is not None, "maximum_disposition")
        result_head = None
        if raised:
            check(call["outcome"] is None and state == "callee_raised_before_end" and end is None and observation["host_error"] is None,
                  "maximum_exception")
        else:
            check(call["outcome"] is not None and state in ("complete", "read_failed"), "maximum_return")
            result_head, result = self.add(call["outcome"], owner)
            check(call["outcome"]["profile"] == "outcome", "maximum_return_profile")
            if call["profile"] == "scoped_llm":
                keys(result, {"diagnostic", "content"}, "maximum_llm_result")
                check(result["diagnostic"]["fingerprint"] is None and type(result["content"]) is dict, "maximum_agent_outcome")
        if state == "complete":
            check(end is not None and observation["host_error"] is None, "maximum_complete")
        elif state == "read_failed":
            check(observation["host_error"] is not None, "maximum_read_failed")
        before, after = observation["clock_epoch_before"], observation["clock_epoch_after"]
        bad_clock = state == "read_failed" or before is None or after is None or before != after or (end is not None and
                    (start["source"] != end["source"] or end["wall_seconds"] < start["wall_seconds"] or end["monotonic_seconds"] < start["monotonic_seconds"]))
        duration = None if bad_clock or end is None else end["monotonic_seconds"] - start["monotonic_seconds"]
        reason = "clock_untrusted" if bad_clock else "duration_overrun" if duration is not None and duration > reservation["payload"]["timeout_seconds"] else "callee_exception" if raised else None
        check(reason is not None and item["reason_code"] == reason, "maximum_reason")
        if raised and evidence != call["exception"]:
            keys(evidence, {"schema_version", "resource_operation_id", "exception"}, "maximum_receipt")
            check(evidence == {"schema_version": "0.1", "resource_operation_id": reservation["payload"]["resource_operation_id"],
                  "exception": call["exception"]}, "maximum_receipt_source")
        else:
            check(evidence == (call["exception"] if raised else observation["host_error"] if state == "read_failed" else
                  {"type": "ControlIntegrityError", "message": "Resource duration is untrusted or exceeds its admitted maximum"}), "maximum_actual_error")
        usage = observation["hard_usage"]
        keys(usage, {"state", "value"}, "maximum_usage")
        if duration is None:
            check(usage == {"state": "unknown", "value": None}, "maximum_usage_unknown")
        else:
            keys(usage["value"], {"llm_calls", "tool_calls", "verification_commands", "active_seconds"}, "maximum_usage_vector")
            check(all(type(usage["value"][k]) is int for k in ("llm_calls", "tool_calls", "verification_commands")) and
                  type(usage["value"]["active_seconds"]) in (int, float), "maximum_usage_types")
            check(usage == {"state": "known", "value": {"llm_calls": int(reservation["payload"]["resource_kind"] == "llm_call"),
                  "tool_calls": int(reservation["payload"]["resource_kind"] == "tool_call"), "verification_commands": 0,
                  "active_seconds": duration}}, "maximum_usage_known")
        self.reference(digest(settlement), ("payload", "evidence_digest"), evidence_head)
        self.observations[head] = ("maximum", (observation_head, result_head, reason))
        self.used_maximums.add(head)

    def request_packets(self):
        from lqcd_agent.control.execution import replay
        from lqcd_agent.control.records import FIELDS
        from lqcd_agent.control.projections import bounded_projection
        for run, records in self.executions.items():
            requests = [r for r in records if r["record_type"] == "human_request"]
            for request_id in {r["human_request_id"] for r in requests}:
                sequence = [r for r in requests if r["human_request_id"] == request_id]
                created = [r for r in sequence if r["event"] == "created"]
                written = [r for r in sequence if r["event"] == "packet_written"]
                check(len(created) == 1 and len(written) <= 1 and created[0]["packet_reference"] is None, "packet_request_sequence")
                if not written:
                    check(all(r["packet_reference"] is None for r in sequence), "packet_unpublished")
                    continue
                created, written = created[0], written[0]
                check(created["event_index"] < written["event_index"] and all(created[k] == written[k] for k in
                      FIELDS["human_request"] if k != "packet_reference"), "packet_request_fields")
                registrations = [(head, r) for head, r in self.registered.values() if
                                 (r["case_id"], r["run_id"]) == run and r["pointer"]["attempt_kind"] == "human_gate" and
                                 any(m["sha256"] == digest(created) for m in r["members"])]
                check(len(registrations) == 1, "packet_registration")
                registration_head, registration = registrations[0]
                publisher = registration["attempt_id"]
                canonical = "attempts/" + publisher + "/approval_packet/request.json"
                check(registration["artifact_id"] == publisher + ":approval" and registration["slot"] == "approval" and
                      len(registration["members"]) == 1, "packet_artifact")
                member = registration["members"][0]
                check(member["logical_name"] == "approval_packet/request.json" and member["canonical_path"] == canonical and
                      member["projection_path"] == "approval_packet/request.json", "packet_member")
                identity, node, name, value = self.member_values[member["sha256"]]
                check(value == created and identity == dict(zip(("case_id", "run_id", "attempt_id"), (*run, publisher))) and
                      node == "human_gate" and name == member["logical_name"], "packet_created_bytes")
                declaration = next(d for d in self.proof["ordinary_members"] if d["registration_head"] == registration_head and
                                   d["member"] == name)
                raw = declaration["content"].encode()
                path = self.roots[run] / canonical
                check(written["packet_reference"] == str(path), "packet_locator")
                for part in (path, *path.parents):
                    check(not stat.S_ISLNK(source_path(part).lstat().st_mode), "packet_symlink")
                check(stat.S_ISREG(source_path(path).lstat().st_mode) and source_path(path).read_bytes() == raw == canonical_bytes(created), "packet_file")
                attempts = [r for r in records if r["record_type"] == "attempt" and r["attempt_id"] == publisher]
                check([r["event"] for r in attempts] == ["scheduled", "started", "finished"] and all(
                      r["attempt_kind"] == "human_gate" and r["node_name"] == "human_gate" and
                      r["parent_attempt_id"] == created["requesting_attempt_id"] and r["cycle_id"] == created["cycle_id"] for r in attempts),
                      "packet_publisher")
                scheduled, started, finished = attempts
                check(created["event_index"] < scheduled["event_index"] < started["event_index"] < written["event_index"] < finished["event_index"] and
                      registration["execution_head"] == digest(started) and
                      written["artifact_head"] == finished["artifact_head"] and written["artifact_event_index"] == finished["artifact_event_index"] and
                      finished["output_references"]["current_artifact_ids"]["approval"] == registration["artifact_id"], "packet_publication_order")
                database = self.roots[run].parent.parent / ".lqcd/control_operations.sqlite"
                check(source_path(database).is_file() and not source_path(database).is_symlink(), "packet_database")
                with closing(sqlite3.connect(source_path(database).as_uri() + "?mode=ro", uri=True)) as connection:
                    connection.row_factory = sqlite3.Row
                    capabilities = [loads(r[0]) for r in connection.execute("SELECT value FROM invocation_capabilities")]
                    capabilities = [c for c in capabilities if c["authorization"]["identity"] == {**identity, "attempt_kind": node}]
                    check(len(capabilities) == 1, "packet_capability")
                    capability = capabilities[0]
                    auth = capability["authorization"]
                    check(set(auth) == AUTHORIZATION and type(auth["producing_epoch"]) is int and type(auth["activation_result_revision"]) is int and
                          capability["authorization_digest"] == digest(auth) and auth["scope"] == "attempt_execution" and
                          auth["terminal_closure_revision"] == 0, "packet_authorization")
                    producer = connection.execute("SELECT * FROM control_operations WHERE operation_id=?", (auth["producer_operation_id"],)).fetchone()
                    check(producer is not None and producer["status"] == "committed" and producer["operation_type"] == "advance_run" and
                          producer["lease_epoch"] == auth["producing_epoch"] and producer["phase_revision"] == auth["activation_result_revision"], "packet_producer")
                    result = loads(producer["result"])
                    matching = [e for e in self.events if e["operation_id"] == producer["operation_id"] and
                                e["phase_revision"] == producer["phase_revision"] and e["lease_epoch"] == producer["lease_epoch"]]
                    check(len(matching) == 1 and matching[0]["result_digest"] == digest(result) and
                          matching[0]["owner"] == producer["worker_owner_id"] and matching[0]["status"] == producer["status"] and
                          matching[0]["phase"] == producer["phase"] and matching[0]["event"] ==
                          "control." + producer["operation_type"] + "." + producer["operation_variant"] + "." + producer["phase"] and
                          result["capability_id"] == "capability_" + producer["operation_id"] and result["run_locator"] == dict(zip(("case_id", "run_id"), run)) and
                          all(result[k] == auth["heads"][k] for k in ("execution_head", "artifact_head", "checkpoint_head")), "packet_producer_phase")
                    projection = auth["projection"]
                    prefix = records[:projection["execution_event_index"]]
                    check(auth["heads"] == {k: projection[k] for k in ("execution_head", "artifact_head", "checkpoint_head")} and
                          digest(prefix[-1]) == auth["heads"]["execution_head"] and
                          auth["manifest"] == self.base_sources[auth["heads"]["checkpoint_head"]]["value"], "packet_authorization_head")
                    index = {"case_id": run[0], "run_id": run[1], "current": projection["current_artifacts"]}
                    expected = bounded_projection(replay(prefix), artifact_index=index, artifact_head=projection["artifact_head"],
                                                  artifact_event_index=projection["artifact_event_index"]).value
                    check(projection == {**expected, "checkpoint_head": auth["manifest"]["checkpoint_head"]} and
                          projection["active_human_request_id"] == request_id and projection["parent_attempt_id"] == created["requesting_attempt_id"],
                          "packet_authorization_projection")
                    intent, start_intent = capability["completion_intent"], capability["started_intent"]
                    # The original canonical publisher acquires its fresh
                    # capability at epoch zero, then invokes epoch one.
                    check(capability["state"] == "finished" and type(capability["invocation_epoch"]) is int and capability["invocation_epoch"] == 1 and
                          capability["worker_id"] == producer["worker_owner_id"] and intent["published"] is True and
                          start_intent["published"] is True and start_intent["record"] == started, "packet_invocation_fence")
                    check(start_intent["previous"].encode() == b"".join(canonical_bytes(r) + b"\n" for r in records[:started["event_index"] - 1]) and
                          start_intent["content"].encode() == b"".join(canonical_bytes(r) + b"\n" for r in records[:started["event_index"]]),
                          "packet_started_ledger")
                    history = b"".join(canonical_bytes(r) + b"\n" for r in records[:finished["event_index"]])
                    check(intent["content"].encode() == history and (source_path(self.roots[run] / "execution_history.jsonl")).read_bytes().startswith(history),
                          "packet_completion_ledger")
                    plan = intent["artifact_publication"]
                    artifacts = [loads(line) for line in plan["content"].splitlines()]
                    check(registration in artifacts and digest(artifacts[-1]) == written["artifact_head"] and
                          artifacts[-1]["event_index"] == written["artifact_event_index"] and
                          plan["content"].startswith(plan["previous"]) and sha256(plan["previous"].encode()).hexdigest() == auth["artifact_history_digest"] and
                          (source_path(self.roots[run] / "artifact_history.jsonl")).read_bytes().startswith(plan["content"].encode()),
                          "packet_completion_artifacts")
                    check(len(plan["projections"]) == 1 and plan["projections"][0] == {"canonical_path": canonical,
                          "projection_path": name, "sha256": member["sha256"], "content_base64": plan["projections"][0]["content_base64"]} and
                          b64decode(plan["projections"][0]["content_base64"], validate=True) == raw, "packet_completion_bytes")
                    completion_index = loads(intent["index"])
                    check(completion_index["current"]["approval"] == registration["pointer"] and
                          completion_index["artifact_head"] == written["artifact_head"] and
                          intent["projection"]["execution_head"] == digest(finished) and
                          intent["projection"]["active_human_request_id"] == request_id and
                          intent["projection"]["approval_packet_dir"] == str(path.parent), "packet_completion_projection")
                    manifest = intent["manifest"]
                    check(manifest == self.base_sources[manifest["checkpoint_head"]]["value"] and digest(intent["checkpoint"]) == manifest["checkpoint_digest"] and
                          manifest["execution_head"] == digest(finished) and manifest["artifact_head"] == written["artifact_head"] and
                          intent["checkpoint_deferred_until_release"] is False, "packet_completion_checkpoint")
                self.packets[(*run, request_id)] = (publisher, canonical, member["sha256"], written)

    def human_snapshot(self, declaration, registration):
        from .strict_json import loads as strict_parse
        check(registration["protected_kind"] == "human_response" and declaration["member"] == "payload.json" and len(registration["members"]) == 1,
              "human_member")
        member = registration["members"][0]
        run = registration["case_id"], registration["run_id"]
        response_id = registration["artifact_id"].removesuffix(":payload")
        canonical = "human_responses/" + response_id + "/payload.json"
        raw = declaration["content"].encode()
        check(member["canonical_path"] == canonical and member["sha256"] == declaration["sha256"] == sha256(raw).hexdigest() and
              member["size_bytes"] == len(raw), "human_bytes")
        path = self.roots[run] / canonical
        for part in (path, *path.parents):
            check(not stat.S_ISLNK(source_path(part).lstat().st_mode), "human_symlink")
        check(stat.S_ISREG(source_path(path).lstat().st_mode) and source_path(path).read_bytes() == raw, "human_file")
        responses = [r for r in self.executions[run] if r.get("record_type") == "human_response" and r["human_response_id"] == response_id]
        check(bool(responses) and len({r["payload_reference"] for r in responses}) == 1 and all(
              r["payload_reference"] in (canonical, str(path)) and r["payload_sha256"] == member["sha256"] and
              r["human_request_id"] == registration["human_request_id"] for r in responses), "human_owner")
        submitted = [r for r in responses if r["event"] == "submitted"]
        check(len(submitted) == 1 and (*run, response_id) not in self.human_snapshots, "human_snapshot")
        payload = strict_parse(raw)
        check(payload == submitted[0]["payload_snapshot"] and all(
              r["event"] == "submitted" or
              (r["event"] == "invalid" and r["decision"] is None and type(r["error"]) is str and bool(r["error"]) and
               any(a.get("record_type") == "attempt" and a["event"] == "finished" and a["attempt_kind"] == "human_gate" and
                   a["attempt_id"] == r["validator_attempt_id"] and a["event_index"] > r["event_index"] for a in self.executions[run])) or
              (r["event"] in ("validated", "consumed") and r["decision"] == payload["decision"])
              for r in responses), "human_snapshot_action")
        self.human_publication(path, raw, registration, submitted[0], payload)
        head, _ = self.add({"schema_version": "0.1", "profile": "report", "sha256": declaration["sha256"], "content": declaration["content"]},
                           dict(zip(("case_id", "run_id"), run)), report=True)
        self.human_snapshots[(*run, response_id)] = (head, payload, responses[0]["payload_reference"])
        self.reference(declaration["registration_head"], ("members", 0, "sha256"), head)
        self.sizes[declaration["registration_head"], ("members", 0, "size_bytes")] = ("size", head)
        for response in responses:
            self.reference(digest(response), ("payload_sha256",), head)

    def human_publication(self, path, raw, registration, submitted, payload):
        database = self.roots[registration["case_id"], registration["run_id"]].parent.parent / ".lqcd/control_operations.sqlite"
        check(source_path(database).is_file() and not source_path(database).is_symlink(), "human_database")
        with closing(sqlite3.connect(source_path(database).as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            publications = connection.execute("SELECT * FROM control_publications WHERE path=?", (str(path),)).fetchall()
            check(len(publications) == 1, "human_publication")
            publication = publications[0]
            content = publication["content"]
            check((content.encode() if type(content) is str else content) == raw and
                  publication["content_digest"] == sha256(raw).hexdigest() and
                  publication["phase"] == "prestart_records_committed", "human_publication_bytes")
            operation = connection.execute("SELECT * FROM control_operations WHERE operation_id=?", (publication["operation_id"],)).fetchone()
            phase = connection.execute("SELECT * FROM control_phases WHERE operation_id=? AND revision=?", (publication["operation_id"], publication["producing_revision"])).fetchone()
            request = loads(operation["request"])
            check(operation["operation_type"] == "resume_run" and request["input_kind"] == "human_response" and
                  request["run_locator"] == {k: registration[k] for k in ("case_id", "run_id")} and
                  request["input_snapshot"] == payload and request["input_digest"] == sha256(raw).hexdigest() and
                  phase["phase"] == publication["phase"] and phase["lease_epoch"] == publication["producing_epoch"], "human_publisher")
            matching = [e for e in self.events if e["operation_id"] == publication["operation_id"] and
                        e["phase_revision"] == publication["producing_revision"] and e["lease_epoch"] == publication["producing_epoch"]]
            check(len(matching) == 1 and matching[0]["phase"] == phase["phase"] and
                  matching[0]["event"] == "control.resume_run." + operation["operation_variant"] + "." + phase["phase"] and
                  matching[0]["owner"] == operation["worker_owner_id"], "human_publisher_phase")
            histories = connection.execute("SELECT path,content FROM control_publications WHERE operation_id=? AND phase=?",
                                           (publication["operation_id"], publication["phase"])).fetchall()
            for name, record in (("artifact_history.jsonl", registration), ("execution_history.jsonl", submitted)):
                history = [r for r in histories if r["path"] == str(path.parents[2] / name)]
                check(len(history) == 1 and record in [loads(line) for line in history[0]["content"].splitlines()], "human_publication_history")

    def failure_and_grant_sources(self, sources, executions):
        for run, records in executions.items():
            for issued in (r for r in records if r.get("event") == "grant_issued"):
                payload = issued["payload"]
                validated = [r for r in records[:issued["event_index"] - 1] if r.get("record_type") == "human_response" and
                             r["event"] == "validated" and r["human_request_id"] == payload["human_request_id"] and
                             r["human_response_id"] == payload["human_response_id"]]
                check(len(validated) == 1 and validated[0]["decision"] == "approve_budget_window" and
                      validated[0]["payload_reference"] == payload["response_reference"] and
                      validated[0]["payload_sha256"] == payload["response_digest"], "grant_validated_source")
        return super().failure_and_grant_sources(sources, executions)

    def human_authorization(self, head, authorization, identity, prefix, target=None):
        run = identity["case_id"], identity["run_id"]
        snapshot, payload, reference = self.human_snapshots[(*run, authorization["human_response_id"])]
        responses = [r for r in self.executions[run] if r.get("record_type") == "human_response" and
                     r["human_response_id"] == authorization["human_response_id"] and r["event"] in ("validated", "consumed")]
        check({r["event"] for r in responses} == {"validated", "consumed"} and all(
              r["decision"] == payload["decision"] and r["payload_reference"] == reference and r["payload_sha256"] == snapshot and
              r["human_request_id"] == authorization["human_request_id"] for r in responses), "human_authorization_action")
        request = next(r for r in self.executions[run] if r.get("record_type") == "human_request" and r["event"] == "created" and
                       r["human_request_id"] == authorization["human_request_id"])
        check(payload["decision"] in request["authorization_scope"]["allowed_decisions"], "human_authorization_scope")
        return super().human_authorization(head, authorization, identity, prefix, target)

    def locator_fields(self, head, value, path=()):
        from lqcd_agent.control.records import FIELDS

        if type(value) is dict:
            if value.get("record_type") == "human_request":
                run = value.get("case_id"), value.get("run_id")
                key = (*run, value.get("human_request_id"))
                if key in self.packets and value.get("packet_reference") is not None:
                    publisher, canonical, member, written = self.packets[key]
                    # A field name or an equal nested object is not provenance.
                    # The actual source closure carries this record as a typed
                    # ledger source; unknown containers remain material.
                    lifecycle = value == written
                    if value.get("event") == "satisfied" and value in self.executions[run]:
                        check(all(value[k] == written[k] for k in FIELDS["human_request"] if k != "status") and
                              value["status"] == "satisfied", "packet_satisfied_binding")
                        consumed = [r for r in self.executions[run] if r.get("record_type") == "human_response" and
                                    r.get("event") == "consumed" and r["human_request_id"] == key[-1] and
                                    digest(r) == value["previous_execution_head"]]
                        check(len(consumed) == 1, "packet_consumer_binding")
                        lifecycle = True
                    if lifecycle and path == () and self.base_sources.get(head, {}).get("kind") == "execution_0_4":
                        self.packet_locators[head, path + ("packet_reference",)] = (run, key[-1], publisher, canonical, member)
                        self.reference(head, path + ("packet_reference",), member)
            if value.get("record_type") == "human_response":
                run = value.get("case_id"), value.get("run_id")
                key = (*run, value.get("human_response_id"))
                if key in self.human_snapshots:
                    snapshot, _, reference = self.human_snapshots[key]
                    check(value in self.executions[run] and value["payload_reference"] == reference, "human_repeated_source")
                    self.locators[head, path + ("payload_reference",)] = (run, key[-1], snapshot)
                    self.reference(head, path + ("payload_sha256",), snapshot)
            elif "response_reference" in value and "budget_grant_id" in value:
                matches = [(run, r) for run, records in self.executions.items() for r in records if
                           r.get("event") == "grant_issued" and r["payload"] == value]
                check(len(matches) == 1, "human_grant_locator")
                run, record = matches[0]
                snapshot, _, reference = self.human_snapshots[(*run, value["human_response_id"])]
                check(value["response_reference"] == reference, "human_grant_reference")
                self.locators[head, path + ("response_reference",)] = (run, value["human_response_id"], snapshot)
            for key, child in value.items():
                self.locator_fields(head, child, path + (key,))
        elif type(value) is list:
            for i, child in enumerate(value):
                self.locator_fields(head, child, path + (i,))

    def encode(self, head, path, project_source):
        if (head, path) in self.packet_locators:
            run, request, publisher, canonical, member = self.packet_locators[head, path]
            return ["human_request_packet_locator", list(run), request, publisher, canonical, project_source(member)]
        if (head, path) in self.locators:
            run, response, snapshot = self.locators[head, path]
            return ["human_snapshot_locator", list(run), response, "human_responses/" + response + "/payload.json", project_source(snapshot)]
        return super().encode(head, path, project_source)

    def finish_content(self, head, content, project_source):
        observation = self.observations.get(head)
        if observation is not None and observation[0] == "maximum":
            stamp, outcome, reason = observation[1]
            return ["maximum_observation", content, reason, project_source(stamp),
                    None if outcome is None else project_source(outcome)]
        return super().finish_content(head, content, project_source)
