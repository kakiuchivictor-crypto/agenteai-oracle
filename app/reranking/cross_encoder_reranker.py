"""Reranker baseado em CrossEncoder local (padrao do projeto, sem custo por uso)."""

from __future__ import annotations

import math

from app.core.exceptions import ProviderUnavailableError
from app.reranking.base import BaseReranker
from app.schemas.vector import SearchResult


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class CrossEncoderReranker(BaseReranker):
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - dependencia declarada no projeto
            raise ProviderUnavailableError("sentence-transformers nao instalado.") from exc

        self._model_name = model_name
        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]:
        if not candidates:
            return []

        pairs = [(query, candidate.text) for candidate in candidates]
        raw_scores = self._model.predict(pairs)

        scored = sorted(
            zip(candidates, raw_scores, strict=True), key=lambda item: item[1], reverse=True
        )
        top = scored[:top_k]

        return [
            SearchResult(
                id=candidate.id, text=candidate.text, metadata=candidate.metadata,
                score=_sigmoid(float(raw_score)),
            )
            for candidate, raw_score in top
        ]

    @property
    def provider_name(self) -> str:
        return "cross_encoder"
