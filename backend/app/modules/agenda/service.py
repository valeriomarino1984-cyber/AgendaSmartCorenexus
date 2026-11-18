"""Agenda dello studio: orari settimanali, eccezioni, orari liberi e appuntamenti.

Doppie prenotazioni: MySQL/MariaDB non ha i vincoli di esclusione di PostgreSQL, quindi ogni
operazione che occupa tempo in agenda (creazione, spostamento) blocca prima la riga del
professionista con SELECT … FOR UPDATE e poi cerca sovrapposizioni con una lettura bloccante
(che vede sempre gli ultimi dati confermati, anche in REPEATABLE READ). Due prenotazioni
contemporanee sullo stesso professionista vengono così messe in fila: la seconda vede la
prima e riceve 409.

Modifiche contemporanee dello stesso appuntamento: ogni modifica deve indicare la versione
letta; se nel frattempo qualcuno l'ha cambiata, si risponde 409 invece di sovrascrivere.
"""

from __future__ import annotations

import itertools
import secrets
import string
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, must
from app.core.models import utcnow
from app.models.agenda import (
    Appointment,
    AppointmentEvent,
    Availability,
    AvailabilityException,
)
from app.models.catalog import Client, Location, Professional, Service, ServiceProfessional
from app.modules.accounts.audit import audit
from app.modules.agenda import slots as sl
from app.modules.agenda.holidays import holiday_name
from app.modules.notifications import service as notifications

if TYPE_CHECKING:
    from app.modules.accounts.service import AuthContext

# Stati che occupano l'agenda: tutti tranne le cancellazioni.
BLOCKING = ("pending", "confirmed", "completed", "no_show")
TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "cancelled_by_client", "cancelled_by_staff", "completed", "no_show"},
    "confirmed": {"cancelled_by_client", "cancelled_by_staff", "completed", "no_show"},
    "completed": {"no_show"},
    "no_show": {"completed"},
}
STATUS_LABELS = {
    "pending": "Da confermare",
    "confirmed": "Confermato",
    "cancelled_by_client": "Disdetto dal cliente",
    "cancelled_by_staff": "Cancellato dallo studio",
    "completed": "Svolto",
    "no_show": "Assente",
}
SLOT_STEP = timedelta(minutes=15)
MAX_RANGE_DAYS = 62
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_ALPHABET = string.ascii_letters + string.digits


class InvalidDataError(AppError):
    status_code = 422
    code = "dati_non_validi"
    message = "Dati non validi."


# ---------------------------------------------------------------- utilità


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value is not None else None


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise InvalidDataError("Indicare data e ora con il fuso orario.", code="orario_senza_fuso")
    return value.astimezone(UTC).replace(tzinfo=None)


def _my_professional_id(s: Session, ctx: AuthContext) -> uuid.UUID | None:
    return s.scalar(select(Professional.id).where(Professional.user_id == ctx.user_id))


def _can_manage(s: Session, ctx: AuthContext, professional_id: uuid.UUID) -> bool:
    """Titolare e segreteria gestiscono tutti; il professionista solo la propria agenda."""
    return ctx.role in ("owner", "secretary") or _my_professional_id(s, ctx) == professional_id


def _require_manage(s: Session, ctx: AuthContext, professional_id: uuid.UUID) -> None:
    if not _can_manage(s, ctx, professional_id):
        raise ForbiddenError("Puoi gestire solo la tua agenda.", code="agenda_di_altri")


def _professional(s: Session, professional_id: uuid.UUID) -> Professional:
    p = s.get(Professional, professional_id)
    if p is None:
        raise NotFoundError("Professionista non trovato.")
    return p


def _default_location(s: Session) -> Location:
    loc = s.scalars(
        select(Location).where(Location.active.is_(True)).order_by(Location.is_default.desc())
    ).first()
    if loc is None:
        raise ConflictError("Lo studio non ha una sede attiva.", code="nessuna_sede")
    return loc


