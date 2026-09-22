"""B00C01 provenance and exactness tests, not durable control acceptance."""
from copy import deepcopy
from pathlib import Path

import pytest

from harness import pytest_evidence
from harness.contracts import ROOT, DIGEST_KEYS, load_contracts
from harness.failpoints import validate_runtime
from harness.exit_checks import Adapter, normalized_pytest, validate_exit
from harness.matrix import validate_matrix
from harness.pytest_evidence import observe, run_pytest, validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, canonical, read, sha, write_new
from harness.trace import compare, event, normalize
from harness.trace_proof import _project_events, source_digest, source_object
from helpers.trace_sources import current_binding, fresh_trace
from test_execution_0_4_foundation import rechain


EXPECTED = "tests/phase_b/expected_traces/trace_source_bound.json"
INVARIANTS = ["exact_semantic_trace", "raw_source_validation", "session_bound_proof"]


def checked(trace):
    return normalize(trace, binding=current_binding())


def test_source_bound_observation():
    first, second = fresh_trace(), fresh_trace(time_offset=500)
    assert first["proof"]["output_roots"] != second["proof"]["output_roots"]
    assert first["events"][-1]["checkpoint_head"] != second["events"][-1]["checkpoint_head"]
    expected = read(ROOT / EXPECTED)
    for trace in (first, second):
        compare(trace, expected, binding=current_binding())
    assert checked(first) == checked(second)
    observe("B00-TRACE-001", {"kind": "boolean", "value": True}, INVARIANTS, first)


@pytest.mark.parametrize("fault", ["hash", "missing", "duplicate", "orphan", "references", "wrong_kind",
                                  "unknown_kind", "unknown_field", "missing_proof", "semantic_actual",
                                  "unknown_version", "self_head", "stale_event", "foreign_event"])
def test_closed_proof_rejections(fault):
    trace = fresh_trace()
    objects = trace["proof"]["objects"]
    if fault == "hash":
        objects[0]["value"]["root_goal_reference"]["sha256"] = "f" * 64
    elif fault == "missing":
        objects.pop(-2)
    elif fault == "duplicate":
        objects.append(deepcopy(objects[0]))
    elif fault == "orphan":
        objects.append(source_object("canonical_json", {"unused": True}))
    elif fault == "references":
        objects[-1]["references"].pop()
    elif fault == "wrong_kind":
        objects[1]["kind"] = "canonical_json"
    elif fault == "unknown_kind":
        objects[0]["kind"] = "unvalidated_run"
    elif fault == "unknown_field":
        trace["proof"]["passing"] = True
    elif fault == "missing_proof":
        del trace["proof"]
    elif fault == "semantic_actual":
        trace = checked(trace)
    elif fault == "unknown_version":
        trace["schema_version"] = "0.99"
    elif fault == "self_head":
        objects[-1]["value"]["checkpoint_head"] = "a" * 64
    elif fault == "stale_event":
        trace["events"][-1]["execution_head"] = "a" * 64
    else:
        trace["events"][-1]["run_id"] = "foreign"
    with pytest.raises(Invalid):
        checked(trace)


@pytest.mark.parametrize("field", ["invocation_token", *sorted(DIGEST_KEYS)])
def test_proof_cannot_rebind_its_session(field):
    trace = fresh_trace()
    if field == "invocation_token":
        trace["proof"]["binding"][field] = "old-token"
    else:
        trace["proof"]["binding"]["digests"][field] = "f" * 64
    with pytest.raises(Invalid, match="trace_binding:session"):
        checked(trace)
    with pytest.raises(Invalid, match="trusted_session_required"):
        normalize(fresh_trace())


@pytest.mark.parametrize("field,value", [("owner", "foreign"), ("phase", "wrong"), ("route", "wrong"),
                                       ("operation_id", "another"), ("attempt_id", "another"),
                                       ("budget", [{"dimension": "attempt", "used": 2, "remaining": 0}])])
def test_semantic_event_changes_are_not_ephemeral(field, value):
    trace = fresh_trace()
    trace["events"][-1][field] = value
    with pytest.raises(Invalid, match="trace:exact"):
        compare(trace, read(ROOT / EXPECTED), binding=current_binding())


def test_rehashed_material_and_wrong_valid_head_remain_different():
    trace = fresh_trace(material_digest="f" * 64)
    checked(trace)
    with pytest.raises(Invalid, match="trace:exact"):
        compare(trace, read(ROOT / EXPECTED), binding=current_binding())
    trace = fresh_trace()
    trace["events"][-1]["execution_head"] = trace["events"][0]["execution_head"]
    checked(trace)
    with pytest.raises(Invalid, match="trace:exact"):
        compare(trace, read(ROOT / EXPECTED), binding=current_binding())


