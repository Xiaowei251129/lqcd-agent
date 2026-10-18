"""Fresh single-run construction complements the required dual-fresh scenarios."""
from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import read
from helpers.b04_trajectories import trajectory
from helpers.b04_forbidden_product import forbidden_trace
from helpers.b04_code_remediation import remediation_trace
from helpers.b04_resource_outcomes import resource_failure_trace
from helpers.b04_stop_routes import stop_route_trace
from helpers.b04_code_product import code_product, deliver_product_code
from helpers.host_identity_fixture import HostIdentities
from helpers.unconsumed_code_final_sources import product_unconsumed_trace
from lqcd_agent.control.strict_json import canonical_bytes, loads
from test_b00c18_ordinary_repause_handoff import repause_trace
import pytest


SCENARIOS = {s["scenario_id"]: s for s in read(ROOT / "tests/phase_b/acceptance_matrix.json")["scenarios"]
             if s["scenario_id"].startswith("B04-CONSTRUCT-")}


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_construction_scenario(scenario_id):
    scenario = SCENARIOS[scenario_id]
    facts = {}
    kind, mode = scenario_id.removeprefix("B04-CONSTRUCT-").split("-", 1)
    if kind == "CODE":
        with HostIdentities("b04-current-code-" + mode).installed():
            coordinator, actor, agent, backend, host, _, result = code_product(
                status=mode, trace=True, trace_version="0.10")
            try:
                resumed, _ = deliver_product_code(coordinator, actor, backend, host, result)
                assert resumed["operation_status"] == "committed" and len(backend.dispatches) == 1
                root, execution = result["runtime"]._records(result["run_locator"])
                code = loads((root / "artifact_index.json").read_bytes())["current"]["code"]
                assert code["status"] == mode
                assert execution.projection.value["run_status"] == ("completed" if mode == "success" else "paused")
                raw = result["trace_capture"].finish(coordinator)
                (coordinator.root / "b04-construction-raw.json").write_bytes(canonical_bytes(raw))
            finally:
                coordinator.close()
    else:
        factories = {"TRAJECTORY": lambda value: trajectory(value, trace_version="0.10"),
                     "FORBID": forbidden_trace, "REMEDIATION": remediation_trace,
                     "RESOURCE": resource_failure_trace, "CAPACITY": repause_trace,
                     "EXTERNAL": product_unconsumed_trace,
                     "STOP": lambda value: stop_route_trace(value, trace_version="0.11")}
        raw, _, facts = factories[kind](mode)
    refs = scenario["contract_refs"]
    if "A01-FORBID-003" in refs:
        transitions = [row["value"] for row in raw["proof"]["objects"]
                       if row["value"].get("record_type") == "transition"]
        assert all(row["target_node"] == "decision_coordinator" for row in transitions
                   if row["source_node"] in ("human_gate", "human_approval_gate"))
    if "A01-FORBID-004" in refs:
        calls = [loads(call["config"]["content"])["node"] for call in raw["proof"]["ordinary_calls"]
                 if call["profile"] == "scoped_llm"]
        assert calls and not ({"memory_report", "decision_coordinator", "human_gate"} & set(calls))
    if "A01-FORBID-009" in refs:
        assert facts["policy_unchanged"]
    observe(scenario_id, {"kind": "boolean", "value": True}, scenario["required_invariants"], raw)
