"""C16 native meta collection and isolated four-consumer source checks."""
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


@pytest.mark.parametrize("mode", ["success", "repeat_empty"])
def test_canonical_sources_have_four_consumers(tmp_path, mode):
    root = tmp_path / "isolated-project"
    (root / "tests").mkdir(parents=True)
    (root / "src/lqcd_agent").mkdir(parents=True)
    # The isolated hook exercises the consumer contract and owns no B04 case.
    (root / "src/lqcd_agent/probe.py").write_text(
        'from harness.pytest_evidence import production_hook\n'
        'def boundary():\n    production_hook("synthetic.c16")\n')
    options = "success=True" if mode == "success" else "success=False, repeat=True"
    (root / "tests/test_probe.py").write_text(
        'import runpy\nfrom helpers.product_failure_sources import code_product_trace\n'
        'from harness.pytest_evidence import observe, observe_case\n'
        'def test_bound():\n'
        '    trace, _, facts = code_product_trace(' + options + ')\n'
        '    assert not facts["B04_owned"]\n'
        '    runpy.run_path("src/lqcd_agent/probe.py")["boundary"]()\n'
        '    observe("synthetic", {"kind":"boolean", "value":True}, ["raw_checked"], trace)\n'
        '    observe_case("synthetic.c16", "validated", ["raw_checked"], trace)\n')
    write_new(root / "tests/expected.json", read(ROOT / ("tests/phase_b/expected_traces/b00c16/code_" + mode + ".json")))
    node = "tests/test_probe.py::test_bound"
    scenario = {"scenario_id": "synthetic", "pytest_nodeids": [node], "expected_result": {"kind": "boolean", "value": True},
                "required_invariants": ["raw_checked"], "expected_trace_fixture": "tests/expected.json"}
    registry = {"entries": [{"hook_ref": "src/lqcd_agent/probe.py:boundary", "case_bindings": [
        {"case_id": "synthetic.c16", "scenario_ids": ["synthetic"]}]}]}
    specs = {"synthetic.c16": {"outcome": "validated", "invariants": ["raw_checked"]}}
    adapter = Adapter(lambda _: pytest.fail("Use the existing actual subprocess evidence"), (node,), (scenario,))

    def exit_digest(value, session, name):
        path = session.directory / (name + ".json")
        write_new(path, value)
        return validate_exit({"schema_version": "0.1", "invocation_token": session.token, "check_id": "layer_0",
            "digests": session.digests, "exit_code": 0, "evidence_refs": [{"relative_path": path.name, "sha256": sha(path.read_bytes())}]},
            "layer_0", session, adapter)

    values, digests = [], []
    for i in range(2):
        session = Session(root, tmp_path / ("evidence-" + str(i)), {k: "a" * 64 for k in DIGEST_KEYS if k != "worktree_inputs"})
        value = run_pytest(session, [node])
        validate_pytest(value, session, [node])
        assert validate_observations(value, [scenario], root) == {"synthetic"}
        assert validate_runtime(value, registry, specs, [scenario], root) == ["synthetic.c16"]
        digests.append(exit_digest(value, session, "valid"))
        values.append(value)
        for field in ("observations", "case_results"):
            for fault in ("missing", "owner", "stale"):
                bad = deepcopy(value)
                proof = bad[field][0]["trace"]["proof"]
                material = next(m for m in proof["material_sources"] if m["kind"] == "canonical_tool_audit")
                if fault == "missing": proof["material_sources"].remove(material)
                elif fault == "owner": material["owner"]["producer_operation_id"] = "foreign"
                else: proof["binding"]["invocation_token"] = "stale"
                with pytest.raises(Invalid): validate_pytest(bad, session, [node])
                with pytest.raises(Invalid):
                    if field == "observations": validate_observations(bad, [scenario], root)
                    else: validate_runtime(bad, registry, specs, [scenario], root)
                with pytest.raises(Invalid): exit_digest(bad, session, field + "-" + fault)
        session.unchanged()
    assert values[0]["invocation_token"] != values[1]["invocation_token"] and digests[0] == digests[1]
    assert canonical(normalized_pytest(values[0])) == canonical(normalized_pytest(values[1]))


@pytest.mark.parametrize("mode", ["empty", "success", "repeat_empty", "repeat_success"])
def test_formal_meta_uses_current_session(tmp_path, mode):
    inputs = load_inputs()
    identifiers = {"B00C16-" + mode.upper()}
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
