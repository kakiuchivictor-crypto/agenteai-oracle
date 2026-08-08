from __future__ import annotations

from app.documents.metadata.chunk_metadata import ChunkContext, build_vector_metadata
from app.schemas.chunk import Chunk


def _context(**overrides) -> ChunkContext:
    defaults = dict(
        document_id="doc-1",
        version_id="ver-1",
        original_filename="politica.pdf",
        document_format="pdf",
        category="Juridico",
        status="approved",
        is_official=True,
        access_classification="internal",
        version_number=1,
    )
    defaults.update(overrides)
    return ChunkContext(**defaults)


def test_builds_flat_metadata_without_none_values() -> None:
    chunk = Chunk(chunk_index=0, text="conteudo", char_count=8, page=3)
    metadata = build_vector_metadata(chunk, _context())

    assert metadata["document_id"] == "doc-1"
    assert metadata["page"] == 3
    assert None not in metadata.values()
    assert "slide" not in metadata  # nao aplicavel a PDF, nao deve aparecer


def test_serializes_tags_as_comma_separated_string() -> None:
    chunk = Chunk(chunk_index=0, text="conteudo", char_count=8)
    metadata = build_vector_metadata(chunk, _context(tags=["financeiro", "urgente"]))
    assert metadata["tags"] == "financeiro,urgente"


def test_only_scalar_types_in_output() -> None:
    chunk = Chunk(chunk_index=0, text="conteudo", char_count=8, slide=2)
    metadata = build_vector_metadata(chunk, _context())
    assert all(isinstance(v, str | int | float | bool) for v in metadata.values())
