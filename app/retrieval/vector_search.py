"""Busca semantica (vetorial) — primeira etapa da recuperacao hibrida (secao 17)."""

from __future__ import annotations

from app.embeddings.base import BaseEmbeddingProvider
from app.schemas.vector import SearchResult
from app.vectorstores.base import VectorRepository


def vector_search(
    query: str,
    *,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    limit: int,
    filters: dict | None = None,
) -> list[SearchResult]:
    query_vector = embedding_provider.embed_query(query)
    return vector_repository.search(query_vector, filters=filters, limit=limit)
