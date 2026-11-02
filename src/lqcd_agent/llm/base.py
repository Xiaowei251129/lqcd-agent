"""Shared provider interfaces for LLM integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str
    default_model: str | None = None
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class LLMRequest:
    messages: list[dict[str, str]]
    json_schema: dict[str, Any] | None = None
    context_sources: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    response_id: str | None = None


class LLMProvider(Protocol):
    config: LLMProviderConfig

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for a bounded request."""
