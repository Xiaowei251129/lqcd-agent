"""Closed acceptance matrix, ownership, fixture and reference checks."""
import re
from .contracts import META_IDS, TICKETS, PROTOCOL_SHA, CATALOG_SHA, required_ids
from .strict_json import keys, require, strings, text, path_in, read, callable_ref
from .trace import normalize
from .ownership import OWNED

LAYERS = ("schema", "node", "route", "trajectory", "recovery", "interface")
CLASSES = ("required_control_acceptance", "compatibility_regression", "capability_evaluation")
SCENARIO_FIELDS = {
    "scenario_id", "contract_refs", "layer", "fixture_id", "entrypoint", "expected_trace_fixture",
    "expected_result", "required_invariants", "pytest_nodeids", "required", "evidence_class",
    "implementation_ticket_id", "validation_stage",
}
RESULT_FIELDS = {"kind", "value"}


def validate_result(value, obj="result"):
    keys(value, RESULT_FIELDS, obj)
    kinds = {"null": type(None), "boolean": bool, "integer": int, "string": str, "strings": list}
    require(type(value["kind"]) is str and value["kind"] in kinds and type(value["value"]) is kinds[value["kind"]], obj, "value")
    if value["kind"] == "strings":
        strings(value["value"], obj, "value", nonempty=False, ordered=False)


def validate_matrix(matrix, catalog, root):
    keys(matrix, {"schema_version", "phase", "requirement_catalog_version", "requirement_catalog_sha256",
                  "control_protocol_version", "control_protocol_sha256", "implementation_slices", "scenarios"}, "matrix")
    for field, expected in {
        "schema_version": "0.1", "phase": "phase-b-graph-harness", "requirement_catalog_version": "0.4.0",
        "control_protocol_version": "0.4", "control_protocol_sha256": PROTOCOL_SHA,
        "requirement_catalog_sha256": CATALOG_SHA,
    }.items():
        require(matrix[field] == expected, "matrix", field)
    required = required_ids(catalog)
    require(type(matrix["implementation_slices"]) is list, "matrix", "implementation_slices")
    slices, assigned = {}, []
    for part in matrix["implementation_slices"]:
        keys(part, {"ticket_id", "owned_requirement_ids"}, "slice")
        tid = part["ticket_id"]
        require(type(tid) is str and tid in TICKETS and tid not in slices, "slice", "ticket_id")
        ids = strings(part["owned_requirement_ids"], tid, "owned_requirement_ids")
        require(set(ids) <= set(required), tid, "owned_requirement_ids")
        require(not set(ids) & set(assigned), tid, "ownership_overlap")
        require(ids == sorted(OWNED[tid]), tid, "owned_requirement_ids")
        slices[tid] = ids
        assigned.extend(ids)
    require(list(slices) == list(TICKETS[:len(slices)]) and "B00" in slices, "matrix", "slice_order")
    require(type(matrix["scenarios"]) is list, "matrix", "scenarios")
    scenario_ids, covered = [], set()
    source_cache = {}
    for scenario in matrix["scenarios"]:
        keys(scenario, SCENARIO_FIELDS, "scenario")
        sid = scenario["scenario_id"]
        text(sid, "scenario", "scenario_id")
        scenario_ids.append(sid)
        tid = scenario["implementation_ticket_id"]
        require(type(tid) is str and tid in slices, sid, "implementation_ticket_id")
        require(scenario["validation_stage"] in ("construction", "final"), sid, "validation_stage")
        refs = strings(scenario["contract_refs"], sid, "contract_refs")
        require(set(refs) <= set(slices[tid]), sid, "contract_refs")
        require(scenario["layer"] in LAYERS, sid, "layer")
        require(type(scenario["required"]) is bool, sid, "required")
        require(scenario["evidence_class"] in CLASSES, sid, "evidence_class")
        require(not scenario["required"] or scenario["evidence_class"] == CLASSES[0], sid, "evidence_class")
        nodes = strings(scenario["pytest_nodeids"], sid, "pytest_nodeids", nonempty=scenario["required"])
        for node in nodes:
            relative, separator, selected = node.partition("::")
            require(separator and selected and relative.startswith("tests/") and relative.endswith(".py")
                    and not re.search(r"[\r\n]", node), sid, "pytest_nodeids")
            path_in(root, relative)
        fixture = path_in(root, scenario["fixture_id"])
        spec = read(fixture)
        keys(spec, {"schema_version", "fixture_id", "entrypoint", "expected_result", "required_invariants"}, sid)
        require(spec["schema_version"] == "0.1" and spec["fixture_id"] == scenario["fixture_id"], sid, "fixture_id")
        for name in ("entrypoint", "expected_result", "required_invariants"):
            require(spec[name] == scenario[name], sid, name)
        text(scenario["entrypoint"], sid, "entrypoint")
        relative, separator, qualified = scenario["entrypoint"].partition(":")
        require(separator and qualified and relative.endswith(".py"), sid, "entrypoint")
        callable_ref(root, scenario["entrypoint"], source_cache=source_cache)
        if tid != "B00":
            require(relative.startswith("src/lqcd_agent/"), sid, "production_entrypoint")
        validate_result(scenario["expected_result"], sid)
        strings(scenario["required_invariants"], sid, "required_invariants")
        trace = scenario["expected_trace_fixture"]
        require(trace is not None or scenario["layer"] in ("schema", "node"), sid, "expected_trace_fixture")
        if trace is not None:
            normalize(read(path_in(root, trace)), expected=True)
        if scenario["required"]:
            covered.update(refs)
    strings(scenario_ids, "matrix", "scenario_ids")
    return slices, [ref for ref in required if ref in covered]


def selected_scenarios(matrix, mode, ticket):
    return [s for s in matrix["scenarios"] if s["required"] and (
        mode == "final" or (s["implementation_ticket_id"] == ticket and s["validation_stage"] == "construction"))]
