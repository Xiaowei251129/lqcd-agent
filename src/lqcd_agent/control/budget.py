"""A06 0.1 policy, semantic failure identity and ledger-derived budget facts.

Policy and semantic helpers are pure. Ordinary Host calls use the original
invocation fence to reserve and settle resources; Agents receive no authority.
"""
from .protocol import PROTOCOL
from .strict_json import (ValidatedValue, canonical_bytes, closed, digest, digest_value,
                          number, require, text)


WORK_KINDS = ("method_planner", "legacy_codex_handoff", "code_agent", "analysis_engineer", "scientific_reviewer")
CONTROL_KINDS = ("decision_coordinator", "human_gate", "memory_report")
LIMITS = (
    ("cycles_per_run", 2, 2), ("automatic_replan_per_run", 1, 1),
    ("automatic_code_fix_per_cycle", 1, 1), ("automatic_analysis_rerun_per_cycle", 1, 1),
    ("automatic_re_review_per_cycle", 1, 1), ("work_attempts_per_run", 16, 8),
    ("control_attempts_per_run", 16, 8), ("transitions_per_run", 40, 20),
    ("llm_calls_per_attempt", 4, 2), ("llm_calls_per_run", 32, 8),
    ("tool_calls_per_attempt", 32, 4), ("tool_calls_per_run", 128, 16),
    ("verification_commands_per_code_attempt", 8, 2),
    ("active_seconds_per_attempt", 900, 30), ("active_seconds_per_run", 3600, 120),
)
ROUTE_DIMENSIONS = tuple(row[0] for row in LIMITS if row[0].startswith("automatic_"))
RESOURCE_DIMENSIONS = ("llm_calls", "tool_calls", "verification_commands", "active_seconds")
EVENTS = ("policy_initialized", "resource_reserved", "resource_settled", "failure_observed",
          "grant_issued", "grant_consumed", "decision_recorded", "active_interval_reserved", "active_interval_settled")


def policy(profile_id="balanced_v1"):
    """Build frozen policy bytes, not a profile-selection authorization."""
    require(profile_id in PROTOCOL["budget_policy_selection_contract"]["allowlisted_profiles"],
            "Unknown budget profile")
    offset = 1 if profile_id == "balanced_v1" else 2
    value = {
        "schema_version": "0.1", "profile_id": profile_id,
        "limits": {row[0]: row[offset] for row in LIMITS},
        "work_attempt_kinds": sorted(WORK_KINDS), "control_attempt_kinds": sorted(CONTROL_KINDS),
        "terminal_reserve": {"control_attempts": 5, "transitions": 6},
        "pause_deadline_seconds": 604800 if profile_id == "balanced_v1" else 60,
        "audit_only_dimensions": ["cost", "tokens"],
        "grant": {"additional_opportunities": 1, "route_dimensions": sorted(ROUTE_DIMENSIONS),
                  "extends_global_ceilings": False},
    }
    return ValidatedValue.from_value({**value, "policy_digest": digest(value)})


def validate_policy(value):
    require(type(value) is dict, "Invalid policy")
    expected = policy(value.get("profile_id"))
    require(canonical_bytes(value) == expected.canonical, "Policy bytes, version or digest changed")
    return expected


class BudgetExhausted(ValueError):
    """An ordinary resource cannot fit its immutable invocation window."""


