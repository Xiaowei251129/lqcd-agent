"""Explicit child provenance and isolated native probes for unbound B04 cases."""
from harness.temporary import mkdtemp
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
import multiprocessing
import os
from pathlib import Path
from unittest.mock import patch

from harness import pytest_evidence
from harness.contracts import ROOT
from harness.failpoints import validate_runtime
from harness.inputs import PATHS
from harness.session import Session, validate_digests
from harness.strict_json import keys, read, require, sha, write_new
from harness.trace import compare
from helpers.trace_sources import PROCESS_BINDING, current_binding


PROBE_MODE = "LQCD_C25_NATIVE_CASE"
HOOK = "src/lqcd_agent/control/coordinator.py:boundary"


def nodeid(case_id):
    return "tests/phase_b/test_b04_runtime_cases.py::test_independent_case[" + case_id + "]"


@contextmanager
def child_binding(request, case_id):
    require(multiprocessing.parent_process() is not None and pytest_evidence.ACTIVE is None,
            "b04_child", "spawned_child")
    keys(request, {"schema_version", "invocation_token", "digests", "project_root", "nodeid", "case_id",
                   "process_token", "hook_ref", "receipt_path"} | ({"pytest_request"} if request.get("schema_version") == "0.2" else set()), "b04_child")
    require(request["schema_version"] in ("0.1", "0.2") and request["case_id"] == case_id,
            "b04_child", "identity")
    validate_digests(request["digests"])
    token = request["invocation_token"]
    require(token == "unit-only-not-acceptance" or (type(token) is str and len(token) == 64 and
            all(c in "0123456789abcdef" for c in token)), "b04_child", "session_token")
    nonce = request["process_token"]
    require(type(nonce) is str and len(nonce) == 64 and all(c in "0123456789abcdef" for c in nonce),
            "b04_child", "process_token")
    require(request["project_root"] == str(ROOT) and request["hook_ref"] == HOOK and
            type(request["nodeid"]) is str and bool(request["nodeid"]), "b04_child", "origin")
    receipt = Path(request["receipt_path"])
    require(receipt.is_absolute() and receipt == receipt.resolve() and receipt.parent.is_dir() and
            not receipt.is_relative_to(ROOT) and receipt.name == nonce + ".json" and not receipt.exists(),
            "b04_child", "receipt_path")
    binding = {"invocation_token": token, "digests": deepcopy(request["digests"])}
    if request["schema_version"] == "0.2":
        root, _ = pytest_evidence.execution_request(request["pytest_request"], binding,
            nodeid=request["nodeid"], case_id=case_id)
        require(root["project_root"] == request["project_root"], "b04_child", "scoped_project")
    require(PROCESS_BINDING.get() in (None, binding), "b04_child", "nested_binding")
    reset = PROCESS_BINDING.set(binding)
    try:
        yield
    finally:
        PROCESS_BINDING.reset(reset)


def bound_child(function):
    @wraps(function)
    def run(output, case_id, request):
        with child_binding(request, case_id):
            return function(output, case_id, request)
    return run


def retain_probe_sources(output, request, *, source=None):
    if os.environ.get(PROBE_MODE) != request["case_id"]:
        return
    writer = pytest_evidence.ACTIVE
    require(writer is not None and writer.nodeid == nodeid(request["case_id"]), "b04_probe", "native_node")
    output, source = Path(output), Path(source or output)
    paths = [source / "process-source.json", Path(request["receipt_path"]), output / "case-trace.json",
             output / "before-raw.json", output / "before-normalized.json"]
    paths.extend(p for p in (output / "after-raw.json", output / "after-normalized.json", output / "result.json")
                 if p.exists())
    write_new(writer.output.parent / "probe-sources.json", {"case_id": request["case_id"],
        "binding": current_binding(), "request": request,
        "files": [{"path": str(p), "sha256": sha(p.read_bytes())} for p in paths]})


def validate_probe(value, session, case_id):
    pytest_evidence.validate_pytest(value, session, [nodeid(case_id)])
    require(value["hook_events"] == [{"case_id": case_id, "nodeid": nodeid(case_id), "hook_ref": HOOK}] and
            value["case_results"] == [], "b04_probe", "unique_diagnostic_hook")
    local_registry = {"entries": [{"hook_ref": HOOK,
        "case_bindings": [{"case_id": case_id, "scenario_ids": []}]}]}
    require(validate_runtime(value, local_registry, {case_id: {}}, [], ROOT) == [],
            "b04_probe", "no_owned_result")
    observations = value["observations"]
    require(len(observations) == 1 and observations[0]["scenario_id"] == "B00C25-PROBE" and
            observations[0]["nodeid"] == nodeid(case_id) and
            observations[0]["result"] == {"kind": "boolean", "value": True}, "b04_probe", "actual_factory_result")
    sources = read(session.directory / "probe-sources.json")
    keys(sources, {"case_id", "binding", "request", "files"}, "b04_probe")
    require(sources["case_id"] == case_id, "b04_probe", "source_case")
    session.verify_binding(sources["binding"])
    request = sources["request"]
    keys(request, {"schema_version", "invocation_token", "digests", "project_root", "nodeid", "case_id",
                   "process_token", "hook_ref", "receipt_path"}, "b04_probe_request")
    session.verify_binding(request)
    require(request["case_id"] == case_id and request["nodeid"] == nodeid(case_id) and
            request["project_root"] == str(ROOT) and request["hook_ref"] == HOOK,
            "b04_probe", "original_request")
    files = {}
    for item in sources["files"]:
        keys(item, {"path", "sha256"}, "b04_probe_file")
        p = Path(item["path"])
        require(p.is_absolute() and not p.is_relative_to(ROOT) and p.name not in files and
                sha(p.read_bytes()) == item["sha256"], "b04_probe", "original_bytes")
        files[p.name] = read(p)
    required = {"process-source.json", request["process_token"] + ".json", "case-trace.json",
                "before-raw.json", "before-normalized.json"}
    require(required <= files.keys(), "b04_probe", "source_files")
    require(any(item["path"] == request["receipt_path"] for item in sources["files"]),
            "b04_probe", "receipt_path")
    receipt = files[request["process_token"] + ".json"]
    source = files["process-source.json"]
    require(receipt["request"] == request and receipt["hook_ref"] == HOOK and
            source["process_id"] == receipt["process_id"] and source["case_id"] == case_id,
            "b04_probe", "source_receipt")
    session.verify_binding(source["binding"])
    require(files["case-trace.json"] == observations[0]["trace"], "b04_probe", "trace_bytes")
    for name in ("before-raw.json", "after-raw.json"):
        if name in files:
            session.verify_binding(files[name]["proof"]["binding"])
    session.unchanged()
    return {name: value for name, value in files.items() if name.endswith("-normalized.json") or name == "case-trace.json"}


