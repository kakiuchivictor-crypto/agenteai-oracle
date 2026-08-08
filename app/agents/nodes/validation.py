"""Validacao da pergunta, deteccao de intencao e reescrita da consulta
(secao 24 do prompt mestre)."""

from __future__ import annotations

import re

from app.agents.state import AgentState

MAX_QUESTION_LENGTH = 2000
# Quantas perguntas anteriores do usuario entram na consulta de busca
# reescrita (secao 23). Mantido pequeno de proposito.
_REWRITE_HISTORY_TURNS = 2

# Heuristicas leves (sem custo de LLM) para desviar perguntas que nao devem
# consumir o pipeline de recuperacao/geracao completo — economiza tokens e
# latencia (secao 42) para os casos mais comuns e obvios.
_ADMIN_KEYWORDS = (
    "aprovar documento",
    "rejeitar documento",
    "criar categoria",
    "excluir usuario",
    "criar usuario",
    "gerenciar usuario",
    "alterar configuracao",
    "configurar provedor",
    "gerenciar permissao",
)
_INGESTION_KEYWORDS = (
    "upload",
    "enviar arquivo",
    "enviar documento",
    "processar documento",
    "indexar documento",
    "adicionar documento",
)
_GREETING_PATTERN = re.compile(
    r"^\s*(oi|ola|olá|bom dia|boa tarde|boa noite|hey|hello)\s*[!.?]*\s*$", re.IGNORECASE
)


def validate_question(state: AgentState) -> dict:
    question = (state.get("question") or "").strip()
    if not question:
        return {"route": "invalid", "error": "Pergunta vazia."}
    if len(question) > MAX_QUESTION_LENGTH:
        return {"route": "invalid", "error": "Pergunta excede o tamanho maximo permitido."}
    return {"normalized_question": question, "route": "continue"}


def identify_intent(state: AgentState) -> dict:
    question_lower = state["normalized_question"].lower()

    if _GREETING_PATTERN.match(question_lower):
        return {"intent": "out_of_scope", "route": "out_of_scope"}
    if any(keyword in question_lower for keyword in _ADMIN_KEYWORDS):
        return {"intent": "admin_request", "route": "admin_request"}
    if any(keyword in question_lower for keyword in _INGESTION_KEYWORDS):
        return {"intent": "ingestion_request", "route": "ingestion_request"}
    return {"intent": "question", "route": "continue"}


def rewrite_query(state: AgentState) -> dict:
    """Amplia a consulta usada na busca com o contexto de perguntas
    anteriores do usuario (secao 23: "E para compras internacionais?" deve
    continuar buscando sobre reembolso), sem chamar o LLM para isso.

    Uma reescrita "perfeita" via LLM produziria uma consulta mais limpa, mas
    custaria uma chamada inteira ao provedor a cada pergunta de
    acompanhamento — em modelos rodando em CPU isso pode dobrar o tempo de
    resposta. Concatenar as ultimas perguntas do usuario a atual e uma
    heuristica praticamente gratuita que ja melhora a busca vetorial o
    suficiente, e a resposta final continua vendo o historico completo de
    qualquer forma (ver `generation.make_generate_answer`)."""
    history = state.get("chat_history") or []
    question = state["normalized_question"]
    if not history:
        return {"rewritten_query": question}

    previous_questions = [turn["content"] for turn in history if turn["role"] == "user"]
    combined = " ".join([*previous_questions[-_REWRITE_HISTORY_TURNS:], question])
    return {"rewritten_query": combined}


def determine_filters(state: AgentState) -> dict:
    filters: dict = {}
    category_filter = state.get("category_filter")
    if category_filter:
        filters["category"] = category_filter
    return {"retrieval_filters": filters}
