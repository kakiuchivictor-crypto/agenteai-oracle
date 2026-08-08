from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import CorruptedFileError
from app.documents.loaders.word_loader import WordLoader


def test_extracts_headings_paragraphs_lists_and_tables(fixtures_dir: Path) -> None:
    loader = WordLoader()
    result = loader.load(fixtures_dir / "sample_word.docx")

    assert result.has_content
    texts = [s.text for s in result.sections]
    assert "Politica de Privacidade" in texts
    assert any(t.startswith("- ") for t in texts)  # item de lista
    assert any("Finalidade" in t for t in texts)  # tabela

    heading_section = next(s for s in result.sections if s.text == "Coleta de dados")
    assert heading_section.section == "Coleta de dados"


def test_corrupted_docx_raises_domain_error(fixtures_dir: Path) -> None:
    loader = WordLoader()
    with pytest.raises(CorruptedFileError):
        loader.load(fixtures_dir / "corrupted.docx")
