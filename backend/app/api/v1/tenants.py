"""Dati dello studio corrente e collaboratori."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import client_ip, current_auth, get_db, get_settings_dep, require_roles
from app.api.v1.auth import Message
from app.core.config import Settings
from app.core.db import Database
from app.modules.accounts import service
from app.modules.accounts.service import AuthContext

router = APIRouter(prefix="/tenants/current", tags=["studio"])

Db = Annotated[Database, Depends(get_db)]
Conf = Annotated[Settings, Depends(get_settings_dep)]
Member = Annotated[AuthContext, Depends(current_auth)]
Owner = Annotated[AuthContext, Depends(require_roles("owner"))]
Ip = Annotated[str | None, Depends(client_ip)]
Role = Literal["owner", "professional", "secretary"]

_PHONE_RE = re.compile(r"^\+?[0-9 ()./-]{6,30}$")
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class StudioUpdate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    business_type: Annotated[str, Field(min_length=2, max_length=40)] | None = None
    neutral_messaging: bool | None = None
    contact_email: Annotated[str, Field(max_length=254)] | None = None
    contact_phone: Annotated[str, Field(max_length=30)] | None = None
    address: Annotated[str, Field(max_length=200)] | None = None
    cancellation_min_hours: Annotated[int, Field(ge=0, le=168)] | None = None
    email_confirmations: bool | None = None
    reminder_hours: Annotated[int, Field(ge=0, le=168)] | None = None

    @field_validator("contact_email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v and not _EMAIL_RE.match(v.strip()):
            raise ValueError("Indirizzo email non valido.")
        return v.strip() if v else None

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v and not _PHONE_RE.match(v.strip()):
            raise ValueError("Numero di telefono non valido.")
        return v.strip() if v else None


class InviteIn(BaseModel):
    email: Annotated[str, Field(min_length=5, max_length=254)]
    full_name: Annotated[str, Field(min_length=2, max_length=120)]
    role: Role

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v.strip()):
            raise ValueError("Indirizzo email non valido.")
        return v.strip()


class MemberUpdate(BaseModel):
    role: Role | None = None
    status: Literal["active", "disabled"] | None = None


@router.get("")
def get_current(ctx: Member, db: Db) -> dict[str, object]:
    return service.get_studio(db, ctx)


@router.put("")
def update_current(body: StudioUpdate, ctx: Owner, db: Db, ip: Ip) -> dict[str, object]:
    return service.update_studio(db, ctx, body.model_dump(exclude_unset=True), ip)


@router.get("/users")
def list_users(ctx: Owner, db: Db) -> list[dict[str, object]]:
    return service.list_members(db, ctx)


@router.post("/users", response_model=Message, status_code=status.HTTP_201_CREATED)
def invite_user(body: InviteIn, ctx: Owner, db: Db, settings: Conf, ip: Ip) -> Message:
    outcome = service.deliver(
        settings,
        service.invite(
            db, settings, ctx, email=body.email, full_name=body.full_name, role=body.role, ip=ip
        ),
    )
    if outcome.email_sent is False:
        return Message(
            message="Collaboratore aggiunto, ma l'email non è partita: riprova più tardi.",
            email_sent=False,
        )
    return Message(message="Invito inviato.", email_sent=True)


@router.patch("/users/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_user(membership_id: uuid.UUID, body: MemberUpdate, ctx: Owner, db: Db, ip: Ip) -> None:
    service.update_member(db, ctx, membership_id, role=body.role, status=body.status, ip=ip)
