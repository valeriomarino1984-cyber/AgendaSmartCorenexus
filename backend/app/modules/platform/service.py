"""Area piattaforma CoreNexus: accesso del personale e gestione degli studi.

Accesso:
- personale nominativo, password + codice a 6 cifre (app di autenticazione) a ogni accesso;
- la prima persona si configura con l'email in PLATFORM_BOOTSTRAP_EMAIL (solo se non esiste
  ancora nessun account), le altre si invitano dal pannello;
- sessione separata (cookie proprio), 30 minuti senza attività, al massimo 12 ore;
- senza PLATFORM_SECRET_KEY l'area è spenta (503).

Privacy: dagli studi si leggono dati amministrativi e conteggi, mai nomi di clienti o
appuntamenti. Ogni azione finisce nel registro (audit_logs, azioni "platform_*").
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    must,
)
from app.core.models import utcnow
from app.core.security import (
    hash_password,
    new_token,
    normalize_email,
    password_problem,
    token_hash,
    verify_password,
)
from app.models.accounts import AuditLog, BusinessType, Membership, Tenant, TenantSettings, User
from app.models.agenda import Appointment
from app.models.catalog import Client, Professional, Service
from app.models.platform import PlatformSession, PlatformStaff, PlatformToken
from app.modules.accounts import ratelimit
from app.modules.accounts import service as accounts
from app.modules.accounts.audit import audit
from app.modules.accounts.service import (
    InvalidInputError,
    Outcome,
    TooManyRequestsError,
    UnauthorizedError,
)
from app.modules.catalog import service as catalog
from app.modules.catalog.presets import profile_for
from app.modules.email import templates
from app.modules.platform import totp

INVITE_TTL = timedelta(hours=24)
MFA_WINDOW = timedelta(minutes=5)
SESSION_IDLE = timedelta(minutes=30)
SESSION_MAX = timedelta(hours=12)
MFA_MAX_FAILURES = 5
LOGIN_FAILS_PER_EMAIL = (5, timedelta(minutes=15))
LOGIN_FAILS_PER_IP = (20, timedelta(minutes=15))
SETUP_PER_IP = (5, timedelta(hours=1))
TENANT_STATUSES = ("trial", "active", "suspended", "cancelled")


@dataclass(frozen=True)
class StaffContext:
    session_id: uuid.UUID
    staff_id: uuid.UUID
    email: str
    full_name: str


class CodeError(AppError):
    status_code = 401
    code = "codice_errato"
    message = "Codice non valido. Controlla l'app e riprova."


# ---------------------------------------------------------------- utilità


def _key(settings: Settings) -> bytes:
    key = settings.platform_secret_key
    if key is None or len(key.get_secret_value()) < 32:
        raise ServiceUnavailableError(
            "L'area piattaforma non è ancora configurata (manca PLATFORM_SECRET_KEY).",
            code="piattaforma_spenta",
        )
    return key.get_secret_value().encode()


def _secret(settings: Settings, staff: PlatformStaff) -> bytes:
    return totp.derive_secret(_key(settings), staff.totp_salt)


def _p_audit(
    s: Session,
    action: str,
    staff_id: uuid.UUID | None,
    ip: str | None,
    *,
    tenant_id: uuid.UUID | None = None,
    resource: str | None = None,
    resource_id: uuid.UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    """Registro delle azioni della piattaforma: chi (staff_id), cosa, su quale studio."""
    data: dict[str, object] = dict(details or {})
    data["staff_id"] = str(staff_id) if staff_id else None
    audit(
        s,
        f"platform_{action}",
        tenant_id=tenant_id,
        resource=resource,
        resource_id=resource_id,
        details=data,
        ip=ip,
    )


def _invite_url(settings: Settings, token: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/piattaforma/invito?token={token}"


def _new_invite(s: Session, staff: PlatformStaff) -> str:
    for old in s.scalars(
        select(PlatformToken).where(
            PlatformToken.staff_id == staff.id, PlatformToken.used_at.is_(None)
        )
    ):
        old.used_at = utcnow()
    token = new_token()
    s.add(
        PlatformToken(
            staff_id=staff.id, token_hash=token_hash(token), expires_at=utcnow() + INVITE_TTL
        )
    )
    return token


def status(db: Database, settings: Settings) -> dict[str, object]:
    """Stato dell'area per la pagina di accesso (nessun dato personale)."""
    configured = settings.platform_secret_key is not None
    with db.system_session() as s:
        has_staff = (s.scalar(select(func.count()).select_from(PlatformStaff)) or 0) > 0
    return {
        "configured": configured,
        "setup_available": configured and not has_staff and bool(settings.platform_bootstrap_email),
    }


