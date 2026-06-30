"""CLI entry point for the deterministic mock graph runtime."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.graph.analysis_graph import compile_analysis_graph
from lqcd_agent.graph.state import initialize_state


PROTECTED_RUN_ARTIFACTS = {
    "run_result.json",
    "manifest.json",
    "scientific_review_report.json",
    "decision_log.json",
    "final_report.md",
    "memory_update.json",
}


def _read_mock_case(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        if value and not value.startswith("["):
            result[key.strip()] = value
    return result


def _sqlite_saver(db_path: Path) -> tuple[Any, sqlite3.Connection]:
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "SqliteSaver is unavailable. Install the declared langgraph-checkpoint-sqlite dependency."
        ) from exc

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(connection)
    setup = getattr(saver, "setup", None)
    if callable(setup):
        setup()
    return saver, connection


def _timestamp_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")


def _protected_artifacts_in(run_output_dir: Path) -> list[Path]:
    return sorted(path for path in (run_output_dir / name for name in PROTECTED_RUN_ARTIFACTS) if path.exists())


def _raise_if_protected_run_exists(run_output_dir: Path) -> None:
    existing = _protected_artifacts_in(run_output_dir)
    if not existing:
        return
    existing_names = ", ".join(path.name for path in existing)
    raise FileExistsError(
        "Refusing to reuse run directory with completed or decision artifacts: "
        f"{run_output_dir} contains {existing_names}. Choose a new --run-id."
    )


def run_mock_graph(
    *,
    case_path: str,
    output_dir: str,
    run_id: str | None = None,
    llm_provider_config_path: str | None = None,
) -> dict[str, Any]:
    case_config_path = Path(case_path)
    requested_output_dir = Path(output_dir)
    case_data = _read_mock_case(case_config_path)
    case_id = case_data.get("case_id", case_config_path.stem)
    resolved_run_id = run_id or _timestamp_run_id()
    run_output_dir = requested_output_dir / case_id / resolved_run_id
    _raise_if_protected_run_exists(run_output_dir)
    checkpoint_db_path = run_output_dir / "checkpoints" / "graph_checkpoints.sqlite"
    checkpointer, connection = _sqlite_saver(checkpoint_db_path)
    try:
        state = initialize_state(
            case_id=case_id,
            run_id=resolved_run_id,
            user_goal=case_data.get("physics_goal", "Run deterministic mock LQCD graph."),
            case_config_path=str(case_config_path),
            output_dir=str(run_output_dir),
            checkpoint_backend="sqlite",
            checkpoint_db_path=str(checkpoint_db_path),
            llm_provider_config_path=llm_provider_config_path,
        )
        app = compile_analysis_graph(checkpointer)
        config = {"configurable": {"thread_id": state["checkpoint_thread_id"]}}
        final_state = app.invoke(state, config=config)
        return {"state": final_state, "config": config, "checkpoint_db_path": str(checkpoint_db_path)}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic mock LQCD LangGraph runtime.")
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--llm-provider-config",
        default=None,
        help="Optional explicit provider config path. Omit to use deterministic agents.",
    )
    args = parser.parse_args()
    try:
        result = run_mock_graph(
            case_path=args.case,
            output_dir=args.output_dir,
            run_id=args.run_id,
            llm_provider_config_path=args.llm_provider_config,
        )
    except FileExistsError as exc:
        parser.exit(status=2, message=f"error: {exc}\n")
    state = result["state"]
    print(f"status={state['status']}")
    print(f"graph_state={Path(state['output_dir']) / 'graph_state.json'}")
    print(f"checkpoint_db_path={result['checkpoint_db_path']}")


if __name__ == "__main__":
    main()
