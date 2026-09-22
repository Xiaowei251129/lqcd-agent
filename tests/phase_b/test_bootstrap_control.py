"""B02 bootstrap control tests, not a claim of the complete B02 owned slice."""
from dataclasses import replace
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile

import pytest

from lqcd_agent.control.budget import policy
from lqcd_agent.control.capabilities import InvocationLeases, TargetOutcome
from lqcd_agent.control.checkpoints import verify_checkpoint
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.integrity import validate_run_root
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.operations import bootstrap_admission
from lqcd_agent.control.protocol import operation_variant
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest

from helpers.process_client import invocation_client, start_client


ACTOR = ActorContext("operator", "human", ("start",))


@pytest.fixture
def root():
    return Path(tempfile.mkdtemp(prefix="lqcd-agent-b02-bootstrap-", dir="/private/tmp"))


def request():
    inputs = {"root_goal": {"goal": "synthetic"}, "input_snapshot": {"data": "synthetic"}}
    return StartRunRequest("case", inputs, digest(inputs), "start-key", "phase_b_test")


def start(root, *, clock=None, observer=None):
    coordinator = Coordinator(root, clock=clock or FakeClock(100, 0), observer=observer)
    plane = ControlPlane(coordinator, worker_id="worker")
    result = plane.start_run(request(), actor=ACTOR)
    return coordinator, plane, result


