"""Testa a logica de classificacao do script de avaliacao do RAG (secao 34)."""

from __future__ import annotations

from scripts.evaluate_rag import _classify


def test_classifies_as_correct_when_all_keywords_match_and_grounded() -> None:
    item = {"expected_document": "doc.pdf", "expected_keywords": ["7 dias"]}
    result = _classify(item, "O prazo e de 7 dias.", True, ["doc.pdf"])
    assert result == "correct"


def test_classifies_as_partially_correct_when_some_keywords_missing() -> None:
    item = {"expected_document": "doc.pdf", "expected_keywords": ["7 dias", "suporte"]}
    result = _classify(item, "O prazo e de 7 dias.", True, ["doc.pdf"])
    assert result == "partially_correct"


def test_classifies_as_incorrect_when_no_keywords_match() -> None:
    item = {"expected_document": "doc.pdf", "expected_keywords": ["7 dias"]}
    result = _classify(item, "Nao sei informar.", True, ["doc.pdf"])
    assert result == "incorrect"


def test_classifies_as_no_evidence_when_no_citation() -> None:
    item = {"expected_document": "doc.pdf", "expected_keywords": ["7 dias"]}
    result = _classify(item, "Nao encontrei informacoes suficientes.", False, [])
    assert result == "no_evidence"


def test_classifies_as_wrong_source_when_citation_is_different_document() -> None:
    item = {"expected_document": "doc.pdf", "expected_keywords": ["7 dias"]}
    result = _classify(item, "O prazo e de 7 dias.", True, ["outro.pdf"])
    assert result == "wrong_source"


def test_out_of_scope_question_correct_when_no_citation() -> None:
    item = {"expected_document": None, "expected_keywords": []}
    result = _classify(item, "Nao encontrei informacoes suficientes.", False, [])
    assert result == "correct"


def test_out_of_scope_question_incorrect_when_model_hallucinates_a_source() -> None:
    item = {"expected_document": None, "expected_keywords": []}
    result = _classify(item, "Segundo o documento X...", True, ["documento_inventado.pdf"])
    assert result == "incorrect"


def test_classifies_as_partially_correct_when_grounded_but_no_keywords_defined() -> None:
    item = {"expected_document": "doc.pdf", "expected_keywords": []}
    result = _classify(item, "Qualquer resposta.", False, ["doc.pdf"])
    assert result == "partially_correct"
