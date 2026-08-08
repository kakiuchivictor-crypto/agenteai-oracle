"""Nos de permissoes, recuperacao hibrida e montagem de contexto (secao 24).

Reaproveita as primitivas ja implementadas na Fase 4 (`app.retrieval.*`) —
este modulo apenas orquestra essas funcoes como nos do grafo do agente,
sem duplicar logica de busca/fusao/permissoes.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.agents.state import AgentState, Citation
from app.core.config import Settings
from app.database.models import Category, Document
from app.embeddings.base import BaseEmbeddingProvider
from app.reranking.base import BaseReranker
from app.retrieval.fusion import fuse_results
from app.retrieval.lexical_search import lexical_search
from app.retrieval.permissions import categorize_results
from app.retrieval.vector_search import vector_search
from app.schemas.vector import SearchResult
from app.vectorstores.base import VectorRepository


def make_retrieve_candidates(
    embedding_provider: BaseEmbeddingProvider, vector_repository: VectorRepository, settings: Settings
):
    def retrieve_candidates(state: AgentState) -> dict:
        query = state.get("rewritten_query") or state["normalized_question"]
        results = vector_search(
            query,
            embedding_provider=embedding_provider,
            vector_repository=vector_repository,
            limit=settings.retrieval_candidates,
            filters=state.get("retrieval_filters") or None,
        )
        return {"vector_results": results}

    return retrieve_candidates


def make_lexical_search_node(session: Session, settings: Settings):
    def lexical_search_node(state: AgentState) -> dict:
        if not settings.hybrid_search_enabled:
            return {"lexical_results": []}
        query = state.get("rewritten_query") or state["normalized_question"]
        results = lexical_search(query, session=session, limit=settings.retrieval_candidates)
        return {"lexical_results": results}

    return lexical_search_node


def make_merge_results(session: Session, settings: Settings):
    def merge_results(state: AgentState) -> dict:
        fused = fuse_results(
            [state.get("vector_results") or [], state.get("lexical_results") or []],
            strategy=settings.hybrid_fusion_strategy.value,
            rrf_k=settings.hybrid_rrf_k,
        )
        categorized = categorize_results(fused, session=session)

        if not fused:
            route = "no_evidence"
        elif categorized.authorized:
            route = "continue"
        elif categorized.pending_approval:
            # Existe conteudo relevante, mas ainda nao aprovado pela
            # curadoria (secao 8: so documentos aprovados sao usados).
            route = "pending_approval"
        else:
            route = "no_evidence"

        return {
            "fused_results": fused,
            "authorized_results": categorized.authorized,
            "route": route,
        }

    return merge_results


def make_rerank_results(reranker: BaseReranker, settings: Settings):
    def rerank_results(state: AgentState) -> dict:
        question = state["normalized_question"]
        rewritten = state.get("rewritten_query") or question
        candidates = state.get("authorized_results") or []

        reranked = reranker.rerank(rewritten, candidates, top_k=settings.rerank_top_k)
        if rewritten != question:
            # `rewritten_query` mistura a pergunta atual com as anteriores
            # (rewrite_query, secao 23) para ajudar continuacoes vagas ("e
            # para compras internacionais?"). Mas quando a pergunta atual
            # MUDA de assunto, essa mistura confunde o reranker: ele pontua
            # mal o trecho certo porque a consulta fala de dois assuntos ao
            # mesmo tempo (bug real observado: pergunta sobre LGPD logo
            # apos pergunta sobre limite de API fazia o trecho de LGPD cair
            # do 1o para o 3o lugar). Rerankear tambem so com a pergunta
            # atual e ficar com o MAIOR score entre as duas rodadas cobre
            # os dois casos — continuacao e troca de assunto — sem regredir
            # nenhum dos dois.
            by_current_question = reranker.rerank(question, candidates, top_k=settings.rerank_top_k)
            best_by_id: dict[str, SearchResult] = {r.id: r for r in reranked}
            for result in by_current_question:
                existing = best_by_id.get(result.id)
                if existing is None or result.score > existing.score:
                    best_by_id[result.id] = result
            reranked = sorted(best_by_id.values(), key=lambda r: r.score, reverse=True)[: settings.rerank_top_k]

        # Descarta "vizinhos mais proximos" que nao sao realmente relevantes
        # (ver comentario de `rerank_min_score` em app/core/config.py) — sem
        # isso, o CONTEXTO nunca ficaria vazio numa base ja populada, e o
        # modo de conhecimento geral do agente nunca seria acionado.
        relevant = [r for r in reranked if r.score >= settings.rerank_min_score]
        return {"search_results": relevant}

    return rerank_results


def validate_evidence(state: AgentState) -> dict:
    results = state.get("search_results") or []
    return {"route": "no_evidence" if not results else "continue"}


def make_build_context(session: Session, settings: Settings):
    def build_context(state: AgentState) -> dict:
        results = state.get("search_results") or []

        document_ids = {
            r.metadata.get("document_id") for r in results if r.metadata.get("document_id")
        }
        documents_by_id: dict[str, Document] = {}
        if document_ids:
            documents = session.exec(select(Document).where(Document.id.in_(document_ids))).all()
            documents_by_id = {d.id: d for d in documents}

        category_ids = {d.category_id for d in documents_by_id.values() if d.category_id}
        category_names: dict[str, str] = {}
        if category_ids:
            categories = session.exec(select(Category).where(Category.id.in_(category_ids))).all()
            category_names = {c.id: c.name for c in categories}

        context_blocks: list[str] = []
        citations: list[Citation] = []
        used_chars = 0

        for index, result in enumerate(results, start=1):
            label = f"Fonte {index}"
            document = documents_by_id.get(result.metadata.get("document_id"))
            document_name = document.original_filename if document else "documento"
            # O bloco usa o NOME do documento, nao um marcador tipo
            # "[Fonte 1]" — o modelo tende a repetir literalmente o que ve
            # no contexto, entao dar a ele o nome real permite uma citacao
            # natural na resposta ("De acordo com a Politica de Reembolso...")
            # em vez de colchetes artificiais. A lista completa de fontes
            # (pagina/secao/trecho) e exibida separadamente para o usuario.
            block = f"Documento: {document_name}\n{result.text.strip()}"
            if context_blocks and used_chars + len(block) > settings.max_context_chars:
                break
            context_blocks.append(block)
            used_chars += len(block)

            citations.append(
                Citation(
                    label=label,
                    document_id=result.metadata.get("document_id", ""),
                    document_name=document.original_filename if document else "Documento",
                    category=category_names.get(document.category_id) if document else None,
                    page=result.metadata.get("page"),
                    section=result.metadata.get("section"),
                    slide=result.metadata.get("slide"),
                    sheet_name=result.metadata.get("sheet_name"),
                    row_number=result.metadata.get("row_number"),
                    table_name=result.metadata.get("table_name"),
                    version_number=result.metadata.get("version_number"),
                    updated_at=document.updated_at.isoformat() if document else None,
                    snippet=result.text.strip()[:800],
                )
            )

        return {"context_text": "\n\n".join(context_blocks), "citations": citations}

    return build_context
