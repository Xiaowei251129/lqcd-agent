"""Production foundation probes, distinct from later durable runtime evidence."""
from harness.temporary import mkdtemp
from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
import json
from pathlib import Path

import pytest

from lqcd_agent.artifacts import registry
from lqcd_agent.control import budget
from lqcd_agent.control.clock import FakeClock, Timestamp, measure
from lqcd_agent.control.execution import append_record_bytes, parse_ledger, replay
from lqcd_agent.control.integrity import artifact_binding, validate_run_root
from lqcd_agent.control.projections import attach_checkpoint, bounded_projection, checkpoint_manifest
from lqcd_agent.control.records import build_record, parse_record, validate_record
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from lqcd_agent.graph.state import canonical_attempt_kind, validate_control_0_4_node_result

from harness.pytest_evidence import observe
from harness.trace import event, compare


DIGEST = "a" * 64
FIXED_ROOT = "/private/tmp/lqcd-agent-b01-construction/case/run"
POLICY = budget.policy("phase_b_test").value


class Ledger:
    def __init__(self, root=FIXED_ROOT):
        self.records = []
        self.clock = FakeClock(1000, 0)
        self.root = str(root)

    def add(self, kind, event, **fields):
        record = build_record(kind, event, run_id="run", case_id="case", event_index=len(self.records) + 1,
                              previous_execution_head=digest(self.records[-1]) if self.records else None,
                              artifact_head=None, artifact_event_index=0, timestamp=self.clock.now(), **fields).value
        self.records.append(record)
        self.clock.advance(1)
        return record

    def budget(self, event, **payload):
        index = sum(record["record_type"] == "budget" for record in self.records) + 1
        return self.add("budget", event, budget_event_id=f"budget_event_{index:06d}", budget_event_index=index,
                        policy_version="0.1", policy_digest=POLICY["policy_digest"], payload=payload)


def decision(proposal_id="bootstrap"):
    value = {"schema_version": "0.1", "proposal_id": proposal_id, "proposed_action": "route",
             "target_kind": "method_planner", "risk": "low", "fingerprint_digest": None, "occurrence": 0,
             "dimensions": {key: {"used": 0, "remaining": POLICY["limits"][key], "projected_after": 1}
                            for key in ("cycles_per_run", "work_attempts_per_run", "transitions_per_run")},
             "budget_grant_id": None, "decision": "allow", "reason_code": "bootstrap_capacity",
             "next_control_action": "bootstrap"}
    return {**value, "decision_digest": digest(value)}


def bootstrap(root=FIXED_ROOT):
    ledger = Ledger(root)
    ledger.add("run", "created", parent_run_id=None, creation_reason="root",
               root_goal_reference={"reference": "root_goal", "sha256": DIGEST},
               input_snapshot_reference={"reference": "input_snapshot", "sha256": DIGEST},
               canonical_output_root=str(root), checkpoint_thread_id="case:run", status="initializing",
               policy_version="0.1", policy_digest=POLICY["policy_digest"])
    ledger.budget("policy_initialized", policy=POLICY, policy_reference="budget_policy.json")
    ledger.budget("decision_recorded", **decision())
    ledger.add("cycle", "created", cycle_id="cycle_0001", cycle_index=1, parent_cycle_id=None,
               trigger_reason="initial", created_by_attempt_id=None, status="active")
    attempt(ledger, "scheduled")
    transition(ledger)
    lifecycle(ledger, "initializing", "running")
    return ledger


def attempt(ledger, event_name, *, identity=1, node="method_planner", status=None, **overrides):
    fields = {"cycle_id": "cycle_0001", "cycle_index": 1, "attempt_id": f"attempt_{identity:06d}",
              "attempt_index": identity, "parent_attempt_id": f"attempt_{identity-1:06d}" if identity > 1 else None,
              "attempt_kind": canonical_attempt_kind(node),
              "node_name": node, "attempt_trigger": "initial" if identity == 1 else "forward",
              "inbound_transition_id": f"transition_{identity:06d}",
              "status": status or {"scheduled": "scheduled", "started": "running", "finished": "succeeded", "abandoned": "abandoned"}[event_name],
              "input_references": {"current_artifact_ids": {}}, "output_references": {"current_artifact_ids": {}}, "error": None}
    fields.update(overrides)
    return ledger.add("attempt", event_name, **fields)


def transition(ledger, identity=1, node="method_planner", source=None):
    return ledger.add("transition", "committed", transition_id=f"transition_{identity:06d}", transition_index=identity,
                       source=source or "START", source_node=source or "START", source_cycle_id="cycle_0001" if source else None,
                       source_attempt_id=f"attempt_{identity-1:06d}" if source else None, route=node or "end", target_node=node,
                       target_cycle_id="cycle_0001" if node else None, target_attempt_id=f"attempt_{identity:06d}" if node else None,
                       target_attempt_kind=canonical_attempt_kind(node) if node else None, human_request_id=None, human_response_id=None, trigger_reason="initial" if not source else "forward",
                       reason="deterministic control fixture", fields={}, evidence_references={}, applied_state_update_keys=[],
                       applied_state_updates_sha256=digest({}), status="committed", committed_at=asdict(ledger.clock.now()))


