"""Area clienti: link di accesso via email, appuntamenti del cliente, disdetta.

Usa un cookie suo (`client_cookie_name`), diverso da quello dello staff: le rotte dello
studio non accettano la sessione di un cliente e queste non accettano quella dello staff.
"""

from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import client_ip, get_db, get_settings_dep
from app.api.v1.auth import Message
from app.core.config import Settings
from app.core.db import Database
from app.core.errors import must
from app.modules.accounts.service import UnauthorizedError, deliver
from app.modules.client_portal import service
from app.modules.client_portal.service import ClientContext

router = APIRouter(prefix="/client-portal", tags=["area clienti"])

Db = Annotated[Database, Depends(get_db)]
Conf = Annotated[Settings, Depends(get_settings_dep)]
Ip = Annotated[str | None, Depends(client_ip)]
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
SENT = (
    "Se l'indirizzo è registrato presso uno studio riceverai un'email con il link per entrare "
    "entro pochi minuti. Controlla anche lo spam."
)


def current_client(request: Request, db: Db, settings: Conf) -> ClientContext:
    ctx = service.resolve(db, request.cookies.get(settings.client_cookie_name))
    if ctx is None:
        raise UnauthorizedError()
    return ctx


ClientAuth = Annotated[ClientContext, Depends(current_client)]


class LinkIn(BaseModel):
    email: Annotated[str, Field(min_length=5, max_length=254)]

    @field_validator("email")
    @classmethod
    def _e(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Indirizzo email non valido.")
        return v


class TokenIn(BaseModel):
    token: Annotated[str, Field(min_length=20, max_length=100)]


@router.post("/link", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def request_link(body: LinkIn, db: Db, settings: Conf, ip: Ip) -> Message:
    deliver(settings, service.request_link(db, settings, email=body.email, ip=ip))
    return Message(message=SENT)


@router.post("/login")
def login(
    body: TokenIn, request: Request, response: Response, db: Db, settings: Conf, ip: Ip
) -> dict[str, object]:
    token = service.verify_link(
        db, token=body.token, ip=ip, user_agent=request.headers.get("user-agent")
    )
    response.set_cookie(
        settings.client_cookie_name,
        token,
        max_age=int(service.SESSION_MAX.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    ctx = must(service.resolve(db, token), "sessione cliente")
    return {"email": ctx.email}


@router.get("/me")
def me(ctx: ClientAuth, db: Db) -> dict[str, object]:
    return service.overview(db, ctx)


@router.post("/appointments/{appointment_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel(appointment_id: uuid.UUID, ctx: ClientAuth, db: Db, ip: Ip) -> None:
    service.cancel(db, ctx, appointment_id, ip)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, ctx: ClientAuth, db: Db, settings: Conf) -> Response:
    service.logout(db, ctx)
    response.delete_cookie(
        settings.client_cookie_name, path="/", secure=settings.cookie_secure, httponly=True
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
