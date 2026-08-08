"""Carregador de PDF (secao 5.1 do prompt mestre).

Extrai texto por pagina via PyMuPDF, preservando o numero da pagina.
Paginas sem texto suficiente mas com imagens sao encaminhadas para OCR
(quando habilitado); o restante e apenas registrado como aviso.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from app.core.exceptions import (
    CorruptedFileError,
    OCRUnavailableError,
    PasswordProtectedDocumentError,
)
from app.core.logging import get_logger
from app.documents.loaders.base import DocumentLoader
from app.documents.loaders.ocr import (
    MIN_TEXT_CHARS_BEFORE_OCR,
    is_ocr_configured,
    run_ocr_on_pdf_page,
)
from app.schemas.document import DocumentSection, ExtractedDocument, ExtractionWarning

logger = get_logger(__name__)


class PDFLoader(DocumentLoader):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def load(self, file_path: Path) -> ExtractedDocument:
        try:
            document = fitz.open(file_path)
        except Exception as exc:  # noqa: BLE001
            raise CorruptedFileError(f"Nao foi possivel abrir o PDF: {file_path.name}") from exc

        if document.is_encrypted and not document.authenticate(""):
            document.close()
            raise PasswordProtectedDocumentError(
                f"O PDF '{file_path.name}' esta protegido por senha."
            )

        sections: list[DocumentSection] = []
        warnings: list[ExtractionWarning] = []
        ocr_available = is_ocr_configured()

        for page_index in range(document.page_count):
            page_number = page_index + 1
            page = document.load_page(page_index)
            text = page.get_text("text").strip()
            has_images = len(page.get_images(full=True)) > 0

            if text and len(text) >= MIN_TEXT_CHARS_BEFORE_OCR:
                sections.append(DocumentSection(text=text, page=page_number))
                continue

            if not text and not has_images:
                warnings.append(
                    ExtractionWarning(
                        code="empty_page",
                        message="Pagina sem texto ou imagens.",
                        location=f"pagina {page_number}",
                    )
                )
                continue

            # Pouco ou nenhum texto, mas ha imagens: candidata a OCR.
            if ocr_available:
                try:
                    ocr_text = run_ocr_on_pdf_page(str(file_path), page_number).strip()
                    if ocr_text:
                        sections.append(
                            DocumentSection(text=ocr_text, page=page_number, is_ocr=True)
                        )
                    else:
                        warnings.append(
                            ExtractionWarning(
                                code="ocr_empty_result",
                                message="OCR executado, mas nenhum texto foi reconhecido.",
                                location=f"pagina {page_number}",
                            )
                        )
                except OCRUnavailableError as exc:
                    warnings.append(
                        ExtractionWarning(
                            code="ocr_unavailable",
                            message=str(exc),
                            location=f"pagina {page_number}",
                        )
                    )
            else:
                warnings.append(
                    ExtractionWarning(
                        code="ocr_needed_but_disabled",
                        message=(
                            "Pagina provavelmente escaneada, mas OCR esta "
                            "desativado ou indisponivel no ambiente."
                        ),
                        location=f"pagina {page_number}",
                    )
                )
                if text:
                    sections.append(DocumentSection(text=text, page=page_number))

        page_count = document.page_count
        document.close()

        return ExtractedDocument(
            source_path=str(file_path),
            document_format="pdf",
            sections=sections,
            warnings=warnings,
            raw_metadata={"page_count": str(page_count)},
        )
