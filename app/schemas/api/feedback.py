"""Schemas da API de feedback (secao 31 do prompt mestre)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.database.models.enums import FeedbackIssueType, FeedbackRating


class FeedbackCreateRequest(BaseModel):
    message_id: str
    rating: FeedbackRating
    issue_type: FeedbackIssueType = FeedbackIssueType.NONE
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    message_id: str
    user_id: str
    rating: FeedbackRating
    issue_type: FeedbackIssueType
    comment: str | None
    created_at: datetime
