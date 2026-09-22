"""All deterministic B02 resolution orderings with external/domain final inputs."""
import itertools
import multiprocessing

import pytest

from helpers.runtime_cases import run_files
from helpers.supplemental_cases import rows
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.pause import CancelPauseRequest, ResolveExternalInterruptRequest
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from test_external_control import SyntheticExternalStop, external_pause_request, external_source
from test_pause_control import control


ORDERINGS = tuple(itertools.permutations(("normal", "cancel", "interrupt")))


def resolution_client(pipe, root, locator, action):
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    adapter = SyntheticExternalStop(safe=True)
    plane = ControlPlane(coordinator, worker_id="resolver-" + action, external_adapter=adapter)
    actor = ActorContext("operator", "human", ("cancel", "control.internal", "resume", "start"))
    trigger = {"run_locator": locator, "producer_operation_id": "producer_code", "reason": "terminal_operator_stop"}
    def resolve():
        try:
            if action == "normal":
                # This is typed external/domain fixture input, not a B03 backend.
                with coordinator.transaction() as db:
                    value = ExternalControl(coordinator).read(db, "producer_code")
                    if value["resolution_owner"] is None:
                        assert db.execute("SELECT 1 FROM run_terminal_closure").fetchone() is None
                        value["resolution_owner"] = "normal"
                        adapter.publish(coordinator, db, value)
                    return {"kind": "external_domain_input", "winner": value["resolution_owner"]}
            if action == "cancel":
                result = plane.cancel_pause(CancelPauseRequest(locator, "pause_000001", "cancel", "operator_cancel"), actor=actor)
            else:
                result = plane.resolve_external_interrupt(ResolveExternalInterruptRequest(locator, "producer_code", trigger["reason"],
                    "order_trigger.json", digest(trigger)), actor=actor)
            return {"kind": "result", "result": result}
        except ControlIntegrityError as error:
            return {"kind": "rejected", "error": str(error)}
    try:
        pipe.send("ready")
        assert pipe.recv() == "go"
        pipe.send((resolve(), adapter.calls))
        assert pipe.recv() == "replay"
        pipe.send((resolve(), adapter.calls))
    finally:
        coordinator.close()
        pipe.close()


@pytest.mark.parametrize("ordering", ORDERINGS, ids=["-".join(order) for order in ORDERINGS])
def test_normal_cancel_interrupt_orderings_preserve_one_resolution_and_terminal_owner(control, ordering):
    coordinator, plane, actor, locator = control
    external_source(control)
    plane.publish_pause(external_pause_request(locator), actor=actor)
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    trigger = {"run_locator": locator, "producer_operation_id": "producer_code", "reason": "terminal_operator_stop"}
    (run / "order_trigger.json").write_bytes(canonical_bytes(trigger))
    context = multiprocessing.get_context("spawn")
    clients, results, calls = {}, {}, {}
    try:
        for action in ordering:
            parent, child = context.Pipe()
            process = context.Process(target=resolution_client, args=(child, str(coordinator.root), locator, action))
            process.start()
            child.close()
            clients[action] = (process, parent)
            assert parent.poll(30) and parent.recv() == "ready"
        for action in ordering:
            _, pipe = clients[action]
            pipe.send("go")
            assert pipe.poll(30)
            results[action], calls[action] = pipe.recv()
        value = ExternalControl(coordinator).read(coordinator.connection, "producer_code")
        assert value["resolution_owner"] == ordering[0]
        assert sum(calls.values()) == int(ordering[0] != "normal")
        closures = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM run_terminal_closure")]
        owners = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM pause_ownership")]
        assert len(closures) == len(owners) == 1
        assert closures[0]["terminal_closure"] == "committed" and closures[0]["run_status"] == "halted"
        assert closures[0]["terminal_closure_owner_operation_id"] == owners[0]["owner"]
        records = parse_ledger((run / "execution_history.jsonl").read_bytes()).values
        assert sum(r["record_type"] == "run_lifecycle" and r["to_status"] == "halted" for r in records) == 1
        assert sum(r["record_type"] == "budget" and r["event"] == "resource_settled" and
                   r["payload"]["resource_operation_id"] == value["reservation_id"] for r in records) == 1
        assert not any(r["record_type"] == "attempt" and r["attempt_id"] == value["attempt_id"] and r["event"] == "started" for r in records)
        frozen_rows, frozen_files = rows(coordinator), run_files(coordinator.root)
        for action in ordering:
            process, pipe = clients[action]
            pipe.send("replay")
            assert pipe.poll(30)
            replay, count = pipe.recv()
            assert count == calls[action]
            if results[action]["kind"] == "result":
                assert replay == results[action]
            process.join(20)
            assert process.exitcode == 0
        assert rows(coordinator) == frozen_rows and run_files(coordinator.root) == frozen_files
    finally:
        for process, pipe in clients.values():
            if process.is_alive():
                process.kill()
                process.join()
            pipe.close()
