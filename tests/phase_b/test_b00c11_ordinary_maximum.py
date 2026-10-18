"""Original-port maximum evidence, compatibility, and conservative prefixes."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.ordinary_maximum import maximum_trace, PassiveClock
from helpers.ordinary_sources import captured_source
from helpers.trace_sources import current_binding
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.execution import replay
from lqcd_agent.control.strict_json import canonical_bytes, loads


def projected(trace):
    return normalize(trace, binding=current_binding())


def legacy(trace):
    value = deepcopy(trace)
    value["schema_version"] = "0.6"
    value["proof"]["schema_version"] = "0.3"
    del value["proof"]["ordinary_maximum_settlements"]
    return value


@pytest.fixture(scope="module")
def exception():
    return maximum_trace()


def test_maximum_two_fresh_roots(exception):
    second = maximum_trace()
    first, root, facts = exception
    assert root != second[1] and projected(first) == projected(second[0])
    assert read(root / "allocations.json") == read(second[1] / "allocations.json")
    for trace, output, fact in (exception, second):
        compare(trace, read(ROOT / "tests/phase_b/expected_traces/b00c11/maximum.json"), binding=current_binding())
        (output / "normalized.json").write_bytes(canonical_bytes(projected(trace)))
        assert fact["effect_count"] == 1 and fact["closure"]["operation_status"] == "committed"
        assert fact["state"]["attempt_status"] == "failed"
        records = sorted((r["value"] for r in trace["proof"]["objects"] if r["kind"] == "execution_0_4"), key=lambda r:r["event_index"])
        budget = replay(records).projection.value["budget"]["dimensions"]
        assert budget["active_seconds_per_attempt"]["used"] == budget["llm_calls_per_attempt"]["used"] == 1
        reads = [r for r in fact["clock_reads"] if r["resource"] is not None]
        assert len(reads) == 1 and reads[0]["error"] is None
        declaration = trace["proof"]["ordinary_maximum_settlements"][0]
        measurement = loads(declaration["observation"]["content"])
        assert declaration["reason_code"] == "callee_exception"
        assert measurement["clock_read_state"] == "callee_raised_before_end" and measurement["end_at"] is None
        assert measurement["hard_usage"] == {"state":"unknown", "value":None}
        assert trace["proof"]["ordinary_calls"][0]["outcome"] is None
        with pytest.raises(Invalid, match="exception_settlement"):
            projected(legacy(trace))
        assert projected(read(output / "raw.json")) == projected(trace)
        assert fact["effect_count"] == 1
    observe("B00C11-MAXIMUM", {"kind":"boolean", "value":True},
            ["exact_maximum_sources", "original_port_closure", "session_bound_proof"], first)


@pytest.mark.parametrize("kind", ["llm_call", "tool_call"])
@pytest.mark.parametrize("mode,reason", [("exception","callee_exception"),("overrun","duration_overrun"),
                                        ("epoch","clock_untrusted"),("exception_epoch","clock_untrusted")])
def test_actual_classification_and_usage(kind, mode, reason):
    trace, _, facts = maximum_trace(kind=kind, mode=mode)
    assert projected(trace) and facts["effect_count"] == 1
    declaration = trace["proof"]["ordinary_maximum_settlements"][0]
    observation = loads(declaration["observation"]["content"])
    assert declaration["reason_code"] == reason
    assert observation["hard_usage"]["state"] == ("known" if mode == "overrun" else "unknown")
    assert observation["call_disposition"] == ("raised" if mode.startswith("exception") else "returned")
    if mode == "overrun":
        assert observation["hard_usage"]["value"]["active_seconds"] == 2
        assert trace["proof"]["ordinary_calls"][0]["outcome"] is not None


@pytest.mark.parametrize("mode", ["exception", "overrun"])
def test_scoped_llm_discarded_or_absent_return_needs_no_domain_artifact(mode):
    result = {"diagnostic": {"fingerprint": None}, "content": {"domain":"discarded"}}
    trace, _, facts = maximum_trace(scoped=True, mode=mode, result=result)
    assert projected(trace) and facts["effect_count"] == 1
    assert not trace["proof"]["ordinary_members"]
    assert (trace["proof"]["ordinary_calls"][0]["outcome"] is None) == (mode == "exception")


@pytest.mark.parametrize("mode", ["unsettled", "unsafe", "regression"])
def test_true_unsettled_and_fenced_prefixes_never_manufacture_closure(mode):
    trace, root, facts = maximum_trace(mode=mode)
    assert projected(trace) and projected(read(root / "raw.json")) == projected(trace)
    assert facts["effect_count"] == 1 and facts["closure"] is None
    assert not trace["proof"]["ordinary_maximum_settlements"]
    records = [r["value"] for r in trace["proof"]["objects"] if r["kind"] == "execution_0_4"]
    assert not any(r.get("event") == "resource_settled" for r in records)
    state = replay(sorted(records,key=lambda r:r["event_index"])).projection.value
    assert state["run_status"] == state["attempt_status"] == "running"
    assert state["budget"]["dimensions"]["active_seconds_per_attempt"]["used"] == 1


def test_unknown_audit_usage_on_trusted_return_does_not_trigger_maximum():
    trace, _, facts = maximum_trace(mode="actual")
    assert projected(trace) and facts["effect_count"] == 1
    assert not trace["proof"]["ordinary_maximum_settlements"]
    settled = next(r["value"]["payload"] for r in trace["proof"]["objects"] if r["value"].get("event") == "resource_settled")
    assert settled["actual"] is not None
    assert settled["tokens"] == settled["cost"] == {"state":"unknown", "value":None}


@pytest.mark.parametrize("fault", ["missing", "duplicate", "orphan", "capability", "settlement", "reason", "forged_return", "exception",
    "missing_observation", "missing_state", "read_failed", "fake_end", "zero_unknown", "epoch_type", "resource", "source_tamper",
    "foreign_owner", "producer_epoch", "producer_revision", "stale", "foreign_object", "extra_field"])
def test_maximum_invalid_sources(exception, fault):
    trace = deepcopy(exception[0]); proof = trace["proof"]
    item = proof["ordinary_maximum_settlements"][0]; call = proof["ordinary_calls"][0]
    observation = loads(item["observation"]["content"])
    if fault == "missing": proof["ordinary_maximum_settlements"] = []
    elif fault == "duplicate": proof["ordinary_maximum_settlements"].append(deepcopy(item))
    elif fault == "orphan": item["reservation_head"] = "f" * 64
    elif fault in ("capability", "settlement", "reason"):
        item[{"capability":"capability_id", "settlement":"settlement_head", "reason":"reason_code"}[fault]] = "foreign"
    elif fault == "forged_return": call["outcome"] = captured_source("outcome", {"host_error":"forged Agent return"})
    elif fault == "exception": call["exception"] = None
    elif fault == "missing_observation": del item["observation"]
    elif fault == "missing_state": del observation["clock_read_state"]
    elif fault == "read_failed": observation["clock_read_state"] = "read_failed"
    elif fault == "fake_end": observation["end_at"] = deepcopy(observation["start_at"])
    elif fault == "zero_unknown": observation["hard_usage"] = {"state":"unknown", "value":0}
    elif fault == "epoch_type": observation["clock_epoch_after"] = False
    elif fault == "resource": observation["resource_operation_id"] = "foreign"
    elif fault == "source_tamper": item["evidence"]["content"] += " "
    elif fault == "foreign_owner": call["authorization"]["identity"]["run_id"] = "foreign"
    elif fault.startswith("producer_"): call["producer"]["lease_epoch" if fault.endswith("epoch") else "phase_revision"] += 1
    elif fault == "stale": proof["binding"]["invocation_token"] = "stale"
    elif fault == "foreign_object": proof["objects"][0]["value"]["case_id"] = "foreign"
    elif fault == "extra_field": item["stop_proven"] = True
    if fault in ("missing_state", "read_failed", "fake_end", "zero_unknown", "epoch_type", "resource"):
        item["observation"] = captured_source("maximum_observation", observation)
    with pytest.raises(Invalid): projected(trace)


def test_material_changes_break_exact_comparison(exception):
    baseline = projected(exception[0])
    for args in ({"message":"Changed actual exception"}, {"mode":"overrun", "result":"Changed actual return"}, {"mode":"epoch"}):
        trace, _, _ = maximum_trace(**args)
        assert projected(trace) != baseline
        with pytest.raises(Invalid): compare(trace, baseline, binding=current_binding())
    overrun, _, _ = maximum_trace(mode="overrun")
    bad = deepcopy(overrun); item = bad["proof"]["ordinary_maximum_settlements"][0]
    observation = loads(item["observation"]["content"])
    observation["end_at"]["monotonic_seconds"] += 1
    observation["hard_usage"]["value"]["active_seconds"] += 1
    item["observation"] = captured_source("maximum_observation", observation)
    assert projected(bad) != projected(overrun)
    observation["hard_usage"]["value"]["llm_calls"] = True
    item["observation"] = captured_source("maximum_observation", observation)
    with pytest.raises(Invalid): projected(bad)


def test_passive_clock_delegates_identical_reads_and_errors():
    subject = FakeClock(100, 0); wrapper = PassiveClock(subject)
    stamp = subject.now()
    assert wrapper.now() is stamp and len(wrapper.reads) == 1
    class BrokenClock:
        epoch_id = "original"
        def now(self):
            raise RuntimeError("Original Clock read failed")
    wrapper = PassiveClock(BrokenClock())
    with pytest.raises(RuntimeError, match="Original Clock read failed"): wrapper.now()
    assert wrapper.reads == [{"resource":None, "timestamp":None, "error":{"type":"RuntimeError", "message":"Original Clock read failed"}}]
