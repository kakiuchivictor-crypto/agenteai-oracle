"""Orquestracao da recuperacao hibrida completa (secoes 17, 18 e 19).

Fluxo: busca vetorial + busca lexical (quando habilitada) -> fusao (RRF ou
soma ponderada) -> aplicacao do status de curadoria -> reranking -> top-k
final. Espelha o trecho relevante do fluxo de RAG da secao 17.
"""

from __future__ import annotations

from sqlmodel import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.embeddings.base import BaseEmbeddingProvider
from app.reranking.base import BaseReranker
from app.retrieval.fusion import fuse_results
from app.retrieval.lexical_search import lexical_search
from app.retrieval.permissions import filter_authorized_results
from app.retrieval.vector_search import vector_search
from app.schemas.vector import SearchResult
from app.vectorstores.base import VectorRepository

logger = get_logger(__name__)


def hybrid_search(
    query: str,
    *,
    session: Session,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    reranker: BaseReranker,
    settings: Settings,
) -> list[SearchResult]:
    vector_results = vector_search(
        query,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        limit=settings.retrieval_candidates,
    )

    lexical_results: list[SearchResult] = []
    if settings.hybrid_search_enabled:
        lexical_results = lexical_search(query, session=session, limit=settings.retrieval_candidates)

    fused = fuse_results(
        [vector_results, lexical_results],
        strategy=settings.hybrid_fusion_strategy.value,
        rrf_k=settings.hybrid_rrf_k,
    )

    authorized = filter_authorized_results(fused, session=session)
    if not authorized:
        logger.info("hybrid_search.no_authorized_results", query=query)
        return []

    reranked = reranker.rerank(query, authorized, top_k=settings.rerank_top_k)
    logger.info(
        "hybrid_search.completed",
        query=query,
        vector_candidates=len(vector_results),
        lexical_candidates=len(lexical_results),
        authorized_candidates=len(authorized),
        final_results=len(reranked),
    )
    return reranked
