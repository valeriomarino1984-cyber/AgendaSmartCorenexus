"""Anagrafiche dello studio: sedi, professionisti, prestazioni, clienti.

Lettura per tutto lo staff; sedi, professionisti e prestazioni si modificano solo dal titolare.
I clienti sono gestiti da tutto lo staff (titolare, professionisti, segreteria).
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import client_ip, current_auth, get_db, require_roles
from app.core.db import Database
from app.modules.accounts.service import AuthContext
from app.modules.catalog import service

router = APIRouter(tags=["anagrafiche"])

Db = Annotated[Database, Depends(get_db)]
Member = Annotated[AuthContext, Depends(current_auth)]
Owner = Annotated[AuthContext, Depends(require_roles("owner"))]
Ip = Annotated[str | None, Depends(client_ip)]

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_TIMEZONES = available_timezones()

Name = Annotated[str, Field(min_length=1, max_length=120)]
Color = Annotated[str, Field(min_length=7, max_length=7)]


def _color(v: str | None) -> str | None:
    if v is not None and not _COLOR_RE.match(v):
        raise ValueError("Colore non valido (formato #RRGGBB).")
    return v.lower() if v else v


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


# ---------------------------------------------------------------- sedi


class LocationUpdate(BaseModel):
    name: Name | None = None
    address: Annotated[str, Field(max_length=200)] | None = None
    timezone: Annotated[str, Field(max_length=40)] | None = None
    active: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is not None and v not in _TIMEZONES:
            raise ValueError("Fuso orario non valido.")
        return v

    @field_validator("address")
    @classmethod
    def _address(cls, v: str | None) -> str | None:
        return _strip(v)


@router.get("/locations")
def list_locations(ctx: Member, db: Db) -> list[dict[str, object]]:
    return service.list_locations(db, ctx)


@router.patch("/locations/{location_id}")
def update_location(
    location_id: uuid.UUID, body: LocationUpdate, ctx: Owner, db: Db, ip: Ip
) -> dict[str, object]:
    return service.update_location(
        db, ctx, location_id, body.model_dump(exclude_unset=True, exclude_none=True), ip
    )


# ---------------------------------------------------------------- professionisti


class ProfessionalFields(BaseModel):
    specialization: Annotated[str, Field(max_length=120)] | None = None
    color: Color | None = None
    public_booking: bool | None = None
    user_id: uuid.UUID | None = None

    @field_validator("color")
    @classmethod
    def _c(cls, v: str | None) -> str | None:
        return _color(v)

    @field_validator("specialization")
    @classmethod
    def _s(cls, v: str | None) -> str | None:
        return _strip(v)


class ProfessionalIn(ProfessionalFields):
    name: Name


class ProfessionalUpdate(ProfessionalFields):
    name: Name | None = None
    status: Literal["active", "inactive"] | None = None


def _without_null_flags(data: dict[str, object], *keys: str) -> dict[str, object]:
    """I campi obbligatori nel database non possono essere azzerati: null significa "invariato"."""
    return {k: v for k, v in data.items() if not (k in keys and v is None)}


_PROF_REQUIRED = ("name", "color", "public_booking", "status")


@router.get("/professionals")
def list_professionals(ctx: Member, db: Db) -> list[dict[str, object]]:
    return service.list_professionals(db, ctx)


@router.post("/professionals", status_code=status.HTTP_201_CREATED)
def create_professional(body: ProfessionalIn, ctx: Owner, db: Db, ip: Ip) -> dict[str, object]:
    data = _without_null_flags(body.model_dump(), *_PROF_REQUIRED)
    return service.create_professional(db, ctx, data, ip)


@router.patch("/professionals/{professional_id}")
def update_professional(
    professional_id: uuid.UUID, body: ProfessionalUpdate, ctx: Owner, db: Db, ip: Ip
) -> dict[str, object]:
    data = _without_null_flags(body.model_dump(exclude_unset=True), *_PROF_REQUIRED)
    return service.update_professional(db, ctx, professional_id, data, ip)


# ---------------------------------------------------------------- prestazioni


class ServiceFields(BaseModel):
    description: Annotated[str, Field(max_length=2000)] | None = None
    preparation_minutes: Annotated[int, Field(ge=0, le=240)] | None = None
    price: Annotated[Decimal, Field(ge=0, le=99999999, decimal_places=2)] | None = None
    color: Color | None = None
    mode: Literal["in_person", "online", "both"] | None = None
    public_visible: bool | None = None
    sort_order: Annotated[int, Field(ge=0, le=10000)] | None = None
    professional_ids: Annotated[list[uuid.UUID], Field(max_length=200)] | None = None

    @field_validator("color")
    @classmethod
    def _c(cls, v: str | None) -> str | None:
        return _color(v)

    @field_validator("description")
    @classmethod
    def _d(cls, v: str | None) -> str | None:
        return _strip(v)


class ServiceIn(ServiceFields):
    name: Name
    duration_minutes: Annotated[int, Field(ge=5, le=600)]


class ServiceUpdate(ServiceFields):
    name: Name | None = None
    duration_minutes: Annotated[int, Field(ge=5, le=600)] | None = None
    active: bool | None = None


_SERVICE_REQUIRED = (
    "name",
    "duration_minutes",
    "preparation_minutes",
    "color",
    "mode",
    "public_visible",
    "active",
    "sort_order",
    "professional_ids",
)


@router.get("/services")
def list_services(ctx: Member, db: Db) -> list[dict[str, object]]:
    return service.list_services(db, ctx)


@router.get("/services/profile")
def preview_profile(ctx: Member, db: Db) -> dict[str, object]:
    return service.preview_profile(db, ctx)


@router.post("/services/profile")
def load_profile(ctx: Owner, db: Db, ip: Ip) -> dict[str, object]:
    return service.load_profile(db, ctx, ip)


@router.post("/services", status_code=status.HTTP_201_CREATED)
def create_service(body: ServiceIn, ctx: Owner, db: Db, ip: Ip) -> dict[str, object]:
    data = _without_null_flags(body.model_dump(), *_SERVICE_REQUIRED)
    return service.create_service(db, ctx, data, ip)


@router.patch("/services/{service_id}")
def update_service(
    service_id: uuid.UUID, body: ServiceUpdate, ctx: Owner, db: Db, ip: Ip
) -> dict[str, object]:
    data = _without_null_flags(body.model_dump(exclude_unset=True), *_SERVICE_REQUIRED)
    return service.update_service(db, ctx, service_id, data, ip)


# ---------------------------------------------------------------- clienti


class ClientFields(BaseModel):
    phone: Annotated[str, Field(max_length=30)] | None = None
    email: Annotated[str, Field(max_length=254)] | None = None
    birth_date: date | None = None
    reference_professional_id: uuid.UUID | None = None
    admin_notes: Annotated[str, Field(max_length=4000)] | None = None
    preferred_channel: Literal["whatsapp", "email", "none"] | None = None
    whatsapp_consent: bool | None = None
    email_consent: bool | None = None
    marketing_consent: bool | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        v = _strip(v)
        if v and not _EMAIL_RE.match(v):
            raise ValueError("Indirizzo email non valido.")
        return v

    @field_validator("phone", "admin_notes")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return _strip(v)

    @field_validator("birth_date")
    @classmethod
    def _birth(cls, v: date | None) -> date | None:
        if v is not None and not date(1900, 1, 1) <= v <= date.today():
            raise ValueError("Data di nascita non valida.")
        return v


class ClientIn(ClientFields):
    first_name: Annotated[str, Field(min_length=1, max_length=80)]
    last_name: Annotated[str, Field(min_length=1, max_length=80)]


class ClientUpdate(ClientFields):
    first_name: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    last_name: Annotated[str, Field(min_length=1, max_length=80)] | None = None


_CLIENT_REQUIRED = (
    "first_name",
    "last_name",
    "whatsapp_consent",
    "email_consent",
    "marketing_consent",
)


def _names(data: dict[str, object]) -> dict[str, object]:
    for key in ("first_name", "last_name"):
        if isinstance(data.get(key), str):
            data[key] = str(data[key]).strip()
            if not data[key]:
                raise service.InvalidDataError("Nome e cognome sono obbligatori.")
    return data


@router.get("/clients")
def list_clients(
    ctx: Member,
    db: Db,
    q: Annotated[str | None, Query(max_length=100)] = None,
    client_status: Annotated[Literal["active", "archived"], Query(alias="status")] = "active",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> dict[str, object]:
    return service.list_clients(db, ctx, q=q, status=client_status, limit=limit, offset=offset)


@router.post("/clients", status_code=status.HTTP_201_CREATED)
def create_client(
    body: ClientIn,
    ctx: Member,
    db: Db,
    ip: Ip,
    force: Annotated[bool, Query()] = False,
) -> dict[str, object]:
    data = _names(_without_null_flags(body.model_dump(), *_CLIENT_REQUIRED))
    return service.create_client(db, ctx, data, force=force, ip=ip)


@router.get("/clients/{client_id}")
def get_client(client_id: uuid.UUID, ctx: Member, db: Db) -> dict[str, object]:
    return service.get_client(db, ctx, client_id)


@router.patch("/clients/{client_id}")
def update_client(
    client_id: uuid.UUID, body: ClientUpdate, ctx: Member, db: Db, ip: Ip
) -> dict[str, object]:
    data = _names(_without_null_flags(body.model_dump(exclude_unset=True), *_CLIENT_REQUIRED))
    return service.update_client(db, ctx, client_id, data, ip)


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_client(client_id: uuid.UUID, ctx: Member, db: Db, ip: Ip) -> None:
    service.set_client_status(db, ctx, client_id, "archived", ip)


@router.post("/clients/{client_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_client(client_id: uuid.UUID, ctx: Member, db: Db, ip: Ip) -> None:
    service.set_client_status(db, ctx, client_id, "active", ip)
