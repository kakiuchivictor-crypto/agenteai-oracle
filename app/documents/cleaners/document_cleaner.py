"""Limpeza em nivel de documento: aplica `clean_text` por secao e detecta
cabecalhos/rodapes repetidos entre paginas (secao 12 do prompt mestre).

A deteccao de cabecalho/rodape so atua quando ha pelo menos 3 secoes
associadas a uma pagina (tipicamente PDFs) e a mesma linha se repete como
primeira/ultima linha em pelo menos 60% delas — evita falsos positivos em
documentos curtos ou com conteudo pouco repetitivo.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from app.documents.cleaners.text_cleaner import CleaningConfig, clean_text
from app.schemas.document import DocumentSection, ExtractedDocument

_MIN_PAGES_FOR_HEADER_FOOTER_DETECTION = 3
_REPETITION_RATIO_THRESHOLD = 0.6


class CleanedSection(BaseModel):
    original_text: str
    normalized_text: str
    page: int | None = None
    section: str | None = None
    slide: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    table_name: str | None = None
    json_path: str | None = None
    is_ocr: bool = False


class CleanedDocument(BaseModel):
    sections: list[CleanedSection]
    removed_header_footer_lines: list[str] = []


def _first_and_last_line(text: str) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return None, None
    return lines[0], lines[-1]


def _detect_repeated_lines(paged_texts: list[str]) -> set[str]:
    if len(paged_texts) < _MIN_PAGES_FOR_HEADER_FOOTER_DETECTION:
        return set()

    first_lines: Counter[str] = Counter()
    last_lines: Counter[str] = Counter()
    for text in paged_texts:
        first, last = _first_and_last_line(text)
        if first:
            first_lines[first.lower()] += 1
        if last:
            last_lines[last.lower()] += 1

    threshold = max(2, int(len(paged_texts) * _REPETITION_RATIO_THRESHOLD))
    repeated = {line for line, count in first_lines.items() if count >= threshold}
    repeated |= {line for line, count in last_lines.items() if count >= threshold}
    return repeated


def _strip_repeated_lines(text: str, repeated_lines: set[str]) -> str:
    if not repeated_lines:
        return text
    lines = text.split("\n")
    kept = [line for line in lines if line.strip().lower() not in repeated_lines]
    return "\n".join(kept).strip()


def clean_document(
    extracted: ExtractedDocument, config: CleaningConfig | None = None
) -> CleanedDocument:
    cleaning_results = [clean_text(section.text, config) for section in extracted.sections]

    paged_texts = [
        result.normalized_text
        for section, result in zip(extracted.sections, cleaning_results, strict=True)
        if section.page is not None
    ]
    repeated_lines = _detect_repeated_lines(paged_texts)

    cleaned_sections: list[CleanedSection] = []
    for section, result in zip(extracted.sections, cleaning_results, strict=True):
        normalized = (
            _strip_repeated_lines(result.normalized_text, repeated_lines)
            if section.page is not None
            else result.normalized_text
        )
        if not normalized.strip():
            continue
        cleaned_sections.append(_to_cleaned_section(section, result.original_text, normalized))

    return CleanedDocument(
        sections=cleaned_sections, removed_header_footer_lines=sorted(repeated_lines)
    )


def _to_cleaned_section(
    section: DocumentSection, original_text: str, normalized_text: str
) -> CleanedSection:
    return CleanedSection(
        original_text=original_text,
        normalized_text=normalized_text,
        page=section.page,
        section=section.section,
        slide=section.slide,
        sheet_name=section.sheet_name,
        row_number=section.row_number,
        table_name=section.table_name,
        json_path=section.json_path,
        is_ocr=section.is_ocr,
    )
