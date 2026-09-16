"""Collectable construction proofs, with final runtime obligations intentionally outstanding."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from harness.contracts import ROOT, META_IDS, PROTOCOL_SHA, CATALOG_SHA, design, load_contracts, required_ids, projection
from harness.strict_json import Invalid, canonical, loads, read, keys, path_in, digest
from harness.matrix import validate_matrix, validate_result
from harness.inventory import validate_inventory, expected_obligations, case_specs, inventory_projection
from harness.meta_fixtures import INVARIANTS, meta_trace
from harness.pytest_evidence import observe
from harness.trace import compare, normalize


def record(number):
    observe(f"B00-META-{number:03d}", {"kind": "boolean", "value": True}, INVARIANTS[number],
            meta_trace() if number == 5 else None)


def matrix():
    """Isolate the approved B00 slice so later appended slices do not rewrite its proofs."""
    value = read(ROOT / "tests/phase_b/acceptance_matrix.json")
    value["implementation_slices"] = [s for s in value["implementation_slices"] if s["ticket_id"] == "B00"]
    value["scenarios"] = [s for s in value["scenarios"]
                          if s["implementation_ticket_id"] == "B00" and s["validation_stage"] == "construction"]
    return value


def test_meta_001():
    for raw in ('{"x":1,"x":2}', '{"x":{"y":1,"y":2}}', 'NaN', 'Infinity', '-Infinity', '1e9999'):
        with pytest.raises(Invalid):
            loads(raw)
    for result in ({"kind": "boolean", "value": 1}, {"kind": "integer", "value": True},
                   {"kind": "string", "value": "ok", "extra": True}, {"kind": "null"}):
        with pytest.raises(Invalid):
            validate_result(result)
    assert loads('{"value":null}') == {"value": None}
    record(1)


def test_meta_002():
    protocol, catalog = load_contracts()
    assert len(required_ids(catalog)) == 131
    assert len({r["owner_ticket"] for r in catalog["requirements"]}) == 9
    design()._validate_catalog(catalog, PROTOCOL_SHA)
    bad = deepcopy(catalog)
    bad["requirements"].append(deepcopy(bad["requirements"][0]))
    with pytest.raises(design().ValidationError):
        design()._validate_catalog(bad, PROTOCOL_SHA)
    record(2)


def test_meta_003():
    _, catalog = load_contracts()
    slices, covered = validate_matrix(matrix(), catalog, ROOT)
    assert slices == {"B00": list(META_IDS)} and covered == list(META_IDS)
    assert len(set(required_ids(catalog)) - set(covered)) == 116
    for change in ("unknown", "duplicate", "missing", "foreign", "stage"):
        bad = matrix()
        if change == "unknown":
            bad["scenarios"][0]["contract_refs"] = ["A07-META-999"]
        elif change == "duplicate":
            bad["scenarios"].append(deepcopy(bad["scenarios"][0]))
        elif change == "missing":
            bad["implementation_slices"][0]["owned_requirement_ids"].pop()
        elif change == "foreign":
            bad["scenarios"][0]["implementation_ticket_id"] = "B05"
        else:
            bad["scenarios"][0]["validation_stage"] = "passing"
        with pytest.raises(Invalid):
            validate_matrix(bad, catalog, ROOT)
    from harness.pytest_evidence import validate_observations
    selected = matrix()["scenarios"][0]
    other = dict(selected, scenario_id="isolated-other-slice")
    rows = [{"scenario_id": s["scenario_id"], "nodeid": s["pytest_nodeids"][0], "result": s["expected_result"],
             "invariants": s["required_invariants"], "trace": None} for s in (selected, other)]
    passed = validate_observations({"observations": rows}, [selected], ROOT, all_scenarios=[selected, other])
    assert passed == {selected["scenario_id"]}
    with pytest.raises(Invalid):
        validate_observations({"observations": rows}, [selected], ROOT)
    record(3)


def test_meta_004(tmp_path):
    from test_evidence_and_final import exercise_real_pytest
    exercise_real_pytest(tmp_path)
    record(4)


def test_meta_005():
    original = meta_trace()
    volatile = deepcopy(original)
    volatile["events"][0]["ephemeral"] = {"timestamp": "one", "process_id": 123, "output_root": "/temporary"}
    assert canonical(normalize(volatile)) == canonical(original)
    for mutation in ("order", "duplicate", "null", "identity", "head", "digest", "route", "unknown"):
        changed = deepcopy(original)
        if mutation == "order":
            changed["events"].reverse()
        elif mutation == "duplicate":
            changed["events"].append(changed["events"][0])
        elif mutation == "null":
            del changed["events"][0]["attempt_id"]
        else:
            key = {"identity": "run_id", "head": "execution_head", "digest": "binding_digest"}.get(mutation, mutation)
            changed["events"][0][key] = "changed"
        with pytest.raises(Invalid):
            compare(changed, original)
    record(5)


def test_meta_006():
    protocol, _ = load_contracts()
    registry = read(ROOT / "tests/phase_b/failpoint_registry.json")
    obligations = read(ROOT / "tests/phase_b/final_obligations.json")
    scenarios = read(ROOT / "tests/phase_b/acceptance_matrix.json")["scenarios"]
    specs = validate_inventory(registry, obligations, protocol, ROOT, scenarios)
    assert specs and all(e["hook_ref"] is None and e["case_bindings"] == [] for e in inventory_projection(registry)["entries"])
    for mutation in ("missing", "owner", "outcome", "source", "duplicate", "unknown", "contract"):
        bad = deepcopy(registry)
        if mutation == "missing":
            bad["entries"].pop()
        elif mutation == "duplicate":
            bad["entries"].append(deepcopy(bad["entries"][0]))
        else:
            field = {"owner": "implementation_ticket_id", "outcome": "allowed_exact_outcomes",
                     "source": "source_locator", "unknown": "failpoint_id", "contract": "contract_refs"}[mutation]
            bad["entries"][0][field] = [] if mutation in {"outcome", "contract"} else "invalid"
        with pytest.raises(Invalid):
            validate_inventory(bad, obligations, protocol, ROOT, scenarios)
    record(6)


def test_meta_007():
    _, catalog = load_contracts()
    for cls in ("compatibility_regression", "capability_evaluation", "live_provider"):
        bad = matrix()
        bad["scenarios"][0]["evidence_class"] = cls
        with pytest.raises(Invalid):
            validate_matrix(bad, catalog, ROOT)
    optional = matrix()
    optional["scenarios"][0].update(required=False, evidence_class="compatibility_regression")
    _, covered = validate_matrix(optional, catalog, ROOT)
    assert len(covered) == 14 and META_IDS[0] not in covered
    record(7)


def test_meta_008(tmp_path):
    from test_evidence_and_final import exercise_final_gate
    exercise_final_gate(tmp_path)
    record(8)


def test_meta_009():
    protocol, _ = load_contracts()
    design()._validate_control_operation(protocol)
    design()._validate_external_operation(protocol)
    design()._validate_cross_machine_invariants(protocol)
    bad = deepcopy(protocol)
    variant = bad["state_machines"]["control_operation"]["operations"][0]["variants"][0]
    variant["success_edges"].append([variant["phases"][-1], variant["phases"][0]])
    with pytest.raises(design().ValidationError):
        design()._validate_control_operation(bad)
    record(9)


def test_meta_010():
    from lqcd_agent.control.protocol import PROTOCOL, operation_variant, allows_edge
    protocol, _ = load_contracts()
    def thaw(value):
        if hasattr(value, "items"):
            return {k: thaw(v) for k, v in value.items()}
        if isinstance(value, tuple):
            return [thaw(v) for v in value]
        return value
    assert thaw(PROTOCOL) == projection(protocol)
    with pytest.raises(TypeError):
        PROTOCOL["state_machines"]["extra"] = True
    first = protocol["state_machines"]["control_operation"]["operations"][0]
    variant = first["variants"][0]
    assert operation_variant(first["operation_type"], variant["operation_variant"])
    assert allows_edge(first["operation_type"], variant["operation_variant"], *variant["success_edges"][0])
    with pytest.raises(ValueError):
        operation_variant("unknown", "unknown")
    spec = importlib.util.spec_from_file_location("generator_test", ROOT / "scripts/generate_phase_b_protocol.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert generator.render(protocol) == (ROOT / "src/lqcd_agent/control/_generated_protocol.py").read_bytes()
    assert generator.render(protocol) != generator.render(protocol) + b"# stale\n"
    design()._validate_dependency_dags(protocol)
    record(10)


def test_meta_011():
    protocol, _ = load_contracts()
    design()._validate_transaction_domains_and_cas(protocol)
    design()._validate_resolution_interleavings(protocol)
    record(11)


def test_meta_012():
    protocol, _ = load_contracts()
    control = protocol["state_machines"]["control_operation"]
    assert sum(len(o["variants"]) for o in control["operations"]) == 12
    design()._validate_control_operation(protocol)
    design()._validate_policy_capability_and_terminal_contracts(protocol)
    record(12)


def test_meta_013():
    protocol, _ = load_contracts()
    design()._validate_branch_contracts(protocol)
    design()._validate_evidence_unions(protocol)
    design()._validate_consumption_release_and_recovery(protocol)
    record(13)


def test_meta_014():
    protocol, _ = load_contracts()
    design()._validate_resolution_interleavings(protocol)
    design()._validate_stop_route_contract(protocol)
    design()._validate_stop_handoff_and_execution_lease(protocol)
    design()._validate_budget_decision_contract(protocol)
    record(14)


def test_meta_015():
    protocol, catalog = load_contracts()
    design()._validate_publication_order(protocol)
    design()._validate_consumption_failure(protocol)
    design()._validate_target_execution_paths(protocol)
    # Each mutation first validates the base and then invokes its independent semantic rule.
    design()._validate_negative_protocol_mutations(protocol)
    assert design()._validate_publication_order_mutations(protocol) == 178
    design()._validate_strict_json_rejections(catalog, PROTOCOL_SHA)
    assert len([c for c in case_specs(protocol) if c.startswith("post_claim.")]) == 28
    obligations = expected_obligations(protocol)
    bad = deepcopy(obligations)
    next(o for o in bad["runtime_obligations"] if o["obligation_id"].startswith("post_claim."))["case_ids"].pop()
    with pytest.raises(Invalid):
        validate_inventory(read(ROOT / "tests/phase_b/failpoint_registry.json"), bad, protocol, ROOT, matrix()["scenarios"])
    record(15)
