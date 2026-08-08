"""Ponto de entrada do agente RAG para a API/interface (secao 24).

Garante que a sessao de chat exista, carrega o historico recente (nao
ilimitado — secao 23) e invoca o grafo do agente.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from sqlmodel import Session, select

from app.agents.graph import build_agent_graph
from app.agents.state import AgentState, ChatTurn, Citation
from app.core.config import Settings, get_settings
from app.core.logging import new_correlation_id
from app.database.models import ChatMessage, ChatSession
from app.embeddings.base import BaseEmbeddingProvider
from app.llm.factory import get_chat_model
from app.reranking.base import BaseReranker
from app.vectorstores.base import VectorRepository


@dataclass
class AskResult:
    answer: str
    message_id: str
    citations: list[Citation]
    grounded: bool | None
    route: str
    model_used: str | None


def _load_recent_history(session: Session, session_id: str, max_turns: int) -> list[ChatTurn]:
    if max_turns <= 0:
        return []
    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(max_turns * 2)
    ).all()
    ordered = list(reversed(messages))
    return [ChatTurn(role=message.role.value, content=message.content) for message in ordered]


def ask_question(
    *,
    question: str,
    session_id: str,
    user_id: str,
    session: Session,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    reranker: BaseReranker,
    chat_model: BaseChatModel | None = None,
    settings: Settings | None = None,
    category_filter: str | None = None,
) -> AskResult:
    settings = settings or get_settings()
    chat_model = chat_model or get_chat_model()

    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        chat_session = ChatSession(id=session_id, user_id=user_id)
        session.add(chat_session)
        session.commit()

    history = _load_recent_history(session, session_id, settings.max_chat_history_turns)

    graph = build_agent_graph(
        session=session,
        chat_model=chat_model,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        reranker=reranker,
        settings=settings,
    )

    initial_state: AgentState = {
        "correlation_id": new_correlation_id(),
        "session_id": session_id,
        "user_id": user_id,
        "question": question,
        "chat_history": history,
        "category_filter": category_filter,
    }

    final_state = graph.invoke(initial_state)

    return AskResult(
        answer=final_state.get("answer", ""),
        message_id=final_state.get("message_id", ""),
        citations=final_state.get("citations") or [],
        grounded=final_state.get("grounded"),
        route=final_state.get("route", "continue"),
        model_used=final_state.get("model_used"),
    )