def lifecycle(ledger, before, after, **overrides):
    fields = dict(from_status=before, to_status=after, reason_code="deterministic_boundary", operation_id="operation-start",
                  attempt_id=None, pause_id=None, budget_event_id="budget_event_000002")
    fields.update(overrides)
    return ledger.add("run_lifecycle", "transitioned", **fields)


def rechain(records):
    for index, record in enumerate(records, 1):
        record["event_index"] = index
        record["event_id"] = f"execution_event_{index:06d}"
        record["previous_execution_head"] = digest(records[index - 2]) if index > 1 else None
    return records


def observation(name, invariants, *, trace=None):
    if trace is not None and name != "LIFECYCLE":
        expected = Path(__file__).parent / f"expected_traces/b01_{name.lower().replace('-', '_')}.json"
        compare(trace, json.loads(expected.read_text()))
    observe("B01-" + name, {"kind": "boolean", "value": True}, sorted(invariants), trace)


def trajectory():
    ledger = bootstrap()
    attempt(ledger, "started")
    attempt(ledger, "finished", status="pending")
    result = replay(ledger.records)
    rows = []
    for index, record in enumerate(ledger.records, 1):
        prefix = replay(ledger.records[:index]).projection.value
        rows.append(event(record["record_type"] + ":" + record["event"], index=index, run_id=record["run_id"],
                          cycle_id=record.get("cycle_id"), attempt_id=record.get("attempt_id"),
                          transition_id=record.get("transition_id"), physical_node=record.get("node_name"),
                          attempt_kind=record.get("attempt_kind"), status=record.get("status"),
                          execution_head=prefix["execution_head"], artifact_head=record["artifact_head"],
                          policy_digest=record.get("policy_digest"), run_status=prefix["run_status"],
                          current_attempt_id=prefix["attempt_id"], cycle_count=prefix["cycle_index"],
                          attempt_count=prefix["attempt_index"], transition_count=prefix["transition_index"],
                          outcome="validated", owner="construction_replay"))
    assert result.projection.value["attempt_status"] == "pending"
    assert result.projection.value["run_status"] == "running"
    return {"schema_version": "0.1", "events": rows}


def test_identity():
    ledger = bootstrap()
    value = replay(ledger.records).projection.value
    assert (value["cycle_id"], value["attempt_id"], value["committed_transition_id"]) == (
        "cycle_0001", "attempt_000001", "transition_000001")
    for key, invalid in (("cycle_id", "cycle_1"), ("cycle_index", True), ("parent_attempt_id", "attempt_999999"),
                         ("attempt_kind", "code_agent"), ("run_id", "other"), ("attempt_index", 2)):
        records = deepcopy(ledger.records)
        records[4][key] = invalid
        with pytest.raises(ControlIntegrityError):
            replay(rechain(records))
    for record in ledger.records:
        assert parse_record(canonical_bytes(record)).value == record
        for change in (dict(record, unexpected=True), {key: val for key, val in record.items() if key != "case_id"}):
            with pytest.raises(ControlIntegrityError):
                validate_record(change)
    for field, value in (("record_type", []), ("event", {}), ("node_name", {})):
        with pytest.raises(ControlIntegrityError):
            validate_record({**ledger.records[4], field: value})
    observation("IDENTITY", ["canonical_identity", "closed_records", "run_nesting"])


def test_lifecycle():
    for prefix_length in (1, 2):
        failed = Ledger()
        failed.records = bootstrap().records[:prefix_length]
        failed.clock.advance(prefix_length)
        lifecycle(failed, "initializing", "failed", budget_event_id=None)
        assert replay(failed.records).projection.value["run_status"] == "failed"
        assert replay(failed.records).projection.value["attempt_index"] == 0
    ledger = bootstrap()
    attempt(ledger, "started")
    attempt(ledger, "finished", status="pending")
    state = replay(ledger.records).projection.value
    assert state["run_status"] == "running" and state["attempt_status"] == "pending"
    for record in (deepcopy(ledger.records[-1]), deepcopy(ledger.records[-2])):
        with pytest.raises(ControlIntegrityError):
            replay(rechain([*deepcopy(ledger.records), record]))
    lifecycle(ledger, "running", "halted")
    assert replay(ledger.records).projection.value["run_status"] == "halted"
    with pytest.raises(ControlIntegrityError):
        replay(rechain([*deepcopy(ledger.records), deepcopy(ledger.records[-1])]))
    trace = trajectory()
    expected = Path(__file__).parent / "expected_traces/b01_execution.json"
    compare(trace, json.loads(expected.read_text()))
    observation("LIFECYCLE", ["domain_control_orthogonal", "exact_once_lifecycle", "terminal_irreversible"], trace=trace)


def test_authority():
    state = replay(bootstrap().records).projection.value
    for field in ("run_id", "cycle_id", "attempt_id", "attempt_index", "committed_transition_id", "current_artifacts"):
        changed = {**state, field: "agent-selected"}
        with pytest.raises(ValueError, match="control-plane"):
            validate_control_0_4_node_result(state, changed)
    assert not any(hasattr(__import__("lqcd_agent.control.execution", fromlist=[name]), name)
                   for name in ("start_run", "commit_transition", "write_ledger"))
    observation("AUTHORITY", ["agent_identity_rejected", "no_durable_mutation"])


