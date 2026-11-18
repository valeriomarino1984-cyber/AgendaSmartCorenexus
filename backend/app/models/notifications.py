"""Notifiche ai clienti (Sprint 5): una riga per ogni messaggio da inviare, con il suo esito.

Coda nel database (outbox): le righe nascono insieme alle modifiche dell'appuntamento, nella
stessa transazione, e vengono inviate subito dopo oppure all'ora prevista (promemoria).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TenantScoped

KINDS = ("confirmation", "reminder", "rescheduled", "cancelled")
STATUSES = ("pending", "sending", "sent", "failed", "skipped", "cancelled")


class NotificationJob(TenantScoped, Base):
    __tablename__ = "notification_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "appointment_id"], ["appointments.tenant_id", "appointments.id"]
        ),
        CheckConstraint(
            "kind IN ('confirmation','reminder','rescheduled','cancelled')", name="tipo_valido"
        ),
        CheckConstraint("channel IN ('email','whatsapp')", name="canale_valido"),
        CheckConstraint(
            "status IN ('pending','sending','sent','failed','skipped','cancelled')",
            name="stato_valido",
        ),
        Index("ix_notification_jobs_due", "status", "scheduled_at"),
        Index("ix_notification_jobs_appointment", "tenant_id", "appointment_id"),
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False, default="email")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Motivo di un invio saltato o non riuscito (mai il contenuto del messaggio).
    reason: Mapped[str | None] = mapped_column(String(60))
