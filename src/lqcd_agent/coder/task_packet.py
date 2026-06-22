"""Coder task packet helpers for deterministic mock handoff artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TASK_PACKET_SCHEMA_VERSION = "0.1"
TASK_PACKET_STATUSES = {"pending"}
TASK_PACKET_REQUIRED_STRING_FIELDS = [
    "schema_version",
    "run_id",
    "case_id",
    "created_at",
    "producer",
    "status",
    "summary",
    "task_summary",
    "physics_goal",
]
TASK_PACKET_REQUIRED_LIST_FIELDS = [
    "warnings",
    "errors",
    "implementation_gaps",
    "allowed_files",
    "forbidden_paths",
    "requirements",
    "acceptance_criteria",
    "verification_commands",
    "context_artifacts",
]
TASK_PACKET_NON_EMPTY_LIST_FIELDS = [
    "allowed_files",
    "forbidden_paths",
    "requirements",
    "acceptance_criteria",
    "verification_commands",
    "context_artifacts",
]

DEFAULT_ALLOWED_FILES = [
    "src/lqcd_agent/agents/method_planner.py",
    "src/lqcd_agent/tools/repo_inventory.py",
    "src/lqcd_agent/coder/task_packet.py",
    "tests/test_method_planner_mock.py",
    "docs/ARTIFACT_CONTRACTS.md",
    "docs/REPO_CURRENT_STATE.md",
]


class TaskPacketValidationError(ValueError):
    """Raised when a coder task packet does not match the handoff schema."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid coder_task_packet.yaml: " + "; ".join(errors))


def build_coder_task_packet(
    *,
    method_plan: dict[str, Any],
    repo_inventory: dict[str, Any],
    task_summary: str | None = None,
    implementation_gaps: list[str] | None = None,
    verification_commands: list[str] | None = None,
) -> dict[str, Any]:
    resolved_task_summary = (
        task_summary
        or method_plan.get("coder_task_summary")
        or "Implement or repair missing mock-only workflow support before analysis execution."
    )
    resolved_gaps = implementation_gaps
    if resolved_gaps is None:
        plan_gaps = method_plan.get("implementation_gaps", [])
        resolved_gaps = [str(gap) for gap in plan_gaps] if isinstance(plan_gaps, list) else []
    if not resolved_gaps:
        resolved_gaps = ["Address the structured code failure before analysis execution."]

    return {
        "schema_version": TASK_PACKET_SCHEMA_VERSION,
        "run_id": method_plan["run_id"],
        "case_id": method_plan["case_id"],
        "created_at": method_plan["created_at"],
        "producer": "method_planner",
        "status": "pending",
        "summary": resolved_task_summary,
        "warnings": [],
        "errors": [],
        "task_summary": resolved_task_summary,
        "physics_goal": method_plan["physics_goal"],
        "implementation_gaps": resolved_gaps,
        "allowed_files": repo_inventory.get("allowed_files") or DEFAULT_ALLOWED_FILES,
        "forbidden_paths": ["raw_data/", "accepted_results/", "real LLM provider files"],
        "requirements": [
            "Keep mock LLM behavior deterministic and replaceable.",
            "Do not call real LLM providers.",
            "Do not write analysis implementation code unless requested by a separate coding task.",
        ],
        "acceptance_criteria": [
            "Method planner emits a valid method_plan.json.",
            "Required code handoff emits coder_task_packet.yaml.",
            "Missing critical inputs return needs_more_info.",
        ],
        "verification_commands": verification_commands or ["pytest tests/test_method_planner_mock.py -q"],
        "context_artifacts": ["method_plan.json"],
    }


def validate_task_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in TASK_PACKET_REQUIRED_STRING_FIELDS:
        value = packet.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string.")

    if packet.get("schema_version") != TASK_PACKET_SCHEMA_VERSION:
        errors.append(f"schema_version must be {TASK_PACKET_SCHEMA_VERSION!r}.")

    if packet.get("status") not in TASK_PACKET_STATUSES:
        allowed = ", ".join(sorted(TASK_PACKET_STATUSES))
        errors.append(f"status must be one of: {allowed}.")

    for field in TASK_PACKET_REQUIRED_LIST_FIELDS:
        value = packet.get(field)
        if not isinstance(value, list):
            errors.append(f"{field} must be a list.")
            continue
        if field in TASK_PACKET_NON_EMPTY_LIST_FIELDS and not value:
            errors.append(f"{field} must contain at least one item.")
            continue
        if field not in {"warnings", "errors"} and not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            errors.append(f"{field} must contain only non-empty strings.")

    return errors


def assert_valid_task_packet(packet: dict[str, Any]) -> None:
    errors = validate_task_packet(packet)
    if errors:
        raise TaskPacketValidationError(errors)


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value == []:
        return "[]"
    if value == {}:
        return "{}"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _to_yaml(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if item == [] or item == {}:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
                continue
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def write_task_packet_yaml(output_dir: str | Path, packet: dict[str, Any]) -> str:
    assert_valid_task_packet(packet)
    path = Path(output_dir) / "coder_task_packet.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_to_yaml(packet)) + "\n", encoding="utf-8")
    return str(path)


def _parse_yaml_scalar(value: str) -> Any:
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def read_task_packet_yaml(path: str | Path) -> dict[str, Any]:
    packet_path = Path(path)
    packet: dict[str, Any] = {}
    current_list_key: str | None = None
    for line_number, raw_line in enumerate(packet_path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and ":" in raw_line:
            key, raw_value = raw_line.split(":", 1)
            value = raw_value.strip()
            if value:
                packet[key] = _parse_yaml_scalar(value)
                current_list_key = key if packet[key] == [] else None
            else:
                packet[key] = []
                current_list_key = key
            continue
        stripped = raw_line.strip()
        if stripped.startswith("- "):
            if current_list_key is None:
                raise TaskPacketValidationError(
                    [f"line {line_number} contains a list item without a list field."]
                )
            packet.setdefault(current_list_key, [])
            packet[current_list_key].append(_parse_yaml_scalar(stripped[2:].strip()))
            continue
        raise TaskPacketValidationError([f"line {line_number} is not valid task-packet YAML."])

    assert_valid_task_packet(packet)
    return packet