def _location(s: Session, location_id: uuid.UUID | None) -> Location:
    if location_id is None:
        return _default_location(s)
    loc = s.get(Location, location_id)
    if loc is None or not loc.active:
        raise InvalidDataError("Sede non valida.", code="sede_non_valida")
    return loc


# ---------------------------------------------------------------- orari settimanali


def _rule_out(r: Availability) -> dict[str, object]:
    return {
        "id": str(r.id),
        "professional_id": str(r.professional_id),
        "location_id": str(r.location_id),
        "weekday": r.weekday,
        "start_time": r.start_time.strftime("%H:%M"),
        "end_time": r.end_time.strftime("%H:%M"),
        "valid_from": r.valid_from.isoformat() if r.valid_from else None,
        "valid_to": r.valid_to.isoformat() if r.valid_to else None,
    }


def list_weekly(
    db: Database, ctx: AuthContext, professional_id: uuid.UUID
) -> list[dict[str, object]]:
    with db.tenant_session(ctx.tenant_id) as s:
        _professional(s, professional_id)
        rows = s.scalars(
            select(Availability)
            .where(Availability.professional_id == professional_id)
            .order_by(Availability.weekday, Availability.start_time)
        )
        return [_rule_out(r) for r in rows]


def replace_weekly(
    db: Database,
    ctx: AuthContext,
    professional_id: uuid.UUID,
    rules: list[dict[str, Any]],
    location_id: uuid.UUID | None,
    ip: str | None,
) -> list[dict[str, object]]:
    """Sostituisce l'orario settimanale del professionista nella sede (editor "a settimana")."""
    by_day: dict[int, list[tuple[time, time]]] = {}
    for r in rules:
        if r["end_time"] <= r["start_time"]:
            raise InvalidDataError(
                "L'orario di fine deve essere dopo l'inizio.", code="orario_non_valido"
            )
        by_day.setdefault(r["weekday"], []).append((r["start_time"], r["end_time"]))
    for day_rules in by_day.values():
        day_rules.sort()
        for (_, end), (start, _) in itertools.pairwise(day_rules):
            if start < end:
                raise InvalidDataError(
                    "Due fasce dello stesso giorno si sovrappongono.", code="fasce_sovrapposte"
                )
    with db.tenant_session(ctx.tenant_id) as s:
        _professional(s, professional_id)
        _require_manage(s, ctx, professional_id)
        loc = _location(s, location_id)
        s.execute(
            delete(Availability).where(
                Availability.professional_id == professional_id,
                Availability.location_id == loc.id,
            )
        )
        s.add_all(
            Availability(
                professional_id=professional_id,
                location_id=loc.id,
                weekday=r["weekday"],
                start_time=r["start_time"],
                end_time=r["end_time"],
            )
            for r in rules
        )
        audit(
            s,
            "availability_updated",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="professional",
            resource_id=professional_id,
            details={"rules": len(rules)},
        )
        s.flush()
        rows = s.scalars(
            select(Availability)
            .where(Availability.professional_id == professional_id)
            .order_by(Availability.weekday, Availability.start_time)
        )
        return [_rule_out(r) for r in rows]


# ---------------------------------------------------------------- eccezioni


def _exception_out(e: AvailabilityException) -> dict[str, object]:
    return {
        "id": str(e.id),
        "professional_id": str(e.professional_id) if e.professional_id else None,
        "kind": e.kind,
        "start_at": _iso(e.start_at),
        "end_at": _iso(e.end_at),
        "reason": e.reason,
    }


def list_exceptions(
    db: Database, ctx: AuthContext, start: datetime, end: datetime
) -> list[dict[str, object]]:
    with db.tenant_session(ctx.tenant_id) as s:
        rows = s.scalars(
            select(AvailabilityException)
            .where(AvailabilityException.start_at < end, AvailabilityException.end_at > start)
            .order_by(AvailabilityException.start_at)
        )
        return [_exception_out(e) for e in rows]


