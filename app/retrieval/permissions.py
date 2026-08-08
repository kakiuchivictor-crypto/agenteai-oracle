"""Aplicacao do status de curadoria sobre resultados de busca (secao 8).

Os metadados gravados no banco vetorial no momento da indexacao (status do
documento) podem ficar desatualizados assim que um documento e aprovado ou
rejeitado depois da ingestao — o Chroma nao e resincronizado automaticamente
a cada mudanca de status. Por isso, o status e sempre verificado aqui contra
o banco relacional (fonte da verdade), nunca confiando apenas nos metadados
do vetor.

Regras aplicadas: somente documentos `APPROVED` e apenas chunks da versao
atualmente ativa do documento (nunca uma versao antiga/substituida). O
sistema e de uso livre (sem login/RBAC) — nao ha restricao por classificacao
de acesso ou papel de usuario.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.database.models import Document
from app.database.models.enums import CurationStatus
from app.schemas.vector import SearchResult


class CategorizedResults:
    """Resultado da checagem de curadoria, separado por motivo de exclusao.
    Permite ao chamador informar ao usuario a razao correta — "ainda em
    revisao" e "sem evidencia" sao situacoes diferentes e nao devem
    compartilhar a mesma mensagem."""

    def __init__(self, authorized: list[SearchResult], pending_approval: list[SearchResult]) -> None:
        self.authorized = authorized
        self.pending_approval = pending_approval


def categorize_results(results: list[SearchResult], *, session: Session) -> CategorizedResults:
    if not results:
        return CategorizedResults([], [])

    document_ids = {
        result.metadata.get("document_id")
        for result in results
        if result.metadata.get("document_id")
    }
    if not document_ids:
        return CategorizedResults([], [])

    documents = session.exec(select(Document).where(Document.id.in_(document_ids))).all()
    documents_by_id = {document.id: document for document in documents}

    authorized: list[SearchResult] = []
    pending_approval: list[SearchResult] = []

    for result in results:
        document = documents_by_id.get(result.metadata.get("document_id"))
        if document is None:
            continue
        version_id = result.metadata.get("version_id")
        if document.active_version_id and version_id and version_id != document.active_version_id:
            # Versao substituida/obsoleta: nunca exibida, em nenhuma categoria.
            continue
        if document.status != CurationStatus.APPROVED:
            pending_approval.append(result)
            continue
        authorized.append(result)

    return CategorizedResults(authorized, pending_approval)


def filter_authorized_results(results: list[SearchResult], *, session: Session) -> list[SearchResult]:
    """Mantido para chamadores que so precisam da lista final autorizada
    (ex: Fase 4, busca hibrida fora do agente conversacional)."""
    return categorize_results(results, session=session).authorized
