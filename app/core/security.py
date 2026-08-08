"""Primitivas de seguranca: validacao de arquivos enviados.

Implementa os controles da secao 29 do prompt mestre relacionados a upload:
validacao de extensao e MIME type, limite de tamanho, nome de arquivo seguro
e bloqueio de caminhos maliciosos (path traversal). O sistema nao possui
login (uso livre para todos os usuarios) — nao ha primitivas de senha/JWT
aqui.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import filetype

from app.core.exceptions import FileTooLargeError, InvalidFileError, UnsafeFilePathError

# MIME types aceitos por extensao. Usado para conferir o conteudo real do
# arquivo contra a extensao declarada (evita renomear .exe para .pdf).
_EXTENSION_MIME_MAP: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
    },
    # Formatos textuais puros (md, csv, json, html) nao possuem assinatura
    # binaria confiavel via magic bytes; sao validados por extensao +
    # verificacao de conteudo textual em `validate_upload`.
}

_TEXT_ONLY_EXTENSIONS = {".md", ".csv", ".json", ".html", ".htm"}


# ==========================================================
# ARQUIVOS
# ==========================================================
_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(original_name: str) -> str:
    """Gera um nome de arquivo seguro e unico, preservando apenas a extensao original."""
    suffix = Path(original_name).suffix.lower()
    suffix = _SAFE_NAME_PATTERN.sub("", suffix)
    return f"{uuid.uuid4().hex}{suffix}"


def resolve_within_base(base_dir: Path, candidate: Path) -> Path:
    """Garante que `candidate` esteja contido em `base_dir`, bloqueando path traversal."""
    base_resolved = base_dir.resolve()
    candidate_resolved = (base_dir / candidate).resolve()
    if base_resolved not in candidate_resolved.parents and candidate_resolved != base_resolved:
        raise UnsafeFilePathError("Caminho de arquivo fora do diretorio permitido.")
    return candidate_resolved


def validate_upload(
    *,
    filename: str,
    content: bytes,
    allowed_extensions: list[str],
    max_size_mb: int,
) -> None:
    """Valida extensao, tamanho e assinatura de conteudo de um arquivo enviado."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise UnsafeFilePathError("Nome de arquivo invalido.")

    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions:
        raise InvalidFileError(
            f"Extensao '{extension}' nao suportada. Extensoes permitidas: "
            f"{', '.join(allowed_extensions)}"
        )

    size_mb = len(content) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise FileTooLargeError(
            f"Arquivo de {size_mb:.1f}MB excede o limite de {max_size_mb}MB."
        )

    if len(content) == 0:
        raise InvalidFileError("Arquivo vazio.")

    expected_mimes = _EXTENSION_MIME_MAP.get(extension)
    if expected_mimes:
        detected = filetype.guess(content)
        detected_mime = detected.mime if detected else None
        if detected_mime not in expected_mimes:
            raise InvalidFileError(
                f"O conteudo do arquivo nao corresponde a extensao '{extension}' "
                f"(tipo detectado: {detected_mime or 'desconhecido'})."
            )
    elif extension in _TEXT_ONLY_EXTENSIONS:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidFileError(
                f"Arquivo '{extension}' nao esta em codificacao de texto valida (UTF-8)."
            ) from exc
