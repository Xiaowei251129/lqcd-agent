"""Small read helpers for memory update artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_memory_update(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("memory_update.json must contain a JSON object.")
    return payload


def memory_category(path: str | Path) -> str:
    payload = read_memory_update(path)
    status = payload.get("memory_status")
    if status not in {"accepted", "pending", "rejected"}:
        raise ValueError("memory_update.json has an invalid memory_status.")
    return str(status)
