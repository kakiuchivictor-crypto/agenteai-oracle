from __future__ import annotations

from app.reranking.heuristic_reranker import HeuristicReranker
from app.schemas.vector import SearchResult


def test_prefers_higher_lexical_overlap_with_query() -> None:
    reranker = HeuristicReranker()
    candidates = [
        SearchResult(id="a", text="prazo de reembolso e de 7 dias corridos", metadata={}, score=0.5),
        SearchResult(id="b", text="texto totalmente sem relacao com a pergunta", metadata={}, score=0.5),
    ]

    reranked = reranker.rerank("qual o prazo de reembolso", candidates, top_k=2)

    assert reranked[0].id == "a"
    assert reranked[0].score > reranked[1].score


def test_boosts_official_documents() -> None:
    reranker = HeuristicReranker()
    candidates = [
        SearchResult(id="a", text="conteudo generico", metadata={"is_official": False}, score=0.6),
        SearchResult(id="b", text="conteudo generico", metadata={"is_official": True}, score=0.6),
    ]

    reranked = reranker.rerank("consulta qualquer", candidates, top_k=2)

    scores_by_id = {r.id: r.score for r in reranked}
    assert scores_by_id["b"] > scores_by_id["a"]


def test_respects_top_k() -> None:
    reranker = HeuristicReranker()
    candidates = [SearchResult(id=str(i), text="texto", metadata={}, score=0.1 * i) for i in range(10)]
    reranked = reranker.rerank("consulta", candidates, top_k=3)
    assert len(reranked) == 3


def test_empty_candidates_returns_empty() -> None:
    reranker = HeuristicReranker()
    assert reranker.rerank("consulta", [], top_k=5) == []
