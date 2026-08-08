from __future__ import annotations

from app.documents.chunkers.hybrid_chunker import chunk_sections
from app.documents.cleaners.document_cleaner import CleanedSection


def _section(text: str, **kwargs) -> CleanedSection:
    return CleanedSection(original_text=text, normalized_text=text, **kwargs)


def test_merges_small_prose_sections_under_same_heading() -> None:
    sections = [
        _section("Paragrafo um.", section="Introducao"),
        _section("Paragrafo dois.", section="Introducao"),
        _section("Paragrafo tres.", section="Introducao"),
    ]
    chunks = chunk_sections(sections, chunk_size=1000, chunk_overlap=50, max_chunk_size=2000)

    assert len(chunks) == 1
    assert "Paragrafo um." in chunks[0].text
    assert "Paragrafo tres." in chunks[0].text
    assert chunks[0].section == "Introducao"


def test_starts_new_chunk_when_heading_changes() -> None:
    sections = [
        _section("Conteudo A.", section="Secao A"),
        _section("Conteudo B.", section="Secao B"),
    ]
    chunks = chunk_sections(sections, chunk_size=1000, chunk_overlap=50, max_chunk_size=2000)

    assert len(chunks) == 2
    assert chunks[0].section == "Secao A"
    assert chunks[1].section == "Secao B"


def test_atomic_rows_never_merge_with_neighbors() -> None:
    sections = [
        _section("Linha 1: valor A", row_number=2, sheet_name="Planilha1"),
        _section("Linha 2: valor B", row_number=3, sheet_name="Planilha1"),
    ]
    chunks = chunk_sections(sections, chunk_size=1000, chunk_overlap=50, max_chunk_size=2000)

    assert len(chunks) == 2
    assert chunks[0].row_number == 2
    assert chunks[1].row_number == 3


def test_splits_oversized_section_with_overlap() -> None:
    long_text = ("Frase numero %d sobre o assunto. " % i for i in range(200))
    text = "".join(long_text)
    sections = [_section(text, section="Secao Longa")]

    chunks = chunk_sections(sections, chunk_size=200, chunk_overlap=40, max_chunk_size=250)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 250
        assert chunk.section == "Secao Longa"


def test_chunk_index_is_sequential() -> None:
    sections = [
        _section("A", section="S1"),
        _section("B", section="S2"),
        _section("C", section="S3"),
    ]
    chunks = chunk_sections(sections, chunk_size=1000, chunk_overlap=0, max_chunk_size=2000)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_flushes_prose_buffer_when_chunk_size_exceeded_even_within_same_section() -> None:
    sections = [
        _section("x" * 80, section="S1"),
        _section("y" * 80, section="S1"),
        _section("z" * 80, section="S1"),
    ]
    chunks = chunk_sections(sections, chunk_size=100, chunk_overlap=10, max_chunk_size=500)

    # 80 + 80 + separadores > 100, entao deve quebrar em mais de um chunk
    assert len(chunks) >= 2
    assert all(c.section == "S1" for c in chunks)
