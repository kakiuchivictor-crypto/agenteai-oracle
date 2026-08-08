from __future__ import annotations

import httpx

from app.core.exceptions import ProviderUnavailableError, RateLimitExceededError, RequestTimeoutError
from app.llm.errors import translate_llm_error


def test_translates_httpx_connect_error_by_type() -> None:
    result = translate_llm_error(httpx.ConnectError("boom"))
    assert isinstance(result, ProviderUnavailableError)


def test_translates_localized_windows_connection_refused_message() -> None:
    """Regressao: no Windows, em portugues, a mensagem de erro de socket e
    "recusou ativamente" (nao contem a palavra em ingles "refused"). Sem a
    checagem por tipo de excecao, esse caso escapava da deteccao."""
    exc = httpx.ConnectError(
        "[WinError 10061] Nenhuma conexao pode ser feita porque a maquina de "
        "destino as recusou ativamente"
    )
    result = translate_llm_error(exc)
    assert isinstance(result, ProviderUnavailableError)
    assert "nao foi possivel conectar" in result.message.lower()


def test_translates_plain_connection_error_by_type() -> None:
    result = translate_llm_error(ConnectionError("qualquer coisa"))
    assert isinstance(result, ProviderUnavailableError)


def test_translates_httpx_timeout_by_type() -> None:
    result = translate_llm_error(httpx.TimeoutException("boom"))
    assert isinstance(result, RequestTimeoutError)


def test_translates_timeout_keyword_in_message() -> None:
    result = translate_llm_error(Exception("Request timeout after 30s"))
    assert isinstance(result, RequestTimeoutError)


def test_translates_auth_keyword_in_message() -> None:
    result = translate_llm_error(Exception("401 Unauthorized: invalid api key"))
    assert isinstance(result, ProviderUnavailableError)
    assert "autenticacao" in result.message.lower()


def test_falls_back_to_generic_provider_error() -> None:
    result = translate_llm_error(Exception("algo inesperado aconteceu"))
    assert isinstance(result, ProviderUnavailableError)


def test_translates_gemini_quota_error_to_clean_rate_limit_message() -> None:
    """Regressao: o texto CRU do erro 429 do Gemini (nomes de metrica
    interna, quota_id, JSON de violacao) vazava direto para a resposta do
    chat, como se o agente tivesse "dito" aquilo — confirmado ao vivo."""
    raw = (
        "429 You exceeded your current quota, please check your plan and billing details. "
        "* Quota exceeded for metric: generativelanguage.googleapis.com/"
        "generate_content_free_tier_requests, limit: 15, model: gemini-3.5-flash-lite"
    )
    result = translate_llm_error(Exception(raw))
    assert isinstance(result, RateLimitExceededError)
    assert "generativelanguage.googleapis.com" not in result.message
    assert "quota_metric" not in result.message
    assert "aguarde" in result.message.lower()


def test_translates_generic_rate_limit_keyword() -> None:
    result = translate_llm_error(Exception("Error: rate limit exceeded, slow down"))
    assert isinstance(result, RateLimitExceededError)
