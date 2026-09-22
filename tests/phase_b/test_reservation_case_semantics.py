"""Versioned case semantics retain every boundary and explain every replacement."""
import pytest

from harness.contracts import ROOT, load_contracts
from harness.inventory import (case_specs, expected_dispositions, expected_inventory, expected_obligations,
                               registry_skeleton, validate_inventory)
from harness.pytest_evidence import observe
from harness.seals import LEGACY_REGISTRY_INVENTORY_SHA256, LEGACY_FINAL_OBLIGATIONS_SHA256
from harness.strict_json import Invalid, digest, read


def test_closed_reservation_case_dispositions():
    protocol, _ = load_contracts()
    before, after = case_specs(protocol, version="0.1"), case_specs(protocol)
    old, new = expected_inventory(protocol, version="0.1"), expected_inventory(protocol)
    assert digest(registry_skeleton(protocol, version="0.1")) == LEGACY_REGISTRY_INVENTORY_SHA256
    assert digest(expected_obligations(protocol, version="0.1")) == LEGACY_FINAL_OBLIGATIONS_SHA256
    assert [(e["failpoint_id"], e["boundary_owner"], e["source_locator"]) for e in old] == [
        (e["failpoint_id"], e["boundary_owner"], e["source_locator"]) for e in new]
    foreign = {e["failpoint_id"] for e in old if e["boundary_owner"] != "B02"}
    assert [e for e in old if e["failpoint_id"] in foreign] == [e for e in new if e["failpoint_id"] in foreign]
    assert {c: s for c, s in before.items() if s["failpoint_id"] in foreign} == {
        c: s for c, s in after.items() if s["failpoint_id"] in foreign}
    dispositions = read(ROOT / "tests/phase_b/reservation_case_dispositions.json")
    assert dispositions == expected_dispositions(protocol)
    rows = dispositions["dispositions"]
    assert {r["old_case_id"] for r in rows} == {c for c, s in before.items() if s["failpoint_id"] not in foreign}
    assert {c for r in rows for c in r["new_case_ids"]} == {c for c, s in after.items() if s["failpoint_id"] not in foreign}
    replaced = [r for r in rows if r["disposition"] == "replaced"]
    assert len(replaced) == 126 and len(after) == len(before) - 78
    for row in rows:
        if row["disposition"] == "retained":
            assert before[row["old_case_id"]] == after[row["old_case_id"]]
        else:
            assert row["counterexample_nodeid"]
            assert after[row["new_case_ids"][0]]["outcome"] == {
                "initial_reservation_before_commit": "reservation_rolled_back",
                "unavailable_only_successor_graph": "terminal_tombstone_replay"}[row["authority_context"]]
    assert sum(c.startswith("post_claim.") for c in after) == 28
    observe("B00-RESERVATION-001", {"kind": "boolean", "value": True},
            ["closed_case_dispositions", "independent_version_and_seals", "unchanged_foreign_obligations"])


@pytest.mark.parametrize("fault", ["old_registry", "old_obligations", "removed_case", "wrong_outcome", "changed_owner"])
def test_case_version_and_independent_seals_reject_downgrades(fault):
    protocol, _ = load_contracts()
    registry, obligations = registry_skeleton(protocol), expected_obligations(protocol)
    if fault == "old_registry":
        registry = registry_skeleton(protocol, version="0.1")
    elif fault == "old_obligations":
        obligations = expected_obligations(protocol, version="0.1")
    elif fault == "removed_case":
        obligations["runtime_obligations"][0]["case_ids"].pop()
    elif fault == "wrong_outcome":
        next(e for e in registry["entries"] if e["failpoint_id"].endswith(".operation_reserved"))["allowed_exact_outcomes"] = ["integrity_conflict"]
    else:
        registry["entries"][0]["boundary_owner"] = "B02"
    with pytest.raises(Invalid):
        validate_inventory(registry, obligations, protocol, ROOT, [])


@pytest.mark.parametrize("variant", ["resume_run.continue_execution", "cancel_pause.not_applicable",
    "resolve_external_interrupt.recoverable_timeout", "resolve_external_interrupt.controlled_halt", "resolve_external_interrupt.integrity_failure"])
def test_unavailable_branch_cannot_replay_a_committed_result(variant):
    from test_pause_control import control
    from test_external_control import SyntheticExternalStop, external_source, external_pause_request
    from test_external_consumption_control import normal_external, ExternalDomainFailure
    from test_timeout_consumption_control import timeout_source, DomainTimeout
    from lqcd_agent.control.pause import CancelPauseRequest, ResolveExternalInterruptRequest
    from lqcd_agent.control.strict_json import canonical_bytes, digest as control_digest
    resume = variant.startswith("resume_run")
    timeout = variant.endswith("recoverable_timeout")
    fixture = (normal_external if resume else timeout_source if timeout else control).__wrapped__()
    context = next(fixture)
    coordinator, plane, actor, locator = context[:4]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    try:
        if resume:
            plane.resume_target_adapter = plane.external_adapter = ExternalDomainFailure(root, safe=False)
            request, method = context[4], plane.resume_run
        elif timeout:
            request, method = context[5], plane.resolve_external_interrupt
            plane.external_adapter = DomainTimeout(safe=False)
        else:
            external_source(context)
            plane.publish_pause(external_pause_request(locator), actor=actor)
            plane.external_adapter = SyntheticExternalStop(safe=False)
            if variant.startswith("cancel_pause"):
                request, method = CancelPauseRequest(locator, "pause_000001", "unavailable", "operator_cancel"), plane.cancel_pause
            else:
                reason = "terminal_operator_stop" if variant.endswith("controlled_halt") else "proven_integrity_trigger"
                trigger = {"run_locator": locator, "producer_operation_id": "producer_code", "reason": reason}
                (root / "synthetic_interrupt.json").write_bytes(canonical_bytes(trigger))
                request = ResolveExternalInterruptRequest(locator, "producer_code", reason, "synthetic_interrupt.json", control_digest(trigger))
                method = plane.resolve_external_interrupt
        result = method(request, actor=actor)
        assert result["operation_status"] == "recovery_required" and result["result"] is None
        assert result["terminal_closure"] == "unavailable" and result["run_status"] is None
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert method(request, actor=actor) == result
        assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        protocol, _ = load_contracts()
        phases = {row["phase"] for row in coordinator.history(result["operation_id"])}
        for entry in expected_inventory(protocol):
            if entry["failpoint_id"].startswith("control." + variant + ".") and "terminal_tombstone_replay" in entry["allowed_exact_outcomes"]:
                assert entry["failpoint_id"].rsplit(".", 1)[1] in phases
    finally:
        fixture.close()
