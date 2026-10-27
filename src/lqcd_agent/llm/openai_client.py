"""OpenAI Responses provider with explicit activation and secret-safe errors."""
from __future__ import annotations
import os
from typing import Any
from lqcd_agent.llm.base import LLMProviderConfig, LLMRequest, LLMResponse, ProviderReadiness


class LiveProviderError(RuntimeError):
    def __init__(self, code, message, *, missing_env_vars=None):
        super().__init__(message)
        self.code = code
        self.missing_env_vars = missing_env_vars or []

    def as_error(self):
        return {"code": self.code, "message": str(self), "missing_env_vars": self.missing_env_vars}


class OpenAIResponsesProvider:
    def __init__(self, config: LLMProviderConfig, *, api_key=None, enabled=False, client=None):
        self.config, self._api_key, self._enabled, self._client = config, api_key, enabled, client

    def _credentials(self):
        key = self._api_key or os.environ.get(self.config.api_key_env or "")
        model = os.environ.get(self.config.model_env or "") or self.config.default_model
        return key, model

    def readiness(self):
        key, model = self._credentials()
        missing = [name for name, value in [(self.config.api_key_env, key), (self.config.model_env, model)] if name and not value]
        active = self._enabled or os.environ.get(self.config.live_test_env) == "1"
        return ProviderReadiness(self.config.provider, bool(active and key and model and self.config.api_base),
                                 active, missing, bool(model), bool(self.config.api_base))

    def generate(self, request: LLMRequest):
        if not self.readiness().ready:
            raise LiveProviderError("provider_not_ready", "OpenAI provider is disabled or missing application configuration.")
        key, model = self._credentials()
        options = {"model": model, "input": request.messages,
                   "max_output_tokens": request.max_tokens if request.max_tokens is not None else self.config.max_tokens,
                   "store": False}
        if request.response_format == "json_schema":
            if request.json_schema is None:
                raise LiveProviderError("missing_json_schema", "JSON schema output requires a schema.")
            schema = dict(request.json_schema)
            if "schema" not in schema:
                schema = {"name": "agent_output", "schema": schema, "strict": True}
            options["text"] = {"format": {"type": "json_schema", **schema}}
        elif request.response_format == "json_object":
            options["text"] = {"format": {"type": "json_object"}}
        elif request.response_format != "text":
            raise LiveProviderError("unsupported_response_format", "Unsupported OpenAI output format.")
        if not model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")):
            options["temperature"] = request.temperature if request.temperature is not None else self.config.temperature
        try:
            from openai import OpenAI, APIError
            client = self._client or OpenAI(api_key=key, base_url=self.config.api_base,
                timeout=self.config.timeout_seconds, max_retries=0)
            try:
                response = client.responses.create(**options)
            finally:
                if self._client is None:
                    client.close()
        except APIError as error:
            status = getattr(error, "status_code", None)
            raise LiveProviderError("provider_api_error", f"OpenAI request failed (HTTP {status or 'unavailable'}).") from None
        if response.status != "completed":
            raise LiveProviderError("response_incomplete", "OpenAI did not return a completed response.")
        content = response.output_text
        if not isinstance(content, str) or not content:
            raise LiveProviderError("response_missing_text", "OpenAI returned no usable text or declined the request.")
        usage = response.usage.model_dump() if response.usage else {}
        return LLMResponse(provider="openai", model=response.model, content=content, finish_reason="stop", usage=usage)
