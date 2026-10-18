"""Code parent uses original producer, consumption and fresh Analysis ports."""
from hashlib import sha256

import pytest

from helpers.b04_code_product import code_product, deliver_product_code
from lqcd_agent.control.strict_json import loads


@pytest.mark.parametrize("status", ["success", "needs_input", "failed"])
def test_product_code_delivers_once_then_uses_new_advance(status):
    coordinator, actor, agent, backend, host, handoff, result = code_product(status=status)
    try:
        assert result["state"]["run_status"] == "paused" and len(backend.dispatches) == 1
        runtime = result["runtime"]
        root, execution = runtime._records(result["run_locator"])
        code = next(r for r in execution.values if r.get("attempt_kind") == "code_agent")
        capability = next(r[0] for r in coordinator.connection.execute("SELECT capability_id,value FROM invocation_capabilities")
                          if loads(r[1])["authorization"]["identity"]["attempt_id"] == code["attempt_id"])
        host.prepare(capability, worker_id="product-host", actor=actor)
        assert len(backend.dispatches) == 1
        resumed, request = deliver_product_code(coordinator, actor, backend, host, result)
        assert resumed["operation_status"] == "committed"
        _, execution = runtime._records(result["run_locator"])
        state = execution.projection.value
        index = loads((root / "artifact_index.json").read_bytes())
        pointer = index["current"]["code"]
        assert pointer is not None and pointer["status"] == status
        transitions = [r for r in execution.values if r["record_type"] == "transition"]
        code_edge = next(r for r in transitions if r["source_node"] == "code_agent")
        assert code_edge["target_node"] == ("analysis_engineer" if status == "success" else "decision_coordinator")
        owner = coordinator.lookup_key("internal_advance", "product-advance:" + code["attempt_id"])
        assert owner["operation_type"] == "advance_run" and owner["status"] == "committed"
        assert coordinator.snapshot(owner["operation_id"])["records"][-1] == code_edge
        if status == "success":
            assert state["run_status"] == "completed"
            analysis = loads((root / next(m["canonical_path"] for m in index["current"]["analysis"]["members"]
                                         if m["logical_name"] == "run_result.json")).read_bytes())
            assert analysis["execution"]["stdout_sha256"] == sha256(b"2\n").hexdigest()
            sources = [loads(r[0]) for r in coordinator.connection.execute("SELECT value FROM invocation_capabilities")
                       if loads(r[0])["authorization"]["identity"]["attempt_kind"] == "analysis_engineer"]
            prepared, = sources
            prep = prepared["authorization"]["target_preparation"]
            assert prep["preparation_kind"] == "analysis_fresh"
            manifest = loads((root / "code_agent_control" / code["attempt_id"] / "workspace_manifest.json").read_bytes())
            workspace = host.consumer.provider.path(manifest["workspace_id"])
            assert handoff.provider.path(prep["fresh_workspace_identity"]) != workspace
        else:
            assert state["run_status"] == "paused" and state["attempt_kind"] == "human_gate"
            assert not any(n == "analysis_engineer" for n, _ in agent.contexts)
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        runtime.resume(request, actor=actor)
        runtime.run(result["run_locator"])
        assert len(backend.dispatches) == 1
        assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    finally:
        coordinator.close()


@pytest.mark.parametrize("fault", ["kill_all", "bounded_drain", "post_stop_stability"])
def test_unsafe_final_graph_reentry_retains_recovery_without_an_active_pause(fault):
    coordinator, _, agent, backend, host, _, result = code_product(status="failed", stop_fault=fault)
    try:
        runtime, locator = result["runtime"], result["run_locator"]
        producer, = backend.dispatches
        audit, patch = backend.deliveries[producer]
        final = host.finalize(producer, tool_audit=audit, patch=patch)
        assert final["operation_status"] == "recovery_required" and final["terminal_closure"] == "unavailable"
        root, execution = runtime._records(locator)
        assert execution.projection.value["run_status"] == "paused"
        assert execution.projection.value["active_pause"] is None
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        capabilities = [dict(row) for row in coordinator.connection.execute("SELECT * FROM invocation_capabilities")]
        for _ in range(2):
            entered = runtime.run(locator)
            stopped, = entered["__interrupt__"]
            assert stopped.value == {"run_locator": locator, "run_status": "paused"}
            assert host.finalize(producer, tool_audit=audit, patch=patch) == final
        assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert capabilities == [dict(row) for row in coordinator.connection.execute("SELECT * FROM invocation_capabilities")]
        assert len(backend.dispatches) == len(agent.contexts) == 1
        assert loads((root / "artifact_index.json").read_bytes())["current"]["code"] is None
    finally:
        coordinator.close()
