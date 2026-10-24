"""Project-owned pytest evidence, consumed only by its spawning session."""
import inspect
import ast
import os
import subprocess
import sys
import secrets
from pathlib import Path

import pytest

from .strict_json import keys, require, read, write_new, strings, path_in, canonical, sha
from .matrix import validate_result
from .trace import normalize, compare

ACTIVE = None
ENVELOPE = {"schema_version", "invocation_token", "digests", "selection", "collected", "deselected",
            "exit_code", "nodes", "observations", "hook_events", "case_results"}


class Writer:
    def __init__(self, config):
        self.config = config
        self.output = Path(os.environ["PHASE_B_EVIDENCE_OUTPUT"])
        request_path = Path(os.environ["PHASE_B_EVIDENCE_REQUEST"])
        self.value = read(request_path)
        fields = {"schema_version", "invocation_token", "digests", "selection"}
        if self.value.get("schema_version") == "0.2":
            keys(self.value, fields | {"execution_root", "batch_index"}, "pytest_request")
            reference = {"path": str(request_path), "sha256": sha(request_path.read_bytes())}
            root, leaf = execution_request(reference, self.value)
            require(root["project_root"] == str(Path(config.rootpath).resolve()), "pytest_request", "project_root")
            self.value = {key: leaf[key] for key in fields}
            self.value.update(execution_root=leaf["execution_root"], pytest_requests=[reference])
        else:
            keys(self.value, fields, "pytest_request")
            require(self.value["schema_version"] == "0.1", "pytest_request", "schema_version")
        self.value.update(collected=[], deselected=[], exit_code=None, nodes=[], observations=[], hook_events=[], case_results=[])
        self.nodeid = None

    def pytest_collection_finish(self, session):
        self.value["collected"] = sorted(item.nodeid for item in session.items)

    def pytest_deselected(self, items):
        self.value["deselected"].extend(item.nodeid for item in items)

    def pytest_runtest_logstart(self, nodeid, location):
        self.nodeid = nodeid

    def pytest_runtest_logreport(self, report):
        self.value["nodes"].append({"nodeid": report.nodeid, "when": report.when,
                                   "outcome": report.outcome, "xfail": hasattr(report, "wasxfail")})

    def pytest_sessionfinish(self, session, exitstatus):
        self.value["exit_code"] = int(exitstatus)
        self.value["deselected"].sort()
        self.value["nodes"].sort(key=lambda x: (x["nodeid"], x["when"]))
        self.value["observations"].sort(key=lambda x: (x["scenario_id"], x["nodeid"]))
        self.value["hook_events"].sort(key=lambda x: (x["case_id"], x["nodeid"]))
        self.value["case_results"].sort(key=lambda x: (x["case_id"], x["nodeid"]))
        write_new(self.output, self.value)


def pytest_configure(config):
    global ACTIVE
    if os.environ.get("PHASE_B_EVIDENCE_REQUEST"):
        ACTIVE = Writer(config)
        config.pluginmanager.register(ACTIVE, "phase-b-evidence-writer")


def pytest_unconfigure(config):
    global ACTIVE
    ACTIVE = None


def observe(scenario_id, result, invariants, trace=None):
    """Record the actual outcome after the scenario's assertions, never a fixture pass flag."""
    validate_result(result)
    strings(invariants, scenario_id, "invariants")
    if trace is not None:
        normalize(trace, binding=ACTIVE.value if ACTIVE else trace.get("proof", {}).get("binding"))
    if ACTIVE:
        ACTIVE.value["observations"].append({"scenario_id": scenario_id, "nodeid": ACTIVE.nodeid,
                                            "result": result, "invariants": invariants, "trace": trace})


