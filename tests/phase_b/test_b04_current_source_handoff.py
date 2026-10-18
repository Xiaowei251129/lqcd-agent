"""The product consumes approved provenance through its original graph ports."""
import pytest

from harness.contracts import ROOT
from harness.strict_json import read
from harness.pytest_evidence import observe
from harness.trace import compare, normalize
from helpers.b04_trajectories import MODES, trajectory
from helpers.b04_code_product import code_product, deliver_product_code
from helpers.host_identity_fixture import HostIdentities
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes


@pytest.mark.parametrize("mode", MODES)
def test_current_product_trajectory_is_exact_across_fresh_roots(mode):
    traces = []
    for _ in range(2):
        raw, output, facts = trajectory(mode, trace_version="0.10")
        assert raw["schema_version"] == "0.10" and raw["proof"]["schema_version"] == "0.7"
        assert facts["duplicate_readonly"]
        projected = normalize(raw, binding=current_binding())
        (output / "normalized.json").write_bytes(canonical_bytes(projected))
        traces.append(projected)
    assert traces[0] == traces[1]
    compare(raw, read(ROOT / ("tests/phase_b/expected_traces/b04_product/trajectory-" + mode + ".json")), binding=current_binding())
    observe("B04-TRAJECTORY-" + mode, {"kind": "boolean", "value": True},
            ["actual_production_path", "dual_fresh_exact", "duplicate_readonly"], raw)


@pytest.mark.parametrize("status", ["success", "needs_input", "failed", "no_change", "needs_human", "budget_exhausted", "policy_blocked"])
def test_current_code_parent_source_is_exact_across_fresh_roots(status):
    traces = []
    for _ in range(2):
        with HostIdentities("b04-current-code-" + status).installed():
            coordinator, actor, agent, backend, host, handoff, result = code_product(
                status=status, trace=True, trace_version="0.10")
            try:
                resumed, request = deliver_product_code(coordinator, actor, backend, host, result)
                assert resumed["operation_status"] == "committed" and len(backend.dispatches) == 1
                raw = result["trace_capture"].finish(coordinator)
                projected = normalize(raw, binding=current_binding())
                for name, value in (("raw", raw), ("normalized", projected)):
                    (coordinator.root / ("b04-current-" + name + ".json")).write_bytes(canonical_bytes(value))
                traces.append(projected)
            finally:
                coordinator.close()
    assert traces[0] == traces[1]
    compare(raw, read(ROOT / ("tests/phase_b/expected_traces/b04_product/code-parent-" + status + ".json")), binding=current_binding())
    observe("B04-CODE-" + status, {"kind": "boolean", "value": True},
            ["actual_production_path", "dual_fresh_exact", "single_dispatch"], raw)
