"""Standard-library HTTP server for the local scientific chat demo."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import tempfile
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
from lqcd_agent.graph.run_graph import run_mock_graph


STATIC_ROOT = Path(__file__).resolve().parent / "static"
DEFAULT_OUTPUT_ROOT = Path("/private/tmp/lqcd-agent-demo-ui")
CASE_CONFIGS_ROOT = REPO_ROOT / "configs" / "cases"
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


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def case_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for path in sorted(CASE_CONFIGS_ROOT.glob("*.yaml")):
        payload = read_case_config(path)
        case_id = str(payload.get("case_id", path.stem))
        configs.append(
            {
                "config_id": path.stem,
                "case_id": case_id,
                "path": str(path),
                "label": f"{case_id} ({path.name})",
                "physics_goal": payload.get("physics_goal"),
                "source_kind": payload.get("source_kind"),
            }
        )
    return configs


def case_config_record(config_id: str) -> dict[str, Any]:
    for config in case_configs():
        if config["config_id"] == config_id or config["case_id"] == config_id:
            return config
    raise DemoServerError(HTTPStatus.NOT_FOUND, f"Unknown case config: {config_id}")


def artifact_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/artifacts?path={quote(path, safe='')}"


def artifact_entries(checklist: dict[str, Any] | None) -> list[dict[str, Any]]:
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
                "url": artifact_url(str(path)),
                "exists": path.exists(),
            }
        )
    return entries


def artifact_entries_for_run(run_dir: Path, graph_state: dict[str, Any], checklist: dict[str, Any] | None) -> list[dict[str, Any]]:
    entries = artifact_entries(checklist)
    seen = {entry["name"] for entry in entries}
    known_paths = {
        "method_plan": graph_state.get("method_plan_path") or str(run_dir / "method_plan.json"),
        "run_result": graph_state.get("run_result_path") or str(run_dir / "run_result.json"),
        "scientific_review": graph_state.get("scientific_review_report_path") or str(run_dir / "scientific_review_report.json"),
        "decision_log": graph_state.get("decision_log_path") or str(run_dir / "decision_log.json"),
        "memory_update": graph_state.get("memory_update_path") or str(run_dir / "memory_update.json"),
        "final_report": graph_state.get("final_report_path") or str(run_dir / "final_report.md"),
        "graph_state": str(run_dir / "graph_state.json"),
    }
    for name, raw_path in known_paths.items():
        if name in seen or not raw_path:
            continue
        path = Path(str(raw_path))
        entries.append({"name": name, "path": str(path), "url": artifact_url(str(path)), "exists": path.exists()})
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
        "graph_state": graph_state,
        "checklist": checklist,
        "final_report": final_report,
        "artifacts": artifact_entries_for_run(run_dir, graph_state, checklist),
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
            if parsed.path.startswith("/api/runs/"):
                parts = [part for part in parsed.path.split("/") if part]
                if len(parts) != 4:
                    raise DemoServerError(HTTPStatus.NOT_FOUND, "Expected /api/runs/{case_id}/{run_id}.")
                self.write_json(
                    dashboard_payload(output_root=self.server.output_root, case_id=parts[2], run_id=parts[3])
                )
                return
            if parsed.path == "/artifacts":
                query = parse_qs(parsed.query)
                requested = query.get("path", [None])[0]
                if not requested:
                    raise DemoServerError(HTTPStatus.BAD_REQUEST, "Missing artifact path.")
                self.write_file(resolve_artifact_path(output_root=self.server.output_root, requested_path=requested))
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
                config_id = str(body.get("config_id") or body.get("case_id") or "")
                if not config_id:
                    raise DemoServerError(HTTPStatus.BAD_REQUEST, "Missing config_id.")
                payload = run_question_against_config(
                    question=str(body.get("message") or "Run selected case config."),
                    config_id=config_id,
                    output_root=self.server.output_root,
                    run_id_prefix=body.get("run_id_prefix"),
                    llm_provider_config_path=body.get("llm_provider_config_path") or self.server.llm_provider_config_path,
                )
                self.write_json(payload, status=HTTPStatus.CREATED)
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
    parser = argparse.ArgumentParser(description="Run the local Phase 10C scientific chat demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument(
        "--llm-provider-config",
        default=None,
        help="Optional provider config path. Omit to use deterministic local agents.",
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
    print(f"Serving Phase 10C chat demo at {url}")
    print(f"Writing demo artifacts under {Path(args.output_root)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping demo dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
