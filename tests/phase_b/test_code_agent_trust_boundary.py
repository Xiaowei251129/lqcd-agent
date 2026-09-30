"""Canonical input validation; schema checks alone earn no runtime coverage."""
from copy import deepcopy

import pytest

from harness.pytest_evidence import observe
from lqcd_agent.code_agent.schemas import relative_path, task_context, validate_manifest, validate_task
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest
from test_b03_task_trace_boundary import immutable_base, task_trace_witness


@pytest.fixture(scope="module")
def canonical_inputs():
    witness = task_trace_witness(immutable_base())
    return witness["task"], witness["manifest"]


def checksum(value, name):
    value[name] = digest({k: v for k, v in value.items() if k != name})
    return value


def test_task_manifest_accept_real_source_identity_and_detach_inputs(canonical_inputs):
    task, manifest = deepcopy(canonical_inputs)
    validated = validate_task(task)
    assert validate_manifest(manifest, task).value == manifest
    task["task_summary"] = "Mutated caller object"
    assert validated.value != task
    assert validate_task(validated.canonical).canonical == validated.canonical
    observe("b03-construction-closed-identities", {"kind": "boolean", "value": True},
            sorted(["strict_task_and_manifest", "detached_inputs", "canonical_identity"]))


def test_task_context_keeps_material_inputs_without_execution_identity(canonical_inputs):
    task = deepcopy(canonical_inputs[0])
    original = task_context(task)
    task.update(attempt_id="attempt_000099", task_id="attempt_000099:code_task", producer_operation_id="other_producer",
                task_summary="Different advice", execution_head=digest("new head"))
    task["evidence"][0]["artifact_id"] = "other_plan"
    task["evidence"][0]["path"] = "attempts/attempt_000098/method_plan.json"
    checksum(task, "task_digest")
    assert task_context(task) == original
    task["requirements"] = ["Different material requirement"]
    checksum(task, "task_digest")
    assert task_context(task) != original


@pytest.mark.parametrize("path", ["", "/tmp/a", "../a", "a/../b", "a//b", "a/./b", "a/", "a\\b", "C:/a", "a\x00b"])
def test_noncanonical_paths_are_rejected_before_filesystem_access(path):
    with pytest.raises(ControlIntegrityError):
        relative_path(path)


@pytest.mark.parametrize("case", ["extra", "missing_nullable", "legacy", "mutable_base", "network", "scope", "case_alias",
    "ephemeral_forbidden", "ephemeral_parent", "duplicate_spec", "no_required", "free_shell", "budget_authority", "manifest_policy",
    "manifest_attempt", "manifest_digest", "duplicate_key"])
def test_closed_input_and_policy_reject_even_rehashed_candidates(canonical_inputs, case):
    task, manifest = deepcopy(canonical_inputs)
    if case == "extra":
        task["backend_selected_outcome"] = "success"
    elif case == "missing_nullable":
        del task["human_authorization_ref"]
    elif case == "legacy":
        task["attempt_kind"] = "legacy_codex_handoff"
    elif case == "mutable_base":
        task["base_revision"] = "HEAD"
    elif case == "network":
        task["network_policy"]["enabled"] = True
    elif case == "scope":
        task["write_paths"] = ["accepted/result.json"]
    elif case == "case_alias":
        task["write_paths"] = ["sample.py", "Sample.py"]
    elif case == "ephemeral_forbidden":
        task["filesystem_policy"]["ephemeral_paths"] = [".git/cache"]
    elif case == "ephemeral_parent":
        task["forbidden_paths"].append("temp/private")
        task["filesystem_policy"]["ephemeral_paths"] = ["temp"]
    elif case == "duplicate_spec":
        task["verification_specs"] *= 2
    elif case == "no_required":
        task["verification_specs"][0]["required"] = False
    elif case == "free_shell":
        task["verification_specs"][0]["argv"] = "python sample.py; touch elsewhere"
    elif case == "budget_authority":
        task["budget_envelope_ref"]["path"] = "backend-budget.json"
    elif case == "manifest_policy":
        manifest["policy_digests"]["write_paths"] = digest(["another.py"])
    elif case == "manifest_attempt":
        manifest["attempt_id"] = "attempt_000099"
    elif case == "manifest_digest":
        manifest["manifest_digest"] = digest("bad")
    else:
        raw = canonical_bytes(task)
        with pytest.raises(ControlIntegrityError, match="Duplicate"):
            validate_task(b'{"schema_version":"0.1",' + raw[1:])
        return
    checksum(task, "task_digest")
    if case != "manifest_digest":
        checksum(manifest, "manifest_digest")
    with pytest.raises(ControlIntegrityError):
        if case.startswith("manifest_"):
            validate_manifest(manifest, task)
        else:
            validate_task(task)
    if case == "legacy":
        observe("b03-construction-legacy-rejection", {"kind": "boolean", "value": True},
                sorted(["legacy_attempt_kind_rejected", "no_canonical_conversion"]))