def run_native_case(case_id):
    require(PROBE_MODE not in os.environ, "b04_probe", "unexpected_nested_mode")
    root = Path(mkdtemp(prefix="lqcd-agent-b00c25-native-", dir="/private/tmp"))
    digests = {key: sha((ROOT / path).read_bytes()) for key, path in PATHS.items()}
    results = []
    for index in range(2):
        session = Session(ROOT, root / str(index), digests)
        write_new(session.directory / "session-binding.json", {"invocation_token": session.token, "digests": session.digests})
        with patch.dict(os.environ, {PROBE_MODE: case_id}):
            value = pytest_evidence.run_pytest(session, [nodeid(case_id)])
        results.append(validate_probe(value, session, case_id))
    require(results[0].keys() == results[1].keys(), "b04_probe", "fresh_source_set")
    for name in results[0]:
        compare(results[0][name], results[1][name]) if name == "case-trace.json" else require(
            results[0][name] == results[1][name], "b04_probe", "fresh_exact")
    write_new(root / "result.json", {"case_id": case_id, "fresh_sessions": 2, "exact": True, "B04_owned": False})
    return root


def run_fault_case(case_id, *, local_consumers=False, fresh_count=2):
    """Run the original native node with explicit C26 source capture only."""
    from helpers.b04_fault_sources import SOURCE_MODE
    from harness.fault_source_trace import anchor_directory, save_evidence
    from harness.strict_json import canonical
    from harness.trace import normalize
    require(PROBE_MODE not in os.environ and fresh_count in (1, 2), "fault_probe", "native_outer")
    root = Path(mkdtemp(prefix="lqcd-agent-b00c26-native-", dir="/private/tmp"))
    digests = {key: sha((ROOT / path).read_bytes()) for key, path in PATHS.items()}
    results = []
    for index in range(fresh_count):
        session = Session(ROOT, root / str(index), digests)
        write_new(session.directory / "session-binding.json", {"invocation_token": session.token, "digests": session.digests})
        mode = {PROBE_MODE: case_id, SOURCE_MODE: "0.12"}
        if local_consumers:
            mode["LQCD_C26_LOCAL_CONSUMERS"] = case_id
        with patch.dict(os.environ, mode):
            value = pytest_evidence.run_pytest(session, [nodeid(case_id)])
        pytest_evidence.validate_pytest(value, session, [nodeid(case_id)])
        require(value["hook_events"] == [{"case_id": case_id, "nodeid": nodeid(case_id), "hook_ref": HOOK}] and
                len(value["observations"]) == 1 and value["observations"][0]["scenario_id"] == "B00C26-PROBE" and
                len(value["case_results"]) == int(local_consumers), "fault_probe", "actual_native_result")
        raw = value["observations"][0]["trace"]
        require(raw["schema_version"] == "0.12", "fault_probe", "source_trace")
        normalized = normalize(raw, binding=value)
        save_evidence(session.directory, "source-raw.json", canonical(raw))
        save_evidence(session.directory, "source-normalized.json", canonical(normalized))
        write_new(session.directory / "source-anchor.json", {"directory": str(anchor_directory(value, case_id))})
        results.append(normalized)
        session.unchanged()
    require(all(value == results[0] for value in results), "fault_probe", "fresh_exact")
    write_new(root / "result.json", {"case_id": case_id, "fresh_sessions": fresh_count,
        "exact": fresh_count == 2, "B04_owned": False, "local_consumers": local_consumers})
    writer = pytest_evidence.ACTIVE
    if writer is not None:
        require(writer.value["digests"] == session.digests, "fault_probe", "outer_input")
        name = sha((writer.nodeid + ":" + case_id).encode())
        write_new(writer.output.parent / ("fault-probe-" + name + ".json"), {"nodeid": writer.nodeid,
            "case_id": case_id, "outer_binding": {key: writer.value[key] for key in ("invocation_token", "digests")},
            "native_root": str(root), "fresh_sessions": fresh_count, "B04_owned": False})
    return root