def test_global_head():
    records = bootstrap().records
    encoded = b""
    heads = []
    for record in records:
        encoded = append_record_bytes(encoded, record)
        heads.append(parse_ledger(encoded).projection.value["execution_head"])
    assert len(set(heads)) == len(records)
    assert heads == [digest(record) for record in records]
    for bad in (encoded[:-1], encoded + b"\n", encoded.replace(b'"run_id":"run"', b'"run_id":"other"', 1)):
        with pytest.raises(ControlIntegrityError):
            parse_ledger(bad)
    observation("HEAD-001", ["all_events_advance_head", "canonical_append_only"])


@pytest.fixture
def root_fixture():
    root = Path(mkdtemp(prefix="lqcd-agent-b01-", dir="/private/tmp"))
    ledger = bootstrap(root)
    execution = replay(ledger.records)
    index = {"schema_version": "0.1", "run_id": "run", "case_id": "case", "revision": 0, "last_event_id": None,
             "current": {slot: None for slot in registry.ARTIFACT_SLOTS}, "managed_projections": {},
             "execution_head": execution.projection.value["execution_head"], "artifact_head": None}
    core = bounded_projection(execution, artifact_index=index, artifact_head=None, artifact_event_index=0)
    manifest = checkpoint_manifest(execution, artifact_head=None, artifact_event_index=0, checkpoint_id="checkpoint_1",
                                   checkpoint_digest=DIGEST, state_digest=core.digest).value
    projection = attach_checkpoint(core, execution, manifest).value
    (root / "execution_history.jsonl").write_bytes(b"\n".join(execution.records) + b"\n")
    (root / "artifact_history.jsonl").write_bytes(b"")
    (root / "artifact_index.json").write_bytes(canonical_bytes(index))
    (root / "budget_policy.json").write_bytes(canonical_bytes(POLICY))
    return root, ledger, index, manifest, projection


def test_cross_heads(root_fixture):
    root, ledger, index, manifest, projection = root_fixture
    before = {file.name: file.read_bytes() for file in root.iterdir()}
    assert validate_run_root(root, manifest=manifest, projection=projection).value == projection
    assert before == {file.name: file.read_bytes() for file in root.iterdir()}
    for key, value in (("execution_head", digest(ledger.records[4])), ("attempt_id", None), ("attempt_index", 0),
                       ("checkpoint_head", DIGEST), ("case_id", "other")):
        changed = {**projection, key: value}
        with pytest.raises(ControlIntegrityError):
            validate_run_root(root, manifest=manifest, projection=changed)
    for key in projection:
        with pytest.raises(ControlIntegrityError):
            validate_run_root(root, manifest=manifest, projection={name: value for name, value in projection.items() if name != key})
    observation("HEAD-002", ["exact_cross_heads", "nullable_fields_required", "read_only_validation"])


def test_publication_prefix(root_fixture):
    root, ledger, index, manifest, projection = root_fixture
    for cut in range(1, len(ledger.records)):
        prefix = replay(ledger.records[:cut])
        (root / "execution_history.jsonl").write_bytes(b"\n".join(prefix.records) + b"\n")
        with pytest.raises(ControlIntegrityError):
            validate_run_root(root, manifest=manifest, projection=projection)
    (root / "execution_history.jsonl").write_bytes(b"\n".join(replay(ledger.records).records) + b"\n")
    assert validate_run_root(root, manifest=manifest, projection=projection)
    changed = {**manifest, "execution_head": digest(ledger.records[-2])}
    changed["checkpoint_head"] = digest({key: value for key, value in changed.items() if key != "checkpoint_head"})
    with pytest.raises(ControlIntegrityError):
        validate_run_root(root, manifest=changed, projection=projection)
    observation("PUBLISH", ["partial_closure_rejected", "pre_resulting_heads_acyclic"])


def test_coordinated_tamper(root_fixture):
    root, ledger, index, manifest, projection = root_fixture
    records = deepcopy(ledger.records)
    records[5].update(target_attempt_id=None, target_node=None, target_cycle_id=None, target_attempt_kind=None)
    # Recompute every cryptographic wrapper: semantic target-null is still invalid.
    rechain(records)
    (root / "execution_history.jsonl").write_bytes(b"\n".join(canonical_bytes(record) for record in records) + b"\n")
    changed_index = {**index, "execution_head": digest(records[-1])}
    (root / "artifact_index.json").write_bytes(canonical_bytes(changed_index))
    changed_manifest = {**manifest, "execution_head": digest(records[-1])}
    changed_manifest["checkpoint_head"] = digest({key: value for key, value in changed_manifest.items() if key != "checkpoint_head"})
    changed_projection = {**projection, "execution_head": digest(records[-1]), "checkpoint_head": changed_manifest["checkpoint_head"]}
    before = {file.name: file.read_bytes() for file in root.iterdir()}
    with pytest.raises(ControlIntegrityError, match="Nonterminal"):
        validate_run_root(root, manifest=changed_manifest, projection=changed_projection)
    assert before == {file.name: file.read_bytes() for file in root.iterdir()}
    observation("TAMPER", ["semantic_tamper_rejected", "zero_repair"])


