from __future__ import annotations

from app.database.models import Document
from app.database.models.enums import CurationStatus
from app.ingestion.service import ingest_new_document
from app.retrieval.hybrid_search import hybrid_search


def _ingest_and_approve(
    fixture_name: str,
    fixtures_dir,
    db_session,
    embedding_provider,
    vector_repository,
    test_settings,
    *,
    approve: bool = True,
):
    content = (fixtures_dir / fixture_name).read_bytes()
    result = ingest_new_document(
        original_filename=fixture_name,
        raw_bytes=content,
        session=db_session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        settings=test_settings,
    )
    assert result.status == "success", result.error

    document = db_session.get(Document, result.document_id)
    if approve:
        document.status = CurationStatus.APPROVED
    db_session.add(document)
    db_session.commit()
    return result


def test_hybrid_search_returns_relevant_approved_content(
    fixtures_dir, db_session, embedding_provider, vector_repository, reranker, test_settings
) -> None:
    _ingest_and_approve(
        "sample_policy.pdf", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings,
    )
    _ingest_and_approve(
        "sample_page.html", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings,
    )

    results = hybrid_search(
        "Qual o prazo para solicitar reembolso?",
        session=db_session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        reranker=reranker,
        settings=test_settings,
    )

    assert len(results) > 0
    assert any("7 dias" in r.text for r in results)


def test_hybrid_search_excludes_pending_review_documents(
    fixtures_dir, db_session, embedding_provider, vector_repository, reranker, test_settings
) -> None:
    _ingest_and_approve(
        "sample_policy.pdf", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings, approve=False,
    )

    results = hybrid_search(
        "Qual o prazo para solicitar reembolso?",
        session=db_session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        reranker=reranker,
        settings=test_settings,
    )

    assert results == []
