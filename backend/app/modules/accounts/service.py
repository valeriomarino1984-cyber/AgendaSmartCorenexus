"""Logica di accesso: registrazione, verifica email, sessioni, password, inviti e collaboratori.

Regole generali:
- le risposte a registrazione, reinvio e password dimenticata sono identiche che l'email esista o
  no (nessuna enumerazione degli account);
- i token inviati per email e quello del cookie sono salvati solo come hash;
- le email partono dopo il commit della transazione, così il link è sempre valido.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, must
from app.core.models import utcnow
from app.core.security import (
    hash_password,
    needs_rehash,
    new_token,
    normalize_email,
    password_problem,
    token_hash,
    verify_password,
)
from app.models.accounts import (
    ROLE_LABELS,
    AuthSession,
    BusinessType,
    Membership,
    Tenant,
    TenantSettings,
    User,
    UserToken,
)
from app.modules.accounts import ratelimit
from app.modules.accounts.audit import audit
from app.modules.catalog import service as catalog
from app.modules.catalog.presets import profile_for
from app.modules.email import templates
from app.modules.email.sender import OutgoingEmail, send_email

log = structlog.get_logger("accounts")

TRIAL_DAYS = 14
VERIFY_TTL = timedelta(hours=48)
RESET_TTL = timedelta(hours=1)
INVITE_TTL = timedelta(days=7)
SESSION_TOUCH_EVERY = timedelta(minutes=1)

LOGIN_FAILS_PER_EMAIL = (5, timedelta(minutes=15))
LOGIN_FAILS_PER_IP = (30, timedelta(minutes=15))
SIGNUPS_PER_IP = (10, timedelta(hours=1))
EMAILS_PER_ADDRESS = (3, timedelta(hours=1))
EMAILS_PER_IP = (20, timedelta(hours=1))

BLOCKED_TENANT_STATUSES = ("suspended", "cancelled")


class UnauthorizedError(AppError):
    status_code = 401
    code = "non_autenticato"
    message = "Accesso richiesto."


class TooManyRequestsError(AppError):
    status_code = 429
    code = "troppe_richieste"
    message = "Troppi tentativi. Riprova tra qualche minuto."


class InvalidInputError(AppError):
    status_code = 422
    code = "dati_non_validi"
    message = "Dati non validi."


@dataclass(frozen=True)
class AuthContext:
    """Chi sta facendo la richiesta e in quale studio."""

    session_id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    email: str
    full_name: str


@dataclass
class Outcome:
    """Risultato di un'operazione: eventuale nuova sessione e email da inviare dopo il commit."""

    session_token: str | None = None
    emails: list[OutgoingEmail] = field(default_factory=list)
    email_sent: bool | None = None


# ---------------------------------------------------------------- utilità


def _slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return (slug or "studio")[:50].strip("-")


def _unique_slug(session: Session, name: str) -> str:
    base = _slugify(name)
    candidate, n = base, 1
    while session.scalar(select(Tenant.id).where(Tenant.slug == candidate)) is not None:
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def _issue_token(
    session: Session,
    user_id: uuid.UUID,
    purpose: str,
    ttl: timedelta,
    invite_tenant_id: uuid.UUID | None = None,
) -> str:
    # Un solo token valido per scopo: i precedenti vengono invalidati.
    session.execute(
        update(UserToken)
        .where(
            UserToken.user_id == user_id, UserToken.purpose == purpose, UserToken.used_at.is_(None)
        )
        .values(used_at=utcnow())
    )
    token = new_token()
    session.add(
        UserToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash(token),
            expires_at=utcnow() + ttl,
            invite_tenant_id=invite_tenant_id,
        )
    )
    return token


def _consume_token(session: Session, token: str, purpose: str) -> UserToken:
    row = session.scalar(
        select(UserToken).where(
            UserToken.token_hash == token_hash(token), UserToken.purpose == purpose
        )
    )
    if row is None or row.used_at is not None or row.expires_at < utcnow():
        raise InvalidInputError(
            "Il link non è valido o è scaduto. Richiedine uno nuovo.", code="link_non_valido"
        )
    row.used_at = utcnow()
    return row


