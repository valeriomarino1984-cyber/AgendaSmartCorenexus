"""Area clienti, separata dall'area dello studio.

- Accesso senza password: il cliente inserisce l'email e riceve un link monouso (15 minuti).
  La risposta è sempre la stessa, che l'email sia di un cliente o no (nessuna enumerazione).
- Il link prova che l'indirizzo è suo: da lì vede gli appuntamenti di tutti gli studi in cui
  è registrato con quell'email (lettura di piattaforma, motivata e in sola lettura).
- La sessione dei clienti ha un cookie diverso da quella dello staff: un account dello studio
  non apre l'area clienti e un cliente non apre l'area dello studio.
- La disdetta si scrive con una sessione legata allo studio dell'appuntamento, rispettando il
  preavviso minimo impostato dallo studio.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.models import utcnow
from app.core.security import new_token, normalize_email, token_hash
from app.models.accounts import Tenant, TenantSettings
from app.models.agenda import Appointment, AppointmentEvent
from app.models.catalog import Client, Location, Professional, Service
from app.models.client_portal import ClientLoginToken, ClientSession
from app.modules.accounts import ratelimit
from app.modules.accounts.audit import audit
from app.modules.accounts.service import BLOCKED_TENANT_STATUSES, Outcome, TooManyRequestsError
from app.modules.agenda.service import STATUS_LABELS
from app.modules.email import templates

LINK_TTL = timedelta(minutes=15)
SESSION_MAX = timedelta(days=14)
SESSION_IDLE = timedelta(days=3)
TOUCH_EVERY = timedelta(minutes=5)
LINKS_PER_EMAIL = (3, timedelta(hours=1))
LINKS_PER_IP = (20, timedelta(hours=1))
PAST_LIMIT = 10


class InvalidLinkError(AppError):
    status_code = 400
    code = "link_non_valido"
    message = "Il link non è valido o è scaduto. Richiedine uno nuovo."


@dataclass(frozen=True)
class ClientContext:
    session_id: uuid.UUID
    email: str


def _iso(value: object) -> str | None:
    return value.isoformat() + "Z" if value is not None else None  # type: ignore[attr-defined]


def _studios_for(db: Database, email: str) -> list[tuple[uuid.UUID, str]]:
    with db.platform_session("area clienti: studi in cui l'email è un cliente") as s:
        rows = s.execute(
            select(Tenant.id, Tenant.name)
            .join(Client, Client.tenant_id == Tenant.id)
            .where(
                Client.email == email,
                Client.status == "active",
                Tenant.status.not_in(BLOCKED_TENANT_STATUSES),
            )
            .distinct()
        ).all()
        return [(tid, name) for tid, name in rows]


def request_link(db: Database, settings: Settings, *, email: str, ip: str | None) -> Outcome:
    email = normalize_email(email)
    outcome = Outcome()
    with db.system_session() as s:
        if not ratelimit.hit(s, "client_link_ip", ip or "-", *LINKS_PER_IP):
            raise TooManyRequestsError()
        if not ratelimit.hit(s, "client_link_email", email, *LINKS_PER_EMAIL):
            # Stessa risposta di sempre: niente indizi su quali indirizzi esistono.
            return outcome
    studios = _studios_for(db, email)
    if not studios:
        return outcome
    token = new_token()
    with db.system_session() as s:
        s.add(
            ClientLoginToken(
                email=email, token_hash=token_hash(token), expires_at=utcnow() + LINK_TTL
            )
        )
        audit(s, "client_link_requested", ip=ip, details={"studios": len(studios)})
    url = f"{settings.app_base_url.rstrip('/')}/area-clienti/entra?token={token}"
    outcome.emails.append(templates.client_login(email, url, [name for _, name in studios]))
    return outcome


def verify_link(db: Database, *, token: str, ip: str | None, user_agent: str | None) -> str:
    now = utcnow()
    with db.system_session() as s:
        row = s.scalar(
            select(ClientLoginToken)
            .where(ClientLoginToken.token_hash == token_hash(token))
            .with_for_update()
        )
        if row is None or row.used_at is not None or row.expires_at < now:
            raise InvalidLinkError()
        row.used_at = now
        session_token = new_token()
        s.add(
            ClientSession(
                email=row.email,
                token_hash=token_hash(session_token),
                created_at=now,
                last_seen_at=now,
                expires_at=now + SESSION_MAX,
                ip=ip,
                user_agent=(user_agent or "")[:255] or None,
            )
        )
        audit(s, "client_login", ip=ip)
        return session_token


def resolve(db: Database, token: str | None) -> ClientContext | None:
    if not token or len(token) > 100:
        return None
    now = utcnow()
    with db.system_session() as s:
        sess = s.scalar(select(ClientSession).where(ClientSession.token_hash == token_hash(token)))
        if sess is None or sess.revoked_at is not None or sess.expires_at <= now:
            return None
        if sess.last_seen_at < now - SESSION_IDLE:
            sess.revoked_at = now
            return None
        if sess.last_seen_at < now - TOUCH_EVERY:
            sess.last_seen_at = now
        return ClientContext(sess.id, sess.email)


def logout(db: Database, ctx: ClientContext) -> None:
    with db.system_session() as s:
        sess = s.get(ClientSession, ctx.session_id)
        if sess is not None:
            sess.revoked_at = utcnow()


def _can_cancel(a: Appointment, min_hours: int) -> bool:
    return a.status in ("pending", "confirmed") and a.start_at - utcnow() >= timedelta(
        hours=min_hours
    )


def overview(db: Database, ctx: ClientContext) -> dict[str, object]:
    now = utcnow()
    with db.platform_session("area clienti: appuntamenti del cliente") as s:
        base = (
            select(Appointment, Tenant, TenantSettings, Service, Professional, Location)
            .join(
                Client,
                (Client.tenant_id == Appointment.tenant_id) & (Client.id == Appointment.client_id),
            )
            .join(Tenant, Tenant.id == Appointment.tenant_id)
            .join(TenantSettings, TenantSettings.tenant_id == Appointment.tenant_id)
            .join(
                Service,
                (Service.tenant_id == Appointment.tenant_id)
                & (Service.id == Appointment.service_id),
            )
            .join(
                Professional,
                (Professional.tenant_id == Appointment.tenant_id)
                & (Professional.id == Appointment.professional_id),
            )
            .join(
                Location,
                (Location.tenant_id == Appointment.tenant_id)
                & (Location.id == Appointment.location_id),
            )
            .where(
                Client.email == ctx.email,
                Client.status == "active",
                Tenant.status.not_in(BLOCKED_TENANT_STATUSES),
            )
        )
        upcoming = s.execute(
            base.where(Appointment.end_at >= now).order_by(Appointment.start_at).limit(50)
        ).all()
        past = s.execute(
            base.where(Appointment.end_at < now)
            .order_by(Appointment.start_at.desc())
            .limit(PAST_LIMIT)
        ).all()

        def out(
            row: tuple[Appointment, Tenant, TenantSettings, Service, Professional, Location],
            future: bool,
        ) -> dict[str, object]:
            a, t, st, svc, prof, loc = row
            active = a.status in ("pending", "confirmed")
            return {
                "id": str(a.id),
                "code": a.public_code,
                "studio": t.name,
                "studio_phone": st.contact_phone,
                "studio_email": st.contact_email,
                "address": None if a.is_online else (loc.address or st.address),
                "timezone": loc.timezone,
                "start_at": _iso(a.start_at),
                "end_at": _iso(a.end_at),
                "service": svc.name,
                "professional": prof.name,
                "status": a.status,
                "status_label": STATUS_LABELS[a.status],
                "is_online": a.is_online,
                # Il link della stanza solo per le visite future ancora valide.
                "video_url": a.video_url if (future and active and a.is_online) else None,
                "can_cancel": future and _can_cancel(a, st.cancellation_min_hours),
                "cancellation_min_hours": st.cancellation_min_hours,
            }

        return {
            "email": ctx.email,
            "upcoming": [out(r, True) for r in upcoming],
            "past": [out(r, False) for r in past],
        }


def cancel(db: Database, ctx: ClientContext, appointment_id: uuid.UUID, ip: str | None) -> None:
    with db.platform_session("area clienti: verifica dell'appuntamento da disdire") as s:
        row = s.execute(
            select(Appointment.tenant_id)
            .join(
                Client,
                (Client.tenant_id == Appointment.tenant_id) & (Client.id == Appointment.client_id),
            )
            .where(
                Appointment.id == appointment_id,
                Client.email == ctx.email,
                Client.status == "active",
            )
        ).first()
    if row is None:
        raise NotFoundError("Appuntamento non trovato.")
    tenant_id = row[0]
    with db.tenant_session(tenant_id) as s:
        a = s.get(Appointment, appointment_id, with_for_update=True)
        st = s.scalar(select(TenantSettings))
        if a is None or st is None:
            raise NotFoundError("Appuntamento non trovato.")
        if a.status not in ("pending", "confirmed"):
            raise ConflictError(
                "L'appuntamento è già disdetto o concluso.", code="appuntamento_chiuso"
            )
        if not _can_cancel(a, st.cancellation_min_hours):
            raise ConflictError(
                f"Mancano meno di {st.cancellation_min_hours} ore: per disdire contatta lo studio.",
                code="preavviso_insufficiente",
            )
        previous = a.status
        a.status = "cancelled_by_client"
        a.cancellation_reason = "Disdetto dall'area clienti"
        a.version += 1
        s.add(
            AppointmentEvent(
                appointment_id=a.id,
                event_type="cancelled_by_client",
                actor_type="client",
                previous_value={"status": previous},
                new_value={"status": a.status},
            )
        )
        audit(
            s,
            "appointment_cancelled_by_client",
            tenant_id=tenant_id,
            ip=ip,
            resource="appointment",
            resource_id=a.id,
        )
