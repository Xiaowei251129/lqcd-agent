"""Closed Host receipts actually submitted through original settlement ports."""
from copy import deepcopy
import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.ordinary_maximum_trace import MaximumProjection
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.ordinary_maximum import maximum_trace
from helpers.ordinary_sources import captured_source
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import digest, loads
from test_b00c11_ordinary_maximum import legacy, projected


@pytest.fixture(scope="module")
def receipt():
    return maximum_trace(host_receipt=True)


def test_receipt_two_fresh_roots(receipt):
    second = maximum_trace(host_receipt=True)
    assert receipt[1] != second[1] and projected(receipt[0]) == projected(second[0])
    assert read(receipt[1] / "allocations.json") == read(second[1] / "allocations.json")
    for trace, output, facts in (receipt, second):
        compare(trace, read(ROOT / "tests/phase_b/expected_traces/b00c12/receipt.json"), binding=current_binding())
        item = trace["proof"]["ordinary_maximum_settlements"][0]
        evidence = loads(item["evidence"]["content"])
        call = trace["proof"]["ordinary_calls"][0]
        settled = next(r["value"] for r in trace["proof"]["objects"] if r["sha256"] == item["settlement_head"])
        assert evidence == {"schema_version": "0.1", "resource_operation_id": settled["payload"]["resource_operation_id"], "exception": call["exception"]}
        assert settled["payload"]["evidence_digest"] == item["evidence"]["sha256"]
        assert settled["payload"]["actual"] is None and call["outcome"] is None
        assert facts["effect_count"] == 1 and facts["state"]["attempt_status"] == "failed"
        assert facts["closure"]["operation_status"] == "committed"
        assert len([r for r in facts["clock_reads"] if r["resource"] is not None]) == 1
        assert projected(read(output / "raw.json")) == projected(trace) and facts["effect_count"] == 1
        with pytest.raises(Invalid, match="exception_settlement"): projected(legacy(trace))
    observe("B00C12-MAXIMUM-HOST-RECEIPT", {"kind": "boolean", "value": True},
            ["exact_host_receipt", "original_port_closure", "session_bound_proof"], receipt[0])


@pytest.mark.parametrize("kind,scoped", [("llm_call", False), ("tool_call", False), ("llm_call", True)])
@pytest.mark.parametrize("mode,reason", [("exception", "callee_exception"), ("exception_epoch", "clock_untrusted")])
def test_receipt_preserves_actual_classification(kind, scoped, mode, reason):
    trace, _, facts = maximum_trace(host_receipt=True, kind=kind, scoped=scoped, mode=mode)
    assert projected(trace) and facts["effect_count"] == 1
    assert trace["proof"]["ordinary_maximum_settlements"][0]["reason_code"] == reason
    assert trace["proof"]["ordinary_calls"][0]["outcome"] is None
    if scoped: assert not trace["proof"]["ordinary_members"]


@pytest.mark.parametrize("fault", ["missing", "bytes", "resource", "exception", "extra", "version", "shape", "foreign_owner", "epoch",
                                   "revision", "duplicate", "return", "stop", "stale"])
def test_receipt_sources_reject_coherent_outer_mutations(receipt, fault):
    trace = deepcopy(receipt[0]); proof = trace["proof"]
    item = proof["ordinary_maximum_settlements"][0]; call = proof["ordinary_calls"][0]
    evidence = loads(item["evidence"]["content"])
    if fault == "missing": del item["evidence"]
    elif fault == "bytes": item["evidence"]["content"] += " "
    elif fault == "resource": evidence["resource_operation_id"] = "foreign"
    elif fault == "exception": evidence["exception"]["message"] = "forged"
    elif fault == "extra": evidence["stop_proven"] = True
    elif fault == "version": evidence["schema_version"] = "0.2"
    elif fault == "shape": evidence = {"error": evidence["exception"]}
    elif fault == "foreign_owner": call["authorization"]["identity"]["run_id"] = "foreign"
    elif fault in ("epoch", "revision"): call["producer"]["lease_epoch" if fault == "epoch" else "phase_revision"] += 1
    elif fault == "duplicate": proof["ordinary_maximum_settlements"].append(deepcopy(item))
    elif fault == "return": call["outcome"] = captured_source("outcome", {"receipt": evidence})
    elif fault == "stop": item["stop_proven"] = True
    elif fault == "stale": proof["binding"]["invocation_token"] = "stale"
    if fault in ("resource", "exception", "extra", "version", "shape"):
        item["evidence"] = captured_source("maximum_evidence", evidence)
    with pytest.raises(Invalid): projected(trace)


def test_legal_receipt_material_changes_exact_result(receipt):
    changed, _, facts = maximum_trace(host_receipt=True, message="Changed actual receipt exception")
    assert facts["effect_count"] == 1 and projected(changed) != projected(receipt[0])
    with pytest.raises(Invalid): compare(changed, projected(receipt[0]), binding=current_binding())


@pytest.mark.parametrize("fault", ["resource", "exception", "extra", "version", "shape"])
def test_closed_receipt_relation_rejects_even_coherent_declared_hashes(receipt, fault):
    # Contract-only negative: make the envelope and declared settlement hashes
    # coherent to exercise the inner relation as well as the full source checks.
    proof = deepcopy(receipt[0]["proof"])
    extension = MaximumProjection(proof)
    sources = {r["sha256"]: r for r in proof["objects"]}
    extension.base_sources = sources
    item = proof["ordinary_maximum_settlements"][0]
    reservation = sources[item["reservation_head"]]["value"]
    settlement = sources[item["settlement_head"]]["value"]
    evidence = loads(item["evidence"]["content"])
    if fault == "resource": evidence["resource_operation_id"] = "foreign"
    elif fault == "exception": evidence["exception"]["message"] = "forged"
    elif fault == "extra": evidence["stop_proven"] = True
    elif fault == "version": evidence["schema_version"] = "0.2"
    else: evidence = {"error": evidence["exception"]}
    item["evidence"] = captured_source("maximum_evidence", evidence)
    settlement["payload"]["evidence_digest"] = item["evidence"]["sha256"]
    item["settlement_head"] = digest(settlement)
    extension.maximums[item["reservation_head"]] = item
    call = proof["ordinary_calls"][0]
    owner = {k: reservation[k] for k in ("case_id", "run_id")}
    with pytest.raises(Invalid, match="maximum_receipt"):
        extension.maximum_settlement(call, reservation, settlement, call["producer"], owner)