def production_hook(case_id, *, process_request=None):
    """Called by a bound production hook at the deterministic boundary during a fresh test."""
    frame = inspect.currentframe().f_back
    filename = Path(frame.f_code.co_filename).resolve()
    if ACTIVE or process_request is not None:
        root = Path(ACTIVE.config.rootpath if ACTIVE else process_request["project_root"]).resolve()
        require(filename.is_relative_to(root / "src/lqcd_agent"), "hook", "production_source")
        def locate(nodes, prefix=()):
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names = prefix + (node.name,)
                    first = min([node.lineno] + [d.lineno for d in node.decorator_list])
                    if not isinstance(node, ast.ClassDef) and first == frame.f_code.co_firstlineno:
                        return ".".join(names)
                    found = locate(node.body, names)
                    if found:
                        return found
            return None
        # AST source locations also work on the supported Python 3.10 baseline.
        qualified = locate(ast.parse(filename.read_bytes()).body)
        require(qualified is not None, "hook", "source_location")
        hook_ref = filename.relative_to(root).as_posix() + ":" + qualified
        if process_request is not None:
            require(case_id == process_request["case_id"] and hook_ref == process_request["hook_ref"],
                    "process_hook", "production_identity", "invalid_evidence")
            receipt = {"request": process_request, "process_id": os.getpid(), "hook_ref": hook_ref}
            output = Path(process_request["receipt_path"])
            with output.open("xb") as stream:
                stream.write(canonical(receipt))
                stream.flush()
                os.fsync(stream.fileno())
            descriptor = os.open(output.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        else:
            ACTIVE.value["hook_events"].append({"case_id": case_id, "nodeid": ACTIVE.nodeid, "hook_ref": hook_ref})


CONSUMED_PROCESS_RECEIPTS = set()
PENDING_PROCESS_REQUESTS = {}


def process_hook_request(case_id, directory, *, scoped=False):
    """Bind one child trigger to the current pytest node and fresh session."""
    from .contracts import ROOT, DIGEST_KEYS
    token = secrets.token_hex(32)
    directory = Path(directory).resolve()
    require(directory.is_dir() and not directory.is_relative_to(ROOT), "process_hook", "evidence_directory")
    binding = ACTIVE.value if ACTIVE else {"invocation_token": "unit-only-not-acceptance", "digests": dict.fromkeys(DIGEST_KEYS, "0" * 64)}
    request = {"schema_version": "0.1", "invocation_token": binding["invocation_token"], "digests": dict(binding["digests"]),
            "project_root": str(Path(ACTIVE.config.rootpath).resolve() if ACTIVE else ROOT),
            "nodeid": ACTIVE.nodeid if ACTIVE else "unit-only", "case_id": case_id, "process_token": token,
            "hook_ref": "src/lqcd_agent/control/coordinator.py:boundary", "receipt_path": str(directory / (token + ".json"))}
    if scoped and ACTIVE is not None and ACTIVE.value["schema_version"] == "0.2":
        reference, = ACTIVE.value["pytest_requests"]
        execution_request(reference, ACTIVE.value, nodeid=ACTIVE.nodeid, case_id=case_id)
        request.update(schema_version="0.2", pytest_request=reference)
    PENDING_PROCESS_REQUESTS[token] = canonical(request)
    return request


def consume_process_hook(request, process, *, expected_exit):
    """A crash receipt proves a trigger, never a recovered case outcome."""
    require(request["process_token"] not in CONSUMED_PROCESS_RECEIPTS, "process_hook", "duplicate_receipt", "invalid_evidence")
    require(PENDING_PROCESS_REQUESTS.get(request["process_token"]) == canonical(request),
            "process_hook", "original_parent_request", "invalid_evidence")
    require(type(expected_exit) is int and process.exitcode == expected_exit and process.pid is not None,
            "process_hook", "process_exit", "invalid_evidence")
    if ACTIVE:
        require(request["invocation_token"] == ACTIVE.value["invocation_token"] and request["digests"] == ACTIVE.value["digests"] and
                request["nodeid"] == ACTIVE.nodeid and request["project_root"] == str(Path(ACTIVE.config.rootpath).resolve()),
                "process_hook", "session_binding", "invalid_evidence")
    if request.get("schema_version") == "0.2":
        require(ACTIVE is not None and ACTIVE.value["schema_version"] == "0.2", "process_hook", "scoped_outer")
        execution_request(request["pytest_request"], ACTIVE.value, nodeid=request["nodeid"], case_id=request["case_id"])
    receipt = read(Path(request["receipt_path"]))
    keys(receipt, {"request", "process_id", "hook_ref"}, "process_hook")
    require(receipt["request"] == request and receipt["process_id"] == process.pid and receipt["hook_ref"] == request["hook_ref"],
            "process_hook", "receipt_binding", "invalid_evidence")
    CONSUMED_PROCESS_RECEIPTS.add(request["process_token"])
    del PENDING_PROCESS_REQUESTS[request["process_token"]]
    event = {"case_id": request["case_id"], "nodeid": request["nodeid"], "hook_ref": receipt["hook_ref"]}
    if ACTIVE:
        ACTIVE.value["hook_events"].append(event)
    return event


def observe_case(case_id, outcome, invariants, trace):
    """Record the recovered outcome after the independently observed production trigger."""
    if ACTIVE:
        normalize(trace, binding=ACTIVE.value)
        ACTIVE.value["case_results"].append({"case_id": case_id, "nodeid": ACTIVE.nodeid,
                                           "outcome": outcome, "invariants": invariants, "trace": trace})


ROOT_FIELDS = {"schema_version", "invocation_token", "digests", "project_root", "check_id",
               "execution_nonce", "selection", "batch_lengths"}
LEAF_FIELDS = {"schema_version", "invocation_token", "digests", "selection", "execution_root", "batch_index"}


def referenced_request(reference):
    keys(reference, {"path", "sha256"}, "request_reference")
    require(type(reference["path"]) is str and bool(reference["path"]), "request_reference", "path")
    path = Path(reference["path"])
    require(path.is_absolute() and path == path.resolve() and path.is_file() and
            all(not ancestor.is_symlink() for ancestor in (path, *path.parents)), "request_reference", "path")
    raw = path.read_bytes()
    require(sha(raw) == reference["sha256"], "request_reference", "original_bytes", "invalid_evidence")
    value = read(path)
    require(canonical(value) == raw, "request_reference", "canonical_bytes", "invalid_evidence")
    return value


def execution_request(reference, binding, *, nodeid=None, case_id=None):
    """Qualify live original transport before source effects or response consumption."""
    from .contracts import EXIT_CHECKS
    from .trace_proof import sha_value
    leaf = referenced_request(reference)
    keys(leaf, LEAF_FIELDS, "pytest_leaf")
    root = referenced_request(leaf["execution_root"])
    keys(root, ROOT_FIELDS, "pytest_execution")
    require(root["schema_version"] == leaf["schema_version"] == "0.2" and
            root["check_id"] in (*EXIT_CHECKS, "required", "capacity_calibration"), "pytest_execution", "identity")
    sha_value(root["execution_nonce"], "execution_nonce")
    strings(root["selection"], "pytest_execution", "selection")
    require(root["selection"] == sorted(set(root["selection"])) and bool(root["selection"]),
            "pytest_execution", "complete_selection")
    lengths = root["batch_lengths"]
    require(type(lengths) is list and bool(lengths) and all(type(n) is int and n > 0 for n in lengths) and
            sum(lengths) == len(root["selection"]), "pytest_execution", "batch_lengths")
    index = leaf["batch_index"]
    require(type(index) is int and 0 <= index < len(lengths), "pytest_leaf", "batch_index")
    offset = sum(lengths[:index])
    require(leaf["selection"] == root["selection"][offset:offset + lengths[index]], "pytest_leaf", "selection")
    for value in (root, leaf):
        require(value["invocation_token"] == binding["invocation_token"] and value["digests"] == binding["digests"],
                "pytest_execution", "session_binding", "invalid_evidence")
    directory = Path(leaf["execution_root"]["path"]).parent
    require(Path(root["project_root"]).is_absolute() and Path(root["project_root"]).resolve() == Path(root["project_root"]) and
            directory != Path(root["project_root"]) and not directory.is_relative_to(Path(root["project_root"])),
            "pytest_execution", "project_root")
    require(Path(leaf["execution_root"]["path"]).name == root["check_id"] + "-execution.json" and
            Path(reference["path"]) == directory / f"{root['check_id']}-{index:04d}-request.json",
            "pytest_execution", "request_names")
    if "execution_root" in binding:
        require(binding["schema_version"] == "0.2" and binding["execution_root"] == leaf["execution_root"],
                "pytest_execution", "outer_root", "invalid_evidence")
        if "pytest_requests" in binding:
            require(reference in binding["pytest_requests"], "pytest_execution", "outer_leaf", "invalid_evidence")
    if nodeid is not None:
        require(nodeid in leaf["selection"], "pytest_execution", "nodeid", "invalid_evidence")
    if case_id is not None:
        require(nodeid == "tests/phase_b/test_b04_runtime_cases.py::test_independent_case[" + case_id + "]",
                "pytest_execution", "case_id", "invalid_evidence")
    return root, leaf


def _begin_execution(session, selection, check_id, lengths):
    from .session import EXECUTIONS
    from .contracts import EXIT_CHECKS
    require(check_id in (*EXIT_CHECKS, "required", "capacity_calibration"), "pytest_execution", "check_id")
    require(session in EXECUTIONS and check_id not in EXECUTIONS[session], "pytest_execution", "fresh_check", "invalid_evidence")
    strings(selection, "pytest_execution", "selection")
    require(selection == sorted(set(selection)) and bool(selection), "pytest_execution", "selection")
    require(type(lengths) is list and bool(lengths) and all(type(n) is int and n > 0 for n in lengths) and
            sum(lengths) == len(selection), "pytest_execution", "batch_lengths")
    root = {"schema_version": "0.2", "invocation_token": session.token, "digests": session.digests,
            "project_root": str(session.root), "check_id": check_id, "execution_nonce": secrets.token_hex(32),
            "selection": list(selection), "batch_lengths": list(lengths)}
    path = session.directory / (check_id + "-execution.json")
    raw = canonical(root)
    state = {"root": root, "raw": raw, "reference": {"path": str(path), "sha256": sha(raw)},
             "leaves": [], "completed": None}
    EXECUTIONS[session][check_id] = state
    write_new(path, root)
    return state


def _execution_authority(value, session, *, check_id=None, completed=True):
    from .session import EXECUTIONS
    require(session in EXECUTIONS, "pytest_execution", "actual_session", "invalid_evidence")
    root = referenced_request(value["execution_root"])
    keys(root, ROOT_FIELDS, "pytest_execution")
    cid = root["check_id"]
    require(type(cid) is str, "pytest_execution", "check_id")
    require(check_id is None or cid == check_id, "pytest_execution", "expected_check", "invalid_evidence")
    state = EXECUTIONS[session].get(cid)
    require(state is not None and state["reference"] == value["execution_root"] and
            state["raw"] == canonical(root) and root["project_root"] == str(session.root),
            "pytest_execution", "original_issuance", "invalid_evidence")
    refs = value["pytest_requests"]
    require(type(refs) is list and bool(refs), "pytest_execution", "leaf_references")
    indices = []
    for reference in refs:
        _, leaf = execution_request(reference, value)
        index = leaf["batch_index"]
        require(index < len(state["leaves"]), "pytest_execution", "issued_leaf", "invalid_evidence")
        issued = state["leaves"][index]
        require(reference == {"path": issued["path"], "sha256": sha(issued["raw"])} and
                canonical(leaf) == issued["raw"] and issued["response"] is not None,
                "pytest_execution", "original_leaf_response", "invalid_evidence")
        indices.append(index)
    require(indices == sorted(set(indices)), "pytest_execution", "ordered_partition", "invalid_evidence")
    if completed:
        require(indices == list(range(len(root["batch_lengths"]))) and value["selection"] == root["selection"] and
                state["completed"] == sha(canonical(value)), "pytest_execution", "completed_response", "invalid_evidence")
    else:
        require(len(indices) == 1 and state["leaves"][indices[0]]["response"] == sha(canonical(value)),
                "pytest_execution", "native_leaf_response", "invalid_evidence")
    return state


def _run_pytest(session, selection, *, name, extra=(), execution=None):
    strings(selection, "pytest", "selection")
    request = session.directory / (name + "-request.json")
    output = session.directory / (name + "-pytest.json")
    value = {"schema_version": "0.1", "invocation_token": session.token,
             "digests": session.digests, "selection": selection}
    if execution is not None:
        state, index = execution
        value.update(schema_version="0.2", execution_root=state["reference"], batch_index=index)
        state["leaves"].append({"path": str(request), "raw": canonical(value), "response": None})
    write_new(request, value)
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("PYTEST_") or key.startswith("PHASE_B_"):
            env.pop(key)
    env.update(RUN_LIVE_LLM_TESTS="0", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
               PHASE_B_EVIDENCE_REQUEST=str(request), PHASE_B_EVIDENCE_OUTPUT=str(output))
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + str(session.root / "src")
    process = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "harness.pytest_evidence",
                              *selection, *extra], cwd=session.root, env=env, capture_output=True, timeout=450)
    with (session.directory / (name + "-output.txt")).open("xb") as stream:
        stream.write(process.stdout + process.stderr)
    require(output.is_file(), "pytest", "writer_output", "invalid_evidence")
    value = read(output)
    require(value.get("exit_code") == process.returncode, "pytest", "process_exit", "invalid_evidence")
    if execution is not None:
        state["leaves"][index]["response"] = sha(canonical(value))
    return value


