"""Preserve case0.3 and validate the exact case0.4 post-claim replacement."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT, load_contracts
from harness.inventory import (case_specs, expected_inventory, expected_obligations,
                               expected_post_claim_dispositions, inventory_projection,
                               registry_skeleton, validate_inventory)
from harness.seals import (CASE_0_3_REGISTRY_INVENTORY_SHA256, CASE_0_3_FINAL_OBLIGATIONS_SHA256,
                           CASE_0_3_REGISTRY_RAW_SHA256, CASE_0_3_FINAL_OBLIGATIONS_RAW_SHA256)
from harness.strict_json import Invalid, digest, read, sha


def test_case_0_3_raw_and_semantic_baseline_is_still_readable():
    protocol, _ = load_contracts()
    registry_path = ROOT / "tests/phase_b/case_0_3_failpoint_registry.json"
    obligations_path = ROOT / "tests/phase_b/case_0_3_final_obligations.json"
    registry, obligations = read(registry_path), read(obligations_path)
    assert sha(registry_path.read_bytes()) == CASE_0_3_REGISTRY_RAW_SHA256
    assert sha(obligations_path.read_bytes()) == CASE_0_3_FINAL_OBLIGATIONS_RAW_SHA256
    assert digest(inventory_projection(registry)) == CASE_0_3_REGISTRY_INVENTORY_SHA256
    assert digest(obligations) == CASE_0_3_FINAL_OBLIGATIONS_SHA256
    assert inventory_projection(registry) == registry_skeleton(protocol, version="0.3")
    assert obligations == expected_obligations(protocol, version="0.3")
    assert len(case_specs(protocol, version="0.3")) == 2199


def test_case_0_4_replaces_exactly_twelve_unstarted_consumer_cases():
    protocol, _ = load_contracts()
    old, new = case_specs(protocol, version="0.3"), case_specs(protocol)
    disposition = read(ROOT / "tests/phase_b/post_claim_case_dispositions.json")
    assert disposition == expected_post_claim_dispositions(protocol)
    rows = disposition["replacements"]
    old_ids = {row["old"] for row in rows}
    new_ids = {row["new"] for row in rows}
    assert len(rows) == len(old_ids) == len(new_ids) == 12
    assert set(old) - set(new) == old_ids and set(new) - set(old) == new_ids
    assert {cid: spec for cid, spec in old.items() if cid not in old_ids} == {
        cid: spec for cid, spec in new.items() if cid not in new_ids}
    assert sum(old[row["old"]]["outcome"] != new[row["new"]]["outcome"] for row in rows) == 6
    assert all(new[row["new"]]["outcome"] == row["new_outcome"] for row in rows)
    assert all("started_intent:null" in new[row["new"]]["invariants"] and
               "stop_proof:not_dispatched" in new[row["new"]]["invariants"] and
               "stop_adapter_calls:0" in new[row["new"]]["invariants"] for row in rows)
    assert expected_inventory(protocol, version="0.3") == expected_inventory(protocol)
    owners = {entry["failpoint_id"]: entry["boundary_owner"] for entry in expected_inventory(protocol)}
    assert {owner: sum(owners[spec["failpoint_id"]] == owner for spec in new.values())
            for owner in ("B02", "B03", "B04")} == {"B02": 1410, "B03": 645, "B04": 144}
    assert len(new) == 2199 and sum(cid.startswith("post_claim.") for cid in new) == 28


def test_case_0_4_disposition_tampering_is_rejected(monkeypatch):
    from harness import strict_json

    original = strict_json.read

    def changed(path):
        value = original(path)
        if str(path).endswith("post_claim_case_dispositions.json"):
            value = deepcopy(value)
            value["replacements"][0]["new_outcome"] = "unavailable_closure"
        return value

    monkeypatch.setattr(strict_json, "read", changed)
    protocol, _ = load_contracts()
    with pytest.raises(Invalid, match="complete_old_to_new"):
        validate_inventory(registry_skeleton(protocol), expected_obligations(protocol), protocol, ROOT, [])
