"""Fixed exit-check dispatch and semantic evidence verification; B05 installs adapters here."""
from dataclasses import dataclass
from typing import Callable

from .contracts import EXIT_CHECKS
from .strict_json import keys, require, read, sha, digest, path_in, strings
from .pytest_evidence import validate_pytest, validate_observations, collect_roots
from .trace import normalize

BENCHMARK_ITEMS = (
    "input_understood", "method_plan_written", "analysis_engineer_consumed_scenario_data", "analysis_command_recorded",
    "case_specific_fit_summary_produced", "reviewer_findings_grounded", "decision_reasons_structured", "expected_conclusion_observed",
    "expected_route_observed", "review_warning_expectations_observed", "human_gate_behavior_correct",
    "memory_status_correct", "final_report_coherent",
)
SMOKE_INVARIANTS = {"ledger", "state", "checkpoint", "artifact", "budget", "pause", "child", "accepted"}
DOC_INVARIANTS = {"phase_a_validator", "generated_protocol", "links", "metadata", "allowed_files",
                  "do_not_touch", "stale_documents", "diff_check", "semantic_review_basis"}
SUITE_ROOTS = {
    "phase_b_suite": ("tests/phase_b",), "full_pytest": ("tests",),
    "synthetic_tests": ("tests/test_synthetic_benchmarks.py",),
    "legacy_regression": ("tests/test_codex_handoff_worker.py", "tests/test_run_graph_with_codex_handoff.py"),
}


@dataclass(frozen=True)
class Adapter:
    """A trusted in-tree runner; selections and expectations are not CLI inputs."""
    run: Callable
    selection: tuple = ()
    scenarios: tuple = ()
    files: tuple = ()
    pytest_schema_version: str = "0.1"


def production_adapters(inputs):
    """B05 supplies explicit check-id bindings here after implementing the frozen adapters."""
    return {}


def validate_adapter_targets(inputs, session, adapters):
    """Adapters cannot replace a whole suite or layer with a passing subset."""
    from .matrix import LAYERS
    scenarios = [s for s in inputs["matrix"]["scenarios"] if s["required"]]
    for index, layer in enumerate(LAYERS):
        cid = f"layer_{index}"
        if cid in adapters:
            expected = tuple(sorted({n for s in scenarios if s["layer"] == layer for n in s["pytest_nodeids"]}))
            require(bool(expected) and adapters[cid].selection == expected, cid, "matrix_layer_selection")
    cid = "cross_system_fault_concurrency"
    if cid in adapters:
        bindings = {sid for entry in inputs["registry"]["entries"] for b in entry["case_bindings"] for sid in b["scenario_ids"]}
        expected = tuple(sorted({n for s in scenarios if s["scenario_id"] in bindings for n in s["pytest_nodeids"]}))
        require(bool(expected) and adapters[cid].selection == expected, cid, "obligation_selection")
    for cid, roots in SUITE_ROOTS.items():
        if cid in adapters:
            require(adapters[cid].selection == collect_roots(session, roots, "collect-" + cid), cid, "complete_suite_selection")
    if "compileall" in adapters:
        expected = sorted([p.relative_to(session.root).as_posix() for base in ("src", "tests")
                           for p in (session.root / base).rglob("*.py")] +
                          ["scripts/generate_phase_b_protocol.py", "scripts/validate_phase_b_acceptance.py"])
        require(list(adapters["compileall"].files) == expected, "compileall", "complete_file_selection")