def create_exception(
    db: Database, ctx: AuthContext, data: dict[str, Any], ip: str | None
) -> dict[str, object]:
    start, end = to_utc(data["start_at"]), to_utc(data["end_at"])
    if end <= start:
        raise InvalidDataError("La fine deve essere dopo l'inizio.", code="periodo_non_valido")
    if end - start > timedelta(days=366):
        raise InvalidDataError("Periodo troppo lungo (massimo un anno).", code="periodo_non_valido")
    with db.tenant_session(ctx.tenant_id) as s:
        prof_id = data.get("professional_id")
        if data["kind"] == "closure":
            if ctx.role != "owner":
                raise ForbiddenError(
                    "Solo il titolare può chiudere lo studio.", code="ruolo_insufficiente"
                )
            prof_id = None
        else:
            if prof_id is None:
                raise InvalidDataError(
                    "Indicare il professionista.", code="professionista_mancante"
                )
            _professional(s, prof_id)
            _require_manage(s, ctx, prof_id)
        e = AvailabilityException(
            professional_id=prof_id,
            kind=data["kind"],
            start_at=start,
            end_at=end,
            reason=data.get("reason"),
        )
        s.add(e)
        s.flush()
        audit(
            s,
            "availability_exception_created",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="availability_exception",
            resource_id=e.id,
            details={"kind": e.kind},
        )
        return _exception_out(e)


def delete_exception(
    db: Database, ctx: AuthContext, exception_id: uuid.UUID, ip: str | None
) -> None:
    with db.tenant_session(ctx.tenant_id) as s:
        e = s.get(AvailabilityException, exception_id)
        if e is None:
            raise NotFoundError("Eccezione non trovata.")
        if e.professional_id is None:
            if ctx.role != "owner":
                raise ForbiddenError(
                    "Solo il titolare può modificare le chiusure.", code="ruolo_insufficiente"
                )
        else:
            _require_manage(s, ctx, e.professional_id)
        s.delete(e)
        audit(
            s,
            "availability_exception_deleted",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="availability_exception",
            resource_id=exception_id,
        )


# ---------------------------------------------------------------- orari liberi


def _windows(
    s: Session, professional_id: uuid.UUID, loc: Location, first: date, last: date
) -> list[sl.Interval]:
    tz = ZoneInfo(loc.timezone)
    rules = [
        sl.WeeklyRule(r.weekday, r.start_time, r.end_time, r.valid_from, r.valid_to)
        for r in s.scalars(
            select(Availability).where(
                Availability.professional_id == professional_id,
                Availability.location_id == loc.id,
            )
        )
    ]
    period_start = sl.local_to_utc(first, time(0), tz)
    period_end = sl.local_to_utc(last + timedelta(days=1), time(0), tz)
    exceptions = s.scalars(
        select(AvailabilityException).where(
            AvailabilityException.start_at < period_end,
            AvailabilityException.end_at > period_start,
            (AvailabilityException.professional_id == professional_id)
            | AvailabilityException.professional_id.is_(None),
        )
    ).all()
    blocks = [(e.start_at, e.end_at) for e in exceptions if e.kind != "extra"]
    extras = [(e.start_at, e.end_at) for e in exceptions if e.kind == "extra"]
    return sl.open_windows(first=first, last=last, tz=tz, rules=rules, blocks=blocks, extras=extras)


def _busy(
    s: Session,
    professional_id: uuid.UUID,
    start: datetime,
    end: datetime,
    *,
    exclude: uuid.UUID | None = None,
    lock: bool = False,
) -> list[Appointment]:
    stmt = select(Appointment).where(
        Appointment.professional_id == professional_id,
        Appointment.status.in_(BLOCKING),
        Appointment.start_at < end,
        Appointment.buffer_end_at > start,
    )
    if exclude is not None:
        stmt = stmt.where(Appointment.id != exclude)
    if lock:
        stmt = stmt.with_for_update()
    return list(s.scalars(stmt))