def run_pytest(session, selection, *, name="required", extra=(), check_id=None):
    if check_id is None:
        return _run_pytest(session, selection, name=name, extra=extra)
    state = _begin_execution(session, selection, check_id, [len(selection)])
    value = _run_pytest(session, selection, name=check_id + "-0000", extra=extra, execution=(state, 0))
    _execution_authority(value, session, check_id=check_id, completed=False)
    _validate_pytest(value, session, selection)
    session.unchanged()
    state["completed"] = sha(canonical(value))
    return value


def run_pytest_batches(session, selection, *, name="runtime", batch_size=25, batch_lengths=None,
                       before_batch=None, check_id=None):
    """Validate every bounded batch before merging an exact single-session selection."""
    strings(selection, "pytest", "selection")
    require(type(batch_size) is int and batch_size > 0, "pytest", "batch_size")
    lengths = ([min(batch_size, len(selection) - offset) for offset in range(0, len(selection), batch_size)]
               if batch_lengths is None else batch_lengths)
    require(type(lengths) is list and bool(lengths) and all(type(n) is int and n > 0 for n in lengths) and
            sum(lengths) == len(selection), "pytest", "batch_lengths")
    require(check_id is not None or batch_lengths is None, "pytest", "scoped_plan")
    state = _begin_execution(session, selection, check_id, lengths) if check_id is not None else None
    merged, offset = None, 0
    for index, length in enumerate(lengths):
        if before_batch is not None:
            before_batch()
        nodes = selection[offset:offset + length]
        value = (_run_pytest(session, nodes, name=f"{check_id}-{index:04d}", execution=(state, index))
                 if state is not None else run_pytest(session, nodes, name=f"{name}-{index:04d}"))
        if state is not None:
            _execution_authority(value, session, check_id=check_id, completed=False)
            _validate_pytest(value, session, nodes)
        else:
            validate_pytest(value, session, nodes)
        session.unchanged()
        if merged is None:
            merged = {**value, "selection": list(selection)}
        else:
            for key in ("collected", "nodes", "observations", "hook_events", "case_results"):
                merged[key].extend(value[key])
            if state is not None:
                merged["pytest_requests"].extend(value["pytest_requests"])
        offset += length
    merged["collected"].sort()
    for key, identity in (("observations", "scenario_id"), ("hook_events", "case_id"), ("case_results", "case_id")):
        ids = [(row[identity], row["nodeid"]) for row in merged[key]]
        require(len(ids) == len(set(ids)), "pytest", "duplicate_batch_evidence", "invalid_evidence")
    _validate_pytest(merged, session, selection)
    session.unchanged()
    if state is not None:
        state["completed"] = sha(canonical(merged))
    return merged