@pytest.mark.parametrize("phase", ["run_root_created", "checkpoint_committed"])
@pytest.mark.parametrize("fault", ["missing", "digest", "invalid_json"])
def test_fresh_process_rejects_lost_bootstrap_plan_with_terminal_control_outcome(root, phase, fault):
    def stop(name, side, value):
        if name == "control.start_run.not_applicable." + phase and side == "after":
            raise RuntimeError("synthetic interrupted publication")
    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=stop)
    try:
        with pytest.raises(RuntimeError, match="interrupted publication"):
            ControlPlane(coordinator, worker_id="worker").start_run(request(), actor=ACTOR)
        coordinator.observer = None
        operation = coordinator.lookup_key("public_control", "start-key")
        locator = operation["reservation"]["reserved_run_locator"]
        run = root / locator["case_id"] / locator["run_id"]
        before = {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()}
        with coordinator.transaction() as db:
            if fault == "missing":
                db.execute("DELETE FROM control_snapshots WHERE operation_id=?", (operation["operation_id"],))
            else:
                db.execute("UPDATE control_snapshots SET value=? WHERE operation_id=?",
                           (b'{}' if fault == "digest" else b'{', operation["operation_id"]))
    finally:
        coordinator.close()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=start_client, args=(child, str(root), None))
    try:
        process.start()
        child.close()
        assert parent.poll(20)
        result = parent.recv()
        process.join(20)
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()
    assert result["operation_id"] == operation["operation_id"]
    assert result["operation_status"] == ("recovery_required" if fault == "missing" else "failed")
    assert result["publication_status"] == "terminal" and result["run_status"] is None
    assert result["terminal_closure"] == ("not_applicable" if fault == "missing" else "unavailable")
    assert {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before
    coordinator = Coordinator(root, clock=FakeClock(150, 50))
    try:
        plane = ControlPlane(coordinator, worker_id="third")
        original = coordinator.get(operation["operation_id"])
        assert plane.start_run(request(), actor=ACTOR) == result
        assert plane.query_operation(operation["operation_id"]) == result
        assert coordinator.get(operation["operation_id"]) == original
        with pytest.raises(ControlIntegrityError):
            InvocationLeases(coordinator).acquire("capability_" + operation["operation_id"], "consumer", expected_epoch=0, lease_seconds=5)
        assert {str(p.relative_to(run)): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before
    finally:
        coordinator.close()


def test_start_bootstrap_produces_real_separate_checkpoint_and_inactive_then_active_capability(root):
    observed = []

    def observer(name, side, value):
        if name.endswith("invocation_capability_prepared") and side == "after":
            observed.append(value["status"])

    coordinator, plane, result = start(root, observer=observer)
    try:
        assert result["operation_status"] == "committed"
        assert observed == ["in_progress"]
        operation_id = result["operation_id"]
        assert [row["phase"] for row in coordinator.history(operation_id)] == list(operation_variant("start_run", "not_applicable")["phases"])
        snap = coordinator.snapshot(operation_id)
        locator = result["result"]["run_locator"]
        run = root / locator["case_id"] / locator["run_id"]
        assert coordinator.path != run / "checkpoints/graph_checkpoints.sqlite"
        assert verify_checkpoint(run, snap["manifest"])["attempt_status"] == "scheduled"
        assert validate_run_root(run, manifest=snap["manifest"]).value == snap["projection"]
        ledger = parse_ledger((run / "execution_history.jsonl").read_bytes()).values
        assert [(row["record_type"], row["event"]) for row in ledger] == [
            ("run", "created"), ("budget", "policy_initialized"), ("budget", "decision_recorded"),
            ("cycle", "created"), ("attempt", "scheduled"), ("transition", "committed"), ("run_lifecycle", "transitioned")]
        assert ledger[2]["payload"]["proposed_action"] == "bootstrap_initial_route"
        dimensions = ledger[2]["payload"]["dimensions"]
        assert dimensions["control_attempts_per_run"]["projected_after"] == 5
        assert dimensions["transitions_per_run"]["projected_after"] == 7
        saved = {str(path): path.read_bytes() for path in run.rglob("*") if path.is_file()}
        assert plane.start_run(request(), actor=ACTOR) == result
        assert saved == {str(path): path.read_bytes() for path in run.rglob("*") if path.is_file()}
        caps = InvocationLeases(coordinator)
        cap = result["result"]["capability_id"]
        assert caps.get(cap)[1]["state"] == "unclaimed"
        before = coordinator.get(operation_id)
        coordinator.clock.advance(31)
        assert caps.acquire(cap, "consumer", expected_epoch=0, lease_seconds=5)["invocation_epoch"] == 1
        assert coordinator.get(operation_id) == before
    finally:
        coordinator.close()


@pytest.mark.parametrize("mutation", ["scope", "digest", "allow", "path", "profile"])
def test_start_rejects_untrusted_inputs_before_operation_or_run_identity(root, mutation):
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    try:
        typed, actor = request(), ACTOR
        if mutation == "scope":
            actor = ActorContext("operator", "human", ())
        elif mutation == "digest":
            typed = replace(typed, root_inputs_digest="0" * 64)
        elif mutation == "allow":
            inputs = {**typed.root_inputs, "allow": True}
            typed = replace(typed, root_inputs=inputs, root_inputs_digest=digest(inputs))
        elif mutation == "path":
            typed = replace(typed, case_id="../escaped")
        else:
            typed = replace(typed, profile_id="unapproved")
        with pytest.raises(ControlIntegrityError):
            ControlPlane(coordinator, worker_id="worker").start_run(typed, actor=actor)
        assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 0
        assert not (root / "case").exists()
    finally:
        coordinator.close()


def test_bootstrap_policy_binding_cannot_be_replaced_by_an_allow_decision():
    selected = policy("phase_b_test").value
    original = bootstrap_admission("operation", "a" * 64, selected)
    assert original["decision"] == "allow"
    assert original != bootstrap_admission("other-operation", "a" * 64, selected)
    assert original != bootstrap_admission("operation", "b" * 64, selected)
    for field, value in (("policy_digest", "0" * 64), ("terminal_reserve", {"control_attempts": 0, "transitions": 0})):
        with pytest.raises(ControlIntegrityError):
            bootstrap_admission("operation", "a" * 64, {**selected, field: value})
    with pytest.raises(TypeError):
        bootstrap_admission("operation", "a" * 64, selected, allow=True)


def test_invocation_start_order_stale_lease_and_no_intent_takeover(root):
    clock = FakeClock(100, 0)
    coordinator, _, result = start(root, clock=clock)
    try:
        cap = result["result"]["capability_id"]
        caps = InvocationLeases(coordinator)
        with pytest.raises(ControlIntegrityError, match="lease"):
            caps.start_intent(cap, "consumer", 0)
        first = caps.acquire(cap, "consumer", expected_epoch=0, lease_seconds=5)
        with pytest.raises(ControlIntegrityError, match="already leased"):
            caps.acquire(cap, "other", expected_epoch=1, lease_seconds=5)
        with pytest.raises(ControlIntegrityError, match="precedes"):
            caps.require_effect_authority(cap, "consumer", 1)
        clock.advance(5)
        second = caps.acquire(cap, "replacement", expected_epoch=1, lease_seconds=5)
        assert second["invocation_epoch"] == 2 and second["deadline"] == first["deadline"]
        with pytest.raises(ControlIntegrityError, match="Stale"):
            caps.start_intent(cap, "consumer", 1)
        value = caps.start_intent(cap, "replacement", 2)
        assert value["started_intent"]["record"]["event"] == "started"
        with pytest.raises(ControlIntegrityError, match="precedes"):
            caps.require_effect_authority(cap, "replacement", 2)
        caps.publish_started(cap, "replacement", 2)
        assert caps.require_effect_authority(cap, "replacement", 2) == value["authorization_digest"]
        clock.advance(5)
        with pytest.raises(ControlIntegrityError, match="cannot be acquired"):
            caps.acquire(cap, "third", expected_epoch=2, lease_seconds=5)
        with pytest.raises(ControlIntegrityError, match="expired"):
            caps.require_effect_authority(cap, "replacement", 2)
    finally:
        coordinator.close()


@pytest.mark.parametrize("fails", [False, True])
def test_trusted_target_port_has_fenced_started_and_finished_boundary(root, fails):
    coordinator, _, result = start(root)
    calls = []
    locator = result["result"]["run_locator"]
    run = root / locator["case_id"] / locator["run_id"]

    class Target:
        def invoke(self, identity):
            records = parse_ledger((run / "execution_history.jsonl").read_bytes()).values
            assert records[-1]["event"] == "started"
            calls.append(identity)
            if fails:
                raise RuntimeError("synthetic target failure")
            return TargetOutcome("succeeded", {"current_artifact_ids": {}})

    try:
        leases = InvocationLeases(coordinator)
        capability = result["result"]["capability_id"]
        leases.acquire(capability, "consumer", expected_epoch=0, lease_seconds=5)
        if fails:
            with pytest.raises(RuntimeError, match="synthetic target failure"):
                leases.invoke(capability, "consumer", 1, Target())
        else:
            leases.invoke(capability, "consumer", 1, Target())
        assert len(calls) == 1
        value = leases.get(capability)[1]
        assert value["state"] == "finished"
        records = parse_ledger((run / "execution_history.jsonl").read_bytes()).values
        assert records[-1]["event"] == "finished"
        assert records[-1]["status"] == ("failed" if fails else "succeeded")
        validate_run_root(run, manifest=value["completion_intent"]["manifest"], projection=value["completion_intent"]["projection"])
        with pytest.raises(ControlIntegrityError):
            leases.invoke(capability, "consumer", 1, Target())
        assert len(calls) == 1
        before = leases.get(capability)
        leases.publish_completion(capability, "consumer", 1)
        assert leases.get(capability) == before
    finally:
        coordinator.close()


def test_uncommitted_capability_cannot_acquire_invocation_lease(root):
    def stop(name, side, value):
        if name == "control.start_run.not_applicable.result_committed" and side == "before":
            raise RuntimeError("before result activation")

    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=stop)
    try:
        with pytest.raises(RuntimeError, match="activation"):
            ControlPlane(coordinator, worker_id="worker").start_run(request(), actor=ACTOR)
        operation = coordinator.lookup_key("public_control", "start-key")
        assert operation["phase"] == "invocation_capability_prepared"
        with pytest.raises(ControlIntegrityError, match="not been activated"):
            InvocationLeases(coordinator).acquire("capability_" + operation["operation_id"], "consumer", expected_epoch=0, lease_seconds=5)
    finally:
        coordinator.close()


@pytest.mark.parametrize("kind", ["root_input", "serializer", "metadata_owner", "metadata_duplicate", "payload"])
def test_invocation_rejects_tampered_sources_without_dispatch(root, kind):
    coordinator, _, result = start(root)
    try:
        locator = result["result"]["run_locator"]
        run = root / locator["case_id"] / locator["run_id"]
        cap = result["result"]["capability_id"]
        leases = InvocationLeases(coordinator)
        before = leases.get(cap)
        if kind == "root_input":
            (run / "root_goal.json").write_bytes(b"{}")
        else:
            database = sqlite3.connect(run / "checkpoints/graph_checkpoints.sqlite")
            try:
                if kind == "serializer":
                    database.execute("UPDATE checkpoints SET type='pickle'")
                elif kind == "metadata_owner":
                    database.execute("UPDATE checkpoints SET metadata=?", (b'{"operation_id":"different"}',))
                elif kind == "metadata_duplicate":
                    database.execute("UPDATE checkpoints SET metadata=?", (b'{"source":"input","source":"input"}',))
                else:
                    database.execute("UPDATE checkpoints SET checkpoint=?", (b'{}',))
                database.commit()
            finally:
                database.close()
        with pytest.raises(ControlIntegrityError):
            leases.acquire(cap, "consumer", expected_epoch=0, lease_seconds=5)
        assert leases.get(cap) == before
        assert len(parse_ledger((run / "execution_history.jsonl").read_bytes()).values) == 7
    finally:
        coordinator.close()


def test_live_invocation_renewal_keeps_original_deadline(root):
    clock = FakeClock(100, 0)
    coordinator, _, result = start(root, clock=clock)
    try:
        leases = InvocationLeases(coordinator)
        cap = result["result"]["capability_id"]
        lease = leases.acquire(cap, "consumer", expected_epoch=0, lease_seconds=5)
        clock.advance(4)
        leases.start_intent(cap, "consumer", 1)
        leases.publish_started(cap, "consumer", 1)
        extended = leases.renew(cap, "consumer", 1, lease_seconds=1000)
        assert extended["deadline"] == lease["deadline"] == extended["expires_at"] == 30
        with pytest.raises(ControlIntegrityError, match="Stale"):
            leases.renew(cap, "other", 1, lease_seconds=5)
        clock.advance(26)
        with pytest.raises(ControlIntegrityError, match="expired"):
            leases.renew(cap, "consumer", 1, lease_seconds=5)
    finally:
        coordinator.close()


@pytest.mark.parametrize("action", ["start_intent", "start_encoding", "renew", "effect"])
def test_invocation_expiry_during_validation_cannot_commit_or_authorize(root, monkeypatch, action):
    import lqcd_agent.control.capabilities as implementation

    clock = FakeClock(100, 0)
    coordinator, _, result = start(root, clock=clock)
    try:
        leases = InvocationLeases(coordinator)
        cap = result["result"]["capability_id"]
        leases.acquire(cap, "consumer", expected_epoch=0, lease_seconds=5)
        if action == "effect":
            leases.start_intent(cap, "consumer", 1)
            leases.publish_started(cap, "consumer", 1)
        before = leases.get(cap)
        locator = result["result"]["run_locator"]
        ledger = root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl"
        previous = ledger.read_bytes()
        name = "verify_checkpoint" if action == "effect" else "append_record_bytes" if action == "start_encoding" else "validate_run_root"
        original = getattr(implementation, name)

        def delayed(*args, **kwargs):
            value = original(*args, **kwargs)
            clock.advance(6)
            return value

        with monkeypatch.context() as patch:
            patch.setattr(implementation, name, delayed)
            with pytest.raises(ControlIntegrityError, match="expired"):
                if action == "renew":
                    leases.renew(cap, "consumer", 1, lease_seconds=10)
                elif action == "effect":
                    leases.require_effect_authority(cap, "consumer", 1)
                else:
                    leases.start_intent(cap, "consumer", 1)
        assert leases.get(cap) == before
        assert ledger.read_bytes() == previous
        if action != "effect":
            replacement = leases.acquire(cap, "replacement", expected_epoch=1, lease_seconds=5)
            assert replacement["invocation_epoch"] == 2
            assert replacement["started_intent"] is None
        else:
            with pytest.raises(ControlIntegrityError, match="cannot be acquired again"):
                leases.acquire(cap, "replacement", expected_epoch=1, lease_seconds=5)
    finally:
        coordinator.close()


@pytest.mark.parametrize("elapsed", [6, 30])
def test_invocation_acquisition_accounts_for_validation_elapsed_time(root, monkeypatch, elapsed):
    import lqcd_agent.control.capabilities as implementation

    clock = FakeClock(100, 0)
    coordinator, _, result = start(root, clock=clock)
    try:
        leases = InvocationLeases(coordinator)
        cap = result["result"]["capability_id"]
        before = leases.get(cap)
        original = implementation.validate_run_root

        def delayed(*args, **kwargs):
            value = original(*args, **kwargs)
            clock.advance(elapsed)
            return value

        monkeypatch.setattr(implementation, "validate_run_root", delayed)
        if elapsed == 30:
            with pytest.raises(ControlIntegrityError, match="deadline elapsed"):
                leases.acquire(cap, "consumer", expected_epoch=0, lease_seconds=5)
            assert leases.get(cap) == before
        else:
            acquired = leases.acquire(cap, "consumer", expected_epoch=0, lease_seconds=5)
            assert acquired["updated_at"]["monotonic_seconds"] == elapsed
            assert acquired["expires_at"] == elapsed + 5
            assert acquired["deadline"] == 30
    finally:
        coordinator.close()


def test_two_process_invocation_claim_has_one_winner(root):
    coordinator, _, result = start(root)
    capability_id = result["result"]["capability_id"]
    coordinator.close()
    context = multiprocessing.get_context("spawn")
    workers = []
    try:
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=invocation_client, args=(child, str(root), capability_id, "claim"))
            process.start()
            child.close()
            workers.append((process, parent))
        for _, pipe in workers:
            assert pipe.poll(20) and pipe.recv() == "ready"
        for _, pipe in workers:
            pipe.send("go")
        outcomes = []
        for process, pipe in workers:
            assert pipe.poll(20)
            outcomes.append(pipe.recv()[0])
            process.join(20)
            assert process.exitcode == 0
        assert sorted(outcomes) == ["acquired", "rejected"]
    finally:
        for process, pipe in workers:
            if process.is_alive():
                process.terminate()
                process.join(5)
            pipe.close()


