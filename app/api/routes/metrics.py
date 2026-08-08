"""Rota de metricas resumidas para o painel (secao 26)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.dependencies.db import get_db_session
from app.schemas.api.metrics import MetricsSummaryResponse
from app.services.metrics_service import build_metrics_summary

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricsSummaryResponse)
def metrics_summary(session: Session = Depends(get_db_session)) -> MetricsSummaryResponse:
    return build_metrics_summary(session)
