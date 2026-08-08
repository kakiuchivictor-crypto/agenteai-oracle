"""Cliente HTTP para a API FastAPI (secao 27 do prompt mestre: a interface
Streamlit consome exclusivamente a API, nunca acessa o banco diretamente).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import dotenv_values

_ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_env = dotenv_values(_ROOT_ENV_PATH) if _ROOT_ENV_PATH.exists() else {}
# Variavel de ambiente real tem prioridade sobre o .env — essencial no
# Docker Compose, onde o servico do frontend recebe API_BASE_URL apontando
# para o nome do servico da API (ex: http://api:8000), nao para localhost.
API_BASE_URL = os.environ.get("API_BASE_URL") or _env.get("API_BASE_URL", "http://localhost:8000")

_DEFAULT_TIMEOUT = 30
_UPLOAD_TIMEOUT = 120
_PROCESS_TIMEOUT = 300
_CHAT_TIMEOUT = 180


class ApiError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """Encapsula `requests.request` convertendo falhas de conexao/timeout em
    `ApiError` — sem isso, uma API fora do ar levantaria `ConnectionError`
    (nao capturado pelo `except ApiError` que toda pagina ja usa), quebrando
    a pagina com uma excecao crua em vez de uma mensagem tratada."""
    try:
        return requests.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        raise ApiError(0, "connection_error", f"Nao foi possivel conectar a API: {exc}") from exc


def _handle_response(response: requests.Response) -> Any:
    if response.status_code >= 400:
        error_code = "unknown_error"
        message = response.text
        try:
            payload = response.json()
            error_code = payload.get("error_code", error_code)
            message = payload.get("message", message)
        except ValueError:
            pass
        raise ApiError(response.status_code, error_code, message)

    if response.status_code == 204 or not response.content:
        return None
    return response.json()


# ==========================================================
# CATEGORIAS
# ==========================================================
@st.cache_data(ttl=60, show_spinner=False)
def list_categories() -> list[dict]:
    """Cacheada por 60s: a lista de categorias e igual para todos os
    usuarios e muda raramente — evita rebuscar a cada rerender do Streamlit
    (o script inteiro reexecuta a cada interacao do usuario). Se uma tela
    passar a criar categorias, chame `list_categories.clear()` logo apos
    `create_category(...)` para nao exibir dado desatualizado."""
    response = _request("GET", f"{API_BASE_URL}/categories", timeout=_DEFAULT_TIMEOUT)
    return _handle_response(response)


def create_category(name: str, slug: str, description: str | None = None) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/categories",
        json={"name": name, "slug": slug, "description": description},
        timeout=_DEFAULT_TIMEOUT,
    )
    result = _handle_response(response)
    list_categories.clear()
    return result


# ==========================================================
# DOCUMENTOS
# ==========================================================
def upload_document(
    file_name: str,
    file_bytes: bytes,
    *,
    category_id: str | None = None,
    subcategory: str | None = None,
    tags: str | None = None,
    department: str | None = None,
    access_classification: str = "internal",
    is_official: bool = False,
) -> dict:
    files = {"file": (file_name, file_bytes)}
    data = {
        "access_classification": access_classification,
        "is_official": str(is_official),
    }
    if category_id:
        data["category_id"] = category_id
    if subcategory:
        data["subcategory"] = subcategory
    if tags:
        data["tags"] = tags
    if department:
        data["department"] = department

    response = _request(
        "POST", f"{API_BASE_URL}/documents/upload", files=files, data=data, timeout=_UPLOAD_TIMEOUT
    )
    return _handle_response(response)


def list_documents(status_filter: str | None = None, category_id: str | None = None) -> list[dict]:
    params = {}
    if status_filter:
        params["status_filter"] = status_filter
    if category_id:
        params["category_id"] = category_id
    response = _request("GET", f"{API_BASE_URL}/documents", params=params, timeout=_DEFAULT_TIMEOUT)
    return _handle_response(response)


def get_document(document_id: str) -> dict:
    response = _request("GET", f"{API_BASE_URL}/documents/{document_id}", timeout=_DEFAULT_TIMEOUT)
    return _handle_response(response)


def process_document(document_id: str) -> dict:
    response = _request(
        "POST", f"{API_BASE_URL}/documents/{document_id}/process", timeout=_PROCESS_TIMEOUT
    )
    return _handle_response(response)


def approve_document(document_id: str, reason: str | None = None) -> dict:
    response = _request(
        "POST", f"{API_BASE_URL}/documents/{document_id}/approve",
        json={"reason": reason}, timeout=_DEFAULT_TIMEOUT,
    )
    return _handle_response(response)


def reject_document(document_id: str, reason: str | None = None) -> dict:
    response = _request(
        "POST", f"{API_BASE_URL}/documents/{document_id}/reject",
        json={"reason": reason}, timeout=_DEFAULT_TIMEOUT,
    )
    return _handle_response(response)


def reindex_document(document_id: str) -> dict:
    response = _request(
        "POST", f"{API_BASE_URL}/documents/{document_id}/reindex", timeout=_PROCESS_TIMEOUT
    )
    return _handle_response(response)


def delete_document(document_id: str) -> dict:
    response = _request("DELETE", f"{API_BASE_URL}/documents/{document_id}", timeout=_DEFAULT_TIMEOUT)
    return _handle_response(response)


# ==========================================================
# CHAT
# ==========================================================
def send_chat_message(question: str, session_id: str | None = None, category_filter: str | None = None) -> dict:
    payload: dict[str, Any] = {"question": question}
    if session_id:
        payload["session_id"] = session_id
    if category_filter:
        payload["category_filter"] = category_filter
    response = _request("POST", f"{API_BASE_URL}/chat", json=payload, timeout=_CHAT_TIMEOUT)
    return _handle_response(response)


def list_chat_sessions() -> list[dict]:
    response = _request("GET", f"{API_BASE_URL}/chat/sessions", timeout=_DEFAULT_TIMEOUT)
    return _handle_response(response)


def list_chat_messages(session_id: str) -> list[dict]:
    response = _request(
        "GET", f"{API_BASE_URL}/chat/sessions/{session_id}/messages", timeout=_DEFAULT_TIMEOUT
    )
    return _handle_response(response)


# ==========================================================
# FEEDBACK
# ==========================================================
def submit_feedback(
    message_id: str, rating: str, issue_type: str = "none", comment: str | None = None
) -> dict:
    response = _request(
        "POST", f"{API_BASE_URL}/feedback",
        json={"message_id": message_id, "rating": rating, "issue_type": issue_type, "comment": comment},
        timeout=_DEFAULT_TIMEOUT,
    )
    return _handle_response(response)


def list_feedback() -> list[dict]:
    response = _request("GET", f"{API_BASE_URL}/feedback", timeout=_DEFAULT_TIMEOUT)
    return _handle_response(response)


# ==========================================================
# CONFIGURACAO (somente leitura)
# ==========================================================
@st.cache_data(ttl=60, show_spinner=False)
def get_system_config() -> dict:
    """Cacheada por 60s pelo mesmo motivo de `list_categories`: parametros
    operacionais que raramente mudam, mas agora consultados a cada rerender
    da sidebar do Chat e da faixa de status de Informacoes — sem cache,
    cada interacao do usuario (o Streamlit reexecuta o script inteiro)
    dispararia uma nova chamada a API so para exibir o mesmo status."""
    response = _request("GET", f"{API_BASE_URL}/config", timeout=_DEFAULT_TIMEOUT)
    return _handle_response(response)


# ==========================================================
# METRICAS
# ==========================================================
@st.cache_data(ttl=15, show_spinner=False)
def get_metrics_summary() -> dict:
    """Cacheada por 15s: o painel nao precisa recalcular a cada rerender,
    mas ainda fica razoavelmente atualizado."""
    response = _request("GET", f"{API_BASE_URL}/metrics/summary", timeout=_DEFAULT_TIMEOUT)
    return _handle_response(response)


# ==========================================================
# FERRAMENTAS (fora do fluxo de RAG)
# ==========================================================
def organize_spreadsheet(
    file_name: str, file_bytes: bytes, *, generate_chart: bool = False, request_text: str = ""
) -> dict:
    files = {"file": (file_name, file_bytes)}
    data = {"generate_chart": str(generate_chart), "request_text": request_text}
    response = _request(
        "POST", f"{API_BASE_URL}/tools/organize-spreadsheet", files=files, data=data,
        timeout=_UPLOAD_TIMEOUT,
    )
    return _handle_response(response)
