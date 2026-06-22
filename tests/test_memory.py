import json
from pathlib import Path

import pytest

from lqcd_agent.graph.state import initialize_state
from lqcd_agent.memory.query import memory_category, read_memory_update
from lqcd_agent.memory.store import write_memory_update


def _state(tmp_path: Path):
    return initialize_state(
        case_id="case_a",
        run_id="run_a",
        user_goal="mock goal",
        case_config_path="case.yaml",
        output_dir=str(tmp_path),
        checkpoint_backend="memory",
    )


def _decision_file(tmp_path: Path, decision: str) -> Path:
    packet_dir = tmp_path / "approval_packet"
    packet_dir.mkdir(parents=True)
    path = packet_dir / "07_human_decision.yaml"
    path.write_text(
        "\n".join(
            [
                'schema_version: "0.1"',
                'run_id: "run_a"',
                'case_id: "case_a"',
                f'decision: "{decision}"',
                'conditions: ""',
                'reason: "Reviewed by test."',
                'decided_by: "tester"',
                'decided_at: "2026-06-19T00:00:00+00:00"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_low_risk_accept_mock_result_writes_accepted_memory(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "low"
    state["recommended_action"] = "accept_mock_result"
    state["human_approval_required"] = False

    result = write_memory_update(state)

    payload = read_memory_update(result["memory_update_path"])
    assert payload["memory_status"] == "accepted"
    assert payload["accepted_result"] is True
    assert memory_category(result["memory_update_path"]) == "accepted"


def test_medium_risk_writes_pending_memory(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "medium"
    state["recommended_action"] = "human_review_recommended"

    result = write_memory_update(state)

    payload = json.loads(Path(result["memory_update_path"]).read_text(encoding="utf-8"))
    assert payload["memory_status"] == "pending"
    assert payload["accepted_result"] is False


def test_high_risk_without_approval_does_not_write_accepted_memory(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "high"
    state["recommended_action"] = "pending_human_approval"
    state["human_approval_required"] = True

    result = write_memory_update(state)

    assert result["memory_update"]["memory_status"] == "pending"
    assert result["memory_update"]["accepted_result"] is False


def test_human_reject_or_hold_writes_rejected_memory(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state["risk_level"] = "high"
    state["recommended_action"] = "pending_human_approval"
    state["human_approval_required"] = True
    state["human_decision_path"] = str(_decision_file(tmp_path, "reject_or_hold"))

    result = write_memory_update(state)

    assert result["memory_update"]["memory_status"] == "rejected"
    assert result["memory_update"]["accepted_result"] is False
    assert result["memory_update"]["human_decision"] == "reject_or_hold"


def test_refuses_to_overwrite_different_run_memory_update(tmp_path: Path) -> None:
    path = tmp_path / "memory_update.json"
    path.write_text('{"run_id": "other", "case_id": "case_a"}\n', encoding="utf-8")
    state = _state(tmp_path)

    with pytest.raises(FileExistsError, match="different run"):
        write_memory_update(state)
