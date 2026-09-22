"""Complete source-bound trajectories supplement focused crash phase evidence."""
from contextlib import ExitStack
from itertools import count
import importlib
from unittest.mock import patch
import uuid

from helpers.construction_cases import check, fixture_value
from helpers.control_traces import ControlTrace
from lqcd_agent.control.coordinator import Coordinator


TRAJECTORIES = {
    "terminal": ("A04-PAUSE-015", check("invocation_artifacts", "real_registered_outputs_reach_end_then_unique_completed_closure")),
    "human": ("A02-HUMAN-001", check("human_control", "human_claim_then_allocate_consume_start_and_validate", "human_pause")),
    "timeout": ("A04-PAUSE-019", check("timeout_consumption_control", "safe_timeout_consumes_same_failed_attempt_before_outbound", "timeout_source")),
    "fork": ("A04-PAUSE-013", check("child_control", "child_bootstrap_reuses_admission_and_never_mutates_source", "child_control", fork=True)),
    "replay": ("A04-PAUSE-011", check("child_control", "child_bootstrap_reuses_admission_and_never_mutates_source", "child_control", fork=False)),
}


def source_trace(name):
    original_init, original_close = Coordinator.__init__, Coordinator.close
    captures, completed = {}, []
    identities = count(1)
    def initialize(coordinator, *args, **kwargs):
        original_init(coordinator, *args, **kwargs)
        assert coordinator.observer is None
        capture = ControlTrace(coordinator.root, version="0.4")
        captures[id(coordinator)] = capture
        coordinator.observer = capture.observer
    def close(coordinator):
        capture = captures.pop(id(coordinator))
        coordinator.observer = None
        completed.append(capture.finish(coordinator))
        original_close(coordinator)
    _, spec = TRAJECTORIES[name]
    with patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=next(identities))), patch.object(Coordinator, "__init__", initialize), patch.object(Coordinator, "close", close), ExitStack() as stack:
        arguments = dict(spec["arguments"])
        if spec["fixture"]:
            arguments[spec["fixture"]] = fixture_value(spec["fixture"], stack)
        getattr(importlib.import_module(spec["module"]), spec["function"])(**arguments)
    assert len(completed) == 1 and not captures
    return completed[0]
