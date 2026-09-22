"""Trace 0.4 proves the actual external Pause resource reservation."""
import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from harness.trace_proof import reference_paths, source_object
from helpers.control_traces import fresh_external_trace
from helpers.trace_sources import current_binding
from test_historical_source_traces import rehash


EXPECTED = "tests/phase_b/expected_traces/external_source_consumption.json"
INVARIANTS = ["complete_artifact_sources", "exact_external_trace", "typed_reservation_source"]


def test_external_reservation_source_trace():
    first, second = fresh_external_trace(), fresh_external_trace()
    assert first["proof"]["output_roots"] != second["proof"]["output_roots"]
    expected = read(ROOT / EXPECTED)
    for actual in (first, second):
        compare(actual, expected, binding=current_binding())
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    observe("B00-EXTERNAL-TRACE-001", {"kind": "boolean", "value": True}, INVARIANTS, first)


@pytest.mark.parametrize("fault", ["missing", "raw_digest", "missing_reference", "wrong_kind", "foreign_producer", "foreign_attempt", "wrong_record", "old_version"])
def test_reservation_source_rejects_incomplete_or_foreign_evidence(fault):
    trace = fresh_external_trace()
    pause = next(r for r in trace["proof"]["objects"] if r["kind"] == "execution_0_4" and r["value"]["event"] == "pause_prepared")
    head = pause["value"]["proof"]["dependency"]["reservation_digest"]
    reservation = next(r for r in trace["proof"]["objects"] if r["sha256"] == head)
    if fault == "missing":
        trace["proof"]["objects"].remove(reservation)
    elif fault == "raw_digest":
        reservation["value"]["payload"]["maximum_charge"]["llm_calls"] += 1
    elif fault == "missing_reference":
        pause["references"] = [r for r in pause["references"] if r["path"] != ["proof", "dependency", "reservation_digest"]]
    elif fault == "wrong_kind":
        reservation["kind"] = "canonical_json"
    elif fault == "old_version":
        trace["schema_version"] = "0.3"
    else:
        def mutate(kind, value):
            if kind == "execution_0_4" and value.get("event") == "resource_reserved":
                if fault == "foreign_producer":
                    value["payload"]["producer_operation_id"] = "foreign"
                elif fault == "foreign_attempt":
                    value["payload"]["attempt_id"] = "attempt_000001"
                else:
                    value["event"] = "resource_settled"
        rehash(trace, mutate, version="0.4")
    with pytest.raises(Invalid):
        normalize(trace, binding=current_binding())


def test_reservation_reference_is_versioned_and_position_specific():
    trace = fresh_external_trace()
    value = next(r["value"] for r in trace["proof"]["objects"] if r["kind"] == "execution_0_4" and r["value"]["event"] == "pause_prepared")
    path = ("proof", "dependency", "reservation_digest")
    assert path in dict(reference_paths(value, kind="execution_0_4", version="0.4"))
    for version in ("0.2", "0.3"):
        assert path not in dict(reference_paths(value, kind="execution_0_4", version=version))
    material = {"reservation_digest": value["proof"]["dependency"]["reservation_digest"]}
    assert source_object("canonical_json", material, version="0.4")["references"] == []
