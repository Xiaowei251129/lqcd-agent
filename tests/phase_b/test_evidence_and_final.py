"""Real subprocess rejection probes and isolated final-driver fixtures."""
from copy import deepcopy
from pathlib import Path

import pytest

from harness.contracts import ROOT, DIGEST_KEYS, EXIT_CHECKS, load_contracts, required_ids
from harness.strict_json import Invalid, canonical, read, sha, write_new
from harness.session import Session
from harness.pytest_evidence import run_pytest, validate_pytest
from harness.driver import execute, exit_code
from harness.exit_checks import Adapter, BENCHMARK_ITEMS, SMOKE_INVARIANTS, DOC_INVARIANTS, validate_exit
from harness.meta_fixtures import meta_trace
from harness.report import validate_report


def session_for(root, evidence):
    return Session(root, evidence, {k: "a" * 64 for k in DIGEST_KEYS if k != "worktree_inputs"})


def exercise_real_pytest(tmp_path):
    root = tmp_path / "subprocess-project"
    (root / "tests").mkdir(parents=True)
    probe = root / "tests/test_probe.py"
    probe.write_text('''import pytest
from harness import pytest_evidence as evidence

def test_pass():
    assert 2 + 2 == 4

def test_skip():
    pytest.skip("negative evidence probe")

@pytest.mark.xfail(reason="negative evidence probe")
def test_xfail():
    assert False

@pytest.mark.xfail(reason="unexpected passing probe")
def test_xpass():
    pass

@pytest.mark.xfail(reason="strict unexpected passing probe", strict=True)
def test_strict_xpass():
    pass

@pytest.fixture
def broken_setup():
    assert False

@pytest.fixture
def broken_teardown():
    yield
    assert False

def test_setup(broken_setup):
    pass

def test_teardown(broken_teardown):
    pass

def test_stale():
    evidence.ACTIVE.value["invocation_token"] = "previous-invocation"

def test_unknown():
    evidence.ACTIVE.value["nodes"].append({"nodeid":"tests/test_probe.py::unknown","when":"call","outcome":"passed","xfail":False})

def test_duplicate():
    evidence.ACTIVE.value["nodes"].append({"nodeid":"tests/test_probe.py::test_duplicate","when":"call","outcome":"passed","xfail":False})
''', encoding="utf-8")
    for name in ("pass", "skip", "xfail", "xpass", "strict_xpass", "setup", "teardown", "stale", "unknown", "duplicate", "deselect"):
        selected = ["tests/test_probe.py::test_" + ("pass" if name == "deselect" else name)]
        session = session_for(root, tmp_path / ("evidence-" + name))
        result = run_pytest(session, selected, extra=("-k", "does_not_exist") if name == "deselect" else ())
        if name == "pass":
            validate_pytest(result, session, selected)
        else:
            with pytest.raises(Invalid):
                validate_pytest(result, session, selected)
        session.unchanged()


def synthetic_inputs(tmp_path):
    root = tmp_path / "isolated-final-project"
    (root / "tests").mkdir(parents=True)
    (root / "tests/test_synthetic.py").write_text("def test_control():\n    pass\n", encoding="utf-8")
    write_new(root / "tests/trace.json", meta_trace())
    full = "evaluation/synthetic_benchmarks/case_sets/full.json"
    write_new(root / full, read(ROOT / full))
    required = required_ids(load_contracts()[1])
    node = "tests/test_synthetic.py::test_control"
    invariants = sorted(SMOKE_INVARIANTS | DOC_INVARIANTS)
    scenarios = [{"scenario_id": "synthetic-" + rid, "contract_refs": [rid], "required": True,
                  "implementation_ticket_id": "B00", "validation_stage": "final", "pytest_nodeids": [node],
                  "expected_result": {"kind": "boolean", "value": True}, "required_invariants": invariants,
                  "expected_trace_fixture": "tests/trace.json"} for rid in required]
    specs = {f"post_claim.synthetic_{i:02d}": {"failpoint_id": f"synthetic_{i:02d}", "outcome": "failed_closure",
                                             "invariants": ["same_owner"]} for i in range(28)}
    registry = {"entries": [{"failpoint_id": spec["failpoint_id"], "hook_ref": "src/lqcd_agent/synthetic.py:boundary",
                             "case_bindings": [{"case_id": cid, "scenario_ids": [scenarios[0]["scenario_id"]]}]}
                            for cid, spec in specs.items()]}
    obligations = {"runtime_obligations": [{"contract_refs": required, "case_ids": list(specs)}]}
    return {"root": root, "required": required, "covered": required, "specs": specs, "registry": registry,
            "matrix": {"scenarios": scenarios}, "obligations": obligations, "slices": {"B00": required}}


