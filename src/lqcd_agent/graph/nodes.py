"""Deterministic mock nodes for the initial graph runtime."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from lqcd_agent.agents.analysis_engineer import run_analysis_engineer
from lqcd_agent.agents.decision_coordinator import run_decision_coordinator
from lqcd_agent.agents.method_planner import run_method_planner
from lqcd_agent.agents.scientific_reviewer import run_scientific_reviewer
from lqcd_agent.artifacts.registry import (
    prepare_attempt_output_dir,
    protect_current_artifact,
    register_artifact_bundle,
)
from lqcd_agent.coder.codex_handoff import ensure_task_packet, read_handoff_results
from lqcd_agent.coder.codex_handoff_worker import run_worker
from lqcd_agent.coder.task_packet import TaskPacketValidationError
from lqcd_agent.graph.approval_packet import (
    decision_route_target,
    parse_human_decision,
    write_approval_packet,
)
from lqcd_agent.graph.state import (
    AnalysisState,
    append_event,
    llm_context_view,
    record_human_request_packet,
    save_graph_state,
    validate_human_response,
)
from lqcd_agent.memory.store import write_memory_update
from lqcd_agent.report.generate_report import write_final_report
from lqcd_agent.tools.repo_inventory import build_repo_inventory


PRODUCT_FILES = {
    "method_planner": ("plan", "method_plan.json", "method_plan_path"),
    "analysis_engineer": ("analysis", "run_result.json", "run_result_path"),
    "scientific_reviewer": ("review", "scientific_review_report.json", "scientific_review_report_path"),
    "decision_coordinator": ("decision", "decision_log.json", "decision_log_path"),
}


def product_diagnostic(root, pointer):
    """Read diagnostics only from an immutable, registered domain member."""
    from hashlib import sha256
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import loads, require
    from lqcd_agent.agents.decision_coordinator import validate_product_diagnostic

    require(pointer is not None, "Product source has no registered domain outcome")
    if pointer["attempt_kind"] == "code_agent":
        from lqcd_agent.code_agent.artifacts import validate_code_result
        from lqcd_agent.code_agent.schemas import validate_task
        members = {member["logical_name"]: member for member in pointer["members"]}
        values = {}
        for name in ("code_agent_task.json", "code_agent_result.json"):
            member = members[name]
            raw = read_regular(Path(root) / member["canonical_path"])
            require(sha256(raw).hexdigest() == member["sha256"], "Code source digest changed")
            values[name] = raw
        task = validate_task(values["code_agent_task.json"]).value
        result = validate_code_result(values["code_agent_result.json"], task).value
        member = members["code_agent_result.json"]
        usable = result["status"] == "success" and result["usable"] is True
        return {"status": "success" if usable else "failed", "category": result["status"], "affected_layer": "code",
                "evidence": [{"artifact_id": pointer["artifact_id"], "member": member["canonical_path"], "sha256": member["sha256"]}],
                "retryability": "retryable" if result["status"] in ("failed", "no_change") else "not_retryable",
                "candidates": [] if usable else ["code_agent"], "confidence": "unique", "fingerprint": None,
                "human_need": None if usable else "approval", "risk": "low" if usable else "high"}
    name = pointer["attempt_kind"] + "_diagnostic.json"
    member = next((item for item in pointer["members"] if item["logical_name"] == name), None)
    require(member is not None, "Source lacks structured canonical diagnostics")
    raw = read_regular(Path(root) / member["canonical_path"])
    require(sha256(raw).hexdigest() == member["sha256"], "Diagnostic source digest changed")
    return validate_product_diagnostic(loads(raw))


def product_human_authorization(records, parent_attempt_id):
    """Derive work scope from a consumed snapshot, never its free text."""
    response = next((row for row in reversed(records) if row["record_type"] == "human_response" and
                     row["event"] == "consumed" and row["authorized_target_attempt_id"] == parent_attempt_id), None)
    if response is None:
        return None
    request = next(row for row in records if row["record_type"] == "human_request" and
                   row["human_request_id"] == response["human_request_id"] and row["event"] == "created")
    scope = request["authorization_scope"]
    target = "memory_report" if response["decision"] == "reject_or_hold" or scope.get("work_target") is None else scope["work_target"]
    return {"human_request_id": response["human_request_id"], "human_response_id": response["human_response_id"],
            "response_digest": response["payload_sha256"], "target_node": target}


def product_failure_material(root, source, diagnostic, records, coordinator):
    """Derive scientific inputs independently of execution identity."""
    from hashlib import sha256
    from lqcd_agent.control.budget import fingerprint, semantic_context
    from lqcd_agent.control.coordinator import read_regular
    from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, require

    root = Path(root)
    history = [loads(line) for line in read_regular(root / "artifact_history.jsonl").splitlines()]
    registrations = {row["artifact_id"]: row for row in history if row["event"] == "registered"}
    registration = registrations[source["artifact_id"]]
    scheduled = next(row for row in records if row["record_type"] == "attempt" and row["event"] == "scheduled"
                     and row["attempt_id"] == source["attempt_id"])
    call = next(row for row in records if row.get("event") == "resource_reserved" and
                row["payload"]["attempt_id"] == source["attempt_id"] and
                (row["payload"]["resource_kind"] == "code_backend_operation" if source["attempt_kind"] == "code_agent" else
                 row["payload"]["resource_operation_id"].endswith(":domain-diagnosis")))
    selected = {}
    for row in history:
        if row["event_index"] > call["artifact_event_index"]:
            break
        if row["event"] == "current_set":
            selected[row["slot"]] = registrations[row["artifact_id"]]
        elif row["event"] == "current_cleared":
            selected.pop(row["slot"], None)
    for slot, artifact in scheduled["input_references"]["current_artifact_ids"].items():
        selected.setdefault(slot, registrations[artifact])
    selected[source["slot"]] = registration
    config = {"node": source["attempt_kind"], "structured_output": True}
    if source["attempt_kind"] != "code_agent":
        require(call["payload"]["config_digest"] == digest(config), "Failure configuration changed")
    policy = next(row for row in records if row.get("event") == "policy_initialized")

    def input_ref(kind, head, member=None, registration_head=None, path=()):
        return {"kind": kind, "head": head, "registration_head": registration_head,
                "member": member, "path": list(path)}

    def binding(profile, inputs, projection, value, reason=None):
        raw = canonical_bytes(projection)
        unique_inputs = {canonical_bytes(item): item for item in inputs}
        return {"profile": profile, "inputs": [unique_inputs[key] for key in sorted(unique_inputs)],
                "projection": {"schema_version": "0.1", "profile": "failure_projection",
                               "sha256": sha256(raw).hexdigest(), "content": raw.decode()},
                "value": value, "not_applicable_reason": reason}

    metadata = {"schema_version", "case_id", "run_id", "attempt_id", "attempt_kind", "producer", "status"}
    leaves, inputs, plan_binding = [], [], None
    for name in ("input_snapshot.json", "root_goal.json"):
        raw = read_regular(root / name)
        value = loads(raw)
        leaves.append({"member_id": name, "content_digest": digest(value)})
        inputs.append(input_ref("root_input", sha256(raw).hexdigest(), name))
    main_names = {"plan": "method_plan.json", "analysis": "run_result.json", "review": "scientific_review_report.json"}
    for slot in main_names:
        if slot not in selected:
            continue
        row = selected[slot]
        pointer = row["pointer"]
        member = next(m for m in pointer["members"] if m["logical_name"] == main_names[slot])
        raw = read_regular(root / member["canonical_path"])
        require(sha256(raw).hexdigest() == member["sha256"], "Failure domain input changed")
        value = loads(raw)
        require(value["schema_version"] == "0.1" and value["producer"] == pointer["attempt_kind"] and
                all(value[k] == row[k] for k in ("case_id", "run_id")) and
                all(value[k] == pointer[k] for k in ("attempt_id", "attempt_kind")),
                "Failure domain owner changed")
        scientific = {k: v for k, v in value.items() if k not in metadata}
        ref = input_ref("member", member["sha256"], member["logical_name"], digest(row))
        leaves.append({"member_id": slot + "/" + member["logical_name"], "content_digest": digest(scientific)})
        inputs.append(ref)
        if slot == "plan":
            plan_binding = binding("domain_v1", [ref], scientific, digest(scientific))
    code_values, code_inputs, code_science, code_context, code_config = {}, [], None, None, None
    if "code" in selected:
        from lqcd_agent.code_agent.artifacts import validate_code_result
        from lqcd_agent.code_agent.schemas import POLICIES, validate_task, validate_manifest
        from lqcd_agent.code_agent.ingress import validate_change_manifest
        from lqcd_agent.code_agent.verification import build_verification_results

        code_registration = selected["code"]
        for member in code_registration["members"]:
            if member["logical_name"] not in ("code_agent_task.json", "code_agent_result.json", "workspace_manifest.json",
                                              "change_manifest.json", "verification_results.json"):
                continue
            raw = read_regular(root / member["canonical_path"])
            require(sha256(raw).hexdigest() == member["sha256"], "Code causal member changed")
            code_values[member["logical_name"]] = loads(raw)
            code_inputs.append(input_ref("member", member["sha256"], member["logical_name"], digest(code_registration)))
        task = validate_task(code_values["code_agent_task.json"]).value
        result = validate_code_result(code_values["code_agent_result.json"], task).value
        manifest = validate_manifest(code_values["workspace_manifest.json"], task).value
        changes = validate_change_manifest(code_values["change_manifest.json"], task, manifest).value
        verification = code_values["verification_results.json"]
        require(verification == build_verification_results(task, verification["spec_results"]), "Code verification source changed")
        code_science = {"base_revision": task["base_revision"], "base_tree_digest": task["base_tree_digest"],
                        "final_tree_digest": changes["final_tree_digest"], "changes": changes["changes"], "patch_digest": result["patch_digest"]}
        change_science = {k: code_science[k] for k in ("base_tree_digest", "final_tree_digest", "changes")}

        def prior_code_science(prior):
            from lqcd_agent.control.operations import ExternalControl

            transition = next(r for r in records if r.get("record_type") == "transition" and
                              r["transition_id"] == task["transition_id"])
            parent = coordinator.snapshot(task["external_producer_contract"]["parent_control_operation_id"])
            require(task["task_origin"] == "coordinator_code_fix" and
                    (prior["case_id"], prior["run_id"]) == (task["case_id"], task["run_id"]) and
                    prior["event_index"] <= transition["artifact_event_index"] and
                    parent["original_index"]["current"]["code"] == prior["pointer"] and
                    transition["source_attempt_id"] == task["source_attempt_id"] and
                    transition["target_attempt_id"] == task["attempt_id"], "Historical Code evidence source changed")
            decision_source = next(r for r in registrations.values() if r["slot"] == "decision" and
                                   r["attempt_id"] == task["source_attempt_id"])
            decision_member = next(m for m in decision_source["members"] if m["logical_name"] == "decision_log.json")
            decision_raw = read_regular(root / decision_member["canonical_path"])
            require(sha256(decision_raw).hexdigest() == decision_member["sha256"], "Code remediation bytes changed")
            packet = loads(decision_raw)["remediation"]
            require(packet["target_node"] == "code_agent" and packet["parent_attempt_id"] == task["source_attempt_id"] and
                    {"artifact_id": evidence["artifact_id"], "member": evidence["path"], "sha256": evidence["sha256"]}
                    in packet["evidence"], "Historical Code is outside its original packet")
            prior_values = {}
            for name in ("code_agent_task.json", "code_agent_result.json", "workspace_manifest.json",
                         "change_manifest.json", "verification_results.json"):
                member = next(m for m in prior["members"] if m["logical_name"] == name)
                raw = read_regular(root / member["canonical_path"])
                require(sha256(raw).hexdigest() == member["sha256"] and len(raw) == member["size_bytes"],
                        "Historical Code member changed")
                prior_values[name] = loads(raw)
                code_inputs.append(input_ref("member", member["sha256"], name, digest(prior)))
            prior_task = validate_task(prior_values["code_agent_task.json"]).value
            prior_result = validate_code_result(prior_values["code_agent_result.json"], prior_task).value
            prior_manifest = validate_manifest(prior_values["workspace_manifest.json"], prior_task).value
            prior_changes = validate_change_manifest(prior_values["change_manifest.json"], prior_task, prior_manifest).value
            prior_verification = prior_values["verification_results.json"]
            require(prior_verification == build_verification_results(prior_task, prior_verification["spec_results"]),
                    "Historical Code verification changed")
            external = ExternalControl(coordinator)
            producer = external.read(coordinator.connection, prior_task["producer_operation_id"])
            release = producer["consumption_release"]
            require(producer["proof_kind"] == "safe_stop" and producer["active_binding_status"] == "released" and
                    release is not None and producer["run_locator"] == {k: task[k] for k in ("case_id", "run_id")} and
                    producer["attempt_id"] == prior["attempt_id"] == prior_task["attempt_id"] and
                    producer["task_digest"] == prior_task["task_digest"] and
                    producer["workspace_manifest_digest"] == prior_manifest["manifest_digest"],
                    "Historical Code producer or safe consumption changed")
            require(coordinator.get(release["consumption_operation_id"])["status"] == "committed" and
                    external.detached(coordinator.connection, producer), "Historical Code consumption proof changed")
            finished = next(r for r in records if r.get("record_type") == "attempt" and r["event"] == "finished" and
                            r["attempt_id"] == prior_task["attempt_id"])
            require(finished["output_references"]["current_artifact_ids"]["code"] == prior["artifact_id"] and
                    finished["event_index"] < transition["event_index"], "Historical Code registration is not consumed")
            final_raw = read_regular(root / producer["terminal_evidence_reference"])
            require(sha256(final_raw).hexdigest() == producer["terminal_evidence_digest"], "Historical Code final changed")
            code_inputs.append(input_ref("typed_source", producer["terminal_evidence_digest"]))
            return {"base_revision": prior_task["base_revision"], "base_tree_digest": prior_task["base_tree_digest"],
                    "final_tree_digest": prior_changes["final_tree_digest"], "changes": prior_changes["changes"],
                    "patch_digest": prior_result["patch_digest"]}

        evidence_digests = []
        for evidence in task["evidence"]:
            evidence_registration = registrations[evidence["artifact_id"]]
            evidence_member = next(m for m in evidence_registration["members"] if m["canonical_path"] == evidence["path"])
            require(evidence_member["sha256"] == evidence["sha256"], "Code evidence owner changed")
            slot = evidence_registration["slot"]
            if slot == "code":
                require(evidence_member["logical_name"] == "code_agent_result.json", "Code evidence is not its canonical result")
                science = prior_code_science(evidence_registration)
            else:
                require(slot in main_names and evidence_member["logical_name"] == main_names[slot], "Code evidence lacks a scientific profile")
                raw = read_regular(root / evidence_member["canonical_path"])
                require(sha256(raw).hexdigest() == evidence_member["sha256"], "Code evidence bytes changed")
                science = {k: v for k, v in loads(raw).items() if k not in metadata}
            evidence_digests.append(digest(science))
            code_inputs.append(input_ref("member", evidence_member["sha256"], evidence_member["logical_name"], digest(evidence_registration)))
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
    leaves.sort(key=lambda row: row["member_id"])
    scheduled_ref = input_ref("execution_record", digest(scheduled), path=("attempt_kind",))
    call_ref = input_ref("ordinary_call", digest(call), path=("config",))
    bindings = {
        "program_ids": binding("host_ids_v1", [scheduled_ref], [source["attempt_kind"]], [source["attempt_kind"]]),
        "tool_ids": binding("host_ids_v1", [call_ref], ["domain-diagnosis"], ["domain-diagnosis"]),
        "verification_ids": binding("host_ids_v1", [scheduled_ref], [], []),
        "input_members": binding("input_members_v1", inputs, leaves, leaves),
        "plan_digest": plan_binding or binding("not_applicable_v1", [], None, None, "no_plan"),
        "code_digest": binding("not_applicable_v1", [], None, None, "no_code"),
        "base_revision": binding("not_applicable_v1", [], None, None, "no_immutable_base"),
        "base_tree_digest": binding("not_applicable_v1", [], None, None, "no_immutable_base"),
        "config_digest": binding("host_config_v1", [call_ref], config, digest(config)),
        "policy_digest": binding("policy_v1", [input_ref("execution_record", digest(policy), path=("payload", "policy"))],
                                 policy["payload"]["policy"], policy["payload"]["policy"]["policy_digest"]),
        "code_task_context_digest": binding("not_applicable_v1", [], None, None, "no_code"),
        "analysis_execution_context_digest": binding("not_applicable_v1", [], None, None, "no_fresh_analysis"),
    }
    if code_science is not None:
        task_input = next(r for r in code_inputs if r["member"] == "code_agent_task.json")
        bindings["code_digest"] = binding("code_causal_v1", code_inputs, code_science, digest(code_science))
        bindings["code_task_context_digest"] = binding("code_causal_v1", code_inputs, code_context, semantic_context("code", code_context))
        bindings["base_revision"] = binding("host_ids_v1", [task_input], task["base_revision"], task["base_revision"])
        bindings["base_tree_digest"] = binding("host_ids_v1", [task_input], task["base_tree_digest"], task["base_tree_digest"])
        bindings["verification_ids"] = binding("host_ids_v1", [task_input], sorted(spec["spec_id"] for spec in task["verification_specs"]),
                                              sorted(spec["spec_id"] for spec in task["verification_specs"]))
        if source["attempt_kind"] == "code_agent":
            bindings["tool_ids"] = binding("host_ids_v1", [task_input], sorted(spec["spec_id"] for spec in task["tool_policy"]),
                                          sorted(spec["spec_id"] for spec in task["tool_policy"]))
            bindings["config_digest"] = binding("host_config_v1", [task_input], code_config, digest(code_config))
    analysis_spec = None
    if code_science is not None and "analysis" in selected:
        from lqcd_agent.control.operations import validate_target_preparation
        from lqcd_agent.code_agent.analysis_handoff import SPEC_FIELDS
        from lqcd_agent.control.strict_json import closed
        import sys

        analysis_registration = selected["analysis"]
        analysis_owner = {**{k: analysis_registration[k] for k in ("case_id", "run_id")},
                          **{k: analysis_registration["pointer"][k] for k in ("attempt_id", "attempt_kind")}}
        analysis_scheduled = next(row for row in records if row["record_type"] == "attempt" and row["event"] == "scheduled" and
                                  row["attempt_id"] == analysis_owner["attempt_id"])
        source_capability, = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM invocation_capabilities")
                             if loads(row[0])["authorization"]["identity"] ==
                             analysis_owner]
        preparation = source_capability["authorization"]["target_preparation"]
        validate_target_preparation(preparation, {k: analysis_registration[k] for k in ("case_id", "run_id")}, "analysis_engineer",
                                    analysis_owner["attempt_id"], analysis_scheduled["inbound_transition_id"], selected["code"]["pointer"])
        require(preparation["preparation_kind"] == "analysis_fresh", "Code Analysis lacks its actual fresh specification")
        analysis_spec = loads(preparation["canonical_spec_bytes"])
        closed(analysis_spec, SPEC_FIELDS)
        runtime = {"python": sys.version, "executable": sys.executable}
        require(analysis_spec["analysis_runtime_fingerprint"] == digest(runtime), "Analysis causal runtime changed")
        analysis_config = {"runtime": runtime, "environment": analysis_spec["environment_policy"],
                           "command": analysis_spec["allowed_command"], "outputs": analysis_spec["expected_outputs"]}
        require(digest(analysis_config) == preparation["runtime_policy_digest"], "Analysis configuration source changed")
        tool_call, = [row for row in records if row.get("event") == "resource_reserved" and
                      row["payload"]["attempt_id"] == analysis_owner["attempt_id"] and
                      row["payload"]["resource_operation_id"].endswith(":analysis-subprocess")]
        require(tool_call["payload"]["input_digest"] == digest(preparation) and
                tool_call["payload"]["config_digest"] == digest(analysis_config), "Analysis causal call changed")
        spec_input = input_ref("typed_source", digest(analysis_spec))
        selected_leaves = []
        for slot, selected_input in analysis_spec["selected_input_artifacts"].items():
            require(slot in selected and selected_input == {"artifact_id": selected[slot]["artifact_id"], "digest": digest(selected[slot]["pointer"])},
                    "Analysis selected scientific input changed")
            selected_leaves.extend(leaf["content_digest"] for leaf in leaves if leaf["member_id"].startswith(slot + "/"))
        analysis_context = {"verified_change_digest": digest(change_science), "effective_tree_digest": changes["final_tree_digest"],
            "base_revision": task["base_revision"], "base_tree_digest": task["base_tree_digest"],
            "input_code_digest": digest(code_science), "input_artifact_digests": sorted(set(selected_leaves)),
            "runtime_digest": digest(analysis_config), "policy_digest": policy["payload"]["policy"]["policy_digest"]}
        bindings["analysis_execution_context_digest"] = binding("analysis_causal_v1", code_inputs + inputs + [spec_input],
                                                               analysis_context, semantic_context("analysis", analysis_context))
        scientific_config = {"agent": config, "code": code_config, "analysis": analysis_config}
        bindings["config_digest"] = binding("host_config_v1", [call_ref, task_input, spec_input], scientific_config, digest(scientific_config))
    category = diagnostic["category"]
    layer = next((name for name in ("security", "policy", "data", "scientific", "provider", "verification", "tool")
                  if category == name or category.startswith((name + ".", name + "_"))),
                 "tool" if category == "analysis_execution" else "control")
    diagnostics = {"exit_code": None, "signal": None, "failing_test_ids": [], "validator_errors": []}
    failure_class, code = diagnostic["status"], category
    if analysis_spec is not None:
        main = next(m for m in analysis_registration["members"] if m["logical_name"] == "run_result.json")
        actual_return = loads(read_regular(root / main["canonical_path"]))["execution"]
        diagnostics["exit_code"] = actual_return["returncode"]
    if source["attempt_kind"] == "code_agent":
        failure_class, code = result["failure_class"], result["status"]
        layer = {"scope_violation": "security", "policy_violation": "policy", "verification_failed": "verification",
                 "tool_error": "tool", "timeout": "control", "external_interruption": "control"}.get(failure_class, "code")
        diagnostics["failing_test_ids"] = sorted(r["spec_id"] for r in verification["spec_results"] if r["status"] == "failed")
    derivation = {"schema_version": "0.1", "layer": layer, "failure_class": failure_class,
                  "code": code, "diagnostics": diagnostics, "context_bindings": bindings}
    fp = fingerprint(layer=layer, failure_class=failure_class, code=code,
                     context={k: v["value"] for k, v in bindings.items()}, diagnostics=diagnostics).value
    return fp, derivation, registration


def product_observe_failure(root, source, diagnostic, port, records):
    """Publish one occurrence for new Work, never for a Human continuation."""
    from lqcd_agent.control.strict_json import digest

    fp, derivation, registration = product_failure_material(root, source, diagnostic, records, port.leases.coordinator)
    occurrence = 1 + sum(row["payload"]["fingerprint"]["fingerprint_digest"] == fp["fingerprint_digest"]
                         for row in records if row.get("event") == "failure_observed")
    failure = port.append_budget("failure_observed", {"fingerprint": fp, "occurrence": occurrence})
    return failure


def product_issue_grant(root, identity, diagnostic, authorization, port, records, state, sequence):
    """Issue a validated budget window only in its started Coordinator."""
    from lqcd_agent.control.capabilities import invocation_prefix
    from lqcd_agent.control.strict_json import digest, loads, require
    from lqcd_agent.graph.routing import PRODUCT_FALLBACKS, select_product_route
    from lqcd_agent.graph.state import stable_attempt_id, stable_transition_id

    if authorization is None:
        return None
    response = next(row for row in records if row.get("record_type") == "human_response" and row["event"] == "consumed"
                    and row["human_response_id"] == authorization["human_response_id"])
    if response["decision"] != "approve_budget_window":
        return None
    require(sequence is None, "Terminal reserve cannot issue a budget window")
    require(response["authorized_target_attempt_id"] == identity["attempt_id"] and response["cycle_id"] == state["cycle_id"],
            "Budget response does not authorize this Coordinator")
    prior = [row for row in records if row.get("event") == "grant_issued" and
             row["payload"]["human_response_id"] == response["human_response_id"]]
    require(len(prior) <= 1, "Budget response has duplicate grants")
    if prior:
        return prior[0]
    request = next(row for row in records if row.get("record_type") == "human_request" and row["event"] == "created"
                   and row["human_request_id"] == response["human_request_id"])
    scope = request["authorization_scope"]
    target = authorization["target_node"]
    require(target in PRODUCT_FALLBACKS and scope.get("work_target") == target and
            "approve_budget_window" in scope["allowed_decisions"] and
            scope.get("failure_fingerprint") is not None and scope["failure_fingerprint"] == state["budget"]["active_failure"],
            "Budget window does not match the exact Work failure")
    category = diagnostic["category"]
    require(not any(category == name or category.startswith((name + ".", name + "_")) for name in ("security", "policy", "data")),
            "Budget window cannot override a hard safety gate")
    require(not (category.startswith("scientific") and diagnostic["status"] != "success" and
                 diagnostic["retryability"] != "retryable"), "Budget window cannot override scientific acceptance")
    require(diagnostic["confidence"] == "unique" and diagnostic["candidates"] == [target], "Budget target is ambiguous")
    pause = next(row for row in records if row.get("event") == "pause_consumed" and
                 row["input_contract"].get("human_request_id") == request["human_request_id"])
    operation = port.leases.coordinator.get(pause["operation_id"])
    resume = operation["request"]
    actor = resume["actor"]
    snapshot = response["payload_sha256"]
    require(operation["operation_type"] == "resume_run" and operation["status"] == "committed" and
            operation["request_digest"] == pause["proof"]["request_digest"] and
            resume["input_kind"] == "human_response" and resume["pause_id"] == pause["pause_id"] and
            resume["input_digest"] == snapshot and digest(resume["input_snapshot"]) == snapshot and
            pause["proof"]["actor"] == actor and actor["actor_type"] == pause["authorization_scope"]["actor_type"] and
            set(pause["authorization_scope"]["scopes"]) <= set(actor["scopes"]) and
            resume["input_snapshot"]["decided_by"] == actor["actor_id"], "Budget actor or protected response mismatch")
    failure = state["budget"]["active_failure"]
    position = state["budget"]["budget_grant_index"] + 1
    grant = {"budget_grant_id": f"budget_grant_{position:06d}", "budget_grant_index": position,
        "cycle_id": response["cycle_id"], "human_request_id": request["human_request_id"],
        "human_response_id": response["human_response_id"], "pause_id": pause["pause_id"],
        "response_reference": response["payload_reference"], "response_digest": snapshot,
        "route_dimension": PRODUCT_FALLBACKS[target][1], "fingerprint_digest": failure["fingerprint_digest"],
        "occurrence": failure["occurrence"], "target_attempt_id": stable_attempt_id(state["attempt_index"] + 1),
        "target_attempt_kind": target, "target_node": target, "transition_id": stable_transition_id(state["transition_index"] + 1),
        "additional_opportunities": 1, "actor_scope": ["approve_budget_window"]}
    view = {"source": {"node_name": "decision_coordinator", "attempt_id": identity["attempt_id"],
                       "status": "succeeded" if diagnostic["status"] == "success" else "failed"}, "state": state}
    selected = select_product_route(view, diagnostic, human_authorization=authorization, proposed_grant=grant)
    require(selected["target_node"] == target and selected["budget_decision"]["decision"] == "allow" and
            selected["stop_sequence_id"] is None, "Budget window failed its full route preflight")
    port.leases.require_effect_authority(port.capability_id, port.worker, port.epoch)
    _, capability = port.leases.get(port.capability_id)
    prefix = invocation_prefix(capability)
    index = loads(prefix["index"])
    admission = {"schema_version": "0.1", "coordinator_attempt_id": identity["attempt_id"],
                 "pre_execution_head": state["execution_head"], "pre_artifact_head": index["artifact_head"],
                 "pre_checkpoint_head": capability["authorization"]["heads"]["checkpoint_head"], "grant_payload": grant,
                 "budget_decision": selected["budget_decision"]}
    issued = port.append_budget("grant_issued", grant)
    return issued


class ProductResourceFailure(RuntimeError):
    """An ended ordinary call whose original reservation retained its maximum."""


def product_resource(port, **request):
    """Keep conservative product settlement separate from the resource primitive."""
    from lqcd_agent.control.budget import BudgetExhausted, usage
    from lqcd_agent.control.capabilities import invocation_prefix
    from lqcd_agent.control.execution import parse_ledger
    from lqcd_agent.control.strict_json import digest

    effect = request.pop("effect")
    ended, callee_error = False, None

    def call():
        nonlocal ended, callee_error
        try:
            result = effect()
        except Exception as error:
            callee_error = error
            ended = True
            raise
        ended = True
        return result

    try:
        return port.run_resource(**request, effect=call)
    except BudgetExhausted:
        raise
    except Exception as error:
        if not ended:
            raise
        _, value = port.leases.get(port.capability_id)
        resource = port.capability_id + ":" + request["resource_id"]
        reservations = [r for r in parse_ledger(invocation_prefix(value)["content"].encode()).values
                        if r.get("event") == "resource_reserved" and r["payload"]["resource_operation_id"] == resource]
        frozen_settlements = [entry for entry in value.get("budget_intents", [])
                              if entry["record"].get("event") == "resource_settled" and
                              entry["record"]["payload"]["resource_operation_id"] == resource]
        if len(reservations) != 1 or frozen_settlements:
            raise
        evidence = {"type": type(error).__name__, "message": str(error)}
        if callee_error is not None:
            evidence = {"schema_version": "0.1", "resource_operation_id": resource,
                        "exception": {"type": type(callee_error).__name__, "message": str(callee_error)}}
        producer = port.leases.coordinator.get(value["authorization"]["producer_operation_id"])
        port.append_budget("resource_settled", {"resource_operation_id": resource, "actual": None,
            "tokens": usage(), "cost": usage(), "evidence_digest": digest(evidence),
            **{key: producer[key] for key in ("operation_id", "lease_epoch", "phase_revision")}})
        raise ProductResourceFailure(str(error) or type(error).__name__) from error


class ProductNode:
    """Host wrapper; the Agent receives only context and returns domain facts."""

    def __init__(self, root, agent_port, *, analysis_handoff=None, preparation=None):
        self.root, self.agent_port = Path(root), agent_port
        self.analysis_handoff, self.preparation = analysis_handoff, preparation

    def invoke_scoped(self, identity, port):
        from hashlib import sha256
        from lqcd_agent.agents.decision_coordinator import product_coordinator_diagnosis, validate_product_diagnostic
        from lqcd_agent.artifacts.registry import SLOT_BY_ATTEMPT_KIND
        from lqcd_agent.control.budget import BudgetExhausted
        from lqcd_agent.control.capabilities import ArtifactOutput, HumanResponseVerdict, TargetOutcome
        from lqcd_agent.control.coordinator import read_regular
        from lqcd_agent.control.execution import parse_ledger
        from lqcd_agent.control.strict_json import canonical_bytes, closed, digest, loads, require
        from lqcd_agent.graph.routing import select_product_route
        from lqcd_agent.graph.state import product_context

        node = identity["attempt_kind"]
        context = product_context(self.root, identity)
        records = parse_ledger(read_regular(self.root / "execution_history.jsonl")).values
        state = parse_ledger(read_regular(self.root / "execution_history.jsonl")).projection.value
        index = loads(read_regular(self.root / "artifact_index.json"))
        refs = {slot: pointer["artifact_id"] for slot, pointer in index["current"].items() if pointer is not None}
        refs[SLOT_BY_ATTEMPT_KIND[node]] = identity["attempt_id"] + ":" + SLOT_BY_ATTEMPT_KIND[node]
        if node == "human_gate":
            response = next((row for row in reversed(records) if row["record_type"] == "human_response" and
                             row["human_request_id"] == state["active_human_request_id"]), None)
            if response is not None and response["status"] == "submitted":
                payload = loads(read_regular(self.root / response["payload_reference"]))
                request = next(row for row in records if row["record_type"] == "human_request" and
                               row["human_request_id"] == response["human_request_id"] and row["event"] == "created")
                valid = payload["decision"] in request["authorization_scope"]["allowed_decisions"]
                from lqcd_agent.graph.routing import product_budget_decision
                inbound = next(r for r in records if r["record_type"] == "transition" and r["target_attempt_id"] == identity["attempt_id"])
                decision = product_budget_decision(state, target="decision_coordinator", trigger="human_response", risk="low",
                    stop_sequence_id=inbound["fields"].get("stop_sequence_id"))
                return TargetOutcome("succeeded" if valid else "failed", {"current_artifact_ids": {
                    slot: pointer["artifact_id"] for slot, pointer in index["current"].items()
                    if pointer is not None and slot != "approval"}},
                    human_response_verdict=HumanResponseVerdict(valid, None if valid else "Decision is outside frozen scope"),
                    terminal_decision=decision if valid and decision["decision"] == "halt" else None)
            request = next(row for row in reversed(records) if row["record_type"] == "human_request")
            path = port.write_member("approval_packet/request.json", canonical_bytes(request))
            return TargetOutcome("pending", {"current_artifact_ids": refs}, human_request_packet=str(path),
                artifact=ArtifactOutput("approval", (path,), {"approval_packet_dir": str(path.parent), "human_decision_path": None}, "pending"))
        if node == "memory_report":
            from lqcd_agent.memory.store import classify_memory_update
            inbound = next(r for r in records if r["record_type"] == "transition" and r["target_attempt_id"] == identity["attempt_id"])
            decision = product_diagnostic(self.root, index["current"]["decision"])
            response = next((row for row in reversed(records) if row["record_type"] == "human_response" and row["status"] == "consumed"), None)
            classification = classify_memory_update({"human_response_status": "consumed" if response else None,
                "human_response_decision": response["decision"] if response else None, "risk_level": decision["risk"],
                "recommended_action": "accept_mock_result" if decision["status"] == "success" and not decision["candidates"] else "hold",
                "human_approval_required": decision["risk"] in ("high", "critical")})
            if classification["accepted_result"] and any(index["current"][slot] is None or
                    index["current"][slot]["status"] != "success" for slot in ("analysis", "review")):
                classification.update(memory_status="pending", accepted_result=False,
                    classification_reason="Scientific acceptance requires successful current Analysis and Reviewer evidence.")
            if inbound["fields"].get("stop_sequence_id") is not None:
                classification.update(memory_status="pending", accepted_result=False, classification_reason="Deterministic budget stop.")
            payload = {"schema_version": "0.1", **identity, "producer": node, "status": classification["memory_status"],
                       **classification, "evidence": context["current_evidence"]}
            memory = port.write_member("memory_update.json", canonical_bytes(payload))
            report = port.write_member("final_report.md", ("# Canonical analysis report\n\n"
                + "Domain result: " + classification["memory_status"] + "\n\n"
                + "\n".join("- " + item["member"] for item in context["current_evidence"]) + "\n").encode())
            terminal_decision = None
            if inbound["fields"].get("stop_sequence_id") is not None:
                from lqcd_agent.graph.routing import product_budget_decision
                terminal_decision = product_budget_decision(state, target=None, trigger="budget_stop", risk=decision["risk"],
                    stop_sequence_id=inbound["fields"]["stop_sequence_id"])
                terminal_decision.update(decision="halt", reason_code="terminal_budget_stop", next_control_action="close_run")
                terminal_decision["decision_digest"] = digest({k: v for k, v in terminal_decision.items() if k != "decision_digest"})
            return TargetOutcome("succeeded", {"current_artifact_ids": refs}, artifact=ArtifactOutput("terminal", (memory, report),
                {"memory_update_path": str(memory), "final_report_path": str(report)}, classification["memory_status"]), terminal_decision=terminal_decision)
        require(node in PRODUCT_FILES, "Code executes through its original external owner")
        if node == "decision_coordinator":
            parent = context["direct_parent_attempt_id"]
            registered = [loads(line)["pointer"] for line in read_regular(self.root / "artifact_history.jsonl").splitlines()
                          if loads(line)["event"] == "registered"]
            source = next((pointer for pointer in reversed(registered) if pointer["attempt_id"] == parent), None)
            if source is not None and source["attempt_kind"] == "human_gate":
                request = next(row for row in reversed(records) if row["record_type"] == "human_request")
                source = next(pointer for pointer in reversed(registered) if pointer["attempt_id"] == request["requesting_attempt_id"])
            elif source is None:
                request = next(row for row in reversed(records) if row["record_type"] == "human_request")
                source = next(pointer for pointer in reversed(registered) if pointer["attempt_id"] == request["requesting_attempt_id"])
            previous = product_diagnostic(self.root, source)
            floor = "critical" if previous["affected_layer"] == "plan" and previous["status"] != "success" else "high" if previous["status"] == "failed" or previous["candidates"] in (["analysis_engineer"], ["code_agent"]) else previous["risk"]
            diagnostic = product_coordinator_diagnosis([previous], local_risk_floor=floor)
            content = {"reasons": [diagnostic["category"]], "evidence": diagnostic["evidence"], "risk_level": diagnostic["risk"]}
        else:
            def effect():
                return self.agent_port.run(node, context, timeout_seconds=1)
            try:
                outcome = product_resource(port, resource_kind="llm_call", resource_id="domain-diagnosis", input_digest=digest(context),
                    config_digest=digest({"node": node, "structured_output": True}), timeout_seconds=1, effect=effect)
                closed(outcome, ("diagnostic", "content"))
                require(type(outcome["content"]) is dict and type(outcome["diagnostic"]) is dict, "Unstructured Agent output")
                diagnostic, content = outcome["diagnostic"], outcome["content"]
                reserved = {"schema_version", "producer", "status", "case_id", "run_id", "cycle_id", "attempt_id",
                            "attempt_kind", "node_name", "transition_id", "parent_attempt_id"} | set(identity)
                require(not (reserved & content.keys()), "Agent content includes reserved Host fields")
                require(diagnostic.get("fingerprint") is None, "Agent cannot assign a failure fingerprint")
            except ProductResourceFailure as error:
                index = loads(read_regular(self.root / "artifact_index.json"))
                current = {slot: pointer["artifact_id"] for slot, pointer in index["current"].items() if pointer is not None}
                return TargetOutcome("failed", {"current_artifact_ids": current},
                    {"type": "OrdinaryResourceFailure", "message": str(error)})
            except BudgetExhausted:
                diagnostic = {"status": "failed", "category": "budget", "affected_layer": "none", "evidence": [],
                    "retryability": "not_retryable", "candidates": [], "confidence": "unique", "fingerprint": None,
                    "human_need": "approval", "risk": "high"}
                content = {"resource_admission": "denied"}
            if node == "analysis_engineer" and index["current"]["code"] is not None:
                require(self.analysis_handoff is not None and self.preparation is not None, "Verified Code requires a fresh Analysis preparation")
                try:
                    content["execution"] = product_resource(port, resource_kind="tool_call", resource_id="analysis-subprocess",
                        input_digest=digest(self.preparation), config_digest=self.preparation["runtime_policy_digest"], timeout_seconds=10,
                        effect=lambda: self.analysis_handoff.execute(self.preparation))
                except ProductResourceFailure as error:
                    current = {slot: pointer["artifact_id"] for slot, pointer in index["current"].items() if pointer is not None}
                    return TargetOutcome("failed", {"current_artifact_ids": current},
                        {"type": "OrdinaryResourceFailure", "message": str(error)})
                if content["execution"]["returncode"] != 0:
                    diagnostic.update(status="failed", category="analysis_execution", affected_layer="analysis", candidates=["analysis_engineer"], risk="high")
        state = parse_ledger(read_regular(self.root / "execution_history.jsonl")).projection.value
        inbound = next(row for row in reversed(records) if row["record_type"] == "transition" and
                       row["target_attempt_id"] == identity["attempt_id"])
        sequence = inbound["fields"].get("stop_sequence_id")
        authorization = product_human_authorization(records, identity["attempt_id"]) if node == "decision_coordinator" else None
        view = {"source": {"node_name": node, "attempt_id": identity["attempt_id"],
                            "status": "succeeded" if diagnostic["status"] == "success" else "failed"}, "state": state}
        selection = None
        if node == "decision_coordinator":
            if authorization is None and sequence is None and (previous["status"] != "success" or previous["candidates"]):
                product_observe_failure(self.root, source, previous, port, records)
                records = parse_ledger(read_regular(self.root / "execution_history.jsonl")).values
                state = parse_ledger(read_regular(self.root / "execution_history.jsonl")).projection.value
                view["state"] = state
            issued = product_issue_grant(self.root, identity, diagnostic, authorization, port, records, state, sequence)
            if issued is not None:
                records = parse_ledger(read_regular(self.root / "execution_history.jsonl")).values
                state = parse_ledger(read_regular(self.root / "execution_history.jsonl")).projection.value
                view["state"] = state
            selection = select_product_route(view, diagnostic, human_authorization=authorization, stop_sequence_id=sequence)
            target = selection["target_node"]
            content["human_authorization"] = authorization
            content["remediation"] = None if target not in ("method_planner", "code_agent", "analysis_engineer", "scientific_reviewer") else {
                "target_node": target, "problem": diagnostic["category"], "evidence": diagnostic["evidence"],
                "constraints": ["Preserve the approved scientific method, immutable inputs and path policy."],
                "success_criteria": ["Resolve the diagnosed issue and provide attributable structured evidence."],
                "parent_attempt_id": identity["attempt_id"], "budget_policy_digest": state["budget"]["policy_digest"],
                "human_authorization": authorization}
        slot, filename, field = PRODUCT_FILES[node]
        path = port.write_member(filename, canonical_bytes({"schema_version": "0.1", **identity, "producer": node,
                                                          "status": diagnostic["status"], **content}))
        reference = {"artifact_id": refs[slot], "member": str(path.relative_to(self.root)), "sha256": sha256(read_regular(path)).hexdigest()}
        if not diagnostic.get("evidence"):
            diagnostic["evidence"] = [reference]
        else:
            allowed = context["current_evidence"] + [reference]
            require(all(item in allowed for item in diagnostic["evidence"]), "Agent evidence exceeds scoped context")
        diagnostic = validate_product_diagnostic(diagnostic)
        members = [path]
        state_paths = {field: str(path)}
        if node == "method_planner":
            require(type(content.get("code_needed")) is bool, "Planner requires a typed code-needed result")
            state_paths["coder_task_packet_path"] = None
        if node == "analysis_engineer":
            output = port.write_member("analysis_outputs/result.json", canonical_bytes(content))
            members.append(output)
            state_paths["analysis_outputs_dir"] = str(output.parent)
        diagnostic_path = port.write_member(node + "_diagnostic.json", canonical_bytes(diagnostic))
        members.append(diagnostic_path)
        if selection is None:
            selection = select_product_route(view, diagnostic, code_needed=content.get("code_needed", False), stop_sequence_id=sequence)
        return TargetOutcome("succeeded" if diagnostic["status"] == "success" else "failed", {"current_artifact_ids": refs},
            artifact=ArtifactOutput(slot, tuple(members), state_paths, diagnostic["status"]),
            terminal_decision=selection["budget_decision"] if selection["budget_decision"]["decision"] == "halt" else None)


def _read_case_config(path: str) -> dict[str, Any] | None:
    case_path = Path(path)
    if not case_path.exists():
        return None

    if case_path.suffix == ".json":
        return json.loads(case_path.read_text(encoding="utf-8"))

    result: dict[str, Any] = {}
    for raw_line in case_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        if value and not value.startswith("["):
            result[key.strip()] = value
    return result


def method_planner_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "method_planner"
    state["status"] = "running"
    llm_context_view(state)
    current_plan = state.get("current_artifacts", {}).get("plan")
    if isinstance(current_plan, dict) and state.get("method_plan_path"):
        method_plan = json.loads(Path(state["method_plan_path"]).read_text(encoding="utf-8"))
        state["code_needed"] = bool(method_plan.get("code_needed"))
        if method_plan.get("status") == "needs_more_info":
            state["status"] = "pending"
        elif method_plan.get("status") != "success":
            state["status"] = "halted"
        append_event(
            state,
            node="method_planner",
            kind="current_artifact_reused",
            summary="Reused the current immutable Planner bundle for legacy handoff continuation.",
            artifact_id=current_plan["artifact_id"],
        )
        save_graph_state(state)
        return state
    artifact_dir = prepare_attempt_output_dir(state)
    repo_root = Path(__file__).resolve().parents[3]
    result = run_method_planner(
        user_goal=state["user_goal"],
        case_config=_read_case_config(state["case_config_path"]),
        repo_inventory=build_repo_inventory(repo_root),
        output_dir=artifact_dir,
        run_id=state["run_id"],
        provider_config_path=state["llm_provider_config_path"],
    )
    method_plan = result["method_plan"]
    state["code_needed"] = result["code_needed"]

    if result["status"] == "needs_more_info":
        state["status"] = "pending"
        state["errors"].extend(
            {
                "node": "method_planner",
                "field": error.get("field"),
                "message": error.get("message"),
                "method_plan_path": result["method_plan_path"],
            }
            for error in method_plan.get("errors", [])
        )
        append_event(
            state,
            node="method_planner",
            kind="node_pending",
            summary="Method planner needs more information before analysis can run.",
        )
    elif result["status"] != "success":
        state["status"] = "halted"
        state["errors"].extend(
            {
                "node": "method_planner",
                "field": error.get("field"),
                "message": error.get("message"),
                "method_plan_path": result["method_plan_path"],
            }
            for error in method_plan.get("errors", [])
        )
        append_event(
            state,
            node="method_planner",
            kind="node_halted",
            summary="Method planner failed validation before analysis could run.",
        )
    elif state["code_needed"]:
        state["status"] = "running"
        append_event(
            state,
            node="method_planner",
            kind="node_complete",
            summary="Method planner wrote a coder task packet for Codex Handoff.",
        )
    else:
        state["status"] = "running"
        append_event(state, node="method_planner", kind="node_complete", summary=method_plan["summary"])
    state = register_artifact_bundle(
        state,
        slot="plan",
        member_paths=[artifact_dir],
        state_paths={
            "method_plan_path": result["method_plan_path"],
            "coder_task_packet_path": result["coder_task_packet_path"],
        },
        status=result["status"],
    )
    save_graph_state(state)
    return state


def _snapshot_handoff_files(
    run_root: Path,
    artifact_dir: Path,
    *,
    include_rebuilt_task_packet: bool,
) -> list[Path]:
    snapshot_paths: list[Path] = []
    names = [
        "code_change_summary.md",
        "tests_status.json",
        "codex_handoff_last_message.md",
    ]
    if include_rebuilt_task_packet:
        names.insert(0, "coder_task_packet.yaml")
    for name in names:
        source = run_root / name
        if not source.is_file():
            continue
        destination = artifact_dir / name
        shutil.copyfile(source, destination)
        snapshot_paths.append(destination)
    return snapshot_paths


def codex_handoff_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "codex_handoff"
    state["status"] = "running"
    llm_context_view(state)

    try:
        task_packet = ensure_task_packet(state)
    except TaskPacketValidationError as exc:
        state["status"] = "halted"
        state["errors"].extend(
            {
                "node": "codex_handoff",
                "field": "coder_task_packet_path",
                "message": error,
            }
            for error in exc.errors
        )
        append_event(
            state,
            node="codex_handoff",
            kind="node_halted",
            summary="Codex Handoff could not validate or rebuild coder_task_packet.yaml.",
        )
        save_graph_state(state)
        return state

    rebuilt_task_packet = task_packet["coder_task_packet_path"] != state.get("coder_task_packet_path")
    handoff = read_handoff_results(state["output_dir"])
    if (
        state.get("auto_codex_handoff") is True
        and handoff["handoff_status"] == "pending"
        and not handoff["code_change_summary_path"]
        and not handoff["tests_status_path"]
    ):
        repo_root = Path(__file__).resolve().parents[3]
        try:
            worker_result = run_worker(
                run_dir=state["output_dir"],
                repo_root=repo_root,
                codex_bin=state.get("codex_bin", "codex"),
                codex_model=state.get("codex_model"),
                timeout_seconds=int(state.get("codex_timeout_seconds", 900)),
                verification_timeout_seconds=int(state.get("verification_timeout_seconds", 60)),
                force=bool(state.get("force_codex_handoff", False)),
                dry_run=bool(state.get("dry_run_codex", False)),
            )
        except Exception as exc:
            state["status"] = "pending"
            state["errors"].append(
                {
                    "node": "codex_handoff",
                    "field": "auto_codex_handoff",
                    "message": str(exc),
                }
            )
            append_event(
                state,
                node="codex_handoff",
                kind="node_pending",
                summary="Automatic Codex handoff failed before structured result files were available.",
                coder_task_packet_path=state["coder_task_packet_path"],
            )
            save_graph_state(state)
            return state
        append_event(
            state,
            node="codex_handoff",
            kind="worker_complete" if worker_result.get("status") != "dry_run" else "worker_dry_run",
            summary=f"Automatic Codex handoff worker returned {worker_result.get('status')}.",
        )
        handoff = read_handoff_results(state["output_dir"])

    snapshot_paths: list[Path] = []
    if handoff["code_change_summary_path"] or handoff["tests_status_path"] or rebuilt_task_packet:
        artifact_dir = prepare_attempt_output_dir(state)
        snapshot_paths = _snapshot_handoff_files(
            Path(state["output_dir"]),
            artifact_dir,
            include_rebuilt_task_packet=rebuilt_task_packet,
        )
        summary_path = artifact_dir / "code_change_summary.md"
        tests_path = artifact_dir / "tests_status.json"
        state = register_artifact_bundle(
            state,
            slot="code",
            member_paths=snapshot_paths,
            state_paths={
                "code_change_summary_path": str(summary_path) if summary_path.is_file() else None,
                "tests_status_path": str(tests_path) if tests_path.is_file() else None,
            },
            status=handoff["handoff_status"],
        )

    if handoff["handoff_status"] == "halted":
        state["status"] = "halted"
        state["errors"].extend(
            {
                "node": "codex_handoff",
                "field": error.get("field"),
                "message": error.get("message"),
                "path": error.get("path"),
            }
            for error in handoff["errors"]
        )
        append_event(
            state,
            node="codex_handoff",
            kind="node_halted",
            summary=handoff["summary"],
        )
    elif handoff["handoff_status"] == "tests_passed":
        state["status"] = "running"
        state["code_needed"] = False
        state["code_fix_requested"] = False
        state["failure_type"] = None
        append_event(
            state,
            node="codex_handoff",
            kind="node_complete",
            summary="Structured handoff tests passed; analysis can continue.",
            tests_status_path=state["tests_status_path"],
            code_change_summary_path=state["code_change_summary_path"],
        )
    elif handoff["handoff_status"] == "tests_failed":
        state["status"] = "pending"
        state["code_fix_requested"] = True
        state["failure_type"] = "code"
        append_event(
            state,
            node="codex_handoff",
            kind="node_pending",
            summary="Structured handoff tests failed; awaiting an external code fix.",
            tests_status_path=state["tests_status_path"],
        )
    else:
        state["status"] = "pending"
        append_event(
            state,
            node="codex_handoff",
            kind="node_pending",
            summary=handoff["summary"],
            coder_task_packet_path=state["coder_task_packet_path"],
        )

    state["warnings"].extend(
        {
            "node": "codex_handoff",
            "field": warning.get("field"),
            "message": warning.get("message"),
        }
        for warning in handoff["warnings"]
    )
    save_graph_state(state)
    return state


def analysis_engineer_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "analysis_engineer"
    state["status"] = "running"
    llm_context_view(state)
    artifact_dir = prepare_attempt_output_dir(state)
    repo_root = Path(__file__).resolve().parents[3]
    result = run_analysis_engineer(
        case_config_path=state["case_config_path"],
        case_id=state["case_id"],
        run_id=state["run_id"],
        run_output_dir=state["output_dir"],
        artifact_output_dir=artifact_dir,
        method_plan_path=state["method_plan_path"],
        repo_root=repo_root,
    )
    state["run_success"] = result["run_success"]
    state["failure_type"] = result["failure_type"]
    state["warnings"].extend(
        {
            "node": "analysis_engineer",
            "field": warning.get("field"),
            "message": warning.get("message"),
        }
        for warning in result["warnings"]
    )
    state["errors"].extend(
        {
            "node": "analysis_engineer",
            "field": error.get("field"),
            "message": error.get("message"),
            "command_id": error.get("command_id"),
            "return_code": error.get("return_code"),
        }
        for error in result["errors"]
    )
    state["status"] = "running" if result["run_success"] else "failed"
    summary = (
        result["run_result"]["summary"]
        if result["run_result"]
        else "Analysis Engineer stopped before writing run artifacts."
    )
    append_event(
        state,
        node="analysis_engineer",
        kind="node_complete" if result["run_success"] else "node_failed",
        summary=summary,
        manifest_path=result["manifest_path"],
    )
    if result["run_result_path"]:
        state = register_artifact_bundle(
            state,
            slot="analysis",
            member_paths=[artifact_dir],
            state_paths={
                "run_result_path": result["run_result_path"],
                "analysis_outputs_dir": result["analysis_outputs_dir"],
            },
            status="success" if result["run_success"] else "failed",
        )
    save_graph_state(state)
    return state


def scientific_reviewer_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "scientific_reviewer"
    state["status"] = "running"
    llm_context_view(state)
    artifact_dir = prepare_attempt_output_dir(state)
    result = run_scientific_reviewer(
        run_id=state["run_id"],
        case_id=state["case_id"],
        run_output_dir=artifact_dir,
        run_result_path=state["run_result_path"],
        analysis_outputs_dir=state["analysis_outputs_dir"],
        method_plan_path=state["method_plan_path"],
        provider_config_path=state["llm_provider_config_path"],
    )
    report = result["report"]
    state["warnings"].extend(
        {
            "node": "scientific_reviewer",
            "section": warning.get("section"),
            "code": warning.get("code"),
            "severity": warning.get("severity"),
            "decision_coordinator_flag": warning.get("decision_coordinator_flag"),
            "message": warning.get("message"),
            "path": warning.get("path"),
            "field": warning.get("field"),
            "value": warning.get("value"),
        }
        for warning in report["warnings"]
    )
    state["errors"].extend(
        {
            "node": "scientific_reviewer",
            "field": error.get("field") or error.get("code"),
            "message": error.get("message"),
        }
        for error in result.get("errors", [])
    )
    if result["status"] != "success":
        state["risk_level"] = "critical"
        state["status"] = "pending"
    elif any(warning.get("severity") == "severe" for warning in report["warnings"]):
        state["risk_level"] = "high"
    elif report["warnings"]:
        state["risk_level"] = "medium"
    else:
        state["risk_level"] = "low"
    append_event(
        state,
        node="scientific_reviewer",
        kind="node_complete" if result["status"] == "success" else "node_pending",
        summary=report["summary"],
    )
    if result["scientific_review_report_path"] and any(artifact_dir.iterdir()):
        state = register_artifact_bundle(
            state,
            slot="review",
            member_paths=[artifact_dir],
            state_paths={
                "scientific_review_report_path": result["scientific_review_report_path"],
            },
            status=result["status"],
        )
    save_graph_state(state)
    return state


def decision_coordinator_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "decision_coordinator"
    state["status"] = "running"
    llm_context_view(state)
    artifact_dir = prepare_attempt_output_dir(state)
    result = run_decision_coordinator(
        run_id=state["run_id"],
        case_id=state["case_id"],
        output_dir=artifact_dir,
        method_plan_path=state["method_plan_path"],
        run_result_path=state["run_result_path"],
        scientific_review_report_path=state["scientific_review_report_path"],
        provider_config_path=state["llm_provider_config_path"],
    )
    decision_log = result["decision_log"]
    state["risk_level"] = result["risk_level"]
    state["recommended_action"] = result["recommended_action"]
    state["human_approval_required"] = result["human_approval_required"]
    state["rerun_requested"] = result["rerun_requested"]
    state["rerun_target"] = result["rerun_target"]
    state["code_fix_requested"] = result["code_fix_requested"]
    state["status"] = "running" if result["status"] == "success" else "pending"
    append_event(state, node="decision_coordinator", kind="node_complete", summary=decision_log["summary"])
    state = register_artifact_bundle(
        state,
        slot="decision",
        member_paths=[artifact_dir],
        state_paths={"decision_log_path": result["decision_log_path"]},
        status=result["status"],
    )
    save_graph_state(state)
    return state


def human_approval_gate_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "human_approval_gate"
    llm_context_view(state)

    if not state["human_approval_required"]:
        state["status"] = "running"
        append_event(
            state,
            node="human_approval_gate",
            kind="node_complete",
            summary="Human Approval Gate was bypassed because approval is not required.",
        )
        save_graph_state(state)
        return state

    approval_pointer = state.get("current_artifacts", {}).get("approval")
    if not isinstance(approval_pointer, dict):
        artifact_dir = prepare_attempt_output_dir(state)
        packet_paths = write_approval_packet(state, output_dir=artifact_dir)
        ingress_decision_path = Path(state["output_dir"]) / "approval_packet" / "07_human_decision.yaml"
        state = register_artifact_bundle(
            state,
            slot="approval",
            member_paths=[artifact_dir],
            state_paths={
                "approval_packet_dir": packet_paths["approval_packet_dir"],
                "human_decision_path": str(ingress_decision_path),
            },
            status="pending",
        )
        state = record_human_request_packet(
            state,
            packet_reference=str(packet_paths["approval_packet_path"]),
        )

    decision_result = parse_human_decision(
        state["human_decision_path"],
        run_id=state["run_id"],
        case_id=state["case_id"],
        cycle_id=state["cycle_id"],
        human_request_id=state["active_human_request_id"],
        requesting_attempt_id=state["human_requesting_attempt_id"],
        human_response_id=state["active_human_response_id"],
    )
    if decision_result["status"] == "pending":
        state["status"] = "pending"
        append_event(
            state,
            node="human_approval_gate",
            kind="node_pending",
            summary="Approval packet is ready and waiting for a human decision.",
            approval_packet_dir=state["approval_packet_dir"],
            human_decision_path=state["human_decision_path"],
        )
        save_graph_state(state)
        return state

    if decision_result["status"] == "invalid":
        if state.get("human_response_status") == "submitted":
            state = validate_human_response(
                state,
                validator_attempt_id=str(state["attempt_id"]),
                valid=False,
                error="Human response failed identity or schema validation.",
            )
        state["status"] = "pending"
        state["errors"].extend(
            {
                "node": "human_approval_gate",
                "field": error.get("field"),
                "message": error.get("message"),
                "path": error.get("path"),
                "value": error.get("value"),
                "expected": error.get("expected"),
            }
            for error in decision_result["errors"]
        )
        append_event(
            state,
            node="human_approval_gate",
            kind="node_pending",
            summary="Human decision file is present but invalid; waiting for correction.",
            human_decision_path=state["human_decision_path"],
        )
        save_graph_state(state)
        return state

    if state.get("human_response_status") != "submitted":
        raise ValueError("A valid human decision requires a submitted Human Response identity.")
    decision = decision_result["decision"]
    follow_up_route = decision_route_target(decision)
    state = validate_human_response(
        state,
        validator_attempt_id=str(state["attempt_id"]),
        valid=True,
        decision_payload=decision_result.get("payload"),
        authorized_route=follow_up_route,
    )
    if state["human_response_status"] == "invalid":
        state["status"] = "pending"
        state["errors"].append(
            {
                "node": "human_approval_gate",
                "field": "authorization_scope",
                "message": f"Human decision target {follow_up_route!r} is outside the active request scope.",
            }
        )
        append_event(
            state,
            node="human_approval_gate",
            kind="node_pending",
            summary="Human decision is outside the active authorization scope.",
        )
        save_graph_state(state)
        return state
    state["rerun_requested"] = False
    state["rerun_target"] = None
    state["code_fix_requested"] = False
    state["code_needed"] = False

    if decision == "approve_rerun":
        state["status"] = "pending"
        state["rerun_requested"] = True
        state["rerun_target"] = "analysis_engineer"
    elif decision == "request_code_change":
        state["status"] = "running"
        state["code_fix_requested"] = True
        state["code_needed"] = True
    else:
        state["status"] = "running"

    append_event(
        state,
        node="human_approval_gate",
        kind="node_complete",
        summary=f"Human decision recorded: {decision}.",
        human_decision_path=state["human_decision_path"],
        requested_route=follow_up_route,
    )
    save_graph_state(state)
    return state


def memory_report_node(state: AnalysisState) -> AnalysisState:
    state = dict(state)
    state["current_node"] = "memory_report"
    llm_context_view(state)
    artifact_dir = prepare_attempt_output_dir(state)
    memory_result = write_memory_update(state, output_dir=artifact_dir)
    state["memory_update_path"] = memory_result["memory_update_path"]
    memory_status = memory_result["memory_update"]["memory_status"]
    state["status"] = "success" if memory_status == "accepted" else "pending"
    report_result = write_final_report(
        state,
        memory_result["memory_update"],
        output_dir=artifact_dir,
    )
    state["final_report_path"] = report_result["final_report_path"]
    append_event(
        state,
        node="memory_report",
        kind="node_complete",
        summary="Wrote final report and structured memory update.",
        memory_status=memory_status,
        final_report_path=state["final_report_path"],
        memory_update_path=state["memory_update_path"],
    )
    state = register_artifact_bundle(
        state,
        slot="terminal",
        member_paths=[artifact_dir],
        state_paths={
            "memory_update_path": memory_result["memory_update_path"],
            "final_report_path": report_result["final_report_path"],
        },
        status=memory_status,
    )
    if memory_status == "accepted":
        state = protect_current_artifact(
            state,
            slot="terminal",
            protected_kind="accepted_result",
        )
    save_graph_state(state)
    return state
