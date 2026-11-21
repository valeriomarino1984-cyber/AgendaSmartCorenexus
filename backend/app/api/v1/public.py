"""Rotte pubbliche della prenotazione online (/prenota/<studio>): nessun accesso richiesto."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import client_ip, get_db, get_settings_dep
from app.core.config import Settings
from app.core.db import Database
from app.modules.notifications import service as notifications
from app.modules.public_booking import service

router = APIRouter(prefix="/public/studios/{slug}", tags=["prenotazione online"])

Db = Annotated[Database, Depends(get_db)]
Conf = Annotated[Settings, Depends(get_settings_dep)]
Ip = Annotated[str | None, Depends(client_ip)]
Slug = Annotated[str, Field(min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")]
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class BookingIn(BaseModel):
    service_id: uuid.UUID
    professional_id: uuid.UUID | None = None
    start_at: datetime
    is_online: bool = False
    first_name: Annotated[str, Field(min_length=1, max_length=80)]
    last_name: Annotated[str, Field(min_length=1, max_length=80)]
    email: Annotated[str, Field(min_length=5, max_length=254)]
    phone: Annotated[str, Field(min_length=6, max_length=30)]
    notes: Annotated[str, Field(max_length=500)] | None = None
    privacy_accepted: bool
    email_consent: bool = False
    marketing_consent: bool = False
    booking_key: Annotated[str, Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
    website: Annotated[str, Field(max_length=200)] = ""  # campo nascosto anti-spam

    @field_validator("email")
    @classmethod
    def _e(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Indirizzo email non valido.")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def _n(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Campo obbligatorio.")
        return v.strip()

    @field_validator("privacy_accepted")
    @classmethod
    def _p(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "Per prenotare devi accettare il trattamento dei dati per l'appuntamento."
            )
        return v


@router.get("")
def studio(slug: Slug, db: Db) -> dict[str, object]:
    return service.studio(db, slug)


@router.get("/slots")
def slots(
    slug: Slug,
    db: Db,
    service_id: uuid.UUID,
    first: Annotated[date, Query(alias="from")],
    last: Annotated[date, Query(alias="to")],
    professional_id: uuid.UUID | None = None,
) -> dict[str, object]:
    return service.slots(
        db, slug, service_id=service_id, professional_id=professional_id, first=first, last=last
    )


@router.post("/bookings", status_code=status.HTTP_201_CREATED)
def book(
    slug: Slug, body: BookingIn, db: Db, settings: Conf, ip: Ip, background: BackgroundTasks
) -> dict[str, object]:
    out = service.book(db, settings, slug, body.model_dump(), ip)
    background.add_task(notifications.maybe_process_now, db, settings)
    return out
