"""Tokens de design e injecao de CSS global (ver auditoria de UI/UX).

Streamlit nao expoe as cores resolvidas de `.streamlit/config.toml` como
variaveis CSS publicas (o tema e aplicado internamente via componentes
React/emotion, sem contrato exposto) — por isso os tokens abaixo duplicam
deliberadamente a paleta do config.toml, para os elementos que nos mesmos
desenhamos como HTML puro (badges, chips, cards, notas do sistema). Se uma
cor mudar aqui, precisa mudar tambem em `.streamlit/config.toml`.

O claro/escuro desses elementos HTML segue `prefers-color-scheme`, o mesmo
sinal que o proprio Streamlit usa por padrao. Ha uma janela de inconsistencia
caso a pessoa troque manualmente o tema pelo menu do Streamlit (Settings)
contra a preferencia do sistema operacional — aceitavel por ora, documentado
na auditoria ("Restricoes do Streamlit").
"""

from __future__ import annotations

import html as _html
import re

import streamlit as st

# ==========================================================
# ICONES — um unico set, mesmo traco (stroke-width 1.6), mesmo tamanho.
# Construidos com primitivas simples (circle/rect/line/polyline/ellipse),
# nunca path data longa desenhada a mao.
# ==========================================================
_ICON_PATHS: dict[str, str] = {
    "check": '<circle cx="12" cy="12" r="9"></circle><polyline points="8 12 11 15 16 9"></polyline>',
    "steps": (
        '<circle cx="4.5" cy="6" r="1.3" fill="currentColor" stroke="none"></circle>'
        '<line x1="9" y1="6" x2="20" y2="6"></line>'
        '<circle cx="4.5" cy="12" r="1.3" fill="currentColor" stroke="none"></circle>'
        '<line x1="9" y1="12" x2="20" y2="12"></line>'
        '<circle cx="4.5" cy="18" r="1.3" fill="currentColor" stroke="none"></circle>'
        '<line x1="9" y1="18" x2="20" y2="18"></line>'
    ),
    "globe": (
        '<circle cx="12" cy="12" r="9"></circle>'
        '<ellipse cx="12" cy="12" rx="4" ry="9"></ellipse>'
        '<line x1="3" y1="12" x2="21" y2="12"></line>'
    ),
    "upload": (
        '<polyline points="8 10 12 6 16 10"></polyline>'
        '<line x1="12" y1="6" x2="12" y2="16"></line>'
        '<rect x="4" y="17" width="16" height="3" rx="1"></rect>'
    ),
    "table": (
        '<rect x="3" y="4" width="18" height="16" rx="2"></rect>'
        '<line x1="3" y1="10" x2="21" y2="10"></line>'
        '<line x1="9" y1="4" x2="9" y2="20"></line>'
    ),
    "chat": (
        '<rect x="3" y="5" width="18" height="12" rx="3"></rect>'
        '<polygon points="8,17 8,21 12,17" fill="currentColor" stroke="none"></polygon>'
    ),
    "file": '<rect x="6" y="3" width="10" height="16" rx="1.5"></rect><polyline points="12 3 12 8 16 8"></polyline>',
    "cpu": (
        '<rect x="7" y="7" width="10" height="10" rx="1.5"></rect>'
        '<line x1="9" y1="3" x2="9" y2="7"></line><line x1="15" y1="3" x2="15" y2="7"></line>'
        '<line x1="9" y1="17" x2="9" y2="21"></line><line x1="15" y1="17" x2="15" y2="21"></line>'
        '<line x1="3" y1="9" x2="7" y2="9"></line><line x1="3" y1="15" x2="7" y2="15"></line>'
        '<line x1="17" y1="9" x2="21" y2="9"></line><line x1="17" y1="15" x2="21" y2="15"></line>'
    ),
    "database": (
        '<ellipse cx="12" cy="5.5" rx="8" ry="3"></ellipse>'
        '<line x1="4" y1="5.5" x2="4" y2="18.5"></line><line x1="20" y1="5.5" x2="20" y2="18.5"></line>'
        '<ellipse cx="12" cy="18.5" rx="8" ry="3"></ellipse>'
    ),
    "sparkle": (
        '<polygon points="12,2 14,10 22,12 14,14 12,22 10,14 2,12 10,10" '
        'fill="currentColor" stroke="none"></polygon>'
    ),
}


