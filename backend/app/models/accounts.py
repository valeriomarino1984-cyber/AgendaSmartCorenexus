"""Studi (tenant), utenti, ruoli, sessioni, token monouso, limiti e registro attività."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TenantScoped, utcnow

ROLES = ("owner", "professional", "secretary")
ROLE_LABELS = {"owner": "Titolare", "professional": "Professionista", "secretary": "Segreteria"}


class BusinessType(Base):
    """Categorie professionali: si aggiungono con una migrazione, senza toccare il codice."""

    __tablename__ = "business_types"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    # Categorie sanitarie: messaggi neutri attivi di default (Decisione 11).
    health_related: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Tenant(Base):
    """Uno studio. Tabella globale: si accede sempre per id, preso dalla sessione."""

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('trial','active','suspended','cancelled')", name="status_valido"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    business_type: Mapped[str] = mapped_column(
        String(40), ForeignKey("business_types.code"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="trial")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    timezone: Mapped[str] = mapped_column(String(40), nullable=False, default="Europe/Rome")
    neutral_messaging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class TenantSettings(TenantScoped, Base):
    __tablename__ = "tenant_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        CheckConstraint("cancellation_min_hours BETWEEN 0 AND 168", name="preavviso_valido"),
    )

    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(200))
    cancellation_min_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class User(Base):
    """Persona che accede (titolare, professionista, segreteria). Può appartenere a più studi."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('pending','active','disabled')", name="status_valido"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Membership(TenantScoped, Base):
    """Ruolo di un utente in uno studio (tabella tenant_users della specifica)."""

    __tablename__ = "tenant_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "user_id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        CheckConstraint("role IN ('owner','professional','secretary')", name="ruolo_valido"),
        CheckConstraint("status IN ('active','disabled')", name="status_valido"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # Permessi granulari (Release 3).
    permissions: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class AuthSession(Base):
    """Sessione di accesso. Nel cookie c'è un token opaco, qui solo il suo hash."""

    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Studio aperto in questa sessione (non è un dato dello studio: niente filtro tenant).
    active_tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class UserToken(Base):
    """Token monouso inviati per email: verifica indirizzo, reimpostazione password, invito."""

    __tablename__ = "user_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('verify_email','reset_password','invite')", name="scopo_valido"
        ),
        Index("ix_user_tokens_user_purpose", "user_id", "purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Per gli inviti: studio in cui entrare.
    invite_tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class RateLimitEvent(Base):
    """Eventi contati per i limiti di frequenza (al posto di Redis, non disponibile su cPanel)."""

    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("ix_rate_limit_events_key_created", "key_hash", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    # Hash di "ambito:valore" (es. login per email): nessun dato personale in chiaro.
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class AuditLog(Base):
    """Registro di sicurezza append-only (esente dal filtro tenant, vedi schema_checks)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, object] | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
