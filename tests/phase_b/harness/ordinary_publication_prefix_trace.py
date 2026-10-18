"""Explicit settled publication prefixes; source evidence conveys no authority."""
from base64 import b64decode
from contextlib import closing
from hashlib import sha256
import sqlite3

from lqcd_agent.agents.decision_coordinator import validate_product_diagnostic
from lqcd_agent.control.capabilities import invocation_prefix
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from . import a05_trace
from .ordinary_trace import MEMBERS, check
from .prior_code_evidence_trace import FIELDS, PriorCodeProjection
from .fault_source_trace import source_path
from .strict_json import Invalid, keys


PROOF_FIELDS = FIELDS | {"ordinary_publication_prefixes"}
PREFIX_FIELDS = {"schema_version", "reservation_head", "settlement_head", "capability_id", "producer_operation_id",
                 "issuer", "journal_revision", "journal", "publication", "stage", "snapshot_sha256"}
PUBLICATION_FIELDS = {"execution_head", "artifact_history", "artifact_index", "index_source", "projected_members", "checkpoint_committed", "checkpoint_published"}
ISSUER_FIELDS = {"worker_id", "invocation_epoch", "producer_epoch", "producer_revision"}
BASE_FIELDS = {"schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources", "workspace_roots"}


def envelope(value, profile):
    keys(value, {"schema_version", "profile", "sha256", "content"}, "prefix_envelope")
    check(value["schema_version"] == "0.1" and value["profile"] == profile and type(value["content"]) is str,
          "prefix_profile")
    raw = value["content"].encode()
    parsed = loads(raw)
    check(raw == canonical_bytes(parsed) and sha256(raw).hexdigest() == value["sha256"], "prefix_bytes")
    return parsed


def frozen(value):
    return None if value is None else {key: item for key, item in value.items() if key != "published"}


def publication_stage(journal, publication):
    completion = journal.get("completion_intent")
    if completion is None:
        return "settled_return"
    execution = parse_ledger(completion["content"].encode())
    if execution.projection.value["attempt_status"] == "failed" and completion["artifact_publication"] is None:
        return "host_rejected"
    if publication["checkpoint_published"]:
        return "checkpoint_published"
    if publication["checkpoint_committed"]:
        return "checkpoint_committed"
    if publication["artifact_index"] == completion["index"]:
        return "index_published"
    if publication["execution_head"] == execution.projection.value["execution_head"]:
        return "finished_published"
    plan = completion["artifact_publication"]
    if plan is not None and publication["artifact_history"] == plan["content"]:
        return "history_published"
    if publication["projected_members"]:
        return "projection_published"
    return "completion_frozen"


def project(events, proof, binding):
    try:
        keys(proof, PROOF_FIELDS, "publication_prefix_proof")
        check(proof["schema_version"] == "0.7", "publication_prefix_version")
        base = {key: value for key, value in proof.items() if key in BASE_FIELDS}
        base["schema_version"] = "0.2"
        return a05_trace._project(events, base, binding, ordinary=PublicationPrefixProjection(proof))
    except Invalid:
        raise
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, RecursionError, StopIteration) as error:
        raise Invalid("ordinary_publication_prefix", "provenance", "invalid_evidence") from error