def test_clock():
    clock = FakeClock(1000, 0)
    setup_start = clock.now()
    setup_end = clock.advance(3)
    assert measure("host_setup", setup_start, setup_end).attempt_seconds == 0
    backend_start = clock.now()
    result = clock.advance(4)
    seal = clock.advance(2)
    charge = measure("backend_active", backend_start, seal, result_ready=result, seal_ready=seal)
    assert charge.run_seconds == charge.attempt_seconds == 6
    waiting_end = clock.advance(100)
    assert measure("paused_waiting", seal, waiting_end).run_seconds == 0
    verification_end = clock.advance(5)
    assert measure("verification", waiting_end, verification_end).attempt_seconds == 5
    for bad in (-1, True, float("inf"), float("nan"), 1e300):
        with pytest.raises(ControlIntegrityError):
            clock.advance(bad)
    with pytest.raises(ControlIntegrityError):
        measure("verification", verification_end, waiting_end)
    with pytest.raises(ControlIntegrityError):
        measure("backend_active", backend_start, waiting_end, result_ready=result, seal_ready=seal)
    with pytest.raises(ControlIntegrityError):
        measure("backend_active", backend_start, seal)
    with pytest.raises(ControlIntegrityError):
        Timestamp("provider", 100, 100)
    charges = [measure("host_setup", setup_start, setup_end), charge, measure("paused_waiting", seal, waiting_end),
               measure("verification", waiting_end, verification_end)]
    trace = {"schema_version": "0.1", "events": [
        event("clock_classified", stage=item.stage, owner="trusted_clock",
              budget=[{"dimension": "run_active_seconds", "used": item.run_seconds, "remaining": None},
                      {"dimension": "attempt_active_seconds", "used": item.attempt_seconds, "remaining": None}]) for item in charges]}
    observation("CLOCK", ["backend_until_result_and_seal", "paused_wait_excluded", "trusted_clock_fail_closed"], trace=trace)


def failure_context():
    return {"program_ids": ["analysis"], "tool_ids": [], "verification_ids": ["test_fit"],
            "input_members": [{"member_id": "input", "content_digest": DIGEST}],
            "plan_digest": DIGEST, "code_digest": DIGEST, "base_revision": "base", "base_tree_digest": DIGEST,
            "config_digest": DIGEST, "policy_digest": POLICY["policy_digest"],
            "code_task_context_digest": None, "analysis_execution_context_digest": None}


def failure(context=None, incidental=None):
    return budget.fingerprint(layer="verification", failure_class="test_failure", code="assertion_failed",
                              context=context or failure_context(),
                              diagnostics={"exit_code": 1, "signal": None, "failing_test_ids": ["test_fit"], "validator_errors": []},
                              incidental=incidental)


def test_fingerprint():
    expected = failure()
    for key in budget.INCIDENTAL_FIELDS:
        assert failure(incidental={key: "different"}) == expected
    code_context = {key: DIGEST for key in budget.CODE_CONTEXT_FIELDS}
    code_context.update(requirements=["fit"], acceptance_criteria=["test_fit"], input_evidence_digests=[DIGEST],
                        base_revision="base", backend_kind="fake")
    before = budget.semantic_context("code", code_context)
    for key in ("backend_kind", "runtime_digest", "base_revision", "base_tree_digest", "policy_digest", "path_policy_digest"):
        after = budget.semantic_context("code", {**code_context, key: "b" * 64 if key.endswith("digest") else "changed"})
        assert after != before
        assert failure({**failure_context(), "code_task_context_digest": after}).digest != expected.digest
    analysis_context = {key: DIGEST for key in budget.ANALYSIS_CONTEXT_FIELDS}
    analysis_context.update(base_revision="base", input_artifact_digests=[DIGEST])
    before = budget.semantic_context("analysis", analysis_context)
    for key in ("verified_change_digest", "effective_tree_digest", "input_code_digest", "runtime_digest", "policy_digest"):
        assert budget.semantic_context("analysis", {**analysis_context, key: "b" * 64}) != before
    ledger = bootstrap()
    ledger.budget("failure_observed", fingerprint=expected.value, occurrence=1)
    ledger.budget("failure_observed", fingerprint=expected.value, occurrence=2)
    assert replay(ledger.records).projection.value["budget"]["active_failure"]["occurrence"] == 2
    changed = deepcopy(ledger.records)
    changed[-1]["payload"]["occurrence"] = 1
    with pytest.raises(ControlIntegrityError):
        replay(rechain(changed))
    trace = {"schema_version": "0.1", "events": [
        event("failure_observed", run_id=record["run_id"], index=record["budget_event_index"], execution_head=digest(record),
              policy_digest=record["policy_digest"], binding_digest=record["payload"]["fingerprint"]["causal_context_digest"],
              result_digest=record["payload"]["fingerprint"]["fingerprint_digest"],
              budget=[{"dimension": "occurrence", "used": record["payload"]["occurrence"], "remaining": None}])
        for record in ledger.records if record["event"] == "failure_observed"]}
    observation("FINGERPRINT", ["incidental_identity_ignored", "material_context_changes_digest", "occurrence_continuous"], trace=trace)


