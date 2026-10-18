"""All four consumers use the same native Session and original production boundary."""
from copy import deepcopy
import os

import pytest

from harness.contracts import ROOT
from harness.exit_checks import Adapter, validate_exit
from harness.failpoints import validate_runtime
from harness.inputs import load_inputs
from harness.matrix import selected_scenarios
from harness.pytest_evidence import observe, observe_case, run_pytest, validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, sha, write_new
from harness.trace import compare
from helpers.trace_sources import current_binding
from helpers.unconsumed_code_final_sources import product_unconsumed_trace
from test_b00c23_unconsumed_code_final import INVARIANTS


MODES = ("attached", "missing_drain", "resume_failure", "consumer_overrun", "consumer_unsafe", "consumer_authority",
         "late_integrity", "usage_overage")


@pytest.mark.parametrize("mode", MODES)
def test_native_boundary_probe(mode):
    from harness.strict_json import read
    case = "b00c24.source." + mode
    runtime_meta = os.environ.get("LQCD_C24_NATIVE_META_MODE") == mode
    trace, _, facts = product_unconsumed_trace(mode, hook=case if runtime_meta else None)
    assert facts["dispatches"] == 1 and facts["readonly_replay"] and not facts["B04_owned"]
    compare(trace, read(ROOT / "tests/phase_b/expected_traces/b00c24" / (mode + ".json")), binding=current_binding())
    if runtime_meta:
        # Only the dedicated native Session emits this test-local runtime binding.
        observe("B00C24-PROBE-" + mode.upper(), {"kind": "boolean", "value": True}, INVARIANTS, trace)
        observe_case(case, "validated", INVARIANTS, trace)


