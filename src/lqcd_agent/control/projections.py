"""Bounded projections and explicit checkpoint manifests, never authorities."""
from lqcd_agent.artifacts.contracts import ARTIFACT_SLOTS, STATE_FIELDS_BY_SLOT
from lqcd_agent.artifacts.registry import code_scalar_projection

from .execution import ExecutionReplay
from .strict_json import ValidatedValue, canonical_bytes, closed, digest, digest_value, number, require, text


def checkpoint_manifest(execution, *, artifact_head, artifact_event_index, checkpoint_id,
                        checkpoint_digest, state_digest):
    """Describe an already-produced checkpoint; this function never creates one."""
    require(type(execution) is ExecutionReplay, "Missing validated execution replay")
    value = execution.projection.value
    for item in (checkpoint_digest, state_digest):
        digest_value(item)
    digest_value(artifact_head, nullable=True)
    number(artifact_event_index, integer=True)
    require((artifact_head is None) == (artifact_event_index == 0), "Partial checkpoint artifact head")
    text(checkpoint_id)
    body = {"schema_version": "0.4", "run_id": value["run_id"], "case_id": value["case_id"],
            "checkpoint_thread_id": value["checkpoint_thread_id"], "checkpoint_id": checkpoint_id,
            "checkpoint_digest": checkpoint_digest, "state_digest": state_digest,
            "execution_head": value["execution_head"], "execution_event_index": value["execution_event_index"],
            "artifact_head": artifact_head, "artifact_event_index": artifact_event_index}
    return ValidatedValue.from_value({**body, "checkpoint_head": digest(body)})


def bounded_projection(execution, *, artifact_index, artifact_head, artifact_event_index):
    """Derive pre-checkpoint state. Registry validation remains in the A03 adapter."""
    require(type(execution) is ExecutionReplay, "Missing execution replay")
    return _bounded_projection(execution, execution.values[0]["canonical_output_root"],
                               artifact_index=artifact_index, artifact_head=artifact_head,
                               artifact_event_index=artifact_event_index)


def _bounded_projection(execution, canonical_output_root, *, artifact_index, artifact_head, artifact_event_index):
    closed(artifact_index["current"], ARTIFACT_SLOTS)
    value = execution.projection.value
    require(artifact_index["run_id"] == value["run_id"] and artifact_index["case_id"] == value["case_id"],
            "Projection belongs to another Run")
    value.update(artifact_head=artifact_head, artifact_event_index=artifact_event_index,
                 current_artifacts=artifact_index["current"])
    for slot in STATE_FIELDS_BY_SLOT:
        fields = STATE_FIELDS_BY_SLOT[slot]
        pointer = artifact_index["current"][slot]
        paths = pointer["state_paths"] if pointer is not None else {}
        for field in fields:
            value[field] = paths.get(field)
    value.update(code_scalar_projection(value, artifact_index, run_root=canonical_output_root))
    return ValidatedValue.from_value(value)


def attach_checkpoint(projection, execution, manifest):
    """Validate the non-self-referential checkpoint/state binding."""
    require(type(projection) is ValidatedValue, "Missing bounded projection")
    value = projection.value
    require(type(manifest) is dict, "Missing checkpoint manifest")
    expected = checkpoint_manifest(execution, artifact_head=value["artifact_head"],
                                   artifact_event_index=value["artifact_event_index"],
                                   checkpoint_id=manifest.get("checkpoint_id"),
                                   checkpoint_digest=manifest.get("checkpoint_digest"), state_digest=projection.digest)
    require(canonical_bytes(manifest) == expected.canonical, "Checkpoint head or pre-checkpoint projection mismatch")
    return ValidatedValue.from_value({**value, "checkpoint_head": manifest["checkpoint_head"]})


def validate_projection(actual, expected):
    require(type(expected) is ValidatedValue and canonical_bytes(actual) == expected.canonical,
            "Bounded projection is not the exact derived head")
    return expected
