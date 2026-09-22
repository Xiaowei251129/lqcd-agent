"""Source-bound historical Fork evidence, separate from B02 construction."""
from copy import deepcopy
import sqlite3

import pytest

from harness.contracts import ROOT, DIGEST_KEYS
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from harness.trace_proof import source_object, source_digest, _project_events
from helpers.historical_trace_sources import historical_trace, files
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes, loads


EXPECTED = "tests/phase_b/expected_traces/historical_trace_fork.json"
INVARIANTS = ["exact_semantic_trace", "historical_source_validation", "source_bytes_unchanged"]


def checked(trace):
    return normalize(trace, binding=current_binding())


def test_historical_fork_observation():
    with historical_trace() as (first, first_root), historical_trace(archive_offset=500) as (second, second_root):
        assert first_root != second_root
        assert first["events"][0]["execution_head"] != second["events"][0]["execution_head"]
        assert {row["kind"] for row in first["proof"]["objects"]} == {
            "historical_execution_0_3", "historical_checkpoint_manifest_0_3",
            "execution_0_4", "checkpoint_manifest", "canonical_json"}
        expected = read(ROOT / EXPECTED)
        for trace, root in ((first, first_root), (second, second_root)):
            before = files(root)
            compare(trace, expected, binding=current_binding())
            assert files(root) == before
        assert checked(first) == checked(second)
        observe("B00-TRACE-HISTORICAL-001", {"kind": "boolean", "value": True}, INVARIANTS, first)


def test_live_wal_is_validated_without_source_changes():
    with historical_trace(wal=True) as (trace, root):
        database = root / "checkpoints/graph_checkpoints.sqlite"
        connection = sqlite3.connect(database.as_uri() + "?immutable=1", uri=True)
        try:
            assert loads(connection.execute("SELECT checkpoint FROM checkpoints").fetchone()[0])["ts"] != "1970-01-01T00:00:11+00:00"
        finally:
            connection.close()
        before = files(root)
        checked(trace)
        assert files(root) == before


def test_historical_subprocess_and_runtime_comparison(tmp_path):
    from test_source_bound_traces import subprocess_and_runtime_comparison
    subprocess_and_runtime_comparison(tmp_path, "0.3")


def rehash(trace, mutate, *, version="0.3"):
    """Recompute the complete raw DAG; negative tests cannot rely on stale hashes."""
    original = {row["sha256"]: row for row in trace["proof"]["objects"]}
    rewritten = {}
    def visit(head):
        if head in rewritten:
            return rewritten[head]["sha256"]
        row = original[head]
        value = deepcopy(row["value"])
        for ref in row["references"]:
            parent = value
            for key in ref["path"][:-1]:
                parent = parent[key]
            parent[ref["path"][-1]] = visit(ref["sha256"])
        mutate(row["kind"], value)
        if row["kind"] in ("checkpoint_manifest", "historical_checkpoint_manifest_0_3"):
            value["checkpoint_head"] = source_digest(row["kind"], value)
        rewritten[head] = source_object(row["kind"], value, version=version)
        return rewritten[head]["sha256"]
    for head in original:
        visit(head)
    for event in trace["events"]:
        for field in ("execution_head", "artifact_head", "checkpoint_head", "result_digest"):
            if event[field] in rewritten:
                event[field] = rewritten[event[field]]["sha256"]
    trace["proof"]["objects"] = list(rewritten.values())


@pytest.mark.parametrize("fault", ["record", "fingerprint", "clock", "identity", "state", "payload", "manifest", "revision"])
def test_rehashed_forged_history_is_rejected(fault):
    with historical_trace() as (trace, _):
        def mutate(kind, value):
            if kind == "historical_execution_0_3":
                if fault == "record" and value["event"] == "started":
                    value["attempt_id"] = "attempt_999999"
                elif fault == "fingerprint" and "runtime_fingerprint" in value:
                    value["runtime_fingerprint"]["application_build"] = "f" * 64
                elif fault == "clock" and value["event_index"] == 2:
                    value["created_at"]["wall_seconds"] = 1
                elif fault == "identity":
                    value["case_id"] = "foreign"
            elif kind == "canonical_json":
                if fault == "state" and "active_pause" in value:
                    value["active_pause"]["status"] = "claimed"
                elif fault == "payload" and "channel_values" in value and value["id"] == "original_public_pause":
                    value["lqcd_control_operation_id"] = "forged"
                elif fault == "revision" and "source_run_identity" in value and "revision" in value:
                    value["revision"] += 1
            elif kind == "historical_checkpoint_manifest_0_3" and fault == "manifest":
                value["checkpoint_thread_id"] = "foreign:thread"
        rehash(trace, mutate)
        with pytest.raises(Invalid):
            checked(trace)