def test_budget_tamper(root_fixture):
    root, ledger, index, manifest, projection = root_fixture
    with pytest.raises(FrozenInstanceError):
        budget.policy().canonical = b"changed"
    changed = deepcopy(POLICY)
    changed["limits"]["cycles_per_run"] += 1
    changed["policy_digest"] = digest({key: value for key, value in changed.items() if key != "policy_digest"})
    with pytest.raises(ControlIntegrityError) as policy_error:
        budget.validate_policy(changed)
    for key, value in (("budget_event_index", 0), ("policy_digest", DIGEST), ("active_failure", {}), ("active_grant", {})):
        changed = deepcopy(projection)
        changed["budget"][key] = value
        with pytest.raises(ControlIntegrityError) as error:
            validate_run_root(root, manifest=manifest, projection=changed)
        assert error.value.code == "control_integrity_failure"
    trace = {"schema_version": "0.1", "events": [event("policy_rejected", outcome=policy_error.value.code,
                                                       policy_digest=POLICY["policy_digest"], run_status=None, owner="pure_validator")]}
    observation("BUDGET-INTEGRITY", ["immutable_policy", "tamper_typed_integrity", "validator_no_terminal_write"], trace=trace)


def test_unknown_usage():
    assert budget.usage() == {"state": "unknown", "value": None}
    assert budget.usage(0) == {"state": "known", "value": 0}
    for value in (budget.usage(), budget.usage(10)):
        budget.validate_usage(value)
    for value in ({"state": "unknown", "value": 0}, {"state": "known", "value": None},
                  {"state": "known", "value": True}, {"state": "unknown"}):
        with pytest.raises(ControlIntegrityError):
            budget.validate_usage(value)
    assert POLICY["audit_only_dimensions"] == ["cost", "tokens"]
    assert not {"cost", "tokens"}.intersection(POLICY["limits"])
    observation("USAGE", ["audit_only_usage", "unknown_not_zero_or_permission"])


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}', b'NaN', b'Infinity', b'1e9999',
                                 b'{"b":1,"a":2}', b'{ "a":1}', b'9007199254740992'])
def test_strict_json_negative(raw):
    with pytest.raises(ControlIntegrityError):
        loads(raw)


def reserve(ledger):
    vector = {"llm_calls": 2, "tool_calls": 4, "verification_commands": 0, "active_seconds": 30}
    return ledger.budget("resource_reserved", resource_operation_id="resource_1", resource_kind="llm_call",
                         attempt_id="attempt_000001", ordinal=1,
                         maximum_charge={"llm_calls": 1, "tool_calls": 0, "verification_commands": 0, "active_seconds": 10},
                         applicable_limits=vector, remaining_before=vector, timeout_seconds=10,
                         input_digest=DIGEST, task_digest=None, config_digest=DIGEST,
                         producer_operation_id=None, workspace_id=None)


def test_reservation_settlement_and_conservative_charge():
    ledger = bootstrap()
    attempt(ledger, "started")
    reserve(ledger)
    dimensions = replay(ledger.records).projection.value["budget"]["dimensions"]
    assert dimensions["active_seconds_per_attempt"]["used"] == 10
    assert dimensions["llm_calls_per_run"]["used"] == 1
    for field, bad in (("ordinal", 2), ("resource_operation_id", ""), ("attempt_id", "attempt_000002")):
        records = deepcopy(ledger.records)
        records[-1]["payload"][field] = bad
        with pytest.raises(ControlIntegrityError):
            replay(rechain(records))
    for field in ("maximum_charge", "remaining_before", "applicable_limits"):
        records = deepcopy(ledger.records)
        records[-1]["payload"][field]["llm_calls"] = 3
        with pytest.raises(ControlIntegrityError):
            replay(rechain(records))
    ledger.budget("resource_settled", resource_operation_id="resource_1",
                   actual={"llm_calls": 1, "tool_calls": 0, "verification_commands": 0, "active_seconds": 4},
                   tokens=budget.usage(), cost=budget.usage(), evidence_digest=DIGEST, operation_id="owner",
                   lease_epoch=1, phase_revision=1)
    assert replay(ledger.records).projection.value["budget"]["dimensions"]["active_seconds_per_run"]["used"] == 4
    changed = deepcopy(ledger.records)
    changed.append(deepcopy(changed[-1]))
    changed[-1]["budget_event_index"] += 1
    changed[-1]["budget_event_id"] = f"budget_event_{changed[-1]['budget_event_index']:06d}"
    with pytest.raises(ControlIntegrityError, match="duplicate settlement"):
        replay(rechain(changed))
    changed = deepcopy(ledger.records)
    changed[-1]["payload"]["actual"] = None
    assert replay(rechain(changed)).projection.value["budget"]["dimensions"]["active_seconds_per_run"]["used"] == 10
    backend = bootstrap()
    attempt(backend, "started")
    attempt(backend, "finished")
    attempt(backend, "scheduled", identity=2, node="code_agent")
    transition(backend, 2, "code_agent", "method_planner")
    limits = {"llm_calls": 2, "tool_calls": 4, "verification_commands": 2, "active_seconds": 30}
    backend.budget("resource_reserved", resource_operation_id="backend_resource", resource_kind="code_backend_operation",
                    attempt_id="attempt_000002", ordinal=1,
                    maximum_charge={"llm_calls": 2, "tool_calls": 4, "verification_commands": 0, "active_seconds": 30},
                    applicable_limits=limits, remaining_before=limits, timeout_seconds=30,
                    input_digest=DIGEST, task_digest=DIGEST, config_digest=DIGEST, producer_operation_id="producer_1",
                    workspace_id="workspace_1", task_id="task_1", code_task_context_digest=DIGEST, coding_backend_kind="fake",
                    backend_runtime_fingerprint=DIGEST, workspace_manifest_digest=DIGEST)
    assert replay(backend.records).projection.value["attempt_status"] == "scheduled"
    for field in ("task_digest", "task_id", "code_task_context_digest", "workspace_manifest_digest", "backend_runtime_fingerprint"):
        changed = deepcopy(backend.records)
        changed[-1]["payload"][field] = None
        with pytest.raises(ControlIntegrityError):
            replay(rechain(changed))
    changed = deepcopy(backend.records)
    changed[-1]["payload"]["pause_id"] = "premature_pause"
    with pytest.raises(ControlIntegrityError):
        replay(rechain(changed))