class PublicationPrefixProjection(PriorCodeProjection):
    def __init__(self, proof):
        super().__init__(proof)
        self.prefixes, self.used_prefixes, self.prefix_members, self.prefix_settlements = {}, set(), {}, {}

    def validate(self, sources, executions, roots, events):
        self.base_sources, self.executions, self.roots = sources, executions, roots
        declarations = self.proof["ordinary_publication_prefixes"]
        check(type(declarations) is list, "publication_prefix_array")
        calls = {row["reservation_head"]: row for row in self.proof["ordinary_calls"]}
        for declaration in declarations:
            keys(declaration, PREFIX_FIELDS, "publication_prefix")
            head = declaration["reservation_head"]
            check(declaration["schema_version"] == "0.1" and head not in self.prefixes and head in calls,
                  "publication_prefix_duplicate_or_orphan")
            call = calls[head]
            check(call["profile"] == "scoped_llm" and call["outcome"] is not None and call["exception"] is None,
                  "publication_prefix_return")
            reservation = sources[head]["value"]
            settlement = sources[declaration["settlement_head"]]["value"]
            run = reservation["case_id"], reservation["run_id"]
            identity = call["authorization"]["identity"]
            check(settlement["event"] == "resource_settled" and settlement["payload"]["actual"] is not None and
                  settlement["payload"]["resource_operation_id"] == reservation["payload"]["resource_operation_id"] and
                  (settlement["case_id"], settlement["run_id"]) == run and settlement in executions[run] and
                  settlement["payload"]["evidence_digest"] == call["outcome"]["sha256"], "publication_prefix_settlement")
            check(sum(row.get("event") == "resource_settled" and row["payload"]["resource_operation_id"] ==
                      reservation["payload"]["resource_operation_id"] for row in executions[run]) == 1,
                  "publication_prefix_unique_settlement")
            journal = envelope(declaration["journal"], "invocation_publication_journal")
            snapshot_path = roots[run].parent.parent / "trace_prefix_evidence" / (declaration["snapshot_sha256"] + ".json")
            check(snapshot_path.resolve() == snapshot_path and not source_path(snapshot_path).is_symlink(), "publication_prefix_snapshot_path")
            raw_snapshot = source_path(snapshot_path).read_bytes()
            snapshot = loads(raw_snapshot)
            check(sha256(raw_snapshot).hexdigest() == declaration["snapshot_sha256"] and snapshot == {
                "schema_version": "0.1", "capability_id": declaration["capability_id"],
                "journal_revision": declaration["journal_revision"], "binding": self.proof["binding"],
                "journal": declaration["journal"], "publication": declaration["publication"]}, "publication_prefix_snapshot")
            keys(declaration["issuer"], ISSUER_FIELDS, "prefix_issuer")
            with closing(sqlite3.connect(source_path(self.database(run)).as_uri() + "?mode=ro", uri=True)) as connection:
                row = connection.execute("SELECT revision,value FROM invocation_capabilities WHERE capability_id=?",
                                         (declaration["capability_id"],)).fetchone()
            check(row is not None and type(declaration["journal_revision"]) is int and
                  0 < declaration["journal_revision"] <= row[0], "publication_prefix_journal_revision")
            actual = loads(row[1])
            check(set(journal) == set(actual), "publication_prefix_journal_fields")
            check(declaration["capability_id"] == call["capability_id"] and declaration["producer_operation_id"] ==
                  call["authorization"]["producer_operation_id"] and journal["authorization"] == actual["authorization"] ==
                  call["authorization"] and journal["state"] in ("started", "finished") and
                  actual["state"] in ("started", "finished"), "publication_prefix_capability")
            check(journal["state"] == "started" or declaration["stage"] == "host_rejected", "publication_prefix_completed_scope")
            check(journal["state"] == actual["state"] or declaration["journal_revision"] < row[0], "publication_prefix_capture_revision")
            for key in ("worker_id", "invocation_epoch", "started_intent", "deadline"):
                check(journal[key] == actual[key], "publication_prefix_journal_owner")
            check(frozen(journal.get("completion_intent")) == frozen(actual.get("completion_intent")),
                  "publication_prefix_frozen_completion")
            check([frozen(item) for item in journal["budget_intents"]] == [frozen(item) for item in actual["budget_intents"]],
                  "publication_prefix_budget_journal")
            producer = call["producer"]
            check(declaration["issuer"] == {"worker_id": journal["worker_id"], "invocation_epoch": journal["invocation_epoch"],
                "producer_epoch": producer["lease_epoch"], "producer_revision": producer["phase_revision"]} and
                all(settlement["payload"][key] == producer[key] for key in ("operation_id", "lease_epoch", "phase_revision")),
                "publication_prefix_issuer")
            self.validate_publication(declaration, journal, identity, run)
            owner = {key: identity[key] for key in ("case_id", "run_id", "attempt_id")}
            key = (*run, identity["attempt_id"])
            check(key not in self.prefixes, "publication_prefix_attempt_duplicate")
            self.prefixes[key] = (declaration, journal)
            self.prefixes[head] = (declaration, journal)
            self.prefix_settlements[declaration["settlement_head"]] = (declaration, journal)
            matches = [item for item in events if item["event"] == "ordinary_publication_prefix" and
                       item["attempt_id"] == identity["attempt_id"] and item["run_id"] == run[1]]
            check(len(matches) == 1 and matches[0]["guard"] == declaration["stage"] and
                  matches[0]["execution_head"] == declaration["publication"]["execution_head"] and
                  matches[0]["result_digest"] is None and matches[0]["owner"] == producer["operation_id"] and
                  matches[0]["lease_epoch"] == journal["invocation_epoch"], "publication_prefix_event")
            self.bind_source_owner(call["outcome"]["sha256"], owner)
        super().validate(sources, executions, roots, events)
        check(self.used_prefixes == {item["reservation_head"] for item in declarations}, "publication_prefix_set")
        check(sum(item["event"] == "ordinary_publication_prefix" for item in events) == len(declarations),
              "publication_prefix_event_set")

    def validate_publication(self, declaration, journal, identity, run):
        publication = declaration["publication"]
        keys(publication, PUBLICATION_FIELDS, "prefix_publication")
        check(type(publication["artifact_history"]) is str and type(publication["artifact_index"]) is str and
              type(publication["checkpoint_published"]) is bool and type(publication["checkpoint_committed"]) is bool,
              "publication_prefix_fields")
        head = publication["execution_head"]
        records = self.executions[run]
        matching = [row for row in records if digest(row) == head]
        check(len(matching) == 1, "publication_prefix_execution_head")
        records = records[:matching[0]["event_index"]]
        prefix = invocation_prefix(journal, published=False)
        completion = journal.get("completion_intent")
        content = b"".join(canonical_bytes(row) + b"\n" for row in records)
        expected = [journal["started_intent"]["content"], *[item["content"] for item in journal["budget_intents"]]]
        if completion is not None:
            expected.append(completion["content"])
        check(content.decode() in expected and (source_path(self.roots[run] / "execution_history.jsonl")).read_bytes().startswith(content),
              "publication_prefix_original_ledger")
        history = publication["artifact_history"].encode()
        check((source_path(self.roots[run] / "artifact_history.jsonl")).read_bytes().startswith(history), "publication_prefix_history_bytes")
        indices = [journal["started_intent"]["index"], *[item["index"] for item in journal["budget_intents"]]]
        plan = completion["artifact_publication"] if completion is not None else None
        if completion is not None:
            indices.append(completion["index"])
            from lqcd_agent.control.projections import attach_checkpoint, bounded_projection
            execution = parse_ledger(completion["content"].encode())
            finished = next(row for row in reversed(execution.values) if row["record_type"] == "attempt")
            index = loads(completion["index"])
            core = bounded_projection(execution, artifact_index=index, artifact_head=finished["artifact_head"],
                                      artifact_event_index=finished["artifact_event_index"])
            check(completion["content"].startswith(prefix["content"]) and finished["event"] == "finished" and
                  all(finished[key] == value for key, value in identity.items()) and
                  completion["projection"] == attach_checkpoint(core, execution, completion["manifest"]).value and
                  completion["checkpoint"]["channel_values"]["control"] == core.value and
                  completion["manifest"]["checkpoint_digest"] == digest(completion["checkpoint"]),
                  "publication_prefix_completion_ledger")
        check(publication["artifact_index"] in indices, "publication_prefix_index")
        check(publication["index_source"] in ("current_file", "finished_journal_checkpoint"), "publication_prefix_index_source")
        if publication["index_source"] == "finished_journal_checkpoint":
            check(journal["state"] == "finished" and completion is not None and completion["published"] and
                  publication["artifact_index"] == completion["index"] and publication["checkpoint_published"],
                  "publication_prefix_historical_index")
        if plan is None:
            check(sha256(history).hexdigest() == journal["authorization"]["artifact_history_digest"], "publication_prefix_unregistered_history")
            check(publication["projected_members"] == [], "publication_prefix_no_projection")
        else:
            check(history.decode() in (plan["previous"], plan["content"]), "publication_prefix_history_plan")
            registrations = [loads(line) for line in plan["content"].encode().splitlines()]
            registration, = [row for row in registrations if row["event"] == "registered" and row["attempt_id"] == identity["attempt_id"]]
            check(plan["content"].startswith(plan["previous"]) and all(registration[key] == identity[key]
                  for key in ("case_id", "run_id", "attempt_id")) and registration["pointer"]["attempt_kind"] == identity["attempt_kind"],
                  "publication_prefix_registration_owner")
            declared = {member["canonical_path"]: member for member in registration["members"]}
            check(set(declared) == {member["canonical_path"] for member in plan["projections"]}, "publication_prefix_member_set")
            values = {}
            check(type(publication["projected_members"]) is list and len(set(publication["projected_members"])) ==
                  len(publication["projected_members"]) and set(publication["projected_members"]) <=
                  {member["logical_name"] for member in declared.values()}, "publication_prefix_projection_set")
            for member in plan["projections"]:
                raw = b64decode(member["content_base64"], validate=True)
                bound = declared[member["canonical_path"]]
                path = self.roots[run] / member["canonical_path"]
                check(bound["logical_name"] in MEMBERS[identity["attempt_kind"]] and member["canonical_path"] ==
                      "attempts/" + identity["attempt_id"] + "/" + bound["logical_name"] and
                      path.resolve() == path and not source_path(path).is_symlink() and source_path(path).read_bytes() == raw and
                      sha256(raw).hexdigest() == member["sha256"] == bound["sha256"] and len(raw) == bound["size_bytes"] and
                      member["projection_path"] == bound["projection_path"], "publication_prefix_frozen_member")
                if bound["logical_name"] in publication["projected_members"]:
                    projected = self.roots[run] / member["projection_path"]
                    check(projected.resolve() == projected and not source_path(projected).is_symlink() and source_path(projected).read_bytes() == raw,
                          "publication_prefix_projection_bytes")
                owner = {key: identity[key] for key in ("case_id", "run_id", "attempt_id")}
                _, value = self.add({"schema_version": "0.1", "profile": "member", "sha256": bound["sha256"],
                                     "content": raw.decode()}, owner)
                values[bound["logical_name"]] = (bound["sha256"], value)
            self.prefix_members[(*run, identity["attempt_id"])] = values
        if publication["checkpoint_committed"]:
            check(completion is not None, "publication_prefix_checkpoint_owner")
            from lqcd_agent.control.checkpoints import verify_checkpoint
            verify_checkpoint(source_path(self.roots[run]), completion["manifest"])
        if publication["checkpoint_published"]:
            check(completion is not None and publication["checkpoint_committed"], "publication_prefix_checkpoint_owner")
            manifest = completion["manifest"]
            path = self.roots[run] / "checkpoints" / (manifest["checkpoint_id"] + ".json")
            check(source_path(path).is_file() and loads(source_path(path).read_bytes()) == manifest, "publication_prefix_checkpoint_manifest")
        check(declaration["stage"] == publication_stage(journal, publication), "publication_prefix_stage")

    def agent_result(self, owner, node, result):
        key = owner["case_id"], owner["run_id"], owner["attempt_id"]
        registered = [v for identity, role, name, v in self.member_bindings if identity == owner and
                      role == node and name == node + "_diagnostic.json"]
        if key not in self.prefixes:
            return super().agent_result(owner, node, result)
        declaration, journal = self.prefixes[key]
        self.used_prefixes.add(declaration["reservation_head"])
        if registered:
            return super().agent_result(owner, node, result)
        validate_product_diagnostic(result["diagnostic"])
        reserved = {"schema_version", "producer", "status", "case_id", "run_id", "cycle_id", "attempt_id", "attempt_kind",
                    "node_name", "transition_id", "parent_attempt_id"}
        completion = journal.get("completion_intent")
        if reserved & result["content"].keys():
            check(declaration["stage"] == "host_rejected" and completion is not None, "publication_prefix_reserved_return")
            finished = parse_ledger(completion["content"].encode()).values[-1]
            check(finished["event"] == "finished" and finished["status"] == "failed" and
                  finished["error"]["type"] == "ControlIntegrityError" and
                  finished["error"]["message"] == "Agent content includes reserved Host fields", "publication_prefix_host_rejection")
            return
        values = self.prefix_members.get(key)
        if values is None:
            check(completion is None, "publication_prefix_missing_domain_plan")
            return
        final = values[node + "_diagnostic.json"][1]
        validate_product_diagnostic(final)
        expected = {**result["diagnostic"], "evidence": final["evidence"]} if result["diagnostic"]["evidence"] == [] else result["diagnostic"]
        check(final == expected, "publication_prefix_agent_diagnostic")
        name = {"method_planner": "method_plan.json", "analysis_engineer": "run_result.json",
                "scientific_reviewer": "scientific_review_report.json"}[node]
        main = values[name][1]
        identity = journal["authorization"]["identity"]
        check(main["producer"] == node and main["schema_version"] == "0.1" and all(main[key] == value for key, value in identity.items()) and
              all(main[key] == value for key, value in result["content"].items()), "publication_prefix_agent_content")

    def finish_content(self, head, content, project_source):
        result = super().finish_content(head, content, project_source)
        if head not in self.prefix_settlements:
            return result
        declaration, journal = self.prefix_settlements[head]
        identity = journal["authorization"]["identity"]
        members = self.prefix_members.get((identity["case_id"], identity["run_id"], identity["attempt_id"]), {})
        return ["ordinary_publication_prefix", result, declaration["stage"],
                declaration["publication"]["index_source"], declaration["publication"]["projected_members"],
                [[name, project_source(value[0])] for name, value in sorted(members.items())]]
