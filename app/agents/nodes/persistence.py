"""No de persistencia da interacao no historico (secoes 23, 24 e 31)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlmodel import Session

from app.agents.prompts.templates import (
    ADMIN_REQUEST_MESSAGE,
    INGESTION_REQUEST_MESSAGE,
    INVALID_QUESTION_MESSAGE,
    NO_EVIDENCE_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    PENDING_APPROVAL_MESSAGE,
)
from app.agents.state import AgentState
from app.database.models import ChatMessage, ChatSession
from app.database.models.enums import MessageRole

_CANNED_MESSAGES_BY_ROUTE = {
    "invalid": INVALID_QUESTION_MESSAGE,
    "out_of_scope": OUT_OF_SCOPE_MESSAGE,
    "admin_request": ADMIN_REQUEST_MESSAGE,
    "ingestion_request": INGESTION_REQUEST_MESSAGE,
    "no_evidence": NO_EVIDENCE_MESSAGE,
    "pending_approval": PENDING_APPROVAL_MESSAGE,
}


def resolve_final_answer(state: AgentState) -> str:
    if state.get("answer"):
        return state["answer"]
    route = state.get("route", "")
    if route in ("provider_error", "provider_busy"):
        return state.get("error") or "Nao foi possivel gerar uma resposta no momento."
    return _CANNED_MESSAGES_BY_ROUTE.get(route, NO_EVIDENCE_MESSAGE)


def make_save_interaction(session: Session):
    def save_interaction(state: AgentState) -> dict:
        final_answer = resolve_final_answer(state)
        is_full_answer = bool(state.get("answer"))

        session.add(
            ChatMessage(
                session_id=state["session_id"], role=MessageRole.USER, content=state["question"]
            )
        )
        assistant_message = ChatMessage(
            session_id=state["session_id"],
            role=MessageRole.ASSISTANT,
            content=final_answer,
            sources_json=json.dumps(state.get("citations") or []) if is_full_answer else None,
            grounded=state.get("grounded") if is_full_answer else None,
            model_used=state.get("model_used") if is_full_answer else None,
            latency_ms=state.get("latency_ms") if is_full_answer else None,
        )
        session.add(assistant_message)

        chat_session = session.get(ChatSession, state["session_id"])
        if chat_session is not None:
            chat_session.updated_at = datetime.now(UTC)
            session.add(chat_session)

        session.commit()

        return {"answer": final_answer, "message_id": assistant_message.id}

    return save_interaction