def _create_session(
    session: Session,
    settings: Settings,
    user: User,
    tenant_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> str:
    token = new_token()
    now = utcnow()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            active_tenant_id=tenant_id,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=settings.session_max_days),
            ip=ip,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    user.last_login_at = now
    return token


def _check_password(password: str, email: str, full_name: str) -> None:
    problem = password_problem(password, email=email, full_name=full_name)
    if problem:
        raise InvalidInputError(problem, code="password_debole")


def _url(settings: Settings, path: str, token: str | None = None) -> str:
    base = settings.app_base_url.rstrip("/")
    return f"{base}{path}" + (f"?token={token}" if token else "")


def _active_memberships(db: Database, user_id: uuid.UUID) -> list[tuple[Membership, Tenant]]:
    with db.platform_session("elenco degli studi di un utente (login, profilo)") as s:
        rows = s.execute(
            select(Membership, Tenant)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(Membership.user_id == user_id, Membership.status == "active")
            .order_by(Tenant.name)
        ).all()
        return [(m, t) for m, t in rows]


def _pick_tenant(db: Database, user_id: uuid.UUID, preferred: uuid.UUID | None = None) -> uuid.UUID:
    usable = [
        (m, t)
        for m, t in _active_memberships(db, user_id)
        if t.status not in BLOCKED_TENANT_STATUSES
    ]
    if not usable:
        raise ForbiddenError(
            "Il tuo account non è attivo in nessuno studio.", code="nessuno_studio"
        )
    for m, _t in usable:
        if m.tenant_id == preferred:
            return m.tenant_id
    return usable[0][0].tenant_id


def deliver(settings: Settings, outcome: Outcome) -> Outcome:
    """Invia le email dopo il commit. Il risultato dell'ultimo invio finisce in email_sent."""
    for mail in outcome.emails:
        outcome.email_sent = send_email(settings, mail)
    return outcome


# ---------------------------------------------------------------- registrazione


def register(
    db: Database,
    settings: Settings,
    *,
    studio_name: str,
    business_type: str,
    full_name: str,
    email: str,
    password: str,
    ip: str | None,
) -> Outcome:
    if not settings.signup_open:
        raise ForbiddenError(
            "La registrazione di nuovi studi al momento è chiusa.", code="registrazione_chiusa"
        )
    email = normalize_email(email)
    _check_password(password, email, full_name)
    outcome = Outcome()

    with db.system_session() as s:
        if not ratelimit.hit(s, "signup_ip", ip or "-", *SIGNUPS_PER_IP):
            raise TooManyRequestsError()
        btype = s.get(BusinessType, business_type)
        if btype is None or not btype.active:
            raise InvalidInputError("Scegli una categoria valida.", code="categoria_non_valida")
        existing = s.scalar(select(User).where(User.email == email))
        if existing is not None:
            audit(s, "signup_existing_email", user_id=existing.id, ip=ip)
            outcome.emails.append(
                templates.already_registered(
                    email, _url(settings, "/accedi"), _url(settings, "/password-dimenticata")
                )
            )
            return outcome
        health_related = btype.health_related

    tenant_id = uuid.uuid4()
    with db.tenant_session(tenant_id) as s:
        tenant = Tenant(
            id=tenant_id,
            name=studio_name.strip(),
            slug=_unique_slug(s, studio_name),
            business_type=business_type,
            status="trial",
            trial_ends_at=utcnow() + timedelta(days=TRIAL_DAYS),
            neutral_messaging=health_related,
        )
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            status="pending",
        )
        s.add_all([tenant, user])
        s.flush()
        s.add_all([TenantSettings(), Membership(user_id=user.id, role="owner")])
        # Profilo professionale: sede principale, scheda del titolare e prestazioni consigliate.
        catalog.create_default_location(s, tenant.timezone)
        catalog.ensure_professional(s, user.id, user.full_name)
        catalog.apply_profile(s, profile_for(business_type))
        token = _issue_token(s, user.id, "verify_email", VERIFY_TTL)
        audit(
            s,
            "signup",
            tenant_id=tenant_id,
            user_id=user.id,
            ip=ip,
            details={"business_type": business_type, "terms_accepted": True},
        )
        outcome.emails.append(
            templates.verify_email(
                email, user.full_name, tenant.name, _url(settings, "/verifica-email", token)
            )
        )
    return outcome


