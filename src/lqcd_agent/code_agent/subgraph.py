"""Trusted Code Attempt consumption under the original B02 resume owner."""
from hashlib import sha256

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


CANONICAL_PATH_MEMBERS = {
    "code_agent_task_path": "code_agent_task.json",
    "code_agent_result_path": "code_agent_result.json",
    "code_change_manifest_path": "change_manifest.json",
    "code_verification_results_path": "verification_results.json",
}


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
        state_paths = {"code_change_summary_path": None, "tests_status_path": None}
        state_paths.update({key: str(root / "attempts" / task["attempt_id"] / member)
                            for key, member in CANONICAL_PATH_MEMBERS.items()})
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
                outcome.artifact.state_paths == {"code_change_summary_path": None, "tests_status_path": None,
                    **{key: str(root / "attempts" / task["attempt_id"] / member)
                       for key, member in CANONICAL_PATH_MEMBERS.items()}},
                "Code result or projection differs from validated delivery")
        expected_members = bundle_members(task, result, receipt, manifest, seal, changes, verification, audit, patch)
        require(actual == expected_members, "Code bundle member set or bytes changed")
        members = [{"path": str(path.relative_to(root)), "sha256": sha256(read_regular(path)).hexdigest()}
                   for path in outcome.artifact.member_paths]
        return CodeConsumptionProof(binding["value"]["producer_operation_id"],
                                    binding["value"]["terminal_evidence_digest"], identity["attempt_id"],
                                    digest(members), outcome.status)
