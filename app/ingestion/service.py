"""Orquestracao da ingestao de documentos (secoes 6, 11 e 40 do prompt mestre).

O fluxo e dividido em duas etapas explicitas, espelhando a interface da
secao 26 ("upload de arquivos" + botao separado "processar"): `register_document`
apenas valida, salva o arquivo e cria os registros de Documento/Versao;
`process_document_version` executa o grafo de ingestao (extracao -> ... ->
disponibilizacao) sobre uma versao ja registrada. `ingest_new_document`
combina as duas em uma unica chamada sincrona, usada pelo pipeline
automatizado (pasta monitorada, scripts, testes).

A deteccao de duplicata exata (mesmo hash de arquivo) acontece ANTES de
qualquer escrita no banco, evitando registros orfaos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.core.exceptions import DocumentNotFoundError, UnsupportedDocumentError
from app.core.logging import get_logger, new_correlation_id
from app.core.security import safe_filename, validate_upload
from app.database.models import Document, DocumentVersion
from app.database.models.enums import CurationStatus, DocumentFormat
from app.documents.validators.hashing import compute_file_hash
from app.embeddings.base import BaseEmbeddingProvider
from app.ingestion.pipeline import build_ingestion_graph
from app.ingestion.state import IngestionState
from app.services.curation_service import change_document_status
from app.vectorstores.base import VectorRepository

logger = get_logger(__name__)

_EXTENSION_TO_FORMAT: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".xlsx": DocumentFormat.XLSX,
    ".pptx": DocumentFormat.PPTX,
    ".md": DocumentFormat.MARKDOWN,
    ".markdown": DocumentFormat.MARKDOWN,
    ".csv": DocumentFormat.CSV,
    ".json": DocumentFormat.JSON,
    ".html": DocumentFormat.HTML,
    ".htm": DocumentFormat.HTML,
}


@dataclass
class IngestionResult:
    status: str  # success | failed | duplicate
    document_id: str | None
    version_id: str | None
    chunks_indexed: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    duplicate_of_document_id: str | None = None


@dataclass
class RegisteredDocument:
    status: str  # registered | duplicate
    document_id: str | None
    version_id: str | None
    duplicate_of_document_id: str | None = None


def _resolve_format(original_filename: str) -> DocumentFormat:
    extension = Path(original_filename).suffix.lower()
    document_format = _EXTENSION_TO_FORMAT.get(extension)
    if document_format is None:
        raise UnsupportedDocumentError(f"Extensao '{extension}' nao suportada para ingestao.")
    return document_format


def _save_upload(raw_bytes: bytes, original_filename: str, settings: Settings) -> Path:
    stored_filename = safe_filename(original_filename)
    destination = Path(settings.upload_dir) / stored_filename
    destination.write_bytes(raw_bytes)
    return destination


def _run_pipeline(
    *,
    initial_state: IngestionState,
    session: Session,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    settings: Settings,
) -> IngestionState:
    graph = build_ingestion_graph(
        session=session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        max_chunk_size=settings.max_chunk_size,
    )
    return graph.invoke(initial_state)  # type: ignore[return-value]


def register_document(
    *,
    original_filename: str,
    raw_bytes: bytes,
    session: Session,
    category_id: str | None = None,
    subcategory: str | None = None,
    tags: list[str] | None = None,
    responsible_id: str | None = None,
    department: str | None = None,
    access_classification: str = "internal",
    is_official: bool = False,
    origin: str = "upload",
    uploaded_by_user_id: str | None = None,
    settings: Settings | None = None,
) -> RegisteredDocument:
    """Valida e salva o upload, criando Documento + primeira Versao (ainda
    sem processar). Nenhuma extracao/chunking/embedding acontece aqui."""
    settings = settings or get_settings()
    settings.ensure_runtime_directories()

    validate_upload(
        filename=original_filename,
        content=raw_bytes,
        allowed_extensions=settings.allowed_extensions_list,
        max_size_mb=settings.max_upload_size_mb,
    )
    document_format = _resolve_format(original_filename)

    file_hash = compute_file_hash(raw_bytes)
    existing_document = session.exec(
        select(Document).where(Document.file_hash == file_hash)
    ).first()
    if existing_document is not None:
        logger.info(
            "ingestion.duplicate_skipped",
            file=original_filename,
            existing_document_id=existing_document.id,
        )
        return RegisteredDocument(
            status="duplicate",
            document_id=None,
            version_id=None,
            duplicate_of_document_id=existing_document.id,
        )

    destination = _save_upload(raw_bytes, original_filename, settings)

    document = Document(
        original_filename=original_filename,
        format=document_format,
        category_id=category_id,
        subcategory=subcategory,
        tags=",".join(tags) if tags else None,
        responsible_id=responsible_id,
        department=department,
        access_classification=access_classification,
        is_official=is_official,
        origin=origin,
        file_hash=file_hash,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    session.add(document)
    session.flush()

    version = DocumentVersion(
        document_id=document.id, version_number=1, storage_path=str(destination), content_hash=""
    )
    session.add(version)
    session.commit()
    session.refresh(document)
    session.refresh(version)

    return RegisteredDocument(status="registered", document_id=document.id, version_id=version.id)


def resolve_version_to_process(document: Document, session: Session) -> str:
    """Retorna a versao ativa do documento ou, se ainda nao houver nenhuma
    (documento registrado mas nunca processado, ou cujo processamento
    anterior falhou), a versao mais recente registrada."""
    if document.active_version_id:
        return document.active_version_id
    latest = session.exec(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_number.desc())
    ).first()
    if latest is None:
        raise DocumentNotFoundError(f"Documento '{document.id}' nao possui versoes registradas.")
    return latest.id


def process_document_version(
    *,
    document_id: str,
    version_id: str,
    session: Session,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    settings: Settings | None = None,
) -> IngestionResult:
    """Executa o grafo de ingestao sobre uma versao ja registrada em disco."""
    settings = settings or get_settings()

    document = session.get(Document, document_id)
    version = session.get(DocumentVersion, version_id)
    if document is None or version is None:
        raise DocumentNotFoundError(
            f"Documento '{document_id}' ou versao '{version_id}' nao encontrados."
        )

    initial_state: IngestionState = {
        "correlation_id": new_correlation_id(),
        "file_path": version.storage_path,
        "original_filename": document.original_filename,
        "category_id": document.category_id,
        "subcategory": document.subcategory,
        "tags": document.tags.split(",") if document.tags else [],
        "responsible_id": document.responsible_id,
        "department": document.department,
        "access_classification": document.access_classification.value,
        "uploaded_by_user_id": document.uploaded_by_user_id,
        "origin": document.origin,
        "is_official": document.is_official,
        "file_hash": document.file_hash,
        "document_id": document.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "warnings": [],
        "error": None,
        "error_stage": None,
        "status": "",
    }

    final_state = _run_pipeline(
        initial_state=initial_state,
        session=session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        settings=settings,
    )

    if final_state.get("status") == "success" and settings.auto_approve_on_upload:
        _auto_approve(document, session=session, vector_repository=vector_repository)

    return IngestionResult(
        status=final_state.get("status", "failed"),
        document_id=document.id,
        version_id=version.id,
        chunks_indexed=final_state.get("chunks_indexed", 0),
        warnings=final_state.get("warnings") or [],
        error=final_state.get("error"),
    )


def _auto_approve(document: Document, *, session: Session, vector_repository: VectorRepository) -> None:
    """Aprova o documento automaticamente quando `AUTO_APPROVE_ON_UPLOAD=true`
    (secao 8 e 29): passa pela MESMA maquina de estados e trilha de
    auditoria da aprovacao manual — apenas sem exigir o clique do curador.
    Falhas aqui sao registradas mas nunca derrubam o resultado da ingestao
    (o documento ja foi processado com sucesso; ele so fica pendente de
    aprovacao manual como fallback, comportamento identico ao padrao)."""
    try:
        change_document_status(
            document_id=document.id,
            new_status=CurationStatus.APPROVED,
            session=session,
            actor_user_id=document.uploaded_by_user_id or "system",
            vector_repository=vector_repository,
            reason="Aprovacao automatica (AUTO_APPROVE_ON_UPLOAD=true)",
        )
        logger.info("ingestion.auto_approved", document_id=document.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingestion.auto_approve_failed", document_id=document.id, error=str(exc))


def ingest_new_document(
    *,
    original_filename: str,
    raw_bytes: bytes,
    session: Session,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    category_id: str | None = None,
    subcategory: str | None = None,
    tags: list[str] | None = None,
    responsible_id: str | None = None,
    department: str | None = None,
    access_classification: str = "internal",
    is_official: bool = False,
    origin: str = "upload",
    uploaded_by_user_id: str | None = None,
    settings: Settings | None = None,
) -> IngestionResult:
    """Registra e processa um documento novo em uma unica chamada sincrona
    (usado por scripts, pasta monitorada e testes)."""
    settings = settings or get_settings()

    registered = register_document(
        original_filename=original_filename,
        raw_bytes=raw_bytes,
        session=session,
        category_id=category_id,
        subcategory=subcategory,
        tags=tags,
        responsible_id=responsible_id,
        department=department,
        access_classification=access_classification,
        is_official=is_official,
        origin=origin,
        uploaded_by_user_id=uploaded_by_user_id,
        settings=settings,
    )
    if registered.status == "duplicate":
        return IngestionResult(
            status="duplicate",
            document_id=None,
            version_id=None,
            duplicate_of_document_id=registered.duplicate_of_document_id,
        )

    return process_document_version(
        document_id=registered.document_id,
        version_id=registered.version_id,
        session=session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        settings=settings,
    )


def reindex_document(
    *,
    document_id: str,
    session: Session,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    settings: Settings | None = None,
) -> IngestionResult:
    """Reprocessa a versao ativa de um documento (ex: apos mudanca de modelo
    de embedding ou corrupcao do indice). Remove os vetores existentes da
    versao antes de reindexar, para nunca duplicar chunks (secao 16)."""
    settings = settings or get_settings()

    document = session.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Documento '{document_id}' nao encontrado.")

    version_id = resolve_version_to_process(document, session)
    vector_repository.delete_by_version(version_id)

    return process_document_version(
        document_id=document_id,
        version_id=version_id,
        session=session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        settings=settings,
    )


def reingest_document_version(
    *,
    document_id: str,
    original_filename: str,
    raw_bytes: bytes,
    session: Session,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    settings: Settings | None = None,
) -> IngestionResult:
    """Cria uma nova versao de um documento existente (secao 40).

    A versao anterior permanece no banco relacional para historico, mas seus
    vetores sao removidos do indice apos a nova versao ser indexada com
    sucesso, para nunca misturar chunks antigos e novos numa mesma consulta.
    """
    settings = settings or get_settings()
    settings.ensure_runtime_directories()

    document = session.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Documento '{document_id}' nao encontrado.")

    validate_upload(
        filename=original_filename,
        content=raw_bytes,
        allowed_extensions=settings.allowed_extensions_list,
        max_size_mb=settings.max_upload_size_mb,
    )

    previous_active_version_id = document.active_version_id
    file_hash = compute_file_hash(raw_bytes)
    destination = _save_upload(raw_bytes, original_filename, settings)

    latest_version_number = session.exec(
        select(DocumentVersion.version_number)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    ).first()
    next_version_number = (latest_version_number or 0) + 1

    version = DocumentVersion(
        document_id=document_id,
        version_number=next_version_number,
        storage_path=str(destination),
        content_hash="",
    )
    session.add(version)
    document.file_hash = file_hash
    session.add(document)
    session.commit()
    session.refresh(version)

    result = process_document_version(
        document_id=document_id,
        version_id=version.id,
        session=session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        settings=settings,
    )

    if result.status == "success" and previous_active_version_id:
        vector_repository.delete_by_version(previous_active_version_id)
        logger.info(
            "ingestion.previous_version_vectors_removed",
            document_id=document_id,
            previous_version_id=previous_active_version_id,
        )

    return result
