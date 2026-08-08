"""Testes do cache de respostas (pergunta normalizada + contexto -> resposta)."""

from __future__ import annotations

from app.llm.answer_cache import compute_cache_key, get_cached_answer, store_answer


def test_compute_cache_key_is_stable_for_same_question_and_context() -> None:
    key1 = compute_cache_key("Qual o prazo?", "ctx")
    key2 = compute_cache_key("qual o prazo?  ", "ctx")
    assert key1 == key2  # normalizado (trim + lower) antes de gerar a chave


def test_compute_cache_key_changes_with_context() -> None:
    key1 = compute_cache_key("q", "contexto 1")
    key2 = compute_cache_key("q", "contexto 2")
    assert key1 != key2


def test_store_and_get_cached_answer(db_session) -> None:
    key = compute_cache_key("q", "ctx")
    assert get_cached_answer(db_session, key) is None

    store_answer(db_session, cache_key=key, answer="resposta", route="continue", model_used="gemini")
    db_session.commit()

    cached = get_cached_answer(db_session, key)
    assert cached is not None
    assert cached.answer == "resposta"
    assert cached.route == "continue"
    assert cached.model_used == "gemini"