# ---------------------------------------------------------------- prima configurazione e inviti


def request_setup(db: Database, settings: Settings, *, email: str, ip: str | None) -> Outcome:
    """Prima persona: solo se non c'è nessun account e l'email è quella configurata."""
    _key(settings)
    outcome = Outcome()
    email = normalize_email(email)
    with db.system_session() as s:
        if not ratelimit.hit(s, "platform_setup_ip", ip or "-", *SETUP_PER_IP):
            raise TooManyRequestsError()
        if (s.scalar(select(func.count()).select_from(PlatformStaff)) or 0) > 0:
            return outcome
        expected = normalize_email(settings.platform_bootstrap_email or "")
        if not expected or email != expected:
            return outcome
        staff = PlatformStaff(
            email=email, full_name=email.split("@")[0], totp_salt=secrets.token_hex(16)
        )
        s.add(staff)
        s.flush()
        token = _new_invite(s, staff)
        _p_audit(s, "setup_requested", staff.id, ip)
        outcome.emails.append(
            templates.platform_invite(email, staff.full_name, _invite_url(settings, token), True)
        )
    return outcome


def _invite_row(s: Session, token: str) -> tuple[PlatformToken, PlatformStaff]:
    row = s.scalar(
        select(PlatformToken).where(PlatformToken.token_hash == token_hash(token)).with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at < utcnow():
        raise InvalidInputError("Il link non è valido o è scaduto.", code="link_non_valido")
    staff = must(s.get(PlatformStaff, row.staff_id))
    if staff.status == "disabled":
        raise InvalidInputError("Il link non è valido o è scaduto.", code="link_non_valido")
    return row, staff


def invite_info(db: Database, settings: Settings, token: str) -> dict[str, object]:
    """Dati per la pagina di invito, compreso l'indirizzo da mostrare come QR."""
    with db.system_session() as s:
        _, staff = _invite_row(s, token)
        secret = _secret(settings, staff)
        return {
            "email": staff.email,
            "full_name": staff.full_name,
            "otpauth_uri": totp.otpauth_uri(secret, staff.email),
            "secret": totp.b32(secret),
        }


def accept_invite(
    db: Database,
    settings: Settings,
    *,
    token: str,
    full_name: str,
    password: str,
    code: str,
    ip: str | None,
    user_agent: str | None,
) -> str:
    with db.system_session() as s:
        row, staff = _invite_row(s, token)
        problem = password_problem(password, email=staff.email, full_name=full_name)
        if problem:
            raise InvalidInputError(problem, code="password_debole")
        step = totp.verify(_secret(settings, staff), code, time.time(), staff.last_totp_step)
        if step is None:
            raise CodeError(
                "Il codice non corrisponde: controlla di aver aggiunto l'account nell'app."
            )
        now = utcnow()
        row.used_at = now
        staff.full_name = full_name.strip()
        staff.password_hash = hash_password(password)
        staff.totp_confirmed_at = now
        staff.last_totp_step = step
        staff.status = "active"
        staff.last_login_at = now
        session_token = new_token()
        s.add(
            PlatformSession(
                staff_id=staff.id,
                token_hash=token_hash(session_token),
                mfa_passed_at=now,
                created_at=now,
                last_seen_at=now,
                expires_at=now + SESSION_MAX,
                ip=ip,
                user_agent=(user_agent or "")[:255] or None,
            )
        )
        _p_audit(s, "invite_accepted", staff.id, ip)
        return session_token


# ---------------------------------------------------------------- accesso


def login(
    db: Database, *, email: str, password: str, ip: str | None, user_agent: str | None
) -> str:
    """Primo passaggio: email e password. La sessione vale solo dopo il codice (mfa)."""
    email = normalize_email(email)
    with db.system_session() as s:
        if ratelimit.exceeded(
            s, "platform_login_email", email, *LOGIN_FAILS_PER_EMAIL
        ) or ratelimit.exceeded(s, "platform_login_ip", ip or "-", *LOGIN_FAILS_PER_IP):
            raise TooManyRequestsError()
        staff = s.scalar(select(PlatformStaff).where(PlatformStaff.email == email))
        ok = verify_password(password, staff.password_hash if staff else None)
        if not ok or staff is None or staff.status != "active":
            ratelimit.record(s, "platform_login_email", email)
            ratelimit.record(s, "platform_login_ip", ip or "-")
            _p_audit(s, "login_failed", staff.id if staff else None, ip)
            failed = True
        else:
            failed = False
            now = utcnow()
            token = new_token()
            s.add(
                PlatformSession(
                    staff_id=staff.id,
                    token_hash=token_hash(token),
                    created_at=now,
                    last_seen_at=now,
                    expires_at=now + MFA_WINDOW,
                    ip=ip,
                    user_agent=(user_agent or "")[:255] or None,
                )
            )
    if failed:  # dopo il commit: il tentativo fallito resta registrato
        raise UnauthorizedError("Email o password non corretti.", code="credenziali_errate")
    return token


def verify_mfa(
    db: Database, settings: Settings, token: str | None, code: str, ip: str | None
) -> None:
    now = utcnow()
    with db.system_session() as s:
        sess = s.scalar(
            select(PlatformSession)
            .where(PlatformSession.token_hash == token_hash(token or "-"))
            .with_for_update()
        )
        if (
            sess is None
            or sess.revoked_at is not None
            or sess.expires_at <= now
            or sess.mfa_passed_at is not None
        ):
            raise UnauthorizedError(
                "Accesso scaduto: inserisci di nuovo email e password.", code="non_autenticato"
            )
        staff = must(s.get(PlatformStaff, sess.staff_id))
        step = totp.verify(_secret(settings, staff), code, time.time(), staff.last_totp_step)
        if step is None:
            sess.mfa_failures += 1
            if sess.mfa_failures >= MFA_MAX_FAILURES:
                sess.revoked_at = now
            _p_audit(s, "mfa_failed", staff.id, ip)
            failed = True
        else:
            failed = False
            staff.last_totp_step = step
            staff.last_login_at = now
            sess.mfa_passed_at = now
            sess.last_seen_at = now
            sess.expires_at = now + SESSION_MAX
            _p_audit(s, "login", staff.id, ip)
    if failed:
        raise CodeError()


def resolve(db: Database, token: str | None) -> StaffContext | None:
    if not token or len(token) > 100:
        return None
    now = utcnow()
    with db.system_session() as s:
        sess = s.scalar(
            select(PlatformSession).where(PlatformSession.token_hash == token_hash(token))
        )
        if (
            sess is None
            or sess.mfa_passed_at is None
            or sess.revoked_at is not None
            or sess.expires_at <= now
        ):
            return None
        if sess.last_seen_at < now - SESSION_IDLE:
            sess.revoked_at = now
            return None
        staff = s.get(PlatformStaff, sess.staff_id)
        if staff is None or staff.status != "active":
            return None
        sess.last_seen_at = now
        return StaffContext(sess.id, staff.id, staff.email, staff.full_name)


def logout(db: Database, ctx: StaffContext, ip: str | None) -> None:
    with db.system_session() as s:
        sess = s.get(PlatformSession, ctx.session_id)
        if sess is not None:
            sess.revoked_at = utcnow()
        _p_audit(s, "logout", ctx.staff_id, ip)


# ---------------------------------------------------------------- personale


def list_staff(db: Database, ctx: StaffContext) -> list[dict[str, object]]:
    with db.system_session() as s:
        rows = s.scalars(select(PlatformStaff).order_by(PlatformStaff.full_name))
        return [
            {
                "id": str(p.id),
                "email": p.email,
                "full_name": p.full_name,
                "status": p.status,
                "last_login_at": p.last_login_at.isoformat() + "Z" if p.last_login_at else None,
                "is_me": p.id == ctx.staff_id,
            }
            for p in rows
        ]


def invite_staff(
    db: Database,
    settings: Settings,
    ctx: StaffContext,
    *,
    email: str,
    full_name: str,
    ip: str | None,
) -> Outcome:
    _key(settings)
    email = normalize_email(email)
    outcome = Outcome()
    with db.system_session() as s:
        staff = s.scalar(select(PlatformStaff).where(PlatformStaff.email == email))
        if staff is not None and staff.status != "invited":
            raise ConflictError("Questa persona ha già un account.", code="gia_presente")
        if staff is None:
            staff = PlatformStaff(
                email=email,
                full_name=full_name.strip(),
                totp_salt=secrets.token_hex(16),
                created_by=ctx.staff_id,
            )
            s.add(staff)
            s.flush()
        token = _new_invite(s, staff)
        _p_audit(
            s, "staff_invited", ctx.staff_id, ip, resource="platform_staff", resource_id=staff.id
        )
        outcome.emails.append(
            templates.platform_invite(email, staff.full_name, _invite_url(settings, token), False)
        )
    return outcome


def set_staff_status(
    db: Database, ctx: StaffContext, staff_id: uuid.UUID, status_: str, ip: str | None
) -> None:
    with db.system_session() as s:
        staff = s.get(PlatformStaff, staff_id)
        if staff is None:
            raise NotFoundError("Persona non trovata.")
        if staff.id == ctx.staff_id:
            raise ConflictError("Non puoi disattivare il tuo account.", code="se_stesso")
        if status_ == "active" and staff.totp_confirmed_at is None:
            raise ConflictError("L'invito non è ancora stato accettato.", code="invito_in_attesa")
        staff.status = status_
        if status_ == "disabled":
            for sess in s.scalars(
                select(PlatformSession).where(
                    PlatformSession.staff_id == staff.id, PlatformSession.revoked_at.is_(None)
                )
            ):
                sess.revoked_at = utcnow()
        _p_audit(
            s,
            "staff_" + ("disabled" if status_ == "disabled" else "enabled"),
            ctx.staff_id,
            ip,
            resource="platform_staff",
            resource_id=staff.id,
        )


# ---------------------------------------------------------------- studi


def _tenant_out(t: Tenant, extra: dict[str, object] | None = None) -> dict[str, object]:
    out: dict[str, object] = {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "business_type": t.business_type,
        "status": t.status,
        "trial_ends_at": t.trial_ends_at.isoformat() + "Z" if t.trial_ends_at else None,
        "created_at": t.created_at.isoformat() + "Z",
    }
    out.update(extra or {})
    return out


def list_tenants(db: Database, ctx: StaffContext, *, q: str | None) -> list[dict[str, object]]:
    with db.platform_session(f"piattaforma: elenco studi ({ctx.email})") as s:
        stmt = select(Tenant).order_by(Tenant.created_at.desc())
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(Tenant.name.like(like) | Tenant.slug.like(like))
        tenants = s.scalars(stmt.limit(500)).all()
        ids = [t.id for t in tenants]

        def counts(
            model: type[Professional | Client | Appointment], *where: Any
        ) -> dict[uuid.UUID, int]:
            if not ids:
                return {}
            rows = s.execute(
                select(model.tenant_id, func.count())
                .where(model.tenant_id.in_(ids), *where)
                .group_by(model.tenant_id)
            )
            return {tid: n for tid, n in rows}

        profs = counts(Professional, Professional.status == "active")
        clients = counts(Client, Client.status == "active")
        upcoming = counts(
            Appointment,
            Appointment.start_at >= utcnow(),
            Appointment.status.in_(("pending", "confirmed")),
        )
        owners: dict[uuid.UUID, tuple[str, str, bool]] = {}
        if ids:
            for tid, name, email, pending in s.execute(
                select(
                    Membership.tenant_id, User.full_name, User.email, User.password_hash.is_(None)
                )
                .join(User, User.id == Membership.user_id)
                .where(Membership.tenant_id.in_(ids), Membership.role == "owner")
                .order_by(Membership.created_at)
            ):
                owners.setdefault(tid, (name, email, bool(pending)))
        return [
            _tenant_out(
                t,
                {
                    "owner_name": owners.get(t.id, ("", "", False))[0],
                    "owner_email": owners.get(t.id, ("", "", False))[1],
                    "owner_invitation_pending": owners.get(t.id, ("", "", False))[2],
                    "professionals": profs.get(t.id, 0),
                    "clients": clients.get(t.id, 0),
                    "upcoming_appointments": upcoming.get(t.id, 0),
                },
            )
            for t in tenants
        ]


def get_tenant(db: Database, ctx: StaffContext, tenant_id: uuid.UUID) -> dict[str, object]:
    for row in list_tenants(db, ctx, q=None):
        if row["id"] == str(tenant_id):
            with db.platform_session(f"piattaforma: dettaglio studio ({ctx.email})") as s:
                st = s.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
                services = (
                    s.scalar(
                        select(func.count(Service.id)).where(
                            Service.tenant_id == tenant_id, Service.active.is_(True)
                        )
                    )
                    or 0
                )
                row = dict(row)
                row["contact_email"] = st.contact_email if st else None
                row["contact_phone"] = st.contact_phone if st else None
                row["services"] = services
            return row
    raise NotFoundError("Studio non trovato.")


def create_tenant(
    db: Database,
    settings: Settings,
    ctx: StaffContext,
    *,
    name: str,
    business_type: str,
    owner_name: str,
    owner_email: str,
    trial_days: int,
    ip: str | None,
) -> tuple[dict[str, object], Outcome]:
    owner_email = normalize_email(owner_email)
    outcome = Outcome()
    with db.system_session() as s:
        btype = s.get(BusinessType, business_type)
        if btype is None or not btype.active:
            raise InvalidInputError("Scegli una categoria valida.", code="categoria_non_valida")
        neutral = btype.health_related
    tenant_id = uuid.uuid4()
    with db.tenant_session(tenant_id) as s:
        tenant = Tenant(
            id=tenant_id,
            name=name.strip(),
            slug=accounts._unique_slug(s, name),
            business_type=business_type,
            status="trial" if trial_days > 0 else "active",
            trial_ends_at=utcnow() + timedelta(days=trial_days) if trial_days > 0 else None,
            neutral_messaging=neutral,
        )
        s.add(tenant)
        user = s.scalar(select(User).where(User.email == owner_email))
        existing = user is not None
        if user is None:
            user = User(email=owner_email, full_name=owner_name.strip(), status="pending")
            s.add(user)
        s.flush()
        s.add_all([TenantSettings(), Membership(user_id=user.id, role="owner")])
        catalog.create_default_location(s, tenant.timezone)
        catalog.ensure_professional(s, user.id, user.full_name)
        catalog.apply_profile(s, profile_for(business_type))
        if existing and user.email_verified_at is not None and user.password_hash is not None:
            outcome.emails.append(
                templates.added_to_studio(
                    owner_email,
                    "CoreNexus",
                    tenant.name,
                    "Titolare",
                    accounts._url(settings, "/accedi"),
                )
            )
        else:
            token = accounts._issue_token(
                s, user.id, "invite", accounts.INVITE_TTL, invite_tenant_id=tenant_id
            )
            outcome.emails.append(
                templates.invitation(
                    owner_email,
                    "CoreNexus",
                    tenant.name,
                    "Titolare",
                    accounts._url(settings, "/invito", token),
                )
            )
        _p_audit(
            s,
            "tenant_created",
            ctx.staff_id,
            ip,
            tenant_id=tenant_id,
            resource="tenant",
            resource_id=tenant_id,
            details={"business_type": business_type, "trial_days": trial_days},
        )
    return get_tenant(db, ctx, tenant_id), outcome


def update_tenant(
    db: Database,
    ctx: StaffContext,
    tenant_id: uuid.UUID,
    changes: dict[str, object],
    ip: str | None,
) -> dict[str, object]:
    with db.system_session() as s:
        tenant = s.get(Tenant, tenant_id)
        if tenant is None:
            raise NotFoundError("Studio non trovato.")
        before = {"status": tenant.status, "business_type": tenant.business_type}
        if "business_type" in changes:
            btype = s.get(BusinessType, str(changes["business_type"]))
            if btype is None or not btype.active:
                raise InvalidInputError("Scegli una categoria valida.", code="categoria_non_valida")
            tenant.business_type = btype.code
        if "name" in changes:
            tenant.name = str(changes["name"]).strip()
        if "extend_trial_days" in changes:
            days = int(str(changes["extend_trial_days"]))
            base = max(tenant.trial_ends_at or utcnow(), utcnow())
            tenant.trial_ends_at = base + timedelta(days=days)
        if "status" in changes:
            new_status = str(changes["status"])
            if new_status not in TENANT_STATUSES:
                raise InvalidInputError("Stato non valido.")
            tenant.status = new_status
        _p_audit(
            s,
            "tenant_updated",
            ctx.staff_id,
            ip,
            tenant_id=tenant_id,
            resource="tenant",
            resource_id=tenant_id,
            details={"before": before, "fields": sorted(changes)},
        )
    return get_tenant(db, ctx, tenant_id)


def load_profile(
    db: Database, ctx: StaffContext, tenant_id: uuid.UUID, ip: str | None
) -> dict[str, object]:
    """Aggiunge allo studio le prestazioni consigliate del suo profilo che mancano."""
    with db.system_session() as s:
        tenant = s.get(Tenant, tenant_id)
        if tenant is None:
            raise NotFoundError("Studio non trovato.")
        profile = profile_for(tenant.business_type)
    with db.tenant_session(tenant_id) as s:
        created = catalog.apply_profile(s, profile)
        _p_audit(
            s,
            "tenant_profile_loaded",
            ctx.staff_id,
            ip,
            tenant_id=tenant_id,
            resource="tenant",
            resource_id=tenant_id,
            details={"profile": profile.code, "created": len(created)},
        )
    return {"profile": profile.code, "created": len(created)}


def resend_owner_invite(
    db: Database, settings: Settings, ctx: StaffContext, tenant_id: uuid.UUID, ip: str | None
) -> Outcome:
    outcome = Outcome()
    with db.tenant_session(tenant_id) as s:
        tenant = s.get(Tenant, tenant_id)
        if tenant is None:
            raise NotFoundError("Studio non trovato.")
        row = (
            s.execute(
                select(User)
                .join(Membership, Membership.user_id == User.id)
                .where(Membership.role == "owner")
                .order_by(Membership.created_at)
            )
            .scalars()
            .first()
        )
        if row is None:
            raise NotFoundError("Lo studio non ha un titolare.")
        if row.password_hash is not None:
            raise ConflictError("Il titolare ha già attivato l'account.", code="gia_attivo")
        token = accounts._issue_token(
            s, row.id, "invite", accounts.INVITE_TTL, invite_tenant_id=tenant_id
        )
        outcome.emails.append(
            templates.invitation(
                row.email,
                "CoreNexus",
                tenant.name,
                "Titolare",
                accounts._url(settings, "/invito", token),
            )
        )
        _p_audit(
            s,
            "tenant_invite_resent",
            ctx.staff_id,
            ip,
            tenant_id=tenant_id,
            resource="tenant",
            resource_id=tenant_id,
        )
    return outcome


def activity(db: Database, ctx: StaffContext, limit: int = 100) -> list[dict[str, object]]:
    with db.system_session() as s:
        names = {p.id: p.full_name for p in s.scalars(select(PlatformStaff))}
        tenant_names = dict(s.execute(select(Tenant.id, Tenant.name)).all())
        rows = s.scalars(
            select(AuditLog)
            .where(AuditLog.action.like("platform\\_%"))
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        out: list[dict[str, object]] = []
        for r in rows:
            details = r.details or {}
            staff_id = details.get("staff_id")
            out.append(
                {
                    "at": r.created_at.isoformat() + "Z",
                    "action": r.action.removeprefix("platform_"),
                    "staff": names.get(uuid.UUID(str(staff_id))) if staff_id else None,
                    "tenant": tenant_names.get(r.tenant_id) if r.tenant_id else None,
                    "ip": r.ip,
                }
            )
        return out
