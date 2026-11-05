"""Freeze a registered Code bundle into an isolated Analysis preparation."""
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys

from lqcd_agent.control.coordinator import boundary, publish_exact, read_regular
from lqcd_agent.control.operations import PreparationVerification
from lqcd_agent.control.strict_json import canonical_bytes, closed, digest, require, loads

from .artifacts import bundle_members, validate_code_result
from .numerical_trials import trial_member
from .schemas import validate_task, validate_manifest
from .workspace import (WorkspaceProvider, canonical_patch, immutable_git_tree, scan_tree,
                        tree_digest, validate_changes)


SPEC_FIELDS = ("schema_version", "analysis_execution_spec_id", "target_attempt_identity",
               "inbound_transition_identity", "source_code_attempt_id", "source_code_bundle_id_digest",
               "source_member_digests", "producing_task_digest", "base_revision", "base_tree_digest",
               "change_manifest_digest", "patch_digest", "expected_effective_tree_digest",
               "selected_input_artifacts", "analysis_runtime_fingerprint", "environment_policy",
               "allowed_command", "expected_outputs", "fresh_workspace_identity",
               "workspace_manifest_digest", "spec_digest")
MANIFEST_FIELDS = ("schema_version", "workspace_id", "manifest_digest", "managed_root_identity",
                   "base_tree_digest", "target_attempt_identity", "inbound_transition_identity",
                   "source_code_bundle_id_digest", "expected_effective_tree_digest")


