"""Trusted, fresh-workspace verification for the Phase B command registry."""
from hashlib import sha256
import os
import subprocess
import sys

from lqcd_agent.control.strict_json import closed, digest, digest_value, number, require

from .schemas import relative_path, validate_task, within
from .verification_resources import run_verification
from .workspace import WorkspaceProvider, scan_tree, tree_digest, validate_changes


_PARSE_CODE = ("import ast,sys; from pathlib import Path; "
               "ast.parse(Path(sys.argv[1]).read_text(encoding='utf-8'), filename=sys.argv[1])")
RESULT_FIELDS = ("spec_id", "status", "exit_code", "stdout_digest", "stderr_digest", "stdout_size",
                 "stderr_size", "produced_files", "reason")


def build_verification_results(task, results):
    task = validate_task(task).value
    specs = task["verification_specs"]
    require(type(results) is list and len(results) == len(specs) and
            [value.get("spec_id") for value in results if type(value) is dict] ==
            [spec["spec_id"] for spec in specs], "Verification result set is incomplete or reordered")
    for result in results:
        closed(result, RESULT_FIELDS)
        require(result["status"] in ("passed", "failed", "blocked", "timeout", "not_run") and
                (result["exit_code"] is None or type(result["exit_code"]) is int),
                "Invalid trusted verification status")
        for name in ("stdout_digest", "stderr_digest"):
            digest_value(result[name])
        for name in ("stdout_size", "stderr_size"):
            number(result[name], integer=True, minimum=0)
        require(result["produced_files"] == [] and
                (result["reason"] is None or type(result["reason"]) is str),
                "Unexpected verification output or reason")
    required = [result for spec, result in zip(specs, results) if spec["required"]]
    value = {"schema_version": "0.1", "task_id": task["task_id"], "attempt_id": task["attempt_id"],
             "spec_results": results, "all_required_passed": bool(required) and
             all(result["status"] == "passed" for result in required)}
    value["verification_results_digest"] = digest(value)
    return value


class TrustedVerifier:
    """Only the fixed Python syntax check is executable in Phase B."""

    def __init__(self, managed_root):
        self.provider = WorkspaceProvider(managed_root)

    @staticmethod
    def _command(task, spec):
        argv = spec["argv"]
        if (len(argv) == 4 and argv[:3] == ["python", "-m", "compileall"] and spec["cwd"] == "." and
                spec["environment_keys"] == [] and argv[3].endswith(".py") and
                within(argv[3], [*task["read_paths"], *task["write_paths"]])):
            relative_path(argv[3])
            return [sys.executable, "-I", "-S", "-c", _PARSE_CODE, argv[3]]
        return None

    def prepare(self, task, base, final, fence):
        task = validate_task(task).value
        changes = validate_changes(task, base, final)
        effective = dict(base)
        for change in changes:
            path = change["path"]
            if change["kind"] == "deleted":
                effective.pop(path)
            else:
                effective[path] = final[path]
        require(effective == final, "Verification effective tree differs from validated change")
        workspace_id = task["attempt_id"] + "_verification"
        manifest = {"workspace_id": workspace_id,
                    "manifest_digest": digest({"task_digest": task["task_digest"],
                                               "effective_tree_digest": tree_digest(effective)}),
                    "managed_root_identity": digest({"verification_root": str(self.provider.root),
                                                     "workspace_id": workspace_id}),
                    "base_tree_digest": tree_digest(effective)}
        witness = self.provider.materialize(manifest, effective, fence)
        require(scan_tree(self.provider.verify_identity(manifest, witness)) == effective,
                "Fresh verification workspace changed")
        return task, manifest, witness, effective

    def execute(self, task, manifest, witness, effective, spec, *, port):
        """A resource port is mandatory for every command that may execute."""
        require(spec in task["verification_specs"], "Foreign verification spec")
        command = self._command(task, spec)
        if command is None:
            return self._result(spec, "blocked", None, b"", b"", "command_not_registered")
        require(port is not None, "Trusted command requires a durable resource port")
        root = self.provider.verify_identity(manifest, witness)
        require(scan_tree(root) == effective, "Fresh verifier input changed")

        return run_verification(port, spec_id=spec["spec_id"], input_digest=tree_digest(effective),
                                config_digest=digest(spec), timeout_seconds=spec["timeout_seconds"],
                                effect=lambda: self._run_command(root, spec, command, effective))

    def verify_all(self, task, base, final, *, candidate_status, fence, port):
        task = validate_task(task).value
        require(candidate_status in ("success", "no_change", "failed", "needs_input", "needs_human",
                                     "budget_exhausted", "policy_blocked"), "Unknown candidate verification status")
        if candidate_status != "success":
            return build_verification_results(task, [self.not_run(spec, candidate_status)
                                                     for spec in task["verification_specs"]])
        require(port is not None, "Success verification requires a durable resource port")
        task, manifest, witness, effective = self.prepare(task, base, final, fence)
        results = [self.execute(task, manifest, witness, effective, spec, port=port)
                   for spec in task["verification_specs"]]
        return build_verification_results(task, results)

    @classmethod
    def _run_command(cls, root, spec, command, effective):
        try:
            process = subprocess.run(command, cwd=root, env={"PATH": os.defpath, "LC_ALL": "C"},
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     timeout=spec["timeout_seconds"], shell=False, check=False)
        except subprocess.TimeoutExpired as error:
            result = cls._result(spec, "timeout", None, error.stdout or b"", error.stderr or b"",
                                 "command_timeout")
        else:
            status = "passed" if process.returncode in spec["expected_exit_codes"] else "failed"
            result = cls._result(spec, status, process.returncode, process.stdout, process.stderr,
                                 None if status == "passed" else "unexpected_exit")
        require(scan_tree(root) == effective, "Verification changed persistent workspace content")
        return result

    @staticmethod
    def _result(spec, status, exit_code, stdout, stderr, reason):
        require(type(stdout) is bytes and type(stderr) is bytes, "Invalid verification output")
        return {"spec_id": spec["spec_id"], "status": status, "exit_code": exit_code,
                "stdout_digest": sha256(stdout).hexdigest(), "stderr_digest": sha256(stderr).hexdigest(),
                "stdout_size": len(stdout), "stderr_size": len(stderr), "produced_files": [], "reason": reason}

    @staticmethod
    def not_run(spec, reason):
        require(reason in ("no_change", "failed", "needs_input", "needs_human", "budget_exhausted",
                           "policy_blocked", "operation_timeout", "prior_verification_failed"),
                "Unknown verifier absence reason")
        return {"spec_id": spec["spec_id"], "status": "not_run", "exit_code": None,
                "stdout_digest": sha256(b"").hexdigest(), "stderr_digest": sha256(b"").hexdigest(),
                "stdout_size": 0, "stderr_size": 0, "produced_files": [], "reason": reason}
