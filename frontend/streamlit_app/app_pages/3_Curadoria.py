"""Pagina de curadoria de documentos (secao 8 e 26 do prompt mestre)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from api_client import (
    ApiError,
    approve_document,
    delete_document,
    list_documents,
    reindex_document,
    reject_document,
)
st.set_page_config(page_title="Curadoria - AxysAI", page_icon="✅", layout="wide")

st.title("✅ Curadoria de Documentos")

st.caption(
    "Somente documentos aprovados sao utilizados pelo agente para responder perguntas. "
    "Revise os documentos pendentes abaixo."
)

STATUS_LABELS = {
    "pending_review": "Pendente de revisao",
    "approved": "Aprovado",
    "rejected": "Rejeitado",
    "outdated": "Desatualizado",
    "replaced": "Substituido",
    "archived": "Arquivado",
    "duplicate": "Duplicata",
}
STATUS_TABS = ["pending_review", "approved", "rejected", "duplicate", "archived"]

tabs = st.tabs([STATUS_LABELS[status] for status in STATUS_TABS])

for tab, status in zip(tabs, STATUS_TABS, strict=True):
    with tab:
        try:
            documents = list_documents(status_filter=status)
        except ApiError as exc:
            st.error(f"Falha ao carregar documentos: {exc.message}")
            documents = []

        if not documents:
            st.info("Nenhum documento neste status.")
            continue

        for document in documents:
            with st.container(border=True):
                st.markdown(f"**{document['original_filename']}**")
                st.caption(
                    f"Formato: {document['format'].upper()} · "
                    f"Classificacao: {document['access_classification']} · "
                    f"Enviado em: {document['created_at'][:19].replace('T', ' ')}"
                )

                reason_key = f"reason_{document['id']}_{status}"
                if status == "pending_review":
                    reason = st.text_input("Motivo (opcional)", key=reason_key)
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Aprovar", key=f"approve_{document['id']}", use_container_width=True):
                            try:
                                approve_document(document["id"], reason or None)
                                st.success("Documento aprovado.")
                                st.rerun()
                            except ApiError as exc:
                                st.error(f"Falha ao aprovar: {exc.message}")
                    with col2:
                        if st.button("❌ Rejeitar", key=f"reject_{document['id']}", use_container_width=True):
                            try:
                                reject_document(document["id"], reason or None)
                                st.success("Documento rejeitado.")
                                st.rerun()
                            except ApiError as exc:
                                st.error(f"Falha ao rejeitar: {exc.message}")

                elif status == "approved":
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔄 Reindexar", key=f"reindex_{document['id']}", use_container_width=True):
                            try:
                                with st.spinner("Reindexando..."):
                                    result = reindex_document(document["id"])
                                if result["status"] == "success":
                                    st.success(f"Reindexado: {result['chunks_indexed']} trechos.")
                                else:
                                    st.error(f"Falha ao reindexar: {result.get('error')}")
                            except ApiError as exc:
                                st.error(f"Falha ao reindexar: {exc.message}")
                    with col2:
                        if st.button("🗑️ Arquivar/Excluir", key=f"delete_{document['id']}", use_container_width=True):
                            try:
                                delete_document(document["id"])
                                st.success("Documento arquivado e removido do indice de busca.")
                                st.rerun()
                            except ApiError as exc:
                                st.error(f"Falha ao excluir: {exc.message}")

                elif status in {"rejected", "duplicate"}:
                    if st.button(
                        "🗑️ Arquivar definitivamente", key=f"archive_{document['id']}",
                        use_container_width=True,
                    ):
                        try:
                            delete_document(document["id"])
                            st.success("Documento arquivado.")
                            st.rerun()
                        except ApiError as exc:
                            st.error(f"Falha ao arquivar: {exc.message}")
