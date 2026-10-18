"""Collector, matrix, runtime and exit consumers retain the same prefix source."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT, DIGEST_KEYS
from harness.exit_checks import Adapter, validate_exit
from harness.failpoints import validate_runtime
from harness.inputs import load_inputs
from harness.matrix import selected_scenarios
from harness.pytest_evidence import run_pytest, validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, read, sha, write_new


@pytest.mark.parametrize("mode", ["settlement_before", "completion_after", "history_after", "finished_after", "host_rejected"])
def test_prefix_has_four_consumers(tmp_path, mode):
    root = tmp_path / "isolated-project"
    (root / "tests").mkdir(parents=True)
    (root / "src/lqcd_agent").mkdir(parents=True)
    (root / "src/lqcd_agent/probe.py").write_text(
        'from harness.pytest_evidence import production_hook\n'
        'def boundary():\n    production_hook("synthetic.c22")\n')
    (root / "tests/test_probe.py").write_text(
        'import runpy\nfrom helpers.ordinary_publication_prefix_sources import product_prefix_trace\n'
        'from harness.pytest_evidence import observe, observe_case\n'
        'def test_bound():\n'
        '    trace, _, facts = product_prefix_trace(' + repr(mode) + ', recover=True)\n'
        '    assert not facts["B04_owned"]\n'
        '    runpy.run_path("src/lqcd_agent/probe.py")["boundary"]()\n'
        '    observe("synthetic", {"kind":"boolean", "value":True}, ["raw_checked"], trace)\n'
        '    observe_case("synthetic.c22", "validated", ["raw_checked"], trace)\n')
    write_new(root / "tests/expected.json", read(ROOT / "tests/phase_b/expected_traces/b00c22" / (mode + ".json")))
    node = "tests/test_probe.py::test_bound"
    scenario = {"scenario_id": "synthetic", "pytest_nodeids": [node], "expected_result": {"kind": "boolean", "value": True},
                "required_invariants": ["raw_checked"], "expected_trace_fixture": "tests/expected.json"}
    registry = {"entries": [{"hook_ref": "src/lqcd_agent/probe.py:boundary", "case_bindings": [
        {"case_id": "synthetic.c22", "scenario_ids": ["synthetic"]}]}]}
    specs = {"synthetic.c22": {"outcome": "validated", "invariants": ["raw_checked"]}}
    adapter = Adapter(lambda _: pytest.fail("Use the original subprocess evidence"), (node,), (scenario,))
    session = Session(root, tmp_path / "evidence", {key: "a" * 64 for key in DIGEST_KEYS if key != "worktree_inputs"})
    value = run_pytest(session, [node])

    def exit_digest(envelope, name):
        path = session.directory / (name + ".json")
        write_new(path, envelope)
        return validate_exit({"schema_version": "0.1", "invocation_token": session.token, "check_id": "layer_0",
            "digests": session.digests, "exit_code": 0,
            "evidence_refs": [{"relative_path": path.name, "sha256": sha(path.read_bytes())}]}, "layer_0", session, adapter)

    validate_pytest(value, session, [node])
    assert validate_observations(value, [scenario], root) == {"synthetic"}
    assert validate_runtime(value, registry, specs, [scenario], root) == ["synthetic.c22"]
    exit_digest(value, "valid")
    for field in ("observations", "case_results"):
        for fault in ("missing", "owner", "stage", "stale"):
            bad = deepcopy(value)
            proof = bad[field][0]["trace"]["proof"]
            declaration = proof["ordinary_publication_prefixes"][0]
            if fault == "missing": proof["ordinary_publication_prefixes"].clear()
            elif fault == "owner": declaration["producer_operation_id"] = "foreign"
            elif fault == "stage": declaration["stage"] = "fabricated_finished"
            else: proof["binding"]["invocation_token"] = "stale"
            with pytest.raises(Invalid): validate_pytest(bad, session, [node])
            with pytest.raises(Invalid):
                if field == "observations": validate_observations(bad, [scenario], root)
                else: validate_runtime(bad, registry, specs, [scenario], root)
            with pytest.raises(Invalid): exit_digest(bad, field + "-" + fault)
    session.unchanged()


@pytest.mark.parametrize("mode", ["settlement_before", "history_after", "host_rejected"])
def test_formal_meta_has_the_current_native_session(tmp_path, mode):
    inputs = load_inputs()
    identifiers = {"B00C22-" + mode.upper()}
    scenarios = [scenario for scenario in selected_scenarios(inputs["matrix"], "final", None)
                 if scenario["scenario_id"] in identifiers]
    assert {scenario["scenario_id"] for scenario in scenarios} == identifiers
    assert all(scenario["implementation_ticket_id"] == "B00" and scenario["contract_refs"] == ["A07-META-006", "A07-META-015"]
               for scenario in scenarios)
    selection = sorted({node for scenario in scenarios for node in scenario["pytest_nodeids"]})
    session = Session(inputs["root"], tmp_path / "source-session", inputs["digests"])
    value = run_pytest(session, selection)
    validate_pytest(value, session, selection)
    assert validate_observations(value, scenarios, inputs["root"], all_scenarios=inputs["matrix"]["scenarios"]) == identifiers
    assert not value["hook_events"] and not value["case_results"]
    session.unchanged()
