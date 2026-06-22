from pathlib import Path

import pytest

from lqcd_agent.coder.task_packet import (
    TaskPacketValidationError,
    build_coder_task_packet,
    read_task_packet_yaml,
    validate_task_packet,
    write_task_packet_yaml,
)


def _method_plan() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": "unit_run",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "method_planner",
        "status": "success",
        "summary": "Method plan.",
        "warnings": [],
        "errors": [],
        "physics_goal": "Plan a mock-only analysis.",
        "implementation_gaps": ["Missing mock validator."],
        "code_needed": True,
        "coder_task_summary": "Implement missing mock validator.",
    }


def test_valid_task_packet_passes_validation_and_round_trips(tmp_path: Path) -> None:
    packet = build_coder_task_packet(
        method_plan=_method_plan(),
        repo_inventory={"allowed_files": ["src/lqcd_agent/coder/task_packet.py"]},
    )

    assert validate_task_packet(packet) == []

    path = write_task_packet_yaml(tmp_path, packet)
    loaded = read_task_packet_yaml(path)

    assert loaded["schema_version"] == "0.1"
    assert loaded["task_summary"] == "Implement missing mock validator."
    assert loaded["verification_commands"] == ["pytest tests/test_method_planner_mock.py -q"]


def test_invalid_task_packet_reports_clear_errors(tmp_path: Path) -> None:
    packet = build_coder_task_packet(
        method_plan=_method_plan(),
        repo_inventory={"allowed_files": ["src/lqcd_agent/coder/task_packet.py"]},
    )
    packet.pop("verification_commands")
    packet["allowed_files"] = []

    errors = validate_task_packet(packet)

    assert "verification_commands must be a list." in errors
    assert "allowed_files must contain at least one item." in errors
    with pytest.raises(TaskPacketValidationError, match="verification_commands"):
        write_task_packet_yaml(tmp_path, packet)
