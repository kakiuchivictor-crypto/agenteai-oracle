from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import EmptyDocumentError
from app.documents.loaders.markdown_loader import MarkdownLoader


def test_extracts_headings_lists_and_code_blocks(fixtures_dir: Path) -> None:
    loader = MarkdownLoader()
    result = loader.load(fixtures_dir / "sample_readme.md")

    texts = [s.text for s in result.sections]
    assert "Guia da Plataforma" in texts
    assert any("Crie sua conta" in t for t in texts)
    assert any("modo: producao" in t for t in texts)  # bloco de codigo preservado

    nested = next(s for s in result.sections if "Confirme o e-mail" in s.text)
    assert nested.section == "Guia da Plataforma > Primeiros passos"


def test_empty_markdown_raises_domain_error(fixtures_dir: Path) -> None:
    loader = MarkdownLoader()
    with pytest.raises(EmptyDocumentError):
        loader.load(fixtures_dir / "empty.md")
