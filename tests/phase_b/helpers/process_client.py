"""Deterministically synchronized fresh interpreters for B02 storage tests.

These workers exercise coordinator primitives, not completed control APIs or
Phase B runtime acceptance. They never invoke providers or product nodes.
"""
import os
from pathlib import Path

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, exclusive_directory
from lqcd_agent.control.strict_json import ControlIntegrityError


def reservation_client(pipe, root, overlay, payload):
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    try:
        pipe.send("ready")
        assert pipe.recv() == "go"
        try:
            result = coordinator.reserve("start_run", "not_applicable", "scope", "key", payload,
                                         "worker", lambda *_: overlay, lease_seconds=10)
            pipe.send(("reserved", result))
        except ControlIntegrityError as error:
            pipe.send(("rejected", str(error)))
    finally:
        coordinator.close()
        pipe.close()


def publication_client(pipe, root, overlay, crash):
    def observer(name, side, value):
        if crash and (name, side) == ("bootstrap.policy.file_sync", "after"):
            os._exit(83)

    coordinator = Coordinator(root, clock=FakeClock(110, 10) if not crash else FakeClock(100, 0),
                              observer=observer)
    try:
        if crash:
            operation = coordinator.reserve("start_run", "not_applicable", "scope", "key", {}, "worker",
                                            lambda *_: overlay, lease_seconds=10)
        else:
            operation = coordinator.lookup_key("scope", "key")
            operation = coordinator.acquire(operation["operation_id"], "restarted", lease_seconds=10)
        locator = operation["reservation"]["reserved_run_locator"]
        run_root = Path(root) / locator["case_id"] / locator["run_id"]

        def advance(phase, publish):
            return coordinator.step(operation["operation_id"], operation["worker_owner_id"],
                                    operation["lease_epoch"], operation["phase_revision"], phase, publish)

        if crash:
            def create(db, current):
                exclusive_directory(run_root.parent)
                exclusive_directory(run_root)
                return {"reserved_run_locator": locator, "current_lease_epoch": current["lease_epoch"]}

            operation = advance("run_root_created", create)
            coordinator.freeze_publication(operation["operation_id"], "worker", 1, 2, "policy_published",
                                           run_root / "budget_policy.json", overlay["canonical_budget_policy_bytes"].encode())

        def publish(db, current):
            coordinator.materialize_publication(db, current, "policy_published", run_root / "budget_policy.json",
                                                name="bootstrap.policy")
            return {"canonical_policy_bytes": current["reservation"]["canonical_budget_policy_bytes"],
                    "policy_digest": current["reservation"]["budget_policy_digest"]}

        operation = advance("policy_published", publish)
        pipe.send((operation, coordinator.history(operation["operation_id"])))
    finally:
        coordinator.close()
        pipe.close()