def test_pause_cycles_and_normal_completion():
    ledger = bootstrap()
    lifecycle(ledger, "running", "paused", pause_id="pause_1", operation_id="publish_1")
    assert replay(ledger.records).projection.value["run_status"] == "paused"
    lifecycle(ledger, "paused", "running", pause_id="pause_1", operation_id="resume_1")
    assert replay(ledger.records).projection.value["run_status"] == "running"
    changed = deepcopy(ledger.records)
    changed[-1]["operation_id"] = "publish_1"
    with pytest.raises(ControlIntegrityError):
        replay(rechain(changed))
    lifecycle(ledger, "running", "paused", pause_id="pause_2", operation_id="publish_2")
    lifecycle(ledger, "paused", "running", pause_id="pause_2", operation_id="resume_2")
    assert replay(ledger.records).projection.value["run_status"] == "running"
    lifecycle(ledger, "running", "paused", pause_id="pause_1", operation_id="publish_3")
    with pytest.raises(ControlIntegrityError):
        replay(ledger.records)
    ledger = bootstrap()
    attempt(ledger, "started")
    attempt(ledger, "finished", status="pending")
    attempt(ledger, "scheduled", identity=2, node="memory_report")
    transition(ledger, 2, "memory_report", "method_planner")
    attempt(ledger, "started", identity=2, node="memory_report")
    attempt(ledger, "finished", identity=2, node="memory_report", status="pending")
    transition(ledger, 3, None, "memory_report")
    lifecycle(ledger, "running", "completed")
    assert replay(ledger.records).projection.value["run_status"] == "completed"
    changed = deepcopy(ledger.records)
    changed[-2]["source_node"] = changed[-2]["source"] = "method_planner"
    with pytest.raises(ControlIntegrityError):
        replay(rechain(changed))


