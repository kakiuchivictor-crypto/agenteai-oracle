"""Grafo LangGraph do pipeline de ingestao (secao 11 e 24 do prompt mestre).

Fonte -> Coleta/Validacao -> Extracao -> Limpeza -> Chunking ->
Validacao de qualidade -> Embeddings/Armazenamento vetorial ->
Disponibilizacao para consulta.

Falha em qualquer no desvia para `finalize_failure` sem lancar excecao,
permitindo que o chamador (servico de ingestao, que processa varios
arquivos em lote) continue com o proximo arquivo mesmo que este falhe.
"""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph
from sqlmodel import Session

from app.embeddings.base import BaseEmbeddingProvider
from app.ingestion.nodes import (
    chunk,
    clean,
    collect_and_validate,
    extract,
    finalize_failure,
    finalize_success,
    make_embed_and_store,
    quality_validate,
)
from app.ingestion.state import IngestionState
from app.vectorstores.base import VectorRepository


def _route_on_error(state: IngestionState) -> str:
    return "failed" if state.get("error") else "continue"


def build_ingestion_graph(
    *,
    session: Session,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    chunk_size: int,
    chunk_overlap: int,
    max_chunk_size: int,
):
    graph = StateGraph(IngestionState)

    graph.add_node("collect_and_validate", partial(collect_and_validate, session))
    graph.add_node("extract", partial(extract, session))
    graph.add_node("clean", partial(clean, session))
    graph.add_node(
        "chunk",
        partial(
            chunk,
            session,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            max_chunk_size=max_chunk_size,
        ),
    )
    graph.add_node("quality_validate", partial(quality_validate, session))
    graph.add_node(
        "embed_and_store", partial(make_embed_and_store(embedding_provider, vector_repository), session)
    )
    graph.add_node("finalize_success", partial(finalize_success, session))
    graph.add_node("finalize_failure", partial(finalize_failure, session))

    graph.set_entry_point("collect_and_validate")

    for node_name, next_node in (
        ("collect_and_validate", "extract"),
        ("extract", "clean"),
        ("clean", "chunk"),
        ("chunk", "quality_validate"),
        ("quality_validate", "embed_and_store"),
        ("embed_and_store", "finalize_success"),
    ):
        graph.add_conditional_edges(
            node_name,
            _route_on_error,
            {"failed": "finalize_failure", "continue": next_node},
        )

    graph.add_edge("finalize_success", END)
    graph.add_edge("finalize_failure", END)

    return graph.compile()
