"""Pure replay of the single execution ledger; no persistence or invocation API."""
from dataclasses import dataclass

from lqcd_agent.artifacts import registry
from lqcd_agent.graph.state import stable_cycle_id

from .budget import WORK_KINDS, validate_policy
from .protocol import PROTOCOL
from .records import IDENTITIES, parse_record, validate_record
from .strict_json import ControlIntegrityError, ValidatedValue, canonical_bytes, digest, require


@dataclass(frozen=True)
class ExecutionReplay:
    records: tuple[bytes, ...]
    projection: ValidatedValue

    @property
    def values(self):
        return [parse_record(record).value for record in self.records]


def _checked_replay(records):
    require(type(records) in (list, tuple) and bool(records), "Missing execution ledger")
    records = [validate_record(record).value for record in records]
    root = records[0]
    require(root["record_type"] == "run", "Ledger must begin with Run creation")
    run_status = root["status"]
    previous = None
    stamp = root["created_at"]
    artifact_index = 0
    seen = {kind: {} for kind in IDENTITIES}
    seen["budget"] = {}
    outbound = set()
    last_pause = None
    pause_ids = set()
    pause_operations = set()
    for index, record in enumerate(records, 1):
        kind, event = record["record_type"], record["event"]
        require(record["event_index"] == index and record["previous_execution_head"] == previous,
                "Execution head, order or continuous event identity mismatch")
        require(record["run_id"] == root["run_id"] and record["case_id"] == root["case_id"], "Cross-Run record")
        require(record["artifact_event_index"] >= artifact_index, "Artifact head rollback")
        if record["artifact_event_index"] == artifact_index and index > 1:
            require(record["artifact_head"] == records[index - 2]["artifact_head"], "Conflicting artifact head")
        artifact_index = record["artifact_event_index"]
        now = record["created_at"]
        require(now["source"] == stamp["source"] and now["wall_seconds"] >= stamp["wall_seconds"] and
                now["monotonic_seconds"] >= stamp["monotonic_seconds"], "Ledger clock regression")
        stamp = now
        if index > 1:
            require(run_status not in PROTOCOL["state_machines"]["run_lifecycle"]["terminal_states"],
                    "Record after terminal Run")
        if kind == "run":
            require(index == 1, "Duplicate Run creation")
        elif kind == "cycle":
            require(record["cycle_index"] == len(seen[kind]) + 1, "Cycle allocation gap or reuse")
            expected_parent = stable_cycle_id(record["cycle_index"] - 1) if seen[kind] else None
            require(record["parent_cycle_id"] == expected_parent, "Cycle parent mismatch")
            if expected_parent is None:
                require(record["created_by_attempt_id"] is None and record["trigger_reason"] == "initial", "Invalid initial Cycle")
            else:
                creator = seen["attempt"].get(record["created_by_attempt_id"])
                require(creator is not None and creator[-1]["attempt_kind"] == "decision_coordinator" and
                        creator[-1]["event"] == "finished" and record["trigger_reason"] == "replan", "Invalid replan Cycle")
        elif kind == "attempt":
            require(record["cycle_id"] in seen["cycle"], "Attempt has no parent Cycle")
            if event == "scheduled":
                require(record["attempt_index"] == len(seen[kind]) + 1, "Attempt allocation gap or reuse")
                parent = record["parent_attempt_id"]
                require((not seen[kind] and parent is None) or parent in seen[kind], "Attempt parent mismatch")
            else:
                require(record["attempt_id"] in seen[kind], "Attempt was not scheduled")
                if event == "started":
                    require(run_status == "running" and record["inbound_transition_id"] in seen["transition"],
                            "Attempt started before running lifecycle or inbound Transition")
        elif kind == "transition":
            require(record["transition_index"] == len(seen[kind]) + 1, "Transition allocation gap or reuse")
            source = record["source_attempt_id"]
            require(source not in outbound, "Duplicate outbound Transition")
            outbound.add(source)
            if source is None:
                require(record["source_node"] == "START" and not seen[kind] and record["source_cycle_id"] is None,
                        "Invalid START Transition")
            else:
                life = seen["attempt"].get(source)
                require(life is not None and life[-1]["event"] == "finished", "Source Attempt is not finished")
                require(record["source_node"] == life[-1]["node_name"] and
                        record["source_cycle_id"] == life[-1]["cycle_id"], "Transition source mismatch")
            if record["target_attempt_id"] is not None:
                target = seen["attempt"].get(record["target_attempt_id"])
                require(target is not None and len(target) == 1 and target[0]["event"] == "scheduled",
                        "Transition target was not preallocated exactly once")
                for target_key, attempt_key in (("target_cycle_id", "cycle_id"), ("target_node", "node_name"),
                                                ("target_attempt_kind", "attempt_kind"), ("transition_id", "inbound_transition_id")):
                    require(record[target_key] == target[0][attempt_key], "Transition/Attempt mismatch")
        elif kind == "human_request":
            require(record["cycle_id"] in seen["cycle"] and record["requesting_attempt_id"] in seen["attempt"],
                    "Human Request lineage mismatch")
            if event == "created":
                require(record["request_index"] == len(seen[kind]) + 1, "Request allocation gap or reuse")
                require(not seen[kind] or list(seen[kind].values())[-1][-1]["status"] == "satisfied", "Overlapping Human Request")
            if event == "satisfied":
                require(any(life[-1]["human_request_id"] == record["human_request_id"] and life[-1]["event"] == "consumed"
                            for life in seen["human_response"].values()), "Request satisfied without consumed response")
        elif kind == "human_response":
            request = seen["human_request"].get(record["human_request_id"])
            require(request is not None and request[-1]["status"] == "open" and
                    record["cycle_id"] == request[-1]["cycle_id"], "Response request mismatch")
            if event == "submitted":
                require(record["response_index"] == len(seen[kind]) + 1, "Response allocation gap or reuse")
                previous_responses = [life for life in seen[kind].values() if life[0]["human_request_id"] == record["human_request_id"]]
                require(not previous_responses or previous_responses[-1][-1]["status"] == "invalid", "Response reuse")
            elif event in ("validated", "invalid"):
                validator = seen["attempt"].get(record["validator_attempt_id"])
                require(validator is not None and validator[-1]["status"] == "running" and
                        validator[-1]["attempt_kind"] == "human_gate", "Response validator is not a running Gate")
                if event == "validated":
                    scope = request[0]["authorization_scope"]
                    choice = record["decision"]
                    require(choice in scope.get("allowed_decisions", []) and
                            record["authorized_route"] in scope.get("allowed_target_nodes", []) and
                            record["authorized_transition_route"] == scope.get("decision_transition_routes", {}).get(choice) and
                            record["authorized_transition_target"] == scope.get("decision_transition_targets", {}).get(choice),
                            "Response exceeds exact request authorization")
                    submitted = seen[kind].get(record["human_response_id"])
                    require(submitted is not None and submitted[0]["payload_snapshot"].get("decision") == choice,
                            "Validated decision differs from submitted payload")
            else:
                life = seen[kind].get(record["human_response_id"])
                require(life is not None and life[-1]["event"] == "validated", "Unvalidated response consumption")
                for key in ("decision", "authorized_route", "authorized_transition_route", "authorized_transition_target", "validator_attempt_id"):
                    require(record[key] == life[-1][key], "Response authorization changed")
                require(record["consumer_attempt_id"] in seen["attempt"], "Missing response consumer")
        elif kind == "run_lifecycle":
            require(record["from_status"] == run_status, "Run lifecycle from-status mismatch")
            if record["to_status"] == "running" and run_status == "initializing":
                require(bool(seen["transition"]) and len(seen["cycle"]) == 1 and len(seen["attempt"]) == 1,
                        "Running before bootstrap records")
                require(next(iter(seen["attempt"].values()))[0]["attempt_kind"] == "method_planner", "Wrong initial target")
            if record["to_status"] == "paused":
                require(record["pause_id"] is not None and record["pause_id"] not in pause_ids and
                        record["operation_id"] is not None and record["operation_id"] not in pause_operations and
                        record["budget_event_id"] in seen["budget"], "Missing monotonic Pause guards")
                last_pause = record["pause_id"]
                pause_ids.add(last_pause)
                pause_operations.add(record["operation_id"])
            if run_status == "paused" and record["to_status"] == "running":
                require(record["pause_id"] == last_pause and record["operation_id"] is not None and
                        record["operation_id"] not in pause_operations, "Resume lifecycle binding mismatch")
                pause_operations.add(record["operation_id"])
            if record["to_status"] == "completed":
                tail = list(seen["transition"].values())[-1][-1] if seen["transition"] else None
                require(tail is not None and tail["target_attempt_id"] is None and tail["source_node"] == "memory_report",
                        "Completed requires committed Memory Report END")
            run_status = record["to_status"]
        elif kind == "budget":
            require(record["budget_event_index"] == len(seen[kind]) + 1, "Budget event gap or reuse")
            require(record["policy_digest"] == root["policy_digest"] and record["policy_version"] == root["policy_version"],
                    "Budget policy drift")
            seen[kind][record["budget_event_id"]] = [record]
        if kind in IDENTITIES:
            identity = record[IDENTITIES[kind][0]]
            seen[kind].setdefault(identity, []).append(record)
            if kind == "attempt":
                life = registry._execution_attempt_lifecycle_records(records[:index], identity)
                registry._attempt_provenance_from_lifecycle(life, identity)
            elif kind == "human_request":
                registry._human_request_lifecycle_records(records[:index], identity)
            elif kind == "human_response":
                registry._human_response_lifecycle_records(records[:index], identity)
        previous = digest(record)
    for kind, (identity, index, _) in IDENTITIES.items():
        registry._validate_execution_index_sequence(
            ((key, life[0][index]) for key, life in seen[kind].items()), label=kind,
            prefix=kind, width=4 if kind == "cycle" else 6)
    budget = _budget_projection(records, seen)
    projection = {"schema_version": "0.4", "run_id": root["run_id"], "case_id": root["case_id"],
                  "parent_run_id": root["parent_run_id"], "run_status": run_status,
                  "execution_head": previous, "execution_event_index": len(records),
                  "checkpoint_thread_id": root["checkpoint_thread_id"], **_identity_projection(seen), "budget": budget}
    return ExecutionReplay(tuple(canonical_bytes(record) for record in records), ValidatedValue.from_value(projection))


