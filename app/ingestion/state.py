"""Estado tipado do grafo de ingestao (secao 11 e 24 do prompt mestre)."""

from __future__ import annotations

from typing import TypedDict

from app.documents.cleaners.document_cleaner import CleanedDocument
from app.schemas.chunk import Chunk
from app.schemas.document import ExtractedDocument


class IngestionState(TypedDict, total=False):
    # --- Entrada ---
    correlation_id: str
    file_path: str
    original_filename: str
    raw_bytes: bytes
    category_id: str | None
    subcategory: str | None
    tags: list[str]
    responsible_id: str | None
    department: str | None
    access_classification: str
    uploaded_by_user_id: str | None
    origin: str
    is_official: bool

    # --- Calculado durante o pipeline ---
    file_hash: str
    extracted: ExtractedDocument
    cleaned: CleanedDocument
    chunks: list[Chunk]
    content_hash: str
    embedding_model: str
    embedding_provider: str
    embedding_dimension: int

    # --- Resultado ---
    document_id: str
    version_id: str
    version_number: int
    chunks_indexed: int
    warnings: list[str]
    error: str | None
    error_stage: str | None
    status: str  # success | failed | duplicate
