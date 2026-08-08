"""Provedor de embeddings local via sentence-transformers (padrao do projeto).

Roda inteiramente offline apos o primeiro download do modelo, sem custo por
uso e sem dependencia de rede em producao. Modelos da familia E5 (padrao do
projeto: `intfloat/multilingual-e5-base`) exigem prefixar o texto com
"query: " ou "passage: " para obter a qualidade de busca esperada.
"""

from __future__ import annotations

from threading import Lock

from app.core.exceptions import EmbeddingGenerationError
from app.embeddings.base import BaseEmbeddingProvider

_model_cache: dict[str, object] = {}
_cache_lock = Lock()


def _load_model(model_name: str):
    with _cache_lock:
        if model_name not in _model_cache:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - dependencia declarada no projeto
                raise EmbeddingGenerationError(
                    "Biblioteca sentence-transformers nao instalada."
                ) from exc
            _model_cache[model_name] = SentenceTransformer(model_name)
        return _model_cache[model_name]


class SentenceTransformerEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._uses_e5_prefixes = "e5" in model_name.lower()
        self._model = _load_model(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"passage: {t}" if self._uses_e5_prefixes else t for t in texts]
        try:
            embeddings = self._model.encode(prefixed, show_progress_bar=False)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingGenerationError(f"Falha ao gerar embeddings: {exc}") from exc
        return [vector.tolist() for vector in embeddings]

    def embed_query(self, text: str) -> list[float]:
        prefixed = f"query: {text}" if self._uses_e5_prefixes else text
        try:
            embedding = self._model.encode([prefixed], show_progress_bar=False)[0]
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingGenerationError(f"Falha ao gerar embedding da consulta: {exc}") from exc
        return embedding.tolist()

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "sentence_transformers"
