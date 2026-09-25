"""Verification resource publications owned by the existing resume capability.

The coordinator journal freezes exact ledger bytes before any effect. It is a
publication intent, never an independent budget authority or a retry permit.
"""
from dataclasses import asdict

from lqcd_agent.control.coordinator import boundary, publish_exact, read_regular, replace_projection
from lqcd_agent.control.execution import append_record_bytes, parse_ledger
from lqcd_agent.control.records import build_record
from lqcd_agent.control.strict_json import canonical_bytes, closed, digest, digest_value, loads, number, require, text


def owned_prefix(value, *, published=True):
    """Validate the exact resource-only suffix anchored to the original start."""
    previous = value["started_intent"]
    entries = value.get("verification_intents", [])
    require(type(entries) is list, "Invalid verification publication journal")
    authorization = value["authorization"]
    reserved, settled = set(), set()
    for entry in entries:
        closed(entry, ("record", "previous", "previous_index", "content", "index", "intent_digest", "published"))
        require(type(entry["published"]) is bool and (entry["published"] or not published), "Unpublished verification prefix")
        require(entry["intent_digest"] == digest({k: v for k, v in entry.items() if k not in ("intent_digest", "published")}),
                "Verification intent digest mismatch")
        require(entry["previous"] == previous["content"] and entry["previous_index"] == previous["index"],
                "Verification prefix is not the owned continuation")
        record = entry["record"]
        require(record["record_type"] == "budget" and record["event"] in ("resource_reserved", "resource_settled"),
                "Non-resource invocation publication")
        require(all(record[k] == authorization["identity"][k] for k in ("case_id", "run_id")), "Foreign verification Run")
        payload = record["payload"]
        resource = payload["resource_operation_id"]
        if record["event"] == "resource_reserved":
            external = authorization["external_consumption"]["value"]
            require(payload["resource_kind"] == "verification_command" and
                    payload["attempt_id"] == authorization["identity"]["attempt_id"] and
                    all(payload[k] == external[k] for k in ("task_digest", "producer_operation_id", "workspace_id")) and
                    resource not in reserved,
                    "Foreign verification reservation")
            reserved.add(resource)
        else:
            require(payload["operation_id"] == authorization["producer_operation_id"] and
                    resource in reserved and resource not in settled, "Foreign verification settlement owner")
            settled.add(resource)
        require(append_record_bytes(entry["previous"].encode(), record).decode() == entry["content"],
                "Verification ledger differs from its frozen record")
        index = loads(entry["previous_index"])
        require(canonical_bytes({**index, "execution_head": digest(record)}).decode() == entry["index"],
                "Verification changed artifact authority")
        previous = entry
    return previous


def publish_pending(coordinator, root, value, fence):
    """Publish only a committed exact suffix, including after a worker crash."""
    owned_prefix(value, published=False)
    for entry in value.get("verification_intents", []):
        if entry["published"]:
            continue
        fence()
        publish_exact(root / "execution_history.jsonl", entry["content"].encode(), previous=entry["previous"].encode(),
                      observer=coordinator.observer, name="invocation.verification_ledger")
        fence()
        replace_projection(root / "artifact_index.json", entry["previous_index"].encode(), entry["index"].encode(),
                           observer=coordinator.observer)
        fence()
        entry["published"] = True


def recover_publications(coordinator, db, operation):
    """The same resume owner may materialize bytes, never redispatch a command."""
    from lqcd_agent.control.capabilities import InvocationLeases
    leases = InvocationLeases(coordinator)
    capability = "capability_" + operation["operation_id"]
    row = db.execute("SELECT 1 FROM invocation_capabilities WHERE capability_id=?", (capability,)).fetchone()
    if row is None:
        return
    revision, value = leases.get(capability, db=db)
    if not value.get("verification_intents"):
        return
    require(value["authorization"]["producer_operation_id"] == operation["operation_id"] and
            operation["operation_type"] == "resume_run" and operation["request"]["input_kind"] == "external_result",
            "Foreign verification recovery owner")
    locator = operation["request"]["run_locator"]
    root = coordinator.root / locator["case_id"] / locator["run_id"]
    fence = lambda: coordinator.fence(db, operation["operation_id"], operation["worker_owner_id"],
                                      operation["lease_epoch"], operation["phase_revision"])
    publish_pending(coordinator, root, value, fence)
    leases._save(db, capability, revision, value)


