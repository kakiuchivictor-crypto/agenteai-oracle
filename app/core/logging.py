"""Logging estruturado com identificador de correlacao por requisicao.

Nunca registrar chaves, senhas, tokens, documentos completos ou dados
pessoais desnecessarios (secao 32 do prompt mestre). O processador
`_redact_sensitive_keys` remove valores de chaves sensiveis antes de
qualquer log ser emitido.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

from app.core.config import get_settings

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

_SENSITIVE_KEYS = {
    "password",
    "senha",
    "api_key",
    "apikey",
    "token",
    "secret",
    "authorization",
    "jwt",
    "anthropic_api_key",
    "openai_api_key",
}


def new_correlation_id() -> str:
    """Gera e armazena um novo identificador de correlacao para a requisicao atual."""
    correlation_id = uuid.uuid4().hex
    _correlation_id.set(correlation_id)
    return correlation_id


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    _correlation_id.set(correlation_id)


def _bind_correlation_id(_logger, _method_name, event_dict: dict) -> dict:
    correlation_id = _correlation_id.get()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def _redact_sensitive_keys(_logger, _method_name, event_dict: dict) -> dict:
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***redacted***"
    return event_dict


def configure_logging() -> None:
    """Configura o logging estruturado global da aplicacao (chamar uma vez, no boot)."""
    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _bind_correlation_id,
            _redact_sensitive_keys,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
