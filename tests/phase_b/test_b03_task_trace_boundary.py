"""Contract witnesses for the A05 digest boundary, not canonical B03 coverage.

The Run, registered plan, Code target and initial producer are production
outputs. Task/manifest values are contract-shaped fixtures; the reservation
uses the production record builder/replayer without publishing a new phase.
"""
from copy import deepcopy
import hashlib
from itertools import count
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
import uuid

import pytest

from harness.strict_json import Invalid
from harness.trace import event, normalize
from harness.trace_proof import reference_paths, source_object
from helpers.control_traces import ControlTrace
from helpers.trace_sources import current_binding
from lqcd_agent.code_agent.external_operation import ExternalProducer
from lqcd_agent.control.execution import parse_ledger, replay
from lqcd_agent.control.pause import runtime_fingerprint
from lqcd_agent.control.records import build_record
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
from test_b03_reservation_boundaries import make_code_target


def immutable_base():
    root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-trace-base-", dir="/private/tmp"))
    content = b"def value():\n    return 1\n"
    (root / "sample.py").write_bytes(content)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
    git("init", "-q")
    git("add", "sample.py")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "-qm", "Immutable trace fixture")
    return {"base_revision": git("rev-parse", "HEAD"),
            "base_tree_digest": digest({"sample.py": hashlib.sha256(content).hexdigest()})}


def task_trace_witness(base, *, requirement="Return the fixture value"):
    identities = count(1)
    with patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=next(identities))):
        coordinator, locator, advanced = make_code_target()
        try:
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            captured = ControlTrace(coordinator.root, version="0.4")
            captured.observer("invocation.attempt_started", "after", {})
            baseline = captured.finish(coordinator)
            producer = ExternalProducer(coordinator).reserve(advanced["result"]["capability_id"],
                backend_kind="fake", backend_version="0.1", hard_deadline=20, worker_id="host", lease_seconds=10)
            records = list(parse_ledger((root / "execution_history.jsonl").read_bytes()).values)
            index = loads((root / "artifact_index.json").read_bytes())
            transition = records[-1]
            assert transition["target_attempt_kind"] == "code_agent" and transition["event"] == "committed"
            decision = [r for r in records if r["record_type"] == "budget" and r["event"] == "decision_recorded"][-1]
            assert decision["payload"]["decision"] == "allow" and decision["payload"]["target_kind"] == "code_agent"
            policy = loads((root / "budget_policy.json").read_bytes())
            plan = index["current"]["plan"]
            evidence = [{"artifact_id": plan["artifact_id"], "path": m["canonical_path"], "sha256": m["sha256"]}
                        for m in plan["members"] if m["logical_name"] == "method_plan.json"]
            assert len(evidence) == 1
            assert hashlib.sha256((root / evidence[0]["path"]).read_bytes()).hexdigest() == evidence[0]["sha256"]
            identity = {**locator, "cycle_id": transition["target_cycle_id"], "attempt_id": transition["target_attempt_id"],
                        "transition_id": transition["transition_id"], "producer_operation_id": producer["producer_operation_id"]}
            spec = {"spec_id": "fixture-check", "argv": ["python", "-m", "compileall", "sample.py"], "cwd": ".",
                    "timeout_seconds": 1, "required": True, "expected_exit_codes": [0], "environment_keys": []}
            task = {**identity, **base, "schema_version": "0.1", "task_id": identity["attempt_id"] + ":code_task",
                "source_attempt_id": transition["source_attempt_id"], "attempt_kind": "code_agent", "node_name": "code_agent",
                "task_origin": "planner_gap", "task_summary": "Check the fixture", "requirements": [requirement],
                "acceptance_criteria": ["Required verification passes"], "evidence": evidence,
                "execution_head": digest(records[-1]), "artifact_head": index["artifact_head"],
                "source_runtime_fingerprint": runtime_fingerprint(),
                "read_paths": ["sample.py"], "write_paths": ["sample.py"], "forbidden_paths": [".git"],
                "tool_policy": [spec], "network_policy": {"enabled": False},
                "filesystem_policy": {"binary_changes": False, "executable_changes": False, "ephemeral_paths": ["__pycache__"]},
                "verification_specs": [spec], "budget_policy_version": policy["schema_version"],
                "budget_profile_id": policy["profile_id"], "budget_policy_digest": policy["policy_digest"],
                "budget_envelope_ref": {"path": "execution_history.jsonl", "event_id": decision["event_id"]},
                "budget_envelope_digest": digest(decision), "human_authorization_ref": None,
                "coding_backend_kind": "fake", "backend_version": "0.1", "backend_runtime_fingerprint": digest("fake-0.1"),
                "external_producer_contract": {"schema_version": "0.1", "parent_control_operation_id": advanced["operation_id"]},
                "expected_result_schema": "0.1"}
            task["task_digest"] = digest(task)
            policy_names = ("read_paths", "write_paths", "forbidden_paths", "tool_policy", "network_policy", "filesystem_policy")
            manifest = {**identity, **base, "schema_version": "0.1", "workspace_id": producer["workspace_id"],
                "workspace_generation": 1, "task_id": task["task_id"], "task_digest": task["task_digest"],
                "source_runtime_fingerprint": task["source_runtime_fingerprint"], "coding_backend_kind": "fake",
                "backend_version": "0.1", "backend_runtime_fingerprint": task["backend_runtime_fingerprint"],
                "workspace_implementation": "deterministic_fixture", "policy_digests": {k: digest(task[k]) for k in policy_names},
                "created_at": 100, "owner": "host", "managed_root_identity": producer["managed_workspace_locator_digest"]}
            manifest["manifest_digest"] = digest(manifest)
            limits = {"llm_calls": 2, "tool_calls": 4, "verification_commands": 2, "active_seconds": 30}
            payload = {"resource_operation_id": "resource_code", "resource_kind": "code_backend_operation",
                "attempt_id": task["attempt_id"], "ordinal": 1,
                "maximum_charge": {"llm_calls": 1, "tool_calls": 1, "verification_commands": 0, "active_seconds": 10},
                "applicable_limits": limits, "remaining_before": limits, "timeout_seconds": 10,
                "input_digest": task["task_digest"], "task_digest": task["task_digest"], "config_digest": digest("config"),
                "producer_operation_id": producer["producer_operation_id"], "workspace_id": producer["workspace_id"],
                "task_id": task["task_id"], "code_task_context_digest": digest({"requirement": requirement, **base}),
                "coding_backend_kind": "fake", "backend_runtime_fingerprint": task["backend_runtime_fingerprint"],
                "workspace_manifest_digest": manifest["manifest_digest"]}
            reservation = build_record("budget", "resource_reserved", **locator, event_index=len(records) + 1,
                previous_execution_head=digest(records[-1]), artifact_head=index["artifact_head"], artifact_event_index=index["revision"],
                timestamp=coordinator._time(), budget_event_id="budget_event_000004", budget_event_index=4,
                policy_version=policy["schema_version"], policy_digest=policy["policy_digest"], payload=payload).value
            replay([*records, reservation])
            trace = deepcopy(baseline)
            trace["proof"]["objects"].append(source_object("execution_0_4", reservation, version="0.4"))
            trace["events"].append(event("budget:resource_reserved", run_id=locator["run_id"], execution_head=digest(reservation),
                artifact_head=index["artifact_head"], attempt_id=task["attempt_id"], owner="contract_witness",
                outcome="validated_record_only"))
            assert producer["task_digest"] is None and producer["operation_phase"] == "external_operation_reserved"
            assert (root / "execution_history.jsonl").read_bytes() == b"".join(canonical_bytes(r) + b"\n" for r in records)
            return {"baseline": baseline, "task": task, "manifest": manifest, "reservation": reservation, "trace": trace}
        finally:
            coordinator.close()


