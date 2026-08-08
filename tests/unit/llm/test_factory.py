"""Testa a troca de provedor de LLM sem alterar a logica central (secao 3)."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.llm.factory import build_chat_model


def test_builds_gemini_chat_model_when_configured() -> None:
    settings = Settings(
        _env_file=None, llm_provider="gemini", gemini_api_key="fake-key",
        llm_model="gemini-flash-lite-latest",
    )
    model = build_chat_model(settings)
    assert isinstance(model, ChatGoogleGenerativeAI)


def test_gemini_model_applies_max_tokens_and_timeout() -> None:
    """Regressao: `gemini-flash-lite-latest` e um modelo "thinking" — tokens de
    raciocinio interno (nao visiveis na resposta) sao descontados do MESMO
    orcamento de `max_output_tokens`. Confirmado ao vivo: um LLM_MAX_TOKENS
    baixo demais (500) cortava a resposta visivel no meio da frase porque
    ate 221 tokens iam para "thoughts". `thinking_budget=0` para desligar
    isso quebra com erro 400 nesse modelo (exige orcamento minimo > 0), entao
    a mitigacao e garantir um LLM_MAX_TOKENS alto o suficiente."""
    settings = Settings(
        _env_file=None, llm_provider="gemini", gemini_api_key="fake-key",
        llm_model="gemini-flash-lite-latest", llm_max_tokens=123, llm_timeout_seconds=45,
    )
    model = build_chat_model(settings)
    assert model.max_output_tokens == 123
    assert model.timeout == 45


def test_builds_ollama_chat_model_when_configured() -> None:
    settings = Settings(_env_file=None, llm_provider="ollama", llm_model="llama3.1")
    model = build_chat_model(settings)
    assert isinstance(model, ChatOllama)


def test_ollama_model_actually_applies_max_tokens_and_keep_alive() -> None:
    """Regressao: `ChatOllama` nao possui campos `timeout`/`max_tokens` — o
    pydantic aceita esses nomes silenciosamente (extra ignorado) sem
    nenhum efeito. O nome correto para limitar tokens e `num_predict`; o
    timeout real vai em `client_kwargs`. Sem este teste, um LLM_MAX_TOKENS
    configurado no .env pareceria funcionar mas nunca limitaria nada."""
    settings = Settings(
        _env_file=None, llm_provider="ollama", llm_model="llama3.1",
        llm_max_tokens=123, llm_timeout_seconds=45, ollama_keep_alive="15m",
    )
    model = build_chat_model(settings)
    assert model.num_predict == 123
    assert model.keep_alive == "15m"
    assert model.client_kwargs == {"timeout": 45}


def test_builds_anthropic_chat_model_when_configured() -> None:
    settings = Settings(
        _env_file=None, llm_provider="anthropic", anthropic_api_key="sk-fake-key",
        llm_model="claude-sonnet-5",
    )
    model = build_chat_model(settings)
    assert isinstance(model, ChatAnthropic)


def test_builds_openai_chat_model_when_configured() -> None:
    settings = Settings(
        _env_file=None, llm_provider="openai", openai_api_key="sk-fake-key",
        llm_model="gpt-4o-mini",
    )
    model = build_chat_model(settings)
    assert isinstance(model, ChatOpenAI)
