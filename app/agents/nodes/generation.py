"""Geracao da resposta, verificacao de fundamentacao e filtragem de citacoes
(secoes 21, 22 e 24 do prompt mestre)."""

from __future__ import annotations

import re
import time

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from sqlmodel import Session

from app.agents.prompts.templates import SYSTEM_PROMPT, build_user_message
from app.agents.state import AgentState
from app.core.config import Settings
from app.core.logging import get_logger
from app.llm.answer_cache import compute_cache_key, get_cached_answer, store_answer
from app.llm.daily_usage import has_daily_capacity, record_daily_call
from app.llm.errors import translate_llm_error
from app.llm.rate_limiter import get_llm_rate_limiter

logger = get_logger(__name__)

_CONFLICT_MARKERS = ("informações divergentes", "informacoes divergentes", "diverg")
_NO_EVIDENCE_MARKERS = ("não encontrei informa", "nao encontrei informa")
_TOKEN_PATTERN = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)
_GROUNDING_OVERLAP_THRESHOLD = 0.3

PROVIDER_BUSY_MESSAGE = (
    "O assistente está recebendo muitas perguntas ao mesmo tempo agora. Aguarde alguns "
    "segundos e tente novamente."
)
DAILY_LIMIT_MESSAGE = (
    "O assistente atingiu o limite de perguntas de hoje. Tente novamente amanhã."
)


def make_generate_answer(chat_model: BaseChatModel, settings: Settings, session: Session):
    def generate_answer(state: AgentState) -> dict:
        normalized_question = state["normalized_question"]
        context_text = state.get("context_text", "")
        cache_key = compute_cache_key(normalized_question, context_text)

        # Cache primeiro: se a MESMA pergunta ja foi respondida sobre o MESMO
        # contexto, reaproveita a resposta sem gastar cota nenhuma — nem
        # chega a passar pelos limitadores abaixo.
        if settings.llm_answer_cache_enabled:
            cached = get_cached_answer(session, cache_key)
            if cached is not None:
                logger.info("agent.answer_cache_hit")
                return {
                    "answer": cached.answer,
                    "model_used": cached.model_used,
                    "latency_ms": 0,
                    "route": cached.route,
                }

        # Checagem PROATIVA antes de sequer tentar chamar o provedor: evita
        # bater na cota real do provedor (ex: Gemini free tier) e evita que
        # os retries automaticos do cliente HTTP piorem o problema (cada
        # retry e mais uma chamada contra a mesma janela ja esgotada). O
        # limitador e cacheado pelo VALOR de `settings.llm_rate_limit_per_minute`
        # (nao um singleton global fixo) — assim producao e testes (que usam
        # limites diferentes) nunca compartilham nem interferem no estado
        # um do outro.
        limiter = get_llm_rate_limiter(settings.llm_rate_limit_per_minute)
        if not limiter.try_acquire():
            logger.warning("agent.llm_rate_limited")
            return {"route": "provider_busy", "error": PROVIDER_BUSY_MESSAGE}

        # Segunda guarda, persistida (sobrevive a reinicios do processo):
        # teto DIARIO de requisicoes, separado do limite por minuto acima.
        if not has_daily_capacity(session, daily_limit=settings.llm_daily_request_limit):
            logger.warning("agent.llm_daily_limit_reached")
            return {"route": "provider_busy", "error": DAILY_LIMIT_MESSAGE}

        history = state.get("chat_history") or []
        history_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history[-6:])
        user_message = build_user_message(
            context_text=context_text,
            chat_history_text=history_text,
            question=normalized_question,
        )

        record_daily_call(session)
        start = time.perf_counter()
        try:
            response = chat_model.invoke(
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_message)]
            )
        except Exception as exc:  # noqa: BLE001
            translated = translate_llm_error(exc)
            logger.warning("agent.generation_failed", error=str(translated))
            return {"route": "provider_error", "error": translated.message}

        latency_ms = int((time.perf_counter() - start) * 1000)
        answer_text = (response.content or "").strip()
        model_name = getattr(chat_model, "model", None) or getattr(chat_model, "model_name", "")

        # Sem nenhum trecho de documento no CONTEXTO, o SYSTEM_PROMPT instrui
        # o modelo a responder no "modo conhecimento geral" — marcamos a rota
        # para deixar isso visivel no log/API (`route`) e para que
        # `verify_grounding` (que ja retorna grounded=False quando o contexto
        # esta vazio) continue coerente com o rotulo exposto ao usuario.
        if any(marker in answer_text.lower() for marker in _CONFLICT_MARKERS):
            route = "conflict"
        elif not context_text.strip():
            route = "general_knowledge"
        else:
            route = "continue"

        if settings.llm_answer_cache_enabled:
            store_answer(
                session, cache_key=cache_key, answer=answer_text, route=route, model_used=str(model_name)
            )

        return {
            "answer": answer_text,
            "model_used": str(model_name),
            "latency_ms": latency_ms,
            "route": route,
        }

    return generate_answer


def verify_grounding(state: AgentState) -> dict:
    """Heuristica best-effort de fundamentacao: sobreposicao lexical entre a
    resposta e o contexto fornecido. Nao substitui verificacao humana —
    apenas sinaliza ao usuario quando a resposta parece pouco ancorada nos
    documentos (secao 21: "nunca apresente uma resposta nao fundamentada
    como certeza")."""
    answer = (state.get("answer") or "").lower()
    if any(marker in answer for marker in _NO_EVIDENCE_MARKERS):
        return {"grounded": False}

    context = (state.get("context_text") or "").lower()
    if not context:
        return {"grounded": False}

    answer_tokens = set(_TOKEN_PATTERN.findall(answer))
    if not answer_tokens:
        return {"grounded": False}

    context_tokens = set(_TOKEN_PATTERN.findall(context))
    overlap_ratio = len(answer_tokens & context_tokens) / len(answer_tokens)
    return {"grounded": overlap_ratio >= _GROUNDING_OVERLAP_THRESHOLD}


def format_citations(state: AgentState) -> dict:
    """Mantem preferencialmente as citacoes cujo documento foi mencionado
    pelo NOME na resposta (a resposta deve exibir as fontes UTILIZADAS, nao
    todas as fontes fornecidas como candidatas — secao 22). A resposta e em
    linguagem natural (sem marcadores `[Fonte N]`, ver `templates.py`), entao
    a deteccao e por nome de documento; se nenhum nome for reconhecido no
    texto (resposta muito parafraseada, ou modelo pequeno que nao repete o
    nome), mostra todas as fontes candidatas em vez de esconder tudo."""
    answer = state.get("answer") or ""
    citations = state.get("citations") or []
    if not citations:
        return {}

    answer_lower = answer.lower()
    referenced = [c for c in citations if c["document_name"].lower() in answer_lower]
    return {"citations": referenced or citations}
