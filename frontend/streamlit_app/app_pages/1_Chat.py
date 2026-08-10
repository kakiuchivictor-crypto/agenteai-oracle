"""Pagina de chat (secao 26 do prompt mestre).

O upload de documentos acontece aqui mesmo, pelo sinal de + do campo de
pergunta (`st.chat_input(accept_file=...)`) — nao existe mais uma pagina
dedicada de Documentos na navegacao. O historico de conversas e mantido
apenas na sessao do navegador (`st.session_state`): como o sistema nao tem
login, nao ha como (nem deveria) guardar/"lembrar" conversas de uma pessoa
especifica no backend sem misturar com as de outra.

Planilhas (.xlsx/.csv) anexadas com um pedido de "organizar" tomam um
caminho diferente do upload normal: em vez de entrar no indice de RAG, vao
para `/tools/organize-spreadsheet` (limpeza automatica via pandas, sem
execucao de codigo) e voltam como tabela + arquivo para baixar (e grafico,
so quando pedido) direto na conversa. O pedido de organizar pode vir numa
mensagem SEPARADA de quando o arquivo foi enviado — a ultima planilha
anexada na conversa fica lembrada (`active["last_spreadsheet"]`) para isso.

Redesenho de UI/UX (ver auditoria): sidebar com preview da ultima mensagem e
destaque de cor na conversa ativa; notas do sistema (upload, erro) usam um
componente visual proprio para nao se confundir com uma resposta real do
agente; resultado de planilha organizada agora e um card unico; e as acoes
destrutivas dos dialogos de confirmacao ficam vermelhas, nunca com a mesma
cor do botao "primary" comum.

Chegamos a exibir as fontes citadas (`response["citations"]`) como chips
abaixo da resposta, mas voltamos atras: a API retorna citacoes mesmo quando
a resposta diz explicitamente que nao encontrou nada sobre o assunto, o que
fazia a tela parecer se contradizer. A tela mostra so a resposta por
enquanto — reintroduzir citacoes exigiria o backend so retornar `citations`
quando de fato usadas na resposta.
"""

from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from api_client import (
    ApiError,
    get_system_config,
    organize_spreadsheet,
    process_document,
    send_chat_message,
    submit_feedback,
    upload_document,
)
from theme import card_header, conversation_preview, hero_header, pill, sidebar_status, system_note

ALLOWED_UPLOAD_TYPES = ["pdf", "docx", "xlsx", "pptx", "md", "csv", "json", "html", "htm"]
_MAX_TITLE_LENGTH = 40
_MAX_PREVIEW_LENGTH = 46
_AGENT_AVATAR = str(Path(__file__).resolve().parent.parent / "assets" / "axys_logo.png")

_SPREADSHEET_EXTENSIONS = {"xlsx", "csv"}
_ORGANIZE_KEYWORDS = ("organiz", "limp", "arruma", "ajeita", "formata", "reorganiz")
_CHART_KEYWORDS = ("grafico", "gráfico", "chart", "compara")

# Rotas de resposta que sinalizam problema no provedor de LLM (ver
# `app/agents/nodes/generation.py`) — usadas para atualizar o indicador
# "Sistema ativo" da sidebar e destacar a resposta como aviso do sistema,
# em vez de uma resposta normal do agente.
_PROVIDER_ISSUE_ROUTES = {"provider_busy": ("slow", "warning"), "provider_error": ("down", "danger")}

st.markdown(hero_header("AxysAI"), unsafe_allow_html=True)


def _new_conversation() -> str:
    conv_id = uuid.uuid4().hex
    st.session_state["conversations"][conv_id] = {
        "title": "Nova conversa",
        "session_id": None,
        "messages": [],  # [{role, content, grounded, message_id, kind, tone, spreadsheet_result}]
        "last_spreadsheet": None,  # {"name": str, "bytes": bytes} — para "organize" sem anexo novo
    }
    return conv_id


def _wants_spreadsheet_organized(question: str) -> bool:
    lowered = question.lower()
    return any(keyword in lowered for keyword in _ORGANIZE_KEYWORDS)


def _wants_chart(question: str) -> bool:
    lowered = question.lower()
    return any(keyword in lowered for keyword in _CHART_KEYWORDS)


