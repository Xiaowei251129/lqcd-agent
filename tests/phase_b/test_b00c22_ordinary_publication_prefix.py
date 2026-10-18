"""Original ordinary prefixes have closed provenance and unchanged runtime results."""
from copy import deepcopy
from hashlib import sha256

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.ordinary_publication_prefix_sources import PREFIX_MODES, product_prefix_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes, loads


MODES = (*PREFIX_MODES, "host_rejected", "domain_non_success", "exception", "overrun", "epoch")
INVARIANTS = sorted(["B04_owned_false", "actual_original_process", "bound_publication_stage", "no_effect_reexecution",
                     "original_frozen_journal", "unknown_usage_preserved"])


@pytest.mark.parametrize("mode", MODES)
def test_dual_fresh_original_publication_prefix(mode):
    expected = read(ROOT / "tests/phase_b/expected_traces/b00c22" / (mode + ".json"))
    values, facts_list = [], []
    for _ in range(2):
        trace, root, facts = product_prefix_trace(mode, recover=True)
        compare(trace, expected, binding=current_binding())
        values.append(normalize(trace, binding=current_binding()))
        facts_list.append(facts)
        assert not facts["B04_owned"] and facts["calls"] == 1
        if mode in ("settlement_before", "settlement_after", "completion_before", "unsettled_return"):
            assert not facts["completion_frozen"] and facts["run_status"] == "running"
        if mode in PREFIX_MODES and facts["completion_frozen"]:
            assert facts["original_suffix_recovered"]
        records = [row["value"] for row in trace["proof"]["objects"] if row["kind"] == "execution_0_4"]
        settlements = [row for row in records if row.get("event") == "resource_settled"]
        assert all(row["payload"]["tokens"] == row["payload"]["cost"] == {"state": "unknown", "value": None}
                   for row in settlements)
        print("C22_ORIGINAL_PREFIX", mode, root)
    assert values[0] == values[1] and facts_list[0] == facts_list[1]
    observe("B00C22-" + mode.upper(), {"kind": "boolean", "value": True}, INVARIANTS, trace)


@pytest.fixture(scope="module")
def settled_source():
    return product_prefix_trace("settlement_before")[0]


@pytest.fixture(scope="module")
def frozen_source():
    return product_prefix_trace("completion_after")[0]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "foreign_reservation", "foreign_settlement", "foreign_capability",
    "foreign_producer", "invocation_epoch", "producer_epoch", "producer_revision", "worker", "future_revision",
    "journal", "return", "stage", "publication", "snapshot", "extra_field", "stale_session"])
def test_settled_prefix_rejects_missing_or_foreign_source(settled_source, fault):
    raw = deepcopy(settled_source)
    declaration = raw["proof"]["ordinary_publication_prefixes"][0]
    if fault == "missing": raw["proof"]["ordinary_publication_prefixes"].clear()
    elif fault == "duplicate": raw["proof"]["ordinary_publication_prefixes"].append(deepcopy(declaration))
    elif fault == "foreign_reservation": declaration["reservation_head"] = "a" * 64
    elif fault == "foreign_settlement": declaration["settlement_head"] = declaration["reservation_head"]
    elif fault == "foreign_capability": declaration["capability_id"] = "foreign"
    elif fault == "foreign_producer": declaration["producer_operation_id"] = "foreign"
    elif fault in ("invocation_epoch", "producer_epoch", "producer_revision"): declaration["issuer"][fault] += 1
    elif fault == "worker": declaration["issuer"]["worker_id"] = "foreign"
    elif fault == "future_revision": declaration["journal_revision"] += 1000
    elif fault == "journal": declaration["journal"]["content"] = "{}"
    elif fault == "return": raw["proof"]["ordinary_calls"][0]["outcome"] = None
    elif fault == "stage": declaration["stage"] = "checkpoint_published"
    elif fault == "publication": declaration["publication"]["checkpoint_published"] = True
    elif fault == "snapshot": declaration["snapshot_sha256"] = "a" * 64
    elif fault == "extra_field": declaration["new_authority"] = True
    else: raw["proof"]["binding"]["invocation_token"] = "stale"
    with pytest.raises(Invalid):
        normalize(raw, binding=current_binding())


