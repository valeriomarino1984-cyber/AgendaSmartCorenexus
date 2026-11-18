"""Limiti di frequenza su database (Redis non è disponibile su hosting condiviso)."""

from __future__ import annotations

import hashlib
import random
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.models import utcnow
from app.models.accounts import RateLimitEvent


def _key(scope: str, value: str) -> str:
    return hashlib.sha256(f"{scope}:{value}".encode()).hexdigest()


def count_recent(session: Session, scope: str, value: str, window: timedelta) -> int:
    since = utcnow() - window
    stmt = (
        select(func.count())
        .select_from(RateLimitEvent)
        .where(RateLimitEvent.key_hash == _key(scope, value), RateLimitEvent.created_at > since)
    )
    return int(session.scalar(stmt) or 0)


def record(session: Session, scope: str, value: str) -> None:
    session.add(RateLimitEvent(key_hash=_key(scope, value)))
    # Pulizia occasionale degli eventi vecchi, senza bisogno di un cron.
    if random.random() < 0.02:  # noqa: S311 - non serve casualità crittografica
        session.execute(
            delete(RateLimitEvent).where(RateLimitEvent.created_at < utcnow() - timedelta(days=2))
        )


def exceeded(session: Session, scope: str, value: str, limit: int, window: timedelta) -> bool:
    return count_recent(session, scope, value, window) >= limit


def hit(session: Session, scope: str, value: str, limit: int, window: timedelta) -> bool:
    """Registra un evento se il limite non è superato. Restituisce False se va bloccato."""
    if exceeded(session, scope, value, limit, window):
        return False
    record(session, scope, value)
    return True
