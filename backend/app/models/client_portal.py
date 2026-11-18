"""Area clienti: accesso con link via email (senza password) e sessioni dei clienti.

Tabelle di piattaforma, non di uno studio: lo stesso indirizzo email può essere cliente di più
studi. Contengono solo l'email e gli hash dei token; i dati dei clienti restano negli studi.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, utcnow


class ClientLoginToken(Base):
    """Link monouso inviato per email per entrare nell'area clienti."""

    __tablename__ = "client_login_tokens"
    __table_args__ = (Index("ix_client_login_tokens_email", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class ClientSession(Base):
    """Sessione dell'area clienti. Nel cookie c'è un token opaco, qui solo il suo hash."""

    __tablename__ = "client_sessions"
    __table_args__ = (Index("ix_client_sessions_email", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
