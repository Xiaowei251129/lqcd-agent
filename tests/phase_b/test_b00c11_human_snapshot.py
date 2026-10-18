"""Actual protected Human snapshot entry and explicitly contract-only chains."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from harness.contracts import ROOT
from harness.ordinary_maximum_trace import MaximumProjection
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from harness.trace_proof import source_object
from helpers.ordinary_human import human_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from test_b00c11_ordinary_maximum import legacy


def projected(trace):
    return normalize(trace, binding=current_binding())


@pytest.fixture(scope="module")
def human():
    return human_trace()


def snapshot_entry(trace):
    declaration = next(d for d in trace["proof"]["ordinary_members"] if d["member"] == "payload.json")
    objects = {r["sha256"]: r for r in trace["proof"]["objects"]}
    registration = objects[declaration["registration_head"]]["value"]
    run = registration["case_id"], registration["run_id"]
    records = sorted((r["value"] for r in objects.values() if r["kind"] == "execution_0_4" and
                     (r["value"]["case_id"],r["value"]["run_id"]) == run), key=lambda r:r["event_index"])
    root = Path(next(r["path"] for r in trace["proof"]["output_roots"] if (r["case_id"],r["run_id"]) == run))
    extension = MaximumProjection(trace["proof"])
    extension.base_sources, extension.executions, extension.roots, extension.events = objects, {run:records}, {run:root}, trace["events"]
    extension.human_snapshot(declaration, registration)
    return extension, declaration, registration, records, root


def test_human_two_fresh_roots(human):
    second = human_trace()
    assert human[1] != second[1] and projected(human[0]) == projected(second[0])
    assert read(human[1] / "allocations.json") == read(second[1] / "allocations.json")
    for trace, output, resumed in (human, second):
        assert resumed["operation_status"] == "in_progress"
        extension, declaration, registration, records, root = snapshot_entry(trace)
        submitted = next(r for r in records if r.get("record_type") == "human_response" and r["event"] == "submitted")
        path = root / registration["members"][0]["canonical_path"]
        assert submitted["payload_reference"] == str(path) and path.read_bytes() == declaration["content"].encode()
        assert sha256(path.read_bytes()).hexdigest() == submitted["payload_sha256"] == declaration["sha256"]
        assert not any(r.get("record_type") == "human_response" and r["event"] == "consumed" for r in records)
        compare(trace, read(ROOT / "tests/phase_b/expected_traces/b00c16/human_prefix.json"), binding=current_binding())
        (output / "normalized.json").write_bytes(canonical_bytes(projected(trace)))
        before = (root / "execution_history.jsonl").read_bytes()
        assert projected(read(output / "raw.json")) == projected(trace)
        assert (root / "execution_history.jsonl").read_bytes() == before
        old = legacy(trace)
        for field in ("product_failure_sources", "product_grant_sources"):
            old["proof"].pop(field)
        with pytest.raises(Invalid, match="human_owner"): projected(old)
    observe("B00C11-HUMAN", {"kind":"boolean", "value":True},
            ["exact_human_snapshot", "original_resume_prefix", "session_bound_proof"], human[0])


@pytest.mark.parametrize("fault", ["missing", "duplicate", "foreign_registration", "member", "foreign_response", "foreign_run", "sha", "size", "bytes", "snapshot", "stale", "extra_field"])
def test_full_human_source_rejects_malformed_proof(human, fault):
    trace = deepcopy(human[0]); proof = trace["proof"]
    declaration = next(d for d in proof["ordinary_members"] if d["member"] == "payload.json")
    registration = next(r for r in proof["objects"] if r["sha256"] == declaration["registration_head"])
    submitted = next(r for r in proof["objects"] if r["value"].get("record_type") == "human_response" and r["value"]["event"] == "submitted")
    if fault == "missing": proof["ordinary_members"].remove(declaration)
    elif fault == "duplicate": proof["ordinary_members"].append(deepcopy(declaration))
    elif fault == "foreign_registration": declaration["registration_head"] = "f" * 64
    elif fault == "member": declaration["member"] = "other.json"
    elif fault == "foreign_response": registration["value"]["human_response_id"] = "foreign"
    elif fault == "foreign_run": proof["output_roots"][0]["run_id"] = "foreign"
    elif fault == "sha": declaration["sha256"] = "f" * 64
    elif fault == "size": registration["value"]["members"][0]["size_bytes"] += 1
    elif fault == "bytes": declaration["content"] += " "
    elif fault == "snapshot": submitted["value"]["payload_snapshot"]["reason"] = "forged"
    elif fault == "stale": proof["binding"]["invocation_token"] = "stale"
    elif fault == "extra_field": declaration["accepted"] = True
    with pytest.raises(Invalid): projected(trace)


@pytest.mark.parametrize("fault", ["relative", "traversal", "alias", "foreign_root", "foreign_member", "different_file", "symlink", "symlink_parent", "wrong_action", "foreign_request", "wrong_publisher"])
def test_locator_and_original_publisher_relation(human, tmp_path, fault):
    trace = deepcopy(human[0])
    extension, declaration, registration, records, root = snapshot_entry(trace)
    extension.human_snapshots.clear()
    submitted = next(r for r in records if r.get("record_type") == "human_response" and r["event"] == "submitted")
    canonical = registration["members"][0]["canonical_path"]; path = root / canonical
    if fault == "relative": submitted["payload_reference"] = canonical
    elif fault == "traversal": submitted["payload_reference"] = str(root / "human_responses/../" / canonical)
    elif fault == "alias": submitted["payload_reference"] = str(path.parent) + "/./payload.json"
    elif fault == "foreign_root": submitted["payload_reference"] = str(tmp_path / canonical)
    elif fault == "foreign_member": submitted["payload_reference"] = str(path.with_name("other.json"))
    elif fault == "different_file":
        duplicate = tmp_path / "payload.json"; duplicate.write_bytes(path.read_bytes()); submitted["payload_reference"] = str(duplicate)
    elif fault == "foreign_request": submitted["human_request_id"] = "foreign"
    elif fault == "wrong_action": records.append({**submitted, "event":"validated", "decision":"reject_or_hold"})
    elif fault == "wrong_publisher": extension.events = [e for e in extension.events if e["phase"] != "prestart_records_committed"]
    saved = path.read_bytes()
    backup = None
    try:
        if fault == "symlink":
            target = tmp_path / "same.json"; target.write_bytes(saved); path.unlink(); path.symlink_to(target)
        elif fault == "symlink_parent":
            backup = path.parent.with_name(path.parent.name + "-backup"); path.parent.rename(backup); path.parent.symlink_to(backup, target_is_directory=True)
        with pytest.raises((Invalid, KeyError)):
            extension.human_snapshot(declaration, registration)
    finally:
        if fault == "symlink": path.unlink(); path.write_bytes(saved)
        elif fault == "symlink_parent": path.parent.unlink(); backup.rename(path.parent)


def test_human_material_change_is_exactly_visible(human):
    changed, _, _ = human_trace(reason="Changed actual Human decision reason")
    assert projected(changed) != projected(human[0])
    with pytest.raises(Invalid): compare(changed, projected(human[0]), binding=current_binding())


@pytest.fixture(scope="module")
def budget_snapshot():
    value = human_trace(decision="approve_budget_window")
    assert projected(value[0]) and value[2]["operation_status"] == "in_progress"
    return value


def contract_chain(budget_snapshot):
    from test_granted_advance_control import granted_source, snapshot
    from test_execution_0_4_foundation import rechain
    extension, _, registration, _, _ = snapshot_entry(budget_snapshot[0])
    ledger, state, admitted, _ = granted_source()
    rows = deepcopy(snapshot(ledger, state, admitted)["records"])
    run = registration["case_id"], registration["run_id"]
    snapshot_head, payload, reference = extension.human_snapshots[(*run, registration["human_response_id"])]
    for row in rows:
        row.update(case_id=run[0], run_id=run[1])
        if row["record_type"] == "human_request": row["authorization_scope"]["work_target"] = "analysis_engineer"
        if row["record_type"] == "human_response":
            row.update(payload_reference=reference, payload_sha256=snapshot_head)
            if row["event"] == "submitted": row["payload_snapshot"] = payload
        if row.get("event") == "failure_observed":
            fp = row["payload"]["fingerprint"]
            fp["context"].update(plan_digest=None, code_digest=None)
            fp["causal_context_digest"] = digest(fp["context"])
            fp["fingerprint_digest"] = digest({k:v for k,v in fp.items() if k != "fingerprint_digest"})
    fp = next(r["payload"]["fingerprint"] for r in rows if r.get("event") == "failure_observed")
    issued = next(r for r in rows if r.get("event") == "grant_issued")
    issued["payload"].update(response_reference=reference, response_digest=snapshot_head, fingerprint_digest=fp["fingerprint_digest"])
    for row in rows:
        if row.get("record_type") == "budget":
            if row["payload"].get("fingerprint_digest") is not None: row["payload"]["fingerprint_digest"] = fp["fingerprint_digest"]
            if "decision_digest" in row["payload"]: row["payload"]["decision_digest"] = digest({k:v for k,v in row["payload"].items() if k != "decision_digest"})
            if row["event"] == "grant_consumed": row["payload"]["grant_digest"] = digest(issued["payload"])
    rows = rechain(rows)
    extension.base_sources = {digest(r): source_object("execution_0_4",r,version="0.4") for r in rows}
    extension.executions = {run:rows}
    # This synthetic authorization chain is contract-only. The snapshot entry
    # above was produced and verified by original resume/publication ports.
    return extension, rows, run, {"contract_only":True, "work_dispatched":False, "B04_owned":False}


@pytest.mark.parametrize("fault", [None, "foreign_request", "foreign_response", "snapshot", "reference", "target", "scope", "occurrence", "fingerprint", "missing_validated", "duplicate_consumption", "action"])
def test_grant_source_contract_only_uses_real_locator_entry(budget_snapshot, fault):
    extension, rows, run, label = contract_chain(budget_snapshot)
    issued = next(r for r in rows if r.get("event") == "grant_issued")
    payload = issued["payload"]
    if fault in ("foreign_request","foreign_response","snapshot","reference","target","occurrence"):
        key = {"foreign_request":"human_request_id","foreign_response":"human_response_id","snapshot":"response_digest","reference":"response_reference","target":"target_node","occurrence":"occurrence"}[fault]
        payload[key] = 99 if fault == "occurrence" else "foreign"
    elif fault == "scope": next(r for r in rows if r.get("record_type") == "human_request")["authorization_scope"]["allowed_decisions"] = []
    elif fault == "fingerprint": payload["fingerprint_digest"] = "f" * 64
    elif fault == "missing_validated": rows[:] = [r for r in rows if not (r.get("record_type") == "human_response" and r["event"] == "validated")]
    elif fault == "duplicate_consumption": rows.append(deepcopy(next(r for r in rows if r.get("event") == "grant_consumed")))
    elif fault == "action": next(r for r in rows if r.get("record_type") == "human_response" and r["event"] == "validated")["decision"] = "approve_rerun"
    if fault is None:
        extension.failure_and_grant_sources(extension.base_sources, {run:rows})
        grant = next(r for r in extension.sources.values() if r["value"].__class__ is dict and r["value"].get("budget_grant_id"))
        extension.locator_fields(grant["sha256"], grant["value"])
        assert extension.locators and label == {"contract_only":True, "work_dispatched":False, "B04_owned":False}
    else:
        with pytest.raises((Invalid, KeyError, StopIteration, ValueError)):
            extension.failure_and_grant_sources(extension.base_sources, {run:rows})


@pytest.mark.parametrize("fault", [None, "foreign_request", "foreign_response", "snapshot", "target", "attempt", "missing_consumed", "missing_validated", "duplicate_consumed", "scope", "action"])
def test_consumed_human_scope_contract_only_uses_real_locator_entry(budget_snapshot, fault):
    extension, rows, run, label = contract_chain(budget_snapshot)
    response = next(r for r in rows if r.get("record_type") == "human_response" and r["event"] == "consumed")
    authorization = {"human_request_id":response["human_request_id"], "human_response_id":response["human_response_id"],
                     "response_digest":response["payload_sha256"], "target_node":"analysis_engineer"}
    identity = {"case_id":run[0], "run_id":run[1], "attempt_id":response["authorized_target_attempt_id"]}
    if fault in ("foreign_request","foreign_response","snapshot","target"):
        authorization[{"foreign_request":"human_request_id","foreign_response":"human_response_id","snapshot":"response_digest","target":"target_node"}[fault]] = "foreign"
    elif fault == "attempt": identity["attempt_id"] = "foreign"
    elif fault in ("missing_consumed","missing_validated"):
        rows[:] = [r for r in rows if not (r.get("record_type") == "human_response" and r["event"] == fault.removeprefix("missing_"))]
    elif fault == "duplicate_consumed": rows.append(deepcopy(response))
    elif fault == "scope": next(r for r in rows if r.get("record_type") == "human_request")["authorization_scope"]["allowed_decisions"] = []
    elif fault == "action": response["decision"] = "approve_rerun"
    if fault is None:
        extension.human_authorization("synthetic", authorization, identity, ("human_authorization",))
        assert extension.refs_at and label["contract_only"] and not label["work_dispatched"]
    else:
        with pytest.raises((Invalid, KeyError, StopIteration)):
            extension.human_authorization("synthetic", authorization, identity, ("human_authorization",))
