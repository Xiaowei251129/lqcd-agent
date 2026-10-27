"""OpenAI-compatible live provider client with explicit opt-in guards."""

from __future__ import annotations

import json
from time import perf_counter
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse, ProviderReadiness


from lqcd_agent.llm.openai_client import LiveProviderError

class DeepSeekChatProvider:
    def __init__(self, config: LLMProviderConfig, *, api_key=None) -> None:
        self.config, self._api_key = config, api_key

    def _live_enabled(self) -> bool:
        return os.environ.get(self.config.live_test_env) == "1"

    def _required_env_values(self) -> tuple[str | None, str | None, list[str]]:
        missing: list[str] = []
        api_key = self._api_key or os.environ.get(self.config.api_key_env or "")
        model = os.environ.get(self.config.model_env or "") or self.config.default_model
        if self.config.api_key_env and not api_key:
            missing.append(self.config.api_key_env)
        if self.config.model_env and not model:
            missing.append(self.config.model_env)
        return api_key, model, missing

    def readiness(self) -> ProviderReadiness:
        _api_key, model, missing = self._required_env_values()
        live_enabled = self._live_enabled()
        return ProviderReadiness(
            provider=self.config.provider,
            ready=live_enabled and not missing and bool(self.config.api_base),
            live_enabled=live_enabled,
            missing_env_vars=missing,
            model_configured=bool(model),
            api_base_configured=bool(self.config.api_base),
        )

    def _ensure_live_ready(self) -> tuple[str, str]:
        if not self._live_enabled():
            raise LiveProviderError(
                "live_llm_tests_disabled",
                f"Live provider calls require {self.config.live_test_env}=1.",
            )
        api_key, model, missing = self._required_env_values()
        if missing:
            raise LiveProviderError(
                "missing_provider_environment",
                "Required provider environment variables are not set.",
                missing_env_vars=missing,
            )
        if not self.config.api_base:
            raise LiveProviderError("missing_api_base", "Provider api_base is not configured.")
        assert api_key is not None
        assert model is not None
        return api_key, model

    def _max_tokens_field(self, model: str) -> str:
        if model.startswith("gpt-5"):
            return "max_completion_tokens"
        return "max_tokens"

    def generate(self, request: LLMRequest) -> LLMResponse:
        api_key, model = self._ensure_live_ready()
        payload = {
            "model": model,
            "messages": request.messages,
            "temperature": self.config.temperature if request.temperature is None else request.temperature,
            self._max_tokens_field(model): self.config.max_tokens if request.max_tokens is None else request.max_tokens,
        }
        if request.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif request.response_format == "json_schema":
            if request.json_schema is None:
                raise LiveProviderError("missing_json_schema", "JSON schema response format requires a schema.")
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": request.json_schema,
            }

        url = self.config.api_base.rstrip("/") + "/chat/completions"
        http_request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = perf_counter()
        request_id = None
        try:
            with urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                request_id = response.headers.get("x-request-id")
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LiveProviderError("provider_http_error", f"Provider request failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise LiveProviderError("provider_network_error", "Provider request failed before a response was returned.") from exc
        except json.JSONDecodeError as exc:
            raise LiveProviderError("provider_response_not_json", "Provider response was not valid JSON.") from exc

        choices = body.get("choices", [])
        if not choices:
            raise LiveProviderError("provider_response_missing_choice", "Provider response did not include choices.")
        first_choice = choices[0]
        if first_choice.get("finish_reason") == "length":
            raise LiveProviderError(
                "finish_reason_length",
                "Provider stopped because the completion token limit was reached before a complete JSON artifact.",
            )
        message = first_choice.get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise LiveProviderError("provider_response_missing_content", "Provider response content was missing.")

        return LLMResponse(
            provider=self.config.provider,
            model=str(body.get("model") or model),
            content=content,
            finish_reason=first_choice.get("finish_reason"),
            elapsed_seconds=perf_counter()-started, request_id=request_id, response_id=body.get("id"),
            usage=body.get("usage", {}) if isinstance(body.get("usage"), dict) else {},
        )
