import os
import subprocess
import sys
from pathlib import Path

from lqcd_agent.llm.openai_client import LiveProviderError
from lqcd_agent.llm.openai_client import OpenAIChatProvider
from lqcd_agent.llm.provider_factory import (
    create_provider,
    dry_run_report,
    load_provider_config,
    load_repo_env,
)


ROOT = Path(__file__).resolve().parents[1]


def test_loads_openai_and_deepseek_configs_without_secrets() -> None:
    openai = load_provider_config(ROOT / "configs/runtime/openai.yaml")
    deepseek = load_provider_config(ROOT / "configs/runtime/deepseek.yaml")

    assert openai.provider == "openai"
    assert openai.api_key_env == "OPENAI_API_KEY"
    assert openai.model_env == "OPENAI_MODEL"
    assert deepseek.provider == "deepseek"
    assert deepseek.api_key_env == "DEEPSEEK_API_KEY"
    assert deepseek.model_env == "DEEPSEEK_MODEL"


def test_dry_run_reports_readiness_without_env_values(monkeypatch) -> None:
    monkeypatch.delenv("RUN_LIVE_LLM_TESTS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    report = dry_run_report(ROOT / "configs/runtime/openai.yaml", env_path=ROOT / ".env.missing")

    assert report["status"] == "success"
    assert report["provider"] == "openai"
    assert report["ready_for_live_call"] is False
    assert report["live_enabled"] is False
    assert report["missing_env_vars"] == ["OPENAI_API_KEY", "OPENAI_MODEL"]
    assert "sk-" not in str(report)


def test_repo_env_loader_does_not_override_exported_values(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=file-value\nOPENAI_MODEL=file-model\nRUN_LIVE_LLM_TESTS=1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "exported-value")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("RUN_LIVE_LLM_TESTS", raising=False)

    loaded = load_repo_env(env_file)

    assert "OPENAI_API_KEY" not in loaded
    assert os.environ["OPENAI_API_KEY"] == "exported-value"
    assert os.environ["OPENAI_MODEL"] == "file-model"
    assert os.environ["RUN_LIVE_LLM_TESTS"] == "1"


def test_live_provider_call_is_blocked_without_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("RUN_LIVE_LLM_TESTS", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    provider = create_provider(load_provider_config(ROOT / "configs/runtime/openai.yaml"))

    try:
        provider.generate(request=object())  # type: ignore[arg-type]
    except LiveProviderError as exc:
        assert exc.code == "live_llm_tests_disabled"
        assert "test-secret" not in str(exc)
    else:
        raise AssertionError("Live provider call was not blocked.")


def test_openai_client_uses_completion_token_limit_for_gpt5_models() -> None:
    provider = OpenAIChatProvider(load_provider_config(ROOT / "configs/runtime/openai.yaml"))

    assert provider._max_tokens_field("gpt-5.4-mini") == "max_completion_tokens"
    assert provider._max_tokens_field("gpt-4.1-mini") == "max_tokens"


def test_env_files_are_ignored_except_example() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert ".env" in gitignore
    assert ".env.*" in gitignore
    assert "!.env.example" in gitignore
    assert "OPENAI_API_KEY=" in example
    assert "DEEPSEEK_API_KEY=" in example
    assert "sk-" not in example


def test_provider_factory_cli_dry_run_does_not_print_secret_names_as_values(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lqcd_agent.llm.provider_factory",
            "--config",
            str(ROOT / "configs/runtime/openai.yaml"),
            "--dry-run",
            "--env-file",
            str(ROOT / ".env.missing"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert '"provider": "openai"' in result.stdout
    assert "OPENAI_API_KEY" in result.stdout
    assert "sk-" not in result.stdout
