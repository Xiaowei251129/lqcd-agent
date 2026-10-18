"""Binding candidates preserve native probe identity and diagnostic isolation."""
from copy import deepcopy

import pytest

from harness import pytest_evidence
from harness.contracts import ROOT
from harness.failpoints import validate_runtime
from harness.inputs import load_inputs
from harness.inventory import validate_inventory
from harness.matrix import validate_matrix
from harness.pytest_evidence import observe, validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, read
from helpers.b04_process_binding import HOOK, nodeid
from test_b00c26_trace_consumers import CASE, native
import test_b00c26_owned_activation as lifecycle


INVARIANTS = ["candidate_only", "original_validators", "unchanged_registry"]


def binding_candidate(inputs, case_ids):
    matrix, registry = deepcopy(inputs["matrix"]), deepcopy(inputs["registry"])
    for entry in registry["entries"]:
        selected = [cid for cid in case_ids if inputs["specs"][cid]["failpoint_id"] == entry["failpoint_id"]]
        if not selected:
            continue
        entry["hook_ref"] = HOOK
        entry["case_bindings"] = [row for row in entry["case_bindings"] if row["case_id"] not in selected]
        for cid in selected:
            sid = "b00c28-candidate-" + cid
            fixture = "tests/phase_b/fixtures/b00c28/candidates/" + cid + ".json"
            spec = read(ROOT / fixture)
            matrix["scenarios"].append({"scenario_id": sid, "contract_refs": ["A07-META-006", "A07-META-015"],
                "layer": "recovery", "fixture_id": fixture, "entrypoint": spec["entrypoint"],
                "expected_trace_fixture": "tests/phase_b/expected_traces/b00c28/candidates/" + cid + ".json",
                "expected_result": spec["expected_result"], "required_invariants": spec["required_invariants"],
                "pytest_nodeids": [nodeid(cid)], "required": True, "evidence_class": "required_control_acceptance",
                "implementation_ticket_id": "B00", "validation_stage": "final"})
            entry["case_bindings"].append({"case_id": cid, "scenario_ids": [sid]})
        entry["case_bindings"].sort(key=lambda row: row["case_id"])
    matrix["scenarios"].sort(key=lambda row: row["scenario_id"])
    return matrix, registry


def test_complete_result_keeps_original_probe_identity(native):
    session, value, probe, _ = native
    validate_pytest(value, session, value["selection"])
    assert validate_observations(value, [probe], ROOT) == {"B00C26-PROBE"}
    inputs = load_inputs()
    matrix, registry = binding_candidate(inputs, [CASE])
    validate_matrix(matrix, inputs["catalog"], ROOT)
    validate_inventory(registry, inputs["obligations"], inputs["protocol"], ROOT, matrix["scenarios"])
    assert validate_runtime(value, registry, inputs["specs"], matrix["scenarios"], ROOT) == [CASE]
    formal = [row for row in matrix["scenarios"] if row["scenario_id"] == "b00c28-candidate-" + CASE]
    with pytest.raises(Invalid, match="observation:identity"):
        validate_observations(value, formal, ROOT, all_scenarios=matrix["scenarios"])
    assert value["observations"][0]["scenario_id"] == "B00C26-PROBE"
    observe("B00C28-IDENTITY", {"kind": "boolean", "value": True}, INVARIANTS)


def test_bound_candidates_keep_original_rejections(native, tmp_path):
    session, value, _, _ = native
    inputs = load_inputs()
    matrix, registry = binding_candidate(inputs, [CASE])
    validate_pytest(value, session, value["selection"])
    for fault in ("missing_result", "missing_hook", "missing_passing_node", "foreign_passing_node", "wrong_hook",
                  "duplicate_hook", "outcome", "invariants", "source", "session"):
        bad = deepcopy(value)
        if fault == "missing_result": bad["case_results"] = []
        elif fault == "missing_hook": bad["hook_events"] = []
        elif fault == "missing_passing_node": bad["nodes"] = [row for row in bad["nodes"] if row["when"] != "call"]
        elif fault == "foreign_passing_node": bad["case_results"][0]["nodeid"] = "tests/test_foreign.py::test_pass"
        elif fault == "wrong_hook": bad["hook_events"][0]["hook_ref"] = "src/lqcd_agent/foreign.py:boundary"
        elif fault == "duplicate_hook": bad["hook_events"] *= 2
        elif fault == "outcome": bad["case_results"][0]["outcome"] = "committed_result_replay"
        elif fault == "invariants": bad["case_results"][0]["invariants"] = []
        elif fault == "source": bad["case_results"][0]["trace"]["proof"]["fault_sources"] = []
        else: bad["invocation_token"] = "f" * 64
        if fault == "missing_result":
            validate_pytest(bad, session, value["selection"])
            assert validate_runtime(bad, registry, inputs["specs"], matrix["scenarios"], ROOT) == []
        else:
            with pytest.raises(Invalid):
                validate_pytest(bad, session, value["selection"])
                validate_runtime(bad, registry, inputs["specs"], matrix["scenarios"], ROOT)
    outer = Session(ROOT, tmp_path / "outer-session", inputs["digests"])
    with pytest.raises(Invalid, match="invocation_token"):
        validate_pytest(value, outer, value["selection"])
    if pytest_evidence.ACTIVE:
        assert not [row for row in pytest_evidence.ACTIVE.value["case_results"] if row["case_id"] == CASE]
        assert not [row for row in pytest_evidence.ACTIVE.value["hook_events"] if row["case_id"] == CASE]
    observe("B00C28-REJECTIONS", {"kind": "boolean", "value": True}, INVARIANTS)


def test_lifecycle_accepts_both_canonical_shapes(native, monkeypatch):
    inputs = load_inputs()
    path = ROOT / "tests/phase_b/failpoint_registry.json"
    original = path.read_bytes()
    lifecycle.test_only_local_bindings_accept_complete_actual_result(native)
    matrix, registry = binding_candidate(inputs, [CASE])
    candidate = {**inputs, "matrix": matrix, "registry": registry}
    with monkeypatch.context() as context:
        context.setattr(lifecycle, "load_inputs", lambda: candidate)
        lifecycle.test_only_local_bindings_accept_complete_actual_result(native)
    assert path.read_bytes() == original
    observe("B00C28-LIFECYCLE", {"kind": "boolean", "value": True}, INVARIANTS)


def test_candidate_inventory_is_complete():
    inputs = load_inputs()
    owners = {row["failpoint_id"]: row["boundary_owner"] for row in inputs["registry"]["entries"]}
    cases = [cid for cid, spec in inputs["specs"].items() if owners[spec["failpoint_id"]] == "B04"]
    assert len(cases) == 144 and len({inputs["specs"][cid]["failpoint_id"] for cid in cases}) == 18
    matrix, registry = binding_candidate(inputs, cases)
    validate_matrix(matrix, inputs["catalog"], ROOT)
    validate_inventory(registry, inputs["obligations"], inputs["protocol"], ROOT, matrix["scenarios"])
    assert matrix["implementation_slices"] == inputs["matrix"]["implementation_slices"]
    actual = [row["case_id"] for entry in registry["entries"] if entry["boundary_owner"] == "B04" for row in entry["case_bindings"]]
    assert sorted(actual) == cases
    observe("B00C28-INVENTORY", {"kind": "boolean", "value": True}, INVARIANTS)
