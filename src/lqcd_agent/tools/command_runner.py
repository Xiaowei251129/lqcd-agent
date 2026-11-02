"""Safe command runner for mock analysis execution."""
from __future__ import annotations
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
FORBIDDEN_PATH_PARTS = {'raw_data', 'accepted_results'}
SUMMARY_LIMIT = 4000

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _summarize_text(text: str | bytes | None) -> str:
    if text is None:
        return ''
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    if len(text) <= SUMMARY_LIMIT:
        return text
    return text[:SUMMARY_LIMIT] + '\n[truncated]\n'

def _has_forbidden_path_part(path: Path) -> bool:
    return any((part in FORBIDDEN_PATH_PARTS for part in path.parts))

def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True

def _safe_output_path(output_dir: Path, relative_path: str) -> tuple[Path | None, str | None]:
    output_path = Path(relative_path)
    if output_path.is_absolute():
        return (None, 'Output paths must be relative to the run output directory.')
    if _has_forbidden_path_part(output_path):
        return (None, 'Output paths must not target raw_data or accepted_results.')
    resolved = (output_dir / output_path).resolve()
    if not _is_within(resolved, output_dir):
        return (None, 'Output paths must stay under the run output directory.')
    return (resolved, None)

def _snapshot_files(output_dir: Path) -> set[str]:
    if not output_dir.exists():
        return set()
    return {str(path.resolve()) for path in output_dir.rglob('*') if path.is_file() and (not _has_forbidden_path_part(path))}

def _command_text(command: str | Sequence[str]) -> str:
    if isinstance(command, str):
        return command
    return shlex.join([str(part) for part in command])

def _blocked_result(*, command_id: str, command: str, cwd: Path, timeout_seconds: int, started_at: str, message: str) -> dict[str, Any]:
    return {'command_id': command_id, 'command': command, 'command_kind': 'blocked', 'working_directory': str(cwd), 'timeout_seconds': timeout_seconds, 'started_at': started_at, 'completed_at': utc_now(), 'return_code': None, 'stdout': '', 'stderr': message, 'produced_files': [], 'status': 'blocked'}

def _split_local_command(command: str) -> tuple[list[str] | None, str | None]:
    blocked_markers = ['|', '&&', '||', ';', '>', '<', '$(', '`']
    if any((marker in command for marker in blocked_markers)):
        return (None, 'Shell control operators are not allowed in analysis commands.')
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return (None, f'Command could not be parsed safely: {exc}.')
    if not parts:
        return (None, 'Command must not be empty.')
    return (parts, None)

def _synthetic_matrix_elements_payload(*, run_id: str, case_id: str) -> dict[str, Any]:
    return {'schema_version': '0.1', 'run_id': run_id, 'case_id': case_id, 'created_at': utc_now(), 'producer': 'analysis_engineer', 'status': 'success', 'summary': 'Mock synthetic matrix elements without real raw data.', 'warnings': [], 'errors': [], 'source_kind': 'synthetic', 'z_values': [0, 1], 'pz_values': [1], 'matrix_elements': [{'z': 0, 'Pz': 1, 'component': 'real', 'value': 1.0, 'error': 0.01}, {'z': 1, 'Pz': 1, 'component': 'real', 'value': 0.5, 'error': 0.02}], 'normalization': 'mock_unit', 'uncertainties': 'deterministic_mock', 'diagnostic_flags': []}

def _run_mock_command(*, command_id: str, command: str, cwd: Path, output_dir: Path, timeout_seconds: int, started_at: str, run_id: str, case_id: str, force: bool) -> dict[str, Any]:
    completed_at = utc_now()
    if command == 'mock:success':
        return {'command_id': command_id, 'command': command, 'command_kind': 'mock', 'working_directory': str(cwd), 'timeout_seconds': timeout_seconds, 'started_at': started_at, 'completed_at': completed_at, 'return_code': 0, 'stdout': 'Mock command completed successfully.\n', 'stderr': '', 'produced_files': [], 'status': 'passed'}
    if command == 'mock:fail':
        return {'command_id': command_id, 'command': command, 'command_kind': 'mock', 'working_directory': str(cwd), 'timeout_seconds': timeout_seconds, 'started_at': started_at, 'completed_at': completed_at, 'return_code': 1, 'stdout': '', 'stderr': 'Configured mock command failed.', 'produced_files': [], 'status': 'failed'}
    prefix = 'mock:write_synthetic_matrix_elements'
    if command == prefix or command.startswith(prefix + ':'):
        relative_output = command[len(prefix) + 1:] if command.startswith(prefix + ':') else 'analysis_outputs/synthetic_matrix_elements.json'
        output_path, error = _safe_output_path(output_dir, relative_output)
        if error or output_path is None:
            return _blocked_result(command_id=command_id, command=command, cwd=cwd, timeout_seconds=timeout_seconds, started_at=started_at, message=error or 'Invalid mock output path.')
        if output_path.exists() and (not force):
            return _blocked_result(command_id=command_id, command=command, cwd=cwd, timeout_seconds=timeout_seconds, started_at=started_at, message='Refusing to overwrite an existing analysis output without force.')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _synthetic_matrix_elements_payload(run_id=run_id, case_id=case_id)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        return {'command_id': command_id, 'command': command, 'command_kind': 'mock', 'working_directory': str(cwd), 'timeout_seconds': timeout_seconds, 'started_at': started_at, 'completed_at': utc_now(), 'return_code': 0, 'stdout': f'Wrote {output_path}.\n', 'stderr': '', 'produced_files': [str(output_path)], 'status': 'passed'}
    return _blocked_result(command_id=command_id, command=command, cwd=cwd, timeout_seconds=timeout_seconds, started_at=started_at, message='Mock analysis command is not recognized.')

