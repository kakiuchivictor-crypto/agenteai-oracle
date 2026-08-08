from __future__ import annotations

from app.documents.cleaners.text_cleaner import clean_text


def test_collapses_multiple_spaces_and_blank_lines() -> None:
    result = clean_text("Ola   mundo\n\n\n\nOutra linha")
    assert result.normalized_text == "Ola mundo\n\nOutra linha"
    assert result.report.collapsed_whitespace_runs >= 1


def test_removes_control_characters() -> None:
    result = clean_text("Texto\x00com\x07controle")
    assert "\x00" not in result.normalized_text
    assert "\x07" not in result.normalized_text
    assert result.report.removed_control_chars == 2


def test_removes_isolated_page_numbers() -> None:
    result = clean_text("Conteudo da pagina\n\n12\n\nMais conteudo")
    assert "12" not in result.normalized_text.split("\n")
    assert result.report.removed_isolated_page_number_lines == 1


def test_preserves_original_text_untouched() -> None:
    original = "Texto   com espacos"
    result = clean_text(original)
    assert result.original_text == original
