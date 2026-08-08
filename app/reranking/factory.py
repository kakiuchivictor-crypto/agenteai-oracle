"""Fabrica de reranker, com fallback automatico para a estrategia heuristica
quando o CrossEncoder configurado nao puder ser carregado (secao 19)."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import RerankerProvider, Settings, get_settings
from app.core.logging import get_logger
from app.reranking.base import BaseReranker
from app.reranking.heuristic_reranker import HeuristicReranker

logger = get_logger(__name__)


def build_reranker(settings: Settings) -> BaseReranker:
    if settings.reranker_provider == RerankerProvider.CROSS_ENCODER:
        try:
            from app.reranking.cross_encoder_reranker import CrossEncoderReranker

            return CrossEncoderReranker(settings.reranker_model)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "reranker.cross_encoder_unavailable_using_heuristic_fallback", error=str(exc)
            )
    return HeuristicReranker()


@lru_cache
def get_reranker() -> BaseReranker:
    return build_reranker(get_settings())
