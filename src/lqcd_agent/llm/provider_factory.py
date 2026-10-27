"""Provider factory and dry-run CLI for Phase 10 LLM configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from lqcd_agent.configuration import read_config
from lqcd_agent.llm.base import LLMProvider, LLMProviderConfig
from lqcd_agent.llm.deepseek_client import DeepSeekChatProvider
from lqcd_agent.llm.mock_provider import MockLLMProvider
from lqcd_agent.llm.openai_client import OpenAIResponsesProvider


def config_from_dict(payload: dict[str, Any]) -> LLMProviderConfig:
    max_tokens = payload.get("max_tokens", payload.get("max_completion_tokens", 1000))
    return LLMProviderConfig(
        schema_version=str(payload.get("schema_version", "0.1")),
        provider=str(payload.get("provider", "mock")),
        api_base=str(payload["api_base"]) if payload.get("api_base") is not None else None,
        api_key_env=str(payload["api_key_env"]) if payload.get("api_key_env") is not None else None,
        model_env=str(payload["model_env"]) if payload.get("model_env") is not None else None,
        default_model=str(payload["default_model"]) if payload.get("default_model") is not None else None,
        timeout_seconds=float(payload.get("timeout_seconds", 30)),
        max_tokens=int(max_tokens),
        temperature=float(payload.get("temperature", 0)),
        live_test_env=str(payload.get("live_test_env", "RUN_LIVE_LLM_TESTS")),
        dry_run_only=bool(payload.get("dry_run_only", False)),
        raw=payload,
    )


def load_provider_config(path: str | Path) -> LLMProviderConfig:
    return config_from_dict(read_config(path))


def create_provider(config: LLMProviderConfig) -> LLMProvider:
    provider = config.provider.lower()
    if provider == "mock":
        return MockLLMProvider(config)
    if provider == "openai":
        return OpenAIResponsesProvider(config)
    if provider == "deepseek":
        return DeepSeekChatProvider(config)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")


def create_provider_from_config_path(
    config_path: str | Path,
    *,
    env_path: str | Path = ".env",
) -> LLMProvider:
    from dataclasses import replace
    from lqcd_agent.settings import read_env
    config = load_provider_config(config_path)
    if config.provider.lower() == 'mock':
        return create_provider(config)
    values = read_env(env_path)
    prefix = 'OPENAI' if config.provider.lower() == 'openai' else 'DEEPSEEK'
    key_name = config.api_key_env or prefix + '_API_KEY'
    model_name = config.model_env or prefix + '_MODEL'
    key = values.get(key_name) or os.environ.get(key_name)
    model = values.get(model_name) or os.environ.get(model_name) or config.default_model
    private_config = replace(config, default_model=model, model_env=None)
    if config.provider.lower() == 'openai':
        return OpenAIResponsesProvider(private_config, api_key=key)
    if config.provider.lower() == 'deepseek':
        return DeepSeekChatProvider(private_config, api_key=key)
    raise ValueError('Unsupported LLM provider: ' + config.provider)


def dry_run_report(config_path: str | Path, *, env_path: str | Path = ".env") -> dict[str, Any]:
    provider = create_provider_from_config_path(config_path, env_path=env_path)
    readiness = provider.readiness()
    return {
        "schema_version": "0.1",
        "status": "success",
        "provider": readiness.provider,
        "ready_for_live_call": readiness.ready,
        "live_enabled": readiness.live_enabled,
        "missing_env_vars": readiness.missing_env_vars,
        "model_configured": readiness.model_configured,
        "api_base_configured": readiness.api_base_configured,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Load an LLM provider config without printing secrets.")
    parser.add_argument("--config", required=True, help="Path to a JSON/YAML provider config.")
    parser.add_argument("--dry-run", action="store_true", help="Load config and environment metadata only.")
    parser.add_argument("--env-file", default=".env", help="Private application env file; credentials are not exported.")
    args = parser.parse_args()

    if not args.dry_run:
        parser.error("Use --dry-run to inspect configuration without making a request.")

    print(json.dumps(dry_run_report(args.config, env_path=args.env_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
