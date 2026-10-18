"""Passive collection of original unconsumed Code sources for trace 0.11."""
from harness.a05_trace import material_source, typed_source
from harness.trace import event
from harness.trace_proof import source_object
from harness.unconsumed_code_final_trace import MEMBERS, read_source, read_consumption_failure, read_backend_claim
from helpers.ordinary_publication_prefix_sources import PublicationPrefixSources
from lqcd_agent.control.strict_json import loads


class UnconsumedCodeSources(PublicationPrefixSources):
    def finish(self, trace):
        super().finish(trace)
        proof = trace["proof"]
        registered = {(row["value"].get("case_id"), row["value"].get("run_id"), row["value"].get("attempt_id"))
            for row in proof["objects"] if row["value"].get("event") == "registered" and row["value"].get("slot") == "code"}
        declarations = []
        for (stored,) in self.coordinator.connection.execute("SELECT value FROM external_operations"):
            producer = loads(stored)
            locator = producer["run_locator"]
            if producer["terminal_evidence_digest"] is None or producer["consumption_release"] is not None or (
                    locator["case_id"], locator["run_id"], producer["attempt_id"]) in registered:
                continue
            declaration, members = read_source(self.coordinator, producer)
            failure = read_consumption_failure(self.coordinator, producer)
            if failure is not None:
                source = source_object("canonical_json", {"durable_consumption_failure": failure}, version="0.4")
                if source not in proof["objects"]:
                    proof["objects"].append(source)
                trace["events"].append(event("consumption_failure_source", run_id=locator["run_id"],
                    attempt_id=producer["attempt_id"], operation_id=failure["owner"], result_digest=source["sha256"],
                    guard=failure["closure"], owner=failure["owner"], outcome="original_failure_journal"))
            owner = {**locator, "attempt_id": producer["attempt_id"], "producer_operation_id": producer["producer_operation_id"],
                     "workspace_id": producer["workspace_id"]}
            for kind, raw in members.items():
                unaccepted = kind == "external_result" and producer["resolution_owner"] != "normal"
                if kind in ("material", "canonical_tool_audit") or unaccepted:
                    item = material_source("material" if unaccepted else "tool_audit" if kind == "canonical_tool_audit" else kind, raw, owner)
                    item["kind"] = "material" if unaccepted else kind
                    if item not in proof["material_sources"]:
                        proof["material_sources"].append(item)
                    if unaccepted:
                        claim, _ = read_backend_claim(self.coordinator.root, producer, raw, proof["binding"])
                        proof["material_sources"].append(material_source("material", claim, owner))
                else:
                    value = loads(raw)
                    source = source_object("canonical_json", value, version="0.4")
                    if source not in proof["objects"]:
                        proof["objects"].append(source)
                    typed = typed_source(kind, value)
                    if typed not in proof["typed_sources"]:
                        proof["typed_sources"].append(typed)
            declarations.append(declaration)
            trace["events"].append(event("unconsumed_code_final", run_id=locator["run_id"], attempt_id=producer["attempt_id"],
                attempt_kind="code_agent", external_operation_id=producer["producer_operation_id"], lease_epoch=producer["lease_epoch"],
                owner=producer["resolution_owner"], operation_id=declaration["terminal_operation_id"], guard=declaration["publication_stage"],
                result_digest=declaration["final_head"], outcome="original_unconsumed_source"))
        proof.update(schema_version="0.8", unconsumed_code_sources=declarations)
        return trace


