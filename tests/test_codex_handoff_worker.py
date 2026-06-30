import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lqcd_agent.coder import codex_handoff_worker
from lqcd_agent.coder.codex_handoff import read_handoff_results
from lqcd_agent.coder.task_packet import TaskPacketValidationError, build_coder_task_packet, write_task_packet_yaml
from lqcd_agent.coder.test_runner import write_tests_status_json


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


def _write_packet(run_dir: Path, *, allowed_files: list[str] | None = None) -> str:
    packet = build_coder_task_packet(
        method_plan=_method_plan(),
        repo_inventory={"allowed_files": allowed_files or ["src/lqcd_agent/coder/codex_handoff_worker.py"]},
        verification_commands=["pytest tests/test_coder_task_packet.py -q"],
    )
    return write_task_packet_yaml(run_dir, packet)


def _passed_status(run_dir: Path) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "run_id": "unit_run",
        "case_id": "case_a",
        "created_at": "2026-06-10T00:00:00+00:00",
        "producer": "test_runner",
        "status": "tests_passed",
        "summary": "All configured verification commands passed.",
        "warnings": [],
        "errors": [],
        "commands": [
            {
                "command": "pytest tests/test_coder_task_packet.py -q",
                "working_directory": str(run_dir),
                "timeout_seconds": 60,
                "return_code": 0,
                "stdout": "passed",
                "stderr": "",
                "produced_files": [],
                "status": "passed",
            }
        ],
    }


def _fake_codex_success(command, cwd, capture_output, text, timeout, check, shell):
    assert command[:2] == ["codex", "exec"]
    message_path = Path(command[command.index("--output-last-message") + 1])
    message_path.write_text("Implemented the requested worker changes.\n", encoding="utf-8")
    return SimpleNamespace(returncode=0, stdout="codex stdout", stderr="")


def test_worker_requires_task_packet(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="coder_task_packet.yaml"):
        codex_handoff_worker.run_worker(run_dir=tmp_path, repo_root=tmp_path)

    assert not (tmp_path / "tests_status.json").exists()
    assert not (tmp_path / "code_change_summary.md").exists()


def test_worker_rejects_invalid_task_packet(tmp_path: Path) -> None:
    (tmp_path / "coder_task_packet.yaml").write_text('schema_version: "0.1"\n', encoding="utf-8")

    with pytest.raises(TaskPacketValidationError):
        codex_handoff_worker.run_worker(run_dir=tmp_path, repo_root=tmp_path)

    assert not (tmp_path / "tests_status.json").exists()
    assert not (tmp_path / "code_change_summary.md").exists()


def test_worker_refuses_existing_results_without_force(tmp_path: Path) -> None:
    _write_packet(tmp_path)
    (tmp_path / "tests_status.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Use --force"):
        codex_handoff_worker.run_worker(run_dir=tmp_path, repo_root=tmp_path)


def test_worker_runs_codex_verification_and_writes_handoff_results(monkeypatch, tmp_path: Path) -> None:
    _write_packet(tmp_path)
    monkeypatch.setattr(codex_handoff_worker.subprocess, "run", _fake_codex_success)
    monkeypatch.setattr(codex_handoff_worker, "_git_status", lambda repo_root: {})

    def fake_verification(packet_path, *, cwd, timeout_seconds):
        payload = _passed_status(Path(packet_path).parent)
        path = write_tests_status_json(Path(packet_path).parent, payload)
        return {"tests_status": payload, "tests_status_path": path}

    monkeypatch.setattr(codex_handoff_worker, "run_task_packet_verification", fake_verification)

    result = codex_handoff_worker.run_worker(run_dir=tmp_path, repo_root=tmp_path)

    assert result["status"] == "tests_passed"
    summary = (tmp_path / "code_change_summary.md").read_text(encoding="utf-8")
    assert "Implemented the requested worker changes." in summary
    assert "verification_status: tests_passed" in summary
    handoff = read_handoff_results(tmp_path)
    assert handoff["handoff_status"] == "tests_passed"


def test_worker_records_codex_failure_as_failed_handoff(monkeypatch, tmp_path: Path) -> None:
    _write_packet(tmp_path)
    monkeypatch.setattr(codex_handoff_worker, "_git_status", lambda repo_root: {})

    def fake_codex_failure(command, cwd, capture_output, text, timeout, check, shell):
        return SimpleNamespace(returncode=1, stdout="", stderr="codex failed")

    monkeypatch.setattr(codex_handoff_worker.subprocess, "run", fake_codex_failure)

    result = codex_handoff_worker.run_worker(run_dir=tmp_path, repo_root=tmp_path)

    assert result["status"] == "tests_failed"
    payload = json.loads((tmp_path / "tests_status.json").read_text(encoding="utf-8"))
    assert payload["status"] == "tests_failed"
    assert payload["commands"][0]["status"] == "failed"
    assert "codex failed" in payload["commands"][0]["stderr"]
    assert read_handoff_results(tmp_path)["handoff_status"] == "tests_failed"


def test_worker_marks_scope_violations_as_failed(monkeypatch, tmp_path: Path) -> None:
    _write_packet(tmp_path, allowed_files=["src/lqcd_agent/coder/codex_handoff_worker.py"])
    monkeypatch.setattr(codex_handoff_worker.subprocess, "run", _fake_codex_success)

    statuses = iter(
        [
            {},
            {
                "src/lqcd_agent/coder/codex_handoff_worker.py": " M",
                "src/lqcd_agent/graph/nodes.py": " M",
            },
        ]
    )
    monkeypatch.setattr(codex_handoff_worker, "_git_status", lambda repo_root: next(statuses))

    def fake_verification(packet_path, *, cwd, timeout_seconds):
        payload = _passed_status(Path(packet_path).parent)
        path = write_tests_status_json(Path(packet_path).parent, payload)
        return {"tests_status": payload, "tests_status_path": path}

    monkeypatch.setattr(codex_handoff_worker, "run_task_packet_verification", fake_verification)

    result = codex_handoff_worker.run_worker(run_dir=tmp_path, repo_root=tmp_path)

    assert result["status"] == "tests_failed"
    payload = json.loads((tmp_path / "tests_status.json").read_text(encoding="utf-8"))
    assert payload["status"] == "tests_failed"
    assert payload["errors"][-1]["paths"] == ["src/lqcd_agent/graph/nodes.py"]
    summary = (tmp_path / "code_change_summary.md").read_text(encoding="utf-8")
    assert "src/lqcd_agent/graph/nodes.py" in summary
