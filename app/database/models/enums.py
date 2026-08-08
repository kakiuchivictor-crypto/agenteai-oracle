"""Enumeracoes compartilhadas pelos modelos de banco de dados."""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """Perfis de acesso descritos na secao 10 do prompt mestre."""

    ADMIN = "admin"
    CURATOR = "curator"
    USER = "user"


class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    MARKDOWN = "markdown"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


class CurationStatus(str, Enum):
    """Estados de curadoria da secao 8 do prompt mestre."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    OUTDATED = "outdated"
    REPLACED = "replaced"
    ARCHIVED = "archived"
    DUPLICATE = "duplicate"


class AccessClassification(str, Enum):
    """Classificacao de acesso do documento (base para restricao futura por
    departamento/grupo/usuario, exigida na secao 10)."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class VersionIndexStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class IngestionStage(str, Enum):
    """Etapas do pipeline da secao 11 do prompt mestre."""

    COLLECTION = "collection"
    VALIDATION = "validation"
    FORMAT_DETECTION = "format_detection"
    EXTRACTION = "extraction"
    CLEANING = "cleaning"
    STRUCTURING = "structuring"
    CHUNKING = "chunking"
    METADATA = "metadata"
    QUALITY_VALIDATION = "quality_validation"
    EMBEDDING = "embedding"
    VECTOR_STORAGE = "vector_storage"
    AVAILABILITY = "availability"


class IngestionStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class FeedbackRating(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class FeedbackIssueType(str, Enum):
    NONE = "none"
    INCOMPLETE_ANSWER = "incomplete_answer"
    WRONG_SOURCE = "wrong_source"
    OUTDATED_ANSWER = "outdated_answer"
    OTHER = "other"


class AccessSubjectType(str, Enum):
    """Tipo de sujeito para concessoes de acesso futuras a documentos."""

    USER = "user"
    DEPARTMENT = "department"
    ROLE = "role"
