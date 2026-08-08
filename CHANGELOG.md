# Changelog

Todas as mudancas relevantes deste projeto sao registradas neste arquivo.

## [1.7.0] - 2026-08-05 - Cache de respostas e teto diario de requisicoes ao LLM

Pedido do usuario: reduzir ainda mais o consumo de cota do provedor de LLM, sem exigir
nenhuma instalacao/servico extra de quem for rodar o projeto (descartada a opcao de fallback
para Ollama local, cogitada e rejeitada por esse motivo).

### Adicionado
- **`app/llm/answer_cache.py` + tabela `answer_cache`**: reaproveita a resposta ja gerada
  quando a MESMA pergunta (normalizada) e feita de novo sobre o MESMO contexto recuperado —
  pula a chamada ao provedor por completo (nem passa pelos limitadores). A chave do cache
  (`sha256(pergunta + contexto)`) inclui o texto do CONTEXTO, entao uma mudanca real nos
  documentos (nova versao, reindexacao) muda a chave automaticamente e nunca serve uma
  resposta desatualizada. Novo setting `LLM_ANSWER_CACHE_ENABLED` (padrao `true`).
- **`app/llm/daily_usage.py` + tabela `llm_daily_usage`**: contador diario de chamadas ao
  provedor, persistido no banco (sobrevive a reinicios do processo — diferente do
  `LlmCallLimiter`, que e por minuto e em memoria). Complementa o limite por minuto: planos
  gratuitos tambem tem teto de requisicoes POR DIA, e sem essa guarda o sistema pode parecer
  saudavel a manha inteira e travar de vez a tarde sem aviso. Novo setting
  `LLM_DAILY_REQUEST_LIMIT` (padrao `0` = desligado — o numero exato varia por
  modelo/conta, confira o seu em aistudio.google.com/apikey antes de ativar).
- `make_generate_answer` agora recebe `session` (mesma convencao ja usada por
  `make_build_context`/`make_rerank_results`) para consultar/gravar cache e contador diario.
- Migration Alembic `c7a29f4e1b83` (tabelas `answer_cache` e `llm_daily_usage`), aplicada ao
  banco de desenvolvimento local.

### Validacao realizada
- `pytest`: 227 passed (9 testes novos: cache — chave estavel/muda com contexto,
  grava/le, reaproveita resposta sem chamar o modelo de novo, ignora contexto diferente;
  contador diario — desliga com limite 0, nega alem do limite, acumula entre chamadas;
  `generate_answer` retorna `provider_busy` com mensagem propria quando o teto diario e
  atingido). `ruff check`: sem avisos. Migration validada com `alembic upgrade head` contra um
  banco SQLite descartavel (schema inicial -> `c7a29f4e1b83` sem erros) e aplicada ao
  `data/app.db` real de desenvolvimento.
- Teste manual ao vivo: mesma pergunta enviada duas vezes via `graph.invoke` contra o Gemini
  real — 1a chamada 1233ms (`route: general_knowledge`, resposta gerada normalmente), 2a
  chamada 362ms com a MESMA resposta, log `agent.answer_cache_hit`, sem nova chamada ao
  provedor.
- README com contagem de testes corrigida (estava com "211 testes" desde antes da v1.6.0,
  nunca atualizada apos os 218 daquela versao) para 227.

## [1.6.0] - 2026-08-05 - Revisao completa: protecao de cota do LLM, limpeza de recursos, confirmacoes de UI

Pedido do usuario: revisao completa do sistema para levantar melhorias. Achados reportados
por prioridade e todos corrigidos nesta versao (ver relatorio completo entregue junto).

### Adicionado
- **`app/llm/rate_limiter.py`** (`LlmCallLimiter`): limitador GLOBAL (nao por IP/usuario) de
  chamadas ao provedor de LLM, em janela deslizante de 60s. Diferente do `RateLimitMiddleware`
  existente (protege a API contra abuso de um cliente), este protege a cota REAL do provedor
  (Gemini free tier: ~15 req/min compartilhada pelo projeto inteiro, nao por pessoa). Quando o
  limite e atingido, a chamada ao provedor nem chega a ser feita — nova rota `provider_busy`
  no grafo do agente, com mensagem amigavel imediata em vez de esperar um 429 real. Cacheado
  pelo VALOR do limite (`get_llm_rate_limiter(max_calls_per_minute)`), nao um singleton fixo,
  para nao interferir entre producao e testes. Novo setting `LLM_RATE_LIMIT_PER_MINUTE`
  (padrao `12`, um pouco abaixo da cota real do Gemini de proposito).
- **`LLM_MAX_RETRIES`** (padrao `2`, era o padrao da lib — 6 para o Gemini): reduz quantas
  vezes o cliente HTTP tenta de novo sozinho antes de desistir. Aplicado em
  Anthropic/OpenAI/Gemini (Ollama nao tem esse campo). Motivacao: com cota por minuto
  esgotada, cada retry e mais uma chamada contra a MESMA janela ja estourada — o pedido
  demorava 80-120s+ so para falhar de qualquer jeito de qualquer forma.
- **Confirmacao antes de apagar/limpar conversa no Chat** (`st.dialog`): um clique sem
  querer no 🗑️ ou no "Limpar conversa atual" nao apaga mais nada direto — abre um modal
  pedindo "Apagar"/"Limpar" ou "Cancelar".

### Corrigido
- **Erro de cota do Gemini (429) vazava texto tecnico bruto direto na resposta do chat**,
  como se o agente tivesse "dito" aquilo (nomes de metrica interna, `quota_id`, JSON de
  violacao) — confirmado ao vivo numa sessao anterior. `app/llm/errors.py` ganhou deteccao
  especifica de erro de cota/rate-limit (`429`, `quota`, `resource exhausted`, `rate limit`),
  traduzido para `RateLimitExceededError` com mensagem limpa antes de cair no fallback
  generico que incluia `str(exc)` cru.
- **Conexoes SQLite nao fechadas na suite de testes** (`tests/conftest.py`): a fixture
  `db_session` criava um `Engine` novo por teste mas nunca chamava `.dispose()` — 47
  `ResourceWarning: unclosed database` na suite completa (visivel com `--cov`). Corrigido com
  `engine.dispose()` apos o teardown do `Session`.
- README com contagem de testes desatualizada ("181 testes", hoje 218).

### Validacao realizada
- `pytest`: 218 passed (7 testes novos: `LlmCallLimiter` — dentro do limite, alem do limite,
  libera apos a janela passar, limite 0 desliga a guarda; `translate_llm_error` — erro real de
  cota do Gemini vira mensagem limpa sem vazar texto tecnico, palavra-chave generica de rate
  limit; `generate_answer` retorna `provider_busy` SEM chamar o modelo quando a cota local ja
  esta esgotada, verificado por contador de chamadas). Zero `ResourceWarning` na suite
  (antes: 47). `ruff check`: sem avisos.
- Teste manual ao vivo: API e Streamlit reiniciados com todas as mudancas, uma pergunta real
  via `/chat` respondeu normalmente (`route: continue`, `grounded: true`, 14.1s) — confirma
  que reduzir `max_retries`/adicionar o limitador nao quebrou o caminho feliz. Smoke test das
  paginas Streamlit confirma que os novos dialogs de confirmacao nao quebram a renderizacao.

## [1.5.2] - 2026-08-04 - Pedidos de planilha encadeados na mesma conversa

Usuario reportou que, ao pedir uma segunda coisa na mesma planilha sem reanexar o arquivo
(ex: organizar por salario, depois pedir mais um ajuste), o agente "se perdia" e reprocessava
do zero a partir do arquivo original bagunçado, perdendo tudo que ja tinha sido organizado.

### Corrigido
- **`frontend/streamlit_app/pages/1_Chat.py`**: `_run_organize_flow` agora atualiza
  `active["last_spreadsheet"]` para apontar para o RESULTADO ja organizado (nome + bytes do
  xlsx retornado pela API) em vez de deixar apontando para o arquivo original enviado no
  upload. Como um pedido de "organizar" sem novo anexo reusa `last_spreadsheet` (v1.4.1),
  isso fazia cada pedido seguinte reprocessar o arquivo cru desde o inicio — reintroduzindo
  linhas vazias/duplicatas ja removidas e perdendo qualquer ordenacao/formatacao anterior que
  o novo pedido nao repetisse explicitamente. Agora cada pedido novo continua de onde o
  anterior parou.

### Validacao realizada
- `pytest`: 211 passed (sem regressao; a correcao e puramente de estado do frontend, sem
  testes automatizados novos — validada manualmente, ver abaixo). `ruff check`: sem avisos.
- Teste manual ao vivo encadeando duas chamadas reais contra `/tools/organize-spreadsheet`
  (simulando exatamente o fluxo do Chat: a segunda chamada usa os bytes retornados pela
  primeira): planilha com duplicata e linha vazia → passo 1 organiza e ordena por salario
  (remove a duplicata, ordena) → passo 2 pede para ordenar por nome, SEM a duplicata
  reaparecer e SEM refazer a limpeza (resumo do passo 2: "nenhuma alteracao necessaria",
  confirmando que partiu da tabela ja limpa, nao do arquivo original).

### Limitacao conhecida
- Formatacao de moeda (R$) aplicada num passo nao "gruda" automaticamente nos passos
  seguintes: `pd.read_excel` le apenas valores, nao a formatacao de celula do Excel, entao
  reprocessar o resultado perde o `number_format` anterior a menos que o novo pedido peca a
  formatacao de novo. Os VALORES em si nunca sao afetados por essa limitacao — so a exibicao
  como moeda no Excel. Nao corrigido nesta versao (exigiria persistir metadados de
  formatacao entre chamadas, fora do escopo desta correcao pontual).

## [1.5.1] - 2026-08-04 - Ordenacao robusta (acentos/moeda) + formatacao de reais + avisos honestos

Usuario reportou um pedido real que so funcionou pela metade: "Organize todos os 50
funcionarios em ordem crescente de salario. Preserve todas as colunas e registros, formate
os salarios em reais e devolva uma nova planilha Excel. Nao altere os valores." — a
ordenacao "esqueceu" do salario, e a formatacao em reais foi ignorada em silencio. Pediu
tambem para o agente avisar quando nao conseguir cumprir algo, em vez de so ignorar.

Duas causas raiz identificadas por revisao de codigo (sem acesso ao arquivo real do
usuario, mas ambas plausiveis e agora cobertas por teste):
1. O casamento "nome da coluna aparece no pedido" (`_find_sort_column`, v1.5.0) era
   sensivel a acento — "salario" (sem acento, como a pessoa digitou) nao batia com a coluna
   real "Salário" (com acento), entao caia no fallback e ordenava pela primeira coluna.
2. Mesmo batendo a coluna certa, se ela ja vinha formatada como texto (`"R$ 12.500,50"`),
   `sort_values` ordenava alfabeticamente, nao numericamente — "R$ 1.200" < "R$ 15.000" <
   "R$ 2.000" nessa ordem, o que parece "nao ordenado" para quem olha os valores.

