from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.core.config import Settings
from app.database.models import DocumentChunk, DocumentVersion
from app.database.models.enums import CurationStatus, VersionIndexStatus
from app.embeddings.sentence_transformer_provider import SentenceTransformerEmbeddingProvider
from app.ingestion.service import ingest_new_document, reingest_document_version
from app.vectorstores.chroma_repository import ChromaVectorRepository


def _ingest(
    fixture_name: str,
    fixtures_dir: Path,
    db_session: Session,
    embedding_provider: SentenceTransformerEmbeddingProvider,
    vector_repository: ChromaVectorRepository,
    test_settings: Settings,
    **overrides,
):
    content = (fixtures_dir / fixture_name).read_bytes()
    return ingest_new_document(
        original_filename=fixture_name,
        raw_bytes=content,
        session=db_session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        settings=test_settings,
        **overrides,
    )


def test_ingests_pdf_end_to_end_and_indexes_vectors(
    fixtures_dir, db_session, embedding_provider, vector_repository, test_settings
) -> None:
    result = _ingest(
        "sample_policy.pdf", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings, category_id="cat-juridico", tags=["reembolso"],
    )

    assert result.status == "success"
    assert result.chunks_indexed > 0
    assert result.error is None

    version = db_session.get(DocumentVersion, result.version_id)
    assert version is not None
    assert version.index_status == VersionIndexStatus.INDEXED
    assert version.content_hash

    db_chunks = db_session.exec(
        select(DocumentChunk).where(DocumentChunk.version_id == result.version_id)
    ).all()
    assert len(db_chunks) == result.chunks_indexed
    assert vector_repository.count() == result.chunks_indexed


def test_new_document_defaults_to_pending_review(
    fixtures_dir, db_session, embedding_provider, vector_repository, test_settings
) -> None:
    from app.database.models import Document

    result = _ingest(
        "sample_readme.md", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings,
    )
    document = db_session.get(Document, result.document_id)
    assert document.status == CurationStatus.PENDING_REVIEW


def test_auto_approve_on_upload_when_enabled(
    fixtures_dir, db_session, embedding_provider, vector_repository, test_settings
) -> None:
    """Com AUTO_APPROVE_ON_UPLOAD=true, o documento fica aprovado assim que
    processado — sem exigir clique manual do curador — mas ainda passa pela
    trilha de auditoria normal (secao 8 e 29)."""
    from app.database.models import AuditEvent, Document

    auto_approve_settings = test_settings.model_copy(update={"auto_approve_on_upload": True})

    result = _ingest(
        "sample_readme.md", fixtures_dir, db_session, embedding_provider, vector_repository,
        auto_approve_settings,
    )

    assert result.status == "success"
    document = db_session.get(Document, result.document_id)
    assert document.status == CurationStatus.APPROVED
    assert document.approved_at is not None

    audit_events = db_session.exec(
        select(AuditEvent).where(AuditEvent.resource_id == result.document_id)
    ).all()
    assert any(e.action == "document_status_change" for e in audit_events)


def test_document_stays_pending_when_auto_approve_disabled(
    fixtures_dir, db_session, embedding_provider, vector_repository, test_settings
) -> None:
    from app.database.models import Document

    assert test_settings.auto_approve_on_upload is False
    result = _ingest(
        "sample_readme.md", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings,
    )
    document = db_session.get(Document, result.document_id)
    assert document.status == CurationStatus.PENDING_REVIEW


def test_duplicate_file_is_detected_and_skipped(
    fixtures_dir, db_session, embedding_provider, vector_repository, test_settings
) -> None:
    first = _ingest(
        "sample_data.csv", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings,
    )
    second = _ingest(
        "sample_data.csv", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings,
    )

    assert first.status == "success"
    assert second.status == "duplicate"
    assert second.duplicate_of_document_id == first.document_id
    assert second.version_id is None


def test_corrupted_file_fails_without_crashing_and_logs_error(
    fixtures_dir, db_session, embedding_provider, vector_repository, test_settings
) -> None:
    result = _ingest(
        "corrupted.pdf", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings,
    )

    assert result.status == "failed"
    assert result.error is not None

    version = db_session.get(DocumentVersion, result.version_id)
    assert version.index_status == VersionIndexStatus.FAILED
    assert version.error_message == result.error


def test_reingest_creates_new_version_and_removes_old_vectors(
    fixtures_dir, db_session, embedding_provider, vector_repository, test_settings
) -> None:
    first = _ingest(
        "sample_config.json", fixtures_dir, db_session, embedding_provider, vector_repository,
        test_settings,
    )
    assert first.status == "success"
    count_after_first = vector_repository.count()
    assert count_after_first > 0

    updated_json = (fixtures_dir / "sample_config.json").read_text(encoding="utf-8").replace(
        "199.9", "249.9"
    )
    second = reingest_document_version(
        document_id=first.document_id,
        original_filename="sample_config.json",
        raw_bytes=updated_json.encode("utf-8"),
        session=db_session,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        settings=test_settings,
    )

    assert second.status == "success"
    assert second.version_id != first.version_id

    from app.database.models import Document

    document = db_session.get(Document, first.document_id)
    assert document.active_version_id == second.version_id

    # vetores da versao antiga foram removidos; so os da nova versao restam
    remaining = vector_repository.search(
        query_vector=embedding_provider.embed_query("teste"), filters=None, limit=100
    )
    version_ids_in_index = {r.metadata.get("version_id") for r in remaining}
    assert first.version_id not in version_ids_in_index
    assert second.version_id in version_ids_in_index