@pytest.mark.parametrize("action", ["crash_intent", "crash_started"])
def test_started_invocation_crash_never_grants_reexecution(root, action):
    coordinator, _, result = start(root)
    capability_id = result["result"]["capability_id"]
    coordinator.close()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=invocation_client, args=(child, str(root), capability_id, action))
    try:
        process.start()
        child.close()
        assert parent.poll(20) and parent.recv() == "ready"
        parent.send("go")
        process.join(20)
        assert process.exitcode == 85
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        parent.close()
    coordinator = Coordinator(root, clock=FakeClock(110, 10))
    try:
        leases = InvocationLeases(coordinator)
        revision, value = leases.get(capability_id)
        assert value["state"] == "started" and value["started_intent"] is not None
        before = {str(path): path.read_bytes() for path in (root / "case").rglob("*") if path.is_file()}
        with pytest.raises(ControlIntegrityError, match="cannot be acquired again"):
            leases.acquire(capability_id, "replacement", expected_epoch=1, lease_seconds=5)
        assert leases.get(capability_id) == (revision, value)
        assert before == {str(path): path.read_bytes() for path in (root / "case").rglob("*") if path.is_file()}
    finally:
        coordinator.close()


@pytest.mark.parametrize("kind", ["partial", "extra", "missing", "changed_policy", "changed_index"])
def test_conflicting_bootstrap_prefix_never_resumes_normal_bootstrap(root, kind):
    def stop(name, side, value):
        if name == "control.start_run.not_applicable.checkpoint_committed" and side == "before":
            raise RuntimeError("checkpoint boundary")

    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=stop)
    try:
        plane = ControlPlane(coordinator, worker_id="worker")
        with pytest.raises(RuntimeError, match="checkpoint boundary"):
            plane.start_run(request(), actor=ACTOR)
        coordinator.observer = None
        operation = coordinator.lookup_key("public_control", "start-key")
        locator = operation["reservation"]["reserved_run_locator"]
        run = root / locator["case_id"] / locator["run_id"]
        if kind == "partial":
            path = run / "execution_history.jsonl"
            path.write_bytes(path.read_bytes() + b'{"partial":')
        elif kind == "extra":
            (run / "unexpected.json").write_bytes(b"{}")
        elif kind == "missing":
            (run / "artifact_history.jsonl").unlink()
        elif kind == "changed_policy":
            (run / "budget_policy.json").write_bytes(b"{}")
        else:
            (run / "artifact_index.json").write_bytes(b"{}")
        prior = (run / "execution_history.jsonl").read_bytes()
        result = plane.start_run(request(), actor=ACTOR)
        assert result["operation_status"] == "failed"
        if kind == "extra":
            assert result["terminal_closure"] == "committed" and result["run_status"] == "failed"
            assert (run / "execution_history.jsonl").read_bytes().startswith(prior)
        else:
            assert result["terminal_closure"] == "unavailable" and result["run_status"] is None
            assert (run / "execution_history.jsonl").read_bytes() == prior
        assert coordinator.get(operation["operation_id"])["phase"] == "running_lifecycle_recorded"
        assert coordinator.connection.execute("SELECT count(*) FROM invocation_capabilities").fetchone()[0] == 0
    finally:
        coordinator.close()