def _commit(port, event, payload, *, timestamp=None):
    coordinator, leases = port.leases.coordinator, port.leases
    with coordinator.transaction() as db:
        leases._effect_authority(db, port.capability_id, port.worker, port.epoch)
        revision, value, root, now = leases._fence(db, port.capability_id, port.worker, port.epoch)
        if event == "resource_reserved":
            producer = coordinator.get(value["authorization"]["producer_operation_id"], db=db)
            require(now.monotonic_seconds + payload["timeout_seconds"] <=
                    min(value["deadline"], value["expires_at"], producer["lease_expires"]), "Verification exceeds its owned lease window")
        previous = owned_prefix(value)
        execution = parse_ledger(previous["content"].encode())
        index = loads(previous["index"])
        state = execution.projection.value
        position = state["budget"]["budget_event_index"] + 1
        record = build_record("budget", event, case_id=state["case_id"], run_id=state["run_id"],
            event_index=len(execution.records) + 1, previous_execution_head=state["execution_head"],
            artifact_head=index["artifact_head"], artifact_event_index=index["revision"], timestamp=timestamp or now,
            budget_event_id=f"budget_event_{position:06d}", budget_event_index=position,
            policy_version="0.1", policy_digest=state["budget"]["policy_digest"], payload=payload).value
        content = append_record_bytes(previous["content"].encode(), record)
        parse_ledger(content)
        entry = {"record": record, "previous": previous["content"], "previous_index": previous["index"],
                 "content": content.decode(), "index": canonical_bytes({**index, "execution_head": digest(record)}).decode()}
        entry.update(intent_digest=digest(entry), published=False)
        value.setdefault("verification_intents", []).append(entry)
        value["updated_at"] = asdict(now)
        leases._save(db, port.capability_id, revision, value)
        boundary(coordinator.observer, "invocation.verification_" + event, "before", entry)
    boundary(coordinator.observer, "invocation.verification_" + event, "after", entry)
    with coordinator.transaction() as db:
        revision, value, root, _ = leases._fence(db, port.capability_id, port.worker, port.epoch)
        publish_pending(coordinator, root, value, lambda: leases._fence(db, port.capability_id, port.worker, port.epoch))
        leases._save(db, port.capability_id, revision, value)
        leases._effect_authority(db, port.capability_id, port.worker, port.epoch)
    return record


