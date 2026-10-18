"""Explicit 0.8 product provenance; declarations never confer authority."""
from contextlib import closing
from hashlib import sha256
import sqlite3

from lqcd_agent.control.budget import CAUSE_FIELDS, fingerprint, semantic_context, validate_budget_payload, validate_fingerprint
from lqcd_agent.control.capabilities import invocation_prefix
from lqcd_agent.control.execution import replay
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from . import a05_trace
from .ordinary_maximum_trace import MaximumProjection
from .ordinary_trace import check
from .fault_source_trace import source_path
from .strict_json import Invalid, keys


PROOF_FIELDS = {"schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources",
                "workspace_roots", "ordinary_calls", "ordinary_members", "ordinary_maximum_settlements",
                "product_failure_sources", "product_grant_sources"}
FAILURE_FIELDS = {"schema_version", "failure_head", "capability_id", "producer_operation_id", "issuer",
                  "source_attempt_id", "source_registration_head", "diagnostic_binding", "derivation"}
GRANT_FIELDS = {"schema_version", "grant_head", "capability_id", "producer_operation_id", "issuer", "human_request_head",
                "response_submitted_head", "response_validated_head", "response_consumed_head", "snapshot_registration_head",
                "pause_consumed_head", "resume_operation_id", "failure_head", "admission"}
INPUT_FIELDS = {"kind", "head", "registration_head", "member", "path"}
BINDING_FIELDS = {"profile", "inputs", "projection", "value", "not_applicable_reason"}
METADATA = {"schema_version", "case_id", "run_id", "attempt_id", "attempt_kind", "producer", "status"}


def project(events, proof, binding):
    try:
        keys(proof, PROOF_FIELDS, "product_proof")
        check(proof["schema_version"] == "0.5", "product_proof_version")
        extension = ProductProjection(proof)
        base = {k: v for k, v in proof.items() if k not in PROOF_FIELDS - {
            "schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources", "workspace_roots"}}
        base["schema_version"] = "0.2"
        return a05_trace._project(events, base, binding, ordinary=extension)
    except Invalid:
        raise
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, RecursionError, StopIteration) as error:
        raise Invalid("product_trace", "provenance", "invalid_evidence") from error


