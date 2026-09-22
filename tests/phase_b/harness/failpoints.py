"""Require bound production triggers, exact outcomes and traces for every sealed case."""
from .strict_json import keys, require, path_in, read, strings
from .trace import compare


def runtime_gaps(registry, specs, scenarios):
    indexed = {s["scenario_id"]: s for s in scenarios}
    available = set()
    for entry in registry["entries"]:
        if entry["hook_ref"] is None:
            continue
        for binding in entry["case_bindings"]:
            if binding["scenario_ids"] and all(sid in indexed for sid in binding["scenario_ids"]):
                available.add(binding["case_id"])
    return [cid for cid in specs if cid not in available]


def validate_runtime(evidence, registry, specs, scenarios, root):
    bindings = {b["case_id"]: (entry, b) for entry in registry["entries"] for b in entry["case_bindings"]}
    scenario_index = {s["scenario_id"]: s for s in scenarios}
    triggers = {}
    for row in evidence["hook_events"]:
        keys(row, {"case_id", "nodeid", "hook_ref"}, "hook")
        cid = row["case_id"]
        require(cid in specs and cid in bindings, "hook", "case_id", "invalid_evidence")
        key = (cid, row["nodeid"])
        require(key not in triggers, cid, "duplicate_trigger", "invalid_evidence")
        triggers[key] = row
        entry, _ = bindings[cid]
        require(row["hook_ref"] == entry["hook_ref"] and row["hook_ref"] is not None, cid, "hook_ref", "invalid_evidence")
    passed, seen = set(), set()
    for row in evidence["case_results"]:
        keys(row, {"case_id", "nodeid", "outcome", "invariants", "trace"}, "case_result")
        cid = row["case_id"]
        key = (cid, row["nodeid"])
        require(cid in specs and cid in bindings, "case_result", "case_id", "invalid_evidence")
        require(key not in seen, cid, "duplicate_case_result", "invalid_evidence")
        seen.add(key)
        if key not in triggers:
            continue
        entry, binding = bindings[cid]
        require(row["outcome"] == specs[cid]["outcome"], cid, "outcome", "invalid_evidence")
        strings(row["invariants"], cid, "invariants")
        require(set(specs[cid]["invariants"]) <= set(row["invariants"]), cid, "invariants", "invalid_evidence")
        matched = [scenario_index[sid] for sid in binding["scenario_ids"]
                   if row["nodeid"] in scenario_index[sid]["pytest_nodeids"]]
        require(bool(matched), cid, "passing_nodeid", "invalid_evidence")
        for scenario in matched:
            compare(row["trace"], read(path_in(root, scenario["expected_trace_fixture"])), binding=evidence)
        passed.add(cid)
    # A multi-scenario binding is conjunctive, not an alternative path wildcard.
    for cid in list(passed):
        _, binding = bindings[cid]
        if any((cid, n) not in seen or (cid, n) not in triggers
               for sid in binding["scenario_ids"] for n in scenario_index[sid]["pytest_nodeids"]):
            passed.remove(cid)
    return [cid for cid in specs if cid in passed]
