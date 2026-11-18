"""Notifiche email ai clienti.

Quando un appuntamento nasce, si sposta o si chiude, nella stessa transazione si aggiungono
le righe da inviare (notification_jobs). L'invio avviene subito dopo (in background) oppure
all'ora prevista per i promemoria, tramite:
- il cron di cPanel (POST /api/v1/webhooks/cron/notifiche), consigliato ogni 5 minuti;
- in più, con il sito in uso, al massimo ogni 5 minuti durante la consultazione dell'agenda.

Al momento dell'invio si ricontrollano email, consenso e stato dell'appuntamento: se qualcosa
manca il messaggio è "saltato" con il motivo, visibile allo studio. Un invio non riuscito
si ritenta fino a 3 volte.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import must
from app.core.models import utcnow
from app.models.accounts import Tenant, TenantSettings
from app.models.agenda import Appointment
from app.models.catalog import Client, Location, Professional, Service
from app.models.notifications import NotificationJob
from app.modules.email import templates
from app.modules.email.sender import OutgoingEmail, send_email

log = structlog.get_logger("notifications")

MAX_ATTEMPTS = 3
STALE_SENDING = timedelta(minutes=15)
OPPORTUNISTIC_EVERY = 300.0
ACTIVE = ("pending", "confirmed")
KIND_LABELS = {
    "confirmation": "Conferma",
    "reminder": "Promemoria",
    "rescheduled": "Appuntamento spostato",
    "cancelled": "Appuntamento annullato",
}
STATUS_LABELS = {
    "pending": "In attesa",
    "sending": "In invio",
    "sent": "Inviata",
    "failed": "Non riuscita",
    "skipped": "Non inviata",
    "cancelled": "Annullata",
}
REASON_LABELS = {
    "senza_email": "Il cliente non ha un'email",
    "senza_consenso": "Manca il consenso ai promemoria via email",
    "nessun_messaggio": "Il cliente ha scelto di non ricevere messaggi",
    "cliente_archiviato": "Cliente archiviato",
    "appuntamento_non_attivo": "Appuntamento non più attivo",
    "troppo_tardi": "L'appuntamento è già iniziato",
    "studio_sospeso": "Studio sospeso",
    "errore_invio": "Errore del server di posta",
    "interrotto": "Invio interrotto",
}

# ---------------------------------------------------------------- creazione delle notifiche


def _settings(s: Session) -> TenantSettings | None:
    return s.scalar(select(TenantSettings))


def _add(s: Session, a: Appointment, kind: str, at: datetime | None = None) -> None:
    s.add(
        NotificationJob(
            appointment_id=a.id,
            kind=kind,
            channel="email",
            status="pending",
            scheduled_at=at or utcnow(),
        )
    )


def _cancel_pending(s: Session, a: Appointment, kinds: tuple[str, ...]) -> None:
    s.execute(
        update(NotificationJob)
        .where(
            NotificationJob.appointment_id == a.id,
            NotificationJob.status == "pending",
            NotificationJob.kind.in_(kinds),
        )
        .values(status="cancelled")
    )


def _schedule_reminder(s: Session, a: Appointment, st: TenantSettings) -> None:
    if st.reminder_hours <= 0:
        return
    at = a.start_at - timedelta(hours=st.reminder_hours)
    now = utcnow()
    if at < now:
        # Appuntamento più vicino dell'anticipo scelto: il promemoria parte solo se manca
        # ancora almeno un'ora (altrimenti basta la conferma appena inviata).
        if a.start_at - now < timedelta(hours=2):
            return
        at = now + timedelta(minutes=30)
    _add(s, a, "reminder", at)


def on_created(s: Session, a: Appointment) -> None:
    st = _settings(s)
    if st is None:
        return
    if st.email_confirmations:
        _add(s, a, "confirmation")
    _schedule_reminder(s, a, st)


def on_confirmed(s: Session, a: Appointment) -> None:
    st = _settings(s)
    if st is not None and st.email_confirmations:
        _add(s, a, "confirmation")


def on_rescheduled(s: Session, a: Appointment) -> None:
    st = _settings(s)
    _cancel_pending(s, a, ("reminder", "confirmation"))
    if st is None:
        return
    if st.email_confirmations:
        _add(s, a, "rescheduled")
    _schedule_reminder(s, a, st)


def on_cancelled(s: Session, a: Appointment) -> None:
    st = _settings(s)
    _cancel_pending(s, a, ("reminder", "confirmation", "rescheduled"))
    if st is not None and st.email_confirmations:
        _add(s, a, "cancelled")


def on_closed(s: Session, a: Appointment) -> None:
    """Svolto o assente: i promemoria ancora in coda non servono più."""
    _cancel_pending(s, a, ("reminder",))


# ---------------------------------------------------------------- testi

_DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
_MONTHS = [
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
]


def italian_when(start: datetime, tz: str) -> tuple[str, str]:
    local = start.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(tz))
    return f"{_DAYS[local.weekday()]} {local.day} {_MONTHS[local.month - 1]}", local.strftime(
        "%H:%M"
    )


@dataclass
class _Context:
    a: Appointment
    client: Client | None
    svc: Service
    prof: Professional
    loc: Location
    tenant: Tenant
    st: TenantSettings


def _skip_reason(job: NotificationJob, c: _Context) -> str | None:
    if c.tenant.status in ("suspended", "cancelled"):
        return "studio_sospeso"
    if c.client is None or c.client.status != "active":
        return "cliente_archiviato"
    if not c.client.email:
        return "senza_email"
    if c.client.preferred_channel == "none":
        return "nessun_messaggio"
    if not c.client.email_consent:
        return "senza_consenso"
    if job.kind in ("confirmation", "reminder", "rescheduled") and c.a.status not in ACTIVE:
        return "appuntamento_non_attivo"
    if job.kind == "reminder" and c.a.start_at <= utcnow():
        return "troppo_tardi"
    return None


def build_email(settings: Settings, job: NotificationJob, c: _Context) -> OutgoingEmail:
    client = must(c.client)
    to = must(client.email)
    day, hour = italian_when(c.a.start_at, c.loc.timezone)
    what = "Appuntamento" if c.tenant.neutral_messaging else c.svc.name
    who = f" con {c.prof.name}"
    base = settings.app_base_url.rstrip("/")
    area = f"{base}/area-clienti"
    name = client.first_name
    place: list[str] = []
    if c.a.is_online:
        place.append(
            "Si svolge online: all'orario dell'appuntamento apri il link della videochiamata."
        )
    else:
        address = c.loc.address or c.st.address
        if address:
            place.append(f"Dove: {address}.")
    contacts = " · ".join(x for x in [c.st.contact_phone, c.st.contact_email] if x)
    after = [f"I tuoi appuntamenti e la disdetta online: {area}"]
    if c.st.cancellation_min_hours:
        after.append(f"Si può disdire fino a {c.st.cancellation_min_hours} ore prima.")
    if contacts:
        after.append(f"Per informazioni: {contacts}.")
    button: tuple[str, str] | None = (
        ("Entra nella videochiamata", c.a.video_url)
        if c.a.is_online and c.a.video_url
        else ("I tuoi appuntamenti", area)
    )
    studio = c.tenant.name
    if job.kind == "confirmation":
        pending = c.a.status == "pending"
        subject = (
            f"{'Appuntamento da confermare' if pending else 'Appuntamento confermato'} · {studio}"
        )
        title = "Appuntamento da confermare" if pending else "Appuntamento confermato"
        lines = [
            f"Ciao {name}, {studio} ha fissato per te: {what}{who}, {day} alle {hour}.",
            *place,
        ]
        if pending:
            lines.append("Lo studio ti confermerà l'orario.")
    elif job.kind == "reminder":
        subject = f"Promemoria: {day} alle {hour} · {studio}"
        title = "Promemoria appuntamento"
        lines = [
            f"Ciao {name}, ti ricordiamo l'appuntamento di {day} alle {hour}{who} presso {studio}.",
            *place,
        ]
    elif job.kind == "rescheduled":
        subject = f"Appuntamento spostato · {studio}"
        title = "Appuntamento spostato"
        lines = [
            f"Ciao {name}, il tuo appuntamento con {studio} è stato spostato "
            f"a {day} alle {hour}{who}.",
            *place,
        ]
    else:
        subject = f"Appuntamento annullato · {studio}"
        title = "Appuntamento annullato"
        lines = [
            f"Ciao {name}, l'appuntamento di {day} alle {hour} presso {studio} è stato annullato."
        ]
        button = ("I tuoi appuntamenti", area)
        after = [f"Per prenotare di nuovo contatta lo studio{': ' + contacts if contacts else '.'}"]
    return templates.appointment_message(
        to,
        subject=subject,
        title=title,
        lines=lines,
        button=button,
        after=after,
        studio=studio,
        reply_to=c.st.contact_email,
    )


# ---------------------------------------------------------------- invio


def _context(s: Session, a: Appointment) -> _Context:
    return _Context(
        a=a,
        client=s.get(Client, a.client_id),
        svc=s.get(Service, a.service_id),  # type: ignore[arg-type]
        prof=s.get(Professional, a.professional_id),  # type: ignore[arg-type]
        loc=s.get(Location, a.location_id),  # type: ignore[arg-type]
        tenant=s.get(Tenant, a.tenant_id),  # type: ignore[arg-type]
        st=s.scalar(select(TenantSettings)),  # type: ignore[arg-type]
    )


def _due(
    db: Database, tenant_id: uuid.UUID | None, limit: int
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    now = utcnow()
    with db.platform_session("notifiche: messaggi da inviare") as s:
        stmt = select(NotificationJob.id, NotificationJob.tenant_id).where(
            NotificationJob.status == "pending", NotificationJob.scheduled_at <= now
        )
        if tenant_id is not None:
            stmt = stmt.where(NotificationJob.tenant_id == tenant_id)
        return [
            (jid, tid)
            for jid, tid in s.execute(stmt.order_by(NotificationJob.scheduled_at).limit(limit))
        ]


def _stale(db: Database) -> list[tuple[uuid.UUID, uuid.UUID]]:
    with db.platform_session("notifiche: invii interrotti") as s:
        return [
            (jid, tid)
            for jid, tid in s.execute(
                select(NotificationJob.id, NotificationJob.tenant_id).where(
                    NotificationJob.status == "sending",
                    NotificationJob.scheduled_at <= utcnow() - STALE_SENDING,
                )
            )
        ]


def process_due(
    db: Database, settings: Settings, *, tenant_id: uuid.UUID | None = None, limit: int = 50
) -> dict[str, int]:
    """Invia i messaggi scaduti. Più processi insieme non inviano due volte (SKIP LOCKED)."""
    counts = {"sent": 0, "failed": 0, "skipped": 0}
    for jid, tid in _stale(db):
        with db.tenant_session(tid) as s:
            job = s.get(NotificationJob, jid, with_for_update=True)
            if job is not None and job.status == "sending":
                # Non sappiamo se l'email è partita: meglio non rischiare un doppione.
                job.status, job.reason = "failed", "interrotto"
    for jid, tid in _due(db, tenant_id, limit):
        mail: OutgoingEmail | None = None
        with db.tenant_session(tid) as s:
            job = s.scalars(
                select(NotificationJob)
                .where(NotificationJob.id == jid, NotificationJob.status == "pending")
                .with_for_update(skip_locked=True)
            ).first()
            if job is None:
                continue
            a = s.get(Appointment, job.appointment_id)
            if a is None:
                job.status, job.reason = "skipped", "appuntamento_non_attivo"
                counts["skipped"] += 1
                continue
            c = _context(s, a)
            reason = _skip_reason(job, c)
            if reason:
                job.status, job.reason = "skipped", reason
                counts["skipped"] += 1
                continue
            mail = build_email(settings, job, c)
            job.status = "sending"
            job.attempts += 1
            job.scheduled_at = utcnow()
        ok = send_email(settings, mail)
        with db.tenant_session(tid) as s:
            job = s.get(NotificationJob, jid, with_for_update=True)
            if job is None:
                continue
            if ok:
                job.status, job.sent_at, job.reason = "sent", utcnow(), None
                counts["sent"] += 1
            elif job.attempts < MAX_ATTEMPTS:
                job.status, job.reason = "pending", "errore_invio"
                job.scheduled_at = utcnow() + timedelta(minutes=10 * job.attempts)
                counts["failed"] += 1
            else:
                job.status, job.reason = "failed", "errore_invio"
                counts["failed"] += 1
    if any(counts.values()):
        log.info("notifications_processed", **counts)
    return counts


_last_run = 0.0
_run_lock = threading.Lock()


def maybe_process(db: Database, settings: Settings) -> None:
    """Invio "di passaggio" mentre il sito è in uso, al massimo ogni 5 minuti per processo."""
    global _last_run
    with _run_lock:
        if time.monotonic() - _last_run < OPPORTUNISTIC_EVERY:
            return
        _last_run = time.monotonic()
    try:
        process_due(db, settings)
    except Exception:  # un problema delle notifiche non deve mai rompere l'agenda
        log.exception("notifications_failed")


def safe_process(db: Database, settings: Settings, tenant_id: uuid.UUID) -> None:
    try:
        process_due(db, settings, tenant_id=tenant_id, limit=10)
    except Exception:
        log.exception("notifications_failed")


# ---------------------------------------------------------------- elenco per lo studio


def _job_out(job: NotificationJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "appointment_id": str(job.appointment_id),
        "kind": job.kind,
        "kind_label": KIND_LABELS[job.kind],
        "channel": job.channel,
        "status": job.status,
        "status_label": STATUS_LABELS[job.status],
        "reason": job.reason,
        "reason_label": REASON_LABELS.get(job.reason or ""),
        "scheduled_at": job.scheduled_at.isoformat() + "Z",
        "sent_at": job.sent_at.isoformat() + "Z" if job.sent_at else None,
        "attempts": job.attempts,
    }


def for_appointment(s: Session, appointment_id: uuid.UUID) -> list[dict[str, object]]:
    rows = s.scalars(
        select(NotificationJob)
        .where(NotificationJob.appointment_id == appointment_id)
        .order_by(NotificationJob.scheduled_at, NotificationJob.created_at)
    )
    return [_job_out(j) for j in rows]


def list_recent(
    s: Session, *, professional_id: uuid.UUID | None, limit: int
) -> list[dict[str, object]]:
    stmt = (
        select(NotificationJob, Appointment, Client)
        .join(Appointment, Appointment.id == NotificationJob.appointment_id)
        .join(Client, Client.id == Appointment.client_id)
        .order_by(NotificationJob.scheduled_at.desc())
        .limit(limit)
    )
    if professional_id is not None:
        stmt = stmt.where(Appointment.professional_id == professional_id)
    out = []
    for job, a, c in s.execute(stmt):
        row = _job_out(job)
        row["client_name"] = f"{c.first_name} {c.last_name}"
        row["appointment_start_at"] = a.start_at.isoformat() + "Z"
        out.append(row)
    return out


def retry(s: Session, job: NotificationJob) -> NotificationJob:
    """Nuovo tentativo di un messaggio non riuscito o saltato (es. dopo aver aggiunto l'email)."""
    copy = NotificationJob(
        appointment_id=job.appointment_id,
        kind=job.kind,
        channel=job.channel,
        status="pending",
        scheduled_at=utcnow(),
    )
    s.add(copy)
    s.flush()
    return copy
