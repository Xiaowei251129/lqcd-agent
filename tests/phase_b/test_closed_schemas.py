"""Permanent strict-schema, path, input-binding and projection rejection regressions."""
from copy import deepcopy
import os

import pytest

from harness.contracts import ROOT, load_contracts, required_ids
from harness.inputs import load_inputs
from harness.matrix import validate_matrix
from harness.inventory import validate_inventory
from harness.strict_json import Invalid, read, path_in, canonical, callable_ref
from harness.session import worktree_digest, Session
from harness.pytest_evidence import run_pytest, validate_pytest
from harness.ownership import OWNED
from test_evidence_and_final import session_for


@pytest.mark.parametrize("field,value", [
    ("schema_version", "0.2"), ("control_protocol_version", "0.3"),
    ("requirement_catalog_version", "0.1"), ("control_protocol_sha256", "0" * 64),
    ("requirement_catalog_sha256", "0" * 64), ("phase", "other"),
    ("implementation_slices", {}), ("scenarios", {}),
])
def test_matrix_top_closed(field, value):
    matrix = read(ROOT / "tests/phase_b/acceptance_matrix.json")
    matrix[field] = value
    with pytest.raises(Invalid):
        validate_matrix(matrix, load_contracts()[1], ROOT)


@pytest.mark.parametrize("field,value", [
    ("required", 1), ("scenario_id", ""), ("pytest_nodeids", []), ("pytest_nodeids", ["tests/absent.py::test_x"]),
    ("layer", "parallel"), ("fixture_id", "../outside.json"), ("contract_refs", []),
    ("expected_result", {"kind": "boolean", "value": 1}), ("required_invariants", []),
    ("validation_stage", "runtime"), ("implementation_ticket_id", []),
])
def test_matrix_scenario_closed(field, value):
    matrix = read(ROOT / "tests/phase_b/acceptance_matrix.json")
    matrix["scenarios"][0][field] = value
    with pytest.raises(Invalid):
        validate_matrix(matrix, load_contracts()[1], ROOT)


@pytest.mark.parametrize("location", ["root", "slice", "scenario", "registry", "entry", "obligations"])
@pytest.mark.parametrize("mutation", ["extra", "missing"])
def test_nested_closed_fields(location, mutation):
    inputs = load_inputs()
    target = {"root": inputs["matrix"], "slice": inputs["matrix"]["implementation_slices"][0],
              "scenario": inputs["matrix"]["scenarios"][0], "registry": inputs["registry"],
              "entry": inputs["registry"]["entries"][0], "obligations": inputs["obligations"]}[location]
    if mutation == "extra":
        target["extra"] = True
    else:
        del target[next(iter(target))]
    with pytest.raises(Invalid):
        validate_matrix(inputs["matrix"], inputs["catalog"], ROOT)
        validate_inventory(inputs["registry"], inputs["obligations"], inputs["protocol"], ROOT, inputs["matrix"]["scenarios"])


