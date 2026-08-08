from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import CorruptedFileError
from app.documents.loaders.pdf_loader import PDFLoader


def test_supports_only_pdf(fixtures_dir: Path) -> None:
    loader = PDFLoader()
    assert loader.supports(fixtures_dir / "sample_policy.pdf")
    assert not loader.supports(fixtures_dir / "sample_word.docx")


def test_extracts_text_preserving_page_numbers(fixtures_dir: Path) -> None:
    loader = PDFLoader()
    result = loader.load(fixtures_dir / "sample_policy.pdf")

    assert result.document_format == "pdf"
    assert result.has_content
    pages = {section.page for section in result.sections}
    assert pages == {1, 2}
    assert any("Reembolso" in section.text for section in result.sections)
    assert any("Estornos" in section.text for section in result.sections)


def test_scanned_pdf_without_ocr_generates_warning(fixtures_dir: Path) -> None:
    loader = PDFLoader()
    result = loader.load(fixtures_dir / "sample_scanned.pdf")

    # Sem Tesseract instalado no ambiente de teste, a pagina sem texto deve
    # gerar um aviso em vez de derrubar o pipeline.
    assert len(result.warnings) >= 1
    assert any(w.code in {"ocr_needed_but_disabled", "empty_page"} for w in result.warnings)


def test_corrupted_pdf_raises_domain_error(fixtures_dir: Path) -> None:
    loader = PDFLoader()
    with pytest.raises(CorruptedFileError):
        loader.load(fixtures_dir / "corrupted.pdf")