def available_slots(
    db: Database,
    ctx: AuthContext,
    *,
    professional_id: uuid.UUID,
    service_id: uuid.UUID,
    first: date,
    last: date,
    location_id: uuid.UUID | None,
) -> dict[str, object]:
    if last < first or (last - first).days > 41:
        raise InvalidDataError("Intervallo di date non valido (massimo 6 settimane).")
    with db.tenant_session(ctx.tenant_id) as s:
        _professional(s, professional_id)
        svc = s.get(Service, service_id)
        if svc is None:
            raise NotFoundError("Prestazione non trovata.")
        loc = _location(s, location_id)
        tz = ZoneInfo(loc.timezone)
        windows = _windows(s, professional_id, loc, first, last)
        period = (
            sl.local_to_utc(first, time(0), tz),
            sl.local_to_utc(last + timedelta(days=1), time(0), tz),
        )
        busy = [(a.start_at, a.buffer_end_at) for a in _busy(s, professional_id, *period)]
        starts = sl.free_slots(
            windows,
            busy,
            duration=timedelta(minutes=svc.duration_minutes),
            preparation=timedelta(minutes=svc.preparation_minutes),
            step=SLOT_STEP,
            not_before=utcnow(),
        )
        return {
            "timezone": loc.timezone,
            "slots": [
                {"start_at": _iso(t), "local": sl.utc_to_local(t, tz).strftime("%Y-%m-%dT%H:%M")}
                for t in starts
            ],
            "holidays": [
                {"date": d.isoformat(), "name": holiday_name(d)}
                for d in sl.days_between(first, last)
                if holiday_name(d)
            ],
        }


# ---------------------------------------------------------------- appuntamenti


def _new_code(s: Session) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if s.scalar(select(Appointment.id).where(Appointment.public_code == code)) is None:
            return code
    raise RuntimeError("impossibile generare un codice appuntamento univoco")


def video_url(settings: Settings) -> str:
    """Stanza con nome casuale (~130 bit): nessun dato dello studio o del cliente nel nome."""
    room = "".join(secrets.choice(ROOM_ALPHABET) for _ in range(22))
    return f"{settings.video_base_url.rstrip('/')}/CN-{room}"


