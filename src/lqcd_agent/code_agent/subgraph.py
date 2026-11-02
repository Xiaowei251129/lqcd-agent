"""Trusted Code Attempt consumption under the original B02 resume owner."""
from hashlib import sha256
from pathlib import Path

from lqcd_agent.artifacts.contracts import CODE_MEMBER_BY_STATE_FIELD
from lqcd_agent.control.capabilities import ArtifactOutput, CodeConsumptionProof, TargetOutcome
from lqcd_agent.control.coordinator import boundary, read_regular
from lqcd_agent.control.execution import parse_ledger
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, require

from .artifacts import bundle_members, canonical_result, validate_code_result
from .backend import validate_receipt
from .ingress import preflight_result
from .schemas import validate_manifest, validate_task
from .verification import TrustedVerifier, build_verification_results
from .workspace import WorkspaceProvider, immutable_git_tree


class CodeAgentSubgraph:
    """The Backend stays outside the graph; this port only consumes its proof."""

    def __init__(self, coordinator, base_repository):
        self.coordinator = coordinator
        self.base_repository = base_repository
        self.provider = WorkspaceProvider(coordinator.root / "code_workspaces")
        self.verifier = TrustedVerifier(coordinator.root / "verification_workspaces")

    def preflight_delivery(self, binding):
        require(type(binding) is dict and binding.get("tag") == "normal_final", "Missing normal Code delivery")
        value, final = binding["value"], binding["final"]
        require(value["resolution_owner"] == "normal" and value["proof_kind"] == final["proof_kind"] == "safe_stop" and
                value["operation_phase"] == "external_final_evidence_committed", "Unfinished Code delivery")
        locator = value["run_locator"]
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        directory = root / "code_agent_control" / value["attempt_id"]
        require(directory == directory.resolve() and directory.is_relative_to(root),
                "Code delivery directory escaped its Run")
        task = validate_task(read_regular(directory / "code_agent_task.json")).value
        manifest = validate_manifest(read_regular(directory / "workspace_manifest.json"), task).value
        receipt = validate_receipt(read_regular(root / value["dispatch_receipt_reference"]), task, manifest).value
        seal = loads(read_regular(directory / "workspace_seal.json"))
        changes = loads(read_regular(directory / "change_manifest.json"))
        audit = read_regular(directory / "tool_audit.jsonl")
        patch_path = directory / "changes.patch"
        require(not patch_path.is_symlink(), "Code patch path is a symlink")
        patch = read_regular(patch_path) if patch_path.exists() else None
        raw = read_regular(root / value["result_reference"])
        require(task["producer_operation_id"] == value["producer_operation_id"] and
                task["attempt_id"] == value["attempt_id"] and
                manifest["workspace_id"] == value["workspace_id"] and
                task["task_digest"] == value["task_digest"] and
                manifest["manifest_digest"] == value["workspace_manifest_digest"] and
                sha256(canonical_bytes(receipt)).hexdigest() == value["dispatch_receipt_digest"] and
                sha256(raw).hexdigest() == value["result_digest"] and
                seal.get("seal_digest") == value["workspace_seal_digest"] == final["workspace_seal_digest"],
                "Code delivery source changed")
        base = immutable_git_tree(self.base_repository, task["base_revision"])
        external = preflight_result(raw, task, manifest, receipt, seal, changes, audit, patch,
                                    self.provider, value["prestart"]["workspace"], base)
        require(external.value["resource_usage"] == final["resource_actual"],
                "Code delivery usage differs from the normal final")
        observed = self.provider.verify_sealed(manifest, value["prestart"]["workspace"], seal["final_tree_digest"])
        return root, task, manifest, receipt, seal, changes, audit, patch, external, base, observed

    @staticmethod
    def _diagnostic(status, passed):
        if status == "success":
            return ("none", "not_retryable") if passed else ("verification_failed", "new_attempt_allowed")
        return {
            "no_change": ("no_safe_change", "new_evidence_required"),
            "failed": ("tool_error", "new_attempt_allowed"),
            "needs_input": ("dependency_unavailable", "new_evidence_required"),
            "needs_human": ("dependency_unavailable", "human_required"),
            "budget_exhausted": ("dependency_unavailable", "new_evidence_required"),
            "policy_blocked": ("policy_violation", "human_required"),
        }[status]

    @staticmethod
    def _trusted_usage(root, attempt_id, backend_actual):
        records = parse_ledger(read_regular(root / "execution_history.jsonl")).values
        reserved = {row["payload"]["resource_operation_id"] for row in records if
                    row["record_type"] == "budget" and row["event"] == "resource_reserved" and
                    row["payload"]["resource_kind"] == "verification_command" and
                    row["payload"]["attempt_id"] == attempt_id}
        settled = {row["payload"]["resource_operation_id"]: row["payload"] for row in records if
                   row["record_type"] == "budget" and row["event"] == "resource_settled" and
                   row["payload"]["resource_operation_id"] in reserved}
        require(set(settled) == reserved and all(item["actual"] is not None for item in settled.values()),
                "Trusted verification resources are not fully settled")
        usage = dict(backend_actual)
        for item in settled.values():
            for name, amount in item["actual"].items():
                usage[name] += amount
        return usage

    def consume_external(self, identity, binding, port):
        root, task, manifest, receipt, seal, changes, audit, patch, external, base, final = self.preflight_delivery(binding)
        require(identity["attempt_kind"] == "code_agent" and
                all(identity[name] == task[name] for name in ("case_id", "run_id", "attempt_id")),
                "Code consumer received a foreign Attempt")
        fence = lambda: port.leases.require_effect_authority(port.capability_id, port.worker, port.epoch)
        fence()
        boundary(self.coordinator.observer, "external.trusted_verification", "before", value=identity)
        verification = self.verifier.verify_all(task, base, final, candidate_status=external.value["declared_status"],
                                                fence=fence, port=port)
        boundary(self.coordinator.observer, "external.trusted_verification", "after", value=identity)
        failure_class, retryability = self._diagnostic(external.value["declared_status"],
                                                       verification["all_required_passed"])
        usage = self._trusted_usage(root, task["attempt_id"], binding["final"]["resource_actual"])
        result = canonical_result(task, external, receipt, manifest, seal, changes, verification,
                                  failure_class=failure_class, retryability=retryability,
                                  recommended_action="review Code result", summary="Validated Code delivery",
                                  trusted_usage=usage)
        members = bundle_members(task, result, receipt, manifest, seal, changes, verification, audit, patch)
        paths = tuple(port.write_member(name, content) for name, content in members.items())
        state_paths = {key: str(root / "attempts" / task["attempt_id"] / member)
                       for key, member in CODE_MEMBER_BY_STATE_FIELD.items()}
        index = loads(read_regular(root / "artifact_index.json"))
        refs = {slot: pointer["artifact_id"] for slot, pointer in index["current"].items() if pointer is not None}
        refs["code"] = task["attempt_id"] + ":code"
        return TargetOutcome("succeeded", {"current_artifact_ids": refs},
                             artifact=ArtifactOutput("code", paths, state_paths, result["status"]))

    def verify_consumption(self, identity, binding, outcome):
        root, task, manifest, receipt, seal, changes, audit, patch, external, _, _ = self.preflight_delivery(binding)
        require(outcome.artifact is not None and outcome.artifact.slot == "code" and
                identity["attempt_id"] == task["attempt_id"], "Code artifact proof lost its Attempt")
        actual = {path.name: read_regular(path) for path in outcome.artifact.member_paths}
        result = validate_code_result(actual["code_agent_result.json"], task).value
        verification = loads(actual["verification_results.json"])
        require(verification == build_verification_results(task, verification["spec_results"]),
                "Code verification member changed")
        failure_class, retryability = self._diagnostic(external.value["declared_status"],
                                                       verification["all_required_passed"])
        expected = canonical_result(task, external, receipt, manifest, seal, changes, verification,
                                    failure_class=failure_class, retryability=retryability,
                                    recommended_action="review Code result", summary="Validated Code delivery",
                                    trusted_usage=self._trusted_usage(root, task["attempt_id"], binding["final"]["resource_actual"]))
        require(result == expected and outcome.artifact.status == result["status"] and
                outcome.artifact.state_paths == {key: str(root / "attempts" / task["attempt_id"] / member)
                                                 for key, member in CODE_MEMBER_BY_STATE_FIELD.items()},
                "Code result or projection differs from validated delivery")
        expected_members = bundle_members(task, result, receipt, manifest, seal, changes, verification, audit, patch)
        require(actual == expected_members, "Code bundle member set or bytes changed")
        members = [{"path": str(path.relative_to(root)), "sha256": sha256(read_regular(path)).hexdigest()}
                   for path in outcome.artifact.member_paths]
        return CodeConsumptionProof(binding["value"]["producer_operation_id"],
                                    binding["value"]["terminal_evidence_digest"], identity["attempt_id"],
                                    digest(members), outcome.status)


