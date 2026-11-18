import os
import uuid

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

from app.core.config import Settings
from app.core.db import SchemaOutOfDateError
from app.core.migrate import alembic_config, migrate_on_startup
from app.main import create_app


def test_single_head() -> None:
    heads = ScriptDirectory.from_config(alembic_config()).get_heads()
    assert len(heads) == 1, f"più head Alembic: {heads}"


def test_migrations_are_reversible() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_auto_migrate_runs_and_drops_ddl_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # setenv con lo stesso valore: a fine test monkeypatch ripristina la variabile rimossa.
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", os.environ["MIGRATIONS_DATABASE_URL"])
    monkeypatch.setenv("AUTO_MIGRATE", "1")
    migrate_on_startup()
    # Dopo le migrazioni le credenziali DDL non sono più nell'ambiente del processo.
    assert "MIGRATIONS_DATABASE_URL" not in os.environ


def test_without_auto_migrate_credentials_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", os.environ["MIGRATIONS_DATABASE_URL"])
    monkeypatch.delenv("AUTO_MIGRATE", raising=False)
    migrate_on_startup()
    assert "MIGRATIONS_DATABASE_URL" not in os.environ


def test_reload_without_url_skips_instead_of_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passenger può ricaricare il file di avvio dopo che le credenziali sono già state rimosse."""
    monkeypatch.setenv("AUTO_MIGRATE", "1")
    monkeypatch.delenv("MIGRATIONS_DATABASE_URL")
    migrate_on_startup()  # non solleva


def test_app_refuses_outdated_schema(settings: Settings) -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    try:
        with pytest.raises(SchemaOutOfDateError, match="AUTO_MIGRATE"):
            create_app(settings)
    finally:
        command.upgrade(cfg, "head")


def test_catalog_migration_backfills_existing_studios(owner_engine: Engine) -> None:
    """Gli studi creati prima dello Sprint 2 ricevono sede principale e schede professionista."""
    cfg = alembic_config()
    command.downgrade(cfg, "0002_accounts")
    tenant, owner, secretary = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
    try:
        with owner_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, business_type, status, timezone, "
                    "neutral_messaging, created_at, updated_at) VALUES (:id, 'Studio Storico', "
                    ":slug, 'osteopata', 'active', 'Europe/Rome', 1, UTC_TIMESTAMP(), "
                    "UTC_TIMESTAMP())"
                ),
                {"id": tenant, "slug": f"storico-{tenant[:8]}"},
            )
            for uid, name, role in [
                (owner, "Ada Neri", "owner"),
                (secretary, "Bea Sala", "secretary"),
            ]:
                conn.execute(
                    text(
                        "INSERT INTO users (id, email, full_name, status, is_platform_admin, "
                        "created_at) VALUES (:id, :email, :name, 'active', 0, UTC_TIMESTAMP())"
                    ),
                    {"id": uid, "email": f"{uid}@example.com", "name": name},
                )
                conn.execute(
                    text(
                        "INSERT INTO tenant_users (id, tenant_id, user_id, role, status, "
                        "permissions, created_at) VALUES (:id, :t, :u, :r, 'active', '{}', "
                        "UTC_TIMESTAMP())"
                    ),
                    {"id": uuid.uuid4().hex, "t": tenant, "u": uid, "r": role},
                )
    finally:
        command.upgrade(cfg, "head")

    with owner_engine.connect() as conn:
        locations = conn.execute(
            text("SELECT name, is_default FROM locations WHERE tenant_id = :t"), {"t": tenant}
        ).all()
        professionals = conn.execute(
            text("SELECT name FROM professionals WHERE tenant_id = :t"), {"t": tenant}
        ).all()
    assert [tuple(r) for r in locations] == [("Sede principale", 1)]
    assert [r[0] for r in professionals] == ["Ada Neri"]  # la segreteria non ha una scheda
