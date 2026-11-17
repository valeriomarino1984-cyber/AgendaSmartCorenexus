"""Infrastruttura Row Level Security condivisa da migrazioni e test.

Ogni tabella con colonna `tenant_id` deve avere RLS attiva e forzata e la policy
`tenant_isolation`, salvo esenzione motivata in RLS_EXEMPT_TABLES.
Il test `tests/security/test_rls_infrastructure.py` fa fallire la CI in caso contrario.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

POLICY_NAME = "tenant_isolation"
_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# tabella -> motivazione dell'esenzione (ogni voce va giustificata in code review)
RLS_EXEMPT_TABLES: dict[str, str] = {}


def _check_identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"identificatore non valido: {name!r}")
    return name


def enable_tenant_rls_sql(table: str) -> list[str]:
    t = _check_identifier(table)
    return [
        f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY {POLICY_NAME} ON {t} "
        "USING (tenant_id = current_tenant_id()) "
        "WITH CHECK (tenant_id = current_tenant_id())",
    ]


def disable_tenant_rls_sql(table: str) -> list[str]:
    t = _check_identifier(table)
    return [
        f"DROP POLICY IF EXISTS {POLICY_NAME} ON {t}",
        f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY",
    ]


_FIND_UNPROTECTED = text(
    """
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = :schema
      AND c.relkind IN ('r', 'p')
      AND EXISTS (
            SELECT 1 FROM pg_attribute a
            WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped)
      AND (NOT c.relrowsecurity
           OR NOT c.relforcerowsecurity
           OR NOT EXISTS (
                SELECT 1 FROM pg_policy p
                WHERE p.polrelid = c.oid AND p.polname = :policy))
    ORDER BY c.relname
    """
)


async def find_tenant_tables_without_rls(
    conn: AsyncConnection, schema: str = "public"
) -> list[str]:
    rows = await conn.execute(_FIND_UNPROTECTED, {"schema": schema, "policy": POLICY_NAME})
    return [name for (name,) in rows if name not in RLS_EXEMPT_TABLES]
