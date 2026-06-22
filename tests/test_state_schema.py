from pathlib import Path

from lqcd_agent.graph.state import initialize_state, llm_context_view, save_graph_state


def test_initialize_state_sets_checkpoint_metadata(tmp_path: Path) -> None:
    state = initialize_state(
        case_id="case_a",
        run_id="run_a",
        user_goal="mock goal",
        case_config_path="case.yaml",
        output_dir=str(tmp_path),
        checkpoint_backend="memory",
    )

    assert state["checkpoint_thread_id"] == "case_a:run_a"
    assert state["checkpoint_backend"] == "memory"
    assert state["retry_count"] == 0
    assert state["max_retry"] == 1
    assert state["context_window_status"] == "normal"


def test_long_event_log_is_summarized_for_llm_context(tmp_path: Path) -> None:
    state = initialize_state(
        case_id="case_a",
        run_id="run_a",
        user_goal="mock goal",
        case_config_path="case.yaml",
        output_dir=str(tmp_path),
        checkpoint_backend="memory",
    )
    for index in range(10):
        state["event_log"].append(
            {"node": "test", "kind": "long", "summary": f"{index} " + ("x" * 300)}
        )

    context = llm_context_view(state)
    save_graph_state(state)

    assert context["context_window_status"] == "summarized"
    assert state["event_log_summary"]
    assert state["context_summary_path"]
    assert (tmp_path / "graph_state.json").exists()
