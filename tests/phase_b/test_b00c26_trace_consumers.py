"""All original consumers independently read the same native fault anchor."""
from copy import deepcopy

import pytest

from harness.contracts import ROOT
from harness.exit_checks import Adapter, validate_exit
from harness.failpoints import validate_runtime
from harness.pytest_evidence import validate_observations, validate_pytest
from harness.session import Session
from harness.strict_json import Invalid, read, sha, write_new
from harness.trace import normalize
from helpers.b04_process_binding import HOOK, nodeid, run_fault_case


CASE = "budget.resource_settled.after.non_materializable_domain_gap"
FAULTS = ("missing", "duplicate", "foreign_owner", "foreign_run", "foreign_workspace", "epoch", "case", "node",
          "receipt", "session", "forged_chain", "S0_as_S2", "missing_recovery", "repeat_business", "fixture", "extra_CAS")


@pytest.fixture(scope="module")
def native():
    root = run_fault_case(CASE, local_consumers=True)
    session = Session.__new__(Session)
    session.root, session.directory = ROOT, root / "0"
    binding = read(session.directory / "session-binding.json")
    session.token, session.digests = binding["invocation_token"], binding["digests"]
    value = read(session.directory / "required-pytest.json")
    scenario = {"scenario_id": "B00C26-PROBE", "pytest_nodeids": [nodeid(CASE)],
        "expected_result": {"kind": "boolean", "value": True}, "required_invariants": value["observations"][0]["invariants"],
        "expected_trace_fixture": "tests/phase_b/expected_traces/b00c26/missing_capability.json"}
    registry = {"entries": [{"hook_ref": HOOK, "case_bindings": [{"case_id": CASE, "scenario_ids": ["B00C26-PROBE"]}]}]}
    return session, value, scenario, registry


def consume(native, value, consumer, name):
    session, _, scenario, registry = native
    if consumer == "collector":
        validate_pytest(value, session, [nodeid(CASE)])
    elif consumer == "matrix":
        assert validate_observations(value, [scenario], ROOT) == {"B00C26-PROBE"}
    elif consumer == "runtime":
        specs = {CASE: {"outcome": CASE.rsplit(".", 1)[1], "invariants": scenario["required_invariants"]}}
        assert validate_runtime(value, registry, specs, [scenario], ROOT) == [CASE]
    else:
        path = session.directory / (name + ".json")
        write_new(path, value)
        adapter = Adapter(lambda _: pytest.fail("Use the original native evidence"), (nodeid(CASE),), (scenario,))
        return validate_exit({"schema_version": "0.1", "invocation_token": session.token, "digests": session.digests,
            "check_id": "layer_0", "exit_code": 0, "evidence_refs": [{"relative_path": path.name,
            "sha256": sha(path.read_bytes())}]}, "layer_0", session, adapter)


def corrupt(value, fault):
    bad = deepcopy(value)
    for group in ("observations", "case_results"):
        proof = bad[group][0]["trace"]["proof"]
        declaration = proof["fault_sources"][0]
        recovery = declaration["recovery_observation"]
        if fault == "missing": proof["fault_sources"].clear()
        elif fault == "duplicate": proof["fault_sources"] *= 2
        elif fault == "foreign_owner": recovery["first_call"]["owner"]["worker_id"] = "foreign"
        elif fault == "foreign_run": declaration["original_source"]["roots"][0]["path"] = "/private/tmp/foreign"
        elif fault == "foreign_workspace": proof["workspace_roots"].append({"path": "/private/tmp/foreign"})
        elif fault == "epoch": recovery["first_call"]["owner"]["invocation_epoch"] += 1
        elif fault == "case": declaration["case_id"] = "foreign"
        elif fault == "node": declaration["process_request"]["nodeid"] = "foreign"
        elif fault == "receipt": declaration["process_receipt"]["process_id"] += 1
        elif fault == "session": proof["binding"]["invocation_token"] = "f" * 64
        elif fault == "forged_chain":
            declaration["original_source"]["anchor"] = "/private/tmp/candidate-anchor.json"
            for field in ("before_snapshot", "after_snapshot"):
                declaration[field]["manifest_sha256"] = sha(("replacement " + field).encode())
            declaration["fault_observation"]["before_snapshot_sha256"] = declaration["before_snapshot"]["manifest_sha256"]
            declaration["fault_observation"]["after_snapshot_sha256"] = declaration["after_snapshot"]["manifest_sha256"]
            for field in ("after_recovery", "after_repeat"):
                recovery[field]["manifest_sha256"] = sha(("replacement " + field).encode())
        elif fault == "S0_as_S2": recovery["after_recovery"] = deepcopy(declaration["before_snapshot"])
        elif fault == "missing_recovery": recovery["first_call"] = None
        elif fault == "repeat_business": recovery["repeat_calls"][0]["return"] = {"settled": True}
        elif fault == "fixture": recovery["first_call"]["identities_after"]["namespace"] = "foreign"
        elif fault == "extra_CAS": recovery["repeat_calls"].append(deepcopy(recovery["repeat_calls"][0]))
        else: raise AssertionError(fault)
    return bad


@pytest.mark.parametrize("consumer", ["collector", "matrix", "runtime", "exit"])
def test_native_source_has_four_consumers(native, consumer):
    consume(native, native[1], consumer, "valid-" + consumer)


@pytest.mark.parametrize("consumer", ["collector", "matrix", "runtime", "exit"])
@pytest.mark.parametrize("fault", FAULTS)
def test_candidate_rehash_does_not_replace_native_authority(native, consumer, fault):
    with pytest.raises(Invalid):
        consume(native, corrupt(native[1], fault), consumer, "invalid-" + consumer + "-" + fault)


def test_reread_keeps_actual_source_and_has_no_effect(native):
    session, value, _, _ = native
    raw = value["observations"][0]["trace"]
    from harness.fault_source_trace import anchor_directory, live_state, read_value_bytes, evidence_bytes
    directory = anchor_directory(value, CASE)
    roots = raw["proof"]["fault_sources"][0]["original_source"]["roots"]
    request = read_value_bytes(evidence_bytes(directory, "request.json"))
    before = live_state(roots, request)
    first = normalize(raw, binding=value)
    assert normalize(raw, binding=value) == first
    assert live_state(roots, request) == before
    session.unchanged()