def resend_verification(db: Database, settings: Settings, *, email: str, ip: str | None) -> Outcome:
    email = normalize_email(email)
    outcome = Outcome()
    with db.system_session() as s:
        if not ratelimit.hit(s, "email_ip", ip or "-", *EMAILS_PER_IP):
            raise TooManyRequestsError()
        if not ratelimit.hit(s, "verify_email", email, *EMAILS_PER_ADDRESS):
            return outcome  # risposta identica: nessuna informazione sull'account
        user = s.scalar(select(User).where(User.email == email))
        if user is None or user.email_verified_at is not None or user.password_hash is None:
            return outcome
        token = _issue_token(s, user.id, "verify_email", VERIFY_TTL)
        outcome.emails.append(
            templates.verify_email(
                email, user.full_name, "il tuo studio", _url(settings, "/verifica-email", token)
            )
        )
    return outcome


def verify_email(
    db: Database, settings: Settings, *, token: str, ip: str | None, user_agent: str | None
) -> Outcome:
    with db.system_session() as s:
        row = _consume_token(s, token, "verify_email")
        user = s.get(User, row.user_id)
        user = must(user)
        user.email_verified_at = user.email_verified_at or utcnow()
        if user.status == "pending":
            user.status = "active"
        audit(s, "email_verified", user_id=user.id, ip=ip)
        user_id = user.id
    tenant_id = _pick_tenant(db, user_id)
    with db.system_session() as s:
        user = s.get(User, user_id)
        user = must(user)
        return Outcome(session_token=_create_session(s, settings, user, tenant_id, ip, user_agent))


# ---------------------------------------------------------------- accesso


def login(
    db: Database,
    settings: Settings,
    *,
    email: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
) -> Outcome:
    email = normalize_email(email)
    with db.system_session() as s:
        if ratelimit.exceeded(
            s, "login_fail_email", email, *LOGIN_FAILS_PER_EMAIL
        ) or ratelimit.exceeded(s, "login_fail_ip", ip or "-", *LOGIN_FAILS_PER_IP):
            raise TooManyRequestsError("Troppi tentativi di accesso. Riprova tra 15 minuti.")
        user = s.scalar(select(User).where(User.email == email))
        ok = verify_password(password, user.password_hash if user else None)
        failed = not ok or user is None or user.status == "disabled"
        if failed:
            # Il tentativo fallito va salvato: si esce dalla transazione SENZA eccezione (che la
            # annullerebbe, cancellando il conteggio per il blocco) e si risponde dopo il commit.
            ratelimit.record(s, "login_fail_email", email)
            ratelimit.record(s, "login_fail_ip", ip or "-")
            audit(s, "login_failed", user_id=user.id if user else None, ip=ip)
    if failed:
        raise UnauthorizedError("Email o password non corretti.", code="credenziali_errate")
    with db.system_session() as s:
        user = must(s.scalar(select(User).where(User.email == email)))
        if user.email_verified_at is None:
            raise ForbiddenError(
                "Conferma prima il tuo indirizzo email: ti abbiamo inviato un link.",
                code="email_non_verificata",
            )
        if user.password_hash and needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user_id = user.id
        last_tenant = s.scalar(
            select(AuthSession.active_tenant_id)
            .where(AuthSession.user_id == user_id)
            .order_by(AuthSession.created_at.desc())
            .limit(1)
        )
    tenant_id = _pick_tenant(db, user_id, preferred=last_tenant)
    with db.system_session() as s:
        user = s.get(User, user_id)
        user = must(user)
        token = _create_session(s, settings, user, tenant_id, ip, user_agent)
        audit(s, "login", tenant_id=tenant_id, user_id=user_id, ip=ip)
    return Outcome(session_token=token)


