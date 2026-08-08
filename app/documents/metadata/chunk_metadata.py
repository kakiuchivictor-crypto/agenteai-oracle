"""Montagem dos metadados completos de um chunk (secao 14 do prompt mestre).

Produz dois formatos a partir do mesmo conjunto de dados:
- um dicionario "achatado" (apenas str/int/float/bool) para o banco vetorial,
  que geralmente nao aceita valores `None` ou aninhados;
- os campos completos para persistir na tabela `document_chunks` do banco
  relacional (que aceita `None`).
"""

from __future__ import annotations

from typing import Any

from app.schemas.chunk import Chunk


class ChunkContext:
    """Contexto de documento/versao aplicado a todo chunk gerado a partir dele."""

    def __init__(
        self,
        *,
        document_id: str,
        version_id: str,
        original_filename: str,
        document_format: str,
        category: str | None = None,
        subcategory: str | None = None,
        tags: list[str] | None = None,
        responsible_name: str | None = None,
        department: str | None = None,
        status: str,
        is_official: bool,
        access_classification: str,
        version_number: int,
        language: str = "pt-br",
    ) -> None:
        self.document_id = document_id
        self.version_id = version_id
        self.original_filename = original_filename
        self.document_format = document_format
        self.category = category
        self.subcategory = subcategory
        self.tags = tags or []
        self.responsible_name = responsible_name
        self.department = department
        self.status = status
        self.is_official = is_official
        self.access_classification = access_classification
        self.version_number = version_number
        self.language = language


def build_vector_metadata(chunk: Chunk, context: ChunkContext) -> dict[str, Any]:
    """Constroi o dict de metadados enviado junto ao vetor no Chroma.

    Apenas valores escalares nao nulos sao incluidos — Chroma nao aceita
    `None` como valor de metadado.
    """
    raw: dict[str, Any] = {
        "document_id": context.document_id,
        "version_id": context.version_id,
        "original_filename": context.original_filename,
        "document_format": context.document_format,
        "category": context.category,
        "subcategory": context.subcategory,
        "tags": ",".join(context.tags) if context.tags else None,
        "responsible_name": context.responsible_name,
        "department": context.department,
        "status": context.status,
        "is_official": context.is_official,
        "access_classification": context.access_classification,
        "version_number": context.version_number,
        "language": context.language,
        "chunk_index": chunk.chunk_index,
        "page": chunk.page,
        "section": chunk.section,
        "slide": chunk.slide,
        "sheet_name": chunk.sheet_name,
        "row_number": chunk.row_number,
        "table_name": chunk.table_name,
        "json_path": chunk.json_path,
        "is_ocr": chunk.is_ocr,
        "char_count": chunk.char_count,
    }
    return {key: value for key, value in raw.items() if value is not None}
