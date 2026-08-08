"""Agregacao de metricas para o painel administrativo (secao 26)."""

from __future__ import annotations

from sqlmodel import Session, func, select

from app.database.models import Category, ChatMessage, Document, Feedback
from app.database.models.enums import FeedbackRating, MessageRole
from app.schemas.api.metrics import MetricsSummaryResponse


def build_metrics_summary(session: Session) -> MetricsSummaryResponse:
    total_documents = session.exec(select(func.count()).select_from(Document)).one()

    status_rows = session.exec(
        select(Document.status, func.count()).group_by(Document.status)
    ).all()
    documents_by_status = {status.value: count for status, count in status_rows}

    category_rows = session.exec(
        select(Category.name, func.count())
        .join(Document, Document.category_id == Category.id)
        .group_by(Category.name)
    ).all()
    documents_by_category = {name: count for name, count in category_rows}

    questions_asked = session.exec(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.role == MessageRole.USER)
    ).one()

    answers_without_evidence = session.exec(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.role == MessageRole.ASSISTANT, ChatMessage.grounded == False)  # noqa: E712
    ).one()

    positive_feedback = session.exec(
        select(func.count()).select_from(Feedback).where(Feedback.rating == FeedbackRating.POSITIVE)
    ).one()
    negative_feedback = session.exec(
        select(func.count()).select_from(Feedback).where(Feedback.rating == FeedbackRating.NEGATIVE)
    ).one()

    return MetricsSummaryResponse(
        total_documents=total_documents,
        documents_by_status=documents_by_status,
        documents_by_category=documents_by_category,
        questions_asked=questions_asked,
        answers_without_evidence=answers_without_evidence,
        positive_feedback=positive_feedback,
        negative_feedback=negative_feedback,
    )
