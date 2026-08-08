"""Modelos SQLModel da aplicacao.

Todos os modelos devem ser importados aqui para que o Alembic (autogenerate)
e o `SQLModel.metadata.create_all` enxerguem as tabelas.
"""

from app.database.models.audit import AppConfigurationEntry, AuditEvent, IngestionLog
from app.database.models.category import Category, Responsible
from app.database.models.conversation import ChatMessage, ChatSession, Feedback
from app.database.models.document import (
    Document,
    DocumentAccessGrant,
    DocumentChunk,
    DocumentVersion,
    EmbeddingIndexVersion,
)
from app.database.models.enums import (
    AccessClassification,
    AccessSubjectType,
    CurationStatus,
    DocumentFormat,
    FeedbackIssueType,
    FeedbackRating,
    IngestionStage,
    IngestionStatus,
    MessageRole,
    UserRole,
    VersionIndexStatus,
)
from app.database.models.llm_usage import AnswerCache, LlmDailyUsage
from app.database.models.user import User

__all__ = [
    "AccessClassification",
    "AccessSubjectType",
    "AnswerCache",
    "AppConfigurationEntry",
    "AuditEvent",
    "Category",
    "ChatMessage",
    "ChatSession",
    "CurationStatus",
    "Document",
    "DocumentAccessGrant",
    "DocumentChunk",
    "DocumentFormat",
    "DocumentVersion",
    "EmbeddingIndexVersion",
    "Feedback",
    "FeedbackIssueType",
    "FeedbackRating",
    "IngestionLog",
    "IngestionStage",
    "IngestionStatus",
    "LlmDailyUsage",
    "MessageRole",
    "Responsible",
    "User",
    "UserRole",
    "VersionIndexStatus",
]
