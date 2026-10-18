"""Original native requests remain strict across isolated diagnostic children."""
from copy import deepcopy
import multiprocessing
from pathlib import Path

import pytest

from harness import pytest_evidence
from harness.contracts import ROOT
from harness.failpoints import validate_runtime
from harness.session import Session
from harness.strict_json import Invalid, read, write_new
from helpers.b04_process_binding import child_binding, run_native_case, validate_probe
from helpers.trace_sources import current_binding


CASE = "artifact.bounded_state_sync.after.committed_result_replay"


def binding_client(pipe, request, fault):
    before = current_binding()
    actual = deepcopy(request)
    if fault == "missing":
        del actual["digests"]
    elif fault == "case":
        actual["case_id"] = "foreign"
    elif fault == "nonce":
        actual["process_token"] = "invalid"
    elif fault == "digest":
        actual["digests"]["registry"] = "invalid"
    elif fault == "project":
        actual["project_root"] = "/private/tmp"
    elif fault == "hook":
        actual["hook_ref"] = "test:spoofed"
    elif fault == "path":
        actual["receipt_path"] = str(ROOT / "forged.json")
    try:
        with child_binding(actual, CASE):
            inside = current_binding()
            with child_binding(actual, CASE):
                assert current_binding() == inside
            foreign = deepcopy(actual)
            foreign["invocation_token"] = "f" * 64
            with pytest.raises(Invalid, match="nested_binding"):
                with child_binding(foreign, CASE):
                    raise AssertionError("A foreign nested binding was entered")
            actual["digests"]["registry"] = "0" * 64
            assert current_binding() == inside
            if fault == "exception":
                raise RuntimeError("Original scoped failure")
        pipe.send({"before": before, "inside": inside, "after": current_binding()})
    except (Invalid, RuntimeError) as error:
        pipe.send({"before": before, "after": current_binding(), "error": str(error)})
    finally:
        pipe.close()


@pytest.mark.parametrize("fault", ["valid", "exception", "missing", "case", "nonce", "digest", "project", "hook", "path"])
def test_spawned_context_is_explicit_scoped_and_restored(tmp_path, fault):
    request = pytest_evidence.process_hook_request(CASE, tmp_path)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=binding_client, args=(child, request, fault))
    process.start()
    child.close()
    try:
        assert parent.poll(20)
        result = parent.recv()
        process.join(20)
        assert process.exitcode == 0
        assert result["before"] == result["after"]
        assert result["after"]["invocation_token"] == "unit-only-not-acceptance"
        if fault == "valid":
            assert result["inside"] == {key: request[key] for key in ("invocation_token", "digests")}
        else:
            assert "error" in result
    finally:
        if process.is_alive():
            process.terminate()
            process.join(10)
        parent.close()
    assert not Path(request["receipt_path"]).exists()


def test_parent_writer_cannot_be_replaced_by_child_context(tmp_path):
    request = pytest_evidence.process_hook_request(CASE, tmp_path)
    before = current_binding()
    with pytest.raises(Invalid, match="spawned_child"):
        with child_binding(request, CASE):
            pytest.fail("The parent entered a child context")
    assert current_binding() == before


@pytest.fixture(scope="module")
def native_probe():
    root = run_native_case(CASE)
    session = Session.__new__(Session)
    session.root, session.directory = ROOT, root / "0"
    binding = read(session.directory / "session-binding.json")
    session.token, session.digests = binding["invocation_token"], binding["digests"]
    return session, read(session.directory / "required-pytest.json")


def test_native_diagnostics_keep_canonical_registry_and_outer_hooks(native_probe):
    session, value = native_probe
    assert validate_probe(value, session, CASE)
    registry_path = ROOT / "tests/phase_b/failpoint_registry.json"
    before = registry_path.read_bytes()
    unbound = read(registry_path)
    for entry in unbound["entries"]:
        entry["case_bindings"] = [row for row in entry["case_bindings"] if row["case_id"] != CASE]
    with pytest.raises(Invalid, match="hook:case_id"):
        validate_runtime(value, unbound, {CASE: {}}, [], ROOT)
    bound = deepcopy(unbound)
    entry = next(row for row in bound["entries"] if row["hook_ref"] == value["hook_events"][0]["hook_ref"])
    entry["case_bindings"].append({"case_id": CASE, "scenario_ids": []})
    assert value["case_results"] == []
    assert validate_runtime(value, bound, {CASE: {}}, [], ROOT) == []
    assert registry_path.read_bytes() == before
    if pytest_evidence.ACTIVE:
        writer = pytest_evidence.ACTIVE
        assert not [row for row in writer.value["hook_events"] if row["nodeid"] == writer.nodeid]


@pytest.mark.parametrize("fault", ["session", "digest", "missing_hook", "duplicate_hook", "case", "node", "hook",
                                  "failed", "owned", "observation"])
def test_original_native_envelope_tampering_is_rejected(native_probe, fault):
    session, original = native_probe
    value = deepcopy(original)
    if fault == "session":
        value["invocation_token"] = "f" * 64
    elif fault == "digest":
        value["digests"]["registry"] = "f" * 64
    elif fault == "missing_hook":
        value["hook_events"].clear()
    elif fault == "duplicate_hook":
        value["hook_events"] *= 2
    elif fault in ("case", "node", "hook"):
        value["hook_events"][0][{"case": "case_id", "node": "nodeid", "hook": "hook_ref"}[fault]] = "foreign"
    elif fault == "failed":
        value["exit_code"] = 1
    elif fault == "owned":
        value["case_results"] = [{}]
    else:
        value["observations"][0]["result"]["value"] = False
    with pytest.raises(Invalid):
        validate_probe(value, session, CASE)
    assert original == read(session.directory / "required-pytest.json")


@pytest.mark.parametrize("fault", ["source_session", "case", "request_nonce", "request_node", "request_path", "bytes", "missing"])
def test_retained_original_source_rejects_rebinding(native_probe, tmp_path, fault):
    session, value = native_probe
    original = read(session.directory / "probe-sources.json")
    changed = deepcopy(original)
    if fault == "source_session":
        changed["binding"]["invocation_token"] = "f" * 64
    elif fault == "case":
        changed["case_id"] = "foreign"
    elif fault.startswith("request_"):
        changed["request"][{"request_nonce": "process_token", "request_node": "nodeid",
                            "request_path": "receipt_path"}[fault]] = "foreign"
    elif fault == "bytes":
        changed["files"][0]["sha256"] = "f" * 64
    else:
        changed["files"] = changed["files"][1:]
    negative = Session.__new__(Session)
    negative.root, negative.directory = session.root, tmp_path
    negative.token, negative.digests = session.token, session.digests
    write_new(tmp_path / "probe-sources.json", changed)
    with pytest.raises(Invalid):
        validate_probe(value, negative, CASE)
    assert original == read(session.directory / "probe-sources.json")


def test_failed_native_child_is_not_hidden(monkeypatch):
    def fail(*args, **kwargs):
        raise Invalid("pytest", "exit_code", "check_failed")
    monkeypatch.setattr(pytest_evidence, "run_pytest", fail)
    with pytest.raises(Invalid, match="check_failed:pytest:exit_code"):
        run_native_case(CASE)
