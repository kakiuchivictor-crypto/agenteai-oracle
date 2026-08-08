"""Contador diario (persistido) de chamadas ao provedor de LLM.

Complementa o `LlmCallLimiter` (janela por minuto, em memoria — o estado some
a cada reinicio do processo): planos gratuitos tambem tem um teto de
requisicoes POR DIA. Sem rastrear isso entre reinicios, o sistema pode
parecer saudavel a manha inteira e travar de vez a tarde sem aviso previo.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from app.database.models import LlmDailyUsage


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def has_daily_capacity(session: Session, *, daily_limit: int) -> bool:
    """`daily_limit <= 0` desliga a guarda (mesma convencao do limite por
    minuto em `LlmCallLimiter`)."""
    if daily_limit <= 0:
        return True
    usage = session.get(LlmDailyUsage, _today())
    return usage is None or usage.call_count < daily_limit


def record_daily_call(session: Session) -> None:
    today = _today()
    usage = session.get(LlmDailyUsage, today)
    if usage is None:
        session.add(LlmDailyUsage(usage_date=today, call_count=1))
    else:
        usage.call_count += 1
        usage.updated_at = datetime.now(UTC)
        session.add(usage)
