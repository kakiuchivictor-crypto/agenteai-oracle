"""Pagina de gestao de documentos: upload, processamento, listagem (secao 26)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from api_client import (
    ApiError,
    approve_document,
    list_categories,
    list_documents,
    process_document,
    reject_document,
    upload_document,
)

st.set_page_config(page_title="Documentos - AxysAI", page_icon="📄", layout="wide")

st.title("📄 Documentos")

STATUS_LABELS = {
    "pending_review": "Pendente de revisao",
    "approved": "Aprovado",
    "rejected": "Rejeitado",
    "outdated": "Desatualizado",
    "replaced": "Substituido",
    "archived": "Arquivado",
    "duplicate": "Duplicata",
}

st.subheader("Enviar novo documento")
try:
    categories = list_categories()
except ApiError:
    categories = []
category_options = {"Sem categoria": None} | {c["name"]: c["id"] for c in categories}

with st.form("upload_form", clear_on_submit=True):
    uploaded_files = st.file_uploader(
        "Arquivo(s) (PDF, Word, Excel, PowerPoint, Markdown, CSV, JSON ou HTML)",
        type=["pdf", "docx", "xlsx", "pptx", "md", "csv", "json", "html", "htm"],
        accept_multiple_files=True,
    )
    st.caption(
        "Selecione varios arquivos de uma vez (Ctrl/Cmd+clique ou arraste o grupo). "
        "Categoria, tags e demais campos abaixo se aplicam a todos os arquivos do lote."
    )
    col1, col2 = st.columns(2)
    with col1:
        category_label = st.selectbox("Categoria", list(category_options.keys()))
        tags = st.text_input("Tags (separadas por virgula)")
    with col2:
        department = st.text_input("Departamento")
        access_classification = st.selectbox(
            "Classificacao de acesso", ["public", "internal", "confidential"], index=1
        )
    is_official = st.checkbox("Documento oficial")
    submitted = st.form_submit_button("Enviar e processar", use_container_width=True)

if submitted:
    if not uploaded_files:
        st.error("Selecione pelo menos um arquivo.")
    else:
        results = []
        progress = st.progress(0.0, text="Iniciando envio...")
        for index, uploaded_file in enumerate(uploaded_files, start=1):
            progress.progress(
                index / len(uploaded_files),
                text=f"Enviando {uploaded_file.name} ({index}/{len(uploaded_files)})...",
            )
            try:
                result = upload_document(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    category_id=category_options[category_label],
                    tags=tags or None,
                    department=department or None,
                    access_classification=access_classification,
                    is_official=is_official,
                )
                if result["status"] == "duplicate":
                    results.append(
                        {
                            "name": uploaded_file.name,
                            "status": "duplicate",
                            "detail": f"Ja existe na base (documento {result['duplicate_of_document_id']}).",
                        }
                    )
                    continue

                process_result = process_document(result["document_id"])
                if process_result["status"] == "success":
                    results.append(
                        {
                            "name": uploaded_file.name,
                            "status": "success",
                            "detail": f"{process_result['chunks_indexed']} trechos indexados.",
                        }
                    )
                else:
                    results.append(
                        {
                            "name": uploaded_file.name,
                            "status": "failed",
                            "detail": process_result.get("error") or "Falha no processamento.",
                        }
                    )
            except ApiError as exc:
                results.append(
                    {"name": uploaded_file.name, "status": "failed", "detail": exc.message}
                )

        progress.empty()

        success_count = sum(1 for r in results if r["status"] == "success")
        duplicate_count = sum(1 for r in results if r["status"] == "duplicate")
        failed_count = sum(1 for r in results if r["status"] == "failed")

        if success_count:
            st.success(
                f"{success_count} de {len(results)} arquivo(s) processado(s) com sucesso. "
                "Aprove-os na lista abaixo (ou na pagina de Curadoria) para liberar para o chat."
            )
        if duplicate_count:
            st.warning(f"{duplicate_count} arquivo(s) ja existiam na base e foram ignorados.")
        if failed_count:
            st.error(f"{failed_count} arquivo(s) falharam no envio/processamento.")

        with st.expander("Detalhes por arquivo", expanded=failed_count > 0):
            status_icons = {"success": "✅", "duplicate": "⚠️", "failed": "❌"}
            for item in results:
                st.markdown(f"{status_icons[item['status']]} **{item['name']}** — {item['detail']}")

        st.rerun()

st.divider()
st.subheader("Documentos indexados")

col_a, col_b = st.columns(2)
with col_a:
    status_filter_label = st.selectbox(
        "Filtrar por status", ["Todos"] + list(STATUS_LABELS.values())
    )
with col_b:
    try:
        categories_for_filter = list_categories()
    except ApiError:
        categories_for_filter = []
    filter_category_options = {"Todas as categorias": None} | {
        c["name"]: c["id"] for c in categories_for_filter
    }
    filter_category_label = st.selectbox("Filtrar por categoria", list(filter_category_options.keys()))

status_filter_value = None
if status_filter_label != "Todos":
    status_filter_value = next(
        key for key, label in STATUS_LABELS.items() if label == status_filter_label
    )

try:
    documents = list_documents(
        status_filter=status_filter_value, category_id=filter_category_options[filter_category_label]
    )
except ApiError as exc:
    st.error(f"Falha ao carregar documentos: {exc.message}")
    documents = []

if not documents:
    st.info("Nenhum documento encontrado com os filtros atuais.")
else:
    for document in documents:
        status_label = STATUS_LABELS.get(document["status"], document["status"])
        is_pending = document["status"] == "pending_review"
        with st.container(border=True):
            cols = st.columns([4, 2, 2, 2, 2] if is_pending else [4, 2, 2, 2])
            cols[0].markdown(f"**{document['original_filename']}**")
            cols[0].caption(f"Formato: {document['format'].upper()} · Origem: {document['origin']}")
            cols[1].markdown(f"Status: `{status_label}`")
            cols[2].markdown("Oficial" if document["is_official"] else "—")
            cols[3].caption(document["created_at"][:19].replace("T", " "))

            # Aprovar/rejeitar direto aqui evita precisar navegar ate a
            # pagina de Curadoria só para o caso mais comum ao testar o
            # sistema: enviar um documento e libera-lo para o chat. Como nao
            # ha login/RBAC, qualquer pessoa pode fazer isso (a maioria dos
            # documentos ja chega aprovado automaticamente via
            # AUTO_APPROVE_ON_UPLOAD).
            if is_pending:
                with cols[4]:
                    approve_col, reject_col = st.columns(2)
                    if approve_col.button("✅", key=f"quick_approve_{document['id']}", help="Aprovar"):
                        try:
                            approve_document(document["id"])
                            st.success("Aprovado.")
                            st.rerun()
                        except ApiError as exc:
                            st.error(f"Falha ao aprovar: {exc.message}")
                    if reject_col.button("❌", key=f"quick_reject_{document['id']}", help="Rejeitar"):
                        try:
                            reject_document(document["id"])
                            st.success("Rejeitado.")
                            st.rerun()
                        except ApiError as exc:
                            st.error(f"Falha ao rejeitar: {exc.message}")
