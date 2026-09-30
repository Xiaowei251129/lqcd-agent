"""Independent process drivers for frozen B02 control phase fault cases."""
from contextlib import contextmanager
from dataclasses import asdict
from functools import partial
import multiprocessing
import os
from pathlib import Path
import tempfile
import traceback

from harness.inventory import case_specs
from harness.pytest_evidence import consume_process_hook, process_hook_request, production_hook
from harness.trace import event
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, read_regular
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane
from lqcd_agent.control.operations import AdvanceRunRequest, CloseRunRequest
from lqcd_agent.control.pause import CancelPauseRequest, ResolveExternalInterruptRequest
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads


SPECS = case_specs(PROTOCOL)
PHASE_CASES = tuple(cid for cid in SPECS if cid.startswith("control."))


def run_files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.glob("*/*/**/*")
            if path.is_file() and ".lqcd" not in path.relative_to(root).parts}


@contextmanager
def phase_fixture(case_id, *, recovery_target=None, canonical_advance=None, canonical_resume=None, canonical_backend_stop=False):
    from test_bootstrap_control import request as start_request
    from test_child_control import child_control
    from test_external_consumption_control import normal_external
    from test_external_control import external_pause_request, external_source
    from test_pause_control import control
    from test_snapshot_loss_control import requests
    from test_timeout_consumption_control import timeout_source
    from lqcd_agent.control.children import ForkRunRequest, ReplayRunRequest
    from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome

    _, kind, variant, phase, side, outcome = case_id.split(".")
    generator = None
    observer_only = phase == "resolution_winner_observed"
    if canonical_backend_stop:
        from test_external_operation_recovery import _running_stop_source
        assert kind in ("cancel_pause", "resolve_external_interrupt")
        coordinator, root, producer = _running_stop_source(containment_fault=None)
        value = loads(coordinator.connection.execute("SELECT value FROM external_operations").fetchone()[0])
        locator = value["run_locator"]
        actor = ActorContext("operator", "human", ("cancel", "control.internal"))
        if kind == "cancel_pause":
            request = CancelPauseRequest(locator, value["pause_id"], "cancel", "operator_cancel")
        else:
            trigger = {"run_locator": locator, "producer_operation_id": producer, "reason": "operation_timeout"}
            (root / "runtime_timeout_trigger.json").write_bytes(canonical_bytes(trigger))
            request = ResolveExternalInterruptRequest(locator, producer, trigger["reason"],
                "runtime_timeout_trigger.json", digest(trigger))
    elif canonical_advance is not None:
        from test_external_consumption_control import success_external
        assert kind in ("advance_run", "close_run")
        generator = (success_external if canonical_advance == "success" else normal_external).__wrapped__()
        coordinator, plane, actor, locator, resume, _ = next(generator)
        assert plane.resume_run(resume, actor=actor)["operation_status"] == "committed"
        attempt = "attempt_000002"
        if kind == "advance_run" and phase == "terminal_transition_committed":
            from test_advance_control import SyntheticDomainRoute
            plane.route_adapter = SyntheticDomainRoute("memory_report")
            prepared = plane.advance_run(AdvanceRunRequest(locator, attempt, "prepare-end"), actor=actor)
            leases = InvocationLeases(coordinator)
            cap = prepared["result"]["capability_id"]
            leases.acquire(cap, "consumer", expected_epoch=0, lease_seconds=10)

            class Report:
                def invoke(self, identity):
                    return TargetOutcome("pending", {"current_artifact_ids": {}})

            attempt = leases.invoke(cap, "consumer", 1, Report())["attempt_id"]
        if kind == "close_run":
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            request = CloseRunRequest(locator, digest(parse_ledger(read_regular(root / "execution_history.jsonl")).values[-1]),
                                      "terminal_operator_stop")
        else:
            request = AdvanceRunRequest(locator, attempt, "advance")
    elif kind == "start_run":
        root = Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-runtime-", dir="/private/tmp"))
        coordinator = Coordinator(root, clock=FakeClock(100, 0))
        actor = ActorContext("operator", "human", ("start",))
        request = start_request()
    elif kind in ("replay_run", "fork_run"):
        generator = child_control.__wrapped__()
        coordinator, plane, actor, source = next(generator)
        locator = source["result"]["run_locator"]
        if kind == "fork_run":
            class Failed:
                def invoke(self, identity):
                    return TargetOutcome("failed", {"current_artifact_ids": {}}, {"type": "SyntheticRecovery", "message": "Deterministic domain input"})
            leases = InvocationLeases(coordinator)
            cap = source["result"]["capability_id"]
            leases.acquire(cap, "consumer", expected_epoch=0, lease_seconds=10)
            leases.invoke(cap, "consumer", 1, Failed())
            paused = plane.publish_pause(requests(locator)["publish"], actor=actor)
            request = ForkRunRequest(locator, "child", paused["result"]["execution_head"], profile_id="phase_b_test")
        else:
            request = ReplayRunRequest(locator, "child", coordinator.get(source["operation_id"])["request"]["root_inputs_digest"])
    elif kind == "resume_run" and variant == "continue_execution" and recovery_target is None:
        if canonical_resume == "success":
            from test_external_consumption_control import success_external
            generator = success_external.__wrapped__()
        else:
            generator = normal_external.__wrapped__()
        coordinator, plane, actor, locator, request, _ = next(generator)
    elif kind == "resolve_external_interrupt" and variant == "recoverable_timeout":
        generator = timeout_source.__wrapped__()
        coordinator, plane, actor, locator, _, request = next(generator)
    else:
        generator = control.__wrapped__()
        coordinator, plane, actor, locator = next(generator)
        if kind == "advance_run":
            attempt = "attempt_000001"
            if phase == "terminal_transition_committed":
                from test_advance_control import SyntheticDomainRoute
                plane.route_adapter = SyntheticDomainRoute("memory_report")
                advanced = plane.advance_run(AdvanceRunRequest(locator, attempt, "prepare-end"), actor=actor)
                leases = InvocationLeases(coordinator)
                cap = advanced["result"]["capability_id"]
                leases.acquire(cap, "consumer", expected_epoch=0, lease_seconds=10)
                class PendingReport:
                    def invoke(self, identity):
                        return TargetOutcome("pending", {"current_artifact_ids": {}})
                state = leases.invoke(cap, "consumer", 1, PendingReport())
                attempt = state["attempt_id"]
            request = AdvanceRunRequest(locator, attempt, "advance")
        elif kind == "close_run":
            records = parse_ledger((coordinator.root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl").read_bytes()).values
            request = CloseRunRequest(locator, digest(records[-1]))
        elif kind == "publish_pause":
            request = requests(locator)["publish"]
        elif kind == "resume_run" and recovery_target is not None:
            from test_advance_control import SyntheticDomainRoute
            from lqcd_agent.control.pause import PublishPauseRequest, ResumeRunRequest
            plane.route_adapter = SyntheticDomainRoute(recovery_target)
            plane.advance_run(AdvanceRunRequest(locator, "attempt_000001", "advance"), actor=actor)
            paused = plane.publish_pause(PublishPauseRequest(locator, "recovery_decision", "attempt_000001", "attempt_000002",
                {"kind": "recovery_decision", "actions": ["abandon_and_halt", "continue_existing_target"]},
                {"actor_type": "human", "scopes": ["resume"]}, "publish"), actor=actor)
            payload = {"action": "continue_existing_target"}
            request = ResumeRunRequest(locator, paused["result"]["pause_id"], "resume", "recovery_decision", payload, digest(payload))
        elif kind == "resume_run":
            plane.publish_pause(requests(locator)["publish"], actor=actor)
            request = requests(locator)["resume"]
        else:
            external_source((coordinator, plane, actor, locator))
            plane.publish_pause(external_pause_request(locator), actor=actor)
            if kind == "cancel_pause":
                if observer_only:
                    from test_external_control import SyntheticExternalStop
                    plane.external_adapter = SyntheticExternalStop(safe=True)
                    plane.cancel_pause(CancelPauseRequest(locator, "pause_000001", "winner", "operator_cancel"), actor=actor)
                request = CancelPauseRequest(locator, "pause_000001", "cancel", "operator_cancel")
            else:
                reason = "terminal_operator_stop" if variant == "controlled_halt" else "proven_integrity_trigger"
                trigger = {"run_locator": locator, "producer_operation_id": "producer_code", "reason": reason}
                (coordinator.root / locator["case_id"] / locator["run_id"] / "synthetic_interrupt.json").write_bytes(canonical_bytes(trigger))
                request = ResolveExternalInterruptRequest(locator, "producer_code", reason, "synthetic_interrupt.json", digest(trigger))
    unavailable = "unavailable" in phase or phase == "pause_quarantined_recorded"
    failure_phase = phase.startswith("consumption_failure_") or kind == "resume_run" and variant == "continue_execution" and phase.startswith("terminal_")
    config = {"root": str(coordinator.root), "method": kind, "request_class": type(request).__name__,
              "request": asdict(request), "actor": asdict(actor), "safe": not unavailable,
              "failure": failure_phase, "observer_only": observer_only, "ordinary": recovery_target is not None, "route": None if phase == "terminal_transition_committed" else "decision_coordinator",
              "violation": kind == "resolve_external_interrupt" and variant == "recoverable_timeout" and
              (phase.startswith("terminal_") or phase in ("interrupt_safe_pause_disposition_committed", "interrupt_terminal_ownership_reserved")), "variant": variant}
    try:
        yield coordinator, config
    finally:
        if generator is not None:
            generator.close()
        else:
            coordinator.close()


def phase_client(pipe, config, *, elapsed, fault=None, hook_request=None):
    from lqcd_agent.control import children, interfaces, operations, pause
    from test_advance_control import SyntheticDomainRoute
    from test_external_control import SyntheticExternalStop
    from test_external_consumption_control import CanonicalDomainConsumer, ExternalDomainConsumer, ExternalDomainFailure
    from test_timeout_consumption_control import DomainTimeout

    seen = 0
    armed = config.get("arm_after") is None
    hooks = {fault: (partial(production_hook, hook_request["case_id"], process_request=hook_request),)} if hook_request else {}
    def observer(name, side, value):
        nonlocal seen, armed
        if config.get("arm_after") == [name, side]:
            armed = True
            observer.production_hooks = hooks
        if (name, side) == fault and armed:
            seen += 1
            if seen < config.get("fault_occurrence", 1):
                if seen + 1 == config["fault_occurrence"]:
                    observer.production_hooks = hooks
                return
            identity = {key: value[key] for key in ("operation_id", "phase", "phase_revision", "lease_epoch")} if value and "operation_id" in value else None
            pipe.send({"kind": "fault", "name": name, "side": side, "operation": identity})
            os._exit(97)
    observer.production_hooks = hooks if armed and config.get("fault_occurrence", 1) == 1 else {}
    coordinator = Coordinator(config["root"], clock=FakeClock(100 + elapsed, elapsed,
        epoch_id="runtime_process_epoch_" + str(elapsed + 2)), observer=observer)
    try:
        cls = next(getattr(module, config["request_class"]) for module in (children, interfaces, operations, pause) if hasattr(module, config["request_class"]))
        request = cls(**config["request"])
        actor = ActorContext(**{**config["actor"], "scopes": tuple(config["actor"]["scopes"])})
        route = SyntheticDomainRoute(config["route"])
        if config.get("preparation_reason") is not None:
            from .b03_analysis_execution_cases import NotApplicableRoute
            route = NotApplicableRoute(config["route"], config["preparation_reason"])
        plane = ControlPlane(coordinator, worker_id=config.get("worker_id", "worker"), route_adapter=route)
        kind = config["method"]
        adapter = None
        if config.get("guard") == "stale_epoch":
            with coordinator.transaction() as db:
                coordinator.fence(db, **config["fence_arguments"])
            raise AssertionError("Stale operation was accepted")
        if config.get("guard") == "early_capability":
            from lqcd_agent.control.capabilities import InvocationLeases
            InvocationLeases(coordinator).acquire(config["capability_id"], "early", expected_epoch=0, lease_seconds=5)
            raise AssertionError("Inactive capability was accepted")
        if config.get("ordinary"):
            from lqcd_agent.control.capabilities import TargetOutcome
            class Ordinary:
                calls = 0
                def invoke(self, identity):
                    self.calls += 1
                    return TargetOutcome("pending", {"current_artifact_ids": {}})
            adapter = Ordinary()
            plane.resume_target_adapter = adapter
        elif kind == "resume_run" and config["variant"] == "continue_execution":
            locator = request.run_locator
            run = coordinator.root / locator["case_id"] / locator["run_id"]
            adapter = (ExternalDomainFailure(run, safe=config["safe"]) if config["failure"] else
                       CanonicalDomainConsumer(coordinator, coordinator.root / "base_repository")
                       if (coordinator.root / "base_repository").exists() else ExternalDomainConsumer(run))
            if config.get("canonical_consumer_stop") is not None:
                from .b03_uncertain_consumer_cases import CanonicalConsumerHost
                adapter = CanonicalConsumerHost(coordinator, coordinator.root / "base_repository",
                                                **config["canonical_consumer_stop"])
            plane.external_adapter = plane.resume_target_adapter = adapter
        elif kind in ("resolve_external_interrupt", "cancel_pause"):
            cls = DomainTimeout if config["variant"] == "recoverable_timeout" else SyntheticExternalStop
            adapter = cls(coordinator, safe=config["safe"], violation=config["violation"]) if cls is DomainTimeout else cls(
                safe=config["safe"], violation=config["violation"])
            plane.external_adapter = adapter
        if config.get("canonical_backend_stop"):
            from lqcd_agent.code_agent.containment import DeterministicContainment
            from lqcd_agent.code_agent.external_operation import CodeExternalStop
            from test_external_operation_recovery import RefuseRedispatch
            backend = RefuseRedispatch(coordinator.root / "fake_backend", clock=lambda: 100 + elapsed)
            adapter = CodeExternalStop(coordinator, backend, DeterministicContainment(coordinator.root / "containment"),
                                       backend.read_receipt)
            plane.external_adapter = adapter
        result = getattr(plane, kind)(request, actor=actor)
        pipe.send({"kind": "result", "result": result, "calls": getattr(adapter, "calls", 0)})
    except Exception as error:
        from lqcd_agent.control.strict_json import ControlIntegrityError
        if config.get("expect_rejection") and isinstance(error, ControlIntegrityError):
            pipe.send({"kind": "result", "result": {"rejected": True, "error": str(error)}})
        else:
            pipe.send({"kind": "error", "traceback": traceback.format_exc()})
    finally:
        coordinator.close()
        pipe.close()


def run_client(config, elapsed, *, fault=None, hook_request=None):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=phase_client, args=(child, config), kwargs={"elapsed": elapsed, "fault": fault, "hook_request": hook_request})
    try:
        process.start()
        child.close()
        assert parent.poll(30), "Control phase process did not return"
        result = parent.recv()
        process.join(20)
        assert process.exitcode == (97 if fault else 0), result
        if hook_request is not None:
            consume_process_hook(hook_request, process, expected_exit=97)
        assert result["kind"] == ("fault" if fault else "result"), result
        return result
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()


def _race_client(pipe, config, elapsed, barrier):
    barrier.wait(timeout=30)
    phase_client(pipe, config, elapsed=elapsed)


def race_clients(config, elapsed):
    from copy import deepcopy
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(3)
    running = []
    try:
        for index in range(2):
            candidate = deepcopy(config)
            candidate["worker_id"] = "racer-" + str(index)
            candidate["expect_rejection"] = True
            parent, child = context.Pipe()
            process = context.Process(target=_race_client, args=(child, candidate, elapsed, barrier))
            process.start()
            child.close()
            running.append((process, parent))
        barrier.wait(timeout=30)
        results = []
        for process, parent in running:
            assert parent.poll(30), "Competing control worker did not return"
            result = parent.recv()
            process.join(20)
            assert process.exitcode == 0 and result["kind"] == "result", result
            value = result["result"]
            if value.get("rejected"):
                assert value["error"] in ("Operation already leased", "Foreign failed operation context",
                                          "Stale or terminal operation fence"), value
            else:
                results.append(value)
        assert results
        assert len({result["operation_id"] for result in results}) == 1
        terminal = [result for result in results if result["operation_status"] != "in_progress"]
        assert terminal and all(value == terminal[0] for value in terminal)
        return terminal[0]
    finally:
        for process, parent in running:
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()


def exercise_phase_case(case_id, *, fixture_case=None, fault_point=None, occurrence=1, arm_after=None, recovery_target=None, takeover=False, competition=None, evidence_check=None, canonical_advance=None, canonical_resume=None, canonical_consumer_stop=None, canonical_backend_stop=False, route_target=None, preparation_reason=None):
    spec = SPECS[case_id]
    boundary, side, outcome = case_id.rsplit(".", 2)
    with phase_fixture(fixture_case or case_id, recovery_target=recovery_target, canonical_advance=canonical_advance, canonical_resume=canonical_resume, canonical_backend_stop=canonical_backend_stop) as (coordinator, config):
        boundary = fault_point or boundary
        config.update(fault_occurrence=occurrence, arm_after=arm_after)
        if canonical_consumer_stop is not None:
            config["canonical_consumer_stop"] = canonical_consumer_stop
        config["canonical_backend_stop"] = canonical_backend_stop
        if route_target is not None:
            config["route"] = route_target
        if preparation_reason is not None:
            config["preparation_reason"] = preparation_reason
        existing_operation = None
        contender = None
        if competition in ("same_key", "double_claim", "terminal_owner"):
            from copy import deepcopy
            first_phase = "control." + config["method"] + "." + config["variant"] + ".resume_disposition_committed"
            run_client(config, 0, fault=(first_phase, "before"))
            existing_operation = coordinator.lookup_key("public_control", config["request"]["idempotency_key"])
            if competition != "same_key":
                contender = deepcopy(config)
                contender["request"]["idempotency_key"] = "contender"
                if competition == "terminal_owner":
                    contender.update(method="cancel_pause", request_class="CancelPauseRequest", variant="not_applicable")
                    contender["request"] = asdict(CancelPauseRequest(config["request"]["run_locator"], "pause_000001", "contender", "operator_cancel"))
                    first_phase = "control.cancel_pause.not_applicable.cancel_arbitrated"
                run_client(contender, 0, fault=(first_phase, "before"))
        if takeover:
            run_client(config, 0, fault=("control.start_run.not_applicable.policy_published", "before"))
            existing_operation = coordinator.lookup_key("public_control", config["request"]["idempotency_key"])
        before_ids = {row[0] for row in coordinator.connection.execute("SELECT operation_id FROM control_operations")}
        before_files = run_files(coordinator.root)
        tables = ("control_operations", "control_phases", "control_snapshots", "control_publications", "run_controls",
                  "pause_ownership", "run_terminal_closure", "invocation_capabilities", "external_operations")
        before_rows = {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)] for table in tables}
        receipt_dir = Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-case-evidence-", dir="/private/tmp"))
        request = process_hook_request(case_id, receipt_dir)
        fault = run_client(config, 40 if takeover else 0, fault=(boundary, side), hook_request=request)
        assert fault["name"] == boundary and fault["side"] == side
        if competition == "post_claim_system_stop":
            from copy import deepcopy
            candidate = deepcopy(config)
            locator = config["request"]["run_locator"]
            root = coordinator.root / locator["case_id"] / locator["run_id"]
            head = digest(parse_ledger(read_regular(root / "execution_history.jsonl")).values[-1])
            candidate.update(method="close_run", request_class="CloseRunRequest", variant="not_applicable", expect_rejection=True)
            candidate["request"] = asdict(CloseRunRequest(locator, head, "terminal_operator_stop"))
            saved = run_files(coordinator.root)
            stopped = run_client(candidate, 0)["result"]
            assert stopped.get("rejected") is True and run_files(coordinator.root) == saved
        new = [coordinator.get(row[0]) for row in coordinator.connection.execute("SELECT operation_id FROM control_operations") if row[0] not in before_ids]
        if outcome == "reservation_rolled_back":
            assert new == [] and run_files(coordinator.root) == before_files
            assert {table: [tuple(row) for row in coordinator.connection.execute("SELECT * FROM " + table)] for table in tables} == before_rows
            recovered = run_client(config, 80 if takeover else 40)["result"]
            assert recovered["lease_epoch"] == 1 and recovered["operation_id"] not in before_ids
            if fault["operation"] is not None:
                assert recovered["operation_id"] != fault["operation"]["operation_id"]
        else:
            operation = coordinator.get(existing_operation["operation_id"]) if existing_operation is not None else next(op for op in new if op["operation_type"] == config["method"])
            assert operation["status"] == "in_progress"
            if fault["operation"] is not None:
                assert fault["operation"]["operation_id"] == operation["operation_id"]
            if outcome == "non_materializable_domain_gap":
                with coordinator.transaction() as db:
                    db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (operation["operation_id"],))
                    # A failure tail owns a separate frozen plan in its phase evidence.
                    # Losing only the normal plan does not remove that authorization.
                    if any(row["phase"] == "consumption_failure_ownership_reserved" for row in coordinator.history(operation["operation_id"])):
                        db.execute("DELETE FROM control_phases WHERE operation_id=? AND phase=?",
                                   (operation["operation_id"], "consumption_failure_ownership_reserved"))
            elif outcome == "integrity_conflict":
                locator = operation["reservation"].get("reserved_run_locator", operation["reservation"].get("reserved_child_run_locator", operation["request"].get("run_locator")))
                ledger = coordinator.root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl"
                if ledger.exists() and not config["observer_only"]:
                    with ledger.open("ab") as stream:
                        stream.write(b"{")
                else:
                    with coordinator.transaction() as db:
                        db.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?", (b"{}", operation["operation_id"]))
            recovered = (race_clients(config, 40) if competition == "failure_worker_race" else
                         run_client(config, 80 if takeover else 40)["result"])
            assert recovered["operation_id"] == operation["operation_id"] and recovered["lease_epoch"] == 2
            assert recovered["operation_status"] != "in_progress", recovered
            if outcome == "non_materializable_domain_gap":
                assert recovered["operation_status"] == "recovery_required" and (recovered["run_status"] is None or config["observer_only"]), recovered
            elif outcome == "integrity_conflict":
                assert recovered["operation_status"] in ("failed", "recovery_required"), recovered
                assert recovered["run_status"] is None or config["observer_only"], recovered
            elif outcome == "committed_result_replay":
                assert recovered["operation_status"] == "committed", recovered
            elif outcome == "terminal_tombstone_replay":
                assert recovered["operation_status"] == "recovery_required" and recovered["terminal_closure"] == "unavailable", recovered
            else:
                assert recovered["operation_status"] in ("committed", "recovery_required"), recovered
        owner = recovered["operation_id"]
        stable = run_files(coordinator.root)
        if outcome in ("committed_result_replay", "terminal_tombstone_replay"):
            with coordinator.transaction() as db:
                db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (owner,))
        assert run_client(config, 120 if takeover else 80)["result"] == recovered
        assert run_files(coordinator.root) == stable
        for path, content in before_files.items():
            if config["method"] in ("replay_run", "fork_run"):
                assert stable[path] == content
        closures = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM run_terminal_closure")]
        assert all(value["terminal_closure"] != "pending" for value in closures), closures
        if config["method"] == "resume_run" and config["request"]["input_kind"] == "external_result" and any(
                value["terminal_closure"] == "unavailable" for value in closures):
            external = loads(coordinator.connection.execute("SELECT value FROM external_operations").fetchone()[0])
            assert external["resolution_owner"] == "normal" and external["active_binding_status"] in ("quarantined", "released")
        if config["observer_only"]:
            assert [tuple(row) for row in coordinator.connection.execute("SELECT * FROM run_terminal_closure")] == before_rows["run_terminal_closure"]
            assert all(value["terminal_closure_owner_operation_id"] != owner for value in closures)
        elif config["method"] in ("resume_run", "cancel_pause", "resolve_external_interrupt"):
            assert all(value["terminal_closure_owner_operation_id"] == owner for value in closures), closures
        for path, content in stable.items():
            if not path.endswith("execution_history.jsonl") or not content.endswith(b"\n"):
                continue
            records = parse_ledger(content).values
            started = [r["attempt_id"] for r in records if r["record_type"] == "attempt" and r["event"] == "started"]
            settled = [r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"]
            assert len(started) == len(set(started)) and len(settled) == len(set(settled))
        if evidence_check is not None:
            evidence_check(coordinator, config, before_rows, recovered)
        events = [event("fault", phase=boundary, stage=side, outcome=outcome)]
        for row in coordinator.history(owner):
            events.append(event("durable_phase", source=config["method"], target=config["variant"], phase=row["phase"], phase_revision=row["revision"], lease_epoch=row["lease_epoch"]))
        events.append(event("immutable_replay", source=config["method"], target=config["variant"], status=recovered["operation_status"],
                            phase=recovered["operation_phase"], lease_epoch=recovered["lease_epoch"],
                            run_status=recovered["run_status"], outcome=recovered["terminal_closure"], invariants=sorted(spec["invariants"])))
        if competition in ("double_claim", "terminal_owner"):
            frozen_operation = coordinator.get(owner)
            second = run_client(contender, 40)["result"]
            assert second["operation_status"] != "in_progress" and second["operation_id"] != owner
            owners = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM pause_ownership")]
            closures = [loads(row[0]) for row in coordinator.connection.execute("SELECT value FROM run_terminal_closure")]
            assert len(owners) == 1 and len(closures) <= 1
            if closures:
                assert owners[0]["owner"] == closures[0]["terminal_closure_owner_operation_id"]
                assert closures[0]["terminal_closure"] != "pending"
            final = run_files(coordinator.root)
            assert coordinator.get(owner) == frozen_operation
            current = run_client(config, 80)["result"]
            # Query closure fields describe the current Run; the stored operation
            # outcome remains byte-identical when a different owner later closes it.
            expected = {**recovered, **({"terminal_closure": closures[0]["terminal_closure"], "run_status": closures[0]["run_status"]} if closures else {})}
            assert current == expected
            assert run_client(contender, 80)["result"] == second
            assert run_files(coordinator.root) == final
            events.append(event("competing_owner_resolved", source=config["method"], target=contender["method"],
                status=second["operation_status"], lease_epoch=second["lease_epoch"],
                owner="first" if owners[0]["owner"] == owner else "contender" if owners[0]["owner"] == second["operation_id"] else "unclaimed"))
        elif competition == "source_owner":
            from lqcd_agent.control.pause import ResumeRunRequest
            from copy import deepcopy
            contender = deepcopy(config)
            payload = {"action": "abandon_and_halt"}
            contender.update(method="resume_run", request_class="ResumeRunRequest", variant="abandon_and_halt", expect_rejection=True)
            contender["request"] = asdict(ResumeRunRequest(config["request"]["source_run_locator"], "pause_000001", "source-owner", "recovery_decision", payload, digest(payload)))
            second = run_client(contender, 40)["result"]
            assert not second.get("rejected") and second["operation_status"] == "committed", second
            final = run_files(coordinator.root)
            assert run_client(config, 80)["result"] == recovered
            assert run_client(contender, 80)["result"] == second
            assert run_files(coordinator.root) == final
            events.append(event("source_claim_after_frozen_snapshot", status=second["operation_status"], run_status=second["run_status"]))
        elif competition == "capability":
            from copy import deepcopy
            contender = deepcopy(config)
            capability = next(row[0] for row in coordinator.connection.execute("SELECT capability_id,value FROM invocation_capabilities")
                              if loads(row[1])["authorization"]["identity"]["attempt_id"] == "attempt_000002" and
                              loads(row[1])["authorization"]["producer_operation_id"] != owner)
            contender.update(guard="early_capability", capability_id=capability, expect_rejection=True)
            before = run_files(coordinator.root)
            result = run_client(contender, 40)["result"]
            assert result.get("rejected") is True
            assert run_files(coordinator.root) == before
            events.append(event("prior_capability_rejected", outcome="integrity_conflict"))
        elif competition in ("failure_worker_race", "post_claim_system_stop"):
            events.append(event("failure_owner_worker_race_resolved" if competition == "failure_worker_race" else
                                "post_claim_system_stop_rejected", accepted=True, owner="original_resume",
                                guard="one_owner_no_second_stop_no_redispatch"))
        return {"schema_version": "0.1", "events": events}
