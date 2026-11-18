"""Area piattaforma CoreNexus (/piattaforma): accesso del personale e gestione degli studi.

Cookie proprio (`platform_cookie_name`): né la sessione di uno studio né quella di un cliente
aprono queste rotte. Ogni rotta, tranne accesso e inviti, richiede password + codice a 6 cifre.
"""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import client_ip, get_db, get_settings_dep
from app.api.v1.auth import Message
from app.core.config import Settings
from app.core.db import Database
from app.modules.accounts.service import UnauthorizedError, deliver
from app.modules.platform import service
from app.modules.platform.service import StaffContext

router = APIRouter(prefix="/platform", tags=["piattaforma"])

Db = Annotated[Database, Depends(get_db)]
Conf = Annotated[Settings, Depends(get_settings_dep)]
Ip = Annotated[str | None, Depends(client_ip)]
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
Email = Annotated[str, Field(min_length=5, max_length=254)]
Code = Annotated[str, Field(min_length=6, max_length=8)]
Token = Annotated[str, Field(min_length=20, max_length=100)]


def _email(v: str) -> str:
    v = v.strip()
    if not _EMAIL_RE.match(v):
        raise ValueError("Indirizzo email non valido.")
    return v


def current_staff(request: Request, db: Db, settings: Conf) -> StaffContext:
    ctx = service.resolve(db, request.cookies.get(settings.platform_cookie_name))
    if ctx is None:
        raise UnauthorizedError()
    return ctx


Staff = Annotated[StaffContext, Depends(current_staff)]


