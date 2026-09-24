"""Closed A05 input schemas shared by every canonical coding backend."""
from pathlib import PurePosixPath
import re

from lqcd_agent.control.strict_json import (
    ValidatedValue, canonical_bytes, closed, digest, digest_value, loads, number, require, text,
)
from lqcd_agent.control.pause import validate_fingerprint


IDENTITY = ("case_id", "run_id", "cycle_id", "attempt_id", "transition_id", "producer_operation_id")
POLICIES = ("read_paths", "write_paths", "forbidden_paths", "tool_policy", "network_policy", "filesystem_policy")
TASK_FIELDS = (*IDENTITY, "schema_version", "task_id", "task_digest", "source_attempt_id", "attempt_kind", "node_name",
    "task_origin", "task_summary", "requirements", "acceptance_criteria", "evidence", "execution_head", "artifact_head",
    "base_revision", "base_tree_digest", "source_runtime_fingerprint", *POLICIES, "verification_specs",
    "budget_policy_version", "budget_profile_id", "budget_policy_digest", "budget_envelope_ref", "budget_envelope_digest",
    "human_authorization_ref", "coding_backend_kind", "backend_version", "backend_runtime_fingerprint",
    "external_producer_contract", "expected_result_schema")
MANIFEST_FIELDS = (*IDENTITY, "schema_version", "workspace_id", "workspace_generation", "manifest_digest",
    "task_id", "task_digest", "base_revision", "base_tree_digest", "source_runtime_fingerprint", "coding_backend_kind",
    "backend_version", "backend_runtime_fingerprint", "workspace_implementation", "policy_digests", "created_at",
    "owner", "managed_root_identity")
SPEC_FIELDS = ("spec_id", "argv", "cwd", "timeout_seconds", "required", "expected_exit_codes", "environment_keys")


def relative_path(value, *, root=False):
    """Reject aliases before filesystem access; root cwd is an explicit case."""
    text(value)
    if root and value == ".":
        return value
    require(not any(ord(c) < 32 or c in "\\\x7f" for c in value), "Invalid path character")
    parts = value.split("/")
    require(all(part not in ("", ".", "..") for part in parts) and not PurePosixPath(value).is_absolute() and
            ":" not in parts[0], "Non-canonical relative path")
    return value


def _paths(values, *, nonempty=False):
    require(type(values) is list and (values or not nonempty), "Missing path scope")
    for value in values:
        relative_path(value)
    require(len(values) == len(set(value.casefold() for value in values)), "Path normalization collision")


def within(path, scope):
    return any(path == prefix or path.startswith(prefix + "/") for prefix in scope)


def protected_path(path):
    """These namespaces are never writable, regardless of a task allowlist."""
    parts = path.casefold().split("/")
    blocked = {".git", "raw", "raw_data", "data", "outputs", "accepted", "accepted_results", "checkpoints",
               "control", "secrets", ".ssh", ".aws", ".config", "human_responses", "credentials"}
    return any(part in blocked or part == ".env" or part.startswith(".env.") or
               part in ("control_operations.sqlite", "execution_history.jsonl", "artifact_history.jsonl",
                        "artifact_index.json", "budget_policy.json") for part in parts)


def validate_spec(value):
    closed(value, SPEC_FIELDS)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", text(value["spec_id"])) is not None,
            "Invalid verification identity")
    argv = value["argv"]
    require(type(argv) is list and argv and all(type(item) is str and item and "\x00" not in item for item in argv),
            "Verification requires typed argv")
    relative_path(value["cwd"], root=True)
    number(value["timeout_seconds"])
    require(value["timeout_seconds"] > 0 and type(value["required"]) is bool, "Invalid verification policy")
    codes = value["expected_exit_codes"]
    require(type(codes) is list and codes and all(type(code) is int and 0 <= code <= 255 for code in codes) and
            len(codes) == len(set(codes)), "Invalid expected exit codes")
    keys = value["environment_keys"]
    require(type(keys) is list and all(type(key) is str and re.fullmatch(r"[A-Z][A-Z0-9_]*", key) for key in keys) and
            keys == sorted(set(keys)), "Invalid environment allowlist")
    return ValidatedValue(canonical_bytes(value))


def _envelope(value, fields, checksum):
    value = loads(value) if type(value) in (str, bytes) else loads(canonical_bytes(value))
    closed(value, fields)
    require(value["schema_version"] == "0.1", "Unsupported Code schema")
    for key in IDENTITY:
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", text(value[key])) is not None,
                "Invalid Code identity")
    digest_value(value[checksum])
    require(value[checksum] == digest({k: v for k, v in value.items() if k != checksum}), "Code checksum mismatch")
    return value


