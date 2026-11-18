"""Agenda: orari settimanali, eccezioni (ferie, chiusure, aperture extra), orari liberi e
appuntamenti.

Titolare e segreteria gestiscono l'agenda di tutti; il professionista solo la propria
(e vede solo i propri appuntamenti).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import client_ip, current_auth, get_db, get_settings_dep
from app.core.config import Settings
from app.core.db import Database
from app.modules.accounts.service import AuthContext
from app.modules.agenda import service
from app.modules.notifications import service as notifications

router = APIRouter(tags=["agenda"])

Db = Annotated[Database, Depends(get_db)]
Conf = Annotated[Settings, Depends(get_settings_dep)]
Member = Annotated[AuthContext, Depends(current_auth)]
Ip = Annotated[str | None, Depends(client_ip)]


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


# ---------------------------------------------------------------- orari settimanali


class WeeklyRuleIn(BaseModel):
    weekday: Annotated[int, Field(ge=1, le=7)]
    start_time: time
    end_time: time


class WeeklyIn(BaseModel):
    location_id: uuid.UUID | None = None
    rules: Annotated[list[WeeklyRuleIn], Field(max_length=70)]


@router.get("/professionals/{professional_id}/availability")
def get_weekly(professional_id: uuid.UUID, ctx: Member, db: Db) -> list[dict[str, object]]:
    return service.list_weekly(db, ctx, professional_id)


@router.put("/professionals/{professional_id}/availability")
def put_weekly(
    professional_id: uuid.UUID, body: WeeklyIn, ctx: Member, db: Db, ip: Ip
) -> list[dict[str, object]]:
    rules = [r.model_dump() for r in body.rules]
    return service.replace_weekly(db, ctx, professional_id, rules, body.location_id, ip)


# ---------------------------------------------------------------- eccezioni


class ExceptionIn(BaseModel):
    kind: Literal["vacation", "unavailable", "closure", "extra"]
    professional_id: uuid.UUID | None = None
    start_at: datetime
    end_at: datetime
    reason: Annotated[str, Field(max_length=200)] | None = None

    @field_validator("reason")
    @classmethod
    def _r(cls, v: str | None) -> str | None:
        return _strip(v)


@router.get("/availability-exceptions")
def get_exceptions(
    ctx: Member,
    db: Db,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
) -> list[dict[str, object]]:
    return service.list_exceptions(db, ctx, service.to_utc(start), service.to_utc(end))


@router.post("/availability-exceptions", status_code=status.HTTP_201_CREATED)
def post_exception(body: ExceptionIn, ctx: Member, db: Db, ip: Ip) -> dict[str, object]:
    return service.create_exception(db, ctx, body.model_dump(), ip)


@router.delete("/availability-exceptions/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_exception(exception_id: uuid.UUID, ctx: Member, db: Db, ip: Ip) -> None:
    service.delete_exception(db, ctx, exception_id, ip)


# ---------------------------------------------------------------- orari liberi


@router.get("/slots")
def get_slots(
    ctx: Member,
    db: Db,
    professional_id: uuid.UUID,
    service_id: uuid.UUID,
    first: Annotated[date, Query(alias="from")],
    last: Annotated[date, Query(alias="to")],
    location_id: uuid.UUID | None = None,
) -> dict[str, object]:
    return service.available_slots(
        db,
        ctx,
        professional_id=professional_id,
        service_id=service_id,
        first=first,
        last=last,
        location_id=location_id,
    )


# ---------------------------------------------------------------- appuntamenti


class AppointmentFields(BaseModel):
    duration_minutes: Annotated[int, Field(ge=5, le=600)] | None = None
    is_online: bool | None = None
    price: Annotated[Decimal, Field(ge=0, le=99999999, decimal_places=2)] | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None
    force: bool = False

    @field_validator("notes")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return _strip(v)


class AppointmentIn(AppointmentFields):
    client_id: uuid.UUID
    professional_id: uuid.UUID
    service_id: uuid.UUID
    location_id: uuid.UUID | None = None
    start_at: datetime
    status: Literal["pending", "confirmed"] = "confirmed"


class AppointmentUpdate(AppointmentFields):
    version: Annotated[int, Field(ge=1)]
    client_id: uuid.UUID | None = None
    professional_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    start_at: datetime | None = None


class StatusIn(BaseModel):
    version: Annotated[int, Field(ge=1)]
    status: Literal[
        "confirmed", "cancelled_by_client", "cancelled_by_staff", "completed", "no_show"
    ]
    reason: Annotated[str, Field(max_length=300)] | None = None

    @field_validator("reason")
    @classmethod
    def _r(cls, v: str | None) -> str | None:
        return _strip(v)


@router.get("/appointments")
def get_appointments(
    ctx: Member,
    db: Db,
    settings: Conf,
    background: BackgroundTasks,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
    professional_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    include_cancelled: bool = False,
) -> list[dict[str, object]]:
    # Promemoria "di passaggio" mentre l'agenda è in uso (oltre al cron di cPanel).
    background.add_task(notifications.maybe_process, db, settings)
    return service.list_appointments(
        db,
        ctx,
        start=start,
        end=end,
        professional_id=professional_id,
        client_id=client_id,
        include_cancelled=include_cancelled,
    )


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
def post_appointment(
    body: AppointmentIn, ctx: Member, db: Db, settings: Conf, background: BackgroundTasks
) -> dict[str, object]:
    out = service.create_appointment(db, settings, ctx, body.model_dump())
    background.add_task(notifications.safe_process, db, settings, ctx.tenant_id)
    return out


@router.get("/appointments/{appointment_id}")
def get_appointment(appointment_id: uuid.UUID, ctx: Member, db: Db) -> dict[str, object]:
    return service.get_appointment(db, ctx, appointment_id)


@router.patch("/appointments/{appointment_id}")
def patch_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentUpdate,
    ctx: Member,
    db: Db,
    settings: Conf,
    background: BackgroundTasks,
) -> dict[str, object]:
    changes = body.model_dump(exclude_unset=True)
    version = changes.pop("version")
    for key in ("client_id", "professional_id", "service_id", "start_at", "duration_minutes"):
        if key in changes and changes[key] is None:
            changes.pop(key)
    out = service.update_appointment(db, settings, ctx, appointment_id, version, changes)
    background.add_task(notifications.safe_process, db, settings, ctx.tenant_id)
    return out


@router.post("/appointments/{appointment_id}/status")
def post_status(
    appointment_id: uuid.UUID,
    body: StatusIn,
    ctx: Member,
    db: Db,
    settings: Conf,
    background: BackgroundTasks,
) -> dict[str, object]:
    out = service.set_status(db, ctx, appointment_id, body.version, body.status, body.reason)
    background.add_task(notifications.safe_process, db, settings, ctx.tenant_id)
    return out
