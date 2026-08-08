"""Rotas de feedback (secao 31 do prompt mestre)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.dependencies.db import get_db_session
from app.core.exceptions import ResourceNotFoundError
from app.core.system_user import SYSTEM_USER_ID
from app.database.models import ChatMessage, Feedback
from app.schemas.api.feedback import FeedbackCreateRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=201)
def create_feedback(
    payload: FeedbackCreateRequest, session: Session = Depends(get_db_session)
) -> FeedbackResponse:
    message = session.get(ChatMessage, payload.message_id)
    if message is None:
        raise ResourceNotFoundError(f"Mensagem '{payload.message_id}' nao encontrada.")

    feedback = Feedback(
        message_id=payload.message_id,
        user_id=SYSTEM_USER_ID,
        rating=payload.rating,
        issue_type=payload.issue_type,
        comment=payload.comment,
    )
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return FeedbackResponse.model_validate(feedback, from_attributes=True)


@router.get("", response_model=list[FeedbackResponse])
def list_feedback(session: Session = Depends(get_db_session)) -> list[FeedbackResponse]:
    items = session.exec(select(Feedback).order_by(Feedback.created_at.desc())).all()
    return [FeedbackResponse.model_validate(f, from_attributes=True) for f in items]