def run_resource(port, *, resource_kind, resource_id, input_digest, config_digest, timeout_seconds, effect):
    """Reserve one Host-controlled call before effects and settle it once."""
    from .capabilities import invocation_prefix
    from .coordinator import boundary, read_regular
    from .execution import parse_ledger
    from .strict_json import loads

    coordinator, leases = port.leases.coordinator, port.leases
    require(port.db is None and not coordinator.connection.in_transaction, "Resource requires an independent writer")
    require(resource_kind in ("llm_call", "tool_call"), "Unknown ordinary resource kind")
    text(resource_id)
    digest_value(input_digest)
    digest_value(config_digest)
    number(timeout_seconds)
    require(timeout_seconds > 0, "Resource timeout must be positive")
    with coordinator.transaction() as db:
        leases._effect_authority(db, port.capability_id, port.worker, port.epoch)
        _, value, root, now = leases._fence(db, port.capability_id, port.worker, port.epoch)
        require(value["authorization"]["identity"]["attempt_kind"] != "code_agent", "Code resources use their original owner")
        execution = parse_ledger(invocation_prefix(value)["content"].encode())
        records, state = execution.values, execution.projection.value
        selected = validate_policy(loads(read_regular(root / "budget_policy.json"))).value["limits"]
        reservations = [r["payload"] for r in records if r["record_type"] == "budget" and r["event"] == "resource_reserved"]
        stable_id = port.capability_id + ":" + resource_id
        require(all(r["resource_operation_id"] != stable_id for r in reservations), "Resource cannot be redispatched")
        settled = {r["payload"]["resource_operation_id"] for r in records if
                   r["record_type"] == "budget" and r["event"] == "resource_settled"}
        require(all(r["resource_operation_id"] in settled for r in reservations if r["attempt_id"] == state["attempt_id"]),
                "Uncertain resource cannot be replaced")
        dimensions = state["budget"]["dimensions"]
        applicable, remaining = {}, {}
        for dimension in RESOURCE_DIMENSIONS:
            if dimension == "verification_commands":
                applicable[dimension] = remaining[dimension] = 0
            else:
                keys = (dimension + "_per_attempt", dimension + "_per_run")
                applicable[dimension] = min(selected[k] for k in keys)
                remaining[dimension] = min(dimensions[k]["remaining"] for k in keys)
        charge = dict.fromkeys(RESOURCE_DIMENSIONS, 0)
        charge["llm_calls" if resource_kind == "llm_call" else "tool_calls"] = 1
        charge["active_seconds"] = timeout_seconds
        if any(charge[k] > remaining[k] for k in charge) or now.monotonic_seconds + timeout_seconds > min(value["deadline"], value["expires_at"]):
            raise BudgetExhausted("Resource exceeds its remaining budget or invocation lease")
        payload = {"resource_operation_id": stable_id, "resource_kind": resource_kind, "attempt_id": state["attempt_id"],
            "ordinal": 1 + sum(r["attempt_id"] == state["attempt_id"] for r in reservations),
            "maximum_charge": charge, "applicable_limits": applicable, "remaining_before": remaining,
            "timeout_seconds": timeout_seconds, "input_digest": input_digest, "task_digest": None,
            "config_digest": config_digest, "producer_operation_id": None, "workspace_id": None}
    decision_body = {"schema_version": "0.1", "proposal_id": digest(payload), "proposed_action": "resource",
        "target_kind": state["attempt_kind"], "risk": "low", "fingerprint_digest": None, "occurrence": 0,
        "dimensions": {k: {**v, "projected_after": v["used"] + (charge[k.removesuffix("_per_run").removesuffix("_per_attempt")]
            if k.removesuffix("_per_run").removesuffix("_per_attempt") in charge else 0)} for k,v in dimensions.items()},
        "budget_grant_id": None, "decision": "allow", "reason_code": "bounded_host_resource", "next_control_action": "resource"}
    port.append_budget("decision_recorded", {**decision_body, "decision_digest": digest(decision_body)})
    boundary(coordinator.observer, "budget.decision_before_resource", "before", payload)
    port.append_budget("resource_reserved", payload)
    boundary(coordinator.observer, "budget.decision_before_resource", "after", payload)
    leases.require_effect_authority(port.capability_id, port.worker, port.epoch)
    start = coordinator._time()
    clock_epoch = coordinator.clock.epoch_id
    result = effect()
    end = coordinator._time()
    require(coordinator.clock.epoch_id == clock_epoch and end.source == start.source and
            end.wall_seconds >= start.wall_seconds and 0 <= end.monotonic_seconds - start.monotonic_seconds <= timeout_seconds,
            "Resource duration is untrusted or exceeds its admitted maximum")
    operation = coordinator.get(value["authorization"]["producer_operation_id"])
    actual = {**charge, "active_seconds": end.monotonic_seconds - start.monotonic_seconds}
    port.append_budget("resource_settled", {"resource_operation_id": stable_id, "actual": actual,
        "tokens": usage(), "cost": usage(), "evidence_digest": digest(result), "operation_id": operation["operation_id"],
        "lease_epoch": operation["lease_epoch"], "phase_revision": operation["phase_revision"]})
    return result


def usage(value=None):
    if value is not None:
        number(value)
    return {"state": "unknown" if value is None else "known", "value": value}


def validate_usage(value):
    closed(value, ("state", "value"))
    require(value["state"] in ("unknown", "known"), "Invalid usage discriminator")
    if value["state"] == "unknown":
        require(value["value"] is None, "Unknown usage cannot carry a measurement")
    else:
        number(value["value"])


