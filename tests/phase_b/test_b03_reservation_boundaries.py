"""Production initial producer crash probes, without B03 Backend acceptance credit.
"""
import multiprocessing
import os
import json
from pathlib import Path
import tempfile
from functools import partial

import pytest

from lqcd_agent.control.capabilities import InvocationLeases
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, TABLES
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.operations import AdvanceRunRequest, ExternalControl
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest
from harness.pytest_evidence import consume_process_hook, production_hook
from harness.trace import event
from test_advance_control import SyntheticDomainRoute
from test_invocation_artifacts import ArtifactTarget


def external_reservation_worker(pipe, output, locator, parent_operation_id, cut, hook_request=None):
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0))
    from lqcd_agent.code_agent.external_operation import ExternalProducer
    phases = {"before_insert": ("external.stub", "before"), "after_insert": ("external.stub", "after"),
              "before": ("external.external_operation_reserved", "before"), "after": ("external.external_operation_reserved", "after")}

    def observer(name, side, value):
        if (name, side) != phases[cut]:
            return
        row = coordinator.connection.execute("SELECT value FROM external_operations").fetchone()
        stub = value if row is None else json.loads(row[0])
        pipe.send({"producer_operation_id": stub["producer_operation_id"], "stub_digest": digest(stub),
                   "in_transaction": coordinator.connection.in_transaction, "row_visible_to_writer": row is not None})
        os._exit(93)

    if hook_request is not None:
        observer.production_hooks = {phases[cut]: (partial(production_hook, hook_request["case_id"],
                                                          process_request=hook_request),)}
    coordinator.observer = observer
    ExternalProducer(coordinator).reserve("capability_" + parent_operation_id, backend_kind="fake", backend_version="0.1",
                                          hard_deadline=20, worker_id="external-host", lease_seconds=30)
    raise AssertionError("The requested production boundary did not execute")


def first_external_reservation_durability(cut, hook_request=None, *, with_context=False):
    coordinator, locator, advanced = make_code_target()
    output = coordinator.root
    run = output / locator["case_id"] / locator["run_id"]
    rows = {name: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + name)] for name in TABLES}
    files = {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    coordinator.close()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=external_reservation_worker,
                              args=(child, str(output), locator, advanced["operation_id"], cut, hook_request))
    try:
        process.start()
        child.close()
        assert parent.poll(30), "External reservation worker did not reach its boundary"
        observation = parent.recv()
        process.join(20)
        assert process.exitcode == 93
        if hook_request is not None:
            consume_process_hook(hook_request, process, expected_exit=93)
        assert observation["in_transaction"] == (cut != "after")
        assert observation["row_visible_to_writer"] == (cut != "before_insert")
        reader, child_reader = context.Pipe()
        reader_process = context.Process(target=read_producer_worker,
            args=(child_reader, str(output), observation["producer_operation_id"]))
        try:
            reader_process.start()
            child_reader.close()
            assert reader.poll(30)
            durable = reader.recv()
            reader_process.join(20)
            assert reader_process.exitcode == 0 and durable["count"] == int(cut == "after")
            if durable["stub"] is not None:
                assert digest(durable["stub"]) == observation["stub_digest"]
        finally:
            if reader_process.is_alive():
                reader_process.kill()
                reader_process.join()
            reader.close()
        restarted = Coordinator(output, clock=FakeClock(140, 40))
        try:
            for name in TABLES:
                if name != "external_operations":
                    assert [tuple(row) for row in restarted.connection.execute("SELECT * FROM " + name)] == rows[name]
            assert {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob("*") if p.is_file()} == files
            assert restarted.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == int(cut == "after")
            if cut == "after":
                stub = ExternalControl(restarted).read(restarted.connection, observation["producer_operation_id"])
                assert digest(stub) == observation["stub_digest"]
                assert stub["operation_phase"] == "external_operation_reserved" and stub["lease_epoch"] == 1
            else:
                with pytest.raises(ControlIntegrityError, match="Unknown ExternalOperation"):
                    ExternalControl(restarted).read(restarted.connection, observation["producer_operation_id"])
                from lqcd_agent.code_agent.external_operation import ExternalProducer
                admitted = ExternalProducer(restarted).reserve(advanced["result"]["capability_id"], backend_kind="fake",
                    backend_version="0.1", hard_deadline=60, worker_id="new-host", lease_seconds=10)
                assert admitted["producer_operation_id"] != observation["producer_operation_id"]
                assert admitted["lease_epoch"] == 1 and admitted["task_digest"] is None
        finally:
            restarted.close()
        trace = {"schema_version": "0.1", "events": [
            event("external_reservation_cut", stage=cut,
                  outcome="committed_stub" if cut == "after" else "reservation_rolled_back",
                  started=False, accepted=cut == "after"),
            event("external_reservation_recovered", stage=cut,
                  outcome="original_stub" if cut == "after" else "fresh_request_readmission",
                  started=False, accepted=True)]}
        return (trace, str(output), observation["producer_operation_id"], locator) if with_context else trace
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()


@pytest.mark.parametrize("cut", ("before_insert", "after_insert", "before", "after"),
                         ids=("before-insert", "after-insert-before-commit", "before-commit", "after-commit"))
def test_first_external_reservation_durability(cut):
    first_external_reservation_durability(cut)


