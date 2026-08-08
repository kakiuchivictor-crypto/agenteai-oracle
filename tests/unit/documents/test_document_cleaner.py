from __future__ import annotations

from app.documents.cleaners.document_cleaner import clean_document
from app.schemas.document import DocumentSection, ExtractedDocument


def _page_section(page: int, body: str) -> DocumentSection:
    return DocumentSection(
        text=f"Manual Corporativo Confidencial\n{body}\nPagina {page} de 4", page=page
    )


def test_detects_and_removes_repeated_header_and_footer() -> None:
    extracted = ExtractedDocument(
        source_path="doc.pdf",
        document_format="pdf",
        sections=[
            _page_section(1, "Conteudo da primeira pagina."),
            _page_section(2, "Conteudo da segunda pagina."),
            _page_section(3, "Conteudo da terceira pagina."),
            _page_section(4, "Conteudo da quarta pagina."),
        ],
    )

    cleaned = clean_document(extracted)

    assert "manual corporativo confidencial" in cleaned.removed_header_footer_lines
    for section in cleaned.sections:
        assert "Manual Corporativo Confidencial" not in section.normalized_text


def test_does_not_touch_non_paginated_sections() -> None:
    extracted = ExtractedDocument(
        source_path="doc.md",
        document_format="markdown",
        sections=[DocumentSection(text="Titulo", section="Titulo")],
    )
    cleaned = clean_document(extracted)
    assert cleaned.sections[0].normalized_text == "Titulo"
    assert cleaned.removed_header_footer_lines == []


def test_drops_sections_that_become_empty_after_cleaning() -> None:
    extracted = ExtractedDocument(
        source_path="doc.pdf",
        document_format="pdf",
        sections=[DocumentSection(text="   \n\n  ", page=1)],
    )
    cleaned = clean_document(extracted)
    assert cleaned.sections == []