class ProductCodeHost:
    """Compose the original B03 producer ports for a committed product target."""

    def __init__(self, coordinator, base_repository, backend, containment, *, task_policy,
                 maximum_charge, timeout_seconds, lease_seconds=30):
        from lqcd_agent.control.strict_json import closed, number
        from .schemas import POLICIES
        from .workspace import tree_digest

        closed(task_policy, ("base_revision", "base_tree_digest", *POLICIES, "verification_specs",
                            "task_summary", "acceptance_criteria", "coding_backend_kind",
                            "backend_version", "backend_runtime_fingerprint"))
        number(timeout_seconds)
        number(lease_seconds)
        require(timeout_seconds > 0 and lease_seconds > 0, "Invalid product Code timeout")
        require(tree_digest(immutable_git_tree(base_repository, task_policy["base_revision"])) ==
                task_policy["base_tree_digest"], "Product Code base changed")
        self.coordinator, self.base_repository = coordinator, base_repository
        self.backend, self.containment = backend, containment
        self.task_policy = loads(canonical_bytes(task_policy))
        self.maximum_charge = loads(canonical_bytes(maximum_charge))
        self.timeout_seconds, self.lease_seconds = timeout_seconds, lease_seconds
        self.consumer = CodeAgentSubgraph(coordinator, base_repository)

    def _task(self, producer, authorization):
        from lqcd_agent.control.pause import runtime_fingerprint
        from lqcd_agent.graph.state import product_context

        root = self.coordinator.root / producer["run_locator"]["case_id"] / producer["run_locator"]["run_id"]
        identity = authorization["identity"]
        execution = parse_ledger(read_regular(root / "execution_history.jsonl"))
        index = loads(read_regular(root / "artifact_index.json"))
        context = product_context(root, identity, execution, index)
        plan = index["current"]["plan"]
        require(plan is not None, "Product Code lacks a current Plan")
        content = loads(read_regular(root / next(m["canonical_path"] for m in plan["members"]
                                               if m["logical_name"] == "method_plan.json")))
        records = execution.values
        inbound = next(r for r in records if r["record_type"] == "transition" and
                       r["target_attempt_id"] == identity["attempt_id"])
        decision = next(r for r in reversed(records) if r.get("event") == "decision_recorded")
        policy = loads(read_regular(root / "budget_policy.json"))
        packet = context["remediation"]
        require((inbound["source_node"] == "method_planner" and packet is None) or
                (inbound["source_node"] == "decision_coordinator" and packet is not None),
                "Product Code lacks its original planner or remediation source")
        plan_member = next(m for m in plan["members"] if m["logical_name"] == "method_plan.json")
        evidence = [{"artifact_id": plan["artifact_id"], "path": plan_member["canonical_path"], "sha256": plan_member["sha256"]}]
        if packet is not None:
            for ref in packet["evidence"]:
                item = {"artifact_id": ref["artifact_id"], "path": ref["member"], "sha256": ref["sha256"]}
                if item not in evidence:
                    evidence.append(item)
        human = None
        if packet is not None and packet["human_authorization"] is not None:
            ref = packet["human_authorization"]
            response = next(r for r in records if r.get("record_type") == "human_response" and
                            r["event"] == "consumed" and r["human_response_id"] == ref["human_response_id"])
            request = next(r for r in records if r.get("record_type") == "human_request" and
                           r["event"] == "created" and r["human_request_id"] == ref["human_request_id"])
            require(response["payload_sha256"] == ref["response_digest"] and ref["target_node"] == "code_agent" and
                    response["authorized_target_attempt_id"] == inbound["source_attempt_id"] and
                    response["human_request_id"] == request["human_request_id"] and
                    all(response[k] == request[k] == producer["run_locator"][k] for k in ("case_id", "run_id")) and
                    response["cycle_id"] == request["cycle_id"] == producer["cycle_id"] and
                    request["authorization_scope"]["work_target"] == "code_agent" and
                    response["decision"] in request["authorization_scope"]["allowed_decisions"],
                    "Code remediation has a foreign Human authorization")
            payload_path = Path(response["payload_reference"])
            if not payload_path.is_absolute():
                payload_path = root / payload_path
            require(payload_path.resolve() == payload_path and payload_path.is_relative_to(root),
                    "Code Human snapshot escaped its Run")
            payload_raw = read_regular(payload_path)
            require(sha256(payload_raw).hexdigest() == response["payload_sha256"], "Code Human snapshot changed")
            payload = loads(payload_raw)
            pause, = [r for r in records if r.get("record_type") == "pause" and r["event"] == "pause_consumed" and
                      r["proof"].get("input_digest") == response["payload_sha256"] and r["proof"].get("input_snapshot") == payload]
            resumed = self.coordinator.get(pause["operation_id"])
            actor = resumed["request"]["actor"]
            require(resumed["status"] == "committed" and resumed["operation_type"] == "resume_run" and
                    resumed["request"]["input_kind"] == "human_response" and
                    resumed["request_digest"] == pause["proof"]["request_digest"] and
                    resumed["request"]["input_snapshot"] == payload and resumed["request"]["input_digest"] == response["payload_sha256"] and
                    payload["decided_by"] == actor["actor_id"] and actor == pause["proof"]["actor"] and
                    actor["actor_type"] == pause["authorization_scope"]["actor_type"] and
                    set(pause["authorization_scope"]["scopes"]) <= set(actor["scopes"]),
                    "Code Human authorization lacks its original Resume actor")
            human = {"artifact_id": response["human_response_id"],
                     "path": str(payload_path.relative_to(root)),
                     "sha256": response["payload_sha256"], "action": response["decision"],
                     "scope_digest": digest(request["authorization_scope"]), "single_use_id": response["human_response_id"]}
        task = {**self.task_policy, **producer["run_locator"], "cycle_id": producer["cycle_id"],
                "attempt_id": identity["attempt_id"], "transition_id": inbound["transition_id"],
                "producer_operation_id": producer["producer_operation_id"], "schema_version": "0.1",
                "task_id": identity["attempt_id"] + ":code_task", "source_attempt_id": inbound["source_attempt_id"],
                "attempt_kind": "code_agent", "node_name": "code_agent",
                "task_origin": "coordinator_code_fix" if packet is not None else "planner_gap",
                "requirements": content.get("requirements"),
                "evidence": evidence,
                "execution_head": digest(inbound), "artifact_head": index["artifact_head"],
                "source_runtime_fingerprint": runtime_fingerprint(), "budget_policy_version": "0.1",
                "budget_profile_id": policy["profile_id"], "budget_policy_digest": policy["policy_digest"],
                "budget_envelope_ref": {"path": "execution_history.jsonl", "event_id": decision["event_id"]},
                "budget_envelope_digest": digest(decision), "human_authorization_ref": human,
                "external_producer_contract": {"schema_version": "0.1",
                    "parent_control_operation_id": producer["parent_control_operation_id"]}, "expected_result_schema": "0.1"}
        if packet is not None:
            task.update(task_summary=packet["problem"], requirements=task["requirements"] + packet["constraints"],
                        acceptance_criteria=packet["success_criteria"])
        task["task_digest"] = digest(task)
        return validate_task(task).value

    def prepare(self, capability_id, *, worker_id, actor):
        from lqcd_agent.control.capabilities import InvocationLeases
        from lqcd_agent.control.interfaces import ControlPlane
        from lqcd_agent.control.operations import ExternalControl
        from lqcd_agent.control.pause import PublishPauseRequest
        from .external_operation import ExternalProducer
        from .prestart import CodePrestart
        from .schemas import IDENTITY, POLICIES

        _, capability = InvocationLeases(self.coordinator).get(capability_id)
        authorization = capability["authorization"]
        matches = [ExternalControl(self.coordinator).read(self.coordinator.connection, r[0])
                   for r in self.coordinator.connection.execute("SELECT external_operation_id FROM external_operations")]
        matches = [r for r in matches if r["parent_control_operation_id"] == authorization["producer_operation_id"]]
        require(len(matches) <= 1, "Multiple product Code producers")
        deadline = matches[0]["hard_deadline"] if matches else self.coordinator._time().monotonic_seconds + self.timeout_seconds
        producer = ExternalProducer(self.coordinator).reserve(capability_id,
            backend_kind=self.task_policy["coding_backend_kind"], backend_version=self.task_policy["backend_version"],
            hard_deadline=deadline, worker_id=worker_id, lease_seconds=self.lease_seconds)
        if producer["operation_phase"] in ("pause_bound", "dispatch_authorized", "dispatch_receipt_committed",
                                            "result_reference_committed", "external_final_evidence_committed"):
            if producer["resolution_owner"] is None:
                self._dispatch(producer, worker_id).dispatch()
            return ExternalProducer(self.coordinator).lookup(producer["producer_operation_id"])
        prestart = CodePrestart(self.coordinator, producer["producer_operation_id"], worker_id, producer["lease_epoch"])
        task = producer.get("prestart", {}).get("task") or self._task(producer, authorization)
        prestart.commit_task(task)
        manifest = producer.get("prestart", {}).get("manifest")
        if manifest is None:
            fields = (*IDENTITY, "task_id", "task_digest", "base_revision", "base_tree_digest",
                      "source_runtime_fingerprint", "coding_backend_kind", "backend_version", "backend_runtime_fingerprint")
            manifest = {**{k: task[k] for k in fields}, "schema_version": "0.1", "workspace_id": producer["workspace_id"],
                        "workspace_generation": 1, "workspace_implementation": "host_managed",
                        "policy_digests": {k: digest(task[k]) for k in POLICIES},
                        "created_at": self.coordinator._time().wall_seconds, "owner": worker_id,
                        "managed_root_identity": producer["managed_workspace_locator_digest"]}
            manifest["manifest_digest"] = digest(manifest)
        prestart.commit_manifest(manifest)
        maximum = {**self.maximum_charge, "active_seconds": producer["prestart"]["active_time"]["backend_maximum_seconds"]}
        prestart.reserve_aggregate(maximum_charge=maximum, timeout_seconds=maximum["active_seconds"],
                                  config_digest=digest(self.task_policy))
        prestart.commit_core()
        prestart.materialize_workspace(self.base_repository)
        plane = ControlPlane(self.coordinator, worker_id=worker_id)
        plane.publish_pause(PublishPauseRequest(producer["run_locator"], "external_result", task["attempt_id"], task["attempt_id"],
            {"kind": "external_result", "producer_operation_id": producer["producer_operation_id"]},
            {"actor_type": "human", "scopes": ["resume"]}, "product-code-pause:" + digest(producer["run_locator"]) + ":" + task["attempt_id"]), actor=actor)
        self._dispatch(producer, worker_id).dispatch()
        return ExternalProducer(self.coordinator).lookup(producer["producer_operation_id"])

    def _dispatch(self, producer, worker_id):
        from .external_operation import ExternalDispatch
        return ExternalDispatch(self.coordinator, producer["producer_operation_id"], worker_id, producer["lease_epoch"],
                                self.backend, self.containment, self.backend.read_receipt, self.backend.read_result)

    def finalize(self, producer_operation_id, *, tool_audit, patch):
        from .external_operation import ExternalNormalFinal, ExternalProducer
        producer = ExternalProducer(self.coordinator).lookup(producer_operation_id)
        dispatch = self._dispatch(producer, producer["worker_owner_id"])
        if producer["resolution_owner"] is None:
            dispatch.publish_result_reference()
        return ExternalNormalFinal(dispatch, self.base_repository).commit(tool_audit=tool_audit, patch=patch)