def replay(records):
    """Validate an in-memory ledger prefix, without granting publication permission."""
    try:
        return _checked_replay(records)
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        raise ControlIntegrityError(str(error)) from error


def parse_ledger(data):
    require(type(data) is bytes and data.endswith(b"\n"), "Partial execution ledger line")
    return replay([parse_record(line).value for line in data[:-1].split(b"\n")])


def append_record_bytes(ledger, record):
    """Return validated new bytes. Only a later durable owner may publish them."""
    prior = [] if ledger == b"" else parse_ledger(ledger).values
    result = replay([*prior, record])
    return b"\n".join(result.records) + b"\n"


def _identity_projection(seen):
    latest = {kind: list(lives.values())[-1][-1] if lives else {} for kind, lives in seen.items()}
    cycle, attempt, transition, request = (latest[kind] for kind in ("cycle", "attempt", "transition", "human_request"))
    responses = [life[-1] for life in seen["human_response"].values()
                 if life[0]["human_request_id"] == request.get("human_request_id")]
    response = responses[-1] if responses else {}
    value = {"cycle_id": cycle.get("cycle_id"), "cycle_index": cycle.get("cycle_index", 0),
             "parent_cycle_id": cycle.get("parent_cycle_id"),
             "attempt_id": attempt.get("attempt_id"), "attempt_index": attempt.get("attempt_index", 0),
             "parent_attempt_id": attempt.get("parent_attempt_id"), "attempt_kind": attempt.get("attempt_kind"),
             "attempt_node": attempt.get("node_name"), "attempt_trigger": attempt.get("attempt_trigger"),
             "attempt_status": attempt.get("status"), "inbound_transition_id": attempt.get("inbound_transition_id"),
             "transition_index": transition.get("transition_index", 0),
             "committed_transition_id": transition.get("transition_id"), "committed_route": transition.get("route"),
             "human_request_index": request.get("request_index", 0), "human_response_index": len(seen["human_response"]),
             "active_human_request_id": request.get("human_request_id"),
             "human_requesting_attempt_id": request.get("requesting_attempt_id"),
             "human_request_kind": request.get("request_kind"), "human_request_status": request.get("status"),
             "human_request_authorization_scope": request.get("authorization_scope"),
             "active_human_response_id": response.get("human_response_id")}
    for target, source in (("status", "status"), ("decision", "decision"), ("authorized_route", "authorized_route"),
                           ("authorized_transition_route", "authorized_transition_route"),
                           ("authorized_transition_target", "authorized_transition_target"),
                           ("validator_attempt_id", "validator_attempt_id"), ("consumer_attempt_id", "consumer_attempt_id"),
                           ("target_attempt_id", "authorized_target_attempt_id")):
        value["human_response_" + target] = response.get(source)
    return value


