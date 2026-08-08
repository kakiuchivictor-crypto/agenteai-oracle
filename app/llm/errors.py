"""Traducao de erros de baixo nivel do provedor de LLM em excecoes de dominio
(secao 41: "erro de provedor" deve ser uma mensagem clara, nunca um traceback).

A checagem por TIPO de excecao vem primeiro porque mensagens de erro de
socket sao localizadas pelo sistema operacional (ex: no Windows, em
portugues, "recusou ativamente" em vez de "connection refused") — depender
apenas de correspondencia de texto em ingles falha nesses casos.
"""

from __future__ import annotations

import httpx

from app.core.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
    RequestTimeoutError,
)

_CONNECTION_KEYWORDS = ("connection", "refused", "unreachable", "econnrefused")
_TIMEOUT_KEYWORDS = ("timeout", "timed out")
_AUTH_KEYWORDS = ("api key", "unauthorized", "401", "authentication")
# Cobre o formato usado pelo Gemini ("429 ... quota ... ResourceExhausted")
# e por outros provedores compativeis com a convencao HTTP padrao de rate
# limit. Verificado antes das checagens genericas: sem isso, o texto CRU do
# erro do provedor (nomes de metrica interna, quota_id, JSON de violacao)
# vazava direto para a resposta do chat, como se o agente tivesse "dito"
# aquilo — confirmado ao vivo com Gemini free tier.
_RATE_LIMIT_KEYWORDS = ("429", "quota", "resource exhausted", "resourceexhausted", "rate limit")

_CONNECTION_ERROR_TYPES = (httpx.ConnectError, httpx.NetworkError, ConnectionError)
_TIMEOUT_ERROR_TYPES = (httpx.TimeoutException, TimeoutError)


def translate_llm_error(exc: Exception) -> Exception:
    if isinstance(exc, _TIMEOUT_ERROR_TYPES):
        return RequestTimeoutError("O provedor de linguagem demorou demais para responder.")
    if isinstance(exc, _CONNECTION_ERROR_TYPES):
        return ProviderUnavailableError(
            "Nao foi possivel conectar ao provedor de linguagem configurado. "
            "Verifique LLM_PROVIDER e as credenciais/URL no .env."
        )

    message = str(exc).lower()
    if any(keyword in message for keyword in _RATE_LIMIT_KEYWORDS):
        return RateLimitExceededError(
            "O provedor de IA está recebendo muitas solicitações no momento. Aguarde alguns "
            "instantes e tente novamente."
        )
    if any(keyword in message for keyword in _TIMEOUT_KEYWORDS):
        return RequestTimeoutError("O provedor de linguagem demorou demais para responder.")
    if any(keyword in message for keyword in _CONNECTION_KEYWORDS):
        return ProviderUnavailableError(
            "Nao foi possivel conectar ao provedor de linguagem configurado. "
            "Verifique LLM_PROVIDER e as credenciais/URL no .env."
        )
    if any(keyword in message for keyword in _AUTH_KEYWORDS):
        return ProviderUnavailableError(
            "Falha de autenticacao com o provedor de linguagem. Verifique a chave de API."
        )
    return ProviderUnavailableError(f"Falha ao gerar resposta com o provedor de linguagem: {exc}")
