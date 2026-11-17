"""Accesso al database MySQL/MariaDB con contesto tenant obbligatorio."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core import tenancy  # noqa: F401  (registra i controlli ORM sull'isolamento)
from app.core.tenancy import TENANT_KEY


class UnsafeDatabaseUserError(RuntimeError):
    """L'applicazione è connessa con un utente che può modificare lo schema."""


# Privilegi che l'utente applicativo NON deve avere: lo schema si cambia solo con le migrazioni.
_FORBIDDEN_PRIVILEGES = (
    "ALL PRIVILEGES",
    "CREATE",
    "DROP",
    "ALTER",
    "INDEX",
    "REFERENCES",
    "TRIGGER",
    "CREATE VIEW",
    "CREATE ROUTINE",
    "ALTER ROUTINE",
    "EVENT",
    "GRANT OPTION",
    "SUPER",
    "FILE",
    "PROCESS",
    "SHUTDOWN",
    "RELOAD",
)
_GRANT_RE = re.compile(r"^GRANT (.+?) ON ", re.IGNORECASE)


def forbidden_privileges(grants: list[str]) -> set[str]:
    """Privilegi vietati presenti nelle righe di SHOW GRANTS (USAGE da solo è innocuo)."""
    found: set[str] = set()
    for grant in grants:
        if " WITH GRANT OPTION" in grant.upper():
            found.add("GRANT OPTION")
        match = _GRANT_RE.match(grant.strip())
        if not match:
            continue
        privileges = {p.strip().upper() for p in match.group(1).split(",")}
        found |= privileges & set(_FORBIDDEN_PRIVILEGES)
    return found


class Database:
    def __init__(
        self, url: str, *, pool_size: int = 5, max_overflow: int = 5, pool_recycle: int = 280
    ) -> None:
        self.engine = create_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,
            connect_args={"charset": "utf8mb4", "init_command": "SET time_zone = '+00:00'"},
        )
        self._sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def tenant_session(self, tenant_id: uuid.UUID) -> Iterator[Session]:
        """Transazione in cui l'ORM vede e scrive soltanto i dati di `tenant_id`."""
        if not isinstance(tenant_id, uuid.UUID):
            raise TypeError("tenant_id deve essere un UUID")
        with self._sessionmaker() as session, session.begin():
            session.info[TENANT_KEY] = tenant_id
            yield session

    @contextmanager
    def system_session(self) -> Iterator[Session]:
        """Transazione senza tenant: l'accesso ORM a dati degli studi è rifiutato (fail-closed)."""
        with self._sessionmaker() as session, session.begin():
            yield session

    def ping(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def verify_privileges(self) -> None:
        """Rifiuta l'avvio se l'utente applicativo può modificare lo schema."""
        with self.engine.connect() as conn:
            grants = [row[0] for row in conn.execute(text("SHOW GRANTS FOR CURRENT_USER()"))]
        found = forbidden_privileges(grants)
        if found:
            raise UnsafeDatabaseUserError(
                "l'utente applicativo ha privilegi sullo schema: " + ", ".join(sorted(found))
            )

    def dispose(self) -> None:
        self.engine.dispose()