def icon(name: str, size: int = 18) -> str:
    body = _ICON_PATHS[name]
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
        f'stroke-linejoin="round" style="display:block">{body}</svg>'
    )


# ==========================================================
# BADGES DE STATUS — mesma tabela ja usada nas paginas, agora com cor
# semantica em vez de texto entre crases.
# ==========================================================
_STATUS_STYLES: dict[str, tuple[str, str, str]] = {
    "pending_review": ("var(--ai-warning)", "var(--ai-warning-tint)", "Pendente de revisão"),
    "approved": ("var(--ai-success)", "var(--ai-success-tint)", "Aprovado"),
    "rejected": ("var(--ai-danger)", "var(--ai-danger-tint)", "Rejeitado"),
    "outdated": ("var(--ai-text-faint)", "var(--ai-surface-2)", "Desatualizado"),
    "replaced": ("var(--ai-text-faint)", "var(--ai-surface-2)", "Substituído"),
    "archived": ("var(--ai-text-faint)", "var(--ai-surface-2)", "Arquivado"),
    "duplicate": ("var(--ai-warning)", "var(--ai-warning-tint)", "Duplicata"),
}


def badge(status: str) -> str:
    color, tint, label = _STATUS_STYLES.get(status, ("var(--ai-text-faint)", "var(--ai-surface-2)", status))
    return (
        f'<span class="ai-badge" style="color:{color};background:{tint};">'
        f'<span class="ai-dot" style="background:{color};"></span>{_html.escape(label)}</span>'
    )


def chip(text: str) -> str:
    return f'<span class="ai-chip">{_html.escape(text)}</span>'


def conversation_preview(text: str) -> str:
    """Previa da ultima pergunta, sob o titulo de uma conversa na sidebar do
    Chat — HTML proprio (em vez de `st.caption`) porque o padding nativo do
    `st.caption` nao se alinha com o do botao de titulo acima, dentro do
    card de 1px de padding (ver auditoria de UI/UX)."""
    return f'<div class="ai-conv-preview">{_html.escape(text)}</div>'


def pill(text: str, tone: str = "success") -> str:
    """Confirmacao curta (ex: feedback registrado) — reaproveita o mesmo
    `.ai-badge`/`.ai-dot` dos badges de status, so com texto livre em vez de
    um status fixo do dicionario de `badge()`."""
    colors = {
        "success": ("var(--ai-success)", "var(--ai-success-tint)"),
        "accent": ("var(--ai-accent)", "var(--ai-accent-tint)"),
    }
    color, tint = colors.get(tone, colors["success"])
    return (
        f'<span class="ai-badge" style="color:{color};background:{tint};">'
        f'<span class="ai-dot" style="background:{color};"></span>{_html.escape(text)}</span>'
    )


def card_header(icon_name: str, title: str) -> str:
    return (
        f'<div class="ai-card-head"><span class="ai-icon-badge">{icon(icon_name)}</span>'
        f'<span class="ai-card-title">{_html.escape(title)}</span></div>'
    )


def hero_header(eyebrow: str, title: str | None = None, subtitle: str | None = None) -> str:
    """Faixa de identidade do topo de pagina — substitui `st.title`/`st.caption`
    soltos, que nao carregam nenhuma marca (ver auditoria de UI/UX).

    `title`/`subtitle` sao opcionais: o Chat mostra so a marca (icone + "AxysAI"),
    ja que a propria mensagem de boas-vindas do agente cumpre esse papel ali."""
    text = [f'<span class="ai-hero-eyebrow">{_html.escape(eyebrow)}</span>']
    if title:
        text.append(f'<h1 class="ai-hero-title">{_html.escape(title)}</h1>')
    if subtitle:
        text.append(f'<p class="ai-hero-subtitle">{_html.escape(subtitle)}</p>')
    return (
        '<div class="ai-hero">'
        f'<div class="ai-hero-mark">{icon("sparkle", 20)}</div>'
        f'<div class="ai-hero-text">{"".join(text)}</div>'
        '<span class="ai-hero-online"><span class="ai-pulse-dot"></span>Sistema ativo</span>'
        "</div>"
    )


