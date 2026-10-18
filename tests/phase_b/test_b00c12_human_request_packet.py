"""C12 original packet publication, exact locators, and material boundaries."""
from copy import deepcopy
from pathlib import Path
from contextlib import closing
import sqlite3

import pytest

from harness.ordinary_maximum_trace import MaximumProjection
from harness.product_failure_trace import ProductProjection
from harness.strict_json import Invalid, read
from harness.trace import normalize
from helpers.ordinary_human import human_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads


@pytest.fixture(scope="module")
def human():
    return human_trace()


def packet_entry(trace):
    proof = deepcopy(trace["proof"])
    sources = {r["sha256"]: r for r in proof["objects"]}
    executions = {}
    for row in sources.values():
        if row["kind"] == "execution_0_4":
            value = row["value"]
            executions.setdefault((value["case_id"], value["run_id"]), []).append(value)
    for records in executions.values():
        records.sort(key=lambda r: r["event_index"])
    roots = {(r["case_id"], r["run_id"]): Path(r["path"]) for r in proof["output_roots"]}
    extension = ProductProjection(proof) if trace["schema_version"] == "0.8" else MaximumProjection(proof)
    extension.validate(sources, executions, roots, trace["events"])
    run, records = next(iter(executions.items()))
    written = next(r for r in records if r.get("record_type") == "human_request" and r["event"] == "packet_written")
    publisher, member, head, _ = extension.packets[(*run, written["human_request_id"])]
    registration = next(r for _, r in extension.registered.values() if r["attempt_id"] == publisher)
    return extension, records, written, registration, roots[run] / member


def test_packet_requester_and_publisher_are_original_and_distinct(human):
    trace, _, resumed = human
    assert normalize(trace, binding=current_binding()) and resumed["operation_status"] == "in_progress"
    extension, records, written, registration, path = packet_entry(trace)
    created = next(r for r in records if r.get("record_type") == "human_request" and r["event"] == "created")
    assert created["requesting_attempt_id"] == "attempt_000003"
    assert registration["attempt_id"] == "attempt_000004"
    assert path.read_bytes() == canonical_bytes(created) and read(path) == created
    assert created != written and registration["artifact_id"] == "attempt_000004:approval"
    assert not any(r.get("event") in ("consumed", "grant_issued", "grant_consumed") for r in records)
    encoded = extension.encode(digest(written), ("packet_reference",), lambda head: head)
    assert encoded == ["human_request_packet_locator", [written["case_id"], written["run_id"]],
                       written["human_request_id"], "attempt_000004", path.relative_to(path.parents[3]).as_posix(), digest(created)]


def test_original_created_prefix_does_not_require_future_packet():
    trace, root, result = human_trace(unpublished=True)
    assert result["operation_status"] == "not_submitted"
    records = [r["value"] for r in trace["proof"]["objects"] if r["kind"] == "execution_0_4"]
    requests = [r for r in records if r["record_type"] == "human_request"]
    assert len(requests) == 1 and requests[0]["event"] == "created" and requests[0]["packet_reference"] is None
    assert not list(root.glob("*/*/attempts/*/approval_packet/request.json"))
    assert normalize(trace, binding=current_binding()) == normalize(read(root / "raw.json"), binding=current_binding())


@pytest.mark.parametrize("fault", ["relative", "traversal", "dot", "separator", "foreign_root", "foreign_attempt", "foreign_member",
    "same_bytes_other_file", "missing_file", "symlink", "symlink_parent", "file_bytes", "duplicate_request", "missing_created",
    "request_scope", "requester", "duplicate_registration", "missing_registration", "member", "publisher", "member_created"])
