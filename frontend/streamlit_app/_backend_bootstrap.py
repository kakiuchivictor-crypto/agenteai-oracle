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


def _ensure_backend_app_package_importable() -> None:
    """Registra o pacote `app/` (backend) em `sys.modules` via caminho
    explicito, sem depender da ordem (racy) do `sys.path` — ver motivo em
    `_run_backend`. Idempotente: reaproveita se ja estiver corretamente
    carregado."""
    import sys
    from importlib.util import module_from_spec, spec_from_file_location

    existing = sys.modules.get("app")
    if existing is not None and hasattr(existing, "__path__"):
        return

    app_dir = _REPO_ROOT / "app"
    spec = spec_from_file_location(
        "app", app_dir / "__init__.py", submodule_search_locations=[str(app_dir)]
    )
    module = module_from_spec(spec)
    sys.modules["app"] = module
    spec.loader.exec_module(module)


def _run_backend() -> None:
    import subprocess
    import sys

    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

    # Mesmos passos do CMD do Dockerfile antes de subir a API: sem isso o
    # banco fica sem tabelas (SQLite novo, criado do zero a cada deploy no
    # Streamlit Cloud) e sem o usuario "sistema" usado para atribuir sessoes
    # de chat/uploads quando nao ha login.
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=_REPO_ROOT, check=True)
    subprocess.run([sys.executable, "scripts/seed_system_user.py"], cwd=_REPO_ROOT, check=True)

    import uvicorn

    # `sys.path` e compartilhado entre threads, e o Streamlit reinsere a
    # pasta do entrypoint (`frontend/streamlit_app`) na posicao 0 a cada
    # rerun do script principal — inclusive enquanto esta thread roda em
    # paralelo. Se isso acontecer bem no meio do `import app...` abaixo,
    # "app" resolve para o `app.py` do Streamlit (um arquivo, nao pacote)
    # em vez do pacote `app/` do backend, e quebra com "'app' is not a
    # package". Carregar o pacote via caminho explicito evita depender da
    # ordem (racy) do sys.path.
    _ensure_backend_app_package_importable()

    from app.api.main import app as fastapi_app

    uvicorn.run(fastapi_app, host=_BACKEND_HOST, port=_BACKEND_PORT, log_level="warning")


def ensure_backend_running() -> None:
    """Garante que a API esta rodando (idempotente entre reruns).

    So sobe a API em thread se ninguem responder em `API_BASE_URL` ainda —
    no Docker Compose e no dev local com uvicorn rodando a parte, a API ja
    esta de pe e isto vira um no-op; so no Streamlit Cloud (onde nao ha
    processo separado) e que o fallback em thread entra em acao.

    NAO espera a API ficar pronta antes de retornar (de proposito): o
    Streamlit manda a lista classica de paginas (a da pasta `pages/`) para o
    navegador assim que a sessao conecta, ANTES do script terminar de rodar.
    `st.navigation()` so desliga essa lista classica quando o script chega
    nela — se este bootstrap bloqueasse aqui esperando a API (migrations +
    seed + uvicorn de pe), a barra lateral ficava alguns segundos mostrando
    todas as paginas soltas em vez de so as duas declaradas. As paginas que
    dependem da API (`api_client.py`) ja tratam `ApiError` de conexao com
    uma mensagem, entao um primeiro load levemente adiantado e inofensivo."""
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
