"""Anagrafiche dello studio: sedi, professionisti, prestazioni e clienti.

Ogni funzione apre una sessione legata allo studio dell'utente (tenant_session): il filtro
automatico rende invisibili i dati degli altri studi, quindi un id di un altro studio risulta
semplicemente "non trovato".
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.db import Database
from app.core.errors import AppError, ConflictError, NotFoundError, must
from app.core.models import utcnow
from app.models.accounts import Membership, Tenant, User
from app.models.catalog import (
    Client,
    ClientConsentEvent,
    Location,
    Professional,
    Service,
    ServiceProfessional,
)
from app.modules.accounts.audit import audit
from app.modules.catalog.phone import InvalidPhoneError, to_e164
from app.modules.catalog.presets import Profile, profile_for

if TYPE_CHECKING:  # import solo per i tipi: accounts.service importa questo modulo
    from app.modules.accounts.service import AuthContext

PROFESSIONAL_ROLES = ("owner", "professional")
CONSENTS = ("whatsapp", "email", "marketing")


class InvalidDataError(AppError):
    status_code = 422
    code = "dati_non_validi"
    message = "Dati non validi."


# ---------------------------------------------------------------- creazione automatica


def ensure_professional(s: Session, user_id: uuid.UUID, name: str) -> Professional:
    """Scheda professionista collegata a un account (creata se manca)."""
    prof = s.scalar(select(Professional).where(Professional.user_id == user_id))
    if prof is None:
        prof = Professional(user_id=user_id, name=name)
        s.add(prof)
        s.flush()
    return prof


def create_default_location(s: Session, timezone: str) -> Location:
    loc = Location(name="Sede principale", timezone=timezone, is_default=True)
    s.add(loc)
    return loc


def apply_profile(s: Session, profile: Profile) -> list[Service]:
    """Aggiunge le prestazioni del profilo che lo studio non ha già (confronto per nome)."""
    existing = {n.casefold() for n in s.scalars(select(Service.name))}
    max_order = s.scalar(select(func.max(Service.sort_order))) or 0
    profs = s.scalars(select(Professional.id).where(Professional.status == "active")).all()
    created: list[Service] = []
    for i, p in enumerate(profile.services, start=1):
        if p.name.casefold() in existing:
            continue
        svc = Service(
            name=p.name,
            duration_minutes=p.duration_minutes,
            preparation_minutes=p.preparation_minutes,
            mode=p.mode,
            color=p.color,
            sort_order=max_order + i,
        )
        s.add(svc)
        s.flush()
        s.add_all(ServiceProfessional(service_id=svc.id, professional_id=pid) for pid in profs)
        created.append(svc)
    return created


# ---------------------------------------------------------------- sedi


def _location_out(loc: Location) -> dict[str, object]:
    return {
        "id": str(loc.id),
        "name": loc.name,
        "address": loc.address,
        "timezone": loc.timezone,
        "is_default": loc.is_default,
        "active": loc.active,
    }


def list_locations(db: Database, ctx: AuthContext) -> list[dict[str, object]]:
    with db.tenant_session(ctx.tenant_id) as s:
        rows = s.scalars(select(Location).order_by(Location.is_default.desc(), Location.name))
        return [_location_out(loc) for loc in rows]


def update_location(
    db: Database,
    ctx: AuthContext,
    location_id: uuid.UUID,
    changes: dict[str, Any],
    ip: str | None,
) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        loc = s.get(Location, location_id)
        if loc is None:
            raise NotFoundError("Sede non trovata.")
        if loc.is_default and changes.get("active") is False:
            raise ConflictError(
                "La sede principale non può essere disattivata.", code="sede_principale"
            )
        for key, value in changes.items():
            setattr(loc, key, value)
        audit(
            s,
            "location_updated",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="location",
            resource_id=loc.id,
            details={"fields": sorted(changes)},
        )
        s.flush()
        return _location_out(loc)


# ---------------------------------------------------------------- professionisti


def _professional_out(p: Professional, email: str | None = None) -> dict[str, object]:
    return {
        "id": str(p.id),
        "user_id": str(p.user_id) if p.user_id else None,
        "account_email": email,
        "name": p.name,
        "specialization": p.specialization,
        "color": p.color,
        "status": p.status,
        "public_booking": p.public_booking,
    }


def list_professionals(db: Database, ctx: AuthContext) -> list[dict[str, object]]:
    with db.tenant_session(ctx.tenant_id) as s:
        rows = s.execute(
            select(Professional, User.email)
            .outerjoin(User, User.id == Professional.user_id)
            .order_by(Professional.status, Professional.name)
        ).all()
        return [_professional_out(p, email) for p, email in rows]


def _check_member(s: Session, user_id: uuid.UUID) -> None:
    m = s.scalar(select(Membership).where(Membership.user_id == user_id))
    if m is None:
        raise InvalidDataError(
            "L'account scelto non fa parte dello studio.", code="account_non_valido"
        )
    if s.scalar(select(Professional).where(Professional.user_id == user_id)) is not None:
        raise ConflictError(
            "Questo account ha già una scheda professionista.", code="professionista_esistente"
        )


def create_professional(
    db: Database, ctx: AuthContext, data: dict[str, Any], ip: str | None
) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        if data.get("user_id") is not None:
            _check_member(s, data["user_id"])
        p = Professional(**data)
        s.add(p)
        s.flush()
        audit(
            s,
            "professional_created",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="professional",
            resource_id=p.id,
        )
        return _professional_out(p)


def update_professional(
    db: Database,
    ctx: AuthContext,
    professional_id: uuid.UUID,
    changes: dict[str, Any],
    ip: str | None,
) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        p = s.get(Professional, professional_id)
        if p is None:
            raise NotFoundError("Professionista non trovato.")
        new_user = changes.get("user_id")
        if new_user is not None and new_user != p.user_id:
            _check_member(s, new_user)
        for key, value in changes.items():
            setattr(p, key, value)
        audit(
            s,
            "professional_updated",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="professional",
            resource_id=p.id,
            details={"fields": sorted(changes)},
        )
        s.flush()
        return _professional_out(p)


# ---------------------------------------------------------------- prestazioni


def _service_out(svc: Service, professional_ids: Iterable[uuid.UUID]) -> dict[str, object]:
    return {
        "id": str(svc.id),
        "name": svc.name,
        "description": svc.description,
        "duration_minutes": svc.duration_minutes,
        "preparation_minutes": svc.preparation_minutes,
        "price": str(svc.price) if svc.price is not None else None,
        "color": svc.color,
        "mode": svc.mode,
        "public_visible": svc.public_visible,
        "active": svc.active,
        "sort_order": svc.sort_order,
        "professional_ids": sorted(str(p) for p in professional_ids),
    }


def _links(s: Session) -> dict[uuid.UUID, list[uuid.UUID]]:
    out: dict[uuid.UUID, list[uuid.UUID]] = {}
    for sid, pid in s.execute(
        select(ServiceProfessional.service_id, ServiceProfessional.professional_id)
    ):
        out.setdefault(sid, []).append(pid)
    return out


def list_services(db: Database, ctx: AuthContext) -> list[dict[str, object]]:
    with db.tenant_session(ctx.tenant_id) as s:
        links = _links(s)
        rows = s.scalars(
            select(Service).order_by(Service.active.desc(), Service.sort_order, Service.name)
        )
        return [_service_out(svc, links.get(svc.id, [])) for svc in rows]


def _set_professionals(s: Session, svc: Service, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    wanted = set(ids)
    if wanted:
        found = set(s.scalars(select(Professional.id).where(Professional.id.in_(wanted))))
        if found != wanted:
            raise InvalidDataError(
                "Uno dei professionisti indicati non esiste.", code="professionista_non_valido"
            )
    s.execute(delete(ServiceProfessional).where(ServiceProfessional.service_id == svc.id))
    s.add_all(ServiceProfessional(service_id=svc.id, professional_id=pid) for pid in wanted)
    return sorted(wanted)


def create_service(
    db: Database, ctx: AuthContext, data: dict[str, Any], ip: str | None
) -> dict[str, object]:
    professional_ids = data.pop("professional_ids", None)
    with db.tenant_session(ctx.tenant_id) as s:
        if "sort_order" not in data:
            data["sort_order"] = (s.scalar(select(func.max(Service.sort_order))) or 0) + 1
        svc = Service(**data)
        s.add(svc)
        s.flush()
        if professional_ids is None:
            professional_ids = list(
                s.scalars(select(Professional.id).where(Professional.status == "active"))
            )
        linked = _set_professionals(s, svc, professional_ids)
        audit(
            s,
            "service_created",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="service",
            resource_id=svc.id,
        )
        return _service_out(svc, linked)


def update_service(
    db: Database,
    ctx: AuthContext,
    service_id: uuid.UUID,
    changes: dict[str, Any],
    ip: str | None,
) -> dict[str, object]:
    professional_ids = changes.pop("professional_ids", None)
    with db.tenant_session(ctx.tenant_id) as s:
        svc = s.get(Service, service_id)
        if svc is None:
            raise NotFoundError("Prestazione non trovata.")
        for key, value in changes.items():
            setattr(svc, key, value)
        if professional_ids is not None:
            linked = _set_professionals(s, svc, professional_ids)
        else:
            linked = _links(s).get(svc.id, [])
        fields = sorted(changes) + (["professional_ids"] if professional_ids is not None else [])
        audit(
            s,
            "service_updated",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="service",
            resource_id=svc.id,
            details={"fields": fields},
        )
        s.flush()
        return _service_out(svc, linked)


def preview_profile(db: Database, ctx: AuthContext) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        tenant = must(s.get(Tenant, ctx.tenant_id))
        profile = profile_for(tenant.business_type)
        existing = {n.casefold() for n in s.scalars(select(Service.name))}
        return {
            "profile": profile.code,
            "label": profile.label,
            "services": [
                {
                    "name": p.name,
                    "duration_minutes": p.duration_minutes,
                    "preparation_minutes": p.preparation_minutes,
                    "mode": p.mode,
                    "already_present": p.name.casefold() in existing,
                }
                for p in profile.services
            ],
        }


def load_profile(db: Database, ctx: AuthContext, ip: str | None) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        tenant = must(s.get(Tenant, ctx.tenant_id))
        profile = profile_for(tenant.business_type)
        created = apply_profile(s, profile)
        audit(
            s,
            "service_profile_loaded",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            details={"profile": profile.code, "created": len(created)},
        )
        return {"profile": profile.code, "created": len(created)}


# ---------------------------------------------------------------- clienti


def _client_out(c: Client) -> dict[str, object]:
    return {
        "id": str(c.id),
        "first_name": c.first_name,
        "last_name": c.last_name,
        "phone": c.phone_e164,
        "email": c.email,
        "birth_date": c.birth_date.isoformat() if c.birth_date else None,
        "reference_professional_id": (
            str(c.reference_professional_id) if c.reference_professional_id else None
        ),
        "admin_notes": c.admin_notes,
        "preferred_channel": c.preferred_channel,
        "whatsapp_consent": c.whatsapp_consent,
        "whatsapp_consent_at": _iso(c.whatsapp_consent_at),
        "email_consent": c.email_consent,
        "email_consent_at": _iso(c.email_consent_at),
        "marketing_consent": c.marketing_consent,
        "marketing_consent_at": _iso(c.marketing_consent_at),
        "status": c.status,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


def _iso(value: Any) -> str | None:
    return value.isoformat() + "Z" if value is not None else None


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_clients(
    db: Database,
    ctx: AuthContext,
    *,
    q: str | None,
    status: str,
    limit: int,
    offset: int,
) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        stmt = select(Client).where(Client.status == status)
        for word in (q or "").split()[:4]:
            like = f"%{_escape_like(word)}%"
            conds = [
                Client.first_name.like(like, escape="\\"),
                Client.last_name.like(like, escape="\\"),
                Client.email.like(like, escape="\\"),
            ]
            digits = "".join(ch for ch in word if ch.isdigit())
            if len(digits) >= 3:
                conds.append(Client.phone_e164.like(f"%{digits}%"))
            stmt = stmt.where(or_(*conds))
        total = s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = s.scalars(
            stmt.order_by(Client.last_name, Client.first_name, Client.id)
            .limit(limit)
            .offset(offset)
        )
        return {"items": [_client_out(c) for c in rows], "total": total}


def get_client(db: Database, ctx: AuthContext, client_id: uuid.UUID) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        c = s.get(Client, client_id)
        if c is None:
            raise NotFoundError("Cliente non trovato.")
        out = _client_out(c)
        events = s.scalars(
            select(ClientConsentEvent)
            .where(ClientConsentEvent.client_id == c.id)
            .order_by(ClientConsentEvent.created_at.desc())
            .limit(50)
        )
        out["consent_history"] = [
            {
                "channel": e.channel,
                "action": e.action,
                "source": e.source,
                "at": _iso(e.created_at),
            }
            for e in events
        ]
        return out


def _normalize_contacts(data: dict[str, Any]) -> None:
    if "phone" in data:
        raw = data.pop("phone")
        try:
            data["phone_e164"] = to_e164(raw) if raw else None
        except InvalidPhoneError as exc:
            raise InvalidDataError(str(exc), code="telefono_non_valido") from exc
    if data.get("email"):
        data["email"] = data["email"].strip().lower()


def _check_reference(s: Session, professional_id: uuid.UUID | None) -> None:
    if professional_id is not None and s.get(Professional, professional_id) is None:
        raise InvalidDataError(
            "Il professionista di riferimento non esiste.", code="professionista_non_valido"
        )


def _apply_consents(
    s: Session, c: Client, consents: dict[str, bool], actor: uuid.UUID, *, new: bool
) -> list[str]:
    """Aggiorna i consensi e registra un evento per ogni cambiamento (anche alla creazione)."""
    changed: list[str] = []
    now = utcnow()
    for channel in CONSENTS:
        if channel not in consents:
            continue
        value = bool(consents[channel])
        if not new and getattr(c, f"{channel}_consent") == value:
            continue
        if new and not value:
            continue
        setattr(c, f"{channel}_consent", value)
        setattr(c, f"{channel}_consent_at", now)
        s.add(
            ClientConsentEvent(
                client_id=c.id,
                channel=channel,
                action="granted" if value else "revoked",
                source="staff",
                actor_user_id=actor,
            )
        )
        changed.append(channel)
    return changed


def _find_duplicate(
    s: Session, phone: str | None, email: str | None, exclude: uuid.UUID | None = None
) -> Client | None:
    conds = []
    if phone:
        conds.append(Client.phone_e164 == phone)
    if email:
        conds.append(Client.email == email)
    if not conds:
        return None
    stmt = select(Client).where(Client.status == "active", or_(*conds))
    if exclude is not None:
        stmt = stmt.where(Client.id != exclude)
    return s.scalars(stmt.limit(1)).first()


def create_client(
    db: Database, ctx: AuthContext, data: dict[str, Any], *, force: bool, ip: str | None
) -> dict[str, object]:
    consents = {k: data.pop(f"{k}_consent") for k in CONSENTS if f"{k}_consent" in data}
    _normalize_contacts(data)
    with db.tenant_session(ctx.tenant_id) as s:
        _check_reference(s, data.get("reference_professional_id"))
        if not force:
            dup = _find_duplicate(s, data.get("phone_e164"), data.get("email"))
            if dup is not None:
                raise ConflictError(
                    f"Esiste già un cliente con questo telefono o email: "
                    f"{dup.first_name} {dup.last_name}.",
                    code="cliente_duplicato",
                    details={"existing_id": str(dup.id)},
                )
        c = Client(**data)
        s.add(c)
        s.flush()
        _apply_consents(s, c, consents, ctx.user_id, new=True)
        audit(
            s,
            "client_created",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="client",
            resource_id=c.id,
        )
        s.flush()
        return _client_out(c)


def update_client(
    db: Database,
    ctx: AuthContext,
    client_id: uuid.UUID,
    changes: dict[str, Any],
    ip: str | None,
) -> dict[str, object]:
    consents = {k: changes.pop(f"{k}_consent") for k in CONSENTS if f"{k}_consent" in changes}
    _normalize_contacts(changes)
    with db.tenant_session(ctx.tenant_id) as s:
        c = s.get(Client, client_id)
        if c is None:
            raise NotFoundError("Cliente non trovato.")
        if "reference_professional_id" in changes:
            _check_reference(s, changes["reference_professional_id"])
        for key, value in changes.items():
            setattr(c, key, value)
        changed = _apply_consents(s, c, consents, ctx.user_id, new=False)
        # Il contenuto dei campi non finisce nel registro: solo i nomi (minimizzazione).
        audit(
            s,
            "client_updated",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="client",
            resource_id=c.id,
            details={"fields": sorted(changes), "consents": changed},
        )
        s.flush()
        return _client_out(c)


def set_client_status(
    db: Database, ctx: AuthContext, client_id: uuid.UUID, status: str, ip: str | None
) -> None:
    with db.tenant_session(ctx.tenant_id) as s:
        c = s.get(Client, client_id)
        if c is None:
            raise NotFoundError("Cliente non trovato.")
        c.status = status
        audit(
            s,
            "client_archived" if status == "archived" else "client_restored",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="client",
            resource_id=c.id,
        )
