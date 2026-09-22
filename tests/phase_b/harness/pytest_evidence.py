"""Project-owned pytest evidence, consumed only by its spawning session."""
import inspect
import ast
import os
import subprocess
import sys
import secrets
from pathlib import Path

import pytest

from .strict_json import keys, require, read, write_new, strings, path_in, canonical
from .matrix import validate_result
from .trace import normalize, compare

ACTIVE = None
ENVELOPE = {"schema_version", "invocation_token", "digests", "selection", "collected", "deselected",
            "exit_code", "nodes", "observations", "hook_events", "case_results"}


class Writer:
    def __init__(self, config):
        self.config = config
        self.output = Path(os.environ["PHASE_B_EVIDENCE_OUTPUT"])
        self.value = read(Path(os.environ["PHASE_B_EVIDENCE_REQUEST"]))
        keys(self.value, {"schema_version", "invocation_token", "digests", "selection"}, "pytest_request")
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


def process_hook_request(case_id, directory):
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


def run_pytest(session, selection, *, name="required", extra=()):
    strings(selection, "pytest", "selection")
    request = session.directory / (name + "-request.json")
    output = session.directory / (name + "-pytest.json")
    write_new(request, {"schema_version": "0.1", "invocation_token": session.token,
                        "digests": session.digests, "selection": selection})
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("PYTEST_") or key.startswith("PHASE_B_"):
            env.pop(key)
    env.update(RUN_LIVE_LLM_TESTS="0", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
               PHASE_B_EVIDENCE_REQUEST=str(request), PHASE_B_EVIDENCE_OUTPUT=str(output))
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + str(session.root / "src")
    process = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "harness.pytest_evidence",
                              *selection, *extra], cwd=session.root, env=env, capture_output=True, timeout=300)
    with (session.directory / (name + "-output.txt")).open("xb") as stream:
        stream.write(process.stdout + process.stderr)
    require(output.is_file(), "pytest", "writer_output", "invalid_evidence")
    value = read(output)
    require(value.get("exit_code") == process.returncode, "pytest", "process_exit", "invalid_evidence")
    return value


def run_pytest_batches(session, selection, *, name="runtime", batch_size=25):
    """Validate every bounded batch before merging an exact single-session selection."""
    strings(selection, "pytest", "selection")
    require(type(batch_size) is int and batch_size > 0, "pytest", "batch_size")
    merged = None
    for offset in range(0, len(selection), batch_size):
        nodes = selection[offset:offset + batch_size]
        value = run_pytest(session, nodes, name=f"{name}-{offset // batch_size:04d}")
        validate_pytest(value, session, nodes)
        session.unchanged()
        if merged is None:
            merged = {**value, "selection": list(selection)}
        else:
            for key in ("collected", "nodes", "observations", "hook_events", "case_results"):
                merged[key].extend(value[key])
    merged["collected"].sort()
    for key, identity in (("observations", "scenario_id"), ("hook_events", "case_id"), ("case_results", "case_id")):
        ids = [(row[identity], row["nodeid"]) for row in merged[key]]
        require(len(ids) == len(set(ids)), "pytest", "duplicate_batch_evidence", "invalid_evidence")
    validate_pytest(merged, session, selection)
    session.unchanged()
    return merged


def validate_pytest(value, session, selection):
    keys(value, ENVELOPE, "pytest")
    require(value["schema_version"] == "0.1", "pytest", "schema_version")
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
