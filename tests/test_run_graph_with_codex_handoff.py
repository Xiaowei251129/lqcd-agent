from lqcd_agent.graph import run_graph_with_codex_handoff as orchestrator


def _state(*, status: str, current_node: str, run_id: str = "run_a", tests_status_path=None):
    return {
        "run_id": run_id,
        "status": status,
        "current_node": current_node,
        "output_dir": "/tmp/case_a/run_a",
        "coder_task_packet_path": "/tmp/case_a/run_a/coder_task_packet.yaml",
        "tests_status_path": tests_status_path,
    }


def test_orchestrator_runs_worker_and_reruns_graph(monkeypatch) -> None:
    graph_calls = []
    worker_calls = []

    def fake_run_graph(**kwargs):
        graph_calls.append(kwargs)
        if len(graph_calls) == 1:
            return {
                "state": _state(status="pending", current_node="codex_handoff"),
                "checkpoint_db_path": "/tmp/checkpoints.sqlite",
            }
        return {
            "state": _state(status="success", current_node="memory_report"),
            "checkpoint_db_path": "/tmp/checkpoints.sqlite",
        }

    def fake_run_worker(**kwargs):
        worker_calls.append(kwargs)
        return {"status": "tests_passed", "tests_status_path": "/tmp/tests_status.json"}

    monkeypatch.setattr(orchestrator, "run_mock_graph", fake_run_graph)
    monkeypatch.setattr(orchestrator, "run_worker", fake_run_worker)

    result = orchestrator.run_graph_with_codex_handoff(
        case_path="case.yaml",
        output_dir="/tmp/out",
        run_id=None,
        repo_root="/repo",
    )

    assert result["handoff_attempt_count"] == 1
    assert len(worker_calls) == 1
    assert worker_calls[0]["run_dir"] == "/tmp/case_a/run_a"
    assert graph_calls[1]["run_id"] == "run_a"
    assert result["state"]["current_node"] == "memory_report"


def test_orchestrator_does_not_run_worker_when_not_pending(monkeypatch) -> None:
    worker_calls = []

    monkeypatch.setattr(
        orchestrator,
        "run_mock_graph",
        lambda **kwargs: {
            "state": _state(status="success", current_node="memory_report"),
            "checkpoint_db_path": "/tmp/checkpoints.sqlite",
        },
    )
    monkeypatch.setattr(orchestrator, "run_worker", lambda **kwargs: worker_calls.append(kwargs))

    result = orchestrator.run_graph_with_codex_handoff(
        case_path="case.yaml",
        output_dir="/tmp/out",
        run_id="run_a",
    )

    assert result["handoff_attempt_count"] == 0
    assert worker_calls == []