def validate_task(value):
    """Validate structure and policy; the Host separately binds current authority."""
    value = _envelope(value, TASK_FIELDS, "task_digest")
    require(value["task_id"] == value["attempt_id"] + ":code_task" and
            value["attempt_kind"] == value["node_name"] == "code_agent" and
            value["task_origin"] in ("planner_gap", "coordinator_code_fix"), "Non-canonical Code target")
    text(value["source_attempt_id"])
    require(len(text(value["task_summary"])) <= 4096, "Unbounded task summary")
    for name in ("requirements", "acceptance_criteria"):
        require(type(value[name]) is list and 0 < len(value[name]) <= 128 and
                all(type(item) is str and 0 < len(item) <= 4096 for item in value[name]), "Missing bounded task criteria")
    require(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", text(value["base_revision"])) is not None,
            "Base must be a full immutable Git commit")
    validate_fingerprint(value["source_runtime_fingerprint"])
    for name in ("base_tree_digest", "execution_head", "artifact_head",
                 "budget_policy_digest", "budget_envelope_digest", "backend_runtime_fingerprint"):
        digest_value(value[name])
    evidence = value["evidence"]
    require(type(evidence) is list and evidence, "Task requires selected evidence")
    for item in evidence:
        closed(item, ("artifact_id", "path", "sha256"))
        text(item["artifact_id"])
        relative_path(item["path"])
        digest_value(item["sha256"])
    require(len({item["path"] for item in evidence}) == len(evidence), "Duplicate task evidence")
    for name in ("read_paths", "write_paths", "forbidden_paths"):
        _paths(value[name], nonempty=name != "forbidden_paths")
    for path in (*value["read_paths"], *value["write_paths"]):
        require(not protected_path(path) and not within(path, value["forbidden_paths"]), "Forbidden task scope")
    closed(value["network_policy"], ("enabled",))
    require(value["network_policy"]["enabled"] is False, "Task cannot enable network")
    fs = closed(value["filesystem_policy"], ("binary_changes", "executable_changes", "ephemeral_paths"))
    require(fs["binary_changes"] is False and fs["executable_changes"] is False, "Unsupported filesystem permission")
    _paths(fs["ephemeral_paths"])
    for path in fs["ephemeral_paths"]:
        require(not protected_path(path) and not within(path, value["forbidden_paths"]) and
                not any(within(other, [path]) for other in value["forbidden_paths"]), "Forbidden verifier temporary scope")
    specs = value["verification_specs"]
    require(type(specs) is list and specs and any(item.get("required") is True for item in specs if type(item) is dict),
            "Task requires trusted verification")
    tools = value["tool_policy"]
    require(type(tools) is list, "Invalid tool policy")
    for sequence in (specs, tools):
        for spec in sequence:
            validate_spec(spec)
        require(len({item["spec_id"] for item in sequence}) == len(sequence), "Duplicate command identity")
    require(value["budget_policy_version"] == "0.1" and value["expected_result_schema"] == "0.1", "Unsupported task contract")
    text(value["budget_profile_id"])
    budget = closed(value["budget_envelope_ref"], ("path", "event_id"))
    require(budget["path"] == "execution_history.jsonl", "Budget authority must be the execution ledger")
    text(budget["event_id"])
    human = value["human_authorization_ref"]
    if human is not None:
        closed(human, ("artifact_id", "path", "sha256", "action", "scope_digest", "single_use_id"))
        for name in ("artifact_id", "action", "single_use_id"):
            text(human[name])
        relative_path(human["path"])
        digest_value(human["sha256"])
        digest_value(human["scope_digest"])
    for name in ("coding_backend_kind", "backend_version"):
        text(value[name])
    producer = closed(value["external_producer_contract"], ("schema_version", "parent_control_operation_id"))
    require(producer["schema_version"] == "0.1", "Unsupported producer contract")
    text(producer["parent_control_operation_id"])
    return ValidatedValue(canonical_bytes(value))


def validate_manifest(value, task):
    task = validate_task(task).value
    value = _envelope(value, MANIFEST_FIELDS, "manifest_digest")
    for name in (*IDENTITY, "task_id", "task_digest", "base_revision", "base_tree_digest", "source_runtime_fingerprint",
                 "coding_backend_kind", "backend_version", "backend_runtime_fingerprint"):
        require(value[name] == task[name], "Workspace manifest task mismatch")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}", text(value["workspace_id"])) is not None,
            "Invalid workspace identity")
    number(value["workspace_generation"], integer=True, minimum=1)
    number(value["created_at"])
    text(value["owner"])
    text(value["workspace_implementation"])
    digest_value(value["managed_root_identity"])
    closed(value["policy_digests"], POLICIES)
    require(value["policy_digests"] == {name: digest(task[name]) for name in POLICIES}, "Workspace policy mismatch")
    return ValidatedValue(canonical_bytes(value))


def task_context(task):
    """A06 semantic inputs exclude execution identity, clocks and physical roots."""
    task = validate_task(task).value
    fields = ("requirements", "acceptance_criteria", "base_revision", "base_tree_digest", "coding_backend_kind",
              "backend_version", "backend_runtime_fingerprint", "budget_policy_digest", *POLICIES, "verification_specs")
    return {**{key: task[key] for key in fields}, "evidence_digests": sorted(item["sha256"] for item in task["evidence"])}
