"""Estado tipado do agente RAG (secao 24 do prompt mestre)."""

from __future__ import annotations

from typing import TypedDict

from app.schemas.vector import SearchResult


class ChatTurn(TypedDict):
    role: str  # "user" | "assistant"
    content: str


class Citation(TypedDict):
    label: str  # "Fonte 1", "Fonte 2", ...
    document_id: str
    document_name: str
    category: str | None
    page: int | None
    section: str | None
    slide: int | None
    sheet_name: str | None
    row_number: int | None
    table_name: str | None
    version_number: int | None
    updated_at: str | None
    snippet: str  # trecho utilizado, para o usuario expandir e conferir (secao 22)


class AgentState(TypedDict, total=False):
    # --- Entrada ---
    correlation_id: str
    session_id: str
    user_id: str
    question: str
    chat_history: list[ChatTurn]
    category_filter: str | None

    # --- Processamento ---
    normalized_question: str
    intent: str  # question | admin_request | ingestion_request | out_of_scope | invalid
    rewritten_query: str
    retrieval_filters: dict
    vector_results: list[SearchResult]
    lexical_results: list[SearchResult]
    fused_results: list[SearchResult]
    authorized_results: list[SearchResult]
    search_results: list[SearchResult]
    context_text: str
    citations: list[Citation]

    # --- Saida ---
    answer: str
    message_id: str
    grounded: bool
    model_used: str
    latency_ms: int
    route: str
    error: str | None