def test_paths_and_callables(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (root / "escape.json").symlink_to(outside)
    for path in ("../outside.json", str(outside), "escape.json", "absent.json", "a\\b", "./inside.json", ""):
        with pytest.raises(Invalid):
            path_in(root, path)
    with pytest.raises(Invalid):
        callable_ref(ROOT, "tests/phase_b/test_acceptance_foundation.py:missing_function")


def test_worktree_digest_includes_dirty_untracked_mode_and_excludes_cache(tmp_path):
    (tmp_path / "src").mkdir()
    source = tmp_path / "src/untracked.py"
    source.write_text("value = 1\n", encoding="utf-8")
    first = worktree_digest(tmp_path)
    source.write_text("value = 2\n", encoding="utf-8")
    second = worktree_digest(tmp_path)
    assert first != second
    source.chmod(0o755)
    third = worktree_digest(tmp_path)
    assert third != second
    cache = tmp_path / "src/__pycache__"
    cache.mkdir()
    (cache / "ignored.pyc").write_bytes(b"cache")
    assert worktree_digest(tmp_path) == third
    (tmp_path / "src/another.py").write_text("new = True\n", encoding="utf-8")
    assert worktree_digest(tmp_path) != third


def test_ownership_partition_and_future_owner_rejection():
    assert [len(v) for v in OWNED.values()] == [15, 11, 30, 28, 47]
    refs = [r for v in OWNED.values() for r in v]
    assert len(refs) == len(set(refs)) == 131 and set(refs) == set(required_ids(load_contracts()[1]))
    matrix = read(ROOT / "tests/phase_b/acceptance_matrix.json")
    matrix["implementation_slices"].append({"ticket_id": "B01", "owned_requirement_ids": sorted(OWNED["B02"])})
    with pytest.raises(Invalid):
        validate_matrix(matrix, load_contracts()[1], ROOT)


def _matrix_with_slices(tickets):
    matrix = read(ROOT / "tests/phase_b/acceptance_matrix.json")
    matrix["implementation_slices"] = [
        {"ticket_id": tid, "owned_requirement_ids": sorted(OWNED[tid])} for tid in tickets
    ]
    matrix["scenarios"] = [s for s in matrix["scenarios"]
                           if s["implementation_ticket_id"] == "B00" and s["validation_stage"] == "construction"]
    return matrix


@pytest.mark.parametrize("length", range(1, 6))
def test_canonical_slice_prefix_preserves_scenario_coverage(length):
    tickets = list(OWNED)[:length]
    matrix = _matrix_with_slices(tickets)
    catalog = load_contracts()[1]
    slices, covered = validate_matrix(matrix, catalog, ROOT)
    assert list(slices) == tickets
    assert slices == {tid: sorted(OWNED[tid]) for tid in tickets}
    assert covered == [rid for rid in required_ids(catalog) if rid in OWNED["B00"]]
    assert len(covered) == 15
    assert len(set(required_ids(catalog)) - set(covered)) == 116


@pytest.mark.parametrize("mutation", ["noncanonical", "duplicate", "missing", "unknown", "wrong_owner", "overlap"])
def test_canonical_slice_ownership_mutations_rejected(mutation):
    matrix = _matrix_with_slices(["B00", "B01"])
    catalog = load_contracts()[1]
    validate_matrix(matrix, catalog, ROOT)
    ids = matrix["implementation_slices"][1]["owned_requirement_ids"]
    if mutation == "noncanonical":
        ids.reverse()
    elif mutation == "duplicate":
        ids.append(ids[0])
        ids.sort()
    elif mutation == "missing":
        ids.pop()
    elif mutation == "unknown":
        ids[0] = "A99-UNKNOWN-001"
        ids.sort()
    elif mutation == "wrong_owner":
        ids[:] = sorted(OWNED["B02"])
    else:
        ids[0] = OWNED["B00"][0]
        ids.sort()
    with pytest.raises(Invalid) as exc:
        validate_matrix(matrix, catalog, ROOT)
    assert exc.value.error == {
        "category": "invalid_input", "object_id": "B01",
        "field_path": "ownership_overlap" if mutation == "overlap" else "owned_requirement_ids",
    }


@pytest.mark.parametrize("mutation", ["reversed", "gap", "duplicate", "b05"])
def test_canonical_slice_sequence_mutations_rejected(mutation):
    matrix = _matrix_with_slices(list(OWNED))
    catalog = load_contracts()[1]
    validate_matrix(matrix, catalog, ROOT)
    slices = matrix["implementation_slices"]
    if mutation == "reversed":
        slices.reverse()
    elif mutation == "gap":
        del slices[1]
    elif mutation == "duplicate":
        slices.append(deepcopy(slices[0]))
    else:
        slices.append({"ticket_id": "B05", "owned_requirement_ids": []})
    with pytest.raises(Invalid) as exc:
        validate_matrix(matrix, catalog, ROOT)
    assert exc.value.error["category"] == "invalid_input"
    assert exc.value.error["field_path"] == ("slice_order" if mutation in ("reversed", "gap") else "ticket_id")


def test_real_production_hook_source_observation(tmp_path):
    root = tmp_path / "hook-project"
    (root / "src/lqcd_agent").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src/lqcd_agent/__init__.py").write_text("", encoding="utf-8")
    (root / "src/lqcd_agent/boundary.py").write_text('''from harness.pytest_evidence import production_hook
from harness.meta_fixtures import meta_trace
def boundary():
    production_hook("case-one")
''', encoding="utf-8")
    (root / "tests/test_hook.py").write_text('''import pytest
from lqcd_agent.boundary import boundary
from harness.pytest_evidence import production_hook
from harness.strict_json import Invalid
from harness.meta_fixtures import meta_trace
def test_hook():
    boundary()
    with pytest.raises(Invalid):
        production_hook("test-only")
''', encoding="utf-8")
    session = session_for(root, tmp_path / "evidence")
    selection = ["tests/test_hook.py::test_hook"]
    result = run_pytest(session, selection)
    validate_pytest(result, session, selection)
    assert len(result["hook_events"]) == 1
    assert result["hook_events"][0]["hook_ref"] == "src/lqcd_agent/boundary.py:boundary"


def test_existing_evidence_directory_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "evidence"
    session_for(root, target)
    with pytest.raises(Invalid):
        session_for(root, target)


def test_stale_projection_and_contract_bytes_rejected(tmp_path):
    import shutil
    from harness.inputs import PATHS
    for relative in (PATHS["protocol"], PATHS["catalog"], PATHS["generated_protocol"], "scripts/generate_phase_b_protocol.py"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    generated = tmp_path / PATHS["generated_protocol"]
    generated.write_bytes(generated.read_bytes() + b"# Stale manual edit.\n")
    with pytest.raises(Invalid, match="projection:byte_equal"):
        load_inputs(tmp_path)
    protocol = tmp_path / PATHS["protocol"]
    protocol.write_bytes(b'{"malformed":NaN}')
    with pytest.raises(Invalid, match="protocol:sha256"):
        load_contracts(tmp_path)


def test_final_adapter_cannot_shrink_a_layer():
    from harness.exit_checks import Adapter, validate_adapter_targets
    inputs = load_inputs()
    with pytest.raises(Invalid, match="matrix_layer_selection"):
        validate_adapter_targets(inputs, None, {"layer_0": Adapter(lambda _: None, ("tests/x.py::test_fake",))})


def test_materialization_is_not_authorized_at_forbidden_boundaries():
    inputs = load_inputs()
    for entry in inputs["registry"]["entries"]:
        if entry["precondition"] in {"exact_replay_only", "lookup_only_after_uncertain_effect", "no_continuation_after_terminal"}:
            assert "materializable_publication_prefix" not in entry["allowed_exact_outcomes"]
        if entry["failpoint_id"].startswith("ingress.") or entry["failpoint_id"] in {
                "recovery.code_agent_rejected", "recovery.legacy_handoff_rejected"}:
            assert entry["allowed_exact_outcomes"] == ["integrity_conflict"]
