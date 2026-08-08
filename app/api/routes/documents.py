"""Rotas de documentos: upload, listagem, processamento e curadoria
(secoes 6, 8, 26, 39 e 40 do prompt mestre)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlmodel import Session, select

from app.api.dependencies.db import get_db_session
from app.api.dependencies.providers import get_embedding_provider_dep, get_vector_repository_dep
from app.core.exceptions import DocumentNotFoundError
from app.core.system_user import SYSTEM_USER_ID
from app.database.models import Document
from app.database.models.enums import CurationStatus
from app.embeddings.base import BaseEmbeddingProvider
from app.ingestion.service import (
    process_document_version,
    register_document,
    reindex_document,
    resolve_version_to_process,
)
from app.schemas.api.documents import (
    DocumentProcessResponse,
    DocumentResponse,
    DocumentStatusChangeRequest,
    DocumentUploadResponse,
)
from app.services.curation_service import change_document_status, delete_document
from app.vectorstores.base import VectorRepository

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_response(document: Document) -> DocumentResponse:
    return DocumentResponse.model_validate(document, from_attributes=True)


def _get_or_404(document_id: str, session: Session) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Documento '{document_id}' nao encontrado.")
    return document


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    category_id: str | None = Form(None),
    subcategory: str | None = Form(None),
    tags: str | None = Form(None),
    responsible_id: str | None = Form(None),
    department: str | None = Form(None),
    access_classification: str = Form("internal"),
    is_official: bool = Form(False),
    session: Session = Depends(get_db_session),
) -> DocumentUploadResponse:
    content = await file.read()
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else None

    result = register_document(
        original_filename=file.filename or "arquivo",
        raw_bytes=content,
        session=session,
        category_id=category_id,
        subcategory=subcategory,
        tags=tag_list,
        responsible_id=responsible_id,
        department=department,
        access_classification=access_classification,
        is_official=is_official,
        uploaded_by_user_id=SYSTEM_USER_ID,
    )
    return DocumentUploadResponse(
        status=result.status,
        document_id=result.document_id,
        version_id=result.version_id,
        duplicate_of_document_id=result.duplicate_of_document_id,
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    status_filter: CurationStatus | None = None,
    category_id: str | None = None,
    session: Session = Depends(get_db_session),
) -> list[DocumentResponse]:
    statement = select(Document)
    if status_filter is not None:
        statement = statement.where(Document.status == status_filter)
    if category_id is not None:
        statement = statement.where(Document.category_id == category_id)
    documents = session.exec(statement.order_by(Document.created_at.desc())).all()
    return [_to_response(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, session: Session = Depends(get_db_session)) -> DocumentResponse:
    return _to_response(_get_or_404(document_id, session))


@router.post("/{document_id}/process", response_model=DocumentProcessResponse)
def process_document(
    document_id: str,
    session: Session = Depends(get_db_session),
    embedding_provider: BaseEmbeddingProvider = Depends(get_embedding_provider_dep),
    vector_repository: VectorRepository = Depends(get_vector_repository_dep),
) -> DocumentProcessResponse:
    document = _get_or_404(document_id, session)
    version_id = resolve_version_to_process(document, session)
    result = process_document_version(
        document_id=document_id,
        version_id=version_id,
        session=session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
    )
    return DocumentProcessResponse(
        status=result.status, document_id=result.document_id, version_id=result.version_id,
        chunks_indexed=result.chunks_indexed, warnings=result.warnings, error=result.error,
    )


@router.post("/{document_id}/approve", response_model=DocumentResponse)
def approve_document(
    document_id: str,
    payload: DocumentStatusChangeRequest | None = None,
    session: Session = Depends(get_db_session),
    vector_repository: VectorRepository = Depends(get_vector_repository_dep),
) -> DocumentResponse:
    document = change_document_status(
        document_id=document_id, new_status=CurationStatus.APPROVED, session=session,
        actor_user_id=SYSTEM_USER_ID, vector_repository=vector_repository,
        reason=payload.reason if payload else None,
    )
    return _to_response(document)


@router.post("/{document_id}/reject", response_model=DocumentResponse)
def reject_document(
    document_id: str,
    payload: DocumentStatusChangeRequest | None = None,
    session: Session = Depends(get_db_session),
    vector_repository: VectorRepository = Depends(get_vector_repository_dep),
) -> DocumentResponse:
    document = change_document_status(
        document_id=document_id, new_status=CurationStatus.REJECTED, session=session,
        actor_user_id=SYSTEM_USER_ID, vector_repository=vector_repository,
        reason=payload.reason if payload else None,
    )
    return _to_response(document)


@router.post("/{document_id}/reindex", response_model=DocumentProcessResponse)
def reindex_document_endpoint(
    document_id: str,
    session: Session = Depends(get_db_session),
    embedding_provider: BaseEmbeddingProvider = Depends(get_embedding_provider_dep),
    vector_repository: VectorRepository = Depends(get_vector_repository_dep),
) -> DocumentProcessResponse:
    result = reindex_document(
        document_id=document_id, session=session, embedding_provider=embedding_provider,
        vector_repository=vector_repository,
    )
    return DocumentProcessResponse(
        status=result.status, document_id=result.document_id, version_id=result.version_id,
        chunks_indexed=result.chunks_indexed, warnings=result.warnings, error=result.error,
    )


@router.delete("/{document_id}", response_model=DocumentResponse)
def delete_document_endpoint(
    document_id: str,
    session: Session = Depends(get_db_session),
    vector_repository: VectorRepository = Depends(get_vector_repository_dep),
) -> DocumentResponse:
    document = delete_document(
        document_id=document_id, session=session, actor_user_id=SYSTEM_USER_ID,
        vector_repository=vector_repository,
    )
    return _to_response(document)
