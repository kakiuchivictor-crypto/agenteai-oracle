"""Interface comum de reranking (secao 19 do prompt mestre)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.vector import SearchResult


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...
