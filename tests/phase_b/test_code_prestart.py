"""Real durable prestart publication, without Backend or Bundle coverage."""
from copy import deepcopy
from functools import partial
import multiprocessing
import os
from pathlib import Path

import pytest

from harness.pytest_evidence import observe, production_hook
from lqcd_agent.code_agent.containment import DeterministicContainment
from lqcd_agent.code_agent.external_operation import CodeWatchdog
from lqcd_agent.code_agent.fake_backend import FakeCodingBackend
from lqcd_agent.code_agent.prestart import CodePrestart
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.operations import ExternalControl
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from helpers.code_workspace import immutable_base_repository
from test_b03_task_trace_boundary import task_trace_witness


@pytest.fixture
def prestart():
    repository, base = immutable_base_repository()
    witness = task_trace_witness(base)
    witness["base_repository"] = str(repository)
    root = Path(witness["trace"]["proof"]["output_roots"][0]["path"])
    coordinator = Coordinator(root.parent.parent, clock=FakeClock(100, 0))
    service = CodePrestart(coordinator, witness["task"]["producer_operation_id"], "host", 1)
    try:
        yield service, root, witness
    finally:
        coordinator.close()


def aggregate(service, witness):
    return service.reserve_aggregate(maximum_charge={"llm_calls": 1, "tool_calls": 1,
        "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10,
        config_digest=digest("config"))


def test_prestart_commits_one_exact_aggregate_and_core_before_any_workspace(prestart):
    service, root, witness = prestart
    before = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert service.commit_task(witness["task"]) == witness["task"]
    assert service.commit_manifest(witness["manifest"]) == witness["manifest"]
    reservation = aggregate(service, witness)
    core = service.commit_core()
    assert service.commit_task(witness["task"]) == witness["task"]
    assert service.commit_manifest(witness["manifest"]) == witness["manifest"]
    assert aggregate(service, witness) == reservation
    assert service.commit_core() == core
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    assert rows == [*before, service.publish_setup(), reservation]
    assert core["reservation_digest"] == digest(reservation)
    external = loads(service.coordinator.connection.execute("SELECT value FROM external_operations").fetchone()[0])
    assert external["operation_phase"] == "core_contract_committed" and external["pause_id"] is None
    assert external["operation_contract_digest"] == core["operation_contract_digest"]
    assert not any(r["record_type"] == "attempt" and r["attempt_id"] == witness["task"]["attempt_id"] and r["event"] == "started" for r in rows)
    assert not any(p.name == witness["manifest"]["workspace_id"] for p in service.coordinator.root.rglob("*"))
    observe("b03-construction-prestart", {"kind": "boolean", "value": True},
            sorted(["acyclic_prestart_order", "one_aggregate_reservation", "idempotent_publication"]))


@pytest.mark.parametrize("mutation", ["heads", "evidence", "producer", "backend", "admission"])
def test_prestart_rejects_rehashed_foreign_authority_without_publication(prestart, mutation):
    service, root, witness = prestart
    task = deepcopy(witness["task"])
    if mutation == "heads":
        task["execution_head"] = digest("wrong")
    elif mutation == "evidence":
        task["evidence"][0]["sha256"] = digest("wrong")
    elif mutation == "producer":
        task["producer_operation_id"] = "other_producer"
    elif mutation == "backend":
        task["coding_backend_kind"] = "unregistered_backend"
    else:
        task["budget_envelope_digest"] = digest("allow")
    task["task_digest"] = digest({k: v for k, v in task.items() if k != "task_digest"})
    before = (root / "execution_history.jsonl").read_bytes()
    with pytest.raises(ControlIntegrityError):
        service.commit_task(task)
    assert (root / "execution_history.jsonl").read_bytes() == before
    assert not (root / "code_agent_control").exists()
    observe("b03-construction-source-authority", {"kind": "boolean", "value": True},
            sorted(["source_identity_checked", "foreign_authority_rejected", "no_publication"]))


def test_prestart_budget_excess_has_no_reservation_or_workspace(prestart):
    service, root, witness = prestart
    service.commit_task(witness["task"])
    service.commit_manifest(witness["manifest"])
    before = (root / "execution_history.jsonl").read_bytes()
    with pytest.raises(ControlIntegrityError):
        service.reserve_aggregate(maximum_charge={"llm_calls": 999, "tool_calls": 1,
            "verification_commands": 0, "active_seconds": 10}, timeout_seconds=10,
            config_digest=digest("config"))
    assert (root / "execution_history.jsonl").read_bytes() == before


def test_physical_workspace_is_fenced_after_core_and_never_recreated(prestart):
    service, root, witness = prestart
    with pytest.raises(ControlIntegrityError):
        service.materialize_workspace(witness["base_repository"])
    assert not (service.coordinator.root / "code_workspaces").exists()
    service.commit_task(witness["task"])
    service.commit_manifest(witness["manifest"])
    aggregate(service, witness)
    service.commit_core()
    proof = service.materialize_workspace(witness["base_repository"])
    assert service.materialize_workspace(witness["base_repository"]) == proof
    path = service.coordinator.root / "code_workspaces" / proof["workspace_id"]
    assert (path / "sample.py").read_bytes() == b"value = 1\n"
    (path / "sample.py").write_bytes(b"tampered\n")
    with pytest.raises(ControlIntegrityError):
        service.materialize_workspace(witness["base_repository"])
    assert (path / "sample.py").read_bytes() == b"tampered\n"


@pytest.mark.parametrize("fault", ["task", "manifest", "stale_epoch", "expired", "conflicting_task"])
def test_prestart_integrity_and_fencing_prevent_core_publication(prestart, fault):
    service, root, witness = prestart
    service.commit_task(witness["task"])
    service.commit_manifest(witness["manifest"])
    aggregate(service, witness)
    directory = root / "code_agent_control" / witness["task"]["attempt_id"]
    if fault in ("task", "manifest"):
        (directory / ("code_agent_task.json" if fault == "task" else "workspace_manifest.json")).write_bytes(b"{}")
    elif fault == "stale_epoch":
        service.epoch += 1
    elif fault == "expired":
        service.coordinator.clock.advance(11)
    else:
        changed = deepcopy(witness["task"])
        changed["task_summary"] = "Conflicting task"
        changed["task_digest"] = digest({k: v for k, v in changed.items() if k != "task_digest"})
        with pytest.raises(ControlIntegrityError, match="Conflicting"):
            service.commit_task(changed)
        assert service.commit_task(witness["task"]) == witness["task"]
        return
    with pytest.raises(ControlIntegrityError):
        service.commit_core()
    value = loads(service.coordinator.connection.execute("SELECT value FROM external_operations").fetchone()[0])
    assert value["operation_contract_digest"] is None and value["operation_phase"] == "reservation_committed"


def prestart_client(pipe, output, witness, cut, physical=False, hook_request=None, expect_rejection=False):
    coordinator = Coordinator(Path(output), clock=FakeClock(100, 0))
    def observer(name, side, value):
        if (name, side) == cut:
            os._exit(95)
    if hook_request is not None:
        observer.production_hooks = {cut: (partial(production_hook, hook_request["case_id"],
                                                   process_request=hook_request),)}
    coordinator.observer = observer
    service = CodePrestart(coordinator, witness["task"]["producer_operation_id"], "host", 1)
    try:
        try:
            service.commit_task(witness["task"])
            service.commit_manifest(witness["manifest"])
            aggregate(service, witness)
            core = service.commit_core()
            if physical:
                service.materialize_workspace(witness["base_repository"])
            assert not expect_rejection
            pipe.send(core)
        except ControlIntegrityError as error:
            if not expect_rejection:
                raise
            pipe.send({"rejected": str(error)})
    finally:
        coordinator.close()
        pipe.close()


@pytest.mark.parametrize("cut", [("external.task.file_sync", "after"), ("external.task_committed", "after"),
    ("external.unmaterialized_manifest.file_sync", "after"), ("external.workspace_manifest_committed", "after"),
    ("external.aggregate_reservation.file_sync", "after"), ("external.reservation_committed", "after"),
    ("external.immutable_core_cas", "after"), ("external.core_contract_committed", "after"),
    ("external.workspace_materialization", "after"), ("external.workspace_materialized", "after")])
def test_prestart_fresh_process_recovers_only_frozen_publication_suffix(prestart, cut):
    service, root, witness = prestart
    context = multiprocessing.get_context("spawn")
    core = None
    physical = cut[0] in ("external.workspace_materialization", "external.workspace_materialized")
    for boundary in (cut, None):
        parent, child = context.Pipe()
        process = context.Process(target=prestart_client, args=(child, str(service.coordinator.root), witness, boundary, physical))
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            assert process.exitcode == (95 if boundary else 0)
            if boundary is None:
                assert parent.poll(2)
                core = parent.recv()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
    rows = parse_ledger((root / "execution_history.jsonl").read_bytes()).values
    reserved = [r for r in rows if r["record_type"] == "budget" and r["event"] == "resource_reserved"]
    assert len(reserved) == 1 and core["reservation_digest"] == digest(reserved[0])
    if physical:
        proof = service.materialize_workspace(witness["base_repository"])
        assert proof["base_tree_digest"] == witness["manifest"]["base_tree_digest"]
    else:
        assert service.commit_core() == core


def test_expired_aggregate_recovery_rejects_changed_frozen_bytes_before_publication(prestart):
    service, root, witness = prestart
    service.commit_task(witness["task"])
    service.commit_manifest(witness["manifest"])
    coordinator = service.coordinator

    def observer(name, side, value):
        if (name, side) == ("external.aggregate_reservation", "before"):
            raise ControlIntegrityError("Injected aggregate publication cut")

    coordinator.observer = observer
    with pytest.raises(ControlIntegrityError, match="Injected aggregate"):
        aggregate(service, witness)
    coordinator.observer = None
    before_ledger = (root / "execution_history.jsonl").read_bytes()
    before_index = (root / "artifact_index.json").read_bytes()
    producer = service.producer
    with coordinator.transaction() as db:
        saved = ExternalControl(coordinator).read(db, producer)
        saved["prestart"]["aggregate"]["content"] += "{}\n"
        db.execute("UPDATE external_operations SET value=? WHERE external_operation_id=?",
                   (canonical_bytes(saved), producer))
    coordinator.clock = FakeClock(140, 40)
    backend = FakeCodingBackend(coordinator.root / "fake_backend")
    watchdog = CodeWatchdog(coordinator, backend, DeterministicContainment(coordinator.root / "containment"),
                            backend.read_receipt)
    with pytest.raises(ControlIntegrityError, match="Frozen aggregate source changed"):
        watchdog.enforce(producer)
    assert (root / "execution_history.jsonl").read_bytes() == before_ledger
    assert (root / "artifact_index.json").read_bytes() == before_index
    final = ExternalControl(coordinator).read(coordinator.connection, producer)
    assert final["operation_phase"] == "workspace_manifest_committed" and final["reservation_digest"] is None
    assert backend.lookup(producer)["status"] == "unknown"