def resolve_session(db: Database, settings: Settings, token: str | None) -> AuthContext | None:
    """Sessione valida dal token del cookie, oppure None (scaduta, revocata, disattivata…)."""
    if not token or len(token) > 100:
        return None
    now = utcnow()
    with db.system_session() as s:
        sess = s.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        if sess is None or sess.revoked_at is not None or sess.expires_at <= now:
            return None
        if sess.last_seen_at < now - timedelta(hours=settings.session_idle_hours):
            sess.revoked_at = now
            return None
        user = s.get(User, sess.user_id)
        tenant = s.get(Tenant, sess.active_tenant_id)
        if (
            user is None
            or user.status != "active"
            or tenant is None
            or tenant.status in BLOCKED_TENANT_STATUSES
        ):
            return None
        if sess.last_seen_at < now - SESSION_TOUCH_EVERY:
            sess.last_seen_at = now
        session_id, user_id, tenant_id = sess.id, user.id, tenant.id
        email, full_name = user.email, user.full_name
    with db.tenant_session(tenant_id) as s:
        membership = s.scalar(select(Membership).where(Membership.user_id == user_id))
        if membership is None or membership.status != "active":
            return None
        role = membership.role
    return AuthContext(session_id, user_id, tenant_id, role, email, full_name)


def logout(db: Database, ctx: AuthContext, ip: str | None) -> None:
    with db.system_session() as s:
        sess = s.get(AuthSession, ctx.session_id)
        if sess is not None and sess.revoked_at is None:
            sess.revoked_at = utcnow()
        audit(s, "logout", tenant_id=ctx.tenant_id, user_id=ctx.user_id, ip=ip)


def switch_tenant(db: Database, ctx: AuthContext, tenant_id: uuid.UUID, ip: str | None) -> None:
    allowed = {
        m.tenant_id
        for m, t in _active_memberships(db, ctx.user_id)
        if t.status not in BLOCKED_TENANT_STATUSES
    }
    if tenant_id not in allowed:
        # Stessa risposta per studio inesistente o di cui non si fa parte.
        raise NotFoundError("Studio non trovato.")
    with db.system_session() as s:
        sess = s.get(AuthSession, ctx.session_id)
        sess = must(sess)
        sess.active_tenant_id = tenant_id
        audit(s, "switch_tenant", tenant_id=tenant_id, user_id=ctx.user_id, ip=ip)


def me(db: Database, ctx: AuthContext) -> dict[str, object]:
    memberships = _active_memberships(db, ctx.user_id)
    with db.system_session() as s:
        tenant = s.get(Tenant, ctx.tenant_id)
        tenant = must(tenant)
        tenant_data = {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "business_type": tenant.business_type,
            "status": tenant.status,
            "trial_ends_at": tenant.trial_ends_at.isoformat() + "Z"
            if tenant.trial_ends_at
            else None,
        }
    return {
        "user": {"id": str(ctx.user_id), "email": ctx.email, "full_name": ctx.full_name},
        "tenant": tenant_data,
        "role": ctx.role,
        "role_label": ROLE_LABELS[ctx.role],
        "tenants": [
            {"id": str(t.id), "name": t.name, "role": m.role, "role_label": ROLE_LABELS[m.role]}
            for m, t in memberships
            if t.status not in BLOCKED_TENANT_STATUSES
        ],
    }


# ---------------------------------------------------------------- password


def forgot_password(db: Database, settings: Settings, *, email: str, ip: str | None) -> Outcome:
    email = normalize_email(email)
    outcome = Outcome()
    with db.system_session() as s:
        if not ratelimit.hit(s, "email_ip", ip or "-", *EMAILS_PER_IP):
            raise TooManyRequestsError()
        if not ratelimit.hit(s, "reset_email", email, *EMAILS_PER_ADDRESS):
            return outcome
        user = s.scalar(select(User).where(User.email == email))
        if user is None or user.status == "disabled":
            return outcome
        token = _issue_token(s, user.id, "reset_password", RESET_TTL)
        audit(s, "password_reset_requested", user_id=user.id, ip=ip)
        outcome.emails.append(
            templates.reset_password(email, _url(settings, "/reimposta-password", token))
        )
    return outcome


def reset_password(db: Database, *, token: str, password: str, ip: str | None) -> None:
    with db.system_session() as s:
        row = _consume_token(s, token, "reset_password")
        user = s.get(User, row.user_id)
        user = must(user)
        _check_password(password, user.email, user.full_name)
        user.password_hash = hash_password(password)
        # Il link è arrivato all'indirizzo email: ne prova il possesso.
        user.email_verified_at = user.email_verified_at or utcnow()
        if user.status == "pending":
            user.status = "active"
        s.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        audit(s, "password_reset", user_id=user.id, ip=ip)


# ---------------------------------------------------------------- inviti e collaboratori


