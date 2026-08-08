"""Schema de chunk produzido pelo chunker hibrido (secao 13 do prompt mestre)."""

from __future__ import annotations

from pydantic import BaseModel


class Chunk(BaseModel):
    """Um trecho pronto para embedding, com metadados de localizacao herdados
    da(s) `DocumentSection` que o originaram."""

    chunk_index: int
    text: str
    char_count: int
    page: int | None = None
    section: str | None = None
    slide: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    table_name: str | None = None
    json_path: str | None = None
    is_ocr: bool = False