CODE_CONTEXT_FIELDS = ("requirements", "acceptance_criteria", "input_evidence_digests",
                       "base_revision", "base_tree_digest", "backend_kind", "runtime_digest",
                       "policy_digest", "path_policy_digest", "tool_policy_digest", "network_policy_digest")
ANALYSIS_CONTEXT_FIELDS = ("verified_change_digest", "effective_tree_digest", "base_revision",
                           "base_tree_digest", "input_code_digest", "input_artifact_digests",
                           "runtime_digest", "policy_digest")
CAUSE_FIELDS = ("program_ids", "tool_ids", "verification_ids", "input_members", "plan_digest",
                "code_digest", "base_revision", "base_tree_digest", "config_digest", "policy_digest",
                "code_task_context_digest", "analysis_execution_context_digest")
INCIDENTAL_FIELDS = ("run_id", "cycle_id", "attempt_id", "transition_id", "task_id", "spec_id",
                     "workspace_id", "operation_id", "reservation_id", "job_id", "thread_id",
                     "session_id", "timestamp", "duration", "generation", "path", "summary", "raw_log")


def _strings(values):
    require(type(values) is list and all(type(item) is str and item for item in values), "Invalid string list")
    require(values == sorted(set(values)), "Non-canonical string list")


def semantic_context(kind, value):
    require(kind in ("code", "analysis"), "Unknown semantic context")
    closed(value, CODE_CONTEXT_FIELDS if kind == "code" else ANALYSIS_CONTEXT_FIELDS)
    for key, item in value.items():
        if key.endswith("_digests"):
            _strings(item)
            for member in item:
                digest_value(member)
        elif key.endswith("_digest"):
            digest_value(item)
        elif key in ("requirements", "acceptance_criteria"):
            _strings(item)
        else:
            text(item)
    return digest(value)


def fingerprint(*, layer, failure_class, code, context, diagnostics, incidental=None):
    require(layer in ("control", "provider", "tool", "verification", "code", "data", "scientific", "policy", "security"),
            "Unknown failure layer")
    text(failure_class)
    text(code)
    closed(context, CAUSE_FIELDS)
    for key, value in context.items():
        if key.endswith("_ids"):
            _strings(value)
        elif key == "input_members":
            require(type(value) is list, "Invalid input members")
            for member in value:
                closed(member, ("member_id", "content_digest"))
                text(member["member_id"])
                digest_value(member["content_digest"])
            require([item["member_id"] for item in value] == sorted(set(item["member_id"] for item in value)),
                    "Non-canonical input member order")
        elif key.endswith("_digest"):
            digest_value(value, nullable=key != "policy_digest")
        else:
            text(value, nullable=True)
    closed(diagnostics, ("exit_code", "signal", "failing_test_ids", "validator_errors"))
    if diagnostics["exit_code"] is not None:
        number(diagnostics["exit_code"], integer=True, minimum=-255)
    text(diagnostics["signal"], nullable=True)
    _strings(diagnostics["failing_test_ids"])
    require(type(diagnostics["validator_errors"]) is list, "Invalid validator errors")
    for error in diagnostics["validator_errors"]:
        closed(error, ("field", "code"))
        text(error["field"])
        text(error["code"])
    encoded = [canonical_bytes(item) for item in diagnostics["validator_errors"]]
    require(encoded == sorted(set(encoded)), "Non-canonical validator diagnostics")
    if incidental is not None:
        require(type(incidental) is dict and set(incidental) <= set(INCIDENTAL_FIELDS), "Unknown incidental field")
        canonical_bytes(incidental)
    body = {"schema_version": "0.1", "layer": layer, "failure_class": failure_class, "code": code,
            "context": context, "diagnostics": diagnostics, "causal_context_digest": digest(context)}
    return ValidatedValue.from_value({**body, "fingerprint_digest": digest(body)})


def validate_fingerprint(value):
    closed(value, ("schema_version", "layer", "failure_class", "code", "context", "diagnostics",
                   "causal_context_digest", "fingerprint_digest"))
    expected = fingerprint(layer=value["layer"], failure_class=value["failure_class"], code=value["code"],
                           context=value["context"], diagnostics=value["diagnostics"])
    require(canonical_bytes(value) == expected.canonical, "Fingerprint changed")
    return expected


def resource_vector(value):
    closed(value, RESOURCE_DIMENSIONS)
    for key, amount in value.items():
        number(amount, integer=key != "active_seconds")
    return value


