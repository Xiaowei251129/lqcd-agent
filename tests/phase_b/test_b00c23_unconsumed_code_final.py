"""Original unconsumed sources remain distinct from registration and safe closure."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.trace_sources import current_binding
from helpers.unconsumed_code_final_sources import product_unconsumed_trace


MODES = ("normal", "attached", "non_success", "halt", "integrity", "late_integrity", "usage_overage",
         "missing_termination", "missing_empty", "missing_drain", "missing_stability", "missing_writes",
         "resume_failure", "consumer_overrun", "consumer_unsafe", "consumer_authority")
INVARIANTS = sorted(["B04_owned_false", "original_unconsumed_source", "no_effect_reexecution",
                     "separate_stop_authorities", "unknown_usage_preserved", "closed_source_provenance"])


@pytest.mark.parametrize("mode", MODES)
def test_dual_fresh_unconsumed_source(mode):
    expected = read(ROOT / "tests/phase_b/expected_traces/b00c24" / (mode + ".json"))
    values = []
    for _ in range(2):
        raw, root, facts = product_unconsumed_trace(mode)
        compare(raw, expected, binding=current_binding())
        values.append(normalize(raw, binding=current_binding()))
        assert facts["dispatches"] == facts["ordinary_calls"] == 1 and facts["readonly_replay"]
        assert not facts["Code_registered"] and not facts["Analysis_registered"] and not facts["B04_owned"]
        if mode.startswith("missing_"):
            assert facts["response_status"] == "recovery_required" and facts["run_status"] == "paused"
            field = {"termination": "termination_or_not_dispatched", "empty": "verify_empty", "drain": "bounded_drain",
                     "stability": "post_stop_stability", "writes": "write_lease_revocation"}[mode.removeprefix("missing_")]
            assert facts["stop_dimensions"][field] not in (True, "confirmed")
        elif mode in ("consumer_unsafe", "consumer_authority"):
            assert facts["resolution_owner"] == "normal" and facts["response_status"] == "recovery_required"
            assert facts["run_status"] == "running" and facts["stop_dimensions"]["termination_or_not_dispatched"] == "confirmed"
            assert facts["consumer_stop"] == ("unavailable" if mode == "consumer_unsafe" else "safe_stop")
            assert facts["run_authority"] == ("unavailable" if mode == "consumer_authority" else "appendable")
        elif mode in ("resume_failure", "consumer_overrun", "late_integrity", "usage_overage", "integrity"):
            assert facts["run_status"] == "failed"
        assert facts["verification_calls"] == int(mode == "consumer_overrun")
        print("C24_ORIGINAL_SOURCE", mode, root)
    assert values[0] == values[1]
    observe("B00C24-" + mode.upper(), {"kind": "boolean", "value": True}, INVARIANTS, raw)


@pytest.fixture(scope="module")
def attached():
    return product_unconsumed_trace("attached")[0]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "foreign_owner", "foreign_run", "foreign_attempt", "foreign_workspace",
    "epoch", "revision", "phase", "parent", "task", "manifest", "receipt", "seal", "audit", "patch", "final", "reservation",
    "terminal_owner", "pause", "stage", "extra_field", "stale_session"])
def test_unconsumed_declaration_rejects_missing_or_foreign_source(attached, fault):
    raw = deepcopy(attached)
    declaration = raw["proof"]["unconsumed_code_sources"][0]
    producer = declaration["producer_snapshot"]
    if fault == "missing": raw["proof"]["unconsumed_code_sources"].clear()
    elif fault == "duplicate": raw["proof"]["unconsumed_code_sources"].append(deepcopy(declaration))
    elif fault == "foreign_owner": declaration["producer_operation_id"] = "foreign"
    elif fault == "foreign_run": producer["run_locator"]["run_id"] = "foreign"
    elif fault == "foreign_attempt": producer["attempt_id"] = "foreign"
    elif fault == "foreign_workspace": producer["workspace_id"] = "foreign"
    elif fault == "epoch": producer["lease_epoch"] += 1
    elif fault == "revision": producer["phase_revision"] += 100
    elif fault == "phase": producer["operation_phase"] = "fabricated_registration"
    elif fault == "parent": producer["parent_control_operation_id"] = "foreign"
    elif fault in ("task", "manifest", "receipt", "seal", "patch", "final", "reservation"):
        declaration[fault + "_head"] = "a" * 64
    elif fault == "audit": declaration["tool_audit_head"] = "a" * 64
    elif fault == "terminal_owner": declaration["terminal_operation_id"] = "foreign"
    elif fault == "pause": declaration["pause_snapshot"] = []
    elif fault == "stage": declaration["publication_stage"] = "normal_final_unconsumed"
    elif fault == "extra_field": declaration["registered"] = True
    else: raw["proof"]["binding"]["invocation_token"] = "stale"
    with pytest.raises(Invalid): normalize(raw, binding=current_binding())


def test_old_version_retains_its_unconsumed_source_rejection(attached):
    raw = deepcopy(attached)
    raw["schema_version"], raw["proof"]["schema_version"] = "0.10", "0.7"
    raw["proof"].pop("unconsumed_code_sources")
    raw["events"] = [e for e in raw["events"] if e["event"] != "unconsumed_code_final"]
    with pytest.raises(Invalid): normalize(raw, binding=current_binding())


def test_actual_material_change_reaches_the_normalized_result(attached):
    changed, _, _ = product_unconsumed_trace("attached", requirement="Compute a different approved synthetic observable")
    assert normalize(changed, binding=current_binding()) != normalize(attached, binding=current_binding())