def _local_command_is_allowed(command: str, allowed_commands: Sequence[str] | None) -> bool:
    return bool(allowed_commands) and command in {str(item) for item in allowed_commands}

def _local_command_has_forbidden_paths(parts: Sequence[str]) -> bool:
    return any((_has_forbidden_path_part(Path(part)) for part in parts))

def run_command(*, command: str | Sequence[str], cwd: str | Path, output_dir: str | Path, run_id: str, case_id: str, command_id: str='cmd_001', timeout_seconds: int=60, allowed_commands: Sequence[str] | None=None, force: bool=False) -> dict[str, Any]:
    cwd_path = Path(cwd).resolve()
    output_path = Path(output_dir).resolve()
    command_display = _command_text(command)
    started_at = utc_now()
    if _has_forbidden_path_part(cwd_path) or _has_forbidden_path_part(output_path):
        return _blocked_result(command_id=command_id, command=command_display, cwd=cwd_path, timeout_seconds=timeout_seconds, started_at=started_at, message='Commands must not run in or write to forbidden data paths.')
    if command_display.startswith('mock:'):
        return _run_mock_command(command_id=command_id, command=command_display, cwd=cwd_path, output_dir=output_path, timeout_seconds=timeout_seconds, started_at=started_at, run_id=run_id, case_id=case_id, force=force)
    parts, parse_error = _split_local_command(command_display)
    if parse_error or parts is None:
        return _blocked_result(command_id=command_id, command=command_display, cwd=cwd_path, timeout_seconds=timeout_seconds, started_at=started_at, message=parse_error or 'Command could not be parsed safely.')
    if not _local_command_is_allowed(command_display, allowed_commands):
        return _blocked_result(command_id=command_id, command=command_display, cwd=cwd_path, timeout_seconds=timeout_seconds, started_at=started_at, message='Local analysis command is not in the exact configured allowlist.')
    if _local_command_has_forbidden_paths(parts):
        return _blocked_result(command_id=command_id, command=command_display, cwd=cwd_path, timeout_seconds=timeout_seconds, started_at=started_at, message='Analysis commands must not reference raw_data or accepted_results.')
    before_files = _snapshot_files(output_path)
    try:
        completed = subprocess.run(parts, cwd=str(cwd_path), capture_output=True, text=True, timeout=timeout_seconds, check=False, shell=False)
    except subprocess.TimeoutExpired as exc:
        after_files = _snapshot_files(output_path)
        return {'command_id': command_id, 'command': command_display, 'command_kind': 'local', 'working_directory': str(cwd_path), 'timeout_seconds': timeout_seconds, 'started_at': started_at, 'completed_at': utc_now(), 'return_code': None, 'stdout': _summarize_text(exc.stdout), 'stderr': _summarize_text(exc.stderr) or f'Command timed out after {timeout_seconds} seconds.', 'produced_files': sorted(after_files - before_files), 'status': 'timeout'}
    after_files = _snapshot_files(output_path)
    return {'command_id': command_id, 'command': command_display, 'command_kind': 'local', 'working_directory': str(cwd_path), 'timeout_seconds': timeout_seconds, 'started_at': started_at, 'completed_at': utc_now(), 'return_code': completed.returncode, 'stdout': _summarize_text(completed.stdout), 'stderr': _summarize_text(completed.stderr), 'produced_files': sorted(after_files - before_files), 'status': 'passed' if completed.returncode == 0 else 'failed'}

def run_commands(*, commands: Sequence[str | Sequence[str]], cwd: str | Path, output_dir: str | Path, run_id: str, case_id: str, timeout_seconds: int=60, allowed_commands: Sequence[str] | None=None, force: bool=False) -> list[dict[str, Any]]:
    return [run_command(command=command, cwd=cwd, output_dir=output_dir, run_id=run_id, case_id=case_id, command_id=f'cmd_{index:03d}', timeout_seconds=timeout_seconds, allowed_commands=allowed_commands, force=force) for index, command in enumerate(commands, 1)]
