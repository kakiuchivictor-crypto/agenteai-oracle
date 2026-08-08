"""Testes das primitivas de seguranca (app.core.security)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import FileTooLargeError, InvalidFileError, UnsafeFilePathError
from app.core.security import resolve_within_base, safe_filename, validate_upload


def test_safe_filename_strips_unsafe_characters_and_keeps_extension() -> None:
    name = safe_filename("../../etc/passwd; rm -rf.pdf")
    assert name.endswith(".pdf")
    assert "/" not in name and ".." not in name


def test_resolve_within_base_blocks_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(UnsafeFilePathError):
        resolve_within_base(tmp_path, Path("../outside.pdf"))


def test_resolve_within_base_allows_nested_path(tmp_path: Path) -> None:
    resolved = resolve_within_base(tmp_path, Path("sub/file.pdf"))
    assert str(resolved).startswith(str(tmp_path.resolve()))


def test_validate_upload_rejects_disallowed_extension() -> None:
    with pytest.raises(InvalidFileError):
        validate_upload(
            filename="malware.exe",
            content=b"conteudo",
            allowed_extensions=[".pdf"],
            max_size_mb=10,
        )


def test_validate_upload_rejects_oversized_file() -> None:
    with pytest.raises(FileTooLargeError):
        validate_upload(
            filename="doc.md",
            content=b"a" * 1024,
            allowed_extensions=[".md"],
            max_size_mb=0.0001,
        )


def test_validate_upload_rejects_path_traversal_filename() -> None:
    with pytest.raises(UnsafeFilePathError):
        validate_upload(
            filename="../secret.md",
            content=b"conteudo",
            allowed_extensions=[".md"],
            max_size_mb=10,
        )


def test_validate_upload_accepts_valid_markdown() -> None:
    validate_upload(
        filename="doc.md",
        content=b"# Titulo\nConteudo valido.",
        allowed_extensions=[".md"],
        max_size_mb=10,
    )


def test_validate_upload_rejects_mime_mismatch_for_pdf() -> None:
    with pytest.raises(InvalidFileError):
        validate_upload(
            filename="fake.pdf",
            content=b"isto nao e um PDF de verdade",
            allowed_extensions=[".pdf"],
            max_size_mb=10,
        )
