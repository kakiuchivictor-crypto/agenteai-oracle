"""Schema da ferramenta de organizacao de planilhas (fora do fluxo de RAG)."""

from __future__ import annotations

from pydantic import BaseModel


class OrganizeSpreadsheetResponse(BaseModel):
    summary: str
    file_name: str
    file_base64: str
    chart_base64: str | None
    columns: list[str]
    preview_rows: list[list[str]]
    total_rows: int
