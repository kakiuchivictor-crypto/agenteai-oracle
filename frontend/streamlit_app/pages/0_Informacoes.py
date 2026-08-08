"""Pagina de informacoes/apresentacao do agente (antiga app.py).

Redesenhada como cards (ver auditoria de UI/UX): cada secao ganha um icone
consistente (de `theme.py`) e um contorno proprio via `st.container(border=True,
key=...)`, em vez do antigo bloco continuo de `st.markdown("## ...")`. O
conteudo de cada secao continua em Markdown nativo (listas, negrito, links)
— so o cabecalho e o contorno mudaram, para nao arriscar quebrar a formatacao
existente reescrevendo tudo como HTML.

Cabecalho de marca (`hero_header`) adicionado na 2a rodada de UI/UX: substitui
`st.title`/`st.caption` soltos por uma identidade consistente.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from theme import card_header, hero_header

st.markdown(
    hero_header(
        "AxysAI",
        "Respostas para suas dúvidas",
        "Assistente de IA que responde com base em documentos corporativos aprovados — e, "
        "quando não há documento sobre o assunto, ainda tenta ajudar com conhecimento geral.",
    ),
    unsafe_allow_html=True,
)

with st.container(border=True, key="info-featured-card-o-que-faz"):
    st.markdown(card_header("check", "O que o agente faz"), unsafe_allow_html=True)
    st.markdown(
        """
- Responde perguntas em linguagem natural com base nos documentos aprovados na base de
  conhecimento.
- Quando encontra documento relevante, responde **exclusivamente** com base nele — nunca
  mistura conhecimento externo com o conteúdo do documento, para não arriscar uma informação
  errada apresentada como se fosse política ou norma da empresa.
- Quando **não** encontra nenhum documento sobre o assunto, tenta ajudar com conhecimento
  geral mesmo assim — deixando sempre claro na resposta que aquilo não veio dos documentos da
  empresa (ver "Perguntas sem documento" abaixo).
- Detecta e avisa quando fontes diferentes trazem informações conflitantes, em vez de
  escolher uma versão silenciosamente.
- Ignora qualquer tentativa de instrução escondida dentro de um documento ou da própria
  pergunta (proteção contra *prompt injection*) — o conteúdo é sempre tratado como dado,
  nunca como comando.
"""
    )

with st.container(border=True, key="info-card-como-usar"):
    st.markdown(card_header("steps", "Como usar"), unsafe_allow_html=True)
    st.markdown(
        """
1. Vá para a aba **💬 Chat** no menu lateral.
2. Digite sua pergunta na caixa de texto e envie.
3. Confira a resposta apresentada.
4. Achou a resposta útil ou não? Use os botões 👍/👎 para dar feedback.
"""
    )

with st.container(border=True, key="info-card-sem-documento"):
    st.markdown(card_header("globe", "Perguntas sem documento"), unsafe_allow_html=True)
    st.markdown(
        """
Nem toda pergunta precisa de um documento cadastrado para ser respondida. Se a base de
conhecimento não tiver nada relevante sobre o assunto, o agente pode responder com
conhecimento geral — de áreas como tecnologia, negócios, cultura geral, etc.

Uma garantia nesse modo: o agente nunca apresenta uma resposta de conhecimento geral como se
fosse política, norma ou fato registrado em algum documento da empresa — e nunca inventa o
nome de um documento que não existe. Se ele não tiver confiança suficiente na resposta —
especialmente para dados internos específicos da empresa (prazos, valores, nomes de
responsáveis) — prefere dizer que não sabe a arriscar um palpite.
"""
    )

with st.container(border=True, key="info-card-enviando"):
    st.markdown(card_header("upload", "Enviando novos documentos"), unsafe_allow_html=True)
    st.markdown(
        """
Não existe uma página separada de upload — envie documentos **direto pelo Chat**, clicando
no sinal de + ao lado da caixa de pergunta. Formatos aceitos: PDF, Word, Excel,
PowerPoint, Markdown, CSV, JSON e HTML.

Assim que o envio termina, o documento é processado (extração, limpeza, indexação) e
**aprovado automaticamente** — não é preciso esperar ninguém revisar manualmente. Em poucos
segundos ele já pode ser citado nas respostas do chat.
"""
    )

with st.container(border=True, key="info-card-planilhas"):
    st.markdown(card_header("table", "Organizando planilhas (Excel/CSV)"), unsafe_allow_html=True)
    st.markdown(
        """
