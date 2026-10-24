"""Native scoped source authority preserves old semantics and independent checks."""
from copy import deepcopy
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness import pytest_evidence as pe
from harness.contracts import ROOT
from harness.inputs import PATHS
from harness.fault_source_trace import anchor_directory
from harness.session import Session
from harness.strict_json import Invalid, sha
from harness.trace import normalize


@pytest.fixture(scope="module")
def native():
    root = Path(mkdtemp(prefix="lqcd-agent-c32-native-", dir="/private/tmp"))
    parent = Session(ROOT, root / "parent", {key: sha((ROOT / path).read_bytes()) for key, path in PATHS.items()})
    case = "artifact.projection_publication.after.committed_result_replay"
    selection = ["tests/phase_b/test_b04_runtime_cases.py::test_independent_case[" + case + "]"]
    values = [pe.run_pytest(parent, selection, check_id=cid) for cid in ("required", "layer_0")]
    return parent, case, selection, values


def test_two_same_parent_native_sources_remain_independently_valid(native):
    parent, case, selection, values = native
    traces = [value["case_results"][0]["trace"] for value in values]
    assert all(trace["schema_version"] == "0.13" and trace["proof"]["schema_version"] == "0.10" for trace in traces)
    assert normalize(traces[0], binding=values[0]) == normalize(traces[1], binding=values[1])
    paths = [anchor_directory(value, case, pytest_request=trace["proof"]["pytest_request"]) for value, trace in zip(values, traces)]
    assert paths[0] != paths[1] and all((path / "anchor.json").is_file() for path in paths)
    for cid, value in zip(("required", "layer_0"), values):
        pe.validate_pytest(value, parent, selection, check_id=cid)


@pytest.mark.parametrize("fault", ["outer", "leaf", "downgrade", "old_outer", "bare_semantic", "source_version", "proof_version"])
def test_scoped_source_cannot_be_crossed_or_downgraded(native, fault):
    _, _, _, values = native
    trace = deepcopy(values[0]["case_results"][0]["trace"])
    binding = values[0]
    if fault == "outer": binding = values[1]
    elif fault == "leaf": trace["proof"]["pytest_request"] = values[1]["pytest_requests"][0]
    elif fault == "downgrade":
        trace["schema_version"] = "0.12"; trace["proof"]["schema_version"] = "0.9"; del trace["proof"]["pytest_request"]
    elif fault == "old_outer": binding = {"schema_version": "0.1", **{key: binding[key] for key in ("invocation_token", "digests")}}
    elif fault == "bare_semantic":
        trace = {"schema_version": "0.13", "representation": "semantic_expected", "events": trace["events"]}
        with pytest.raises(Invalid): normalize(trace, expected=True)
        return
    elif fault == "source_version": trace["schema_version"] = "0.14"
    else: trace["proof"]["schema_version"] = "0.9"
    with pytest.raises(Invalid): normalize(trace, binding=binding)