def start_client(pipe, root, crash_boundary, occurrence=1, hook_request=None):
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
    from lqcd_agent.control.strict_json import digest

    count = 0

    def observer(name, side, value):
        nonlocal count
        if (name, side) == crash_boundary:
            count += 1
            if count == occurrence:
                os._exit(84)

    if hook_request is not None:
        from functools import partial
        from harness.pytest_evidence import production_hook
        observer.production_hooks = {tuple(crash_boundary): (partial(production_hook, hook_request["case_id"], process_request=hook_request),)}

    clock = FakeClock(100, 0) if crash_boundary else FakeClock(140, 40)
    coordinator = Coordinator(root, clock=clock, observer=observer)
    try:
        inputs = {"root_goal": {"goal": "synthetic"}, "input_snapshot": {"data": "synthetic"}}
        request = StartRunRequest("case", inputs, digest(inputs), "start-key", "phase_b_test")
        result = ControlPlane(coordinator, worker_id="first" if crash_boundary else "second").start_run(
            request, actor=ActorContext("operator", "human", ("start",)))
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def pause_client(pipe, root, locator, action, crash_boundary=None, *, elapsed=0, synchronized=False):
    """Run a real Pause API in an independent interpreter at an exact boundary."""
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.pause import CancelPauseRequest, PublishPauseRequest, ResumeRunRequest
    from lqcd_agent.control.strict_json import digest

    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(87)

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    actor = ActorContext("operator", "human", ("cancel", "control.internal", "resume", "start"))
    plane = ControlPlane(coordinator, worker_id="pause-worker-" + str(os.getpid()))
    try:
        if synchronized:
            pipe.send("ready")
            assert pipe.recv() == "go"
        try:
            if action == "publish":
                result = plane.publish_pause(PublishPauseRequest(
                    locator, "recovery_decision", "attempt_000001", None,
                    {"kind": "recovery_decision", "actions": ["abandon_and_halt"]},
                    {"actor_type": "human", "scopes": ["resume"]}, "publish"), actor=actor)
            elif action == "cancel":
                result = plane.cancel_pause(CancelPauseRequest(locator, "pause_000001", "cancel", "operator_cancel"), actor=actor)
            else:
                payload = {"action": "abandon_and_halt"}
                result = plane.resume_run(ResumeRunRequest(locator, "pause_000001", "resume", "recovery_decision", payload, digest(payload)), actor=actor)
            pipe.send(("result", result))
        except ControlIntegrityError as error:
            pipe.send(("rejected", str(error)))
    finally:
        coordinator.close()
        pipe.close()


def external_cancel_client(pipe, root, locator, safe, crash_boundary=None, *, elapsed=0):
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.pause import CancelPauseRequest
    from test_external_control import SyntheticExternalStop

    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(90)

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    try:
        plane = ControlPlane(coordinator, worker_id="external-cancel-" + str(os.getpid()), external_adapter=SyntheticExternalStop(safe=safe))
        result = plane.cancel_pause(CancelPauseRequest(locator, "pause_000001", "cancel", "operator_cancel"),
                                    actor=ActorContext("operator", "human", ("cancel", "control.internal", "resume", "start")))
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def external_interrupt_client(pipe, root, request, safe, crash_boundary=None, *, elapsed=0):
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.pause import ResolveExternalInterruptRequest
    from test_external_control import SyntheticExternalStop

    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(91)

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    try:
        plane = ControlPlane(coordinator, worker_id="external-interrupt-" + str(os.getpid()), external_adapter=SyntheticExternalStop(safe=safe))
        result = plane.resolve_external_interrupt(ResolveExternalInterruptRequest(**request), actor=ActorContext("operator", "human", ("control.internal",)))
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def child_client(pipe, root, payload, fork, crash_boundary=None, *, elapsed=0):
    from lqcd_agent.control.children import ForkRunRequest, ReplayRunRequest
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane

    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(88)

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    plane = ControlPlane(coordinator, worker_id="child-worker-" + str(os.getpid()))
    actor = ActorContext("operator", "human", ("control.internal", "fork", "policy.select", "replay", "resume", "start"))
    try:
        if fork:
            payload["artifact_ids"] = tuple(payload["artifact_ids"])
            result = plane.fork_run(ForkRunRequest(**payload), actor=actor)
        else:
            result = plane.replay_run(ReplayRunRequest(**payload), actor=actor)
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def resume_client(pipe, root, payload, crash_boundary=None, *, elapsed=0, valid=True, synchronized=False):
    """A fresh interpreter resumes the same canonical request without test evidence injection."""
    from lqcd_agent.control.capabilities import HumanResponseVerdict, TargetOutcome
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.pause import ResumeRunRequest
    from helpers.domain_adapters import SyntheticRepauseAdapter

    calls = []
    rendezvous = {"armed": False}

    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(89)
        if synchronized == "reservation" and rendezvous["armed"] and (name, side) == ("coordinator.database_commit", "after"):
            rendezvous["armed"] = False
            pipe.send("reserved")
            assert pipe.recv() == "claim"

    class Target:
        def invoke(self, identity):
            calls.append(identity)
            return TargetOutcome("succeeded" if valid else "pending", {"current_artifact_ids": {}},
                                 human_response_verdict=HumanResponseVerdict(valid, None if valid else "Synthetic invalid input"))

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    try:
        if synchronized:
            pipe.send("ready")
            assert pipe.recv() == "go"
        rendezvous["armed"] = True
        actor = ActorContext("operator", "human", ("control.internal", "resume"))
        plane = ControlPlane(coordinator, worker_id="resume-worker-" + str(os.getpid()), resume_target_adapter=Target(),
                             resume_decision_adapter=SyntheticRepauseAdapter())
        try:
            result = plane.resume_run(ResumeRunRequest(**payload), actor=actor)
            pipe.send(("result", result, calls))
        except ControlIntegrityError as error:
            pipe.send(("rejected", str(error), calls))
    finally:
        coordinator.close()
        pipe.close()


