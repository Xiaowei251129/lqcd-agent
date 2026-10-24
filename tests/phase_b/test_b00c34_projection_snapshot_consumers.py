"""Projection consumers retain strict public inputs and detached exact results."""
import json

import pytest

from lqcd_agent.artifacts.registry import ARTIFACT_SLOTS
from lqcd_agent.control.execution import ExecutionReplay, replay
from lqcd_agent.control.projections import _bounded_projection, bounded_projection
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes
from test_execution_0_4_foundation import bootstrap


@pytest.mark.parametrize("malformed", ["noncanonical", "boolean_index"])
def test_public_projection_rejects_malformed_later_snapshot(malformed):
    execution = replay(bootstrap().records)
    records = list(execution.records)
    if malformed == "noncanonical":
        records[1] += b" "
    else:
        value = json.loads(records[1])
        value["event_index"] = True
        records[1] = canonical_bytes(value)
    untrusted = ExecutionReplay(tuple(records), execution.projection)
    index = {"run_id": "run", "case_id": "case", "current": dict.fromkeys(ARTIFACT_SLOTS)}
    with pytest.raises(ControlIntegrityError):
        bounded_projection(untrusted, artifact_index=index, artifact_head=None, artifact_event_index=0)


def test_validated_projection_is_exact_and_detached():
    ledger = bootstrap()
    execution = replay(ledger.records)
    index = {"run_id": "run", "case_id": "case", "current": dict.fromkeys(ARTIFACT_SLOTS)}
    public = bounded_projection(execution, artifact_index=index, artifact_head=None, artifact_event_index=0)
    private = _bounded_projection(execution, ledger.root, artifact_index=index,
                                  artifact_head=None, artifact_event_index=0)
    assert private.canonical == public.canonical
    detached = private.value
    detached["current_artifacts"]["method_plan"] = {"changed": True}
    index["current"]["method_plan"] = {"changed": True}
    assert private.canonical == public.canonical
    assert private.value["current_artifacts"] == dict.fromkeys(ARTIFACT_SLOTS)
    assert execution.projection.value == replay(ledger.records).projection.value


def test_public_projection_requires_execution_replay():
    with pytest.raises(ControlIntegrityError, match="Missing execution replay"):
        bounded_projection(object(), artifact_index={}, artifact_head=None, artifact_event_index=0)
