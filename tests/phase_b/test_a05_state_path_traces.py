"""Trace 0.5 binds Code paths only in registered state positions."""
from pathlib import Path
import pytest

from harness.strict_json import Invalid
from harness.trace import normalize
from helpers.a05_traces import rebind, state_projection_trace
from helpers.trace_sources import current_binding
from test_b03_task_trace_boundary import immutable_base


def normalized(trace):
    return normalize(trace, binding=current_binding())


@pytest.mark.parametrize("outcome", ["normal", "timeout"])
def test_canonical_paths_in_pointer_state_and_checkpoint_are_fresh_root_stable(outcome):
    base = immutable_base()
    first, _ = state_projection_trace(base, outcome=outcome, clock=100)
    second, _ = state_projection_trace(base, outcome=outcome, clock=200)
    assert normalized(first) == normalized(second)


@pytest.mark.parametrize("kind,path", [
    ("code_bundle", "code_agent_task_path"),
    ("bounded_state", "code_agent_result_path"),
    ("checkpoint_copy", "code_change_manifest_path"),
])
def test_wrong_or_foreign_canonical_path_rejected_after_source_rehash(kind, path):
    trace, _ = state_projection_trace()
    def mutate(value):
        target = (value["pointer"]["state_paths"] if kind == "code_bundle" else
                  value["channel_values"]["control"] if kind == "checkpoint_copy" else value)
        target[path] = "/private/tmp/foreign/attempts/attempt_000002/" + target[path].split("/")[-1]
    with pytest.raises(Invalid):
        normalized(rebind(trace, kind, mutate))


@pytest.mark.parametrize("kind", ["bounded_state", "checkpoint_copy"])
def test_state_scalar_must_match_validated_result(kind):
    trace, _ = state_projection_trace()
    def mutate(value):
        state = value["channel_values"]["control"] if kind == "checkpoint_copy" else value
        state["code_agent_usable"] = False
    with pytest.raises(Invalid):
        normalized(rebind(trace, kind, mutate))


def test_nested_same_name_material_remains_material():
    trace, _ = state_projection_trace()
    changed = rebind(trace, "bounded_state", lambda value: value.update(
        metadata={"code_agent_task_path": "first material value"}))
    other = rebind(trace, "bounded_state", lambda value: value.update(
        metadata={"code_agent_task_path": "second material value"}))
    assert normalized(changed) != normalized(other)


def test_symlinked_canonical_member_path_is_not_projected():
    trace, _ = state_projection_trace()
    bundle = next(row["value"] for row in trace["proof"]["objects"] if
                  row["value"].get("slot") == "code" and row["value"].get("event") == "registered")
    path = Path(bundle["pointer"]["state_paths"]["code_agent_task_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(path.parent / "different.json")
    with pytest.raises(Invalid):
        normalized(trace)
