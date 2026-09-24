"""A05 trace provenance checks; contract fixtures never claim Backend coverage."""
from copy import deepcopy

import pytest

from harness.strict_json import Invalid
from harness.trace import normalize
from harness.trace import compare
from harness.contracts import ROOT
from harness.strict_json import read
from harness.pytest_evidence import observe
from helpers.a05_traces import prestart_trace, full_trace, rebind
from helpers.trace_sources import current_binding
from test_b03_task_trace_boundary import immutable_base


def normalized(trace):
    return normalize(trace, binding=current_binding())


def test_prestart_two_fresh_roots_have_one_exact_trace():
    base = immutable_base()
    first, a = prestart_trace(base)
    second, b = prestart_trace(base)
    assert a["task"]["task_digest"] != b["task"]["task_digest"]
    assert normalized(first) == normalized(second)


@pytest.mark.parametrize("outcome", ["normal", "timeout", "failed", "unavailable"])
def test_complete_contract_chain_is_exact_across_roots_and_clocks(outcome):
    base = immutable_base()
    first, _ = full_trace(base, outcome=outcome, clock=100)
    second, _ = full_trace(base, outcome=outcome, clock=200)
    assert normalized(first) == normalized(second)


@pytest.mark.parametrize("outcome", ["normal", "timeout", "failed", "unavailable"])
def test_reviewed_full_chain_golden(outcome):
    first, _ = full_trace(outcome=outcome, clock=100)
    second, _ = full_trace(outcome=outcome, clock=200)
    expected = read(ROOT / f"tests/phase_b/expected_traces/a05_{outcome}.json")
    for trace in (first, second):
        compare(trace, expected, binding=current_binding())
    observe("B00-A05-" + outcome.upper(), {"kind": "boolean", "value": True},
            ["exact_semantic_trace", "raw_source_validation", "session_bound_proof"], first)


@pytest.mark.parametrize("field", ["task_digest", "manifest_digest", "seal_digest", "bundle_digest",
                                  "analysis_spec_digest", "result_digest", "binding_digest"])
@pytest.mark.parametrize("value", ["not-a-digest", "a" * 64])
def test_top_level_digest_requires_exact_source(field, value):
    trace, _ = prestart_trace()
    trace["events"][-1][field] = value
    with pytest.raises(Invalid):
        normalized(trace)


@pytest.mark.parametrize("fault", ["checksum", "missing", "duplicate", "kind", "mixed_version", "raw_bytes"])
def test_prestart_source_proof_rejects_forgery(fault):
    trace, _ = prestart_trace()
    if fault == "checksum":
        trace["proof"]["objects"][-3]["value"]["task_digest"] = "a" * 64
    elif fault == "missing":
        trace["proof"]["typed_sources"].pop()
    elif fault == "duplicate":
        trace["proof"]["typed_sources"].append(deepcopy(trace["proof"]["typed_sources"][0]))
    elif fault == "kind":
        trace["proof"]["typed_sources"][0]["kind"] = "manifest"
    elif fault == "mixed_version":
        trace["proof"]["schema_version"] = "0.1"
    else:
        trace["proof"]["objects"][-3]["value"]["requirements"] = ["forged content"]
    with pytest.raises(Invalid):
        normalized(trace)


@pytest.mark.parametrize("kind,field,value", [
    ("task", "requirements", ["Different task"]),
    ("task", "network_policy", {"enabled": True}),
    ("task", "base_revision", "a" * 40),
    ("task", "task_summary", {"created_at": 42}),
    ("seal", "write_lease_revoked", False),
    ("code_result", "status", "failed"),
    ("external_final", "lease_epoch", 2),
    ("external_operation", "phase_revision", 11),
    ("analysis_spec", "effective_tree_digest", "b" * 64),
])
def test_material_changes_survive_rehashed_proof(kind, field, value):
    trace, _ = full_trace()
    changed = rebind(trace, kind, lambda v: v.update({field: value}))
    original = normalized(trace)
    try:
        projected = normalized(changed)
    except Invalid:
        return
    assert original != projected


@pytest.mark.parametrize("kind,field,value", [
    ("core", "producer_operation_id", "foreign"),
    ("manifest", "task_id", "foreign:code_task"),
    ("seal", "workspace_id", "foreign_workspace"),
    ("external_result", "provider_operation_reference", "conflicting_job"),
    ("analysis_spec", "source_code_attempt_id", "foreign_attempt"),
    ("pause_binding", "pause_id", "foreign_pause"),
])
def test_rehashed_foreign_bindings_are_rejected(kind, field, value):
    trace, _ = full_trace()
    changed = rebind(trace, kind, lambda v: v.update({field: value}))
    with pytest.raises(Invalid):
        normalized(changed)


def test_registry_member_size_is_verified_before_projection():
    trace, _ = full_trace()
    changed = rebind(trace, "code_bundle", lambda v: v["members"][0].update(size_bytes=1))
    with pytest.raises(Invalid):
        normalized(changed)


def test_typed_clock_must_be_ordered():
    trace, _ = full_trace()
    changed = rebind(trace, "verification", lambda v: v["results"][0].update(finished_at=0))
    with pytest.raises(Invalid):
        normalized(changed)


def test_verification_command_is_material_even_with_rehashed_bytes():
    trace, _ = full_trace()
    changed = rebind(trace, "verification", lambda v: v["results"][0].update(argv=["unapproved-tool"]))
    assert normalized(trace) != normalized(changed)


def test_whole_object_hash_cannot_replace_self_checksum():
    trace, _ = prestart_trace()
    declaration = trace["proof"]["typed_sources"][0]
    trace["events"][-1]["task_digest"] = declaration["source_sha256"]
    with pytest.raises(Invalid, match="algorithm"):
        normalized(trace)


def test_self_checksum_cannot_replace_member_byte_hash():
    trace, values = full_trace()
    changed = rebind(trace, "code_bundle", lambda v: v["members"][2].update(sha256=values["code_result"]["result_digest"]))
    with pytest.raises(Invalid):
        normalized(changed)


@pytest.mark.parametrize("fault", ["event", "missing", "kind"])
def test_artifact_digest_requires_source_and_identity(fault):
    trace, _ = full_trace()
    artifact = trace["events"][-2]["artifacts"][0]
    if fault == "event":
        artifact["artifact_id"] = "foreign:code"
    elif fault == "missing":
        artifact["digest"] = "a" * 64
    else:
        artifact["digest"] = trace["events"][-2]["result_digest"]
    with pytest.raises(Invalid):
        normalized(trace)


def test_failure_identity_requires_exact_consumption_owner():
    trace, _ = full_trace(outcome="failed")
    changed = rebind(trace, "failure_identity", lambda v: v.update(owner="foreign"))
    with pytest.raises(Invalid, match="failure_owner"):
        normalized(changed)


def test_material_string_cannot_claim_workspace_projection():
    trace, _ = full_trace()
    path = trace["proof"]["workspace_roots"][0]["path"]
    changed = rebind(trace, "verification", lambda v: v.update(message=path))
    with pytest.raises(Invalid, match="material_path"):
        normalized(changed)


def test_nested_control_envelope_requires_external_final_source():
    trace, _ = full_trace()
    changed = rebind(trace, "control_envelope", lambda v: v["request"]["input_snapshot"].update(external_final_digest="a" * 64))
    with pytest.raises(Invalid, match="missing_source"):
        normalized(changed)
