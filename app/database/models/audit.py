"""Logs de ingestao, configuracoes e trilha de auditoria (secoes 28, 29 e 32)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel

from app.database.models.enums import IngestionStage, IngestionStatus


class IngestionLog(SQLModel, table=True):
    __tablename__ = "ingestion_logs"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    document_id: str | None = Field(default=None, foreign_key="documents.id", index=True)
    version_id: str | None = Field(default=None, foreign_key="document_versions.id", index=True)
    correlation_id: str | None = Field(default=None, index=True)
    stage: IngestionStage
    status: IngestionStatus
    message: str
    duration_ms: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(SQLModel, table=True):
    """Trilha de auditoria de acoes sensiveis (login, aprovacao, exclusao, etc.)."""

    __tablename__ = "audit_events"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="users.id", index=True)
    action: str
    resource_type: str
    resource_id: str | None = None
    details_json: str | None = None
    ip_address: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AppConfigurationEntry(SQLModel, table=True):
    """Configuracoes administrativas editaveis em runtime (nunca segredos —
    chaves de API continuam exclusivas do .env, conforme secao 3)."""

    __tablename__ = "app_configuration_entries"

    key: str = Field(primary_key=True)
    value: str
    updated_by_user_id: str | None = Field(default=None, foreign_key="users.id")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
