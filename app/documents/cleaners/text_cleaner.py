"""Limpeza configuravel de texto (secao 12 do prompt mestre).

A limpeza e deliberadamente conservadora: remove ruido estrutural (espacos
duplicados, caracteres de controle, numeracao de pagina isolada) sem
eliminar conteudo. O relatorio de transformacoes permite auditar o que foi
alterado em relacao ao texto original.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel

# Caracteres de controle exceto \n e \t.
_CONTROL_CHARS_PATTERN = re.compile(
    "[" + "".join(chr(c) for c in range(0, 32) if chr(c) not in "\n\t") + chr(127) + "]"
)
_MULTIPLE_SPACES_PATTERN = re.compile(r"[ \t]{2,}")
_MULTIPLE_BLANK_LINES_PATTERN = re.compile(r"\n{3,}")
_ISOLATED_PAGE_NUMBER_PATTERN = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")


class CleaningConfig(BaseModel):
    remove_control_chars: bool = True
    collapse_whitespace: bool = True
    remove_isolated_page_numbers: bool = True
    normalize_unicode: bool = True


class CleaningReport(BaseModel):
    original_char_count: int
    normalized_char_count: int
    removed_control_chars: int = 0
    removed_isolated_page_number_lines: int = 0
    collapsed_whitespace_runs: int = 0


class CleaningResult(BaseModel):
    original_text: str
    normalized_text: str
    report: CleaningReport


def clean_text(text: str, config: CleaningConfig | None = None) -> CleaningResult:
    """Limpa um trecho de texto preservando o original para auditoria."""
    config = config or CleaningConfig()
    original_text = text
    working = text

    removed_control_chars = 0
    if config.remove_control_chars:
        working, removed_control_chars = _count_and_sub(_CONTROL_CHARS_PATTERN, "", working)

    if config.normalize_unicode:
        working = unicodedata.normalize("NFC", working)

    removed_page_number_lines = 0
    if config.remove_isolated_page_numbers:
        lines = working.split("\n")
        kept_lines = []
        for line in lines:
            if _ISOLATED_PAGE_NUMBER_PATTERN.match(line):
                removed_page_number_lines += 1
                continue
            kept_lines.append(line)
        working = "\n".join(kept_lines)

    collapsed_runs = 0
    if config.collapse_whitespace:
        working, collapsed_spaces = _count_and_sub(_MULTIPLE_SPACES_PATTERN, " ", working)
        working, collapsed_blank_lines = _count_and_sub(_MULTIPLE_BLANK_LINES_PATTERN, "\n\n", working)
        collapsed_runs = collapsed_spaces + collapsed_blank_lines
        working = "\n".join(line.rstrip() for line in working.split("\n"))

    working = working.strip()

    report = CleaningReport(
        original_char_count=len(original_text),
        normalized_char_count=len(working),
        removed_control_chars=removed_control_chars,
        removed_isolated_page_number_lines=removed_page_number_lines,
        collapsed_whitespace_runs=collapsed_runs,
    )
    return CleaningResult(original_text=original_text, normalized_text=working, report=report)


def _count_and_sub(pattern: re.Pattern[str], replacement: str, text: str) -> tuple[str, int]:
    count = len(pattern.findall(text))
    return pattern.sub(replacement, text), count
