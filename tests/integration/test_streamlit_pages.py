"""Smoke tests das paginas Streamlit via `streamlit.testing.v1.AppTest`.

O sistema nao tem login (uso livre para todos os usuarios) — cada pagina
deve renderizar diretamente, sem excecao, ja na primeira execucao headless.
`app.py` e o roteador (`st.navigation`) e so expoe Informacoes/Chat no menu;
Documentos/Curadoria/Configuracoes/Painel continuam existindo como arquivos
(reativaveis no futuro) mas nao fazem mais parte do fluxo do usuario — ainda
assim seguem testados aqui para nao apodrecer silenciosamente.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "streamlit_app"

_VISIBLE_PAGES = [
    FRONTEND_DIR / "app.py",
    FRONTEND_DIR / "pages" / "0_Informacoes.py",
    FRONTEND_DIR / "pages" / "1_Chat.py",
]

_HIDDEN_PAGES = [
    FRONTEND_DIR / "pages" / "2_Documentos.py",
    FRONTEND_DIR / "pages" / "3_Curadoria.py",
    FRONTEND_DIR / "pages" / "4_Configuracoes.py",
    FRONTEND_DIR / "pages" / "5_Painel.py",
]


@pytest.mark.parametrize("page_path", _VISIBLE_PAGES, ids=[p.name for p in _VISIBLE_PAGES])
def test_visible_page_renders_without_exception(page_path: Path) -> None:
    at = AppTest.from_file(str(page_path), default_timeout=30)
    at.run()

    assert not at.exception, [str(exc) for exc in at.exception]
    # `hero_header` (theme.py) e HTML proprio via st.markdown, nao `st.title()`
    # nativo — e no Chat, desde que o titulo/subtitulo foram removidos a
    # pedido do usuario, so sobra a marca "AxysAI" no cabecalho. Checa a
    # marca em vez de `at.title`, que nunca capturaria esse cabecalho.
    assert any("AxysAI" in md.value for md in at.markdown), "Pagina deveria renderizar a marca AxysAI."


@pytest.mark.parametrize("page_path", _HIDDEN_PAGES, ids=[p.name for p in _HIDDEN_PAGES])
def test_hidden_page_still_renders_without_exception(page_path: Path) -> None:
    """Fora da navegacao (nao aparecem no menu), mas continuam validas caso
    alguem as reative em `app.py` no futuro."""
    at = AppTest.from_file(str(page_path), default_timeout=30)
    at.run()

    assert not at.exception, [str(exc) for exc in at.exception]
