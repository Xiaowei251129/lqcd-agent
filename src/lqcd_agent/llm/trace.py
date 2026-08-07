"""Run-level audit traces for provider-backed LLM calls."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lqcd_agent.llm.base import LLMProvider, LLMRequest, LLMResponse


TRACE_SCHEMA_VERSION = "0.1"
TRACE_DIR_NAME = "llm_calls"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_payload(request: LLMRequest) -> dict[str, Any]:
    return {
        "messages": [dict(message) for message in request.messages],
        "response_format": request.response_format,
        "json_schema": request.json_schema,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }


def _response_payload(response: LLMResponse | None) -> dict[str, Any] | None:
    if response is None:
        return None
    return asdict(response)


def _provider_payload(provider: LLMProvider, response: LLMResponse | None) -> dict[str, Any]:
    config = provider.config
    return {
        "provider": config.provider,
        "api_base": config.api_base,
        "model": response.model if response is not None else None,
        "model_env": config.model_env,
        "default_model": config.default_model,
        "live_test_env": config.live_test_env,
        "dry_run_only": config.dry_run_only,
    }


def _error_payload(error: Any | None) -> list[dict[str, Any]]:
    if error is None:
        return []
    if isinstance(error, dict):
        errors = error.get("errors")
        if isinstance(errors, list):
            return [dict(item) for item in errors if isinstance(item, dict)]
        return [dict(error)]
    return [{"code": getattr(error, "code", "provider_call_failed"), "message": str(error)}]


def write_llm_call_trace(
    *,
    output_dir: str | Path,
    agent: str,
    provider: LLMProvider,
    request: LLMRequest,
    response: LLMResponse | None = None,
    parsed_payload_path: str | Path | None = None,
    status: str,
    error: Any | None = None,
) -> str:
    trace_dir = Path(output_dir) / TRACE_DIR_NAME
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{agent}.json"
    payload = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "agent": agent,
        "created_at": utc_now(),
        "status": status,
        "provider": _provider_payload(provider, response),
        "request": _request_payload(request),
        "response": _response_payload(response),
        "parsed_payload_path": str(parsed_payload_path) if parsed_payload_path else None,
        "errors": _error_payload(error),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)