class AnalysisHandoff:
    """A trusted B02 target-preparation adapter, without product route ownership."""

    def __init__(self, coordinator, base_repository, *, allowed_command, expected_outputs=(),
                 generated_program=None, workspace=None):
        self.coordinator = coordinator
        self.base_repository = Path(base_repository)
        self.provider = WorkspaceProvider(coordinator.root / "analysis_workspaces")
        require(type(allowed_command) in (list, tuple) and allowed_command and
                all(type(part) is str and part for part in allowed_command), "Missing trusted Analysis command")
        require(type(expected_outputs) in (list, tuple) and
                all(type(part) is str and part for part in expected_outputs), "Invalid Analysis outputs")
        self.allowed_command = list(allowed_command)
        self.expected_outputs = list(expected_outputs)
        self.generated_program = loads(canonical_bytes(generated_program)) if generated_program is not None else None
        self.workspace = workspace
        self.timeout_seconds = generated_program['timeout_seconds'] if generated_program is not None else 10

    def _environment(self, locator):
        policy = {'network': 'disabled', 'inherited_environment': False, 'python_isolated': True,
                  'timeout_seconds': self.timeout_seconds}
        if self.generated_program is not None:
            from .execution import interpreter_identity
            goal = loads(read_regular(self._run_root(locator)/'root_goal.json'))
            require(goal['workspace'] == str(self.workspace), 'Scientific workspace changed')
            require(goal['dataset_snapshot'] is not None and goal['dataset_snapshot']['exists'],
                    'Generated analysis requires a frozen existing dataset')
            policy.update(generated_program={k: self.generated_program[k] for k in
                ('python', 'parameters', 'timeout_seconds', 'result_kind')},
                dataset_snapshot=goal['dataset_snapshot'], runtime=interpreter_identity(self.allowed_command[0]))
        return policy

    def _run_root(self, locator):
        root = self.coordinator.root / locator["case_id"] / locator["run_id"]
        require(root == root.resolve() and root.is_relative_to(self.coordinator.root),
                "Analysis Run path escaped its coordinator")
        return root

    def _source(self, locator, selected):
        root = self._run_root(locator)
        index = loads(read_regular(root / "artifact_index.json"))
        require(index["current"]["code"] == selected and selected["slot"] == "code" and
                selected["attempt_kind"] == "code_agent" and selected["status"] == "success",
                "Analysis requires the exact current canonical success Code pointer")
        attempt = selected["attempt_id"]
        member_bytes = {}
        member_digests = {}
        for member in selected["members"]:
            name = member["logical_name"]
            relative = Path(member["canonical_path"])
            require(name == member["projection_path"] and len(relative.parts) == 3 and
                    relative.parts == ("attempts", attempt, name) and name not in member_bytes,
                    "Code member path or identity changed")
            member_path = root / relative
            require(member_path == member_path.resolve() and member_path.is_relative_to(root),
                    "Analysis Code member escaped its Run")
            content = read_regular(member_path)
            actual = sha256(content).hexdigest()
            require(actual == member["sha256"], "Code bundle member changed")
            member_bytes[name] = content
            member_digests[name] = actual
        task = validate_task(member_bytes["code_agent_task.json"]).value
        result = validate_code_result(member_bytes["code_agent_result.json"], task).value
        manifest = validate_manifest(member_bytes["workspace_manifest.json"], task).value
        require(result["result_origin"] == "backend_delivery" and result["usable"] is True and
                result["attempt_id"] == attempt and result["status"] == "success" and
                task["case_id"] == locator["case_id"] and task["run_id"] == locator["run_id"],
                "Code bundle is not usable by this Analysis")
        receipt = loads(member_bytes["backend_dispatch_receipt.json"])
        seal = loads(member_bytes["workspace_seal.json"])
        changes = loads(member_bytes["change_manifest.json"])
        verification = loads(member_bytes["verification_results.json"])
        patch = member_bytes["changes.patch"]
        expected = bundle_members(task, result, receipt, manifest, seal, changes, verification,
                                  member_bytes["tool_audit.jsonl"], patch)
        expected.update(trial_member(self.coordinator, task))
        require(expected == member_bytes and verification["all_required_passed"] is True and
                changes["changes"] and result["patch_digest"] == sha256(patch).hexdigest(),
                "Code source is incomplete or not verified")
        base = immutable_git_tree(self.base_repository, task["base_revision"])
        require(tree_digest(base) == task["base_tree_digest"], "Analysis base drift")
        return root, index, task, result, changes, patch, member_digests, base

    def snapshot(self, view, target_attempt_id, inbound_transition_id):
        locator = view["run_locator"]
        selected = view["selected_code"]
        root, index, task, result, changes, patch, member_digests, _ = self._source(locator, selected)
        require(view["state"]["artifact_head"] == index["artifact_head"] and
                view["state"]["schema_version"] == "0.4", "Analysis source head changed")
        target = {**locator, "attempt_id": target_attempt_id, "attempt_kind": "analysis_engineer"}
        source = {"artifact_id": selected["artifact_id"], "digest": digest(selected)}
        workspace_id = "analysis_" + digest(target)
        manifest = {"schema_version": "0.1", "workspace_id": workspace_id,
                    "managed_root_identity": digest(str(self.provider.root)),
                    "base_tree_digest": task["base_tree_digest"], "target_attempt_identity": target,
                    "inbound_transition_identity": inbound_transition_id,
                    "source_code_bundle_id_digest": source,
                    "expected_effective_tree_digest": changes["final_tree_digest"]}
        manifest["manifest_digest"] = digest(manifest)
        selected_inputs = {slot: {"artifact_id": index["current"][slot]["artifact_id"],
                                  "digest": digest(index["current"][slot])}
                           for slot in ("plan",) if index["current"][slot] is not None}
        require("plan" in selected_inputs, "Analysis lacks a current plan")
        runtime = {"python": sys.version, "executable": sys.executable}
        environment = self._environment(locator)
        spec = {"schema_version": "0.1", "analysis_execution_spec_id": target_attempt_id + ":analysis_execution_spec",
                "target_attempt_identity": target, "inbound_transition_identity": inbound_transition_id,
                "source_code_attempt_id": task["attempt_id"], "source_code_bundle_id_digest": source,
                "source_member_digests": member_digests, "producing_task_digest": task["task_digest"],
                "base_revision": task["base_revision"], "base_tree_digest": task["base_tree_digest"],
                "change_manifest_digest": changes["change_manifest_digest"],
                "patch_digest": sha256(patch).hexdigest(),
                "expected_effective_tree_digest": changes["final_tree_digest"],
                "selected_input_artifacts": selected_inputs,
                "analysis_runtime_fingerprint": digest(runtime), "environment_policy": environment,
                "allowed_command": self.allowed_command, "expected_outputs": self.expected_outputs,
                "fresh_workspace_identity": workspace_id, "workspace_manifest_digest": manifest["manifest_digest"]}
        spec["spec_digest"] = digest(spec)
        value = {"preparation_kind": "analysis_fresh", "target_attempt_identity": target,
                 "inbound_transition_identity": inbound_transition_id,
                 "analysis_execution_spec_id": spec["analysis_execution_spec_id"],
                 "canonical_spec_bytes": canonical_bytes(spec).decode(), "spec_digest": digest(spec),
                 "fresh_workspace_identity": workspace_id,
                 "canonical_workspace_manifest_bytes": canonical_bytes(manifest).decode(),
                 "workspace_manifest_digest": digest(manifest), "source_code_bundle_id_digest": source,
                 "base_revision_tree": {"revision": task["base_revision"], "tree": task["base_tree_digest"]},
                 "verified_change_digest": changes["change_manifest_digest"],
                 "expected_effective_tree_digest": changes["final_tree_digest"],
                 "runtime_policy_digest": digest({"runtime": runtime, "environment": environment,
                                                   "command": self.allowed_command,
                                                   "outputs": self.expected_outputs})}
        require(root == self._run_root(locator), "Analysis Run source changed")
        return value

    def _frozen(self, value):
        spec = loads(value["canonical_spec_bytes"])
        manifest = loads(value["canonical_workspace_manifest_bytes"])
        closed(spec, SPEC_FIELDS)
        closed(manifest, MANIFEST_FIELDS)
        runtime = {"python": sys.version, "executable": sys.executable}
        locator = {key: spec['target_attempt_identity'][key] for key in ('case_id', 'run_id')}
        require(value["canonical_spec_bytes"] == canonical_bytes(spec).decode() and
                value["canonical_workspace_manifest_bytes"] == canonical_bytes(manifest).decode() and
                value["analysis_execution_spec_id"] == spec["analysis_execution_spec_id"] and
                spec["schema_version"] == manifest["schema_version"] == "0.1" and
                spec["spec_digest"] == digest({key: item for key, item in spec.items() if key != "spec_digest"}) and
                value["spec_digest"] == digest(spec) and
                manifest["manifest_digest"] == digest({key: item for key, item in manifest.items() if key != "manifest_digest"}) and
                value["workspace_manifest_digest"] == digest(manifest) and
                spec["workspace_manifest_digest"] == manifest["manifest_digest"] and
                spec["fresh_workspace_identity"] == manifest["workspace_id"] == value["fresh_workspace_identity"] and
                spec["target_attempt_identity"] == manifest["target_attempt_identity"] == value["target_attempt_identity"] and
                spec["inbound_transition_identity"] == manifest["inbound_transition_identity"] == value["inbound_transition_identity"] and
                spec["source_code_bundle_id_digest"] == manifest["source_code_bundle_id_digest"] == value["source_code_bundle_id_digest"] and
                spec["expected_effective_tree_digest"] == manifest["expected_effective_tree_digest"] == value["expected_effective_tree_digest"] and
                spec["base_tree_digest"] == manifest["base_tree_digest"] == value["base_revision_tree"]["tree"] and
                spec["base_revision"] == value["base_revision_tree"]["revision"] and
                spec["change_manifest_digest"] == value["verified_change_digest"] and
                manifest["managed_root_identity"] == digest(str(self.provider.root)) and
                spec["allowed_command"] == self.allowed_command and spec["expected_outputs"] == self.expected_outputs and
                spec['environment_policy'] == self._environment(locator) and
                spec["analysis_runtime_fingerprint"] == digest(runtime) and
                value["runtime_policy_digest"] == digest({"runtime": runtime,
                    "environment": spec["environment_policy"], "command": self.allowed_command,
                    "outputs": self.expected_outputs}),
                "Frozen Analysis specification changed")
        return spec, manifest

    def _verify_source(self, value):
        spec, manifest = self._frozen(value)
        locator = {key: spec["target_attempt_identity"][key] for key in ("case_id", "run_id")}
        index = loads(read_regular(self._run_root(locator) / "artifact_index.json"))
        selected = index["current"]["code"]
        require(selected is not None and spec["source_code_bundle_id_digest"] ==
                {"artifact_id": selected["artifact_id"], "digest": digest(selected)},
                "Selected Code is no longer current")
        _, _, task, result, changes, patch, members, base = self._source(locator, selected)
        require(task["task_digest"] == spec["producing_task_digest"] and
                task["attempt_id"] == spec["source_code_attempt_id"] and members == spec["source_member_digests"] and
                changes["change_manifest_digest"] == spec["change_manifest_digest"] and
                sha256(patch).hexdigest() == spec["patch_digest"] and
                changes["final_tree_digest"] == spec["expected_effective_tree_digest"] and
                result["usable"] is True and tree_digest(base) == spec["base_tree_digest"] and
                {slot: {"artifact_id": index["current"][slot]["artifact_id"],
                        "digest": digest(index["current"][slot])}
                 for slot in ("plan",) if index["current"][slot] is not None} ==
                spec["selected_input_artifacts"], "Analysis source changed after reservation")
        return spec, manifest, task, changes, patch, base

    def receipt(self, value):
        return PreparationVerification(digest(value), value["workspace_manifest_digest"],
                                       value["expected_effective_tree_digest"])

    def verify_preparation_source(self, value):
        self._verify_source(value)
        return self.receipt(value)

    def witness(self, value):
        target = value["target_attempt_identity"]
        return self._run_root(target) / "attempts" / target["attempt_id"] / "control" / "domain_preparation.json"

    def materialize_preparation(self, value, port):
        spec, manifest, task, changes, patch, base = self._verify_source(value)
        namespace = self.witness(value).parent
        port.fence()
        boundary(self.coordinator.observer, "analysis.exact_duplicate", "before", value=value)
        require(read_regular(namespace / "analysis_execution_spec.json") == canonical_bytes(spec) and
                read_regular(namespace / "analysis_workspace_manifest.json") == canonical_bytes(manifest),
                "Frozen Analysis publication changed")
        boundary(self.coordinator.observer, "analysis.exact_duplicate", "after", value=value)
        destination = self.provider.path(manifest["workspace_id"])
        boundary(self.coordinator.observer, "analysis.fresh_workspace", "before", value=value)
        if destination.exists():
            witness = self.provider._public_witness(manifest)
            self.provider.verify_identity(manifest, witness)
            current = scan_tree(destination)
            require(current == base or tree_digest(current) == spec["expected_effective_tree_digest"],
                    "Analysis workspace contains an uncertain partial change")
        else:
            witness = self.provider.materialize(manifest, base, port.fence)
            current = base
        boundary(self.coordinator.observer, "analysis.fresh_workspace", "after", value=value)
        if current == base:
            port.fence()
            environment = {"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
                           "GIT_CONFIG_GLOBAL": os.devnull}
            command = ["/usr/bin/git", "apply", "--check", "-"]
            subprocess.run(command, input=patch, cwd=destination, env=environment, timeout=10,
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["/usr/bin/git", "apply", "-"], input=patch, cwd=destination,
                           env=environment, timeout=10, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        port.fence()
        boundary(self.coordinator.observer, "analysis.effective_tree_verification", "before", value=value)
        final = scan_tree(destination)
        require(tree_digest(final) == spec["expected_effective_tree_digest"] and
                validate_changes(task, base, final) == changes["changes"] and
                canonical_patch(base, final, changes["changes"]) == patch,
                "Fresh Analysis tree differs from verified Code")
        self.provider.verify_identity(manifest, witness)
        boundary(self.coordinator.observer, "analysis.effective_tree_verification", "after", value=value)
        boundary(self.coordinator.observer, "analysis.preparation_proof", "before", value=value)
        publish_exact(self.witness(value), canonical_bytes(self.receipt(value).__dict__))
        boundary(self.coordinator.observer, "analysis.preparation_proof", "after", value=value)
        port.fence()
        return self.receipt(value)

    def verify_preparation(self, value):
        spec, manifest, task, changes, patch, base = self._verify_source(value)
        require(read_regular(self.witness(value)) == canonical_bytes(self.receipt(value).__dict__),
                "Analysis preparation witness changed")
        final = self.provider.verify_sealed(manifest, self.provider._public_witness(manifest),
                                            spec["expected_effective_tree_digest"])
        require(validate_changes(task, base, final) == changes["changes"] and
                canonical_patch(base, final, changes["changes"]) == patch,
                "Fresh Analysis content changed")
        return self.receipt(value)

    def execute(self, value):
        """Run the frozen command in a new process after rechecking the source."""
        self.verify_preparation(value)
        spec, manifest = self._frozen(value)
        if self.generated_program is not None:
            from .execution import execute_candidate, read_scientific_input
            environment = spec['environment_policy']
            record = environment['dataset_snapshot']
            parameters = environment['generated_program']['parameters']
            payload = read_scientific_input(self.workspace, record, parameters)
            files = self.provider.verify_sealed(manifest, self.provider._public_witness(manifest),
                                                spec['expected_effective_tree_digest'])
            result, execution = execute_candidate(files['analysis.py'], payload, self.allowed_command[0],
                timeout=self.timeout_seconds, expected_runtime=environment['runtime'])
            self.verify_preparation(value)
            return {'returncode': 0, 'result': result, 'execution': execution, 'dataset_snapshot': record,
                    'parameters': parameters, 'result_kind': self.generated_program['result_kind'],
                    'spec_digest': spec['spec_digest'],
                    'stdout_sha256': execution['stdout_sha256'], 'stderr_sha256': execution['stderr_sha256']}
        require(spec["allowed_command"][:3] == [sys.executable, "-I", "-S"], 'Analysis command is not isolated')
        boundary(self.coordinator.observer, "analysis.fresh_subprocess", "before", value=value)
        completed = subprocess.run(spec["allowed_command"], cwd=self.provider.path(manifest["workspace_id"]),
                                   env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"},
                                   shell=False, timeout=10, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        boundary(self.coordinator.observer, "analysis.fresh_subprocess", "after", value={
            "returncode": completed.returncode, "stdout_sha256": sha256(completed.stdout).hexdigest()})
        self.verify_preparation(value)
        require(completed.returncode == 0, "Fresh Analysis subprocess failed")
        return {"returncode": completed.returncode, "stdout_sha256": sha256(completed.stdout).hexdigest(),
                "stderr_sha256": sha256(completed.stderr).hexdigest()}
