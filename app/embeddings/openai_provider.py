"""Provedor de embeddings via API da OpenAI (alternativa paga/em nuvem)."""

from __future__ import annotations

from app.core.exceptions import EmbeddingGenerationError, MissingConfigurationError
from app.embeddings.base import BaseEmbeddingProvider

# Dimensoes conhecidas dos modelos de embedding mais comuns da OpenAI.
_KNOWN_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, model_name: str, api_key: str) -> None:
        if not api_key:
            raise MissingConfigurationError(
                "OPENAI_API_KEY e obrigatoria para usar EMBEDDING_PROVIDER=openai."
            )
        from langchain_openai import OpenAIEmbeddings

        self._model_name = model_name
        self._client = OpenAIEmbeddings(model=model_name, api_key=api_key)
        self._dimension = _KNOWN_DIMENSIONS.get(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            embeddings = self._client.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingGenerationError(f"Falha ao gerar embeddings via OpenAI: {exc}") from exc
        if self._dimension is None and embeddings:
            self._dimension = len(embeddings[0])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        try:
            embedding = self._client.embed_query(text)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingGenerationError(
                f"Falha ao gerar embedding da consulta via OpenAI: {exc}"
            ) from exc
        if self._dimension is None:
            self._dimension = len(embedding)
        return embedding

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            raise EmbeddingGenerationError(
                "Dimensao do embedding OpenAI ainda desconhecida (nenhuma chamada realizada)."
            )
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "openai"