def synthetic_pytest(inputs, session, selection):
    scenarios = inputs["matrix"]["scenarios"]
    return {"schema_version": "0.1", "invocation_token": session.token, "digests": session.digests,
            "selection": selection, "collected": selection, "deselected": [], "exit_code": 0,
            "nodes": [{"nodeid": n, "when": p, "outcome": "passed", "xfail": False}
                      for n in selection for p in ("setup", "call", "teardown")],
            "observations": [{"scenario_id": s["scenario_id"], "nodeid": n, "result": s["expected_result"],
                              "invariants": s["required_invariants"], "trace": meta_trace()}
                             for s in scenarios for n in s["pytest_nodeids"]],
            "hook_events": [{"case_id": cid, "nodeid": selection[0], "hook_ref": "src/lqcd_agent/synthetic.py:boundary"}
                            for cid in inputs["specs"]],
            "case_results": [{"case_id": cid, "nodeid": selection[0], "outcome": spec["outcome"],
                              "invariants": spec["invariants"], "trace": meta_trace()}
                            for cid, spec in inputs["specs"].items()]}


def benchmark_artifact(root):
    return {"schema_version": "0.1", "passed": True, "cases": [
        {"case_id": cid, "passed": True, "review_needed": False,
         "items": [{"name": name, "passed": True} for name in BENCHMARK_ITEMS]}
        for cid in read(root / "evaluation/synthetic_benchmarks/case_sets/full.json")["case_ids"]]}


def synthetic_adapters(inputs, mutation=None):
    scenarios = tuple(inputs["matrix"]["scenarios"])
    selection = tuple(sorted({n for s in scenarios for n in s["pytest_nodeids"]}))
    adapters = {}
    for cid in EXIT_CHECKS:
        def run(session, cid=cid):
            artifact = (benchmark_artifact(session.root) if cid == "full_mock_benchmark" else
                        {"schema_version": "0.1", "files": ["tests/test_synthetic.py"], "failures": []}
                        if cid == "compileall" else synthetic_pytest(inputs, session, list(selection)))
            if mutation:
                mutation(cid, artifact)
            path = session.directory / (cid + ".json")
            write_new(path, artifact)
            return {"schema_version": "0.1", "invocation_token": session.token, "check_id": cid,
                    "digests": session.digests, "exit_code": 0,
                    "evidence_refs": [{"relative_path": path.name, "sha256": sha(path.read_bytes())}]}
        adapters[cid] = Adapter(run, selection, scenarios, ("tests/test_synthetic.py",))
    return adapters


