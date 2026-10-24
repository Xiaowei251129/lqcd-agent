"""Actual transport responses, complete partitions and immutable check authority."""
from copy import deepcopy
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness.contracts import DIGEST_KEYS
from harness.session import Session
from harness.strict_json import Invalid, canonical, read, sha
from harness import pytest_evidence as pe
from harness.exit_checks import normalized_pytest


@pytest.fixture(scope="module")
def native():
    root = Path(mkdtemp(prefix="lqcd-agent-c32-transport-", dir="/private/tmp"))
    project = root / "project"
    (project / "tests").mkdir(parents=True)
    (project / "tests/test_transport.py").write_text(
        "def test_a(): assert True\ndef test_b(): assert True\ndef test_c(): assert True\ndef test_failure(): assert False\n")
    selection = ["tests/test_transport.py::test_" + name for name in ("a", "b", "c")]
    digests = dict.fromkeys(set(DIGEST_KEYS) - {"worktree_inputs"}, "1" * 64)
    parents, values = [], []
    for index, plan in enumerate(([1, 2], [2, 1])):
        parent = Session(project, root / str(index), digests)
        value = pe.run_pytest_batches(parent, selection, check_id="required", batch_lengths=list(plan))
        pe.validate_pytest(value, parent, selection, check_id="required", schema_version="0.2")
        parents.append(parent)
        values.append(value)
    return root, selection, parents, values


def test_actual_complete_roots_are_semantically_equal_across_plans(native):
    _, selection, parents, values = native
    assert normalized_pytest(values[0]) == normalized_pytest(values[1])
    assert values[0]["execution_root"] != values[1]["execution_root"]
    for parent, value in zip(parents, values):
        pe.validate_pytest(value, parent, selection, check_id="required")


@pytest.mark.parametrize("fault", ["parent", "check", "token", "digests", "selection", "partial", "duplicate", "reordered", "response", "root_hash", "leaf_hash"])
def test_transport_retag_and_partition_changes_are_rejected(native, fault):
    _, selection, parents, values = native
    value = deepcopy(values[0])
    parent = parents[0]
    if fault == "parent": parent = parents[1]
    elif fault == "check":
        with pytest.raises(Invalid): pe.validate_pytest(value, parent, selection, check_id="full_pytest")
        return
    elif fault == "token": value["invocation_token"] = "f" * 64
    elif fault == "digests": value["digests"]["worktree_inputs"] = "f" * 64
    elif fault == "selection": value["selection"] = selection[:-1]
    elif fault == "partial": value["pytest_requests"] = value["pytest_requests"][:1]
    elif fault == "duplicate": value["pytest_requests"].append(value["pytest_requests"][0])
    elif fault == "reordered": value["pytest_requests"].reverse()
    elif fault == "response": value["nodes"][0]["outcome"] = "failed"
    elif fault == "root_hash": value["execution_root"]["sha256"] = "f" * 64
    else: value["pytest_requests"][0]["sha256"] = "f" * 64
    with pytest.raises(Invalid): pe.validate_pytest(value, parent, selection, check_id="required")


def test_request_only_cannot_authorize_retagged_actual_response(native):
    root, selection, parents, values = native
    parent = Session(parents[0].root, root / "request-only", dict.fromkeys(set(DIGEST_KEYS) - {"worktree_inputs"}, "1" * 64))
    state = pe._begin_execution(parent, selection, "required", [len(selection)])
    leaf = {"schema_version": "0.2", "invocation_token": parent.token, "digests": parent.digests,
            "selection": selection, "execution_root": state["reference"], "batch_index": 0}
    path = parent.directory / "required-0000-request.json"
    path.write_bytes(canonical(leaf))
    value = deepcopy(values[0])
    value.update(invocation_token=parent.token, digests=parent.digests, execution_root=state["reference"],
                 pytest_requests=[{"path": str(path), "sha256": sha(path.read_bytes())}])
    with pytest.raises(Invalid): pe.validate_pytest(value, parent, selection, check_id="required")


def test_one_leaf_also_requires_completed_actual_response(native):
    root, selection, parents, _ = native
    parent = Session(parents[0].root, root / "one-leaf", dict.fromkeys(set(DIGEST_KEYS) - {"worktree_inputs"}, "1" * 64))
    state = pe._begin_execution(parent, selection[:1], "required", [1])
    value = pe._run_pytest(parent, selection[:1], name="required-0000", execution=(state, 0))
    with pytest.raises(Invalid): pe.validate_pytest(value, parent, selection[:1], check_id="required")
    pe._execution_authority(value, parent, completed=False)
    pe._validate_pytest(value, parent, selection[:1])


def test_failed_root_does_not_complete_and_cannot_retry(native):
    root, _, parents, _ = native
    parent = Session(parents[0].root, root / "failed", dict.fromkeys(set(DIGEST_KEYS) - {"worktree_inputs"}, "1" * 64))
    selection = ["tests/test_transport.py::test_failure"]
    with pytest.raises(Invalid): pe.run_pytest(parent, selection, check_id="required")
    value = read(parent.directory / "required-0000-pytest.json")
    with pytest.raises(Invalid): pe.validate_pytest(value, parent, selection)
    with pytest.raises(Invalid): pe.run_pytest(parent, selection, name="alternate", check_id="required")


