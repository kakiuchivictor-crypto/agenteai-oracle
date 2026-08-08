from __future__ import annotations

from app.agents.nodes.validation import (
    determine_filters,
    identify_intent,
    rewrite_query,
    validate_question,
)


def test_validate_question_rejects_empty() -> None:
    result = validate_question({"question": "   "})
    assert result["route"] == "invalid"


def test_validate_question_rejects_too_long() -> None:
    result = validate_question({"question": "a" * 3000})
    assert result["route"] == "invalid"


def test_validate_question_accepts_valid_question() -> None:
    result = validate_question({"question": "Qual o prazo de reembolso?"})
    assert result["route"] == "continue"
    assert result["normalized_question"] == "Qual o prazo de reembolso?"


def test_identify_intent_detects_greeting() -> None:
    result = identify_intent({"normalized_question": "Oi!"})
    assert result["intent"] == "out_of_scope"
    assert result["route"] == "out_of_scope"


def test_identify_intent_detects_admin_request() -> None:
    result = identify_intent({"normalized_question": "Preciso aprovar documento pendente"})
    assert result["route"] == "admin_request"


def test_identify_intent_detects_ingestion_request() -> None:
    result = identify_intent({"normalized_question": "Como faço upload de um novo arquivo?"})
    assert result["route"] == "ingestion_request"


def test_identify_intent_defaults_to_question() -> None:
    result = identify_intent({"normalized_question": "Qual o prazo de reembolso?"})
    assert result["intent"] == "question"
    assert result["route"] == "continue"


def test_rewrite_query_returns_question_unchanged_without_history() -> None:
    result = rewrite_query({"normalized_question": "Qual o prazo?", "chat_history": []})
    assert result["rewritten_query"] == "Qual o prazo?"


def test_rewrite_query_prepends_previous_user_questions_without_calling_llm() -> None:
    result = rewrite_query(
        {
            "normalized_question": "E para compras internacionais?",
            "chat_history": [
                {"role": "user", "content": "Qual o prazo de reembolso?"},
                {"role": "assistant", "content": "O prazo e de 7 dias."},
            ],
        }
    )
    assert result["rewritten_query"] == "Qual o prazo de reembolso? E para compras internacionais?"


def test_rewrite_query_only_uses_last_two_user_turns() -> None:
    result = rewrite_query(
        {
            "normalized_question": "E depois?",
            "chat_history": [
                {"role": "user", "content": "pergunta 1"},
                {"role": "assistant", "content": "resposta 1"},
                {"role": "user", "content": "pergunta 2"},
                {"role": "assistant", "content": "resposta 2"},
                {"role": "user", "content": "pergunta 3"},
                {"role": "assistant", "content": "resposta 3"},
            ],
        }
    )
    assert result["rewritten_query"] == "pergunta 2 pergunta 3 E depois?"


def test_determine_filters_passes_through_category() -> None:
    result = determine_filters({"category_filter": "cat-123"})
    assert result["retrieval_filters"] == {"category": "cat-123"}


def test_determine_filters_empty_when_no_category() -> None:
    result = determine_filters({})
    assert result["retrieval_filters"] == {}
