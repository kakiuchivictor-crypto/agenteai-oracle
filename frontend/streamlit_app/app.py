"""Ponto de entrada do AxysAI.

So expoe as paginas listadas em `st.navigation` abaixo — Documentos, Curadoria,
Configuracoes e Painel continuam existindo como arquivos (`app_pages/2_Documentos.py`
em diante), mas nao aparecem mais no menu nem sao navegaveis pelo app: o
sistema e de uso livre e a curadoria roda automaticamente (`AUTO_APPROVE_ON_UPLOAD`),
entao essas telas deixaram de ser necessarias no dia a dia. Para reativar
alguma delas no futuro, basta acrescenta-la a lista `pages` abaixo.

A pasta se chama `app_pages/`, e nao `pages/` (convencao classica do
Streamlit): uma pasta literalmente chamada `pages/` ao lado do script
principal faz o Streamlit exibir TODOS os arquivos nela na barra lateral,
mesmo com `st.navigation` configurado so com os dois abaixo — bug
reproduzido e confirmado nesta versao do Streamlit.

Executar com: streamlit run frontend/streamlit_app/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from _backend_bootstrap import ensure_backend_running
from theme import inject_css

_LOGO_PATH = str(Path(__file__).resolve().parent / "assets" / "axys_logo.png")

st.set_page_config(page_title="AxysAI - Respostas para suas dúvidas", page_icon=_LOGO_PATH, layout="wide")

# No Streamlit Community Cloud so existe um processo — a API FastAPI sobe em
# background dentro dele (ver _backend_bootstrap.py). Em Docker/local, a API
# ja responde em API_BASE_URL e isto vira um no-op.
ensure_backend_running()

inject_css()

pages = [
    st.Page("app_pages/0_Informacoes.py", title="Informações", icon="ℹ️", default=True),
    st.Page("app_pages/1_Chat.py", title="Chat", icon="💬"),
]

st.navigation(pages).run()
