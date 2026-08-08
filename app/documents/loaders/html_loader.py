"""Carregador de arquivos HTML (secao 5.8 do prompt mestre).

Remove scripts, estilos e menus repetitivos (nav/header/footer/aside),
extrai titulos, paragrafos, listas e tabelas, preservando a hierarquia de
titulos no campo `section` (formato `H1 > H2 > ...`).
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from app.core.exceptions import EmptyDocumentError
from app.documents.loaders.base import DocumentLoader
from app.schemas.document import DocumentSection, ExtractedDocument, ExtractionWarning

_REMOVED_TAGS = ("script", "style", "nav", "header", "footer", "aside", "noscript")
_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_TARGET_TAGS = (*_HEADING_TAGS, "p", "ul", "ol", "table")


def _table_to_text(table_tag) -> str:
    rows_text = []
    for row_index, row in enumerate(table_tag.find_all("tr")):
        cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
        if not any(cells):
            continue
        prefix = "Cabecalho" if row_index == 0 else f"Linha {row_index}"
        rows_text.append(f"{prefix}: " + " | ".join(cells))
    return "\n".join(rows_text)


def _list_to_text(list_tag) -> str:
    items = [item.get_text(strip=True) for item in list_tag.find_all("li")]
    return "\n".join(f"- {item}" for item in items if item)


class HTMLLoader(DocumentLoader):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in {".html", ".htm"}

    def load(self, file_path: Path) -> ExtractedDocument:
        try:
            raw_html = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_html = file_path.read_text(encoding="latin-1")

        if not raw_html.strip():
            raise EmptyDocumentError(f"Arquivo HTML vazio: {file_path.name}")

        soup = BeautifulSoup(raw_html, "lxml")
        for tag in soup.find_all(_REMOVED_TAGS):
            tag.decompose()

        sections: list[DocumentSection] = []
        warnings: list[ExtractionWarning] = []
        heading_stack: list[tuple[int, str]] = []

        def current_section_path() -> str | None:
            return " > ".join(text for _, text in heading_stack) or None

        for tag in soup.find_all(_TARGET_TAGS):
            # Evita duplicar conteudo ja capturado pelo bloco pai (tabela/lista).
            if tag.name in ("p", *_HEADING_TAGS) and tag.find_parent(["table", "ul", "ol"]):
                continue

            if tag.name in _HEADING_TAGS:
                text = tag.get_text(strip=True)
                if not text:
                    continue
                level = int(tag.name[1])
                heading_stack[:] = [item for item in heading_stack if item[0] < level]
                heading_stack.append((level, text))
                sections.append(DocumentSection(text=text, section=current_section_path()))
                continue

            if tag.name == "p":
                text = tag.get_text(strip=True)
                if text:
                    sections.append(DocumentSection(text=text, section=current_section_path()))
                continue

            if tag.name in ("ul", "ol"):
                if tag.find_parent(["ul", "ol"]):
                    continue  # sublista sera incluida pela lista externa
                text = _list_to_text(tag)
                if text:
                    sections.append(DocumentSection(text=text, section=current_section_path()))
                continue

            if tag.name == "table":
                text = _table_to_text(tag)
                if text:
                    sections.append(
                        DocumentSection(
                            text=text, section=current_section_path(), table_name="Tabela HTML"
                        )
                    )

        if not sections:
            warnings.append(
                ExtractionWarning(code="empty_document", message="Nenhum conteudo extraido do HTML.")
            )

        return ExtractedDocument(
            source_path=str(file_path), document_format="html", sections=sections, warnings=warnings
        )
