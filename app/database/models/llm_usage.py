"""Cache de respostas e contagem diaria de chamadas ao provedor de LLM.

Duas defesas adicionais de cota, complementares ao `LlmCallLimiter` (janela
por minuto, em memoria, ver `app/llm/rate_limiter.py`):

- `AnswerCache`: evita uma chamada inteira ao provedor quando a MESMA
  pergunta (normalizada) e feita de novo sobre o MESMO contexto ja
  recuperado. A chave inclui o texto do contexto, entao se o conteudo dos
  documentos mudar (nova versao, reindexacao), a chave muda junto e a
  resposta antiga nunca e reaproveitada por engano.
- `LlmDailyUsage`: contador persistido (sobrevive a reinicios do processo,
  diferente do limitador por minuto) do teto DIARIO de requisicoes do plano
  gratuito do provedor.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


class AnswerCache(SQLModel, table=True):
    __tablename__ = "answer_cache"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    cache_key: str = Field(index=True)
    answer: str
    route: str
    model_used: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LlmDailyUsage(SQLModel, table=True):
    __tablename__ = "llm_daily_usage"

    usage_date: str = Field(primary_key=True)  # "YYYY-MM-DD" (UTC)
    call_count: int = Field(default=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
