"""Fabrica do modelo de chat, selecionado por `LLM_PROVIDER` (secao 3 do prompt mestre).

Nao existe uma interface propria de LLM neste projeto: o `BaseChatModel` do
LangChain ja e a camada de abstracao exigida pelo prompt mestre ("permita
substituir o provedor de LLM sem alterar a logica central"). Todos os nos
do agente (Fase 5) chamam `.invoke(messages)` da mesma forma, independente
do provedor configurado.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import LLMProvider, Settings, get_settings
from app.core.exceptions import MissingConfigurationError


def build_chat_model(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == LLMProvider.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if settings.llm_provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if settings.llm_provider == LLMProvider.GEMINI:
        from langchain_google_genai import ChatGoogleGenerativeAI

        # Modelos Gemini "thinking" (2.5+) gastam tokens de raciocinio interno
        # (nao visiveis na resposta) do MESMO orcamento de `max_output_tokens`
        # — `thinking_budget=0` tentaria desligar isso, mas modelos mais
        # novos (ex.: gemini-3.6-flash, por tras do alias "gemini-flash-
        # latest") rejeitam esse valor com erro 400 (exigem orcamento minimo
        # maior que zero). Por isso deixamos o orcamento de pensamento no
        # padrao dinamico do modelo e garantimos espaco suficiente em
        # `max_output_tokens` (ver LLM_MAX_TOKENS no .env) para que a
        # resposta visivel nao seja cortada apos o raciocinio.
        # max_retries: o padrao da lib e 6 (com backoff exponencial) — bom
        # para falha de rede pontual, pessimo para cota por minuto esgotada
        # (ver comentario de `llm_max_retries` em app/core/config.py).
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if settings.llm_provider == LLMProvider.OLLAMA:
        from langchain_ollama import ChatOllama

        # `ChatOllama` nao possui um campo `timeout`/`max_tokens` — sao
        # aceitos silenciosamente pelo pydantic (extra ignorado) e NUNCA
        # tem efeito algum. O nome correto para limitar o tamanho da
        # resposta e `num_predict`; o timeout real do cliente HTTP
        # subjacente e configurado via `client_kwargs`. `keep_alive`
        # mantem o modelo carregado na memoria entre chamadas — sem isso,
        # o Ollama descarrega o modelo apos alguns minutos ocioso e a
        # proxima chamada paga o custo total de recarregar do disco
        # (dezenas de segundos a mais em CPU).
        return ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
            num_predict=settings.llm_max_tokens,
            keep_alive=settings.ollama_keep_alive,
            client_kwargs={"timeout": settings.llm_timeout_seconds},
        )

    raise MissingConfigurationError(f"LLM_PROVIDER '{settings.llm_provider}' nao e suportado.")


@lru_cache
def get_chat_model() -> BaseChatModel:
    return build_chat_model(get_settings())