def invite(
    db: Database,
    settings: Settings,
    ctx: AuthContext,
    *,
    email: str,
    full_name: str,
    role: str,
    ip: str | None,
) -> Outcome:
    email = normalize_email(email)
    outcome = Outcome()
    with db.tenant_session(ctx.tenant_id) as s:
        tenant = s.get(Tenant, ctx.tenant_id)
        tenant = must(tenant)
        existing = s.scalar(select(User).where(User.email == email))
        if existing is not None:
            already = s.scalar(select(Membership).where(Membership.user_id == existing.id))
            if already is not None:
                raise ConflictError(
                    "Questa persona fa già parte dello studio.", code="gia_nello_studio"
                )
            membership = Membership(user_id=existing.id, role=role)
            s.add(membership)
            s.flush()
            if role in catalog.PROFESSIONAL_ROLES:
                catalog.ensure_professional(s, existing.id, existing.full_name)
            if existing.email_verified_at is not None:
                outcome.emails.append(
                    templates.added_to_studio(
                        email,
                        ctx.full_name,
                        tenant.name,
                        ROLE_LABELS[role],
                        _url(settings, "/accedi"),
                    )
                )
            else:
                token = _issue_token(
                    s, existing.id, "invite", INVITE_TTL, invite_tenant_id=ctx.tenant_id
                )
                outcome.emails.append(
                    templates.invitation(
                        email,
                        ctx.full_name,
                        tenant.name,
                        ROLE_LABELS[role],
                        _url(settings, "/invito", token),
                    )
                )
            user_id = existing.id
        else:
            user = User(email=email, full_name=full_name.strip(), status="pending")
            s.add(user)
            s.flush()
            membership = Membership(user_id=user.id, role=role)
            s.add(membership)
            s.flush()
            if role in catalog.PROFESSIONAL_ROLES:
                catalog.ensure_professional(s, user.id, user.full_name)
            token = _issue_token(s, user.id, "invite", INVITE_TTL, invite_tenant_id=ctx.tenant_id)
            outcome.emails.append(
                templates.invitation(
                    email,
                    ctx.full_name,
                    tenant.name,
                    ROLE_LABELS[role],
                    _url(settings, "/invito", token),
                )
            )
            user_id = user.id
        audit(
            s,
            "member_invited",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="membership",
            resource_id=membership.id,
            details={"role": role, "invited_user_id": str(user_id)},
        )
    return outcome


def accept_invitation(
    db: Database,
    settings: Settings,
    *,
    token: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
) -> Outcome:
    with db.system_session() as s:
        row = _consume_token(s, token, "invite")
        user = s.get(User, row.user_id)
        user = must(user)
        must(row.invite_tenant_id)
        if user.password_hash is None:
            _check_password(password, user.email, user.full_name)
            user.password_hash = hash_password(password)
        elif not verify_password(password, user.password_hash):
            raise UnauthorizedError(
                "Hai già un account: inserisci la tua password attuale.", code="credenziali_errate"
            )
        user.email_verified_at = user.email_verified_at or utcnow()
        user.status = "active" if user.status == "pending" else user.status
        audit(s, "invitation_accepted", tenant_id=row.invite_tenant_id, user_id=user.id, ip=ip)
        user_id, tenant_id = user.id, row.invite_tenant_id
    tenant_id = _pick_tenant(db, user_id, preferred=tenant_id)
    with db.system_session() as s:
        user = s.get(User, user_id)
        user = must(user)
        return Outcome(session_token=_create_session(s, settings, user, tenant_id, ip, user_agent))


def invitation_info(db: Database, token: str) -> dict[str, object]:
    with db.system_session() as s:
        row = s.scalar(
            select(UserToken).where(
                UserToken.token_hash == token_hash(token), UserToken.purpose == "invite"
            )
        )
        if (
            row is None
            or row.used_at is not None
            or row.expires_at < utcnow()
            or row.invite_tenant_id is None
        ):
            raise InvalidInputError("L'invito non è valido o è scaduto.", code="link_non_valido")
        user = s.get(User, row.user_id)
        tenant = s.get(Tenant, row.invite_tenant_id)
        user = must(user)
        tenant = must(tenant)
        return {
            "studio": tenant.name,
            "email": user.email,
            "full_name": user.full_name,
            "has_password": user.password_hash is not None,
        }