def invocation_client(pipe, root, capability_id, action):
    from lqcd_agent.control.capabilities import InvocationLeases

    def observer(name, side, value):
        target = "invocation.started_intent" if action == "crash_intent" else "invocation.attempt_started.file_sync"
        if action.startswith("crash_") and (name, side) == (target, "after"):
            os._exit(85)

    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=observer)
    try:
        leases = InvocationLeases(coordinator)
        pipe.send("ready")
        assert pipe.recv() == "go"
        try:
            result = leases.acquire(capability_id, "consumer-" + str(os.getpid()), expected_epoch=0, lease_seconds=5)
            if action.startswith("crash_"):
                leases.start_intent(capability_id, result["worker_id"], result["invocation_epoch"])
                leases.publish_started(capability_id, result["worker_id"], result["invocation_epoch"])
            pipe.send(("acquired", result["invocation_epoch"]))
        except ControlIntegrityError as error:
            pipe.send(("rejected", str(error)))
    finally:
        coordinator.close()
        pipe.close()


def external_pause_client(pipe, root, locator, phase):
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from test_external_control import external_pause_request

    def observer(name, side, value):
        if name == "control.publish_pause.not_applicable." + phase and side == "after":
            os._exit(92)

    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=observer)
    try:
        ControlPlane(coordinator, worker_id="external-publisher").publish_pause(
            external_pause_request(locator), actor=ActorContext("operator", "human", ("control.internal",)))
        pipe.send("unexpected_completed_publication")
    finally:
        coordinator.close()
        pipe.close()


def external_resume_client(pipe, root, request, crash_boundary=None, *, elapsed=0, failure=False, safe=True):
    from pathlib import Path
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.pause import ResumeRunRequest
    from test_external_consumption_control import ExternalDomainConsumer, ExternalDomainFailure

    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(93)

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    try:
        locator = request["run_locator"]
        run_root = Path(root) / locator["case_id"] / locator["run_id"]
        adapter = ExternalDomainFailure(run_root, safe=safe) if failure else ExternalDomainConsumer(run_root)
        plane = ControlPlane(coordinator, worker_id="external-consumer-" + str(os.getpid()),
                             external_adapter=adapter, resume_target_adapter=adapter)
        result = plane.resume_run(ResumeRunRequest(**request), actor=ActorContext("operator", "human", ("cancel", "control.internal", "resume", "start")))
        pipe.send((result, adapter.calls))
    finally:
        coordinator.close()
        pipe.close()


def close_client(pipe, root, request, crash_boundary=None, *, elapsed=0, hold_phase=None):
    """Resume a precomputed terminal publication with a new process lease."""
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.operations import CloseRunRequest

    held = False
    coordinator = None

    def observer(name, side, value):
        nonlocal held
        if (name, side) == crash_boundary:
            os._exit(94)
        if coordinator is not None and not held and hold_phase is not None and (name, side) == ("coordinator.database_commit", "after"):
            rows = coordinator.connection.execute("SELECT operation_id FROM control_operations WHERE operation_type='close_run'").fetchall()
            if rows and coordinator.get(rows[-1][0])["phase"] == hold_phase:
                held = True
                pipe.send(("held", rows[-1][0]))
                assert pipe.recv() == "continue"

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    try:
        result = ControlPlane(coordinator, worker_id="close-" + str(os.getpid())).close_run(
            CloseRunRequest(**request), actor=ActorContext("operator", "human", ("control.internal",)))
        pipe.send(result)
    finally:
        coordinator.close()
        pipe.close()


