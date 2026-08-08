"""Painel administrativo basico (secao 26 do prompt mestre)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from api_client import ApiError, get_metrics_summary
st.set_page_config(page_title="Painel - AxysAI", page_icon="📊", layout="wide")

st.title("📊 Painel")

try:
    metrics = get_metrics_summary()
except ApiError as exc:
    st.error(f"Falha ao carregar metricas: {exc.message}")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Documentos indexados", metrics["total_documents"])
col2.metric("Perguntas realizadas", metrics["questions_asked"])
col3.metric("Respostas sem evidencia", metrics["answers_without_evidence"])
col4.metric(
    "Avaliacoes",
    f"👍 {metrics['positive_feedback']} / 👎 {metrics['negative_feedback']}",
)

st.divider()

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Documentos por status")
    if metrics["documents_by_status"]:
        st.bar_chart(metrics["documents_by_status"])
    else:
        st.info("Nenhum documento indexado ainda.")

with col_b:
    st.subheader("Documentos por categoria")
    if metrics["documents_by_category"]:
        st.bar_chart(metrics["documents_by_category"])
    else:
        st.info("Nenhum documento categorizado ainda.")
