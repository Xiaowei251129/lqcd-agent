"""Passive 0.9 declarations from actual registered Tasks and original sources."""
from copy import deepcopy

from helpers.product_failure_sources import ProductFailureSources
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import digest


class PriorCodeSources(ProductFailureSources):
    def finish(self, trace):
        super().finish(trace)
        proof = trace["proof"]
        sources = {row["sha256"]: row["value"] for row in proof["objects"]}
        registrations = {(v["case_id"], v["run_id"], v["artifact_id"]): v for v in sources.values()
                         if v.get("event") == "registered" and "pointer" in v}
        evidence_sources, authorizations = [], []
        for typed in proof["typed_sources"]:
            if typed["kind"] != "task":
                continue
            task_head = typed["source_sha256"]
            task = sources[task_head]
            run = task["case_id"], task["run_id"]
            records = [r for r in sources.values() if r.get("record_type") is not None and
                       (r.get("case_id"), r.get("run_id")) == run]
            transition, = [r for r in records if r["record_type"] == "transition" and r["transition_id"] == task["transition_id"]]
            for i, evidence in enumerate(task["evidence"]):
                prior = registrations[(*run, evidence["artifact_id"])]
                if prior["slot"] != "code":
                    continue
                members = {m["logical_name"]: m for m in prior["members"]}
                prior_task = sources[members["code_agent_task.json"]["sha256"]]
                producer = ExternalControl(self.coordinator).read(self.coordinator.connection, prior_task["producer_operation_id"])
                evidence_sources.append({"schema_version": "0.1", "consumer_task_head": task_head, "evidence_index": i,
                    "consumer_transition_head": digest(transition), "source_registration_head": digest(prior),
                    "source_task_head": members["code_agent_task.json"]["sha256"],
                    "source_result_head": members["code_agent_result.json"]["sha256"],
                    "source_manifest_head": members["workspace_manifest.json"]["sha256"],
                    "source_change_head": members["change_manifest.json"]["sha256"],
                    "source_verification_head": members["verification_results.json"]["sha256"],
                    "source_final_evidence_head": producer["terminal_evidence_digest"],
                    "source_producer_operation_id": prior_task["producer_operation_id"]})
            human = task["human_authorization_ref"]
            if human is None:
                continue
            response = {r["event"]: r for r in records if r["record_type"] == "human_response" and
                        r["human_response_id"] == human["single_use_id"]}
            consumed = response["consumed"]
            request, = [r for r in records if r["record_type"] == "human_request" and r["event"] == "created" and
                        r["human_request_id"] == consumed["human_request_id"]]
            snapshot, = [v for v in sources.values() if v.get("event") == "protected_snapshot_registered" and
                         v.get("protected_kind") == "human_response" and
                         (v.get("case_id"), v.get("run_id")) == run and v.get("human_response_id") == human["single_use_id"]]
            parent, = [r for r in records if r["record_type"] == "transition" and r["target_attempt_id"] == task["source_attempt_id"]]
            pause, = [r for r in records if r["record_type"] == "pause" and r["event"] == "pause_consumed" and
                      r["proof"].get("input_digest") == consumed["payload_sha256"]]
            authorizations.append({"schema_version": "0.1", "consumer_task_head": task_head,
                "human_request_head": digest(request), "response_submitted_head": digest(response["submitted"]),
                "response_validated_head": digest(response["validated"]), "response_consumed_head": digest(consumed),
                "snapshot_registration_head": digest(snapshot), "resume_operation_id": pause["operation_id"],
                "parent_transition_head": digest(parent), "consumer_transition_head": digest(transition)})
        proof.update(schema_version="0.6", code_evidence_sources=deepcopy(evidence_sources),
                     code_task_authorizations=deepcopy(authorizations))
        return trace


