"""External Codex CLI worker for file-based coder handoffs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.coder.codex_handoff import CODE_CHANGE_SUMMARY_FILENAME, TESTS_STATUS_FILENAME
from lqcd_agent.coder.task_packet import TaskPacketValidationError, read_task_packet_yaml
from lqcd_agent.coder.test_runner import (
    TEST_STATUS_SCHEMA_VERSION,
    run_task_packet_verification,
    write_tests_status_json,
)


LAST_MESSAGE_FILENAME = "codex_handoff_last_message.md"
WORKER_PRODUCER = "codex_handoff_worker"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_codex_prompt(packet: dict[str, Any]) -> str:
    def bullet_list(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items)

    return "\n".join(
        [
            "You are Codex acting as the external coder for a file-based LQCD agent handoff.",
            "",
            "Follow the task packet exactly. Keep changes minimal and scoped.",
            "Do not modify raw data, accepted results, secrets, or unrelated files.",
            "Do not write code comments in any language other than English.",
            "",
            f"Run ID: {packet['run_id']}",
            f"Case ID: {packet['case_id']}",
            f"Task summary: {packet['task_summary']}",
            f"Physics goal: {packet['physics_goal']}",
            "",
            "Implementation gaps:",
            bullet_list(packet["implementation_gaps"]),
            "",
            "Allowed files:",
            bullet_list(packet["allowed_files"]),
            "",
            "Forbidden paths:",
            bullet_list(packet["forbidden_paths"]),
            "",
            "Requirements:",
            bullet_list(packet["requirements"]),
            "",
            "Acceptance criteria:",
            bullet_list(packet["acceptance_criteria"]),
            "",
            "Verification commands to consider while implementing:",
            bullet_list(packet["verification_commands"]),
            "",
            "When finished, summarize the code changes and verification outcome. "
            "The outer handoff worker will run the configured verification commands and write tests_status.json.",
        ]
    )


def _artifact_paths(run_dir: Path) -> dict[str, Path]:
    return {
        "packet": run_dir / "coder_task_packet.yaml",
        "summary": run_dir / CODE_CHANGE_SUMMARY_FILENAME,
        "tests": run_dir / TESTS_STATUS_FILENAME,
        "last_message": run_dir / LAST_MESSAGE_FILENAME,
    }


def _raise_if_existing_results(run_dir: Path, *, force: bool) -> None:
    if force:
        return
    paths = _artifact_paths(run_dir)
    existing = [path for key, path in paths.items() if key in {"summary", "tests"} and path.exists()]
    if existing:
        names = ", ".join(path.name for path in existing)
        raise FileExistsError(f"Refusing to overwrite existing handoff result artifacts: {names}. Use --force.")


def _git_status(repo_root: Path) -> dict[str, str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        return {}
    status: dict[str, str] = {}
    for raw_line in completed.stdout.splitlines():
        if len(raw_line) < 4:
            continue
        path = raw_line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        status[path] = raw_line[:2]
    return status


def _changed_status_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed: list[str] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed


def _is_allowed_path(path: str, allowed_files: list[str]) -> bool:
    normalized = Path(path).as_posix()
    for allowed in allowed_files:
        allowed_path = Path(allowed).as_posix().rstrip("/")
        if normalized == allowed_path or normalized.startswith(f"{allowed_path}/"):
            return True
    return False


def scope_violations(
    *,
    before_status: dict[str, str],
    after_status: dict[str, str],
    allowed_files: list[str],
) -> list[str]:
    return [
        path
        for path in _changed_status_paths(before_status, after_status)
        if not _is_allowed_path(path, allowed_files)
    ]


def _codex_command(
    *,
    codex_bin: str,
    repo_root: Path,
    last_message_path: Path,
    codex_model: str | None,
    prompt: str,
) -> list[str]:
    command = [
        codex_bin,
        "exec",
        "--cd",
        str(repo_root),
        "--sandbox",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "--output-last-message",
        str(last_message_path),
    ]
    if codex_model:
        command.extend(["--model", codex_model])
    command.append(prompt)
    return command


def _display_command(command: list[str]) -> list[str]:
    if not command:
        return command
    return [*command[:-1], "<prompt omitted>"]


def _failed_tests_status(
    *,
    packet: dict[str, Any],
    summary: str,
    command: str,
    working_directory: Path,
    timeout_seconds: int,
    return_code: int | None,
    stdout: str,
    stderr: str,
    command_status: str,
) -> dict[str, Any]:
    return {
        "schema_version": TEST_STATUS_SCHEMA_VERSION,
        "run_id": packet["run_id"],
        "case_id": packet["case_id"],
        "created_at": utc_now(),
        "producer": WORKER_PRODUCER,
        "status": "tests_failed",
        "summary": summary,
        "warnings": [],
        "errors": [
            {
                "field": "codex_handoff_worker",
                "message": stderr or summary,
                "command": command,
            }
        ],
        "commands": [
            {
                "command": command,
                "working_directory": str(working_directory),
                "timeout_seconds": timeout_seconds,
                "return_code": return_code,
                "stdout": stdout,
                "stderr": stderr,
                "produced_files": [],
                "status": command_status,
            }
        ],
    }


def _write_summary(
    *,
    path: Path,
    packet: dict[str, Any],
    codex_command: list[str],
    codex_return_code: int | None,
    verification_status: str,
    before_status: dict[str, str],
    after_status: dict[str, str],
    scope_errors: list[str],
    last_message: str,
) -> None:
    lines = [
        "# Codex Handoff Summary",
        "",
        f"- created_at: {utc_now()}",
        f"- producer: {WORKER_PRODUCER}",
        f"- run_id: {packet['run_id']}",
        f"- case_id: {packet['case_id']}",
        f"- codex_return_code: {codex_return_code}",
        f"- verification_status: {verification_status}",
        f"- codex_command: {json.dumps(_display_command(codex_command))}",
        f"- pre_git_status_count: {len(before_status)}",
        f"- post_git_status_count: {len(after_status)}",
        f"- scope_violations: {json.dumps(scope_errors)}",
        "",
        "## Codex Final Message",
        "",
        last_message.strip() or "(Codex did not write a final message.)",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_worker(
    *,
    run_dir: str | Path,
    repo_root: str | Path | None = None,
    codex_bin: str = "codex",
    codex_model: str | None = None,
    timeout_seconds: int = 900,
    verification_timeout_seconds: int = 60,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    run_path = Path(run_dir).resolve()
    paths = _artifact_paths(run_path)
    resolved_repo_root = Path(repo_root).resolve() if repo_root is not None else default_repo_root()

    _raise_if_existing_results(run_path, force=force)

    try:
        packet = read_task_packet_yaml(paths["packet"])
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Missing coder task packet: {paths['packet']}") from exc

    prompt = build_codex_prompt(packet)
    command = _codex_command(
        codex_bin=codex_bin,
        repo_root=resolved_repo_root,
        last_message_path=paths["last_message"],
        codex_model=codex_model,
        prompt=prompt,
    )

    if dry_run:
        return {
            "status": "dry_run",
            "run_dir": str(run_path),
            "repo_root": str(resolved_repo_root),
            "codex_command": _display_command(command),
            "prompt_preview": prompt[:1000],
        }

    before_status = _git_status(resolved_repo_root)
    try:
        completed = subprocess.run(
            command,
            cwd=str(resolved_repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        codex_return_code = completed.returncode
        codex_stdout = completed.stdout
        codex_stderr = completed.stderr
        codex_status = "passed" if completed.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        codex_return_code = None
        codex_stdout = exc.stdout or ""
        codex_stderr = exc.stderr or f"Codex CLI timed out after {timeout_seconds} seconds."
        codex_status = "timeout"

    if codex_return_code != 0:
        payload = _failed_tests_status(
            packet=packet,
            summary="Codex CLI failed before verification commands could run.",
            command=" ".join(_display_command(command)),
            working_directory=resolved_repo_root,
            timeout_seconds=timeout_seconds,
            return_code=codex_return_code,
            stdout=codex_stdout,
            stderr=codex_stderr,
            command_status=codex_status,
        )
        tests_status_path = write_tests_status_json(run_path, payload)
        after_status = _git_status(resolved_repo_root)
        last_message = paths["last_message"].read_text(encoding="utf-8") if paths["last_message"].exists() else ""
        _write_summary(
            path=paths["summary"],
            packet=packet,
            codex_command=command,
            codex_return_code=codex_return_code,
            verification_status=payload["status"],
            before_status=before_status,
            after_status=after_status,
            scope_errors=[],
            last_message=last_message,
        )
        return {"status": payload["status"], "tests_status_path": tests_status_path, "code_change_summary_path": str(paths["summary"])}

    verification = run_task_packet_verification(
        paths["packet"],
        cwd=resolved_repo_root,
        timeout_seconds=verification_timeout_seconds,
    )
    tests_status = verification["tests_status"]
    after_status = _git_status(resolved_repo_root)
    scope_errors = scope_violations(
        before_status=before_status,
        after_status=after_status,
        allowed_files=[str(item) for item in packet["allowed_files"]],
    )
    if scope_errors:
        tests_status["status"] = "tests_failed"
        tests_status["summary"] = "Verification failed because Codex changed files outside the task packet scope."
        tests_status["errors"].append(
            {
                "field": "allowed_files",
                "message": "Codex changed files outside allowed_files.",
                "paths": scope_errors,
            }
        )
        write_tests_status_json(run_path, tests_status)

    last_message = paths["last_message"].read_text(encoding="utf-8") if paths["last_message"].exists() else ""
    _write_summary(
        path=paths["summary"],
        packet=packet,
        codex_command=command,
        codex_return_code=codex_return_code,
        verification_status=tests_status["status"],
        before_status=before_status,
        after_status=after_status,
        scope_errors=scope_errors,
        last_message=last_message,
    )
    return {
        "status": tests_status["status"],
        "tests_status_path": verification["tests_status_path"],
        "code_change_summary_path": str(paths["summary"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run external Codex CLI for a file-based coder handoff.")
    parser.add_argument("--run-dir", required=True, help="Run directory containing coder_task_packet.yaml.")
    parser.add_argument("--repo-root", default=None, help="Repository root. Defaults to the package repository root.")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable to invoke.")
    parser.add_argument("--codex-model", default=None, help="Optional Codex model override.")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="Codex CLI timeout.")
    parser.add_argument("--verification-timeout-seconds", type=int, default=60, help="Verification command timeout.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing handoff result artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned command metadata without invoking Codex.")
    args = parser.parse_args(argv)

    try:
        result = run_worker(
            run_dir=args.run_dir,
            repo_root=args.repo_root,
            codex_bin=args.codex_bin,
            codex_model=args.codex_model,
            timeout_seconds=args.timeout_seconds,
            verification_timeout_seconds=args.verification_timeout_seconds,
            force=args.force,
            dry_run=args.dry_run,
        )
    except (FileExistsError, FileNotFoundError, TaskPacketValidationError) as exc:
        parser.exit(status=2, message=f"error: {exc}\n")
    except subprocess.SubprocessError as exc:
        parser.exit(status=1, message=f"error: {exc}\n")

    if args.dry_run:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"status={result['status']}")
        print(f"tests_status_path={result['tests_status_path']}")
        print(f"code_change_summary_path={result['code_change_summary_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