@pytest.mark.parametrize("mode", MODES)
def test_same_native_trace_has_four_strict_consumers(tmp_path, monkeypatch, mode):
    inputs = load_inputs()
    node = "tests/phase_b/test_b00c23_trace_consumers.py::test_native_boundary_probe[" + mode + "]"
    case = "b00c24.source." + mode
    scenario = {"scenario_id": "B00C24-PROBE-" + mode.upper(), "pytest_nodeids": [node],
        "expected_result": {"kind": "boolean", "value": True}, "required_invariants": INVARIANTS,
        "expected_trace_fixture": "tests/phase_b/expected_traces/b00c24/" + mode + ".json"}
    registry = {"entries": [{"hook_ref": "src/lqcd_agent/control/coordinator.py:boundary",
        "case_bindings": [{"case_id": case, "scenario_ids": [scenario["scenario_id"]]}]}]}
    specs = {case: {"outcome": "validated", "invariants": INVARIANTS}}
    adapter = Adapter(lambda _: pytest.fail("Use the original native subprocess evidence"), (node,), (scenario,))
    session = Session(inputs["root"], tmp_path / "native-session", inputs["digests"])
    with monkeypatch.context() as context:
        context.setenv("LQCD_C24_NATIVE_META_MODE", mode)
        value = run_pytest(session, [node])

    def exit_digest(envelope, name):
        path = session.directory / (name + ".json")
        write_new(path, envelope)
        return validate_exit({"schema_version": "0.1", "invocation_token": session.token, "check_id": "layer_0",
            "digests": session.digests, "exit_code": 0,
            "evidence_refs": [{"relative_path": path.name, "sha256": sha(path.read_bytes())}]}, "layer_0", session, adapter)

    validate_pytest(value, session, [node])
    assert value["observations"][0]["trace"] == value["case_results"][0]["trace"]
    assert validate_observations(value, [scenario], ROOT) == {scenario["scenario_id"]}
    assert validate_runtime(value, registry, specs, [scenario], ROOT) == [case]
    exit_digest(value, "valid")
    faults = ["missing", "owner", "run", "attempt", "epoch", "revision", "receipt", "duplicate", "stage", "release", "stale"]
    failure = mode in ("resume_failure", "consumer_overrun", "consumer_unsafe", "consumer_authority")
    unaccepted = any('"profile":"unaccepted_backend_claim"' in row["content"]
                     for row in value["observations"][0]["trace"]["proof"]["material_sources"])
    assert unaccepted == (mode in ("missing_drain", "late_integrity"))
    if mode == "usage_overage":
        assert value["observations"][0]["trace"]["proof"]["unconsumed_code_sources"][0]["external_result_head"] is None
    if failure:
        faults += ["failure_missing", "failure_identity", "failure_settlement", "failure_closure", "failure_error_preimage"]
    if unaccepted:
        faults += ["claim_missing", "claim_binding", "claim_seal", "claim_result"]
    for fault in faults:
        bad = deepcopy(value)
        for field in ("observations", "case_results"):
            proof = bad[field][0]["trace"]["proof"]
            declaration = proof["unconsumed_code_sources"][0]
            if fault == "missing": proof["unconsumed_code_sources"].clear()
            elif fault == "owner": declaration["producer_operation_id"] = "foreign"
            elif fault == "run": declaration["producer_snapshot"]["run_locator"]["run_id"] = "foreign"
            elif fault == "attempt": declaration["producer_snapshot"]["attempt_id"] = "foreign"
            elif fault == "epoch": declaration["producer_snapshot"]["lease_epoch"] -= 1
            elif fault == "revision": declaration["producer_snapshot"]["phase_revision"] += 100
            elif fault == "receipt": declaration["receipt_head"] = "a" * 64
            elif fault == "duplicate": proof["unconsumed_code_sources"].append(deepcopy(declaration))
            elif fault == "stage": declaration["publication_stage"] = "fabricated_registration"
            elif fault == "release": declaration["producer_snapshot"]["consumption_release"] = {"owner": "fabricated"}
            elif fault == "stale": proof["binding"]["invocation_token"] = "stale"
            else:
                from harness.trace_proof import source_object
                from lqcd_agent.control.strict_json import canonical_bytes, loads, digest
                if fault.startswith("claim_"):
                    material = next(r for r in proof["material_sources"] if '"profile":"unaccepted_backend_claim"' in r["content"])
                    if fault == "claim_missing":
                        proof["material_sources"].remove(material)
                    else:
                        claim = loads(material["content"])
                        claim[fault.removeprefix("claim_")] = None
                        content = canonical_bytes(claim)
                        material.update(content=content.decode(), sha256=sha(content))
                else:
                    source = next(r for r in proof["objects"] if "durable_consumption_failure" in r["value"])
                    snapshot = source["value"]["durable_consumption_failure"]
                    if fault == "failure_missing":
                        proof["objects"].remove(source)
                    elif fault == "failure_error_preimage":
                        invented = {"owner": snapshot["owner"], "source_phase": snapshot["source_phase"],
                            "source_revision": snapshot["failure"]["source_phase_revision"],
                            "epoch": snapshot["failure"]["source_resume_owner_epoch"], "cause_type": "Error", "cause": "Invented"}
                        proof["objects"].append(source_object("canonical_json", invented, version="0.4"))
                        proof["typed_sources"].append({"kind": "failure_identity", "source_sha256": digest(invented)})
                    else:
                        if fault == "failure_identity": snapshot["failure"]["failure_id_digest"] = "a" * 64
                        elif fault == "failure_closure": snapshot["closure"] = "fabricated_release"
                        else:
                            snapshot["resource_settlements"] += snapshot["resource_settlements"] or [{"event": "fabricated_settlement"}]
                        old = source["sha256"]
                        source.update(source_object("canonical_json", source["value"], version="0.4"))
                        for event in bad[field][0]["trace"]["events"]:
                            if event["event"] == "consumption_failure_source":
                                assert event["result_digest"] == old
                                event["result_digest"] = source["sha256"]
        with pytest.raises(Invalid): validate_pytest(bad, session, [node])
        with pytest.raises(Invalid): validate_observations(bad, [scenario], ROOT)
        with pytest.raises(Invalid): validate_runtime(bad, registry, specs, [scenario], ROOT)
        with pytest.raises(Invalid): exit_digest(bad, fault)
    session.unchanged()


def test_formal_meta_keeps_original_owners_and_registry():
    inputs = load_inputs()
    selected = [s for s in selected_scenarios(inputs["matrix"], "final", None) if s["scenario_id"].startswith("B00C24-")]
    assert len(selected) == 16
    assert all(s["implementation_ticket_id"] == "B00" and s["contract_refs"] == ["A07-META-006", "A07-META-015"] for s in selected)
