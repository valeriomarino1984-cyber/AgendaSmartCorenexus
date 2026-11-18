"""Notifiche ai clienti: elenco per lo studio, nuovo tentativo e rotta del cron di cPanel."""

from __future__ import annotations

import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import select

from app.api.deps import current_auth, get_db, get_settings_dep
from app.core.config import Settings
from app.core.db import Database
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.agenda import Appointment
from app.models.catalog import Professional
from app.models.notifications import NotificationJob
from app.modules.accounts.service import AuthContext
from app.modules.notifications import service

router = APIRouter(tags=["notifiche"])

Db = Annotated[Database, Depends(get_db)]
Conf = Annotated[Settings, Depends(get_settings_dep)]
Member = Annotated[AuthContext, Depends(current_auth)]


def _own_professional(db: Database, ctx: AuthContext) -> uuid.UUID | None:
    """Il professionista vede solo le notifiche dei propri appuntamenti."""
    if ctx.role != "professional":
        return None
    with db.tenant_session(ctx.tenant_id) as s:
        return (
            s.scalar(select(Professional.id).where(Professional.user_id == ctx.user_id))
            or uuid.uuid4()
        )


@router.get("/notifications")
def list_notifications(
    ctx: Member, db: Db, limit: Annotated[int, Query(ge=1, le=200)] = 100
) -> list[dict[str, object]]:
    mine = _own_professional(db, ctx)
    with db.tenant_session(ctx.tenant_id) as s:
        return service.list_recent(s, professional_id=mine, limit=limit)


@router.post("/notifications/{job_id}/retry", status_code=201)
def retry(
    job_id: uuid.UUID, ctx: Member, db: Db, settings: Conf, background: BackgroundTasks
) -> dict[str, object]:
    mine = _own_professional(db, ctx)
    with db.tenant_session(ctx.tenant_id) as s:
        job = s.get(NotificationJob, job_id)
        if job is None:
            raise NotFoundError("Notifica non trovata.")
        a = s.get(Appointment, job.appointment_id)
        if a is None or (mine is not None and a.professional_id != mine):
            raise NotFoundError("Notifica non trovata.")
        if job.status not in ("failed", "skipped"):
            raise ConflictError(
                "Si può ritentare solo un messaggio non inviato.", code="non_ritentabile"
            )
        copy = service.retry(s, job)
        new_id = copy.id
    background.add_task(service.safe_process, db, settings, ctx.tenant_id)
    return {"id": str(new_id)}


@router.post("/webhooks/cron/notifiche")
def cron(request: Request, db: Db, settings: Conf) -> dict[str, int]:
    """Chiamata dal cron di cPanel (ogni 5 minuti) con l'intestazione X-Cron-Key."""
    secret = settings.cron_secret
    given = request.headers.get("x-cron-key", "")
    if secret is None:
        raise NotFoundError()
    if not hmac.compare_digest(given.encode(), secret.get_secret_value().encode()):
        raise ForbiddenError("Chiave non valida.", code="chiave_non_valida")
    return service.process_due(db, settings, limit=200)
