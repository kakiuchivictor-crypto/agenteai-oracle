"""Testes da camada de configuracao (app.core.config)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import EmbeddingProvider, LLMProvider, Settings


def test_settings_loads_defaults_for_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    settings = Settings(_env_file=None)
    assert settings.llm_provider == LLMProvider.OLLAMA
    assert settings.embedding_provider == EmbeddingProvider.SENTENCE_TRANSFORMERS


def test_settings_requires_anthropic_key_when_selected() -> None:
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None, llm_provider=LLMProvider.ANTHROPIC, anthropic_api_key="")


def test_settings_requires_openai_key_when_selected() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(_env_file=None, llm_provider=LLMProvider.OPENAI, openai_api_key="")


def test_settings_requires_gemini_key_when_selected() -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        Settings(_env_file=None, llm_provider=LLMProvider.GEMINI, gemini_api_key="")


def test_settings_rejects_default_secrets_outside_development() -> None:
    with pytest.raises(ValidationError, match="APP_SECRET_KEY"):
        Settings(_env_file=None, app_env="production", app_secret_key="changeme")


def test_cors_origins_list_parses_csv() -> None:
    settings = Settings(_env_file=None, cors_origins="http://a.com, http://b.com")
    assert settings.cors_origins_list == ["http://a.com", "http://b.com"]


def test_allowed_extensions_list_lowercases_and_splits() -> None:
    settings = Settings(_env_file=None, allowed_extensions=".PDF,.Docx")
    assert settings.allowed_extensions_list == [".pdf", ".docx"]
