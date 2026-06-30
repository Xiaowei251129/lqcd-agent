"""Graph runner with an external Codex handoff orchestration loop."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lqcd_agent.coder.codex_handoff_worker import run_worker
from lqcd_agent.graph.run_graph import run_mock_graph


def _needs_codex_worker(state: dict[str, Any]) -> bool:
    return (
        state.get("current_node") == "codex_handoff"
        and state.get("status") == "pending"
        and bool(state.get("coder_task_packet_path"))
        and not state.get("tests_status_path")
    )


def run_graph_with_codex_handoff(
    *,
    case_path: str,
    output_dir: str,
    run_id: str | None = None,
    llm_provider_config_path: str | None = None,
    repo_root: str | Path | None = None,
    codex_bin: str = "codex",
    codex_model: str | None = None,
    codex_timeout_seconds: int = 900,
    verification_timeout_seconds: int = 60,
    max_handoffs: int = 1,
    force_codex_handoff: bool = False,
    dry_run_codex: bool = False,
) -> dict[str, Any]:
    result = run_mock_graph(
        case_path=case_path,
        output_dir=output_dir,
        run_id=run_id,
        llm_provider_config_path=llm_provider_config_path,
    )
    state = result["state"]
    resolved_run_id = str(state["run_id"])
    handoff_attempts: list[dict[str, Any]] = []

    while len(handoff_attempts) < max_handoffs and _needs_codex_worker(state):
        worker_result = run_worker(
            run_dir=state["output_dir"],
            repo_root=repo_root,
            codex_bin=codex_bin,
            codex_model=codex_model,
            timeout_seconds=codex_timeout_seconds,
            verification_timeout_seconds=verification_timeout_seconds,
            force=force_codex_handoff,
            dry_run=dry_run_codex,
        )
        handoff_attempts.append(worker_result)
        if dry_run_codex:
            break
        result = run_mock_graph(
            case_path=case_path,
            output_dir=output_dir,
            run_id=resolved_run_id,
            llm_provider_config_path=llm_provider_config_path,
        )
        state = result["state"]

    return {
        **result,
        "handoff_attempts": handoff_attempts,
        "handoff_attempt_count": len(handoff_attempts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run graph and automatically execute external Codex handoffs.")
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--llm-provider-config",
        default=None,
        help="Optional explicit provider config path. Omit to use deterministic agents.",
    )
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--codex-model", default=None)
    parser.add_argument("--codex-timeout-seconds", type=int, default=900)
    parser.add_argument("--verification-timeout-seconds", type=int, default=60)
    parser.add_argument("--max-handoffs", type=int, default=1)
    parser.add_argument("--force-codex-handoff", action="store_true")
    parser.add_argument("--dry-run-codex", action="store_true")
    args = parser.parse_args()

    try:
        result = run_graph_with_codex_handoff(
            case_path=args.case,
            output_dir=args.output_dir,
            run_id=args.run_id,
            llm_provider_config_path=args.llm_provider_config,
            repo_root=args.repo_root,
            codex_bin=args.codex_bin,
            codex_model=args.codex_model,
            codex_timeout_seconds=args.codex_timeout_seconds,
            verification_timeout_seconds=args.verification_timeout_seconds,
            max_handoffs=args.max_handoffs,
            force_codex_handoff=args.force_codex_handoff,
            dry_run_codex=args.dry_run_codex,
        )
    except FileExistsError as exc:
        parser.exit(status=2, message=f"error: {exc}\n")

    state = result["state"]
    print(f"status={state['status']}")
    print(f"current_node={state['current_node']}")
    print(f"handoff_attempt_count={result['handoff_attempt_count']}")
    print(f"graph_state={Path(state['output_dir']) / 'graph_state.json'}")
    print(f"checkpoint_db_path={result['checkpoint_db_path']}")


if __name__ == "__main__":
    main()
