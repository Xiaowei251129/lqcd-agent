"""Reviewed complete source-bound B02 paths through the unchanged trace checker."""
import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.b02_source_traces import TRAJECTORIES, source_trace
from helpers.trace_sources import current_binding


@pytest.mark.parametrize("name", sorted(TRAJECTORIES))
def test_source_bound_trajectory(name):
    first, second = source_trace(name), source_trace(name)
    assert first["proof"]["output_roots"] != second["proof"]["output_roots"]
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    compare(first, read(ROOT / "tests/phase_b/expected_traces" / ("b02_source_" + name + ".json")), binding=current_binding())
    requirement, _ = TRAJECTORIES[name]
    observe("b02-source-" + name, {"kind": "boolean", "value": True}, sorted([requirement, "source_bound_heads"]), first)


@pytest.mark.parametrize("fault", ["missing_delivery", "changed_timeout_member", "wrong_interval"])
def test_timeout_source_rejects_incomplete_canonical_proof(fault):
    trace = source_trace("timeout")
    rows = trace["proof"]["objects"]
    if fault == "missing_delivery":
        head = next(row["source_sha256"] for row in trace["proof"]["typed_sources"] if row["kind"] == "delivery")
        rows.remove(next(row for row in rows if row["sha256"] == head))
    elif fault == "changed_timeout_member":
        bundle = next(row["value"] for row in rows if row["kind"] == "canonical_json" and
                      row["value"].get("slot") == "code" and row["value"].get("event") == "registered")
        head = next(member["sha256"] for member in bundle["members"] if
                    member["canonical_path"].endswith("/interrupt_evidence.json"))
        next(row for row in rows if row["sha256"] == head)["value"]["dispatch_phase"] = "forged"
    else:
        interval = next(row["value"] for row in rows if row["kind"] == "execution_0_4" and
                        row["value"].get("event") == "active_interval_settled" and
                        row["value"]["payload"]["stage"] == "attempt_active")
        interval["payload"]["evidence_digest"] = "0" * 64
    with pytest.raises(Invalid):
        normalize(trace, binding=current_binding())