def preparation_client(pipe, root, locator, crash_boundary=None, *, elapsed=0):
    """Materialize only the frozen preparation after an independent restart."""
    from pathlib import Path
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.operations import AdvanceRunRequest
    from test_target_preparation_control import DomainPreparation

    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(95)

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    try:
        adapter = DomainPreparation(Path(root) / locator["case_id"] / locator["run_id"])
        result = ControlPlane(coordinator, worker_id="prepare-" + str(os.getpid()), route_adapter=adapter).advance_run(
            AdvanceRunRequest(locator, "attempt_000002", "prepare"), actor=ActorContext("operator", "human", ("control.internal",)))
        pipe.send((result, adapter.calls))
    finally:
        coordinator.close()
        pipe.close()


def timeout_client(pipe, root, request, crash_boundary=None, *, elapsed=0):
    """Continue the same safe timeout without executing a domain consumer."""
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from lqcd_agent.control.pause import ResolveExternalInterruptRequest
    from test_timeout_consumption_control import DomainTimeout

    def observer(name, side, value):
        if (name, side) == crash_boundary:
            os._exit(96)

    coordinator = Coordinator(root, clock=FakeClock(100 + elapsed, elapsed), observer=observer)
    try:
        adapter = DomainTimeout()
        result = ControlPlane(coordinator, worker_id="timeout-" + str(os.getpid()), external_adapter=adapter).resolve_external_interrupt(
            ResolveExternalInterruptRequest(**request), actor=ActorContext("operator", "human", ("control.internal",)))
        pipe.send((result, adapter.calls, adapter.deliveries))
    finally:
        coordinator.close()
        pipe.close()


def historical_child_client(pipe, root, request, fork, *, hold_snapshot=False):
    """Use the real child API; a competing historical owner changes the same DB."""
    from lqcd_agent.control.children import ForkRunRequest, ReplayRunRequest
    from lqcd_agent.control.interfaces import ActorContext, ControlPlane
    from test_historical_source_control import Archived03Reader
    parked = False
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    def observer(name, side, value):
        nonlocal parked
        if hold_snapshot and not parked and (name, side) == ("coordinator.database_commit", "after"):
            old = coordinator.lookup_key("public_control", request["idempotency_key"])
            if old is not None and old["phase"] == "operation_reserved":
                parked = True
                pipe.send(("snapshot_frozen", old["reservation"]["source_snapshot_proof"]))
                assert pipe.recv() == "continue"
    coordinator.observer = observer
    try:
        plane = ControlPlane(coordinator, worker_id="historical-child-" + str(os.getpid()), source_adapter=Archived03Reader())
        actor = ActorContext("operator", "human", ("fork", "policy.select", "replay"))
        try:
            result = (plane.fork_run if fork else plane.replay_run)((ForkRunRequest if fork else ReplayRunRequest)(**request), actor=actor)
            pipe.send(("result", result))
        except ControlIntegrityError as error:
            pipe.send(("rejected", str(error)))
    finally:
        coordinator.close()
        pipe.close()


def historical_claim_client(pipe, root, locator):
    """Represent the original historical Host's pre-publication claim CAS."""
    from lqcd_agent.control.strict_json import canonical_bytes, digest, loads
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    try:
        with coordinator.transaction() as db:
            key = digest(locator)
            row = db.execute("SELECT value FROM pause_ownership WHERE run_key=?", (key,)).fetchone()
            value = loads(row[0])
            assert value["owner"] is None and value["status"] == "opened"
            value["owner"] = "original_historical_resume"
            db.execute("UPDATE pause_ownership SET revision=revision+1,value=? WHERE run_key=?", (canonical_bytes(value), key))
            db.execute("UPDATE run_controls SET revision=revision+1 WHERE run_key=?", (key,))
        pipe.send("claimed")
    finally:
        coordinator.close()
        pipe.close()
