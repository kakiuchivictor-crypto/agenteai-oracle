"""Schemas da API de documentos (secoes 26 e 39 do prompt mestre)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.database.models.enums import (
    AccessClassification,
    CurationStatus,
    DocumentFormat,
    VersionIndexStatus,
)


class DocumentUploadResponse(BaseModel):
    status: str  # registered | duplicate
    document_id: str | None
    version_id: str | None
    duplicate_of_document_id: str | None = None


class DocumentProcessResponse(BaseModel):
    status: str  # success | failed | duplicate
    document_id: str | None
    version_id: str | None
    chunks_indexed: int
    warnings: list[str]
    error: str | None


class DocumentResponse(BaseModel):
    id: str
    original_filename: str
    format: DocumentFormat
    category_id: str | None
    subcategory: str | None
    tags: str | None
    responsible_id: str | None
    department: str | None
    status: CurationStatus
    is_official: bool
    access_classification: AccessClassification
    origin: str
    active_version_id: str | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None


class DocumentVersionResponse(BaseModel):
    id: str
    document_id: str
    version_number: int
    index_status: VersionIndexStatus
    embedding_model: str | None
    embedding_provider: str | None
    is_ocr: bool
    warnings: str | None
    error_message: str | None
    created_at: datetime


class DocumentStatusChangeRequest(BaseModel):
    reason: str | None = None
