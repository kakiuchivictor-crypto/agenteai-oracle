"""Carregador de arquivos CSV (secao 5.6 do prompt mestre).

Usa Pandas para detectar cabecalho e separador, trata encoding com fallback,
e converte cada linha em conteudo estruturado preservando o numero da linha.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from app.core.exceptions import CorruptedFileError, EmptyDocumentError
from app.documents.loaders.base import DocumentLoader
from app.schemas.document import DocumentSection, ExtractedDocument, ExtractionWarning

_CANDIDATE_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


def _read_text_with_fallback_encoding(file_path: Path) -> tuple[str, str]:
    last_error: UnicodeDecodeError | None = None
    for encoding in _CANDIDATE_ENCODINGS:
        try:
            return file_path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise CorruptedFileError(
        f"Nao foi possivel decodificar o CSV '{file_path.name}' com nenhum encoding conhecido."
    ) from last_error


def _detect_separator(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


class CSVLoader(DocumentLoader):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".csv"

    def load(self, file_path: Path) -> ExtractedDocument:
        raw_text, encoding_used = _read_text_with_fallback_encoding(file_path)
        if not raw_text.strip():
            raise EmptyDocumentError(f"Arquivo CSV vazio: {file_path.name}")

        separator = _detect_separator(raw_text[:4096])

        try:
            frame = pd.read_csv(
                file_path, sep=separator, encoding=encoding_used, dtype=str, keep_default_na=False
            )
        except pd.errors.ParserError as exc:
            raise CorruptedFileError(f"CSV malformado: {file_path.name}") from exc

        sections: list[DocumentSection] = []
        warnings: list[ExtractionWarning] = []
        headers = [str(col) for col in frame.columns]

        for row_position, row in enumerate(frame.itertuples(index=False), start=2):
            values = list(row)
            if all(str(v).strip() == "" for v in values):
                continue
            lines = [f"Linha {row_position}"]
            for header, value in zip(headers, values, strict=False):
                if str(value).strip() == "":
                    continue
                lines.append(f"{header}: {value}")
            sections.append(DocumentSection(text="\n".join(lines), row_number=row_position))

        if not sections:
            warnings.append(
                ExtractionWarning(
                    code="csv_without_data_rows",
                    message="CSV possui apenas cabecalho, sem linhas de dados.",
                )
            )

        return ExtractedDocument(
            source_path=str(file_path),
            document_format="csv",
            sections=sections,
            warnings=warnings,
            raw_metadata={"separator": separator, "encoding": encoding_used},
        )
