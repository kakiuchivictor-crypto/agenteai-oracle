"""Mudancas de status de curadoria com trilha de auditoria (secoes 8 e 29)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlmodel import Session

from app.core.exceptions import DocumentNotFoundError
from app.database.models import AuditEvent, Document
from app.database.models.enums import CurationStatus
from app.documents.validators.curation import validate_transition
from app.vectorstores.base import VectorRepository


def change_document_status(
    *,
    document_id: str,
    new_status: CurationStatus,
    session: Session,
    actor_user_id: str,
    vector_repository: VectorRepository | None = None,
    reason: str | None = None,
) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Documento '{document_id}' nao encontrado.")

    validate_transition(document.status, new_status)
    previous_status = document.status
    document.status = new_status
    document.updated_at = datetime.now(UTC)
    if new_status == CurationStatus.APPROVED:
        document.approved_at = datetime.now(UTC)
        document.approved_by_user_id = actor_user_id

    # Remocao logica: quando um documento aprovado deixa de estar vigente
    # (rejeitado, arquivado, marcado como duplicata), seus vetores saem do
    # indice imediatamente — a resposta a perguntas nao pode usar conteudo
    # nao aprovado, mesmo que o registro relacional seja mantido para
    # historico/auditoria (secao 8 e 29).
    if (
        vector_repository is not None
        and new_status != CurationStatus.APPROVED
        and document.active_version_id
    ):
        vector_repository.delete_by_version(document.active_version_id)

    session.add(document)
    session.add(
        AuditEvent(
            user_id=actor_user_id,
            action="document_status_change",
            resource_type="document",
            resource_id=document_id,
            details_json=json.dumps(
                {"from": previous_status.value, "to": new_status.value, "reason": reason}
            ),
        )
    )
    session.commit()
    session.refresh(document)
    return document


def delete_document(
    *,
    document_id: str,
    session: Session,
    actor_user_id: str,
    vector_repository: VectorRepository,
) -> Document:
    """Exclusao logica (secao 40): o documento e arquivado e seus vetores
    removidos do indice; o registro relacional permanece para auditoria."""
    document = change_document_status(
        document_id=document_id,
        new_status=CurationStatus.ARCHIVED,
        session=session,
        actor_user_id=actor_user_id,
        vector_repository=vector_repository,
        reason="Exclusao solicitada via API",
    )
    session.add(
        AuditEvent(
            user_id=actor_user_id,
            action="document_deleted",
            resource_type="document",
            resource_id=document_id,
        )
    )
    session.commit()
    return document