### Corrigido
- **`app/documents/spreadsheet_tools.py`**: `_find_sort_column` virou `_find_mentioned_column`
  — casamento agora ignora acentos/caixa (`_normalize_for_match`, via
  `unicodedata.normalize("NFKD", ...)`) e, entre varias colunas que casarem, prefere a de
  nome mais especifico/longo (evita que uma coluna curta e generica "roube" o casamento).
- **`_numeric_sort_key`**: quando a coluna-alvo da ordenacao nao e numerica, tenta extrair um
  valor numerico dos textos (remove "R$", separador de milhar, troca virgula decimal por
  ponto) so para decidir a ORDEM das linhas — os valores originais na planilha nunca sao
  reescritos (`kind="stable"`, chave de ordenacao descartada depois de usada).

### Adicionado
- **Formatacao de moeda (R$)**: pedidos como "formate o salario em reais" agora aplicam a
  formatacao de moeda do Excel (`worksheet.cell(...).number_format = '"R$" #,##0.00'`) na
  coluna reconhecida — SO quando ela ja e numerica de verdade (nunca converte texto em
  numero, para respeitar literalmente "nao altere os valores"). `dataframe_to_xlsx_bytes`
  ganhou o parametro `currency_columns`.
- **Avisos explicitos quando o pedido nao pode ser cumprido**
  (`SpreadsheetCleaningResult.warnings`, exibidos no `summary` com ⚠️): coluna de moeda nao
  identificada, coluna de moeda identificada mas nao numerica, e nota quando a coluna de
  ordenacao foi um "chute" (nenhuma coluna citada no pedido, usou a primeira) — isso e o
  equivalente, nesta ferramenta 100% determinista (sem LLM), ao que o usuario pediu como
  "melhorar o prompt para avisar quando nao conseguir realizar a tarefa": como esse fluxo
  nunca passa pelo modelo de linguagem, a "honestidade sobre falha" e implementada como
  mensagem explicita no resultado, nao como instrucao de prompt.

### Validacao realizada
- `pytest`: 211 passed (11 testes novos: casamento de coluna ignorando acento, ordenacao
  numerica de coluna formatada como moeda-texto, formatacao de moeda aplicada quando numerica
  e number_format conferido via `openpyxl`, avisos quando a coluna de moeda nao e numerica ou
  nao e identificavel, e um teste de integracao reproduzindo o pedido exato do usuario).
  `ruff check`: sem avisos.
- Teste manual ao vivo via API real (sem consumir cota do Gemini — fluxo 100% determinista):
  50 funcionarios com salario formatado como texto ("R$ 12.500,50") ordenados corretamente
  em ordem numerica crescente (R$ 1.712,00 ... R$ 19.890,00), com aviso explicito de que a
  formatacao de moeda nao foi aplicada por a coluna ja ser texto. Segundo teste com salario
  numerico de verdade: ordenado e formatado como moeda com sucesso.

## [1.5.0] - 2026-08-04 - Organizar planilha agora suporta ordenacao

Usuario reportou que pedir para "organizar novamente por ordem crescente" nao funcionava
corretamente. Causa raiz: nao era um bug, era escopo — `clean_spreadsheet` nunca implementou
ordenacao (decisao deliberada da v1.4.0: so "limpeza automatica" fixa, sem interpretar
pedidos livres). O pedido do usuario rodava a limpeza normalmente, so nao ordenava nada,
dando a impressao de que o agente "nao obedeceu".

### Adicionado
- **`app/documents/spreadsheet_tools.py`**: `clean_spreadsheet` ganhou o parametro
  `request_text` (texto livre do pedido do usuario). `_detect_sort_intent` reconhece pedidos
  de ordenacao por palavra-chave ("orden", "classific", "crescente", "decrescente", etc.) —
  sem essas palavras, nada muda (comportamento anterior preservado). `_find_sort_column` casa
  o nome de alguma coluna REAL da planilha como substring do pedido (ex: "ordene por vendas"
  → coluna `Vendas`); sem coluna reconhecida, usa a primeira coluna como padrao previsivel.
  Continua 100% deterministico — nenhum codigo e gerado ou executado a partir do pedido, so
  casamento de texto contra nomes de coluna ja conhecidos.
  `SpreadsheetCleaningResult` ganhou `sort_column`/`sort_ascending`, e o `summary` agora
  informa explicitamente qual coluna foi usada para ordenar (ou nao menciona nada, se a
  planilha nao foi ordenada) — importante para o usuario perceber e corrigir se o agente
  escolheu a coluna errada por falta de uma citada no pedido.
- **`POST /tools/organize-spreadsheet`**: novo campo de formulario `request_text` (opcional),
  repassado direto para `clean_spreadsheet`.
- **Chat**: `question` (o texto digitado pelo usuario) passa a ser enviado como
  `request_text` em toda chamada de organizar planilha — tanto quando o arquivo e anexado na
  mesma mensagem quanto quando reaproveita a ultima planilha lembrada da conversa (v1.4.1).

### Validacao realizada
- `pytest`: 204 passed (8 testes novos cobrindo ordenar por coluna citada
  ascendente/descendente, sem coluna citada usando a primeira, e sem ordenar quando o pedido
  nao menciona nada disso). `ruff check`: sem avisos.