def test_deleted_request_and_fabricated_session_do_not_restore_authority(native):
    root, selection, parents, _ = native
    parent = Session(parents[0].root, root / "deleted", dict.fromkeys(set(DIGEST_KEYS) - {"worktree_inputs"}, "1" * 64))
    pe._begin_execution(parent, selection, "required", [len(selection)])
    (parent.directory / "required-execution.json").unlink()
    with pytest.raises(Invalid): pe.run_pytest(parent, selection, name="alternate", check_id="required")
    fake = Session.__new__(Session)
    fake.__dict__.update(parent.__dict__)
    with pytest.raises(Invalid): pe._begin_execution(fake, selection, "full_pytest", [len(selection)])


@pytest.mark.parametrize("field", ["schema_version", "invocation_token", "digests", "project_root", "check_id", "execution_nonce", "selection", "batch_lengths", "batch_index", "nodeid", "case_id"])
def test_rehashed_request_cannot_change_original_execution(native, field):
    root, selection, parents, _ = native
    parent = Session(parents[0].root, root / ("rehash-" + field), dict.fromkeys(set(DIGEST_KEYS) - {"worktree_inputs"}, "1" * 64))
    state = pe._begin_execution(parent, selection, "required", [len(selection)])
    value = pe._run_pytest(parent, selection, name="required-0000", execution=(state, 0))
    root_path = Path(state["reference"]["path"])
    descriptor = read(root_path)
    if field == "batch_index":
        path = Path(value["pytest_requests"][0]["path"])
        leaf = read(path); leaf[field] = True; path.write_bytes(canonical(leaf))
        value["pytest_requests"][0]["sha256"] = sha(path.read_bytes())
    elif field in ("nodeid", "case_id"):
        with pytest.raises(Invalid):
            pe.execution_request(value["pytest_requests"][0], value, nodeid="foreign", case_id="foreign" if field == "case_id" else None)
        return
    else:
        replacements = {"schema_version": "0.1", "invocation_token": "f" * 64, "digests": dict.fromkeys(DIGEST_KEYS, "f" * 64),
                        "project_root": str(root), "check_id": "full_pytest", "execution_nonce": "f" * 64,
                        "selection": selection[:-1], "batch_lengths": [1, len(selection)-1]}
        descriptor[field] = replacements[field]
        root_path.write_bytes(canonical(descriptor))
        value["execution_root"]["sha256"] = sha(root_path.read_bytes())
    with pytest.raises(Invalid): pe.validate_pytest(value, parent, selection, check_id="required")


def test_distinct_check_and_calibration_cannot_be_promoted(native):
    root, selection, parents, _ = native
    parent = Session(parents[0].root, root / "checks", dict.fromkeys(set(DIGEST_KEYS) - {"worktree_inputs"}, "1" * 64))
    a = pe.run_pytest(parent, selection[:1], check_id="layer_0")
    b = pe.run_pytest(parent, selection[:1], check_id="capacity_calibration")
    assert normalized_pytest(a)["check_id"] != normalized_pytest(b)["check_id"]
    for value in (a, b):
        with pytest.raises(Invalid): pe.validate_pytest(value, parent, selection[:1], check_id="required")
        with pytest.raises(Invalid): pe.validate_pytest(value, parent, selection[:1], schema_version="0.1")


@pytest.mark.parametrize("value", [None, [], "pytest", 0, False])
def test_malformed_envelope_keeps_the_original_typed_rejection(native, value):
    _, selection, parents, _ = native
    with pytest.raises(Invalid):
        pe.validate_pytest(value, parents[0], selection)


@pytest.mark.parametrize("batched", [False, True])
def test_input_fence_failure_never_completes_a_root_even_after_restoration(batched):
    root = Path(mkdtemp(prefix="lqcd-agent-c32-input-fence-", dir="/private/tmp"))
    project = root / "project"
    (project / "tests").mkdir(parents=True)
    path = project / "tests/test_input.py"
    source = 'from pathlib import Path\ndef test_change():\n    p=Path(__file__)\n    p.write_text(p.read_text()+"\\n")\n'
    path.write_text(source)
    parent = Session(project, root / "parent", dict.fromkeys(set(DIGEST_KEYS)-{"worktree_inputs"}, "1"*64))
    selection = ["tests/test_input.py::test_change"]
    runner = pe.run_pytest_batches if batched else pe.run_pytest
    with pytest.raises(Invalid, match="worktree_inputs"):
        runner(parent, selection, check_id="required")
    value = read(parent.directory / "required-0000-pytest.json")
    assert value["exit_code"] == 0
    path.write_text(source)
    parent.unchanged()
    with pytest.raises(Invalid, match="completed_response"):
        pe.validate_pytest(value, parent, selection, check_id="required")
    with pytest.raises(Invalid, match="fresh_check"):
        runner(parent, selection, check_id="required")
