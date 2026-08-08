"""Fabrica do repositorio vetorial, selecionado por `VECTOR_STORE_PROVIDER`."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, VectorStoreProvider, get_settings
from app.core.exceptions import MissingConfigurationError
from app.vectorstores.base import VectorRepository


def build_vector_repository(settings: Settings) -> VectorRepository:
    if settings.vector_store_provider == VectorStoreProvider.CHROMA:
        from app.vectorstores.chroma_repository import ChromaVectorRepository

        return ChromaVectorRepository(
            persist_path=settings.vector_store_path,
            collection_name=settings.vector_store_collection,
        )

    raise MissingConfigurationError(
        f"VECTOR_STORE_PROVIDER '{settings.vector_store_provider}' nao e suportado."
    )


@lru_cache
def get_vector_repository() -> VectorRepository:
    settings = get_settings()
    settings.ensure_runtime_directories()
    return build_vector_repository(settings)
