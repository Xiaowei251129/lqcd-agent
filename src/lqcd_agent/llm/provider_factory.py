"""Provider factory and dry-run CLI for Phase 10 LLM configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from lqcd_agent.llm.base import LLMProvider, LLMProviderConfig
from lqcd_agent.llm.deepseek_client import DeepSeekChatProvider
from lqcd_agent.llm.mock_provider import MockLLMProvider
from lqcd_agent.llm.openai_client import OpenAIChatProvider


def _coerce_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped in {"true", "True"}:
        return True
    if stripped in {"false", "False"}:
        return False
    if stripped in {"null", "None", "~"}:
        return None
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        return stripped[1:-1]
    try:
        if "." in stripped:
            return float(stripped)
        return int(stripped)
    except ValueError:
        return stripped


def load_flat_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    payload: dict[str, Any] = {}
    current_list_key: str | None = None
    for line_number, raw_line in enumerate(config_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("- ") and current_list_key:
            payload.setdefault(current_list_key, [])
            payload[current_list_key].append(_coerce_scalar(line[2:].strip()))
            continue
        current_list_key = None
        if ":" not in line:
            raise ValueError(f"{config_path}:{line_number} is not a flat key/value YAML line.")
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"{config_path}:{line_number} has an empty key.")
        value = value.strip()
        if value:
            payload[key] = _coerce_scalar(value)
        else:
            payload[key] = []
            current_list_key = key
    return payload


def config_from_dict(payload: dict[str, Any]) -> LLMProviderConfig:
    return LLMProviderConfig(
        schema_version=str(payload.get("schema_version", "0.1")),
        provider=str(payload.get("provider", "mock")),
        api_base=str(payload["api_base"]) if payload.get("api_base") is not None else None,
        api_key_env=str(payload["api_key_env"]) if payload.get("api_key_env") is not None else None,
        model_env=str(payload["model_env"]) if payload.get("model_env") is not None else None,
        default_model=str(payload["default_model"]) if payload.get("default_model") is not None else None,
        timeout_seconds=float(payload.get("timeout_seconds", 30)),
        max_tokens=int(payload.get("max_tokens", 1000)),
        temperature=float(payload.get("temperature", 0)),
        live_test_env=str(payload.get("live_test_env", "RUN_LIVE_LLM_TESTS")),
        dry_run_only=bool(payload.get("dry_run_only", False)),
        raw=payload,
    )


def load_provider_config(path: str | Path) -> LLMProviderConfig:
    return config_from_dict(load_flat_yaml(path))


def load_repo_env(env_path: str | Path = ".env") -> list[str]:
    path = Path(env_path)
    loaded: list[str] = []
    if not path.exists():
        return loaded
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = str(_coerce_scalar(value))
        loaded.append(key)
    return loaded


def create_provider(config: LLMProviderConfig) -> LLMProvider:
    provider = config.provider.lower()
    if provider == "mock":
        return MockLLMProvider(config)
    if provider == "openai":
        return OpenAIChatProvider(config)
    if provider == "deepseek":
        return DeepSeekChatProvider(config)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")


def create_provider_from_config_path(
    config_path: str | Path,
    *,
    env_path: str | Path = ".env",
) -> LLMProvider:
    load_repo_env(env_path)
    return create_provider(load_provider_config(config_path))


def dry_run_report(config_path: str | Path, *, env_path: str | Path = ".env") -> dict[str, Any]:
    load_repo_env(env_path)
    config = load_provider_config(config_path)
    provider = create_provider(config)
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
    parser.add_argument("--config", required=True, help="Path to a flat runtime YAML provider config.")
    parser.add_argument("--dry-run", action="store_true", help="Load config and environment metadata only.")
    parser.add_argument("--env-file", default=".env", help="Optional repo-local env file to load without overriding exports.")
    args = parser.parse_args()

    if not args.dry_run:
        parser.error("Only --dry-run is supported by this Phase 10 CLI.")

    print(json.dumps(dry_run_report(args.config, env_path=args.env_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