def product_unconsumed_trace(mode, *, requirement="Compute the approved synthetic observable", hook=None):
    """Exercise real product and control ports, then capture their durable source."""
    from functools import partial
    from hashlib import sha256
    from unittest.mock import patch
    import tempfile

    from harness.pytest_evidence import production_hook
    from harness.trace import normalize
    from helpers.b04_code_product import code_product
    from helpers.host_identity_fixture import HostIdentities
    from helpers.trace_sources import current_binding
    from lqcd_agent.code_agent.external_operation import CodeExternalStop
    from lqcd_agent.control.operations import CloseRunRequest, ExternalControl
    from lqcd_agent.control.pause import ResolveExternalInterruptRequest, ResumeRunRequest
    from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest

    normal = mode in ("normal", "attached", "non_success", "resume_failure", "consumer_overrun", "consumer_unsafe", "consumer_authority")
    authority_roots = []
    verification_calls = []
    fault = {"missing_termination": "kill_all", "missing_empty": "kill_all", "missing_drain": "bounded_drain",
             "missing_stability": "post_stop_stability"}.get(mode)
    def observer(name, side, value):
        if mode == "consumer_authority" and (name, side) == (
                "control.resume_run.continue_execution.consumption_failure_ownership_reserved", "after"):
            (authority_roots[0] / "artifact_index.json").write_bytes(b"{}")
        if hook is not None and (name, side) in (("external.final_evidence", "after"),
                                               ("external.external_final_evidence_committed", "after")):
            observer.production_hooks.clear()
    observer.production_hooks = {(name, "after"): (partial(production_hook, hook),) for name in
        ("external.final_evidence", "external.external_final_evidence_committed")} if hook else {}
    make_temp = tempfile.mkdtemp
    def source_directory(*args, **kwargs):
        if kwargs.get("prefix") == "lqcd-agent-b04-code-product-":
            kwargs["prefix"] = "lqcd-agent-b00c24-" + mode + "-"
        return make_temp(*args, **kwargs)
    with HostIdentities("b00c23-" + mode).installed(), patch.object(tempfile, "mkdtemp", source_directory):
        coordinator, actor, agent, backend, host, _, result = code_product(trace=True, trace_version="0.11",
            observer=observer, status="failed" if mode == "non_success" or not normal else "success", requirement=requirement,
            stop_fault=fault)
        try:
            producer, = backend.dispatches
            runtime, locator, capture = result["runtime"], result["run_locator"], result["trace_capture"]
            root, _ = runtime._records(locator)
            authority_roots.append(root)
            audit, changes = backend.deliveries[producer]
            if normal or fault is not None:
                response = host.finalize(producer, tool_audit=audit, patch=changes)
                assert host.finalize(producer, tool_audit=audit, patch=changes) == response
                if mode == "attached":
                    request = CloseRunRequest(locator, runtime._records(locator)[1].projection.value["execution_head"], "terminal_operator_stop")
                    response = runtime.plane.close_run(request, actor=actor)
                    assert runtime.plane.close_run(request, actor=actor) == response
                elif mode in ("resume_failure", "consumer_overrun", "consumer_unsafe", "consumer_authority"):
                    from helpers.b03_uncertain_consumer_cases import CanonicalConsumerHost
                    class Consumer(CanonicalConsumerHost):
                        def consume_external(self, identity, binding, port):
                            if mode == "consumer_overrun":
                                from lqcd_agent.code_agent.containment import DeterministicContainment
                                containment = DeterministicContainment(self.coordinator.root / "consumer_containment")
                                containment.start("consumer_" + port.capability_id, identity["attempt_id"] + "_consumer")
                                def effect():
                                    verification_calls.append("original_verification_effect")
                                    coordinator.clock.subject.advance(2)
                                    return {"spec_id": "c23-overrun", "status": "passed", "output_digest": digest("observed")}
                                return port.run_verification(spec_id="c23-overrun", input_digest=digest("input"), config_digest=digest("config"),
                                                             timeout_seconds=1, effect=effect)
                            return super().consume_external(identity, binding, port)
                    consumer = Consumer(coordinator, host.base_repository, safe=mode != "consumer_unsafe", reject=True)
                    runtime.plane.resume_target_adapter = runtime.plane.external_adapter = consumer
                    payload = {"producer_operation_id": producer, "external_final_digest": response["terminal_evidence_digest"]}
                    request = ResumeRunRequest(locator, response["pause_id"], "c23-resume", "external_result", payload, digest(payload))
                    response = runtime.plane.resume_run(request, actor=actor)
                    assert runtime.plane.resume_run(request, actor=actor) == response
            else:
                observed_error = None
                if mode == "late_integrity":
                    workspace = coordinator.root / "code_workspaces" / ("workspace_" + producer)
                    (workspace / "sample.py").write_bytes(b"def value():\n    return 123\n")
                    try:
                        host.finalize(producer, tool_audit=audit, patch=changes)
                    except ControlIntegrityError as error:
                        observed_error = {"type": type(error).__name__, "message": str(error)}
                    assert observed_error is not None
                if mode == "usage_overage":
                    coordinator.clock.subject.advance(11)
                class ObservedStop(CodeExternalStop):
                    def _observe_stop(self, value):
                        proof = super()._observe_stop(value)
                        if mode == "late_integrity":
                            assert observed_error is not None
                            proof["proven_policy_violation"] = True
                        if mode == "usage_overage":
                            proof["resource_actual"]["active_seconds"] = (
                                coordinator._time().monotonic_seconds - value["dispatch_started_at"])
                            assert proof["resource_actual"]["active_seconds"] > self._maximum(value)["active_seconds"]
                        return proof
                runtime.plane.external_adapter = ObservedStop(coordinator, backend, host.containment, backend.read_receipt)
                reason = "proven_integrity_trigger" if mode == "integrity" else "terminal_operator_stop"
                trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": reason}
                if observed_error is not None:
                    trigger["observed_integrity_error"] = observed_error
                (root / "c23-stop-trigger.json").write_bytes(canonical_bytes(trigger))
                request = ResolveExternalInterruptRequest(locator, producer, reason, "c23-stop-trigger.json", digest(trigger))
                if mode == "missing_writes":
                    with patch.object(host.containment, "revoke_writes", side_effect=OSError("Injected write-lease storage failure")):
                        response = runtime.plane.resolve_external_interrupt(request, actor=actor)
                else:
                    assert mode in ("integrity", "halt", "late_integrity", "usage_overage")
                    response = runtime.plane.resolve_external_interrupt(request, actor=actor)
                assert runtime.plane.resolve_external_interrupt(request, actor=actor) == response
            final_producer, final = ExternalControl(coordinator).final_evidence(coordinator.connection, producer)
            failure_source = read_consumption_failure(coordinator, final_producer)
            history = [loads(line) for line in (root / "artifact_history.jsonl").read_bytes().splitlines()]
            _, execution = runtime._records(locator)
            settlements = [row for row in execution.values if row.get("event") == "resource_settled" and
                           row["payload"]["resource_operation_id"] == final_producer["reservation_id"]]
            facts = {"mode": mode, "B04_owned": False, "dispatches": len(backend.dispatches), "ordinary_calls": len(agent.contexts),
                "run_status": execution.projection.value["run_status"], "producer_status": final_producer["operation_status"],
                "resolution_owner": final_producer["resolution_owner"], "settlements": len(settlements),
                "Code_registered": any(r.get("slot") == "code" and r["event"] == "registered" for r in history),
                "Analysis_registered": any(r.get("slot") == "analysis" and r["event"] == "registered" for r in history),
                "stop_dimensions": final["stop_proof"], "response_status": response["operation_status"],
                "terminal_owner": response.get("operation_id"), "readonly_replay": False,
                "verification_calls": len(verification_calls),
                "consumer_stop": failure_source["consumer_stop"]["classification"] if failure_source else None,
                "run_authority": failure_source["authority"] if failure_source else None}
            assert facts["dispatches"] == facts["ordinary_calls"] == 1 and not facts["Code_registered"] and not facts["Analysis_registered"]
            assert len(settlements) == int(mode != "normal" and mode != "non_success")
            assert all(row["payload"]["tokens"] == row["payload"]["cost"] == {"state": "unknown", "value": None} for row in settlements)
            (coordinator.root / "facts-before-capture.json").write_bytes(canonical_bytes(facts))
            raw = capture.finish(coordinator)
            (coordinator.root / "raw.json").write_bytes(canonical_bytes(raw))
            (coordinator.root / "facts.json").write_bytes(canonical_bytes(facts))
            before = {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
            normalized = normalize(raw, binding=current_binding())
            assert normalize(raw, binding=current_binding()) == normalized
            assert before == {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
            assert len(backend.dispatches) == 1
            assert len(verification_calls) == int(mode == "consumer_overrun")
            facts["readonly_replay"] = True
            (coordinator.root / "normalized.json").write_bytes(canonical_bytes(normalized))
            (coordinator.root / "facts.json").write_bytes(canonical_bytes(facts))
            return raw, coordinator.root, facts
        finally:
            coordinator.close()
