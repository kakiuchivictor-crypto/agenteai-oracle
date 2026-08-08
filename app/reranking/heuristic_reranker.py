"""Reranker de fallback sem dependencia de modelo (secao 19 do prompt mestre).

Usado quando nenhum CrossEncoder esta disponivel. Combina a similaridade ja
calculada na fusao, correspondencia lexical direta com a pergunta e sinais
de qualidade do documento (status oficial) — evita depender de um servico
pago obrigatorio na primeira versao do projeto.
"""

from __future__ import annotations

import re

from app.reranking.base import BaseReranker
from app.schemas.vector import SearchResult

_TOKEN_PATTERN = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)

_SIMILARITY_WEIGHT = 0.6
_LEXICAL_OVERLAP_WEIGHT = 0.3
_OFFICIAL_DOCUMENT_BOOST = 0.1


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))


class HeuristicReranker(BaseReranker):
    def rerank(self, query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]:
        if not candidates:
            return []

        query_terms = _tokenize(query)
        scored: list[tuple[SearchResult, float]] = []

        for candidate in candidates:
            lexical_overlap = (
                len(query_terms & _tokenize(candidate.text)) / len(query_terms)
                if query_terms
                else 0.0
            )
            official_boost = _OFFICIAL_DOCUMENT_BOOST if candidate.metadata.get("is_official") else 0.0
            composite_score = (
                _SIMILARITY_WEIGHT * candidate.score
                + _LEXICAL_OVERLAP_WEIGHT * lexical_overlap
                + official_boost
            )
            scored.append((candidate, min(1.0, composite_score)))

        scored.sort(key=lambda item: item[1], reverse=True)
        top = scored[:top_k]

        return [
            SearchResult(id=c.id, text=c.text, metadata=c.metadata, score=score)
            for c, score in top
        ]

    @property
    def provider_name(self) -> str:
        return "heuristic"
