"""The approved recovery CAS and scoped Host identities retain their provenance."""
from copy import deepcopy
import uuid

import pytest

from harness.contracts import ROOT
from harness.fault_source_trace import anchor_directory, source_bundle, identity_state
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare
from helpers.b04_process_binding import run_fault_case
from helpers.host_identity_fixture import HostIdentities


CASES = {
    "budget_cas": "budget.resource_settled.after.committed_result_replay",
    "started_cas": "artifact.transition_before_target_started.after.materializable_publication_prefix",
    "human_allow": "budget.invalid_response_allow.after.committed_result_replay",
    "human_halt": "budget.invalid_response_halt.after.committed_result_replay",
}


@pytest.mark.parametrize("mode", CASES)
def test_original_recovery_contract(mode):
    case = CASES[mode]
    root = run_fault_case(case)
    value = read(root / "0/required-pytest.json")
    raw = value["observations"][0]["trace"]
    compare(raw, read(ROOT / "tests/phase_b/expected_traces/b00c27" / (mode + ".json")), binding=value)
    bundle = source_bundle(anchor_directory(value, case), value, case)
    assert all(row["valid"] for row in bundle["stage_facts"])
    if mode.endswith("cas"):
        delta, = bundle["repeat"]["cas"]
        assert (delta["before_revision"], delta["after_revision"], delta["successful_saves"]) == (
            (11, 12, 1) if mode == "budget_cas" else (4, 5, 1))
        assert not bundle["allocations"]
    else:
        assert not bundle["repeat"]["cas"]
        allocation = next(row for row in bundle["allocations"] if row["allocation_site"] == "lqcd_agent.control.coordinator")
        operation = "control_" + allocation["uuid"].replace("-", "")
        child = next(row for row in bundle["recovery"]["operation_results"] if row["operation_id"] == operation)
        assert child["operation_type"] == ("publish_pause" if mode == "human_allow" else "close_run")
        assert any(row["operation_id"] == operation for row in bundle["stages"][2]["events"])
    assert not bundle["repeat"]["new_business_effects"]
    observe("B00C27-" + mode.upper(), {"kind": "boolean", "value": True},
            ["exact_recovery_bookkeeping", "original_host_identity", "source_bound_trace"])


@pytest.mark.parametrize("fault", ["namespace", "ordinal", "duplicate", "uuid", "site"])
def test_allocation_is_derived_from_actual_case_and_continuous_ordinal(fault):
    case = CASES["human_allow"]
    host = HostIdentities("b00c27-parent-recovery:" + case)
    with host.installed():
        from lqcd_agent.control import coordinator
        coordinator.uuid.uuid4()
    value = {"namespace": host.scenario_id, "ordinals": dict(host.ordinals), "allocations": deepcopy(host.allocations)}
    assert identity_state(value, case)
    if fault == "namespace": value["namespace"] = "foreign"
    elif fault == "ordinal": value["allocations"][0]["ordinal"] += 1
    elif fault == "duplicate": value["allocations"].append(deepcopy(value["allocations"][0]))
    elif fault == "uuid": value["allocations"][0]["uuid"] = str(uuid.uuid4())
    else: value["allocations"][0]["allocation_site"] = "foreign"
    with pytest.raises(Invalid): identity_state(value, case)


def test_existing_host_provider_is_restored_after_exception():
    from lqcd_agent.control import coordinator
    original = coordinator.uuid
    host = HostIdentities("b00c27-parent-recovery:" + CASES["human_allow"])
    with pytest.raises(RuntimeError, match="actual scoped exception"):
        with host.installed():
            coordinator.uuid.uuid4()
            raise RuntimeError("actual scoped exception")
    assert coordinator.uuid is original
    with host.installed(): coordinator.uuid.uuid4()
    assert [row["ordinal"] for row in host.allocations] == [1, 2]
    assert coordinator.uuid is original


def test_rolled_back_callback_cannot_be_promoted_to_a_new_epoch():
    from harness.fault_source_trace import evidence_bytes, read_value_bytes
    from harness.trace import normalize
    case = "artifact.bundle_before_analysis_transition.after.committed_result_replay"
    root = run_fault_case(case, fresh_count=1)
    envelope = read(root / "0/required-pytest.json")
    raw = envelope["observations"][0]["trace"]
    directory = anchor_directory(envelope, case)
    process = read_value_bytes(evidence_bytes(directory, "process-source.json"))
    pending = [row for row in process["events"] if row["event"].startswith("control.") and row not in raw["events"]]
    assert pending
    after = read_value_bytes(evidence_bytes(directory, "S2-raw.json"))
    original = pending[-1]
    current = [row for row in after["events"] if row["operation_id"] == original["operation_id"] and
               row["phase_revision"] == original["phase_revision"]]
    assert current and all(row["lease_epoch"] > original["lease_epoch"] for row in current)
    bad = deepcopy(raw)
    promoted = deepcopy(original)
    promoted["lease_epoch"] = current[0]["lease_epoch"]
    bad["events"].append(promoted)
    with pytest.raises(Invalid): normalize(bad, binding=envelope)
    bad = deepcopy(raw)
    bad["proof"]["fault_sources"][0]["recovery_observation"]["first_call"] = None
    with pytest.raises(Invalid): normalize(bad, binding=envelope)