def run_verification(port, *, spec_id, input_digest, config_digest, timeout_seconds, effect):
    """Reserve one trusted command, execute outside the writer, then settle."""
    coordinator, leases = port.leases.coordinator, port.leases
    require(port.db is None and not coordinator.connection.in_transaction, "Verification requires an independent writer boundary")
    text(spec_id)
    for head in (input_digest, config_digest):
        digest_value(head)
    number(timeout_seconds, minimum=0)
    require(timeout_seconds > 0, "Verification timeout must be positive")
    with coordinator.transaction() as db:
        leases._effect_authority(db, port.capability_id, port.worker, port.epoch)
        _, value, root, now = leases._fence(db, port.capability_id, port.worker, port.epoch)
        authorization = value["authorization"]
        require(authorization["identity"]["attempt_kind"] == "code_agent" and "external_consumption" in authorization,
                "Verification requires normal Code consumption")
        require(now.monotonic_seconds + timeout_seconds <= min(value["deadline"], value["expires_at"]),
                "Verification exceeds its owned lease window")
        execution = parse_ledger(owned_prefix(value)["content"].encode())
        records, state = execution.values, execution.projection.value
        reserved = [r["payload"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved"]
        resource_id = port.capability_id + ":verification:" + spec_id
        require(all(r["resource_operation_id"] != resource_id for r in reserved), "Verification cannot execute twice")
        settled = {r["payload"]["resource_operation_id"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_settled"}
        require(all(r["resource_operation_id"] in settled for r in reserved if r["attempt_id"] == state["attempt_id"]),
                "Uncertain verification cannot be replaced")
        policy = loads(read_regular(root / "budget_policy.json"))["limits"]
        dimensions = state["budget"]["dimensions"]
        limits, remaining = {}, {}
        for name in ("llm_calls", "tool_calls", "verification_commands", "active_seconds"):
            keys = ("verification_commands_per_code_attempt",) if name == "verification_commands" else (name + "_per_attempt", name + "_per_run")
            limits[name] = min(policy[k] for k in keys)
            remaining[name] = min(dimensions[k]["remaining"] for k in keys)
        if "active_time" in authorization:
            parent = value["started_intent"].get("interval_record")
            require(parent is not None and parent["payload"]["interval_id"] == authorization["active_time"]["interval_id"],
                    "Verification lacks its active parent")
            require(coordinator.clock.epoch_id == parent["payload"]["clock_epoch_id"],
                    "Verification clock epoch differs from its active parent")
            prior = [r["payload"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved" and
                     r["event_index"] > parent["event_index"] and r["payload"]["resource_kind"] == "verification_command" and
                     r["payload"]["attempt_id"] == state["attempt_id"]]
            resolved = {r["payload"]["resource_operation_id"]: r["payload"] for r in records if
                        r["record_type"] == "budget" and r["event"] == "resource_settled"}
            covered = sum((resolved[r["resource_operation_id"]]["actual"]["active_seconds"] if
                           r["resource_operation_id"] in resolved and resolved[r["resource_operation_id"]]["actual"] is not None else
                           r["maximum_charge"]["active_seconds"]) for r in prior)
            remaining["active_seconds"] = max(0, min(parent["payload"]["deadline_monotonic_seconds"] - now.monotonic_seconds,
                                                    parent["payload"]["maximum_seconds"] - covered))
        external = authorization["external_consumption"]["value"]
        payload = {"resource_operation_id": resource_id, "resource_kind": "verification_command", "attempt_id": state["attempt_id"],
            "ordinal": 1 + sum(r["attempt_id"] == state["attempt_id"] for r in reserved),
            "maximum_charge": {"llm_calls": 0, "tool_calls": 0, "verification_commands": 1, "active_seconds": timeout_seconds},
            "applicable_limits": limits, "remaining_before": remaining, "timeout_seconds": timeout_seconds,
            "input_digest": input_digest, "task_digest": external["task_digest"], "config_digest": config_digest,
            "producer_operation_id": external["producer_operation_id"], "workspace_id": external["workspace_id"]}
    _commit(port, "resource_reserved", payload, timestamp=now)
    leases.require_effect_authority(port.capability_id, port.worker, port.epoch)
    started = coordinator._time()
    result = effect()
    require(type(result) is dict, "Untyped verification result")
    ended = coordinator._time()
    if "active_time" in authorization:
        require(coordinator.clock.epoch_id == parent["payload"]["clock_epoch_id"],
                "Verification clock epoch changed during its active parent")
    require(ended.source == started.source and ended.wall_seconds >= started.wall_seconds and
            0 <= ended.monotonic_seconds - started.monotonic_seconds <= timeout_seconds, "Invalid verification duration")
    operation = coordinator.get(authorization["producer_operation_id"])
    _commit(port, "resource_settled", {"resource_operation_id": resource_id,
        "actual": {"llm_calls": 0, "tool_calls": 0, "verification_commands": 1,
                   "active_seconds": ended.monotonic_seconds - started.monotonic_seconds},
        "tokens": {"state": "unknown", "value": None}, "cost": {"state": "unknown", "value": None},
        "evidence_digest": digest(result), "operation_id": operation["operation_id"],
        "lease_epoch": operation["lease_epoch"], "phase_revision": operation["phase_revision"]})
    return result