def validate_pytest(value, session, selection, *, check_id=None, schema_version=None):
    require(type(value) is dict, "pytest", "fields")
    version = value.get("schema_version")
    require(schema_version is None or version == schema_version, "pytest", "expected_schema", "invalid_evidence")
    require(check_id is None or version == "0.2", "pytest", "scoped_check", "invalid_evidence")
    if version == "0.2":
        keys(value, ENVELOPE | {"execution_root", "pytest_requests"}, "pytest")
        _execution_authority(value, session, check_id=check_id)
    return _validate_pytest(value, session, selection)


def _validate_pytest(value, session, selection):
    version = value.get("schema_version")
    keys(value, ENVELOPE | ({"execution_root", "pytest_requests"} if version == "0.2" else set()), "pytest")
    require(version in ("0.1", "0.2"), "pytest", "schema_version")
    session.verify_binding(value)
    require(value["selection"] == selection, "pytest", "selection", "invalid_evidence")
    strings(value["collected"], "pytest", "collected")
    expected = sorted(selection)
    require(value["collected"] == expected and value["deselected"] == [], "pytest", "collection", "invalid_evidence")
    require(type(value["exit_code"]) is int and value["exit_code"] == 0, "pytest", "exit_code", "check_failed")
    require(type(value["nodes"]) is list, "pytest", "nodes")
    actual = []
    for row in value["nodes"]:
        keys(row, {"nodeid", "when", "outcome", "xfail"}, "node")
        require(row["nodeid"] in expected and row["when"] in ("setup", "call", "teardown"), "node", "identity")
        require(row["outcome"] == "passed" and row["xfail"] is False, row["nodeid"], row["when"], "check_failed")
        actual.append((row["nodeid"], row["when"]))
    require(sorted(actual) == sorted((node, phase) for node in expected for phase in ("setup", "call", "teardown")),
            "pytest", "unique_complete_results", "invalid_evidence")
    require(all(type(value[k]) is list for k in ("observations", "hook_events", "case_results")), "pytest", "observations")
    for row in value["observations"]:
        keys(row, {"scenario_id", "nodeid", "result", "invariants", "trace"}, "observation")
        validate_result(row["result"])
        strings(row["invariants"], "observation", "invariants")
        require(type(row["scenario_id"]) is str and bool(row["scenario_id"]) and row["nodeid"] in expected,
                "observation", "identity")
        if row["trace"] is not None:
            normalize(row["trace"], binding=value)
    for row in value["hook_events"]:
        keys(row, {"case_id", "nodeid", "hook_ref"}, "hook")
        require(all(type(row[k]) is str and row[k] for k in ("case_id", "nodeid", "hook_ref")), "hook", "identity")
        require(row["nodeid"] in expected, "hook", "nodeid")
    for row in value["case_results"]:
        keys(row, {"case_id", "nodeid", "outcome", "invariants", "trace"}, "case_result")
        require(all(type(row[k]) is str and row[k] for k in ("case_id", "nodeid", "outcome")), "case_result", "identity")
        require(row["nodeid"] in expected, "case_result", "nodeid")
        strings(row["invariants"], "case_result", "invariants")
        normalize(row["trace"], binding=value)
    return value


