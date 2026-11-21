"""Prenotazione online: pagina pubblica dello studio, orari liberi e prenotazione del cliente.

- La pagina esiste solo se lo studio l'ha attivata ed è attivo o in prova.
- Si vedono solo prestazioni "prenotabili online" con almeno un professionista prenotabile.
- Gli orari liberi usano lo stesso calcolo dell'agenda, con il preavviso minimo e il limite
  di giorni scelti dallo studio. La prenotazione accetta solo un orario davvero proposto.
- Nessuna doppia prenotazione: stesso blocco del professionista dell'agenda.
- Un doppio invio con la stessa chiave restituisce la stessa prenotazione (booking_key).
- Il cliente è riconosciuto dall'email: niente schede doppie. I consensi si aggiungono, mai
  si tolgono da qui; ogni consenso dato crea un evento con origine "public_booking".
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import AppError, ConflictError, NotFoundError, must
from app.core.models import utcnow
from app.core.security import normalize_email
from app.models.accounts import Tenant, TenantSettings
from app.models.agenda import Appointment, AppointmentEvent
from app.models.catalog import (
    Client,
    ClientConsentEvent,
    Location,
    Professional,
    Service,
    ServiceProfessional,
)
from app.modules.accounts import ratelimit
from app.modules.accounts.service import BLOCKED_TENANT_STATUSES, TooManyRequestsError
from app.modules.agenda import service as agenda
from app.modules.agenda import slots as sl
from app.modules.agenda.service import SLOT_STEP, STATUS_LABELS
from app.modules.catalog.phone import InvalidPhoneError, to_e164
from app.modules.notifications import service as notifications

BOOKINGS_PER_IP = (10, timedelta(hours=1))
BOOKINGS_PER_EMAIL = (5, timedelta(days=1))
MAX_RANGE_DAYS = 14


class InvalidBookingError(AppError):
    status_code = 422
    code = "dati_non_validi"
    message = "Dati non validi."


# ---------------------------------------------------------------- studio


def _tenant(db: Database, slug: str) -> Tenant:
    with db.system_session() as s:
        t = s.scalar(select(Tenant).where(Tenant.slug == slug))
        if t is None or t.status in BLOCKED_TENANT_STATUSES:
            raise NotFoundError("Pagina di prenotazione non trovata.")
        s.expunge(t)
        return t


def _open(s: Session) -> TenantSettings:
    st: TenantSettings | None = s.scalar(select(TenantSettings))
    if st is None or not st.online_booking_enabled:
        raise NotFoundError("Pagina di prenotazione non trovata.")
    return st


def _bookable(
    s: Session,
) -> tuple[list[Service], list[Professional], dict[uuid.UUID, list[uuid.UUID]]]:
    profs = list(
        s.scalars(
            select(Professional)
            .where(Professional.status == "active", Professional.public_booking.is_(True))
            .order_by(Professional.name)
        )
    )
    prof_ids = {p.id for p in profs}
    links: dict[uuid.UUID, list[uuid.UUID]] = {}
    for sid, pid in s.execute(
        select(ServiceProfessional.service_id, ServiceProfessional.professional_id)
    ):
        if pid in prof_ids:
            links.setdefault(sid, []).append(pid)
    services = [
        svc
        for svc in s.scalars(
            select(Service)
            .where(Service.active.is_(True), Service.public_visible.is_(True))
            .order_by(Service.sort_order, Service.name)
        )
        if links.get(svc.id)
    ]
    used = {pid for svc in services for pid in links[svc.id]}
    return services, [p for p in profs if p.id in used], links


def studio(db: Database, slug: str) -> dict[str, object]:
    t = _tenant(db, slug)
    with db.tenant_session(t.id) as s:
        st = _open(s)
        loc = agenda._default_location(s)
        services, profs, links = _bookable(s)
        return {
            "name": t.name,
            "slug": t.slug,
            "timezone": loc.timezone,
            "address": loc.address or st.address,
            "phone": st.contact_phone,
            "email": st.contact_email,
            "cancellation_min_hours": st.cancellation_min_hours,
            "days_ahead": st.online_booking_days_ahead,
            "requires_confirmation": st.online_booking_requires_confirmation,
            "services": [
                {
                    "id": str(svc.id),
                    "name": svc.name,
                    "description": svc.description,
                    "duration_minutes": svc.duration_minutes,
                    "mode": svc.mode,
                    "price": str(svc.price) if svc.price is not None else None,
                    "color": svc.color,
                    "professional_ids": sorted(str(p) for p in links[svc.id]),
                }
                for svc in services
            ],
            "professionals": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "specialization": p.specialization,
                    "color": p.color,
                }
                for p in profs
            ],
        }


# ---------------------------------------------------------------- orari liberi


def _limits(st: TenantSettings, tz: ZoneInfo) -> tuple[datetime, date]:
    """Primo istante prenotabile (UTC) e ultimo giorno prenotabile (locale)."""
    not_before = utcnow() + timedelta(hours=st.online_booking_min_notice_hours)
    today = sl.utc_to_local(utcnow(), tz).date()
    return not_before, today + timedelta(days=st.online_booking_days_ahead)


def _candidates(
    s: Session, svc_id: uuid.UUID, professional_id: uuid.UUID | None
) -> tuple[Service, list[uuid.UUID]]:
    services, _, links = _bookable(s)
    svc = next((x for x in services if x.id == svc_id), None)
    if svc is None:
        raise InvalidBookingError(
            "Prestazione non disponibile online.", code="prestazione_non_valida"
        )
    pids = links[svc.id]
    if professional_id is not None:
        if professional_id not in pids:
            raise InvalidBookingError(
                "Professionista non disponibile per questa prestazione.",
                code="professionista_non_valido",
            )
        pids = [professional_id]
    return svc, pids


def _free(
    s: Session,
    svc: Service,
    pid: uuid.UUID,
    loc: Location,
    first: date,
    last: date,
    not_before: datetime,
    exclude_lock: bool = False,
) -> list[datetime]:
    tz = ZoneInfo(loc.timezone)
    windows = agenda._windows(s, pid, loc, first, last)
    period = (
        sl.local_to_utc(first, time(0), tz),
        sl.local_to_utc(last + timedelta(days=1), time(0), tz),
    )
    busy = [(a.start_at, a.buffer_end_at) for a in agenda._busy(s, pid, *period, lock=exclude_lock)]
    return sl.free_slots(
        windows,
        busy,
        duration=timedelta(minutes=svc.duration_minutes),
        preparation=timedelta(minutes=svc.preparation_minutes),
        step=SLOT_STEP,
        not_before=not_before,
    )


def slots(
    db: Database,
    slug: str,
    *,
    service_id: uuid.UUID,
    professional_id: uuid.UUID | None,
    first: date,
    last: date,
) -> dict[str, object]:
    t = _tenant(db, slug)
    with db.tenant_session(t.id) as s:
        st = _open(s)
        loc = agenda._default_location(s)
        tz = ZoneInfo(loc.timezone)
        not_before, last_day = _limits(st, tz)
        today = sl.utc_to_local(utcnow(), tz).date()
        first = max(first, today)
        last = min(last, last_day, first + timedelta(days=MAX_RANGE_DAYS - 1))
        svc, pids = _candidates(s, service_id, professional_id)
        by_start: dict[datetime, list[str]] = {}
        if first <= last:
            for pid in pids:
                for start in _free(s, svc, pid, loc, first, last, not_before):
                    by_start.setdefault(start, []).append(str(pid))
        days: dict[str, list[dict[str, object]]] = {}
        for start in sorted(by_start):
            local = sl.utc_to_local(start, tz)
            days.setdefault(local.date().isoformat(), []).append(
                {
                    "start_at": start.isoformat() + "Z",
                    "time": local.strftime("%H:%M"),
                    "professional_ids": by_start[start],
                }
            )
        return {
            "timezone": loc.timezone,
            "first": first.isoformat(),
            "last_bookable_day": last_day.isoformat(),
            "days": days,
        }


# ---------------------------------------------------------------- prenotazione


def _summary(
    a: Appointment, t: Tenant, svc: Service, prof: Professional, loc: Location
) -> dict[str, object]:
    return {
        "code": a.public_code,
        "status": a.status,
        "status_label": STATUS_LABELS[a.status],
        "start_at": a.start_at.isoformat() + "Z",
        "end_at": a.end_at.isoformat() + "Z",
        "timezone": loc.timezone,
        "studio": t.name,
        "service": svc.name,
        "professional": prof.name,
        "is_online": a.is_online,
        "address": None if a.is_online else loc.address,
    }


def _existing(db: Database, tenant: Tenant, key: str) -> dict[str, object] | None:
    with db.tenant_session(tenant.id) as s:
        a = s.scalar(select(Appointment).where(Appointment.booking_key == key))
        if a is None:
            return None
        return _summary(
            a,
            tenant,
            must(s.get(Service, a.service_id)),
            must(s.get(Professional, a.professional_id)),
            must(s.get(Location, a.location_id)),
        )


def _client(s: Session, data: dict[str, Any], phone: str | None) -> Client:
    email = normalize_email(data["email"])
    c = s.scalars(
        select(Client)
        .where(Client.email == email, Client.status == "active")
        .order_by(Client.created_at)
    ).first()
    if c is None:
        c = Client(
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            email=email,
            phone_e164=phone,
            preferred_channel="email",
        )
        s.add(c)
        s.flush()
    elif phone and not c.phone_e164:
        c.phone_e164 = phone
    now = utcnow()
    for channel in ("email", "marketing"):
        if data.get(f"{channel}_consent") and not getattr(c, f"{channel}_consent"):
            setattr(c, f"{channel}_consent", True)
            setattr(c, f"{channel}_consent_at", now)
            s.add(
                ClientConsentEvent(
                    client_id=c.id, channel=channel, action="granted", source="public_booking"
                )
            )
    return c


def book(
    db: Database, settings: Settings, slug: str, data: dict[str, Any], ip: str | None
) -> dict[str, object]:
    t = _tenant(db, slug)
    if data.get("website"):  # campo nascosto: lo compilano solo i programmi automatici
        raise InvalidBookingError("Richiesta non valida.")
    try:
        phone = to_e164(data["phone"]) if data.get("phone") else None
    except InvalidPhoneError as exc:
        raise InvalidBookingError(str(exc), code="telefono_non_valido") from exc
    key = data["booking_key"]
    previous = _existing(db, t, key)
    if previous is not None:
        return previous
    email = normalize_email(data["email"])
    with db.system_session() as s:
        if not ratelimit.hit(s, "public_booking_ip", ip or "-", *BOOKINGS_PER_IP):
            raise TooManyRequestsError()
        if not ratelimit.hit(s, "public_booking_email", f"{t.id}:{email}", *BOOKINGS_PER_EMAIL):
            raise TooManyRequestsError(
                "Hai già fatto diverse prenotazioni oggi: per altre contatta lo studio."
            )
    start = agenda.to_utc(data["start_at"])

    with db.tenant_session(t.id) as s:
        _open(s)
        _, pids = _candidates(s, data["service_id"], data.get("professional_id"))
    # Con "qualsiasi professionista" si prova chi è libero a quell'ora, uno alla volta.
    last_conflict: AppError | None = None
    for pid in pids:
        try:
            return _book_with(db, settings, t, pid, data, start, phone, key)
        except ConflictError as exc:
            last_conflict = exc
        except IntegrityError:
            # Stesso invio arrivato due volte nello stesso istante: vale il primo.
            existing = _existing(db, t, key)
            if existing is not None:
                return existing
            raise
    raise last_conflict or ConflictError(
        "Orario non più disponibile.", code="orario_non_disponibile"
    )


def _book_with(
    db: Database,
    settings: Settings,
    t: Tenant,
    pid: uuid.UUID,
    data: dict[str, Any],
    start: datetime,
    phone: str | None,
    key: str,
) -> dict[str, object]:
    with db.tenant_session(t.id) as s:
        agenda._lock_professionals(s, {pid})
        st = _open(s)
        loc = agenda._default_location(s)
        tz = ZoneInfo(loc.timezone)
        svc, _ = _candidates(s, data["service_id"], pid)
        not_before, last_day = _limits(st, tz)
        day = sl.utc_to_local(start, tz).date()
        if day > last_day:
            raise InvalidBookingError(
                "Giorno non prenotabile online.", code="giorno_non_prenotabile"
            )
        # Solo un orario davvero proposto: dentro l'orario di lavoro, libero, con il preavviso.
        if start not in _free(s, svc, pid, loc, day, day, not_before, exclude_lock=True):
            raise ConflictError(
                "Questo orario non è più disponibile: scegline un altro.",
                code="orario_non_disponibile",
            )
        client = _client(s, data, phone)
        prof = must(s.get(Professional, pid))
        end = start + timedelta(minutes=svc.duration_minutes)
        online = svc.mode == "online" or (svc.mode == "both" and bool(data.get("is_online")))
        a = Appointment(
            public_code=agenda._new_code(s),
            client_id=client.id,
            professional_id=pid,
            service_id=svc.id,
            location_id=loc.id,
            start_at=start,
            end_at=end,
            preparation_minutes=svc.preparation_minutes,
            buffer_end_at=end + timedelta(minutes=svc.preparation_minutes),
            status="pending" if st.online_booking_requires_confirmation else "confirmed",
            source="public_booking",
            is_online=online,
            video_url=agenda.video_url(settings) if online else None,
            price=svc.price,
            notes=(data.get("notes") or None),
            booking_key=key,
        )
        s.add(a)
        s.flush()
        s.add(
            AppointmentEvent(
                appointment_id=a.id,
                event_type="created",
                actor_type="client",
                new_value={
                    "start_at": a.start_at.isoformat() + "Z",
                    "status": a.status,
                    "source": "public_booking",
                },
            )
        )
        notifications.on_created(s, a)
        s.flush()
        return _summary(a, t, svc, prof, loc)
