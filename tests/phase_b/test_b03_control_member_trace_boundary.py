"""A03 member-digest witnesses, not canonical A05 or B03 runtime coverage."""
from dataclasses import replace
from unittest.mock import patch

import pytest

from harness.strict_json import Invalid
from harness.trace import normalize
from helpers.control_traces import fresh_external_trace
from helpers.trace_sources import current_binding
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.strict_json import canonical_bytes, digest
from test_external_consumption_control import ExternalDomainConsumer


def source_bound_member_trace():
    original = ExternalDomainConsumer.consume_external

    def consume(self, identity, binding, port):
        outcome = original(self, identity, binding, port)
        records = parse_ledger((self.root / "execution_history.jsonl").read_bytes()).values
        prestart = next(row for row in reversed(records) if row["record_type"] == "transition")
        # Only the mandatory source dependency is modeled, not a closed task.
        task = {**identity, "execution_head": digest(prestart), "requirements": ["unchanged material"]}
        task["task_digest"] = digest(task)
        member = port.write_member("code_agent_task.json", canonical_bytes(task))
        return replace(outcome, artifact=replace(outcome.artifact,
                                                member_paths=(*outcome.artifact.member_paths, member)))

    with patch.object(ExternalDomainConsumer, "consume_external", consume):
        return fresh_external_trace()


def registered_code(trace):
    return next(row for row in trace["proof"]["objects"] if
                row["value"].get("event") == "registered" and row["value"].get("slot") == "code")


def test_source_bound_member_normalizes_across_fresh_roots():
    first, second = source_bound_member_trace(), source_bound_member_trace()
    assert first["proof"]["output_roots"] != second["proof"]["output_roots"]
    assert first["events"] != second["events"]
    projected = [normalize(trace, binding=current_binding()) for trace in (first, second)]
    assert projected[0] == projected[1]
    members = []
    for trace in (first, second):
        registered = registered_code(trace)
        member = next(m for m in registered["value"]["members"] if m["logical_name"] == "code_agent_task.json")
        assert not any(ref["sha256"] == member["sha256"] for ref in registered["references"])
        members.append(member)
    assert members[0]["sha256"] != members[1]["sha256"]
    assert members[0]["size_bytes"] == members[1]["size_bytes"]


def test_source_bound_member_raw_tamper_is_still_rejected():
    trace = source_bound_member_trace()
    registered_code(trace)["value"]["members"][-1]["sha256"] = "0" * 64
    with pytest.raises(Invalid):
        normalize(trace, binding=current_binding())
