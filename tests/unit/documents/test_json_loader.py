from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import EmptyDocumentError
from app.documents.loaders.json_loader import JSONLoader


def test_preserves_field_path_for_nested_scalars(fixtures_dir: Path) -> None:
    loader = JSONLoader()
    result = loader.load(fixtures_dir / "sample_config.json")

    paths = {s.json_path for s in result.sections}
    assert "planos.profissional" in paths  # dict "flat" agrupado em uma secao
    section = next(s for s in result.sections if s.json_path == "planos.profissional")
    assert "preco: 199.9" in section.text


def test_list_of_records_grouped_per_item(fixtures_dir: Path) -> None:
    loader = JSONLoader()
    result = loader.load(fixtures_dir / "sample_config.json")

    contact_sections = [s for s in result.sections if s.json_path and "contatos" in s.json_path]
    assert len(contact_sections) == 2
    assert any("suporte@example.com" in s.text for s in contact_sections)


def test_empty_json_raises_domain_error(fixtures_dir: Path) -> None:
    loader = JSONLoader()
    with pytest.raises(EmptyDocumentError):
        loader.load(fixtures_dir / "empty.json")
