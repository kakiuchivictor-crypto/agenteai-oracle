"""Schema de configuracao efetiva exposta somente leitura (secao 26).

Nunca inclui segredos (chaves de API, etc.) — apenas parametros operacionais
uteis para conferir o que esta ativo.
"""

from __future__ import annotations

from pydantic import BaseModel


class SystemConfigResponse(BaseModel):
    llm_provider: str
    llm_model: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    vector_store_provider: str
    reranker_provider: str
    reranker_model: str
    chunk_size: int
    chunk_overlap: int
    max_chunk_size: int
    retrieval_candidates: int
    rerank_top_k: int
    rerank_min_score: float
    hybrid_search_enabled: bool
    hybrid_fusion_strategy: str
    ocr_enabled: bool
    ocr_language: str
    rate_limit_per_minute: int
    max_upload_size_mb: int
    allowed_extensions: list[str]