def test_atomic_index_recovery_consumes_only_frozen_temporary_bytes():
    from harness.fault_source_trace import capture_records, logical_state, recovery_difference
    from helpers.b04_publication_cases import SPECS
    case = "artifact.index_publication.before.committed_result_replay"
    root = run_fault_case(case)
    envelope = read(root / "0/required-pytest.json")
    directory = anchor_directory(envelope, case)
    _, records, manifests = capture_records(directory, envelope, case)
    states = [logical_state(directory, manifest) for manifest in manifests]
    result = recovery_difference(directory, records, manifests, states, SPECS[case])
    assert {"kind": "atomic_artifact_index_consumption", "target": "artifact_index.json"} in result["writes"]
    temporary, = [key for key in states[1].keys() - states[2].keys() if "/.artifact_index_" in key]
    bad = deepcopy(states)
    bad[1][temporary]["sha256"] = "0" * 64
    with pytest.raises(Invalid, match="original_atomic_index_consumption"):
        recovery_difference(directory, records, manifests, bad, SPECS[case])


def test_corrupt_index_does_not_publish_invalid_prefix_evidence():
    from harness.fault_source_trace import capture_records, evidence_bytes, read_value_bytes
    from harness.trace import normalize
    case = "budget.resource_settled.after.integrity_conflict"
    root = run_fault_case(case)
    envelope = read(root / "0/required-pytest.json")
    directory = anchor_directory(envelope, case)
    _, records, manifests = capture_records(directory, envelope, case)
    original = [row for row in manifests[0]["files"] if row["path"].startswith("trace_prefix_evidence/")]
    assert original
    for manifest, record in zip(manifests[1:], records[1:]):
        assert [row for row in manifest["files"] if row["path"].startswith("trace_prefix_evidence/")] == original
        assert record["observation"]["source"]["raw_sha256"] is None
        assert record["observation"]["source"]["rejection"]["type"] == "ControlIntegrityError"
    before = read_value_bytes(evidence_bytes(directory, "original-before-raw.json"))
    assert normalize(before, binding=envelope)
    bundle = source_bundle(directory, envelope, case)
    for fact in bundle['stage_facts'][1:]:
        assert not fact['valid']
        assert fact['rejection']['validator'] == 'lqcd_agent.control.strict_json.loads'
        assert fact['rejection']['type'] == 'ControlIntegrityError'
    assert normalize(envelope["observations"][0]["trace"], binding=envelope)


def test_advance_conflict_keeps_its_bound_unavailable_close():
    case = "budget.grant_transition.after.integrity_conflict"
    root = run_fault_case(case)
    envelope = read(root / "0/required-pytest.json")
    bundle = source_bundle(anchor_directory(envelope, case), envelope, case)
    result = bundle["recovery"]["result"]
    assert result["operation_status"] == "failed" and result["run_status"] is None
    assert result["terminal_closure"] == "unavailable"
    close, = [row for row in bundle["recovery"]["operation_results"] if row["operation_type"] == "close_run"]
    assert close["phase"] == "terminal_ownership_reserved" and close["status"] == "failed"
    assert not bundle["recovery"]["writes"] and not bundle["repeat"]["new_business_effects"]
    assert all(not row["valid"] for row in bundle["stage_facts"][1:])
    allocation, = bundle["allocations"]
    assert close["operation_id"] == "control_" + allocation["uuid"].replace("-", "")


def test_first_prefix_has_only_its_required_parent_directory():
    from harness.fault_source_trace import capture_records, logical_state, validate_calls
    case = "budget.resource_settled.before.committed_result_replay"
    root = run_fault_case(case)
    envelope = read(root / "0/required-pytest.json")
    directory = anchor_directory(envelope, case)
    _, records, manifests = capture_records(directory, envelope, case)
    states = [logical_state(directory, manifest) for manifest in manifests]
    parent, = [key for key in states[2].keys() - states[1].keys() if key.endswith("/trace_prefix_evidence")]
    assert states[2][parent]["type"] == "directory"
    assert validate_calls(directory, records, manifests, states)
    bad = deepcopy(states)
    bad[2][parent]["type"] = "file"
    with pytest.raises(Invalid, match="prefix_directory"):
        validate_calls(directory, records, manifests, bad)
    bad = deepcopy(states)
    bad[2][parent + "_unrelated"] = deepcopy(states[2][parent])
    with pytest.raises(Invalid, match="call_snapshot_continuity"):
        validate_calls(directory, records, manifests, bad)
