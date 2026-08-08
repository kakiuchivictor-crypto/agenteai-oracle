from __future__ import annotations

from pathlib import Path

from app.documents.loaders.excel_loader import ExcelLoader


def test_each_row_becomes_a_readable_section(fixtures_dir: Path) -> None:
    loader = ExcelLoader()
    result = loader.load(fixtures_dir / "sample_plans.xlsx")

    assert len(result.sections) == 2  # 2 linhas de dados (sem contar cabecalho)
    first = result.sections[0]
    assert first.sheet_name == "Planos"
    assert first.row_number == 2
    assert "Plano: Profissional" in first.text
    assert "Preco mensal: R$ 199,90" in first.text
    assert "Planilha: Planos" in first.text

    # Nao deve concatenar a planilha inteira em um unico bloco.
    all_texts = {s.text for s in result.sections}
    assert len(all_texts) == len(result.sections)
