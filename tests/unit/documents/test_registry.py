from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import UnsupportedDocumentError
from app.documents.loaders.csv_loader import CSVLoader
from app.documents.loaders.excel_loader import ExcelLoader
from app.documents.loaders.html_loader import HTMLLoader
from app.documents.loaders.json_loader import JSONLoader
from app.documents.loaders.markdown_loader import MarkdownLoader
from app.documents.loaders.pdf_loader import PDFLoader
from app.documents.loaders.powerpoint_loader import PowerPointLoader
from app.documents.loaders.registry import get_loader_for
from app.documents.loaders.word_loader import WordLoader

_EXPECTED_LOADER_BY_EXTENSION = {
    ".pdf": PDFLoader,
    ".docx": WordLoader,
    ".xlsx": ExcelLoader,
    ".pptx": PowerPointLoader,
    ".md": MarkdownLoader,
    ".csv": CSVLoader,
    ".json": JSONLoader,
    ".html": HTMLLoader,
}


@pytest.mark.parametrize("extension,expected_type", _EXPECTED_LOADER_BY_EXTENSION.items())
def test_dispatches_to_correct_loader(extension: str, expected_type: type) -> None:
    loader = get_loader_for(Path(f"documento{extension}"))
    assert isinstance(loader, expected_type)


def test_unsupported_extension_raises_domain_error() -> None:
    with pytest.raises(UnsupportedDocumentError):
        get_loader_for(Path("arquivo.exe"))
