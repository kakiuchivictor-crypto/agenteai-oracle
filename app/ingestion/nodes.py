"""Nos do grafo de ingestao (secao 11 do prompt mestre).

Cada funcao recebe e devolve apenas o pedaco do estado que altera —
o LangGraph mescla o retorno ao estado global automaticamente. Erros de
dominio (`AppError`) sao capturados e convertidos em `state["error"]` em vez
de propagar, para que o grafo decida a proxima aresta (nó de tratamento de
erro) sem derrubar o processo do lote inteiro.
"""

from __future__ import annotations

import time
from pathlib import Path

from sqlmodel import Session, select

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.database.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    EmbeddingIndexVersion,
    IngestionLog,
)
from app.database.models.enums import IngestionStage, IngestionStatus, VersionIndexStatus
from app.documents.chunkers.hybrid_chunker import chunk_sections
from app.documents.cleaners.document_cleaner import clean_document
from app.documents.loaders.registry import get_loader_for
from app.documents.metadata.chunk_metadata import ChunkContext, build_vector_metadata
from app.documents.validators.hashing import compute_content_hash
from app.embeddings.base import BaseEmbeddingProvider
from app.ingestion.state import IngestionState
from app.schemas.vector import VectorDocument
from app.vectorstores.base import VectorRepository

logger = get_logger(__name__)


def _log_stage(
    session: Session,
    state: IngestionState,
    stage: IngestionStage,
    status: IngestionStatus,
    message: str,
    duration_ms: int | None = None,
) -> None:
    session.add(
        IngestionLog(
            document_id=state.get("document_id"),
            version_id=state.get("version_id"),
            correlation_id=state.get("correlation_id"),
            stage=stage,
            status=status,
            message=message,
            duration_ms=duration_ms,
        )
    )
    session.commit()


def _timed_stage(stage: IngestionStage):
    """Decorator que cronometra um no e converte AppError em `state['error']`."""

    def decorator(func):
        def wrapper(session: Session, state: IngestionState, *args, **kwargs) -> dict:
            if state.get("error"):
                return {}
            start = time.perf_counter()
            try:
                result = func(session, state, *args, **kwargs)
                duration_ms = int((time.perf_counter() - start) * 1000)
                _log_stage(
                    session, state, stage, IngestionStatus.SUCCESS, f"{stage.value} concluido",
                    duration_ms,
                )
                return result
            except AppError as exc:
                duration_ms = int((time.perf_counter() - start) * 1000)
                logger.warning("ingestion.stage_failed", stage=stage.value, error=exc.message)
                _log_stage(session, state, stage, IngestionStatus.FAILED, exc.message, duration_ms)
                return {"error": exc.message, "error_stage": stage.value}

        return wrapper

    return decorator


# ==========================================================
# COLETA E VALIDACAO
# ==========================================================
# A deteccao de duplicata exata (por file_hash) acontece em
# `app.ingestion.service` ANTES de criar os registros de Documento/Versao e
# de invocar este grafo — nao ha necessidade de repetir aqui. Este no apenas
# confirma que o arquivo salvo em disco esta acessivel para o restante do
# pipeline, gerando a entrada de log correspondente a etapa de validacao.
@_timed_stage(IngestionStage.VALIDATION)
def collect_and_validate(session: Session, state: IngestionState) -> dict:
    file_path = Path(state["file_path"])
    if not file_path.exists():
        raise AppError(f"Arquivo nao encontrado: {file_path}")
    return {}


# ==========================================================
# IDENTIFICACAO DO FORMATO E EXTRACAO
# ==========================================================
@_timed_stage(IngestionStage.EXTRACTION)
def extract(session: Session, state: IngestionState) -> dict:
    file_path = Path(state["file_path"])
    loader = get_loader_for(file_path)
    extracted = loader.load(file_path)
    return {"extracted": extracted}


# ==========================================================
# LIMPEZA E ESTRUTURACAO
# ==========================================================
@_timed_stage(IngestionStage.CLEANING)
def clean(session: Session, state: IngestionState) -> dict:
    cleaned = clean_document(state["extracted"])
    if not cleaned.sections:
        raise AppError("Documento nao possui conteudo textual apos a limpeza.")
    return {"cleaned": cleaned}


# ==========================================================
# CHUNKING
# ==========================================================
@_timed_stage(IngestionStage.CHUNKING)
def chunk(
    session: Session, state: IngestionState, *, chunk_size: int, chunk_overlap: int,
    max_chunk_size: int,
) -> dict:
    chunks = chunk_sections(
        state["cleaned"].sections,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_chunk_size=max_chunk_size,
    )
    if not chunks:
        raise AppError("Nenhum chunk gerado a partir do documento.")

    full_text = "\n\n".join(c.text for c in chunks)
    content_hash = compute_content_hash(full_text)
    return {"chunks": chunks, "content_hash": content_hash}