def collect_pytest(session, selection):
    value = run_pytest(session, selection, name="preflight", extra=("--collect-only",))
    keys(value, ENVELOPE, "collection")
    session.verify_binding(value)
    require(value["schema_version"] == "0.1" and value["selection"] == selection and value["collected"] == selection
            and value["deselected"] == [] and type(value["exit_code"]) is int and value["exit_code"] == 0
            and value["nodes"] == [] and value["observations"] == [] and value["hook_events"] == [] and value["case_results"] == [],
            "pytest", "preflight_collection", "invalid_evidence")


def collect_roots(session, roots, name):
    value = run_pytest(session, list(roots), name=name, extra=("--collect-only",))
    keys(value, ENVELOPE, "collection")
    session.verify_binding(value)
    require(value["schema_version"] == "0.1" and value["selection"] == list(roots) and value["exit_code"] == 0
            and value["deselected"] == [] and value["nodes"] == [] and value["observations"] == []
            and value["hook_events"] == [] and value["case_results"] == [], "collection", "complete", "invalid_evidence")
    strings(value["collected"], "collection", "collected")
    for node in value["collected"]:
        require(any(node.startswith(root + ("::" if root.endswith(".py") else "/")) for root in roots),
                "collection", "root", "invalid_evidence")
    return tuple(value["collected"])


