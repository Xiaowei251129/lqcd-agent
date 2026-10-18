"""C18 verifies failure, Grant and repause across four existing consumers."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT, DIGEST_KEYS
from harness.exit_checks import Adapter, normalized_pytest, validate_exit
from harness.failpoints import validate_runtime
from harness.inputs import load_inputs
from harness.matrix import selected_scenarios
from harness.pytest_evidence import run_pytest, validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, canonical, read, sha, write_new


MODES = ("failure", "grant", "ordinary_insufficient", "ordinary_corrected", "terminal_corrected")


@pytest.mark.parametrize("mode", MODES)
def test_product_and_repause_sources_have_four_consumers(tmp_path, mode):
    root = tmp_path / "isolated-project"
    (root / "tests").mkdir(parents=True)
    (root / "src/lqcd_agent").mkdir(parents=True)
    # This synthetic hook tests the consumers without adding a repository case.
    (root / "src/lqcd_agent/probe.py").write_text(
        'from harness.pytest_evidence import production_hook\n'
        'def boundary():\n    production_hook("synthetic.c18")\n')
    product = mode in ("failure", "grant")
    module = "test_b00c15_product_failure_sources" if product else "test_b00c18_ordinary_repause_handoff"
    function = "product_trace" if product else "repause_trace"
    ticket = "b00c15" if product else "b00c18"
    (root / "tests/test_probe.py").write_text(
        'import runpy\nfrom ' + module + ' import ' + function + '\n'
        'from harness.pytest_evidence import observe, observe_case\n'
        'def test_bound():\n'
        '    trace, _, facts = ' + function + '(' + repr(mode) + ')\n'
        '    assert not facts["B04_owned"]\n'
        '    runpy.run_path("src/lqcd_agent/probe.py")["boundary"]()\n'
        '    observe("synthetic", {"kind":"boolean", "value":True}, ["raw_checked"], trace)\n'
        '    observe_case("synthetic.c18", "validated", ["raw_checked"], trace)\n')
    write_new(root / "tests/expected.json", read(ROOT / ("tests/phase_b/expected_traces/" + ticket + "/" + mode + ".json")))
    node = "tests/test_probe.py::test_bound"
    scenario = {"scenario_id": "synthetic", "pytest_nodeids": [node], "expected_result": {"kind": "boolean", "value": True},
                "required_invariants": ["raw_checked"], "expected_trace_fixture": "tests/expected.json"}
    registry = {"entries": [{"hook_ref": "src/lqcd_agent/probe.py:boundary", "case_bindings": [
        {"case_id": "synthetic.c18", "scenario_ids": ["synthetic"]}]}]}
    specs = {"synthetic.c18": {"outcome": "validated", "invariants": ["raw_checked"]}}
    adapter = Adapter(lambda _: pytest.fail("Use the actual original subprocess evidence"), (node,), (scenario,))

    def exit_digest(value, session, name):
        path = session.directory / (name + ".json")
        write_new(path, value)
        return validate_exit({"schema_version": "0.1", "invocation_token": session.token, "check_id": "layer_0",
            "digests": session.digests, "exit_code": 0, "evidence_refs": [{"relative_path": path.name, "sha256": sha(path.read_bytes())}]},
            "layer_0", session, adapter)

    values, digests = [], []
    for index in range(2):
        session = Session(root, tmp_path / ("evidence-" + str(index)), {k: "a" * 64 for k in DIGEST_KEYS if k != "worktree_inputs"})
        value = run_pytest(session, [node])
        validate_pytest(value, session, [node])
        assert validate_observations(value, [scenario], root) == {"synthetic"}
        assert validate_runtime(value, registry, specs, [scenario], root) == ["synthetic.c18"]
        digests.append(exit_digest(value, session, "valid"))
        values.append(value)
        for field in ("observations", "case_results"):
            for fault in ("missing", "duplicate", "foreign", "stale"):
                bad = deepcopy(value)
                proof = bad[field][0]["trace"]["proof"]
                declarations = proof["product_grant_sources" if mode == "grant" else "product_failure_sources"]
                if fault == "missing": declarations.clear()
                elif fault == "duplicate": declarations.append(deepcopy(declarations[0]))
                elif fault == "foreign": declarations[0]["capability_id"] = "foreign"
                else: proof["binding"]["invocation_token"] = "stale"
                with pytest.raises(Invalid): validate_pytest(bad, session, [node])
                with pytest.raises(Invalid):
                    if field == "observations": validate_observations(bad, [scenario], root)
                    else: validate_runtime(bad, registry, specs, [scenario], root)
                with pytest.raises(Invalid): exit_digest(bad, session, field + "-" + fault)
        session.unchanged()
    assert values[0]["invocation_token"] != values[1]["invocation_token"] and digests[0] == digests[1]
    assert canonical(normalized_pytest(values[0])) == canonical(normalized_pytest(values[1]))


@pytest.mark.parametrize("mode", MODES)
def test_formal_product_source_meta_uses_current_session(tmp_path, mode):
    inputs = load_inputs()
    ticket = "B00C15" if mode in ("failure", "grant") else "B00C18"
    identifiers = {ticket + "-" + mode.upper()}
    scenarios = [s for s in selected_scenarios(inputs["matrix"], "final", None) if s["scenario_id"] in identifiers]
    assert {s["scenario_id"] for s in scenarios} == identifiers
    assert all(s["implementation_ticket_id"] == "B00" and s["contract_refs"] == ["A07-META-006", "A07-META-015"] for s in scenarios)
    selection = sorted({node for s in scenarios for node in s["pytest_nodeids"]})
    session = Session(inputs["root"], tmp_path / "source-session", inputs["digests"])
    value = run_pytest(session, selection)
    validate_pytest(value, session, selection)
    assert validate_observations(value, scenarios, inputs["root"], all_scenarios=inputs["matrix"]["scenarios"]) == identifiers
    assert not value["hook_events"] and not value["case_results"]
    session.unchanged()
