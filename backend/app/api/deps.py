"""Dipendenze FastAPI comuni: database, configurazione, IP del client, sessione e ruoli."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import ForbiddenError
from app.modules.accounts.service import AuthContext, UnauthorizedError, resolve_session


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def client_ip(request: Request) -> str | None:
    # LiteSpeed/Passenger passano l'IP reale in REMOTE_ADDR: non ci si fida di X-Forwarded-For,
    # che il client può falsificare.
    return request.client.host if request.client else None


def current_auth(
    request: Request,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> AuthContext:
    ctx = resolve_session(db, settings, request.cookies.get(settings.session_cookie_name))
    if ctx is None:
        raise UnauthorizedError()
    return ctx


def require_roles(*roles: str) -> Callable[..., AuthContext]:
    def _check(ctx: Annotated[AuthContext, Depends(current_auth)]) -> AuthContext:
        if ctx.role not in roles:
            raise ForbiddenError(
                "Questa operazione è riservata al titolare dello studio.",
                code="ruolo_insufficiente",
            )
        return ctx

    return _check