_SYSTEM_STATUS_STYLES: dict[str, tuple[str, str]] = {
    "ok": ("var(--ai-success)", "Sistema ativo"),
    "slow": ("var(--ai-warning)", "Sistema lento"),
    "down": ("var(--ai-danger)", "Sistema interrompido"),
}


def sidebar_status(rows: list[tuple[str, str, str]], status: str = "ok") -> str:
    """Bloco compacto de status do SISTEMA para a sidebar do Chat — nunca de
    usuario/conta (o produto e de uso livre, sem login, ver auditoria).

    `status` reflete a rota da ultima resposta do chat (`provider_busy` /
    `provider_error`, ver `app/agents/nodes/generation.py`) — nao e um
    health-check continuo, so atualiza quando uma pergunta e respondida."""
    color, label = _SYSTEM_STATUS_STYLES.get(status, _SYSTEM_STATUS_STYLES["ok"])
    items = "".join(
        '<div class="ai-sidebar-status-row">'
        f'<span class="ai-stat-icon-sm">{icon(icon_name, 13)}</span>'
        f"<span>{_html.escape(label)}</span>"
        f'<span class="ai-sidebar-status-value">{_html.escape(str(value))}</span>'
        "</div>"
        for icon_name, label, value in rows
    )
    return (
        '<div class="ai-sidebar-status">'
        f'<div class="ai-sidebar-status-head" style="color:{color};">'
        f'<span class="ai-pulse-dot" style="color:{color};"></span>{_html.escape(label)}</div>'
        f"{items}</div>"
    )


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def system_note(text: str, tone: str = "neutral") -> str:
    """Nota do sistema (upload, erro, aviso) — visualmente diferente de uma
    resposta real do agente, para nao confundir as duas na conversa."""
    colors = {
        "success": ("var(--ai-success)", "var(--ai-success-tint)"),
        "warning": ("var(--ai-warning)", "var(--ai-warning-tint)"),
        "danger": ("var(--ai-danger)", "var(--ai-danger-tint)"),
        "neutral": ("var(--ai-border)", "var(--ai-surface-2)"),
    }
    color, tint = colors.get(tone, colors["neutral"])
    # Escapa primeiro (o nome do arquivo vem de upload livre, sem
    # autenticacao) e so depois aplica o **negrito** — nunca o contrario,
    # senao um nome de arquivo malicioso poderia injetar HTML.
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", _html.escape(text))
    return (
        f'<div class="ai-system-note" style="border-left-color:{color};background:{tint};">'
        f'<span class="ai-system-note-icon" style="color:{color};">{icon("file", 16)}</span>'
        f"<span>{escaped}</span></div>"
    )


