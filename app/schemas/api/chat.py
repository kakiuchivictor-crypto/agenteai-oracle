"""Schemas da API de chat (secoes 21, 22, 23 e 39 do prompt mestre)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.agents.state import Citation


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None
    category_filter: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    citations: list[Citation]
    grounded: bool | None
    route: str
    model_used: str | None


class ChatSessionResponse(BaseModel):
    id: str
    title: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources_json: str | None
    grounded: bool | None
    created_at: datetime
