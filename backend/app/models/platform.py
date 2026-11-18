"""Area piattaforma CoreNexus: personale con verifica in due passaggi, link di invito, sessioni.

Tabelle globali (non di uno studio). Il segreto del codice a 6 cifre non è salvato: si ricava
da una chiave del server (PLATFORM_SECRET_KEY) e da un sale casuale per persona, quindi una
copia del database da sola non basta per generare i codici.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, utcnow


class PlatformStaff(Base):
    __tablename__ = "platform_staff"
    __table_args__ = (
        CheckConstraint("status IN ('invited','active','disabled')", name="status_valido"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    totp_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Ultimo intervallo di 30 secondi usato: lo stesso codice non vale due volte.
    last_totp_step: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class PlatformToken(Base):
    """Link di invito monouso (anche quello della prima configurazione)."""

    __tablename__ = "platform_tokens"
    __table_args__ = (Index("ix_platform_tokens_staff", "staff_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("platform_staff.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class PlatformSession(Base):
    """Sessione del personale CoreNexus. Valida solo dopo il codice a 6 cifre (mfa_passed_at)."""

    __tablename__ = "platform_sessions"
    __table_args__ = (Index("ix_platform_sessions_staff", "staff_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("platform_staff.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    mfa_passed_at: Mapped[datetime | None] = mapped_column(DateTime)
    mfa_failures: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
