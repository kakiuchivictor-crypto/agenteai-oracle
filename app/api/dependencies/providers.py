"""Dependencias FastAPI para os provedores plugaveis (LLM, embeddings, banco
vetorial, reranker) — expostas como dependencias para permitir override em
testes (`app.dependency_overrides`)."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import Settings, get_settings
from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings.factory import get_embedding_provider
from app.llm.factory import get_chat_model
from app.reranking.base import BaseReranker
from app.reranking.factory import get_reranker
from app.vectorstores.base import VectorRepository
from app.vectorstores.factory import get_vector_repository


def get_settings_dep() -> Settings:
    return get_settings()


def get_embedding_provider_dep() -> BaseEmbeddingProvider:
    return get_embedding_provider()


def get_vector_repository_dep() -> VectorRepository:
    return get_vector_repository()


def get_reranker_dep() -> BaseReranker:
    return get_reranker()


def get_chat_model_dep() -> BaseChatModel:
    return get_chat_model()