def list_members(db: Database, ctx: AuthContext) -> list[dict[str, object]]:
    with db.tenant_session(ctx.tenant_id) as s:
        rows = s.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .order_by(User.full_name)
        ).all()
        return [
            {
                "id": str(m.id),
                "user_id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "role": m.role,
                "role_label": ROLE_LABELS[m.role],
                "status": m.status,
                "invitation_pending": u.password_hash is None or u.email_verified_at is None,
                "is_me": u.id == ctx.user_id,
            }
            for m, u in rows
        ]


def update_member(
    db: Database,
    ctx: AuthContext,
    membership_id: uuid.UUID,
    *,
    role: str | None,
    status: str | None,
    ip: str | None,
) -> None:
    with db.tenant_session(ctx.tenant_id) as s:
        m = s.get(Membership, membership_id)
        if m is None:
            raise NotFoundError("Collaboratore non trovato.")
        new_role = role or m.role
        new_status = status or m.status
        losing_owner = (
            m.role == "owner"
            and m.status == "active"
            and (new_role != "owner" or new_status != "active")
        )
        if losing_owner:
            owners = s.scalars(
                select(Membership).where(Membership.role == "owner", Membership.status == "active")
            ).all()
            if len(owners) <= 1:
                raise ConflictError(
                    "Lo studio deve avere almeno un titolare attivo.", code="ultimo_titolare"
                )
        before = {"role": m.role, "status": m.status}
        m.role, m.status = new_role, new_status
        if new_role in catalog.PROFESSIONAL_ROLES and new_role != before["role"]:
            member = must(s.get(User, m.user_id))
            catalog.ensure_professional(s, member.id, member.full_name)
        audit(
            s,
            "member_updated",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="membership",
            resource_id=m.id,
            details={"before": before, "after": {"role": new_role, "status": new_status}},
        )
        target_user = m.user_id
    if new_status == "disabled":
        with db.system_session() as s:
            s.execute(
                update(AuthSession)
                .where(
                    AuthSession.user_id == target_user,
                    AuthSession.active_tenant_id == ctx.tenant_id,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=utcnow())
            )


# ---------------------------------------------------------------- dati dello studio


def get_studio(db: Database, ctx: AuthContext) -> dict[str, object]:
    with db.tenant_session(ctx.tenant_id) as s:
        tenant = s.get(Tenant, ctx.tenant_id)
        st = s.scalar(select(TenantSettings))
        tenant = must(tenant)
        st = must(st)
        return {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "business_type": tenant.business_type,
            "status": tenant.status,
            "neutral_messaging": tenant.neutral_messaging,
            "timezone": tenant.timezone,
            "contact_email": st.contact_email,
            "contact_phone": st.contact_phone,
            "address": st.address,
            "cancellation_min_hours": st.cancellation_min_hours,
            "email_confirmations": st.email_confirmations,
            "reminder_hours": st.reminder_hours,
        }


def update_studio(
    db: Database, ctx: AuthContext, changes: dict[str, object], ip: str | None
) -> dict[str, object]:
    tenant_fields = {"name", "business_type", "neutral_messaging"}
    with db.tenant_session(ctx.tenant_id) as s:
        tenant = s.get(Tenant, ctx.tenant_id)
        st = s.scalar(select(TenantSettings))
        tenant = must(tenant)
        st = must(st)
        if "business_type" in changes:
            btype = s.get(BusinessType, str(changes["business_type"]))
            if btype is None or not btype.active:
                raise InvalidInputError("Scegli una categoria valida.", code="categoria_non_valida")
        for key, value in changes.items():
            setattr(tenant if key in tenant_fields else st, key, value)
        audit(
            s,
            "studio_updated",
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            ip=ip,
            resource="tenant",
            resource_id=ctx.tenant_id,
            details={"fields": sorted(changes)},
        )
    return get_studio(db, ctx)


def business_types(db: Database) -> list[dict[str, object]]:
    with db.system_session() as s:
        rows = s.scalars(
            select(BusinessType)
            .where(BusinessType.active.is_(True))
            .order_by(BusinessType.sort_order)
        )
        return [{"code": b.code, "label": b.label} for b in rows]