def normalized_pytest(value):
    # Raw file digests are deliberately not used as normalized evidence digests.
    result = {k: v for k, v in value.items() if k not in ({"invocation_token", "execution_root", "pytest_requests"} if value["schema_version"] == "0.2" else {"invocation_token"})}
    if value["schema_version"] == "0.2":
        from .pytest_evidence import referenced_request
        result["check_id"] = referenced_request(value["execution_root"])["check_id"]
    result["observations"] = [dict(row, trace=normalize(row["trace"], binding=value) if row["trace"] is not None else None)
                              for row in value["observations"]]
    result["case_results"] = [dict(row, trace=normalize(row["trace"], binding=value)) for row in value["case_results"]]
    if value["schema_version"] == "0.2":
        result["nodes"] = sorted(result["nodes"], key=lambda row: (row["nodeid"], row["when"]))
        for name, identity in (("observations", "scenario_id"), ("hook_events", "case_id"), ("case_results", "case_id")):
            result[name] = sorted(result[name], key=lambda row: (row[identity], row["nodeid"]))
    return result


def validate_benchmark(value, root):
    keys(value, {"schema_version", "passed", "cases"}, "benchmark")
    require(value["schema_version"] == "0.1" and value["passed"] is True, "benchmark", "passed", "check_failed")
    required = read(root / "evaluation/synthetic_benchmarks/case_sets/full.json")["case_ids"]
    require(type(value["cases"]) is list, "benchmark", "cases")
    seen = []
    for case in value["cases"]:
        keys(case, {"case_id", "passed", "review_needed", "items"}, "benchmark_case")
        require(case["passed"] is True and case["review_needed"] is False, "benchmark", "case_pass", "check_failed")
        seen.append(case["case_id"])
        require(type(case["items"]) is list, "benchmark", "items")
        names = []
        for item in case["items"]:
            keys(item, {"name", "passed"}, "checklist_item")
            require(item["passed"] is True, "benchmark", "checklist_item", "check_failed")
            names.append(item["name"])
        require(sorted(names) == sorted(BENCHMARK_ITEMS), "benchmark", "required_items", "invalid_evidence")
    require(sorted(seen) == sorted(required), "benchmark", "full_case_set", "invalid_evidence")
    return value


def validate_exit(value, check_id, session, adapter):
    keys(value, {"schema_version", "invocation_token", "check_id", "digests", "exit_code", "evidence_refs"}, "exit")
    require(value["schema_version"] == "0.1" and value["check_id"] == check_id and check_id in EXIT_CHECKS,
            "exit", "identity", "invalid_evidence")
    session.verify_binding(value)
    require(type(value["exit_code"]) is int and value["exit_code"] == 0, check_id, "exit_code", "check_failed")
    # One closed semantic artifact is authoritative per check; its own node/case arrays can be large.
    require(type(value["evidence_refs"]) is list and len(value["evidence_refs"]) == 1, check_id, "evidence_refs")
    ref = value["evidence_refs"][0]
    keys(ref, {"relative_path", "sha256"}, "reference")
    path = path_in(session.directory, ref["relative_path"])
    require(sha(path.read_bytes()) == ref["sha256"], check_id, "artifact_hash", "invalid_evidence")
    artifact = read(path)
    if check_id == "full_mock_benchmark":
        normalized = validate_benchmark(artifact, session.root)
    elif check_id == "compileall":
        keys(artifact, {"schema_version", "files", "failures"}, check_id)
        require(artifact["schema_version"] == "0.1" and artifact["files"] == list(adapter.files)
                and bool(adapter.files) and artifact["failures"] == [], check_id, "compiled_files", "check_failed")
        strings(artifact["files"], check_id, "files")
        normalized = artifact
    else:
        validate_pytest(artifact, session, list(adapter.selection),
                        check_id=check_id if adapter.pytest_schema_version == "0.2" else None,
                        schema_version=adapter.pytest_schema_version)
        if adapter.scenarios:
            validate_observations(artifact, adapter.scenarios, session.root)
        if check_id in {"cli_smoke", "documentation_scope"}:
            required = SMOKE_INVARIANTS if check_id == "cli_smoke" else DOC_INVARIANTS
            observed = {inv for s in adapter.scenarios for inv in s["required_invariants"]}
            require(required <= observed and bool(adapter.scenarios), check_id, "semantic_invariants", "invalid_evidence")
        normalized = normalized_pytest(artifact)
    return [digest({"check_id": check_id, "digests": session.digests, "artifact": normalized})]
