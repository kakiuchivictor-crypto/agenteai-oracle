from __future__ import annotations

from pathlib import Path

from app.documents.loaders.csv_loader import CSVLoader


def test_each_data_row_becomes_a_section_with_row_number(fixtures_dir: Path) -> None:
    loader = CSVLoader()
    result = loader.load(fixtures_dir / "sample_data.csv")

    assert len(result.sections) == 3
    first = result.sections[0]
    assert first.row_number == 2  # linha 1 e o cabecalho
    assert "produto: Camiseta" in first.text
    assert "preco: 49.90" in first.text
