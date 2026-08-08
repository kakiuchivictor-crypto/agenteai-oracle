from __future__ import annotations

from pathlib import Path

from app.documents.loaders.powerpoint_loader import PowerPointLoader


def test_extracts_title_content_and_notes_per_slide(fixtures_dir: Path) -> None:
    loader = PowerPointLoader()
    result = loader.load(fixtures_dir / "sample_deck.pptx")

    assert result.has_content
    slide_numbers = {s.slide for s in result.sections}
    assert slide_numbers == {1, 2}

    slide1_texts = " ".join(s.text for s in result.sections if s.slide == 1)
    assert "Plataforma SaaS" in slide1_texts
    assert "periodo de teste gratuito" in slide1_texts  # nota do apresentador