def _render_spreadsheet_result(result: dict, *, key_prefix: str) -> None:
    with st.container(border=True, key=f"sheet-card-{key_prefix}"):
        st.markdown(card_header("table", "Planilha organizada"), unsafe_allow_html=True)
        st.markdown(result["summary"])
        if result.get("chart_base64"):
            st.image(base64.b64decode(result["chart_base64"]))
        if result.get("preview_rows"):
            preview = {
                column: [row[i] for row in result["preview_rows"]]
                for i, column in enumerate(result["columns"])
            }
            st.dataframe(preview, use_container_width=True)
            if result["total_rows"] > len(result["preview_rows"]):
                st.caption(f"Mostrando {len(result['preview_rows'])} de {result['total_rows']} linhas.")
        st.download_button(
            "⬇️ Baixar planilha organizada",
            data=base64.b64decode(result["file_base64"]),
            file_name=result["file_name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{key_prefix}",
        )


def _run_organize_flow(
    file_name: str, file_bytes: bytes, *, chart_requested: bool, request_text: str, active: dict
) -> None:
    with st.chat_message("assistant", avatar=_AGENT_AVATAR):
        with st.spinner(f"Organizando {file_name}..."):
            try:
                result = organize_spreadsheet(
                    file_name, file_bytes, generate_chart=chart_requested, request_text=request_text
                )
                _render_spreadsheet_result(result, key_prefix=f"live_{uuid.uuid4().hex}")
                active["messages"].append(
                    {
                        "role": "assistant",
                        "content": result["summary"],
                        "kind": "spreadsheet_result",
                        "spreadsheet_result": result,
                    }
                )
                # A planilha lembrada passa a ser o RESULTADO ja organizado,
                # nao mais o arquivo original bagunçado — sem isso, um
                # segundo pedido na mesma conversa (ex: "agora ordena por
                # nome tambem") reprocessava do zero a partir do upload
                # original e perdia tudo que ja tinha sido ajustado antes.
                active["last_spreadsheet"] = {
                    "name": result["file_name"],
                    "bytes": base64.b64decode(result["file_base64"]),
                }
            except ApiError as exc:
                note = f"Não consegui organizar **{file_name}**: {exc.message}"
                st.markdown(system_note(note, "danger"), unsafe_allow_html=True)
                active["messages"].append(
                    {"role": "assistant", "content": note, "kind": "system_note", "tone": "danger"}
                )


@st.dialog("Apagar esta conversa?")
def _confirm_delete_conversation(conv_id: str) -> None:
    st.write("Essa ação não pode ser desfeita.")
    with st.container(key="confirm-danger-delete-conv"):
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Apagar", type="primary", use_container_width=True):
                del st.session_state["conversations"][conv_id]
                if conv_id == st.session_state["active_conversation_id"]:
                    remaining = list(st.session_state["conversations"].keys())
                    st.session_state["active_conversation_id"] = (
                        remaining[-1] if remaining else _new_conversation()
                    )
                st.rerun()
        with col_no:
            if st.button("Cancelar", use_container_width=True):
                st.rerun()


@st.dialog("Limpar esta conversa?")
def _confirm_clear_conversation(active: dict) -> None:
    st.write("O conteúdo desta conversa será apagado. Essa ação não pode ser desfeita.")
    with st.container(key="confirm-danger-clear-conv"):
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Limpar", type="primary", use_container_width=True):
                active["session_id"] = None
                active["messages"] = []
                active["title"] = "Nova conversa"
                active["last_spreadsheet"] = None
                st.rerun()
        with col_no:
            if st.button("Cancelar", use_container_width=True):
                st.rerun()


if "conversations" not in st.session_state:
    st.session_state["conversations"] = {}
if "active_conversation_id" not in st.session_state or (
    st.session_state["active_conversation_id"] not in st.session_state["conversations"]
):
    st.session_state["active_conversation_id"] = _new_conversation()

active_id = st.session_state["active_conversation_id"]
active = st.session_state["conversations"][active_id]

# Chamado aqui (em vez de logo antes de ser usado, no final do arquivo) so
# para o estado vazio abaixo saber, no MESMO rerender, que uma pergunta
# acabou de ser enviada — sem isso, o card de "comece uma conversa" pisca
# por cima da primeira pergunta enquanto a resposta ainda esta carregando.
# `st.chat_input` sempre fica fixado embaixo da tela, independente de onde
# e chamado no script.
prompt = st.chat_input(
    "Digite sua pergunta, peça para organizar uma planilha ou anexe um documento (+)...",
    accept_file="multiple",
    file_type=ALLOWED_UPLOAD_TYPES,
)

with st.sidebar:
    try:
        config = get_system_config()
        st.markdown(
            sidebar_status(
                [
                    ("cpu", "Modelo", config["llm_model"]),
                    ("database", "Banco vetorial", config["vector_store_provider"]),
                    ("sparkle", "Embeddings", config["embedding_model"]),
                ],
                status=st.session_state.get("system_status", "ok"),
            ),
            unsafe_allow_html=True,
        )
    except ApiError:
        pass  # Status e um extra informativo — a sidebar de conversas continua funcionando sem ele.

    st.subheader("Conversas")

    if st.button("➕ Nova conversa", use_container_width=True, type="primary"):
        st.session_state["active_conversation_id"] = _new_conversation()
        st.rerun()

    st.caption("Histórico")
    # Mais recente primeiro; dicts em Python 3.7+ preservam ordem de insercao.
    for conv_id, conv in reversed(list(st.session_state["conversations"].items())):
        is_active = conv_id == active_id
        row_key = f"conv-row-{conv_id}-active" if is_active else f"conv-row-{conv_id}"
        with st.container(key=row_key):
            col_select, col_delete = st.columns([5, 1])
            with col_select:
                if st.button(
                    conv["title"],
                    key=f"conv_{conv_id}",
                    use_container_width=True,
                    disabled=is_active,
                    help=conv["title"],
                ):
                    st.session_state["active_conversation_id"] = conv_id
                    st.rerun()
                first_user_msg = next((m["content"] for m in conv["messages"] if m["role"] == "user"), None)
                last_user_msg = next(
                    (m["content"] for m in reversed(conv["messages"]) if m["role"] == "user"), None
                )
                # So mostra a previa se ela trouxer algo novo em relacao ao
                # titulo (que ja e a primeira pergunta) — repetir o mesmo
                # texto duas vezes numa conversa de uma unica mensagem parecia
                # bug, nao design.
                if last_user_msg and last_user_msg != first_user_msg:
                    preview = last_user_msg[:_MAX_PREVIEW_LENGTH]
                    if len(last_user_msg) > _MAX_PREVIEW_LENGTH:
                        preview += "…"
                    st.markdown(conversation_preview(preview), unsafe_allow_html=True)
            with col_delete:
                # "x" de texto puro em vez do emoji de lixeira: o fallback de
                # fonte do Windows/Chromium renderiza esse emoji com a caixa
                # delimitadora descentralizada (fica torto e cortado dentro
                # do botao) — um glifo de texto simples nao tem esse problema
                # em nenhuma fonte.
                if st.button("✕", key=f"delete_{conv_id}", help="Apagar esta conversa"):
                    _confirm_delete_conversation(conv_id)

    st.divider()
    if st.button("🧹 Limpar conversa atual", use_container_width=True):
        _confirm_clear_conversation(active)


if not active["messages"] and not prompt:
    with st.chat_message("assistant", avatar=_AGENT_AVATAR):
        st.markdown(
            "Olá, sou a **Axys**! Respondo com base nos documentos que você enviar e, "
            "quando o assunto não estiver neles, também ajudo com conhecimento geral. "
            "Para começar, clique no **+** e envie um documento."
        )

for index, message in enumerate(active["messages"]):
    avatar = _AGENT_AVATAR if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        if message.get("kind") == "spreadsheet_result":
            _render_spreadsheet_result(message["spreadsheet_result"], key_prefix=f"hist_{active_id}_{index}")
            continue

        if message.get("kind") == "system_note":
            st.markdown(system_note(message["content"], message.get("tone", "neutral")), unsafe_allow_html=True)
            continue

        st.markdown(message["content"])
        if message["role"] == "assistant":
            if message.get("grounded") is False:
                st.warning(
                    "Esta resposta pode nao estar totalmente fundamentada nos documentos.",
                    icon="⚠️",
                )

            feedback_key = f"feedback_{message.get('message_id', index)}"
            if message.get("message_id") and not st.session_state.get(feedback_key):
                with st.container(key=f"feedback-{feedback_key}"):
                    col1, col2, _spacer = st.columns([1, 1, 10])
                    with col1:
                        if st.button("👍", key=f"up_{message['message_id']}"):
                            try:
                                submit_feedback(message["message_id"], "positive")
                                st.session_state[feedback_key] = True
                                st.rerun()
                            except ApiError as exc:
                                st.error(f"Falha ao enviar feedback: {exc.message}")
                    with col2:
                        if st.button("👎", key=f"down_{message['message_id']}"):
                            try:
                                submit_feedback(message["message_id"], "negative")
                                st.session_state[feedback_key] = True
                                st.rerun()
                            except ApiError as exc:
                                st.error(f"Falha ao enviar feedback: {exc.message}")
            elif st.session_state.get(feedback_key):
                st.markdown(pill("Obrigado pelo seu feedback!"), unsafe_allow_html=True)

if prompt:
    question = (prompt.text or "").strip()
    uploaded_files = prompt.files
    organize_requested = bool(question) and _wants_spreadsheet_organized(question)
    chart_requested = bool(question) and _wants_chart(question)

    if active["title"] == "Nova conversa":
        seed = question or (uploaded_files[0].name if uploaded_files else "Conversa")
        active["title"] = seed[:_MAX_TITLE_LENGTH] + ("…" if len(seed) > _MAX_TITLE_LENGTH else "")

    if question:
        active["messages"].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

    organized_any = False
    remaining_files = []
    for uploaded_file in uploaded_files:
        extension = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
        is_spreadsheet = extension in _SPREADSHEET_EXTENSIONS
        if is_spreadsheet:
            # Lembrada mesmo se este envio nao pedir "organizar" agora — permite
            # pedir "organiza essa planilha" numa mensagem separada, depois do upload.
            active["last_spreadsheet"] = {"name": uploaded_file.name, "bytes": uploaded_file.getvalue()}
        if organize_requested and is_spreadsheet:
            organized_any = True
            _run_organize_flow(
                uploaded_file.name, uploaded_file.getvalue(), chart_requested=chart_requested,
                request_text=question, active=active,
            )
        else:
            remaining_files.append(uploaded_file)

    for uploaded_file in remaining_files:
        with st.chat_message("assistant", avatar=_AGENT_AVATAR):
            with st.spinner(f"Enviando {uploaded_file.name}..."):
                tone = "success"
                try:
                    result = upload_document(uploaded_file.name, uploaded_file.getvalue())
                    if result["status"] == "duplicate":
                        note = f"**{uploaded_file.name}** já existe na base — envio ignorado."
                        tone = "warning"
                    else:
                        process_result = process_document(result["document_id"])
                        if process_result["status"] == "success":
                            note = (
                                f"**{uploaded_file.name}** enviado e aprovado automaticamente "
                                f"({process_result['chunks_indexed']} trechos indexados). Já pode "
                                "ser usado nas respostas."
                            )
                        else:
                            note = (
                                f"**{uploaded_file.name}** falhou no processamento: "
                                f"{process_result.get('error') or 'erro desconhecido'}."
                            )
                            tone = "danger"
                except ApiError as exc:
                    note = f"**{uploaded_file.name}** falhou no envio: {exc.message}"
                    tone = "danger"
                st.markdown(system_note(note, tone), unsafe_allow_html=True)
                active["messages"].append(
                    {"role": "assistant", "content": note, "kind": "system_note", "tone": tone}
                )

    if organize_requested and not uploaded_files:
        last = active.get("last_spreadsheet")
        if last:
            organized_any = True
            _run_organize_flow(
                last["name"], last["bytes"], chart_requested=chart_requested,
                request_text=question, active=active,
            )
        else:
            with st.chat_message("assistant", avatar=_AGENT_AVATAR):
                note = (
                    "Não encontrei nenhuma planilha para organizar nesta conversa. Anexe um "
                    "arquivo .xlsx ou .csv pelo sinal de + e peça novamente."
                )
                st.markdown(system_note(note, "warning"), unsafe_allow_html=True)
                active["messages"].append(
                    {"role": "assistant", "content": note, "kind": "system_note", "tone": "warning"}
                )
            organized_any = True

    if question and not organized_any:
        with st.chat_message("assistant", avatar=_AGENT_AVATAR):
            with st.spinner("Consultando os documentos aprovados..."):
                try:
                    response = send_chat_message(question, session_id=active["session_id"])
                    active["session_id"] = response["session_id"]
                    route = response.get("route")

                    if route in _PROVIDER_ISSUE_ROUTES:
                        status, tone = _PROVIDER_ISSUE_ROUTES[route]
                        st.session_state["system_status"] = status
                        st.markdown(system_note(response["answer"], tone), unsafe_allow_html=True)
                        active["messages"].append(
                            {
                                "role": "assistant",
                                "content": response["answer"],
                                "kind": "system_note",
                                "tone": tone,
                            }
                        )
                    else:
                        st.session_state["system_status"] = "ok"
                        st.markdown(response["answer"])

                        if response.get("grounded") is False:
                            st.warning(
                                "Esta resposta pode nao estar totalmente fundamentada nos documentos.",
                                icon="⚠️",
                            )

                        active["messages"].append(
                            {
                                "role": "assistant",
                                "content": response["answer"],
                                "grounded": response.get("grounded"),
                                "message_id": response.get("message_id"),
                            }
                        )
                except ApiError as exc:
                    st.session_state["system_status"] = "down"
                    st.error(f"Nao foi possivel obter uma resposta: {exc.message}")

    st.rerun()
