"""Four-level product fallback retains original Code and fresh Analysis owners."""
from helpers.b04_code_product import code_product, deliver_product_code
from helpers.host_identity_fixture import HostIdentities
from lqcd_agent.control.pause import ResumeRunRequest
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from test_b04_product_graph import diagnostic


MODES = {"code_fix": ("code_agent", "code"), "code_rerun": ("analysis_engineer", "analysis"),
         "code_replan": ("method_planner", "plan")}


def remediation_trace(mode):
    target, layer = MODES[mode]
    failure = diagnostic(category="method_revision" if layer == "plan" else "implementation_failure",
        affected_layer=layer, retryability="retryable", candidates=[target], risk="medium")
    with HostIdentities("b04-code-remediation-" + mode).installed():
        coordinator, actor, agent, backend, host, handoff, result = code_product(
            outcomes={"scientific_reviewer": [failure, diagnostic()]}, trace=True, trace_version="0.10")
        try:
            runtime, locator = result["runtime"], result["run_locator"]
            _, first = deliver_product_code(coordinator, actor, backend, host, result)
            if mode != "code_replan":
                _, pending = runtime._records(locator)
                state = pending.projection.value
                assert state["run_status"] == "paused"
                payload = {**locator, "cycle_id": state["cycle_id"], "human_request_id": state["active_human_request_id"],
                    "decision": "request_code_change" if mode == "code_fix" else "approve_rerun", "conditions": [],
                    "reason": "Authorize the bounded remediation selected from actual evidence", "decided_by": "operator"}
                approval = ResumeRunRequest(locator, state["active_pause"]["pause_id"], "b04-remediation-approval",
                                            "human_response", payload, digest(payload))
                assert runtime.resume(approval, actor=actor)["operation_status"] == "committed"
            if mode != "code_rerun":
                assert len(backend.dispatches) == 2
                _, last = deliver_product_code(coordinator, actor, backend, host, result, producer=backend.dispatches[-1])
            else:
                last = first
            root, execution = runtime._records(locator)
            assert execution.projection.value["run_status"] == "completed"
            scheduled = [row for row in execution.values if row["record_type"] == "attempt" and row["event"] == "scheduled"]
            targets = [row for row in scheduled if row["attempt_kind"] == target]
            assert len(targets) == 2 and len({row["attempt_id"] for row in targets}) == 2
            assert len({row["cycle_id"] for row in targets}) == (2 if mode == "code_replan" else 1)
            index = loads((root / "artifact_index.json").read_bytes())
            current = index["current"]
            assert current["code"]["status"] == "success" and current["analysis"]["status"] == "success"
            analyses = [loads(row[0])["authorization"]["target_preparation"] for row in coordinator.connection.execute(
                "SELECT value FROM invocation_capabilities") if loads(row[0])["authorization"]["identity"]["attempt_kind"] == "analysis_engineer"]
            assert len(analyses) == 2 and all(value["preparation_kind"] == "analysis_fresh" for value in analyses)
            assert analyses[0]["fresh_workspace_identity"] != analyses[1]["fresh_workspace_identity"]
            contexts = [context for node, context in agent.contexts if node == target]
            if mode == "code_replan":
                assert contexts[1]["remediation"]["target_node"] == target
            tasks = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM external_operations")]
            assert len(tasks) == len(backend.dispatches) == (1 if mode == "code_rerun" else 2)
            if mode == "code_fix":
                assert targets[1]["parent_attempt_id"] != targets[0]["parent_attempt_id"]
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            calls, dispatches = len(agent.contexts), len(backend.dispatches)
            runtime.resume(last, actor=actor)
            runtime.run(locator)
            assert (len(agent.contexts), len(backend.dispatches)) == (calls, dispatches)
            assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            raw = result["trace_capture"].finish(coordinator)
            facts = {"mode": mode, "target": target, "cycles": execution.projection.value["cycle_index"],
                "dispatches": dispatches, "fresh_analyses": len(analyses), "run_status": "completed",
                "routes": [[row["source_node"], row["target_node"]] for row in execution.values if row["record_type"] == "transition"]}
            for name, value in (("raw", raw), ("facts", facts)):
                (coordinator.root / ("b04-remediation-" + name + ".json")).write_bytes(canonical_bytes(value))
            return raw, coordinator.root, facts
        finally:
            coordinator.close()