def test_legacy_trace_cannot_cross_versions_or_accept_semantic_actual():
    trace = fresh_trace()
    expected = read(ROOT / EXPECTED)
    with pytest.raises(Invalid):
        compare({"schema_version": "0.1", "events": expected["events"]}, expected)
    with pytest.raises(Invalid):
        compare(expected, expected, binding=current_binding())
    legacy = {"schema_version": "0.1", "events": [event("raw", execution_head="raw-head")]}
    assert normalize(legacy) == legacy
    with pytest.raises(Invalid):
        compare(trace, legacy, binding=current_binding())


def attach_content(trace, value):
    obj = source_object("canonical_json", value)
    trace["proof"]["objects"].append(obj)
    trace["events"][-1]["result_digest"] = obj["sha256"]


@pytest.mark.parametrize("fault", ["foreign_identity", "different_root", "relative", "parent_escape",
                                  "symlink", "duplicate_root", "missing_root"])
def test_root_and_path_rejections(fault):
    trace = fresh_trace()
    binding = trace["proof"]["output_roots"][0]
    root = Path(binding["path"])
    if fault == "foreign_identity":
        binding["run_id"] = "foreign"
    elif fault == "different_root":
        binding["path"] = fresh_trace()["proof"]["output_roots"][0]["path"]
    elif fault == "relative":
        binding["path"] = "relative"
    elif fault == "parent_escape":
        attach_content(trace, {"path": str(root) + "/../escaped"})
    elif fault == "symlink":
        (root / "escape").symlink_to(root.parent, target_is_directory=True)
        attach_content(trace, {"path": str(root / "escape/foreign")})
    elif fault == "duplicate_root":
        trace["proof"]["output_roots"].append(deepcopy(binding))
    else:
        trace["proof"]["output_roots"] = []
    with pytest.raises(Invalid):
        checked(trace)


def test_path_tags_cannot_collide_with_literal_business_content():
    first, second = fresh_trace(), fresh_trace()
    root = first["proof"]["output_roots"][0]["path"]
    attach_content(first, {"path": root + "/artifact.json"})
    attach_content(second, {"path": ["physical_path", ["case", "run"], "artifact.json"]})
    assert checked(first) != checked(second)


def test_rehashed_clock_regression_is_rejected_before_projection():
    trace = fresh_trace()
    records = [deepcopy(row["value"]) for row in trace["proof"]["objects"] if row["kind"] == "execution_0_4"]
    records[1]["created_at"]["monotonic_seconds"] = records[0]["created_at"]["monotonic_seconds"] - 1
    trace["proof"]["objects"] = [source_object("execution_0_4", row) for row in rechain(records)]
    trace["events"] = trace["events"][:-1]
    for obj, item in zip(trace["proof"]["objects"], trace["events"]):
        item["execution_head"] = obj["sha256"]
    with pytest.raises(Invalid, match="source_validation"):
        checked(trace)


def test_rehashed_checkpoint_state_must_match_the_manifest():
    trace = fresh_trace()
    objects = trace["proof"]["objects"]
    core = deepcopy(objects[-3]["value"])
    core["execution_event_index"] -= 1
    core_object = source_object("canonical_json", core)
    payload = deepcopy(objects[-2]["value"])
    payload.update(state=core, state_digest=core_object["sha256"])
    payload_object = source_object("canonical_json", payload)
    manifest = deepcopy(objects[-1]["value"])
    manifest.update(state_digest=core_object["sha256"], checkpoint_digest=payload_object["sha256"])
    manifest["checkpoint_head"] = source_digest("checkpoint_manifest", manifest)
    objects[-3:] = [core_object, payload_object, source_object("checkpoint_manifest", manifest)]
    trace["events"][-1]["checkpoint_head"] = manifest["checkpoint_head"]
    with pytest.raises(Invalid, match="checkpoint_proof:execution_event_index"):
        checked(trace)


