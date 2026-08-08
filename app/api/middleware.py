"""Middlewares transversais: correlation ID e limitacao basica de
requisicoes (secao 29 e 32 do prompt mestre)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_correlation_id, new_correlation_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-correlation-id")
        correlation_id = incoming or new_correlation_id()
        if incoming:
            from app.core.logging import set_correlation_id

            set_correlation_id(incoming)

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = get_correlation_id() or correlation_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limitador de requisicoes por IP em janela deslizante de 60 segundos.

    Implementacao em memoria, adequada para uma unica instancia (MVP). Para
    producao com multiplas instancias, trocar por um backend compartilhado
    (ex: Redis) sem alterar a interface do middleware.
    """

    def __init__(self, app, requests_per_minute: int) -> None:
        super().__init__(app)
        self._limit = requests_per_minute
        self._window_seconds = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._limit <= 0:
            return await call_next(request)

        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[client_key]

        while hits and now - hits[0] > self._window_seconds:
            hits.popleft()

        if len(hits) >= self._limit:
            # Middlewares adicionados via `add_middleware` rodam FORA da
            # camada que trata `@app.exception_handler` — uma excecao
            # levantada aqui nao seria convertida em resposta HTTP pelo
            # handler global (viraria erro 500 nao tratado). Por isso a
            # resposta 429 e construida diretamente, no mesmo formato do
            # handler de `AppError` usado pelo restante da API.
            from app.core.exceptions import RateLimitExceededError

            error = RateLimitExceededError(
                "Numero de requisicoes excedido. Tente novamente em instantes."
            )
            return JSONResponse(
                status_code=error.status_code,
                content={"error_code": error.error_code, "message": error.message},
            )

        hits.append(now)
        return await call_next(request)
