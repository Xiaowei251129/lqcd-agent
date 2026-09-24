"""Trace 0.5 evidence plumbing; isolated hooks never claim B03 runtime cases."""
from copy import deepcopy

import pytest

from harness import pytest_evidence
from harness.contracts import ROOT, DIGEST_KEYS
from harness.failpoints import validate_runtime
from harness.exit_checks import Adapter, normalized_pytest, validate_exit
from harness.pytest_evidence import observe, run_pytest, validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, canonical, read, sha, write_new
from helpers.trace_sources import current_binding
from helpers.a05_traces import full_trace


def test_a05_four_evidence_paths(tmp_path):
    root = tmp_path / "isolated-project"
    (root / "tests").mkdir(parents=True)
    (root / "src/lqcd_agent").mkdir(parents=True)
    # This isolated hook demonstrates the validator path only. It is never a
    # binding in the project's production registry or a B02 passing scenario.
    (root / "src/lqcd_agent/probe.py").write_text(
        'from harness.pytest_evidence import production_hook\n'
        'def boundary():\n    production_hook("synthetic.trace")\n', encoding="utf-8")
    source_import = "from helpers.a05_traces import full_trace\n"
    (root / "tests/test_probe.py").write_text(
        'import runpy\n' + source_import +
        'from harness.pytest_evidence import observe, observe_case\n'
        'def test_bound():\n'
        '    trace, _ = full_trace()\n'
        '    runpy.run_path("src/lqcd_agent/probe.py")["boundary"]()\n'
        '    observe("synthetic", {"kind":"boolean", "value":True}, ["raw_checked"], trace)\n'
        '    observe_case("synthetic.trace", "validated", ["raw_checked"], trace)\n', encoding="utf-8")
    expected_path = "tests/phase_b/expected_traces/a05_normal.json"
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
        missing = deepcopy(value)
        missing[field][0]["trace"]["events"][-1]["analysis_spec_digest"] = "a" * 64
        with pytest.raises(Invalid):
            validate_pytest(missing, session, [node])
        with pytest.raises(Invalid):
            if field == "observations":
                validate_observations(missing, [scenario], root)
            else:
                validate_runtime(missing, registry, specs, [scenario], root)
        with pytest.raises(Invalid):
            exit_result(missing, session, field + "-missing-a05-source")
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
    observe("B00-A05-PIPELINE", {"kind": "boolean", "value": True},
            ["exit_semantic_binding", "fresh_subprocess", "parent_proof_validation", "runtime_comparison_path"])


def test_a05_collector_rejects_digest_before_serialization(monkeypatch):
    from types import SimpleNamespace

    trace, _ = full_trace()
    trace["events"][-1]["analysis_spec_digest"] = "a" * 64
    writer = SimpleNamespace(value={**current_binding(), "observations": [], "case_results": []}, nodeid="synthetic")
    monkeypatch.setattr(pytest_evidence, "ACTIVE", writer)
    with pytest.raises(Invalid):
        observe("synthetic", {"kind": "boolean", "value": True}, [], trace)
    with pytest.raises(Invalid):
        pytest_evidence.observe_case("synthetic", "validated", [], trace)
    assert writer.value["observations"] == writer.value["case_results"] == []