class ProductProjection(MaximumProjection):
    product_sources = True

    def __init__(self, proof):
        super().__init__(proof)
        self.product_declarations = {}
        self.owner_bindings = {}
        self.derivation_heads = set()

    def envelope(self, declaration, profile, owner):
        keys(declaration, {"schema_version", "profile", "sha256", "content"}, "product_envelope")
        check(declaration["schema_version"] == "0.1" and declaration["profile"] == profile and
              type(declaration["content"]) is str, "product_profile")
        raw = declaration["content"].encode()
        value = loads(raw)
        check(sha256(raw).hexdigest() == declaration["sha256"] and canonical_bytes(value) == raw, "product_bytes")
        return self.internal_source(value, owner), value

    def internal_source(self, value, owner):
        head = digest(value)
        if head in self.base_sources:
            check(self.base_sources[head]["value"] == value, "product_source_collision")
            return head
        row = {"kind": "ordinary", "sha256": head, "value": value, "references": []}
        check(head not in self.sources or self.sources[head] == row, "product_source_collision")
        self.sources[head] = row
        self.bind_source_owner(head, owner)
        self.refs.setdefault(head, {})
        return head

    def validate(self, sources, executions, roots, events):
        super().validate(sources, executions, roots, events)
        self.repause_sources(sources, executions)
        def diagnostic_source(run, request):
            candidates = self.request_diagnostic_sources(run, request["requesting_attempt_id"])
            check(len(candidates) == 1 and candidates[0][0] == request["authorization_scope"]["diagnostic_digest"],
                  "product_human_diagnostic_owner")
            return candidates[0][0]
        for head, row in sources.items():
            value = row["value"]
            if value.get("record_type") == "human_request" and "diagnostic_digest" in value["authorization_scope"]:
                run = value["case_id"], value["run_id"]
                request, = [r for r in executions[run] if r.get("event") == "created" and
                            r.get("record_type") == "human_request" and r["human_request_id"] == value["human_request_id"]]
                check(value["authorization_scope"] == request["authorization_scope"], "product_human_scope_copy")
                self.reference(head, ("authorization_scope", "diagnostic_digest"), diagnostic_source(run, request))
            candidates = [((), value)]
            if type(value.get("channel_values", {}).get("control")) is dict:
                candidates.append((("channel_values", "control"), value["channel_values"]["control"]))
            for prefix, state in candidates:
                if state.get("schema_version") != "0.4" or "current_artifacts" not in state:
                    continue
                run = state["case_id"], state["run_id"]
                index = state["execution_event_index"]
                check(run in executions and type(index) is int and 0 < index <= len(executions[run]), "product_projection_owner")
                prefix_records = executions[run][:index]
                check(state["execution_head"] == digest(prefix_records[-1]), "product_projection_revision")
                scope = state.get("human_request_authorization_scope")
                if scope is not None and "diagnostic_digest" in scope:
                    request, = [r for r in prefix_records if r.get("record_type") == "human_request" and r["event"] == "created" and
                                r["human_request_id"] == state["active_human_request_id"]]
                    check(scope == request["authorization_scope"], "product_projection_human_scope")
                    self.reference(head, (*prefix, "human_request_authorization_scope", "diagnostic_digest"), diagnostic_source(run, request))
                summary = state["budget"]["latest_decision"]
                if summary is None:
                    continue
                decisions = [record for record in prefix_records if record.get("event") == "decision_recorded"]
                check(bool(decisions), "product_projection_decision")
                decision = decisions[-1]
                check(summary == {k: decision["payload"][k] for k in
                      ("proposal_id", "decision", "reason_code", "next_control_action", "decision_digest")}, "product_projection_summary")
                # Resolve the existing decision source at this exact historical
                # revision. Both checksums retain its complete owner and facts.
                for field in ("proposal_id", "decision_digest"):
                    self.reference(head, (*prefix, "budget", "latest_decision", field), digest(decision))

    def repause_sources(self, sources, executions):
        for head, row in sources.items():
            decision = row["value"]
            if decision.get("record_type") != "budget" or decision.get("event") != "decision_recorded" or \
                    decision["payload"]["proposed_action"] != "repause":
                continue
            run = decision["case_id"], decision["run_id"]
            prefix = executions[run][:decision["event_index"] - 1]
            check(bool(prefix) and decision["previous_execution_head"] == digest(prefix[-1]), "product_repause_prefix")
            validator = prefix[-1]
            pauses = [r for r in prefix if r["record_type"] == "pause"]
            responses = [r for r in prefix if r["record_type"] == "human_response"]
            check(bool(pauses) and bool(responses), "product_repause_sources")
            pause, response = pauses[-1], responses[-1]
            state = replay(prefix).projection.value
            check(validator["record_type"] == "attempt" and validator["event"] == "finished" and
                  response["status"] == "invalid" and response["validator_attempt_id"] == validator["attempt_id"] and
                  pause["status"] == "consumed" and pause["input_contract"]["human_request_id"] ==
                  response["human_request_id"] == state["active_human_request_id"], "product_repause_owner")
            dimensions = decision["payload"]["dimensions"]
            check(set(dimensions) == set(state["budget"]["dimensions"]) and all(
                all(row[key] == state["budget"]["dimensions"][name][key] for key in ("used", "remaining"))
                for name, row in dimensions.items()), "product_repause_dimensions")
            binding = {"consumed_old_pause": digest(pause), "finished_validator_attempt": digest(validator),
                       "open_human_request": state["active_human_request_id"],
                       "derived_next_pause_identity": f"pause_{state['pause_index'] + 1:06d}", "terminal_tail_capacity": dimensions}
            check(decision["payload"]["proposal_id"] == digest(binding), "product_repause_proposal")
            binding_head = self.internal_source(binding, dict(zip(("case_id", "run_id"), run)))
            self.reference(binding_head, ("consumed_old_pause",), digest(pause))
            self.reference(binding_head, ("finished_validator_attempt",), digest(validator))
            self.reference(head, ("payload", "proposal_id"), binding_head)

    def issuer(self, declaration, record):
        keys(declaration["issuer"], {"worker_id", "invocation_epoch", "producer_epoch", "producer_revision"}, "product_issuer")
        run = record["case_id"], record["run_id"]
        database = self.roots[run].parent.parent / ".lqcd/control_operations.sqlite"
        with closing(sqlite3.connect(source_path(database).as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT value FROM invocation_capabilities WHERE capability_id=?", (declaration["capability_id"],)).fetchone()
            check(row is not None, "product_capability")
            capability = loads(row[0])
            operation = connection.execute("SELECT * FROM control_operations WHERE operation_id=?", (declaration["producer_operation_id"],)).fetchone()
            check(operation is not None, "product_producer")
            producer = dict(operation)
        auth, issuer = capability["authorization"], declaration["issuer"]
        check(auth["producer_operation_id"] == declaration["producer_operation_id"] and
              declaration["capability_id"] == "capability_" + declaration["producer_operation_id"] and
              auth["identity"]["attempt_kind"] == "decision_coordinator" and
              (auth["identity"]["case_id"], auth["identity"]["run_id"]) == run and
              capability["authorization_digest"] == digest(auth) and auth["scope"] == "attempt_execution" and
              auth["terminal_closure_revision"] == 0 and capability["started_intent"] is not None and
              capability["started_intent"]["published"], "product_issuer_owner")
        check(issuer == {"worker_id": capability["worker_id"], "invocation_epoch": capability["invocation_epoch"],
              "producer_epoch": auth["producing_epoch"], "producer_revision": auth["activation_result_revision"]} and
              producer["lease_epoch"] == issuer["producer_epoch"] and producer["phase_revision"] == issuer["producer_revision"] and
              producer["status"] == "committed", "product_issuer_fence")
        invocation_prefix(capability, published=False)
        journals = [entry for entry in capability.get("budget_intents", []) if entry["record"] == record]
        check(len(journals) == 1 and journals[0]["published"], "product_original_journal")
        started = capability["started_intent"]["record"]
        check(started in self.executions[run] and started["attempt_id"] == auth["identity"]["attempt_id"] and
              started["event_index"] < record["event_index"] and
              all(record[k] == auth["identity"][k] for k in ("case_id", "run_id")), "product_started_order")
        return capability, journals[0], auth["identity"]

    def failure_recipe(self, declaration, record, coordinator):
        run = record["case_id"], record["run_id"]
        rows = self.executions[run]
        registrations = {row[1]["artifact_id"]: row[1] for key, row in self.registered.items() if key[:2] == run}
        registration = self.base_sources[declaration["source_registration_head"]]["value"]
        source = registration["pointer"]
        check(registration["event"] == "registered" and (registration["case_id"], registration["run_id"]) == run and
              source["attempt_id"] == declaration["source_attempt_id"] and
              registration["event_index"] <= record["artifact_event_index"], "product_failure_registration")
        scheduled = next(r for r in rows if r["record_type"] == "attempt" and r["event"] == "scheduled" and
                         r["attempt_id"] == source["attempt_id"])
        issuer_scheduled = next(r for r in rows if r["record_type"] == "attempt" and r["event"] == "scheduled" and
                                r["attempt_id"] == coordinator["attempt_id"])
        check(issuer_scheduled["parent_attempt_id"] == source["attempt_id"], "product_failure_parent")
        diagnostic = declaration["diagnostic_binding"]
        keys(diagnostic, {"kind", "registration_head", "member", "sha256"}, "product_diagnostic")
        member = next(m for m in source["members"] if m["logical_name"] == diagnostic["member"])
        is_code = source["attempt_kind"] == "code_agent"
        check(diagnostic == {"kind": "canonical_code_result" if is_code else "ordinary_diagnostic", "registration_head": declaration["source_registration_head"],
              "member": "code_agent_result.json" if is_code else source["attempt_kind"] + "_diagnostic.json", "sha256": member["sha256"]}, "product_diagnostic_owner")
        value = (self.sources.get(member["sha256"]) or self.base_sources[member["sha256"]])["value"]
        check(value["status"] != "success" or (not value["usable"] if is_code else value["candidates"]), "product_actual_failure")
        call, = [r for r in rows if r.get("event") == "resource_reserved" and r["payload"]["attempt_id"] == source["attempt_id"] and
                  (r["payload"]["resource_kind"] == "code_backend_operation" if is_code else r["payload"]["resource_operation_id"].endswith(":domain-diagnosis"))]
        config = {"node": source["attempt_kind"], "structured_output": True}
        if not is_code:
            captured, = [c for c in self.proof["ordinary_calls"] if c["reservation_head"] == digest(call)]
            check(loads(captured["config"]["content"]) == config, "product_actual_config")
        selected = {}
        history = sorted((row["value"] for row in self.base_sources.values() if row["kind"] == "canonical_json" and
                         row["value"].get("event") in ("current_set", "current_cleared") and
                         (row["value"].get("case_id"), row["value"].get("run_id")) == run and
                         row["value"]["event_index"] <= call["artifact_event_index"]), key=lambda r: r["event_index"])
        for row in history:
            if row["event"] == "current_set":
                selected[row["slot"]] = registrations[row["artifact_id"]]
            else:
                selected.pop(row["slot"], None)
        for slot, artifact in scheduled["input_references"]["current_artifact_ids"].items():
            selected.setdefault(slot, registrations[artifact])
        selected[source["slot"]] = registration

        def ref(kind, head, member=None, registration_head=None, path=()):
            return {"kind": kind, "head": head, "registration_head": registration_head, "member": member, "path": list(path)}

        expected, leaves, inputs = {}, [], []
        for name, field in (("root_goal.json", "root_goal_reference"), ("input_snapshot.json", "input_snapshot_reference")):
            raw = (source_path(self.roots[run] / name)).read_bytes()
            creation = rows[0][field]
            check(creation == {"reference": name, "sha256": sha256(raw).hexdigest()}, "product_root_owner")
            science = loads(raw)
            self.internal_source(science, dict(zip(("case_id", "run_id"), run)))
            leaves.append({"member_id": name, "content_digest": digest(science)})
            inputs.append(ref("root_input", sha256(raw).hexdigest(), name))
        for slot, name in (("plan", "method_plan.json"), ("analysis", "run_result.json"), ("review", "scientific_review_report.json")):
            if slot not in selected:
                continue
            reg = selected[slot]
            main = next(m for m in reg["members"] if m["logical_name"] == name)
            domain = self.sources[main["sha256"]]["value"]
            science = {k: v for k, v in domain.items() if k not in METADATA}
            item = ref("member", main["sha256"], name, digest(reg))
            leaves.append({"member_id": slot + "/" + name, "content_digest": digest(science)})
            inputs.append(item)
            if slot == "plan":
                expected["plan_digest"] = ("domain_v1", [item], science, digest(science), None)
        code_inputs, code_science, code_context, code_config, analysis_spec = [], None, None, None, None
        stable = {"exit_code": None, "signal": None, "failing_test_ids": [], "validator_errors": []}
        if "code" in selected:
            from lqcd_agent.code_agent.schemas import POLICIES, validate_task, validate_manifest
            from lqcd_agent.code_agent.artifacts import validate_code_result
            from lqcd_agent.code_agent.ingress import validate_change_manifest
            from lqcd_agent.code_agent.verification import build_verification_results
            reg = selected["code"]
            members = {m["logical_name"]: m for m in reg["members"]}
            values = {}
            for name in ("code_agent_task.json", "code_agent_result.json", "workspace_manifest.json", "change_manifest.json", "verification_results.json"):
                member = members[name]
                values[name] = self.base_sources[member["sha256"]]["value"]
                code_inputs.append(ref("member", member["sha256"], name, digest(reg)))
            task = validate_task(values["code_agent_task.json"]).value
            result = validate_code_result(values["code_agent_result.json"], task).value
            manifest = validate_manifest(values["workspace_manifest.json"], task).value
            changes = validate_change_manifest(values["change_manifest.json"], task, manifest).value
            verification = values["verification_results.json"]
            check(verification == build_verification_results(task, verification["spec_results"]), "product_code_verification")
            code_science = {"base_revision": task["base_revision"], "base_tree_digest": task["base_tree_digest"],
                            "final_tree_digest": changes["final_tree_digest"], "changes": changes["changes"], "patch_digest": result["patch_digest"]}
            change_science = {k: code_science[k] for k in ("base_tree_digest", "final_tree_digest", "changes")}
            evidence_digests = []
            for evidence in task["evidence"]:
                evidence_registration = registrations[evidence["artifact_id"]]
                evidence_member = next(m for m in evidence_registration["members"] if m["canonical_path"] == evidence["path"])
                science, extra_inputs = self.task_evidence_science(task, evidence, evidence_registration, evidence_member)
                code_inputs.extend(extra_inputs)
                evidence_digests.append(digest(science))
                code_inputs.append(ref("member", evidence_member["sha256"], evidence_member["logical_name"], digest(evidence_registration)))
            code_context = {"requirements": task["requirements"], "acceptance_criteria": task["acceptance_criteria"],
                "input_evidence_digests": sorted(set(evidence_digests)), "base_revision": task["base_revision"],
                "base_tree_digest": task["base_tree_digest"], "backend_kind": task["coding_backend_kind"],
                "runtime_digest": digest({"backend_version": task["backend_version"], "backend_runtime_fingerprint": task["backend_runtime_fingerprint"]}),
                "policy_digest": task["budget_policy_digest"],
                "path_policy_digest": digest({k: task[k] for k in ("read_paths", "write_paths", "forbidden_paths", "filesystem_policy")}),
                "tool_policy_digest": digest(task["tool_policy"]), "network_policy_digest": digest(task["network_policy"])}
            code_config = {k: task[k] for k in ("task_origin", "task_summary", "requirements", "acceptance_criteria", "base_revision", "base_tree_digest",
                "coding_backend_kind", "backend_version", "backend_runtime_fingerprint", "source_runtime_fingerprint", *POLICIES, "verification_specs",
                "budget_policy_version", "budget_profile_id", "budget_policy_digest", "expected_result_schema")}
            leaves.append({"member_id": "code/code_agent_result.json", "content_digest": digest(code_science)})
            inputs.extend(code_inputs)
        leaves.sort(key=lambda r: r["member_id"])
        scheduled_input = ref("execution_record", digest(scheduled), path=("attempt_kind",))
        config_input = ref("ordinary_call", digest(call), path=("config",))
        policy = next(r for r in rows if r.get("event") == "policy_initialized")
        expected.update({"program_ids": ("host_ids_v1", [scheduled_input], [source["attempt_kind"]], [source["attempt_kind"]], None),
            "tool_ids": ("host_ids_v1", [config_input], ["domain-diagnosis"], ["domain-diagnosis"], None),
            "verification_ids": ("host_ids_v1", [scheduled_input], [], [], None),
            "input_members": ("input_members_v1", inputs, leaves, leaves, None),
            "config_digest": ("host_config_v1", [config_input], config, digest(config), None),
            "policy_digest": ("policy_v1", [ref("execution_record", digest(policy), path=("payload", "policy"))],
                              policy["payload"]["policy"], policy["payload"]["policy"]["policy_digest"], None)})
        for field, reason in (("plan_digest", "no_plan"), ("code_digest", "no_code"), ("base_revision", "no_immutable_base"),
                              ("base_tree_digest", "no_immutable_base"), ("code_task_context_digest", "no_code"),
                              ("analysis_execution_context_digest", "no_fresh_analysis")):
            expected.setdefault(field, ("not_applicable_v1", [], None, None, reason))
        if code_science is not None:
            task_input = next(r for r in code_inputs if r["member"] == "code_agent_task.json")
            expected["code_digest"] = ("code_causal_v1", code_inputs, code_science, digest(code_science), None)
            expected["code_task_context_digest"] = ("code_causal_v1", code_inputs, code_context, semantic_context("code", code_context), None)
            expected["base_revision"] = ("host_ids_v1", [task_input], task["base_revision"], task["base_revision"], None)
            expected["base_tree_digest"] = ("host_ids_v1", [task_input], task["base_tree_digest"], task["base_tree_digest"], None)
            ids = sorted(spec["spec_id"] for spec in task["verification_specs"])
            expected["verification_ids"] = ("host_ids_v1", [task_input], ids, ids, None)
            if is_code:
                ids = sorted(spec["spec_id"] for spec in task["tool_policy"])
                expected["tool_ids"] = ("host_ids_v1", [task_input], ids, ids, None)
                expected["config_digest"] = ("host_config_v1", [task_input], code_config, digest(code_config), None)
                stable["failing_test_ids"] = sorted(r["spec_id"] for r in verification["spec_results"] if r["status"] == "failed")
            if "analysis" in selected:
                analysis_source = selected["analysis"]["pointer"]
                tool, = [c for c in self.proof["ordinary_calls"] if c["profile"] == "analysis_tool" and
                         c["authorization"]["identity"]["attempt_id"] == analysis_source["attempt_id"] and
                         (c["authorization"]["identity"]["case_id"], c["authorization"]["identity"]["run_id"]) == run]
                preparation = loads(tool["input"]["content"])
                analysis_spec = loads(preparation["canonical_spec_bytes"])
                analysis_config = loads(tool["config"]["content"])
                check(analysis_config["environment"] == analysis_spec["environment_policy"] and
                      analysis_config["command"] == analysis_spec["allowed_command"] and analysis_config["outputs"] == analysis_spec["expected_outputs"] and
                      digest(analysis_config["runtime"]) == analysis_spec["analysis_runtime_fingerprint"] and
                      digest(analysis_config) == preparation["runtime_policy_digest"], "product_analysis_config")
                spec_input = ref("typed_source", digest(analysis_spec))
                selected_leaves = []
                for slot, selected_input in analysis_spec["selected_input_artifacts"].items():
                    check(slot in selected and selected_input == {"artifact_id": selected[slot]["artifact_id"], "digest": digest(selected[slot]["pointer"])}, "product_analysis_selected")
                    selected_leaves.extend(leaf["content_digest"] for leaf in leaves if leaf["member_id"].startswith(slot + "/"))
                analysis_context = {"verified_change_digest": digest(change_science), "effective_tree_digest": changes["final_tree_digest"],
                    "base_revision": task["base_revision"], "base_tree_digest": task["base_tree_digest"], "input_code_digest": digest(code_science),
                    "input_artifact_digests": sorted(set(selected_leaves)), "runtime_digest": digest(analysis_config),
                    "policy_digest": policy["payload"]["policy"]["policy_digest"]}
                expected["analysis_execution_context_digest"] = ("analysis_causal_v1", code_inputs + inputs + [spec_input], analysis_context,
                                                                  semantic_context("analysis", analysis_context), None)
                scientific_config = {"agent": config, "code": code_config, "analysis": analysis_config}
                expected["config_digest"] = ("host_config_v1", [config_input, task_input, spec_input], scientific_config, digest(scientific_config), None)
                main = next(m for m in analysis_source["members"] if m["logical_name"] == "run_result.json")
                stable["exit_code"] = self.sources[main["sha256"]]["value"]["execution"]["returncode"]
        if is_code:
            category = result["status"]
            layer = {"scope_violation": "security", "policy_violation": "policy", "verification_failed": "verification",
                     "tool_error": "tool", "timeout": "control", "external_interruption": "control"}.get(result["failure_class"], "code")
            value = {"status": result["failure_class"], "category": category}
        else:
            category = value["category"]
            layer = next((n for n in ("security", "policy", "data", "scientific", "provider", "verification", "tool") if
                      category == n or category.startswith((n + ".", n + "_"))), "tool" if category == "analysis_execution" else "control")
        return expected, value, layer, stable

    def task_evidence_science(self, task, evidence, registration, member):
        check(member["sha256"] == evidence["sha256"] and registration["slot"] in ("plan", "analysis", "review"), "product_code_evidence")
        value = self.sources[member["sha256"]]["value"]
        return {k: v for k, v in value.items() if k not in METADATA}, []

    def failure_and_grant_sources(self, sources, executions):
        declarations = {}
        for field, event, fields in (("product_failure_sources", "failure_observed", FAILURE_FIELDS),
                                     ("product_grant_sources", "grant_issued", GRANT_FIELDS)):
            array = self.proof[field]
            check(type(array) is list, "product_array")
            expected = [digest(r) for run in sorted(executions) for r in executions[run] if r.get("event") == event]
            actual = []
            for declaration in array:
                keys(declaration, fields, "product_declaration")
                head = declaration["failure_head" if event == "failure_observed" else "grant_head"]
                check(declaration["schema_version"] == "0.1" and head not in declarations, "product_duplicate")
                declarations[head] = declaration
                actual.append(head)
            check(actual == expected, "product_source_set_order")
        failures, grants = {}, {}
        for run, records in executions.items():
            owner = dict(zip(("case_id", "run_id"), run))
            for record in records:
                if record.get("record_type") != "budget":
                    continue
                payload, head = record["payload"], digest(record)
                validate_budget_payload(record["event"], payload)
                if record["event"] == "failure_observed":
                    declaration = declarations[head]
                    capability, journal, issuer = self.issuer(declaration, record)
                    expected, diagnostic, layer, stable = self.failure_recipe(declaration, record, issuer)
                    derivation_head, derivation = self.envelope(declaration["derivation"], "product_failure_derivation", owner)
                    self.derivation_heads.add(derivation_head)
                    keys(derivation, {"schema_version", "layer", "failure_class", "code", "diagnostics", "context_bindings"}, "product_derivation")
                    keys(derivation["context_bindings"], set(CAUSE_FIELDS), "product_cause")
                    check(derivation["schema_version"] == "0.1" and derivation["layer"] == layer and
                          derivation["failure_class"] == diagnostic["status"] and derivation["code"] == diagnostic["category"] and
                          derivation["diagnostics"] == stable, "product_classification")
                    context = {}
                    for field, (profile, inputs, projection, value, reason) in expected.items():
                        binding = derivation["context_bindings"][field]
                        keys(binding, BINDING_FIELDS, "product_binding")
                        for item in binding["inputs"]:
                            keys(item, INPUT_FIELDS, "product_input")
                        canonical_inputs = {canonical_bytes(item): item for item in inputs}
                        check(binding["profile"] == profile and binding["inputs"] == [canonical_inputs[key] for key in sorted(canonical_inputs)] and
                              binding["value"] == value and binding["not_applicable_reason"] == reason, "product_recipe")
                        projection_head, projected = self.envelope(binding["projection"], "failure_projection", owner)
                        check(projected == projection, "product_projection")
                        context[field] = value
                        self.reference(derivation_head, ("context_bindings", field, "projection", "sha256"), projection_head)
                        for i, item in enumerate(binding["inputs"]):
                            target = item["head"]
                            if item["kind"] == "ordinary_call":
                                target = loads(next(c["config"]["content"] for c in self.proof["ordinary_calls"] if c["reservation_head"] == target))
                                target = digest(target)
                            self.reference(derivation_head, ("context_bindings", field, "inputs", i, "head"), target)
                            if item["registration_head"] is not None:
                                self.reference(derivation_head, ("context_bindings", field, "inputs", i, "registration_head"), item["registration_head"])
                    fp = fingerprint(layer=layer, failure_class=diagnostic["status"], code=diagnostic["category"], context=context, diagnostics=stable).value
                    check(payload["fingerprint"] == fp, "product_actual_fingerprint")
                    fp_head, _ = self.add({"schema_version": "0.1", "profile": "fingerprint", "sha256": digest(fp),
                                          "content": canonical_bytes(fp).decode()}, owner)
                    cause_head, _ = self.add({"schema_version": "0.1", "profile": "causal_context", "sha256": digest(fp["context"]),
                                             "content": canonical_bytes(fp["context"]).decode()}, owner)
                    self.reference(fp_head, ("context",), cause_head)
                    self.reference(fp_head, ("causal_context_digest",), cause_head)
                    self.sizes[fp_head, ("fingerprint_digest",)] = ("self", None)
                    self.reference(head, ("payload", "fingerprint"), fp_head)
                    self.product_declarations[head] = (declaration, derivation_head)
                    failures[head] = (fp_head, payload["occurrence"], fp)
                elif record["event"] == "grant_issued":
                    declaration = declarations[head]
                    capability, journal, issuer = self.issuer(declaration, record)
                    admission_head = self.grant_recipe(declaration, record, capability, journal, failures)
                    fp_head, occurrence, _ = failures[declaration["failure_head"]]
                    snapshot_head, _, _ = self.human_snapshots[(*run, payload["human_response_id"])]
                    grant_head, _ = self.add({"schema_version": "0.1", "profile": "grant", "sha256": digest(payload),
                                             "content": canonical_bytes(payload).decode()}, owner)
                    self.reference(grant_head, ("response_digest",), snapshot_head)
                    self.reference(grant_head, ("fingerprint_digest",), fp_head)
                    self.reference(head, ("payload",), grant_head)
                    self.product_declarations[head] = (declaration, admission_head)
                    grants[(*run, payload["budget_grant_id"])] = (grant_head, payload, False)
                elif record["event"] == "grant_consumed":
                    key = (*run, payload["budget_grant_id"])
                    grant_head, issued, consumed = grants[key]
                    check(not consumed and payload["grant_digest"] == grant_head and all(payload[k] == issued[k] for k in
                          ("target_attempt_id", "transition_id")), "product_grant_single_use")
                    self.reference(head, ("payload", "grant_digest"), grant_head)
                    grants[key] = (grant_head, issued, True)
        for head, row in sources.items():
            value = row["value"]
            run = (value.get("case_id"), value.get("run_id"))
            if value.get("record_type") == "budget" and value.get("event") == "decision_recorded" and value["payload"]["fingerprint_digest"] is not None:
                candidates = [r for r in executions[run][:value["event_index"] - 1] if digest(r) in failures and
                              r["payload"]["fingerprint"]["fingerprint_digest"] == value["payload"]["fingerprint_digest"] and
                              r["payload"]["occurrence"] == value["payload"]["occurrence"]]
                check(bool(candidates), "product_decision_failure")
                self.reference(head, ("payload", "fingerprint_digest"), failures[digest(candidates[-1])][0])
            if value.get("record_type") == "human_request" and value.get("event") == "created" and "diagnostic_digest" in value["authorization_scope"]:
                candidates = self.request_diagnostic_sources(run, value["requesting_attempt_id"])
                check(len(candidates) == 1 and candidates[0][0] == value["authorization_scope"]["diagnostic_digest"], "human_diagnostic_source")
                self.reference(head, ("authorization_scope", "diagnostic_digest"), candidates[0][0])

    def grant_recipe(self, declaration, record, capability, journal, failures):
        run = record["case_id"], record["run_id"]
        rows = self.executions[run]
        payload = record["payload"]
        lookup = {digest(r): r for r in rows}
        request, submitted, validated, consumed, pause = [lookup[declaration[field]] for field in
            ("human_request_head", "response_submitted_head", "response_validated_head", "response_consumed_head", "pause_consumed_head")]
        check(request["record_type"] == "human_request" and request["event"] == "created" and
              all(row["record_type"] == "human_response" and row["event"] == event and
                  row["human_response_id"] == payload["human_response_id"] and row["human_request_id"] == request["human_request_id"]
                  for row, event in ((submitted, "submitted"), (validated, "validated"), (consumed, "consumed"))) and
              consumed["authorized_target_attempt_id"] == capability["authorization"]["identity"]["attempt_id"] and
              consumed["decision"] == validated["decision"] == "approve_budget_window" and
              submitted["event_index"] < validated["event_index"] < consumed["event_index"] < record["event_index"], "product_grant_stage")
        fp_head, occurrence, fp = failures[declaration["failure_head"]]
        scope = request["authorization_scope"]
        check(scope["failure_fingerprint"] == {"fingerprint_digest": fp["fingerprint_digest"],
              "causal_context_digest": fp["causal_context_digest"], "occurrence": occurrence} and
              scope["work_target"] == payload["target_node"] and "approve_budget_window" in scope["allowed_decisions"] and
              payload["occurrence"] == occurrence and payload["fingerprint_digest"] == fp["fingerprint_digest"] and
              lookup[declaration["failure_head"]]["event_index"] < request["event_index"], "product_grant_occurrence")
        snapshot_head, snapshot, path = self.human_snapshots[(*run, payload["human_response_id"])]
        registration = self.base_sources[declaration["snapshot_registration_head"]]["value"]
        check(registration["event"] == "protected_snapshot_registered" and registration["protected_kind"] == "human_response" and
              registration["human_response_id"] == payload["human_response_id"] and registration["members"][0]["sha256"] == snapshot_head and
              snapshot_head == payload["response_digest"] and path == payload["response_reference"] and
              pause["event"] == "pause_consumed" and pause["pause_id"] == payload["pause_id"] and
              pause["operation_id"] == declaration["resume_operation_id"], "product_grant_snapshot_pause")
        database = self.roots[run].parent.parent / ".lqcd/control_operations.sqlite"
        with closing(sqlite3.connect(source_path(database).as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            operation = connection.execute("SELECT * FROM control_operations WHERE operation_id=?", (declaration["resume_operation_id"],)).fetchone()
        check(operation is not None and operation["operation_type"] == "resume_run" and operation["status"] == "committed", "product_grant_resume")
        resume = loads(operation["request"])
        actor = resume["actor"]
        check(operation["request_digest"] == pause["proof"]["request_digest"] and resume["input_snapshot"] == snapshot and
              resume["input_digest"] == snapshot_head and resume["pause_id"] == pause["pause_id"] and
              actor == pause["proof"]["actor"] and snapshot["decided_by"] == actor["actor_id"] and
              actor["actor_type"] == pause["authorization_scope"]["actor_type"] and
              set(pause["authorization_scope"]["scopes"]) <= set(actor["scopes"]) and payload["actor_scope"] == ["approve_budget_window"], "product_grant_actor")
        admission_head, admission = self.envelope(declaration["admission"], "product_grant_admission", dict(zip(("case_id", "run_id"), run)))
        keys(admission, {"schema_version", "coordinator_attempt_id", "pre_execution_head", "pre_artifact_head", "pre_checkpoint_head",
                         "grant_payload", "budget_decision"}, "product_admission")
        prior = replay(rows[:record["event_index"] - 1]).projection.value
        index = loads(journal["previous_index"])
        decision = admission["budget_decision"]
        validate_budget_payload("decision_recorded", decision)
        diagnosis, = [value for identity, node, name, value in self.member_bindings if
                       (identity["case_id"], identity["run_id"], identity["attempt_id"]) == (*run, request["requesting_attempt_id"]) and
                       name == "decision_coordinator_diagnostic.json"]
        category = diagnosis["category"]
        check(diagnosis["confidence"] == "unique" and diagnosis["candidates"] == [payload["target_node"]] and
              not any(category == n or category.startswith((n + ".", n + "_")) for n in ("security", "policy", "data")) and
              not (category.startswith("scientific") and diagnosis["status"] != "success" and diagnosis["retryability"] != "retryable"),
              "product_grant_risk_science")
        trigger = {"method_planner": "replan", "code_agent": "code_fix", "analysis_engineer": "analysis_rerun", "scientific_reviewer": "re_review"}[payload["target_node"]]
        check(decision["proposal_id"] == digest({"source": admission["coordinator_attempt_id"], "target": payload["target_node"],
              "trigger": trigger, "stop_sequence_id": None}) and decision["proposed_action"] == "route" and
              decision["risk"] == diagnosis["risk"] and decision["reason_code"] == "canonical_route_admitted" and
              decision["next_control_action"] == "advance", "product_grant_preflight")
        check(admission["schema_version"] == "0.1" and admission["coordinator_attempt_id"] == capability["authorization"]["identity"]["attempt_id"] and
              admission["pre_execution_head"] == prior["execution_head"] and admission["pre_artifact_head"] == index["artifact_head"] and
              admission["pre_checkpoint_head"] == capability["authorization"]["heads"]["checkpoint_head"] and
              admission["grant_payload"] == payload and decision["decision"] == "allow" and decision["target_kind"] == payload["target_node"] and
              decision["budget_grant_id"] == payload["budget_grant_id"] and decision["fingerprint_digest"] == fp["fingerprint_digest"] and
              decision["occurrence"] == occurrence, "product_admission_binding")
        changes = {"cycles_per_run": int(payload["target_node"] == "method_planner"), "work_attempts_per_run": 1,
                   "control_attempts_per_run": 0, "transitions_per_run": 1, payload["route_dimension"]: 1}
        expected = {k: {**v, "projected_after": v["used"] + changes.get(k, 0)} for k, v in prior["budget"]["dimensions"].items()}
        check(decision["dimensions"] == expected and all(changes.get(k, 0) <= v["remaining"] for k, v in expected.items() if k != payload["route_dimension"]) and
              expected["control_attempts_per_run"]["remaining"] >= 5 and expected["transitions_per_run"]["remaining"] >= 7,
              "product_grant_ceiling_reserve")
        for field in ("pre_execution_head", "pre_artifact_head", "pre_checkpoint_head"):
            self.reference(admission_head, (field,), admission[field])
        self.reference(admission_head, ("grant_payload", "response_digest"), snapshot_head)
        self.reference(admission_head, ("grant_payload", "fingerprint_digest"), fp_head)
        self.reference(admission_head, ("budget_decision", "fingerprint_digest"), fp_head)
        return admission_head

    def finish_content(self, head, content, project_source):
        result = super().finish_content(head, content, project_source)
        if head not in self.product_declarations:
            return result
        declaration, evidence_head = self.product_declarations[head]
        refs = [[field, project_source(value)] for field, value in sorted(declaration.items()) if field.endswith("_head") and field not in
                ("failure_head", "grant_head")]
        return ["product_provenance", result, declaration["issuer"], declaration["capability_id"],
                declaration["producer_operation_id"], refs, project_source(evidence_head)]

    def encode(self, head, path, project_source):
        if head in self.derivation_heads and len(path) == 3 and path[0] == "context_bindings" and path[2] == "inputs":
            inputs = self.sources[head]["value"]["context_bindings"][path[1]]["inputs"]
            def bound(value, at):
                if at in self.refs[head]:
                    return ["digest_reference", project_source(self.refs[head][at])]
                if type(value) is dict:
                    return ["object", [[key, bound(value[key], (*at, key))] for key in sorted(value)]]
                if type(value) is list:
                    return ["array", [bound(child, (*at, i)) for i, child in enumerate(value)]]
                return ["literal", value]
            # Raw bindings already form a validated closed set. Their SHA sort
            # order is incidental; preserve every row after owner resolution.
            rows = [bound(value, (*path, i)) for i, value in enumerate(inputs)]
            return ["array", sorted(rows, key=canonical_bytes)]
        return super().encode(head, path, project_source)