@pytest.mark.parametrize("boundary", ["bootstrap_records_complete", "running_lifecycle_recorded", "checkpoint_committed"])
def test_appendable_bootstrap_prefix_can_close_failed_without_completing_bootstrap(root, boundary):
    def stop(name, side, value):
        if name == "control.start_run.not_applicable." + boundary and side == "before":
            raise RuntimeError("prefix boundary")

    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=stop)
    try:
        plane = ControlPlane(coordinator, worker_id="worker")
        with pytest.raises(RuntimeError, match="prefix boundary"):
            plane.start_run(request(), actor=ACTOR)
        coordinator.observer = None
        operation = coordinator.lookup_key("public_control", "start-key")
        locator = operation["reservation"]["reserved_run_locator"]
        run = root / locator["case_id"] / locator["run_id"]
        before = (run / "execution_history.jsonl").read_bytes()
        (run / "unexpected.json").write_bytes(b"{}")
        result = plane.start_run(request(), actor=ACTOR)
        assert result["operation_status"] == "failed" and result["terminal_closure"] == "committed"
        assert result["run_status"] == "failed"
        records = parse_ledger((run / "execution_history.jsonl").read_bytes()).values
        assert records[-1]["to_status"] == "failed"
        assert (run / "execution_history.jsonl").read_bytes().startswith(before)
        assert coordinator.connection.execute("SELECT count(*) FROM invocation_capabilities").fetchone()[0] == 0
        assert plane.start_run(request(), actor=ACTOR) == result
    finally:
        coordinator.close()


