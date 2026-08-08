"""Carregador de arquivos JSON (secao 5.7 do prompt mestre).

Percorre objetos, listas e estruturas aninhadas convertendo cada campo em
conteudo legivel que preserva o caminho do campo (ex: `planos.profissional.preco`).
Registros "planos" (dicionarios cujos valores sao todos escalares) sao
agrupados em uma unica secao, similar a uma linha de planilha, para nao
fragmentar excessivamente listas de objetos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.exceptions import CorruptedFileError, EmptyDocumentError
from app.documents.loaders.base import DocumentLoader
from app.schemas.document import DocumentSection, ExtractedDocument, ExtractionWarning

_Scalar = str | int | float | bool | None


def _is_scalar(value: Any) -> bool:
    return isinstance(value, str | int | float | bool) or value is None


def _is_flat_dict(value: dict) -> bool:
    return bool(value) and all(_is_scalar(v) for v in value.values())


def _walk(value: Any, path: str) -> list[DocumentSection]:
    sections: list[DocumentSection] = []

    if isinstance(value, dict):
        if not value:
            return sections
        if _is_flat_dict(value):
            lines = [f"Caminho: {path}" if path else "Caminho: (raiz)"]
            lines.extend(f"{key}: {val}" for key, val in value.items())
            sections.append(DocumentSection(text="\n".join(lines), json_path=path or None))
            return sections
        for key, val in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if _is_scalar(val):
                sections.append(
                    DocumentSection(
                        text=f"Caminho: {child_path}\nValor: {val}", json_path=child_path
                    )
                )
            else:
                sections.extend(_walk(val, child_path))
        return sections

    if isinstance(value, list):
        if not value:
            return sections
        if all(_is_scalar(item) for item in value):
            values_str = ", ".join(str(item) for item in value)
            sections.append(
                DocumentSection(text=f"Caminho: {path}\nValores: {values_str}", json_path=path)
            )
            return sections
        for index, item in enumerate(value):
            sections.extend(_walk(item, f"{path}[{index}]"))
        return sections

    sections.append(DocumentSection(text=f"Caminho: {path}\nValor: {value}", json_path=path))
    return sections


class JSONLoader(DocumentLoader):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".json"

    def load(self, file_path: Path) -> ExtractedDocument:
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise CorruptedFileError(
                f"JSON '{file_path.name}' nao esta em codificacao UTF-8 valida."
            ) from exc

        if not raw_text.strip():
            raise EmptyDocumentError(f"Arquivo JSON vazio: {file_path.name}")

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise CorruptedFileError(f"JSON invalido em '{file_path.name}': {exc}") from exc

        sections = _walk(data, "")
        warnings: list[ExtractionWarning] = []
        if not sections:
            warnings.append(
                ExtractionWarning(code="empty_document", message="JSON sem campos extraiveis.")
            )

        return ExtractedDocument(
            source_path=str(file_path), document_format="json", sections=sections, warnings=warnings
        )
