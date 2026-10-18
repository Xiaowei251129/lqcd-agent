"""Explicit C10 current failure handoff without changing legacy provenance."""
from copy import deepcopy
from contextlib import closing
import sqlite3

import pytest

from harness.contracts import ROOT, DIGEST_KEYS
from harness.exit_checks import Adapter, normalized_pytest, validate_exit
from harness.failpoints import validate_runtime
from harness.inputs import load_inputs
from harness.matrix import selected_scenarios
from harness.pytest_evidence import observe, run_pytest, validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, canonical, read, sha, write_new
from harness.trace import compare, normalize
from helpers.ordinary_mixed import no_code_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.strict_json import canonical_bytes, loads
from test_b04_product_graph import StructuredOutcomes, diagnostic


EXPECTED = ROOT / "tests/phase_b/expected_traces/b00c20/failure.json"
INVARIANTS = ["B04_owned_false", "exact_sources", "explicit_version", "original_ports", "single_effect"]


def failed_outcomes():
    return {"analysis_engineer": diagnostic(status="failed", category="tool_failure", affected_layer="analysis",
        retryability="retryable", candidates=["analysis_engineer"], risk="low")}


def current_failure_trace(*, agent=None):
    trace, root, agent, state = no_code_trace(trace_version="0.8", outcomes=failed_outcomes(), agent=agent)
    assert trace["schema_version"] == "0.8" and trace["proof"]["schema_version"] == "0.5"
    calls = trace["proof"]["ordinary_calls"]
    assert [node for node, _ in agent.contexts] == ["method_planner", "analysis_engineer"]
    assert len(calls) == 2 and all(c["outcome"] is not None and c["exception"] is None for c in calls)
    assert loads(calls[1]["outcome"]["content"])["diagnostic"]["status"] == "failed"
    rows = [r["value"] for r in trace["proof"]["objects"] if r["kind"] == "execution_0_4"]
    reservations = [r["payload"] for r in rows if r.get("event") == "resource_reserved"]
    settlements = [r["payload"] for r in rows if r.get("event") == "resource_settled"]
    assert len(reservations) == len(settlements) == 2
    assert {r["resource_operation_id"] for r in reservations} == {r["resource_operation_id"] for r in settlements}
    assert all(r["actual"] is not None for r in settlements)
    assert trace["proof"]["ordinary_maximum_settlements"] == trace["proof"]["product_grant_sources"] == []
    failure, = [r for r in rows if r.get("event") == "failure_observed"]
    assert failure["payload"]["occurrence"] == 1 and len(trace["proof"]["product_failure_sources"]) == 1
    assert state["run_status"] == "paused"
    run_root = root / "case"
    before = {p.relative_to(run_root).as_posix(): p.read_bytes() for p in run_root.rglob("*") if p.is_file()}
    database = root / ".lqcd/control_operations.sqlite"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        durable_before = list(connection.iterdump())
    projected = normalize(trace, binding=current_binding())
    assert normalize(read(root / "raw.json"), binding=current_binding()) == projected
    assert before == {p.relative_to(run_root).as_posix(): p.read_bytes() for p in run_root.rglob("*") if p.is_file()}
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        assert list(connection.iterdump()) == durable_before
    assert len(agent.contexts) == 2
    facts = {"run_status": state["run_status"], "calls": 2, "settlements": 2, "failure_occurrence": 1, "B04_owned": False}
    for name, value in (("normalized", projected), ("facts", facts)):
        (root / (name + ".json")).write_bytes(canonical_bytes(value))
    print("C20_CURRENT_FAILURE_EVIDENCE", root)
    return trace, root, facts


def legacy_material(trace, version):
    result = deepcopy(trace)
    proof = result["proof"]
    assert not proof["ordinary_maximum_settlements"] and not proof["product_grant_sources"]
    result["schema_version"] = version
    proof["schema_version"] = "0.3" if version == "0.6" else "0.4"
    for field in ("product_failure_sources", "product_grant_sources"):
        proof.pop(field)
    if version == "0.6":
        proof.pop("ordinary_maximum_settlements")
    fields = {"schema_version", "binding", "objects", "output_roots", "typed_sources", "material_sources",
              "workspace_roots", "ordinary_calls", "ordinary_members"}
    assert set(proof) == fields | ({"ordinary_maximum_settlements"} if version == "0.7" else set())
    assert result["events"] == trace["events"]
    for field in fields - {"schema_version"}:
        assert proof[field] == trace["proof"][field]
    return result


@pytest.fixture(scope="module")
def actual_source():
    return current_failure_trace()[0]


def test_current_failure_dual_fresh_and_fixed_meta():
    first, root, facts = current_failure_trace()
    second, other, other_facts = current_failure_trace()
    assert root != other and facts == other_facts
    assert normalize(first, binding=current_binding()) == normalize(second, binding=current_binding())
    for trace in (first, second):
        compare(trace, read(EXPECTED), binding=current_binding())
    observe("B00C20-CURRENT-FAILURE", {"kind": "boolean", "value": True}, INVARIANTS, first)