@pytest.mark.parametrize("corruption", ["partial", "extra_file"])
def test_bootstrap_integrity_failure_has_durable_unique_terminal_owner(root, corruption):
    def stop(name, side, value):
        if name == "control.start_run.not_applicable.invocation_capability_prepared" and side == "before":
            raise RuntimeError("before capability")

    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=stop)
    try:
        plane = ControlPlane(coordinator, worker_id="worker")
        with pytest.raises(RuntimeError, match="before capability"):
            plane.start_run(request(), actor=ACTOR)
        coordinator.observer = None
        operation = coordinator.lookup_key("public_control", "start-key")
        locator = operation["reservation"]["reserved_run_locator"]
        run = root / locator["case_id"] / locator["run_id"]
        ledger = run / "execution_history.jsonl"
        if corruption == "partial":
            ledger.write_bytes(ledger.read_bytes() + b'{"partial":')
        else:
            (run / "unexpected.json").write_bytes(b"{}")
        before = ledger.read_bytes()
        result = plane.start_run(request(), actor=ACTOR)
        assert result["operation_status"] == "failed"
        assert result["publication_status"] != "materialization_pending"
        assert result["operation_phase"] == operation["phase"]
        assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 1
        assert result["terminal_closure"] == ("unavailable" if corruption == "partial" else "committed")
        assert result["run_status"] == (None if corruption == "partial" else "failed")
        if corruption == "partial":
            assert ledger.read_bytes() == before
        else:
            records = parse_ledger(ledger.read_bytes()).values
            assert records[-1]["to_status"] == "failed"
            assert records[-2]["event"] == "abandoned"
            assert sum(row["record_type"] == "run_lifecycle" and row["to_status"] == "failed" for row in records) == 1
        frozen = ledger.read_bytes()
        assert plane.start_run(request(), actor=ACTOR) == result
        assert ledger.read_bytes() == frozen
        assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 2
    finally:
        coordinator.close()


