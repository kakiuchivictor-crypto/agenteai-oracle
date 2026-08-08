"""Documentos, versoes e chunks (secoes 8, 11, 14 e 40 do prompt mestre)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel

from app.database.models.enums import (
    AccessClassification,
    AccessSubjectType,
    CurationStatus,
    DocumentFormat,
    VersionIndexStatus,
)


class Document(SQLModel, table=True):
    """Registro logico de um documento. O conteudo/texto vive nas versoes
    (`DocumentVersion`) para permitir historico completo sem misturar chunks
    antigos e novos (secao 40)."""

    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    original_filename: str
    format: DocumentFormat
    category_id: str | None = Field(default=None, foreign_key="categories.id")
    subcategory: str | None = None
    tags: str | None = None  # lista separada por virgula
    responsible_id: str | None = Field(default=None, foreign_key="responsibles.id")
    department: str | None = None
    status: CurationStatus = Field(default=CurationStatus.PENDING_REVIEW)
    is_official: bool = Field(default=False)
    confidence_level: str | None = None
    access_classification: AccessClassification = Field(default=AccessClassification.INTERNAL)
    origin: str = Field(default="upload")  # upload | watched_folder | api | <connector>
    file_hash: str = Field(index=True)  # sha256 do arquivo bruto, deduplicacao exata
    # Sem constraint de FK: evita ciclo com document_versions.document_id
    # (uma versao so pode existir apos o documento, mas o documento so
    # aponta para sua versao ativa depois que ela e processada).
    active_version_id: str | None = Field(default=None, index=True)
    uploaded_by_user_id: str | None = Field(default=None, foreign_key="users.id")
    valid_until: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    approved_by_user_id: str | None = Field(default=None, foreign_key="users.id")


class DocumentVersion(SQLModel, table=True):
    """Uma versao especifica do conteudo de um documento."""

    __tablename__ = "document_versions"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    version_number: int
    storage_path: str  # caminho do arquivo original armazenado
    processed_text_path: str | None = None  # texto normalizado apos limpeza
    content_hash: str = Field(index=True)  # hash do conteudo normalizado
    index_status: VersionIndexStatus = Field(default=VersionIndexStatus.PENDING)
    embedding_model: str | None = None
    embedding_provider: str | None = None
    is_ocr: bool = Field(default=False)
    warnings: str | None = None  # avisos de extracao, separados por ' | '
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentChunk(SQLModel, table=True):
    """Um trecho indexavel de uma versao de documento, com metadados de
    origem completos (secao 14). O texto tambem fica aqui (alem do vetor no
    banco vetorial) para viabilizar busca lexical/BM25 (secao 18)."""

    __tablename__ = "document_chunks"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    version_id: str = Field(foreign_key="document_versions.id", index=True)
    vector_id: str = Field(index=True, unique=True)
    chunk_index: int
    text: str
    char_count: int
    page: int | None = None
    section: str | None = None
    slide: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    table_name: str | None = None
    json_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentAccessGrant(SQLModel, table=True):
    """Concessao explicita de acesso a um documento confidencial, alem da
    classificacao padrao. Ponto de extensao para RBAC granular (secao 10)."""

    __tablename__ = "document_access_grants"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    subject_type: AccessSubjectType
    subject_value: str  # user_id, nome de departamento ou role
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EmbeddingIndexVersion(SQLModel, table=True):
    """Registro do modelo/provedor de embedding usado para indexar, conforme
    exigido na secao 15 (nunca misturar vetores incompativeis no mesmo indice)."""

    __tablename__ = "embedding_index_versions"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    provider: str
    model: str
    dimension: int
    collection_name: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
