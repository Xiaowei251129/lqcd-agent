"""B02C01 exercises real legacy bytes through the public child control entry."""
from harness.temporary import mkdtemp
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
import json
import multiprocessing

import pytest

from lqcd_agent.control.children import ForkRunRequest, ReplayRunRequest, validate_source_fingerprint
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.interfaces import ActorContext, ControlPlane, StartRunRequest
from lqcd_agent.control.pause import ResumeRunRequest, runtime_fingerprint, validate_fingerprint
from lqcd_agent.control.records import validate_record
from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from lqcd_agent.graph.state import initialize_state, save_graph_state
from helpers.process_client import child_client


MISSING = {"availability": "not_recorded", "reason": "legacy_schema_0_2"}


@pytest.fixture
def legacy_control():
    output = Path(mkdtemp(prefix="lqcd-agent-b02c01-legacy-", dir="/private/tmp"))
    config = output / "_generated_case_configs/case.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"case_id": "case", "physics_goal": "synthetic", "data": "synthetic"}, indent=2) + "\n")
    root = output / "case/legacy"
    state = initialize_state(case_id="case", run_id="legacy", user_goal="synthetic", case_config_path=str(config), output_dir=str(root))
    save_graph_state(state)
    inputs = {"root_goal": {"goal": "synthetic"}, "input_snapshot": json.loads(config.read_text())}
    coordinator = Coordinator(output, clock=FakeClock(100, 0))
    plane = ControlPlane(coordinator, worker_id="worker")
    actor = ActorContext("operator", "human", ("control.internal", "fork", "policy.select", "replay", "resume", "start"))
    request = ReplayRunRequest({"case_id": "case", "run_id": "legacy"}, "legacy-replay", digest(inputs))
    try:
        yield coordinator, plane, actor, request, root, config
    finally:
        coordinator.close()


