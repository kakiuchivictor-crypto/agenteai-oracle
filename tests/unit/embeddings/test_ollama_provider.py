"""Testa a traducao de erros do provedor de embeddings Ollama (secao 41)."""

from __future__ import annotations

import pytest

from app.core.exceptions import EmbeddingGenerationError, ProviderUnavailableError
from app.embeddings.ollama_provider import OllamaEmbeddingProvider


class _FakeFailingClient:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise self._exc

    def embed_query(self, text: str) -> list[float]:
        raise self._exc


def _provider_with_fake_client(exc: Exception) -> OllamaEmbeddingProvider:
    provider = OllamaEmbeddingProvider("nomic-embed-text", "http://localhost:11434")
    provider._client = _FakeFailingClient(exc)
    return provider


def test_translates_connection_error_to_provider_unavailable() -> None:
    provider = _provider_with_fake_client(ConnectionError("connection refused"))
    with pytest.raises(ProviderUnavailableError):
        provider.embed_query("teste")


def test_translates_generic_error_to_embedding_generation_error() -> None:
    provider = _provider_with_fake_client(ValueError("formato invalido"))
    with pytest.raises(EmbeddingGenerationError):
        provider.embed_documents(["a", "b"])
