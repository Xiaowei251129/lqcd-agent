"""Safe verification command runner for file-based coder handoffs."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.coder.task_packet import read_task_packet_yaml


TEST_STATUS_SCHEMA_VERSION = "0.1"
TEST_STATUS_VALUES = {"tests_passed", "tests_failed"}
COMMAND_STATUS_VALUES = {"passed", "failed", "blocked", "timeout"}
ALLOWED_PYTHON_MODULES = {"pytest", "lqcd_agent.graph.run_graph"}


class TestStatusValidationError(ValueError):
    """Raised when tests_status.json does not match the handoff schema."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid tests_status.json: " + "; ".join(errors))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_status(*, run_id: str, case_id: str, status: str, summary: str) -> dict[str, Any]:
    return {
        "schema_version": TEST_STATUS_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": utc_now(),
        "producer": "test_runner",
        "status": status,
        "summary": summary,
        "warnings": [],
        "errors": [],
        "commands": [],
    }


def validate_tests_status(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["schema_version", "run_id", "case_id", "created_at", "producer", "status", "summary"]:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string.")

    if payload.get("schema_version") != TEST_STATUS_SCHEMA_VERSION:
        errors.append(f"schema_version must be {TEST_STATUS_SCHEMA_VERSION!r}.")
    if payload.get("status") not in TEST_STATUS_VALUES:
        allowed = ", ".join(sorted(TEST_STATUS_VALUES))
        errors.append(f"status must be one of: {allowed}.")

    for field in ["warnings", "errors", "commands"]:
        if not isinstance(payload.get(field), list):
            errors.append(f"{field} must be a list.")

    commands = payload.get("commands", [])
    if isinstance(commands, list):
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                errors.append(f"commands[{index}] must be an object.")
                continue
            for field in ["command", "working_directory", "stdout", "stderr", "status"]:
                value = command.get(field)
                if not isinstance(value, str):
                    errors.append(f"commands[{index}].{field} must be a string.")
            if not isinstance(command.get("produced_files"), list):
                errors.append(f"commands[{index}].produced_files must be a list.")
            if command.get("status") not in COMMAND_STATUS_VALUES:
                allowed = ", ".join(sorted(COMMAND_STATUS_VALUES))
                errors.append(f"commands[{index}].status must be one of: {allowed}.")
            if not (command.get("return_code") is None or isinstance(command.get("return_code"), int)):
                errors.append(f"commands[{index}].return_code must be an integer or null.")
            if not isinstance(command.get("timeout_seconds"), int):
                errors.append(f"commands[{index}].timeout_seconds must be an integer.")

    return errors


def assert_valid_tests_status(payload: dict[str, Any]) -> None:
    errors = validate_tests_status(payload)
    if errors:
        raise TestStatusValidationError(errors)


def write_tests_status_json(output_dir: str | Path, payload: dict[str, Any]) -> str:
    assert_valid_tests_status(payload)
    path = Path(output_dir) / "tests_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def read_tests_status_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert_valid_tests_status(payload)
    return payload


def _split_command(command: str) -> tuple[list[str] | None, str | None]:
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return None, f"Command could not be parsed safely: {exc}."
    if not parts:
        return None, "Command must not be empty."
    blocked_tokens = {"|", "||", "&", "&&", ";", ">", ">>", "<", "$(", "`"}
    if any(token in blocked_tokens for token in parts):
        return None, "Shell control operators are not allowed in verification commands."
    return parts, None


def _is_allowed_command(parts: list[str]) -> bool:
    executable = Path(parts[0]).name
    if executable == "pytest":
        return True
    if executable in {"python", "python3", Path(sys.executable).name} and len(parts) >= 3:
        return parts[1] == "-m" and parts[2] in ALLOWED_PYTHON_MODULES
    return False


def _blocked_command_result(
    *, command: str, cwd: Path, timeout_seconds: int, message: str
) -> dict[str, Any]:
    return {
        "command": command,
        "working_directory": str(cwd),
        "timeout_seconds": timeout_seconds,
        "return_code": None,
        "stdout": "",
        "stderr": message,
        "produced_files": [],
        "status": "blocked",
    }


def _run_one_command(*, command: str, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    parts, parse_error = _split_command(command)
    if parse_error or parts is None:
        return _blocked_command_result(
            command=command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            message=parse_error or "Command could not be parsed safely.",
        )
    if not _is_allowed_command(parts):
        return _blocked_command_result(
            command=command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            message="Command is not in the mock/test/smoke allowlist.",
        )

    try:
        completed = subprocess.run(
            parts,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "working_directory": str(cwd),
            "timeout_seconds": timeout_seconds,
            "return_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"Command timed out after {timeout_seconds} seconds.",
            "produced_files": [],
            "status": "timeout",
        }

    return {
        "command": command,
        "working_directory": str(cwd),
        "timeout_seconds": timeout_seconds,
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "produced_files": [],
        "status": "passed" if completed.returncode == 0 else "failed",
    }


def run_verification_commands(
    *,
    commands: list[str],
    output_dir: str | Path,
    run_id: str,
    case_id: str,
    cwd: str | Path,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    cwd_path = Path(cwd).resolve()
    command_results = [
        _run_one_command(command=command, cwd=cwd_path, timeout_seconds=timeout_seconds)
        for command in commands
    ]
    passed = bool(command_results) and all(result["status"] == "passed" for result in command_results)
    status = "tests_passed" if passed else "tests_failed"
    payload = _base_status(
        run_id=run_id,
        case_id=case_id,
        status=status,
        summary=(
            "All configured verification commands passed."
            if passed
            else "One or more configured verification commands failed or were blocked."
        ),
    )
    payload["commands"] = command_results
    if not passed:
        payload["errors"] = [
            {
                "field": "verification_commands",
                "message": result["stderr"] or f"{result['command']} did not pass.",
                "command": result["command"],
            }
            for result in command_results
            if result["status"] != "passed"
        ]
    tests_status_path = write_tests_status_json(output_dir, payload)
    return {"tests_status": payload, "tests_status_path": tests_status_path}


def run_task_packet_verification(
    packet_path: str | Path, *, cwd: str | Path, timeout_seconds: int = 60
) -> dict[str, Any]:
    packet = read_task_packet_yaml(packet_path)
    return run_verification_commands(
        commands=packet["verification_commands"],
        output_dir=Path(packet_path).parent,
        run_id=packet["run_id"],
        case_id=packet["case_id"],
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )
