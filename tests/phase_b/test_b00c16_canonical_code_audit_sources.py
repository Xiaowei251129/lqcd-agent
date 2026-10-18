"""C16 actual canonical Code sources, independent owners and closed rejection."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys

import pytest

from harness.contracts import ROOT
from harness.pytest_evidence import observe
from harness.strict_json import Invalid, read
from harness.trace import compare, normalize
from helpers.product_failure_sources import code_product_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, loads


MODES = {"empty": (False, False), "success": (True, False), "repeat_empty": (False, True), "repeat_success": (True, True)}
INVARIANTS = ["B04_owned_false", "canonical_audit_profile", "exact_owner_bindings", "original_B03_ports", "single_effect"]


def records(trace):
    return [row["value"] for row in trace["proof"]["objects"] if row["kind"] == "execution_0_4"]


def legacy(trace):
    old = deepcopy(trace)
    old["schema_version"], old["proof"]["schema_version"] = "0.7", "0.4"
    for key in ("product_failure_sources", "product_grant_sources"):
        old["proof"].pop(key)
    return old


def files(trace):
    return {str(path): path.read_bytes() for row in trace["proof"]["output_roots"]
            for path in Path(row["path"]).rglob("*") if path.is_file() and not path.name.endswith(("-shm", "-wal"))}


@pytest.fixture(scope="module")
def canonical():
    source = code_product_trace(success=True)
    (source[1] / "C16-baseline-raw.json").write_bytes(canonical_bytes(source[0]))
    return source


@pytest.mark.parametrize("mode", MODES)
def test_dual_fresh_canonical_sources(mode, canonical):
    success, repeat = MODES[mode]
    first = canonical if mode == "success" else code_product_trace(success=success, repeat=repeat)
    second = code_product_trace(success=success, repeat=repeat)
    traces = []
    for trace, output, facts in (first, second):
        assert not facts["B04_owned"] and not facts["Code_parent_delivered"]
        assert facts["Code_target_from_product_selector"] and facts["original_Code_ports"]
        count = 2 if repeat else 1
        assert facts["same_Run_Code_attempts"] == count
        assert len(facts["dispatches"]) == len(set(facts["dispatches"])) == count
        rows = records(trace)
        code = [r for r in rows if r.get("event") == "finished" and r.get("attempt_kind") == "code_agent"]
        assert len(code) == count and len({r["attempt_id"] for r in code}) == count
        backend_reservations = [r for r in rows if r.get("event") == "resource_reserved" and r["payload"]["resource_kind"] == "code_backend_operation"]
        for reserved in backend_reservations:
            settlements = [r for r in rows if r.get("event") == "resource_settled" and
                           r["payload"]["resource_operation_id"] == reserved["payload"]["resource_operation_id"]]
            assert len(settlements) == 1
        audits = [m for m in trace["proof"]["material_sources"] if m["kind"] == "canonical_tool_audit"]
        assert len(audits) == count and len({tuple(m["owner"].values()) for m in audits}) == count
        if repeat and not success:
            assert len({m["sha256"] for m in audits}) == 1 and all(m["content"] == "" for m in audits)
        if repeat and success:
            patches = [m for m in trace["proof"]["material_sources"] if m["kind"] == "material"]
            assert len(patches) == 2 and patches[0]["sha256"] == patches[1]["sha256"]
            assert patches[0]["owner"] != patches[1]["owner"]
            assert len([r for r in rows if r.get("event") == "resource_reserved" and
                        r["payload"]["resource_kind"] == "verification_command"]) == 2
        before = files(trace)
        normalized = normalize(trace, binding=current_binding())
        assert normalized == normalize(trace, binding=current_binding()) and files(trace) == before
        with pytest.raises(Invalid):
            normalize(legacy(trace), binding=current_binding())
        compare(trace, read(ROOT / ("tests/phase_b/expected_traces/b00c16/code_" + mode + ".json")), binding=current_binding())
        (output / "C16-raw.json").write_bytes(canonical_bytes(trace))
        (output / "C16-normalized.json").write_bytes(canonical_bytes(normalized))
        traces.append(normalized)
    assert first[1] != second[1] and traces[0] == traces[1]
    observe("B00C16-" + mode.upper(), {"kind": "boolean", "value": True}, INVARIANTS, first[0])


@pytest.mark.parametrize("fault", ["missing", "duplicate", "orphan", "foreign", "kind", "bytes", "sha", "task", "workspace", "argv", "cwd",
                                  "time", "usage", "path", "extra", "dialect", "epoch", "fake_effect", "stale"])
def test_closed_source_and_owner_rejections(canonical, fault):
    trace = deepcopy(canonical[0])
    proof = trace["proof"]
    material = next(row for row in proof["material_sources"] if row["kind"] == "canonical_tool_audit")
    if fault == "missing": proof["material_sources"].remove(material)
    elif fault == "duplicate": proof["material_sources"].append(deepcopy(material))
    elif fault == "orphan":
        extra = deepcopy(material); extra["owner"]["attempt_id"] = "attempt_999999"; proof["material_sources"].append(extra)
    elif fault == "foreign": material["owner"]["producer_operation_id"] = "foreign"
    elif fault == "kind": material["kind"] = "unknown_tool_audit"
    elif fault == "bytes": material["content"] += " "
    elif fault == "sha": material["sha256"] = "f" * 64
    elif fault == "stale": proof["binding"]["invocation_token"] = "stale"
    elif fault in ("epoch", "fake_effect"):
        final = next(row for row in proof["objects"] if row["value"].get("proof_kind") == "safe_stop" and
                     "resource_actual" in row["value"])
        if fault == "epoch": final["value"]["lease_epoch"] += 1
        else: final["value"]["resource_actual"]["tool_calls"] += 1
    else:
        audit = loads(material["content"].splitlines()[0])
        if fault == "task": audit["task_id"] = "foreign"
        elif fault == "workspace": audit["workspace_id"] = "foreign"
        elif fault == "argv": audit["argv_digest"] = "f" * 64
        elif fault == "cwd": audit["cwd"] = "elsewhere"
        elif fault == "time": audit["end_at"] = audit["start_at"] - 1
        elif fault == "usage": audit["resource_usage"]["tool_calls"] = 0
        elif fault == "path": audit["affected_paths"] = ["../escape"]
        elif fault == "extra": audit["accepted"] = True
        elif fault == "dialect": audit["started_at"] = audit.pop("start_at")
        material["content"] = (canonical_bytes(audit) + b"\n").decode()
        material["sha256"] = sha256(material["content"].encode()).hexdigest()
    with pytest.raises(Invalid):
        normalize(trace, binding=current_binding())


@pytest.mark.parametrize("change", ["requirements", "change", "command"])
def test_legitimate_causal_material_changes(canonical, change):
    options = {"requirements": {"requirement": "Return a newly requested observable"},
               "change": {"changed_content": b"def value():\n    return 3\n"},
               "command": {"command": [sys.executable, "-I", "-S", "-c", "print('new analysis command')"]}}[change]
    varied, _, _ = code_product_trace(success=True, **options)
    assert normalize(varied, binding=current_binding()) != normalize(canonical[0], binding=current_binding())
    original = next(r for r in records(canonical[0]) if r.get("event") == "failure_observed")["payload"]["fingerprint"]
    changed = next(r for r in records(varied) if r.get("event") == "failure_observed")["payload"]["fingerprint"]
    assert original["causal_context_digest"] != changed["causal_context_digest"]


def test_known_clock_and_locator_changes_preserve_scientific_key(canonical):
    varied, output, _ = code_product_trace(success=True, clock_time=200)
    (output / "C16-clock-raw.json").write_bytes(canonical_bytes(varied))
    # Pause deadlines and A03/checkpoint timestamps keep their original meaning.
    assert normalize(varied, binding=current_binding()) != normalize(canonical[0], binding=current_binding())
    original = next(r for r in records(canonical[0]) if r.get("event") == "failure_observed")["payload"]["fingerprint"]
    changed = next(r for r in records(varied) if r.get("event") == "failure_observed")["payload"]["fingerprint"]
    assert original == changed


def test_only_canonical_audit_clocks_are_normalized(canonical):
    varied, output, _ = code_product_trace(success=True, audit_time=200)
    (output / "C16-audit-clock-raw.json").write_bytes(canonical_bytes(varied))
    assert normalize(varied, binding=current_binding()) == normalize(canonical[0], binding=current_binding())


def test_original_bytes_cannot_claim_another_task_command():
    trace, output, _ = code_product_trace(success=True, audit_fault="argv")
    (output / "C16-wrong-command-raw.json").write_bytes(canonical_bytes(trace))
    with pytest.raises(Invalid, match="audit_command"):
        normalize(trace, binding=current_binding())


def test_original_final_rejects_an_unobserved_audit_effect():
    with pytest.raises(ControlIntegrityError, match="omits a Host-observed invocation"):
        code_product_trace(success=True, audit_fault="extra_event")


def test_cross_run_sharing_is_supplemental_and_has_separate_owners(canonical):
    second, _, _ = code_product_trace(success=True, label="second-owner")
    combined = deepcopy(canonical[0])
    combined["events"].extend(deepcopy(second["events"]))
    for key, values in second["proof"].items():
        if type(values) is list:
            combined["proof"][key].extend(deepcopy(row) for row in values if row not in combined["proof"][key])
    lookup = {row["sha256"]: row["value"] for row in combined["proof"]["objects"]}
    for field, head in (("product_failure_sources", "failure_head"), ("product_grant_sources", "grant_head")):
        combined["proof"][field].sort(key=lambda d: (lookup[d[head]]["case_id"], lookup[d[head]]["run_id"], lookup[d[head]]["event_index"]))
    assert len(combined["proof"]["output_roots"]) == 2
    assert normalize(combined, binding=current_binding())
    with pytest.raises(Invalid):
        normalize(legacy(combined), binding=current_binding())
