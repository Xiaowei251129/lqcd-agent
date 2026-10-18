"""C11 four consumer paths; isolated hooks confer no runtime coverage."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT, DIGEST_KEYS
from harness.failpoints import validate_runtime
from harness.exit_checks import Adapter, normalized_pytest, validate_exit
from harness.pytest_evidence import run_pytest, validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, canonical, read, sha, write_new


@pytest.mark.parametrize("kind", ["maximum", "human"])
def test_new_source_four_evidence_paths(tmp_path, kind):
    root = tmp_path / "isolated-project"
    (root / "tests").mkdir(parents=True)
    (root / "src/lqcd_agent").mkdir(parents=True)
    # This isolated hook demonstrates the validator path only. It is never a
    # binding in the project's production registry or a B04 passing scenario.
    (root / "src/lqcd_agent/probe.py").write_text(
        'from harness.pytest_evidence import production_hook\n'
        'def boundary():\n    production_hook("synthetic.c11")\n', encoding="utf-8")
    source_import = "from helpers.ordinary_" + ("maximum" if kind == "receipt" else kind) + " import " + ("human_trace" if kind == "human" else "maximum_trace") + " as source_trace\n"
    if kind in ("approve_rerun", "reject_or_hold"):
        source_import = 'from test_b00c13_human_continuation import continuation\ndef source_trace():\n    return continuation("' + kind + '")\n'
    (root / "tests/test_probe.py").write_text(
        'import runpy\n' + source_import +
        'from harness.pytest_evidence import observe, observe_case\n'
        'def test_bound():\n' +
        ('    trace, _, _ = source_trace(host_receipt=True)\n' if kind == "receipt" else '    trace, _, _ = source_trace()\n') +
        '    runpy.run_path("src/lqcd_agent/probe.py")["boundary"]()\n'
        '    observe("synthetic", {"kind":"boolean", "value":True}, ["raw_checked"], trace)\n'
        '    observe_case("synthetic.c11", "validated", ["raw_checked"], trace)\n', encoding="utf-8")
    expected_path = "tests/phase_b/expected_traces/" + ("b00c12/" + kind + ".json" if kind in ("human", "receipt") else "b00c11/maximum.json")
    if kind == "human":
        expected_path = "tests/phase_b/expected_traces/b00c16/human_prefix.json"
    elif kind in ("approve_rerun", "reject_or_hold"):
        expected_path = "tests/phase_b/expected_traces/b00c16/" + kind + ".json"
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
        {"case_id": "synthetic.c11", "scenario_ids": ["synthetic"]}]}]}
    specs = {"synthetic.c11": {"outcome": "validated", "invariants": ["raw_checked"]}}
    assert validate_runtime(value, registry, specs, [scenario], root) == ["synthetic.c11"]
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
        missing[field][0]["trace"]["events"][-1]["result_digest"] = "a" * 64
        with pytest.raises(Invalid):
            validate_pytest(missing, session, [node])
        with pytest.raises(Invalid):
            if field == "observations":
                validate_observations(missing, [scenario], root)
            else:
                validate_runtime(missing, registry, specs, [scenario], root)
        with pytest.raises(Invalid):
            exit_result(missing, session, field + "-missing-new-source")
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
        for fault in ("invocation_token", *sorted(DIGEST_KEYS), "missing_source", "source_tamper", "foreign_source"):
            bad = deepcopy(value)
            proof = bad[field][0]["trace"]["proof"]
            if fault == "invocation_token":
                proof["binding"][fault] = "stale"
            elif fault == "source_tamper":
                proof["objects"][0]["value"]["root_goal_reference"]["sha256"] = "f" * 64
            elif fault == "missing_source":
                proof["objects"].pop(0)
            elif fault == "foreign_source":
                proof["ordinary_calls"][0]["authorization"]["identity"]["run_id"] = "foreign"
            else:
                proof["binding"]["digests"][fault] = "f" * 64
            with pytest.raises(Invalid):
                validate_pytest(bad, session, [node])
            with pytest.raises(Invalid):
                if field == "observations":
                    validate_observations(bad, [scenario], root)
                else:
                    validate_runtime(bad, registry, specs, [scenario], root)
            with pytest.raises(Invalid):
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
            validate_pytest(bad, session, [node])
        with pytest.raises(Invalid, match="evidence:invocation_token|evidence:digests"):
            exit_result(bad, session, "coherently-stale-" + fault)
    session.unchanged()
