"""Sobe a API FastAPI em background dentro do mesmo processo do Streamlit.

O Streamlit Community Cloud so executa um unico comando (`streamlit run ...`)
e nao tem como subir um segundo servico para a API. Como a interface consome
exclusivamente a API por HTTP (nunca acessa o banco/vetor direto — secao 27
do prompt mestre), a solucao e iniciar o uvicorn numa thread daemon dentro do
proprio processo do Streamlit, escutando em localhost, antes de qualquer
pagina ser renderizada.

`app.py` roda do zero a cada interacao do usuario (rerun do Streamlit), mas o
cache de modulos do Python (`sys.modules`) persiste entre reruns dentro do
mesmo processo — por isso o guard de "ja iniciado" mora aqui, num modulo
separado importado por `app.py`, e nao direto no corpo de `app.py`.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import dotenv_values

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_HOST = "127.0.0.1"
_BACKEND_PORT = 8000
_DEFAULT_API_BASE_URL = f"http://{_BACKEND_HOST}:{_BACKEND_PORT}"

_started = False
_lock = threading.Lock()


def _apply_secrets_to_env() -> None:
    """Copia os secrets configurados no dashboard do Streamlit Cloud para
    variaveis de ambiente, unica forma de chegarem ate `Settings` (que le
    apenas env vars / .env — nao conhece `st.secrets`)."""
    try:
        secrets = dict(st.secrets)
    except Exception:
        return
    for key, value in secrets.items():
        if isinstance(value, str | int | float | bool):
            os.environ.setdefault(key.upper(), str(value))


def _resolve_api_base_url() -> str:
    """Mesma logica de resolucao usada por `api_client.py`: env var real
    vence, senao cai para o `.env` da raiz, senao o default local."""
    if value := os.environ.get("API_BASE_URL"):
        return value
    env_file = _REPO_ROOT / ".env"
    if env_file.exists():
        if value := dotenv_values(env_file).get("API_BASE_URL"):
            return value
    return _DEFAULT_API_BASE_URL


def _api_already_running(base_url: str) -> bool:
    try:
        return requests.get(f"{base_url}/health", timeout=1.5).status_code == 200
    except requests.exceptions.RequestException:
        return False


def _run_backend() -> None:
    import sys

    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

    import uvicorn

    from app.api.main import app as fastapi_app

    uvicorn.run(fastapi_app, host=_BACKEND_HOST, port=_BACKEND_PORT, log_level="warning")


def ensure_backend_running() -> None:
    """Garante que a API esta rodando (idempotente entre reruns).

    So sobe a API em thread se ninguem responder em `API_BASE_URL` ainda —
    no Docker Compose e no dev local com uvicorn rodando a parte, a API ja
    esta de pe e isto vira um no-op; so no Streamlit Cloud (onde nao ha
    processo separado) e que o fallback em thread entra em acao."""
    global _started
    with _lock:
        if _started:
            return

        base_url = _resolve_api_base_url()
        if _api_already_running(base_url):
            _started = True
            return

        _apply_secrets_to_env()
        os.environ.setdefault("API_BASE_URL", _DEFAULT_API_BASE_URL)

        thread = threading.Thread(target=_run_backend, daemon=True, name="axysai-api")
        thread.start()
        _started = True

        # Espera a API responder antes de liberar a primeira pagina — evita
        # um "connection refused" cosmetico no primeiro load.
        for _ in range(30):
            if _api_already_running(_DEFAULT_API_BASE_URL):
                break
            time.sleep(0.5)
