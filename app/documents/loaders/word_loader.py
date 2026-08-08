"""Carregador de documentos Word (secao 5.2 do prompt mestre).

Extrai titulos, paragrafos, listas e tabelas preservando a ordem original do
documento (iterando os elementos XML do corpo em vez das colecoes separadas
`paragraphs`/`tables` do python-docx, que perdem a ordem relativa).
"""

from __future__ import annotations

from pathlib import Path

from docx import Document as open_docx
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.exceptions import CorruptedFileError
from app.documents.loaders.base import DocumentLoader
from app.schemas.document import DocumentSection, ExtractedDocument, ExtractionWarning


def _iter_block_items(document):
    parent_elm = document.element.body
    for child in parent_elm.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def _table_to_text(table: Table) -> str:
    rows_text = []
    for row_index, row in enumerate(table.rows):
        cells = [cell.text.strip() for cell in row.cells]
        prefix = "Cabecalho" if row_index == 0 else f"Linha {row_index}"
        rows_text.append(f"{prefix}: " + " | ".join(cells))
    return "\n".join(rows_text)


class WordLoader(DocumentLoader):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".docx"

    def load(self, file_path: Path) -> ExtractedDocument:
        try:
            document = open_docx(str(file_path))
        except PackageNotFoundError as exc:
            raise CorruptedFileError(
                f"Nao foi possivel abrir o documento Word: {file_path.name}"
            ) from exc

        sections: list[DocumentSection] = []
        warnings: list[ExtractionWarning] = []
        current_heading: str | None = None
        table_index = 0

        for block in _iter_block_items(document):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text:
                    continue
                style_name = (block.style.name or "").lower()
                if style_name.startswith("heading") or style_name.startswith("title"):
                    current_heading = text
                    sections.append(DocumentSection(text=text, section=current_heading))
                elif "list" in style_name:
                    sections.append(
                        DocumentSection(text=f"- {text}", section=current_heading)
                    )
                else:
                    sections.append(DocumentSection(text=text, section=current_heading))
            elif isinstance(block, Table):
                table_index += 1
                table_text = _table_to_text(block)
                if table_text.strip():
                    sections.append(
                        DocumentSection(
                            text=table_text,
                            section=current_heading,
                            table_name=f"Tabela {table_index}",
                        )
                    )
                else:
                    warnings.append(
                        ExtractionWarning(
                            code="empty_table",
                            message="Tabela vazia ignorada.",
                            location=f"tabela {table_index}",
                        )
                    )

        if not sections:
            warnings.append(
                ExtractionWarning(code="empty_document", message="Documento sem conteudo textual.")
            )

        return ExtractedDocument(
            source_path=str(file_path),
            document_format="docx",
            sections=sections,
            warnings=warnings,
            raw_metadata={"table_count": str(table_index)},
        )
