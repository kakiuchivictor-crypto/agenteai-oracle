from __future__ import annotations

from pathlib import Path

from app.documents.loaders.html_loader import HTMLLoader


def test_removes_scripts_styles_and_repetitive_menus(fixtures_dir: Path) -> None:
    loader = HTMLLoader()
    result = loader.load(fixtures_dir / "sample_page.html")

    all_text = " ".join(s.text for s in result.sections)
    assert "console.log" not in all_text
    assert "Menu de navegacao repetitivo" not in all_text
    assert "Rodape repetitivo" not in all_text


def test_extracts_headings_lists_and_tables_with_hierarchy(fixtures_dir: Path) -> None:
    loader = HTMLLoader()
    result = loader.load(fixtures_dir / "sample_page.html")

    texts = [s.text for s in result.sections]
    assert "Perguntas Frequentes" in texts
    assert any(t.startswith("- Cartao de credito") for t in texts)
    assert any("Basico" in t and "R$ 49,90" in t for t in texts)

    payments_section = next(s for s in result.sections if "boleto bancario" in s.text)
    assert payments_section.section == "Perguntas Frequentes > Pagamentos"