def validate_budget_payload(event, value):
    require(event in EVENTS, "Unknown budget event")
    require(type(value) is dict, "Budget payload must be an object")
    fields = {
        "policy_initialized": ("policy", "policy_reference"),
        "resource_reserved": ("resource_operation_id", "resource_kind", "attempt_id", "ordinal", "maximum_charge",
                              "applicable_limits", "remaining_before", "timeout_seconds", "input_digest",
                              "task_digest", "config_digest", "producer_operation_id", "workspace_id"),
        "resource_settled": ("resource_operation_id", "actual", "tokens", "cost", "evidence_digest",
                             "operation_id", "lease_epoch", "phase_revision"),
        "active_interval_reserved": ("schema_version", "interval_id", "stage", "attempt_id", "producer_operation_id",
                                     "owner_operation_id", "clock_epoch_id", "start_at", "maximum_seconds",
                                     "run_remaining_before", "attempt_remaining_before", "deadline_monotonic_seconds"),
        "active_interval_settled": ("schema_version", "interval_id", "stage", "attempt_id", "producer_operation_id",
                                    "owner_operation_id", "settlement_operation_id", "lease_epoch", "phase_revision",
                                    "clock_epoch_id", "end_at", "actual_seconds", "disposition", "evidence_digest"),
        "failure_observed": ("fingerprint", "occurrence"),
        "grant_issued": ("budget_grant_id", "budget_grant_index", "cycle_id", "human_request_id", "human_response_id",
                         "pause_id", "response_reference", "response_digest", "route_dimension", "fingerprint_digest",
                         "occurrence", "target_attempt_id", "target_attempt_kind", "target_node", "transition_id",
                         "additional_opportunities", "actor_scope"),
        "grant_consumed": ("budget_grant_id", "transition_id", "target_attempt_id", "grant_digest"),
        "decision_recorded": ("schema_version", "proposal_id", "proposed_action", "target_kind", "risk",
                              "fingerprint_digest", "occurrence", "dimensions", "budget_grant_id", "decision",
                              "reason_code", "next_control_action", "decision_digest"),
    }
    aggregate_fields = ("task_id", "code_task_context_digest", "coding_backend_kind", "backend_runtime_fingerprint", "workspace_manifest_digest")
    is_aggregate = event == "resource_reserved" and value.get("resource_kind") == "code_backend_operation"
    closed(value, fields[event] + (aggregate_fields if is_aggregate else ()))
    if event == "policy_initialized":
        validate_policy(value["policy"])
        require(value["policy_reference"] == "budget_policy.json", "Non-canonical policy reference")
    elif event == "resource_reserved":
        for key in ("resource_operation_id", "attempt_id"):
            text(value[key])
        require(value["resource_kind"] in ("llm_call", "tool_call", "verification_command", "code_backend_operation"),
                "Unknown resource kind")
        number(value["ordinal"], integer=True, minimum=1)
        for key in ("maximum_charge", "applicable_limits", "remaining_before"):
            resource_vector(value[key])
        number(value["timeout_seconds"])
        require(0 < value["timeout_seconds"] <= value["maximum_charge"]["active_seconds"], "Invalid reservation timeout")
        for key in ("input_digest", "task_digest", "config_digest"):
            digest_value(value[key], nullable=key == "task_digest" and not is_aggregate)
        for key in ("producer_operation_id", "workspace_id"):
            text(value[key], nullable=value["resource_kind"] != "code_backend_operation")
        if is_aggregate:
            text(value["task_id"])
            text(value["coding_backend_kind"])
            for key in ("code_task_context_digest", "backend_runtime_fingerprint", "workspace_manifest_digest"):
                digest_value(value[key])
    elif event == "resource_settled":
        text(value["resource_operation_id"])
        if value["actual"] is not None:
            resource_vector(value["actual"])
        validate_usage(value["tokens"])
        validate_usage(value["cost"])
        digest_value(value["evidence_digest"])
        text(value["operation_id"])
        number(value["lease_epoch"], integer=True, minimum=1)
        number(value["phase_revision"], integer=True, minimum=1)
    elif event in ("active_interval_reserved", "active_interval_settled"):
        require(value["schema_version"] == "active_time_0.1", "Unknown active-time payload version")
        require(value["stage"] in ("host_setup", "attempt_active"), "Unknown active-time stage")
        for key in ("interval_id", "attempt_id", "producer_operation_id", "owner_operation_id", "clock_epoch_id"):
            text(value[key])
        if event == "active_interval_reserved":
            from .clock import Timestamp
            closed(value["start_at"], ("source", "wall_seconds", "monotonic_seconds"))
            Timestamp(**value["start_at"])
            for key in ("maximum_seconds", "run_remaining_before", "deadline_monotonic_seconds"):
                number(value[key])
            require(value["maximum_seconds"] > 0 and value["run_remaining_before"] >= value["maximum_seconds"] and
                    value["deadline_monotonic_seconds"] == value["start_at"]["monotonic_seconds"] + value["maximum_seconds"],
                    "Invalid active-time window")
            if value["stage"] == "host_setup":
                require(value["attempt_remaining_before"] is None and
                        value["owner_operation_id"] == value["producer_operation_id"], "Setup must be Run-only")
            else:
                number(value["attempt_remaining_before"])
                require(value["attempt_remaining_before"] >= value["maximum_seconds"], "Attempt window is insufficient")
        else:
            for key in ("settlement_operation_id",):
                text(value[key])
            number(value["lease_epoch"], integer=True, minimum=1)
            number(value["phase_revision"], integer=True, minimum=1)
            require(value["disposition"] in ("actual", "conservative_maximum"), "Unknown active-time disposition")
            if value["disposition"] == "actual":
                from .clock import Timestamp
                closed(value["end_at"], ("source", "wall_seconds", "monotonic_seconds"))
                Timestamp(**value["end_at"])
                number(value["actual_seconds"])
            else:
                require(value["end_at"] is None and value["actual_seconds"] is None, "Conservative settlement cannot claim actual")
            digest_value(value["evidence_digest"])
    elif event == "failure_observed":
        validate_fingerprint(value["fingerprint"])
        number(value["occurrence"], integer=True, minimum=1)
    elif event == "grant_issued":
        number(value["budget_grant_index"], integer=True, minimum=1)
        require(value["budget_grant_id"] == f"budget_grant_{value['budget_grant_index']:06d}", "Non-canonical grant identity")
        for key in ("cycle_id", "human_request_id", "human_response_id", "pause_id", "response_reference",
                    "target_attempt_id", "target_node", "transition_id"):
            text(value[key])
        require(value["target_attempt_kind"] in WORK_KINDS + CONTROL_KINDS, "Unknown grant target")
        for key in ("response_digest", "fingerprint_digest"):
            digest_value(value[key])
        require(value["route_dimension"] in ROUTE_DIMENSIONS, "Invalid grant scope")
        expected_kind = dict(zip(ROUTE_DIMENSIONS, ("method_planner", "code_agent", "analysis_engineer", "scientific_reviewer")))[value["route_dimension"]]
        require(value["target_attempt_kind"] == expected_kind, "Grant target does not match route scope")
        number(value["occurrence"], integer=True, minimum=1)
        require(type(value["additional_opportunities"]) is int and value["additional_opportunities"] == 1,
                "Grant cannot extend a global ceiling")
        _strings(value["actor_scope"])
        require("approve_budget_window" in value["actor_scope"], "Missing grant actor scope")
    elif event == "grant_consumed":
        for key in ("budget_grant_id", "transition_id", "target_attempt_id"):
            text(value[key])
        digest_value(value["grant_digest"])
    else:
        require(value["schema_version"] == "0.1", "Unknown decision version")
        require(value["decision"] in PROTOCOL["budget_decision_contract"]["decision_values"], "Unknown decision")
        require(value["proposed_action"] in ("route", "resource", "repause", "bootstrap_initial_route"),
                "Unknown proposal kind")
        require(value["target_kind"] is None or value["target_kind"] in WORK_KINDS + CONTROL_KINDS, "Unknown decision target")
        require(value["risk"] in ("low", "medium", "high", "critical", "unknown"), "Unknown risk")
        for key in ("proposal_id", "reason_code", "next_control_action"):
            text(value[key])
        text(value["budget_grant_id"], nullable=True)
        digest_value(value["fingerprint_digest"], nullable=True)
        number(value["occurrence"], integer=True)
        require((value["fingerprint_digest"] is None) == (value["occurrence"] == 0), "Partial failure binding")
        require(type(value["dimensions"]) is dict and bool(value["dimensions"]), "Missing decision dimensions")
        for key, amounts in value["dimensions"].items():
            require(key in dict((row[0], row[1]) for row in LIMITS), "Unknown decision dimension")
            closed(amounts, ("used", "remaining", "projected_after"))
            for amount in amounts.values():
                number(amount, integer=not key.startswith("active_seconds"))
        require(value["decision_digest"] == digest({key: item for key, item in value.items() if key != "decision_digest"}),
                "Decision digest mismatch")