- Teste manual ao vivo via API real reproduzindo o pedido exato do usuario ("organize
  novamente por ordem crescente"): planilha sem coluna citada no pedido, ordenada
  corretamente pela primeira coluna, resumo confirma qual coluna foi usada. Teste feito
  direto contra `/tools/organize-spreadsheet` (sem passar pelo `/chat`), entao nao consumiu
  cota do Gemini.

## [1.4.2] - 2026-08-04 - Troca para gemini-flash-lite-latest (mais cota gratuita)

Usuario reportou estourar o limite de requisicoes do Gemini rapido demais. Pesquisado (ver
resposta anterior com fontes) que, no plano gratuito, o Flash-Lite tem bem mais margem que o
Flash usado ate entao: ~15 RPM / 1000 RPD contra ~10 RPM / 250 RPD — cerca de 4x mais
requisicoes por dia. O Pro saiu do plano gratuito (so Flash/Flash-Lite continuam gratuitos).

### Alterado
- **`LLM_MODEL` de `gemini-flash-latest` para `gemini-flash-lite-latest`** em `.env` e
  `.env.example`. Mantido o alias `-latest` (em vez de fixar numa versao como
  `gemini-3.5-flash-lite`) pelo mesmo motivo documentado na v1.0.6: nomes de versao fixos ja
  foram descontinuados duas vezes neste projeto (`gemini-2.5-flash`, depois
  `gemini-2.5-flash-lite`, ambos com erro `404 ... no longer available to new users`) —
  o alias e quem absorve essa troca automaticamente no futuro.
- Referencias ao nome do modelo atualizadas em `tests/unit/llm/test_factory.py`,
  `frontend/streamlit_app/pages/0_Informacoes.py` e `README.md`.

### Validacao realizada
- `pytest`: 198 passed. `ruff check`: sem avisos.
- Teste manual ao vivo via API real: `route: continue`, `grounded: true`,
  `model_used: models/gemini-flash-lite-latest`, resposta correta. Durante a validacao,
  varias chamadas de teste em sequencia rapida (testando nomes de modelo alternativos)
  esgotaram propositalmente a cota de 15 req/min e provocaram um `429` real do Google —
  confirmando ao vivo o numero exato do limite (`quota_value: 15`,
  `model: gemini-3.5-flash-lite`, o que `gemini-flash-lite-latest` resolve hoje) e validando
  que o erro e tratado sem quebrar a aplicacao (`route: provider_error`, mensagem clara).
  Observacao: o retry automatico do LangChain em cima de erro 429 tambem consome cota a cada
  nova tentativa — em rajadas de teste manual isso pode prolongar o proprio esgotamento da
  janela; nao e um problema em uso normal (uma pergunta por vez).

## [1.4.1] - 2026-08-04 - Correcoes no fluxo de organizar planilha

Usuario reportou que o recurso "parecia nao obedecer". Causa raiz: a deteccao de intencao
so disparava quando o arquivo e o pedido de "organizar" chegavam na MESMA mensagem do chat
— um uso perfeitamente natural (enviar o arquivo primeiro, pedir para organizar depois, em
mensagens separadas) simplesmente nao acionava o fluxo e caia sem querer no chat normal de
RAG. Usuario tambem pediu para o grafico deixar de ser gerado sempre, so quando pedido
explicitamente.

### Corrigido
- **`frontend/streamlit_app/pages/1_Chat.py`**: toda planilha anexada (mesmo sem pedido de
  "organizar" naquele momento) passa a ser lembrada em `active["last_spreadsheet"]`
  (nome + bytes, por conversa). Um pedido de "organizar" numa mensagem posterior, sem novo
  anexo, agora reusa essa planilha lembrada em vez de cair no fluxo de chat normal. Quando
  nao ha nenhuma planilha lembrada na conversa, o agente avisa explicitamente em vez de
  silenciosamente ignorar o pedido ("Nao encontrei nenhuma planilha para organizar nesta
  conversa...").

### Alterado
- **Grafico deixa de ser gerado por padrao**: `POST /tools/organize-spreadsheet` ganhou o
  parametro `generate_chart` (form field, padrao `false`) — `build_summary_chart` so roda
  quando `generate_chart=true`. No Chat, isso e decidido por deteccao de palavra-chave
  separada da deteccao de "organizar" (`_wants_chart`: "grafico"/"gráfico"/"chart"/"compara"),
  entao um pedido simples de "organiza essa planilha" nao gera grafico — so quando o pedido
  menciona algo como "gráfico" ou "comparar" (ex: "organize e me mostra um grafico
  comparando as vendas").

### Validacao realizada
- `pytest`: 198 passed. Teste antigo que esperava grafico sempre presente ajustado para o
  novo padrao (`generate_chart=False`); teste novo confirma que `generate_chart=true` ainda
  produz o grafico. `ruff check`: sem avisos.
- Teste manual ao vivo via API real: mesmo payload de planilha com `generate_chart=false` ->
  `chart_base64: null`; com `generate_chart=true` -> grafico presente.

## [1.4.0] - 2026-08-04 - Organizar planilhas pelo chat (limpeza + grafico + download)

Pedido original: usuario enviou um .xlsx pelo chat pedindo para organizar a tabela e receber
de volta, e o sistema nao tinha nenhuma capacidade de editar/gerar arquivos — so respondia
perguntas sobre o conteudo. Antes de implementar, perguntei ao usuario o escopo (limpeza fixa
vs. comandos flexiveis, graficos, execucao de codigo) dado que "comandos flexiveis" normalmente
implicaria o modelo gerar codigo para rodar no servidor, contradizendo a regra 12 do
`SYSTEM_PROMPT` ("nunca execute codigo"). Confirmado: limpeza automatica fixa, grafico no
chat, sem execucao de codigo.

### Adicionado
- **`app/documents/spreadsheet_tools.py`** (novo modulo, sem uso de LLM): `clean_spreadsheet`
  aplica um conjunto FIXO e deterministico de operacoes via pandas — remove linhas/colunas
  totalmente vazias, remove linhas duplicadas, remove espacos em branco nas bordas de texto e
  nos nomes de coluna, preenche nomes de coluna vazios/duplicados de forma previsivel. Nao
  ordena por nenhuma coluna (nao ha como adivinhar qual faz sentido sem perguntar) e nao
  interpreta pedidos livres — nenhum codigo gerado por modelo de linguagem e executado em
  nenhum momento. `dataframe_to_xlsx_bytes` escreve o resultado de volta em `.xlsx`.
  `build_summary_chart` gera um grafico de barras heuristico (matplotlib): primeira coluna
  numerica como valor, primeira coluna categorica como rotulo (somando categorias repetidas);
  sem coluna numerica, retorna `None` em vez de forcar um grafico sem sentido.
- **`POST /tools/organize-spreadsheet`** (`app/api/routes/tools.py`, `app/schemas/api/tools.py`):
  rota nova, stateless — nao persiste nada no banco nem no indice vetorial (diferente de
  `/documents`). Reaproveita `validate_upload` (mesma validacao de extensao/MIME/tamanho do
  upload normal) e devolve `summary`, `file_base64` (o `.xlsx` organizado), `chart_base64`
  (grafico em PNG, ou `null`), `columns`, `preview_rows` e `total_rows`.
- **Integracao no Chat** (`frontend/streamlit_app/pages/1_Chat.py`): ao anexar um `.xlsx`/`.csv`
  junto com um pedido contendo "organizar"/"limpar"/"arruma"/"formata"/"reorganiz", o arquivo
  vai para o novo endpoint em vez do upload normal (que indexa para RAG). O resultado aparece
  na propria conversa: resumo, `st.dataframe` com a previa, `st.image` com o grafico (quando
  houver) e `st.download_button` com o `.xlsx` organizado. O resultado fica salvo na mensagem
  (`kind: "spreadsheet_result"`) para continuar renderizavel (incluindo o botao de download)
  ao reabrir aquela conversa no historico.
- **`matplotlib`** adicionado como dependencia (`requirements.txt`, `pyproject.toml`) — unica
  lib nova deste recurso; tudo o resto (pandas, openpyxl) ja era usado no projeto.
- Pagina **Informacoes** e README ganharam uma secao "Organizar planilhas" explicando o
  recurso e deixando explicito, para o usuario final, que a limpeza nunca envolve o modelo de
  linguagem gerando ou executando codigo.

### Validacao realizada
- `pytest`: 197 passed (14 testes novos: `tests/unit/documents/test_spreadsheet_tools.py` —
  remocao de linhas/colunas vazias, duplicatas, trim de espacos, leitura de csv, rejeicao de
  extensao invalida/arquivo corrompido, geracao de grafico com/sem coluna numerica; e
  `tests/integration/test_tools_api.py` — fluxo completo via API real incluindo os mesmos
  erros de validacao de upload ja usados em `/documents/upload`). `ruff check`: sem avisos.
- Teste manual ponta-a-ponta via API real: planilha com linhas/coluna vazias e duplicatas
  enviada a `/tools/organize-spreadsheet`, resposta 200 com resumo correto, xlsx retornado
  valido (reaberto com pandas para conferir), grafico gerado.

## [1.3.0] - 2026-08-04 - Modo de conhecimento geral, apagar conversa, info de tecnologias

### Adicionado
- **Modo de conhecimento geral**: quando nenhum documento relevante existe sobre o assunto,
  o agente agora tenta responder mesmo assim usando conhecimento geral do modelo, em vez de
  simplesmente recusar. A resposta sempre deixa explicito que nao veio dos documentos da
  empresa. Implementado em duas partes:
  - `app/agents/prompts/templates.py`: `SYSTEM_PROMPT` reescrito com dois modos claramente
    separados e nunca misturaveis — MODO DOCUMENTO (CONTEXTO presente: continua tao estrito
    quanto antes, nunca completa lacunas com conhecimento externo) e MODO CONHECIMENTO GERAL
    (CONTEXTO vazio: pode responder por conta propria, mas so se confiante, sempre avisando
    que nao veio de documento, e admitindo quando nao sabe em vez de arriscar um palpite).
    Reforcada tambem a regra de tratar a PERGUNTA do usuario como dado, nao so o documento
    (protecao contra injecao via pergunta, nao so via documento).
  - `app/agents/graph.py`: `"no_evidence"` deixou de ser uma saida antecipada
    (`_EARLY_EXIT_ROUTES`) — o pipeline agora sempre chega em `generate_answer`, que decide o
    modo com base no `CONTEXTO` estar vazio ou nao.
  - `app/agents/nodes/generation.py`: `make_generate_answer` passa a marcar
    `route: "general_knowledge"` quando responde sem contexto (distinto de `"continue"`),
    para ficar visivel em logs/API/testes qual modo foi usado.
- **Limiar de relevancia pos-reranking** (`RERANK_MIN_SCORE`, padrao `0.3`): a busca vetorial
  sempre devolve os "vizinhos mais proximos" mesmo quando nada e realmente relevante — sem
  esse corte, o modo de conhecimento geral nunca seria acionado numa base ja populada, porque
  sempre haveria algum CONTEXTO fraco (porem nao vazio) vindo de documentos sem relacao real
  com a pergunta. `app/agents/nodes/retrieval.py` (`make_rerank_results`) agora descarta
  resultados abaixo do limiar antes de montar o CONTEXTO. Exposto tambem em
  `GET /config` (`rerank_min_score`).
- **Apagar conversa individual no Chat**: cada item do historico na barra lateral
  (`frontend/streamlit_app/pages/1_Chat.py`) ganhou um botao 🗑️ para remove-la da lista.
  Assim como "Limpar conversa", e uma operacao local ao frontend (`st.session_state`) — nao
  chama nenhum endpoint de exclusao no backend, as mensagens continuam no banco para
  auditoria.
- **Informacoes de tecnologia na pagina "Informacoes"**
  (`frontend/streamlit_app/pages/0_Informacoes.py`): tabela explicando o que roda por tras do
  agente (Gemini, LangChain/LangGraph, FastAPI, Streamlit, Pandas, sentence-transformers,
  Chroma, CrossEncoder, PyMuPDF/python-docx/python-pptx/openpyxl/BeautifulSoup, SQLModel),
  alem de uma secao nova explicando o modo de conhecimento geral para quem esta usando o
  sistema pela primeira vez.

### Validacao realizada
- `pytest`: 183 passed. Testes novos/reescritos em `tests/integration/test_agent_graph.py`
  (fallback para conhecimento geral quando nada esta indexado; garante que contexto parcial
  NUNCA cai no modo conhecimento geral) e `tests/security/test_prompt_injection.py`
  (pergunta maliciosa sem documento indexado agora cai em `general_knowledge` em vez de travar
  numa recusa automatica). `ruff check`: sem avisos.
- Teste manual ponta-a-ponta com Gemini real: "Qual a capital da Franca?" →
  `route: general_knowledge`, `grounded: false`, resposta correta e explicitamente rotulada
  como fora dos documentos. "Quantos dias de ferias..." (com documento, mas sem o dado exato)
  → continuou recusando no modo documento em vez de completar com conhecimento geral,
  confirmando que o limiar de relevancia distingue os dois casos corretamente.

## [1.2.0] - 2026-08-04 - Interface enxuta: so Informacoes + Chat, upload pelo chat, historico de conversas

### Removido
- **Documentos/Curadoria/Configuracoes/Painel fora do menu**: `app.py` deixou de ser uma
  pagina de conteudo e virou um roteador fino via `st.navigation`/`st.Page`, listando so
  "Informacoes" e "Chat". Os quatro arquivos continuam existindo em `pages/` (nada foi
  apagado) mas nao aparecem mais no menu nem sao navegaveis pelo app em execucao — para
  reativar algum, basta acrescenta-lo a lista `pages` em `app.py`. Motivacao: com curadoria
  automatica e sem administrador, essas telas pararam de fazer parte do fluxo normal de uso.
- **Filtro de categoria no Chat**: a selecao de categoria na barra lateral (`Filtros`) foi
  removida — o parametro `category_filter` continua existindo na API/`send_chat_message`
  para quem quiser usa-lo programaticamente, so nao ha mais widget na interface.

### Adicionado
- **Upload de documento direto no chat** (`frontend/streamlit_app/pages/1_Chat.py`): o campo
  de pergunta usa `st.chat_input(accept_file="multiple", file_type=[...])` (recurso nativo do
  Streamlit 1.40+), que renderiza um icone de clipe 📎 ao lado da caixa de texto. Anexar um
  ou mais arquivos ali dispara upload + processamento (mesmo caminho da antiga pagina
  Documentos, sem os campos avancados de categoria/tags/classificacao) e mostra o resultado
  como uma mensagem do agente na propria conversa.
- **Historico de conversas com multiplas conversas paralelas**: `st.session_state["conversations"]`
  passa a guardar varias conversas (nao so uma) — barra lateral lista todas, com a ativa
  destacada; botao **➕ Nova conversa** cria uma conversa separada sem descartar a atual;
  botao **🧹 Limpar conversa atual** continua existindo, agora limpando so a conversa aberta
  no momento. O historico e local ao navegador (`st.session_state`), nunca buscado do
  backend — como o sistema nao tem login, `GET /chat/sessions` retorna sessoes de todo mundo,
  entao usa-lo para "historico" misturaria conversas de pessoas diferentes.
- **Nova pagina "Informacoes"** (`pages/0_Informacoes.py`, antigo conteudo de `app.py`):
  explica o que o agente faz, como perguntar, como enviar documentos pelo clipe do chat, e
  como funcionam as conversas/historico — pensada para alguem chegando no sistema pela
  primeira vez sem nenhum contexto previo.

### Validacao realizada
- `pytest`: 182 passed (`tests/integration/test_streamlit_pages.py` reescrito: testa as
  paginas visiveis — `app.py`, `0_Informacoes.py`, `1_Chat.py` — e tambem confirma que as
  paginas escondidas continuam validas caso sejam reativadas). `ruff check`: sem avisos.
- Inspecao via `AppTest`: confirmado que `app.py` cai em "Informacoes" por padrao, que o
  `chat_input` do Chat tem `accept_file` habilitado com os 9 formatos aceitos, e que a barra
  lateral do Chat nao tem mais nenhum widget de "Filtros".

## [1.1.0] - 2026-08-04 - Remocao completa de login/RBAC (uso livre)

Mudanca de arquitetura pedida explicitamente: o sistema e de uso livre para todos os
usuarios, sem cadastro/administrador dedicado gerenciando acessos — a automacao de
curadoria (`AUTO_APPROVE_ON_UPLOAD`, ja existente desde a v1.0.3) passa a ser a peca central
para viabilizar isso, ja que nao ha mais curador/admin logado para aprovar manualmente.

### Removido
- **Autenticacao JWT e RBAC por completo**: rotas `/auth/*`, `app/api/dependencies/auth.py`
  (`get_current_user`, `require_admin`, `require_curator_or_admin`), `app/services/auth_service.py`,
  `app/schemas/api/auth.py`, e as primitivas de senha/JWT em `app/core/security.py`
  (`hash_password`, `verify_password`, `create_access_token`, `decode_access_token`).
  Dependencias `python-jose`/`bcrypt`/`email-validator` removidas de `requirements.txt` e
  `pyproject.toml` (ficaram sem nenhum uso). Todos os endpoints da API respondem
  diretamente, sem exigir token.
- **Restricao de acesso por classificacao de documento/papel de usuario**
  (`ROLE_ALLOWED_CLASSIFICATIONS`, `allowed_classifications_for_role`,
  `check_permissions` no grafo do agente, bucket `access_denied` em
  `app/retrieval/permissions.py`): o campo `access_classification` continua existindo no
  documento como metadado, mas deixou de restringir quem pode ver a resposta. O unico
  controle de acesso que resta e por status de curadoria (`approved` vs pendente/rejeitado).
- **Login/RBAC no frontend Streamlit**: `frontend/streamlit_app/auth.py` (formulario de
  login, badge de usuario, botao de sair) removido inteiramente; todas as paginas
  (`app.py`, `1_Chat.py` a `5_Painel.py`) renderizam direto, sem gate de papel — upload,
  curadoria e configuracoes agora sao acessiveis a qualquer pessoa que abra a interface.

### Alterado
- **`AUTO_APPROVE_ON_UPLOAD` passa a `true` por padrao** (antes `false`, opt-in "para
  testes"): sem administrador dedicado, exigir aprovacao manual travaria o uso normal do
  sistema. A pagina de Curadoria continua disponivel para quem quiser revisar/rejeitar um
  documento manualmente — so deixou de ser obrigatoria.
- **Atribuicao de acoes**: uploads, aprovacoes, sessoes de chat e feedback passam a ser
  atribuidos a um unico usuario "sistema" fixo (`app/core/system_user.py`,
  `SYSTEM_USER_ID`), criado por `scripts/seed_system_user.py` (substitui
  `scripts/seed_admin.py`). A tabela `users` continua existindo (sem migration necessaria —
  as chaves estrangeiras existentes ja eram opcionais/nao aplicadas pelo SQLite em uso) para
  satisfazer as referencias ja existentes em `ChatSession`, `Feedback`, `Document` e
  `AuditEvent`.
- **Grafo do agente simplificado**: no `check_permissions` removido; `AgentState` perdeu os
  campos `user_role`/`allowed_classifications`; `categorize_results` agora so recebe
  `results`/`session` (sem `allowed_classifications`); rota `access_denied` removida do
  roteamento (`_EARLY_EXIT_ROUTES`) — os unicos desvios possiveis relacionados a curadoria
  agora sao `pending_approval` (documento ainda nao aprovado) e `no_evidence`.
- **`api_client.py` (frontend)**: chamadas HTTP passam por um novo wrapper `_request()` que
  converte falhas de conexao (`ConnectionError`/timeout) em `ApiError` — antes, uma API fora
  do ar quebraria a pagina com uma excecao crua, algo mascarado ate agora porque toda pagina
  parava no formulario de login antes de chamar a API de verdade.

### Corrigido
- `NO_EVIDENCE_MESSAGE` e textos da interface (`1_Chat.py`) que mencionavam "documentos
  autorizados" — nao fazia mais sentido sem controle de acesso por usuario; ajustado para
  "documentos aprovados".

### Validacao realizada
- `pytest`: 181 passed (suite ajustada: testes de login/RBAC removidos —
  `tests/security/test_auth_and_permissions.py` — e os demais testes de integracao/seguranca
  reescritos para chamar a API sem cabecalho de autenticacao). `ruff check`: sem avisos.
- Smoke test das paginas Streamlit (`tests/integration/test_streamlit_pages.py`) reescrito:
  antes validava que a pagina parava no formulario de login; agora valida que cada pagina
  renderiza por completo sem excecao, sem sessao alguma.

## [1.0.6] - 2026-08-04 - Provedor de LLM Google Gemini (novo padrao)

### Adicionado
- **Novo provedor de LLM: Gemini** (`app/llm/factory.py`, `app/core/config.py`), via
  `langchain-google-genai>=2.0,<3.0`. Motivacao: o projeto sera entregue como desafio para
  outras pessoas testarem sem precisar instalar/baixar um modelo local (Ollama) — Gemini
  tem camada gratuita e responde em segundos, sem custo de carregar modelo na memoria.
  - `LLMProvider.GEMINI` no enum de configuracao; `GEMINI_API_KEY` validada como obrigatoria
    quando `LLM_PROVIDER=gemini` (mesmo padrao de validacao usado para Anthropic/OpenAI).
  - O padrao de CLASSE em `Settings` continua `ollama` (nao exige credencial), para nao
    quebrar `Settings()` construido sem `.env` nos testes; o `.env`/`.env.example` reais do
    projeto passam a trazer `LLM_PROVIDER=gemini` — e esse arquivo, nao a classe, e quem
    decide o provedor efetivo da aplicacao rodando.
  - `LLM_MODEL` passou a `gemini-flash-latest` (alias mantido pelo Google sempre apontando
    para o Flash mais recente) em vez de uma versao fixa como `gemini-2.5-flash` — essa
    versao especifica ja retornou 404 "no longer available to new users" durante o teste
    ao vivo, o que causava 5 tentativas com backoff exponencial (~1min) antes de falhar.
  - Teste de regressao (`tests/unit/llm/test_factory.py`) confirma que `max_output_tokens`
    e `timeout` sao campos reais aceitos por `ChatGoogleGenerativeAI` (evita repetir o
    mesmo tipo de bug silencioso corrigido no Ollama na versao anterior).

### Corrigido
- **`LLM_MAX_TOKENS` 500->2048**: modelos Gemini "thinking" (2.5+, incluindo o resolvido por
  `gemini-flash-latest`) gastam tokens de raciocinio interno (nao visiveis na resposta) do
  MESMO orcamento de `max_output_tokens`. Com o limite de 500 (ajustado na versao anterior
  para velocidade em CPU com Ollama), respostas mais elaboradas eram cortadas no meio da
  frase — medido ao vivo: ate 221 tokens de "thoughts" consumidos de um limite de 500.
  Tentativa de desligar o raciocinio via `thinking_budget=0` foi revertida: o modelo por
  tras do alias atual (`gemini-3.6-flash`) rejeita esse valor com erro 400 (exige orcamento
  minimo maior que zero) — a mitigacao real e garantir espaco suficiente no limite de saida.

### Validacao realizada
- `pytest`: 204 passed. `ruff check`: sem avisos.
- Teste manual ponta-a-ponta via API real com chave Gemini: 3 perguntas sobre documentos
  reais ja indexados, todas com `grounded: true`, sem truncamento, entre 3.0s e 15.2s.
- README atualizado: Gemini agora e o caminho recomendado na secao de pre-requisitos e
  configuracao; Ollama continua documentado como alternativa 100% offline.

## [1.0.5] - 2026-08-03 - Respostas diretas, chat sem citacoes na tela e correcoes de velocidade no Ollama

### Alterado
- **Prompt do agente mais direto** (`SYSTEM_PROMPT`, `app/agents/prompts/templates.py`): nova
  regra proibe explicitamente o modelo de narrar o proprio processo ("De acordo com o
  documento X..." como abertura, "encontrei essa informacao em...") antes de responder.
  A resposta agora vai direto ao ponto; regra de concisao tambem reforcada.
- **Pagina de Chat sem exibicao de fontes** (`frontend/streamlit_app/pages/1_Chat.py`):
  removida a funcao `_render_citation` e todos os pontos de renderizacao de citacoes/fontes
  (tanto no historico replay quanto na resposta nova). A resposta some do aviso de
  "nao fundamentada" continua visivel quando aplicavel.
- **`rewrite_query` deixou de chamar o LLM** (`app/agents/nodes/validation.py`): a reescrita
  de pergunta com base no historico da conversa agora e uma concatenacao heuristica das
  ultimas 2 perguntas do usuario + a pergunta atual, em vez de uma chamada extra ao modelo.
  Remove uma ida-e-volta completa ao LLM por pergunta (relevante em CPU, onde cada chamada
  custa segundos).
- Config de velocidade ajustada: `RERANK_TOP_K` 5->3, `MAX_CONTEXT_CHARS` 6000->3000,
  `LLM_MAX_TOKENS` 2048->500 — menos texto no prompt e na resposta, sem cortar a qualidade
  da resposta para perguntas objetivas.

### Corrigido
- **Bug silencioso no provedor Ollama** (`app/llm/factory.py`): `ChatOllama` nao possui os
  campos `timeout`/`max_tokens` — o pydantic aceita esses nomes via kwargs sem erro (extra
  ignorado) mas eles nunca tinham efeito algum. `LLM_MAX_TOKENS` e `LLM_TIMEOUT_SECONDS`
  configurados no `.env` pareciam funcionar mas nunca limitavam nada. Corrigido usando os
  nomes reais aceitos pelo `ChatOllama`: `num_predict` (limite de tokens) e
  `client_kwargs={"timeout": ...}` (timeout do cliente HTTP). Teste de regressao adicionado
  (`tests/unit/llm/test_factory.py::test_ollama_model_actually_applies_max_tokens_and_keep_alive`).
- **Novo campo `OLLAMA_KEEP_ALIVE`** (padrao `30m`): sem ele, o Ollama descarrega o modelo da
  memoria ~5 min apos o ultimo uso; a proxima chamada paga o custo total de recarregar ~5GB
  do disco. Medido neste ambiente (CPU): ~93s numa chamada fria vs ~8s com o modelo quente.
- **`LLM_TIMEOUT_SECONDS` 60->180**: consequencia direta da correcao acima — antes, o timeout
  configurado era ignorado, entao uma carga fria de +60s passava despercebida. Com o timeout
  passando a valer de verdade, 60s cortava a conexao antes do modelo terminar de carregar; o
  Ollama aborta o carregamento junto quando o cliente desconecta, entao o modelo nunca ficava
  "quente" e a chamada seguinte tambem falhava (loop de timeout). 180s comporta a carga fria
  em CPU com folga; o `keep_alive` evita que isso se repita durante o uso normal.

### Validacao realizada
- `pytest`: 201 passed. `ruff check`: sem avisos.
- Teste manual ponta-a-ponta via API real: chamada fria 93.4s (completa dentro do timeout),
  chamada seguinte (modelo quente) 7.9s.

## [1.0.4] - 2026-08-03 - Upload de multiplos arquivos

### Adicionado
- Pagina **Documentos**: o seletor de arquivo agora aceita multiplos arquivos de uma vez
  (`accept_multiple_files=True`). Categoria/tags/departamento/classificacao se aplicam ao
  lote inteiro. Cada arquivo e enviado e processado individualmente (upload + process em
  sequencia por arquivo, preservando deteccao de duplicata e auto-aprovacao por arquivo), com
  barra de progresso e um resumo detalhado por arquivo (sucesso/duplicata/falha) ao final.

### Validacao realizada
- `ruff check`: sem avisos. Pagina validada de forma headless (`AppTest`) sem sessao e
  autenticada como admin contra a API real — sem excecoes, seletor de arquivo renderizado
  corretamente.

## [1.0.3] - 2026-08-03 - Respostas mais naturais + aprovacao automatica opcional

### Alterado
- **Respostas do agente sem marcadores `[Fonte N]`**: o modelo estava copiando literalmente
  o marcador de colchetes do CONTEXTO para dentro da resposta ("De acordo com [Fonte 1],
  ..."), o que soa artificial. Corrigido em duas pontas:
  - `SYSTEM_PROMPT` (`app/agents/prompts/templates.py`): a regra de citacao agora instrui o
    modelo a mencionar o documento pelo NOME, em linguagem natural ("De acordo com a
    Politica de Reembolso..."), e proibe explicitamente marcadores/colchetes.
  - `build_context` (`app/agents/nodes/retrieval.py`): os blocos de contexto enviados ao
    modelo agora sao rotulados com o nome real do documento ("Documento: X") em vez de
    "[Fonte N]" — o modelo tende a repetir o padrao que ve, entao dar a ele o nome certo
    produz uma citacao natural.
  - `format_citations` (`app/agents/nodes/generation.py`): a filtragem de "fontes realmente
    citadas" (secao 22) agora casa pelo NOME do documento mencionado na resposta, em vez de
    procurar marcadores `[Fonte N]` que deixaram de existir. Fallback inalterado: se nenhum
    nome for reconhecido no texto, mostra todas as fontes candidatas.
  - As fontes completas (documento, pagina, secao, trecho) continuam sendo exibidas
    separadamente na interface — a mudanca afeta apenas o texto da resposta em si.

### Adicionado
- **Aprovacao automatica opcional** (`AUTO_APPROVE_ON_UPLOAD`, secao 8 e 29): quando ativa,
  um documento e aprovado assim que o processamento termina com sucesso, sem esperar um
  clique manual na Curadoria — pensado para testers experimentarem o agente rapido.
  Implementado em `app/ingestion/service.py::_auto_approve`, que chama a MESMA
  `change_document_status` usada pela aprovacao manual (preserva a maquina de estados de
  curadoria e a trilha de auditoria — "seguindo as normas", nao um atalho que pula
  validacoes). Padrao `false` em `.env.example` (producao deve manter curadoria humana);
  ativado (`true`) no `.env` local deste ambiente de teste.

### Validacao realizada
- `pytest`: 199/199 testes passando (2 novos: `test_auto_approve_on_upload_when_enabled`,
  `test_document_stays_pending_when_auto_approve_disabled`), `ruff` limpo.
- Testado contra a API real: upload → processamento → documento ja aparece `approved` sem
  nenhum clique manual, com evento de auditoria registrado.

## [1.0.2] - 2026-08-03 - Melhorias de UX e correcao de mensagem (feedback do usuario)

### Corrigido
- **Mensagem de "sem autorizacao" enganosa para documentos ainda nao aprovados**: um
  documento `pending_review` fazia o chat responder "voce nao possui autorizacao... entre em
  contato com o administrador" — absurdo quando quem pergunta ja e o administrador. Causa
  raiz: `filter_authorized_results` misturava dois motivos de exclusao (nao aprovado vs.
  classificacao de acesso insuficiente) na mesma lista. Corrigido com
  `app.retrieval.permissions.categorize_results`, que separa `pending_approval` de
  `access_denied`; o agente agora usa uma nova rota `pending_approval` com mensagem propria
  ("ainda aguardando revisao da curadoria"). `filter_authorized_results` continua existindo
  como wrapper fino para quem so precisa da lista final autorizada.

### Adicionado (usabilidade para testers, a pedido do usuario)
- Botoes de aprovar/rejeitar direto na lista da pagina **Documentos**, para o fluxo mais
  comum ao testar (enviar → aprovar) sem precisar navegar ate a Curadoria.
- Cache de 60s (`list_categories`) e 15s (`get_metrics_summary`) no frontend Streamlit via
  `st.cache_data` — reduz chamadas HTTP repetidas causadas pelo modelo de execucao do
  Streamlit (o script inteiro reexecuta a cada interacao do usuario).
- `RATE_LIMIT_PER_MINUTE` padrao aumentado de 60 para 300 (`.env.example`, `.env` e o
  default em `app/core/config.py`) — o limite anterior podia ser atingido rapido com varios
  testers clicando na interface. Documentado que producao deve ajustar conforme o volume
  real esperado.

### Validacao realizada
- 3 novos testes (`test_categorize_distinguishes_pending_from_access_denied`,
  `test_categorize_excludes_stale_version_from_every_category`,
  `test_agent_returns_pending_approval_when_document_not_yet_approved`) — 197/197 testes
  passando, `ruff` limpo.
- Validado contra a API real: apos o usuario aprovar o documento pendente via o novo botao
  inline, uma pergunta sobre o conteudo real (politica de ferias de RH) foi respondida
  corretamente pelo `llama3.1` com `grounded: true`, citando a fonte correta.

## [1.0.1] - 2026-08-02 - Validacao final com LLM real (Ollama)

### Validado
- Ollama instalado, configurado e testado de ponta a ponta com o usuario, fechando a
  unica pendencia registrada nas fases anteriores ("LLM real nao testado neste ambiente").
- Pergunta real via API (`POST /chat`) respondida pelo `llama3.1` rodando localmente:
  resposta fundamentada (`grounded: true`), citacao correta (`sample_policy.pdf`, pagina 1,
  trecho exato), `route: continue`.

### Problemas de ambiente encontrados e resolvidos (fora do codigo da aplicacao)
- **Disco C: com 0 GB livres**: impedia o download do modelo (`ollama pull`) e chegou a
  quebrar a escrita de arquivos temporarios do proprio terminal. Identificados e removidos
  ~15 GB de caches seguros (modelos antigos do Ollama ja orfaos apos redirecionamento,
  `AppData\Local\Temp`, cache do npm/pnpm/pip) mediante confirmacao explicita do usuario
  antes de qualquer exclusao.
- **`OLLAMA_MODELS` redirecionado para o drive D:** (`D:\OllamaModels`, 912 GB livres) via
  variavel de ambiente de usuario — evita que modelos futuros voltem a encher o C:.
- **Driver CUDA da GPU falhando** (`CUDA error: shared object initialization failed`,
  estouro de buffer): contornado forcando o Ollama a rodar em CPU
  (`OLLAMA_NUM_GPU=0`/`CUDA_VISIBLE_DEVICES=-1`). Mais lento (~80s para uma pergunta curta),
  mas funcional. Investigar o driver NVIDIA/CUDA fica como melhoria futura opcional para
  respostas mais rapidas.

## [1.0.0] - 2026-08-02 - Fase 9: Documentacao e empacotamento

### Adicionado
- `README.md` completo: resumo, problema resolvido, funcionalidades, arquitetura (diagramas
  Mermaid do pipeline de ingestao e do grafo do agente), tecnologias com versoes testadas,
  formatos suportados, estrutura de pastas, pre-requisitos, instalacao (Windows/Linux/macOS),
  configuracao, escolha e troca de provedor de LLM/embeddings/banco vetorial, execucao local
  e via Docker, uso (ingestao/chat/curadoria/reindexacao), testes, avaliacao do RAG, tabela
  de solucao de problemas, checklist de seguranca, limitacoes conhecidas, roadmap, exemplos
  de pergunta/resposta (com aviso de dados ficticios), exemplos por tipo de empresa, e guias
  de extensao (novo formato de documento, novo banco vetorial, novo provedor).
- `Dockerfile`: imagem unica (Python 3.12-slim + Tesseract/Poppler para OCR opcional) usada
  tanto pela API quanto pelo frontend, com healthcheck e migrations/seed automaticos no boot.
- `docker-compose.yml`: servicos `api` + `frontend` (com `API_BASE_URL` apontando para o
  nome do servico da API na rede interna) + servico opcional `ollama` via profile.
- `.dockerignore`: garante que `.env` e segredos nunca entrem na imagem.
- `Makefile`: atalhos (`install`, `migrate`, `seed`, `run-api`, `run-frontend`, `test`,
  `test-cov`, `lint`, `evaluate`, `docker-up/down`) assumindo o venv ja ativado — funciona
  identico em Windows/Linux/macOS sem depender de caminhos `bin/`/`Scripts/` especificos do
  SO.

### Correcao
- **`frontend/streamlit_app/api_client.py` nao respeitava variaveis de ambiente reais**,
  apenas o conteudo do arquivo `.env` (via `dotenv_values`). Isso quebraria o Docker Compose,
  onde o servico do frontend recebe `API_BASE_URL=http://api:8000` como variavel de
  ambiente real (nao um arquivo `.env` diferente) para alcancar o backend pelo nome do
  servico na rede interna. Corrigido para `os.environ` ter prioridade sobre o `.env`.

### Validacao realizada
- `pytest`: 194/194 testes passando. `ruff check`: sem avisos.
- Todos os numeros citados no README (contagem de testes, cobertura) conferidos contra a
  execucao real da suite antes de publicar.
- API real reiniciada uma ultima vez para confirmar `/health`, `/docs` (Swagger UI) e
  `/openapi.json` respondendo HTTP 200.
- `docker-compose.yml` validado sintaticamente (parser YAML) — build completa da imagem
  **nao** executada neste ambiente (Docker indisponivel); documentado como limitacao
  conhecida no README.

## [0.9.0] - 2026-08-02 - Fase 8: Qualidade (seguranca, cobertura, avaliacao do RAG)

### Adicionado
- `tests/conftest.py`: fixtures compartilhados (`db_session`, `vector_repository`,
  `embedding_provider`, `reranker`, `test_settings`, `api_client`) movidos para a raiz da
  suite, disponiveis agora tambem para `tests/security/`. `tests/helpers.py` centraliza
  `create_user`/`auth_headers` reutilizados pelos testes de API.
- `tests/security/test_upload_security.py`: arquivo disfarcado (assinatura falsa), extensao
  nao suportada, path traversal no nome, arquivo vazio, nome de arquivo malicioso nunca
  reutilizado no disco.
- `tests/security/test_auth_and_permissions.py`: token JWT adulterado, header malformado,
  ausencia de token, varredura parametrizada de todos os endpoints restritos a
  curador/admin e admin, isolamento de documento confidencial no chat (usuario comum nunca
  recebe citacao nem trecho de um documento confidencial; curador recebe normalmente).
- `tests/security/test_prompt_injection.py`: 4 padroes de ataque distintos via documento
  (revelacao de chave, role-play, exfiltracao, override de contexto), pergunta maliciosa vinda
  do proprio usuario, verificacao estatica de que o prompt de sistema nunca contem segredos
  reais e que o contexto do documento fica sempre dentro do bloco delimitado `CONTEXTO:`.
- `tests/security/test_rate_limiting.py`: confirma HTTP 429 com formato de erro padrao apos
  exceder o limite configurado.
- Testes de cobertura para troca de provedor: `tests/unit/llm/test_factory.py` (Anthropic/
  OpenAI/Ollama), `tests/unit/reranking/test_factory.py` (fallback automatico para
  heuristica), `tests/unit/embeddings/test_ollama_provider.py` e `test_openai_provider.py`
  (traducao de erro de conexao/config ausente).
- `scripts/evaluate_rag.py` + `tests/fixtures/rag_eval_dataset.json` (secao 34): ingere os
  documentos ficticios em um ambiente isolado (banco e indice vetorial temporarios, nunca
  toca os dados reais), executa cada pergunta pelo agente RAG completo e classifica cada
  resposta como `correct` / `partially_correct` / `incorrect` / `no_evidence` /
  `wrong_source`. Reporta taxa de fundamentacao, taxa de citacao, latencia media; documenta
  que tokens e satisfacao dependem de instrumentacao do provedor real e do feedback de
  producao, respectivamente. Suporta `--fake` para validar o proprio script sem LLM real.
  `tests/unit/test_evaluate_rag_classification.py` cobre a logica de classificacao.

### Bugs reais encontrados e corrigidos
- **Rate limiter derrubava a requisicao com erro nao tratado em vez de HTTP 429**: excecoes
  levantadas dentro de um middleware `BaseHTTPMiddleware` (`add_middleware`) rodam FORA da
  camada que o FastAPI usa para `@app.exception_handler` — o `RateLimitExceededError` nunca
  era convertido em resposta JSON, propagando como erro 500 nao tratado. Corrigido para
  `RateLimitMiddleware` construir a `JSONResponse` diretamente. Encontrado escrevendo o teste
  de seguranca para o proprio limitador — nao havia sido exercitado antes.
- **`scripts/evaluate_rag.py` falhava ao limpar o diretorio temporario no Windows**: o Chroma
  mantem um handle aberto sobre o arquivo do indice HNSW que o coletor de lixo do Python nao
  libera a tempo da limpeza automatica do `tempfile.TemporaryDirectory`, causando
  `PermissionError`. Corrigido com `ignore_cleanup_errors=True`.

### Validacao realizada
- `pytest`: 194/194 testes passando (147 unitarios + 47 de integracao/seguranca).
- `ruff check` (app, tests, scripts, frontend): sem avisos.
- Cobertura de `app/`: 92% (subiu de 90% no fim da Fase 7).
- `scripts/evaluate_rag.py --fake`: executado com sucesso, validando a estrutura do script
  (ingestao dos 8 formatos, classificacao, resumo) sem depender de um LLM real.
- Auditoria manual do checklist de seguranca da secao 29: nenhuma chamada de log inclui
  texto completo de documento, resposta ou contexto (apenas metadados/IDs/contagens).

### Pendente
- Avaliacao do RAG com um provedor de LLM real (Ollama/Anthropic/OpenAI) continua pendente
  pela mesma razao das fases anteriores — nenhum provedor real disponivel neste ambiente.
- "Controle de timeout" (secao 29) esta implementado no nivel de cada chamada ao provedor de
  LLM (`LLM_TIMEOUT_SECONDS`), mas nao ha um timeout generico de requisicao HTTP na API —
  decisao consciente para nao interromper prematuramente uploads/processamentos legitimos de
  documentos grandes. Documentado como limitacao conhecida.

## [0.8.0] - 2026-08-02 - Fase 7: Interface Streamlit

### Adicionado
- `frontend/streamlit_app/api_client.py`: cliente HTTP fino sobre a API — a interface nunca
  acessa o banco de dados diretamente (secao 27). Le `API_BASE_URL` do `.env` da raiz do
  projeto via `python-dotenv`.
- `frontend/streamlit_app/auth.py`: formulario de login, guarda `require_login()` usada no
  topo de toda pagina, badge do usuario logado e botao de logout.
- `frontend/streamlit_app/app.py`: pagina inicial com identificacao clara de que se trata de
  um agente de IA (secao 26) e navegacao para as demais paginas.
- `frontend/streamlit_app/pages/1_Chat.py`: chat com historico de sessao, filtro por
  categoria, indicador de processamento, aviso quando a resposta pode nao estar fundamentada,
  fontes expansiveis mostrando o trecho utilizado, feedback positivo/negativo por resposta e
  botao para limpar conversa.
- `frontend/streamlit_app/pages/2_Documentos.py`: upload com categoria/tags/departamento/
  classificacao de acesso, processamento imediato apos upload, listagem com filtros por
  status e categoria.
- `frontend/streamlit_app/pages/3_Curadoria.py`: abas por status (pendente, aprovado,
  rejeitado, duplicata, arquivado) com acoes de aprovar/rejeitar/reindexar/arquivar
  *(curador/admin)*.
- `frontend/streamlit_app/pages/4_Configuracoes.py`: parametros efetivos do sistema, somente
  leitura *(admin)* — nenhuma chave secreta exibida.
- `frontend/streamlit_app/pages/5_Painel.py`: metricas basicas (documentos por status/
  categoria, perguntas realizadas, respostas sem evidencia, feedback) *(curador/admin)*.
- Backend: `GET /config` (admin, somente leitura) alimenta a pagina de Configuracoes.
- 6 novos testes automatizados (`tests/integration/test_streamlit_pages.py`) usando o
  framework oficial `streamlit.testing.v1.AppTest` — carregam cada pagina de forma headless
  e falham se houver qualquer excecao Python, sem precisar de navegador.

### Correcoes encontradas durante a validacao manual
- **`app.py` nao importava `auth`/`api_client`**: faltava adicionar o diretorio do proprio
  script ao `sys.path` (diferente das paginas em `pages/`, que precisam apontar para o
  diretorio *pai*). Descoberto pelo teste headless com `AppTest`, nao por inspecao visual —
  por isso o teste foi mantido como regressao automatizada.
- **Mensagem de erro do provedor de LLM nao traduzida em portugues no Windows**:
  `translate_llm_error` dependia de correspondencia de texto em ingles ("connection",
  "refused"), mas o Windows localizado em portugues gera "[WinError 10061]... recusou
  ativamente" — a palavra em ingles nunca aparece. Corrigido para checar o TIPO da excecao
  (`httpx.ConnectError`, `ConnectionError`, `httpx.TimeoutException`) primeiro, com a
  correspondencia textual como fallback. Descoberto testando o chat de ponta a ponta contra a
  API real (sem Ollama instalado) — o usuario veria um erro tecnico em vez da mensagem clara
  exigida pela secao 41. Teste de regressao dedicado em `tests/unit/llm/test_errors.py`.
- **Citacoes sem o trecho de texto e resposta do chat sem `message_id`**: a secao 22 exige
  que o usuario consiga "expandir a fonte e visualizar o trecho utilizado", e o feedback por
  resposta (secao 26/31) exige um identificador da mensagem. Adicionado `snippet` a
  `Citation` (populado em `build_context`) e `message_id` propagado de
  `persistence.py` -> `AgentState` -> `AskResult` -> `ChatResponse`.

### Validacao realizada
- `pytest`: 144/144 testes passando (105 unitarios + 39 de integracao).
- `ruff check` (incluindo `frontend/`): sem avisos.
- **Validacao manual de ponta a ponta com a stack real rodando** (nao apenas testes
  automatizados): API real (`uvicorn`) + Streamlit real, login com o admin seedado, upload
  -> processamento -> aprovacao de um PDF real, pergunta respondida com citacoes corretas
  (incluindo o trecho exato), e o caminho de erro de provedor (Ollama ausente) confirmado
  gerando mensagem limpa em vez de traceback. Ambiente de dev limpo apos os testes (banco e
  arquivos de upload de teste removidos, `alembic upgrade head` + seed do admin reexecutados).

### Pendente
- Teste manual do chat com um LLM de verdade (Ollama/Anthropic/OpenAI) continua pendente —
  confirmado apenas o caminho de erro gracioso quando o provedor esta indisponivel. Requer
  que o usuario instale o Ollama (ou configure uma chave) localmente.
- Pagina de Configuracoes e somente leitura (edicao em runtime nao implementada — mudar
  parametros exige editar o `.env` e reiniciar); decisao documentada para nao simular uma
  funcionalidade de escrita que nao persiste de verdade.

## [0.7.0] - 2026-08-02 - Fase 6: API (FastAPI)

### Adicionado
- `app/ingestion/service.py` refatorado: `register_document` (valida, salva e cria os
  registros, sem processar) separado de `process_document_version` (roda o grafo de
  ingestao) — necessario porque a interface (secao 26) tem upload e "processar" como acoes
  distintas. `ingest_new_document` continua existindo como composicao sincrona das duas
  (usada por scripts/pasta monitorada/testes existentes, sem quebrar nada da Fase 3).
  Adicionado tambem `reindex_document` e o helper `resolve_version_to_process`.
- `app/services/`: `auth_service.py` (autenticacao, emissao de JWT, criacao de usuario),
  `curation_service.py` (transicoes de status com trilha de auditoria via `AuditEvent` e
  remocao dos vetores do indice sempre que um documento deixa de estar `APPROVED`;
  `delete_document` = exclusao logica/arquivamento + limpeza do indice, nunca apaga o
  registro do banco), `metrics_service.py` (agregacoes para o painel administrativo).
- `app/api/dependencies/`: `db.py` (sessao por requisicao), `auth.py` (`get_current_user`,
  `require_roles`, com `require_curator_or_admin`/`require_admin` prontos), `providers.py`
  (LLM/embeddings/vetor/reranker como dependencias sobrescreviveis em teste).
- `app/api/middleware.py`: correlation ID por requisicao e limitador de requisicoes por IP
  (janela deslizante em memoria, secao 29).
- `app/schemas/api/`: schemas de requisicao/resposta tipados para auth, documentos,
  categorias, chat e feedback/metricas — nunca os modelos SQLModel diretamente na API.
- `app/api/routes/`: `health`, `auth` (login + `/me` + gerenciamento de usuarios pelo
  admin), `documents` (upload, listagem, detalhe, processar, aprovar, rejeitar, reindexar,
  excluir), `categories`, `chat` (perguntar, listar sessoes, listar mensagens), `feedback`,
  `metrics`. Endpoints batem com a lista da secao 39, mais os endpoints de autenticacao
  essenciais para o RBAC funcionar (nao listados explicitamente na secao 39, mas exigidos
  pela secao 10).
- `app/api/main.py`: monta a aplicacao, CORS, tratador de excecao global (`AppError` ->
  JSON com `error_code`/`message`, nunca traceback), documentacao automatica via OpenAPI
  (`/docs`, `/redoc`).
- 12 novos testes de integracao ponta-a-ponta via `TestClient` (login, RBAC nos 3 papeis,
  fluxo completo upload -> processar -> aprovar, chat -> feedback, 404/403 corretos).

### Decisoes tecnicas
- **Autenticacao JWT com bearer token** (`python-jose`), papeis `user`/`curator`/`admin`
  aplicados via dependencia FastAPI reutilizavel — suposicao assumida na Fase 0 (o prompt
  mestre nao especifica o mecanismo de autenticacao), documentada desde entao.
- **Exclusao de documento = arquivamento + limpeza do indice vetorial**, nunca `DELETE` no
  banco relacional: preserva historico/auditoria (secao 29: "nao exclua documentos
  automaticamente sem registro") enquanto garante que o documento excluido nunca mais
  aparece em uma resposta (vetores removidos imediatamente).
- **Todas as excecoes de dominio (`AppError`) tratadas por um unico handler global**:tanto
  as dependencias de autenticacao/permissao quanto os servicos internos levantam
  `AppError`, garantindo formato de erro uniforme (`error_code` + `message`, nunca
  traceback) em toda a API, sem duplicar tratamento por rota.

### Validacao realizada
- `pytest`: 131/131 testes passando (98 unitarios + 33 de integracao).
- `ruff check`: sem avisos.
- Servidor real iniciado com `uvicorn app.api.main:app` (nao apenas `TestClient`): `/health`
  respondeu `{"status":"ok"}` e `/docs` (Swagger UI) respondeu HTTP 200.

### Pendente
- Nenhuma pendencia bloqueante para a Fase 7 (interface Streamlit), que vai consumir esta
  API exclusivamente via HTTP.

## [0.6.0] - 2026-08-02 - Fase 5: Agente RAG (LangGraph)

### Adicionado
- `app/llm/factory.py`: selecao do modelo de chat (`ChatAnthropic`/`ChatOpenAI`/`ChatOllama`)
  por `LLM_PROVIDER`. Nao existe uma interface propria de LLM — o `BaseChatModel` do LangChain
  ja e a camada de abstracao exigida (secao 3): todo no do agente chama `.invoke(messages)`
  da mesma forma, independente do provedor.
- `app/llm/errors.py`: traduz erros de conexao/timeout/autenticacao do provedor em excecoes
  de dominio com mensagem clara (secao 41 — "erro de provedor" nunca deve virar traceback).
- `app/agents/state.py`: `AgentState` (estado tipado do grafo) e `Citation`/`ChatTurn`.
- `app/agents/prompts/templates.py`: prompt de sistema com as 9 regras anti-prompt-injection
  da secao 30 (documento = dado, nunca comando) e mensagens padronizadas para cada desvio
  (sem evidencia, acesso negado, pergunta invalida, fora de escopo, solicitacao administrativa,
  pedido de ingestao).
- `app/agents/nodes/`: `validation.py` (valida pergunta, detecta intencao por heuristica sem
  custo de LLM, reescreve consulta usando o LLM somente quando ha historico, determina
  filtros), `retrieval.py` (permissoes por papel, busca vetorial/lexical, fusao, reranking,
  validacao de evidencia, montagem de contexto com citacoes) — reaproveita integralmente as
  primitivas da Fase 4 sem duplicar logica — e `generation.py` (geracao da resposta,
  deteccao heuristica de conflito, verificacao de fundamentacao por sobreposicao lexical,
  filtragem de citacoes para exibir so as fontes realmente referenciadas na resposta) e
  `persistence.py` (grava pergunta/resposta no historico, com mensagens padronizadas quando
  o fluxo termina antes de gerar uma resposta real).
- `app/agents/graph.py`: grafo completo da secao 24 (`validate_question -> identify_intent ->
  rewrite_query -> determine_filters -> check_permissions -> retrieve_candidates ->
  lexical_search -> merge_results -> rerank_results -> validate_evidence -> build_context ->
  generate_answer -> verify_grounding -> format_citations -> save_interaction`), com desvio
  direto para `save_interaction` em qualquer ramificacao de saida antecipada.
- `app/agents/service.py`: `ask_question(...)`, ponto de entrada usado pela API (Fase 6) —
  garante a sessao de chat, carrega historico recente (nao ilimitado) e invoca o grafo.
- 29 novos testes: 24 unitarios (nos individuais com `FakeListChatModel` do LangChain, sem
  chamar nenhum provedor real) e 5 de integracao ponta-a-ponta (resposta fundamentada com
  citacao real, ausencia de evidencia, pergunta invalida, saudacao fora de escopo, e um teste
  dedicado que ingere um documento com um ataque de prompt injection e comprova que o texto
  malicioso permanece isolado dentro do bloco CONTEXTO, nunca influenciando o comportamento
  do pipeline).

### Decisoes tecnicas
- **Deteccao de intencao por heuristica de palavras-chave, nao por chamada ao LLM**: evita uma
  chamada cara a cada pergunta so para classificar (secao 42 — otimizacao de custos). Reescrita
  de consulta (`rewrite_query`) usa o LLM, mas apenas quando ha historico de conversa —
  perguntas de abertura pulam essa chamada.
- **Verificacao de fundamentacao (`verify_grounding`) e heuristica best-effort** (sobreposicao
  lexical resposta/contexto), documentada como tal: nao substitui um classificador de
  entailment real, mas sinaliza ao usuario quando a resposta parece pouco ancorada nos
  documentos, sem bloquear a resposta (o usuario ve o sinal, decide a confianca).
- **Citacoes finais filtradas pelos marcadores `[Fonte N]` presentes na resposta**: exibe as
  fontes que o modelo de fato citou, nao todas as fontes candidatas fornecidas como contexto
  (secao 22 — "fontes utilizadas").
- **Protecao contra prompt injection e estrutural, nao apenas uma instrucao no prompt**: o
  conteudo de documentos so entra na mensagem do usuario dentro do bloco literal `CONTEXTO:`
  (`build_user_message`); nenhuma parte do pipeline reinterpreta ou executa o texto do
  documento como instrucao de sistema. O teste de integracao dedicado comprova isso na pratica
  com um documento contendo um ataque real.

### Validacao realizada
- `pytest`: 119/119 testes passando (98 unitarios + 21 de integracao).
- `ruff check`: sem avisos.
- Testes de integracao usam `FakeListChatModel` (utilitario oficial do LangChain) para
  determinismo, mas com busca vetorial, lexical, fusao, permissoes e reranking REAIS.

### Pendente
- **Ollama nao esta instalado neste ambiente de desenvolvimento** — a integracao com o
  provedor de LLM real (`app/llm/factory.py`, `ChatOllama`) nao foi testada ponta-a-ponta
  com um modelo de verdade, apenas com o `FakeListChatModel` do LangChain. A arquitetura de
  troca de provedor (`LLM_PROVIDER=anthropic|openai|ollama`) esta implementada e pronta;
  falta apenas a validacao manual do usuario apos instalar o Ollama (ou configurar uma chave
  Anthropic/OpenAI) localmente.
- Nenhuma pendencia bloqueante para a Fase 6 (API).

## [0.5.0] - 2026-08-02 - Fase 4: Recuperacao hibrida e reranking

### Adicionado
- `app/retrieval/vector_search.py`: busca semantica (embed da pergunta + consulta ao Chroma).
- `app/retrieval/lexical_search.py`: busca lexical via BM25 (`rank_bm25`) sobre os chunks do
  SQLite — importante para numeros, codigos, identificadores e termos exatos que a busca
  semantica pode nao priorizar (secao 18).
- `app/retrieval/fusion.py`: fusao Reciprocal Rank Fusion (RRF, padrao) e soma ponderada
  normalizada (alternativa), selecionavel por `HYBRID_FUSION_STRATEGY`.
- `app/retrieval/permissions.py`: filtro de autorizacao/curadoria pos-recuperacao — mantem
  apenas chunks de documentos `APPROVED`, dentro da classificacao de acesso permitida, e
  pertencentes a versao ativa do documento.
- `app/reranking/`: `BaseReranker` + `CrossEncoderReranker` (padrao,
  `cross-encoder/ms-marco-MiniLM-L-6-v2`, score normalizado via sigmoid) +
  `HeuristicReranker` (fallback sem modelo: similaridade + sobreposicao lexical + selo de
  documento oficial) + `factory.py` com downgrade automatico para heuristica caso o
  CrossEncoder nao possa ser carregado.
- `app/retrieval/hybrid_search.py`: orquestra o fluxo completo — vetorial + lexical -> fusao
  -> permissoes -> reranking -> top-k final.
- 16 novos testes (5 de fusao, 4 do reranker heuristico, 4 de permissoes com banco real, 3 de
  busca hibrida ponta-a-ponta com ingestao + reranking reais).

### Decisoes tecnicas
- **Permissoes verificadas contra o banco relacional, nunca contra os metadados gravados no
  vetor no momento da indexacao**: o status de curadoria de um documento muda depois da
  ingestao (aprovacao/rejeicao), mas o Chroma nao e resincronizado a cada mudanca. Confiar no
  metadado do vetor para "somente documentos aprovados" (secao 8) permitiria vazar documentos
  ja aprovados apos terem sido rejeitados, ou o inverso. A checagem sempre consulta o SQLite
  (fonte da verdade) apos a fusao, antes do reranking.
- **BM25 construido sob demanda a partir do SQLite**: suficiente para o volume esperado da
  primeira versao; documentado como ponto de otimizacao futura (indice persistente) caso o
  corpus cresca muito.

### Validacao realizada
- `pytest`: 90/90 testes passando (79 unitarios + 11 de integracao, incluindo busca hibrida
  real com CrossEncoder de verdade sobre documentos realmente ingeridos).
- `ruff check`: sem avisos.

### Pendente
- Nenhuma pendencia bloqueante para a Fase 5. A geracao de respostas do LLM ainda nao existe
  — a Fase 4 entrega apenas os chunks recuperados e reranqueados.

## [0.4.0] - 2026-08-02 - Fase 3: Embeddings, banco vetorial e pipeline de ingestao

### Adicionado
- `app/embeddings/`: `BaseEmbeddingProvider` + 3 implementacoes
  (`sentence_transformer_provider.py` local/padrao com prefixos automaticos "query:"/"passage:"
  para modelos E5, `openai_provider.py`, `ollama_provider.py`) e `factory.py` selecionando por
  `EMBEDDING_PROVIDER`.
- `app/vectorstores/`: `VectorRepository` (interface) + `chroma_repository.py` (Chroma
  persistente local, espaco de similaridade cosseno) + `factory.py`.
- `app/ingestion/`: `state.py` (estado tipado do grafo), `nodes.py` (etapas do pipeline com
  log de cada estagio e conversao de erro de dominio em roteamento, nao excecao), `pipeline.py`
  (grafo LangGraph: validacao -> extracao -> limpeza -> chunking -> validacao de qualidade ->
  embeddings/indexacao vetorial -> finalizacao, com desvio para `finalize_failure` em qualquer
  etapa) e `service.py` (`ingest_new_document`, `reingest_document_version`).
- Deteccao de duplicata exata (hash do arquivo) acontece ANTES de criar qualquer registro no
  banco, evitando documentos orfaos.
- `reingest_document_version`: cria nova versao preservando o historico da anterior no banco
  relacional, mas remove os vetores da versao antiga do indice apos a nova ser indexada com
  sucesso — nunca mistura chunks antigos e novos numa consulta (secao 40).
- 5 testes de integracao ponta-a-ponta (`tests/integration/test_ingestion_pipeline.py`):
  ingestao completa com indexacao real no Chroma, status padrao "pendente de revisao",
  deduplicacao exata, falha graciosa sem derrubar o processo, e reingestao com remocao dos
  vetores antigos.

### Decisoes tecnicas
- **Sessao de banco via closure, nao via estado do grafo**: o `Session` do SQLModel e vinculado
  aos nos do LangGraph por `functools.partial` na construcao do grafo, em vez de viajar dentro
  do `IngestionState` (TypedDict). O grafo roda inteiramente em memoria (sem checkpointer
  persistente), entao nao ha necessidade de o estado ser serializavel.
- **Documento/Versao sao criados no banco ANTES do grafo rodar**: permite registrar o erro
  (`DocumentVersion.error_message`, `index_status=FAILED`) mesmo quando a extracao falha,
  em vez de o documento simplesmente desaparecer sem rastro.
- **Espaco de similaridade cosseno no Chroma** (`hnsw:space: cosine`): `score = 1 - distancia`
  funciona diretamente como similaridade, independente da normalizacao do modelo de embedding.

### Validacao realizada
- Modelo de embedding padrao (`intfloat/multilingual-e5-base`, dimensao 768) baixado e
  validado localmente.
- `pytest`: 74/74 testes passando (69 unitarios + 5 de integracao com ingestao real).
- `ruff check`: sem avisos.

### Pendente
- Nenhuma pendencia bloqueante para a Fase 4. A busca em si (vetorial/lexical/reranking) ainda
  nao existe — apenas a indexacao. Sera implementada na Fase 4.

## [0.3.0] - 2026-08-02 - Fase 2: Processamento (limpeza, chunking, metadados, curadoria)

### Adicionado
- `app/documents/cleaners/text_cleaner.py`: limpeza configuravel (espacos duplicados,
  caracteres de controle, numeracao de pagina isolada, normalizacao Unicode NFC),
  preservando texto original + relatorio de transformacoes.
- `app/documents/cleaners/document_cleaner.py`: deteccao e remocao de cabecalhos/rodapes
  repetidos entre paginas (heuristica: linha repetida como primeira/ultima linha em >=60%
  das paginas, com minimo de 3 paginas para evitar falso positivo).
- `app/documents/chunkers/hybrid_chunker.py`: chunking hibrido — unidades atomicas (linha de
  planilha/CSV, slide, tabela, campo JSON) nunca se mesclam; blocos de prosa (paragrafos,
  titulos) se agrupam pelo mesmo contexto ate `CHUNK_SIZE`; divisao por tamanho
  (`langchain-text-splitters`, `RecursiveCharacterTextSplitter`) e usada apenas como ultimo
  recurso, com overlap configuravel, quando uma unidade excede `MAX_CHUNK_SIZE`.
- `app/documents/metadata/chunk_metadata.py`: monta o dict de metadados achatado (somente
  escalares, sem `None`) enviado ao banco vetorial junto de cada chunk.
- `app/documents/validators/hashing.py`: hash do arquivo bruto (duplicata exata) e hash do
  conteudo normalizado (duplicata apos reenvio/reexportacao).
- `app/documents/validators/duplicates.py`: similaridade textual (`difflib`) como fallback
  para quase-duplicatas, sem dependencia paga.
- `app/documents/validators/curation.py`: maquina de estados da curadoria
  (`PENDING_REVIEW -> APPROVED/REJECTED/DUPLICATE -> OUTDATED/REPLACED/ARCHIVED`, etc.),
  com excecao dedicada `InvalidCurationTransitionError` para transicoes nao permitidas.
- 28 novos testes unitarios cobrindo limpeza, deduplicacao de cabecalho/rodape, chunking
  (agrupamento, atomicidade, overlap, indexacao sequencial), metadados, hashing, similaridade
  e transicoes de curadoria.

### Decisoes tecnicas
- **Divisao por tamanho via `langchain-text-splitters`** (nova dependencia, ja no ecossistema
  LangChain exigido pelo prompt mestre): reimplementar um splitter recursivo por conta propria
  seria redundante e mais propenso a erros; o pacote oficial ja resolve paragrafo → sentenca →
  caractere com overlap. Um teto rigido adicional (`MAX_CHUNK_SIZE`) e aplicado por cima, pois
  o splitter trata `chunk_size` como alvo, nao limite absoluto.
- **Overlap aplicado somente na divisao por tamanho**, nao entre chunks de contexto diferente
  (mudanca de secao/titulo): overlap existe para nao cortar uma ideia no meio; entre secoes
  distintas ja ha uma fronteira natural, entao duplicar texto ali so adicionaria ruido.

### Validacao realizada
- `pytest`: 69/69 testes passando (16 Fase 0 + 25 Fase 1 + 28 Fase 2).
- `ruff check`: sem avisos.

### Pendente
- Nenhuma pendencia bloqueante para a Fase 3.

## [0.2.0] - 2026-08-02 - Fase 1: Carregadores de documentos

### Adicionado
- `app/schemas/document.py`: `DocumentSection` e `ExtractedDocument`, o contrato padronizado
  de saida de qualquer carregador (independente do formato de origem).
- `app/documents/loaders/base.py`: interface `DocumentLoader` (`supports`/`load`).
- 8 carregadores completos, um por formato exigido na secao 5 do prompt mestre:
  `pdf_loader.py` (PyMuPDF, preserva pagina, deteccao de OCR sob demanda),
  `word_loader.py` (python-docx, preserva ordem de paragrafos/listas/tabelas via
  iteracao do corpo XML), `excel_loader.py` (openpyxl, uma secao legivel por linha),
  `powerpoint_loader.py` (python-pptx, titulo/conteudo/tabelas/notas por slide),
  `markdown_loader.py` (parser proprio preservando hierarquia de titulos `H1 > H2`),
  `csv_loader.py` (pandas, deteccao de separador e encoding com fallback),
  `json_loader.py` (percorre caminhos aninhados, agrupa dicionarios "flat" como registro),
  `html_loader.py` (BeautifulSoup, remove script/style/nav/header/footer/aside).
- `app/documents/loaders/ocr.py`: OCR opcional (pytesseract + pdf2image), desativavel por
  `.env`, com deteccao de indisponibilidade do Tesseract/Poppler sem derrubar o pipeline.
- `app/documents/loaders/registry.py`: despacho por extensao, extensivel sem alterar
  nenhum outro ponto do sistema.
- `tests/fixtures/generate_fixtures.py` + `tests/fixtures/documents/`: documentos ficticios
  pequenos para os 8 formatos, incluindo um PDF "escaneado" (sem texto) e arquivos
  corrompidos/vazios para testar os caminhos de erro.
- 25 novos testes unitarios (`tests/unit/documents/`) cobrindo extracao, preservacao de
  pagina/slide/linha/planilha, hierarquia de secoes e tratamento de arquivos invalidos.

### Decisoes tecnicas
- **OCR nao testado neste ambiente**: Tesseract/Poppler nao estao instalados na maquina de
  desenvolvimento. O carregador de PDF detecta a auséncia e gera um aviso
  (`ocr_needed_but_disabled`) em vez de falhar — validado pelo teste do PDF "escaneado".
- **JSON**: dicionarios cujos valores sao todos escalares viram uma unica secao (como uma
  linha de planilha); campos aninhados isolados preservam o caminho completo
  (`planos.profissional.preco`), conforme o exemplo do prompt mestre.

### Validacao realizada
- `pytest`: 41/41 testes passando (16 da Fase 0 + 25 da Fase 1).
- `ruff check`: sem avisos.

### Pendente
- OCR de fato (ponta-a-ponta) permanece nao testado ate haver Tesseract/Poppler instalados.

## [0.1.0] - 2026-08-02 - Fase 0: Base do projeto

### Adicionado
- Estrutura completa de pastas do projeto (`app/`, `frontend/`, `tests/`, `data/`, `scripts/`, `docs/`).
- `pyproject.toml` e `requirements.txt` com versoes pesquisadas e compativeis (LangChain 1.3,
  LangGraph 1.2, FastAPI 0.124, Chroma 1.5, sentence-transformers 3.4, Python 3.13).
- `app/core/config.py`: configuracao tipada (Pydantic Settings) com validacao explicita de
  credenciais obrigatorias por provedor selecionado.
- `app/core/logging.py`: logging estruturado (structlog) com correlation ID por requisicao e
  redacao automatica de campos sensiveis.
- `app/core/exceptions.py`: hierarquia de excecoes de dominio com `error_code`/`status_code`.
- `app/core/security.py`: hashing de senha (bcrypt direto), JWT, nome de arquivo seguro,
  bloqueio de path traversal e validacao de upload (extensao + tamanho + assinatura de conteudo).
- Modelos de banco (SQLModel): `User`, `Category`, `Responsible`, `Document`, `DocumentVersion`,
  `DocumentChunk`, `DocumentAccessGrant`, `EmbeddingIndexVersion`, `ChatSession`, `ChatMessage`,
  `Feedback`, `IngestionLog`, `AuditEvent`, `AppConfigurationEntry`.
- Alembic configurado (`app/database/migrations`), migration inicial `11f738c7cae7` aplicada.
- `scripts/seed_admin.py`: cria o usuario administrador a partir do `.env`.
- `.env.example` completo e `.gitignore` cobrindo segredos, dados e caches.
- Testes unitarios de configuracao e seguranca (`tests/unit/core/`) — 16 testes.

### Decisoes tecnicas
- **chromadb fixado em `>=1.0,<2.0`**: a serie `0.5.x` depende de `chroma-hnswlib`, que nao
  possui wheel pre-compilada para Python 3.13 no Windows e exige Visual Studio Build Tools. A
  serie `1.x` reescreveu o nucleo em Rust e publica wheels prontas — evita dependencia de
  ferramentas de compilacao no ambiente do usuario.
- **Autenticacao de senha migrada de `passlib` para `bcrypt` direto**: `passlib` (sem release
  desde 2020) e incompativel com `bcrypt>=4.1` (erro `module 'bcrypt' has no attribute
  '__about__'`). Chamado direto de `bcrypt.hashpw`/`checkpw` remove a dependencia quebrada.
- **`Document.active_version_id` sem constraint de FK**: evita ciclo de chave estrangeira com
  `DocumentVersion.document_id` (um documento so aponta para sua versao ativa depois que ela
  existe). A referencia continua indexada, apenas sem `ForeignKeyConstraint` no schema.

### Validacao realizada
- `pip install -r requirements.txt`: sucesso, 0 erros.
- `alembic upgrade head`: schema criado sem erros.
- `python scripts/seed_admin.py`: usuario admin criado.
- `pytest tests/unit/core`: 16/16 testes passando.
- `ruff check app scripts tests`: sem avisos.

### Pendente
- Ollama nao esta instalado no ambiente local (sera necessario para testar o LLM na Fase 5).
- Nenhuma pendencia bloqueante para a Fase 1.
