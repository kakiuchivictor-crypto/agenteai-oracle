from __future__ import annotations

from app.documents.validators.hashing import compute_content_hash, compute_file_hash


def test_file_hash_is_deterministic() -> None:
    content = b"conteudo binario de teste"
    assert compute_file_hash(content) == compute_file_hash(content)


def test_file_hash_differs_for_different_content() -> None:
    assert compute_file_hash(b"a") != compute_file_hash(b"b")


def test_content_hash_ignores_trailing_whitespace_differences() -> None:
    a = compute_content_hash("linha um  \nlinha dois")
    b = compute_content_hash("linha um\nlinha dois")
    assert a == b


def test_content_hash_differs_for_different_text() -> None:
    assert compute_content_hash("texto A") != compute_content_hash("texto B")
