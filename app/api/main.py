"""Ponto de entrada da API FastAPI (secao 39 do prompt mestre).

Uso: uvicorn app.api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware import CorrelationIdMiddleware, RateLimitMiddleware
from app.api.routes import categories, chat, config, documents, feedback, health, metrics, tools
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    settings.ensure_runtime_directories()

    app = FastAPI(
        title=settings.app_name,
        description="AxysAI para Consulta de Documentos (RAG).",
        version="0.7.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(CorrelationIdMiddleware)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        # Nunca expor traceback ao usuario final (secao 41); o detalhe
        # tecnico completo ja foi registrado via logging estruturado onde
        # a excecao foi originalmente levantada.
        logger.warning(
            "api.request_failed",
            error_code=exc.error_code,
            path=str(request.url.path),
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(categories.router)
    app.include_router(chat.router)
    app.include_router(feedback.router)
    app.include_router(metrics.router)
    app.include_router(config.router)
    app.include_router(tools.router)

    return app


app = create_app()
