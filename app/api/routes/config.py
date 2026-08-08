"""Rota de configuracao efetiva do sistema, somente leitura (secao 26).

Alterar estes parametros exige editar o `.env` e reiniciar a aplicacao —
nao existe persistencia de configuracao em runtime nesta versao. Expor um
formulario de edicao que nao gravasse nada seria uma funcionalidade
simulada, o que o prompt mestre proibe explicitamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.api.dependencies.providers import get_settings_dep
from app.schemas.api.config import SystemConfigResponse

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=SystemConfigResponse)
def read_system_config(settings: Settings = Depends(get_settings_dep)) -> SystemConfigResponse:
    return SystemConfigResponse(
        llm_provider=settings.llm_provider.value,
        llm_model=settings.llm_model,
        embedding_provider=settings.embedding_provider.value,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        vector_store_provider=settings.vector_store_provider.value,
        reranker_provider=settings.reranker_provider.value,
        reranker_model=settings.reranker_model,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        max_chunk_size=settings.max_chunk_size,
        retrieval_candidates=settings.retrieval_candidates,
        rerank_top_k=settings.rerank_top_k,
        rerank_min_score=settings.rerank_min_score,
        hybrid_search_enabled=settings.hybrid_search_enabled,
        hybrid_fusion_strategy=settings.hybrid_fusion_strategy.value,
        ocr_enabled=settings.ocr_enabled,
        ocr_language=settings.ocr_language,
        rate_limit_per_minute=settings.rate_limit_per_minute,
        max_upload_size_mb=settings.max_upload_size_mb,
        allowed_extensions=settings.allowed_extensions_list,
    )