@pytest.mark.parametrize("fault", ["input", "execution", "artifact_index", "artifact_history", "checkpoint", "manifest", "source_revision"])
def test_original_bytes_and_real_reservation_are_checked(fault):
    with historical_trace() as (trace, root):
        if fault == "input":
            (root / "root_goal.json").write_bytes(b'{"goal":"tampered"}')
        elif fault == "execution":
            path = root / "execution_history.jsonl"
            path.write_bytes(path.read_bytes().replace(b'HistoricalFailure', b'TamperedFailure'))
        elif fault == "artifact_index":
            path = root / "artifact_index.json"
            value = loads(path.read_bytes())
            value["current"] = {"foreign": {"artifact_id": "forged"}}
            path.write_bytes(canonical_bytes(value))
        elif fault == "artifact_history":
            (root / "artifact_history.jsonl").write_bytes(b'{}\n')
        elif fault == "manifest":
            (root / "checkpoints/original_public_pause.json").write_bytes(b'{}')
        elif fault == "checkpoint":
            with sqlite3.connect(root / "checkpoints/graph_checkpoints.sqlite") as connection:
                connection.execute("UPDATE checkpoints SET checkpoint=?", (b'{}',))
        else:
            with sqlite3.connect(root.parent.parent / ".lqcd/control_operations.sqlite") as connection:
                row = connection.execute("SELECT operation_id,reservation FROM control_operations WHERE operation_type='fork_run'").fetchone()
                reservation = loads(row[1])
                reservation["source_snapshot_proof"]["source_control_revision"] += 1
                connection.execute("UPDATE control_operations SET reservation=? WHERE operation_id=?", (canonical_bytes(reservation), row[0]))
        with pytest.raises(Invalid):
            checked(trace)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "orphan", "generic_history", "current_history", "historical_child", "unbound_generic", "wrong_event_run", "old_version", "semantic_actual"])
def test_historical_kinds_are_closed_and_context_bound(fault):
    with historical_trace() as (trace, _):
        objects = trace["proof"]["objects"]
        historical = next(row for row in objects if row["kind"] == "historical_execution_0_3")
        if fault == "missing":
            objects.remove(historical)
        elif fault == "duplicate":
            objects.append(deepcopy(historical))
        elif fault == "orphan":
            objects.append(source_object("canonical_json", {"orphan": True}, version="0.3"))
        elif fault in ("generic_history", "current_history"):
            historical["kind"] = "canonical_json" if fault == "generic_history" else "execution_0_4"
        elif fault == "historical_child":
            next(row for row in objects if row["kind"] == "execution_0_4")["kind"] = "historical_execution_0_3"
        elif fault == "unbound_generic":
            row = source_object("canonical_json", {"execution_head": historical["sha256"]}, version="0.3")
            objects.append(row)
            trace["events"][-1]["result_digest"] = row["sha256"]
        elif fault == "wrong_event_run":
            trace["events"][0]["run_id"] = trace["events"][-1]["run_id"]
        elif fault == "old_version":
            trace["schema_version"] = "0.2"
        else:
            trace = checked(trace)
        with pytest.raises(Invalid):
            checked(trace)


@pytest.mark.parametrize("change", [{"material": "different scientific goal"}, {"revision_offset": 1}])
def test_valid_material_and_source_revision_remain_semantic(change):
    with historical_trace(**change) as (trace, _):
        checked(trace)
        with pytest.raises(Invalid, match="trace:exact"):
            compare(trace, read(ROOT / EXPECTED), binding=current_binding())


@pytest.mark.parametrize("field", ["invocation_token", *sorted(DIGEST_KEYS)])
def test_historical_proof_is_bound_to_current_session(field):
    with historical_trace() as (trace, _):
        binding = trace["proof"]["binding"]
        if field == "invocation_token":
            binding[field] = "stale"
        else:
            binding["digests"][field] = "f" * 64
        with pytest.raises(Invalid, match="trace_binding:session"):
            checked(trace)


def test_historical_projection_retains_cycle_guard():
    head = "a" * 64
    row = {"kind": "historical_execution_0_3", "value": {"previous_execution_head": head},
           "references": [{"path": ["previous_execution_head"], "sha256": head}]}
    from harness.trace import event
    with pytest.raises(Invalid, match="cyclic_reference"):
        _project_events([event("cycle", execution_head=head)], {head: row}, {}, version="0.3")
