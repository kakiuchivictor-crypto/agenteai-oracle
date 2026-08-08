from __future__ import annotations

from sqlmodel import select

from app.agents.nodes.persistence import make_save_interaction, resolve_final_answer
from app.database.models import ChatMessage, ChatSession, User
from app.database.models.enums import MessageRole, UserRole


def test_resolve_final_answer_prefers_generated_answer() -> None:
    state = {"answer": "resposta gerada", "route": "continue"}
    assert resolve_final_answer(state) == "resposta gerada"


def test_resolve_final_answer_uses_canned_message_for_no_evidence() -> None:
    state = {"route": "no_evidence"}
    assert "Não encontrei" in resolve_final_answer(state) or "encontrei" in resolve_final_answer(state)


def test_resolve_final_answer_uses_provider_error_message() -> None:
    state = {"route": "provider_error", "error": "Falha ao conectar."}
    assert resolve_final_answer(state) == "Falha ao conectar."


def _make_user_and_session(db_session):
    user = User(email="user@example.com", hashed_password="x", full_name="Usuario", role=UserRole.USER)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    chat_session = ChatSession(id="session-1", user_id=user.id)
    db_session.add(chat_session)
    db_session.commit()
    return user, chat_session


def test_save_interaction_persists_user_and_assistant_messages(db_session) -> None:
    _make_user_and_session(db_session)
    save_interaction = make_save_interaction(db_session)

    result = save_interaction(
        {
            "session_id": "session-1",
            "question": "Qual o prazo?",
            "answer": "O prazo e de 7 dias. [Fonte 1]",
            "citations": [{"label": "Fonte 1", "document_id": "d1"}],
            "grounded": True,
            "model_used": "fake-model",
            "latency_ms": 42,
            "route": "continue",
        }
    )

    assert result["answer"] == "O prazo e de 7 dias. [Fonte 1]"

    messages = db_session.exec(
        select(ChatMessage).where(ChatMessage.session_id == "session-1")
    ).all()
    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[1].role == MessageRole.ASSISTANT
    assert messages[1].grounded is True
    assert messages[1].model_used == "fake-model"


def test_save_interaction_stores_canned_message_without_sources(db_session) -> None:
    _make_user_and_session(db_session)
    save_interaction = make_save_interaction(db_session)

    save_interaction({"session_id": "session-1", "question": "oi", "route": "out_of_scope"})

    messages = db_session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == "session-1", ChatMessage.role == MessageRole.ASSISTANT)
    ).all()
    assert len(messages) == 1
    assert messages[0].sources_json is None
    assert messages[0].grounded is None
