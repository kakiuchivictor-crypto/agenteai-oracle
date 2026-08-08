"""Testa o provedor de embeddings OpenAI: validacao de config e erros (secao 41)."""

from __future__ import annotations

import pytest

from app.core.exceptions import EmbeddingGenerationError, MissingConfigurationError
from app.embeddings.openai_provider import OpenAIEmbeddingProvider


def test_requires_api_key() -> None:
    with pytest.raises(MissingConfigurationError):
        OpenAIEmbeddingProvider("text-embedding-3-small", api_key="")


class _FakeFailingClient:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise self._exc

    def embed_query(self, text: str) -> list[float]:
        raise self._exc


def test_translates_client_error_to_embedding_generation_error() -> None:
    provider = OpenAIEmbeddingProvider("text-embedding-3-small", api_key="sk-fake-key")
    provider._client = _FakeFailingClient(RuntimeError("falha na API"))
    with pytest.raises(EmbeddingGenerationError):
        provider.embed_query("teste")


def test_known_model_dimension_available_before_any_call() -> None:
    provider = OpenAIEmbeddingProvider("text-embedding-3-small", api_key="sk-fake-key")
    assert provider.dimension == 1536