def test_nonempty_artifact_adapter_and_semantic_mutations(root_fixture, monkeypatch):
    root, ledger, index, _, _ = root_fixture
    attempt(ledger, "started")
    execution = replay(ledger.records)
    index["execution_head"] = execution.projection.value["execution_head"]
    (root / "execution_history.jsonl").write_bytes(b"\n".join(execution.records) + b"\n")
    (root / "artifact_index.json").write_bytes(canonical_bytes(index))
    core = bounded_projection(execution, artifact_index=index, artifact_head=None, artifact_event_index=0)
    state = {**core.value, "output_dir": str(root), "execution_history_path": str(root / "execution_history.jsonl"),
             "artifact_history_path": str(root / "artifact_history.jsonl"), "artifact_index_path": str(root / "artifact_index.json")}
    directory = registry.prepare_attempt_output_dir(state)
    member = directory / "method_plan.md"
    member.write_bytes(b"A deterministic plan.\n")
    monkeypatch.setattr(registry, "_utc_now", lambda: "2000-01-01T00:00:00+00:00")
    state = registry.register_artifact_bundle(state, slot="plan", member_paths=[member],
                                              state_paths={"method_plan_path": str(member), "coder_task_packet_path": None}, status="success")
    history = [json.loads(line) for line in (root / "artifact_history.jsonl").read_text().splitlines()]
    bound = []
    for record in history:
        bound.append(artifact_binding(record, previous_artifact_head=digest(bound[-1]) if bound else None,
                                       execution_head=execution.projection.value["execution_head"]).value)
    finished = attempt(ledger, "finished", output_references={"current_artifact_ids": {"plan": "attempt_000001:plan"}})
    finished.update(artifact_head=digest(bound[-1]), artifact_event_index=len(bound))
    execution = replay(ledger.records)
    index = json.loads((root / "artifact_index.json").read_text())
    index.update(execution_head=execution.projection.value["execution_head"], artifact_head=digest(bound[-1]))
    (root / "execution_history.jsonl").write_bytes(b"\n".join(execution.records) + b"\n")
    (root / "artifact_history.jsonl").write_bytes(b"\n".join(canonical_bytes(item) for item in bound) + b"\n")
    (root / "artifact_index.json").write_bytes(canonical_bytes(index))
    core = bounded_projection(execution, artifact_index=index, artifact_head=index["artifact_head"], artifact_event_index=len(bound))
    manifest = checkpoint_manifest(execution, artifact_head=index["artifact_head"], artifact_event_index=len(bound),
                                   checkpoint_id="checkpoint_with_artifact", checkpoint_digest=DIGEST, state_digest=core.digest).value
    projection = attach_checkpoint(core, execution, manifest).value
    assert validate_run_root(root, manifest=manifest, projection=projection)
    for field in ("artifact_head", "execution_head"):
        bad = {**index, field: DIGEST}
        (root / "artifact_index.json").write_bytes(canonical_bytes(bad))
        with pytest.raises(ControlIntegrityError):
            validate_run_root(root, manifest=manifest, projection=projection)
    (root / "artifact_index.json").write_bytes(canonical_bytes(index))
    # A coherent pointer/index/state rewrite cannot substitute another producer.
    changed = deepcopy(bound)
    changed[0]["pointer"]["attempt_kind"] = "analysis_engineer"
    changed[1]["previous_artifact_head"] = digest(changed[0])
    forged_ledger = deepcopy(ledger.records)
    forged_ledger[-1]["artifact_head"] = digest(changed[-1])
    forged_execution = replay(forged_ledger)
    forged_index = deepcopy(index)
    forged_index.update(execution_head=forged_execution.projection.value["execution_head"], artifact_head=digest(changed[-1]))
    forged_index["current"]["plan"] = changed[0]["pointer"]
    forged_core = bounded_projection(forged_execution, artifact_index=forged_index, artifact_head=digest(changed[-1]), artifact_event_index=2)
    forged_manifest = checkpoint_manifest(forged_execution, artifact_head=digest(changed[-1]), artifact_event_index=2,
                                          checkpoint_id="forged", checkpoint_digest=DIGEST, state_digest=forged_core.digest).value
    (root / "execution_history.jsonl").write_bytes(b"\n".join(forged_execution.records) + b"\n")
    (root / "artifact_history.jsonl").write_bytes(b"\n".join(canonical_bytes(item) for item in changed) + b"\n")
    (root / "artifact_index.json").write_bytes(canonical_bytes(forged_index))
    with pytest.raises(ControlIntegrityError, match="Attempt kind"):
        validate_run_root(root, manifest=forged_manifest)


def test_static_definitions_match_frozen_sources():
    from lqcd_agent.control.protocol import PROTOCOL
    root = Path(__file__).resolve().parents[2]
    source = (root / "docs/tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md").read_text()
    assert tuple(PROTOCOL["budget_policy_selection_contract"]["allowlisted_profiles"]) == ("balanced_v1", "phase_b_test")
    labels = ("Cycles / Run", "Automatic replan / Run", "Automatic code fix / Cycle", "Automatic analysis rerun / Cycle",
              "Automatic re-review / Cycle", "Work Attempts / Run", "Control Attempts / Run", "Transitions / Run",
              "LLM calls / Attempt", "LLM calls / Run", "Tool calls / Attempt", "Tool calls / Run",
              "Verification commands / Code Attempt", "Active seconds / Attempt", "Active seconds / Run")
    for label, (_, balanced, harness) in zip(labels, budget.LIMITS):
        assert f"| {label} | {balanced} | {harness} |" in source
    for event_name in budget.EVENTS[:7]:
        assert f"`{event_name}`" in source
    assert budget.EVENTS[7:] == ("active_interval_reserved", "active_interval_settled")
    corrective = (root / "docs/tickets/phase-b-graph-harness/B00C09_ACTIVE_TIME_LEDGER_HANDOFF.md").read_text()
    for event_name in budget.EVENTS[7:]:
        assert f"`{event_name}`" in corrective
    for kind in budget.WORK_KINDS + budget.CONTROL_KINDS:
        assert f"`{kind}`" in source
    for key in ("code_task_context_digest", "analysis_execution_context_digest", "causal_context_digest", "fingerprint_digest"):
        assert f"`{key}`" in source
    for path in (root / "src/lqcd_agent/control").glob("*.py"):
        if path.name == "_generated_protocol.py":
            continue
        content = path.read_text()
        assert 'read_text("docs/' not in content and 'read_bytes("docs/' not in content


