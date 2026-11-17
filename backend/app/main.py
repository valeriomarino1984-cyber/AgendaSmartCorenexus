"""Entry point FastAPI. Avvio: `uvicorn app.main:create_app --factory`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.sentry import init_sentry

log = structlog.get_logger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(
        level=settings.log_level,
        json_logs=settings.log_json,
        cache=settings.environment != "test",
    )
    init_sentry(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(
            settings.database_url.get_secret_value(),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )
        # Fail-closed: con un ruolo che aggira la RLS l'applicazione non parte.
        await db.verify_role(settings.app_db_role)
        redis = Redis.from_url(settings.redis_url.get_secret_value())
        app.state.db = db
        app.state.redis = redis
        log.info("startup", environment=settings.environment)
        try:
            yield
        finally:
            await redis.aclose()
            await db.dispose()

    expose_docs = settings.environment != "production"
    app = FastAPI(
        title="CoreNexus Agenda API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if expose_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if expose_docs else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)  # ultimo aggiunto = più esterno
    register_error_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")
    return app