# ==========================================================
# VALIDACAO DE QUALIDADE
# ==========================================================
@_timed_stage(IngestionStage.QUALITY_VALIDATION)
def quality_validate(session: Session, state: IngestionState) -> dict:
    chunks = state["chunks"]
    warnings: list[str] = [f"{w.code}: {w.message}" for w in state["extracted"].warnings]
    if len(chunks) == 0:
        raise AppError("Documento sem chunks validos para indexacao.")
    return {"warnings": warnings}


# ==========================================================
# EMBEDDINGS E ARMAZENAMENTO VETORIAL
# ==========================================================
def make_embed_and_store(embedding_provider: BaseEmbeddingProvider, vector_repository: VectorRepository):
    @_timed_stage(IngestionStage.EMBEDDING)
    def embed_and_store(session: Session, state: IngestionState) -> dict:
        chunks = state["chunks"]
        texts = [c.text for c in chunks]
        embeddings = embedding_provider.embed_documents(texts)

        context = ChunkContext(
            document_id=state["document_id"],
            version_id=state["version_id"],
            original_filename=state["original_filename"],
            document_format=state["extracted"].document_format,
            category=state.get("category_id"),
            subcategory=state.get("subcategory"),
            tags=state.get("tags") or [],
            department=state.get("department"),
            status="pending_review",
            is_official=state.get("is_official", False),
            access_classification=state.get("access_classification", "internal"),
            version_number=state["version_number"],
        )

        vector_documents = []
        db_chunks = []
        for chunk_item, embedding in zip(chunks, embeddings, strict=True):
            vector_id = f"{state['version_id']}:{chunk_item.chunk_index}"
            metadata = build_vector_metadata(chunk_item, context)
            vector_documents.append(
                VectorDocument(id=vector_id, text=chunk_item.text, embedding=embedding, metadata=metadata)
            )
            db_chunks.append(
                DocumentChunk(
                    document_id=state["document_id"],
                    version_id=state["version_id"],
                    vector_id=vector_id,
                    chunk_index=chunk_item.chunk_index,
                    text=chunk_item.text,
                    char_count=chunk_item.char_count,
                    page=chunk_item.page,
                    section=chunk_item.section,
                    slide=chunk_item.slide,
                    sheet_name=chunk_item.sheet_name,
                    row_number=chunk_item.row_number,
                    table_name=chunk_item.table_name,
                    json_path=chunk_item.json_path,
                )
            )

        vector_repository.add_documents(vector_documents)
        for db_chunk in db_chunks:
            session.add(db_chunk)
        session.commit()

        return {
            "embedding_model": embedding_provider.model_name,
            "embedding_provider": embedding_provider.provider_name,
            "embedding_dimension": embedding_provider.dimension,
            "chunks_indexed": len(vector_documents),
        }

    return embed_and_store


# ==========================================================
# FINALIZACAO
# ==========================================================
def finalize_success(session: Session, state: IngestionState) -> dict:
    version = session.get(DocumentVersion, state["version_id"])
    document = session.get(Document, state["document_id"])
    if version is None or document is None:
        raise AppError("Documento/versao nao encontrados ao finalizar a ingestao.")

    version.index_status = VersionIndexStatus.INDEXED
    version.embedding_model = state.get("embedding_model")
    version.embedding_provider = state.get("embedding_provider")
    version.is_ocr = any(s.is_ocr for s in state["cleaned"].sections)
    version.warnings = " | ".join(state.get("warnings") or []) or None
    version.content_hash = state["content_hash"]
    document.active_version_id = version.id
    document.updated_at = version.created_at

    _register_embedding_index_version(
        session,
        provider=state.get("embedding_provider", ""),
        model=state.get("embedding_model", ""),
        dimension=state.get("embedding_dimension", 0),
    )

    session.add(version)
    session.add(document)
    session.commit()

    _log_stage(
        session, state, IngestionStage.AVAILABILITY, IngestionStatus.SUCCESS,
        f"Documento disponivel para consulta com {state.get('chunks_indexed', 0)} chunks.",
    )
    return {"status": "success"}


def finalize_failure(session: Session, state: IngestionState) -> dict:
    version = session.get(DocumentVersion, state.get("version_id"))
    if version is not None:
        version.index_status = VersionIndexStatus.FAILED
        version.error_message = state.get("error")
        session.add(version)
        session.commit()

    logger.error(
        "ingestion.failed",
        stage=state.get("error_stage"),
        error=state.get("error"),
        file=state.get("original_filename"),
    )
    return {"status": "failed"}


def _register_embedding_index_version(
    session: Session, *, provider: str, model: str, dimension: int
) -> None:
    existing = session.exec(
        select(EmbeddingIndexVersion).where(
            EmbeddingIndexVersion.provider == provider,
            EmbeddingIndexVersion.model == model,
            EmbeddingIndexVersion.is_active == True,  # noqa: E712
        )
    ).first()
    if existing:
        return
    session.add(
        EmbeddingIndexVersion(
            provider=provider,
            model=model,
            dimension=dimension,
            collection_name="documents",
            is_active=True,
        )
    )