@pytest.mark.parametrize("fault", ["overlap", "cross_run_head"])
def test_independently_valid_runs_cannot_alias_root_or_head(fault):
    first, second = fresh_trace(), fresh_trace()
    combined = deepcopy(first)
    combined["events"] = combined["events"][:-1]
    combined["proof"]["objects"] = combined["proof"]["objects"][:7]
    records = [deepcopy(row["value"]) for row in second["proof"]["objects"][:7]]
    root = Path(second["proof"]["output_roots"][0]["path"])
    if fault == "overlap":
        root = Path(first["proof"]["output_roots"][0]["path"]) / "nested"
        root.mkdir()
    for row in records:
        row["run_id"] = "second_run"
    records[0].update(canonical_output_root=str(root), checkpoint_thread_id="case:second_run")
    objects = [source_object("execution_0_4", row) for row in rechain(records)]
    combined["proof"]["objects"].extend(objects)
    combined["proof"]["output_roots"].append({"case_id": "case", "run_id": "second_run", "path": str(root)})
    for row in objects:
        combined["events"].append(event("second_run", run_id="second_run", execution_head=row["sha256"]))
    if fault == "cross_run_head":
        checked(combined)
        combined["events"][0]["execution_head"] = objects[0]["sha256"]
    with pytest.raises(Invalid, match="overlapping_roots" if fault == "overlap" else "event_run_binding"):
        checked(combined)


def test_projection_cycle_guard_is_independent_of_raw_hash_rejection():
    # A valid SHA cycle is computationally infeasible; test the DAG guard itself
    # with deliberately unverified objects, never through an acceptance writer.
    head = "a" * 64
    row = {"kind": "canonical_json", "value": {"state_digest": head},
           "references": [{"path": ["state_digest"], "sha256": head}]}
    with pytest.raises(Invalid, match="cyclic_reference"):
        _project_events([event("cycle", result_digest=head)], {head: row}, {})


def test_real_subprocess_and_runtime_comparison(tmp_path):
    subprocess_and_runtime_comparison(tmp_path, "0.2")