def normalized(value):
    return normalize(value, binding=current_binding())


def test_trace_0_4_keeps_root_dependent_a05_reservation_digests():
    base = immutable_base()
    first, second = [task_trace_witness(base) for _ in range(2)]
    assert normalized(first["baseline"]) == normalized(second["baseline"])
    assert first["task"]["execution_head"] != second["task"]["execution_head"]
    assert {k for k in first["task"] if first["task"][k] != second["task"][k]} == {
        "execution_head", "artifact_head", "budget_envelope_digest", "task_digest"}
    assert first["task"]["task_digest"] != second["task"]["task_digest"]
    assert first["manifest"]["manifest_digest"] != second["manifest"]["manifest_digest"]
    refs = reference_paths(first["reservation"], kind="execution_0_4", version="0.4")
    assert not any(path[0] == "payload" for path, _ in refs)
    assert normalized(first["trace"]) != normalized(second["trace"])


def test_trace_0_4_rejects_tampered_raw_reservation():
    witness = task_trace_witness(immutable_base())
    trace = deepcopy(witness["trace"])
    trace["proof"]["objects"][-1]["value"]["payload"]["task_digest"] = digest("forged")
    with pytest.raises(Invalid):
        normalized(trace)


def test_trace_0_4_preserves_changed_task_material():
    witness = task_trace_witness(immutable_base())
    task = deepcopy(witness["task"])
    task["requirements"] = ["Return a different fixture value"]
    task["task_digest"] = digest({k: v for k, v in task.items() if k != "task_digest"})
    manifest = deepcopy(witness["manifest"])
    manifest["task_digest"] = task["task_digest"]
    manifest["manifest_digest"] = digest({k: v for k, v in manifest.items() if k != "manifest_digest"})
    reservation = deepcopy(witness["reservation"])
    reservation["payload"].update(task_digest=task["task_digest"], input_digest=task["task_digest"],
        workspace_manifest_digest=manifest["manifest_digest"], code_task_context_digest=digest("changed context"))
    changed = deepcopy(witness["trace"])
    changed["proof"]["objects"][-1] = source_object("execution_0_4", reservation, version="0.4")
    changed["events"][-1]["execution_head"] = digest(reservation)
    assert normalized(witness["trace"]) != normalized(changed)