def validate_observations(value, scenarios, root, *, all_scenarios=None):
    expected = {(s["scenario_id"], n): s for s in scenarios for n in s["pytest_nodeids"]}
    known = {(s["scenario_id"], n) for s in (all_scenarios if all_scenarios is not None else scenarios)
             for n in s["pytest_nodeids"]}
    seen = set()
    for row in value["observations"]:
        keys(row, {"scenario_id", "nodeid", "result", "invariants", "trace"}, "observation")
        key = (row["scenario_id"], row["nodeid"])
        require(key in known and key not in seen, "observation", "identity", "invalid_evidence")
        seen.add(key)
        # A shared node may report another known slice; it cannot enter this slice's totals.
        if key not in expected:
            continue
        scenario = expected[key]
        validate_result(row["result"])
        require(canonical(row["result"]) == canonical(scenario["expected_result"]), key[0], "result", "invalid_evidence")
        require(row["invariants"] == scenario["required_invariants"], key[0], "invariants", "invalid_evidence")
        trace = scenario["expected_trace_fixture"]
        if trace is None:
            require(row["trace"] is None, key[0], "trace")
        else:
            compare(row["trace"], read(path_in(root, trace)), binding=value)
    require(set(expected) <= seen, "observation", "missing", "invalid_evidence")
    return {s["scenario_id"] for s in scenarios}
