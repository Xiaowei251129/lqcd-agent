"""Async SDK calls retain the same real Host fences and resource accounting."""
import asyncio
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pytest

from lqcd_agent.control.budget import (
    BudgetExhausted, async_run_resource, resource_scope, run_resource, settle_resource_failure,
)
from lqcd_agent.control.capabilities import ArtifactEffectPort, InvocationLeases
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.storage import execution_scratch_root
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from tests.support import mkdtemp


@pytest.fixture
def resource_host():
    root = Path(mkdtemp(prefix="lqcd-async-resource-", dir=execution_scratch_root()))
    clock = FakeClock(100, 0)
    with closing(Coordinator(root, clock=clock)) as coordinator:
        actor = ActorContext("operator", "human", ("start",))
        plane = ControlPlane(coordinator, worker_id="worker")
        inputs = {"root_goal": {"goal": "Check a scientific estimate"},
                  "input_snapshot": {"kind": "resource-test"}}
        result = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start",
                                                profile_id="phase_b_test"), actor=actor)
        locator = result["result"]["run_locator"]
        capability = coordinator.connection.execute("SELECT capability_id FROM invocation_capabilities").fetchone()[0]
        leases = InvocationLeases(coordinator)
        leased = leases.acquire(capability, "worker", expected_epoch=0, lease_seconds=30)
        epoch = leased["invocation_epoch"]
        leases.start_intent(capability, "worker", epoch)
        leases.publish_started(capability, "worker", epoch)
        port = ArtifactEffectPort(leases, None, capability, "worker", epoch)
        yield port, clock, root / locator["case_id"] / locator["run_id"]


def request(resource_id, kind="llm_call", timeout=5):
    return {"resource_kind": kind, "resource_id": resource_id,
            "input_digest": digest({"input": resource_id}), "config_digest": digest({"model": "fixture"}),
            "timeout_seconds": timeout}


def ledger(root):
    return parse_ledger((root / "execution_history.jsonl").read_bytes())


def events(root, event):
    return [row["payload"] for row in ledger(root).values if row.get("event") == event]


def test_async_result_keeps_sdk_object_and_records_real_usage(resource_host):
    port, clock, root = resource_host

    @dataclass
    class SDKResult:
        answer: str
        tokens: int

    expected = SDKResult("Inspect the covariance", 17)

    async def effect():
        assert len(events(root, "resource_reserved")) == 1
        assert not events(root, "resource_settled")
        await asyncio.sleep(0)
        clock.advance(2)
        return expected

    result = asyncio.run(async_run_resource(port, **request("model-1"), effect=effect,
        evidence=lambda value: {"answer": value.answer}, tokens=lambda value: value.tokens))
    assert result is expected
    settled, = events(root, "resource_settled")
    assert settled["actual"]["llm_calls"] == 1 and settled["actual"]["active_seconds"] == 2
    assert settled["tokens"] == {"state": "known", "value": 17}
    assert settled["cost"] == {"state": "unknown", "value": None}
    assert settled["evidence_digest"] == digest({"answer": expected.answer})
    assert run_resource(port, **request("read-1", "tool_call"), effect=lambda: {"rows": 4}) == {"rows": 4}
    state = ledger(root).projection.value["budget"]["dimensions"]
    assert state["llm_calls_per_attempt"]["used"] == 1
    assert state["tool_calls_per_attempt"]["used"] == 1


def test_async_budget_denial_does_not_call_model(resource_host):
    port, _, root = resource_host
    called = []

    async def effect():
        called.append(True)
        return {"answer": "evidence"}

    async def calls():
        for index in range(2):
            await async_run_resource(port, **request(f"model-{index}"), effect=effect)
        with pytest.raises(BudgetExhausted):
            await async_run_resource(port, **request("model-denied"), effect=effect)

    asyncio.run(calls())
    assert len(called) == 2 and len(events(root, "resource_reserved")) == 2


def test_cancellation_retains_maximum_and_cannot_redispatch(resource_host):
    port, _, root = resource_host
    entered = asyncio.Event()
    returned = []

    async def effect():
        entered.set()
        await asyncio.Event().wait()
        returned.append(True)

    async def cancel():
        task = asyncio.create_task(async_run_resource(port, **request("cancelled"), effect=effect))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert not returned and not events(root, "resource_settled")
    assert ledger(root).projection.value["budget"]["dimensions"]["active_seconds_per_attempt"]["used"] == 5
    called = []
    with pytest.raises(ControlIntegrityError, match="Uncertain resource"):
        run_resource(port, **request("replacement"), effect=lambda: called.append(True))
    settle_resource_failure(port, resource_id="cancelled", error=asyncio.CancelledError())
    settled, = events(root, "resource_settled")
    assert settled["actual"] is None and settled["tokens"]["state"] == "unknown"
    with pytest.raises(ControlIntegrityError, match="redispatched"):
        run_resource(port, **request("cancelled"), effect=lambda: called.append(True))
    with pytest.raises(ControlIntegrityError, match="single unsettled"):
        settle_resource_failure(port, resource_id="cancelled", error=RuntimeError("again"))
    assert not called
    run_resource(port, **request("next"), effect=lambda: {"complete": True})
    assert len(events(root, "resource_reserved")) == 2


def test_scope_cannot_settle_after_exit_or_twice(resource_host):
    port, _, root = resource_host
    with resource_scope(port, **request("finished")) as finish:
        assert finish({"ok": True}, tokens=3) == {"ok": True}
        with pytest.raises(ControlIntegrityError, match="already used"):
            finish({"ok": False})
    with pytest.raises(ControlIntegrityError, match="closed"):
        finish({"ok": False})
    with resource_scope(port, **request("unfinished")) as unfinished:
        pass
    with pytest.raises(ControlIntegrityError, match="closed"):
        unfinished({"ok": True})
    assert len(events(root, "resource_reserved")) == 2
    assert len(events(root, "resource_settled")) == 1
    settle_resource_failure(port, resource_id="unfinished", error=RuntimeError("effect ended without output"))


def test_async_untrusted_duration_cannot_become_success(resource_host):
    port, clock, root = resource_host

    async def effect():
        clock.advance(3)
        return {"answer": "late"}

    with pytest.raises(ControlIntegrityError, match="duration"):
        asyncio.run(async_run_resource(port, **request("late", timeout=2), effect=effect))
    assert not events(root, "resource_settled")
    settle_resource_failure(port, resource_id="late", error=TimeoutError("late result"))
    assert events(root, "resource_settled")[0]["actual"] is None
