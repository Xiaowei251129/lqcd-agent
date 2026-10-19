"""Fresh, validated B01 source snapshots for B00C01 semantic trace tests."""
from harness.temporary import mkdtemp
from copy import deepcopy
from contextvars import ContextVar
from pathlib import Path

from lqcd_agent.artifacts.registry import ARTIFACT_SLOTS
from lqcd_agent.control.execution import replay
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.projections import attach_checkpoint, bounded_projection, checkpoint_manifest
from lqcd_agent.control.strict_json import canonical_bytes, digest

from harness import pytest_evidence
from harness.contracts import DIGEST_KEYS
from harness.trace import event
from harness.trace_proof import source_object
from test_execution_0_4_foundation import bootstrap, POLICY, rechain


PROCESS_BINDING = ContextVar("phase_b_process_binding", default=None)


def current_binding():
    if pytest_evidence.ACTIVE:
        value = pytest_evidence.ACTIVE.value
        return {"invocation_token": value["invocation_token"], "digests": dict(value["digests"])}
    if PROCESS_BINDING.get() is not None:
        return deepcopy(PROCESS_BINDING.get())
    # This binding supports local unit checks only; a fresh acceptance Session
    # always rejects it, even if a caller copies these source objects verbatim.
    return {"invocation_token": "unit-only-not-acceptance", "digests": dict.fromkeys(DIGEST_KEYS, "0" * 64)}


def fresh_trace(*, time_offset=0, material_digest=None, binding=None):
    root = Path(mkdtemp(prefix="lqcd-agent-b00c01-", dir="/private/tmp"))
    records = deepcopy(bootstrap(root).records)
    for row in records:
        for key in ("created_at", "committed_at"):
            if key in row:
                row[key]["wall_seconds"] += time_offset
                row[key]["monotonic_seconds"] += time_offset
    if material_digest is not None:
        records[0]["root_goal_reference"]["sha256"] = material_digest
    records = rechain(records)
    execution = replay(records)
    index = {"schema_version": "0.1", "run_id": "run", "case_id": "case", "revision": 0, "last_event_id": None,
             "current": {slot: None for slot in ARTIFACT_SLOTS}, "managed_projections": {},
             "execution_head": execution.projection.value["execution_head"], "artifact_head": None}
    core = bounded_projection(execution, artifact_index=index, artifact_head=None, artifact_event_index=0)
    # This canonical checkpoint-shaped object demonstrates digest propagation.
    # It is not a durable LangGraph checkpoint or B02 runtime acceptance.
    payload = {"checkpoint_id": "checkpoint_1", "state_digest": core.digest, "state": core.value}
    manifest = checkpoint_manifest(execution, artifact_head=None, artifact_event_index=0, checkpoint_id="checkpoint_1",
                                   checkpoint_digest=digest(payload), state_digest=core.digest).value
    projection = attach_checkpoint(core, execution, manifest).value
    (root / "execution_history.jsonl").write_bytes(b"\n".join(execution.records) + b"\n")
    (root / "artifact_history.jsonl").write_bytes(b"")
    (root / "artifact_index.json").write_bytes(canonical_bytes(index))
    (root / "budget_policy.json").write_bytes(canonical_bytes(POLICY))
    validate_run_root(root, manifest=manifest, projection=projection)
    objects = [source_object("execution_0_4", row) for row in records]
    objects += [source_object("canonical_json", core.value), source_object("canonical_json", payload),
                source_object("checkpoint_manifest", manifest)]
    proof = {"schema_version": "0.1", "binding": binding or current_binding(), "objects": objects,
             "output_roots": [{"case_id": "case", "run_id": "run", "path": str(root)}]}
    events = []
    for row in records:
        state = replay(records[:row["event_index"]]).projection.value
        events.append(event(row["record_type"] + ":" + row["event"], run_id=row["run_id"],
                            cycle_id=row.get("cycle_id"), attempt_id=row.get("attempt_id"),
                            transition_id=row.get("transition_id"), operation_id=row.get("operation_id"),
                            physical_node=row.get("node_name"), attempt_kind=row.get("attempt_kind"),
                            index=row["event_index"], execution_head=digest(row), artifact_head=row["artifact_head"],
                            run_status=state["run_status"], current_attempt_id=state["attempt_id"],
                            cycle_count=state["cycle_index"], attempt_count=state["attempt_index"],
                            transition_count=state["transition_index"], outcome="validated", owner="construction_replay",
                            ephemeral={"output_root": str(root), "timestamp": row["created_at"]["wall_seconds"]}))
    events.append(event("checkpoint_bound", run_id="run", execution_head=projection["execution_head"],
                        checkpoint_head=manifest["checkpoint_head"], run_status="running", outcome="validated",
                        owner="construction_replay"))
    return {"schema_version": "0.2", "representation": "raw_with_proof", "events": events, "proof": proof}
