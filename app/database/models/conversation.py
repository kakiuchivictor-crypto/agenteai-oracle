"""Sessoes de chat, mensagens e feedback (secoes 23 e 31 do prompt mestre)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel

from app.database.models.enums import FeedbackIssueType, FeedbackRating, MessageRole


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    title: str | None = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    session_id: str = Field(foreign_key="chat_sessions.id", index=True)
    role: MessageRole
    content: str
    sources_json: str | None = None  # JSON serializado das fontes citadas
    grounded: bool | None = None  # None quando nao se aplica (ex: mensagem do usuario)
    retrieval_config_json: str | None = None  # parametros de recuperacao usados
    model_used: str | None = None
    latency_ms: int | None = None
    tokens_used: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Feedback(SQLModel, table=True):
    __tablename__ = "feedbacks"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    message_id: str = Field(foreign_key="chat_messages.id", index=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    rating: FeedbackRating
    issue_type: FeedbackIssueType = Field(default=FeedbackIssueType.NONE)
    comment: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
