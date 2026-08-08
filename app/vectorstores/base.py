"""Interface comum de banco vetorial (secao 16 do prompt mestre).

Qualquer provedor (Chroma hoje; pgvector/Qdrant/Pinecone/Weaviate no futuro)
implementa esta interface, permitindo trocar o backend sem alterar a
logica de recuperacao.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.vector import SearchResult, VectorDocument


class VectorRepository(ABC):
    @abstractmethod
    def add_documents(self, documents: list[VectorDocument]) -> None: ...

    @abstractmethod
    def search(
        self, query_vector: list[float], filters: dict | None, limit: int
    ) -> list[SearchResult]: ...

    @abstractmethod
    def delete_by_document(self, document_id: str) -> None: ...

    @abstractmethod
    def delete_by_version(self, version_id: str) -> None: ...

    @abstractmethod
    def count(self) -> int: ...
