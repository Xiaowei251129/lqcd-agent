"""External initial rollback is distinct from retained durable recovery contexts."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT, load_contracts
from harness.inventory import (EXTERNAL_INITIAL, case_specs, expected_external_dispositions,
                               expected_inventory, expected_obligations, registry_skeleton, validate_inventory)
from harness.pytest_evidence import observe
from harness.seals import CASE_0_2_REGISTRY_INVENTORY_SHA256, CASE_0_2_FINAL_OBLIGATIONS_SHA256
from harness.strict_json import Invalid, digest, read


def test_external_initial_case_dispositions():
    protocol, _ = load_contracts()
    old, new = case_specs(protocol, version="0.2"), case_specs(protocol)
    assert digest(registry_skeleton(protocol, version="0.2")) == CASE_0_2_REGISTRY_INVENTORY_SHA256
    assert digest(expected_obligations(protocol, version="0.2")) == CASE_0_2_FINAL_OBLIGATIONS_SHA256
    assert {c: s for c, s in old.items() if s["failpoint_id"] not in EXTERNAL_INITIAL} == {
        c: s for c, s in new.items() if s["failpoint_id"] not in EXTERNAL_INITIAL}
    assert [(r["failpoint_id"], r["boundary_owner"]) for r in expected_inventory(protocol, version="0.2")] == [
        (r["failpoint_id"], r["boundary_owner"]) for r in expected_inventory(protocol)]
    dispositions = read(ROOT / "tests/phase_b/external_reservation_case_dispositions.json")
    assert dispositions == expected_external_dispositions(protocol)
    rows = dispositions["dispositions"]
    assert {r["old_case_id"] for r in rows} == {c for c, s in old.items() if s["failpoint_id"] in EXTERNAL_INITIAL}
    assert {c for r in rows for c in r["new_case_ids"]} == {c for c, s in new.items() if s["failpoint_id"] in EXTERNAL_INITIAL}
    assert len(rows) == 16 and sum(r["disposition"] == "replaced" for r in rows) == 12
    for row in rows:
        assert row["runtime_owner"] == "B03" and row["counterexample_nodeid"]
        assert row["protection_case_id"] in new
        if row["disposition"] == "retained":
            assert old[row["old_case_id"]] == new[row["old_case_id"]]
            assert row["cut"] == "after-commit"
        else:
            spec = new[row["new_case_ids"][0]]
            assert spec["outcome"] == "reservation_rolled_back"
            assert "parent_run_and_target_preserved" in spec["invariants"]
            assert "no_owner_or_capability" not in spec["invariants"]
    counts = {owner: sum(s["failpoint_id"] in {r["failpoint_id"] for r in expected_inventory(protocol)
                  if r["boundary_owner"] == owner} for s in new.values()) for owner in ("B02", "B03", "B04")}
    assert counts == {"B02": 1410, "B03": 645, "B04": 144} and len(new) == 2199
    assert sum(c.startswith("post_claim.") for c in new) == 28
    observe("B00-EXTERNAL-RESERVATION-001", {"kind": "boolean", "value": True},
            ["case_0_2_seals_preserved", "durable_protections_retained", "external_initial_dispositions"])


@pytest.mark.parametrize("fault", ["registry_0_2", "obligations_0_2", "precommit_replay", "postcommit_rollback", "missing_durable"])
def test_external_case_semantics_reject_mixed_or_weakened_inputs(fault):
    protocol, _ = load_contracts()
    registry, obligations = registry_skeleton(protocol), expected_obligations(protocol)
    if fault == "registry_0_2":
        registry = registry_skeleton(protocol, version="0.2")
    elif fault == "obligations_0_2":
        obligations = expected_obligations(protocol, version="0.2")
    else:
        row = next(r for r in obligations["runtime_obligations"] if r["obligation_id"] == "external.external_operation_reserved")
        if fault == "precommit_replay":
            row["case_ids"].append("external.external_operation_reserved.before.committed_result_replay")
        elif fault == "postcommit_rollback":
            row["case_ids"].append("external.external_operation_reserved.after.reservation_rolled_back")
        else:
            row["case_ids"].remove("external.external_operation_reserved.after.integrity_conflict")
    with pytest.raises(Invalid):
        validate_inventory(registry, obligations, protocol, ROOT, [])


def test_external_disposition_tampering_is_rejected(monkeypatch):
    from harness import strict_json
    original = strict_json.read
    def changed(path):
        value = original(path)
        if str(path).endswith("external_reservation_case_dispositions.json"):
            value = deepcopy(value)
            value["dispositions"][0]["protection_case_id"] = "missing"
        return value
    monkeypatch.setattr(strict_json, "read", changed)
    protocol, _ = load_contracts()
    with pytest.raises(Invalid, match="complete_old_to_new"):
        validate_inventory(registry_skeleton(protocol), expected_obligations(protocol), protocol, ROOT, [])
