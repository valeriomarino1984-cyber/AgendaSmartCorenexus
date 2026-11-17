"""Accesso al database con contesto tenant obbligatorio (Row Level Security)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class UnsafeDatabaseRoleError(RuntimeError):
    """L'applicazione è connessa con un ruolo che aggirerebbe la RLS."""


class Database:
    def __init__(self, url: str, *, pool_size: int = 5, max_overflow: int = 10) -> None:
        self.engine = create_async_engine(
            url, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True
        )
        self._sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def tenant_session(self, tenant_id: UUID) -> AsyncIterator[AsyncSession]:
        """Transazione in cui la RLS espone soltanto le righe di `tenant_id`.

        `set_config(..., true)` equivale a SET LOCAL: il valore vale solo per questa
        transazione e non resta sulla connessione restituita al pool.
        """
        if not isinstance(tenant_id, UUID):
            raise TypeError("tenant_id deve essere un UUID")
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
            )
            yield session

    @asynccontextmanager
    async def system_session(self) -> AsyncIterator[AsyncSession]:
        """Transazione senza tenant: le tabelle tenant-specific risultano vuote (fail-closed).

        Da usare solo per tabelle globali (es. risoluzione slug → tenant).
        """
        async with self._sessionmaker() as session, session.begin():
            yield session

    async def ping(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def verify_role(self, expected_role: str) -> None:
        """Rifiuta l'avvio se il ruolo connesso può aggirare la RLS."""
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT current_user AS name, r.rolsuper, r.rolbypassrls "
                        "FROM pg_roles r WHERE r.rolname = current_user"
                    )
                )
            ).one()
        if row.name != expected_role:
            raise UnsafeDatabaseRoleError(
                f"connesso come '{row.name}', atteso il ruolo applicativo '{expected_role}'"
            )
        if row.rolsuper or row.rolbypassrls:
            raise UnsafeDatabaseRoleError(f"il ruolo '{row.name}' è superuser o ha BYPASSRLS")

    async def dispose(self) -> None:
        await self.engine.dispose()
