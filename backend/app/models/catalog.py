"""Sedi, professionisti, prestazioni e clienti (Sprint 2). Tutte tabelle di uno studio."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TenantScoped, utcnow

SERVICE_MODES = ("in_person", "online", "both")
CONSENT_CHANNELS = ("whatsapp", "email", "marketing")


class Location(TenantScoped, Base):
    """Sede dello studio. Ogni studio ne ha una principale, creata alla registrazione."""

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(40), nullable=False, default="Europe/Rome")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Professional(TenantScoped, Base):
    """Chi eroga le prestazioni. Può essere collegato a un account (user_id) oppure no."""

    __tablename__ = "professionals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "user_id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        CheckConstraint("status IN ('active','inactive')", name="status_valido"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(120))
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#0071e3")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    public_booking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Service(TenantScoped, Base):
    """Prestazione del catalogo: durata, prezzo, colore, tempo di preparazione, modalità."""

    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        CheckConstraint("duration_minutes BETWEEN 5 AND 600", name="durata_valida"),
        CheckConstraint("preparation_minutes BETWEEN 0 AND 240", name="preparazione_valida"),
        CheckConstraint("price IS NULL OR price >= 0", name="prezzo_valido"),
        CheckConstraint("mode IN ('in_person','online','both')", name="modalita_valida"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    preparation_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#0071e3")
    # Visite online: il link della videochiamata sarà generato per ogni appuntamento (Sprint 3).
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="in_person")
    public_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ServiceProfessional(TenantScoped, Base):
    """Professionisti abilitati a una prestazione."""

    __tablename__ = "service_professionals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("service_id", "professional_id"),
        ForeignKeyConstraint(["tenant_id", "service_id"], ["services.tenant_id", "services.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
    )

    service_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    professional_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)


class Client(TenantScoped, Base):
    """Anagrafica amministrativa del cliente. Nessun dato clinico (fuori perimetro)."""

    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "reference_professional_id"],
            ["professionals.tenant_id", "professionals.id"],
        ),
        CheckConstraint("status IN ('active','archived')", name="status_valido"),
        CheckConstraint(
            "preferred_channel IS NULL OR preferred_channel IN ('whatsapp','email','none')",
            name="canale_valido",
        ),
        Index("ix_clients_tenant_name", "tenant_id", "last_name", "first_name"),
        Index("ix_clients_tenant_phone", "tenant_id", "phone_e164"),
        Index("ix_clients_tenant_email", "tenant_id", "email"),
    )

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone_e164: Mapped[str | None] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(254))
    birth_date: Mapped[date | None] = mapped_column(Date)
    reference_professional_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    admin_notes: Mapped[str | None] = mapped_column(Text)
    preferred_channel: Mapped[str | None] = mapped_column(String(20))
    whatsapp_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    whatsapp_consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    email_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Consenso separato per comunicazioni promozionali (futuro modulo Campagne).
    marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    marketing_consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class ClientConsentEvent(TenantScoped, Base):
    """Storico di consensi e revoche (prova del consenso, art. 7 GDPR)."""

    __tablename__ = "client_consent_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "client_id"], ["clients.tenant_id", "clients.id"]),
        CheckConstraint("channel IN ('whatsapp','email','marketing')", name="canale_valido"),
        CheckConstraint("action IN ('granted','revoked')", name="azione_valida"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
