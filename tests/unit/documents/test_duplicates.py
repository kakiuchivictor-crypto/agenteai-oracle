from __future__ import annotations

from app.documents.validators.duplicates import is_near_duplicate, text_similarity_ratio


def test_identical_texts_have_ratio_one() -> None:
    assert text_similarity_ratio("mesmo texto", "mesmo texto") == 1.0


def test_completely_different_texts_have_low_ratio() -> None:
    assert text_similarity_ratio("abc", "xyz123456789") < 0.5


def test_is_near_duplicate_detects_minor_edits() -> None:
    original = "A solicitacao de reembolso deve ser feita em ate 7 dias corridos."
    edited = "A solicitacao de reembolso deve ser feita em ate 7 dias uteis."
    assert is_near_duplicate(original, edited, threshold=0.85)


def test_is_near_duplicate_rejects_unrelated_documents() -> None:
    doc_a = "Politica de reembolso para produtos com defeito de fabricacao."
    doc_b = "Manual de integracao da API de pagamentos via webhook."
    assert not is_near_duplicate(doc_a, doc_b, threshold=0.85)
