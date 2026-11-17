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
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

log = structlog.get_logger("migrate")
BACKEND_DIR = Path(__file__).resolve().parents[2]
LOCK_NAME = "corenexus_agenda_migrations"


def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def migrate_on_startup() -> None:
    """Applica le migrazioni se AUTO_MIGRATE=1, poi toglie le credenziali DDL dall'ambiente.

    Passenger può ricaricare il file di avvio nello stesso processo: in quel caso le credenziali
    sono già state rimosse e le migrazioni (già applicate) vengono saltate senza errore.
    Se lo schema non fosse aggiornato, create_app() si rifiuta comunque di partire.
    """
    url = os.environ.pop("MIGRATIONS_DATABASE_URL", None)
    if os.environ.get("AUTO_MIGRATE") != "1":
        return
    if not url:
        log.warning("auto_migrate_skipped", reason="MIGRATIONS_DATABASE_URL non disponibile")
        return
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            got = conn.execute(text("SELECT GET_LOCK(:n, 120)"), {"n": LOCK_NAME}).scalar()
            if got != 1:
                raise RuntimeError("impossibile ottenere il lock delle migrazioni")
            try:
                cfg = alembic_config()
                # URL passato ad Alembic in memoria: non torna mai nell'ambiente del processo.
                cfg.attributes["database_url"] = url
                command.upgrade(cfg, "head")
            finally:
                conn.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": LOCK_NAME})
    finally:
        engine.dispose()
    log.info("migrations_applied")


def expected_revision() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()