def make_code_target(*, worker_id="host"):
    output = Path(tempfile.mkdtemp(prefix="lqcd-agent-b03-reservation-", dir="/private/tmp"))
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    actor = ActorContext("operator", "human", ("control.internal", "start"))
    plane = ControlPlane(coordinator, worker_id=worker_id, route_adapter=SyntheticDomainRoute("code_agent"))
    inputs = {"root_goal": {"goal": "reservation audit"}, "input_snapshot": {"data": "synthetic"}}
    started = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start", "phase_b_test"), actor=actor)
    locator = started["result"]["run_locator"]
    run = output / locator["case_id"] / locator["run_id"]
    leases = InvocationLeases(coordinator)
    capability = started["result"]["capability_id"]
    leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=10)
    leases.invoke(capability, "consumer", 1, ArtifactTarget("plan", run))
    advanced = plane.advance_run(AdvanceRunRequest(locator, "attempt_000001", "code-target"), actor=actor)
    authorization = leases.get(advanced["result"]["capability_id"])[1]["authorization"]
    assert authorization["scope"] == "external_prestart_only"
    assert coordinator.get(advanced["operation_id"])["status"] == "committed"
    assert coordinator.get(advanced["operation_id"])["phase_revision"] == authorization["activation_result_revision"]
    return coordinator, locator, advanced


def read_producer_worker(pipe, output, producer):
    from lqcd_agent.code_agent.external_operation import ExternalProducer
    with_coordinator = Coordinator(Path(output), clock=FakeClock(140, 40))
    try:
        rows = with_coordinator.connection.execute("SELECT external_operation_id FROM external_operations").fetchall()
        pipe.send({"count": len(rows), "stub": ExternalProducer(with_coordinator).lookup(producer) if rows else None})
    finally:
        with_coordinator.close()
        pipe.close()


def competing_reservation(pipe, barrier, output, capability, version):
    from lqcd_agent.code_agent.external_operation import ExternalProducer
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0))
    try:
        barrier.wait(timeout=30)
        try:
            value = ExternalProducer(coordinator).reserve(capability, backend_kind="fake", backend_version=version,
                hard_deadline=20, worker_id="host-" + version, lease_seconds=10)
            pipe.send({"stub": value})
        except ControlIntegrityError as error:
            pipe.send({"conflict": str(error)})
    finally:
        coordinator.close()
        pipe.close()


@pytest.mark.parametrize("conflicting", [False, True], ids=["exact-clients", "conflicting-clients"])
def test_producer_two_processes_share_one_target(conflicting):
    coordinator, locator, advanced = make_code_target()
    output = coordinator.root
    run = output / locator["case_id"] / locator["run_id"]
    rows = {name: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + name)] for name in TABLES}
    files = {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    coordinator.close()
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(3)
    clients = []
    try:
        for version in ("0.1", "0.2" if conflicting else "0.1"):
            parent, child = context.Pipe()
            process = context.Process(target=competing_reservation,
                args=(child, barrier, str(output), advanced["result"]["capability_id"], version))
            process.start()
            child.close()
            clients.append((process, parent))
        barrier.wait(timeout=30)
        results = []
        for process, pipe in clients:
            assert pipe.poll(30)
            results.append(pipe.recv())
            process.join(20)
            assert process.exitcode == 0
        assert sum("conflict" in result for result in results) == int(conflicting)
        saved = [result["stub"] for result in results if "stub" in result]
        assert all(value == saved[0] for value in saved)
        restarted = Coordinator(output, clock=FakeClock(140, 40))
        try:
            assert restarted.connection.execute("SELECT count(*) FROM external_operations").fetchone()[0] == 1
            assert ExternalControl(restarted).read(restarted.connection, saved[0]["producer_operation_id"]) == saved[0]
            for name in TABLES:
                if name != "external_operations":
                    assert [tuple(row) for row in restarted.connection.execute("SELECT * FROM " + name)] == rows[name]
            assert {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob("*") if p.is_file()} == files
        finally:
            restarted.close()
    finally:
        for process, pipe in clients:
            if process.is_alive():
                process.kill()
                process.join()
            pipe.close()


@pytest.mark.parametrize("fault", ["scope", "parent", "closure", "head", "deadline"])
def test_producer_rejects_invalid_authority_without_mutation(fault):
    from lqcd_agent.code_agent.external_operation import ExternalProducer
    coordinator, locator, advanced = make_code_target()
    capability = advanced["result"]["capability_id"]
    run = coordinator.root / locator["case_id"] / locator["run_id"]
    try:
        if fault == "scope":
            revision, value = InvocationLeases(coordinator).get(capability)
            value["authorization"]["scope"] = "attempt_execution"
            value["authorization_digest"] = digest(value["authorization"])
            coordinator.connection.execute("UPDATE invocation_capabilities SET value=? WHERE capability_id=?", (canonical_bytes(value), capability))
        elif fault == "parent":
            coordinator.connection.execute("UPDATE control_operations SET status='in_progress' WHERE operation_id=?", (advanced["operation_id"],))
        elif fault == "closure":
            coordinator.connection.execute("INSERT INTO run_terminal_closure VALUES (?,?,?)", (digest(locator), 1, canonical_bytes({"test": "terminal owner"})))
        elif fault == "head":
            with (run / "execution_history.jsonl").open("ab") as stream:
                stream.write(b'{}\n')
        rows = {name: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + name)] for name in TABLES}
        files = {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob("*") if p.is_file()}
        with pytest.raises(ControlIntegrityError):
            ExternalProducer(coordinator).reserve(capability, backend_kind="fake", backend_version="0.1",
                hard_deadline=0 if fault == "deadline" else 20, worker_id="host", lease_seconds=10)
        assert {name: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + name)] for name in TABLES} == rows
        assert {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob("*") if p.is_file()} == files
    finally:
        coordinator.close()
