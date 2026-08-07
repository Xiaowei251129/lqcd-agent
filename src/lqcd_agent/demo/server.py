"""Standard-library HTTP server for the local multi-agent run console."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shlex
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lqcd_agent.agents.analysis_engineer import read_case_config
from lqcd_agent.graph.approval_packet import (
    APPROVAL_PACKET_FILENAME,
    APPROVAL_SCHEMA_VERSION,
    DECISION_OPTIONS,
    HUMAN_DECISION_FILENAME,
    read_flat_human_decision_yaml,
)
from lqcd_agent.graph.nodes import human_approval_gate_node, memory_report_node
from lqcd_agent.graph.run_graph import run_mock_graph
from lqcd_agent.graph.routing import route_after_human_approval_gate


STATIC_ROOT = Path(__file__).resolve().parent / "static"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs"
CASE_CONFIGS_ROOT = REPO_ROOT / "configs" / "cases"
RUNTIME_CONFIGS_ROOT = REPO_ROOT / "configs" / "runtime"
GENERATED_CONFIG_DIRNAME = "_generated_case_configs"
RUN_JOBS: dict[tuple[str, str], dict[str, Any]] = {}
RUN_JOBS_LOCK = threading.Lock()
CASE_CONFIG_PATTERNS = ("*.yaml", "*.yml", "*.json")
RAW_DATA_DEMO_ORDER = {
    "clean_fit.input": 0,
    "noisy_valid_fit.input": 1,
    "fit_window_contamination.input": 2,
    "plateau_instability.input": 3,
    "missing_input.input": 4,
}
NODE_LABELS = {
    "START": "Start",
    "method_planner": "Method Planner",
    "analysis_engineer": "Analysis Engineer",
    "scientific_reviewer": "Scientific Reviewer",
    "decision_coordinator": "Decision Coordinator",
    "human_approval_gate": "Human Approval Gate",
    "memory_report": "Memory / Report",
    "codex_handoff": "Codex Handoff",
}


class DemoServerError(Exception):
    """Error that should be returned to the dashboard client."""

    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def utc_run_prefix() -> str:
    return datetime.now(timezone.utc).strftime("ui_%Y%m%d_%H%M%S_%f")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def read_flat_config(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    return read_case_config(path)


def case_config_sort_key(path: Path) -> tuple[int, int, str]:
    order = RAW_DATA_DEMO_ORDER.get(path.stem)
    if order is not None:
        return (0, order, path.name)
    return (1, 999, path.name)


def case_config_paths() -> list[Path]:
    paths: set[Path] = set()
    for pattern in CASE_CONFIG_PATTERNS:
        paths.update(CASE_CONFIGS_ROOT.glob(pattern))
    return sorted(paths, key=case_config_sort_key)


def raw_data_preview(payload: dict[str, Any]) -> tuple[str | None, str]:
    raw_data_path = payload.get("raw_data_path")
    if not raw_data_path:
        return None, "not_configured"
    raw_data_text = str(raw_data_path)
    candidate = Path(raw_data_text).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return raw_data_text, "exists" if candidate.is_file() else "missing"


def case_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for path in case_config_paths():
        payload = read_case_config(path)
        case_id = str(payload.get("case_id", path.stem))
        commands = as_string_list(payload.get("analysis_commands") or payload.get("analysis_command"))
        analysis_program_tags = as_string_list(payload.get("analysis_program_tags") or payload.get("analysis_tags"))
        target_observables = as_string_list(payload.get("target_observables"))
        expected_outputs = as_string_list(payload.get("expected_outputs") or payload.get("analysis_expected_outputs"))
        raw_data_path, raw_data_status = raw_data_preview(payload)
        configs.append(
            {
                "config_id": path.stem,
                "case_id": case_id,
                "path": relative_to_repo(path),
                "absolute_path": str(path),
                "label": f"{case_id} ({path.name})",
                "physics_goal": payload.get("physics_goal"),
                "source_kind": payload.get("source_kind"),
                "config_type": path.suffix.lstrip(".") or "config",
                "analysis_commands": commands,
                "analysis_route": analysis_route(
                    commands=commands,
                    analysis_program_tags=analysis_program_tags,
                    target_observables=target_observables,
                ),
                "raw_data_path": raw_data_path,
                "raw_data_status": raw_data_status,
                "analysis_program_tags": analysis_program_tags,
                "target_observables": target_observables,
                "expected_outputs": expected_outputs,
            }
        )
    return configs


def case_config_record(config_id: str) -> dict[str, Any]:
    for config in case_configs():
        if config["config_id"] == config_id or config["case_id"] == config_id or config["path"] == config_id:
            return config
    raise DemoServerError(HTTPStatus.NOT_FOUND, f"Unknown case config: {config_id}")


def runtime_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for path in sorted(RUNTIME_CONFIGS_ROOT.glob("*.yaml")):
        payload = read_flat_config(path)
        live_env = str(payload["live_test_env"]) if payload.get("live_test_env") else None
        provider = str(payload.get("provider", path.stem))
        provider_lower = provider.lower()
        provider_mode = "live" if live_env else "testing" if provider_lower == "mock" else "local"
        recommended = path.stem == "openai" or provider_lower == "openai"
        label_suffix = "live provider" if provider_mode == "live" else "testing/developer only" if provider_mode == "testing" else "local provider"
        configs.append(
            {
                "config_id": path.stem,
                "path": relative_to_repo(path),
                "absolute_path": str(path),
                "label": f"{provider} ({path.name}) - {label_suffix}",
                "provider": provider,
                "provider_mode": provider_mode,
                "recommended": recommended,
                "model_env": payload.get("model_env"),
                "api_key_env": payload.get("api_key_env"),
                "live_test_env": live_env,
                "live_test_env_enabled": bool(live_env and os.environ.get(live_env) == "1"),
            }
        )
    return sorted(configs, key=lambda item: (not bool(item["recommended"]), str(item["label"])))


def runtime_config_record(config_id: str) -> dict[str, Any]:
    candidate = Path(config_id).expanduser()
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    for config in runtime_configs():
        absolute = Path(str(config["absolute_path"])).resolve()
        if config["config_id"] == config_id or config["path"] == config_id or absolute == candidate:
            return config
    raise DemoServerError(HTTPStatus.NOT_FOUND, f"Unknown runtime config: {config_id}")


def as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def analysis_route(*, commands: list[str], analysis_program_tags: list[str], target_observables: list[str]) -> str:
    if commands:
        return "analysis_commands"
    if analysis_program_tags or target_observables:
        return "registered_analysis_program"
    return "default_mock_command"


def case_config_preview(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    payload = read_case_config(config_path)
    case_id = str(payload.get("case_id", config_path.stem))
    commands = as_string_list(payload.get("analysis_commands") or payload.get("analysis_command"))
    analysis_program_tags = as_string_list(payload.get("analysis_program_tags") or payload.get("analysis_tags"))
    target_observables = as_string_list(payload.get("target_observables"))
    expected_outputs = as_string_list(payload.get("expected_outputs") or payload.get("analysis_expected_outputs"))
    raw_data_path, raw_data_status = raw_data_preview(payload)
    route = analysis_route(
        commands=commands,
        analysis_program_tags=analysis_program_tags,
        target_observables=target_observables,
    )
    warnings: list[str] = []
    if not payload.get("case_id"):
        warnings.append("case_id is missing; the filename will be used as a fallback.")
    if not payload.get("physics_goal"):
        warnings.append("physics_goal is missing.")
    if route == "default_mock_command":
        warnings.append("analysis_commands is missing; Analysis Engineer will use its developer/testing fallback command.")
    if raw_data_status == "missing":
        warnings.append(f"raw_data_path is configured but the file is missing: {raw_data_path}.")
    if not expected_outputs:
        warnings.append("expected_outputs is missing; Analysis Engineer will use its default expected output.")
    return {
        "case_id": case_id,
        "config_name": config_path.name,
        "path": str(config_path),
        "physics_goal": payload.get("physics_goal"),
        "source_kind": payload.get("source_kind"),
        "analysis_commands": commands,
        "analysis_route": route,
        "raw_data_path": raw_data_path,
        "raw_data_status": raw_data_status,
        "analysis_program_tags": analysis_program_tags,
        "target_observables": target_observables,
        "expected_outputs": expected_outputs,
        "warnings": warnings,
    }


def generated_config_root(output_root: str | Path) -> Path:
    path = Path(output_root) / GENERATED_CONFIG_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_generated_case_config(*, config_text: str, output_root: str | Path) -> Path:
    text = config_text.strip()
    if not text:
        raise DemoServerError(HTTPStatus.BAD_REQUEST, "Case config text is empty.")
    root = generated_config_root(output_root)
    suffix = ".json" if text.startswith("{") else ".yaml"
    temp_path = root / f"pasted_{utc_run_prefix()}{suffix}"
    temp_path.write_text(text + "\n", encoding="utf-8")
    preview = case_config_preview(temp_path)
    case_id = str(preview["case_id"]).replace("/", "_").replace("..", "_")
    final_path = root / f"{case_id}_{utc_run_prefix()}{suffix}"
    temp_path.replace(final_path)
    return final_path


def resolve_case_config_path(
    *,
    output_root: str | Path,
    config_id: str | None = None,
    config_text: str | None = None,
) -> Path:
    if config_text and config_text.strip():
        return write_generated_case_config(config_text=config_text, output_root=output_root)
    if not config_id:
        raise DemoServerError(HTTPStatus.BAD_REQUEST, "Missing case config.")
    record = case_config_record(config_id)
    return Path(str(record.get("absolute_path") or record["path"]))


def resolve_output_dir(value: str | Path | None) -> Path:
    if not value:
        return DEFAULT_OUTPUT_ROOT
    output_path = Path(str(value)).expanduser()
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    return output_path.resolve()


def resolve_runtime_config_path(config_id_or_path: str | Path | None) -> str | None:
    if not config_id_or_path:
        return None
    value = str(config_id_or_path)
    record = runtime_config_record(value)
    return str(record.get("absolute_path") or (REPO_ROOT / record["path"]))


def bool_from_body(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def int_from_body(value: Any, default: int) -> int:
    if value in {None, ""}:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise DemoServerError(HTTPStatus.BAD_REQUEST, f"Expected integer value, got {value!r}.") from exc


def selected_runtime_warning(llm_provider_config_path: str | None) -> str | None:
    live_env = missing_live_env(llm_provider_config_path)
    if not live_env:
        return None
    return f"{live_env}=1 is not set on the demo server process; live provider runs are blocked."


def missing_live_env(llm_provider_config_path: str | Path | None) -> str | None:
    if not llm_provider_config_path:
        return None
    payload = read_flat_config(Path(llm_provider_config_path))
    live_env = str(payload.get("live_test_env") or "")
    if live_env and os.environ.get(live_env) != "1":
        return live_env
    return None


def command_preview(
    *,
    case_path: str | Path,
    output_dir: str | Path,
    run_id: str | None = None,
    llm_provider_config_path: str | Path | None = None,
    auto_codex_handoff: bool = False,
    codex_bin: str = "codex",
    codex_model: str | None = None,
    codex_timeout_seconds: int = 900,
    verification_timeout_seconds: int = 60,
    force_codex_handoff: bool = False,
    dry_run_codex: bool = False,
) -> str:
    parts = ["python", "-m", "lqcd_agent.graph.run_graph", "--case", relative_to_repo(Path(case_path))]
    parts.extend(["--output-dir", relative_to_repo(Path(output_dir))])
    if run_id:
        parts.extend(["--run-id", run_id])
    if llm_provider_config_path:
        parts.extend(["--llm-provider-config", relative_to_repo(Path(llm_provider_config_path))])
    if auto_codex_handoff:
        parts.append("--auto-codex-handoff")
    if codex_bin != "codex":
        parts.extend(["--codex-bin", codex_bin])
    if codex_model:
        parts.extend(["--codex-model", codex_model])
    if codex_timeout_seconds != 900:
        parts.extend(["--codex-timeout-seconds", str(codex_timeout_seconds)])
    if verification_timeout_seconds != 60:
        parts.extend(["--verification-timeout-seconds", str(verification_timeout_seconds)])
    if force_codex_handoff:
        parts.append("--force-codex-handoff")
    if dry_run_codex:
        parts.append("--dry-run-codex")
    command = " ".join(shlex.quote(part) for part in parts)
    if llm_provider_config_path:
        payload = read_flat_config(Path(llm_provider_config_path))
        live_env = str(payload.get("live_test_env") or "")
        if live_env and os.environ.get(live_env) != "1":
            command = f"{live_env}=1 {command}"
    return command


def validate_case_config_request(*, output_root: str | Path, body: dict[str, Any]) -> dict[str, Any]:
    config_path = resolve_case_config_path(
        output_root=output_root,
        config_id=body.get("config_id") or body.get("case_id"),
        config_text=body.get("config_text"),
    )
    return {"config": case_config_preview(config_path)}


def artifact_url(path: str | None, output_root: str | Path | None = None) -> str | None:
    if not path:
        return None
    query = f"path={quote(path, safe='')}"
    if output_root is not None:
        query += f"&output_dir={quote(str(output_root), safe='')}"
    return f"/artifacts?{query}"


def artifact_entries(checklist: dict[str, Any] | None, output_root: str | Path) -> list[dict[str, Any]]:
    if not checklist:
        return []
    paths = checklist.get("artifact_paths", {})
    if not isinstance(paths, dict):
        return []
    entries: list[dict[str, Any]] = []
    for name, raw_path in paths.items():
        if not raw_path:
            continue
        path = Path(str(raw_path))
        entries.append(
            {
                "name": str(name),
                "path": str(path),
                "url": artifact_url(str(path), output_root),
                "exists": path.exists(),
            }
        )
    return entries


def artifact_entries_for_run(
    run_dir: Path,
    graph_state: dict[str, Any],
    checklist: dict[str, Any] | None,
    output_root: str | Path,
) -> list[dict[str, Any]]:
    entries = artifact_entries(checklist, output_root)
    seen = {entry["name"] for entry in entries}
    known_paths = {
        "method_plan": graph_state.get("method_plan_path") or str(run_dir / "method_plan.json"),
        "run_result": graph_state.get("run_result_path") or str(run_dir / "run_result.json"),
        "scientific_review": graph_state.get("scientific_review_report_path") or str(run_dir / "scientific_review_report.json"),
        "decision_log": graph_state.get("decision_log_path") or str(run_dir / "decision_log.json"),
        "memory_update": graph_state.get("memory_update_path") or str(run_dir / "memory_update.json"),
        "final_report": graph_state.get("final_report_path") or str(run_dir / "final_report.md"),
        "approval_packet": str(run_dir / "approval_packet" / APPROVAL_PACKET_FILENAME),
        "human_decision": str(run_dir / "approval_packet" / HUMAN_DECISION_FILENAME),
        "graph_state": str(run_dir / "graph_state.json"),
    }
    for name, raw_path in known_paths.items():
        if name in seen or not raw_path:
            continue
        path = Path(str(raw_path))
        entries.append({"name": name, "path": str(path), "url": artifact_url(str(path), output_root), "exists": path.exists()})
    return entries


def memory_status(run_dir: Path) -> str | None:
    payload = read_json_file(run_dir / "memory_update.json")
    return str(payload.get("memory_status")) if payload and payload.get("memory_status") is not None else None


def route_nodes_from_state(graph_state: dict[str, Any]) -> list[str]:
    nodes: list[str] = []
    for event in graph_state.get("event_log", []):
        if isinstance(event, dict) and event.get("node"):
            nodes.append(str(event["node"]))
    for decision in graph_state.get("route_decisions", []):
        if not isinstance(decision, dict):
            continue
        if decision.get("source"):
            nodes.append(str(decision["source"]))
        route = decision.get("route")
        if route and route != "end":
            nodes.append(str(route))
    if graph_state.get("current_node"):
        nodes.append(str(graph_state["current_node"]))
    unique: list[str] = []
    for node in nodes:
        if node not in unique:
            unique.append(node)
    return unique


def review_warning_codes(run_dir: Path) -> list[str]:
    payload = read_json_file(run_dir / "scientific_review_report.json")
    if not payload or not isinstance(payload.get("warnings"), list):
        return []
    return [str(warning.get("code")) for warning in payload["warnings"] if isinstance(warning, dict)]


def approval_status(run_dir: Path) -> dict[str, Any]:
    packet_path = run_dir / "approval_packet" / APPROVAL_PACKET_FILENAME
    decision_path = run_dir / "approval_packet" / HUMAN_DECISION_FILENAME
    packet = read_json_file(packet_path)
    decision_payload: dict[str, Any] | None = None
    if decision_path.exists():
        try:
            decision_payload = read_flat_human_decision_yaml(decision_path)
        except (json.JSONDecodeError, ValueError):
            decision_payload = {"decision": None, "invalid": True}
    decision = decision_payload.get("decision") if decision_payload else None
    return {
        "required": bool(packet),
        "pending": bool(packet and not decision),
        "packet": packet,
        "decision": decision_payload,
        "packet_path": str(packet_path) if packet_path.exists() else None,
        "decision_path": str(decision_path) if decision_path.exists() else None,
    }


def final_report_summary(final_report: str) -> str:
    lines: list[str] = []
    for raw_line in final_report.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lines.append(line)
        if len(lines) >= 10:
            break
    return "\n".join(lines)


def run_dir_for(output_root: Path, case_id: str, run_id: str) -> Path:
    return output_root / case_id / run_id


def dashboard_payload(*, output_root: str | Path, case_id: str, run_id: str) -> dict[str, Any]:
    output_path = Path(output_root)
    run_dir = run_dir_for(output_path, case_id, run_id)
    graph_state = read_json_file(run_dir / "graph_state.json")
    if graph_state is None:
        raise DemoServerError(HTTPStatus.NOT_FOUND, f"Run not found: {case_id}/{run_id}")

    checklist = read_json_file(run_dir / "demonstration_checklist.json")
    final_report_path = run_dir / "final_report.md"
    final_report = final_report_path.read_text(encoding="utf-8") if final_report_path.exists() else ""
    actual = checklist.get("actual", {}) if checklist else {}
    approval = approval_status(run_dir)

    return {
        "case_id": case_id,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "summary": {
            "status": graph_state.get("status"),
            "current_node": graph_state.get("current_node"),
            "risk_level": graph_state.get("risk_level"),
            "recommended_action": graph_state.get("recommended_action"),
            "human_approval_required": graph_state.get("human_approval_required"),
            "memory_status": actual.get("memory_status") or memory_status(run_dir),
            "checklist_passed": checklist.get("passed") if checklist else None,
            "route_nodes": actual.get("route_nodes") or route_nodes_from_state(graph_state),
            "warning_codes": actual.get("warning_codes") or review_warning_codes(run_dir),
            "approval_packet": actual.get("approval_packet") if actual else (run_dir / "approval_packet" / "approval_packet.json").exists(),
        },
        "events": graph_state.get("event_log", []),
        "route_decisions": graph_state.get("route_decisions", []),
        "approval": approval,
        "graph_state": graph_state,
        "checklist": checklist,
        "final_report": final_report,
        "final_report_summary": final_report_summary(final_report),
        "artifacts": artifact_entries_for_run(run_dir, graph_state, checklist, output_path),
    }


def route_label(route_nodes: list[Any]) -> str:
    return " -> ".join(NODE_LABELS.get(str(node), str(node)) for node in route_nodes)


def final_report_excerpt(final_report: str) -> str:
    lines = []
    for raw_line in final_report.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
        if len(lines) >= 3:
            break
    return " ".join(lines)


def answer_for_run(*, message: str, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    route = route_label(summary.get("route_nodes", []))
    warnings = summary.get("warning_codes") or []
    approval = "需要 Human Approval Gate" if summary.get("human_approval_required") else "不需要 Human Approval Gate"
    excerpt = final_report_excerpt(str(payload.get("final_report", "")))
    warning_text = "、".join(str(warning) for warning in warnings) if warnings else "没有严重 reviewer warning"
    answer_lines = [
        f"我用你选择的 case config 运行了 LangGraph：{payload['case_id']}。",
        f"你的原始问题作为本次 graph run 的 physics_goal 写入：{message}",
        (
            "这次多 agent 运行的结论是："
            f"risk={summary.get('risk_level')}，action={summary.get('recommended_action')}，"
            f"memory={summary.get('memory_status')}，{approval}。"
        ),
        f"路径是：{route}。Reviewer 侧观察到：{warning_text}。",
    ]
    if excerpt:
        answer_lines.append(f"报告摘要：{excerpt}")
    answer_lines.append("我在右侧保留了本次 run 的关键证据和 artifact 链接，默认不把完整 JSON 全部展开。")
    return "\n\n".join(answer_lines)


def write_question_case_config(*, question: str, source_config_path: str | Path, output_root: str | Path) -> tuple[Path, str]:
    source_path = Path(source_config_path)
    source_payload = read_case_config(source_path)
    case_id = str(source_payload.get("case_id", source_path.stem))
    generated_dir = Path(output_root) / "_generated_chat_cases"
    generated_dir.mkdir(parents=True, exist_ok=True)
    case_path = generated_dir / f"{case_id}_{utc_run_prefix()}.yaml"
    lines: list[str] = []
    replaced = False
    for raw_line in source_path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("physics_goal:"):
            lines.append(f"physics_goal: {json.dumps(question)}")
            replaced = True
        else:
            lines.append(raw_line)
    if not replaced:
        lines.append(f"physics_goal: {json.dumps(question)}")
    case_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return case_path, case_id


def run_question_against_config(
    *,
    question: str,
    config_id: str,
    output_root: str | Path,
    run_id_prefix: str | None = None,
    llm_provider_config_path: str | Path | None = None,
) -> dict[str, Any]:
    config = case_config_record(config_id)
    case_config, case_id = write_question_case_config(
        question=question,
        source_config_path=str(config["path"]),
        output_root=output_root,
    )
    prefix = run_id_prefix or utc_run_prefix()
    run_id = f"{prefix}_{case_id}"
    run_mock_graph(
        case_path=str(case_config),
        output_dir=str(output_root),
        run_id=run_id,
        llm_provider_config_path=str(llm_provider_config_path) if llm_provider_config_path else None,
    )
    return dashboard_payload(output_root=output_root, case_id=case_id, run_id=run_id)


def run_status_payload(*, output_root: str | Path, case_id: str, run_id: str) -> dict[str, Any]:
    job_key = (case_id, run_id)
    with RUN_JOBS_LOCK:
        job = dict(RUN_JOBS.get(job_key, {}))
    if job.get("output_root"):
        output_root = str(job["output_root"])
    run_dir = run_dir_for(Path(output_root), case_id, run_id)
    if (run_dir / "graph_state.json").exists():
        payload = dashboard_payload(output_root=output_root, case_id=case_id, run_id=run_id)
        payload["job_status"] = job.get("status", "completed")
        if job.get("error"):
            payload["job_error"] = job["error"]
        if job.get("command_preview"):
            payload["command_preview"] = job["command_preview"]
        if job.get("warnings"):
            payload["warnings"] = job["warnings"]
        return payload
    if job:
        return {
            "case_id": case_id,
            "run_id": run_id,
            "run_dir": str(run_dir),
            "job_status": job.get("status", "running"),
            "summary": {"status": job.get("status", "running"), "route_nodes": []},
            "events": [],
            "route_decisions": [],
            "approval": {"required": False, "pending": False, "packet": None, "decision": None},
            "artifacts": [],
            "final_report": "",
            "final_report_summary": "",
            "job_error": job.get("error"),
            "command_preview": job.get("command_preview"),
            "warnings": job.get("warnings", []),
        }
    raise DemoServerError(HTTPStatus.NOT_FOUND, f"Run not found: {case_id}/{run_id}")


def start_graph_run(
    *,
    output_root: str | Path,
    config_id: str | None = None,
    config_text: str | None = None,
    output_dir: str | Path | None = None,
    run_id: str | None = None,
    run_id_prefix: str | None = None,
    llm_provider_config_path: str | Path | None = None,
    auto_codex_handoff: bool = False,
    codex_bin: str = "codex",
    codex_model: str | None = None,
    codex_timeout_seconds: int = 900,
    verification_timeout_seconds: int = 60,
    force_codex_handoff: bool = False,
    dry_run_codex: bool = False,
) -> dict[str, Any]:
    resolved_output_root = resolve_output_dir(output_dir or output_root)
    config_path = resolve_case_config_path(output_root=resolved_output_root, config_id=config_id, config_text=config_text)
    preview = case_config_preview(config_path)
    case_id = str(preview["case_id"])
    resolved_run_id = str(run_id).strip() if run_id else f"{run_id_prefix or utc_run_prefix()}_{case_id}"
    resolved_provider_config = resolve_runtime_config_path(llm_provider_config_path)
    blocked_live_env = missing_live_env(resolved_provider_config)
    if blocked_live_env:
        raise DemoServerError(
            HTTPStatus.BAD_REQUEST,
            f"{blocked_live_env}=1 is required for the selected live LLM provider. "
            f"Restart the demo server with {blocked_live_env}=1 before running this case.",
        )
    warnings = [warning for warning in [selected_runtime_warning(resolved_provider_config)] if warning]
    command = command_preview(
        case_path=config_path,
        output_dir=resolved_output_root,
        run_id=resolved_run_id,
        llm_provider_config_path=resolved_provider_config,
        auto_codex_handoff=auto_codex_handoff,
        codex_bin=codex_bin,
        codex_model=codex_model,
        codex_timeout_seconds=codex_timeout_seconds,
        verification_timeout_seconds=verification_timeout_seconds,
        force_codex_handoff=force_codex_handoff,
        dry_run_codex=dry_run_codex,
    )
    job_key = (case_id, resolved_run_id)
    with RUN_JOBS_LOCK:
        RUN_JOBS[job_key] = {
            "status": "running",
            "case_id": case_id,
            "run_id": resolved_run_id,
            "config_path": str(config_path),
            "output_root": str(resolved_output_root),
            "llm_provider_config_path": resolved_provider_config,
            "command_preview": command,
            "warnings": warnings,
            "started_at": utc_now(),
        }

    def run_worker() -> None:
        try:
            run_mock_graph(
                case_path=str(config_path),
                output_dir=str(resolved_output_root),
                run_id=resolved_run_id,
                llm_provider_config_path=resolved_provider_config,
                auto_codex_handoff=auto_codex_handoff,
                codex_bin=codex_bin,
                codex_model=codex_model,
                codex_timeout_seconds=codex_timeout_seconds,
                verification_timeout_seconds=verification_timeout_seconds,
                force_codex_handoff=force_codex_handoff,
                dry_run_codex=dry_run_codex,
            )
            with RUN_JOBS_LOCK:
                RUN_JOBS[job_key]["status"] = "completed"
                RUN_JOBS[job_key]["completed_at"] = utc_now()
        except Exception as exc:
            with RUN_JOBS_LOCK:
                RUN_JOBS[job_key]["status"] = "failed"
                RUN_JOBS[job_key]["error"] = str(exc)
                RUN_JOBS[job_key]["completed_at"] = utc_now()

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()
    return run_status_payload(output_root=resolved_output_root, case_id=case_id, run_id=resolved_run_id)


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def write_human_decision_file(
    *,
    path: Path,
    run_id: str,
    case_id: str,
    decision: str,
    conditions: str = "",
    reason: str = "",
    decided_by: str = "",
) -> None:
    allowed = {str(option["decision"]) for option in DECISION_OPTIONS}
    if decision not in allowed:
        raise DemoServerError(HTTPStatus.BAD_REQUEST, f"Unsupported human decision: {decision}")
    payload = {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "decision": decision,
        "conditions": conditions,
        "reason": reason,
        "decided_by": decided_by,
        "decided_at": utc_now(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{key}: {yaml_scalar(value)}" for key, value in payload.items()) + "\n", encoding="utf-8")


def apply_human_decision(
    *,
    output_root: str | Path,
    case_id: str,
    run_id: str,
    decision: str,
    conditions: str = "",
    reason: str = "",
    decided_by: str = "",
) -> dict[str, Any]:
    run_dir = run_dir_for(Path(output_root), case_id, run_id)
    graph_state = read_json_file(run_dir / "graph_state.json")
    if graph_state is None:
        raise DemoServerError(HTTPStatus.NOT_FOUND, f"Run not found: {case_id}/{run_id}")
    packet_path = run_dir / "approval_packet" / APPROVAL_PACKET_FILENAME
    if not packet_path.exists():
        raise DemoServerError(HTTPStatus.BAD_REQUEST, "This run does not have an approval packet.")
    decision_path = run_dir / "approval_packet" / HUMAN_DECISION_FILENAME
    write_human_decision_file(
        path=decision_path,
        run_id=run_id,
        case_id=case_id,
        decision=decision,
        conditions=conditions,
        reason=reason,
        decided_by=decided_by,
    )
    state = dict(graph_state)
    state["output_dir"] = str(run_dir)
    state["human_decision_path"] = str(decision_path)
    state["approval_packet_dir"] = str(packet_path.parent)
    state = human_approval_gate_node(state)
    route = route_after_human_approval_gate(state)
    if route == "memory_report":
        state = memory_report_node(state)
    return dashboard_payload(output_root=output_root, case_id=case_id, run_id=run_id)


def chat_response(
    *,
    message: str,
    config_id: str | None,
    output_root: str | Path,
    run_id_prefix: str | None = None,
    llm_provider_config_path: str | Path | None = None,
) -> dict[str, Any]:
    clean_message = message.strip()
    if not clean_message:
        raise DemoServerError(HTTPStatus.BAD_REQUEST, "Missing chat message.")
    if not config_id:
        raise DemoServerError(HTTPStatus.BAD_REQUEST, "Missing case config.")
    run = run_question_against_config(
        question=clean_message,
        config_id=config_id,
        output_root=output_root,
        run_id_prefix=run_id_prefix,
        llm_provider_config_path=llm_provider_config_path,
    )
    return {
        "role": "assistant",
        "content": answer_for_run(message=clean_message, payload=run),
        "mode": "single",
        "selected_config_id": config_id,
        "run": run,
    }


def resolve_artifact_path(*, output_root: str | Path, requested_path: str) -> Path:
    output_path = Path(output_root).resolve()
    artifact_path = Path(unquote(requested_path)).expanduser()
    if not artifact_path.is_absolute():
        artifact_path = output_path / artifact_path
    resolved = artifact_path.resolve()
    try:
        resolved.relative_to(output_path)
    except ValueError as exc:
        raise DemoServerError(HTTPStatus.FORBIDDEN, "Artifact path is outside the demo output root.") from exc
    if not resolved.exists() or not resolved.is_file():
        raise DemoServerError(HTTPStatus.NOT_FOUND, "Artifact not found.")
    return resolved


class DemoRequestHandler(BaseHTTPRequestHandler):
    server: "DemoHTTPServer"

    def log_message(self, format: str, *args: Any) -> None:
        if self.server.quiet:
            return
        super().log_message(format, *args)

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path in {"/api/cases", "/api/configs"}:
                self.write_json({"configs": case_configs(), "cases": case_configs()})
                return
            if parsed.path == "/api/runtime-configs":
                self.write_json(
                    {
                        "runtime_configs": runtime_configs(),
                        "server": {
                            "default_output_dir": relative_to_repo(resolve_output_dir(self.server.output_root)),
                            "run_live_llm_tests": os.environ.get("RUN_LIVE_LLM_TESTS") == "1",
                        },
                    }
                )
                return
            if parsed.path.startswith("/api/runs/"):
                parts = [part for part in parsed.path.split("/") if part]
                if len(parts) != 4:
                    raise DemoServerError(HTTPStatus.NOT_FOUND, "Expected /api/runs/{case_id}/{run_id}.")
                query = parse_qs(parsed.query)
                output_root = resolve_output_dir(query.get("output_dir", [None])[0] or self.server.output_root)
                self.write_json(run_status_payload(output_root=output_root, case_id=parts[2], run_id=parts[3]))
                return
            if parsed.path == "/artifacts":
                query = parse_qs(parsed.query)
                requested = query.get("path", [None])[0]
                if not requested:
                    raise DemoServerError(HTTPStatus.BAD_REQUEST, "Missing artifact path.")
                output_root = resolve_output_dir(query.get("output_dir", [None])[0] or self.server.output_root)
                self.write_file(resolve_artifact_path(output_root=output_root, requested_path=requested))
                return
            self.write_static(parsed.path)
        except DemoServerError as exc:
            self.write_json({"error": exc.message}, status=exc.status)
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            body = self.read_json_body()
            if parsed.path == "/api/configs/validate":
                self.write_json(validate_case_config_request(output_root=self.server.output_root, body=body))
                return
            if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/human-decision"):
                parts = [part for part in parsed.path.split("/") if part]
                if len(parts) != 5:
                    raise DemoServerError(
                        HTTPStatus.NOT_FOUND,
                        "Expected /api/runs/{case_id}/{run_id}/human-decision.",
                    )
                payload = apply_human_decision(
                    output_root=self.server.output_root,
                    case_id=parts[2],
                    run_id=parts[3],
                    decision=str(body.get("decision") or ""),
                    conditions=str(body.get("conditions") or ""),
                    reason=str(body.get("reason") or ""),
                    decided_by=str(body.get("decided_by") or ""),
                )
                self.write_json(payload)
                return
            if parsed.path == "/api/chat":
                message = str(body.get("message", ""))
                payload = chat_response(
                    message=message,
                    config_id=body.get("config_id") or body.get("case_id"),
                    output_root=self.server.output_root,
                    run_id_prefix=body.get("run_id_prefix"),
                    llm_provider_config_path=body.get("llm_provider_config_path") or self.server.llm_provider_config_path,
                )
                self.write_json(payload, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/runs":
                output_root = resolve_output_dir(body.get("output_dir") or self.server.output_root)
                payload = start_graph_run(
                    config_id=body.get("config_id") or body.get("case_id"),
                    config_text=body.get("config_text"),
                    output_root=output_root,
                    output_dir=str(output_root),
                    run_id=body.get("run_id"),
                    run_id_prefix=body.get("run_id_prefix"),
                    llm_provider_config_path=body.get("llm_provider_config_path") or self.server.llm_provider_config_path,
                    auto_codex_handoff=bool_from_body(body.get("auto_codex_handoff")),
                    codex_bin=str(body.get("codex_bin") or "codex"),
                    codex_model=str(body.get("codex_model")) if body.get("codex_model") else None,
                    codex_timeout_seconds=int_from_body(body.get("codex_timeout_seconds"), 900),
                    verification_timeout_seconds=int_from_body(body.get("verification_timeout_seconds"), 60),
                    force_codex_handoff=bool_from_body(body.get("force_codex_handoff")),
                    dry_run_codex=bool_from_body(body.get("dry_run_codex")),
                )
                self.write_json(payload, status=HTTPStatus.ACCEPTED)
                return
            raise DemoServerError(HTTPStatus.NOT_FOUND, "Unknown endpoint.")
        except DemoServerError as exc:
            self.write_json({"error": exc.message}, status=exc.status)
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise DemoServerError(HTTPStatus.BAD_REQUEST, "Expected a JSON object.")
        return payload

    def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def write_file(self, path: Path) -> None:
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "text/plain"
        if path.suffix == ".md":
            content_type = "text/markdown"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def write_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        path = (STATIC_ROOT / relative).resolve()
        try:
            path.relative_to(STATIC_ROOT.resolve())
        except ValueError as exc:
            raise DemoServerError(HTTPStatus.FORBIDDEN, "Static path is outside the demo UI.") from exc
        if not path.exists() or not path.is_file():
            raise DemoServerError(HTTPStatus.NOT_FOUND, "Static file not found.")
        self.write_file(path)


class DemoHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        output_root: str | Path,
        quiet: bool = False,
        llm_provider_config_path: str | Path | None = None,
    ) -> None:
        super().__init__(server_address, DemoRequestHandler)
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.quiet = quiet
        self.llm_provider_config_path = str(llm_provider_config_path) if llm_provider_config_path else None


def create_server(
    *,
    host: str,
    port: int,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    quiet: bool = False,
    llm_provider_config_path: str | Path | None = None,
) -> DemoHTTPServer:
    return DemoHTTPServer(
        (host, port),
        output_root=output_root,
        quiet=quiet,
        llm_provider_config_path=llm_provider_config_path,
    )


def run_once_smoke(output_root: str | Path) -> dict[str, Any]:
    output_path = Path(output_root)
    payload = run_question_against_config(
        question="Run a smoke test through the local chat demo.",
        config_id="mock_lqcd_goal",
        output_root=output_path,
    )
    return {
        "ok": payload["summary"]["status"] == "success" and bool(payload["final_report"]),
        "case_id": payload["case_id"],
        "run_id": payload["run_id"],
        "run_dir": payload["run_dir"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local LQCD multi-agent console.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument(
        "--llm-provider-config",
        default=None,
        help="Optional provider config path. Omit to use developer/testing deterministic mode.",
    )
    parser.add_argument("--once-smoke", action="store_true", help="Run one clean demo case and exit.")
    args = parser.parse_args()

    if args.once_smoke:
        with tempfile.TemporaryDirectory(prefix="lqcd-agent-demo-smoke-") as tmp_dir:
            result = run_once_smoke(args.output_root or tmp_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    server = create_server(
        host=args.host,
        port=args.port,
        output_root=args.output_root,
        llm_provider_config_path=args.llm_provider_config,
    )
    url = f"http://{args.host}:{server.server_address[1]}"
    print(f"Serving LQCD multi-agent console at {url}")
    print(f"Writing demo artifacts under {Path(args.output_root)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping demo dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