def _budget_projection(records, seen):
    events = [record for record in records if record["record_type"] == "budget"]
    if not events:
        failed_before_policy_record = (len(records) == 2 and records[1]["record_type"] == "run_lifecycle" and
                                       records[1]["from_status"] == "initializing" and records[1]["to_status"] == "failed")
        require(len(records) == 1 or failed_before_policy_record, "Policy initialization must follow Run creation")
        return None
    require(records[1] is events[0] and events[0]["event"] == "policy_initialized", "Policy initialization order")
    policy = validate_policy(events[0]["payload"]["policy"]).value
    require(policy["policy_digest"] == records[0]["policy_digest"], "Run policy binding mismatch")
    if len(records) > 2:
        failed_before_admission = (records[2]["record_type"] == "run_lifecycle" and
                                   records[2]["from_status"] == "initializing" and records[2]["to_status"] == "failed")
        require(failed_before_admission or
                (records[2]["record_type"] == "budget" and records[2]["event"] == "decision_recorded" and
                 records[2]["payload"]["decision"] == "allow"), "Missing bootstrap admission record")
    reservations, settlements, fingerprints, grants, consumed = {}, {}, {}, {}, set()
    latest_failure = None
    latest_decision = None
    ordinals = {}
    aggregate_bindings = set()
    for record in events:
        event, payload = record["event"], record["payload"]
        if event == "policy_initialized":
            require(record is events[0], "Duplicate policy initialization")
        elif event == "resource_reserved":
            identity, attempt = payload["resource_operation_id"], payload["attempt_id"]
            require(identity not in reservations and attempt in seen["attempt"], "Duplicate or unbound resource")
            require(seen["attempt"][attempt][0]["event_index"] < record["event_index"], "Reservation precedes Attempt")
            prior_lifecycle = [item for item in seen["attempt"][attempt] if item["event_index"] < record["event_index"]]
            is_backend = payload["resource_kind"] == "code_backend_operation"
            require(prior_lifecycle[-1]["status"] == ("scheduled" if is_backend else "running"),
                    "Resource reservation at an invalid Attempt boundary")
            require(payload["ordinal"] == ordinals.get(attempt, 0) + 1, "Resource ordinal gap")
            ordinals[attempt] = payload["ordinal"]
            if payload["resource_kind"] == "code_backend_operation":
                require(seen["attempt"][attempt][0]["attempt_kind"] == "code_agent", "Backend reservation for non-Code Attempt")
                bindings = {(key, payload[key]) for key in ("attempt_id", "producer_operation_id", "workspace_id", "task_id", "task_digest")}
                require(not bindings.intersection(aggregate_bindings), "Duplicate Backend aggregate")
                aggregate_bindings.update(bindings)
            for key, amount in payload["maximum_charge"].items():
                attempt_used = run_used = 0
                for prior_id, prior in reservations.items():
                    settled = settlements.get(prior_id)
                    charge = settled["actual"] if settled and settled["actual"] is not None else prior["maximum_charge"]
                    run_used += charge[key]
                    if prior["attempt_id"] == attempt:
                        attempt_used += charge[key]
                if key == "verification_commands":
                    limit = policy["limits"]["verification_commands_per_code_attempt"] if prior_lifecycle[-1]["attempt_kind"] == "code_agent" else 0
                    remaining = max(0, limit - attempt_used)
                else:
                    limit = min(policy["limits"][key + "_per_attempt"], policy["limits"][key + "_per_run"])
                    remaining = max(0, min(policy["limits"][key + "_per_attempt"] - attempt_used,
                                           policy["limits"][key + "_per_run"] - run_used))
                require(payload["applicable_limits"][key] == limit and payload["remaining_before"][key] == remaining,
                        "Reservation limits or remaining disagree with policy replay")
                require(amount <= payload["applicable_limits"][key] and amount <= payload["remaining_before"][key],
                        "Reservation exceeds frozen available window")
            call_dimension = {"llm_call": "llm_calls", "tool_call": "tool_calls", "verification_command": "verification_commands"}
            if is_backend:
                require(payload["maximum_charge"]["verification_commands"] == 0, "Backend cannot reserve trusted verification")
            else:
                dimension = call_dimension[payload["resource_kind"]]
                require(payload["maximum_charge"][dimension] == 1 and
                        all(value == 0 for key, value in payload["maximum_charge"].items() if key not in (dimension, "active_seconds")),
                        "Ordinary reservation must bind exactly one resource call")
            reservations[identity] = payload
        elif event == "resource_settled":
            identity = payload["resource_operation_id"]
            require(identity in reservations and identity not in settlements, "Unknown or duplicate settlement")
            settlements[identity] = payload
        elif event == "failure_observed":
            failure = payload["fingerprint"]
            key = failure["causal_context_digest"], failure["fingerprint_digest"]
            require(payload["occurrence"] == fingerprints.get(key, 0) + 1, "Fingerprint occurrence mismatch")
            require(failure["context"]["policy_digest"] == policy["policy_digest"], "Fingerprint policy mismatch")
            fingerprints[key] = payload["occurrence"]
            latest_failure = {"fingerprint_digest": key[1], "causal_context_digest": key[0], "occurrence": payload["occurrence"]}
        elif event == "grant_issued":
            identity = payload["budget_grant_id"]
            require(identity not in grants and payload["budget_grant_index"] == len(grants) + 1, "Grant index mismatch")
            response = seen["human_response"].get(payload["human_response_id"])
            require(response is not None and any(item["event"] == "validated" and item["event_index"] < record["event_index"]
                                                 for item in response), "Grant lacks validated response")
            require(any(item["event"] == "validated" and item["decision"] == "approve_budget_window" for item in response),
                    "Grant requires the typed budget-window action")
            require(not any(item["human_response_id"] == payload["human_response_id"] for item in grants.values()),
                    "Human budget-window authorization already issued a grant")
            require(response[0]["payload_sha256"] == payload["response_digest"] and
                    response[0]["human_request_id"] == payload["human_request_id"] and
                    response[0]["cycle_id"] == payload["cycle_id"] and
                    response[0]["payload_reference"] == payload["response_reference"], "Grant authorization mismatch")
            require(latest_failure is not None and latest_failure["fingerprint_digest"] == payload["fingerprint_digest"] and
                    latest_failure["occurrence"] == payload["occurrence"], "Grant failure context mismatch")
            from lqcd_agent.graph.state import canonical_attempt_kind, stable_attempt_id, stable_transition_id
            prior_attempts = sum(life[0]["event_index"] < record["event_index"] for life in seen["attempt"].values())
            prior_transitions = sum(life[0]["event_index"] < record["event_index"] for life in seen["transition"].values())
            require(payload["target_attempt_id"] == stable_attempt_id(prior_attempts + 1) and
                    payload["transition_id"] == stable_transition_id(prior_transitions + 1) and
                    canonical_attempt_kind(payload["target_node"]) == payload["target_attempt_kind"], "Grant target intent mismatch")
            grants[identity] = payload
        elif event == "grant_consumed":
            identity = payload["budget_grant_id"]
            require(identity in grants and identity not in consumed, "Unknown or duplicate grant consumption")
            grant = grants[identity]
            require(payload["grant_digest"] == digest(grant) and payload["target_attempt_id"] == grant["target_attempt_id"] and
                    payload["transition_id"] == grant["transition_id"], "Grant consumption scope mismatch")
            target = seen["attempt"].get(payload["target_attempt_id"])
            if target:
                require(target[0]["event_index"] > record["event_index"] and
                        target[0]["attempt_kind"] == grant["target_attempt_kind"] and target[0]["cycle_id"] == grant["cycle_id"],
                        "Grant consumed after target allocation or for a changed target")
            consumed.add(identity)
        elif event == "decision_recorded":
            latest_decision = {key: payload[key] for key in ("proposal_id", "decision", "reason_code", "next_control_action", "decision_digest")}
    totals = {"cycles_per_run": len(seen["cycle"]), "work_attempts_per_run": 0, "control_attempts_per_run": 0,
              "transitions_per_run": len(seen["transition"]), "automatic_replan_per_run": 0,
              "automatic_code_fix_per_cycle": 0, "automatic_analysis_rerun_per_cycle": 0, "automatic_re_review_per_cycle": 0,
              "llm_calls_per_attempt": 0, "llm_calls_per_run": 0, "tool_calls_per_attempt": 0, "tool_calls_per_run": 0,
              "verification_commands_per_code_attempt": 0, "active_seconds_per_attempt": 0, "active_seconds_per_run": 0}
    for life in seen["attempt"].values():
        totals["work_attempts_per_run" if life[0]["attempt_kind"] in WORK_KINDS else "control_attempts_per_run"] += 1
    current_attempt = list(seen["attempt"])[-1] if seen["attempt"] else None
    current_cycle = list(seen["cycle"])[-1] if seen["cycle"] else None
    route_by_target = {"method_planner": "automatic_replan_per_run", "code_agent": "automatic_code_fix_per_cycle",
                       "analysis_engineer": "automatic_analysis_rerun_per_cycle", "scientific_reviewer": "automatic_re_review_per_cycle"}
    for life in seen["transition"].values():
        transition = life[0]
        source = seen["attempt"].get(transition["source_attempt_id"])
        dimension = route_by_target.get(transition["target_attempt_kind"])
        if source and source[0]["attempt_kind"] == "decision_coordinator" and dimension:
            if dimension.endswith("per_run") or transition["target_cycle_id"] == current_cycle:
                totals[dimension] += 1
    for identity, reservation in reservations.items():
        settlement = settlements.get(identity)
        charge = settlement["actual"] if settlement and settlement["actual"] is not None else reservation["maximum_charge"]
        for resource, amount in charge.items():
            if resource != "verification_commands":
                totals[resource + "_per_run"] += amount
            if reservation["attempt_id"] == current_attempt:
                key = "verification_commands_per_code_attempt" if resource == "verification_commands" else resource + "_per_attempt"
                totals[key] += amount
    dimensions = {key: {"used": amount, "remaining": max(0, policy["limits"][key] - amount)} for key, amount in totals.items()}
    active_grants = [grant for key, grant in grants.items() if key not in consumed]
    require(len(active_grants) <= 1, "Overlapping active grants")
    return {"policy_version": "0.1", "profile_id": policy["profile_id"], "policy_reference": "budget_policy.json",
            "policy_digest": policy["policy_digest"], "budget_event_index": len(events), "budget_grant_index": len(grants),
            "dimensions": dimensions, "active_failure": latest_failure,
            "active_grant": active_grants[-1] if active_grants else None,
            "latest_decision": latest_decision,
            "exhausted_dimensions": sorted(key for key, value in dimensions.items() if value["remaining"] == 0),
            "stop_reason": latest_decision["reason_code"] if latest_decision and latest_decision["decision"] == "halt" else None}
