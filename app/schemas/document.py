"""Schemas de dominio para o resultado padronizado dos carregadores de documento.

Todo `DocumentLoader` (secao 4 do prompt mestre) deve retornar `list[DocumentSection]`
dentro de um `ExtractedDocument`, independente do formato de origem.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentSection(BaseModel):
    """Um trecho de conteudo extraido preservando sua localizacao de origem.

    Nem todo campo de localizacao se aplica a todo formato — cada carregador
    preenche apenas os campos relevantes (ex: PDF preenche `page`, PPTX
    preenche `slide`, XLSX preenche `sheet_name`/`row_number`).
    """

    text: str
    page: int | None = None
    section: str | None = None
    slide: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    table_name: str | None = None
    json_path: str | None = None
    is_ocr: bool = False


class ExtractionWarning(BaseModel):
    code: str
    message: str
    location: str | None = None


class ExtractedDocument(BaseModel):
    """Resultado padronizado da extracao de um arquivo, antes da limpeza/chunking."""

    source_path: str
    document_format: str
    sections: list[DocumentSection] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    raw_metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def has_content(self) -> bool:
        return any(section.text.strip() for section in self.sections)

    @property
    def full_text(self) -> str:
        return "\n\n".join(section.text for section in self.sections if section.text.strip())