Além de indexar planilhas para consulta, o agente consegue **limpar e organizar** uma
planilha e te devolver o resultado. Anexe o arquivo (.xlsx ou .csv) pelo sinal de + e escreva
um pedido com uma palavra como "organizar", "limpar", "arrumar" ou "formatar" (ex: *"pode
organizar essa planilha pra mim?"*). Não precisa ser na mesma mensagem do anexo — pode
enviar o arquivo primeiro e pedir para organizar depois, numa mensagem separada, que o
agente lembra da última planilha enviada na conversa.

O agente devolve, direto na conversa:

- Um resumo do que foi ajustado (linhas/colunas vazias removidas, duplicatas removidas).
- Uma prévia da tabela já organizada.
- Um botão para **baixar a planilha organizada** em `.xlsx`.

Também dá para pedir para **ordenar** — "organize por ordem crescente", "ordene por salário
decrescente", "classifique por nome" etc. Se você citar o nome de uma coluna no pedido, o
agente ordena por ela (funciona mesmo com acento diferente do nome exato da coluna, e mesmo
se a coluna já estiver formatada como texto tipo "R$ 5.000,00" — a ordenação é sempre
numérica quando faz sentido); se não citar nenhuma coluna, usa a primeira da planilha. O
resumo sempre diz qual coluna foi usada, então dá para pedir de novo especificando outra se
não for a que você queria.

E dá para pedir para **formatar uma coluna como moeda** — "formate o salário em reais". Isso
só funciona quando a coluna já tem valores numéricos de verdade (não texto) — nesse caso o
agente aplica a formatação de moeda do Excel sem alterar nenhum valor. Se a coluna citada não
for numérica, ou se o agente não identificar qual coluna você quis dizer, ele **avisa
explicitamente no resumo** em vez de fingir que formatou.

Por padrão **não** gera gráfico — só quando o pedido menciona algo como "gráfico" ou
"comparar" (ex: *"organize e me mostra um gráfico comparando as vendas"*).

Essa limpeza usa sempre o mesmo conjunto fixo de operações (remover linhas/colunas
totalmente vazias, remover duplicatas, remover espaços em branco nas bordas, padronizar
cabeçalhos) — o modelo de IA não escreve nem executa código sobre a sua planilha, então o
resultado é previsível e seguro.
"""
    )

with st.container(border=True, key="info-card-conversas"):
    st.markdown(card_header("chat", "Conversas"), unsafe_allow_html=True)
    st.markdown(
        """
- O histórico das suas conversas fica disponível na barra lateral do Chat, para você
  retomar qualquer uma delas.
- Use **➕ Nova conversa** para começar um assunto separado sem perder a conversa atual.
- Use **🧹 Limpar conversa** para apagar o conteúdo da conversa aberta no momento, caso
  precise recomeçar do zero.
- Use **🗑️ (lixeira)** ao lado de uma conversa no histórico para apagá-la individualmente.
"""
    )

with st.expander("Detalhes técnicos (para curiosos)"):
    st.markdown(
        """
| Camada | Tecnologia |
|---|---|
| Modelo de linguagem (LLM) | **Google Gemini** (`gemini-flash-lite-latest`) |
| Orquestração do agente | **LangChain** + **LangGraph** |
| API (backend) | **FastAPI** |
| Interface (frontend) | **Streamlit** |
| Planilhas e dados tabulares (Excel/CSV) | **Pandas** |
| Gráficos gerados a partir de planilhas | **Matplotlib** |
| Busca por similaridade (embeddings) | **sentence-transformers** |
| Banco vetorial | **Chroma** |
| Reordenação dos resultados (reranking) | **CrossEncoder** |
| Extração de documentos | PyMuPDF (PDF), python-docx (Word), python-pptx (PowerPoint), \
openpyxl (Excel), BeautifulSoup (HTML) |
| Metadados, histórico e auditoria | **SQLModel** + **SQLite** |
"""
    )
    st.caption(
        "O provedor de LLM é plugável: o mesmo agente funciona com Gemini, OpenAI, Anthropic ou "
        "Ollama (100% local) trocando uma variável no `.env`, sem alterar nenhum código."
    )

st.warning(
    "Este é um agente de IA: as respostas são geradas automaticamente e podem conter "
    "imprecisões, mesmo quando baseadas em documentos. Sempre confira as fontes citadas "
    "antes de tomar uma decisão com base na resposta.",
    icon="⚠️",
)
