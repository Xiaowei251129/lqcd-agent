"""File-based Codex handoff helpers.

The default runtime writes and reads handoff files. Explicit auto-handoff mode may
invoke Codex through the separate Codex CLI worker.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lqcd_agent.coder.task_packet import (
    TaskPacketValidationError,
    build_coder_task_packet,
    read_task_packet_yaml,
    write_task_packet_yaml,
)
from lqcd_agent.coder.test_runner import TestStatusValidationError, read_tests_status_json


CODE_CHANGE_SUMMARY_FILENAME = "code_change_summary.md"
TESTS_STATUS_FILENAME = "tests_status.json"


def ensure_task_packet(state: dict[str, Any]) -> dict[str, Any]:
    packet_path = state.get("coder_task_packet_path")
    if packet_path and Path(packet_path).exists():
        packet = read_task_packet_yaml(packet_path)
        return {"packet": packet, "coder_task_packet_path": str(Path(packet_path))}

    method_plan_path = state.get("method_plan_path")
    if not method_plan_path or not Path(method_plan_path).exists():
        raise TaskPacketValidationError(
            ["coder_task_packet_path is missing and method_plan_path cannot be used to rebuild it."]
        )

    method_plan = json.loads(Path(method_plan_path).read_text(encoding="utf-8"))
    gaps = method_plan.get("implementation_gaps") or [
        "Address the structured code failure reported by the graph runtime."
    ]
    packet = build_coder_task_packet(
        method_plan=method_plan,
        repo_inventory={},
        task_summary="Repair the mock-only workflow before analysis execution can continue.",
        implementation_gaps=[str(gap) for gap in gaps],
    )
    written_path = write_task_packet_yaml(state["output_dir"], packet)
    return {"packet": packet, "coder_task_packet_path": written_path}


def read_handoff_results(output_dir: str | Path) -> dict[str, Any]:
    output_path = Path(output_dir)
    summary_path = output_path / CODE_CHANGE_SUMMARY_FILENAME
    tests_path = output_path / TESTS_STATUS_FILENAME

    result: dict[str, Any] = {
        "handoff_status": "pending",
        "summary": "Waiting for external Codex handoff result files.",
        "code_change_summary_path": str(summary_path) if summary_path.exists() else None,
        "tests_status_path": str(tests_path) if tests_path.exists() else None,
        "code_change_summary": None,
        "tests_status": None,
        "warnings": [],
        "errors": [],
    }

    if summary_path.exists():
        result["code_change_summary"] = summary_path.read_text(encoding="utf-8")
        if not str(result["code_change_summary"]).strip():
            result["warnings"].append(
                {
                    "field": CODE_CHANGE_SUMMARY_FILENAME,
                    "message": "Code change summary exists but is empty.",
                }
            )

    if not tests_path.exists():
        return result

    try:
        tests_status = read_tests_status_json(tests_path)
    except (json.JSONDecodeError, TestStatusValidationError) as exc:
        result["handoff_status"] = "halted"
        result["summary"] = "tests_status.json is present but invalid."
        result["errors"].append(
            {
                "field": TESTS_STATUS_FILENAME,
                "message": str(exc),
                "path": str(tests_path),
            }
        )
        return result

    result["tests_status"] = tests_status
    structured_status = tests_status["status"]
    if structured_status == "tests_passed" and not summary_path.exists():
        result["handoff_status"] = "pending"
        result["summary"] = "tests_status.json passed, but code_change_summary.md is missing."
        result["warnings"].append(
            {
                "field": CODE_CHANGE_SUMMARY_FILENAME,
                "message": "Required handoff summary is missing.",
            }
        )
        return result

    result["handoff_status"] = structured_status
    result["summary"] = tests_status["summary"]
    return result
