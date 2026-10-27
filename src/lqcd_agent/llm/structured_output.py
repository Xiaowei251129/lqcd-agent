"""Helpers for validating structured JSON provider output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def structured_error_artifact(
    *,
    producer: str,
    summary: str,
    code: str,
    message: str,
    run_id: str = "provider_validation",
    case_id: str = "provider_validation",
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "case_id": case_id,
        "created_at": _utc_now(),
        "producer": producer,
        "status": "failed",
        "summary": summary,
        "warnings": [],
        "errors": [{"code": code, "message": message}],
    }


def parse_json_object(
    content: str,
    *,
    producer: str = "llm_provider",
    run_id: str = "provider_validation",
    case_id: str = "provider_validation",
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        return None, structured_error_artifact(
            producer=producer,
            run_id=run_id,
            case_id=case_id,
            summary="Provider output was not valid JSON.",
            code="invalid_json",
            message=str(exc),
        )

    if not isinstance(payload, dict):
        return None, structured_error_artifact(
            producer=producer,
            run_id=run_id,
            case_id=case_id,
            summary="Provider output JSON was not an object.",
            code="json_not_object",
            message="Structured provider output must be a JSON object.",
        )
    return payload, None


def validation_error_artifact(
    *,
    producer: str,
    run_id: str,
    case_id: str,
    errors: list[str],
) -> dict[str, Any]:
    return structured_error_artifact(
        producer=producer,
        run_id=run_id,
        case_id=case_id,
        summary="Provider output failed structured validation.",
        code="provider_schema_error",
        message="; ".join(errors),
    )


def provider_exception_artifact(
    *,
    producer: str,
    run_id: str,
    case_id: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    return structured_error_artifact(
        producer=producer,
        run_id=run_id,
        case_id=case_id,
        summary="Provider call failed before a validated artifact was available.",
        code=code,
        message=message,
    )


def write_error_artifact(path: str | Path, artifact: dict[str, Any]) -> str:
    artifact_path = Path(path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(artifact_path)
