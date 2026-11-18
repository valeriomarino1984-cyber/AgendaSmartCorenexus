"""Disponibilità, eccezioni e appuntamenti (Sprint 3). Tutte tabelle di uno studio.

Gli orari degli appuntamenti e delle eccezioni sono salvati in UTC (DATETIME senza fuso);
gli orari settimanali sono "ora locale" della sede (es. 09:00 a Roma, d'estate e d'inverno).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    JSON,
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
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TenantScoped, utcnow


def utcnow_precise() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


EXCEPTION_KINDS = ("vacation", "unavailable", "closure", "extra")
ACTIVE_STATUSES = ("pending", "confirmed")
STATUSES = (
    "pending",
    "confirmed",
    "cancelled_by_client",
    "cancelled_by_staff",
    "completed",
    "no_show",
)


class Availability(TenantScoped, Base):
    """Fascia oraria settimanale di un professionista in una sede (ora locale della sede)."""

    __tablename__ = "availability"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
        ForeignKeyConstraint(["tenant_id", "location_id"], ["locations.tenant_id", "locations.id"]),
        CheckConstraint("weekday BETWEEN 1 AND 7", name="giorno_valido"),
        CheckConstraint("end_time > start_time", name="orario_valido"),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="periodo_valido",
        ),
        Index("ix_availability_tenant_prof", "tenant_id", "professional_id", "weekday"),
    )

    professional_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # ISO: 1 = lunedì
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class AvailabilityException(TenantScoped, Base):
    """Ferie, indisponibilità, chiusure dello studio (professional_id nullo) o aperture extra."""

    __tablename__ = "availability_exceptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
        CheckConstraint("end_at > start_at", name="periodo_valido"),
        CheckConstraint("kind IN ('vacation','unavailable','closure','extra')", name="tipo_valido"),
        CheckConstraint(
            "(kind = 'closure') = (professional_id IS NULL)", name="chiusura_di_studio"
        ),
        Index("ix_availability_exceptions_period", "tenant_id", "start_at", "end_at"),
    )

    professional_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200))


class Appointment(TenantScoped, Base):
    """Appuntamento. Nessuna sovrapposizione per professionista tra quelli attivi: garantita
    dal servizio con un lock sulla riga del professionista (MySQL non ha vincoli di esclusione).
    """

    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "public_code"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        ForeignKeyConstraint(["tenant_id", "client_id"], ["clients.tenant_id", "clients.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
        ForeignKeyConstraint(["tenant_id", "service_id"], ["services.tenant_id", "services.id"]),
        ForeignKeyConstraint(["tenant_id", "location_id"], ["locations.tenant_id", "locations.id"]),
        CheckConstraint("end_at > start_at", name="orario_valido"),
        CheckConstraint("buffer_end_at >= end_at", name="preparazione_valida"),
        CheckConstraint(
            "status IN ('pending','confirmed','cancelled_by_client','cancelled_by_staff',"
            "'completed','no_show')",
            name="stato_valido",
        ),
        CheckConstraint(
            "source IN ('staff','public_booking','waitlist','recurring')", name="origine_valida"
        ),
        CheckConstraint("price IS NULL OR price >= 0", name="prezzo_valido"),
        CheckConstraint("NOT is_online OR video_url IS NOT NULL", name="link_video"),
        Index("ix_appointments_prof_start", "tenant_id", "professional_id", "start_at"),
        Index("ix_appointments_client_start", "tenant_id", "client_id", "start_at"),
        Index("ix_appointments_start", "tenant_id", "start_at"),
    )

    public_code: Mapped[str] = mapped_column(String(12), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    professional_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Tempo di preparazione copiato dalla prestazione: l'agenda resta occupata fino a buffer_end_at.
    preparation_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buffer_end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="confirmed")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="staff")
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    video_url: Mapped[str | None] = mapped_column(String(300))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)  # solo amministrative, mai nei messaggi
    cancellation_reason: Mapped[str | None] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class AppointmentEvent(TenantScoped, Base):
    """Storico dell'appuntamento: creazione, spostamenti, cambi di stato."""

    __tablename__ = "appointment_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "appointment_id"], ["appointments.tenant_id", "appointments.id"]
        ),
        CheckConstraint("actor_type IN ('staff','client','system')", name="attore_valido"),
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(10), nullable=False, default="staff")
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    previous_value: Mapped[dict[str, object] | None] = mapped_column(JSON)
    new_value: Mapped[dict[str, object] | None] = mapped_column(JSON)
    # Con i microsecondi: più eventi nello stesso secondo restano nell'ordine giusto.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql", "mariadb"),
        nullable=False,
        default=utcnow_precise,
    )