def exercise_final_gate(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    reports = []
    for n in range(2):
        session = session_for(inputs["root"], tmp_path / f"success-{n}")
        reports.append(execute(inputs, session, "final", _adapters=synthetic_adapters(inputs),
                               _pytest_runner=lambda s, ns: synthetic_pytest(inputs, s, ns)))
    assert reports[0]["requirements_zero_gap"] and reports[0]["phase_b_complete"]
    assert exit_code(reports[0]) == 0
    assert canonical(reports[0]) == canonical(reports[1])
    for missing in ("cli_smoke", "full_mock_benchmark", "legacy_regression"):
        adapters = synthetic_adapters(inputs)
        del adapters[missing]
        report = execute(inputs, session_for(inputs["root"], tmp_path / missing), "final", _adapters=adapters,
                         _pytest_runner=lambda *_: pytest.fail("Preflight must not run tests"))
        assert report["requirements"]["covered"] == 131 and report["requirements"]["remaining"] == 0
        assert not report["phase_b_complete"] and exit_code(report) == 1
        assert any(e["category"] == "exit_evidence_gap" and e["object_id"] == missing for e in report["errors"])


@pytest.mark.parametrize("mutation", ["missing_hook", "missing_case", "no_trigger", "wrong_outcome", "trace_drift",
                                     "old_token", "worktree_digest", "contract_digest", "changed_inputs", "internal"])
def test_final_rejects_runtime_and_stale_evidence(tmp_path, mutation):
    inputs = synthetic_inputs(tmp_path)
    session = session_for(inputs["root"], tmp_path / "evidence")
    if mutation == "missing_hook":
        inputs["registry"]["entries"][0]["hook_ref"] = None
    if mutation == "missing_case":
        inputs["registry"]["entries"][0]["case_bindings"] = []
    def runner(s, selection):
        value = synthetic_pytest(inputs, s, selection)
        if mutation == "no_trigger":
            value["hook_events"].pop()
        elif mutation == "wrong_outcome":
            value["case_results"][0]["outcome"] = "unavailable_closure"
        elif mutation == "trace_drift":
            value["case_results"][0]["trace"]["events"][0]["run_id"] = "foreign"
        elif mutation == "old_token":
            value["invocation_token"] = "stale"
        elif mutation in {"worktree_digest", "contract_digest"}:
            value["digests"] = dict(value["digests"], **{"worktree_inputs" if mutation == "worktree_digest" else "protocol": "b" * 64})
        elif mutation == "changed_inputs":
            (inputs["root"] / "tests/new.py").write_text("dirty = True\n", encoding="utf-8")
        elif mutation == "internal":
            raise RuntimeError("isolated error")
        return value
    report = execute(inputs, session, "final", _adapters=synthetic_adapters(inputs), _pytest_runner=runner)
    assert not report["phase_b_complete"] and not report["requirements_zero_gap"] and exit_code(report) == 1
    assert report["errors"]


@pytest.mark.parametrize("fault", ["case_false", "item_false", "missing_item", "missing_case", "duplicate_case", "false_total"])
def test_benchmark_zero_exit_is_not_success(tmp_path, fault):
    inputs = synthetic_inputs(tmp_path)
    def mutate(cid, value):
        if cid != "full_mock_benchmark":
            return
        if fault == "case_false":
            value["cases"][0]["passed"] = False
        elif fault == "item_false":
            value["cases"][0]["items"][0]["passed"] = False
        elif fault == "missing_item":
            value["cases"][0]["items"].pop()
        elif fault == "missing_case":
            value["cases"].pop()
        elif fault == "duplicate_case":
            value["cases"].append(deepcopy(value["cases"][0]))
        else:
            value["passed"] = False
    report = execute(inputs, session_for(inputs["root"], tmp_path / "evidence"), "final",
                     _adapters=synthetic_adapters(inputs, mutate), _pytest_runner=lambda s, ns: synthetic_pytest(inputs, s, ns))
    assert report["requirements_zero_gap"] and not report["phase_b_complete"] and exit_code(report) == 1
    assert next(row for row in report["exit_checks"] if row["check_id"] == "full_mock_benchmark")["status"] == "failed"


@pytest.mark.parametrize("fault", ["stale", "unknown", "missing_ref", "duplicate_ref", "hash", "escape", "exit", "extra"])
def test_exit_envelope_rejection(tmp_path, fault):
    inputs = synthetic_inputs(tmp_path)
    session = session_for(inputs["root"], tmp_path / "evidence")
    cid = "full_mock_benchmark"
    adapter = synthetic_adapters(inputs)[cid]
    evidence = adapter.run(session)
    if fault == "stale":
        evidence["invocation_token"] = "stale"
    elif fault == "unknown":
        evidence["check_id"] = "unknown"
    elif fault == "missing_ref":
        evidence["evidence_refs"] = []
    elif fault == "duplicate_ref":
        evidence["evidence_refs"] *= 2
    elif fault == "hash":
        evidence["evidence_refs"][0]["sha256"] = "b" * 64
    elif fault == "escape":
        evidence["evidence_refs"][0]["relative_path"] = "../outside.json"
    elif fault == "exit":
        evidence["exit_code"] = 1
    else:
        evidence["extra"] = True
    with pytest.raises(Invalid):
        validate_exit(evidence, cid, session, adapter)


def test_canonical_normalizes_token_but_preserves_semantics(tmp_path):
    exercise_final_gate(tmp_path)


def test_report_schema_rejects_false_completion(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    report = execute(inputs, session_for(inputs["root"], tmp_path / "evidence"), "final", _adapters={})
    for name, value in (("phase_b_complete", True), ("requirements_zero_gap", True), ("phase_b_pass", False)):
        bad = deepcopy(report)
        bad[name] = value
        with pytest.raises(Invalid):
            validate_report(bad)