def product_trace(mode, *, label=None, observer=None, requirement="Compute the approved synthetic observable", first_failure_change=None):
    """Run complete product retries with original Human and Code ports."""
    from helpers.b04_code_product import code_product, deliver_product_code
    from helpers.host_identity_fixture import HostIdentities
    from lqcd_agent.code_agent.external_operation import CodeWatchdog
    from lqcd_agent.control.pause import ResumeRunRequest
    from lqcd_agent.control.strict_json import canonical_bytes, loads

    assert mode in ("retry_success", "retry_failed", "triple_success", "no_change", "needs_input", "needs_human",
                    "budget_exhausted", "policy_blocked", "timeout_retry")
    statuses = ["failed", "failed", "success"] if mode == "triple_success" else [
        mode if mode in ("no_change", "needs_input", "needs_human", "budget_exhausted", "policy_blocked") else "failed",
        "failed" if mode == "retry_failed" else "success"]
    identities = HostIdentities(label or "c21-product-" + mode)
    with identities.installed():
        coordinator, actor, agent, backend, host, handoff, result = code_product(
            status=statuses, trace=True, trace_version="0.9", observer=observer, requirement=requirement,
            first_failure_change=first_failure_change)
        try:
            runtime, locator = result["runtime"], result["run_locator"]
            requests = []
            for i in range(2 if mode == "triple_success" else 1):
                if mode == "timeout_retry":
                    coordinator.clock.subject.advance(11)
                    watchdog = CodeWatchdog(coordinator, backend, host.containment, backend.read_receipt)
                    interrupted = watchdog.enforce(backend.dispatches[-1])
                    assert interrupted["operation_status"] == "committed" and interrupted["domain_status"] == "failed"
                    runtime.run(locator)
                else:
                    _, request = deliver_product_code(coordinator, actor, backend, host, result, producer=backend.dispatches[-1])
                    requests.append(request)
                root, execution = runtime._records(locator)
                state = execution.projection.value
                assert state["run_status"] == "paused" and state["attempt_kind"] == "human_gate"
                response = {**locator, "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
                    "decision": "approve_budget_window" if i else "request_code_change", "conditions": [],
                    "reason": "A bounded retry of the original Code task", "decided_by": "operator"}
                request = ResumeRunRequest(locator, state["active_pause"]["pause_id"], "c21-approval-" + str(i),
                                          "human_response", response, digest(response))
                requests.append(request)
                resumed = runtime.resume(request, actor=actor)
                assert resumed["operation_status"] == "committed" and len(backend.dispatches) == i + 2
            _, request = deliver_product_code(coordinator, actor, backend, host, result, producer=backend.dispatches[-1])
            requests.append(request)
            root, execution = runtime._records(locator)
            state = execution.projection.value
            count = 3 if mode == "triple_success" else 2
            codes = [r for r in execution.values if r.get("record_type") == "attempt" and r["event"] == "finished" and
                     r["attempt_kind"] == "code_agent"]
            assert len(codes) == len(backend.dispatches) == count
            assert len(set(backend.dispatches)) == count
            index = loads((root / "artifact_index.json").read_bytes())["current"]
            if mode != "retry_failed":
                assert state["run_status"] == "completed" and index["analysis"] is not None
                analysis = next(m for m in index["analysis"]["members"] if m["logical_name"] == "run_result.json")
                assert loads((root / analysis["canonical_path"]).read_bytes())["execution"]["returncode"] == 0
            else:
                assert state["run_status"] == "paused"
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            runtime.resume(requests[-1], actor=actor)
            runtime.run(locator)
            assert len(backend.dispatches) == count
            assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            trace = result["trace_capture"].finish(coordinator)
            facts = {"mode": mode, "run_status": state["run_status"], "Code_attempts": count, "dispatches": count,
                "human_consumed": sum(r.get("record_type") == "human_response" and r["event"] == "consumed" for r in execution.values),
                "grants_issued": sum(r.get("event") == "grant_issued" for r in execution.values),
                "grants_consumed": sum(r.get("event") == "grant_consumed" for r in execution.values),
                "B04_owned": False, "fresh_analysis": mode != "retry_failed"}
            for name, value in (("c21-raw.json", trace), ("c21-facts.json", facts), ("c21-identities.json", identities.allocations)):
                (coordinator.root / name).write_bytes(canonical_bytes(value))
            return trace, coordinator.root, facts
        finally:
            coordinator.close()
