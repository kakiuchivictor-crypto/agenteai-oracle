"""Pagina de configuracoes (secao 26 do prompt mestre).

Somente leitura: os parametros sao definidos no `.env` do backend. Nenhuma
chave secreta e exibida aqui (nem sequer transita pela API)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from api_client import ApiError, get_system_config
st.set_page_config(page_title="Configuracoes - AxysAI", page_icon="⚙️", layout="wide")

st.title("⚙️ Configuracoes do Sistema")

st.info(
    "Estes parametros sao carregados do arquivo `.env` do backend na inicializacao. "
    "Para altera-los, edite o `.env` e reinicie a aplicacao. Nenhuma chave de API ou "
    "segredo e exibido aqui.",
    icon="ℹ️",
)

try:
    config = get_system_config()
except ApiError as exc:
    st.error(f"Falha ao carregar configuracoes: {exc.message}")
    st.stop()

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Modelo de linguagem")
    st.write(f"**Provedor:** {config['llm_provider']}")
    st.write(f"**Modelo:** {config['llm_model']}")

    st.subheader("Embeddings")
    st.write(f"**Provedor:** {config['embedding_provider']}")
    st.write(f"**Modelo:** {config['embedding_model']}")
    st.write(f"**Dimensao:** {config['embedding_dimension']}")

with col2:
    st.subheader("Recuperacao e reranking")
    st.write(f"**Banco vetorial:** {config['vector_store_provider']}")
    st.write(f"**Busca hibrida ativa:** {'Sim' if config['hybrid_search_enabled'] else 'Nao'}")
    st.write(f"**Estrategia de fusao:** {config['hybrid_fusion_strategy']}")
    st.write(f"**Candidatos recuperados:** {config['retrieval_candidates']}")
    st.write(f"**Reranker:** {config['reranker_provider']} ({config['reranker_model']})")
    st.write(f"**Resultados finais (top-k):** {config['rerank_top_k']}")
    st.write(f"**Score minimo pos-reranking:** {config['rerank_min_score']}")

with col3:
    st.subheader("Chunking e ingestao")
    st.write(f"**Tamanho do chunk:** {config['chunk_size']}")
    st.write(f"**Overlap:** {config['chunk_overlap']}")
    st.write(f"**Tamanho maximo do chunk:** {config['max_chunk_size']}")
    st.write(f"**OCR ativo:** {'Sim' if config['ocr_enabled'] else 'Nao'}")
    st.write(f"**Idioma do OCR:** {config['ocr_language']}")
    st.write(f"**Tamanho maximo de upload:** {config['max_upload_size_mb']} MB")
    st.write(f"**Extensoes permitidas:** {', '.join(config['allowed_extensions'])}")

st.divider()
st.write(f"**Limite de requisicoes por minuto:** {config['rate_limit_per_minute']}")
