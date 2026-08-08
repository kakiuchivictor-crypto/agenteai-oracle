"""Grafo LangGraph do agente RAG conversacional (secao 24 do prompt mestre).

START -> validate_question -> identify_intent -> rewrite_query ->
determine_filters -> retrieve_candidates -> lexical_search -> merge_results ->
rerank_results -> validate_evidence -> build_context -> generate_answer ->
verify_grounding -> format_citations -> save_interaction -> END

Qualquer etapa pode desviar diretamente para `save_interaction` com uma
mensagem padronizada quando a pergunta e invalida, fora de escopo, ainda
pendente de curadoria, ou quando o provedor de LLM falha — essas
ramificacoes espelham a lista de casos da secao 24 (o sistema nao tem
login/RBAC, entao nao ha ramificacao de acesso negado). "Sem evidencia" NAO
e mais uma saida antecipada: quando nenhum documento cobre o assunto, o
pipeline segue ate `generate_answer`, que cai no modo de conhecimento geral
do `SYSTEM_PROMPT` (ver `app/agents/prompts/templates.py`) em vez de recusar
a resposta de cara.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langchain_core.language_models.chat_models import BaseChatModel
from sqlmodel import Session

from app.agents.nodes.generation import format_citations, make_generate_answer, verify_grounding
from app.agents.nodes.persistence import make_save_interaction
from app.agents.nodes.retrieval import (
    make_build_context,
    make_lexical_search_node,
    make_merge_results,
    make_rerank_results,
    make_retrieve_candidates,
    validate_evidence,
)
from app.agents.nodes.validation import (
    determine_filters,
    identify_intent,
    rewrite_query,
    validate_question,
)
from app.agents.state import AgentState
from app.core.config import Settings
from app.embeddings.base import BaseEmbeddingProvider
from app.reranking.base import BaseReranker
from app.vectorstores.base import VectorRepository

_EARLY_EXIT_ROUTES = {
    "invalid",
    "out_of_scope",
    "admin_request",
    "ingestion_request",
    "pending_approval",
    "provider_error",
    "provider_busy",
}


def _route_or_continue(next_node: str):
    def router(state: AgentState) -> str:
        route = state.get("route", "continue")
        return "save_interaction" if route in _EARLY_EXIT_ROUTES else next_node

    return router


def build_agent_graph(
    *,
    session: Session,
    chat_model: BaseChatModel,
    embedding_provider: BaseEmbeddingProvider,
    vector_repository: VectorRepository,
    reranker: BaseReranker,
    settings: Settings,
):
    graph = StateGraph(AgentState)

    graph.add_node("validate_question", validate_question)
    graph.add_node("identify_intent", identify_intent)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("determine_filters", determine_filters)
    graph.add_node(
        "retrieve_candidates", make_retrieve_candidates(embedding_provider, vector_repository, settings)
    )
    graph.add_node("lexical_search", make_lexical_search_node(session, settings))
    graph.add_node("merge_results", make_merge_results(session, settings))
    graph.add_node("rerank_results", make_rerank_results(reranker, settings))
    graph.add_node("validate_evidence", validate_evidence)
    graph.add_node("build_context", make_build_context(session, settings))
    graph.add_node("generate_answer", make_generate_answer(chat_model, settings, session))
    graph.add_node("verify_grounding", verify_grounding)
    graph.add_node("format_citations", format_citations)
    graph.add_node("save_interaction", make_save_interaction(session))

    graph.set_entry_point("validate_question")

    graph.add_conditional_edges(
        "validate_question",
        _route_or_continue("identify_intent"),
        {"identify_intent": "identify_intent", "save_interaction": "save_interaction"},
    )
    graph.add_conditional_edges(
        "identify_intent",
        _route_or_continue("rewrite_query"),
        {"rewrite_query": "rewrite_query", "save_interaction": "save_interaction"},
    )

    graph.add_edge("rewrite_query", "determine_filters")
    graph.add_edge("determine_filters", "retrieve_candidates")
    graph.add_edge("retrieve_candidates", "lexical_search")
    graph.add_edge("lexical_search", "merge_results")

    graph.add_conditional_edges(
        "merge_results",
        _route_or_continue("rerank_results"),
        {"rerank_results": "rerank_results", "save_interaction": "save_interaction"},
    )
    graph.add_edge("rerank_results", "validate_evidence")
    graph.add_conditional_edges(
        "validate_evidence",
        _route_or_continue("build_context"),
        {"build_context": "build_context", "save_interaction": "save_interaction"},
    )
    graph.add_edge("build_context", "generate_answer")
    graph.add_conditional_edges(
        "generate_answer",
        _route_or_continue("verify_grounding"),
        {"verify_grounding": "verify_grounding", "save_interaction": "save_interaction"},
    )
    graph.add_edge("verify_grounding", "format_citations")
    graph.add_edge("format_citations", "save_interaction")
    graph.add_edge("save_interaction", END)

    return graph.compile()
