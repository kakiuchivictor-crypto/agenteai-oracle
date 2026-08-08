from __future__ import annotations

from app.retrieval.fusion import fuse_results, reciprocal_rank_fusion, weighted_score_fusion
from app.schemas.vector import SearchResult


def _result(id_: str, score: float) -> SearchResult:
    return SearchResult(id=id_, text=f"texto {id_}", metadata={}, score=score)


def test_rrf_boosts_documents_appearing_in_both_lists() -> None:
    vector_results = [_result("a", 0.9), _result("b", 0.8), _result("c", 0.7)]
    lexical_results = [_result("c", 0.95), _result("a", 0.5)]

    fused = reciprocal_rank_fusion([vector_results, lexical_results], k=60)
    fused_ids = [r.id for r in fused]

    # "a" (rank 1 e 2) e "c" (rank 3 e 1) aparecem em ambas as listas;
    # "b" so aparece na busca vetorial e deve ficar atras de ambos.
    assert fused_ids.index("a") < fused_ids.index("b")
    assert fused_ids.index("c") < fused_ids.index("b")


def test_rrf_handles_single_list() -> None:
    results = [_result("x", 0.5), _result("y", 0.9)]
    fused = fuse_results([results, []], strategy="rrf", rrf_k=60)
    assert [r.id for r in fused] == ["y", "x"]


def test_fuse_results_empty_lists_returns_empty() -> None:
    assert fuse_results([[], []]) == []


def test_weighted_fusion_favors_higher_weighted_list() -> None:
    list_a = [_result("a", 1.0)]
    list_b = [_result("b", 1.0)]

    fused = weighted_score_fusion([list_a, list_b], weights=[0.9, 0.1])
    assert fused[0].id == "a"


def test_fuse_results_deduplicates_by_id() -> None:
    list_a = [_result("a", 0.5)]
    list_b = [_result("a", 0.9)]
    fused = fuse_results([list_a, list_b], strategy="rrf")
    assert len(fused) == 1
