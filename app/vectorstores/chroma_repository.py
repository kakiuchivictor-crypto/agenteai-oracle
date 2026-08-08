"""Implementacao do banco vetorial usando Chroma (persistencia local).

Os embeddings sao gerados fora do Chroma (pela camada `app.embeddings`) e
passados prontos aqui — o Chroma atua apenas como indice/armazenamento,
nunca como gerador de embeddings, para manter a troca de provedor
transparente (secao 15 do prompt mestre).
"""

from __future__ import annotations

from typing import Any

import chromadb

from app.core.exceptions import VectorStoreError
from app.schemas.vector import SearchResult, VectorDocument
from app.vectorstores.base import VectorRepository


def _build_where_clause(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    if not filters:
        return None
    if len(filters) == 1:
        ((key, value),) = filters.items()
        return {key: value}
    return {"$and": [{key: value} for key, value in filters.items()]}


class ChromaVectorRepository(VectorRepository):
    def __init__(self, *, persist_path: str, collection_name: str) -> None:
        try:
            self._client = chromadb.PersistentClient(path=persist_path)
            self._collection = self._client.get_or_create_collection(
                name=collection_name, metadata={"hnsw:space": "cosine"}
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Falha ao inicializar o Chroma: {exc}") from exc

    def add_documents(self, documents: list[VectorDocument]) -> None:
        if not documents:
            return
        try:
            self._collection.add(
                ids=[doc.id for doc in documents],
                embeddings=[doc.embedding for doc in documents],
                documents=[doc.text for doc in documents],
                metadatas=[doc.metadata for doc in documents],
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Falha ao indexar chunks no Chroma: {exc}") from exc

    def search(
        self, query_vector: list[float], filters: dict[str, Any] | None, limit: int
    ) -> list[SearchResult]:
        try:
            raw = self._collection.query(
                query_embeddings=[query_vector],
                n_results=limit,
                where=_build_where_clause(filters),
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Falha ao consultar o Chroma: {exc}") from exc

        ids = raw.get("ids") or [[]]
        documents = raw.get("documents") or [[]]
        metadatas = raw.get("metadatas") or [[]]
        distances = raw.get("distances") or [[]]

        results: list[SearchResult] = []
        for doc_id, text, metadata, distance in zip(
            ids[0], documents[0], metadatas[0], distances[0], strict=True
        ):
            score = max(0.0, 1.0 - distance)
            results.append(
                SearchResult(id=doc_id, text=text, metadata=dict(metadata), score=score)
            )
        return results

    def delete_by_document(self, document_id: str) -> None:
        try:
            self._collection.delete(where={"document_id": document_id})
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Falha ao excluir vetores do documento: {exc}") from exc

    def delete_by_version(self, version_id: str) -> None:
        try:
            self._collection.delete(where={"version_id": version_id})
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Falha ao excluir vetores da versao: {exc}") from exc

    def count(self) -> int:
        return self._collection.count()
