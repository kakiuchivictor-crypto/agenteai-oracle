"""Suporte opcional de OCR para paginas de PDF sem camada textual (secao 5.1).

O OCR so e acionado quando uma pagina especifica for detectada como
provavelmente escaneada, nunca no arquivo inteiro por padrao (regra
explicita do prompt mestre: "Nao execute OCR em todos os arquivos sem
necessidade").
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.exceptions import OCRUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Uma pagina com menos caracteres que este limiar, mas que possui imagens,
# e considerada candidata a OCR.
MIN_TEXT_CHARS_BEFORE_OCR = 20


def is_ocr_configured() -> bool:
    settings = get_settings()
    if not settings.ocr_enabled:
        return False
    try:
        import pytesseract

        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001 - qualquer falha significa OCR indisponivel
        return False


def run_ocr_on_pdf_page(pdf_path: str, page_number: int) -> str:
    """Executa OCR em uma unica pagina (1-indexada) de um PDF.

    Levanta `OCRUnavailableError` com mensagem clara caso o Tesseract ou o
    Poppler (dependencia nativa do pdf2image) nao estejam instalados, em vez
    de deixar a excecao generica estourar no meio do pipeline de ingestao.
    """
    settings = get_settings()
    if not settings.ocr_enabled:
        raise OCRUnavailableError("OCR esta desativado por configuracao (OCR_ENABLED=false).")

    try:
        import pytesseract
        from pdf2image import convert_from_path

        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

        images = convert_from_path(
            pdf_path, first_page=page_number, last_page=page_number, dpi=200
        )
        if not images:
            return ""
        return pytesseract.image_to_string(images[0], lang=settings.ocr_language)
    except OCRUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("ocr.unavailable", page=page_number, error=str(exc))
        raise OCRUnavailableError(
            "OCR indisponivel: verifique se o Tesseract e o Poppler estao "
            "instalados e acessiveis no PATH (ou configure TESSERACT_CMD)."
        ) from exc