def _set_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        settings.platform_cookie_name,
        token,
        max_age=int(service.SESSION_MAX.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def _me(ctx: StaffContext) -> dict[str, object]:
    return {"id": str(ctx.staff_id), "email": ctx.email, "full_name": ctx.full_name}


class EmailIn(BaseModel):
    email: Email
    _v = field_validator("email")(lambda cls, v: _email(v))


class LoginIn(BaseModel):
    email: Email
    password: Annotated[str, Field(min_length=1, max_length=128)]


class CodeIn(BaseModel):
    code: Code


class AcceptIn(BaseModel):
    token: Token
    full_name: Annotated[str, Field(min_length=2, max_length=120)]
    password: Annotated[str, Field(min_length=1, max_length=128)]
    code: Code


class StaffIn(BaseModel):
    email: Email
    full_name: Annotated[str, Field(min_length=2, max_length=120)]
    _v = field_validator("email")(lambda cls, v: _email(v))


class StaffUpdate(BaseModel):
    status: Literal["active", "disabled"]


class TenantIn(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    business_type: Annotated[str, Field(min_length=2, max_length=40)]
    owner_name: Annotated[str, Field(min_length=2, max_length=120)]
    owner_email: Email
    trial_days: Annotated[int, Field(ge=0, le=365)] = 14
    _v = field_validator("owner_email")(lambda cls, v: _email(v))


class TenantUpdate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    business_type: Annotated[str, Field(min_length=2, max_length=40)] | None = None
    status: Literal["trial", "active", "suspended", "cancelled"] | None = None
    extend_trial_days: Annotated[int, Field(ge=1, le=365)] | None = None


# ---------------------------------------------------------------- accesso


@router.get("/status")
def get_status(db: Db, settings: Conf) -> dict[str, object]:
    return service.status(db, settings)


@router.post("/setup", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def setup(body: EmailIn, db: Db, settings: Conf, ip: Ip) -> Message:
    deliver(settings, service.request_setup(db, settings, email=body.email, ip=ip))
    return Message(
        message="Se l'indirizzo è quello previsto riceverai un'email con il link di configurazione."
    )


@router.get("/invite")
def invite_info(
    db: Db, settings: Conf, token: Annotated[str, Query(min_length=20, max_length=100)]
) -> dict[str, object]:
    return service.invite_info(db, settings, token)


@router.post("/invite/accept")
def accept(
    body: AcceptIn, request: Request, response: Response, db: Db, settings: Conf, ip: Ip
) -> dict[str, object]:
    token = service.accept_invite(
        db,
        settings,
        token=body.token,
        full_name=body.full_name,
        password=body.password,
        code=body.code,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    _set_cookie(response, settings, token)
    ctx = service.resolve(db, token)
    if ctx is None:
        raise UnauthorizedError()
    return _me(ctx)


@router.post("/login")
def login(
    body: LoginIn, request: Request, response: Response, db: Db, settings: Conf, ip: Ip
) -> dict[str, object]:
    service._key(settings)  # area spenta senza chiave
    token = service.login(
        db,
        email=body.email,
        password=body.password,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    _set_cookie(response, settings, token)
    return {"mfa_required": True}


@router.post("/login/mfa")
def login_mfa(body: CodeIn, request: Request, db: Db, settings: Conf, ip: Ip) -> dict[str, object]:
    token = request.cookies.get(settings.platform_cookie_name)
    service.verify_mfa(db, settings, token, body.code, ip)
    ctx = service.resolve(db, token)
    if ctx is None:
        raise UnauthorizedError()
    return _me(ctx)


@router.get("/me")
def me(ctx: Staff) -> dict[str, object]:
    return _me(ctx)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, ctx: Staff, db: Db, settings: Conf, ip: Ip) -> Response:
    service.logout(db, ctx, ip)
    response.delete_cookie(
        settings.platform_cookie_name, path="/", secure=settings.cookie_secure, httponly=True
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


# ---------------------------------------------------------------- personale


@router.get("/staff")
def staff_list(ctx: Staff, db: Db) -> list[dict[str, object]]:
    return service.list_staff(db, ctx)


@router.post("/staff", response_model=Message, status_code=status.HTTP_201_CREATED)
def staff_invite(body: StaffIn, ctx: Staff, db: Db, settings: Conf, ip: Ip) -> Message:
    outcome = deliver(
        settings,
        service.invite_staff(db, settings, ctx, email=body.email, full_name=body.full_name, ip=ip),
    )
    return Message(message="Invito inviato.", email_sent=outcome.email_sent)


@router.patch("/staff/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
def staff_update(staff_id: uuid.UUID, body: StaffUpdate, ctx: Staff, db: Db, ip: Ip) -> None:
    service.set_staff_status(db, ctx, staff_id, body.status, ip)


# ---------------------------------------------------------------- studi


@router.get("/tenants")
def tenants(
    ctx: Staff, db: Db, q: Annotated[str | None, Query(max_length=100)] = None
) -> list[dict[str, object]]:
    return service.list_tenants(db, ctx, q=q)


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
def tenant_create(body: TenantIn, ctx: Staff, db: Db, settings: Conf, ip: Ip) -> dict[str, object]:
    tenant, outcome = service.create_tenant(
        db,
        settings,
        ctx,
        name=body.name,
        business_type=body.business_type,
        owner_name=body.owner_name,
        owner_email=body.owner_email,
        trial_days=body.trial_days,
        ip=ip,
    )
    deliver(settings, outcome)
    return {**tenant, "email_sent": outcome.email_sent}


@router.get("/tenants/{tenant_id}")
def tenant_get(tenant_id: uuid.UUID, ctx: Staff, db: Db) -> dict[str, object]:
    return service.get_tenant(db, ctx, tenant_id)


@router.patch("/tenants/{tenant_id}")
def tenant_update(
    tenant_id: uuid.UUID, body: TenantUpdate, ctx: Staff, db: Db, ip: Ip
) -> dict[str, object]:
    return service.update_tenant(db, ctx, tenant_id, body.model_dump(exclude_none=True), ip)


@router.post("/tenants/{tenant_id}/profile")
def tenant_profile(tenant_id: uuid.UUID, ctx: Staff, db: Db, ip: Ip) -> dict[str, object]:
    return service.load_profile(db, ctx, tenant_id, ip)


@router.post("/tenants/{tenant_id}/resend-invite", response_model=Message)
def tenant_resend(tenant_id: uuid.UUID, ctx: Staff, db: Db, settings: Conf, ip: Ip) -> Message:
    outcome = deliver(settings, service.resend_owner_invite(db, settings, ctx, tenant_id, ip))
    return Message(message="Invito inviato di nuovo.", email_sent=outcome.email_sent)


@router.get("/activity")
def activity(ctx: Staff, db: Db) -> list[dict[str, object]]:
    return service.activity(db, ctx)