def test_packet_relation_rejects_aliases_and_foreign_sources(human, tmp_path, fault):
    extension, records, written, registration, path = packet_entry(human[0])
    run = written["case_id"], written["run_id"]
    saved = path.read_bytes()
    backup = None
    if fault == "relative": written["packet_reference"] = path.relative_to(extension.roots[run]).as_posix()
    elif fault == "traversal": written["packet_reference"] = str(path.parent / "../request.json")
    elif fault == "dot": written["packet_reference"] = str(path.parent) + "/./request.json"
    elif fault == "separator": written["packet_reference"] = str(path.parent) + "//request.json"
    elif fault == "foreign_root": written["packet_reference"] = str(tmp_path / "request.json")
    elif fault == "foreign_attempt": written["packet_reference"] = written["packet_reference"].replace("attempt_000004", "attempt_000003")
    elif fault == "foreign_member": written["packet_reference"] = str(path.with_name("response.json"))
    elif fault == "same_bytes_other_file":
        other = tmp_path / "request.json"; other.write_bytes(saved); written["packet_reference"] = str(other)
    elif fault == "duplicate_request": records.append(deepcopy(written))
    elif fault == "missing_created": records[:] = [r for r in records if not (r.get("record_type") == "human_request" and r["event"] == "created")]
    elif fault == "request_scope": written["authorization_scope"]["work_target"] = "code_agent"
    elif fault == "requester": written["requesting_attempt_id"] = registration["attempt_id"]
    elif fault == "duplicate_registration": extension.registered[(*run, "duplicate")] = ("f" * 64, deepcopy(registration))
    elif fault == "missing_registration": extension.registered = {k: v for k, v in extension.registered.items() if v[1] != registration}
    elif fault == "member": registration["members"][0]["canonical_path"] = "attempts/attempt_000003/approval_packet/request.json"
    elif fault == "publisher": registration["attempt_id"] = "attempt_000003"
    elif fault == "member_created":
        member = registration["members"][0]; identity, node, name, _ = extension.member_values[member["sha256"]]
        extension.member_values[member["sha256"]] = identity, node, name, written
    try:
        if fault == "missing_file": path.unlink()
        elif fault == "file_bytes": path.write_bytes(saved + b" ")
        elif fault == "symlink":
            target = tmp_path / "request.json"; target.write_bytes(saved); path.unlink(); path.symlink_to(target)
        elif fault == "symlink_parent":
            backup = path.parent.with_name(path.parent.name + "-saved"); path.parent.rename(backup); path.parent.symlink_to(backup, target_is_directory=True)
        with pytest.raises((Invalid, OSError, KeyError)):
            extension.request_packets()
    finally:
        if fault in ("missing_file", "file_bytes", "symlink"):
            if path.is_symlink(): path.unlink()
            path.write_bytes(saved)
        elif fault == "symlink_parent": path.parent.unlink(); backup.rename(path.parent)


@pytest.mark.parametrize("fault", ["authorization", "epoch", "revision", "worker", "invocation_epoch", "unpublished", "ledger",
                                   "artifact_plan", "projection", "receipt_bytes", "start_intent", "producer_status"])
def test_original_packet_capability_and_completion_are_required(human, fault):
    extension, _, written, registration, path = packet_entry(human[0])
    database = extension.roots[written["case_id"], written["run_id"]].parent.parent / ".lqcd/control_operations.sqlite"
    with closing(sqlite3.connect(database)) as connection:
        rows = connection.execute("SELECT capability_id,value FROM invocation_capabilities").fetchall()
        identifier, saved = next((key, value) for key, value in rows if loads(value)["authorization"]["identity"]["attempt_id"] == registration["attempt_id"])
        value = loads(saved); auth = value["authorization"]
        producer = auth["producer_operation_id"]
        saved_status = connection.execute("SELECT status FROM control_operations WHERE operation_id=?", (producer,)).fetchone()[0]
        if fault == "authorization": auth["identity"]["run_id"] = "foreign"; value["authorization_digest"] = digest(auth)
        elif fault == "epoch": auth["producing_epoch"] += 1; value["authorization_digest"] = digest(auth)
        elif fault == "revision": auth["activation_result_revision"] += 1; value["authorization_digest"] = digest(auth)
        elif fault == "worker": value["worker_id"] = "foreign"
        elif fault == "invocation_epoch": value["invocation_epoch"] += 1
        elif fault == "unpublished": value["completion_intent"]["published"] = False
        elif fault == "ledger": value["completion_intent"]["content"] += "\n"
        elif fault == "artifact_plan": value["completion_intent"]["artifact_publication"]["content"] = ""
        elif fault == "projection": value["completion_intent"]["projection"]["active_human_request_id"] = "foreign"
        elif fault == "receipt_bytes": value["completion_intent"]["artifact_publication"]["projections"][0]["content_base64"] = "e30="
        elif fault == "start_intent": value["started_intent"]["published"] = False
        elif fault == "producer_status": connection.execute("UPDATE control_operations SET status='recovery_required' WHERE operation_id=?", (producer,))
        connection.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?", (canonical_bytes(value).decode(), identifier)); connection.commit()
        try:
            with pytest.raises(Invalid): normalize(human[0], binding=current_binding())
        finally:
            connection.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?", (saved, identifier))
            connection.execute("UPDATE control_operations SET status=? WHERE operation_id=?", (saved_status, producer)); connection.commit()


def test_request_material_and_unknown_packet_fields_are_preserved(human):
    changed, _, _ = human_trace(risk="high")
    assert normalize(changed, binding=current_binding()) != normalize(human[0], binding=current_binding())
    extension, _, written, _, _ = packet_entry(human[0])
    head = "unknown-container"
    extension.base_sources[head] = {"kind": "canonical_json", "value": {"nested": written}}
    extension.locator_fields(head, {"nested": written})
    assert (head, ("nested", "packet_reference")) not in extension.packet_locators
    assert extension.encode(head, ("nested", "packet_reference"), lambda x: x) is None
