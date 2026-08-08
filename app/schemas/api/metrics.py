"""Schemas da API de metricas (secao 26 - painel basico)."""

from __future__ import annotations

from pydantic import BaseModel


class MetricsSummaryResponse(BaseModel):
    total_documents: int
    documents_by_status: dict[str, int]
    documents_by_category: dict[str, int]
    questions_asked: int
    answers_without_evidence: int
    positive_feedback: int
    negative_feedback: int
