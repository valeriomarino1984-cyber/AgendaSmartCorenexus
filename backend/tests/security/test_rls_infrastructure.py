"""Isolamento multi-tenant a livello di database (criterio MVP 15)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import Settings
from app.core.db import Database, UnsafeDatabaseRoleError
from app.core.rls import enable_tenant_rls_sql, find_tenant_tables_without_rls

TENANT_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


@pytest.fixture
async def protected_table(owner_conn: AsyncConnection) -> AsyncIterator[str]:
    """Tabella tenant-specific creata dal ruolo proprietario, come farebbe una migrazione."""
    name = f"t_rls_{uuid.uuid4().hex[:8]}"
    await owner_conn.execute(text(f"CREATE TABLE {name} (tenant_id uuid NOT NULL, label text)"))
    for stmt in enable_tenant_rls_sql(name):
        await owner_conn.execute(text(stmt))
    # Il proprietario è anch'esso soggetto alla RLS (FORCE): inserisce i dati fissando il tenant.
    for tenant, label in ((TENANT_A, "a1"), (TENANT_A, "a2"), (TENANT_B, "b1")):
        await owner_conn.execute(
            text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)}
        )
        await owner_conn.execute(
            text(f"INSERT INTO {name} VALUES (:t, :l)"), {"t": str(tenant), "l": label}
        )
    await owner_conn.commit()
    yield name
    await owner_conn.execute(text(f"DROP TABLE {name}"))
    await owner_conn.commit()


async def _labels(db: Database, table: str, tenant: uuid.UUID | None) -> list[str]:
    ctx = db.tenant_session(tenant) if tenant else db.system_session()
    async with ctx as session:
        rows = await session.execute(text(f"SELECT label FROM {table} ORDER BY label"))
        return [r for (r,) in rows]


async def test_tenant_sees_only_own_rows(db: Database, protected_table: str) -> None:
    assert await _labels(db, protected_table, TENANT_A) == ["a1", "a2"]
    assert await _labels(db, protected_table, TENANT_B) == ["b1"]


async def test_context_does_not_leak_between_transactions(
    db: Database, protected_table: str
) -> None:
    # Stessa connessione fisica (pool_size=1): dopo una transazione del tenant A,
    # una sessione senza tenant non deve vedere nulla e non deve andare in errore.
    assert await _labels(db, protected_table, TENANT_A) == ["a1", "a2"]
    assert await _labels(db, protected_table, None) == []


async def test_cannot_write_rows_of_another_tenant(db: Database, protected_table: str) -> None:
    with pytest.raises(DBAPIError, match="row-level security"):
        async with db.tenant_session(TENANT_A) as session:
            await session.execute(
                text(f"INSERT INTO {protected_table} VALUES (:t, 'intruso')"),
                {"t": str(TENANT_B)},
            )
    assert await _labels(db, protected_table, TENANT_B) == ["b1"]


async def test_cannot_move_row_to_another_tenant(db: Database, protected_table: str) -> None:
    with pytest.raises(DBAPIError, match="row-level security"):
        async with db.tenant_session(TENANT_A) as session:
            await session.execute(
                text(f"UPDATE {protected_table} SET tenant_id = :t"), {"t": str(TENANT_B)}
            )


async def test_tenant_session_rejects_non_uuid(db: Database) -> None:
    with pytest.raises(TypeError):
        async with db.tenant_session("00000000-0000-0000-0000-00000000000a"):  # type: ignore[arg-type]
            pass


async def test_schema_has_no_unprotected_tenant_tables(owner_conn: AsyncConnection) -> None:
    """Guardia CI: ogni tabella con tenant_id creata dalle migrazioni deve avere la RLS."""
    assert await find_tenant_tables_without_rls(owner_conn) == []


async def test_checker_detects_unprotected_table(owner_conn: AsyncConnection) -> None:
    name = f"t_norls_{uuid.uuid4().hex[:8]}"
    await owner_conn.execute(text(f"CREATE TABLE {name} (tenant_id uuid)"))
    try:
        assert name in await find_tenant_tables_without_rls(owner_conn)
        await owner_conn.execute(text(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY"))
        # Abilitata ma non forzata e senza policy: ancora non conforme.
        assert name in await find_tenant_tables_without_rls(owner_conn)
    finally:
        await owner_conn.rollback()


async def test_app_role_cannot_bypass_rls(db: Database, settings: Settings) -> None:
    await db.verify_role(settings.app_db_role)  # non solleva
    async with db.system_session() as session:
        row = (
            await session.execute(
                text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            )
        ).one()
    assert row == (False, False)


async def test_app_role_cannot_create_tables(db: Database) -> None:
    with pytest.raises(DBAPIError, match="permission denied"):
        async with db.system_session() as session:
            await session.execute(text("CREATE TABLE t_forbidden (id int)"))


async def test_startup_refuses_wrong_role(settings: Settings) -> None:
    assert settings.migrations_database_url is not None
    wrong = Database(settings.migrations_database_url.get_secret_value())
    try:
        with pytest.raises(UnsafeDatabaseRoleError):
            await wrong.verify_role(settings.app_db_role)
    finally:
        await wrong.dispose()