@pytest.mark.parametrize("version", ["0.6", "0.7"])
def test_same_actual_material_keeps_legacy_source_rejection(actual_source, version):
    with pytest.raises(Invalid) as error:
        normalize(legacy_material(actual_source, version), binding=current_binding())
    assert error.value.error["field_path"] == "failure_member_source"


def test_default_version_still_rejects_actual_current_failure():
    trace, _, agent, state = no_code_trace(outcomes=failed_outcomes())
    assert trace["schema_version"] == "0.6" and trace["proof"]["schema_version"] == "0.3"
    assert state["run_status"] == "paused" and len(agent.contexts) == 2
    with pytest.raises(Invalid) as error:
        normalize(trace, binding=current_binding())
    assert error.value.error["field_path"] == "failure_member_source"


@pytest.mark.parametrize("version", ["0.5", "0.7", "unknown", None])
def test_unknown_or_unapproved_explicit_version_is_rejected(version):
    agent = StructuredOutcomes(failed_outcomes())
    with pytest.raises(ValueError, match="Unsupported explicit ordinary trace version"):
        no_code_trace(trace_version=version, agent=agent)
    assert agent.contexts == []


@pytest.mark.parametrize("fault", ["missing", "duplicate", "foreign", "stale", "return", "source"])
def test_current_failure_rejects_forged_material(actual_source, fault):
    trace = deepcopy(actual_source)
    declarations = trace["proof"]["product_failure_sources"]
    if fault == "missing": declarations.clear()
    elif fault == "duplicate": declarations.append(deepcopy(declarations[0]))
    elif fault == "foreign": declarations[0]["capability_id"] = "foreign"
    elif fault == "stale": trace["proof"]["binding"]["invocation_token"] = "stale"
    elif fault == "return": trace["proof"]["ordinary_calls"][1]["outcome"]["content"] += " "
    else: declarations[0]["derivation"]["content"] += " "
    with pytest.raises(Invalid):
        normalize(trace, binding=current_binding())


def test_real_scientific_return_change_remains_material(actual_source):
    class Changed(StructuredOutcomes):
        def run(self, node, context, *, timeout_seconds):
            result = super().run(node, context, timeout_seconds=timeout_seconds)
            if node == "method_planner":
                result["content"]["method"] = {"observable": "changed scientific definition"}
            return result
    changed, _, _ = current_failure_trace(agent=Changed(failed_outcomes()))
    assert normalize(changed, binding=current_binding()) != normalize(actual_source, binding=current_binding())
    def fingerprint(trace):
        return next(r["value"]["payload"]["fingerprint"] for r in trace["proof"]["objects"]
                    if r["value"].get("event") == "failure_observed")
    assert fingerprint(changed) != fingerprint(actual_source)


def test_current_failure_has_four_consumers(tmp_path):
    root = tmp_path / "isolated-project"
    (root / "tests").mkdir(parents=True)
    (root / "src/lqcd_agent").mkdir(parents=True)
    # This isolated hook does not add a repository runtime case.
    (root / "src/lqcd_agent/probe.py").write_text(
        'from harness.pytest_evidence import production_hook\n'
        'def boundary():\n    production_hook("synthetic.c20")\n')
    (root / "tests/test_probe.py").write_text(
        'import runpy\nfrom test_b00c20_current_failure_handoff import current_failure_trace\n'
        'from harness.pytest_evidence import observe, observe_case\n'
        'def test_bound():\n'
        '    trace, _, facts = current_failure_trace()\n'
        '    assert not facts["B04_owned"]\n'
        '    runpy.run_path("src/lqcd_agent/probe.py")["boundary"]()\n'
        '    observe("synthetic", {"kind":"boolean", "value":True}, ["raw_checked"], trace)\n'
        '    observe_case("synthetic.c20", "validated", ["raw_checked"], trace)\n')
    write_new(root / "tests/expected.json", read(EXPECTED))
    node = "tests/test_probe.py::test_bound"
    scenario = {"scenario_id": "synthetic", "pytest_nodeids": [node], "expected_result": {"kind": "boolean", "value": True},
                "required_invariants": ["raw_checked"], "expected_trace_fixture": "tests/expected.json"}
    registry = {"entries": [{"hook_ref": "src/lqcd_agent/probe.py:boundary", "case_bindings": [
        {"case_id": "synthetic.c20", "scenario_ids": ["synthetic"]}]}]}
    specs = {"synthetic.c20": {"outcome": "validated", "invariants": ["raw_checked"]}}
    adapter = Adapter(lambda _: pytest.fail("Use actual original subprocess evidence"), (node,), (scenario,))
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
        assert validate_runtime(value, registry, specs, [scenario], root) == ["synthetic.c20"]
        digests.append(exit_digest(value, session, "valid")); values.append(value)
        for field in ("observations", "case_results"):
            for fault in ("missing", "duplicate", "foreign", "stale"):
                bad = deepcopy(value)
                proof = bad[field][0]["trace"]["proof"]
                declarations = proof["product_failure_sources"]
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


def test_formal_current_failure_meta_uses_current_session(tmp_path):
    inputs = load_inputs()
    identifiers = {"B00C20-CURRENT-FAILURE"}
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
