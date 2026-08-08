"""Limitador de chamadas ao provedor de LLM (janela deslizante em memoria).

Diferente do `RateLimitMiddleware` (por IP, protege a API contra abuso de um
unico cliente), este limitador e GLOBAL — protege a cota real do provedor de
LLM configurado (ex: Gemini free tier: ~15 requisicoes/minuto, compartilhada
pelo PROJETO inteiro, nao por usuario). Sem isso, poucas pessoas testando a
aplicacao ao mesmo tempo já estouram a cota do provedor, e cada tentativa
automatica de retry da biblioteca cliente (LangChain) so piora o problema —
cada retry e mais uma chamada contra a mesma janela ja esgotada.

Aqui, quando o limite e atingido, a chamada ao provedor nem chega a ser
feita: falha rapido com uma mensagem amigavel, em vez de esperar dezenas de
segundos (varios retries com backoff) so para no fim receber um 429 do
provedor mesmo assim.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from functools import lru_cache


class LlmCallLimiter:
    def __init__(self, *, max_calls_per_minute: int, window_seconds: float = 60.0) -> None:
        self._max_calls = max_calls_per_minute
        self._window_seconds = window_seconds
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        """Registra uma tentativa de chamada. Retorna True se estiver dentro
        do limite (a chamada pode prosseguir) ou False se o limite ja foi
        atingido na janela atual (o chamador NAO deve prosseguir)."""
        if self._max_calls <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            while self._hits and now - self._hits[0] > self._window_seconds:
                self._hits.popleft()
            if len(self._hits) >= self._max_calls:
                return False
            self._hits.append(now)
            return True


@lru_cache
def get_llm_rate_limiter(max_calls_per_minute: int) -> LlmCallLimiter:
    """Cacheada pelo VALOR do limite (nao um singleton unico): producao usa
    o limite real do `.env`; testes passam um valor diferente (ex: 0, para
    desligar a guarda) e assim recebem uma instancia separada, sem interferir
    umas nas outras nem na guarda real usada pela aplicacao."""
    return LlmCallLimiter(max_calls_per_minute=max_calls_per_minute)