def _appointment_out(
    a: Appointment,
    client: Client | None = None,
    svc: Service | None = None,
    prof: Professional | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {
        "id": str(a.id),
        "public_code": a.public_code,
        "client_id": str(a.client_id),
        "professional_id": str(a.professional_id),
        "service_id": str(a.service_id),
        "location_id": str(a.location_id),
        "start_at": _iso(a.start_at),
        "end_at": _iso(a.end_at),
        "buffer_end_at": _iso(a.buffer_end_at),
        "duration_minutes": int((a.end_at - a.start_at).total_seconds() // 60),
        "preparation_minutes": a.preparation_minutes,
        "status": a.status,
        "status_label": STATUS_LABELS[a.status],
        "source": a.source,
        "is_online": a.is_online,
        "video_url": a.video_url,
        "price": str(a.price) if a.price is not None else None,
        "notes": a.notes,
        "cancellation_reason": a.cancellation_reason,
        "version": a.version,
    }
    if client is not None:
        out["client_name"] = f"{client.first_name} {client.last_name}"
        out["client_phone"] = client.phone_e164
    if svc is not None:
        out["service_name"] = svc.name
        out["color"] = svc.color
    if prof is not None:
        out["professional_name"] = prof.name
        out["professional_color"] = prof.color
    return out


def list_appointments(
    db: Database,
    ctx: AuthContext,
    *,
    start: datetime,
    end: datetime,
    professional_id: uuid.UUID | None,
    client_id: uuid.UUID | None,
    include_cancelled: bool,
) -> list[dict[str, object]]:
    start, end = to_utc(start), to_utc(end)
    if end <= start or end - start > timedelta(days=MAX_RANGE_DAYS):
        raise InvalidDataError("Intervallo non valido (massimo 62 giorni).")
    with db.tenant_session(ctx.tenant_id) as s:
        stmt = (
            select(Appointment, Client, Service, Professional)
            .join(Client, Client.id == Appointment.client_id)
            .join(Service, Service.id == Appointment.service_id)
            .join(Professional, Professional.id == Appointment.professional_id)
            .where(Appointment.start_at < end, Appointment.end_at > start)
            .order_by(Appointment.start_at)
        )
        if ctx.role == "professional":
            mine = _my_professional_id(s, ctx)
            stmt = stmt.where(Appointment.professional_id == mine)
        if professional_id is not None:
            stmt = stmt.where(Appointment.professional_id == professional_id)
        if client_id is not None:
            stmt = stmt.where(Appointment.client_id == client_id)
        if not include_cancelled:
            stmt = stmt.where(Appointment.status.in_(BLOCKING))
        return [_appointment_out(a, c, sv, p) for a, c, sv, p in s.execute(stmt)]


def _load_visible(s: Session, ctx: AuthContext, appointment_id: uuid.UUID) -> Appointment:
    a = s.get(Appointment, appointment_id)
    if a is None or (
        ctx.role == "professional" and _my_professional_id(s, ctx) != a.professional_id
    ):
        raise NotFoundError("Appuntamento non trovato.")
    return a


def get_appointment(db: Database, ctx: AuthContext, appointment_id: uuid.UUID) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        a = _load_visible(s, ctx, appointment_id)
        out = _appointment_out(
            a,
            s.get(Client, a.client_id),
            s.get(Service, a.service_id),
            s.get(Professional, a.professional_id),
        )
        events = s.scalars(
            select(AppointmentEvent)
            .where(AppointmentEvent.appointment_id == a.id)
            .order_by(AppointmentEvent.occurred_at)
        )
        out["notifications"] = notifications.for_appointment(s, a.id)
        out["events"] = [
            {
                "type": e.event_type,
                "actor_type": e.actor_type,
                "at": _iso(e.occurred_at),
                "previous": e.previous_value,
                "new": e.new_value,
            }
            for e in events
        ]
        return out


def _check_service(s: Session, svc_id: uuid.UUID, prof_id: uuid.UUID) -> Service:
    svc = s.get(Service, svc_id)
    if svc is None or not svc.active:
        raise InvalidDataError(
            "Prestazione non valida o disattivata.", code="prestazione_non_valida"
        )
    enabled = s.scalar(
        select(ServiceProfessional.id).where(
            ServiceProfessional.service_id == svc_id,
            ServiceProfessional.professional_id == prof_id,
        )
    )
    if enabled is None:
        raise InvalidDataError(
            "Il professionista non è abilitato a questa prestazione.",
            code="prestazione_non_abilitata",
        )
    return svc


def _online(svc: Service, requested: bool | None) -> bool:
    if svc.mode == "online":
        return True
    if svc.mode == "in_person":
        if requested:
            raise InvalidDataError(
                "Questa prestazione si svolge solo in studio.", code="modalita_non_valida"
            )
        return False
    return bool(requested)


def _lock_professionals(s: Session, ids: set[uuid.UUID]) -> None:
    # Ordine fisso: due operazioni che bloccano gli stessi professionisti non si incrociano.
    for pid in sorted(ids, key=str):
        s.scalar(select(Professional.id).where(Professional.id == pid).with_for_update())


def _check_slot(
    s: Session,
    *,
    professional_id: uuid.UUID,
    loc: Location,
    start: datetime,
    end: datetime,
    buffer_end: datetime,
    exclude: uuid.UUID | None,
    force: bool,
) -> None:
    clash = _busy(s, professional_id, start, buffer_end, exclude=exclude, lock=True)
    if clash:
        tz = ZoneInfo(loc.timezone)
        other = clash[0]
        when = sl.utc_to_local(other.start_at, tz).strftime("%H:%M")
        raise ConflictError(
            f"Orario già occupato: c'è un altro appuntamento alle {when}.",
            code="orario_occupato",
            details={"appointment_id": str(other.id)},
        )
    if force:
        return
    tz = ZoneInfo(loc.timezone)
    local_start = sl.utc_to_local(start, tz).date()
    local_end = sl.utc_to_local(end, tz).date()
    windows = _windows(s, professional_id, loc, local_start, local_end)
    if not sl.within(windows, (start, end)):
        holiday = holiday_name(local_start)
        reason = f"è {holiday}" if holiday else "è fuori dall'orario di lavoro"
        raise ConflictError(
            f"L'appuntamento {reason}. Confermi comunque?",
            code="fuori_orario",
        )


def _event(
    s: Session,
    a: Appointment,
    ctx: AuthContext,
    event_type: str,
    previous: dict[str, object] | None = None,
    new: dict[str, object] | None = None,
) -> None:
    s.add(
        AppointmentEvent(
            appointment_id=a.id,
            event_type=event_type,
            actor_type="staff",
            actor_user_id=ctx.user_id,
            previous_value=previous,
            new_value=new,
        )
    )


def create_appointment(
    db: Database, settings: Settings, ctx: AuthContext, data: dict[str, Any]
) -> dict[str, object]:
    start = to_utc(data["start_at"])
    with db.tenant_session(ctx.tenant_id) as s:
        prof_id: uuid.UUID = data["professional_id"]
        # Il lock va preso per primo: le letture successive vedono i dati più recenti.
        _lock_professionals(s, {prof_id})
        prof = _professional(s, prof_id)
        _require_manage(s, ctx, prof_id)
        if prof.status != "active":
            raise InvalidDataError(
                "Il professionista non è attivo.", code="professionista_inattivo"
            )
        client = s.get(Client, data["client_id"])
        if client is None or client.status != "active":
            raise InvalidDataError("Cliente non valido o archiviato.", code="cliente_non_valido")
        svc = _check_service(s, data["service_id"], prof_id)
        loc = _location(s, data.get("location_id"))
        duration = data.get("duration_minutes") or svc.duration_minutes
        end = start + timedelta(minutes=duration)
        buffer_end = end + timedelta(minutes=svc.preparation_minutes)
        if start < utcnow() - timedelta(days=366):
            raise InvalidDataError("Data troppo nel passato.", code="data_non_valida")
        _check_slot(
            s,
            professional_id=prof_id,
            loc=loc,
            start=start,
            end=end,
            buffer_end=buffer_end,
            exclude=None,
            force=bool(data.get("force")),
        )
        online = _online(svc, data.get("is_online"))
        a = Appointment(
            public_code=_new_code(s),
            client_id=client.id,
            professional_id=prof_id,
            service_id=svc.id,
            location_id=loc.id,
            start_at=start,
            end_at=end,
            preparation_minutes=svc.preparation_minutes,
            buffer_end_at=buffer_end,
            status=data.get("status") or "confirmed",
            source="staff",
            is_online=online,
            video_url=video_url(settings) if online else None,
            price=data["price"] if data.get("price") is not None else svc.price,
            notes=data.get("notes"),
            created_by=ctx.user_id,
        )
        s.add(a)
        s.flush()
        _event(s, a, ctx, "created", new={"start_at": _iso(start), "status": a.status})
        notifications.on_created(s, a)
        s.flush()
        return _appointment_out(a, client, svc, prof)


def update_appointment(
    db: Database,
    settings: Settings,
    ctx: AuthContext,
    appointment_id: uuid.UUID,
    version: int,
    changes: dict[str, Any],
) -> dict[str, object]:
    force = bool(changes.pop("force", False))
    with db.tenant_session(ctx.tenant_id) as s:
        current = _load_visible(s, ctx, appointment_id)
        new_prof: uuid.UUID = changes.get("professional_id") or current.professional_id
        _lock_professionals(s, {current.professional_id, new_prof})
        s.refresh(current, with_for_update=True)
        a = current
        if a.version != version:
            raise ConflictError(
                "L'appuntamento è stato modificato da qualcun altro: ricarica e riprova.",
                code="modificato_da_altri",
            )
        _require_manage(s, ctx, a.professional_id)
        _require_manage(s, ctx, new_prof)
        if a.status not in ("pending", "confirmed"):
            raise ConflictError(
                "Un appuntamento cancellato o concluso non si può modificare.",
                code="appuntamento_chiuso",
            )
        before: dict[str, object] = {
            "start_at": _iso(a.start_at),
            "professional_id": str(a.professional_id),
        }
        prof = _professional(s, new_prof)
        if new_prof != a.professional_id and prof.status != "active":
            raise InvalidDataError(
                "Il professionista non è attivo.", code="professionista_inattivo"
            )
        svc_id = changes.get("service_id") or a.service_id
        if svc_id != a.service_id or new_prof != a.professional_id:
            svc = _check_service(s, svc_id, new_prof)
        else:
            svc = must(s.get(Service, svc_id))
        if "client_id" in changes and changes["client_id"] != a.client_id:
            c = s.get(Client, changes["client_id"])
            if c is None or c.status != "active":
                raise InvalidDataError(
                    "Cliente non valido o archiviato.", code="cliente_non_valido"
                )
            a.client_id = c.id
        start = to_utc(changes["start_at"]) if changes.get("start_at") else a.start_at
        if changes.get("duration_minutes"):
            duration = changes["duration_minutes"]
        elif svc_id != a.service_id:
            duration = svc.duration_minutes
        else:
            duration = int((a.end_at - a.start_at).total_seconds() // 60)
        prep = svc.preparation_minutes if svc_id != a.service_id else a.preparation_minutes
        end = start + timedelta(minutes=duration)
        buffer_end = end + timedelta(minutes=prep)
        moved = (start, end, new_prof) != (a.start_at, a.end_at, a.professional_id) or (
            buffer_end != a.buffer_end_at
        )
        if moved:
            _check_slot(
                s,
                professional_id=new_prof,
                loc=s.get(Location, a.location_id) or _default_location(s),
                start=start,
                end=end,
                buffer_end=buffer_end,
                exclude=a.id,
                force=force,
            )
        online = _online(svc, changes.get("is_online", a.is_online if svc.mode == "both" else None))
        a.start_at, a.end_at, a.buffer_end_at = start, end, buffer_end
        a.professional_id, a.service_id, a.preparation_minutes = new_prof, svc.id, prep
        if online and not a.video_url:
            a.video_url = video_url(settings)
        if not online:
            a.video_url = None
        a.is_online = online
        if "notes" in changes:
            a.notes = changes["notes"]
        if "price" in changes:
            a.price = changes["price"]
        a.version += 1
        after: dict[str, object] = {
            "start_at": _iso(a.start_at),
            "professional_id": str(a.professional_id),
        }
        _event(s, a, ctx, "rescheduled" if moved else "updated", before, after)
        if moved:
            notifications.on_rescheduled(s, a)
        s.flush()
        return _appointment_out(a, s.get(Client, a.client_id), svc, prof)


def set_status(
    db: Database,
    ctx: AuthContext,
    appointment_id: uuid.UUID,
    version: int,
    status: str,
    reason: str | None,
) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        a = _load_visible(s, ctx, appointment_id)
        s.refresh(a, with_for_update=True)
        if a.version != version:
            raise ConflictError(
                "L'appuntamento è stato modificato da qualcun altro: ricarica e riprova.",
                code="modificato_da_altri",
            )
        _require_manage(s, ctx, a.professional_id)
        if status not in TRANSITIONS.get(a.status, set()):
            raise ConflictError(
                f"Non si può passare da «{STATUS_LABELS[a.status]}» a «{STATUS_LABELS[status]}».",
                code="cambio_stato_non_valido",
            )
        if status in ("completed", "no_show") and a.start_at > utcnow():
            raise ConflictError(
                "Un appuntamento futuro non può essere segnato come svolto o assente.",
                code="appuntamento_futuro",
            )
        previous = a.status
        a.status = status
        if status.startswith("cancelled"):
            a.cancellation_reason = reason
        a.version += 1
        _event(s, a, ctx, status, {"status": previous}, {"status": status})
        if status == "confirmed":
            notifications.on_confirmed(s, a)
        elif status.startswith("cancelled"):
            notifications.on_cancelled(s, a)
        else:
            notifications.on_closed(s, a)
        s.flush()
        return _appointment_out(
            a,
            s.get(Client, a.client_id),
            s.get(Service, a.service_id),
            s.get(Professional, a.professional_id),
        )
