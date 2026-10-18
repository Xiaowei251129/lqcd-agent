"""Durable failure identities and Backend claims cannot grant replacement authority."""
from copy import deepcopy
from hashlib import sha256
import sqlite3

import pytest

from harness.strict_json import Invalid
from harness.trace import normalize
from harness.trace_proof import source_object
from helpers.trace_sources import current_binding
from helpers.unconsumed_code_final_sources import product_unconsumed_trace
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads


@pytest.fixture(scope="module")
def failure():
    return product_unconsumed_trace("consumer_overrun")


@pytest.fixture(scope="module")
def unavailable():
    return product_unconsumed_trace("missing_drain")


@pytest.mark.parametrize("field", ["owner", "source_phase", "failure_id_digest", "source_phase_revision", "source_resume_owner_epoch",
    "original_normal_final_digest", "active_binding_generation", "consumer_stop", "authority", "closure", "resource_settlements",
    "active_settlements", "verification_reservations"])
def test_rehashed_failure_snapshot_still_requires_original_journal(failure, field):
    raw = deepcopy(failure[0])
    source = next(row for row in raw["proof"]["objects"] if "durable_consumption_failure" in row["value"])
    value = source["value"]["durable_consumption_failure"]
    target = value if field in value else value["failure"]
    target[field] = None
    new = source_object("canonical_json", source["value"], version="0.4")
    old = source["sha256"]
    source.update(new)
    for event in raw["events"]:
        if event["event"] == "consumption_failure_source":
            assert event["result_digest"] == old
            event["result_digest"] = new["sha256"]
    with pytest.raises(Invalid): normalize(raw, binding=current_binding())


@pytest.mark.parametrize("field", ["invocation_epoch", "state", "authorization", "started_intent", "verification_intents"])
def test_original_resume_capability_is_checked_independently(failure, field):
    raw, root, _ = failure
    identity = next(row["value"]["durable_consumption_failure"]["owner"] for row in raw["proof"]["objects"]
                    if "durable_consumption_failure" in row["value"])
    with sqlite3.connect(root / ".lqcd/control_operations.sqlite") as connection:
        old, = connection.execute("SELECT value FROM invocation_capabilities WHERE capability_id=?", ("capability_" + identity,)).fetchone()
        value = loads(old)
        value[field] = None
        try:
            connection.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?",
                               (canonical_bytes(value), "capability_" + identity))
            connection.commit()
            with pytest.raises(Invalid): normalize(raw, binding=current_binding())
        finally:
            connection.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?", (old, "capability_" + identity))
            connection.commit()
    assert normalize(raw, binding=current_binding())


@pytest.mark.parametrize("field", ["binding", "producer_operation_id", "task", "manifest", "receipt", "result",
                                 "change_manifest", "seal", "tool_audit", "patch"])
def test_rehashed_unaccepted_claim_cannot_replace_generated_material(unavailable, field):
    raw = deepcopy(unavailable[0])
    material = next(row for row in raw["proof"]["material_sources"] if '"profile":"unaccepted_backend_claim"' in row["content"])
    value = loads(material["content"])
    value[field] = "changed patch bytes" if field == "patch" else None
    content = canonical_bytes(value)
    material.update(content=content.decode(), sha256=sha256(content).hexdigest())
    with pytest.raises(Invalid): normalize(raw, binding=current_binding())


def test_backend_claim_requires_original_file_and_immutable_backend(unavailable):
    raw, root, _ = unavailable
    declaration = raw["proof"]["unconsumed_code_sources"][0]
    path = root / "trace_backend_claims" / (declaration["producer_operation_id"] + ".json")
    original = path.read_bytes()
    try:
        path.unlink()
        with pytest.raises(Invalid): normalize(raw, binding=current_binding())
    finally:
        path.write_bytes(original)
    with sqlite3.connect(root / "fake_backend/fake_backend.sqlite") as connection:
        old, = connection.execute("SELECT result FROM operations").fetchone()
        try:
            connection.execute("UPDATE operations SET result=?", (b"{}",))
            connection.commit()
            with pytest.raises(Invalid): normalize(raw, binding=current_binding())
        finally:
            connection.execute("UPDATE operations SET result=?", (old,))
            connection.commit()


def test_failure_has_no_fabricated_legacy_error_preimage(failure):
    raw = deepcopy(failure[0])
    original = next(row["value"]["durable_consumption_failure"] for row in raw["proof"]["objects"]
                    if "durable_consumption_failure" in row["value"])
    invented = {"owner": original["owner"], "source_phase": original["source_phase"],
        "source_revision": original["failure"]["source_phase_revision"], "epoch": original["failure"]["source_resume_owner_epoch"],
        "cause_type": "ControlIntegrityError", "cause": "Invented error preimage"}
    assert digest(invented) != original["failure"]["failure_id_digest"]
    raw["proof"]["objects"].append(source_object("canonical_json", invented, version="0.4"))
    raw["proof"]["typed_sources"].append({"kind": "failure_identity", "source_sha256": digest(invented)})
    with pytest.raises(Invalid): normalize(raw, binding=current_binding())


def test_unregistered_active_time_extension_preserves_the_old_rejection(failure):
    from unittest.mock import patch
    from harness.unconsumed_code_final_trace import UnconsumedCodeProjection
    with patch.object(UnconsumedCodeProjection, "active_interval_source", None):
        with pytest.raises(Invalid, match="a05_active_time"):
            normalize(failure[0], binding=current_binding())


def test_material_sensitivity_of_unaccepted_claim(unavailable):
    changed, _, _ = product_unconsumed_trace("missing_drain", requirement="Audit a different actual synthetic requirement")
    assert normalize(changed, binding=current_binding()) != normalize(unavailable[0], binding=current_binding())