@pytest.mark.parametrize("field", ["authorization", "worker_id", "invocation_epoch", "completion_intent", "budget_intents"])
def test_rehashed_journal_cannot_replace_original_snapshot(frozen_source, field):
    raw = deepcopy(frozen_source)
    declaration = raw["proof"]["ordinary_publication_prefixes"][0]
    journal = loads(declaration["journal"]["content"])
    journal[field] = None
    content = canonical_bytes(journal)
    declaration["journal"].update(content=content.decode(), sha256=sha256(content).hexdigest())
    with pytest.raises(Invalid):
        normalize(raw, binding=current_binding())


def test_old_version_keeps_rejecting_real_settled_prefix(settled_source):
    raw = deepcopy(settled_source)
    raw["schema_version"], raw["proof"]["schema_version"] = "0.9", "0.6"
    raw["proof"].pop("ordinary_publication_prefixes")
    raw["events"] = [event for event in raw["events"] if event["event"] != "ordinary_publication_prefix"]
    with pytest.raises(Invalid, match="agent_registered_diagnostic"):
        normalize(raw, binding=current_binding())


def test_actual_material_changes_reach_the_normalized_result(settled_source):
    changed, _, _ = product_prefix_trace("settlement_before", material="changed actual domain material")
    assert normalize(changed, binding=current_binding()) != normalize(settled_source, binding=current_binding())


def test_changed_clock_retains_the_original_return_and_measurement(settled_source):
    shifted, _, _ = product_prefix_trace("settlement_before", clock_time=200)
    assert normalize(shifted, binding=current_binding())
    assert shifted["proof"]["ordinary_calls"][0]["outcome"] == settled_source["proof"]["ordinary_calls"][0]["outcome"]
    assert shifted["proof"]["ordinary_calls"][0]["producer"]["created_at"]["wall_seconds"] == 200
    assert shifted["proof"]["ordinary_publication_prefixes"][0]["stage"] == "settled_return"


def test_scientific_return_projection_is_stable_across_real_identities():
    from harness import a05_trace
    projections, identities = [], []
    for label in ("first-owner", "second-owner"):
        raw, _, _ = product_prefix_trace("settlement_before", identity_label=label)
        identities.append(raw["proof"]["ordinary_calls"][0]["authorization"]["identity"])
        original = a05_trace.digest
        values = set()
        def capture(value):
            result = original(value)
            if type(value) is dict and value.get("source_kind") == "ordinary":
                content = value["content"]
                if type(content) is list and len(content) == 2 and content[0] == "object" and \
                        {item[0] for item in content[1]} == {"diagnostic", "content"}:
                    values.add(result)
            return result
        a05_trace.digest = capture
        try:
            assert normalize(raw, binding=current_binding())
        finally:
            a05_trace.digest = original
        assert len(values) == 1
        projections.append(values)
    assert identities[0] != identities[1] and projections[0] == projections[1]


@pytest.mark.parametrize("fault", ["expired", "missing_member", "tampered_plan", "missing_completion"])
def test_unavailable_suffix_never_creates_domain_or_terminal_state(fault):
    from lqcd_agent.control.capabilities import InvocationLeases
    from lqcd_agent.control.clock import FakeClock
    from lqcd_agent.control.coordinator import Coordinator
    from lqcd_agent.control.strict_json import ControlIntegrityError

    _, output, facts = product_prefix_trace("completion_after")
    coordinator = Coordinator(output, clock=FakeClock(131, 31) if fault == "expired" else FakeClock(100, 0))
    try:
        capability_id, value = next((row[0], loads(row[1])) for row in coordinator.connection.execute(
            "SELECT capability_id,value FROM invocation_capabilities") if loads(row[1])["state"] == "started")
        identity = value["authorization"]["identity"]
        root = output / identity["case_id"] / identity["run_id"]
        if fault == "missing_member":
            (root / value["completion_intent"]["artifact_publication"]["projections"][0]["canonical_path"]).unlink()
        elif fault in ("tampered_plan", "missing_completion"):
            if fault == "tampered_plan": value["completion_intent"]["artifact_publication"]["projections"][0]["sha256"] = "a" * 64
            else: value.pop("completion_intent")
            with coordinator.transaction() as db:
                db.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?", (canonical_bytes(value), capability_id))
        before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        with pytest.raises((ControlIntegrityError, OSError)):
            InvocationLeases(coordinator).publish_completion(capability_id, value["worker_id"], value["invocation_epoch"])
        assert before == {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        assert facts["calls"] == 1 and facts["run_status"] == "running"
    finally:
        coordinator.close()