@pytest.mark.parametrize("phase", list(operation_variant("start_run", "not_applicable")["phases"])[1:])
def test_start_each_phase_recovers_in_fresh_process(root, phase):
    _crash_then_continue(root, ("control.start_run.not_applicable." + phase, "after"))


@pytest.mark.parametrize("phase", list(operation_variant("close_run", "not_applicable")["phases"])[1:])
@pytest.mark.parametrize("side", ["before", "after"])
def test_bootstrap_failure_closure_recovers_each_phase_in_fresh_process(root, phase, side):
    def stop(name, boundary_side, value):
        if name == "control.start_run.not_applicable.invocation_capability_prepared" and boundary_side == "before":
            raise RuntimeError("before capability")

    coordinator = Coordinator(root, clock=FakeClock(100, 0), observer=stop)
    try:
        with pytest.raises(RuntimeError, match="before capability"):
            ControlPlane(coordinator, worker_id="first").start_run(request(), actor=ACTOR)
        operation_id = coordinator.lookup_key("public_control", "start-key")["operation_id"]
        locator = coordinator.get(operation_id)["reservation"]["reserved_run_locator"]
        (root / locator["case_id"] / locator["run_id"] / "unexpected.json").write_bytes(b"{}")
    finally:
        coordinator.close()
    context = multiprocessing.get_context("spawn")
    for crash in (True, False):
        parent, child = context.Pipe()
        point = ("control.close_run.not_applicable." + phase, side) if crash else None
        process = context.Process(target=start_client, args=(child, str(root), point))
        try:
            process.start()
            child.close()
            if not crash:
                assert parent.poll(20)
                result = parent.recv()
                assert result["operation_id"] == operation_id and result["operation_status"] == "failed"
                assert result["terminal_closure"] == "committed" and result["run_status"] == "failed"
            process.join(20)
            assert process.exitcode == (84 if crash else 0)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
    coordinator = Coordinator(root, clock=FakeClock(140, 40))
    try:
        assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 2
        assert coordinator.connection.execute("SELECT count(*) FROM run_terminal_closure").fetchone()[0] == 1
    finally:
        coordinator.close()


