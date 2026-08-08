"""Testa o fallback automatico para reranking heuristico (secao 19)."""

from __future__ import annotations

from app.core.config import Settings
from app.reranking.cross_encoder_reranker import CrossEncoderReranker
from app.reranking.factory import build_reranker
from app.reranking.heuristic_reranker import HeuristicReranker


def test_builds_cross_encoder_by_default() -> None:
    settings = Settings(
        _env_file=None, reranker_provider="cross_encoder",
        reranker_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    reranker = build_reranker(settings)
    assert isinstance(reranker, CrossEncoderReranker)


def test_falls_back_to_heuristic_when_cross_encoder_fails_to_load(monkeypatch) -> None:
    def _boom(self, model_name: str) -> None:  # noqa: ARG001
        raise RuntimeError("modelo indisponivel neste ambiente")

    monkeypatch.setattr(CrossEncoderReranker, "__init__", _boom)

    settings = Settings(_env_file=None, reranker_provider="cross_encoder", reranker_model="qualquer")
    reranker = build_reranker(settings)
    assert isinstance(reranker, HeuristicReranker)


def test_builds_heuristic_when_explicitly_configured() -> None:
    settings = Settings(_env_file=None, reranker_provider="heuristic")
    reranker = build_reranker(settings)
    assert isinstance(reranker, HeuristicReranker)
