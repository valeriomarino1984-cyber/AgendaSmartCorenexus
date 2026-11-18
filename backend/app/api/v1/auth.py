"""Rotte di accesso: registrazione, verifica email, login, logout, profilo, password, inviti."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import client_ip, current_auth, get_db, get_settings_dep
from app.core.config import Settings
from app.core.db import Database
from app.core.errors import must
from app.modules.accounts import service
from app.modules.accounts.service import AuthContext, Outcome

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
Email = Annotated[str, Field(min_length=5, max_length=254)]
Name = Annotated[str, Field(min_length=2, max_length=120)]
Password = Annotated[str, Field(min_length=1, max_length=128)]
Token = Annotated[str, Field(min_length=20, max_length=100)]


def _email(value: str) -> str:
    value = value.strip()
    if not _EMAIL_RE.match(value):
        raise ValueError("Indirizzo email non valido.")
    return value


class RegisterIn(BaseModel):
    studio_name: Name
    business_type: Annotated[str, Field(min_length=2, max_length=40)]
    full_name: Name
    email: Email
    password: Password
    accept_terms: bool

    _v_email = field_validator("email")(lambda cls, v: _email(v))

    @field_validator("accept_terms")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Per registrarti devi accettare i termini e l'informativa privacy.")
        return v


class EmailIn(BaseModel):
    email: Email
    _v_email = field_validator("email")(lambda cls, v: _email(v))


class LoginIn(BaseModel):
    email: Email
    password: Password


class TokenIn(BaseModel):
    token: Token


class ResetIn(BaseModel):
    token: Token
    password: Password


class SwitchIn(BaseModel):
    tenant_id: uuid.UUID


class Message(BaseModel):
    message: str
    email_sent: bool | None = None


Db = Annotated[Database, Depends(get_db)]
Conf = Annotated[Settings, Depends(get_settings_dep)]
Auth = Annotated[AuthContext, Depends(current_auth)]
Ip = Annotated[str | None, Depends(client_ip)]


def _set_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_max_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _login_response(
    db: Database, settings: Settings, outcome: Outcome, response: Response
) -> dict[str, object]:
    token = must(outcome.session_token, "token di sessione")
    _set_cookie(response, settings, token)
    ctx = must(service.resolve_session(db, settings, token), "sessione")
    return service.me(db, ctx)


SENT = "Se i dati sono corretti riceverai un'email entro pochi minuti. Controlla anche lo spam."


@router.post(
    "/register",
    response_model=Message,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Registrazione di un nuovo studio (risposta identica se l'email esiste)",
)
def register(body: RegisterIn, db: Db, settings: Conf, ip: Ip) -> Message:
    outcome = service.register(
        db,
        settings,
        studio_name=body.studio_name,
        business_type=body.business_type,
        full_name=body.full_name,
        email=body.email,
        password=body.password,
        ip=ip,
    )
    service.deliver(settings, outcome)
    return Message(message=SENT)


@router.post("/verify-email/resend", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def resend_verification(body: EmailIn, db: Db, settings: Conf, ip: Ip) -> Message:
    service.deliver(settings, service.resend_verification(db, settings, email=body.email, ip=ip))
    return Message(message=SENT)


@router.post("/verify-email", summary="Conferma l'email e apre la sessione")
def verify_email(
    body: TokenIn, request: Request, response: Response, db: Db, settings: Conf, ip: Ip
) -> dict[str, object]:
    outcome = service.verify_email(
        db, settings, token=body.token, ip=ip, user_agent=request.headers.get("user-agent")
    )
    return _login_response(db, settings, outcome, response)


@router.post("/login")
def login(
    body: LoginIn, request: Request, response: Response, db: Db, settings: Conf, ip: Ip
) -> dict[str, object]:
    outcome = service.login(
        db,
        settings,
        email=body.email,
        password=body.password,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    return _login_response(db, settings, outcome, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, ctx: Auth, db: Db, settings: Conf, ip: Ip) -> Response:
    service.logout(db, ctx, ip)
    response.delete_cookie(
        settings.session_cookie_name, path="/", secure=settings.cookie_secure, httponly=True
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me")
def me(ctx: Auth, db: Db) -> dict[str, object]:
    return service.me(db, ctx)


@router.post("/switch-tenant")
def switch_tenant(
    body: SwitchIn, ctx: Auth, db: Db, settings: Conf, request: Request, ip: Ip
) -> dict[str, object]:
    service.switch_tenant(db, ctx, body.tenant_id, ip)
    cookie = request.cookies.get(settings.session_cookie_name)
    new_ctx = must(service.resolve_session(db, settings, cookie), "sessione")
    return service.me(db, new_ctx)


@router.post("/password/forgot", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: EmailIn, db: Db, settings: Conf, ip: Ip) -> Message:
    service.deliver(settings, service.forgot_password(db, settings, email=body.email, ip=ip))
    return Message(message=SENT)


@router.post("/password/reset", response_model=Message)
def reset_password(body: ResetIn, db: Db, ip: Ip) -> Message:
    service.reset_password(db, token=body.token, password=body.password, ip=ip)
    return Message(message="Password aggiornata. Ora puoi accedere.")


@router.get("/invitation", summary="Dati dell'invito (studio, email) prima di accettarlo")
def invitation_info(
    token: Annotated[str, Field(min_length=20, max_length=100)], db: Db
) -> dict[str, object]:
    return service.invitation_info(db, token)


@router.post("/invitation/accept")
def accept_invitation(
    body: ResetIn, request: Request, response: Response, db: Db, settings: Conf, ip: Ip
) -> dict[str, object]:
    outcome = service.accept_invitation(
        db,
        settings,
        token=body.token,
        password=body.password,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    return _login_response(db, settings, outcome, response)


Role = Literal["owner", "professional", "secretary"]
