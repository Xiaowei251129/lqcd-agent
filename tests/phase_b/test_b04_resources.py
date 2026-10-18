"""Ordinary calls use the invocation fence and the authoritative budget ledger."""
from pathlib import Path
import tempfile

import pytest

from lqcd_agent.control.budget import BudgetExhausted
from lqcd_agent.control.capabilities import ArtifactEffectPort, InvocationLeases, TargetOutcome
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from test_bootstrap_control import start


@pytest.mark.parametrize("kind", ["llm_call", "tool_call"])
def test_resource_reserves_before_effect_and_settles_trusted_duration(kind):
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-resource-", dir="/private/tmp"))
    coordinator, _, source = start(output)
    locator = source["result"]["run_locator"]
    root = output / locator["case_id"] / locator["run_id"]
    leases = InvocationLeases(coordinator)
    capability = source["result"]["capability_id"]
    calls = []

    class Target:
        def invoke_scoped(self, identity, port):
            def effect():
                records = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
                assert records[-1]["event"] == "resource_reserved"
                calls.append(identity["attempt_id"])
                coordinator.clock.advance(2)
                return {"output": "bounded"}
            result = port.run_resource(resource_kind=kind, resource_id="call-1", input_digest=digest("input"),
                config_digest=digest("config"), timeout_seconds=3, effect=effect)
            assert result == {"output": "bounded"}
            return TargetOutcome("succeeded", {"current_artifact_ids": {}})

    try:
        leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
        state = leases.invoke(capability, "consumer", 1, Target())
        assert calls == ["attempt_000001"] and state["attempt_status"] == "succeeded"
        dimensions = state["budget"]["dimensions"]
        assert dimensions["active_seconds_per_run"]["used"] == 2
        assert dimensions[("llm_calls" if kind == "llm_call" else "tool_calls") + "_per_run"]["used"] == 1
        rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
        settlement = next(row["payload"] for row in rows if row["event"] == "resource_settled")
        assert settlement["tokens"] == settlement["cost"] == {"state": "unknown", "value": None}
        with pytest.raises(ControlIntegrityError):
            leases.invoke(capability, "consumer", 1, Target())
        assert len(calls) == 1
    finally:
        coordinator.close()


def test_resource_reuse_exhaustion_and_foreign_suffix_have_no_new_effect():
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-resource-negative-", dir="/private/tmp"))
    coordinator, _, source = start(output)
    capability = source["result"]["capability_id"]
    leases = InvocationLeases(coordinator)
    calls = []
    try:
        leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
        leases.start_intent(capability, "consumer", 1)
        leases.publish_started(capability, "consumer", 1)
        port = ArtifactEffectPort(leases, None, capability, "consumer", 1)
        request = dict(resource_kind="tool_call", resource_id="call-1", input_digest=digest("input"),
                       config_digest=digest("config"), timeout_seconds=1, effect=lambda: calls.append("effect") or {})
        port.run_resource(**request)
        with pytest.raises(ControlIntegrityError, match="redispatched"):
            port.run_resource(**request)
        with pytest.raises(BudgetExhausted):
            port.run_resource(**{**request, "resource_id": "too-large", "timeout_seconds": 31})
        assert calls == ["effect"]
        with coordinator.transaction() as db:
            revision, value = leases.get(capability, db=db)
            value["budget_intents"][0]["record"]["run_id"] = "foreign"
            leases._save(db, capability, revision, value)
        with pytest.raises(ControlIntegrityError):
            port.run_resource(**{**request, "resource_id": "tampered"})
        assert calls == ["effect"]
    finally:
        coordinator.close()


def test_uncertain_resource_retains_maximum_and_cannot_reexecute():
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b04-resource-uncertain-", dir="/private/tmp"))
    coordinator, _, source = start(output)
    leases = InvocationLeases(coordinator)
    capability = source["result"]["capability_id"]
    try:
        leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
        leases.start_intent(capability, "consumer", 1)
        leases.publish_started(capability, "consumer", 1)
        port = ArtifactEffectPort(leases, None, capability, "consumer", 1)
        def effect():
            raise RuntimeError("Uncertain provider completion")
        with pytest.raises(RuntimeError):
            port.run_resource(resource_kind="llm_call", resource_id="uncertain", input_digest=digest("input"),
                config_digest=digest("config"), timeout_seconds=4, effect=effect)
        locator = source["result"]["run_locator"]
        root = output / locator["case_id"] / locator["run_id"]
        dimensions = parse_ledger((root / "execution_history.jsonl").read_bytes()).projection.value["budget"]["dimensions"]
        assert dimensions["active_seconds_per_run"]["used"] == 4 and dimensions["llm_calls_per_run"]["used"] == 1
        with pytest.raises(ControlIntegrityError, match="Uncertain resource"):
            port.run_resource(resource_kind="llm_call", resource_id="replacement", input_digest=digest("input"),
                config_digest=digest("config"), timeout_seconds=1, effect=lambda: {})
    finally:
        coordinator.close()
