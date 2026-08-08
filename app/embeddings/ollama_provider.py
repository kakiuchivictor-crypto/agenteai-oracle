"""Provedor de embeddings via Ollama (modelo local, ex: nomic-embed-text)."""

from __future__ import annotations

from app.core.exceptions import EmbeddingGenerationError, ProviderUnavailableError
from app.embeddings.base import BaseEmbeddingProvider


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, model_name: str, base_url: str) -> None:
        from langchain_ollama import OllamaEmbeddings

        self._model_name = model_name
        self._client = OllamaEmbeddings(model=model_name, base_url=base_url)
        self._dimension: int | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            embeddings = self._client.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_error(exc) from exc
        if self._dimension is None and embeddings:
            self._dimension = len(embeddings[0])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        try:
            embedding = self._client.embed_query(text)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_error(exc) from exc
        if self._dimension is None:
            self._dimension = len(embedding)
        return embedding

    @staticmethod
    def _translate_error(exc: Exception) -> Exception:
        message = str(exc).lower()
        if "connection" in message or "refused" in message:
            return ProviderUnavailableError(
                "Nao foi possivel conectar ao Ollama. Verifique se o servico esta em "
                "execucao e se OLLAMA_BASE_URL esta correto."
            )
        return EmbeddingGenerationError(f"Falha ao gerar embedding via Ollama: {exc}")

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            raise EmbeddingGenerationError(
                "Dimensao do embedding Ollama ainda desconhecida (nenhuma chamada realizada)."
            )
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "ollama"
