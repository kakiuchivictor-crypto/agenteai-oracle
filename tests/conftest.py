"""Fixtures compartilhados por toda a suite (unit/integration/security)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from sqlmodel import Session, SQLModel, create_engine

import app.database.models  # noqa: F401 - popula o metadata antes do create_all
from app.api.dependencies.db import get_db_session
from app.api.dependencies.providers import (
    get_chat_model_dep,
    get_embedding_provider_dep,
    get_reranker_dep,
    get_vector_repository_dep,
)
from app.api.main import create_app
from app.core.config import Settings
from app.embeddings.sentence_transformer_provider import SentenceTransformerEmbeddingProvider
from app.reranking.cross_encoder_reranker import CrossEncoderReranker
from app.vectorstores.chroma_repository import ChromaVectorRepository

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "documents"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    # Sem isso, o Engine (e a conexao pool subjacente) so era liberado pelo
    # coletor de lixo — gerava um ResourceWarning "unclosed database" por
    # teste (visivel com `pytest -W error` ou `--cov`) e, num run longo,
    # podia acumular handles de arquivo abertos desnecessariamente.
    engine.dispose()


@pytest.fixture
def vector_repository(tmp_path: Path) -> ChromaVectorRepository:
    return ChromaVectorRepository(
        persist_path=str(tmp_path / "vector_store"), collection_name="test_documents"
    )


@pytest.fixture(scope="session")
def embedding_provider() -> SentenceTransformerEmbeddingProvider:
    # Modelo pequeno e ja usado no restante do projeto: reaproveita o cache
    # local do HuggingFace baixado durante o desenvolvimento da Fase 3.
    return SentenceTransformerEmbeddingProvider("intfloat/multilingual-e5-base")


@pytest.fixture(scope="session")
def reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2")


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        upload_dir=str(tmp_path / "uploads"),
        processed_dir=str(tmp_path / "processed"),
        vector_store_path=str(tmp_path / "vector_store"),
        log_dir=str(tmp_path / "logs"),
        chunk_size=400,
        chunk_overlap=50,
        max_chunk_size=600,
        # Fixado explicitamente (independente do padrao de classe): varios
        # testes exercitam o comportamento de "documento fica pendente ate
        # ser aprovado" e precisam de um ponto de partida deterministico.
        auto_approve_on_upload=False,
        # Desligado (0) nos testes: o limitador de chamadas ao LLM e
        # cacheado pelo VALOR do limite (ver `get_llm_rate_limiter`) — se os
        # testes usassem o mesmo limite do `.env` real, a suite inteira
        # compartilharia (e esgotaria) a mesma janela de chamadas, causando
        # falhas intermitentes sem relacao com o que cada teste verifica.
        llm_rate_limit_per_minute=0,
    )


@pytest.fixture
def api_client(db_session, embedding_provider, vector_repository, reranker):
    fake_chat_model = FakeListChatModel(responses=["Resposta padrao de teste. [Fonte 1]"] * 50)

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_embedding_provider_dep] = lambda: embedding_provider
    app.dependency_overrides[get_vector_repository_dep] = lambda: vector_repository
    app.dependency_overrides[get_reranker_dep] = lambda: reranker
    app.dependency_overrides[get_chat_model_dep] = lambda: fake_chat_model

    with TestClient(app) as client:
        yield client