def bytes_in(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def child_records(coordinator, result):
    locator = result["result"]["run_locator"]
    return parse_ledger((coordinator.root / locator["case_id"] / locator["run_id"] / "execution_history.jsonl").read_bytes()).values


def test_real_legacy_replay_preserves_source_and_records_historical_absence(legacy_control):
    coordinator, plane, actor, request, root, config = legacy_control
    before = bytes_in(root)
    config_before = config.read_bytes()
    result = plane.replay_run(request, actor=actor)
    assert result["operation_status"] == "committed"
    records = child_records(coordinator, result)
    assert len(records) == 8 and records[0]["schema_version"] == "0.4"
    lineage = records[1]
    assert lineage["source_runtime_fingerprint"] == MISSING
    assert lineage["source_snapshot_proof"]["runtime_fingerprint"] == MISSING
    assert lineage["target_runtime_fingerprint"] == runtime_fingerprint()
    assert lineage["source_snapshot_proof"]["source_control_revision_proof"] == "legacy_control_revision_not_applicable"
    assert records[2]["payload"]["policy"]["profile_id"] == "balanced_v1"
    assert records[3]["payload"]["decision"] == "allow" and records[4]["record_type"] == "cycle"
    assert records[6]["source_node"] == "START"
    operation = coordinator.get(result["operation_id"])
    classification = operation["reservation"]["source_policy_classification_proof"]
    assert classification["classification"] == "pre_a06"
    assert classification["authoritative_policy_absence_proof"]["source_ledger_bytes_digest"] == sha256(before["execution_history.jsonl"]).hexdigest()
    assert plane.replay_run(request, actor=actor) == result
    with pytest.raises(ControlIntegrityError, match="Same-key"):
        plane.replay_run(replace(request, source_root_input_digest="0" * 64), actor=actor)
    assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 1
    assert bytes_in(root) == before and config.read_bytes() == config_before


@pytest.mark.parametrize("fault", ["goal", "missing_goal", "goal_digest", "state_run", "run_identity", "missing_state",
                                  "config", "missing_config", "missing_config_flag", "config_digest", "config_array", "empty_config",
                                  "duplicate_json", "nan", "unknown_fingerprint", "mixed_schema", "policy_record", "policy_file",
                                  "foreign_path", "symlink", "request_digest", "duplicate_run", "unknown_reference"])
def test_invalid_legacy_source_rejects_without_reservation(legacy_control, fault):
    coordinator, plane, actor, request, root, config = legacy_control
    ledger = root / "execution_history.jsonl"
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    created = records[0]
    state_path = root / "graph_state.json"
    state = json.loads(state_path.read_text())
    if fault == "goal":
        state["user_goal"] = "changed"
    elif fault == "missing_goal":
        state.pop("user_goal")
    elif fault == "goal_digest":
        created["root_goal_reference"]["sha256"] = "0" * 64
    elif fault == "state_run":
        state["run_id"] = "foreign"
    elif fault == "run_identity":
        created["run_id"] = "foreign"
    elif fault == "config":
        config.write_text('{"changed":true}')
    elif fault == "missing_config":
        config.unlink()
    elif fault == "missing_config_flag":
        created["input_snapshot_reference"]["exists"] = False
    elif fault == "config_digest":
        created["input_snapshot_reference"]["sha256"] = "0" * 64
    elif fault in ("config_array", "empty_config", "duplicate_json", "nan"):
        config.write_text({"config_array": "[]", "empty_config": "{}", "duplicate_json": '{"x":1,"x":2}', "nan": '{"x":NaN}'}[fault])
        created["input_snapshot_reference"]["sha256"] = sha256(config.read_bytes()).hexdigest()
    elif fault == "unknown_fingerprint":
        created["runtime_fingerprint"] = MISSING
    elif fault == "mixed_schema":
        records[-1]["schema_version"] = "0.4"
    elif fault == "policy_record":
        records[-1]["record_type"] = "budget"
    elif fault == "policy_file":
        (root / "budget_policy.json").write_text('{}')
    elif fault == "foreign_path":
        outside = coordinator.root / "raw_data/secret.json"
        outside.parent.mkdir()
        outside.write_bytes(config.read_bytes())
        created["input_snapshot_reference"]["path"] = str(outside)
    elif fault == "symlink":
        link = config.with_name("alias.json")
        link.symlink_to(config)
        created["input_snapshot_reference"]["path"] = str(link)
    elif fault == "request_digest":
        request = replace(request, source_root_input_digest="0" * 64)
    elif fault == "duplicate_run":
        records.append(deepcopy(created))
    elif fault == "unknown_reference":
        created["root_goal_reference"]["reference"] = "root_goal.json"
    state_path.write_text(json.dumps(state))
    if fault == "missing_state":
        state_path.unlink()
    ledger.write_text("".join(json.dumps(row) + "\n" for row in records))
    before = bytes_in(root)
    with pytest.raises(ControlIntegrityError):
        plane.replay_run(request, actor=actor)
    assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 0
    assert list(root.parent.iterdir()) == [root]
    assert bytes_in(root) == before


@pytest.mark.parametrize("value", [None, {}, "", {"availability": "not_recorded"},
                                 {"availability": "not_recorded", "reason": "unknown"}, {**MISSING, "build": "current"}])
def test_missing_fingerprint_value_is_closed(value):
    with pytest.raises(ControlIntegrityError):
        validate_source_fingerprint(value, "0.2", "replay_of")


@pytest.mark.parametrize("schema,reason", [("0.2", "fork_of"), ("0.3", "replay_of"), ("0.4", "replay_of"), ("0.4", "fork_of")])
def test_historical_absence_cannot_authorize_other_sources(schema, reason):
    with pytest.raises(ControlIntegrityError):
        validate_source_fingerprint(MISSING, schema, reason)
    with pytest.raises(ControlIntegrityError):
        validate_fingerprint(MISSING)


@pytest.mark.parametrize("fault", ["source", "target", "source_schema", "fork", "unknown_missing_field"])
def test_lineage_rejects_missing_fingerprint_cross_wiring(legacy_control, fault):
    coordinator, plane, actor, request, root, config = legacy_control
    lineage = deepcopy(child_records(coordinator, plane.replay_run(request, actor=actor))[1])
    if fault == "source":
        lineage["source_runtime_fingerprint"] = runtime_fingerprint()
    elif fault == "target":
        lineage["target_runtime_fingerprint"] = MISSING
    elif fault == "source_schema":
        lineage["source_snapshot_proof"]["source_schema"] = "0.3"
        lineage["source_snapshot_proof"]["source_control_revision_proof"] = "versioned_control_revision_not_consumed_for_root_replay"
    elif fault == "fork":
        lineage["creation_reason"] = "fork_of"
    else:
        lineage["source_snapshot_proof"]["runtime_fingerprint"]["extra"] = True
    lineage["lineage_snapshot_digest"] = digest(lineage["source_snapshot_proof"])
    with pytest.raises(ControlIntegrityError):
        validate_record(lineage)


def test_legacy_fork_and_resume_remain_rejected(legacy_control):
    coordinator, plane, actor, request, root, config = legacy_control
    before = bytes_in(root)
    with pytest.raises(ControlIntegrityError, match="replay only"):
        plane.fork_run(ForkRunRequest(request.source_run_locator, "fork", "0" * 64), actor=actor)
    payload = {"action": "abandon_and_halt"}
    with pytest.raises(ControlIntegrityError):
        plane.resume_run(ResumeRunRequest(request.source_run_locator, "pause_000001", "resume", "recovery_decision", payload, digest(payload)), actor=actor)
    assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 0
    assert bytes_in(root) == before


@pytest.mark.parametrize("phase", ["source_snapshot_committed", "child_lineage_recorded", "child_checkpoint_committed", "invocation_capability_prepared"])
@pytest.mark.parametrize("side", ["before", "after"])
def test_legacy_child_crash_restarts_same_operation(legacy_control, phase, side):
    coordinator, plane, actor, request, root, config = legacy_control
    before = bytes_in(root)
    context = multiprocessing.get_context("spawn")
    def run(boundary, elapsed):
        parent, child = context.Pipe()
        process = context.Process(target=child_client, args=(child, str(coordinator.root), asdict(request), False, boundary), kwargs={"elapsed": elapsed})
        try:
            process.start()
            child.close()
            process.join(20)
            assert not process.is_alive()
            if boundary:
                assert process.exitcode == 88
            else:
                assert process.exitcode == 0 and parent.poll(2)
                return parent.recv()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
    run(("control.replay_run.not_applicable." + phase, side), 0)
    old = coordinator.lookup_key("public_control", request.idempotency_key)
    result = run(None, 40)
    assert result["operation_status"] == "committed" and result["operation_id"] == old["operation_id"]
    assert result["result"]["run_locator"] == old["reservation"]["reserved_child_run_locator"]
    assert child_records(coordinator, result)[1]["source_runtime_fingerprint"] == MISSING
    assert bytes_in(root) == before


def test_yaml_legacy_case_uses_existing_scalar_and_list_semantics(legacy_control):
    coordinator, plane, actor, request, root, config = legacy_control
    yaml = config.with_suffix(".yaml")
    yaml.write_text('case_id: case\nphysics_goal: synthetic\ncommands:\n  - mock:example\ncount: 2\n')
    ledger = root / "execution_history.jsonl"
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    records[0]["input_snapshot_reference"].update(path=str(yaml), sha256=sha256(yaml.read_bytes()).hexdigest())
    ledger.write_text("".join(json.dumps(row) + "\n" for row in records))
    inputs = {"root_goal": {"goal": "synthetic"}, "input_snapshot": {"case_id": "case", "physics_goal": "synthetic", "commands": ["mock:example"], "count": 2}}
    result = plane.replay_run(replace(request, source_root_input_digest=digest(inputs)), actor=actor)
    assert child_records(coordinator, result)[1]["source_snapshot_proof"]["immutable_root_input"] == inputs


def test_versioned_missing_policy_cannot_be_downgraded(legacy_control):
    coordinator, plane, actor, request, root, config = legacy_control
    inputs = {"root_goal": {"goal": "new"}, "input_snapshot": {"kind": "synthetic"}}
    source = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start"), actor=actor)
    locator = source["result"]["run_locator"]
    versioned = coordinator.root / locator["case_id"] / locator["run_id"]
    (versioned / "budget_policy.json").unlink()
    with pytest.raises(ControlIntegrityError):
        plane.replay_run(ReplayRunRequest(locator, "versioned-replay", digest(inputs)), actor=actor)
    assert coordinator.connection.execute("SELECT count(*) FROM control_operations").fetchone()[0] == 1


@pytest.mark.parametrize("schema", ["0.3", "0.4"])
def test_versioned_source_fingerprint_is_historical_not_current(schema):
    fingerprint = runtime_fingerprint()
    fingerprint.update(execution_schema=schema, application_build="a" * 64)
    validate_source_fingerprint(fingerprint, schema, "replay_of")
    with pytest.raises(ControlIntegrityError, match="schema mismatch"):
        validate_source_fingerprint(fingerprint, "0.4" if schema == "0.3" else "0.3", "replay_of")


@pytest.mark.parametrize("reason", ["replay", "fork"])
def test_historical_legacy_child_can_be_a_root_replay_source(legacy_control, reason):
    coordinator, plane, actor, request, root, config = legacy_control
    source_root = coordinator.root / "case/legacy_child"
    state = initialize_state(case_id="case", run_id="legacy_child", user_goal="synthetic", case_config_path=str(config),
                             output_dir=str(source_root), parent_run_id="legacy", run_creation_reason=reason)
    save_graph_state(state)
    result = plane.replay_run(replace(request, source_run_locator={"case_id": "case", "run_id": "legacy_child"}), actor=actor)
    assert child_records(coordinator, result)[0]["parent_run_id"] == "legacy_child"


def test_versioned_replay_preserves_source_build_across_target_build_change(legacy_control, monkeypatch):
    from lqcd_agent.control import children
    coordinator, plane, actor, request, root, config = legacy_control
    inputs = {"root_goal": {"goal": "versioned"}, "input_snapshot": {"kind": "synthetic"}}
    source = plane.start_run(StartRunRequest("case", inputs, digest(inputs), "start"), actor=actor)
    original = runtime_fingerprint()
    target = {**original, "application_build": "b" * 64}
    monkeypatch.setattr(children, "runtime_fingerprint", lambda: target)
    result = plane.replay_run(ReplayRunRequest(source["result"]["run_locator"], "replay-versioned", digest(inputs)), actor=actor)
    lineage = child_records(coordinator, result)[1]
    assert lineage["source_runtime_fingerprint"] == original
    assert lineage["target_runtime_fingerprint"] == target
