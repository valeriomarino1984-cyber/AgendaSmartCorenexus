"""Baseline: estensioni, funzione current_tenant_id(), privilegi del ruolo applicativo.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-17
"""

import os
import re
from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _app_role() -> str:
    role = os.environ.get("APP_DB_ROLE", "corenexus_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise ValueError(f"APP_DB_ROLE non valido: {role!r}")
    return role


def upgrade() -> None:
    role = _app_role()
    op.execute(
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
            RAISE EXCEPTION 'Ruolo applicativo "{role}" assente: eseguire infra/db/roles.sql';
          END IF;
        END $$;
        """
    )
    for ext in ("pgcrypto", "citext", "btree_gist"):
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")

    # Unico punto in cui si legge il tenant corrente. NULLIF: dopo una SET LOCAL
    # conclusa la variabile vale '' sulla connessione (non NULL) e il cast fallirebbe.
    op.execute(
        """
        CREATE FUNCTION current_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION current_tenant_id() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION current_tenant_id() TO {role}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    # Tabelle e sequenze create in futuro dal ruolo proprietario: DML per il ruolo app.
    # Le tabelle append-only (es. audit_logs) revocheranno UPDATE/DELETE esplicitamente.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {role}"
    )


def downgrade() -> None:
    role = _app_role()
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM {role}"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {role}"
    )
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {role}")
    op.execute("DROP FUNCTION current_tenant_id()")
    for ext in ("btree_gist", "citext", "pgcrypto"):
        op.execute(f"DROP EXTENSION IF EXISTS {ext}")
