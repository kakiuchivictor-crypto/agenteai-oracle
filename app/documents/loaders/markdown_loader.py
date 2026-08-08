"""Carregador de arquivos Markdown (secao 5.5 do prompt mestre).

Preserva titulos, subtitulos, listas, tabelas e blocos de codigo como secoes
distintas, associadas ao caminho de titulos vigente (`H1 > H2 > ...`),
removendo apenas a marcacao redundante (ex: simbolos de heading) sem perder
a estrutura semantica do documento.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.exceptions import EmptyDocumentError
from app.documents.loaders.base import DocumentLoader
from app.schemas.document import DocumentSection, ExtractedDocument, ExtractionWarning

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
_CODE_FENCE_PATTERN = re.compile(r"^(```|~~~)")


class MarkdownLoader(DocumentLoader):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in {".md", ".markdown"}

    def load(self, file_path: Path) -> ExtractedDocument:
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = file_path.read_text(encoding="latin-1")

        if not raw_text.strip():
            raise EmptyDocumentError(f"Arquivo Markdown vazio: {file_path.name}")

        sections: list[DocumentSection] = []
        warnings: list[ExtractionWarning] = []
        heading_stack: list[tuple[int, str]] = []
        buffer: list[str] = []
        in_code_block = False

        def current_section_path() -> str | None:
            return " > ".join(text for _, text in heading_stack) or None

        def flush_buffer() -> None:
            if not buffer:
                return
            text = "\n".join(buffer).strip()
            buffer.clear()
            if text:
                sections.append(DocumentSection(text=text, section=current_section_path()))

        for raw_line in raw_text.splitlines():
            line = raw_line.rstrip()

            if _CODE_FENCE_PATTERN.match(line.strip()):
                if in_code_block:
                    buffer.append(line)
                    flush_buffer()
                    in_code_block = False
                else:
                    flush_buffer()
                    buffer.append(line)
                    in_code_block = True
                continue

            if in_code_block:
                buffer.append(line)
                continue

            heading_match = _HEADING_PATTERN.match(line)
            if heading_match:
                flush_buffer()
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                heading_stack[:] = [item for item in heading_stack if item[0] < level]
                heading_stack.append((level, heading_text))
                sections.append(DocumentSection(text=heading_text, section=current_section_path()))
                continue

            if not line.strip():
                flush_buffer()
                continue

            buffer.append(line)

        flush_buffer()

        if not sections:
            warnings.append(
                ExtractionWarning(code="empty_document", message="Nenhum conteudo extraido.")
            )

        return ExtractedDocument(
            source_path=str(file_path),
            document_format="markdown",
            sections=sections,
            warnings=warnings,
        )
