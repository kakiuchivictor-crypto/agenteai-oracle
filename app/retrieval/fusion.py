"""Fusao dos resultados de busca vetorial e lexical (secao 18 do prompt mestre).

Estrategia padrao: Reciprocal Rank Fusion (RRF), robusta a diferencas de
escala entre os scores de cada busca (similaridade de cosseno vs. BM25).
Uma estrategia alternativa por soma ponderada de scores normalizados
tambem esta disponivel, selecionavel por configuracao.
"""

from __future__ import annotations

from app.schemas.vector import SearchResult


def reciprocal_rank_fusion(result_lists: list[list[SearchResult]], k: int = 60) -> list[SearchResult]:
    scores: dict[str, float] = {}
    canonical: dict[str, SearchResult] = {}

    for results in result_lists:
        for rank, result in enumerate(results, start=1):
            scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (k + rank)
            canonical.setdefault(result.id, result)

    fused = [
        SearchResult(id=doc_id, text=canonical[doc_id].text, metadata=canonical[doc_id].metadata, score=score)
        for doc_id, score in scores.items()
    ]
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused


def weighted_score_fusion(
    result_lists: list[list[SearchResult]], weights: list[float] | None = None
) -> list[SearchResult]:
    weights = weights or [1.0] * len(result_lists)
    scores: dict[str, float] = {}
    canonical: dict[str, SearchResult] = {}

    for results, weight in zip(result_lists, weights, strict=True):
        max_score = max((r.score for r in results), default=0.0) or 1.0
        for result in results:
            normalized = (result.score / max_score) * weight
            scores[result.id] = scores.get(result.id, 0.0) + normalized
            canonical.setdefault(result.id, result)

    fused = [
        SearchResult(id=doc_id, text=canonical[doc_id].text, metadata=canonical[doc_id].metadata, score=score)
        for doc_id, score in scores.items()
    ]
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused


def fuse_results(
    result_lists: list[list[SearchResult]], *, strategy: str = "rrf", rrf_k: int = 60
) -> list[SearchResult]:
    non_empty_lists = [results for results in result_lists if results]
    if not non_empty_lists:
        return []
    if len(non_empty_lists) == 1:
        return sorted(non_empty_lists[0], key=lambda r: r.score, reverse=True)

    if strategy == "weighted":
        return weighted_score_fusion(non_empty_lists)
    return reciprocal_rank_fusion(non_empty_lists, k=rrf_k)
