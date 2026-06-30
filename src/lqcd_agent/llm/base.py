"""Shared provider interfaces for LLM integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMProviderConfig:
    schema_version: str
    provider: str
    api_base: str | None = None
    api_key_env: str | None = None
    model_env: str | None = None
    default_model: str | None = None
    timeout_seconds: float = 30.0
    max_tokens: int = 1000
    temperature: float = 0.0
    live_test_env: str = "RUN_LIVE_LLM_TESTS"
    dry_run_only: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMRequest:
    messages: list[dict[str, str]]
    response_format: str = "json_object"
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: str
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderReadiness:
    provider: str
    ready: bool
    live_enabled: bool
    missing_env_vars: list[str]
    model_configured: bool
    api_base_configured: bool


class LLMProvider(Protocol):
    config: LLMProviderConfig

    def readiness(self) -> ProviderReadiness:
        """Return non-secret provider readiness metadata."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for a bounded request."""
