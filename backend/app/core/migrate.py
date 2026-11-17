"""Migrazioni all'avvio, per gli hosting senza terminale (cPanel/Passenger).

Si usa l'utente con privilegi DDL (MIGRATIONS_DATABASE_URL) solo qui; poi la variabile viene
rimossa dall'ambiente del processo, così il codice dell'applicazione non può usarla.
Un lock di MySQL (GET_LOCK) evita che più processi Passenger migrino in contemporanea.
"""

from __future__ import annotations

import os
from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

log = structlog.get_logger("migrate")
BACKEND_DIR = Path(__file__).resolve().parents[2]
LOCK_NAME = "corenexus_agenda_migrations"


def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def migrate_on_startup() -> None:
    if os.environ.get("AUTO_MIGRATE") != "1":
        os.environ.pop("MIGRATIONS_DATABASE_URL", None)
        return
    url = os.environ.get("MIGRATIONS_DATABASE_URL")
    if not url:
        raise RuntimeError("AUTO_MIGRATE=1 ma MIGRATIONS_DATABASE_URL non è impostata")
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            got = conn.execute(text("SELECT GET_LOCK(:n, 120)"), {"n": LOCK_NAME}).scalar()
            if got != 1:
                raise RuntimeError("impossibile ottenere il lock delle migrazioni")
            try:
                command.upgrade(alembic_config(), "head")
                log.info("migrations_applied")
            finally:
                conn.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": LOCK_NAME})
    finally:
        engine.dispose()
        os.environ.pop("MIGRATIONS_DATABASE_URL", None)
