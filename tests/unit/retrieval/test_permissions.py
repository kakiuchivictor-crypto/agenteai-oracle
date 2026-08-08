from __future__ import annotations

from app.database.models import Document
from app.database.models.enums import AccessClassification, CurationStatus, DocumentFormat
from app.retrieval.permissions import categorize_results, filter_authorized_results
from app.schemas.vector import SearchResult


def _make_document(
    session, *, status: CurationStatus, active_version_id: str = "v1"
) -> Document:
    document = Document(
        original_filename="doc.pdf",
        format=DocumentFormat.PDF,
        file_hash=f"hash-{status}-{active_version_id}",
        status=status,
        access_classification=AccessClassification.INTERNAL,
        active_version_id=active_version_id,
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def _result_for(document_id: str, version_id: str = "v1") -> SearchResult:
    return SearchResult(
        id=f"{version_id}:0",
        text="conteudo",
        metadata={"document_id": document_id, "version_id": version_id},
        score=0.9,
    )


def test_keeps_only_approved_documents(db_session) -> None:
    approved = _make_document(db_session, status=CurationStatus.APPROVED)
    pending = _make_document(db_session, status=CurationStatus.PENDING_REVIEW)

    results = [_result_for(approved.id), _result_for(pending.id)]
    authorized = filter_authorized_results(results, session=db_session)

    assert len(authorized) == 1
    assert authorized[0].metadata["document_id"] == approved.id


def test_excludes_chunks_from_non_active_version(db_session) -> None:
    document = _make_document(db_session, status=CurationStatus.APPROVED, active_version_id="v2")

    stale_result = _result_for(document.id, version_id="v1")
    current_result = _result_for(document.id, version_id="v2")

    authorized = filter_authorized_results([stale_result, current_result], session=db_session)

    assert len(authorized) == 1
    assert authorized[0].metadata["version_id"] == "v2"


def test_unknown_document_id_is_excluded(db_session) -> None:
    results = [_result_for("does-not-exist")]
    authorized = filter_authorized_results(results, session=db_session)
    assert authorized == []


def test_categorize_separates_authorized_from_pending_approval(db_session) -> None:
    pending = _make_document(db_session, status=CurationStatus.PENDING_REVIEW)
    approved = _make_document(db_session, status=CurationStatus.APPROVED, active_version_id="v1-approved")

    results = [_result_for(pending.id), _result_for(approved.id, version_id="v1-approved")]

    categorized = categorize_results(results, session=db_session)

    assert len(categorized.authorized) == 1
    assert categorized.authorized[0].metadata["document_id"] == approved.id
    assert len(categorized.pending_approval) == 1
    assert categorized.pending_approval[0].metadata["document_id"] == pending.id


def test_categorize_excludes_stale_version_from_every_category(db_session) -> None:
    document = _make_document(db_session, status=CurationStatus.PENDING_REVIEW, active_version_id="v2")
    stale_result = _result_for(document.id, version_id="v1")

    categorized = categorize_results([stale_result], session=db_session)
    assert categorized.authorized == []
    assert categorized.pending_approval == []