@pytest.mark.parametrize("record", range(1, 8))
def test_start_each_durable_ledger_prefix_recovers_in_fresh_process(root, record):
    _crash_then_continue(root, ("bootstrap.execution_history.jsonl.file_sync", "after"), record)


def _crash_then_continue(root, crash_boundary, occurrence=1):
    context = multiprocessing.get_context("spawn")
    operation_id = None
    for crash in (True, False):
        parent, child = context.Pipe()
        process = context.Process(target=start_client, args=(child, str(root), crash_boundary if crash else None, occurrence))
        try:
            process.start()
            child.close()
            if not crash:
                assert parent.poll(20)
                result = parent.recv()
                assert result["operation_status"] == "committed" and result["operation_id"] == operation_id
                assert result["lease_epoch"] == 2
            process.join(20)
            assert process.exitcode == (84 if crash else 0)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
        coordinator = Coordinator(root, clock=FakeClock(140, 40))
        try:
            operation = coordinator.lookup_key("public_control", "start-key")
            operation_id = operation["operation_id"]
            assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 1
            if not crash:
                snap = coordinator.snapshot(operation_id)
                locator = operation["result"]["run_locator"]
                run = root / locator["case_id"] / locator["run_id"]
                verify_checkpoint(run, snap["manifest"])
                validate_run_root(run, manifest=snap["manifest"])
                assert (run / "execution_history.jsonl").read_bytes() == b"".join(canonical_bytes(r) + b"\n" for r in snap["records"])
        finally:
            coordinator.close()