def test_human_records_and_grant_scope():
    ledger = bootstrap()
    attempt(ledger, "started")
    attempt(ledger, "finished")
    attempt(ledger, "scheduled", identity=2, node="decision_coordinator")
    transition(ledger, 2, "decision_coordinator", "method_planner")
    attempt(ledger, "started", identity=2, node="decision_coordinator")
    attempt(ledger, "finished", identity=2, node="decision_coordinator")
    request = dict(cycle_id="cycle_0001", human_request_id="human_request_000001", request_index=1,
                   request_kind="approval", requesting_attempt_id="attempt_000002", packet_reference=None, status="open",
                   authorization_scope={"allowed_decisions": ["approve_budget_window"], "allowed_target_nodes": ["analysis_engineer"],
                                        "decision_transition_routes": {"approve_budget_window": "analysis_engineer"},
                                        "decision_transition_targets": {"approve_budget_window": "analysis_engineer"}})
    ledger.add("human_request", "created", **request)
    attempt(ledger, "scheduled", identity=3, node="human_approval_gate")
    transition(ledger, 3, "human_approval_gate", "decision_coordinator")
    attempt(ledger, "started", identity=3, node="human_approval_gate")
    response = dict(cycle_id="cycle_0001", human_request_id="human_request_000001", human_response_id="human_response_000001",
                    response_index=1, payload_reference="human_responses/human_response_000001/payload.json", payload_sha256=DIGEST,
                    validator_attempt_id=None, consumer_attempt_id=None, authorized_target_attempt_id=None,
                    decision=None, authorized_route=None, authorized_transition_route=None, authorized_transition_target=None)
    ledger.add("human_response", "submitted", **response, status="submitted", submitted_payload_reference="incoming",
               payload_snapshot={"decision": "approve_budget_window"})
    response.update(validator_attempt_id="attempt_000003", decision="approve_budget_window", authorized_route="analysis_engineer",
                    authorized_transition_route="analysis_engineer", authorized_transition_target="analysis_engineer")
    ledger.add("human_response", "validated", **response, status="validated", error=None)
    fp = failure().value
    ledger.budget("failure_observed", fingerprint=fp, occurrence=1)
    grant = dict(budget_grant_id="budget_grant_000001", budget_grant_index=1, cycle_id="cycle_0001",
                 human_request_id="human_request_000001", human_response_id="human_response_000001", pause_id="pause_1",
                 response_reference=response["payload_reference"], response_digest=DIGEST,
                 route_dimension="automatic_analysis_rerun_per_cycle", fingerprint_digest=fp["fingerprint_digest"], occurrence=1,
                 target_attempt_id="attempt_000004", target_attempt_kind="analysis_engineer", target_node="analysis_engineer",
                 transition_id="transition_000004", additional_opportunities=1, actor_scope=["approve_budget_window"])
    ledger.budget("grant_issued", **grant)
    assert replay(ledger.records).projection.value["budget"]["active_grant"] == grant
    duplicate = deepcopy(ledger.records)
    duplicate.append(deepcopy(duplicate[-1]))
    duplicate[-1]["budget_event_index"] += 1
    duplicate[-1]["budget_event_id"] = f"budget_event_{duplicate[-1]['budget_event_index']:06d}"
    duplicate[-1]["payload"].update(budget_grant_id="budget_grant_000002", budget_grant_index=2)
    with pytest.raises(ControlIntegrityError, match="already issued"):
        replay(rechain(duplicate))
    for key, value in (("additional_opportunities", 2), ("response_digest", "b" * 64), ("target_attempt_id", "attempt_000005"),
                       ("occurrence", 2), ("target_attempt_kind", "code_agent"), ("actor_scope", [])):
        changed = deepcopy(ledger.records)
        changed[-1]["payload"][key] = value
        with pytest.raises(ControlIntegrityError):
            replay(rechain(changed))
    ledger.budget("grant_consumed", budget_grant_id=grant["budget_grant_id"], transition_id=grant["transition_id"],
                   target_attempt_id=grant["target_attempt_id"], grant_digest=digest(grant))
    assert replay(ledger.records).projection.value["budget"]["active_grant"] is None
    response.update(consumer_attempt_id="attempt_000003", authorized_target_attempt_id="attempt_000004")
    ledger.add("human_response", "consumed", **response, status="consumed")
    ledger.add("human_request", "satisfied", **{**request, "status": "satisfied"})
    attempt(ledger, "finished", identity=3, node="human_approval_gate")
    attempt(ledger, "scheduled", identity=4, node="analysis_engineer")
    transition(ledger, 4, "analysis_engineer", "human_approval_gate")
    value = replay(ledger.records).projection.value
    assert value["human_request_status"] == "satisfied" and value["human_response_status"] == "consumed"
    assert value["human_response_index"] == 1 and value["human_response_target_attempt_id"] == "attempt_000004"
    changed = deepcopy(ledger.records)
    changed[-1]["target_attempt_id"] = "attempt_000003"
    with pytest.raises(ControlIntegrityError):
        replay(rechain(changed))


def test_explicit_version_dispatch_and_no_migration():
    from lqcd_agent.control.protocol import PROTOCOL
    record = bootstrap().records[0]
    for version in ("0.2", "0.3", "0.5", None):
        changed = {**record, "schema_version": version}
        before = canonical_bytes(changed)
        with pytest.raises(ControlIntegrityError, match="schema"):
            validate_record(changed)
        assert canonical_bytes(changed) == before
    compatibility = str(PROTOCOL["compatibility"])
    assert all(version in compatibility for version in ("0.2", "0.3", "0.4"))
