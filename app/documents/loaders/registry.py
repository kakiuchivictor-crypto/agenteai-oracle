"""Registro de carregadores: despacha o carregador correto por extensao.

Novos formatos sao adicionados registrando uma nova instancia de
`DocumentLoader` em `_LOADERS`, sem alterar nenhum outro ponto do pipeline
(secao 4 do prompt mestre: "A arquitetura devera permitir adicionar novos
formatos posteriormente").
"""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import UnsupportedDocumentError
from app.documents.loaders.base import DocumentLoader
from app.documents.loaders.csv_loader import CSVLoader
from app.documents.loaders.excel_loader import ExcelLoader
from app.documents.loaders.html_loader import HTMLLoader
from app.documents.loaders.json_loader import JSONLoader
from app.documents.loaders.markdown_loader import MarkdownLoader
from app.documents.loaders.pdf_loader import PDFLoader
from app.documents.loaders.powerpoint_loader import PowerPointLoader
from app.documents.loaders.word_loader import WordLoader

_LOADERS: list[DocumentLoader] = [
    PDFLoader(),
    WordLoader(),
    ExcelLoader(),
    PowerPointLoader(),
    MarkdownLoader(),
    CSVLoader(),
    JSONLoader(),
    HTMLLoader(),
]


def get_loader_for(file_path: Path) -> DocumentLoader:
    for loader in _LOADERS:
        if loader.supports(file_path):
            return loader
    raise UnsupportedDocumentError(
        f"Nenhum carregador disponivel para o formato '{file_path.suffix}'."
    )
