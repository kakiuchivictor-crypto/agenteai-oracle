"""Rotas de chat (secoes 21, 22, 23, 26 e 39 do prompt mestre)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from langchain_core.language_models.chat_models import BaseChatModel
from sqlmodel import Session, select

from app.agents.service import ask_question
from app.api.dependencies.db import get_db_session
from app.api.dependencies.providers import (
    get_chat_model_dep,
    get_embedding_provider_dep,
    get_reranker_dep,
    get_vector_repository_dep,
)
from app.core.exceptions import ResourceNotFoundError
from app.core.system_user import SYSTEM_USER_ID
from app.database.models import ChatMessage, ChatSession
from app.embeddings.base import BaseEmbeddingProvider
from app.reranking.base import BaseReranker
from app.schemas.api.chat import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionResponse,
)
from app.vectorstores.base import VectorRepository

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    session: Session = Depends(get_db_session),
    embedding_provider: BaseEmbeddingProvider = Depends(get_embedding_provider_dep),
    vector_repository: VectorRepository = Depends(get_vector_repository_dep),
    reranker: BaseReranker = Depends(get_reranker_dep),
    chat_model: BaseChatModel = Depends(get_chat_model_dep),
) -> ChatResponse:
    session_id = payload.session_id or uuid.uuid4().hex
    result = ask_question(
        question=payload.question,
        session_id=session_id,
        user_id=SYSTEM_USER_ID,
        session=session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        reranker=reranker,
        chat_model=chat_model,
        category_filter=payload.category_filter,
    )
    return ChatResponse(
        session_id=session_id,
        message_id=result.message_id,
        answer=result.answer,
        citations=result.citations,
        grounded=result.grounded,
        route=result.route,
        model_used=result.model_used,
    )


@router.get("/chat/sessions", response_model=list[ChatSessionResponse])
def list_chat_sessions(session: Session = Depends(get_db_session)) -> list[ChatSessionResponse]:
    sessions = session.exec(
        select(ChatSession).order_by(ChatSession.updated_at.desc())
    ).all()
    return [ChatSessionResponse.model_validate(s, from_attributes=True) for s in sessions]


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_chat_messages(
    session_id: str, session: Session = Depends(get_db_session)
) -> list[ChatMessageResponse]:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        raise ResourceNotFoundError(f"Sessao de chat '{session_id}' nao encontrada.")

    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    ).all()
    return [
        ChatMessageResponse(
            id=m.id, role=m.role.value, content=m.content, sources_json=m.sources_json,
            grounded=m.grounded, created_at=m.created_at,
        )
        for m in messages
    ]
