"""Fabrica de provedores de embedding, selecionados por `EMBEDDING_PROVIDER`."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import EmbeddingProvider, Settings, get_settings
from app.core.exceptions import MissingConfigurationError
from app.embeddings.base import BaseEmbeddingProvider


def build_embedding_provider(settings: Settings) -> BaseEmbeddingProvider:
    if settings.embedding_provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
        from app.embeddings.sentence_transformer_provider import (
            SentenceTransformerEmbeddingProvider,
        )

        return SentenceTransformerEmbeddingProvider(settings.embedding_model)

    if settings.embedding_provider == EmbeddingProvider.OPENAI:
        from app.embeddings.openai_provider import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider(settings.embedding_model, settings.openai_api_key)

    if settings.embedding_provider == EmbeddingProvider.OLLAMA:
        from app.embeddings.ollama_provider import OllamaEmbeddingProvider

        return OllamaEmbeddingProvider(settings.embedding_model, settings.ollama_base_url)

    raise MissingConfigurationError(
        f"EMBEDDING_PROVIDER '{settings.embedding_provider}' nao e suportado."
    )


@lru_cache
def get_embedding_provider() -> BaseEmbeddingProvider:
    """Instancia (cacheada) do provedor de embedding configurado no .env."""
    return build_embedding_provider(get_settings())
