"""Teste de limitacao basica de requisicoes (secao 29 do prompt mestre)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.api.dependencies.db import get_db_session
from app.api.dependencies.providers import (
    get_chat_model_dep,
    get_embedding_provider_dep,
    get_reranker_dep,
    get_vector_repository_dep,
)
from app.api.main import create_app
from app.core.config import get_settings


def test_rate_limit_returns_429_after_threshold(
    db_session, embedding_provider, vector_repository, reranker, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_embedding_provider_dep] = lambda: embedding_provider
    app.dependency_overrides[get_vector_repository_dep] = lambda: vector_repository
    app.dependency_overrides[get_reranker_dep] = lambda: reranker
    app.dependency_overrides[get_chat_model_dep] = lambda: FakeListChatModel(responses=["ok"] * 10)

    with TestClient(app) as client:
        statuses = [client.get("/health").status_code for _ in range(5)]

    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:]


def test_rate_limit_response_has_standard_error_format(
    db_session, embedding_provider, vector_repository, reranker, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_embedding_provider_dep] = lambda: embedding_provider
    app.dependency_overrides[get_vector_repository_dep] = lambda: vector_repository
    app.dependency_overrides[get_reranker_dep] = lambda: reranker
    app.dependency_overrides[get_chat_model_dep] = lambda: FakeListChatModel(responses=["ok"] * 10)

    with TestClient(app) as client:
        client.get("/health")
        response = client.get("/health")

    assert response.status_code == 429
    payload = response.json()
    assert payload["error_code"] == "rate_limit_exceeded"
    assert "message" in payload
