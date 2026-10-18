"""Original corrupt or missing sources remain faults, not restored authority."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT
from harness.fault_source_trace import anchor_directory, source_bundle, evidence_bytes, read_value_bytes
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.b04_process_binding import run_fault_case


CASES = {
    "missing_capability": "budget.resource_settled.after.non_materializable_domain_gap",
    "corrupt_member": "artifact.projection_publication.before.integrity_conflict",
}


@pytest.mark.parametrize("mode", CASES)
def test_original_fault_sources(mode):
    case = CASES[mode]
    native = run_fault_case(case)
    value = read(native / "0/required-pytest.json")
    raw = value["observations"][0]["trace"]
    compare(raw, read(ROOT / "tests/phase_b/expected_traces/b00c26" / (mode + ".json")), binding=value)
    directory = anchor_directory(value, case)
    bundle = source_bundle(directory, value, case)
    assert bundle["stage_facts"][0]["valid"] is True
    assert all(not row["valid"] for row in bundle["stage_facts"][1:])
    assert len(bundle["declaration"]["fault_observation"]["targets"]) == 1
    assert bundle["recovery"]["result"] == "rejected_original_authority"
    assert all(call["exception_type"] == "ControlIntegrityError" for call in bundle["calls"])
    assert not bundle["repeat"]["new_business_effects"]
    original = read_value_bytes(evidence_bytes(directory, "original-before-raw.json"))
    with pytest.raises(Invalid): normalize(original, binding=value)
    old = deepcopy(raw)
    old["schema_version"], old["proof"]["schema_version"] = "0.11", "0.8"
    old["proof"].pop("fault_sources")
    with pytest.raises(Invalid): normalize(old, binding=value)
    assert len(bundle["stages"][0]["events"]) > 10
    observe("B00C26-" + mode.upper(), {"kind": "boolean", "value": True},
            ["native_fault_source", "original_rejection", "source_bound_trace"])


def test_explicit_source_probe_cannot_enter_from_another_node(monkeypatch):
    from helpers.b04_fault_sources import SOURCE_MODE, before_fault
    monkeypatch.setenv(SOURCE_MODE, "0.12")
    with pytest.raises(Invalid, match="native_node"):
        before_fault(None, None, {"case_id": CASES["missing_capability"], "nodeid": "foreign"}, None, None, None)


def test_actual_fault_kind_and_material_change_are_visible():
    from harness.fault_source_trace import manifest_file, owner_location
    from lqcd_agent.control.strict_json import loads
    values, policies = [], []
    for side in ("allow", "halt"):
        case = "budget.invalid_response_" + side + ".after.committed_result_replay"
        native = run_fault_case(case, fresh_count=1)
        envelope = read(native / "0/required-pytest.json")
        directory = anchor_directory(envelope, case)
        from harness.fault_source_trace import capture_records
        _, records, manifests = capture_records(directory, envelope, case)
        _, _, _, run = owner_location(records, manifests)
        policies.append(loads(manifest_file(directory, manifests[0], run + "/budget_policy.json")))
        normalized = normalize(envelope["observations"][0]["trace"], binding=envelope)
        values.append([row["execution_head"] for row in normalized["events"] if row["event"] == "budget:policy_initialized"])
    assert policies[0] != policies[1]
    assert values[0] and values[1] and values[0] != values[1]
    snapshots = []
    for outcome in ("committed_result_replay", "non_materializable_domain_gap"):
        case = "budget.resource_settled.after." + outcome
        native = run_fault_case(case, fresh_count=1)
        envelope = read(native / "0/required-pytest.json")
        normalized = normalize(envelope["observations"][0]["trace"], binding=envelope)
        snapshots.append(next(row["guard"] for row in normalized["events"] if row["event"] == "fault_source_recovery"))
    assert snapshots == ["none", "row_delete"]


def test_corrupt_ledger_keeps_the_actual_parser_rejection():
    from harness.fault_source_trace import capture_records, private_view
    case = "budget.invalid_response_allow.before.integrity_conflict"
    native = run_fault_case(case)
    value = read(native / "0/required-pytest.json")
    directory = anchor_directory(value, case)
    bundle = source_bundle(directory, value, case)
    assert all(row["rejection"]["validator"] == "lqcd_agent.control.execution.parse_ledger"
               for row in bundle["stage_facts"][1:])
    assert bundle["recovery"]["result"]["operation_status"] in ("failed", "recovery_required")
    assert all(call["exception_type"] is None for call in bundle["calls"])
    _, _, manifests = capture_records(directory, value, case)
    with private_view(directory, manifests[1], resolve=True):
        assert normalize(bundle["source"], binding=value)
    assert normalize(value["observations"][0]["trace"], binding=value)