def subprocess_and_runtime_comparison(tmp_path, trace_version):
    root = tmp_path / "isolated-project"
    (root / "tests").mkdir(parents=True)
    (root / "src/lqcd_agent").mkdir(parents=True)
    # This isolated hook demonstrates the validator path only. It is never a
    # binding in the project's production registry or a B02 passing scenario.
    (root / "src/lqcd_agent/probe.py").write_text(
        'from harness.pytest_evidence import production_hook\n'
        'def boundary():\n    production_hook("synthetic.trace")\n', encoding="utf-8")
    source_import = ('from helpers.trace_sources import fresh_trace\n' if trace_version == "0.2" else
                     'from helpers.historical_trace_sources import fresh_historical_trace as fresh_trace\n')
    (root / "tests/test_probe.py").write_text(
        'import runpy\n' + source_import +
        'from harness.pytest_evidence import observe, observe_case\n'
        'def test_bound():\n'
        '    trace = fresh_trace()\n'
        '    runpy.run_path("src/lqcd_agent/probe.py")["boundary"]()\n'
        '    observe("synthetic", {"kind":"boolean", "value":True}, ["raw_checked"], trace)\n'
        '    observe_case("synthetic.trace", "validated", ["raw_checked"], trace)\n', encoding="utf-8")
    expected_path = EXPECTED if trace_version == "0.2" else "tests/phase_b/expected_traces/historical_trace_fork.json"
    write_new(root / "tests/expected.json", read(ROOT / expected_path))
    session = Session(root, tmp_path / "evidence", {k: "a" * 64 for k in DIGEST_KEYS if k != "worktree_inputs"})
    node = "tests/test_probe.py::test_bound"
    value = run_pytest(session, [node])
    validate_pytest(value, session, [node])
    scenario = {"scenario_id": "synthetic", "pytest_nodeids": [node],
                "expected_result": {"kind": "boolean", "value": True}, "required_invariants": ["raw_checked"],
                "expected_trace_fixture": "tests/expected.json"}
    validate_observations(value, [scenario], root)
    registry = {"entries": [{"hook_ref": "src/lqcd_agent/probe.py:boundary", "case_bindings": [
        {"case_id": "synthetic.trace", "scenario_ids": ["synthetic"]}]}]}
    specs = {"synthetic.trace": {"outcome": "validated", "invariants": ["raw_checked"]}}
    assert validate_runtime(value, registry, specs, [scenario], root) == ["synthetic.trace"]
    adapter = Adapter(lambda _: pytest.fail("Evidence already came from a real subprocess"), (node,), (scenario,))

    def exit_result(artifact, active_session, name):
        path = active_session.directory / (name + ".json")
        write_new(path, artifact)
        envelope = {"schema_version": "0.1", "invocation_token": active_session.token,
                    "check_id": "layer_0", "digests": active_session.digests, "exit_code": 0,
                    "evidence_refs": [{"relative_path": path.name, "sha256": sha(path.read_bytes())}]}
        return validate_exit(envelope, "layer_0", active_session, adapter)

    first_digest = exit_result(value, session, "valid-exit")
    second_session = Session(root, tmp_path / "second-evidence", session.digests)
    second = run_pytest(second_session, [node])
    assert second_session.token != session.token
    assert second_session.digests == session.digests
    assert value["observations"][0]["trace"]["proof"]["output_roots"] != second["observations"][0]["trace"]["proof"]["output_roots"]
    assert exit_result(second, second_session, "valid-exit") == first_digest
    normalized = canonical(normalized_pytest(value))
    assert normalized == canonical(normalized_pytest(second))
    assert b'"proof"' not in normalized and b'"invocation_token"' not in normalized
    for artifact in (value, second):
        assert artifact["invocation_token"].encode() not in normalized
        for binding in artifact["observations"][0]["trace"]["proof"]["output_roots"]:
            assert binding["path"].encode() not in normalized
    second_session.unchanged()
    for field in ("observations", "case_results"):
        bad = deepcopy(value)
        bad[field][0]["trace"]["proof"]["binding"]["invocation_token"] = "stale"
        with pytest.raises(Invalid):
            validate_pytest(bad, session, [node])
        with pytest.raises(Invalid):
            if field == "observations":
                validate_observations(bad, [scenario], root)
            else:
                validate_runtime(bad, registry, specs, [scenario], root)
        # Recompute the outer file hash for each mutation. Rejection must come
        # from the proof/session checks, not merely a stale artifact checksum.
        for fault in ("invocation_token", *sorted(DIGEST_KEYS), "source_tamper"):
            bad = deepcopy(value)
            proof = bad[field][0]["trace"]["proof"]
            if fault == "invocation_token":
                proof["binding"][fault] = "stale"
            elif fault == "source_tamper":
                proof["objects"][0]["value"]["root_goal_reference"]["sha256"] = "f" * 64
            else:
                proof["binding"]["digests"][fault] = "f" * 64
            with pytest.raises(Invalid, match="trace_binding:session|source:raw_digest"):
                exit_result(bad, session, field + "-" + fault)
    for fault in ("invocation_token", *sorted(DIGEST_KEYS)):
        bad = deepcopy(value)
        if fault == "invocation_token":
            bad[fault] = "stale"
        else:
            bad["digests"][fault] = "f" * 64
        for field in ("observations", "case_results"):
            bad[field][0]["trace"]["proof"]["binding"] = {
                "invocation_token": bad["invocation_token"], "digests": dict(bad["digests"])}
        with pytest.raises(Invalid, match="evidence:invocation_token|evidence:digests"):
            exit_result(bad, session, "coherently-stale-" + fault)
    session.unchanged()
    matrix = read(ROOT / "tests/phase_b/acceptance_matrix.json")
    # Keep the historical C01/C03 regression scoped to its prerequisite slices.
    matrix["implementation_slices"] = [part for part in matrix["implementation_slices"] if part["ticket_id"] in ("B00", "B01")]
    matrix["scenarios"] = [row for row in matrix["scenarios"] if row["implementation_ticket_id"] in ("B00", "B01")]
    slices, covered = validate_matrix(matrix, load_contracts()[1], ROOT)
    assert list(slices) == ["B00", "B01"] and len(covered) == 26
    scenario_id = "B00-TRACE-002" if trace_version == "0.2" else "B00-TRACE-HISTORICAL-002"
    observe(scenario_id, {"kind": "boolean", "value": True},
            ["fresh_subprocess", "parent_proof_validation", "runtime_comparison_path"])


def test_writer_rejects_stale_case_before_serialization(monkeypatch):
    from types import SimpleNamespace

    binding = current_binding()
    writer = SimpleNamespace(value={**binding, "observations": [], "case_results": []}, nodeid="synthetic")
    monkeypatch.setattr(pytest_evidence, "ACTIVE", writer)
    trace = fresh_trace()
    trace["proof"]["binding"]["invocation_token"] = "stale"
    with pytest.raises(Invalid):
        observe("synthetic", {"kind": "boolean", "value": True}, [], trace)
    with pytest.raises(Invalid):
        pytest_evidence.observe_case("synthetic", "validated", [], trace)
    assert writer.value["observations"] == writer.value["case_results"] == []
