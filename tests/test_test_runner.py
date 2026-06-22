from pathlib import Path

from lqcd_agent.coder.task_packet import build_coder_task_packet, write_task_packet_yaml
from lqcd_agent.coder.test_runner import run_task_packet_verification


def _write_packet(tmp_path: Path, command: str) -> str:
    method_plan = {
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
    packet = build_coder_task_packet(
        method_plan=method_plan,
        repo_inventory={"allowed_files": ["src/lqcd_agent/coder/test_runner.py"]},
        verification_commands=[command],
    )
    return write_task_packet_yaml(tmp_path, packet)


def test_runner_records_passing_command(tmp_path: Path) -> None:
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    packet_path = _write_packet(tmp_path, "pytest test_sample.py -q")

    result = run_task_packet_verification(packet_path, cwd=tmp_path, timeout_seconds=30)
    command = result["tests_status"]["commands"][0]

    assert result["tests_status"]["status"] == "tests_passed"
    assert command["command"] == "pytest test_sample.py -q"
    assert command["return_code"] == 0
    assert command["stdout"]
    assert isinstance(command["stderr"], str)
    assert command["produced_files"] == []
    assert command["status"] == "passed"
    assert (tmp_path / "tests_status.json").exists()


def test_runner_records_failing_command(tmp_path: Path) -> None:
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_bad():\n    assert False\n", encoding="utf-8")
    packet_path = _write_packet(tmp_path, "pytest test_sample.py -q")

    result = run_task_packet_verification(packet_path, cwd=tmp_path, timeout_seconds=30)
    command = result["tests_status"]["commands"][0]

    assert result["tests_status"]["status"] == "tests_failed"
    assert command["return_code"] != 0
    assert command["stdout"]
    assert isinstance(command["stderr"], str)
    assert command["produced_files"] == []
    assert command["status"] == "failed"


def test_runner_records_blocked_command_without_shell_execution(tmp_path: Path) -> None:
    packet_path = _write_packet(tmp_path, "python -c 'print(1)'")

    result = run_task_packet_verification(packet_path, cwd=tmp_path, timeout_seconds=30)
    command = result["tests_status"]["commands"][0]

    assert result["tests_status"]["status"] == "tests_failed"
    assert command["return_code"] is None
    assert command["stdout"] == ""
    assert "allowlist" in command["stderr"]
    assert command["produced_files"] == []
    assert command["status"] == "blocked"