_CSS = """
<style>
:root{
  --ai-bg:#FAFAF8; --ai-surface:#FFFFFF; --ai-surface-2:#F1EFEA; --ai-border:#E3E0D8;
  --ai-text:#1C1D1F; --ai-text-muted:#6B6D76; --ai-text-faint:#9A9CA5;
  --ai-accent:#146661; --ai-accent-ink:#0E4F4B; --ai-accent-tint:#E3F1EE;
  --ai-success:#1F7A47; --ai-success-tint:#E6F4EA;
  --ai-warning:#9C6B12; --ai-warning-tint:#FBF1DD;
  --ai-danger:#C6423B; --ai-danger-tint:#FBEAE8;
  --ai-info:#2F6FAF; --ai-info-tint:#EAF2F9;
  --ai-serif: ui-serif, 'Source Serif 4', Georgia, 'Times New Roman', serif;
  --ai-mono: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
  --ai-shadow: 0 1px 2px rgba(20,20,30,.05), 0 8px 20px -12px rgba(20,20,30,.12);
}
@media (prefers-color-scheme: dark){
  :root{
    --ai-bg:#0C0E12; --ai-surface:#12151B; --ai-surface-2:#171B22; --ai-border:#262B34;
    --ai-text:#E8E9EC; --ai-text-muted:#9A9DA8; --ai-text-faint:#666A75;
    --ai-accent:#3FB8AC; --ai-accent-ink:#7FDCD0; --ai-accent-tint:#0E2624;
    --ai-success:#46B36B; --ai-success-tint:#12291C;
    --ai-warning:#E0A83E; --ai-warning-tint:#332608;
    --ai-danger:#F0645C; --ai-danger-tint:#33191A;
    --ai-info:#6FB3E8; --ai-info-tint:#12232F;
    --ai-shadow: 0 1px 2px rgba(0,0,0,.35), 0 8px 20px -12px rgba(0,0,0,.55);
  }
}

h1, h2, h3, h4 { letter-spacing:-0.01em; }

[data-testid="stChatInput"] { border-radius:14px; }
[data-testid="stChatMessage"] { border-radius:14px; }
[data-testid="stAlert"] { border-radius:10px; }

.stButton button, .stDownloadButton button, .stFormSubmitButton button {
  font-weight:600;
  transition: background .12s ease, transform .08s ease, border-color .12s ease;
}
.stButton button:active, .stDownloadButton button:active { transform: translateY(1px); }

/* Containers marcados como card (key contendo "-card-") ganham cantos e
   sombra consistentes com o resto do sistema. */
div[class*="st-key-"][class*="-card-"] {
  border-radius:14px !important;
  box-shadow: var(--ai-shadow);
}

/* Variante de destaque — para o unico card mais importante de uma pagina,
   os demais ficam no tratamento padrao acima (mesma hierarquia sempre,
   nunca mais de um destaque por tela). */
div[class*="st-key-"][class*="-featured-card-"] {
  border-color: var(--ai-accent) !important;
  background: var(--ai-accent-tint) !important;
}

/* Linha de conversa na sidebar do Chat — estado ativo por cor, nao so por
   um emoji prefixado no texto do botao. Titulo forcado a uma linha (com
   reticencias) em vez do wrap padrao do botao, que quebrava titulos longos
   em duas linhas e deixava a previa abaixo parecendo desalinhada. */
div[class*="st-key-conv-row-"] { border-radius:10px; padding:6px 4px 8px; margin-bottom:4px; }
div[class*="st-key-conv-row-"][class*="-active"] {
  background: var(--ai-accent-tint);
  border-left:2px solid var(--ai-accent);
}
div[class*="st-key-conv-row-"][class*="-active"] button {
  color: var(--ai-accent-ink) !important;
  font-weight:600 !important;
}
div[class*="st-key-conv-row-"] div[class*="st-key-conv_"] button > div {
  justify-content: flex-start;
}
div[class*="st-key-conv-row-"] div[class*="st-key-conv_"] button p {
  text-align:left; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%;
}
.ai-conv-preview{
  font-size:12px; color: var(--ai-text-faint); padding:2px 14px 0; margin-top:-2px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
div[class*="st-key-conv-row-"] div[class*="st-key-delete_"] button {
  color: var(--ai-text-faint) !important; border-color: transparent !important; background: transparent !important;
}
div[class*="st-key-conv-row-"] div[class*="st-key-delete_"] button:hover {
  color: var(--ai-danger) !important; background: var(--ai-danger-tint) !important;
}

/* Par de botoes de feedback compacto, em vez de dois botoes de tamanho
   normal boiando numa coluna larga vazia. */
div[class*="st-key-feedback-"] .stButton button {
  padding:2px 10px; font-size:12px; border-radius:999px;
}

/* Acoes destrutivas nos dialogos de confirmacao (apagar/limpar conversa):
   nunca com a mesma cor de "confirmar" seguro — sempre vermelho. */
div[class*="st-key-confirm-danger-"] button[kind="primary"] {
  background: var(--ai-danger) !important;
  border-color: var(--ai-danger) !important;
}

.ai-badge{
  display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:600;
  padding:3px 10px; border-radius:999px; font-family: var(--ai-mono);
}
.ai-badge .ai-dot{ width:6px; height:6px; border-radius:50%; }

.ai-chip{
  display:inline-flex; align-items:center; gap:5px; font-family: var(--ai-mono);
  font-size:11px; background: var(--ai-surface); border:1px solid var(--ai-border);
  border-radius:6px; padding:2px 8px; margin:6px 6px 0 0; color: var(--ai-text-muted);
}

.ai-card-head{ display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.ai-icon-badge{
  width:32px; height:32px; border-radius:9px; flex:none;
  background: var(--ai-accent-tint); color: var(--ai-accent-ink);
  display:flex; align-items:center; justify-content:center;
}
.ai-card-title{ font-family: var(--ai-serif); font-size:17px; font-weight:600; color: var(--ai-text); }

.ai-system-note{
  display:flex; align-items:flex-start; gap:8px; border-left:3px solid var(--ai-border);
  border-radius:8px; padding:8px 12px; font-size:13.5px; margin:2px 0;
}
.ai-system-note-icon{ flex:none; margin-top:1px; }

/* Pulso de "sistema ativo" — reutilizado no cabecalho da pagina e no bloco
   de status da sidebar do Chat. */
.ai-pulse-dot{
  width:7px; height:7px; border-radius:50%; background: currentColor; position:relative;
  color: var(--ai-success); flex:none;
}
.ai-pulse-dot::after{
  content:""; position:absolute; inset:-4px; border-radius:50%; background: currentColor;
  opacity:.5; animation: ai-pulse 2.2s ease-out infinite;
}
@keyframes ai-pulse{
  0%{ transform:scale(.6); opacity:.55; }
  100%{ transform:scale(2.4); opacity:0; }
}

/* Cabecalho de identidade — substitui st.title/st.caption soltos no topo
   de cada pagina por uma faixa de marca consistente. */
.ai-hero{ display:flex; align-items:flex-start; gap:14px; padding:2px 0 10px; }
.ai-hero-mark{
  width:44px; height:44px; border-radius:12px; flex:none; color:#fff;
  background: linear-gradient(155deg, var(--ai-accent) 0%, var(--ai-accent-ink) 100%);
  display:flex; align-items:center; justify-content:center; box-shadow: var(--ai-shadow);
}
.ai-hero-eyebrow{
  font-family: var(--ai-mono); font-size:11px; letter-spacing:.08em;
  color: var(--ai-accent-ink);
}
.ai-hero-title{
  font-family: var(--ai-serif); font-size:26px; font-weight:600; letter-spacing:-0.01em;
  color: var(--ai-text); margin:2px 0 3px;
}
.ai-hero-subtitle{ font-size:14px; color: var(--ai-text-muted); margin:0; max-width:640px; }
.ai-hero-online{
  margin-left:auto; display:flex; align-items:center; gap:6px; font-size:12px;
  color: var(--ai-text-muted); white-space:nowrap; padding-top:8px;
}

/* Bloco de status do SISTEMA na sidebar do Chat (nunca de usuario/conta —
   o produto e de uso livre, sem login). */
.ai-sidebar-status{
  display:flex; flex-direction:column; gap:7px; padding:10px 12px; margin-bottom:10px;
  border-radius:12px; border:1px solid var(--ai-border); background: var(--ai-surface-2);
}
.ai-sidebar-status-head{
  display:flex; align-items:center; gap:6px; font-size:11px; font-weight:600;
  letter-spacing:.04em; text-transform:uppercase; color: var(--ai-text-muted); margin-bottom:1px;
}
.ai-sidebar-status-row{ display:flex; align-items:center; gap:7px; font-size:12px; color: var(--ai-text-muted); }
.ai-sidebar-status-row .ai-stat-icon-sm{
  width:20px; height:20px; border-radius:6px; flex:none;
  background: var(--ai-accent-tint); color: var(--ai-accent-ink);
  display:flex; align-items:center; justify-content:center;
}
.ai-sidebar-status-value{ margin-left:auto; color: var(--ai-text); font-weight:600; }

/* Indicador de "processando" com a voz visual do sistema (mono, cor de
   acento) em vez do spinner cru padrao do Streamlit. */
[data-testid="stSpinner"]{
  color: var(--ai-accent); font-family: var(--ai-mono); font-size:13px; letter-spacing:.01em;
}

/* Bolhas do chat: usuario com leve preenchimento em acento, assistente em
   superficie neutra — para nao serem o mesmo cinza indistinguivel do
   `st.chat_message` padrao (ver auditoria de UI/UX). */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){
  background: var(--ai-accent-tint);
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]){
  background: var(--ai-surface); border:1px solid var(--ai-border);
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
